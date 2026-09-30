"""MinMin Mắt Nhà: nhận sự kiện camera từ máy ở nhà, cho dashboard và MinMin đọc lại.

Đường đi của dữ liệu: camera EZVIZ -> Frigate (máy Windows ở nhà, nhận diện tại chỗ) -> MQTT
-> cầu nối minmin-cau -> POST /mat-nha/su-kien ở đây. VPS không vào được mạng nhà, nên chiều
duy nhất là nhà đẩy lên.

- `POST /mat-nha/su-kien`  CÔNG KHAI với hàng rào đăng nhập, xác thực DUY NHẤT bằng header
  `x-mat-nha-token` (so thời gian hằng). Miễn đăng nhập hẹp nhất có thể: đúng đường này, đúng
  phương thức POST (xem `LOI_VAO_CONG_KHAI` và `_auth_guard` trong main.py). GET cùng đường
  vẫn cần đăng nhập.
- `GET  /mat-nha/su-kien`  (cần đăng nhập) lọc theo tu, den, camera, loai, ten, bien_so,
  chi_nguoi_la, limit.
- `GET  /mat-nha/anh/{id}.jpg`, `POST /mat-nha/ma` (tạo/đổi mã ghép nối), `GET /mat-nha/trang-thai`,
  `GET /mat-nha` (trang dashboard).
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse

import mat_nha

# (đường, phương thức) được miễn cổng đăng nhập. main._auth_guard đọc hằng này.
LOI_VAO_CONG_KHAI = ("/mat-nha/su-kien", "POST")
THAN_TOI_DA = 1_500_000          # 1,5MB: đủ cho ảnh 300KB base64 + JSON, chặn thân khổng lồ
_SAI = {}                        # ip -> [mốc các lần sai mã] (chống dò mã)
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600


@dataclass
class MatNhaDeps:
    dashboard_dir: Path


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _bi_chan(ip: str) -> bool:
    now = time.time()
    ds = [t for t in _SAI.get(ip, []) if now - t < _SAI_CUA_SO]
    _SAI[ip] = ds
    if len(_SAI) > 5000:
        _SAI.clear()
    return len(ds) >= _SAI_TOI_DA


def register(app: FastAPI, deps: MatNhaDeps) -> None:
    index = deps.dashboard_dir / "mat-nha" / "index.html"

    @app.get("/mat-nha")
    def mat_nha_page():
        return FileResponse(str(index), media_type="text/html",
                            headers={"Cache-Control": "no-cache"})

    @app.post("/mat-nha/su-kien")
    async def mat_nha_nhan(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return JSONResponse({"error": "sai mã quá nhiều lần, thử lại sau 10 phút"}, status_code=429)
        if not mat_nha.ma_dung(str(request.headers.get("x-mat-nha-token") or "")):
            _SAI.setdefault(ip, []).append(time.time())
            return JSONResponse({"error": "unauthorized", "mat_nha": "sai hoặc thiếu mã ghép nối"},
                                status_code=401)
        body = await request.body()
        if len(body) > THAN_TOI_DA:
            return JSONResponse({"error": "thân yêu cầu quá lớn"}, status_code=413)
        try:
            raw = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return JSONResponse({"error": "JSON hỏng"}, status_code=400)
        try:
            if isinstance(raw, dict) and raw.get("loai") == "nhip":
                return mat_nha.ghi_nhip(raw)
            return mat_nha.luu_su_kien(raw)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get("/mat-nha/su-kien")
    def mat_nha_doc(tu: str = Query(None), den: str = Query(None), camera: str = Query(None),
                    loai: str = Query(None), ten: str = Query(None), bien_so: str = Query(None),
                    chi_nguoi_la: bool = Query(False), limit: int = Query(100)):
        try:
            ds = mat_nha.tim(tu=tu, den=den, camera=camera, loai=loai, ten=ten, bien_so=bien_so,
                             chi_nguoi_la=chi_nguoi_la, limit=limit)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        for ev in ds:
            if ev.get("co_anh"):
                ev["anh"] = f"/mat-nha/anh/{ev['id']}.jpg"
        return {"su_kien": ds, "so": len(ds)}

    @app.get("/mat-nha/anh/{eid}.jpg")
    def mat_nha_anh(eid: str):
        p = mat_nha.doc_anh(eid)
        if not p:
            return JSONResponse({"error": "không có ảnh"}, status_code=404)
        return FileResponse(str(p), media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=86400",
                                     "X-Content-Type-Options": "nosniff"})

    @app.post("/mat-nha/ma")
    def mat_nha_tao_ma():
        # Mã chỉ trả về ĐÚNG MỘT LẦN ở đây; settings giữ bản băm. Không in, không ghi log.
        return {"ok": True, "ma": mat_nha.tao_ma(),
                "luu_y": "Mã chỉ hiện một lần. Tạo mã mới thì cầu nối ở nhà phải dán lại mã mới."}

    @app.get("/mat-nha/trang-thai")
    def mat_nha_trang_thai():
        return mat_nha.trang_thai()
