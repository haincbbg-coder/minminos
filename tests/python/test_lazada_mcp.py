"""Cầu nối Lazada (server/lazada_mcp.py). Không mạng.

    python tests/run.py lazada_mcp

Phủ: chữ ký HMAC sha256 hex in hoa, link ủy quyền, đổi code lấy token rồi LƯU, code đã dùng
không đổi lại lần hai, token hết hạn thì tự làm mới, hai lượt làm mới song song chỉ gọi Lazada
MỘT lần, lọc trạng thái lạ, giới hạn số lượng, chặn gọi thô vào /auth, lỗi không lộ bí mật.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import os
import tempfile
import time
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-lazada-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import lazada_mcp as s  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

SECRET = "bi-mat-app-lazada-246810"
AKEY = "112233"


def spec(**them):
    sec = {"app_key": AKEY, "app_secret": SECRET}
    sec.update(them)
    return {"key": "conn-lzd-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def ky_doc_lap(path, params):
    p = {kk: v for kk, v in params.items() if kk != "sign"}
    chuoi = path + "".join(kk + str(p[kk]) for kk in sorted(p))
    return hmac.new(SECRET.encode(), chuoi.encode(), hashlib.sha256).hexdigest().upper()


CON_HAN = str(int(time.time()) + 99999)

# ---- 1. chữ ký và link ủy quyền ----
q = {"app_key": AKEY, "timestamp": "1700000000000", "sign_method": "sha256", "access_token": "AT", "limit": "10"}
check("ký đúng công thức (có access_token)", s.ky(SECRET, "/orders/get", q) == ky_doc_lap("/orders/get", q))
check("chữ ký là hex IN HOA", s.ky(SECRET, "/a", q) == s.ky(SECRET, "/a", q).upper())
url = s.lien_ket_uy_quyen(spec()["secrets"], "https://minmin.vi.du/cb")
u = parse_qs(urlparse(url).query)
check("link ủy quyền đúng host", url.startswith("https://auth.lazada.com/oauth/authorize?"))
check("link ủy quyền đủ tham số", u["client_id"] == [AKEY] and u["redirect_uri"] == ["https://minmin.vi.du/cb"]
      and u["response_type"] == ["code"] and u["force_auth"] == ["true"], u)
check("link không chứa secret", SECRET not in url)
check("tool link đòi redirect https",
      chay(s.call("lazada_lien_ket_uy_quyen", {"redirect_url": "javascript:x"}, spec())).startswith("ERROR"))
check("tool link lấy redirect_url đã lưu",
      chay(s.call("lazada_lien_ket_uy_quyen", {}, spec(redirect_url="https://a.b/cb"))).startswith(
          "https://auth.lazada.com/oauth/authorize?"))

# ---- 2. thiếu ô ----
check("thiếu app_secret -> báo rõ", "app_secret" in chay(s.call("lazada_thong_tin_shop", {},
                                                                {"secrets": {"app_key": "x"}})))
check("chưa có code/token -> chỉ cách ủy quyền",
      "lazada_lien_ket_uy_quyen" in chay(s.call("lazada_thong_tin_shop", {}, spec())))

# ---- 3. đổi code lấy token rồi lưu ----
gia = GiaHttp().lap()
gia.tra("/auth/token/create", {"code": "0", "access_token": "AT-LZD-0001", "refresh_token": "RT-LZD-0001",
                               "expires_in": 604800, "refresh_expires_in": 2592000, "country": "vn"})
gia.tra("/seller/get", {"code": "0", "data": {"name": "HALIMI Official", "seller_id": 1}, "request_id": "r1"})
sp = spec(auth_code="CODE-LZD-1")
ra = chay(s.call("lazada_thong_tin_shop", {}, sp))
check("đổi code xong gọi được API shop", "HALIMI Official" in ra, ra)
tk = [g for g in gia.goi if "token/create" in g["url"]][0]
check("đổi code là POST lên auth host", tk["method"] == "POST" and tk["url"] == "https://auth.lazada.com/rest/auth/token/create")
check("đổi code gửi form có code", tk["data"]["code"] == "CODE-LZD-1" and tk["data"]["sign_method"] == "sha256")
check("đổi code không kèm access_token", "access_token" not in tk["data"])
check("đổi code ký đúng", tk["data"]["sign"] == ky_doc_lap("/auth/token/create", tk["data"]))
check("timestamp tính bằng mili giây", len(tk["data"]["timestamp"]) == 13)
api = [g for g in gia.goi if "/seller/get" in g["url"]][0]
check("API shop gọi đúng host", api["url"] == "https://api.lazada.vn/rest/seller/get" and api["method"] == "GET")
check("API shop ký có access_token", api["params"]["access_token"] == "AT-LZD-0001"
      and api["params"]["sign"] == ky_doc_lap("/seller/get", api["params"]))
luu = {}
for _cid, patch in da_luu:
    luu.update(patch["fields"])
check("token mới được LƯU", luu.get("access_token") == "AT-LZD-0001" and luu.get("refresh_token") == "RT-LZD-0001")
check("hạn token tính từ expires_in", abs(int(luu.get("token_het_han", 0)) - (int(time.time()) + 604800)) < 60)
check("đánh dấu code đã dùng", luu.get("auth_code_da_dung") == "CODE-LZD-1")
check("lưu vào đúng kết nối", all(c == "conn-lzd-1" for c, _ in da_luu))
n_truoc = len([g for g in gia.goi if "token/create" in g["url"]])
chay(s.call("lazada_thong_tin_shop", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if "token/create" in g["url"]]) == n_truoc)
gia.go()

# ---- 4. token hết hạn -> làm mới, song song chỉ một lần ----
gia = GiaHttp().lap()
gia.tra("/auth/token/refresh", {"code": "0", "access_token": "AT-2", "refresh_token": "RT-2",
                                "expires_in": 604800, "refresh_expires_in": 2592000})
gia.tra("/orders/get", {"code": "0", "data": {"count": 1, "orders": [{"order_id": 4401}]}})
sp = spec(access_token="AT-CU", refresh_token="RT-CU", token_het_han=str(int(time.time()) - 10))


async def hai_luot():
    return await asyncio.gather(s.call("lazada_don_hang", {}, sp), s.call("lazada_don_hang", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("làm mới xong lấy được đơn", "4401" in r1 and "4401" in r2, r1)
lm = [g for g in gia.goi if "token/refresh" in g["url"]]
check("hai lượt song song chỉ làm mới MỘT lần", len(lm) == 1, len(lm))
check("làm mới gửi refresh token cũ và ký đúng", lm and lm[0]["data"]["refresh_token"] == "RT-CU"
      and lm[0]["data"]["sign"] == ky_doc_lap("/auth/token/refresh", lm[0]["data"]))
dh = [g for g in gia.goi if "/orders/get" in g["url"]][-1]["params"]
check("đơn hàng dùng token mới", dh["access_token"] == "AT-2")
check("ngày dạng ISO +07:00", dh["created_after"].endswith("+07:00") and dh["created_before"].endswith("+07:00"), dh)
check("đơn mới nhất trước", dh["sort_direction"] == "DESC")
gia.go()

# ---- 5. lọc, giới hạn ----
gia = GiaHttp().lap()
gia.tra("api.lazada.vn", {"code": "0", "data": {}})
sp = spec(access_token="AT-OK-123456", token_het_han=CON_HAN)
chay(s.call("lazada_don_hang", {"tu_ngay": "2026-01-01", "den_ngay": "2026-01-31", "trang_thai": "delivered",
                                "so_luong": 999}, sp))
p = gia.goi[-1]["params"]
check("lọc trạng thái hợp lệ được gửi", p.get("status") == "delivered")
check("limit đơn bị cắt còn 100", p["limit"] == "100")
check("khoảng ngày đúng", p["created_after"] == "2026-01-01T00:00:00+07:00"
      and p["created_before"] == "2026-01-31T23:59:59+07:00", p)
chay(s.call("lazada_don_hang", {"trang_thai": "xoa_het"}, sp))
check("trạng thái lạ bị bỏ", "status" not in gia.goi[-1]["params"])
chay(s.call("lazada_san_pham", {"loc": "lung_tung", "so_luong": 500}, sp))
p = gia.goi[-1]["params"]
check("bộ lọc sản phẩm lạ -> live", p["filter"] == "live")
check("limit sản phẩm bị cắt còn 50", p["limit"] == "50")
chay(s.call("lazada_san_pham", {"loc": "sold-out"}, sp))
check("bộ lọc sold-out được gửi", gia.goi[-1]["params"]["filter"] == "sold-out")
check("chi tiết đơn đòi mã số", chay(s.call("lazada_chi_tiet_don", {"order_id": "1;drop"}, sp)).startswith("ERROR"))
chay(s.call("lazada_chi_tiet_don", {"order_id": "4401"}, sp))
check("chi tiết đơn đúng path", gia.goi[-1]["url"].endswith("/rest/order/get") and gia.goi[-1]["params"]["order_id"] == "4401")
chay(s.call("lazada_san_pham_don", {"order_id": "4401"}, sp))
check("sản phẩm trong đơn đúng path", gia.goi[-1]["url"].endswith("/rest/order/items/get"))

# ---- 6. gọi thô ----
check("gọi thô chặn /auth", chay(s.call("lazada_goi_api", {"path": "/auth/token/create"}, sp)).startswith("ERROR"))
check("gọi thô chặn path lạ", chay(s.call("lazada_goi_api", {"path": "https://evil/x"}, sp)).startswith("ERROR"))
check("gọi thô chặn ..", chay(s.call("lazada_goi_api", {"path": "/orders/../auth"}, sp)).startswith("ERROR"))
check("gọi thô chặn ?", chay(s.call("lazada_goi_api", {"path": "/orders/get?x=1"}, sp)).startswith("ERROR"))
chay(s.call("lazada_goi_api", {"path": "/finance/transaction/details/get",
                               "params": {"trans_type": "-1", "access_token": "TOKEN-GIA", "app_key": "GIA",
                                          "sign": "GIA", "sign_method": "md5", "timestamp": "1"}}, sp))
g = gia.goi[-1]
check("gọi thô là GET", g["method"] == "GET")
check("gọi thô không cho ghi đè tham số hệ thống", g["params"]["access_token"] == "AT-OK-123456"
      and g["params"]["app_key"] == AKEY and g["params"]["sign_method"] == "sha256"
      and g["params"]["sign"] == ky_doc_lap("/finance/transaction/details/get", g["params"]))
check("gọi thô giữ tham số thường", g["params"].get("trans_type") == "-1")
gia.go()

# ---- 7. lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/seller/get", {"code": "IllegalAccessToken", "message": "token AT-LO-BI-MAT-999 invalid", "request_id": "x"})
ra = chay(s.call("lazada_thong_tin_shop", {}, spec(access_token="AT-LO-BI-MAT-999", token_het_han=CON_HAN)))
check("lỗi Lazada được báo kèm mã", ra.startswith("ERROR") and "IllegalAccessToken" in ra, ra)
check("lỗi KHÔNG lộ access token", "AT-LO-BI-MAT-999" not in ra, ra)
gia.nem_loi("/seller/get", ConnectionError("không tới được " + SECRET))
ra = chay(s.call("lazada_thong_tin_shop", {}, spec(access_token="AT-X-123456", token_het_han=CON_HAN)))
check("lỗi mạng KHÔNG lộ app secret", SECRET not in ra and ra.startswith("ERROR"), ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/auth/token/create", {"code": "InvalidCode", "message": "code CODE-BI-MAT-77 expired"})
ra = chay(s.call("lazada_thong_tin_shop", {}, spec(auth_code="CODE-BI-MAT-77")))
check("đổi code lỗi -> báo, không lộ code", ra.startswith("ERROR") and "CODE-BI-MAT-77" not in ra
      and "InvalidCode" in ra, ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("lazada_xoa_shop", {}, sp)).startswith("ERROR"))
check("list_tools đủ 7 tool", len(chay(s.list_tools({}))) == 7)
check.ket_thuc()
