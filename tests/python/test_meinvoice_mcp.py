"""Cầu nối MISA meInvoice (server/meinvoice_mcp.py). Không mạng.

    python tests/run.py meinvoice_mcp

Phủ: đăng nhập lấy JWT (appid, taxcode, username, password) rồi LƯU kèm hạn đọc từ `exp`, token
còn hạn thì không đăng nhập lại, hai lượt song song chỉ đăng nhập MỘT lần, token bị thu hồi (401
hoặc TokenExpired) thì đăng nhập lại đúng một lần, môi trường thử, Bearer header, `data` dạng
chuỗi JSON được parse, kiểm mã tra cứu và giới hạn số mã, lỗi không lộ bí mật, không có tool ghi.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import json
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-meinvoice-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import meinvoice_mcp as s  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

MK = "MatKhau-MISA-24680"
APPID = "APPID-MISA-112233"
MST = "0101243150"
CON_HAN = str(int(time.time()) + 99999)
GOC = "https://api.meinvoice.vn/api/integration"


def jwt(exp):
    def b(x):
        return base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip("=")
    return f"{b({'alg': 'HS256', 'typ': 'JWT'})}.{b({'exp': exp, 'TaxCode': MST})}.chuky-gia-123"


def spec(**them):
    sec = {"app_id": APPID, "ma_so_thue": MST, "ten_dang_nhap": "ketoan@halimi.vn", "mat_khau": MK}
    sec.update(them)
    return {"key": "conn-misa-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def luu_gop():
    out = {}
    for _c, p in da_luu:
        out.update(p["fields"])
    return out


def ok_token(tok):
    return {"Success": True, "ErrorCode": None, "Errors": [], "Data": tok, "CustomData": None}


def ok_data(data):
    return {"success": True, "errorCode": None, "descriptionErrorCode": None, "errors": [], "data": data,
            "customData": ""}


# ---- 1. thiếu ô, JWT ----
check("thiếu mật khẩu -> báo rõ", "mat_khau" in chay(s.call("meinvoice_mau_hoa_don", {},
                                                          {"secrets": {"app_id": "a", "ma_so_thue": "1",
                                                                       "ten_dang_nhap": "u"}})))
check("đọc được exp trong JWT", s.han_jwt(jwt(1900000000)) == 1900000000)
check("JWT hỏng -> None", s.han_jwt("khong-phai-jwt") is None)

# ---- 2. đăng nhập rồi lưu ----
EXP = int(time.time()) + 15 * 86400
TOK = jwt(EXP)
gia = GiaHttp().lap()
gia.tra("/auth/token", ok_token(TOK))
gia.tra("/invoice/templates", ok_data(json.dumps([{"IPTemplateID": "t1", "InvSeries": "1C26TAA"}])))
sp = spec()
ra = chay(s.call("meinvoice_mau_hoa_don", {"nam": 2026, "co_ma_cqt": True}, sp))
check("đăng nhập xong lấy được mẫu", "1C26TAA" in ra, ra)
check("data dạng chuỗi JSON được parse", '"InvSeries": "1C26TAA"' in ra, ra)
dn = [g for g in gia.goi if "/auth/token" in g["url"]][0]
check("đăng nhập là POST JSON đúng URL", dn["method"] == "POST" and dn["url"] == GOC + "/auth/token")
check("đăng nhập gửi đủ 4 trường", dn["json"] == {"appid": APPID, "taxcode": MST, "username": "ketoan@halimi.vn",
                                                  "password": MK}, dn["json"])
mau = [g for g in gia.goi if "/invoice/templates" in g["url"]][0]
check("mẫu hoá đơn đúng URL, GET, Bearer", mau["method"] == "GET" and mau["url"] == GOC + "/invoice/templates"
      and mau["headers"]["Authorization"] == "Bearer " + TOK)
check("mẫu hoá đơn đúng tham số", mau["params"] == {"invoiceWithCode": "true", "ticket": "false", "year": "2026"},
      mau["params"])
luu = luu_gop()
check("token được LƯU", luu.get("access_token") == TOK)
check("hạn token lấy từ exp", luu.get("token_het_han") == str(EXP))
check("lưu đúng kết nối", all(c == "conn-misa-1" for c, _ in da_luu))
n = len([g for g in gia.goi if "/auth/token" in g["url"]])
chay(s.call("meinvoice_mau_hoa_don", {}, sp))
check("token còn hạn thì không đăng nhập lại", len([g for g in gia.goi if "/auth/token" in g["url"]]) == n)
p = gia.goi[-1]["params"]
check("năm lạ -> năm nay, cờ mặc định false", p["invoiceWithCode"] == "false" and p["ticket"] == "false"
      and 2026 <= int(p["year"]) <= 2100, p)
gia.go()

# ---- 3. hết hạn, song song chỉ một lần ----
gia = GiaHttp().lap()
TOK2 = jwt(int(time.time()) + 86400 * 10)
gia.tra("/auth/token", ok_token(TOK2))
gia.tra("/invoice/status", ok_data([{"TransactionID": "M9CKT_180J", "PublishStatus": 1}]))
sp = spec(access_token="TOKEN-CU-123456", token_het_han=str(int(time.time()) - 10))


async def hai_luot():
    return await asyncio.gather(s.call("meinvoice_trang_thai", {"ma": ["M9CKT_180J"]}, sp),
                                s.call("meinvoice_trang_thai", {"ma": "M9CKT_180J"}, sp))

r1, r2 = asyncio.run(hai_luot())
check("đăng nhập lại xong tra được trạng thái", "M9CKT_180J" in r1 and "M9CKT_180J" in r2, r1)
check("hai lượt song song chỉ đăng nhập MỘT lần", len([g for g in gia.goi if "/auth/token" in g["url"]]) == 1)
st = [g for g in gia.goi if "/invoice/status" in g["url"]][-1]
check("trạng thái là POST, body là danh sách mã", st["method"] == "POST" and st["json"] == ["M9CKT_180J"])
check("trạng thái dùng token mới", st["headers"]["Authorization"] == "Bearer " + TOK2)
check("mặc định tra theo mã tra cứu", st["params"]["inputType"] == "1" and st["params"]["invoiceCalcu"] == "false")
gia.go()

# ---- 4. token bị thu hồi -> đăng nhập lại đúng một lần ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra("/auth/token", ok_token(TOK2))
gia.tra("/invoice/publishview", {"Message": "Unauthorized"}, code=401)
gia.tra("/invoice/publishview", ok_data("https://app.meinvoice.vn/xem/abc"))
sp = spec(access_token="TOKEN-THU-HOI-1", token_het_han=CON_HAN)
ra = chay(s.call("meinvoice_link_xem", {"ma": "L4CXU6X0W0"}, sp))
check("401 -> đăng nhập lại rồi gọi lại", "app.meinvoice.vn/xem/abc" in ra, ra)
check("đăng nhập lại đúng một lần", len([g for g in gia.goi if "/auth/token" in g["url"]]) == 1)
check("gọi lại bằng token mới", gia.goi[-1]["headers"]["Authorization"] == "Bearer " + TOK2)
check("link xem đúng URL", gia.goi[-1]["url"] == GOC + "/invoice/publishview" and gia.goi[-1]["json"] == ["L4CXU6X0W0"])
gia.go()
gia = GiaHttp().lap()
gia.tra("/auth/token", ok_token(TOK2))
gia.tra("/invoice/status", {"success": False, "errorCode": "TokenExpiredCode", "errors": []})
ra = chay(s.call("meinvoice_trang_thai", {"ma": "M9CKT_180J"}, spec(access_token="TOKEN-HET-1", token_het_han=CON_HAN)))
check("TokenExpired lặp lại -> chỉ thử lại một lần rồi báo lỗi", ra.startswith("ERROR")
      and len([g for g in gia.goi if "/invoice/status" in g["url"]]) == 2, ra)
gia.go()

# ---- 5. môi trường thử, kiểm mã ----
gia = GiaHttp().lap()
gia.tra("testapi.meinvoice.vn", ok_data([]))
sp = spec(access_token="AT-OK-123456", token_het_han=CON_HAN, moi_truong="test")
chay(s.call("meinvoice_trang_thai", {"ma": "ABCD1234", "loai_ma": "ref_id", "co_ma_cqt": True,
                                     "may_tinh_tien": True}, sp))
g = gia.goi[-1]
check("môi trường test gọi testapi", g["url"] == "https://testapi.meinvoice.vn/api/integration/invoice/status")
check("tra theo refID và cờ đúng", g["params"] == {"invoiceWithCode": "true", "invoiceCalcu": "true", "inputType": "2"},
      g["params"])
n = len(gia.goi)
for ma in ("../auth/token", "ab", "x" * 65, "M9CKT 180J", "a/b/c/d"):
    check(f"chặn mã {ma[:20]!r}", chay(s.call("meinvoice_trang_thai", {"ma": ma}, sp)).startswith("ERROR"))
check("thiếu mã -> lỗi", chay(s.call("meinvoice_link_xem", {"ma": []}, sp)).startswith("ERROR"))
check("mã sai không chạm mạng", len(gia.goi) == n)
chay(s.call("meinvoice_trang_thai", {"ma": [f"MA{i:06d}" for i in range(80)]}, sp))
check("tối đa 50 mã mỗi lần", len(gia.goi[-1]["json"]) == 50)
gia.go()

# ---- 6. lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/auth/token", {"Success": False, "ErrorCode": "UnAuthorize", "Errors": [f"sai mat khau {MK}"], "Data": None})
ra = chay(s.call("meinvoice_mau_hoa_don", {}, spec()))
check("sai đăng nhập -> báo kèm gợi ý", ra.startswith("ERROR") and "UnAuthorize" in ra and "mật khẩu" in ra, ra)
check("lỗi đăng nhập KHÔNG lộ mật khẩu", MK not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/auth/token", {"Success": False, "ErrorCode": "InvalidAppID", "Errors": [APPID]})
ra = chay(s.call("meinvoice_mau_hoa_don", {}, spec()))
check("AppID sai -> gợi ý liên hệ MISA, không lộ AppID", "MISA" in ra and APPID not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/invoice/templates", {"success": False, "errorCode": "Exception", "descriptionErrorCode": "token AT-LO-777777 lỗi"})
ra = chay(s.call("meinvoice_mau_hoa_don", {}, spec(access_token="AT-LO-777777", token_het_han=CON_HAN)))
check("lỗi nghiệp vụ được báo kèm mã", ra.startswith("ERROR") and "Exception" in ra, ra)
check("lỗi nghiệp vụ KHÔNG lộ token", "AT-LO-777777" not in ra, ra)
gia.nem_loi("/invoice/templates", ConnectionError("không tới được " + MK))
ra = chay(s.call("meinvoice_mau_hoa_don", {}, spec(access_token="AT-X-123456", token_het_han=CON_HAN)))
check("lỗi mạng KHÔNG lộ mật khẩu", MK not in ra and ra.startswith("ERROR"), ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/auth/token", ok_token(""))
check("Data rỗng -> báo lỗi", chay(s.call("meinvoice_mau_hoa_don", {}, spec())).startswith("ERROR"))
gia.go()

ten = [t["name"] for t in chay(s.list_tools({}))]
check("list_tools đủ 3 tool", len(ten) == 3, ten)
check("không có tool phát hành/huỷ/gửi", not any(x in n for n in ten for x in ("phat_hanh", "huy", "gui", "publish")))
check("tool lạ -> lỗi", chay(s.call("meinvoice_huy_hoa_don", {}, spec())).startswith("ERROR"))
check.ket_thuc()
