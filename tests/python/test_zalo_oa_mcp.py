"""Cầu nối Zalo Official Account (server/zalo_oa_mcp.py). Không mạng.

    python tests/run.py zalo_oa_mcp

Phủ: link ủy quyền, đổi code lấy token (form + header secret_key) rồi LƯU và không đổi lại, làm
mới bằng refresh token DÙNG MỘT LẦN lưu CẢ HAI token mới, hai lượt song song với token hết hạn
chỉ làm mới MỘT lần, lỗi -216 làm mới rồi thử lại đúng một lần (không lặp vô hạn), tham số data=
mã hoá JSON và chặn count, kiểm tra gửi tin trước khi chạm mạng, không lộ bí mật, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
import os
import tempfile
import time
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-zalo-oa-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import zalo_oa_mcp as z  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

APP_SECRET = "zalo-app-secret-ABC123456"
AT = "zalo-access-token-0000001"
RT = "zalo-refresh-token-0000001"
OAUTH = "oauth.zaloapp.com/v4/oa/access_token"


def spec(**them):
    sec = {"app_id": "4455667788", "app_secret": APP_SECRET}
    sec.update(them)
    return {"key": "conn-zalo-oa-1", "secrets": sec}


def con_han(**them):
    return spec(access_token=AT, refresh_token=RT, token_het_han=str(int(time.time()) + 9999), **them)


def chay(c):
    return asyncio.run(c)


def luu_gop():
    ra = {}
    for _c, patch in da_luu:
        ra.update(patch["fields"])
    return ra


# ---- 1. link ủy quyền + thiếu ô ----
ra = chay(z.call("zalo_oa_lien_ket_uy_quyen", {"redirect_url": "https://minmin.vi.du/zalo"}, spec()))
u = urlparse(ra)
check("link ủy quyền đúng host/path", ra.startswith("https://oauth.zaloapp.com/v4/oa/permission?"), ra)
check("link có app_id + redirect_uri", parse_qs(u.query) == {"app_id": ["4455667788"],
                                                            "redirect_uri": ["https://minmin.vi.du/zalo"]})
check("link không lộ app_secret", APP_SECRET not in ra)
check("link đòi redirect http(s)",
      chay(z.call("zalo_oa_lien_ket_uy_quyen", {"redirect_url": "javascript:alert(1)"}, spec())).startswith("ERROR"))
check("link dùng redirect_url của kết nối",
      "redirect_uri=https" in chay(z.call("zalo_oa_lien_ket_uy_quyen", {}, spec(redirect_url="https://a.b/c"))))
check("thiếu app_secret -> báo rõ", "app_secret" in chay(z.call("zalo_oa_thong_tin", {}, {"secrets": {"app_id": "1"}})))
check("app_id không phải số -> lỗi", chay(z.call("zalo_oa_thong_tin", {}, spec(app_id="abc"))).startswith("ERROR"))
check("chưa ủy quyền -> chỉ cách", "zalo_oa_lien_ket_uy_quyen" in chay(z.call("zalo_oa_thong_tin", {}, spec())))

# ---- 2. đổi code lấy token ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra(OAUTH, {"access_token": "AT-MOI-111111", "refresh_token": "RT-MOI-111111", "expires_in": "90000"})
gia.tra("/v2.0/oa/getoa", {"error": 0, "message": "Success", "data": {"name": "HALIMI OA", "oa_id": "99"}})
sp = spec(auth_code="CODE-ZL-123", code_verifier="verifier-xyz-123456")
ra = chay(z.call("zalo_oa_thong_tin", {}, sp))
check("đổi code xong gọi được", "HALIMI OA" in ra, ra)
tk = [g for g in gia.goi if OAUTH in g["url"]][0]
check("đổi code là POST form", tk["method"] == "POST" and tk["json"] is None and isinstance(tk["data"], dict))
check("đổi code gửi grant_type + code + app_id + code_verifier",
      tk["data"] == {"grant_type": "authorization_code", "code": "CODE-ZL-123", "app_id": "4455667788",
                     "code_verifier": "verifier-xyz-123456"}, tk["data"])
check("đổi code header secret_key", tk["headers"].get("secret_key") == APP_SECRET)
api = [g for g in gia.goi if "/getoa" in g["url"]][0]
check("API header access_token", api["headers"].get("access_token") == "AT-MOI-111111", api["headers"])
check("API đúng host", api["url"] == "https://openapi.zalo.me/v2.0/oa/getoa")
luu = luu_gop()
check("lưu access + refresh mới", luu.get("access_token") == "AT-MOI-111111" and luu.get("refresh_token") == "RT-MOI-111111")
check("lưu mốc hết hạn ~25h", abs(int(luu.get("token_het_han", 0)) - (int(time.time()) + 90000)) < 60)
check("đánh dấu code đã dùng", luu.get("auth_code_da_dung") == "CODE-ZL-123")
check("lưu đúng kết nối", all(c == "conn-zalo-oa-1" for c, _ in da_luu))
chay(z.call("zalo_oa_thong_tin", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if OAUTH in g["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra(OAUTH, {"error": -14014, "error_name": "Invalid code", "error_description": "code CODE-HONG-77 invalid"})
ra = chay(z.call("zalo_oa_thong_tin", {}, spec(auth_code="CODE-HONG-77")))
check("code hỏng -> lỗi không lộ code", ra.startswith("ERROR") and "CODE-HONG-77" not in ra and "-14014" in ra, ra)
gia.go()

# ---- 3. hết hạn -> làm mới, lưu CẢ HAI, song song chỉ một lần ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra(OAUTH, {"access_token": "AT-2-222222", "refresh_token": "RT-2-222222", "expires_in": 90000})
gia.tra("/v2.0/oa/listrecentchat", {"error": 0, "data": [{"message": "chào shop"}]})
sp = spec(access_token=AT, refresh_token=RT, token_het_han=str(int(time.time()) - 10))


async def hai_luot():
    return await asyncio.gather(z.call("zalo_oa_hoi_thoai_gan_day", {}, sp),
                                z.call("zalo_oa_hoi_thoai_gan_day", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("làm mới xong đọc được", "chào shop" in r1 and "chào shop" in r2, r1)
lm = [g for g in gia.goi if OAUTH in g["url"]]
check("hai lượt song song chỉ làm mới MỘT lần", len(lm) == 1, len(lm))
check("làm mới gửi grant_type=refresh_token + refresh cũ + app_id",
      lm and lm[0]["data"] == {"grant_type": "refresh_token", "refresh_token": RT, "app_id": "4455667788"})
luu = luu_gop()
check("làm mới LƯU cả access lẫn refresh mới", luu.get("access_token") == "AT-2-222222"
      and luu.get("refresh_token") == "RT-2-222222", luu)
check("spec đang dùng cập nhật refresh mới", sp["secrets"]["refresh_token"] == "RT-2-222222")
check("cả hai lượt dùng token mới", all(g["headers"]["access_token"] == "AT-2-222222"
                                        for g in gia.goi if "listrecentchat" in g["url"]))
gia.go()

# ---- 4. -216: làm mới + thử lại đúng một lần ----
gia = GiaHttp().lap()
gia.tra("/v2.0/oa/getoa", {"error": -216, "message": "Access token is invalid"})
gia.tra("/v2.0/oa/getoa", {"error": 0, "data": {"name": "OA sau làm mới"}})
gia.tra(OAUTH, {"access_token": "AT-3-333333", "refresh_token": "RT-3-333333", "expires_in": 90000})
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("-216 -> làm mới rồi thử lại thành công", "OA sau làm mới" in ra, ra)
check("-216 -> đúng một lần làm mới", len([g for g in gia.goi if OAUTH in g["url"]]) == 1)
goi_api = [g for g in gia.goi if "getoa" in g["url"]]
check("-216 -> gọi API đúng hai lần, lần hai bằng token mới",
      len(goi_api) == 2 and goi_api[1]["headers"]["access_token"] == "AT-3-333333")
gia.go()

gia = GiaHttp().lap()
gia.tra("/v2.0/oa/getoa", {"error": -124, "message": "expired"})
gia.tra(OAUTH, {"access_token": "AT-4-444444", "refresh_token": "RT-4-444444", "expires_in": 90000})
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("vẫn lỗi token sau làm mới -> ERROR, không lặp vô hạn", ra.startswith("ERROR") and "-124" in ra, ra)
check("không lặp: 2 lần API, 1 lần làm mới",
      len([g for g in gia.goi if "getoa" in g["url"]]) == 2 and len([g for g in gia.goi if OAUTH in g["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra("/v2.0/oa/getoa", {"error": -216, "message": "invalid"})
gia.tra(OAUTH, {"error": -14020, "error_name": "Invalid refresh token " + RT})
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("-216 mà làm mới hỏng -> ERROR không lộ refresh", ra.startswith("ERROR") and RT not in ra, ra)
check("làm mới hỏng -> không thử API lần hai", len([g for g in gia.goi if "getoa" in g["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra("/v2.0/oa/getoa", {"error": -201, "message": "param invalid"})
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("lỗi khác không làm mới", ra.startswith("ERROR") and not any(OAUTH in g["url"] for g in gia.goi), ra)
gia.go()

# ---- 5. data= mã hoá JSON, chặn count ----
gia = GiaHttp().lap()
gia.tra("openapi.zalo.me", {"error": 0, "data": {}})
sp = con_han()
chay(z.call("zalo_oa_hoi_thoai_gan_day", {"count": 50, "offset": 5}, sp))
d = json.loads(gia.goi[-1]["params"]["data"])
check("recent chat: data JSON, count chặn 10", d == {"offset": 5, "count": 10}, d)
chay(z.call("zalo_oa_hoi_thoai", {"user_id": "123456789", "count": 99}, sp))
g = gia.goi[-1]
d = json.loads(g["params"]["data"])
check("conversation: path + user_id + count 10", g["url"].endswith("/v2.0/oa/conversation")
      and d == {"user_id": 123456789, "offset": 0, "count": 10}, d)
chay(z.call("zalo_oa_nguoi_quan_tam", {"count": 500, "tag_name": "VIP"}, sp))
g = gia.goi[-1]
d = json.loads(g["params"]["data"])
check("getlist: v3 + count 50 + tag + is_follower", g["url"].endswith("/v3.0/oa/user/getlist")
      and d == {"offset": 0, "count": 50, "is_follower": True, "tag_name": "VIP"}, d)
check("getlist: data là chuỗi JSON", isinstance(g["params"]["data"], str))
chay(z.call("zalo_oa_thong_tin_nguoi_dung", {"user_id": "8877"}, sp))
g = gia.goi[-1]
check("user detail: path + data", g["url"].endswith("/v3.0/oa/user/detail")
      and json.loads(g["params"]["data"]) == {"user_id": "8877"})
n = len(gia.goi)
check("conversation user_id lạ -> lỗi", chay(z.call("zalo_oa_hoi_thoai", {"user_id": "abc"}, sp)).startswith("ERROR"))
check("user detail thiếu user_id -> lỗi", chay(z.call("zalo_oa_thong_tin_nguoi_dung", {}, sp)).startswith("ERROR"))
check("tham số sai không chạm mạng", len(gia.goi) == n)
gia.go()

# ---- 6. gửi tin: kiểm tra trước khi chạm mạng ----
gia = GiaHttp().lap()
gia.tra("/v3.0/oa/message/cs", {"error": 0, "message": "Success", "data": {"message_id": "m1"}})
sp = con_han()
for ten, args in [("rỗng", {"user_id": "123", "text": ""}), ("toàn khoảng trắng", {"user_id": "123", "text": "   "}),
                  ("quá 2000", {"user_id": "123", "text": "a" * 2001}), ("thiếu text", {"user_id": "123"}),
                  ("text không phải chuỗi", {"user_id": "123", "text": 5}),
                  ("user_id chữ", {"user_id": "12a", "text": "hi"}), ("thiếu user_id", {"text": "hi"})]:
    check("gửi tin từ chối: " + ten, chay(z.call("zalo_oa_gui_tin", args, sp)).startswith("ERROR"))
check("gửi tin sai không chạm mạng", gia.goi == [])
ra = chay(z.call("zalo_oa_gui_tin", {"user_id": "123456", "text": "a" * 2000}, sp))
g = gia.goi[-1]
check("gửi tin 2000 ký tự được", "m1" in ra, ra)
check("gửi tin POST đúng body", g["method"] == "POST" and g["url"] == "https://openapi.zalo.me/v3.0/oa/message/cs"
      and g["json"] == {"recipient": {"user_id": "123456"}, "message": {"text": "a" * 2000}})
check("gửi tin header access_token", g["headers"]["access_token"] == AT)
gia.go()

# ---- 7. bí mật không lộ ----
gia = GiaHttp().lap()
gia.tra("/v2.0/oa/getoa", {"error": -32, "message": "quota " + AT + " " + APP_SECRET})
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("lỗi API không lộ token/secret", ra.startswith("ERROR") and AT not in ra and APP_SECRET not in ra, ra)
gia.nem_loi("/v2.0/oa/getoa", ConnectionError("rớt " + AT + " " + RT + " " + APP_SECRET))
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("lỗi mạng không lộ bí mật", ra.startswith("ERROR") and all(s not in ra for s in (AT, RT, APP_SECRET)), ra)
gia.nem_loi(OAUTH, TimeoutError("hết giờ " + APP_SECRET + " " + RT))
ra = chay(z.call("zalo_oa_thong_tin", {}, spec(refresh_token=RT)))
check("lỗi mạng lúc làm mới không lộ bí mật", ra.startswith("ERROR") and APP_SECRET not in ra and RT not in ra, ra)
gia.tra("/v2.0/oa/getoa", {"error": 0, "data": {"echo": AT}})
ra = chay(z.call("zalo_oa_thong_tin", {}, con_han()))
check("kết quả thành công cũng giấu token", AT not in ra, ra)
gia.go()

# ---- 8. danh sách tool, tool lạ, không gạch dài ----
ten = {x["name"] for x in chay(z.list_tools({}))}
check("đủ 7 tool", ten == {"zalo_oa_lien_ket_uy_quyen", "zalo_oa_thong_tin", "zalo_oa_hoi_thoai_gan_day",
                           "zalo_oa_hoi_thoai", "zalo_oa_nguoi_quan_tam", "zalo_oa_thong_tin_nguoi_dung",
                           "zalo_oa_gui_tin"}, ten)
check("tool lạ -> lỗi", chay(z.call("zalo_oa_xoa_oa", {}, con_han())).startswith("ERROR"))
nguon = (SERVER / "zalo_oa_mcp.py").read_text(encoding="utf-8")
check("không có gạch dài", "\u2014" not in nguon and "\u2013" not in nguon)
check.ket_thuc()
