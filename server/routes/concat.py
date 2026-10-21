"""Concat (26.10.196): HTTP cho cầu nối ở máy nhà và trang quản lý.

Concat là trình dựng video (thay CapCut) có MCP server sẵn trong app. MinMin trên VPS không gọi
thẳng được máy nhà, nên cầu nối `apps/concat/cau/concat_cau.py` ở máy nhà tự kết nối RA ngoài,
nhận lời gọi công cụ, chuyển vào `concat --mcp` rồi gửi kết quả lên. Kho ở `server/concat_cau.py`.

Hai nhóm đường:

1. `/concat/may/...` - CHO CẦU NỐI, miễn cổng đăng nhập (không có cookie). Tự xác thực bằng header
   `x-minmin-may` (token máy, trừ đường ghép dùng mã 6 số). Chống dò như Đội Social.
     POST /concat/may/ghep              {ma, ten, phien_ban} -> {may_id, token}
     POST /concat/may/nhip              {concat_ok, loi_concat, concat, cong_cu, thu_muc_lam_viec, phien_ban}
     GET  /concat/may/viec?cho=25       long-poll: việc kế tiếp hoặc {viec: null}
     GET  /concat/may/tep/{id}/{so}     tải tệp bộ não đính kèm việc (video/ảnh để nhập)
     POST /concat/may/tai-len/{id}?ten= thân là byte tệp (việc lay_tep)
     POST /concat/may/ket-qua/{id}      {ok, ket_qua, loi}

2. `/apps/concat/...` - trang quản lý, cần đăng nhập + app đã mở khoá (Kết nối ngoài).
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import time
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

import concat_cau
import giay_phep
import routes.ket_noi_ngoai as knn

APP_ID = "concat"
GOC = "/apps/concat"
TIEN_TO_MAY = "/concat/may/"              # main._auth_guard miễn đăng nhập cho tiền tố này (GET/POST)
APP_DIR = Path(__file__).resolve().parents[2] / "apps" / "concat"
WEB_DIR = APP_DIR / "web"
CAU_DIR = APP_DIR / "cau"
WEB_FILES = {"index.html", "app.js", "styles.css"}
CAU_BO_QUA = {"cau-noi.json", "cau-noi.log"}
THAN_TOI_DA = concat_cau.KET_QUA_TOI_DA + 1_000_000
_SAI: dict = {}
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600

# main.py đưa vào: (brain) -> thư mục gốc bộ não, để lưu tệp lấy về máy nhà.
_goc_brain: Optional[Callable[[str], str]] = None


def ly_do_chan() -> Optional[str]:
    if not giay_phep.da_mo(APP_ID):
        return "Concat chưa được mở khoá. Vào Kết nối & Khách > Kết nối ngoài để nhập mã kích hoạt."
    if not knn.da_dong_y("chung"):
        return "Cần đồng ý Điều khoản sử dụng MinMin trước (trang Kết nối ngoài)."
    return None


def _loi(msg, ma: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(msg)}, status_code=ma)


def _chan() -> Optional[JSONResponse]:
    ly = ly_do_chan()
    return _loi(ly, 403) if ly else None


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


def _trang_khoa(ly: str) -> HTMLResponse:
    import html
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                        f"<body style='font-family:system-ui;max-width:560px;margin:15vh auto;padding:0 20px'>"
                        f"<h2>Concat</h2><p>{html.escape(ly)}</p></body>", status_code=403)


def goi_cau_zip() -> bytes:
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(CAU_DIR.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc" or p.name in CAU_BO_QUA:
                continue
            z.write(str(p), "MinMinConcat/" + str(p.relative_to(CAU_DIR)).replace("\\", "/"))
    return buf.getvalue()


def thu_muc_nhan(brain: str = "") -> Path:
    """Nơi lưu tệp lấy từ máy nhà: <brain>/attachments/concat (rơi về STATE_DIR nếu chưa nối brain)."""
    goc = None
    if _goc_brain:
        try:
            goc = _goc_brain(brain or "")
        except Exception:
            goc = None
    if goc:
        return Path(goc) / "attachments" / "concat"
    return concat_cau.thu_muc() / "tep"


def register(app: FastAPI, goc_brain: Optional[Callable[[str], str]] = None) -> None:
    global _goc_brain
    _goc_brain = goc_brain
    A = GOC + "/api"

    # ---------------------------------------------------------------- cầu nối (không cookie)
    async def _may(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return None, JSONResponse({"error": "sai token quá nhiều lần, thử lại sau 10 phút"}, status_code=429)
        m = concat_cau.may_theo_token(str(request.headers.get("x-minmin-may") or ""))
        if not m:
            _ghi_sai(ip)
            return None, JSONResponse({"error": "unauthorized", "concat": "token máy sai hoặc máy đã bị gỡ"},
                                      status_code=401)
        if ly_do_chan():
            return None, JSONResponse({"error": ly_do_chan()}, status_code=403)
        return m, None

    async def _json(request: Request, toi_da: int = THAN_TOI_DA) -> dict:
        body = await request.body()
        if len(body) > toi_da:
            raise ValueError("thân yêu cầu quá lớn")
        try:
            raw = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("thân yêu cầu không phải JSON hợp lệ")
        if not isinstance(raw, dict):
            raise ValueError("JSON phải là object")
        return raw

    @app.post(TIEN_TO_MAY + "ghep")
    async def cc_may_ghep(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return JSONResponse({"error": "sai mã quá nhiều lần, thử lại sau 10 phút"}, status_code=429)
        if ly_do_chan():
            return _loi(ly_do_chan(), 403)
        try:
            d = await _json(request, 20_000)
            kq = concat_cau.ghep(d.get("ma"), d.get("ten"), d.get("phien_ban") or "")
        except ValueError as e:
            _ghi_sai(ip)
            return _loi(e, 400)
        return {"ok": True, **kq}

    @app.post(TIEN_TO_MAY + "nhip")
    async def cc_may_nhip(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request, 2_000_000)
        except ValueError as e:
            return _loi(e)
        concat_cau.nhip(m["id"], d.get("concat_ok"), d.get("loi_concat") or "",
                        d.get("concat") if isinstance(d.get("concat"), dict) else None,
                        d.get("cong_cu") if isinstance(d.get("cong_cu"), list) else None,
                        d.get("thu_muc_lam_viec") or "", d.get("phien_ban") or "")
        return {"ok": True}

    @app.get(TIEN_TO_MAY + "viec")
    async def cc_may_viec(request: Request, cho: int = Query(25)):
        m, err = await _may(request)
        if err:
            return err
        han = time.monotonic() + max(0, min(int(cho or 0), 30))
        while True:
            v = concat_cau.nhan_viec(m["id"], 0)
            if v or time.monotonic() >= han:
                return {"ok": True, "viec": v}
            await asyncio.sleep(min(0.25, max(0.05, han - time.monotonic())))
            if await request.is_disconnected():
                return {"ok": True, "viec": None}

    @app.get(TIEN_TO_MAY + "tep/{vid}/{so}")
    async def cc_may_tep(vid: int, so: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        p = concat_cau.duong_tep(vid, so, m["id"])
        if not p:
            return _loi("không có tệp này cho máy này", 404)
        return FileResponse(str(p), filename=p.name)

    @app.post(TIEN_TO_MAY + "tai-len/{vid}")
    async def cc_may_tai_len(vid: int, request: Request, ten: str = Query("tep")):
        m, err = await _may(request)
        if err:
            return err
        buf = bytearray()
        async for phan in request.stream():
            buf.extend(phan)
            if len(buf) > concat_cau.TEP_LEN_TOI_DA:
                return _loi("tệp quá lớn (trên 1,5 GB)", 413)
        v = concat_cau.lay_viec(vid)
        brain = ""
        if v:
            brain = str((v.get("tham_so") or {}).get("_brain") or "")
        try:
            dich_goc = thu_muc_nhan(brain)
            dich = await asyncio.to_thread(concat_cau.luu_tep_len, vid, m["id"], ten, bytes(buf), dich_goc)
        except ValueError as e:
            return _loi(e, 403)
        rel = dich.name
        try:
            rel = str(dich.relative_to(dich_goc.parent.parent)).replace("\\", "/")
        except ValueError:
            pass
        return {"ok": True, "duong_dan": rel}

    @app.post(TIEN_TO_MAY + "ket-qua/{vid}")
    async def cc_may_ket_qua(vid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
        except ValueError as e:
            return _loi(e)
        ok = concat_cau.ghi_ket_qua(vid, m["id"], bool(d.get("ok")), d.get("ket_qua"), str(d.get("loi") or ""))
        if not ok:
            return _loi("việc không thuộc máy này hoặc đã xong", 403)
        return {"ok": True}

    # ---------------------------------------------------------------- trang quản lý (đăng nhập)
    @app.get(GOC)
    def cc_goc():
        return RedirectResponse(GOC + "/", status_code=307)

    @app.get(GOC + "/")
    def cc_trang():
        ly = ly_do_chan()
        if ly:
            return _trang_khoa(ly)
        return FileResponse(str(WEB_DIR / "index.html"), headers={"Cache-Control": "no-cache"})

    @app.get(GOC + "/{ten}")
    def cc_tinh(ten: str):
        if ten not in WEB_FILES or ten == "index.html":
            return _loi("Không có tệp này.", 404)
        if ly_do_chan():
            return _loi(ly_do_chan(), 403)
        return FileResponse(str(WEB_DIR / ten), headers={"Cache-Control": "no-cache"})

    @app.get(A + "/trang-thai")
    def cc_trang_thai():
        if (c := _chan()):
            return c
        tt = concat_cau.trang_thai()
        for m in tt["may"]:
            m["so_cong_cu"] = len(m.pop("cong_cu", []) or [])
        return {"ok": True, **tt, "viec": concat_cau.ds_viec(20)}

    @app.post(A + "/ma-ghep")
    def cc_ma_ghep():
        if (c := _chan()):
            return c
        return {"ok": True, "ma": concat_cau.tao_ma_ghep(), "song_phut": concat_cau.MA_SONG // 60}

    @app.delete(A + "/may/{may_id}")
    def cc_go_may(may_id: str):
        if (c := _chan()):
            return c
        if not re.fullmatch(r"c[0-9a-f]{8}", may_id or ""):
            return _loi("mã máy không hợp lệ")
        return {"ok": concat_cau.go_may(may_id)}

    @app.get(A + "/bo-cai.zip")
    def cc_bo_cai():
        if (c := _chan()):
            return c
        return Response(goi_cau_zip(), media_type="application/zip",
                        headers={"Content-Disposition": "attachment; filename=MinMinConcat.zip"})
