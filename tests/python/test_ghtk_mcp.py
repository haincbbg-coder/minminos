"""Cầu nối Giao Hàng Tiết Kiệm (server/ghtk_mcp.py). Không mạng.

    python tests/run.py ghtk_mcp

Phủ: header Token và X-Client-Source, đúng URL/tham số/body từng tool, đổi môi trường test,
kiểm tra đầu vào tạo đơn (sai thì KHÔNG gọi mạng), chặn ký tự lạ trong mã đơn (chống chèn đường
dẫn), success false thành ERROR, lỗi và ngoại lệ mạng không lộ token, thiếu token, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import copy
import httpx

from _gia_http import GiaHttp, KiemTra
import ghtk_mcp as g

check = KiemTra()
TOKEN = "ghtk-token-bi-mat-987654abcdef"
LIVE = "https://services.giaohangtietkiem.vn"
TEST = "https://services-staging.ghtklab.com"


def spec(**them):
    sec = {"token": TOKEN}
    sec.update(them)
    return {"key": "conn-ghtk-1", "secrets": sec}


def chay(tool, args=None, sp=None):
    return asyncio.run(g.call(tool, args or {}, sp or spec()))


# ---- 0. khai báo ----
ten = [t["name"] for t in asyncio.run(g.list_tools({}))]
check("đủ 5 tool", sorted(ten) == sorted(["ghtk_tinh_phi", "ghtk_trang_thai_don", "ghtk_dia_chi_lay_hang",
                                          "ghtk_tao_don", "ghtk_huy_don"]), ten)
check("thiếu token -> báo rõ", "token" in chay("ghtk_dia_chi_lay_hang", {}, {"secrets": {}}))
check("tool lạ -> ERROR", chay("ghtk_xoa").startswith("ERROR"))

# ---- 1. header, môi trường ----
gia = GiaHttp().lap()
gia.tra("/services/shipment/list_pick_add", {"success": True, "data": [{"pick_address_id": "1", "address": "Kho Hà Nội"}]})
ra = chay("ghtk_dia_chi_lay_hang")
r = gia.goi[-1]
check("địa chỉ lấy hàng trả dữ liệu", "Kho Hà Nội" in ra, ra)
check("GET đúng host live", r["method"] == "GET" and r["url"] == LIVE + "/services/shipment/list_pick_add", r["url"])
check("header Token", r["headers"].get("Token") == TOKEN)
check("không có mã đối tác thì không gửi X-Client-Source", "X-Client-Source" not in r["headers"])
chay("ghtk_dia_chi_lay_hang", {}, spec(ma_doi_tac="HALIMI01", moi_truong="test"))
r = gia.goi[-1]
check("moi_truong test đổi host staging", r["url"] == TEST + "/services/shipment/list_pick_add", r["url"])
check("có mã đối tác thì gửi X-Client-Source", r["headers"].get("X-Client-Source") == "HALIMI01")
check("mã đối tác có ký tự lạ -> ERROR",
      chay("ghtk_dia_chi_lay_hang", {}, spec(ma_doi_tac="a\r\nX: y")).startswith("ERROR"))
gia.go()

# ---- 2. tính phí, trạng thái ----
gia = GiaHttp().lap()
gia.tra("giaohangtietkiem.vn", {"success": True, "fee": {"fee": 30000}})
ra = chay("ghtk_tinh_phi", {"pick_province": "Hà Nội", "pick_district": "Cầu Giấy", "province": "TP Hồ Chí Minh",
                            "district": "Quận 1", "weight": 1000, "value": 500000, "transport": "road",
                            "deliver_option": "none", "address": "12 Lê Lợi"})
r = gia.goi[-1]
check("tính phí trả phí", "30000" in ra, ra)
check("tính phí GET đúng URL", r["method"] == "GET" and r["url"] == LIVE + "/services/shipment/fee")
check("tính phí đủ tham số", r["params"] == {"pick_province": "Hà Nội", "pick_district": "Cầu Giấy",
                                             "province": "TP Hồ Chí Minh", "district": "Quận 1", "weight": 1000,
                                             "value": 500000, "transport": "road", "deliver_option": "none",
                                             "address": "12 Lê Lợi"}, r["params"])
n = len(gia.goi)
check("tính phí thiếu district -> ERROR", chay("ghtk_tinh_phi", {"pick_province": "a", "pick_district": "b",
                                                                 "province": "c", "weight": 1}).startswith("ERROR"))
check("tính phí transport lạ -> ERROR", chay("ghtk_tinh_phi", {"pick_province": "a", "pick_district": "b",
                                                               "province": "c", "district": "d", "weight": 1,
                                                               "transport": "boat"}).startswith("ERROR"))
check("tính phí weight 0 -> ERROR", chay("ghtk_tinh_phi", {"pick_province": "a", "pick_district": "b",
                                                           "province": "c", "district": "d", "weight": 0}).startswith("ERROR"))
check("tính phí sai không gọi mạng", len(gia.goi) == n)

chay("ghtk_trang_thai_don", {"ma_don": "S1.A1.17373471"})
check("trạng thái đơn đúng URL", gia.goi[-1]["url"] == LIVE + "/services/shipment/v2/S1.A1.17373471", gia.goi[-1]["url"])
n = len(gia.goi)
for xau in ("../x", "a/b", "a?b=1", "", "x" * 65, "a b"):
    check(f"trạng thái chặn mã {xau[:12]!r}", chay("ghtk_trang_thai_don", {"ma_don": xau}).startswith("ERROR"))
check("trạng thái chặn partner_id: (chỉ hủy mới nhận)",
      chay("ghtk_trang_thai_don", {"ma_don": "partner_id:X1"}).startswith("ERROR"))
check("mã sai không gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 3. tạo đơn ----
DON = {"products": [{"name": "Váy lụa", "weight": 0.4, "quantity": 1}, {"name": "Áo", "weight": 0.2, "quantity": 2}],
       "order": {"id": "HALIMI-003", "pick_name": "HALIMI", "pick_address": "1 Trần Duy Hưng",
                 "pick_province": "Hà Nội", "pick_district": "Cầu Giấy", "pick_tel": "0911222333",
                 "name": "Nguyễn Thị B", "address": "12 Lê Lợi", "province": "TP Hồ Chí Minh",
                 "district": "Quận 1", "ward": "Bến Nghé", "tel": "0987.654.321", "pick_money": 450000,
                 "value": 450000, "is_freeship": 1, "note": "Gọi trước"}}
gia = GiaHttp().lap()
gia.tra("/services/shipment/order", {"success": True, "order": {"label": "S1.A1.999", "fee": 30000}})
ra = chay("ghtk_tao_don", DON)
r = gia.goi[-1]
check("tạo đơn trả label", "S1.A1.999" in ra, ra)
check("tạo đơn POST đúng URL", r["method"] == "POST" and r["url"] == LIVE + "/services/shipment/order")
b = r["json"]
check("tạo đơn products đúng", b["products"] == DON["products"], b["products"])
check("tạo đơn hamlet mặc định Khác", b["order"]["hamlet"] == "Khác")
check("tạo đơn chuẩn hoá sđt", b["order"]["tel"] == "0987654321")
check("tạo đơn giữ COD, freeship, ward", b["order"]["pick_money"] == 450000 and b["order"]["is_freeship"] == 1
      and b["order"]["ward"] == "Bến Nghé")
n = len(gia.goi)


def doi(**o):
    d = copy.deepcopy(DON)
    d["order"].update(o)
    return d


sai = [
    ("sđt người nhận sai", doi(tel="12345")),
    ("sđt lấy hàng sai", doi(pick_tel="abc")),
    ("COD quá 50 triệu", doi(pick_money=50_000_001)),
    ("COD âm", doi(pick_money=-5)),
    ("is_freeship 2", doi(is_freeship=2)),
    ("thiếu tên người nhận", doi(name="")),
    ("thiếu tỉnh", doi(province=None)),
    ("mã đơn có /", doi(id="a/b")),
    ("thiếu products", {"order": DON["order"]}),
    ("products rỗng", {**DON, "products": []}),
    ("sản phẩm nặng 0", {**DON, "products": [{"name": "x", "weight": 0, "quantity": 1}]}),
    ("sản phẩm quá 50kg", {**DON, "products": [{"name": "x", "weight": 51, "quantity": 1}]}),
    ("sản phẩm thiếu quantity", {**DON, "products": [{"name": "x", "weight": 1}]}),
    ("thiếu order", {"products": DON["products"]}),
]
for ten_ca, d in sai:
    check("tạo đơn từ chối: " + ten_ca, chay("ghtk_tao_don", d).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n, len(gia.goi) - n)
gia.go()

# ---- 4. hủy đơn ----
gia = GiaHttp().lap()
gia.tra("/services/shipment/cancel/", {"success": True, "message": "Hủy đơn hàng thành công"})
chay("ghtk_huy_don", {"ma_don": "S1.A1.17373471"})
r = gia.goi[-1]
check("hủy đơn POST đúng URL", r["method"] == "POST" and r["url"] == LIVE + "/services/shipment/cancel/S1.A1.17373471")
chay("ghtk_huy_don", {"ma_don": "partner_id:HALIMI-003"})
check("hủy theo partner_id", gia.goi[-1]["url"].endswith("/services/shipment/cancel/partner_id:HALIMI-003"))
n = len(gia.goi)
for xau in ("../x", "a/b", "partner_id:../x", "partner_id:", "x#y", ""):
    check(f"hủy chặn mã {xau!r}", chay("ghtk_huy_don", {"ma_don": xau}).startswith("ERROR"))
check("hủy sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 5. lỗi API, không lộ token ----
gia = GiaHttp().lap()
gia.tra("/services/shipment/v2/", {"success": False, "message": "Token " + TOKEN + " không hợp lệ"})
ra = chay("ghtk_trang_thai_don", {"ma_don": "X1"})
check("success false -> ERROR", ra.startswith("ERROR") and "không hợp lệ" in ra, ra)
check("lỗi API không lộ token", TOKEN not in ra, ra)
gia.tra("/services/shipment/list_pick_add", {"message": "Unauthorized " + TOKEN}, code=401)
ra = chay("ghtk_dia_chi_lay_hang")
check("HTTP 401 -> ERROR không lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.nem_loi("/services/shipment/fee", httpx.ConnectError("hỏng Token=" + TOKEN))
ra = chay("ghtk_tinh_phi", {"pick_province": "a", "pick_district": "b", "province": "c", "district": "d", "weight": 1})
check("ngoại lệ mạng -> ERROR không lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.tra("/services/shipment/cancel/", {"message": "thiếu success"})
check("thiếu trường success -> ERROR", chay("ghtk_huy_don", {"ma_don": "A1"}).startswith("ERROR"))
gia.go()

# ---- 6. không có gạch dài ----
src = open(SERVER / "ghtk_mcp.py", encoding="utf-8").read()
check("không có em/en dash", "\u2014" not in src and "\u2013" not in src)

check.ket_thuc()
