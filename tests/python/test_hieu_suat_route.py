"""Bảng Hiệu suất Sale: GET /office/hieu-suat (server/routes/hud.py). Không mạng.

    python tests/run.py hieu_suat_route

Phủ: chưa có kết nối thì báo cách nối, gom page của nhiều kết nối bỏ trùng, chỉ lấy kết nối
pancake-thong-ke, kỳ hôm nay/hôm qua/7 ngày đúng ngày, lọc bo_qua theo file cấu hình brain,
chấm điểm và xếp hạng, không lộ token, kỳ lạ về hôm nay.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from _gia_http import GiaHttp, KiemTra
import ket_noi_api as k
import pancake_chat_mcp as m
from routes import hud

check = KiemTra()
T1, T2 = "eyJ.token_mot_bi_mat_aaaa", "eyJ.token_hai_bi_mat_bbbb"
CONNS = [
    {"connector_id": "pancake-thong-ke", "secrets": {"pages": f"598364820025920 | {T1} | Page A"}},
    {"connector_id": "pancake-thong-ke", "secrets": {"pages": f"598364820025920 | {T1} | Page A\n120769791116649 | {T2} | Page B"}},
    {"connector_id": "pancake-pos", "secrets": {"pages": "111111111111 | khong-dung | POS"}},
]


def chay(x):
    return asyncio.run(x)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    ra = chay(hud.hieu_suat_sale(root, "nay", conns=[]))
    check("chưa có kết nối -> báo cách nối, không bịa số", ra["source"] is None and "Thống kê Pancake" in ra["error"] and ra["nhan_vien"] == [], ra)

    ds = hud._hs_pages(CONNS)
    check("gom 2 kết nối, bỏ trùng, bỏ kết nối khác loại", [p["id"] for p in ds] == ["598364820025920", "120769791116649"], ds)

    hom_nay = datetime.now(k.mui_gio()).date()
    for ky, tu, den in (("nay", 0, 0), ("qua", 1, 1), ("7ngay", 6, 0), ("bay", 0, 0)):
        _, a, b = hud._hs_ngay(ky)
        check(f"kỳ {ky}: đúng ngày", a == hom_nay - timedelta(days=tu) and b == hom_nay - timedelta(days=den), (a, b))

    (root / "00 - Dashboard").mkdir()
    (root / "00 - Dashboard" / "hieu-suat-sale.json").write_text(json.dumps({"bo_qua": ["TEN"]}), encoding="utf-8")
    m._DEM.clear()
    gia = GiaHttp().lap()
    users = {"success": True, "data": {"users": {
        "u1": {"user_name": "Khánh Vy", "unique_inbox_count": 195, "inbox_count": 367, "phone_number_count": 22, "average_response_time": 18000},
        "u2": {"user_name": "Hồng Cẩm", "unique_inbox_count": 33, "inbox_count": 88, "phone_number_count": 3, "average_response_time": 54000},
        "u3": {"user_name": "TEN", "unique_inbox_count": 457, "inbox_count": 610, "phone_number_count": 16, "average_response_time": 112000}}}}
    eng = {"success": True, "data": {"categories": [], "series": [], "users_engagements": [
        {"user_id": "u1", "name": "Khánh Vy", "order_count": 4}, {"user_id": "u2", "name": "Hồng Cẩm", "order_count": 16},
        {"user_id": "u3", "name": "TEN", "order_count": 1}]}}
    gia.tra("/pages/598364820025920/statistics/users", users)
    gia.tra("/pages/598364820025920/statistics/customer_engagements", eng)
    gia.tra("/pages/120769791116649/statistics/users", {"success": True, "data": {"users": {}}})
    gia.tra("/pages/120769791116649/statistics/customer_engagements", {"success": True, "data": {"series": []}})
    ra = chay(hud.hieu_suat_sale(root, "qua", conns=CONNS))
    ten = [r["ten"] for r in ra["nhan_vien"]]
    check("bo_qua trong cấu hình loại TEN", "TEN" not in ten and len(ten) == 2, ten)
    check("có nguồn, kỳ Hôm qua", ra["source"] == "Thống kê Pancake" and ra["ten_ky"] == "Hôm qua" and ra["so_page"] == 2, ra)
    vy = ra["nhan_vien"][0]
    check("xếp hạng theo điểm: Khánh Vy #1", vy["ten"] == "Khánh Vy" and vy["hang"] == 1, ra["nhan_vien"])
    check("có đủ cột cho bảng", all(kk in vy for kk in ("diem", "mo_khach", "chot", "toc_do", "vai", "khach", "tin", "sdt", "don", "ty_le", "phan_hoi")), vy)
    check("phản hồi đổi về giây", vy["phan_hoi"] == 18.0, vy["phan_hoi"])
    check("tổng đội không tính TEN", ra["tong"]["don_chot"] == 20 and ra["tong"]["khach_da_tra_loi"] == 228, ra["tong"])
    hq = (hom_nay - timedelta(days=1)).strftime("%d/%m/%Y")
    g = [x for x in gia.goi if "statistics/users" in x["url"]][0]
    check("gọi Pancake đúng ngày hôm qua", g["params"]["date_range"] == f"{hq} 00:00:00 - {hq} 23:59:59", g["params"])
    check("kết quả không lộ token", T1 not in json.dumps(ra, ensure_ascii=False) and T2 not in json.dumps(ra, ensure_ascii=False))

check.ket_thuc()
