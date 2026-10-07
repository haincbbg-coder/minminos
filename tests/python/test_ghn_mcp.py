"""Cầu nối Giao Hàng Nhanh (server/ghn_mcp.py). Không mạng.

    python tests/run.py ghn_mcp

Phủ: header Token + ShopId (mặc định của kết nối và ghi đè từng lượt), đúng URL và body từng tool,
đổi môi trường test, kiểm tra đầu vào tạo đơn (sai thì KHÔNG gọi mạng), giới hạn hủy 20 mã và chặn
ký tự lạ, lỗi code != 200, lỗi và ngoại lệ mạng không lộ token, thiếu token, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import httpx

from _gia_http import GiaHttp, KiemTra
import ghn_mcp as g

check = KiemTra()
TOKEN = "ghn-token-bi-mat-abcdef123456"
LIVE = "https://online-gateway.ghn.vn/shiip/public-api"
DEV = "https://dev-online-gateway.ghn.vn/shiip/public-api"


def spec(**them):
    sec = {"token": TOKEN, "shop_id": "885"}
    sec.update(them)
    return {"key": "conn-ghn-1", "secrets": sec}


def chay(tool, args=None, sp=None):
    return asyncio.run(g.call(tool, args or {}, sp or spec()))


OK = {"code": 200, "message": "Success", "data": {"ok": 1}}

# ---- 0. khai báo ----
ten = [t["name"] for t in asyncio.run(g.list_tools({}))]
check("đủ 10 tool", len(ten) == 10 and "ghn_tao_don" in ten and "ghn_huy_don" in ten, ten)
check("thiếu token -> báo rõ", "token" in chay("ghn_tinh_thanh", {}, {"secrets": {}}))
check("tool lạ -> ERROR", chay("ghn_xoa_het").startswith("ERROR"))

# ---- 1. header, URL, môi trường ----
gia = GiaHttp().lap()
gia.tra("/master-data/province", {"code": 200, "message": "Success", "data": [{"ProvinceID": 201, "ProvinceName": "Hà Nội"}]})
ra = chay("ghn_tinh_thanh")
r = gia.goi[-1]
check("tỉnh thành trả dữ liệu", "Hà Nội" in ra, ra)
check("tỉnh thành GET đúng host live", r["method"] == "GET" and r["url"] == LIVE + "/master-data/province", r["url"])
check("header Token", r["headers"].get("Token") == TOKEN)
check("header Content-Type JSON", r["headers"].get("Content-Type") == "application/json")
chay("ghn_tinh_thanh", {}, spec(moi_truong="test"))
check("moi_truong test đổi host dev", gia.goi[-1]["url"] == DEV + "/master-data/province", gia.goi[-1]["url"])
gia.go()

gia = GiaHttp().lap()
gia.tra("ghn.vn", OK)
chay("ghn_danh_sach_shop", {"offset": 5, "limit": 999})
r = gia.goi[-1]
check("danh sách shop GET /v2/shop/all", r["method"] == "GET" and r["url"].endswith("/v2/shop/all"))
check("limit bị chặn 200, offset giữ", r["params"] == {"offset": 5, "limit": 200}, r["params"])

chay("ghn_quan_huyen", {"province_id": 201})
r = gia.goi[-1]
check("quận huyện POST body province_id", r["method"] == "POST" and r["url"].endswith("/master-data/district")
      and r["json"] == {"province_id": 201}, r["json"])
check("quận huyện thiếu province_id -> ERROR", chay("ghn_quan_huyen", {}).startswith("ERROR"))
chay("ghn_phuong_xa", {"district_id": "1442"})
r = gia.goi[-1]
check("phường xã POST body district_id số", r["url"].endswith("/master-data/ward") and r["json"] == {"district_id": 1442})

chay("ghn_dich_vu", {"from_district": 1447, "to_district": 1442})
r = gia.goi[-1]
check("dịch vụ đúng URL", r["url"].endswith("/v2/shipping-order/available-services"))
check("dịch vụ body shop_id mặc định", r["json"] == {"shop_id": 885, "from_district": 1447, "to_district": 1442}, r["json"])
check("dịch vụ header ShopId mặc định", r["headers"].get("ShopId") == "885")
chay("ghn_dich_vu", {"from_district": 1447, "to_district": 1442, "shop_id": "99001"})
r = gia.goi[-1]
check("shop_id từng lượt ghi đè header", r["headers"].get("ShopId") == "99001")
check("shop_id từng lượt ghi đè body", r["json"]["shop_id"] == 99001)
check("shop_id không phải số -> ERROR", chay("ghn_dich_vu", {"from_district": 1, "to_district": 2,
                                                              "shop_id": "1;drop"}).startswith("ERROR"))
check("không có shop nào -> ERROR",
      chay("ghn_dich_vu", {"from_district": 1, "to_district": 2}, {"secrets": {"token": TOKEN}}).startswith("ERROR"))

chay("ghn_tinh_phi", {"service_type_id": 2, "to_district_id": 1442, "to_ward_code": "20109", "weight": 500,
                      "length": 20, "insurance_value": 300000, "from_district_id": 1447})
r = gia.goi[-1]
check("tính phí đúng URL", r["url"].endswith("/v2/shipping-order/fee"))
check("tính phí body đúng", r["json"] == {"service_type_id": 2, "to_district_id": 1442, "to_ward_code": "20109",
                                          "weight": 500, "length": 20, "insurance_value": 300000,
                                          "from_district_id": 1447}, r["json"])
check("tính phí có ShopId", r["headers"].get("ShopId") == "885")
check("tính phí thiếu service -> ERROR",
      chay("ghn_tinh_phi", {"to_district_id": 1, "to_ward_code": "1", "weight": 1}).startswith("ERROR"))
check("tính phí service_id thay service_type_id được",
      not chay("ghn_tinh_phi", {"service_id": 53320, "to_district_id": 1, "to_ward_code": "1", "weight": 1}).startswith("ERROR"))

chay("ghn_chi_tiet_don", {"order_code": "LKXK3F"})
r = gia.goi[-1]
check("chi tiết đơn", r["url"].endswith("/v2/shipping-order/detail") and r["json"] == {"order_code": "LKXK3F"})
chay("ghn_chi_tiet_don_theo_ma_khach", {"client_order_code": "HALIMI-001"})
r = gia.goi[-1]
check("chi tiết theo mã khách", r["url"].endswith("/v2/shipping-order/detail-by-client-code")
      and r["json"] == {"client_order_code": "HALIMI-001"})
check("mã đơn có / -> ERROR", chay("ghn_chi_tiet_don", {"order_code": "a/b"}).startswith("ERROR"))
gia.go()

# ---- 2. tạo đơn ----
DON = {"to_name": "Nguyễn Thị A", "to_phone": "0987 654 321", "to_address": "12 Lê Lợi, Q1",
       "to_ward_code": "20109", "to_district_id": 1442, "weight": 800, "cod_amount": 450000,
       "items": [{"name": "Váy lụa", "quantity": 1, "weight": 400}, {"name": "Áo", "quantity": 2}],
       "client_order_code": "HALIMI-002", "content": "Váy"}
gia = GiaHttp().lap()
gia.tra("/v2/shipping-order/create", {"code": 200, "message": "Success",
                                      "data": {"order_code": "GHN123", "total_fee": 33000}})
ra = chay("ghn_tao_don", DON)
r = gia.goi[-1]
check("tạo đơn trả mã vận đơn", "GHN123" in ra, ra)
check("tạo đơn POST đúng URL", r["method"] == "POST" and r["url"] == LIVE + "/v2/shipping-order/create")
b = r["json"]
check("tạo đơn mặc định service_type 2, người nhận trả, không cho xem",
      b["service_type_id"] == 2 and b["payment_type_id"] == 2 and b["required_note"] == "KHONGCHOXEMHANG", b)
check("tạo đơn chuẩn hoá số điện thoại", b["to_phone"] == "0987654321")
check("tạo đơn giữ items, cod, mã khách", b["items"][0] == {"name": "Váy lụa", "quantity": 1, "weight": 400}
      and b["cod_amount"] == 450000 and b["client_order_code"] == "HALIMI-002")
check("tạo đơn header ShopId", r["headers"].get("ShopId") == "885")
n = len(gia.goi)
sai = [
    ("số điện thoại sai", {**DON, "to_phone": "12345"}),
    ("số điện thoại có chữ", {**DON, "to_phone": "09876543ab"}),
    ("khối lượng 0", {**DON, "weight": 0}),
    ("khối lượng quá 50kg", {**DON, "weight": 50001}),
    ("required_note lạ", {**DON, "required_note": "CHO_MO"}),
    ("thiếu items", {kk: v for kk, v in DON.items() if kk != "items"}),
    ("items rỗng", {**DON, "items": []}),
    ("item thiếu quantity", {**DON, "items": [{"name": "x"}]}),
    ("COD quá 50 triệu", {**DON, "cod_amount": 50_000_001}),
    ("COD âm", {**DON, "cod_amount": -1}),
    ("payment_type 3", {**DON, "payment_type_id": 3}),
    ("thiếu tên", {**DON, "to_name": ""}),
    ("ward_code có ký tự lạ", {**DON, "to_ward_code": "../1"}),
    ("client_order_code có /", {**DON, "client_order_code": "a/b"}),
]
for ten_ca, d in sai:
    check("tạo đơn từ chối: " + ten_ca, chay("ghn_tao_don", d).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n, len(gia.goi) - n)
gia.go()

# ---- 3. hủy đơn ----
gia = GiaHttp().lap()
gia.tra("/v2/switch-status/cancel", {"code": 200, "message": "Success", "data": [{"order_code": "A1", "result": True}]})
chay("ghn_huy_don", {"order_codes": ["A1", "B2"], "shop_id": "777"})
r = gia.goi[-1]
check("hủy đơn đúng URL + body", r["url"].endswith("/v2/switch-status/cancel") and r["json"] == {"order_codes": ["A1", "B2"]})
check("hủy đơn ShopId ghi đè", r["headers"].get("ShopId") == "777")
chay("ghn_huy_don", {"order_codes": "C3, D4"})
check("hủy đơn nhận chuỗi a,b", gia.goi[-1]["json"] == {"order_codes": ["C3", "D4"]})
n = len(gia.goi)
check("hủy quá 20 mã -> ERROR", chay("ghn_huy_don", {"order_codes": [f"M{i}" for i in range(21)]}).startswith("ERROR"))
check("hủy mã ../x -> ERROR", chay("ghn_huy_don", {"order_codes": ["../x"]}).startswith("ERROR"))
check("hủy mã a/b -> ERROR", chay("ghn_huy_don", {"order_codes": ["a/b"]}).startswith("ERROR"))
check("hủy không có mã -> ERROR", chay("ghn_huy_don", {"order_codes": []}).startswith("ERROR"))
check("hủy sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 4. lỗi API, không lộ token ----
gia = GiaHttp().lap()
gia.tra("/v2/shipping-order/detail", {"code": 400, "message": "Token " + TOKEN + " không hợp lệ", "data": None})
ra = chay("ghn_chi_tiet_don", {"order_code": "X1"})
check("code != 200 -> ERROR", ra.startswith("ERROR") and "400" in ra, ra)
check("lỗi API không lộ token", TOKEN not in ra, ra)
gia.tra("/master-data/province", {"loi": "Unauthorized " + TOKEN}, code=401)
ra = chay("ghn_tinh_thanh")
check("HTTP 401 -> ERROR không lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.nem_loi("/master-data/ward", httpx.ConnectError("không nối được với Token=" + TOKEN))
ra = chay("ghn_phuong_xa", {"district_id": 1})
check("ngoại lệ mạng -> ERROR không lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.tra("/master-data/district", "<html>bad gateway</html>")
check("trả về không phải JSON -> ERROR", chay("ghn_quan_huyen", {"province_id": 1}).startswith("ERROR"))
gia.go()

# ---- 5. không có gạch dài ----
src = open(SERVER / "ghn_mcp.py", encoding="utf-8").read()
check("không có em/en dash", "\u2014" not in src and "\u2013" not in src)

check.ket_thuc()
