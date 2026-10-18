"""Webhook: đường công khai `POST /hook/<mã>` cho hệ thống ngoài gọi vào, và API quản lý
(cần đăng nhập) cho trang Việc định kỳ. Logic nằm ở server/webhooks.py."""
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse

import webhooks

# (mẫu đường, phương thức) được miễn cổng đăng nhập. main._auth_guard đọc hằng này.
LOI_VAO_CONG_KHAI = (r"/hook/[A-Za-z0-9_-]{20,80}", "POST")
_SAI = {}                        # ip -> mốc các lần sai mã (chống dò mã)
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600


@dataclass
class WebhooksDeps:
    # reminders_feature, lấy trễ vì nó được tạo trước nhưng giữ ở main.
    nhac_hen: Callable[[], object]
    duong_dan_goc: Callable[[Request], str]


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


async def chay_viec(deps: WebhooksDeps, w: dict, than: bytes, ctype: str = "") -> dict:
    """Xếp việc của webhook vào cơ chế nhắc hẹn (chạy ngay, chế độ task)."""
    feat = deps.nhac_hen()
    text = webhooks.soan_loi_nhac(w, than, ctype)
    async with feat._io:
        rem = feat._create(w.get("brain") or "brain", text, delay_min=0, mode="task",
                           label=f"Webhook: {w.get('ten')}", created_by="webhook",
                           allow_no_channel=True, muc_quyen=w.get("muc_quyen") or "suggest")
    return {"id": rem["id"]}


def register(app: FastAPI, deps: WebhooksDeps) -> None:

    @app.post("/hook/{token}")
    async def hook_vao(token: str, request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return JSONResponse({"ok": False, "error": "sai quá nhiều lần"}, status_code=429)
        w = webhooks.tim_theo_token(token)
        if not w:
            _SAI.setdefault(ip, []).append(time.time())
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        than = await _doc_than(request)
        if than is None:
            return JSONResponse({"ok": False, "error": "thân quá lớn"}, status_code=413)
        kq = webhooks.nhan_goi(w["id"], webhooks.dau_lan_giao(dict(request.headers), than))
        if kq == "tat":
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        if kq == "trung":
            return {"ok": True, "trung": True}
        if kq == "qua_tran":
            return JSONResponse({"ok": False, "error": "quá số lần cho phép mỗi giờ"}, status_code=429,
                                headers={"Retry-After": "600"})
        try:
            r = await chay_viec(deps, w, than, request.headers.get("content-type", ""))
        except Exception as e:
            print(f"[webhook {w['id']}] xếp việc lỗi: {type(e).__name__}: {e}", file=sys.stderr)
            return JSONResponse({"ok": False, "error": "không xếp được việc"}, status_code=500)
        return {"ok": True, "queued": r["id"]}

    def _url(request: Request, tok: str) -> str:
        goc = str(request.base_url).rstrip("/")
        return f"{goc}/hook/{tok}"

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
        ok = webhooks.dat(str(p.get("id") or ""), bat=p.get("bat"), muc_quyen=p.get("muc_quyen"),
                          viec=p.get("viec"), ten=p.get("ten"))
        return {"ok": ok, "error": "" if ok else "không thấy webhook này"}

    @app.post("/webhooks/xoa")
    def wh_xoa(payload: dict = Body(None)):
        ok = webhooks.xoa(str((payload or {}).get("id") or ""))
        return {"ok": ok, "error": "" if ok else "không thấy webhook này"}

    @app.post("/webhooks/thu")
    async def wh_thu(payload: dict = Body(None)):
        """Gọi thử một webhook bằng dữ liệu mẫu (đã đăng nhập, không cần mã)."""
        wid = str((payload or {}).get("id") or "")
        w = next((x for x in webhooks._doc() if x.get("id") == wid), None)
        if not w:
            return {"ok": False, "error": "không thấy webhook này"}
        mau = b'{"su_kien": "thu", "ghi_chu": "Gui thu tu trang Viec dinh ky"}'
        r = await chay_viec(deps, w, mau, "application/json")
        return {"ok": True, "queued": r["id"]}
