"""Cầu nối Nhanh.vn v3 (server/nhanhvn_mcp.py). Không mạng.

    python tests/run.py nhanhvn_mcp

Phủ: POST JSON tới pos.open.nhanh.vn/v3.0 với appId + businessId trên query và header
Authorization không có Bearer, link ủy quyền, đổi accessCode lấy token rồi LƯU (kèm businessId,
hạn), code đã dùng không đổi lại, hai lượt song song chỉ đổi một lần, token hết hạn báo ủy quyền
lại, khoảng ngày tối đa 31 ngày, trạng thái lạ bị bỏ, size tối đa 100, trang sau gửi nguyên
paginator.next, lỗi code 0 / HTTP / mạng không lộ bí mật, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import tempfile
import time
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-nhanh-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import nhanhvn_mcp as s  # noqa: E402
import ket_noi_api as k  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

APP = "12345"
SKEY = "nhanh-secret-key-97531"
TOKEN = "NHANH-ACCESS-TOKEN-" + "x" * 40


def spec(**them):
    sec = {"app_id": APP, "business_id": "777"}
    sec.update(them)
    return {"key": "conn-nh-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


# ---- thiếu ô, link ----
check("thiếu app_id -> báo", "app_id" in chay(s.call("nhanhvn_don_hang", {}, {"secrets": {}})))
check("chưa token -> chỉ cách ủy quyền", "nhanhvn_lien_ket_uy_quyen" in chay(s.call("nhanhvn_don_hang", {}, spec())))
url = chay(s.call("nhanhvn_lien_ket_uy_quyen", {"redirect_url": "https://minmin.vi.du/cb"}, spec()))
q = parse_qs(urlparse(url).query)
check("link ủy quyền đúng", url.startswith("https://nhanh.vn/oauth?") and q["appId"] == [APP]
      and q["returnLink"] == ["https://minmin.vi.du/cb"], url)
check("link đòi redirect https", chay(s.call("nhanhvn_lien_ket_uy_quyen", {"redirect_url": "javascript:x"},
                                             spec())).startswith("ERROR"))
check("link không chứa secret", SKEY not in chay(s.call("nhanhvn_lien_ket_uy_quyen", {}, spec(
    secret_key=SKEY, redirect_url="https://a.b/cb"))))

# ---- đổi accessCode lấy token ----
gia = GiaHttp().lap()
gia.tra("/app/getaccesstoken", {"code": 1, "data": {"accessToken": TOKEN, "businessId": 888,
                                                    "expiredAt": int(time.time()) + 365 * 86400, "depotIds": []}})
gia.tra("/order/list", {"code": 1, "data": [{"info": {"id": 5501}}], "paginator": {"next": {"id": 5500}}})
sp = {"key": "conn-nh-1", "secrets": {"app_id": APP, "secret_key": SKEY, "access_code": "CODE-NH-1"}}


async def hai_luot():
    return await asyncio.gather(s.call("nhanhvn_don_hang", {}, sp), s.call("nhanhvn_don_hang", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("đổi code xong lấy được đơn", "5501" in r1 and "5501" in r2, r1)
tk = [g for g in gia.goi if "getaccesstoken" in g["url"]]
check("hai lượt song song chỉ đổi code MỘT lần", len(tk) == 1, len(tk))
check("đổi code POST JSON đúng URL", tk[0]["method"] == "POST" and tk[0]["url"] == "https://pos.open.nhanh.vn/v3.0/app/getaccesstoken"
      and tk[0]["params"] == {"appId": APP} and tk[0]["json"] == {"accessCode": "CODE-NH-1", "secretKey": SKEY})
luu = {}
for _c, patch in da_luu:
    luu.update(patch["fields"])
check("token, businessId, hạn được LƯU", luu.get("access_token") == TOKEN and luu.get("business_id") == "888"
      and luu.get("access_code_da_dung") == "CODE-NH-1" and luu.get("token_het_han"))
dh = [g for g in gia.goi if "/order/list" in g["url"]][0]
check("API đúng host + query", dh["url"] == "https://pos.open.nhanh.vn/v3.0/order/list"
      and dh["params"] == {"appId": APP, "businessId": "888"}, dh["params"])
check("header Authorization KHÔNG có Bearer", dh["headers"].get("Authorization") == TOKEN)
check("là POST JSON", dh["method"] == "POST" and isinstance(dh["json"], dict))
n = len(tk)
chay(s.call("nhanhvn_don_hang", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if "getaccesstoken" in g["url"]]) == n)
gia.go()

# ---- token hết hạn ----
ra = chay(s.call("nhanhvn_kho", {}, spec(access_token=TOKEN, token_het_han=str(int(time.time()) - 10))))
check("token hết hạn -> báo ủy quyền lại", ra.startswith("ERROR") and "nhanhvn_lien_ket_uy_quyen" in ra, ra)
ra = chay(s.call("nhanhvn_kho", {}, {"secrets": {"app_id": APP, "access_token": TOKEN}}))
check("thiếu business_id -> báo", ra.startswith("ERROR") and "business_id" in ra, ra)

# ---- tham số ----
gia = GiaHttp().lap()
gia.tra("pos.open.nhanh.vn", {"code": 1, "data": []})
sp = spec(access_token=TOKEN)
chay(s.call("nhanhvn_don_hang", {"tu_ngay": "2026-01-01", "den_ngay": "2026-03-31", "trang_thai": "60, 63, 99, x",
                                 "kho": "3,y", "so_luong": 999}, sp))
b = gia.goi[-1]["json"]
f = b["filters"]
check("khoảng ngày cắt còn 31 ngày", f["createdAtTo"] - f["createdAtFrom"] <= 31 * 86400
      and f["createdAtTo"] == k.ngay_sang_ts("2026-03-31", cuoi_ngay=True), f)
check("trạng thái chỉ giữ mã hợp lệ", f["statuses"] == [60, 63], f)
check("kho chỉ giữ id số", f["depotIds"] == [3])
check("size cắt còn 100", b["paginator"]["size"] == 100)
nxt = {"id": 5500, "createdAt": 1767225600}
chay(s.call("nhanhvn_don_hang", {"trang_tiep": nxt}, sp))
check("trang sau gửi NGUYÊN paginator.next", gia.goi[-1]["json"]["paginator"].get("next") == nxt)
chay(s.call("nhanhvn_don_hang", {"trang_tiep": "abc"}, sp))
check("trang_tiep không phải object bị bỏ", "next" not in gia.goi[-1]["json"]["paginator"])
check("chi tiết đơn đòi số", chay(s.call("nhanhvn_chi_tiet_don", {"order_id": "1 or 1"}, sp)).startswith("ERROR"))
chay(s.call("nhanhvn_chi_tiet_don", {"order_id": "5501"}, sp))
check("chi tiết đơn lọc ids", gia.goi[-1]["url"].endswith("/order/list") and gia.goi[-1]["json"]["filters"] == {"ids": [5501]})
chay(s.call("nhanhvn_san_pham", {"tu_khoa": "váy", "trang_thai": "2,9"}, sp))
b = gia.goi[-1]["json"]
check("sản phẩm đúng path, lọc tên + trạng thái hợp lệ", gia.goi[-1]["url"].endswith("/product/list")
      and b["filters"] == {"name": "váy", "status": [2]}, b)
chay(s.call("nhanhvn_chi_tiet_san_pham", {"product_id": "123"}, sp))
check("chi tiết sản phẩm đúng path", gia.goi[-1]["url"].endswith("/product/detail")
      and gia.goi[-1]["json"] == {"filters": {"id": "123"}})
chay(s.call("nhanhvn_ton_kho", {"kho": "1,2"}, sp))
check("tồn kho đúng path", gia.goi[-1]["url"].endswith("/product/inventory")
      and gia.goi[-1]["json"]["filters"] == {"depotIds": [1, 2]})
chay(s.call("nhanhvn_khach_hang", {"so_dien_thoai": "0912345678", "loai": 7}, sp))
b = gia.goi[-1]["json"]
check("khách hàng lọc sđt, loại lạ bị bỏ", gia.goi[-1]["url"].endswith("/customer/list")
      and b["filters"] == {"mobile": "0912345678"}, b)
chay(s.call("nhanhvn_kho", {}, sp))
check("kho đúng path", gia.goi[-1]["url"].endswith("/business/depot"))
gia.go()

# ---- lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/order/list", {"code": 0, "errorCode": "ERR_INVALID_ACCESS_TOKEN", "messages": "token " + TOKEN + " sai"})
ra = chay(s.call("nhanhvn_don_hang", {}, spec(access_token=TOKEN)))
check("code 0 -> ERROR kèm errorCode", ra.startswith("ERROR") and "ERR_INVALID_ACCESS_TOKEN" in ra, ra)
check("code 0 KHÔNG lộ token", TOKEN not in ra, ra)
gia.tra("/customer/list", {"message": TOKEN}, code=500)
ra = chay(s.call("nhanhvn_khach_hang", {}, spec(access_token=TOKEN)))
check("HTTP 500 -> ERROR, không lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.nem_loi("/business/depot", ConnectionError("đứt " + TOKEN))
ra = chay(s.call("nhanhvn_kho", {}, spec(access_token=TOKEN)))
check("lỗi mạng KHÔNG lộ token", ra.startswith("ERROR") and TOKEN not in ra, ra)
gia.tra("/app/getaccesstoken", {"code": 0, "errorCode": "ERR", "messages": "secret " + SKEY + " code CODE-BI-MAT-1"})
ra = chay(s.call("nhanhvn_kho", {}, {"key": "x", "secrets": {"app_id": APP, "secret_key": SKEY,
                                                            "access_code": "CODE-BI-MAT-1"}}))
check("đổi code lỗi -> ERROR, không lộ secret/code", ra.startswith("ERROR") and SKEY not in ra
      and "CODE-BI-MAT-1" not in ra, ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("nhanhvn_xoa_don", {}, spec(access_token=TOKEN))).startswith("ERROR"))
check("list_tools đủ 8 tool", len(chay(s.list_tools({}))) == 8)
check.ket_thuc()
