"""Cầu nối KiotViet (server/kiotviet_mcp.py). Không mạng.

    python tests/run.py kiotviet_mcp

Phủ: xin token client_credentials đúng form, LƯU token kèm hạn, còn hạn thì không xin lại, hết
hạn thì xin lại, hai lượt song song chỉ xin MỘT lần, 401 thì xin token mới và thử lại đúng một
lần, header Retailer + Bearer, khoảng ngày, giới hạn trang, gọi thô có rào chắn, lỗi không lộ
bí mật, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-kiotviet-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import kiotviet_mcp as s  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

CID = "e4fe37ab-5d10-4919-bf59-d9a568456d0b"
CSEC = "01A3703244752CFF6350A801F900742179C7CCDA"
CON_HAN = str(int(time.time()) + 99999)


def spec(**them):
    sec = {"retailer": "halimi", "client_id": CID, "client_secret": CSEC}
    sec.update(them)
    return {"key": "conn-kv-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


# ---- thiếu ô ----
ra = chay(s.call("kiotviet_chi_nhanh", {}, {"secrets": {"client_id": CID}}))
check("thiếu retailer/secret -> báo", ra.startswith("ERROR") and "retailer" in ra and "client_secret" in ra, ra)

# ---- xin token lần đầu ----
gia = GiaHttp().lap()
gia.tra("id.kiotviet.vn/connect/token", {"access_token": "KV-AT-0001", "expires_in": 86400, "token_type": "Bearer"})
gia.tra("public.kiotapi.com/branches", {"total": 1, "data": [{"id": 1, "branchName": "Chi nhánh trung tâm"}]})
sp = spec()
ra = chay(s.call("kiotviet_chi_nhanh", {}, sp))
check("xin token xong lấy được chi nhánh", "Chi nhánh trung tâm" in ra, ra)
tk = [g for g in gia.goi if "connect/token" in g["url"]]
check("xin token đúng 1 lần", len(tk) == 1)
tk = tk[0]
check("xin token POST đúng URL", tk["method"] == "POST" and tk["url"] == "https://id.kiotviet.vn/connect/token")
check("form client_credentials đủ khoá", tk["data"] == {"scopes": "PublicApi.Access", "grant_type": "client_credentials",
                                                      "client_id": CID, "client_secret": CSEC}, tk["data"])
check("content-type form", tk["headers"].get("Content-Type") == "application/x-www-form-urlencoded")
api = [g for g in gia.goi if "/branches" in g["url"]][0]
check("API đúng host", api["url"] == "https://public.kiotapi.com/branches" and api["method"] == "GET")
check("header Retailer + Bearer", api["headers"].get("Retailer") == "halimi"
      and api["headers"].get("Authorization") == "Bearer KV-AT-0001")
luu = {}
for _c, patch in da_luu:
    luu.update(patch["fields"])
check("token được LƯU", luu.get("access_token") == "KV-AT-0001")
check("hạn token tính từ expires_in", abs(int(luu.get("token_het_han", 0)) - (int(time.time()) + 86400)) < 60)
check("lưu vào đúng kết nối", all(c == "conn-kv-1" for c, _ in da_luu))
chay(s.call("kiotviet_chi_nhanh", {}, sp))
check("còn hạn thì không xin lại", len([g for g in gia.goi if "connect/token" in g["url"]]) == 1)
gia.go()

# ---- hết hạn: song song chỉ xin một lần ----
gia = GiaHttp().lap()
gia.tra("connect/token", {"access_token": "KV-AT-0002", "expires_in": 86400})
gia.tra("/invoices", {"total": 1, "data": [{"id": 8801, "code": "HD000123"}]})
sp = spec(access_token="KV-AT-CU", token_het_han=str(int(time.time()) - 5))


async def hai_luot():
    return await asyncio.gather(s.call("kiotviet_hoa_don", {}, sp), s.call("kiotviet_hoa_don", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("hết hạn xin lại xong lấy được hoá đơn", "HD000123" in r1 and "HD000123" in r2, r1)
check("hai lượt song song chỉ xin token MỘT lần", len([g for g in gia.goi if "connect/token" in g["url"]]) == 1)
check("hoá đơn dùng token mới", all(g["headers"].get("Authorization") == "Bearer KV-AT-0002"
                                    for g in gia.goi if "/invoices" in g["url"]))
gia.go()

# ---- 401 -> xin token mới, thử lại đúng 1 lần ----
gia = GiaHttp().lap()
gia.tra("connect/token", {"access_token": "KV-AT-0003", "expires_in": 86400})
gia.tra("/customers", {"responseStatus": {"errorCode": "Unauthorized", "message": "token revoked"}}, code=401)
gia.tra("/customers", {"total": 1, "data": [{"name": "Chị Lan"}]})
sp = spec(access_token="KV-AT-THU-HOI", token_het_han=CON_HAN)
ra = chay(s.call("kiotviet_khach_hang", {"so_dien_thoai": "0912345678"}, sp))
check("401 -> xin token mới rồi thử lại thành công", "Chị Lan" in ra, ra)
kh = [g for g in gia.goi if "/customers" in g["url"]]
check("thử lại đúng 1 lần", len(kh) == 2)
check("lần thử lại dùng token mới", kh[-1]["headers"]["Authorization"] == "Bearer KV-AT-0003")
check("lọc số điện thoại gửi contactNumber", kh[-1]["params"].get("contactNumber") == "0912345678")
gia.go()
gia = GiaHttp().lap()
gia.tra("connect/token", {"access_token": "KV-AT-0004", "expires_in": 86400})
gia.tra("/customers", {"message": "denied"}, code=401)
ra = chay(s.call("kiotviet_khach_hang", {}, spec(access_token="KV-AT-X", token_het_han=CON_HAN)))
check("401 lặp lại -> ERROR, không lặp vô hạn", ra.startswith("ERROR")
      and len([g for g in gia.goi if "/customers" in g["url"]]) == 2, ra)
gia.go()

# ---- tham số ----
gia = GiaHttp().lap()
gia.tra("public.kiotapi.com", {"data": []})
sp = spec(access_token="KV-AT-OK", token_het_han=CON_HAN)
chay(s.call("kiotviet_hoa_don", {"tu_ngay": "2026-01-01", "den_ngay": "2026-01-31", "chi_nhanh": "1, 2, x",
                                 "so_luong": 500, "vi_tri": 200}, sp))
g = gia.goi[-1]
p = g["params"]
check("hoá đơn đúng path", g["url"] == "https://public.kiotapi.com/invoices")
check("khoảng ngày bán", p["fromPurchaseDate"] == "2026-01-01T00:00:00" and p["toPurchaseDate"] == "2026-01-31T23:59:59", p)
check("pageSize cắt còn 100, currentItem giữ", p["pageSize"] == 100 and p["currentItem"] == 200)
check("chi nhánh chỉ nhận id số", p["branchIds"] == "1,2")
check("mới nhất trước", p["orderDirection"] == "Desc")
chay(s.call("kiotviet_dat_hang", {}, sp))
check("đặt hàng đúng path", gia.goi[-1]["url"].endswith("/orders"))
chay(s.call("kiotviet_ton_kho", {"chi_nhanh": "5"}, sp))
check("tồn kho đúng path", gia.goi[-1]["url"].endswith("/productOnHands") and gia.goi[-1]["params"]["branchIds"] == "5")
chay(s.call("kiotviet_hang_hoa", {"ten": "váy"}, sp))
p = gia.goi[-1]["params"]
check("hàng hoá kèm tồn kho, lọc tên", gia.goi[-1]["url"].endswith("/products") and p["includeInventory"] == "true"
      and p["name"] == "váy")
check("chi tiết hoá đơn đòi số", chay(s.call("kiotviet_chi_tiet_hoa_don", {"invoice_id": "1/x"}, sp)).startswith("ERROR"))
chay(s.call("kiotviet_chi_tiet_hoa_don", {"invoice_id": "8801"}, sp))
check("chi tiết hoá đơn đúng path", gia.goi[-1]["url"].endswith("/invoices/8801"))

# ---- gọi thô ----
for xau in ("https://evil.com/x", "/connect/token", "/a/../b", "/a?x=1", "//evil.com", "categories"):
    check(f"gọi thô chặn {xau}", chay(s.call("kiotviet_goi_api", {"path": xau}, sp)).startswith("ERROR"))
chay(s.call("kiotviet_goi_api", {"path": "/categories", "params": {"pageSize": 10}}, sp))
g = gia.goi[-1]
check("gọi thô GET đúng host", g["method"] == "GET" and g["url"] == "https://public.kiotapi.com/categories")
check("gọi thô tham số thành chuỗi", g["params"] == {"pageSize": "10"})
gia.go()

# ---- lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("connect/token", {"error": "invalid_client " + CSEC}, code=400)
ra = chay(s.call("kiotviet_chi_nhanh", {}, spec()))
check("xin token lỗi -> ERROR, không lộ secret", ra.startswith("ERROR") and CSEC not in ra, ra)
gia.tra("connect/token", {"error": "invalid_client " + CSEC})
ra = chay(s.call("kiotviet_chi_nhanh", {}, spec()))
check("token rỗng trong 200 -> ERROR, không lộ", ra.startswith("ERROR") and CSEC not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/branches", {"responseStatus": {"errorCode": "Err", "message": "token KV-AT-BI-MAT-55 sai"}})
ra = chay(s.call("kiotviet_chi_nhanh", {}, spec(access_token="KV-AT-BI-MAT-55", token_het_han=CON_HAN)))
check("responseStatus -> ERROR, không lộ token", ra.startswith("ERROR") and "KV-AT-BI-MAT-55" not in ra, ra)
gia.nem_loi("/branches", ConnectionError("đứt " + CSEC + " KV-AT-BI-MAT-55"))
ra = chay(s.call("kiotviet_chi_nhanh", {}, spec(access_token="KV-AT-BI-MAT-55", token_het_han=CON_HAN)))
check("lỗi mạng KHÔNG lộ bí mật", ra.startswith("ERROR") and CSEC not in ra and "KV-AT-BI-MAT-55" not in ra, ra)
gia.go()

check("tool lạ -> lỗi", chay(s.call("kiotviet_xoa", {}, spec())).startswith("ERROR"))
check("list_tools đủ 8 tool", len(chay(s.list_tools({}))) == 8)
check.ket_thuc()
