"""Tín hiệu dùng (26.10.69): hai route mỏng bọc quanh tin_hieu.py.

- `POST /tin-hieu`          JSON {loai, doi_tuong?}  ghi một tín hiệu (whitelist, không nội dung)
- `GET  /tin-hieu/tom-tat`  trang hay dùng + đếm chat (?ngay=30)

Qua `_auth_guard` và `_csrf_guard` của main.py như mọi route khác.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import tin_hieu


def register(app: FastAPI) -> None:
    @app.post("/tin-hieu")
    async def th_ghi(request: Request):
        try:
            b = await request.json()
        except Exception:
            b = None
        if not isinstance(b, dict):
            return JSONResponse({"ok": False, "error": "Cần JSON {loai, doi_tuong}."}, status_code=400)
        ok = tin_hieu.ghi(b.get("loai", ""), b.get("doi_tuong", ""))
        if not ok:
            return JSONResponse({"ok": False, "error": "Tín hiệu không hợp lệ."}, status_code=400)
        return {"ok": True}

    @app.get("/tin-hieu/tom-tat")
    def th_tom_tat(ngay: int = 30):
        return {"ok": True, **tin_hieu.tom_tat(ngay)}
