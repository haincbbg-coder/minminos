"""Cầu nối Casso (server/casso_mcp.py). Không mạng.

    python tests/run.py casso_mcp

Phủ: header Apikey, đúng URL, ngày mặc định, chặn pageSize/sort, id chỉ nhận số, tổng hợp tiền
vào/ra theo dấu amount, vòng trang của casso_tong_hop có giới hạn (Casso giới hạn số lần gọi mỗi
phút), dạng lỗi {error != 0}, lỗi không lộ API key, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
from datetime import datetime, timedelta

from _gia_http import GiaHttp, KiemTra
import ket_noi_api as k
import casso_mcp as c

check = KiemTra()
KEY = "AK_CASSO_bi_mat_9f8e7d6c5b4a"


def spec(**them):
    sec = {"api_key": KEY}
    sec.update(them)
    return {"key": "conn-casso-1", "secrets": sec}


def chay(x):
    return asyncio.run(x)


def ok(data):
    return {"error": 0, "message": "success", "data": data}


hom_nay = datetime.now(k.mui_gio()).strftime("%Y-%m-%d")
bay_ngay = (datetime.now(k.mui_gio()) - timedelta(days=7)).strftime("%Y-%m-%d")

ten = [t["name"] for t in chay(c.list_tools({}))]
check("đủ 4 tool", ten == ["casso_thong_tin", "casso_giao_dich", "casso_chi_tiet_giao_dich", "casso_tong_hop"], ten)
ra = chay(c.call("casso_thong_tin", {}, {"secrets": {"api_key": "  "}}))
check("thiếu api_key -> báo rõ", ra.startswith("ERROR") and "api_key" in ra, ra)

# ---- thông tin ----
gia = GiaHttp().lap()
gia.tra("/v2/userInfo", ok({"business": {"id": 1009, "name": "HALIMI"},
                            "bankAccs": [{"id": 87, "bankSubAccId": "123456789", "balance": 64875755}]}))
ra = chay(c.call("casso_thong_tin", {}, spec()))
g = gia.goi[-1]
check("thông tin: đúng URL", g["url"] == "https://oauth.casso.vn/v2/userInfo", g["url"])
check("thông tin: header Apikey", g["headers"].get("Authorization") == f"Apikey {KEY}", g["headers"])
check("thông tin: trả doanh nghiệp + tài khoản", "HALIMI" in ra and "123456789" in ra, ra)

# ---- giao dịch ----
gia.tra("/v2/transactions", ok({"page": 1, "pageSize": 100, "totalRecords": 1, "records": [{"id": 1, "amount": 5000}]}))
chay(c.call("casso_giao_dich", {}, spec()))
g = gia.goi[-1]
p = g["params"]
check("giao dịch: đúng URL", g["url"] == "https://oauth.casso.vn/v2/transactions", g["url"])
check("giao dịch: mặc định 7 ngày, YYYY-MM-DD giờ VN", p["fromDate"] == bay_ngay and p["toDate"] == hom_nay, p)
check("giao dịch: mặc định page 1, pageSize 100, DESC", p["page"] == 1 and p["pageSize"] == 100 and p["sort"] == "DESC", p)
chay(c.call("casso_giao_dich", {"tu_ngay": "2026-09-01", "den_ngay": "2026-09-30", "page": 3,
                                "pageSize": 99999, "sort": "asc"}, spec()))
p = gia.goi[-1]["params"]
check("giao dịch: khoảng ngày theo yêu cầu", p["fromDate"] == "2026-09-01" and p["toDate"] == "2026-09-30", p)
check("giao dịch: pageSize bị chặn 500", p["pageSize"] == 500, p)
check("giao dịch: page và sort ASC", p["page"] == 3 and p["sort"] == "ASC", p)
chay(c.call("casso_giao_dich", {"sort": "DROP TABLE", "page": -4}, spec()))
p = gia.goi[-1]["params"]
check("giao dịch: sort lạ về DESC, page âm về 1", p["sort"] == "DESC" and p["page"] == 1, p)
gia.go()

# ---- id chỉ nhận số, không gọi mạng ----
gia = GiaHttp().lap()
for v in ("../userInfo", "", "12x", "1/2"):
    ra = chay(c.call("casso_chi_tiet_giao_dich", {"id": v}, spec()))
    check(f"chặn id {v!r}", ra.startswith("ERROR"), ra)
check("không request nào đi ra khi id xấu", gia.goi == [], gia.goi)
gia.tra("/v2/transactions/", ok({"id": 5789, "tid": "TF2104", "amount": -193000}))
ra = chay(c.call("casso_chi_tiet_giao_dich", {"id": "5789"}, spec()))
check("chi tiết: đúng URL", gia.goi[-1]["url"] == "https://oauth.casso.vn/v2/transactions/5789")
check("chi tiết: trả dữ liệu", "TF2104" in ra, ra)
gia.go()

# ---- tổng hợp: toán ----
rec = [{"amount": 100000}, {"amount": "250000"}, {"amount": -30000}, {"amount": -1500.5}, {"amount": 0},
       {"amount": "rác"}, "không phải dict"]
th = c.tong_hop(rec)
check("tổng hợp: tiền vào chỉ cộng amount > 0", th["tong_tien_vao"] == 350000, th)
check("tổng hợp: tiền ra là trị tuyệt đối amount < 0", th["tong_tien_ra"] == 31500.5, th)
check("tổng hợp: chênh lệch", th["chenh_lech"] == 318499.5, th)
check("tổng hợp: đếm", th["so_giao_dich"] == 6 and th["so_giao_dich_vao"] == 2 and th["so_giao_dich_ra"] == 2, th)

# ---- tổng hợp tool: một trang ----
gia = GiaHttp().lap()
gia.tra("/v2/transactions", ok({"page": 1, "totalRecords": 3, "records": [{"amount": 10000}, {"amount": 20000},
                                                                           {"amount": -5000}]}))
kq = json.loads(chay(c.call("casso_tong_hop", {}, spec())))
p = gia.goi[-1]["params"]
check("tổng hợp tool: mặc định hôm nay", p["fromDate"] == hom_nay and p["toDate"] == hom_nay, p)
check("tổng hợp tool: pageSize 500", p["pageSize"] == 500)
check("tổng hợp tool: một trang là đủ, gọi 1 lần", len(gia.goi) == 1, len(gia.goi))
check("tổng hợp tool: số liệu", kq["tong_tien_vao"] == 30000 and kq["tong_tien_ra"] == 5000 and "canh_bao" not in kq, kq)
gia.go()

# ---- tổng hợp tool: nhiều trang, dừng đúng lúc ----
gia = GiaHttp().lap()
gia.tra("/v2/transactions", ok({"totalRecords": 700, "records": [{"amount": 1000}] * 500}))
gia.tra("/v2/transactions", ok({"totalRecords": 700, "records": [{"amount": -100}] * 200}))
kq = json.loads(chay(c.call("casso_tong_hop", {"tu_ngay": "2026-10-01", "den_ngay": "2026-10-05"}, spec())))
check("tổng hợp tool: đọc 2 trang rồi dừng", len(gia.goi) == 2 and [g["params"]["page"] for g in gia.goi] == [1, 2],
      [g["params"]["page"] for g in gia.goi])
check("tổng hợp tool: cộng cả hai trang", kq["tong_tien_vao"] == 500000 and kq["tong_tien_ra"] == 20000
      and kq["so_giao_dich"] == 700 and "canh_bao" not in kq, kq)
gia.go()

# ---- tổng hợp tool: vòng trang có trần ----
gia = GiaHttp().lap()
gia.tra("/v2/transactions", ok({"totalRecords": 99999, "records": [{"amount": 1}] * 500}))
kq = json.loads(chay(c.call("casso_tong_hop", {}, spec())))
check(f"tổng hợp tool: tối đa {c.SO_TRANG_TONG_HOP} trang", len(gia.goi) == c.SO_TRANG_TONG_HOP, len(gia.goi))
check("tổng hợp tool: chưa đủ thì cảnh báo", "canh_bao" in kq and kq["so_giao_dich"] == 2500, kq)
gia.go()
gia = GiaHttp().lap()
gia.tra("/v2/transactions", ok({"records": [{"amount": 1}] * 500}))
kq = json.loads(chay(c.call("casso_tong_hop", {}, spec())))
check("tổng hợp tool: không có totalRecords vẫn dừng ở trần", len(gia.goi) == c.SO_TRANG_TONG_HOP and "canh_bao" in kq)
gia.go()
gia = GiaHttp().lap()
gia.tra("/v2/transactions", ok({"totalRecords": 900, "records": [{"amount": 1}] * 500}))
gia.tra("/v2/transactions", {"error": 429, "message": "Too many requests", "data": None})
ra = chay(c.call("casso_tong_hop", {}, spec()))
check("tổng hợp tool: lỗi giữa chừng -> ERROR, không cộng nửa vời", ra.startswith("ERROR") and "429" in ra, ra)
gia.go()

# ---- lỗi ----
gia = GiaHttp().lap()
gia.tra("/v2/userInfo", {"error": 401, "message": "Unauthorized Access", "data": None})
ra = chay(c.call("casso_thong_tin", {}, spec()))
check("error 401 trong body -> ERROR", ra.startswith("ERROR") and "Unauthorized" in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/v2/userInfo", {"error": 401, "message": f"Apikey {KEY} không hợp lệ", "data": None}, code=401)
ra = chay(c.call("casso_thong_tin", {}, spec()))
check("HTTP 401 vọng lại key -> ERROR, KHÔNG lộ key", ra.startswith("ERROR") and KEY not in ra, ra)
gia.tra("/v2/transactions", {"error": 1, "message": f"sai key {KEY}"})
ra = chay(c.call("casso_giao_dich", {}, spec()))
check("lỗi body vọng lại key -> KHÔNG lộ", ra.startswith("ERROR") and KEY not in ra, ra)
gia.nem_loi("/v2/transactions/", TimeoutError("hết giờ với Apikey " + KEY))
ra = chay(c.call("casso_chi_tiet_giao_dich", {"id": "1"}, spec()))
check("lỗi mạng -> ERROR, KHÔNG lộ key", ra.startswith("ERROR") and KEY not in ra, ra)
gia.go()

check("tool lạ -> lỗi", chay(c.call("casso_xoa", {}, spec())).startswith("ERROR"))
check.ket_thuc()
