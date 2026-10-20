"""Đội Social (26.10.185): HTTP cho máy ở nhà (worker) và trang quản lý.

Hai nhóm đường:

1. `/doi-social/may/...` - CHO WORKER, miễn cổng đăng nhập (không có cookie). Tự xác thực bằng
   header `x-minmin-may` (token máy, trừ đường ghép dùng mã 6 số). Chống dò như Mắt Nhà.
     POST /doi-social/may/ghep            {ma, ten, driver, phien_ban} -> {may_id, token}
     POST /doi-social/may/nhip            {nick:[...], driver_ok, loi_driver, phien_ban}
     GET  /doi-social/may/viec?cho=25     long-poll: trả việc kế tiếp hoặc {viec:null}
     GET  /doi-social/may/tep/{id}/{luu}  tải ảnh/video đính kèm của việc
     POST /doi-social/may/ket-qua/{id}    {ok, thong_diep, buoc, anh(base64 png)}

2. Còn lại - cần đăng nhập + app đã mở khoá (Kết nối ngoài) như các app khác.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

import doi_social
import giay_phep
import routes.ket_noi_ngoai as knn

APP_ID = "doi_social"
GOC = "/apps/doi-social"
TIEN_TO_MAY = "/doi-social/may/"          # main._auth_guard miễn đăng nhập cho tiền tố này
APP_DIR = Path(__file__).resolve().parents[2] / "apps" / "doi-social"
WEB_DIR = APP_DIR / "web"
WORKER_DIR = APP_DIR / "worker"
WEB_FILES = {"index.html", "app.js", "styles.css"}
THAN_TOI_DA = 12_000_000                  # ảnh chụp toàn trang base64 + bước
_SAI: dict = {}
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600
_CHO: dict = {}                           # may_id -> asyncio.Event (đánh thức long-poll)


@dataclass
class DoiSocialDeps:
    # Báo chủ qua Telegram/hòm thư. (viec, su_kien) với su_kien in {"cho_duyet","xong","loi"}.
    bao: Optional[Callable[[dict, str], Awaitable]] = None


def ly_do_chan() -> Optional[str]:
    if not giay_phep.da_mo(APP_ID):
        return "Đội Social chưa được mở khoá. Vào Kết nối & Khách > Kết nối ngoài để nhập mã kích hoạt."
    if not knn.da_dong_y("chung"):
        return "Cần đồng ý Điều khoản sử dụng MinMin trước (trang Kết nối ngoài)."
    return None


def _loi(msg, ma: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(msg)}, status_code=ma)


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _bi_chan(ip: str) -> bool:
    now = time.time()
    ds = [t for t in _SAI.get(ip, []) if now - t < _SAI_CUA_SO]
    _SAI[ip] = ds
    if len(_SAI) > 5000:
        _SAI.clear()
    return len(ds) >= _SAI_TOI_DA


def _ghi_sai(ip: str) -> None:
    _SAI.setdefault(ip, []).append(time.time())


def danh_thuc(may_id: str) -> None:
    """Có việc mới cho máy -> nhả long-poll đang chờ ngay, khỏi đợi hết 25 giây."""
    ev = _CHO.get(may_id)
    if not ev:
        return
    try:
        asyncio.get_running_loop()
        ev.set()
    except RuntimeError:
        if _VONG and _VONG[0].is_running():
            _VONG[0].call_soon_threadsafe(ev.set)


_VIEC_BAO: set = set()
_DEPS = DoiSocialDeps()      # register() thay bằng deps thật; plugin dùng chung qua tao_viec_va_bao


_VONG: list = []             # vòng sự kiện của server, nhớ lúc khởi động


def _bao_nen(deps: DoiSocialDeps, viec: dict, su_kien: str) -> None:
    """Báo chủ ở nền, không bắt người gọi chờ Telegram. Gọi được từ cả hai phía: trong vòng sự
    kiện (endpoint async) thì tạo task; từ một luồng khác (tool plugin đồng bộ có thể chạy
    trong to_thread) thì đẩy sang vòng của server. Không có vòng nào thì ghi log, KHÔNG lặng
    lẽ bỏ - bài chờ duyệt mà chủ không được báo là bài nằm im mãi."""
    if not deps.bao or not viec:
        return

    async def _chay():
        try:
            await deps.bao(viec, su_kien)
        except Exception as ex:
            print(f"[doi-social] báo chủ lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
    try:
        vong = asyncio.get_running_loop()
    except RuntimeError:
        vong = None
    if vong is not None:
        t = vong.create_task(_chay())
        _VIEC_BAO.add(t)
        t.add_done_callback(_VIEC_BAO.discard)
    elif _VONG and _VONG[0].is_running():
        asyncio.run_coroutine_threadsafe(_chay(), _VONG[0])
    else:
        print(f"[doi-social] không có vòng sự kiện để báo việc #{viec.get('id')} ({su_kien})", file=sys.stderr)


def tao_viec_va_bao(**kw) -> dict:
    """Dùng chung cho trang web và plugin: tạo việc, rồi xin duyệt hoặc đánh thức máy."""
    v = doi_social.tao_viec(**kw)
    if v["trang_thai"] == "cho_duyet":
        _bao_nen(_DEPS, v, "cho_duyet")
    else:
        danh_thuc(v["may_id"])
    return v


def duyet_va_bao(vid, dong_y: bool) -> dict:
    v = doi_social.duyet(vid, dong_y)
    if dong_y:
        danh_thuc(v["may_id"])
    return v


def _goi_worker_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(WORKER_DIR.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                z.write(str(p), "MinMinWorker/" + str(p.relative_to(WORKER_DIR)).replace("\\", "/"))
    return buf.getvalue()


def register(app: FastAPI, deps: DoiSocialDeps) -> None:
    global _DEPS
    _DEPS = deps

    @app.on_event("startup")
    async def _nho_vong():
        _VONG[:] = [asyncio.get_running_loop()]
    # ---------------------------------------------------------------- worker (không cookie)
    async def _may(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return None, JSONResponse({"error": "sai token quá nhiều lần, thử lại sau 10 phút"}, status_code=429)
        m = doi_social.may_theo_token(str(request.headers.get("x-minmin-may") or ""))
        if not m:
            _ghi_sai(ip)
            return None, JSONResponse({"error": "unauthorized", "doi_social": "token máy sai hoặc máy đã bị gỡ"},
                                      status_code=401)
        if ly_do_chan():
            return None, JSONResponse({"error": ly_do_chan()}, status_code=403)
        return m, None

    async def _json(request: Request) -> dict:
        body = await request.body()
        if len(body) > THAN_TOI_DA:
            raise ValueError("thân yêu cầu quá lớn")
        raw = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(raw, dict):
            raise ValueError("JSON phải là object")
        return raw

    @app.post("/doi-social/may/ghep")
    async def ds_may_ghep(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return JSONResponse({"error": "sai mã quá nhiều lần, thử lại sau 10 phút"}, status_code=429)
        if ly_do_chan():
            return _loi(ly_do_chan(), 403)
        try:
            d = await _json(request)
            kq = doi_social.ghep(d.get("ma"), d.get("ten"), d.get("driver") or "gpm", d.get("phien_ban") or "")
        except ValueError as e:
            _ghi_sai(ip)
            return _loi(e, 400)
        return {"ok": True, **kq}

    @app.post("/doi-social/may/nhip")
    async def ds_may_nhip(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
        except ValueError as e:
            return _loi(e)
        nick = d.get("nick")
        doi_social.nhip(m["id"], nick if isinstance(nick, list) else None,
                        d.get("driver_ok"), d.get("loi_driver") or "", d.get("phien_ban") or "")
        return {"ok": True, "gioi_han": doi_social.gioi_han()}

    @app.get("/doi-social/may/viec")
    async def ds_may_viec(request: Request, cho: int = Query(25)):
        m, err = await _may(request)
        if err:
            return err
        doi_social.nhip(m["id"])
        han = time.monotonic() + max(0, min(int(cho or 0), 30))
        while True:
            v = doi_social.nhan_viec(m["id"])
            if v or time.monotonic() >= han:
                return {"ok": True, "viec": v}
            ev = _CHO.setdefault(m["id"], asyncio.Event())
            ev.clear()
            try:
                await asyncio.wait_for(ev.wait(), timeout=min(5.0, max(0.1, han - time.monotonic())))
            except asyncio.TimeoutError:
                pass
            if await request.is_disconnected():
                return {"ok": True, "viec": None}

    @app.get("/doi-social/may/tep/{vid}/{luu}")
    async def ds_may_tep(vid: int, luu: str, request: Request):
        m, err = await _may(request)
        if err:
            return err
        v = doi_social.lay_viec(vid)
        if not v or v["may_id"] != m["id"]:
            return _loi("không có việc này", 404)
        p = doi_social.duong_tep(vid, luu)
        if not p:
            return _loi("không có tệp", 404)
        return FileResponse(str(p))

    @app.post("/doi-social/may/ket-qua/{vid}")
    async def ds_may_ket_qua(vid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            anh = base64.b64decode(d.get("anh") or "") if d.get("anh") else b""
            v = doi_social.ghi_ket_qua(vid, m["id"], bool(d.get("ok")), d.get("thong_diep") or "",
                                       d.get("buoc") if isinstance(d.get("buoc"), list) else [], anh)
        except (ValueError, TypeError) as e:
            return _loi(e)
        _bao_nen(deps, v, "xong" if v["trang_thai"] == "xong" else "loi")
        return {"ok": True}

    # ---------------------------------------------------------------- trang quản lý (đăng nhập)
    def _chan():
        ly = ly_do_chan()
        return _loi(ly, 403) if ly else None

    @app.get(GOC + "/")
    def ds_trang():
        ly = ly_do_chan()
        if ly:
            import html
            return HTMLResponse("<!doctype html><meta charset=utf-8><body style='font-family:system-ui;"
                                f"max-width:560px;margin:15vh auto;padding:0 20px'><h2>Đội Social</h2>"
                                f"<p>{html.escape(ly)}</p></body>", status_code=403)
        return FileResponse(str(WEB_DIR / "index.html"), media_type="text/html",
                            headers={"Cache-Control": "no-cache"})

    @app.get(GOC + "/{ten}")
    def ds_tinh(ten: str):
        if ten not in WEB_FILES:
            return _loi("không có", 404)
        return FileResponse(str(WEB_DIR / ten), headers={"Cache-Control": "no-cache"})

    @app.get("/doi-social/trang-thai")
    def ds_trang_thai():
        c = _chan()
        if c:
            return c
        return {"ok": True, "may": doi_social.ds_may(), "nick": doi_social.ds_nick(),
                "viec": doi_social.ds_viec(30), "gioi_han": doi_social.gioi_han(),
                "ky_nang": doi_social.KY_NANG}

    @app.post("/doi-social/ma-ghep")
    def ds_ma_ghep():
        c = _chan()
        if c:
            return c
        return {"ok": True, "ma": doi_social.tao_ma_ghep(), "song_phut": doi_social.MA_SONG // 60}

    @app.delete("/doi-social/may/{may_id}")
    def ds_go_may(may_id: str):
        # Cùng tiền tố với worker nhưng là DELETE: _auth_guard chỉ miễn GET/POST của tiền tố
        # này, nên đường gỡ máy vẫn phải đăng nhập.
        c = _chan()
        if c:
            return c
        return {"ok": doi_social.go_may(may_id)}

    @app.post("/doi-social/gioi-han")
    async def ds_gioi_han(request: Request):
        c = _chan()
        if c:
            return c
        d = await request.json()
        return {"ok": True, "gioi_han": doi_social.dat_gioi_han(d.get("bai_moi_ngay"), d.get("nghi_phut"))}

    @app.post("/doi-social/viec")
    async def ds_tao_viec(request: Request):
        c = _chan()
        if c:
            return c
        d = await request.json()
        try:
            v = tao_viec_va_bao(ky_nang=d.get("ky_nang") or "fb_dang_bai", nick=d.get("nick") or "",
                                noi_dung=d.get("noi_dung") or "", noi_dang=d.get("noi_dang") or "",
                                can_duyet=bool(d.get("can_duyet", True)), nguon="web")
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "viec": v}

    @app.post("/doi-social/viec/{vid}/duyet")
    async def ds_duyet(vid: int, request: Request):
        c = _chan()
        if c:
            return c
        d = await request.json()
        try:
            return {"ok": True, "viec": duyet_va_bao(vid, bool(d.get("dong_y")))}
        except ValueError as e:
            return _loi(e)

    @app.get("/doi-social/anh/{vid}.png")
    def ds_anh(vid: int):
        c = _chan()
        if c:
            return c
        p = doi_social.duong_anh(vid)
        return FileResponse(str(p), media_type="image/png") if p else _loi("chưa có ảnh", 404)

    @app.get("/doi-social/tai-worker.zip")
    def ds_tai_worker():
        c = _chan()
        if c:
            return c
        return Response(_goi_worker_zip(), media_type="application/zip",
                        headers={"Content-Disposition": "attachment; filename=MinMinWorker.zip"})
