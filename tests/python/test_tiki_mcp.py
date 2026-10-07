"""Cầu nối Tiki (server/tiki_mcp.py). Không mạng.

    python tests/run.py tiki_mcp

Phủ: link ủy quyền, đổi code lấy token (Basic auth, form) rồi LƯU, code đã dùng không đổi lại,
app nội bộ tự lấy token client_credentials, token hết hạn thì làm mới bằng refresh token, hai lượt
song song chỉ gọi Tiki MỘT lần, Bearer header, khoảng ngày giờ Tiki, giới hạn trang/số lượng,
chặn mã chèn path, lỗi không lộ bí mật.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import os
import tempfile
import time
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-tiki-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import tiki_mcp as s  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

SECRET = "bi-mat-app-tiki-13579bd"
CID = "3750874604017328"
BASIC = "Basic " + base64.b64encode(f"{CID}:{SECRET}".encode()).decode()
CON_HAN = str(int(time.time()) + 99999)


def spec(**them):
    sec = {"client_id": CID, "client_secret": SECRET}
    sec.update(them)
    return {"key": "conn-tiki-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def luu_gop():
    out = {}
    for _c, p in da_luu:
        out.update(p["fields"])
    return out


# ---- 1. link ủy quyền ----
url = s.lien_ket_uy_quyen(spec()["secrets"], "https://minmin.vi.du/cb")
u = parse_qs(urlparse(url).query)
check("link ủy quyền đúng host", url.startswith("https://api.tiki.vn/sc/oauth2/auth?"), url)
check("link đủ tham số", u["client_id"] == [CID] and u["redirect_uri"] == ["https://minmin.vi.du/cb"]
      and u["response_type"] == ["code"] and "order" in u["scope"][0] and "offline" in u["scope"][0], u)
check("state tối thiểu 8 ký tự", len(u["state"][0]) >= 8)
check("link không chứa secret", SECRET not in url)
check("tool link đòi redirect https",
      chay(s.call("tiki_lien_ket_uy_quyen", {"redirect_url": "javascript:x"}, spec())).startswith("ERROR"))
check("tool link lấy redirect_url đã lưu",
      chay(s.call("tiki_lien_ket_uy_quyen", {}, spec(redirect_url="https://a.b/cb"))).startswith(
          "https://api.tiki.vn/sc/oauth2/auth?"))

# ---- 2. thiếu ô ----
check("thiếu client_secret -> báo rõ", "client_secret" in chay(s.call("tiki_thong_tin_shop", {},
                                                                     {"secrets": {"client_id": "x"}})))

# ---- 3. đổi code lấy token rồi lưu ----
gia = GiaHttp().lap()
gia.tra("/sc/oauth2/token", {"access_token": "AT-TIKI-0001", "refresh_token": "RT-TIKI-0001",
                             "expires_in": 3599, "scope": "offline order product", "token_type": "bearer"})
gia.tra("/integration/v2/sellers/me", {"id": 99, "name": "HALIMI Tiki", "active": 1})
sp = spec(auth_code="CODE-TIKI-1", redirect_url="https://minmin.vi.du/cb")
ra = chay(s.call("tiki_thong_tin_shop", {}, sp))
check("đổi code xong gọi được API nhà bán", "HALIMI Tiki" in ra, ra)
tk = [g for g in gia.goi if "oauth2/token" in g["url"]][0]
check("đổi code là POST lên token URL", tk["method"] == "POST" and tk["url"] == "https://api.tiki.vn/sc/oauth2/token")
check("đổi code dùng Basic client_id:secret", tk["headers"].get("Authorization") == BASIC)
check("đổi code gửi form đúng", tk["data"]["grant_type"] == "authorization_code" and tk["data"]["code"] == "CODE-TIKI-1"
      and tk["data"]["redirect_uri"] == "https://minmin.vi.du/cb" and tk["data"]["client_id"] == CID, tk["data"])
check("form token không chứa secret trần", SECRET not in str(tk["data"]))
api = [g for g in gia.goi if "/sellers/me" in g["url"]][0]
check("API nhà bán đúng URL và Bearer", api["url"] == "https://api.tiki.vn/integration/v2/sellers/me"
      and api["headers"]["Authorization"] == "Bearer AT-TIKI-0001")
luu = luu_gop()
check("token mới được LƯU", luu.get("access_token") == "AT-TIKI-0001" and luu.get("refresh_token") == "RT-TIKI-0001")
check("hạn token tính từ expires_in", abs(int(luu.get("token_het_han", 0)) - (int(time.time()) + 3599)) < 60)
check("đánh dấu code đã dùng", luu.get("auth_code_da_dung") == "CODE-TIKI-1")
check("lưu vào đúng kết nối", all(c == "conn-tiki-1" for c, _ in da_luu))
n = len([g for g in gia.goi if "oauth2/token" in g["url"]])
chay(s.call("tiki_thong_tin_shop", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if "oauth2/token" in g["url"]]) == n)
check("code thiếu redirect_uri -> báo, không gọi mạng",
      chay(s.call("tiki_thong_tin_shop", {}, spec(auth_code="CODE-X"))).startswith("ERROR"))
gia.go()

# ---- 4. app nội bộ: client_credentials, song song chỉ một lần ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra("/sc/oauth2/token", {"access_token": "AT-CC-1", "expires_in": 3600, "scope": "order"})
gia.tra("/integration/v2/orders", {"data": [{"code": "303886378"}], "paging": {"page": 1, "limit": 20, "total": 1}})
sp = spec()


async def hai_luot(tool, sp_):
    return await asyncio.gather(s.call(tool, {}, sp_), s.call(tool, {}, sp_))

r1, r2 = asyncio.run(hai_luot("tiki_don_hang", sp))
check("client_credentials lấy được đơn", "303886378" in r1 and "303886378" in r2, r1)
cc = [g for g in gia.goi if "oauth2/token" in g["url"]]
check("hai lượt song song chỉ xin token MỘT lần", len(cc) == 1, len(cc))
check("xin token client_credentials", cc and cc[0]["data"]["grant_type"] == "client_credentials"
      and cc[0]["headers"]["Authorization"] == BASIC)
check("client_credentials không lưu refresh token", "refresh_token" not in luu_gop())
gia.go()

# ---- 5. hết hạn -> refresh, song song chỉ một lần ----
gia = GiaHttp().lap()
gia.tra("/sc/oauth2/token", {"access_token": "AT-2", "refresh_token": "RT-2", "expires_in": 3600})
gia.tra("/integration/v2/orders", {"data": [{"code": "4401"}], "paging": {}})
sp = spec(access_token="AT-CU", refresh_token="RT-CU", token_het_han=str(int(time.time()) - 10))
r1, r2 = asyncio.run(hai_luot("tiki_don_hang", sp))
check("làm mới xong lấy được đơn", "4401" in r1 and "4401" in r2, r1)
lm = [g for g in gia.goi if "oauth2/token" in g["url"]]
check("hai lượt song song chỉ làm mới MỘT lần", len(lm) == 1, len(lm))
check("làm mới gửi refresh token cũ", lm and lm[0]["data"]["grant_type"] == "refresh_token"
      and lm[0]["data"]["refresh_token"] == "RT-CU")
dh = [g for g in gia.goi if "/v2/orders" in g["url"]][-1]
check("đơn hàng dùng token mới", dh["headers"]["Authorization"] == "Bearer AT-2")
check("ngày dạng yyyy-MM-dd HH:mm:ss", len(dh["params"]["created_from_date"]) == 19
      and dh["params"]["created_from_date"][10] == " ", dh["params"])
check("mới nhất trước", dh["params"]["order_by"] == "created_at|desc")
gia.go()

# ---- 6. lọc, giới hạn, chặn chèn path ----
gia = GiaHttp().lap()
gia.tra("api.tiki.vn/integration", {"data": [], "paging": {}})
sp = spec(access_token="AT-OK-123456", token_het_han=CON_HAN)
chay(s.call("tiki_don_hang", {"tu_ngay": "2026-01-01", "den_ngay": "2026-01-31", "trang_thai": "queueing, canceled",
                              "so_luong": 999, "trang": 0, "ma_don": "303886378,abc;x"}, sp))
p = gia.goi[-1]["params"]
check("khoảng ngày đúng giờ Tiki", p["created_from_date"] == "2026-01-01 00:00:00"
      and p["created_to_date"] == "2026-01-31 23:59:59", p)
check("trạng thái thành set expression", p.get("status") == "in|queueing,canceled", p.get("status"))
check("limit đơn bị cắt còn 100", p["limit"] == "100")
check("trang tối thiểu 1", p["page"] == "1")
check("mã đơn lạ bị bỏ", p.get("code") == "303886378")
chay(s.call("tiki_don_hang", {"tu_ngay": "2025-01-01", "den_ngay": "2026-01-31", "trang_thai": "x|y"}, sp))
p = gia.goi[-1]["params"]
check("khoảng ngày bị cắt còn 90 ngày", p["created_from_date"] == "2025-11-02 23:59:59", p["created_from_date"])
check("trạng thái chứa ký tự lạ bị bỏ", "status" not in p)
chay(s.call("tiki_san_pham", {"so_luong": 500, "dang_ban": False, "kem_ton_kho": True, "tu_khoa": "váy"}, sp))
g = gia.goi[-1]
check("sản phẩm gọi v2.1", g["url"] == "https://api.tiki.vn/integration/v2.1/products")
check("limit sản phẩm bị cắt còn 50", g["params"]["limit"] == "50")
check("lọc đang tắt và kèm tồn kho", g["params"]["active"] == "0" and g["params"]["include"] == "inventory"
      and g["params"]["name"] == "váy")
chay(s.call("tiki_san_pham", {}, sp))
check("không lọc active khi không hỏi", "active" not in gia.goi[-1]["params"])
n = len(gia.goi)
for ma in ("../sellers/me", "1;drop", "12/../../x", "", "abc"):
    check(f"chi tiết đơn chặn mã {ma!r}", chay(s.call("tiki_chi_tiet_don", {"ma_don": ma}, sp)).startswith("ERROR"))
    check(f"chi tiết SP chặn mã {ma!r}", chay(s.call("tiki_chi_tiet_san_pham", {"product_id": ma}, sp)).startswith("ERROR"))
check("mã sai không chạm mạng", len(gia.goi) == n)
chay(s.call("tiki_chi_tiet_don", {"ma_don": "303886378"}, sp))
g = gia.goi[-1]
check("chi tiết đơn đúng path", g["url"] == "https://api.tiki.vn/integration/v2/orders/303886378"
      and "status_histories" in g["params"]["include"])
chay(s.call("tiki_chi_tiet_san_pham", {"product_id": "12345678"}, sp))
check("chi tiết SP đúng path", gia.goi[-1]["url"] == "https://api.tiki.vn/integration/v2.1/products/12345678")
chay(s.call("tiki_kho_hang", {}, sp))
check("kho hàng đúng path", gia.goi[-1]["url"] == "https://api.tiki.vn/integration/v2/sellers/me/warehouses")
chay(s.call("tiki_ton_kho_kho_tiki", {"ma_kho": "SGN,hn4,../x"}, sp))
g = gia.goi[-1]
check("tồn kho kho Tiki lọc mã kho hợp lệ", g["url"].endswith("/v2/seller-inventories")
      and g["params"].get("tiki_warehouse_codes") == "sgn,hn4", g["params"])
gia.go()

# ---- 7. lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/sellers/me", {"errors": ["token AT-LO-BI-MAT-999 invalid"]}, code=401)
ra = chay(s.call("tiki_thong_tin_shop", {}, spec(access_token="AT-LO-BI-MAT-999", token_het_han=CON_HAN)))
check("lỗi 401 được báo", ra.startswith("ERROR") and "401" in ra, ra)
check("lỗi KHÔNG lộ access token", "AT-LO-BI-MAT-999" not in ra, ra)
gia.nem_loi("/sellers/me", ConnectionError("không tới được " + SECRET))
ra = chay(s.call("tiki_thong_tin_shop", {}, spec(access_token="AT-X-123456", token_het_han=CON_HAN)))
check("lỗi mạng KHÔNG lộ client secret", SECRET not in ra and ra.startswith("ERROR"), ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/sc/oauth2/token", {"error": "invalid_grant", "error_description": "code CODE-BI-MAT-77 expired"}, code=400)
ra = chay(s.call("tiki_thong_tin_shop", {}, spec(auth_code="CODE-BI-MAT-77", redirect_url="https://a.b/cb")))
check("đổi code lỗi -> báo, không lộ code", ra.startswith("ERROR") and "CODE-BI-MAT-77" not in ra
      and "invalid_grant" in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/sc/oauth2/token", {"scope": "order"})
ra = chay(s.call("tiki_thong_tin_shop", {}, spec()))
check("token thiếu access_token -> báo lỗi", ra.startswith("ERROR"), ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/sc/oauth2/token", {"access_token": "AT-Z-123456", "expires_in": 3600})
gia.tra("/sellers/me", {"errors": ["seller not found"]})
ra = chay(s.call("tiki_thong_tin_shop", {}, spec()))
check("200 kèm errors -> báo lỗi", ra.startswith("ERROR") and "seller not found" in ra, ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("tiki_xoa_shop", {}, sp)).startswith("ERROR"))
check("list_tools đủ 8 tool", len(chay(s.list_tools({}))) == 8)
check.ket_thuc()
