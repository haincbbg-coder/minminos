"""Văn phòng AI 3D: `GET /office/events` cho trình duyệt hỏi sự kiện agent đang làm gì.

Chỉ đọc vòng đệm trong RAM của `office_bus`; không ghi gì, không gọi dịch vụ ngoài.
"""
from fastapi import FastAPI, Query

import office_bus


def register(app: FastAPI) -> None:
    @app.get("/office/events")
    def office_events(since: int = Query(0), brain: str = Query("")):
        return office_bus.since(since, brain)
