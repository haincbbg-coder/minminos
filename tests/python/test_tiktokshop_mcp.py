"""Cầu nối TikTok Shop (server/tiktokshop_mcp.py). Không mạng.

    python tests/run.py tiktokshop_mcp

Phủ: chữ ký HMAC đúng công thức 202309 (có thân POST), đổi code lấy token rồi LƯU, code đã dùng
không đổi lại lần hai, tự tìm và lưu shop_cipher, token hết hạn thì tự làm mới, hai lượt làm mới
song song chỉ gọi TikTok MỘT lần, lọc trạng thái lạ, giới hạn số lượng, chặn gọi thô, lỗi không
lộ bí mật.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import json
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-tiktokshop-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import tiktokshop_mcp as s  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

SECRET = "bi-mat-app-tiktok-987654"
AKEY = "6abcappkey01"


def spec(**them):
    sec = {"app_key": AKEY, "app_secret": SECRET}
    sec.update(them)
    return {"key": "conn-tts-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def ky_doc_lap(path, params, body=""):
    """Tự tính lại chữ ký, không dùng code của module."""
    p = {kk: v for kk, v in params.items() if kk not in ("sign", "access_token")}
    chuoi = path
    for kk in sorted(p):
        chuoi += kk + str(p[kk])
    chuoi = SECRET + chuoi + body + SECRET
    return hmac.new(SECRET.encode(), chuoi.encode(), hashlib.sha256).hexdigest()


CON_HAN = str(int(time.time()) + 99999)

# ---- 1. chữ ký ----
q = {"app_key": AKEY, "timestamp": 1700000000, "shop_cipher": "ROW_abc", "page_size": 10,
     "access_token": "khong-tinh", "sign": "khong-tinh"}
body = '{"create_time_ge":1,"create_time_lt":2}'
check("ký GET đúng công thức", s.ky(SECRET, "/order/202309/orders", q) == ky_doc_lap("/order/202309/orders", q))
check("ký POST có thân JSON", s.ky(SECRET, "/order/202309/orders/search", q, body)
      == ky_doc_lap("/order/202309/orders/search", q, body))
check("ký bỏ access_token và sign", s.ky(SECRET, "/x/202309/y", {"a": 1, "access_token": "Z"})
      == s.ky(SECRET, "/x/202309/y", {"a": 1}))
check("chữ ký là hex thường", s.ky(SECRET, "/a", {}) == s.ky(SECRET, "/a", {}).lower())

# ---- 2. thiếu ô ----
check("thiếu app_secret -> báo rõ", "app_secret" in chay(s.call("tiktokshop_thong_tin_shop", {},
                                                                {"secrets": {"app_key": "x"}})))
check("chưa có code/token -> chỉ cách ủy quyền",
      "code" in chay(s.call("tiktokshop_thong_tin_shop", {}, spec())))

# ---- 3. đổi code lấy token, tìm shop_cipher, lưu ----
gia = GiaHttp().lap()
het = int(time.time()) + 7 * 86400
gia.tra("/api/v2/token/get", {"code": 0, "message": "success", "data": {
    "access_token": "AT-TTS-0001", "access_token_expire_in": het, "refresh_token": "RT-TTS-0001",
    "refresh_token_expire_in": het + 86400, "seller_name": "HALIMI"}})
gia.tra("/authorization/202309/shops", {"code": 0, "message": "Success", "data": {
    "shops": [{"cipher": "ROW_CIPHER_1", "name": "HALIMI Official", "region": "VN"}]}})
gia.tra("/order/202309/orders/search", {"code": 0, "message": "Success", "data": {
    "orders": [{"id": "5770001"}], "next_page_token": ""}})
sp = spec(auth_code="CODE-TTS-1")
ra = chay(s.call("tiktokshop_don_hang", {"trang_thai": "COMPLETED", "so_luong": 500}, sp))
check("đổi code xong lấy được đơn", "5770001" in ra, ra)
tk = [g for g in gia.goi if "token/get" in g["url"]][0]
check("đổi code gọi auth host", tk["url"].startswith("https://auth.tiktok-shops.com/"))
check("đổi code gửi đúng tham số", tk["params"] == {"app_key": AKEY, "app_secret": SECRET,
                                                    "auth_code": "CODE-TTS-1",
                                                    "grant_type": "authorized_code"}, tk["params"])
sh = [g for g in gia.goi if "authorization/202309/shops" in g["url"]][0]
check("tra shop không gửi shop_cipher", "shop_cipher" not in sh["params"])
check("tra shop ký đúng", sh["params"]["sign"] == ky_doc_lap("/authorization/202309/shops", sh["params"]))
check("header mang access token", sh["headers"].get("x-tts-access-token") == "AT-TTS-0001")
dh = [g for g in gia.goi if "orders/search" in g["url"]][0]
check("đơn hàng là POST", dh["method"] == "POST")
check("đơn hàng gửi shop_cipher vừa tìm", dh["params"]["shop_cipher"] == "ROW_CIPHER_1")
check("access_token không nằm trên query", "access_token" not in dh["params"])
than = dh["content"].decode("utf-8")
check("thân gửi đúng chuỗi đã ký", dh["params"]["sign"] == ky_doc_lap("/order/202309/orders/search",
                                                                       dh["params"], than), than)
bd = json.loads(than)
check("lọc trạng thái hợp lệ được gửi", bd.get("order_status") == "COMPLETED")
check("khoảng ngày mặc định 7 ngày", 0 < bd["create_time_lt"] - bd["create_time_ge"] <= 8 * 86400)
check("page_size bị cắt còn 100", dh["params"]["page_size"] == 100)
luu = {}
for _cid, patch in da_luu:
    luu.update(patch["fields"])
check("token mới được LƯU", luu.get("access_token") == "AT-TTS-0001" and luu.get("refresh_token") == "RT-TTS-0001")
check("hạn token lấy mốc unix của TikTok", luu.get("token_het_han") == str(het))
check("đánh dấu code đã dùng", luu.get("auth_code_da_dung") == "CODE-TTS-1")
check("shop_cipher được LƯU", luu.get("shop_cipher") == "ROW_CIPHER_1")
check("lưu vào đúng kết nối", all(c == "conn-tts-1" for c, _ in da_luu))

n_truoc = len([g for g in gia.goi if "token/get" in g["url"]])
n_shop = len([g for g in gia.goi if "authorization/202309/shops" in g["url"]])
chay(s.call("tiktokshop_don_hang", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if "token/get" in g["url"]]) == n_truoc)
check("shop_cipher đã lưu không tra lại", len([g for g in gia.goi if "authorization/202309/shops" in g["url"]]) == n_shop)
gia.go()

# ---- 4. token hết hạn -> làm mới, song song chỉ một lần ----
gia = GiaHttp().lap()
gia.tra("/api/v2/token/refresh", {"code": 0, "message": "success", "data": {
    "access_token": "AT-2", "access_token_expire_in": int(time.time()) + 86400, "refresh_token": "RT-2",
    "refresh_token_expire_in": int(time.time()) + 9 * 86400}})
gia.tra("/product/202309/products/search", {"code": 0, "message": "Success", "data": {"products": [{"id": "P1"}]}})
sp = spec(access_token="AT-CU", refresh_token="RT-CU", token_het_han=str(int(time.time()) - 10),
          refresh_het_han=CON_HAN, shop_cipher="ROW_X")


async def hai_luot():
    return await asyncio.gather(s.call("tiktokshop_san_pham", {}, sp), s.call("tiktokshop_san_pham", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("làm mới xong lấy được sản phẩm", "P1" in r1 and "P1" in r2, r1)
lm = [g for g in gia.goi if "token/refresh" in g["url"]]
check("hai lượt song song chỉ làm mới MỘT lần", len(lm) == 1, len(lm))
check("làm mới gửi refresh token cũ", lm and lm[0]["params"]["refresh_token"] == "RT-CU"
      and lm[0]["params"]["grant_type"] == "refresh_token")
spg = [g for g in gia.goi if "products/search" in g["url"]][-1]
check("sản phẩm dùng token mới", spg["headers"]["x-tts-access-token"] == "AT-2")
check("trạng thái sản phẩm trống -> thân rỗng", spg["content"] == b"{}")
chay(s.call("tiktokshop_san_pham", {"trang_thai": "XOA_HET"}, sp))
check("trạng thái sản phẩm lạ bị bỏ", json.loads(gia.goi[-1]["content"]) == {})
chay(s.call("tiktokshop_san_pham", {"trang_thai": "ACTIVATE"}, sp))
check("trạng thái sản phẩm hợp lệ được gửi", json.loads(gia.goi[-1]["content"]) == {"status": "ACTIVATE"})
gia.go()

# refresh token đã hết hạn -> báo ủy quyền lại, không gọi mạng
gia = GiaHttp().lap()
ra = chay(s.call("tiktokshop_san_pham", {}, spec(access_token="A", refresh_token="R",
                                                  token_het_han="1", refresh_het_han="1", shop_cipher="C")))
check("refresh hết hạn -> báo ủy quyền lại", ra.startswith("ERROR") and not gia.goi, ra)
gia.go()

# ---- 5. giới hạn, lọc, gọi thô ----
gia = GiaHttp().lap()
gia.tra("tiktokglobalshop.com", {"code": 0, "message": "Success", "data": {}})
sp = spec(access_token="AT-OK-123456", token_het_han=CON_HAN, shop_cipher="ROW_Y")
chay(s.call("tiktokshop_don_hang", {"trang_thai": "XOA_HET"}, sp))
check("trạng thái đơn lạ bị bỏ", "order_status" not in json.loads(gia.goi[-1]["content"]))
chay(s.call("tiktokshop_chi_tiet_don", {"order_id": ",".join(str(570000 + i) for i in range(80))}, sp))
g = gia.goi[-1]
check("chi tiết đơn cắt còn 50 mã", len(g["params"]["ids"].split(",")) == 50)
check("chi tiết đơn là GET không thân", g["method"] == "GET" and g["content"] is None)
check("chi tiết đơn bỏ mã không phải số",
      chay(s.call("tiktokshop_chi_tiet_don", {"order_id": "abc;drop"}, sp)).startswith("ERROR"))
check("chi tiết sản phẩm đòi id số",
      chay(s.call("tiktokshop_chi_tiet_san_pham", {"product_id": "../x"}, sp)).startswith("ERROR"))
chay(s.call("tiktokshop_chi_tiet_san_pham", {"product_id": "1729"}, sp))
check("chi tiết sản phẩm đúng path", gia.goi[-1]["url"].endswith("/product/202309/products/1729"))

check("gọi thô chặn path lạ", chay(s.call("tiktokshop_goi_api", {"path": "https://evil/x"}, sp)).startswith("ERROR"))
check("gọi thô chặn ..", chay(s.call("tiktokshop_goi_api", {"path": "/order/202309/../x"}, sp)).startswith("ERROR"))
check("gọi thô chặn ?", chay(s.call("tiktokshop_goi_api", {"path": "/order/202309/orders?a=1"}, sp)).startswith("ERROR"))
check("gọi thô đòi phiên bản 6 số", chay(s.call("tiktokshop_goi_api", {"path": "/api/v2/token/get"}, sp)).startswith("ERROR"))
n = len(gia.goi)
chay(s.call("tiktokshop_goi_api", {"path": "/logistics/202309/warehouses",
                                   "params": {"x": "1", "app_key": "GIA", "access_token": "TOKEN-GIA",
                                              "shop_cipher": "GIA", "sign": "GIA", "timestamp": 1}}, sp))
check("gọi thô có gửi đi", len(gia.goi) == n + 1)
g = gia.goi[-1]
check("gọi thô là GET", g["method"] == "GET")
check("gọi thô không cho ghi đè tham số hệ thống", g["params"]["app_key"] == AKEY
      and g["params"]["shop_cipher"] == "ROW_Y" and "access_token" not in g["params"]
      and g["params"]["sign"] == ky_doc_lap("/logistics/202309/warehouses", g["params"]))
check("gọi thô giữ tham số thường", g["params"].get("x") == "1")
gia.go()

# ---- 6. lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/authorization/202309/shops", {"code": 105002, "message": "Invalid access token AT-LO-BI-MAT-999"})
ra = chay(s.call("tiktokshop_thong_tin_shop", {}, spec(access_token="AT-LO-BI-MAT-999", token_het_han=CON_HAN)))
check("lỗi TikTok được báo kèm mã", ra.startswith("ERROR") and "105002" in ra, ra)
check("lỗi KHÔNG lộ access token", "AT-LO-BI-MAT-999" not in ra, ra)
gia.nem_loi("/authorization/202309/shops", ConnectionError("không tới được " + SECRET))
ra = chay(s.call("tiktokshop_thong_tin_shop", {}, spec(access_token="AT-X-123456", token_het_han=CON_HAN)))
check("lỗi mạng KHÔNG lộ app secret", SECRET not in ra and ra.startswith("ERROR"), ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/api/v2/token/get", {"code": 36004004, "message": "auth code CODE-BI-MAT-77 invalid " + SECRET})
ra = chay(s.call("tiktokshop_thong_tin_shop", {}, spec(auth_code="CODE-BI-MAT-77")))
check("đổi code lỗi -> báo, không lộ code và secret",
      ra.startswith("ERROR") and "CODE-BI-MAT-77" not in ra and SECRET not in ra, ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("tiktokshop_xoa_shop", {}, sp)).startswith("ERROR"))
check("list_tools đủ 6 tool", len(chay(s.list_tools({}))) == 6)
check.ket_thuc()
