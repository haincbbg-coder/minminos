"""Cầu nối Ahamove (server/ahamove_mcp.py). Không mạng.

    python tests/run.py ahamove_mcp

Phủ: lấy token qua /accounts/token (mobile + api_key), hạn đọc từ exp của JWT, token được LƯU và
lần sau dùng lại; hết hạn hoặc đổi tài khoản thì lấy lại; 401 thì lấy lại đúng một lần; header
Bearer; đúng URL/params/body từng tool; kiểm tra đầu vào (sai thì KHÔNG gọi mạng); chặn chèn đường
dẫn vào order_id/tracking_number; lỗi HTTP; không lộ api_key/token; thiếu ô; tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import json
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-aha-"))

import httpx  # noqa: E402

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import ahamove_mcp as a  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

KEY = "aha-api-key-bi-mat-5566778899"
MOBILE = "84912345678"
LIVE = "https://partner-api.ahamove.com/v3"
STG = "https://partner-apistg.ahamove.com/v3"


def jwt(exp, duoi="chuky"):
    def b(x):
        return base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip("=")
    return f"{b({'alg': 'HS256'})}.{b({'exp': exp, 'typ': 'user'})}.{duoi}"


EXP = int(time.time()) + 5 * 86400
TOK = jwt(EXP, "aaaa1111bbbb")
TOK2 = jwt(EXP, "cccc2222dddd")


def spec(**them):
    sec = {"api_key": KEY, "mobile": MOBILE}
    sec.update(them)
    return {"key": "conn-aha-1", "secrets": sec}


def chay(tool, args=None, sp=None):
    return asyncio.run(a.call(tool, args or {}, sp if sp is not None else spec()))


def sp_san(tok=TOK):
    s = spec(access_token=tok, token_het_han=str(EXP))
    s["secrets"]["token_tk"] = a._dau_tk(s["secrets"])
    return s


# ---- 0. khai báo ----
ten = [t["name"] for t in asyncio.run(a.list_tools({}))]
check("đủ 7 tool", len(ten) == 7 and "aha_tao_don" in ten and "aha_huy_don" in ten, ten)
ra = chay("aha_thanh_pho", {}, {"secrets": {"api_key": KEY}})
check("thiếu mobile -> báo rõ", ra.startswith("ERROR") and "mobile" in ra, ra)
check("tool lạ -> ERROR", chay("aha_xoa_het").startswith("ERROR"))

# ---- 1. token ----
gia = GiaHttp().lap()
gia.tra("/accounts/token", {"token": TOK, "refresh_token": "rf-1"})
gia.tra("/cities", [{"_id": "SGN", "name": "Hồ Chí Minh"}])
sp = spec()
ra = chay("aha_thanh_pho", {}, sp)
check("thành phố trả dữ liệu", "SGN" in ra, ra)
g0, g1 = gia.goi
check("lấy token POST /accounts/token body mobile + api_key", g0["method"] == "POST"
      and g0["url"] == LIVE + "/accounts/token" and g0["json"] == {"mobile": MOBILE, "api_key": KEY}, g0)
check("thành phố GET /cities?country_id=VN", g1["method"] == "GET" and g1["url"] == LIVE + "/cities"
      and g1["params"] == {"country_id": "VN"})
check("header Bearer token", g1["headers"].get("Authorization") == "Bearer " + TOK)
check("token được lưu", any(p["fields"].get("access_token") == TOK for _, p in da_luu))
check("hạn lấy từ exp của JWT", sp["secrets"]["token_het_han"] == str(EXP), sp["secrets"].get("token_het_han"))
n = len(gia.goi)
chay("aha_thanh_pho", {}, sp)
check("lần hai dùng lại token, không lấy mới", len(gia.goi) == n + 1 and gia.goi[-1]["url"].endswith("/cities"))
sp["secrets"]["token_het_han"] = str(int(time.time()) - 1)
n = len(gia.goi)
chay("aha_thanh_pho", {}, sp)
check("hết hạn thì lấy token mới", gia.goi[n]["url"].endswith("/accounts/token"))
sp["secrets"]["api_key"] = KEY + "-moi"
n = len(gia.goi)
chay("aha_thanh_pho", {}, sp)
check("đổi api_key thì lấy token mới", gia.goi[n]["url"].endswith("/accounts/token")
      and gia.goi[n]["json"]["api_key"] == KEY + "-moi")
gia.go()

gia = GiaHttp().lap()
gia.tra("/accounts/token", {"token": "khong-phai-jwt-123456"})
gia.tra("/cities", [])
sp = spec()
chay("aha_thanh_pho", {}, sp)
check("token không phải JWT -> hạn mặc định trong tương lai", int(sp["secrets"]["token_het_han"]) > time.time() + 3600)
gia.go()

# 401 -> lấy token lại đúng một lần
gia = GiaHttp().lap()
gia.tra("/accounts/token", {"token": TOK2})
gia.tra("/orders/ORD1", {"title": "Not authorized"}, code=401)
gia.tra("/orders/ORD1", {"_id": "ORD1", "status": "ASSIGNING"})
ra = chay("aha_chi_tiet_don", {"order_id": "ORD1"}, sp_san())
urls = [g["url"].replace(LIVE, "") for g in gia.goi]
check("401 -> lấy token lại rồi gọi lại", urls == ["/orders/ORD1", "/accounts/token", "/orders/ORD1"]
      and "ASSIGNING" in ra, (urls, ra))
check("lượt sau dùng token mới", gia.goi[-1]["headers"]["Authorization"] == "Bearer " + TOK2)
gia.go()
gia = GiaHttp().lap()
gia.tra("/accounts/token", {"token": TOK2})
gia.tra("/orders/ORD1", {"title": "Not authorized"}, code=401)
ra = chay("aha_chi_tiet_don", {"order_id": "ORD1"}, sp_san())
check("401 mãi -> ERROR, chỉ lấy token lại một lần",
      ra.startswith("ERROR") and sum(1 for g in gia.goi if g["url"].endswith("/accounts/token")) == 1, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/accounts/token", {"code": 404, "title": "PARTNER_NOT_FOUND " + KEY}, code=404)
ra = chay("aha_thanh_pho")
check("api_key sai -> ERROR không lộ key", ra.startswith("ERROR") and KEY not in ra and "404" in ra, ra)
check("lấy token hỏng không gọi tiếp", len(gia.goi) == 1)
gia.go()
gia = GiaHttp().lap()
gia.tra("/accounts/token", {"token": TOK})
gia.tra("/cities", [])
chay("aha_thanh_pho", {}, spec(moi_truong="test"))
check("moi_truong test dùng host staging", all(g["url"].startswith(STG) for g in gia.goi), [g["url"] for g in gia.goi])
gia.go()

# ---- 2. tool đọc ----
gia = GiaHttp().lap()
gia.tra("ahamove.com", {"ok": 1})
chay("aha_dich_vu", {"city_id": "sgn", "delivery_type": "instant"}, sp_san())
r = gia.goi[-1]
check("dịch vụ GET /services?city_id", r["url"] == LIVE + "/services"
      and r["params"] == {"city_id": "SGN", "delivery_type": "INSTANT"}, r["params"])
chay("aha_dich_vu", {"lat": 10.77, "lng": 106.66}, sp_san())
check("dịch vụ theo toạ độ", gia.goi[-1]["params"] == {"lat": 10.77, "lng": 106.66})
n = len(gia.goi)
check("dịch vụ thiếu city và toạ độ -> ERROR", chay("aha_dich_vu", {}, sp_san()).startswith("ERROR"))
check("city_id có ký tự lạ -> ERROR", chay("aha_dich_vu", {"city_id": "SGN&x=1"}, sp_san()).startswith("ERROR"))
check("lat ngoài khoảng -> ERROR", chay("aha_dich_vu", {"lat": 200, "lng": 1}, sp_san()).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n)

DUONG = [{"address": "7/28 Thành Thái, Q10", "name": "HALIMI", "mobile": "0912 345 678", "lat": 10.769, "lng": 106.663},
         {"address": "475A Điện Biên Phủ", "name": "Chị Anh", "mobile": "0987654321", "cod": 450000,
          "tracking_number": "HALIMI-01"}]
chay("aha_uoc_tinh_phi", {"path": DUONG, "services": ["sgn-bike", "SGN-EXPRESS"]}, sp_san())
r = gia.goi[-1]
check("ước tính phí POST /orders/estimates", r["method"] == "POST" and r["url"] == LIVE + "/orders/estimates")
b = r["json"]
check("ước tính phí services dạng [{_id, requests}]", b["services"] == [{"_id": "SGN-BIKE", "requests": []},
                                                                         {"_id": "SGN-EXPRESS", "requests": []}], b)
check("ước tính phí mặc định CASH, giao ngay", b["payment_method"] == "CASH" and b["order_time"] == 0)
check("ước tính phí chuẩn hoá số điện thoại, giữ cod", b["path"][0]["mobile"] == "0912345678"
      and b["path"][1]["cod"] == 450000 and b["path"][1]["tracking_number"] == "HALIMI-01", b["path"])
n = len(gia.goi)
for ten_ca, args in [("một điểm", {"path": DUONG[:1], "services": ["SGN-BIKE"]}),
                     ("thiếu services", {"path": DUONG}),
                     ("dịch vụ có /", {"path": DUONG, "services": ["SGN/BIKE"]}),
                     ("điểm thiếu mobile", {"path": [DUONG[0], {"address": "x", "name": "y"}], "services": ["SGN-BIKE"]}),
                     ("cod ở điểm lấy hàng", {"path": [{**DUONG[0], "cod": 1000}, DUONG[1]], "services": ["SGN-BIKE"]}),
                     ("cod quá 50 triệu", {"path": [DUONG[0], {**DUONG[1], "cod": 50_000_001}], "services": ["SGN-BIKE"]}),
                     ("payment lạ", {"path": DUONG, "services": ["SGN-BIKE"], "payment_method": "CARD"}),
                     ("order_time quá xa", {"path": DUONG, "services": ["SGN-BIKE"], "order_time": int(time.time()) + 30 * 86400})]:
    check("ước tính phí từ chối: " + ten_ca, chay("aha_uoc_tinh_phi", args, sp_san()).startswith("ERROR"))
check("ước tính sai KHÔNG gọi mạng", len(gia.goi) == n)

chay("aha_chi_tiet_don", {"order_id": "24ABCD12"}, sp_san())
check("chi tiết đơn GET /orders/<id>", gia.goi[-1]["url"] == LIVE + "/orders/24ABCD12" and gia.goi[-1]["method"] == "GET")
chay("aha_don_theo_ma_van_don", {"tracking_number": "HALIMI-01"}, sp_san())
check("đơn theo mã vận đơn GET /orders/tracks/<mã>", gia.goi[-1]["url"] == LIVE + "/orders/tracks/HALIMI-01")
n = len(gia.goi)
for bad in ("../accounts", "a/b", "a?x=1", "a#b", "%2e%2e", ""):
    check(f"chi tiết đơn chặn {bad!r}", chay("aha_chi_tiet_don", {"order_id": bad}, sp_san()).startswith("ERROR"))
    check(f"mã vận đơn chặn {bad!r}",
          chay("aha_don_theo_ma_van_don", {"tracking_number": bad}, sp_san()).startswith("ERROR"))
check("chèn đường dẫn KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 3. tạo đơn ----
DON = {"path": DUONG, "service_id": "sgn-bike", "payment_method": "CASH_BY_RECIPIENT",
       "requests": [{"_id": "SGN-BIKE-TIP", "num": 1}], "remarks": "Gọi trước khi giao",
       "items": [{"name": "Váy lụa", "num": 1, "price": 450000}]}
gia = GiaHttp().lap()
gia.tra("/v3/orders", {"order_id": "24XYZ", "status": "ASSIGNING", "shared_link": "https://aha.vn/x"})
ra = chay("aha_tao_don", DON, sp_san())
r = gia.goi[-1]
check("tạo đơn trả order_id", "24XYZ" in ra, ra)
check("tạo đơn POST /orders", r["method"] == "POST" and r["url"] == LIVE + "/orders")
b = r["json"]
check("tạo đơn body đúng", b["service_id"] == "SGN-BIKE" and b["payment_method"] == "CASH_BY_RECIPIENT"
      and b["order_time"] == 0 and b["requests"] == [{"_id": "SGN-BIKE-TIP", "num": 1}]
      and b["items"] == [{"_id": "SP1", "name": "Váy lụa", "num": 1, "price": 450000}], b)
check("tạo đơn header Bearer", r["headers"].get("Authorization") == "Bearer " + TOK)
n = len(gia.goi)
sai = [("thiếu service_id", {**DON, "service_id": ""}),
       ("thiếu payment_method", {kk: vv for kk, vv in DON.items() if kk != "payment_method"}),
       ("payment lạ", {**DON, "payment_method": "FREE"}),
       ("path một điểm", {**DON, "path": DUONG[:1]}),
       ("path quá 10 điểm", {**DON, "path": [DUONG[0]] * 11}),
       ("số điện thoại có chữ", {**DON, "path": [DUONG[0], {**DUONG[1], "mobile": "09abc"}]}),
       ("request _id lạ", {**DON, "requests": [{"_id": "../x"}]}),
       ("items thiếu num", {**DON, "items": [{"name": "x"}]}),
       ("order_time âm", {**DON, "order_time": -5})]
for ten_ca, d in sai:
    check("tạo đơn từ chối: " + ten_ca, chay("aha_tao_don", d, sp_san()).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n, len(gia.goi) - n)
gia.go()

# ---- 4. hủy đơn ----
gia = GiaHttp().lap()
gia.tra("/orders/24XYZ", {})
chay("aha_huy_don", {"order_id": "24XYZ", "ly_do": "Khách đổi ý"}, sp_san())
r = gia.goi[-1]
check("hủy đơn DELETE /orders/<id> body comment", r["method"] == "DELETE" and r["url"] == LIVE + "/orders/24XYZ"
      and r["json"] == {"comment": "Khách đổi ý"}, r)
n = len(gia.goi)
check("hủy mã ../x -> ERROR", chay("aha_huy_don", {"order_id": "../x"}, sp_san()).startswith("ERROR"))
check("hủy mã a/b -> ERROR", chay("aha_huy_don", {"order_id": "a/b"}, sp_san()).startswith("ERROR"))
check("hủy thiếu mã -> ERROR", chay("aha_huy_don", {}, sp_san()).startswith("ERROR"))
check("hủy sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 5. lỗi, không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/orders/E1", {"code": 406, "title": "INVALID_ORDER_STATUS " + TOK + " " + KEY}, code=406)
ra = chay("aha_huy_don", {"order_id": "E1"}, sp_san())
check("HTTP 406 -> ERROR", ra.startswith("ERROR") and "406" in ra, ra)
check("lỗi API không lộ token/api_key", TOK not in ra and KEY not in ra, ra)
gia.nem_loi("/cities", httpx.ConnectError("không nối được Bearer " + TOK))
ra = chay("aha_thanh_pho", {}, sp_san())
check("ngoại lệ mạng -> ERROR không lộ token", ra.startswith("ERROR") and TOK not in ra, ra)
gia.tra("/orders/tracks/T1", [{"ghi_chu": "key=" + KEY}])
ra = chay("aha_don_theo_ma_van_don", {"tracking_number": "T1"}, sp_san())
check("kết quả thành công nhại api_key cũng bị giấu", KEY not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.nem_loi("/accounts/token", httpx.ConnectError("timeout api_key=" + KEY))
ra = chay("aha_thanh_pho")
check("lỗi mạng khi lấy token không lộ api_key", ra.startswith("ERROR") and KEY not in ra, ra)
gia.go()

src = open(SERVER / "ahamove_mcp.py", encoding="utf-8").read()
check("không có em/en dash", "\u2014" not in src and "\u2013" not in src)

check.ket_thuc()
