"""Đội Social (26.10.187): HTTP cho máy ở nhà (worker) và trang quản lý.

Hợp đồng đầy đủ: docs/doi-social/KIEN-TRUC.md mục 3 và 7.

Hai nhóm đường:

1. `/doi-social/may/...` - CHO WORKER, miễn cổng đăng nhập (không có cookie). Tự xác thực bằng
   header `x-minmin-may` (token máy, trừ đường ghép dùng mã 6 số). Chống dò như Mắt Nhà.
   Mọi đường theo viec_id đều kiểm việc thuộc đúng máy gọi.
     POST /doi-social/may/ghep            {ma, ten, driver, phien_ban} -> {may_id, token}
     POST /doi-social/may/nhip            {nick:[...], driver_ok, loi_driver, phien_ban, kich_ban, song_song}
     GET  /doi-social/may/viec?cho=25     long-poll: trả việc kế tiếp hoặc {viec:null}
     GET  /doi-social/may/tep/{id}/{luu}  tải ảnh/video đính kèm của việc
     POST /doi-social/may/ket-qua/{id}    {ok, thong_diep, buoc, anh(base64 png), dem}
     ... và các đường mới của 26.10.187 (su-kien, buoc, dung, ai, ban-nhap, kho, nhom-fb,
     da-tuong-tac, hoi-thoai, bai-doi-da-dang, ban-cap-nhat).

2. Còn lại - cần đăng nhập + app đã mở khoá (Kết nối ngoài) như các app khác.

Quy ước trả về cho trang web: `{ok: true, ...}`. Danh sách nằm ở khoá `muc` (phân trang thêm
`tong`, `trang`); một đối tượng nằm ở khoá theo tên của nó (`dot`, `lich`, `ban_nhap`, ...).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.datastructures import UploadFile

import doi_social
import doi_social_bo_nao
import doi_social_v2 as v2
import giay_phep
import routes.ket_noi_ngoai as knn

APP_ID = "doi_social"
GOC = "/apps/doi-social"
TIEN_TO_MAY = "/doi-social/may/"          # main._auth_guard miễn đăng nhập cho tiền tố này
APP_DIR = Path(__file__).resolve().parents[2] / "apps" / "doi-social"
WEB_DIR = APP_DIR / "web"
WORKER_DIR = APP_DIR / "worker"
WEB_FILES = {"index.html", "app.js", "styles.css"}     # giữ cho mã cũ tham chiếu; nay phục vụ theo mẫu tên
TEN_TINH = re.compile(r"^[a-z0-9][a-z0-9._-]*\.(html|js|css|svg|png|webp|json)$")
THU_MUC_TINH = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
KIEU_TINH = {"html": "text/html", "js": "text/javascript", "css": "text/css", "svg": "image/svg+xml",
             "png": "image/png", "webp": "image/webp", "json": "application/json"}
WORKER_BO_QUA = {"worker.json", "worker.log"}           # cấu hình + nhật ký riêng của từng máy
THAN_TOI_DA = 12_000_000                  # ảnh chụp toàn trang base64 + bước
THAN_NHAP_TOI_DA = 80_000_000             # nháp kèm ảnh/video dạng base64
THAN_KQ_TOI_DA = 15_000_000               # tệp kết quả CSV 10MB dạng base64
ANH_AI_TOI_DA = 4
ANH_AI_BYTE = 5 * 1024 * 1024
MUC_DICH_AI = {"cham_bai", "viet_binh_luan", "tra_loi_binh_luan", "tra_loi_tin_nhan", "tra_loi_cau_hoi_nhom",
               "viet_bai", "chon_nhom"}
NHIP_NEN = 30.0
# Vòng nền lịch hẹn: tắt bằng JAVIS_DOI_SOCIAL_VONG=0 (test) hoặc đặt VONG_NEN_BAT = False trước register.
VONG_NEN_BAT = os.environ.get("JAVIS_DOI_SOCIAL_VONG", "1") != "0"
_SAI: dict = {}
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600
_CHO: dict = {}                           # may_id -> asyncio.Event (đánh thức long-poll)
_NEN: list = []                           # task vòng nền đang chạy
_PB_WORKER: dict = {}                     # cache phiên bản Worker theo mtime


@dataclass
class DoiSocialDeps:
    # Báo chủ qua Telegram/hòm thư. (viec, su_kien) với su_kien in {"cho_duyet","xong","loi"}.
    bao: Optional[Callable[[dict, str], Awaitable]] = None
    # 26.10.187 (mục 7 hợp đồng). Mọi trường mặc định None: main.py chưa nối thì app vẫn chạy,
    # chỉ các tính năng AI trả lỗi rõ ràng.
    goi_ai: Optional[Callable[[str, list], Awaitable[str]]] = None       # (prompt, ảnh) -> chữ
    thong_tin_ai: Optional[Callable[[], dict]] = None                    # -> {engine, mo_hinh, nhin_anh, san_sang}
    bao_ke_hoach: Optional[Callable[[dict], Awaitable]] = None           # gửi kế hoạch + nút dsk:<id>:1|0
    bao_su_kien: Optional[Callable[[str, str], Awaitable]] = None        # (tiêu đề, nội dung) -> hòm thư + Telegram
    co_telegram: Optional[Callable[[], bool]] = None                     # Telegram đã nối chưa (huy hiệu Tổng quan)
    goc_brain: Optional[Callable[[], str]] = None                        # thư mục bộ não MinMin (wiki, memory)


def ly_do_chan() -> Optional[str]:
    if not giay_phep.da_mo(APP_ID):
        return "Đội Social chưa được mở khoá. Vào Kết nối & Khách > Kết nối ngoài để nhập mã kích hoạt."
    if not knn.da_dong_y("chung"):
        return "Cần đồng ý Điều khoản sử dụng MinMin trước (trang Kết nối ngoài)."
    return None


def _loi(msg, ma: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(msg)}, status_code=ma)


def _loi_v(e: Exception) -> JSONResponse:
    """ValueError từ kho -> 403 nếu là sai quyền (việc của máy khác), còn lại 400."""
    s = str(e)
    return _loi(s, 403 if "không thuộc máy này" in s or "không do việc của máy này" in s else 400)


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


def _danh_thuc_tat_ca() -> None:
    for k in list(_CHO):
        danh_thuc(k)


_VIEC_BAO: set = set()
_DEPS = DoiSocialDeps()      # register() thay bằng deps thật; plugin dùng chung qua tao_viec_va_bao


_VONG: list = []             # vòng sự kiện của server, nhớ lúc khởi động


def _chay_nen(coro_fn, mo_ta: str) -> None:
    """Chạy một coroutine ở nền (trong vòng hiện tại, hoặc đẩy sang vòng của server khi gọi từ
    luồng khác). Không có vòng nào thì ghi log, KHÔNG lặng lẽ bỏ."""
    async def _chay():
        try:
            await coro_fn()
        except Exception as ex:
            print(f"[doi-social] {mo_ta} lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
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
        print(f"[doi-social] không có vòng sự kiện để {mo_ta}", file=sys.stderr)


def _bao_nen(deps: DoiSocialDeps, viec: dict, su_kien: str) -> None:
    """Báo chủ ở nền, không bắt người gọi chờ Telegram. Gọi được từ cả hai phía: trong vòng sự
    kiện (endpoint async) thì tạo task; từ một luồng khác (tool plugin đồng bộ có thể chạy
    trong to_thread) thì đẩy sang vòng của server. Không có vòng nào thì ghi log, KHÔNG lặng
    lẽ bỏ - bài chờ duyệt mà chủ không được báo là bài nằm im mãi."""
    if not deps.bao or not viec:
        return
    _chay_nen(lambda: deps.bao(viec, su_kien), f"báo chủ việc #{viec.get('id')} ({su_kien})")


def _xa_bao() -> None:
    """Gửi các thông báo kho đã xếp hàng (đợt xong, nick bị đăng xuất, khách cần trả lời tay...)."""
    fn = _DEPS.bao_su_kien
    if not fn:
        return
    for tieu, than in v2.lay_bao():
        _chay_nen(lambda t=tieu, b=than: fn(t, b), f"báo '{tieu}'")


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


# ---------------------------------------------------------------- hàm dùng chung (plugin, main)

def tao_dot_va_chay(**kw) -> dict:
    """Tạo đợt chạy (v2.tao_dot) rồi đánh thức các máy có việc. Raise ValueError."""
    dot = v2.tao_dot(**kw)
    for m in {x["may_id"] for x in dot.get("viec") or []}:
        danh_thuc(m)
    return dot


def duyet_ke_hoach_va_chay(kid, dong_y: bool) -> dict:
    kh = v2.duyet_ke_hoach(kid, dong_y)
    if dong_y:
        _danh_thuc_tat_ca()
    _xa_bao()
    return kh


def _loi_ai() -> str:
    return ("Đội Social chưa nối được bộ não MinMin (AI). Kiểm tra trang Mô hình đã chọn bộ não và "
            "cập nhật MinMin lên bản mới nhất.")


def _kt_ai(sp, cau_hoi: str = ""):
    """Kiến thức sản phẩm cho AI, đã nối thêm tri thức từ bộ não MinMin (wiki, ghi chú gắn tay)."""
    kt = v2.kien_thuc_cho_ai(sp)
    try:
        return doi_social_bo_nao.bo_sung(kt, cau_hoi)
    except Exception as ex:
        print(f"[doi-social] bộ não lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
        return kt


def _ngu_canh_ai(du_lieu: dict) -> str:
    """Chữ ngữ cảnh để tự tra bộ não: nội dung bài, bình luận, tin nhắn cuối của khách, câu hỏi nhóm."""
    if not isinstance(du_lieu, dict):
        return ""
    phan = []
    bai = du_lieu.get("bai")
    if isinstance(bai, dict):
        phan.append(str(bai.get("chu") or "")[:300])
    bl = du_lieu.get("binh_luan")
    if isinstance(bl, dict):
        phan.append(str(bl.get("chu") or "")[:300])
    ht = du_lieu.get("hoi_thoai")
    if isinstance(ht, dict):
        tin = [t for t in (ht.get("tin") or []) if isinstance(t, dict) and t.get("tu") == "khach"]
        if tin:
            phan.append(str(tin[-1].get("noi_dung") or "")[:300])
    ch = du_lieu.get("cau_hoi")
    if isinstance(ch, list):
        phan.append(" ".join(str(x) for x in ch)[:300])
    if du_lieu.get("yeu_cau"):
        phan.append(str(du_lieu["yeu_cau"])[:300])
    return " ".join(p for p in phan if p)


async def tro_ly_tra_loi(tin: str, phien: str = "", nguon: str = "web", chat_id: str = "") -> dict:
    """Một lượt Trợ lý AI: gọi AI với bối cảnh đội, lưu lịch sử, lưu kế hoạch (CHỜ DUYỆT, không
    tự chạy), báo Telegram kèm nút Duyệt nếu yêu cầu đến từ Telegram. Raise ValueError."""
    tin = str(tin or "").strip()
    if not tin:
        raise ValueError("tin nhắn trống")
    if len(tin) > 4000:
        raise ValueError("tin nhắn quá dài (tối đa 4000 ký tự)")
    if not _DEPS.goi_ai:
        raise ValueError(_loi_ai())
    phien = re.sub(r"[^A-Za-z0-9_-]", "", str(phien or ""))[:40] or ("p" + secrets.token_hex(6))
    lich = [{"vai": x["vai"], "noi_dung": x["noi_dung"]} for x in v2.lich_su_tro_ly(phien, 20)]
    boi = v2.boi_canh_tro_ly()
    if _DEPS.thong_tin_ai and isinstance(boi.get("tong_quan"), dict):
        try:    # trạng thái AI thật (engine đang dùng), không phải giá trị mặc định của kho
            boi["tong_quan"]["ai"] = {**(boi["tong_quan"].get("ai") or {}), **(_DEPS.thong_tin_ai() or {})}
        except Exception:
            pass
    if _DEPS.co_telegram and isinstance(boi.get("tong_quan"), dict):
        try:
            boi["tong_quan"]["telegram"] = bool(_DEPS.co_telegram())
        except Exception:
            pass
    try:
        boi["bo_nao"] = doi_social_bo_nao.boi_canh_tro_ly(tin)
    except Exception as ex:
        print(f"[doi-social] bộ não cho trợ lý lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
    import doi_social_ai
    kq = await doi_social_ai.tro_ly(tin, lich, boi, goi_ai=_DEPS.goi_ai) or {}
    tra_loi = str(kq.get("tra_loi") or "").strip()
    kh = None
    k = kq.get("ke_hoach")
    if isinstance(k, dict) and k.get("buoc"):
        try:
            kh = v2.tao_ke_hoach(mo_ta=k.get("mo_ta") or "", buoc=k.get("buoc"),
                                 nguon=nguon if nguon in ("web", "telegram") else "web", chat_id=chat_id)
            tra_loi += f"\n\nMình đã lên kế hoạch #{kh['id']}, bạn xem rồi bấm Duyệt thì đội mới chạy."
        except ValueError as e:
            tra_loi += f"\n\n(Kế hoạch chưa lưu được: {e})"
    tra_loi = tra_loi.strip() or "Mình chưa có câu trả lời."
    v2.ghi_tro_ly(phien, "nguoi", tin)
    v2.ghi_tro_ly(phien, "ai", tra_loi, kh["id"] if kh else None)
    if kh and nguon == "telegram" and _DEPS.bao_ke_hoach:
        try:
            await _DEPS.bao_ke_hoach(kh)
        except Exception as ex:
            print(f"[doi-social] gửi kế hoạch lên Telegram lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
    return {"phien": phien, "tra_loi": tra_loi, "ke_hoach": kh}


def _goi_worker_zip(bo_cau_hinh: bool = True) -> bytes:
    import io
    import zipfile        # nạp lúc cần: zipfile tốn ~27ms, không đáng đánh thuế lúc khởi động
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(WORKER_DIR.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            if bo_cau_hinh and p.name in WORKER_BO_QUA:
                continue
            z.write(str(p), "MinMinWorker/" + str(p.relative_to(WORKER_DIR)).replace("\\", "/"))
    return buf.getvalue()


def phien_ban_worker() -> str:
    """PHIEN_BAN trong minmin_worker.py của máy chủ (để Worker tự cập nhật)."""
    p = WORKER_DIR / "minmin_worker.py"
    try:
        mt = p.stat().st_mtime
    except OSError:
        return ""
    if _PB_WORKER.get("mt") != mt:
        m = re.search(r'^PHIEN_BAN\s*=\s*["\']([^"\']+)["\']', p.read_text(encoding="utf-8", errors="ignore"), re.M)
        _PB_WORKER.update(mt=mt, pb=m.group(1) if m else "")
    return _PB_WORKER.get("pb", "")


async def _luu_tai_len(f: UploadFile, toi_da: int) -> Path:
    """Ghi tệp tải lên ra thư mục tạm, cắt ngay khi vượt `toi_da`. Raise ValueError."""
    tam = doi_social._goc / "tai-len-tam"
    tam.mkdir(parents=True, exist_ok=True)
    dich = tam / secrets.token_hex(8)
    co = 0
    try:
        with open(dich, "wb") as out:
            while True:
                kh = await f.read(1024 * 1024)
                if not kh:
                    break
                co += len(kh)
                if co > toi_da:
                    raise ValueError(f"tệp '{v2._ten_an_toan(f.filename)}' quá lớn (tối đa {toi_da // (1024 * 1024)}MB)")
                out.write(kh)
    except BaseException:
        dich.unlink(missing_ok=True)
        raise
    return dich


def _so(v, mac: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return mac


async def mot_nhip_nen() -> None:
    """Một nhịp vòng nền: lịch hẹn tới giờ -> đợt, nháp quá hạn, rồi gửi thông báo đang chờ."""
    dots = await asyncio.to_thread(v2.vong_nen)
    for d in dots:
        for m in {x["may_id"] for x in d.get("viec") or []}:
            danh_thuc(m)
    so = await asyncio.to_thread(v2.dem_nhap_cho_duyet)
    now = time.time()
    if so and so != _NHAC_NHAP.get("so") and now - _NHAC_NHAP.get("luc", 0) > 3600:
        _NHAC_NHAP.update(so=so, luc=now)
        v2.bao("Nội dung chờ duyệt", f"{so} nháp AI đang chờ bạn duyệt trong Đội Social > Duyệt nội dung.")
    _xa_bao()


_NHAC_NHAP: dict = {}


async def _vong_nen() -> None:
    await asyncio.sleep(5)
    while True:
        try:
            await mot_nhip_nen()
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            print(f"[doi-social] vòng nền lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
        await asyncio.sleep(NHIP_NEN)


def register(app: FastAPI, deps: DoiSocialDeps) -> None:
    global _DEPS
    _DEPS = deps
    doi_social_bo_nao.dat_goc(deps.goc_brain)

    @app.on_event("startup")
    async def _nho_vong():
        _VONG[:] = [asyncio.get_running_loop()]
        if VONG_NEN_BAT and not _NEN:
            _NEN.append(asyncio.get_running_loop().create_task(_vong_nen()))

    @app.on_event("shutdown")
    async def _tat_vong():
        for t in _NEN:
            t.cancel()
        _NEN.clear()

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
        kbs = d.get("kich_ban")
        doi_social.nhip(m["id"], nick if isinstance(nick, list) else None,
                        d.get("driver_ok"), d.get("loi_driver") or "", d.get("phien_ban") or "",
                        kich_ban=kbs if isinstance(kbs, list) else None, song_song=d.get("song_song"))
        return {"ok": True, "gioi_han": doi_social.gioi_han(), "gioi_han_v2": v2.gioi_han_v2(),
                "phien_ban_worker": phien_ban_worker()}

    @app.get("/doi-social/may/ban-cap-nhat")
    async def ds_may_ban_cap_nhat(request: Request):
        m, err = await _may(request)
        if err:
            return err
        return Response(_goi_worker_zip(), media_type="application/zip",
                        headers={"Content-Disposition": "attachment; filename=MinMinWorker.zip",
                                 "x-phien-ban": phien_ban_worker()})

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
                _xa_bao()
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
                                       d.get("buoc") if isinstance(d.get("buoc"), list) else [], anh,
                                       dem=d.get("dem") if isinstance(d.get("dem"), dict) else None)
        except (ValueError, TypeError) as e:
            return _loi_v(e) if isinstance(e, ValueError) else _loi(e)
        if v["ky_nang"] == "fb_dang_bai":       # việc đăng bài cũ: báo từng việc như trước
            _bao_nen(deps, v, "xong" if v["trang_thai"] == "xong" else "loi")
        _xa_bao()
        return {"ok": True}

    @app.post("/doi-social/may/su-kien/{vid}")
    async def ds_may_su_kien(vid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            kq = v2.ghi_su_kien(vid, m["id"], await _json(request))
        except ValueError as e:
            return _loi_v(e)
        _xa_bao()
        return {"ok": True, **kq}

    @app.post("/doi-social/may/buoc/{vid}")
    async def ds_may_buoc(vid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            v2.viec_cua_may(vid, m["id"])
            v2.ghi_buoc(vid, (await _json(request)).get("dong") or "")
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True}

    @app.get("/doi-social/may/dung/{vid}")
    async def ds_may_dung(vid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            v2.viec_cua_may(vid, m["id"])
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "dung": v2.can_dung(vid)}

    @app.post("/doi-social/may/ai")
    async def ds_may_ai(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            v = v2.viec_cua_may(d.get("viec_id"), m["id"])
        except ValueError as e:
            return _loi_v(e)
        muc = str(d.get("muc_dich") or "")
        if muc not in MUC_DICH_AI:
            return _loi(f"muc_dich lạ: {muc[:40]}")
        if not deps.goi_ai:
            return _loi(_loi_ai(), 503)
        du_lieu = d.get("du_lieu") if isinstance(d.get("du_lieu"), dict) else {}
        anh_ds = d.get("anh") or []
        if not isinstance(anh_ds, list) or len(anh_ds) > ANH_AI_TOI_DA:
            return _loi(f"tối đa {ANH_AI_TOI_DA} ảnh mỗi lần hỏi AI")
        tam = doi_social._goc / "ai-tam"
        duong = []
        try:
            for a in anh_ds:
                s = str(a or "")
                if s.startswith("data:"):
                    s = s.split(",", 1)[-1]
                try:
                    b = base64.b64decode(s, validate=False)
                except Exception:
                    return _loi("ảnh base64 hỏng")
                if not b or len(b) > ANH_AI_BYTE:
                    return _loi("mỗi ảnh gửi AI tối đa 5MB")
                tam.mkdir(parents=True, exist_ok=True)
                p = tam / f"{secrets.token_hex(8)}.jpg"
                p.write_bytes(b)
                duong.append(str(p))
            ts = v.get("tham_so") or {}
            sp = du_lieu.get("san_pham_id") or (ts.get("tham_so") or {}).get("san_pham") or ""
            kt = _kt_ai(sp, _ngu_canh_ai(du_lieu))
            import doi_social_ai
            try:
                kq = await doi_social_ai.xu_ly_may(muc, du_lieu, duong, goi_ai=deps.goi_ai, kien_thuc=kt)
            except ValueError as e:
                return _loi(e)
            except Exception as e:
                return _loi(f"AI lỗi: {type(e).__name__}: {str(e)[:300]}", 502)
        finally:
            for p in duong:
                try:
                    os.remove(p)
                except OSError:
                    pass
        kq = kq if isinstance(kq, dict) else {}
        if muc == "tra_loi_binh_luan" and kq.get("can_hoi_chu") and sp:
            bl = du_lieu.get("binh_luan") if isinstance(du_lieu.get("binh_luan"), dict) else {}
            v2.ghi_hoi_cho_ban(sp, kq.get("cau_hoi") or bl.get("chu") or "", f"bình luận · {v['nick_ten']}")
        if muc == "tra_loi_tin_nhan":
            ht = du_lieu.get("hoi_thoai") if isinstance(du_lieu.get("hoi_thoai"), dict) else {}
            if ht.get("khach_link") and (kq.get("sdt") or kq.get("can_tra_loi_tay")):
                v2.danh_dau_hoi_thoai(v["nick_id"], ht["khach_link"], sdt=str(kq.get("sdt") or ""),
                                      can_tay=bool(kq.get("can_tra_loi_tay")))
        _xa_bao()
        return {"ok": True, "ket_qua": kq}

    @app.post("/doi-social/may/ban-nhap")
    async def ds_may_ban_nhap(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request, THAN_NHAP_TOI_DA)
            n = v2.tao_ban_nhap_tu_may(d.get("viec_id"), m["id"], d)
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "id": n["id"]}

    @app.get("/doi-social/may/ban-nhap/lay")
    async def ds_may_lay_nhap(request: Request, viec_id: int = Query(0), noi_dang: str = Query(""),
                              san_pham: str = Query("")):
        m, err = await _may(request)
        if err:
            return err
        try:
            n = v2.lay_ban_nhap_cho_viec(viec_id, m["id"], noi_dang, san_pham)
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "ban_nhap": n}

    @app.get("/doi-social/may/ban-nhap/tep/{nid}/{luu}")
    async def ds_may_nhap_tep(nid: int, luu: str, request: Request):
        m, err = await _may(request)
        if err:
            return err
        if not v2.nhap_cua_may(nid, m["id"]):
            return _loi("nháp này không do việc của máy này giữ", 403)
        p = v2.duong_tep_nhap(nid, luu)
        return FileResponse(str(p)) if p else _loi("không có tệp", 404)

    @app.post("/doi-social/may/tep-ket-qua/{vid}")
    async def ds_may_tep_ket_qua(vid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        tam = None
        try:
            v2.viec_cua_may(vid, m["id"])
            if (request.headers.get("content-type") or "").startswith("multipart/form-data"):
                form = await request.form(max_files=1, max_fields=5)
                f = form.get("tep")
                if not isinstance(f, UploadFile) or not f.filename:
                    raise ValueError("chưa gửi tệp (trường 'tep')")
                tam = await _luu_tai_len(f, v2.KQ_TOI_DA)
                kq = v2.luu_tep_ket_qua(vid, m["id"], str(form.get("ten") or f.filename), tam)
            else:
                d = await _json(request, THAN_KQ_TOI_DA)
                try:
                    b = base64.b64decode(str(d.get("b64") or ""))
                except Exception:
                    raise ValueError("base64 hỏng")
                if not b:
                    raise ValueError("tệp rỗng")
                kq = v2.luu_tep_ket_qua(vid, m["id"], str(d.get("ten") or "ket-qua.csv"), b)
        except ValueError as e:
            return _loi_v(e)
        finally:
            if tam:
                Path(tam).unlink(missing_ok=True)
        return {"ok": True, **kq}

    @app.post("/doi-social/may/ban-nhap/{nid}/ket-qua")
    async def ds_may_nhap_ket_qua(nid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            n = v2.ket_qua_ban_nhap(nid, m["id"], bool(d.get("ok")), d.get("link") or "", d.get("loi") or "")
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "trang_thai": n["trang_thai"]}

    @app.get("/doi-social/may/kho/lay")
    async def ds_may_kho_lay(request: Request, viec_id: int = Query(0)):
        m, err = await _may(request)
        if err:
            return err
        try:
            b = v2.lay_kho_cho_viec(viec_id, m["id"])
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "bai": b}

    @app.get("/doi-social/may/kho/tep/{bid}/{luu}")
    async def ds_may_kho_tep(bid: int, luu: str, request: Request):
        m, err = await _may(request)
        if err:
            return err
        if not v2.bai_kho_cua_may(bid, m["id"]):
            return _loi("bài này không do việc của máy này giữ", 403)
        p = v2.duong_tep_kho(bid, luu)
        return FileResponse(str(p)) if p else _loi("không có tệp", 404)

    @app.post("/doi-social/may/kho/{bid}/ket-qua")
    async def ds_may_kho_ket_qua(bid: int, request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            b = v2.ket_qua_kho(bid, m["id"], bool(d.get("ok")), bool(d.get("da_bam_dang")),
                               d.get("link") or "", d.get("loi") or "", hong=bool(d.get("hong")))
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "trang_thai": b["trang_thai"]}

    @app.get("/doi-social/may/nhom-fb")
    async def ds_may_nhom(request: Request, viec_id: int = Query(0)):
        m, err = await _may(request)
        if err:
            return err
        try:
            muc = v2.nhom_cho_viec(viec_id, m["id"])
            v = v2.viec_cua_may(viec_id, m["id"])
            sp_id = str(((v.get("tham_so") or {}).get("tham_so") or {}).get("san_pham") or "")
            kt = v2.lay_kien_thuc(sp_id, day_du=False) if sp_id else None
            sp = {"id": kt["id"], "ten": kt.get("ten", ""), "tu_khoa": kt.get("tu_khoa", "")} if kt else None
            return {"ok": True, "muc": muc, "san_pham": sp, "tu_khoa": (sp or {}).get("tu_khoa", "")}
        except ValueError as e:
            return _loi_v(e)

    @app.post("/doi-social/may/nhom-fb")
    async def ds_may_bao_nhom(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            n = v2.bao_nhom(d.get("viec_id"), m["id"], d)
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True, "nhom": n}

    @app.get("/doi-social/may/da-tuong-tac")
    async def ds_may_da_lam(request: Request, nick_id: str = Query(""), khoa: str = Query(""),
                            ca_doi: int = Query(0)):
        m, err = await _may(request)
        if err:
            return err
        if not v2.nick_thuoc_may(nick_id, m["id"]):
            return _loi("nick không thuộc máy này", 403)
        return {"ok": True, "da_lam": v2.da_lam(nick_id, khoa, bool(ca_doi))}

    @app.post("/doi-social/may/da-tuong-tac")
    async def ds_may_ghi_da_lam(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            nick_id = str(d.get("nick_id") or "")
            if d.get("viec_id"):
                nick_id = v2.viec_cua_may(d.get("viec_id"), m["id"])["nick_id"]
            if not v2.nick_thuoc_may(nick_id, m["id"]):
                return _loi("nick không thuộc máy này", 403)
            v2.ghi_da_lam(nick_id, d.get("khoa") or "")
        except ValueError as e:
            return _loi_v(e)
        return {"ok": True}

    @app.post("/doi-social/may/hoi-thoai")
    async def ds_may_hoi_thoai(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
            kq = v2.ghi_hoi_thoai(d.get("viec_id"), m["id"], d)
        except ValueError as e:
            return _loi_v(e)
        _xa_bao()
        return {"ok": True, **kq}

    @app.get("/doi-social/may/bai-doi-da-dang")
    async def ds_may_bai_doi(request: Request, viec_id: int = Query(0)):
        m, err = await _may(request)
        if err:
            return err
        try:
            return {"ok": True, "muc": v2.bai_doi_da_dang(viec_id, m["id"])}
        except ValueError as e:
            return _loi_v(e)

    # ---------------------------------------------------------------- trang quản lý (đăng nhập)
    def _chan():
        ly = ly_do_chan()
        return _loi(ly, 403) if ly else None

    async def _than(request: Request) -> dict:
        body = await request.body()
        if not body:
            return {}
        try:
            d = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("thân yêu cầu không phải JSON hợp lệ")
        if not isinstance(d, dict):
            raise ValueError("JSON phải là object")
        return d

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

    def _tep_tinh(*phan: str):
        for x in phan[:-1]:
            if not THU_MUC_TINH.match(x):
                return _loi("không có", 404)
        ten = phan[-1]
        if ".." in ten or not TEN_TINH.match(ten):
            return _loi("không có", 404)
        p = WEB_DIR.joinpath(*phan)
        try:
            p.resolve().relative_to(WEB_DIR.resolve())
        except (ValueError, OSError):
            return _loi("không có", 404)
        if not p.is_file():
            return _loi("không có", 404)
        return FileResponse(str(p), media_type=KIEU_TINH.get(ten.rsplit(".", 1)[-1]),
                            headers={"Cache-Control": "no-cache"})

    @app.get(GOC + "/{ten}")
    def ds_tinh(ten: str):
        return _tep_tinh(ten)

    @app.get(GOC + "/{thu_muc}/{ten}")
    def ds_tinh_con(thu_muc: str, ten: str):
        return _tep_tinh(thu_muc, ten)

    @app.get("/doi-social/trang-thai")
    def ds_trang_thai():
        c = _chan()
        if c:
            return c
        return {"ok": True, "may": doi_social.ds_may(), "nick": doi_social.ds_nick(),
                "viec": doi_social.ds_viec(30), "gioi_han": doi_social.gioi_han(),
                "ky_nang": doi_social.KY_NANG, "phien_ban_worker": phien_ban_worker()}

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

    # ---------------------------------------------------------------- 26.10.187: trang web đầy đủ
    @app.get("/doi-social/tong-quan")
    def ds_tong_quan(ngay: int = Query(14)):
        c = _chan()
        if c:
            return c
        tq = v2.tong_quan(ngay)
        try:
            tq["telegram"] = bool(deps.co_telegram()) if deps.co_telegram else False
        except Exception:
            tq["telegram"] = False
        if deps.thong_tin_ai:
            try:
                tq["ai"] = {**tq["ai"], **(deps.thong_tin_ai() or {})}
            except Exception as ex:
                print(f"[doi-social] thong_tin_ai lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
        elif deps.goi_ai:
            tq["ai"]["san_sang"] = True
        return {"ok": True, **tq}

    @app.get("/doi-social/kich-ban")
    def ds_kich_ban():
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.danh_muc_kem_san_sang()}

    @app.get("/doi-social/nick")
    def ds_ds_nick():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.ds_nick()}

    @app.post("/doi-social/nick/meta")
    async def ds_nick_meta(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            n = v2.dat_nick_meta(d.get("ids"), d.get("nhan"), d.get("tao_tu"), d.get("ghi_chu"))
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "so": n}

    @app.get("/doi-social/gioi-han-v2")
    def ds_gh2():
        c = _chan()
        if c:
            return c
        import doi_social_kich_ban as kb
        return {"ok": True, "gia_tri": v2.gioi_han_v2(), "mac_dinh": kb.GIOI_HAN_MAC_DINH, "hanh_dong": kb.HANH_DONG}

    @app.post("/doi-social/gioi-han-v2")
    async def ds_dat_gh2(request: Request):
        c = _chan()
        if c:
            return c
        try:
            g = v2.dat_gioi_han_v2(await _than(request))
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "gia_tri": g}

    @app.get("/doi-social/dot-chay")
    def ds_ds_dot(trang_thai: str = Query(""), tu: float = Query(0), trang: int = Query(1),
                  moi_trang: int = Query(50)):
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.ds_dot(trang_thai, tu, trang, moi_trang)}

    @app.post("/doi-social/dot-chay")
    async def ds_tao_dot(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            kw = dict(kich_ban=d.get("kich_ban"), nick=d.get("nick") or [], tham_so=d.get("tham_so") or {},
                      ten=d.get("ten") or "", song_song=d.get("song_song") or 1, chay_an=bool(d.get("chay_an")))
            if (d.get("che_do") or "ngay") == "hen":
                return {"ok": True, "lich": v2.tao_lich(cron=d.get("cron") or "", **kw)}
            if "chay_thu" in d:
                kw["chay_thu"] = bool(d.get("chay_thu"))
            dot = tao_dot_va_chay(nguon="web", **kw)
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "dot": dot}

    @app.get("/doi-social/dot-chay/{did}")
    def ds_lay_dot(did: int):
        c = _chan()
        if c:
            return c
        d = v2.lay_dot(did)
        return {"ok": True, "dot": d} if d else _loi("không có đợt chạy này", 404)

    @app.post("/doi-social/dot-chay/{did}/huy")
    def ds_huy_dot(did: int):
        c = _chan()
        if c:
            return c
        try:
            d = v2.huy_dot(did)
        except ValueError as e:
            return _loi(e)
        _xa_bao()
        return {"ok": True, "dot": d}

    @app.get("/doi-social/lich-hen")
    def ds_ds_lich():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.ds_lich()}

    @app.post("/doi-social/lich-hen/{lid}")
    async def ds_sua_lich(lid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            l = v2.sua_lich(lid, bat=d.get("bat"), ten=d.get("ten"), cron=d.get("cron"), nick=d.get("nick"),
                            tham_so=d.get("tham_so"), song_song=d.get("song_song"), chay_an=d.get("chay_an"))
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "lich": l}

    @app.delete("/doi-social/lich-hen/{lid}")
    def ds_xoa_lich(lid: int):
        c = _chan()
        if c:
            return c
        return {"ok": True} if v2.xoa_lich(lid) else _loi("không có lịch hẹn này", 404)

    @app.post("/doi-social/lich-hen/{lid}/chay")
    def ds_chay_lich(lid: int):
        c = _chan()
        if c:
            return c
        try:
            dot = v2.chay_lich(lid)
        except ValueError as e:
            _xa_bao()
            return _loi(e)
        for m in {x["may_id"] for x in dot.get("viec") or []}:
            danh_thuc(m)
        return {"ok": True, "dot": dot}

    @app.get("/doi-social/lich-su")
    def ds_lich_su(trang_thai: str = Query(""), kich_ban: str = Query(""), trang: int = Query(1),
                   moi_trang: int = Query(50)):
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.lich_su(trang_thai, kich_ban, trang, moi_trang)}

    @app.get("/doi-social/dang-chay")
    def ds_dang_chay():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.dang_chay()}

    @app.get("/doi-social/hom-nay-theo-nick")
    def ds_hom_nay():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.hom_nay_theo_nick()}

    def _loc_sk(request: Request) -> dict:
        q = request.query_params
        return {"tu": _so(q.get("tu")) or None, "den": _so(q.get("den")) or None, "nick": q.get("nick") or "",
                "tinh_nang": q.get("tinh_nang") or "", "ket_qua": q.get("ket_qua") or "",
                "kich_ban": q.get("kich_ban") or "", "dot": q.get("dot") or None}

    @app.get("/doi-social/su-kien")
    def ds_su_kien(request: Request, trang: int = Query(1), moi_trang: int = Query(50)):
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.ds_su_kien(trang=trang, moi_trang=moi_trang, **_loc_sk(request))}

    @app.get("/doi-social/su-kien.csv")
    def ds_su_kien_csv(request: Request):
        c = _chan()
        if c:
            return c
        return Response(v2.su_kien_csv(**_loc_sk(request)).encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=doi-social-nhat-ky.csv"})

    @app.get("/doi-social/ket-qua/{vid}/{ten}")
    def ds_tep_ket_qua(vid: int, ten: str):
        c = _chan()
        if c:
            return c
        p = v2.duong_tep_ket_qua(vid, ten)
        if not p:
            return _loi("không có tệp", 404)
        kieu = "text/plain; charset=utf-8" if p.suffix.lower() == ".txt" else "text/csv; charset=utf-8"
        return FileResponse(str(p), media_type=kieu, filename=p.name)

    @app.post("/doi-social/kham-trang")
    async def ds_kham_trang(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            v = v2.tao_kham_trang(str(d.get("nick") or ""), str(d.get("url") or ""), d.get("cuon") or 0,
                                  str(d.get("trong") or ""), str(d.get("chon") or ""))
        except ValueError as e:
            return _loi(e)
        danh_thuc(v["may_id"])
        return {"ok": True, "viec": v}

    @app.get("/doi-social/kho")
    def ds_kho_tong(nen_tang: str = Query("")):
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.kho_tong(nen_tang)}

    @app.get("/doi-social/kho/muc")
    def ds_kho_muc(request: Request, nen_tang: str = Query(""), trang_thai: str = Query(""),
                   trang: int = Query(1), moi_trang: int = Query(50)):
        c = _chan()
        if c:
            return c
        nick = request.query_params.get("nick")       # vắng = mọi kho; '' = kho chung
        return {"ok": True, **v2.ds_kho(nen_tang, nick, trang_thai, trang, moi_trang)}

    @app.post("/doi-social/kho")
    async def ds_them_kho(request: Request):
        c = _chan()
        if c:
            return c
        if not (request.headers.get("content-type") or "").startswith("multipart/form-data"):
            return _loi("gửi dạng multipart/form-data (nen_tang, nick, tieu_de, noi_dung, tep)")
        tam = []
        try:
            form = await request.form(max_files=50, max_fields=20)
            tep = [f for f in (form.getlist("tep") + form.getlist("tep[]")) if isinstance(f, UploadFile) and f.filename]
            for f in tep:
                v2.kiem_duoi_kho(f.filename)
            for f in tep:
                tam.append((f.filename, await _luu_tai_len(f, v2.KHO_TOI_DA)))
            ids = v2.them_kho(nen_tang=str(form.get("nen_tang") or ""), nick_id=str(form.get("nick") or ""),
                              tieu_de=str(form.get("tieu_de") or ""), noi_dung=str(form.get("noi_dung") or ""),
                              tep=tam)
        except ValueError as e:
            return _loi(e)
        finally:
            for _, p in tam:
                Path(p).unlink(missing_ok=True)
        return {"ok": True, "ids": ids, "so": len(ids)}

    @app.delete("/doi-social/kho/{bid}")
    def ds_xoa_kho(bid: int):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True} if v2.xoa_kho(bid) else _loi("không có bài này", 404)
        except ValueError as e:
            return _loi(e)

    @app.post("/doi-social/kho/{bid}/tra-lai")
    def ds_tra_lai_kho(bid: int):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "bai": v2.tra_lai_kho(bid)}
        except ValueError as e:
            return _loi(e)

    @app.get("/doi-social/kho/tep/{bid}/{luu}")
    def ds_kho_tep(bid: int, luu: str):
        c = _chan()
        if c:
            return c
        p = v2.duong_tep_kho(bid, luu)
        return FileResponse(str(p)) if p else _loi("không có tệp", 404)

    @app.post("/doi-social/viet-bai")
    async def ds_viet_bai(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            noi_dang = str(d.get("noi_dang") or "")
            if noi_dang not in v2.NOI_DANG:
                raise ValueError("chọn nơi đăng hợp lệ")
            kt = _kt_ai(d.get("san_pham_id"), str(d.get("yeu_cau") or ""))
            if not kt:
                raise ValueError("chọn sản phẩm/chủ đề trong Kiến thức cho Agent")
            nick_id, nick_ten = str(d.get("nick_id") or ""), ""
            if nick_id:
                n = [x for x in doi_social.ds_nick() if x["id"] == nick_id]
                if not n:
                    raise ValueError(f"không thấy nick '{nick_id}'")
                nick_ten = n[0]["ten"]
            so_ban = max(1, min(5, int(d.get("so_ban") or 1)))
        except (ValueError, TypeError) as e:
            return _loi(e)
        if not deps.goi_ai:
            return _loi(_loi_ai(), 503)
        import doi_social_ai
        yeu_cau = str(d.get("yeu_cau") or "")[:2000]
        try:
            bai = await doi_social_ai.viet_bai(kt, noi_dang, so_ban, yeu_cau, goi_ai=deps.goi_ai)
        except ValueError as e:
            return _loi(e)
        except Exception as e:
            return _loi(f"AI lỗi: {type(e).__name__}: {str(e)[:300]}", 502)
        muc = []
        for nd in (bai or [])[:so_ban]:
            if str(nd or "").strip():
                muc.append(v2.tao_ban_nhap(loai="bai_dang", noi_dang=noi_dang, noi_dung=str(nd), nick_id=nick_id,
                                           nick_ten=nick_ten, nhom=str(d.get("nhom") or ""), san_pham_id=str(kt["id"]),
                                           ly_do=("Viết theo yêu cầu: " + yeu_cau) if yeu_cau else "Viết từ hồ sơ sản phẩm"))
        if not muc:
            return _loi("AI không trả về bài nào, thử lại", 502)
        return {"ok": True, "muc": muc}

    @app.get("/doi-social/ban-nhap")
    def ds_ds_nhap(trang_thai: str = Query("cho_duyet"), noi_dang: str = Query(""), san_pham: str = Query(""),
                   trang: int = Query(1), moi_trang: int = Query(50)):
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.ds_ban_nhap(trang_thai, noi_dang, san_pham, trang, moi_trang)}

    def _sau_duyet_nhap(n: dict) -> None:
        if n.get("viec_id"):
            v = doi_social.lay_viec(n["viec_id"])
            if v:
                danh_thuc(v["may_id"])

    @app.post("/doi-social/ban-nhap/duyet-nhieu")
    async def ds_duyet_nhieu(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
        except ValueError as e:
            return _loi(e)
        ids = d.get("ids") if isinstance(d.get("ids"), list) else []
        ok, loi = [], []
        for i in ids[:500]:
            try:
                n = v2.duyet_ban_nhap(i, bool(d.get("dong_y")))
                _sau_duyet_nhap(n)
                ok.append(n["id"])
            except ValueError as e:
                loi.append({"id": i, "loi": str(e)})
        return {"ok": True, "xong": ok, "loi": loi}

    @app.post("/doi-social/ban-nhap/{nid}/duyet")
    def ds_duyet_nhap(nid: int):
        c = _chan()
        if c:
            return c
        try:
            n = v2.duyet_ban_nhap(nid, True)
        except ValueError as e:
            return _loi(e)
        _sau_duyet_nhap(n)
        return {"ok": True, "ban_nhap": n}

    @app.post("/doi-social/ban-nhap/{nid}/bo")
    def ds_bo_nhap(nid: int):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "ban_nhap": v2.duyet_ban_nhap(nid, False)}
        except ValueError as e:
            return _loi(e)

    @app.post("/doi-social/ban-nhap/{nid}/viet-lai")
    async def ds_viet_lai(nid: int, request: Request):
        c = _chan()
        if c:
            return c
        n = v2.lay_ban_nhap(nid)
        if not n:
            return _loi("không có nháp này", 404)
        if n["trang_thai"] not in ("cho_duyet", "het_han", "loi"):
            return _loi("chỉ viết lại được nháp đang chờ duyệt, hết hạn hoặc lỗi")
        if not deps.goi_ai:
            return _loi(_loi_ai(), 503)
        try:
            d = await _than(request)
        except ValueError as e:
            return _loi(e)
        import doi_social_ai
        try:
            moi = await doi_social_ai.viet_lai(n, _kt_ai(n.get("san_pham_id"), n.get("bai_goc") or ""),
                                               str(d.get("yeu_cau") or "")[:2000], goi_ai=deps.goi_ai)
            n = v2.sua_ban_nhap(nid, moi)
        except ValueError as e:
            return _loi(e)
        except Exception as e:
            return _loi(f"AI lỗi: {type(e).__name__}: {str(e)[:300]}", 502)
        return {"ok": True, "ban_nhap": n}

    @app.post("/doi-social/ban-nhap/{nid}/tep")
    async def ds_nhap_tep(nid: int, request: Request):
        c = _chan()
        if c:
            return c
        if not (request.headers.get("content-type") or "").startswith("multipart/form-data"):
            return _loi("gửi dạng multipart/form-data (trường 'tep')")
        tam = []
        try:
            n = v2.lay_ban_nhap(nid)
            if not n:
                return _loi("không có nháp này", 404)
            if n["trang_thai"] not in ("cho_duyet", "het_han", "loi"):
                raise ValueError("chỉ thêm tệp cho nháp đang chờ duyệt, hết hạn hoặc lỗi")
            form = await request.form(max_files=20, max_fields=5)
            tep = [f for f in (form.getlist("tep") + form.getlist("tep[]")) if isinstance(f, UploadFile) and f.filename]
            if not tep:
                raise ValueError("chưa chọn tệp")
            for f in tep:
                v2.kiem_duoi_kho(f.filename)
            for f in tep:
                tam.append((f.filename, await _luu_tai_len(f, v2.KHO_TOI_DA)))
            v2.them_tep_nhap(nid, tam)
        except ValueError as e:
            return _loi(e)
        finally:
            for _, p in tam:
                Path(p).unlink(missing_ok=True)
        return {"ok": True, "ban_nhap": v2.lay_ban_nhap(nid)}

    @app.get("/doi-social/ban-nhap/tep/{nid}/{luu}")
    def ds_nhap_xem_tep(nid: int, luu: str):
        c = _chan()
        if c:
            return c
        p = v2.duong_tep_nhap(nid, luu)
        return FileResponse(str(p)) if p else _loi("không có tệp", 404)

    @app.put("/doi-social/ban-nhap/{nid}")
    async def ds_sua_nhap(nid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            n = v2.sua_ban_nhap(nid, (await _than(request)).get("noi_dung"))
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "ban_nhap": n}

    # ---------------------------------------------------------------- bộ não MinMin (wiki, ghi chú, trí nhớ)
    @app.get("/doi-social/bo-nao/tim")
    def ds_bo_nao_tim(q: str = Query("")):
        c = _chan()
        if c:
            return c
        return {"ok": True, "co_bo_nao": doi_social_bo_nao.goc() is not None, "muc": doi_social_bo_nao.tim(q, 8)}

    @app.get("/doi-social/bo-nao/tep")
    def ds_bo_nao_tep(path: str = Query("")):
        c = _chan()
        if c:
            return c
        t = doi_social_bo_nao.doc_tep(path, 20000)
        return {"ok": True, "tep": t} if t else _loi("không đọc được tệp này trong bộ não", 404)

    @app.post("/doi-social/kien-thuc/tu-bo-nao")
    async def ds_kt_tu_bo_nao(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            t = doi_social_bo_nao.doc_tep(str(d.get("path") or ""), 20000)
            if not t:
                raise ValueError("không đọc được tệp này trong bộ não")
            than = t["noi_dung"]
            if than.startswith("---"):
                ket = than.find("\n---", 3)
                if ket > 0:
                    than = than[ket + 4:]
            than = "\n".join(x for x in than.splitlines() if not x.startswith("# ")).strip()
            k = v2.tao_kien_thuc({"loai": d.get("loai") or "san_pham", "ten": d.get("ten") or t["ten"],
                                  "mo_ta": than[:3000], "nguon_bo_nao": [t["path"]], "tu_tra_bo_nao": True})
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "kien_thuc": k}

    @app.get("/doi-social/kien-thuc")
    def ds_ds_kt():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.ds_kien_thuc()}

    @app.post("/doi-social/kien-thuc")
    async def ds_tao_kt(request: Request):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "kien_thuc": v2.tao_kien_thuc(await _than(request))}
        except ValueError as e:
            return _loi(e)

    @app.get("/doi-social/kien-thuc/{kid}")
    def ds_lay_kt(kid: int):
        c = _chan()
        if c:
            return c
        k = v2.lay_kien_thuc(kid)
        return {"ok": True, "kien_thuc": k} if k else _loi("không có mục kiến thức này", 404)

    @app.put("/doi-social/kien-thuc/{kid}")
    async def ds_sua_kt(kid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "kien_thuc": v2.sua_kien_thuc(kid, await _than(request))}
        except ValueError as e:
            return _loi(e)

    @app.delete("/doi-social/kien-thuc/{kid}")
    def ds_xoa_kt(kid: int):
        c = _chan()
        if c:
            return c
        return {"ok": True} if v2.xoa_kien_thuc(kid) else _loi("không có mục kiến thức này", 404)

    @app.post("/doi-social/kien-thuc/{kid}/tai-lieu")
    async def ds_them_tl(kid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            if (request.headers.get("content-type") or "").startswith("multipart/form-data"):
                form = await request.form(max_files=1, max_fields=10)
                f = form.get("tep")
                if not isinstance(f, UploadFile) or not f.filename:
                    raise ValueError("chưa chọn tệp tài liệu")
                if Path(v2._ten_an_toan(f.filename)).suffix.lower() not in v2.TL_DUOI:
                    raise ValueError(f"tài liệu chỉ nhận {', '.join(sorted(v2.TL_DUOI))}")
                p = await _luu_tai_len(f, v2.TL_TOI_DA)
                try:
                    chu = v2.trich_chu_tai_lieu(f.filename, p.read_bytes())
                finally:
                    p.unlink(missing_ok=True)
                tl = v2.them_tai_lieu(kid, str(form.get("ten") or "") or v2._ten_an_toan(f.filename), chu)
            else:
                d = await _than(request)
                tl = v2.them_tai_lieu(kid, d.get("ten") or "", d.get("noi_dung") or "")
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "tai_lieu": tl}

    @app.delete("/doi-social/tai-lieu/{tid}")
    def ds_xoa_tl(tid: int):
        c = _chan()
        if c:
            return c
        return {"ok": True} if v2.xoa_tai_lieu(tid) else _loi("không có tài liệu này", 404)

    @app.post("/doi-social/kien-thuc/{kid}/hoi-dap")
    async def ds_them_hd(kid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            return {"ok": True, "hoi_dap": v2.them_hoi_dap(kid, d.get("hoi") or "", d.get("dap") or "")}
        except ValueError as e:
            return _loi(e)

    @app.put("/doi-social/hoi-dap/{hid}")
    async def ds_tra_loi_hd(hid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "hoi_dap": v2.tra_loi_hoi_dap(hid, (await _than(request)).get("dap") or "")}
        except ValueError as e:
            return _loi(e)

    @app.delete("/doi-social/hoi-dap/{hid}")
    def ds_xoa_hd(hid: int):
        c = _chan()
        if c:
            return c
        return {"ok": True} if v2.xoa_hoi_dap(hid) else _loi("không có hỏi đáp này", 404)

    @app.get("/doi-social/nhom-fb")
    def ds_ds_nhom(san_pham: str = Query("")):
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.ds_nhom(san_pham)}

    @app.post("/doi-social/nhom-fb")
    async def ds_them_nhom(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            ids = v2.them_nhom(d.get("san_pham_id"), d.get("links") or d.get("link") or [], d.get("ten") or "",
                               d.get("trang_thai") or "da_duyet")
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "ids": ids}

    @app.put("/doi-social/nhom-fb/{gid}")
    async def ds_sua_nhom(gid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            n = v2.sua_nhom(gid, trang_thai=d.get("trang_thai"), nick_chinh=d.get("nick_chinh"),
                            nick_tuong_tac=d.get("nick_tuong_tac"), quet_lai_gio=d.get("quet_lai_gio"),
                            ten=d.get("ten"), ghi_chu=d.get("ghi_chu"))
        except ValueError as e:
            return _loi(e)
        return {"ok": True, "nhom": n}

    @app.delete("/doi-social/nhom-fb/{gid}")
    def ds_xoa_nhom(gid: int):
        c = _chan()
        if c:
            return c
        return {"ok": True} if v2.xoa_nhom(gid) else _loi("không có nhóm này", 404)

    @app.get("/doi-social/hoi-thoai")
    def ds_ds_ht(tab: str = Query("tat_ca")):
        c = _chan()
        if c:
            return c
        return {"ok": True, **v2.ds_hoi_thoai(tab)}

    @app.get("/doi-social/hoi-thoai/{hid}")
    def ds_lay_ht(hid: int):
        c = _chan()
        if c:
            return c
        h = v2.lay_hoi_thoai(hid)
        return {"ok": True, "hoi_thoai": h} if h else _loi("không có hội thoại này", 404)

    @app.post("/doi-social/hoi-thoai/{hid}")
    async def ds_doi_ht(hid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "hoi_thoai": v2.doi_hoi_thoai(hid, (await _than(request)).get("hanh_dong") or "")}
        except ValueError as e:
            return _loi(e)

    @app.post("/doi-social/hoi-thoai/{hid}/tra-loi")
    async def ds_tra_loi_ht(hid: int, request: Request):
        c = _chan()
        if c:
            return c
        try:
            kq = v2.tra_loi_tay(hid, (await _than(request)).get("noi_dung") or "")
        except ValueError as e:
            return _loi(e)
        danh_thuc(kq["viec"]["may_id"])
        return {"ok": True, **kq}

    @app.post("/doi-social/tro-ly")
    async def ds_tro_ly(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await _than(request)
            if not deps.goi_ai:
                return _loi(_loi_ai(), 503)
            kq = await tro_ly_tra_loi(d.get("tin") or "", d.get("phien") or "", "web")
        except ValueError as e:
            return _loi(e)
        except Exception as e:
            return _loi(f"AI lỗi: {type(e).__name__}: {str(e)[:300]}", 502)
        return {"ok": True, **kq}

    @app.get("/doi-social/tro-ly/lich-su")
    def ds_tro_ly_ls(phien: str = Query("")):
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.lich_su_tro_ly(phien) if phien else []}

    @app.get("/doi-social/tro-ly/phien")
    def ds_tro_ly_phien():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.ds_phien_tro_ly()}

    @app.get("/doi-social/ke-hoach")
    def ds_ds_kh():
        c = _chan()
        if c:
            return c
        return {"ok": True, "muc": v2.ds_ke_hoach()}

    @app.post("/doi-social/ke-hoach/{kid}/duyet")
    def ds_duyet_kh(kid: int):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "ke_hoach": duyet_ke_hoach_va_chay(kid, True)}
        except ValueError as e:
            return _loi(e)

    @app.post("/doi-social/ke-hoach/{kid}/tu-choi")
    def ds_tu_choi_kh(kid: int):
        c = _chan()
        if c:
            return c
        try:
            return {"ok": True, "ke_hoach": duyet_ke_hoach_va_chay(kid, False)}
        except ValueError as e:
            return _loi(e)
