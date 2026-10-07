"""Cầu nối SePay (server/sepay_mcp.py). Không mạng.

    python tests/run.py sepay_mcp

Phủ: header Bearer, đúng URL, ngày mặc định 7 ngày (giờ VN, đủ giờ đầu/cuối ngày), giới hạn
limit, id chỉ nhận số (chặn "../x" mà không gọi mạng), cộng tiền vào/ra theo tài khoản, các dạng
lỗi của SePay, lỗi không lộ token, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
from datetime import datetime, timedelta

from _gia_http import GiaHttp, KiemTra
import ket_noi_api as k
import sepay_mcp as s

check = KiemTra()
TOKEN = "SEPAY-TOKEN-BI-MAT-ABCDEF123456"
OK = {"status": 200, "error": None, "messages": {"success": True}}


def spec(**them):
    sec = {"api_token": TOKEN}
    sec.update(them)
    return {"key": "conn-sepay-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


hom_nay = datetime.now(k.mui_gio()).strftime("%Y-%m-%d")
bay_ngay = (datetime.now(k.mui_gio()) - timedelta(days=7)).strftime("%Y-%m-%d")

# ---- 1. danh sách tool ----
ten = [t["name"] for t in chay(s.list_tools({}))]
check("đủ 5 tool", ten == ["sepay_tai_khoan_ngan_hang", "sepay_giao_dich", "sepay_chi_tiet_giao_dich",
                          "sepay_dem_giao_dich", "sepay_tong_hop"], ten)

# ---- 2. thiếu ô ----
ra = chay(s.call("sepay_giao_dich", {}, {"secrets": {}}))
check("thiếu api_token -> báo rõ", ra.startswith("ERROR") and "api_token" in ra, ra)

# ---- 3. tài khoản ngân hàng: header, URL ----
gia = GiaHttp().lap()
gia.tra("/bankaccounts/list", {**OK, "bankaccounts": [{"id": "1", "account_number": "0071000888999",
                                                       "bank_short_name": "Vietcombank"}]})
ra = chay(s.call("sepay_tai_khoan_ngan_hang", {}, spec()))
g = gia.goi[-1]
check("tài khoản: đúng URL", g["url"] == "https://my.sepay.vn/userapi/bankaccounts/list", g["url"])
check("tài khoản: GET", g["method"] == "GET")
check("tài khoản: header Bearer", g["headers"].get("Authorization") == f"Bearer {TOKEN}", g["headers"])
check("tài khoản: trả danh sách", "0071000888999" in ra and "Vietcombank" in ra, ra)
check("tài khoản: không lộ token trong kết quả", TOKEN not in ra)

# ---- 4. giao dịch: ngày mặc định, limit, lọc ----
gia.tra("/transactions/list", {**OK, "transactions": [{"id": "9", "amount_in": "50000.00"}]})
ra = chay(s.call("sepay_giao_dich", {}, spec()))
p = gia.goi[-1]["params"]
check("giao dịch: đúng URL", gia.goi[-1]["url"] == "https://my.sepay.vn/userapi/transactions/list")
check("giao dịch: mặc định đến hết hôm nay (giờ VN)", p["transaction_date_max"] == hom_nay + " 23:59:59", p)
check("giao dịch: mặc định từ 7 ngày trước", p["transaction_date_min"] == bay_ngay + " 00:00:00", p)
check("giao dịch: limit mặc định 100", p["limit"] == 100, p)
check("giao dịch: không gửi lọc rỗng", "account_number" not in p and "since_id" not in p
      and "amount_in" not in p and "reference_number" not in p, p)
check("giao dịch: kết quả có giao dịch", '"so_giao_dich": 1' in ra, ra)

chay(s.call("sepay_giao_dich", {"tu_ngay": "2026-09-01", "den_ngay": "2026-09-03", "limit": 99999,
                                "account_number": "0071000888999", "since_id": "120", "reference_number": "FT26245",
                                "amount_in": "150000", "amount_out": 20000}, spec()))
p = gia.goi[-1]["params"]
check("giao dịch: khoảng ngày theo yêu cầu", p["transaction_date_min"] == "2026-09-01 00:00:00"
      and p["transaction_date_max"] == "2026-09-03 23:59:59", p)
check("giao dịch: limit bị chặn 5000", p["limit"] == 5000, p)
check("giao dịch: lọc tài khoản/since_id/mã tham chiếu", p["account_number"] == "0071000888999"
      and p["since_id"] == "120" and p["reference_number"] == "FT26245", p)
check("giao dịch: lọc số tiền", p["amount_in"] == "150000" and p["amount_out"] == "20000", p)
chay(s.call("sepay_giao_dich", {"tu_ngay": "2026-09-05", "den_ngay": "2026-09-01"}, spec()))
p = gia.goi[-1]["params"]
check("giao dịch: ngày đảo ngược tự đổi chỗ", p["transaction_date_min"].startswith("2026-09-01")
      and p["transaction_date_max"].startswith("2026-09-05"), p)
gia.go()

# ---- 5. đầu vào xấu bị chặn TRƯỚC khi gọi mạng ----
gia = GiaHttp().lap()
for ten_tool, args, mo_ta in [
    ("sepay_chi_tiet_giao_dich", {"id": "../bankaccounts/list"}, "id '../x'"),
    ("sepay_chi_tiet_giao_dich", {"id": ""}, "id rỗng"),
    ("sepay_chi_tiet_giao_dich", {"id": "12a"}, "id có chữ"),
    ("sepay_giao_dich", {"account_number": "123&limit=1"}, "account_number có ký tự lạ"),
    ("sepay_giao_dich", {"since_id": "1 OR 1"}, "since_id không phải số"),
    ("sepay_giao_dich", {"amount_in": "-5"}, "amount_in âm"),
    ("sepay_giao_dich", {"amount_out": "abc"}, "amount_out chữ"),
    ("sepay_giao_dich", {"reference_number": "a/../b"}, "reference_number có /"),
    ("sepay_dem_giao_dich", {"account_number": "../x"}, "đếm: account_number '../x'"),
]:
    ra = chay(s.call(ten_tool, args, spec()))
    check(f"chặn {mo_ta}", ra.startswith("ERROR"), ra)
check("không request nào đi ra khi đầu vào xấu", gia.goi == [], gia.goi)
gia.go()

# ---- 6. chi tiết + đếm ----
gia = GiaHttp().lap()
gia.tra("/transactions/details/", {**OK, "transaction": {"id": "777", "amount_in": "1000.00"}})
ra = chay(s.call("sepay_chi_tiet_giao_dich", {"id": " 777 "}, spec()))
check("chi tiết: đúng URL", gia.goi[-1]["url"] == "https://my.sepay.vn/userapi/transactions/details/777")
check("chi tiết: trả transaction", '"id": "777"' in ra, ra)
gia.tra("/transactions/count", {**OK, "count_transactions": 2322})
ra = chay(s.call("sepay_dem_giao_dich", {"account_number": "0071000888999"}, spec()))
p = gia.goi[-1]["params"]
check("đếm: đúng URL", gia.goi[-1]["url"] == "https://my.sepay.vn/userapi/transactions/count")
check("đếm: cùng bộ lọc", p["account_number"] == "0071000888999" and p["transaction_date_max"] == hom_nay + " 23:59:59", p)
check("đếm: không gửi limit", "limit" not in p)
check("đếm: trả con số", json.loads(ra)["so_giao_dich"] == 2322, ra)
gia.go()

# ---- 7. tổng hợp ----
gd = [
    {"id": "1", "account_number": "A1", "bank_brand_name": "VCB", "amount_in": "100000.00", "amount_out": "0.00"},
    {"id": "2", "account_number": "A1", "bank_brand_name": "VCB", "amount_in": "250000.50", "amount_out": "0.00"},
    {"id": "3", "account_number": "B2", "bank_brand_name": "MB", "amount_in": "0.00", "amount_out": "30000.00"},
    {"id": "4", "account_number": "B2", "bank_brand_name": "MB", "amount_in": "1,000.00", "amount_out": None},
    {"id": "5", "account_number": "B2", "bank_brand_name": "MB", "amount_in": "rác", "amount_out": "NaN"},
]
th = s.tong_hop(gd)
check("tổng hợp: tiền vào", th["tong_tien_vao"] == 351000.5, th)
check("tổng hợp: tiền ra", th["tong_tien_ra"] == 30000, th)
check("tổng hợp: chênh lệch", th["chenh_lech"] == 321000.5, th)
check("tổng hợp: số giao dịch", th["so_giao_dich"] == 5, th)
tk = {t["account_number"]: t for t in th["theo_tai_khoan"]}
check("tổng hợp: theo tài khoản A1", tk["A1"]["tien_vao"] == 350000.5 and tk["A1"]["so_giao_dich"] == 2, tk)
check("tổng hợp: theo tài khoản B2", tk["B2"]["tien_vao"] == 1000 and tk["B2"]["tien_ra"] == 30000
      and tk["B2"]["chenh_lech"] == -29000 and tk["B2"]["ngan_hang"] == "MB", tk)
check("tổng hợp rỗng = 0", s.tong_hop([])["tong_tien_vao"] == 0 and s.tong_hop(None)["so_giao_dich"] == 0)

gia = GiaHttp().lap()
gia.tra("/transactions/list", {**OK, "transactions": gd})
ra = chay(s.call("sepay_tong_hop", {}, spec()))
p = gia.goi[-1]["params"]
check("tổng hợp tool: mặc định HÔM NAY", p["transaction_date_min"] == hom_nay + " 00:00:00"
      and p["transaction_date_max"] == hom_nay + " 23:59:59", p)
check("tổng hợp tool: đọc tối đa 5000", p["limit"] == 5000)
kq = json.loads(ra)
check("tổng hợp tool: số liệu đúng", kq["tong_tien_vao"] == 351000.5 and kq["tu_ngay"] == hom_nay, kq)
check("tổng hợp tool: chưa chạm trần thì không cảnh báo", "canh_bao" not in kq)
gia.go()
gia = GiaHttp().lap()
gia.tra("/transactions/list", {**OK, "transactions": [{"amount_in": "1"}] * 5000})
kq = json.loads(chay(s.call("sepay_tong_hop", {"account_number": "A1"}, spec())))
check("tổng hợp tool: chạm 5000 thì cảnh báo thiếu", "canh_bao" in kq and kq["account_number"] == "A1", kq)
gia.go()

# ---- 8. dạng lỗi SePay + không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/bankaccounts/list", {"status": 200, "error": None, "messages": {"success": False}})
check("messages.success=false -> ERROR", chay(s.call("sepay_tai_khoan_ngan_hang", {}, spec())).startswith("ERROR"))
gia.go()
gia = GiaHttp().lap()
gia.tra("/bankaccounts/list", {"status": 403, "error": "Forbidden", "messages": {"success": False}})
ra = chay(s.call("sepay_tai_khoan_ngan_hang", {}, spec()))
check("status 403 trong body -> ERROR", ra.startswith("ERROR") and "Forbidden" in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/bankaccounts/list", {"status": 401, "error": f"Invalid token {TOKEN}"}, code=401)
ra = chay(s.call("sepay_tai_khoan_ngan_hang", {}, spec()))
check("HTTP 401 -> ERROR", ra.startswith("ERROR") and "401" in ra, ra)
check("lỗi API vọng lại token -> KHÔNG lộ token", TOKEN not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/transactions/list", {"status": 500, "error": f"bad token {TOKEN}", "messages": {"success": False}})
ra = chay(s.call("sepay_giao_dich", {}, spec()))
check("lỗi trong body vọng lại token -> KHÔNG lộ", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.nem_loi("/transactions/count", ConnectionError("proxy từ chối Bearer " + TOKEN))
ra = chay(s.call("sepay_dem_giao_dich", {}, spec()))
check("lỗi mạng -> ERROR, KHÔNG lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.tra("/bankaccounts/list", "<html>bảo trì</html>")
ra = chay(s.call("sepay_tai_khoan_ngan_hang", {}, spec()))
check("trả HTML -> ERROR", ra.startswith("ERROR"), ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("sepay_chuyen_tien", {}, spec())).startswith("ERROR"))
check.ket_thuc()
