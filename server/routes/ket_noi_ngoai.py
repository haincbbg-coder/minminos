"""Kết nối ngoài (26.10.3): các app nhà phát hành tự làm, mở khoá bằng mã kích hoạt, và điều
khoản sử dụng người dùng phải đồng ý.

- `GET  /ket-noi-ngoai`               danh sách app + quyền + mã máy + trạng thái đồng ý điều khoản
- `POST /ket-noi-ngoai/kich-hoat`     nhập mã kích hoạt (form `ma`)
- `POST /ket-noi-ngoai/go-ma`         gỡ một mã đã nhập (form `ma`)
- `POST /ket-noi-ngoai/tao-ma`        CHỈ máy nhà phát hành: tạo mã cho khách (JSON)
- `GET  /dieu-khoan.md`               văn bản điều khoản (markdown)
- `POST /dieu-khoan/dong-y`           ghi nhận đồng ý (form `phan` = chung | zalo | dieu_khien)

Mọi đường đi qua `_auth_guard` của main.py như route khác.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

import giay_phep

# Đổi số này khi sửa NỘI DUNG điều khoản: mọi người dùng sẽ được hỏi đồng ý lại.
DIEU_KHOAN_PHIEN_BAN = "2026-10-01"
PHAN_DIEU_KHOAN = ("chung", "zalo", "dieu_khien")
_KHOA = threading.Lock()


def _dong_y_path() -> Path:
    return giay_phep._thu_muc() / "dong-y-dieu-khoan.json"


def doc_dong_y() -> dict:
    try:
        d = json.loads(_dong_y_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def da_dong_y(phan: str = "chung") -> bool:
    """Đã đồng ý ĐÚNG phiên bản điều khoản hiện hành chưa (đổi phiên bản là phải đồng ý lại)."""
    return (doc_dong_y().get(phan) or {}).get("phien_ban") == DIEU_KHOAN_PHIEN_BAN


def ghi_dong_y(phan: str, ip: str = "") -> dict:
    if phan not in PHAN_DIEU_KHOAN:
        raise ValueError("phần điều khoản không hợp lệ")
    with _KHOA:
        d = doc_dong_y()
        # Giữ bằng chứng giao kết điện tử: phiên bản, thời điểm, máy, địa chỉ mạng.
        d[phan] = {"phien_ban": DIEU_KHOAN_PHIEN_BAN, "luc": round(time.time(), 3),
                   "ma_may": giay_phep.ma_may(), "ip": str(ip or "")[:64]}
        _dong_y_path().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return d[phan]


def trang_thai_dieu_khoan() -> dict:
    return {"phien_ban": DIEU_KHOAN_PHIEN_BAN, **{p: da_dong_y(p) for p in PHAN_DIEU_KHOAN}}


def register(app: FastAPI, dashboard_dir: Path) -> None:
    van_ban = Path(dashboard_dir) / "legal" / "dieu-khoan-su-dung.md"

    @app.get("/ket-noi-ngoai")
    def knn_danh_sach():
        q = giay_phep.quyen()
        return {
            "ok": True,
            "ma_may": giay_phep.ma_may(),
            "nha_phat_hanh": giay_phep.la_nha_phat_hanh(),
            "dieu_khoan": trang_thai_dieu_khoan(),
            "ung_dung": [dict(u, **q.get(u["id"], {})) for u in giay_phep.UNG_DUNG],
        }

    @app.post("/ket-noi-ngoai/kich-hoat")
    def knn_kich_hoat(ma: str = Form(...)):
        if not da_dong_y("chung"):
            return JSONResponse({"ok": False, "error": "Cần đồng ý Điều khoản sử dụng trước."}, status_code=403)
        try:
            p = giay_phep.kich_hoat(ma)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return {"ok": True, "khach": p.get("kh"), "ung_dung": p.get("ung_dung"), "het_han": p.get("het_han")}

    @app.post("/ket-noi-ngoai/go-ma")
    def knn_go_ma(ma: str = Form(...)):
        return {"ok": giay_phep.go_ma(ma)}

    @app.post("/ket-noi-ngoai/tao-ma")
    async def knn_tao_ma(request: Request):
        if not giay_phep.la_nha_phat_hanh():
            return JSONResponse({"ok": False, "error": "Chỉ máy nhà phát hành mới tạo được mã."}, status_code=403)
        try:
            d = await request.json()
        except Exception:
            d = {}
        try:
            ma = giay_phep.tao_ma(d.get("khach"), d.get("ung_dung") or [], d.get("may") or "*",
                                  d.get("het_han") or None, d.get("ghi_chu") or "")
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return {"ok": True, "ma": ma}

    @app.get("/dieu-khoan.md")
    def dieu_khoan_md():
        return FileResponse(str(van_ban), media_type="text/markdown; charset=utf-8",
                            headers={"Cache-Control": "no-cache"})

    @app.post("/dieu-khoan/dong-y")
    def dieu_khoan_dong_y(request: Request, phan: str = Form("chung")):
        try:
            ghi = ghi_dong_y(phan, request.client.host if request.client else "")
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return {"ok": True, "dong_y": ghi, "dieu_khoan": trang_thai_dieu_khoan()}



    # App bundled with MinMin: always retain both the normal auth guard and app license.
    finance_dir = Path(dashboard_dir).parent / "apps" / "business-finance" / "web"
    finance_files = {
        "index.html", "style.css", "design.css", "readability.css", "theme-bridge.css",
        "app.js", "numbers.js", "profit.js", "calculator.js", "business-engine.js",
        "business.js", "audit-ui.js",
    }

    def _serve_business_finance(name: str):
        if name not in finance_files:
            return JSONResponse({"ok": False, "error": "Không có tệp này."}, status_code=404)
        if not giay_phep.da_mo("business_finance"):
            return JSONResponse({"ok": False, "error": "Bảng tính kinh doanh chưa được mở khóa. Nhập mã tại Kết Nối Ngoài."}, status_code=403)
        if not da_dong_y("chung"):
            return JSONResponse({"ok": False, "error": "Cần đồng ý điều khoản sử dụng MinMin trước."}, status_code=403)
        path = finance_dir / name
        if not path.is_file():
            return JSONResponse({"ok": False, "error": "Bộ tệp ứng dụng chưa đầy đủ. Hãy cập nhật MinMin."}, status_code=404)
        return FileResponse(str(path), headers={"Cache-Control": "no-cache"})

    @app.get("/apps/business-finance")
    def business_finance_redirect():
        return RedirectResponse("/apps/business-finance/", status_code=307)

    @app.get("/apps/business-finance/")
    def business_finance_index():
        return _serve_business_finance("index.html")

    @app.get("/apps/business-finance/{name}")
    def business_finance_asset(name: str):
        return _serve_business_finance(name)
