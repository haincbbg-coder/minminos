"""Webhook: đường công khai `POST /hook/<mã>` cho hệ thống ngoài gọi vào, và API quản lý (cần
đăng nhập). Cấu hình ở server/webhooks.py, hòm sự kiện bền ở webhook_su_kien.py, kiểm chữ ký ở
webhook_ky.py, bộ chạy nền ở webhook_chay.py (26.10.273).

Đường nhận làm đúng bốn việc rồi trả lời ngay (nhà gửi như POSCake, Casso chờ vài giây):
mã đúng -> chữ ký đúng (nếu webhook bật kiểm) -> LƯU sự kiện -> đánh thức bộ chạy nền.
Không gọi AI, không gửi gì ra ngoài trong lúc nhà gửi còn chờ.
"""
import asyncio
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

import webhook_chay
import webhook_ky
import webhook_su_kien as sk
import webhooks

# (mẫu đường, phương thức) được miễn cổng đăng nhập. main._auth_guard đọc hằng này.
LOI_VAO_CONG_KHAI = (r"/hook/[A-Za-z0-9_-]{20,80}", "POST")
_SAI = {}                        # ip -> mốc các lần sai mã / sai chữ ký (chống dò)
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600
_BO_CHAY: Optional[webhook_chay.BoChay] = None


@dataclass
class WebhooksDeps:
    # (brain, lời nhắc, mức quyền) -> (kết quả, lỗi). main nối vào bộ chạy việc của nhắc hẹn.
    chay_ai: Callable[[str, str, str], Awaitable[tuple]]
    # (tên webhook, câu) -> báo chủ (hòm thư + Telegram)
    bao_chu: Optional[Callable[[str, str], Awaitable]] = None
    tu_chay: bool = True         # test tắt để tự lái bộ chạy


def bo_chay() -> Optional[webhook_chay.BoChay]:
    return _BO_CHAY


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _bi_chan(ip: str) -> bool:
    now = time.time()
    ds = [t for t in _SAI.get(ip, []) if now - t < _SAI_CUA_SO]
    _SAI[ip] = ds
    if len(_SAI) > 5000:
        _SAI.clear()
    return len(ds) >= _SAI_TOI_DA


async def _doc_than(request: Request) -> Optional[bytes]:
    try:
        if int(request.headers.get("content-length") or 0) > webhooks.THAN_TOI_DA:
            return None
    except ValueError:
        return None
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > webhooks.THAN_TOI_DA:
            return None
    return bytes(buf)


def _xem_truoc(w: dict, than: bytes, ctype: str) -> dict:
    """Webhook SẼ làm gì với thân này, theo cấu hình hiện tại. Không lưu, không gửi, không gọi AI."""
    doc, kieu = sk.doc_than(than, ctype)
    khop, ly_do = sk.xet_loc(w.get("loc") or [], doc)
    hd = []
    for a in webhook_chay.chuan_hanh_dong(w.get("hanh_dong")):
        if a["loai"] == "ai":
            hd.append({"id": a["id"], "loai": "ai",
                       "mo_ta": f"MinMin chạy việc \"{(w.get('viec') or '')[:80]}\" ở mức {w.get('muc_quyen')}"})
        else:
            hd.append({"id": a["id"], "loai": "chuyen_tiep",
                       "mo_ta": f"Gửi nguyên thân tới {webhook_chay.an_url(a['url'])}"})
    return {"kieu_than": kieu, "se_chay": khop, "ly_do": ly_do, "hanh_dong": hd if khop else []}


def register(app: FastAPI, deps: WebhooksDeps) -> None:
    global _BO_CHAY

    async def _bao(ten: str, text: str):
        if deps.bao_chu:
            await deps.bao_chu(ten, text)

    _BO_CHAY = webhook_chay.BoChay(webhook_chay.ChayDeps(
        lay_hook=webhooks.lay_day_du, chay_ai=deps.chay_ai, bao_chu=_bao))

    if deps.tu_chay:
        @app.on_event("startup")
        async def _webhook_bat_dau():
            try:
                _BO_CHAY.bat_dau()
            except Exception as e:
                print(f"[webhook] không khởi động được bộ chạy: {type(e).__name__}", file=sys.stderr)

    @app.post("/hook/{token}")
    async def hook_vao(token: str, request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return JSONResponse({"ok": False, "error": "sai quá nhiều lần"}, status_code=429,
                                headers={"Retry-After": "600"})
        w = webhooks.tim_theo_token(token)
        if not w or not w.get("bat", True):
            if not w:
                _SAI.setdefault(ip, []).append(time.time())
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        than = await _doc_than(request)
        if than is None:
            return JSONResponse({"ok": False, "error": "thân quá lớn"}, status_code=413)
        xt = w.get("xac_thuc") or {"kieu": "none"}
        if xt.get("kieu", "none") != "none":
            dung, ly_do = webhook_ky.kiem(xt, webhooks.khoa_ky(w), request.headers, than)
            if not dung:
                _SAI.setdefault(ip, []).append(time.time())
                print(f"[webhook {w['id']}] từ chối: {ly_do}", file=sys.stderr)
                return JSONResponse({"ok": False, "error": "chữ ký không hợp lệ"}, status_code=401)
        ctype = request.headers.get("content-type", "")
        doc, _ = sk.doc_than(than, ctype)
        khoa = sk.khoa_giao(request.headers, than,
                            webhook_ky.ma_lan_giao(xt.get("kieu", "none"), request.headers, doc),
                            bool(w.get("trung_theo_don")))
        qua_tran = await asyncio.to_thread(sk.dem_gio, w["id"]) >= webhooks.TRAN_MOI_GIO
        try:
            kq = await asyncio.to_thread(sk.nhan, w["id"], than, ctype, webhook_ky.header_luu(request.headers),
                                         khoa, float(w.get("trung_gio") or webhooks.TRUNG_GIO_MAC_DINH))
        except Exception as e:
            print(f"[webhook {w['id']}] lưu sự kiện lỗi: {type(e).__name__}", file=sys.stderr)
            return JSONResponse({"ok": False, "error": "không lưu được sự kiện"}, status_code=503,
                                headers={"Retry-After": "30"})
        if kq["trung"]:
            return {"ok": True, "trung": True, "su_kien": kq["id"]}
        await asyncio.to_thread(webhooks.ghi_nhan_goi, w["id"])
        if qua_tran:
            # Vẫn LƯU (không mất đơn), chỉ không tự chạy: chủ xem rồi bấm chạy lại.
            sk.dat_trang_thai(kq["id"], sk.BI_CHAN, f"quá {webhooks.TRAN_MOI_GIO} lần trong một giờ",
                              buoc="chan", chi_tiet="quá trần mỗi giờ")
            return {"ok": True, "su_kien": kq["id"], "bi_chan": True}
        if _BO_CHAY:
            _BO_CHAY.danh_thuc()
        return {"ok": True, "su_kien": kq["id"]}

    def _url(request: Request, tok: str) -> str:
        goc = str(request.base_url).rstrip("/")
        return f"{goc}/hook/{tok}"

    @app.get("/webhook")
    def wh_trang():
        """Trang Webhook (Cấu hình / Sự kiện / Tình trạng). Cần đăng nhập như mọi trang."""
        return FileResponse(str(Path(__file__).resolve().parents[2] / "dashboard" / "webhook" / "index.html"),
                            media_type="text/html", headers={"Cache-Control": "no-cache"})

    @app.get("/webhooks")
    def wh_ds():
        return {"ok": True, "webhooks": webhooks.danh_sach()}

    @app.post("/webhooks")
    def wh_tao(request: Request, payload: dict = Body(None)):
        p = payload or {}
        try:
            r = webhooks.tao(p.get("ten"), p.get("viec"), p.get("muc_quyen") or "suggest",
                             p.get("brain") or "brain")
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "webhook": r["webhook"], "token": r["token"], "url": _url(request, r["token"])}

    @app.post("/webhooks/doi-token")
    def wh_doi(request: Request, payload: dict = Body(None)):
        tok = webhooks.doi_token(str((payload or {}).get("id") or ""))
        if not tok:
            return {"ok": False, "error": "không thấy webhook này"}
        return {"ok": True, "token": tok, "url": _url(request, tok)}

    @app.post("/webhooks/cap-nhat")
    def wh_capnhat(payload: dict = Body(None)):
        p = payload or {}
        try:
            ok = webhooks.dat(str(p.get("id") or ""), bat=p.get("bat"), muc_quyen=p.get("muc_quyen"),
                              viec=p.get("viec"), ten=p.get("ten"), loc=p.get("loc"),
                              hanh_dong=p.get("hanh_dong"), xac_thuc=p.get("xac_thuc"),
                              khoa=p.get("khoa"), tam_dung=p.get("tam_dung"), trung_gio=p.get("trung_gio"),
                              trung_theo_don=p.get("trung_theo_don"))
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if ok and p.get("tam_dung") is False and _BO_CHAY:
            _BO_CHAY.danh_thuc()
        return {"ok": ok, "error": "" if ok else "không thấy webhook này"}

    @app.post("/webhooks/xoa")
    def wh_xoa(payload: dict = Body(None)):
        ok = webhooks.xoa(str((payload or {}).get("id") or ""))
        return {"ok": ok, "error": "" if ok else "không thấy webhook này"}

    def _than_thu(p: dict) -> tuple:
        than = p.get("than")
        if than in (None, ""):
            return b'{"su_kien": "thu", "ghi_chu": "Gui thu tu trang Webhook"}', "application/json"
        if not isinstance(than, str):
            import json
            return json.dumps(than, ensure_ascii=False).encode("utf-8"), "application/json"
        b = than.encode("utf-8")[:webhooks.THAN_TOI_DA]
        return b, ("application/json" if than.lstrip()[:1] in ("{", "[") else "text/plain")

    @app.post("/webhooks/xem-truoc")
    def wh_xem_truoc(payload: dict = Body(None)):
        """Xem trước lần gửi thử: thân này qua bộ lọc không, sẽ chạy những gì. Không làm gì thật."""
        p = payload or {}
        w = webhooks.lay_day_du(str(p.get("id") or ""))
        if not w:
            return {"ok": False, "error": "không thấy webhook này"}
        than, ct = _than_thu(p)
        return {"ok": True, **_xem_truoc(w, than, ct)}

    @app.post("/webhooks/thu")
    async def wh_thu(payload: dict = Body(None)):
        """Gửi thử THẬT (đã đăng nhập, không cần mã): lưu thành sự kiện có nhãn thử rồi chạy như thật.
        Mỗi lần thử có khoá riêng nên không bao giờ bị coi là trùng với đơn thật."""
        p = payload or {}
        w = webhooks.lay_day_du(str(p.get("id") or ""))
        if not w:
            return {"ok": False, "error": "không thấy webhook này"}
        than, ct = _than_thu(p)
        kq = await asyncio.to_thread(sk.nhan, w["id"], than, ct, {"content-type": ct},
                                     "thu:" + uuid.uuid4().hex, 0, True)
        if _BO_CHAY:
            _BO_CHAY.danh_thuc()
        return {"ok": True, "su_kien": kq["id"], **_xem_truoc(w, than, ct)}

    # ---------------- Sự kiện và Tình trạng
    @app.get("/webhooks/su-kien")
    def wh_su_kien(request: Request):
        q = request.query_params
        try:
            gh = int(q.get("gioi_han") or 100)
        except ValueError:
            gh = 100
        ds = sk.danh_sach(str(q.get("id") or ""), str(q.get("trang_thai") or ""), gh)
        return {"ok": True, "su_kien": ds}

    @app.get("/webhooks/su-kien/chi-tiet")
    def wh_chi_tiet(request: Request):
        """Một sự kiện: thân ĐÃ CHE (khách, nhân viên, link, khoá), dòng thời gian, kết quả từng hành động."""
        ev = sk.lay(str(request.query_params.get("sk") or ""))
        if not ev:
            return {"ok": False, "error": "không thấy sự kiện này"}
        than = ev.pop("than", b"")
        ev["than_che"] = sk.xem_che(than, ev.get("ctype", ""))
        ev["dai"] = len(than)
        ev["dong_thoi_gian"] = sk.dong_thoi_gian(ev["id"])
        ev.pop("khoa_giao", None)
        ev["thu"] = bool(ev.get("thu"))
        return {"ok": True, "su_kien": ev}

    @app.post("/webhooks/su-kien/chay-lai")
    def wh_chay_lai(payload: dict = Body(None)):
        ok = sk.chay_lai(str((payload or {}).get("sk") or ""))
        if ok and _BO_CHAY:
            _BO_CHAY.danh_thuc()
        return {"ok": ok, "error": "" if ok else "sự kiện đang chạy hoặc không còn"}

    @app.post("/webhooks/su-kien/chay-lai-bi-chan")
    def wh_chay_lai_het(payload: dict = Body(None)):
        n = sk.chay_lai_bi_chan(str((payload or {}).get("id") or ""))
        if n and _BO_CHAY:
            _BO_CHAY.danh_thuc()
        return {"ok": True, "so": n}

    @app.get("/webhooks/tinh-trang")
    def wh_tinh_trang():
        ds = webhooks.danh_sach()
        tt = sk.tinh_trang([w["id"] for w in ds])
        return {"ok": True, **tt, "dang_chay": bool(_BO_CHAY and _BO_CHAY._task and not _BO_CHAY._task.done())}

