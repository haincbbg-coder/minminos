"""Đường HTTP của kênh Zalo OA trong Chatbot (26.10.314).

    POST /zalo-oa/webhook             Zalo gọi vào (CÔNG KHAI, không cookie): kiểm chữ ký bằng OA secret key
    GET  /zalo-oa/webhook-info        địa chỉ webhook và các mã xác thực tên miền đã lưu, cho form Thêm kênh
    POST /zalo-oa/xac-thuc            lưu (hoặc xoá) mã xác thực tên miền chủ dán từ developers.zalo.me
    GET  /zalo_verifier<mã>.html      file Zalo tải về để xác thực tên miền (CÔNG KHAI, chỉ mã đã lưu)
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

import web_security
import zalo_oa_kenh

router = APIRouter()

THAN_TOI_DA = 2_000_000


def dia_chi_webhook(request: Request) -> str:
    goc = web_security.external_base(request.url.scheme, request.url.netloc,
                                     request.headers.get("x-forwarded-proto", ""),
                                     request.headers.get("x-forwarded-host", ""))
    return goc + "/zalo-oa/webhook"


@router.post("/zalo-oa/webhook")
async def zalo_oa_webhook(request: Request):
    """Địa chỉ công khai: chưa khớp chữ ký thì không tin gì, trả 401 và không giao cho bot nào. Khớp thì trả 200
    ngay (Zalo muốn trả lời trong khoảng 2 giây, chậm là gửi lại), sự kiện chạy nền."""
    than = await request.body()
    if len(than) > THAN_TOI_DA:
        return PlainTextResponse("too large", status_code=413)
    ky = request.headers.get("x-zevent-signature", "") or request.headers.get("mac", "")
    if not zalo_oa_kenh.hop_le_chu_ky(than, ky, zalo_oa_kenh.cap_khoa_webhook()):
        return PlainTextResponse("bad signature", status_code=401)
    try:
        d = json.loads(than.decode("utf-8") or "{}")
    except Exception:
        return PlainTextResponse("bad json", status_code=400)
    n = await zalo_oa_kenh.nhan_webhook(d if isinstance(d, dict) else {})
    return {"ok": True, "events": n}


@router.get("/zalo-oa/webhook-info")
async def zalo_oa_webhook_info(request: Request):
    url = dia_chi_webhook(request)
    return {"ok": True, "webhook_url": url, "https": url.startswith("https://"),
            "ma_xac_thuc": zalo_oa_kenh.ma_xac_thuc()}


@router.post("/zalo-oa/xac-thuc")
async def zalo_oa_xac_thuc(request: Request):
    """Lưu mã Zalo đưa (tên file, thẻ meta hoặc chính mã) để /zalo_verifier<mã>.html trả lời, rồi chủ bấm Xác thực
    ở developers.zalo.me. `xoa: true` thì bỏ mã."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    ma = zalo_oa_kenh.doc_ma_xac_thuc((body or {}).get("ma"))
    if not ma:
        return JSONResponse({"ok": False, "error": "Không đọc được mã. Dán tên file zalo_verifier...html, thẻ meta "
                                                   "hoặc chính mã đó."}, status_code=400)
    ds = zalo_oa_kenh.luu_ma_xac_thuc(ma, xoa=bool((body or {}).get("xoa")))
    return {"ok": True, "ma": ma, "ma_xac_thuc": ds, "file": f"/zalo_verifier{ma}.html"}


@router.get("/zalo_verifier{ma}.html")
async def zalo_oa_file_xac_thuc(ma: str):
    if ma not in zalo_oa_kenh.ma_xac_thuc():
        return PlainTextResponse("not found", status_code=404)
    return HTMLResponse(zalo_oa_kenh.html_xac_thuc(ma))


def register(app) -> None:
    app.include_router(router)
