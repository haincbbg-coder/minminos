"""Văn phòng AI 3D: `GET /office/events` cho trình duyệt hỏi sự kiện agent đang làm gì.

Chỉ đọc vòng đệm trong RAM của `office_bus`; không ghi gì, không gọi dịch vụ ngoài.
"""
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

import office_bus


def register(app: FastAPI) -> None:
    @app.get("/office/events")
    def office_events(since: int = Query(0), brain: str = Query("")):
        return office_bus.since(since, brain)

    @app.get("/office-3d")
    def office_page():
        """Trang riêng cho văn phòng AI 3D (mở ở cửa sổ mới / màn phụ)."""
        f = Path(__file__).resolve().parent.parent.parent / "dashboard" / "office.html"
        return FileResponse(str(f), media_type="text/html", headers={"Cache-Control": "no-cache"})
