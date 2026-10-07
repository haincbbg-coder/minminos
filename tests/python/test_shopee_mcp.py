"""Cầu nối Shopee (server/shopee_mcp.py). Không mạng.

    python tests/run.py shopee_mcp

Phủ: chữ ký HMAC đúng công thức v2, đổi code lấy token rồi LƯU, code đã dùng không đổi lại lần
hai, token hết hạn thì tự làm mới (refresh token dùng một lần), hai lượt làm mới song song chỉ
gọi Shopee MỘT lần, lỗi không lộ bí mật, giới hạn 15 ngày, chặn gọi thô vào nhóm auth.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-shopee-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import shopee_mcp as s  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

PKEY = "khoa-doi-tac-bi-mat-123456"


def spec(**them):
    sec = {"partner_id": "2001234", "partner_key": PKEY, "shop_id": "778899"}
    sec.update(them)
    return {"key": "conn-shopee-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def ky(base):
    return hmac.new(PKEY.encode(), base.encode(), hashlib.sha256).hexdigest()


# ---- 1. link ủy quyền ----
url = s.lien_ket_uy_quyen(spec()["secrets"], "https://minmin.vi.du/cb", ts=1700000000)
check("link ủy quyền trỏ đúng host live", url.startswith("https://partner.shopeemobile.com/api/v2/shop/auth_partner?"))
check("link ủy quyền ký partner_id+path+timestamp",
      "sign=" + ky("2001234/api/v2/shop/auth_partner1700000000") in url, url)
check("link ủy quyền không chứa partner_key", PKEY not in url)
check("môi trường test đổi host",
      s.lien_ket_uy_quyen(spec(moi_truong="test")["secrets"], "https://a.b", 1).startswith(
          "https://partner.test-stable.shopeemobile.com"))
check("tool link ủy quyền đòi redirect https",
      chay(s.call("shopee_lien_ket_uy_quyen", {"redirect_url": "javascript:x"}, spec())).startswith("ERROR"))

# ---- 2. thiếu ô / sai kiểu ----
check("thiếu partner_key -> báo rõ", "partner_key" in chay(s.call("shopee_thong_tin_shop", {},
                                                                  {"secrets": {"partner_id": "1", "shop_id": "2"}})))
check("partner_id không phải số -> từ chối",
      chay(s.call("shopee_thong_tin_shop", {}, spec(partner_id="abc"))).startswith("ERROR"))
check("chưa có code/token -> chỉ cách ủy quyền",
      "shopee_lien_ket_uy_quyen" in chay(s.call("shopee_thong_tin_shop", {}, spec())))

# ---- 3. đổi code lấy token rồi lưu ----
gia = GiaHttp().lap()
gia.tra("/api/v2/auth/token/get", {"error": "", "access_token": "AT-MOI-0001", "refresh_token": "RT-MOI-0001",
                                    "expire_in": 14400})
gia.tra("/api/v2/shop/get_shop_info", {"error": "", "message": "", "shop_name": "HALIMI Official"})
sp = spec(auth_code="CODE-ABC-1")
ra = chay(s.call("shopee_thong_tin_shop", {}, sp))
check("đổi code xong gọi được API shop", "HALIMI Official" in ra, ra)
tk = [g for g in gia.goi if "token/get" in g["url"]][0]
check("đổi code gửi đúng code + shop_id dạng số", tk["json"] == {"code": "CODE-ABC-1", "shop_id": 778899,
                                                                 "partner_id": 2001234}, tk["json"])
check("đổi code ký không kèm token", tk["params"]["sign"] == ky(f"2001234/api/v2/auth/token/get{tk['params']['timestamp']}"))
api = [g for g in gia.goi if "get_shop_info" in g["url"]][0]
p = api["params"]
check("API shop ký partner_id+path+ts+token+shop",
      p["sign"] == ky(f"2001234/api/v2/shop/get_shop_info{p['timestamp']}AT-MOI-00017788 99".replace(" ", "")))
luu = {}
for _cid, patch in da_luu:
    luu.update(patch["fields"])
check("token mới được LƯU vào kết nối", luu.get("access_token") == "AT-MOI-0001" and luu.get("refresh_token") == "RT-MOI-0001")
check("đánh dấu code đã dùng", luu.get("auth_code_da_dung") == "CODE-ABC-1")
check("lưu vào đúng kết nối", all(c == "conn-shopee-1" for c, _ in da_luu))

# gọi lần hai: code đã dùng thì KHÔNG đổi lại (Shopee sẽ báo code hết hạn)
n_truoc = len([g for g in gia.goi if "token/get" in g["url"]])
chay(s.call("shopee_thong_tin_shop", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if "token/get" in g["url"]]) == n_truoc)
gia.go()

# ---- 4. token hết hạn -> làm mới, song song chỉ làm mới một lần ----
gia = GiaHttp().lap()
gia.tra("/api/v2/auth/access_token/get", {"error": "", "access_token": "AT-2", "refresh_token": "RT-2", "expire_in": 14400})
gia.tra("/api/v2/order/get_order_list", {"error": "", "response": {"order_list": [{"order_sn": "X1"}], "more": False}})
sp = spec(access_token="AT-CU", refresh_token="RT-CU", token_het_han=str(int(time.time()) - 10))


async def hai_luot():
    return await asyncio.gather(s.call("shopee_don_hang", {}, sp), s.call("shopee_don_hang", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("làm mới xong lấy được đơn", "X1" in r1 and "X1" in r2, r1)
lm = [g for g in gia.goi if "access_token/get" in g["url"]]
check("hai lượt song song chỉ làm mới MỘT lần (refresh token dùng một lần)", len(lm) == 1, len(lm))
check("làm mới gửi refresh token cũ", lm and lm[0]["json"]["refresh_token"] == "RT-CU")
dh = [g for g in gia.goi if "get_order_list" in g["url"]][0]["params"]
check("đơn hàng mặc định 7 ngày", dh["time_to"] - dh["time_from"] <= 7 * 86400 + 86400)
check("đơn hàng dùng token mới", dh["access_token"] == "AT-2")
gia.go()

# ---- 5. giới hạn 15 ngày, lọc trạng thái, cắt 50 mã ----
gia = GiaHttp().lap()
gia.tra("shopeemobile.com", {"error": ""})
sp = spec(access_token="AT", token_het_han=str(int(time.time()) + 9999))
chay(s.call("shopee_don_hang", {"tu_ngay": "2026-01-01", "den_ngay": "2026-03-01", "trang_thai": "COMPLETED"}, sp))
dh = gia.goi[-1]["params"]
check("khoảng ngày bị cắt còn 15 ngày", dh["time_to"] - dh["time_from"] <= 15 * 86400, dh["time_to"] - dh["time_from"])
check("lọc trạng thái hợp lệ được gửi", dh.get("order_status") == "COMPLETED")
chay(s.call("shopee_don_hang", {"trang_thai": "XOA_HET"}, sp))
check("trạng thái lạ bị bỏ", "order_status" not in gia.goi[-1]["params"])
chay(s.call("shopee_chi_tiet_don", {"order_sn": ",".join(f"S{i}" for i in range(80))}, sp))
check("chi tiết đơn cắt còn 50 mã", len(gia.goi[-1]["params"]["order_sn_list"].split(",")) == 50)
check("chi tiết sản phẩm bỏ id không phải số",
      chay(s.call("shopee_chi_tiet_san_pham", {"item_id": "abc,;drop"}, sp)).startswith("ERROR"))

# ---- 6. gọi thô: chỉ GET, chặn nhóm auth, không cho ghi đè tham số ký ----
check("gọi thô chặn nhóm auth",
      chay(s.call("shopee_goi_api", {"path": "/api/v2/auth/token/get"}, sp)).startswith("ERROR"))
check("gọi thô chặn path lạ", chay(s.call("shopee_goi_api", {"path": "https://evil/x"}, sp)).startswith("ERROR"))
check("gọi thô chặn ..", chay(s.call("shopee_goi_api", {"path": "/api/v2/../x"}, sp)).startswith("ERROR"))
chay(s.call("shopee_goi_api", {"path": "/api/v2/logistics/get_tracking_number",
                               "params": {"order_sn": "A", "access_token": "TOKEN-GIA", "shop_id": 1}}, sp))
g = gia.goi[-1]
check("gọi thô là GET", g["method"] == "GET")
check("gọi thô không cho model ghi đè access_token/shop_id", g["params"]["access_token"] == "AT"
      and g["params"]["shop_id"] == 778899)
gia.go()

# ---- 7. lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("get_shop_info", {"error": "error_auth", "message": "Invalid access_token AT-LO-BI-MAT-999"})
ra = chay(s.call("shopee_thong_tin_shop", {}, spec(access_token="AT-LO-BI-MAT-999",
                                                     token_het_han=str(int(time.time()) + 9999))))
check("lỗi Shopee được báo", ra.startswith("ERROR") and "error_auth" in ra, ra)
check("lỗi KHÔNG lộ access token", "AT-LO-BI-MAT-999" not in ra, ra)
gia.nem_loi("get_shop_info", ConnectionError("không tới được " + PKEY))
ra = chay(s.call("shopee_thong_tin_shop", {}, spec(access_token="AT-X-123456", token_het_han=str(int(time.time()) + 9999))))
check("lỗi mạng KHÔNG lộ partner key", PKEY not in ra and ra.startswith("ERROR"), ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("shopee_xoa_shop", {}, sp)).startswith("ERROR"))
check.ket_thuc()
