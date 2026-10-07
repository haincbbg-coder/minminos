"""Cầu nối Haravan (server/haravan_mcp.py). Không mạng.

    python tests/run.py haravan_mcp

Phủ: header Bearer, đúng host /com, khoảng ngày ISO theo múi giờ người dùng, lọc trạng thái lạ,
giới hạn số lượng, tìm khách đổi sang /customers/search.json, tồn kho chỉ nhận id số, gọi thô
có rào chắn, lỗi API và lỗi mạng không lộ token, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-haravan-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import haravan_mcp as s  # noqa: E402

check = KiemTra()
TOKEN = "HRV-TOKEN-BI-MAT-135790"


def spec(**them):
    sec = {"access_token": TOKEN}
    sec.update(them)
    return {"key": "conn-hrv-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


# ---- thiếu ô ----
check("thiếu token -> báo rõ", "access_token" in chay(s.call("haravan_thong_tin_shop", {}, {"secrets": {}})))

gia = GiaHttp().lap()
gia.tra("apis.haravan.com/com", {"ok": True})

chay(s.call("haravan_thong_tin_shop", {}, spec()))
g = gia.goi[-1]
check("shop đúng URL", g["url"] == "https://apis.haravan.com/com/shop.json" and g["method"] == "GET", g["url"])
check("header Bearer token", g["headers"].get("Authorization") == "Bearer " + TOKEN)

chay(s.call("haravan_don_hang", {"tu_ngay": "2026-01-01", "den_ngay": "2026-01-31", "trang_thai": "cancelled",
                                 "thanh_toan": "paid", "giao_hang": "shipped", "so_luong": 999, "trang": 3}, spec()))
p = gia.goi[-1]["params"]
check("đơn hàng đúng path", gia.goi[-1]["url"].endswith("/com/orders.json"))
check("khoảng ngày ISO +07:00", p["created_at_min"] == "2026-01-01T00:00:00+07:00"
      and p["created_at_max"] == "2026-01-31T23:59:59+07:00", p)
check("lọc trạng thái hợp lệ", p["status"] == "cancelled" and p["financial_status"] == "paid"
      and p["fulfillment_status"] == "shipped")
check("limit cắt còn 50", p["limit"] == 50)
check("trang được gửi", p["page"] == 3)
chay(s.call("haravan_don_hang", {"trang_thai": "xoa", "thanh_toan": "lung_tung"}, spec()))
p = gia.goi[-1]["params"]
check("trạng thái lạ -> any", p["status"] == "any")
check("thanh toán lạ bị bỏ", "financial_status" not in p)

check("chi tiết đơn đòi số", chay(s.call("haravan_chi_tiet_don", {"order_id": "1/../shop"}, spec())).startswith("ERROR"))
chay(s.call("haravan_chi_tiet_don", {"order_id": "123456"}, spec()))
check("chi tiết đơn đúng path", gia.goi[-1]["url"].endswith("/com/orders/123456.json"))

chay(s.call("haravan_san_pham", {"sku": "AO-01", "so_luong": 500}, spec()))
p = gia.goi[-1]["params"]
check("sản phẩm lọc SKU, limit 50", p["sku"] == "AO-01" and p["limit"] == 50 and gia.goi[-1]["url"].endswith("/products.json"))

chay(s.call("haravan_khach_hang", {}, spec()))
check("khách không từ khoá -> /customers.json", gia.goi[-1]["url"].endswith("/com/customers.json"))
chay(s.call("haravan_khach_hang", {"tu_khoa": "0912"}, spec()))
check("khách có từ khoá -> search", gia.goi[-1]["url"].endswith("/customers/search.json")
      and gia.goi[-1]["params"]["query"] == "0912")

chay(s.call("haravan_chi_nhanh", {}, spec()))
check("chi nhánh đúng path", gia.goi[-1]["url"].endswith("/com/locations.json"))
chay(s.call("haravan_ton_kho", {"location_ids": "11, x, 12", "variant_ids": ["7", "a;b"], "so_luong": 9999}, spec()))
p = gia.goi[-1]["params"]
check("tồn kho đúng path", gia.goi[-1]["url"].endswith("/com/inventory_locations.json"))
check("tồn kho chỉ nhận id số", p["location_ids"] == "11,12" and p["variant_ids"] == "7", p)
check("tồn kho limit cắt còn 250", p["limit"] == 250)

# ---- gọi thô ----
for xau in ("https://evil.com/x.json", "/orders/../shop.json", "/orders.json?x=1", "//evil.com/a.json",
            "/orders", "/Orders.json"):
    check(f"gọi thô chặn {xau}", chay(s.call("haravan_goi_api", {"path": xau}, spec())).startswith("ERROR"))
chay(s.call("haravan_goi_api", {"path": "/com/orders/count.json", "params": {"status": "any"}}, spec()))
g = gia.goi[-1]
check("gọi thô là GET, bỏ tiền tố /com", g["method"] == "GET" and g["url"] == "https://apis.haravan.com/com/orders/count.json")
check("gọi thô giữ tham số", g["params"] == {"status": "any"})
gia.go()

# ---- lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/shop.json", {"errors": "Invalid token " + TOKEN}, code=401)
ra = chay(s.call("haravan_thong_tin_shop", {}, spec()))
check("lỗi 401 báo ERROR", ra.startswith("ERROR") and "401" in ra, ra)
check("lỗi KHÔNG lộ token", TOKEN not in ra, ra)
gia.tra("/orders.json", {"errors": {"token": TOKEN}})
ra = chay(s.call("haravan_don_hang", {}, spec()))
check("errors trong body 200 -> ERROR, không lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.nem_loi("/locations.json", ConnectionError("đứt mạng, Authorization: Bearer " + TOKEN))
ra = chay(s.call("haravan_chi_nhanh", {}, spec()))
check("lỗi mạng KHÔNG lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.tra("/products.json", "<html>bảo trì</html>")
check("trả về không phải JSON -> ERROR", chay(s.call("haravan_san_pham", {}, spec())).startswith("ERROR"))
gia.go()

check("tool lạ -> lỗi", chay(s.call("haravan_xoa_don", {}, spec())).startswith("ERROR"))
check("list_tools đủ 8 tool", len(chay(s.list_tools({}))) == 8)
check.ket_thuc()
