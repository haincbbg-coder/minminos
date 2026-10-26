"""Facebook nhiều tài khoản (26.10.252): HTTP cho khối Facebook trên trang Kết nối và thẻ duyệt bật/tắt camp.

Cần đăng nhập dashboard như mọi đường khác (không có lối vào công khai).
    GET  /meta/tai-san?lam_moi=0|1         Trang + tài khoản quảng cáo gộp theo tài khoản Facebook
    GET  /meta/soi-quyen?fb_id=            quyền token, cái chưa giao và vì sao
    POST /meta/hoi-trang  (form fb_id, q)  hỏi thẳng Facebook về một Trang
    GET  /meta-ads/duyet/{id}              đề xuất bật/tắt (không token)
    POST /meta-ads/duyet/{id} (form hanh_dong=duyet|tu_choi|sua|hoan_tac)
Không tool nào của model gọi tới đây. POST duyệt còn đòi header `Sec-Fetch-Site: same-origin` mà trình duyệt tự gửi:
đây là vạch giảm tốc cho lệnh curl chứ không phải tường bảo mật - não CLI ở mức Toàn quyền có shell vẫn giả được
(xem docstring server/meta_ads_duyet.py).
"""
from __future__ import annotations

import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import meta_ads_duyet
import meta_tai_san

_RE_ID = re.compile(r"^[a-f0-9]{8,32}$")


def _loi(msg, ma: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "loi": str(msg)}, status_code=ma)


def register(app: FastAPI, ai_dang_dung=lambda request: "chủ") -> None:
    @app.get("/meta/tai-san")
    async def meta_tai_san_get(lam_moi: int = 0):
        try:
            return await meta_tai_san.tai_san(lam_moi=bool(lam_moi))
        except Exception as e:
            return _loi(f"{type(e).__name__}: {e}", 500)

    @app.get("/meta/soi-quyen")
    async def meta_soi_quyen_get(fb_id: str = ""):
        if not fb_id:
            return _loi("thiếu fb_id")
        try:
            return await meta_tai_san.soi_quyen(fb_id)
        except Exception as e:
            return _loi(f"{type(e).__name__}: {e}", 500)

    @app.post("/meta/hoi-trang")
    async def meta_hoi_trang_post(request: Request):
        f = await request.form()
        fb_id, q = str(f.get("fb_id") or ""), str(f.get("q") or "")[:300]
        if not fb_id:
            return _loi("thiếu fb_id")
        try:
            return await meta_tai_san.hoi_trang(fb_id, q)
        except Exception as e:
            return _loi(f"{type(e).__name__}: {e}", 500)

    @app.get("/meta-ads/duyet/{rid}")
    async def meta_ads_duyet_get(rid: str):
        if not _RE_ID.match(rid or ""):
            return _loi("mã đề xuất không hợp lệ")
        v = meta_ads_duyet.xem(rid)
        return v if v else _loi("Không có đề xuất này.", 404)

    @app.post("/meta-ads/duyet/{rid}")
    async def meta_ads_duyet_post(rid: str, request: Request):
        if not _RE_ID.match(rid or ""):
            return _loi("mã đề xuất không hợp lệ")
        if str(request.headers.get("sec-fetch-site") or "") != "same-origin":
            return _loi("Chỉ duyệt được bằng nút trên dashboard hoặc trên Telegram.", 403)
        f = await request.form()
        hd = str(f.get("hanh_dong") or "")
        if hd not in ("duyet", "tu_choi", "sua", "hoan_tac"):
            return _loi("hanh_dong phải là duyet, tu_choi, sua hoặc hoan_tac")
        v = await meta_ads_duyet.quyet(rid, hd, ai=ai_dang_dung(request), nguon="dashboard")
        if not v.get("ok") and v.get("loi"):
            return _loi(v["loi"], 404)
        return v
