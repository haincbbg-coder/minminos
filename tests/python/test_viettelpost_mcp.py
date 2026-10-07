"""Cầu nối Viettel Post (server/viettelpost_mcp.py). Không mạng.

    python tests/run.py viettelpost_mcp

Phủ: đăng nhập Login rồi ownerconnect (header Token tạm), token dài hạn được LƯU kèm hạn và lần
sau dùng lại không đăng nhập; hết hạn hoặc đổi tài khoản thì đăng nhập lại; 401 thì đăng nhập lại
đúng một lần; ownerconnect hỏng vẫn dùng token Login; đúng URL/params/body từng tool; kiểm tra đầu
vào tạo đơn (sai thì KHÔNG gọi mạng), chặn ký tự lạ trong mã đơn; lỗi {error: true} và HTTP;
không lộ mật khẩu/token; thiếu ô; tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-vtp-"))

import httpx  # noqa: E402

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import viettelpost_mcp as v  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

USER = "0987000111"
PASS = "mat-khau-vtp-bi-mat-778899"
TOK_TAM = "TOKEN-TAM-vtp-aaaa1111"
TOK_DAI = "TOKEN-DAI-HAN-vtp-bbbb2222"
LIVE = "https://partner.viettelpost.vn"
DEV = "https://partnerdev.viettelpost.vn"


def spec(**them):
    sec = {"username": USER, "password": PASS}
    sec.update(them)
    return {"key": "conn-vtp-1", "secrets": sec}


def chay(tool, args=None, sp=None):
    return asyncio.run(v.call(tool, args or {}, sp if sp is not None else spec()))


def boc(data):
    return {"status": 200, "error": False, "message": "OK", "data": data}


def gia_dang_nhap(gia, het=None):
    het = het if het is not None else int((time.time() + 30 * 86400) * 1000)
    gia.tra("/v2/user/Login", boc({"userId": 1, "token": TOK_TAM, "expired": het}))
    gia.tra("/v2/user/ownerconnect", boc({"userId": 1, "token": TOK_DAI, "expired": het}))


# ---- 0. khai báo ----
ten = [t["name"] for t in asyncio.run(v.list_tools({}))]
check("đủ 8 tool", len(ten) == 8 and "vtp_tao_don" in ten and "vtp_huy_don" in ten, ten)
ra = chay("vtp_tinh_thanh", {}, {"secrets": {"username": USER}})
check("thiếu password -> báo rõ", ra.startswith("ERROR") and "password" in ra, ra)
check("tool lạ -> ERROR", chay("vtp_xoa_het").startswith("ERROR"))

# ---- 1. đăng nhập, lưu token, dùng lại ----
gia = GiaHttp().lap()
gia_dang_nhap(gia)
gia.tra("/v2/categories/listProvince", boc([{"PROVINCE_ID": 1, "PROVINCE_NAME": "Hà Nội"}]))
sp = spec()
ra = chay("vtp_tinh_thanh", {}, sp)
check("tỉnh thành trả dữ liệu", "Hà Nội" in ra, ra)
check("đi đúng 3 bước: Login, ownerconnect, listProvince", [g["url"] for g in gia.goi] == [
    LIVE + "/v2/user/Login", LIVE + "/v2/user/ownerconnect", LIVE + "/v2/categories/listProvince"],
    [g["url"] for g in gia.goi])
g0, g1, g2 = gia.goi
check("Login POST body USERNAME/PASSWORD", g0["method"] == "POST" and g0["json"] == {"USERNAME": USER, "PASSWORD": PASS})
check("Login không mang header Token", "Token" not in g0["headers"])
check("ownerconnect mang Token tạm, cùng body", g1["headers"].get("Token") == TOK_TAM
      and g1["json"] == {"USERNAME": USER, "PASSWORD": PASS})
check("API sau dùng token dài hạn", g2["headers"].get("Token") == TOK_DAI and g2["method"] == "GET")
check("token dài hạn được lưu vào kết nối", any(c == "conn-vtp-1" and p["fields"].get("access_token") == TOK_DAI
                                               for c, p in da_luu), da_luu)
check("mốc hết hạn mili giây đổi sang giây", 0 < int(sp["secrets"]["token_het_han"]) - time.time() < 31 * 86400,
      sp["secrets"].get("token_het_han"))
n = len(gia.goi)
chay("vtp_tinh_thanh", {}, sp)
check("lần hai dùng token đã lưu, không đăng nhập lại", len(gia.goi) == n + 1
      and gia.goi[-1]["url"].endswith("/listProvince"), [g["url"] for g in gia.goi[n:]])

# hết hạn -> đăng nhập lại
sp["secrets"]["token_het_han"] = str(int(time.time()) - 10)
n = len(gia.goi)
chay("vtp_tinh_thanh", {}, sp)
check("token hết hạn thì đăng nhập lại", [g["url"].rsplit("/", 1)[-1] for g in gia.goi[n:]]
      == ["Login", "ownerconnect", "listProvince"], [g["url"] for g in gia.goi[n:]])

# đổi mật khẩu trong kết nối -> token cũ bỏ
sp["secrets"]["password"] = PASS + "-moi"
n = len(gia.goi)
chay("vtp_tinh_thanh", {}, sp)
check("đổi mật khẩu thì đăng nhập lại", gia.goi[n]["url"].endswith("/v2/user/Login")
      and gia.goi[n]["json"]["PASSWORD"] == PASS + "-moi")
gia.go()

# 401 -> đăng nhập lại đúng một lần
gia = GiaHttp().lap()
gia_dang_nhap(gia)
gia.tra("/v2/user/listInventory", {"status": 401, "error": True, "message": "Token invalid"}, code=401)
gia.tra("/v2/user/listInventory", boc([{"groupaddressId": 5818802, "cusId": 1456467, "name": "Kho HALIMI"}]))
sp = spec(access_token="TOKEN-CU-da-chet-123456", token_het_han=str(int(time.time()) + 86400),
          token_tk=v._dau_tk(spec()["secrets"]))
ra = chay("vtp_kho_hang", {}, sp)
urls = [g["url"].rsplit("/", 1)[-1] for g in gia.goi]
check("401 -> đăng nhập lại một lần rồi gọi lại thành công", urls == ["listInventory", "Login", "ownerconnect",
                                                                       "listInventory"] and "Kho HALIMI" in ra,
      (urls, ra))
check("lượt đầu dùng token cũ, lượt sau token mới", gia.goi[0]["headers"]["Token"] == "TOKEN-CU-da-chet-123456"
      and gia.goi[-1]["headers"]["Token"] == TOK_DAI)
gia.go()

gia = GiaHttp().lap()
gia_dang_nhap(gia)
gia.tra("/v2/user/listInventory", {"status": 401, "error": True, "message": "Token invalid"}, code=401)
ra = chay("vtp_kho_hang", {}, spec())
dem = sum(1 for g in gia.goi if g["url"].endswith("/v2/user/Login"))
check("401 mãi -> ERROR, chỉ đăng nhập lại một lần (tổng 2 lần Login)", ra.startswith("ERROR") and dem == 2, (dem, ra))
gia.go()

gia = GiaHttp().lap()
gia_dang_nhap(gia)
gia.tra("/v2/user/listInventory", {"status": 401, "error": True, "message": "het han"})
gia.tra("/v2/user/listInventory", boc([{"name": "Kho 2"}]))
ra = chay("vtp_kho_hang", {}, spec(access_token="TOKEN-CU-2-zzzz", token_het_han=str(int(time.time()) + 9999),
                                   token_tk=v._dau_tk(spec()["secrets"])))
check("status 401 trong body -> đăng nhập lại rồi thành công", "Kho 2" in ra, ra)
gia.go()

# ownerconnect hỏng -> vẫn dùng token Login
gia = GiaHttp().lap()
gia.tra("/v2/user/Login", boc({"token": TOK_TAM, "expired": 0}))
gia.tra("/v2/user/ownerconnect", {"status": 205, "error": True, "message": "khong co quyen"})
gia.tra("/v2/categories/listProvince", boc([]))
sp = spec()
chay("vtp_tinh_thanh", {}, sp)
check("ownerconnect hỏng thì dùng token Login", gia.goi[-1]["headers"].get("Token") == TOK_TAM)
check("không có mốc hạn -> đặt hạn mặc định trong tương lai", int(sp["secrets"]["token_het_han"]) > time.time() + 3600)
gia.go()

# đăng nhập sai
gia = GiaHttp().lap()
gia.tra("/v2/user/Login", {"status": 200, "error": True, "message": "Sai mật khẩu " + PASS})
ra = chay("vtp_tinh_thanh")
check("đăng nhập sai -> ERROR không lộ mật khẩu", ra.startswith("ERROR") and PASS not in ra, ra)
check("đăng nhập sai không gọi tiếp", len(gia.goi) == 1)
gia.go()

# môi trường test
gia = GiaHttp().lap()
gia_dang_nhap(gia)
gia.tra("/v2/categories/listProvince", boc([]))
chay("vtp_tinh_thanh", {}, spec(moi_truong="test"))
check("moi_truong test đổi host partnerdev", all(g["url"].startswith(DEV) for g in gia.goi), [g["url"] for g in gia.goi])
gia.go()

# ---- 2. URL, params, body từng tool đọc ----
DAU = {"access_token": TOK_DAI, "token_het_han": str(int(time.time()) + 86400)}


def sp_san():
    s = spec(**DAU)
    s["secrets"]["token_tk"] = v._dau_tk(s["secrets"])
    return s


gia = GiaHttp().lap()
gia.tra("viettelpost.vn", boc({"ok": 1}))
chay("vtp_quan_huyen", {"province_id": "1"}, sp_san())
r = gia.goi[-1]
check("quận huyện GET listDistrict?provinceId", r["method"] == "GET" and r["url"] == LIVE + "/v2/categories/listDistrict"
      and r["params"] == {"provinceId": 1}, (r["url"], r["params"]))
chay("vtp_phuong_xa", {"district_id": 12}, sp_san())
r = gia.goi[-1]
check("phường xã GET listWards?districtId", r["url"].endswith("/v2/categories/listWards") and r["params"] == {"districtId": 12})
check("quận huyện thiếu province_id -> ERROR", chay("vtp_quan_huyen", {}, sp_san()).startswith("ERROR"))
check("phường xã district_id rác -> ERROR", chay("vtp_phuong_xa", {"district_id": "1;x"}, sp_san()).startswith("ERROR"))
chay("vtp_kho_hang", {}, sp_san())
check("kho hàng GET /v2/user/listInventory", gia.goi[-1]["url"] == LIVE + "/v2/user/listInventory"
      and gia.goi[-1]["method"] == "GET")

GIA = {"sender_province": 1, "sender_district": 12, "receiver_province": 34, "receiver_district": 390,
       "product_weight": 500, "product_price": 300000, "money_collection": 450000}
chay("vtp_dich_vu_va_gia", GIA, sp_san())
r = gia.goi[-1]
check("dịch vụ và giá POST getPriceAll", r["method"] == "POST" and r["url"] == LIVE + "/v2/order/getPriceAll")
check("getPriceAll body đúng", r["json"] == {"SENDER_PROVINCE": 1, "SENDER_DISTRICT": 12, "RECEIVER_PROVINCE": 34,
                                             "RECEIVER_DISTRICT": 390, "PRODUCT_TYPE": "HH", "PRODUCT_WEIGHT": 500,
                                             "PRODUCT_PRICE": 300000, "MONEY_COLLECTION": 450000, "TYPE": 1}, r["json"])
chay("vtp_tinh_phi", {**GIA, "order_service": "vcn", "order_service_add": "GBH"}, sp_san())
r = gia.goi[-1]
check("tính phí POST getPrice", r["url"] == LIVE + "/v2/order/getPrice")
check("getPrice body có dịch vụ in hoa và NATIONAL_TYPE", r["json"]["ORDER_SERVICE"] == "VCN"
      and r["json"]["ORDER_SERVICE_ADD"] == "GBH" and r["json"]["NATIONAL_TYPE"] == 1, r["json"])
n = len(gia.goi)
for ten_ca, args in [("thiếu quận nhận", {kk: vv for kk, vv in GIA.items() if kk != "receiver_district"}),
                     ("khối lượng 0", {**GIA, "product_weight": 0}),
                     ("COD quá 50 triệu", {**GIA, "money_collection": 50_000_001}),
                     ("product_type lạ", {**GIA, "product_type": "XX"})]:
    check("dịch vụ và giá từ chối: " + ten_ca, chay("vtp_dich_vu_va_gia", args, sp_san()).startswith("ERROR"))
check("tính phí thiếu order_service -> ERROR", chay("vtp_tinh_phi", GIA, sp_san()).startswith("ERROR"))
check("tính phí order_service có / -> ERROR",
      chay("vtp_tinh_phi", {**GIA, "order_service": "../VCN"}, sp_san()).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.tra("/v2/order/getPriceAll", [{"MA_DV_CHINH": "VCN", "GIA_CUOC": 30000}])
ra = chay("vtp_dich_vu_va_gia", GIA, sp_san())
check("getPriceAll trả thẳng danh sách vẫn nhận", "VCN" in ra and not ra.startswith("ERROR"), ra)
gia.go()

# ---- 3. tạo đơn ----
DON = {"order_number": "HALIMI-001", "groupaddress_id": 5818802, "cus_id": 1456467,
       "receiver_fullname": "Nguyễn Thị A", "receiver_phone": "0987 654 321", "receiver_address": "12 Lê Lợi",
       "receiver_province": 34, "receiver_district": 390, "receiver_ward": 7393,
       "product_name": "Váy lụa", "product_weight": 800, "product_price": 500000, "money_collection": 450000,
       "order_payment": 3, "order_service": "VCN"}
gia = GiaHttp().lap()
gia.tra("/v2/order/createOrder", boc({"ORDER_NUMBER": "1587818001", "MONEY_TOTAL": 16500}))
ra = chay("vtp_tao_don", DON, sp_san())
r = gia.goi[-1]
check("tạo đơn trả mã vận đơn", "1587818001" in ra, ra)
check("tạo đơn POST createOrder", r["method"] == "POST" and r["url"] == LIVE + "/v2/order/createOrder")
b = r["json"]
check("tạo đơn body kho + người nhận", b["GROUPADDRESS_ID"] == 5818802 and b["CUS_ID"] == 1456467
      and b["RECEIVER_PHONE"] == "0987654321" and b["RECEIVER_WARD"] == 7393, b)
check("tạo đơn mặc định PRODUCT_TYPE HH, số lượng 1", b["PRODUCT_TYPE"] == "HH" and b["PRODUCT_QUANTITY"] == 1)
check("tạo đơn tự dựng LIST_ITEM từ sản phẩm", b["LIST_ITEM"] == [{"PRODUCT_NAME": "Váy lụa", "PRODUCT_QUANTITY": 1,
                                                                    "PRODUCT_PRICE": 500000, "PRODUCT_WEIGHT": 800}])
check("tạo đơn có DELIVERY_DATE dd/mm/yyyy", len(b.get("DELIVERY_DATE", "")) == 19 and b["DELIVERY_DATE"][2] == "/")
check("tạo đơn header Token", r["headers"].get("Token") == TOK_DAI)
NGUOI_GUI = {"sender_fullname": "HALIMI", "sender_phone": "0912345678", "sender_address": "1 Kim Mã",
             "sender_province": 1, "sender_district": 12, "sender_ward": 123}
don2 = {kk: vv for kk, vv in DON.items() if kk not in ("groupaddress_id", "cus_id")}
chay("vtp_tao_don", {**don2, **NGUOI_GUI, "list_item": [{"name": "Áo", "quantity": 2, "price": 100000, "weight": 300}]},
     sp_san())
b = gia.goi[-1]["json"]
check("tạo đơn bằng thông tin người gửi", b["SENDER_FULLNAME"] == "HALIMI" and b["SENDER_WARD"] == 123
      and "GROUPADDRESS_ID" not in b, b)
check("tạo đơn giữ list_item", b["LIST_ITEM"] == [{"PRODUCT_NAME": "Áo", "PRODUCT_QUANTITY": 2, "PRODUCT_PRICE": 100000,
                                                    "PRODUCT_WEIGHT": 300}])
n = len(gia.goi)
sai = [
    ("không có người gửi", don2),
    ("thiếu cus_id đi kèm kho", {**don2, "groupaddress_id": 5818802}),
    ("số điện thoại sai", {**DON, "receiver_phone": "12345"}),
    ("khối lượng 0", {**DON, "product_weight": 0}),
    ("COD quá 50 triệu", {**DON, "money_collection": 50_000_001}),
    ("COD âm", {**DON, "money_collection": -1}),
    ("order_payment 4", {**DON, "order_payment": 4}),
    ("thiếu order_service", {**DON, "order_service": ""}),
    ("mã đơn có /", {**DON, "order_number": "a/b"}),
    ("mã đơn ../", {**DON, "order_number": "../x"}),
    ("thiếu phường nhận", {**DON, "receiver_ward": None}),
    ("thiếu tên hàng", {**DON, "product_name": ""}),
    ("list_item thiếu quantity", {**DON, "list_item": [{"name": "x"}]}),
    ("sender_phone sai", {**DON, "sender_phone": "abc"}),
]
for ten_ca, d in sai:
    check("tạo đơn từ chối: " + ten_ca, chay("vtp_tao_don", d, sp_san()).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n, len(gia.goi) - n)
gia.go()

# ---- 4. hủy đơn ----
gia = GiaHttp().lap()
gia.tra("/v2/order/UpdateOrder", boc(None))
chay("vtp_huy_don", {"order_number": "1587818001", "ghi_chu": "Khách đổi ý"}, sp_san())
r = gia.goi[-1]
check("hủy đơn POST UpdateOrder TYPE 4", r["url"] == LIVE + "/v2/order/UpdateOrder"
      and r["json"] == {"TYPE": 4, "ORDER_NUMBER": "1587818001", "NOTE": "Khách đổi ý"}, r["json"])
chay("vtp_huy_don", {"order_number": "1587818002"}, sp_san())
check("hủy đơn có NOTE mặc định", gia.goi[-1]["json"]["NOTE"] == "Hủy đơn")
n = len(gia.goi)
check("hủy mã ../x -> ERROR", chay("vtp_huy_don", {"order_number": "../x"}, sp_san()).startswith("ERROR"))
check("hủy mã a/b -> ERROR", chay("vtp_huy_don", {"order_number": "a/b"}, sp_san()).startswith("ERROR"))
check("hủy mã có ? -> ERROR", chay("vtp_huy_don", {"order_number": "a?b=1"}, sp_san()).startswith("ERROR"))
check("hủy thiếu mã -> ERROR", chay("vtp_huy_don", {}, sp_san()).startswith("ERROR"))
check("hủy sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 5. lỗi API, không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/v2/order/UpdateOrder", {"status": 204, "error": True, "message": "Đơn đã lấy hàng " + TOK_DAI})
ra = chay("vtp_huy_don", {"order_number": "X1"}, sp_san())
check("error true -> ERROR", ra.startswith("ERROR") and "204" in ra, ra)
check("lỗi API không lộ token", TOK_DAI not in ra, ra)
gia.tra("/v2/categories/listProvince", {"loi": "bad " + TOK_DAI + " " + PASS}, code=500)
ra = chay("vtp_tinh_thanh", {}, sp_san())
check("HTTP 500 -> ERROR không lộ token/mật khẩu", ra.startswith("ERROR") and TOK_DAI not in ra and PASS not in ra, ra)
gia.nem_loi("/v2/categories/listWards", httpx.ConnectError("không nối được Token=" + TOK_DAI))
ra = chay("vtp_phuong_xa", {"district_id": 1}, sp_san())
check("ngoại lệ mạng -> ERROR không lộ token", ra.startswith("ERROR") and TOK_DAI not in ra, ra)
gia.tra("/v2/categories/listDistrict", "<html>bad gateway</html>")
check("trả về không phải JSON -> ERROR", chay("vtp_quan_huyen", {"province_id": 1}, sp_san()).startswith("ERROR"))
gia.tra("/v2/user/listInventory", boc([{"ghi_chu": "token " + TOK_DAI}]))
ra = chay("vtp_kho_hang", {}, sp_san())
check("kết quả thành công nhại token cũng bị giấu", TOK_DAI not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.nem_loi("/v2/user/Login", httpx.ConnectError("timeout USERNAME=" + USER + " PASSWORD=" + PASS))
ra = chay("vtp_tinh_thanh")
check("lỗi mạng khi đăng nhập không lộ mật khẩu", ra.startswith("ERROR") and PASS not in ra, ra)
gia.go()

# ---- 6. văn bản sạch ----
src = open(SERVER / "viettelpost_mcp.py", encoding="utf-8").read()
check("không có em/en dash", "\u2014" not in src and "\u2013" not in src)
check("không ghim cứng UTC+7", "timedelta(hours=7)" not in src)

check.ket_thuc()
