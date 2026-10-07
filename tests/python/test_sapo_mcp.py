"""Cầu nối Sapo (server/sapo_mcp.py). Không mạng.

    python tests/run.py sapo_mcp

Phủ: chống SSRF ở tên cửa hàng, Basic auth từ API Key + Secret, X-Sapo-Access-Token khi có token,
đúng host <tên>.mysapo.net/admin, khoảng ngày created_on_*, giới hạn số lượng, lọc lạ bị bỏ,
gọi thô có rào chắn, lỗi không lộ bí mật, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import os
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-sapo-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import sapo_mcp as s  # noqa: E402

check = KiemTra()
KEY = "sapo-api-key-24680"
SEC = "sapo-api-secret-13579"
TOKEN = "SAPO-ACCESS-TOKEN-99887"


def spec(**them):
    sec = {"shop_id": "halimi", "api_key": KEY, "api_secret": SEC}
    sec.update(them)
    return {"key": "conn-sapo-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


# ---- chống SSRF ----
for tot, mong in (("halimi", "halimi"), ("HALIMI", "halimi"), ("halimi.mysapo.net", "halimi"),
                  ("https://halimi.mysapo.net/admin", "halimi"), ("shop-01", "shop-01")):
    check(f"tên cửa hàng hợp lệ: {tot}", s.ten_cua_hang(tot) == mong, s.ten_cua_hang(tot))
for xau in ("evil.com", "a.mysapo.net.evil.com", "a/b", "@", "a@evil.com", "a.b", "-abc", "abc-", "",
            "a:443", "a b", "evil.com#.mysapo.net", "a\\b", "x" * 64):
    check(f"tên cửa hàng bị chặn: {xau!r}", s.ten_cua_hang(xau) is None)

gia = GiaHttp().lap()
gia.tra("mysapo.net/admin", {"ok": True})
for xau in ("evil.com", "a.mysapo.net.evil.com", "a/b", "@"):
    ra = chay(s.call("sapo_thong_tin_cua_hang", {}, spec(shop_id=xau)))
    check(f"call từ chối shop {xau!r}", ra.startswith("ERROR"), ra)
check("tên cửa hàng xấu thì KHÔNG gửi request nào", not gia.goi, [g["url"] for g in gia.goi])

# ---- auth ----
chay(s.call("sapo_thong_tin_cua_hang", {}, spec()))
g = gia.goi[-1]
check("cửa hàng đúng URL", g["url"] == "https://halimi.mysapo.net/admin/store.json" and g["method"] == "GET", g["url"])
check("Basic auth từ key:secret", g["headers"].get("Authorization")
      == "Basic " + base64.b64encode(f"{KEY}:{SEC}".encode()).decode())
check("không gửi header token khi chưa có token", "X-Sapo-Access-Token" not in g["headers"])
chay(s.call("sapo_thong_tin_cua_hang", {}, {"secrets": {"shop_id": "halimi", "access_token": TOKEN}}))
g = gia.goi[-1]
check("có token -> X-Sapo-Access-Token", g["headers"].get("X-Sapo-Access-Token") == TOKEN
      and "Authorization" not in g["headers"])

# ---- tool ----
chay(s.call("sapo_don_hang", {"tu_ngay": "2026-02-01", "den_ngay": "2026-02-28", "trang_thai": "closed",
                              "thanh_toan": "unpaid", "giao_hang": "partial", "so_luong": 9999, "trang": 2}, spec()))
p = gia.goi[-1]["params"]
check("đơn hàng đúng path", gia.goi[-1]["url"].endswith("/admin/orders.json"))
check("khoảng ngày created_on_*", p["created_on_min"] == "2026-02-01T00:00:00+07:00"
      and p["created_on_max"] == "2026-02-28T23:59:59+07:00", p)
check("lọc hợp lệ được gửi", p["status"] == "closed" and p["financial_status"] == "unpaid"
      and p["fulfillment_status"] == "partial")
check("limit cắt còn 250", p["limit"] == 250 and p["page"] == 2)
chay(s.call("sapo_don_hang", {"trang_thai": "xoa", "giao_hang": "bay"}, spec()))
p = gia.goi[-1]["params"]
check("lọc lạ -> any / bỏ", p["status"] == "any" and "fulfillment_status" not in p)

check("chi tiết đơn đòi số", chay(s.call("sapo_chi_tiet_don", {"order_id": "../store"}, spec())).startswith("ERROR"))
chay(s.call("sapo_chi_tiet_don", {"order_id": "450789469"}, spec()))
check("chi tiết đơn đúng path", gia.goi[-1]["url"].endswith("/admin/orders/450789469.json"))
chay(s.call("sapo_san_pham", {"so_luong": 0}, spec()))
check("sản phẩm limit tối thiểu 1", gia.goi[-1]["params"]["limit"] == 1 and gia.goi[-1]["url"].endswith("/products.json"))
chay(s.call("sapo_khach_hang", {"tu_ngay": "2026-03-01"}, spec()))
check("khách lọc created_on_min", gia.goi[-1]["params"].get("created_on_min") == "2026-03-01T00:00:00+07:00")
chay(s.call("sapo_khach_hang", {"tu_ngay": "hôm qua"}, spec()))
check("ngày sai dạng bị bỏ", "created_on_min" not in gia.goi[-1]["params"])
chay(s.call("sapo_chi_nhanh", {}, spec()))
check("chi nhánh đúng path", gia.goi[-1]["url"].endswith("/admin/locations.json"))
chay(s.call("sapo_ton_kho", {"location_ids": "1,2,x", "inventory_item_ids": "9;rm"}, spec()))
p = gia.goi[-1]["params"]
check("tồn kho đúng path, chỉ id số", gia.goi[-1]["url"].endswith("/admin/inventory_levels.json")
      and p["location_ids"] == "1,2" and "inventory_item_ids" not in p, p)

# ---- gọi thô ----
for xau in ("https://evil.com/a.json", "/a/../b.json", "/orders.json?x=1", "//evil.com/a.json", "/@evil.com/a.json",
            "/orders"):
    check(f"gọi thô chặn {xau}", chay(s.call("sapo_goi_api", {"path": xau}, spec())).startswith("ERROR"))
chay(s.call("sapo_goi_api", {"path": "/admin/orders/count.json", "params": {"status": "any"}}, spec()))
g = gia.goi[-1]
check("gọi thô GET, bỏ tiền tố /admin", g["method"] == "GET" and g["url"] == "https://halimi.mysapo.net/admin/orders/count.json")
check("gọi thô vẫn ở đúng host cửa hàng", all(x["url"].startswith("https://halimi.mysapo.net/admin/")
                                              for x in gia.goi))
gia.go()

# ---- lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/store.json", {"errors": f"bad {KEY} {SEC}"}, code=401)
ra = chay(s.call("sapo_thong_tin_cua_hang", {}, spec()))
check("lỗi 401 -> ERROR", ra.startswith("ERROR") and "401" in ra, ra)
check("lỗi KHÔNG lộ key/secret", KEY not in ra and SEC not in ra, ra)
b64 = base64.b64encode(f"{KEY}:{SEC}".encode()).decode()
gia.nem_loi("/orders.json", ConnectionError(f"đứt {SEC} {TOKEN}"))
ra = chay(s.call("sapo_don_hang", {}, spec(access_token=TOKEN)))
check("lỗi mạng KHÔNG lộ secret/token", ra.startswith("ERROR") and SEC not in ra and TOKEN not in ra, ra)
gia.tra("/products.json", {"errors": {"x": TOKEN}})
ra = chay(s.call("sapo_san_pham", {}, spec(access_token=TOKEN)))
check("errors trong body 200 -> ERROR, không lộ", ra.startswith("ERROR") and TOKEN not in ra, ra)
check("chuỗi Basic không xuất hiện trong lỗi", b64 not in ra)
gia.go()

# ---- thiếu ô ----
ra = chay(s.call("sapo_don_hang", {}, {"secrets": {"shop_id": "halimi"}}))
check("thiếu key/secret và token -> báo", ra.startswith("ERROR") and "api_key" in ra, ra)
ra = chay(s.call("sapo_don_hang", {}, {"secrets": {"api_key": KEY, "api_secret": SEC}}))
check("thiếu tên cửa hàng -> báo", ra.startswith("ERROR") and "shop_id" in ra, ra)
check("tool lạ -> lỗi", chay(s.call("sapo_xoa_don", {}, spec())).startswith("ERROR"))
check("list_tools đủ 8 tool", len(chay(s.list_tools({}))) == 8)
check.ket_thuc()
