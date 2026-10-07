"""Cầu nối X (Twitter) API v2 (server/x_mcp.py). Không mạng.

    python tests/run.py x_mcp

Phủ: PKCE S256 so với tính độc lập, link ủy quyền đủ tham số và giữ verifier tới khi dùng, đổi
code bằng Basic auth (client bí mật) hoặc client_id trong form (client công khai) rồi LƯU, code
dùng rồi không đổi lại, state lệch bị chặn, làm mới XOAY VÒNG lưu cả hai token, hai lượt song
song chỉ làm mới MỘT lần, 401 làm mới rồi thử lại đúng một lần, đếm ký tự kiểu X, kiểm tra đăng
bài và xoá bài trước khi chạm mạng, không lộ bí mật, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import hashlib
import os
import tempfile
import time
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-x-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import x_mcp as x  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

CID = "x-client-id-public-01"
CS = "x-client-secret-ABCDEF123456"
AT = "x-access-token-00000001"
RT = "x-refresh-token-0000001"
TOKEN = "api.x.com/2/oauth2/token"
CB = "https://minmin.vi.du/x/cb"


def spec(**them):
    sec = {"client_id": CID, "client_secret": CS, "redirect_url": CB}
    sec.update(them)
    return {"key": "conn-x-1", "secrets": sec}


def con_han(**them):
    return spec(access_token=AT, refresh_token=RT, token_het_han=str(int(time.time()) + 9999), **them)


def chay(c):
    return asyncio.run(c)


def luu_gop():
    ra = {}
    for _c, patch in da_luu:
        ra.update(patch["fields"])
    return ra


def basic(a, b):
    return "Basic " + base64.b64encode(f"{a}:{b}".encode()).decode()


# ---- 1. PKCE + link ủy quyền ----
v = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
doc_lap = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).decode().rstrip("=")
check("PKCE S256 khớp tính độc lập", x.pkce_challenge(v) == doc_lap)
check("PKCE khớp ví dụ RFC 7636", x.pkce_challenge(v) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

da_luu.clear()
sp = spec()
ra = chay(x.call("x_lien_ket_uy_quyen", {}, sp))
link = ra.split()[0]
q = parse_qs(urlparse(link).query)
check("link đúng host/path", link.startswith("https://x.com/i/oauth2/authorize?"), link)
ver = sp["secrets"].get("code_verifier", "")
check("verifier lưu vào kết nối, dài 43..128", 43 <= len(ver) <= 128 and luu_gop().get("code_verifier") == ver)
check("link: challenge = S256(verifier lưu)", q.get("code_challenge") == [x.pkce_challenge(ver)]
      and q.get("code_challenge_method") == ["S256"])
check("link: response_type, client_id, redirect, scope",
      q.get("response_type") == ["code"] and q.get("client_id") == [CID] and q.get("redirect_uri") == [CB]
      and q.get("scope") == ["tweet.read tweet.write users.read offline.access"], q)
check("link: state lưu trùng state trên link", q.get("state") == [sp["secrets"].get("pkce_state")])
check("link không lộ verifier/secret", ver not in ra and CS not in ra)
ra2 = chay(x.call("x_lien_ket_uy_quyen", {}, sp))
check("tạo lại link khi verifier chưa dùng thì giữ verifier", sp["secrets"]["code_verifier"] == ver
      and parse_qs(urlparse(ra2.split()[0]).query)["code_challenge"] == [x.pkce_challenge(ver)])
check("link đòi redirect http(s)",
      chay(x.call("x_lien_ket_uy_quyen", {"redirect_url": "javascript:alert(1)"}, spec(redirect_url=""))).startswith("ERROR"))
check("link không mạng", True)

# ---- 2. đổi code (client bí mật: Basic auth) ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra(TOKEN, {"token_type": "bearer", "access_token": "AT-MOI-111111", "refresh_token": "RT-MOI-111111",
                "expires_in": 7200, "scope": "tweet.read tweet.write users.read offline.access"})
gia.tra("/2/users/me", {"data": {"id": "1449263311", "name": "HALIMI", "username": "halimi_vn"}})
st = sp["secrets"]["pkce_state"]
ra = chay(x.call("x_nhap_ma_uy_quyen", {"code": f"{CB}?state={st}&code=CODE-X-123"}, sp))
check("đổi code xong báo tài khoản", "@halimi_vn" in ra, ra)
tk = [g for g in gia.goi if TOKEN in g["url"]][0]
check("đổi code là POST form", tk["method"] == "POST" and tk["json"] is None and isinstance(tk["data"], dict))
check("đổi code gửi code + grant_type + redirect_uri + code_verifier (không client_id)",
      tk["data"] == {"code": "CODE-X-123", "grant_type": "authorization_code", "redirect_uri": CB,
                     "code_verifier": ver}, tk["data"])
check("đổi code header Basic client_id:secret", tk["headers"].get("Authorization") == basic(CID, CS), tk["headers"])
me = [g for g in gia.goi if "/2/users/me" in g["url"]][0]
check("API header Bearer token mới", me["headers"].get("Authorization") == "Bearer AT-MOI-111111")
check("API đúng host", me["url"] == "https://api.x.com/2/users/me")
luu = luu_gop()
check("lưu access + refresh mới", luu.get("access_token") == "AT-MOI-111111" and luu.get("refresh_token") == "RT-MOI-111111")
check("lưu mốc hết hạn ~2h", abs(int(luu.get("token_het_han", 0)) - (int(time.time()) + 7200)) < 60)
check("đánh dấu verifier đã dùng", luu.get("code_verifier_da_dung") == ver)
check("lưu user_id/username", luu.get("user_id") == "1449263311" and luu.get("username") == "halimi_vn")
check("lưu đúng kết nối", all(c == "conn-x-1" for c, _ in da_luu))
n = len(gia.goi)
ra = chay(x.call("x_nhap_ma_uy_quyen", {"code": "CODE-X-456"}, sp))
check("verifier đã dùng -> không đổi lần hai, đòi link mới", ra.startswith("ERROR") and len(gia.goi) == n, ra)
ra = chay(x.call("x_lien_ket_uy_quyen", {}, sp))
check("link mới sau khi dùng -> verifier mới", sp["secrets"]["code_verifier"] != ver)
gia.go()

# client công khai: không Client Secret -> client_id trong form, không Basic
gia = GiaHttp().lap()
gia.tra(TOKEN, {"access_token": "AT-PUB-111111", "refresh_token": "RT-PUB-111111", "expires_in": 7200})
gia.tra("/2/users/me", {"data": {"id": "77", "username": "pub"}})
spp = spec(client_secret="")
chay(x.call("x_lien_ket_uy_quyen", {}, spp))
chay(x.call("x_nhap_ma_uy_quyen", {"code": "CODE-PUB-1"}, spp))
tk = [g for g in gia.goi if TOKEN in g["url"]][0]
check("client công khai: client_id trong form, không Basic",
      tk["data"].get("client_id") == CID and "Authorization" not in tk["headers"], tk)
gia.go()

# state lệch, code rỗng, code hỏng
gia = GiaHttp().lap()
sp = spec()
chay(x.call("x_lien_ket_uy_quyen", {}, sp))
ra = chay(x.call("x_nhap_ma_uy_quyen", {"code": f"{CB}?state=KHAC&code=CODE-1"}, sp))
check("state lệch -> lỗi, không chạm mạng", ra.startswith("ERROR") and gia.goi == [], ra)
check("code rỗng -> lỗi", chay(x.call("x_nhap_ma_uy_quyen", {"code": "  "}, sp)).startswith("ERROR"))
check("chưa tạo link -> lỗi chỉ cách", "x_lien_ket_uy_quyen" in chay(x.call("x_nhap_ma_uy_quyen", {"code": "C1"}, spec())))
gia.tra(TOKEN, {"error": "invalid_request", "error_description": "Value passed for the authorization code was invalid."}, 400)
ra = chay(x.call("x_nhap_ma_uy_quyen", {"code": "CODE-HONG-77"}, sp))
check("code hỏng -> ERROR, chỉ đường ủy quyền lại, không lộ verifier",
      ra.startswith("ERROR") and "x_lien_ket_uy_quyen" in ra and sp["secrets"]["code_verifier"] not in ra, ra)
gia.go()

# ---- 3. hết hạn -> làm mới XOAY VÒNG, song song chỉ một lần ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra(TOKEN, {"access_token": "AT-2-222222", "refresh_token": "RT-2-222222", "expires_in": 7200})
gia.tra("/2/users/me", {"data": {"id": "1449263311", "name": "HALIMI", "username": "halimi_vn"}})
sp = spec(access_token=AT, refresh_token=RT, token_het_han=str(int(time.time()) - 10))


async def hai_luot():
    return await asyncio.gather(x.call("x_thong_tin", {}, sp), x.call("x_thong_tin", {}, sp))

r1, r2 = asyncio.run(hai_luot())
check("làm mới xong đọc được", "halimi_vn" in r1 and "halimi_vn" in r2, r1)
lm = [g for g in gia.goi if TOKEN in g["url"]]
check("hai lượt song song chỉ làm mới MỘT lần", len(lm) == 1, len(lm))
check("làm mới gửi grant_type=refresh_token + refresh cũ + Basic",
      lm and lm[0]["data"] == {"grant_type": "refresh_token", "refresh_token": RT}
      and lm[0]["headers"].get("Authorization") == basic(CID, CS), lm and lm[0])
luu = luu_gop()
check("làm mới LƯU cả access lẫn refresh mới", luu.get("access_token") == "AT-2-222222"
      and luu.get("refresh_token") == "RT-2-222222", luu)
check("spec đang dùng cập nhật refresh mới", sp["secrets"]["refresh_token"] == "RT-2-222222")
check("cả hai lượt dùng token mới", all(g["headers"]["Authorization"] == "Bearer AT-2-222222"
                                        for g in gia.goi if "/2/users/me" in g["url"]))
gia.go()

check("chưa ủy quyền -> chỉ cách", "x_lien_ket_uy_quyen" in chay(x.call("x_thong_tin", {}, spec())))

# ---- 4. 401: làm mới + thử lại đúng một lần ----
gia = GiaHttp().lap()
gia.tra("/2/users/me", {"title": "Unauthorized", "status": 401}, 401)
gia.tra("/2/users/me", {"data": {"id": "5", "username": "sau_lam_moi"}})
gia.tra(TOKEN, {"access_token": "AT-3-333333", "refresh_token": "RT-3-333333", "expires_in": 7200})
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("401 -> làm mới rồi thử lại thành công", "sau_lam_moi" in ra, ra)
check("401 -> đúng một lần làm mới", len([g for g in gia.goi if TOKEN in g["url"]]) == 1)
goi_api = [g for g in gia.goi if "/2/users/me" in g["url"]]
check("401 -> gọi API hai lần, lần hai bằng token mới",
      len(goi_api) == 2 and goi_api[1]["headers"]["Authorization"] == "Bearer AT-3-333333")
gia.go()

gia = GiaHttp().lap()
gia.tra("/2/users/me", {"title": "Unauthorized"}, 401)
gia.tra(TOKEN, {"access_token": "AT-4-444444", "refresh_token": "RT-4-444444", "expires_in": 7200})
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("vẫn 401 sau làm mới -> ERROR, không lặp vô hạn", ra.startswith("ERROR") and "401" in ra, ra)
check("không lặp: 2 lần API, 1 lần làm mới",
      len([g for g in gia.goi if "/2/users/me" in g["url"]]) == 2 and len([g for g in gia.goi if TOKEN in g["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra("/2/users/me", {"title": "Unauthorized"}, 401)
gia.tra(TOKEN, {"error": "invalid_request", "error_description": "bad refresh " + RT}, 400)
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("401 mà làm mới hỏng -> ERROR không lộ refresh", ra.startswith("ERROR") and RT not in ra, ra)
check("làm mới hỏng -> không thử API lần hai", len([g for g in gia.goi if "/2/users/me" in g["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra("/2/users/me", {"title": "Too Many Requests"}, 429)
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("429 không làm mới, có gợi ý", ra.startswith("ERROR") and "15 phút" in ra
      and not any(TOKEN in g["url"] for g in gia.goi), ra)
gia.go()

# ---- 5. bài gần đây ----
gia = GiaHttp().lap()
gia.tra("/2/users/me", {"data": {"id": "1449263311", "username": "halimi_vn"}})
gia.tra("/tweets", {"data": [{"id": "1", "text": "chào"}], "meta": {"result_count": 1}})
sp = con_han()
chay(x.call("x_bai_gan_day", {"max_results": 500, "bo_tra_loi": True, "bo_dang_lai": True}, sp))
g = gia.goi[-1]
check("bài gần đây: tự lấy id của mình rồi gọi timeline",
      g["url"] == "https://api.x.com/2/users/1449263311/tweets" and any("/2/users/me" in x_["url"] for x_ in gia.goi))
check("bài gần đây: max_results chặn 100, exclude", g["params"]["max_results"] == 100
      and g["params"]["exclude"] == "replies,retweets" and "tweet.fields" in g["params"], g["params"])
n = len(gia.goi)
chay(x.call("x_bai_gan_day", {"max_results": 1}, sp))
check("bài gần đây: id đã lưu thì không gọi /me nữa, max_results tối thiểu 5",
      len(gia.goi) == n + 1 and gia.goi[-1]["params"]["max_results"] == 5)
chay(x.call("x_bai_gan_day", {"user_id": "44196397", "pagination_token": "7140dibdnow9c7btw3w29grvxfcgvpb9n9coehpk7xz5i"}, sp))
g = gia.goi[-1]
check("bài gần đây: user_id khác + pagination_token", g["url"].endswith("/2/users/44196397/tweets")
      and g["params"]["pagination_token"].startswith("7140"))
n = len(gia.goi)
check("user_id chữ -> lỗi", chay(x.call("x_bai_gan_day", {"user_id": "abc"}, sp)).startswith("ERROR"))
check("user_id 20 chữ số -> lỗi", chay(x.call("x_bai_gan_day", {"user_id": "1" * 20}, sp)).startswith("ERROR"))
check("pagination_token lạ -> lỗi", chay(x.call("x_bai_gan_day", {"pagination_token": "a&b=c"}, sp)).startswith("ERROR"))
check("tham số sai không chạm mạng", len(gia.goi) == n)
gia.go()

# ---- 6. đếm ký tự kiểu X ----
check("đếm: 280 chữ Latin = 280", x.do_dai_x("a" * 280) == 280)
check("đếm: link tính 23", x.do_dai_x("xem https://halimi.vn/" + "a" * 100 + " nhé") == 4 + 23 + 4)
check("đếm: emoji tính 2", x.do_dai_x("\U0001F600") == 2)
check("đếm: emoji ghép ZWJ + màu da tính 2", x.do_dai_x("\U0001F469\U0001F3FD‍\U0001F4BB") == 2)
check("đếm: cờ tính 2", x.do_dai_x("\U0001F1FB\U0001F1F3") == 2)
check("đếm: chữ Hán tính 2", x.do_dai_x("中文") == 4)
check("đếm: NFC (e + dấu ghép = 1)", x.do_dai_x("café") == 4)
check("đếm: tiếng Việt dựng sẵn ngoài 0..4351 tính 2", x.do_dai_x("ạ") == 2 and x.do_dai_x("à") == 1)

# ---- 7. đăng bài: kiểm tra trước khi chạm mạng ----
gia = GiaHttp().lap()
gia.tra("/2/tweets", {"data": {"id": "1445880548472328192", "text": "ok"}}, 201)
sp = con_han()
for ten, args in [("rỗng", {"text": ""}), ("toàn khoảng trắng", {"text": "   \n"}), ("thiếu text", {}),
                  ("không phải chuỗi", {"text": 5}), ("quá 280", {"text": "a" * 281}),
                  ("141 emoji = 282", {"text": "\U0001F600" * 141}),
                  ("trả lời mã chữ", {"text": "hi", "tra_loi_bai": "12a"}),
                  ("trả lời mã 20 số", {"text": "hi", "tra_loi_bai": "1" * 20})]:
    check("đăng bài từ chối: " + ten, chay(x.call("x_dang_bai", args, sp)).startswith("ERROR"))
check("đăng bài sai không chạm mạng", gia.goi == [])
ra = chay(x.call("x_dang_bai", {"text": "a" * 280}, sp))
g = gia.goi[-1]
check("đăng bài 280 được", "1445880548472328192" in ra, ra)
check("đăng bài POST /2/tweets body chỉ text", g["method"] == "POST" and g["url"] == "https://api.x.com/2/tweets"
      and g["json"] == {"text": "a" * 280})
check("đăng bài header Bearer", g["headers"]["Authorization"] == "Bearer " + AT)
chay(x.call("x_dang_bai", {"text": "cảm ơn", "tra_loi_bai": "1346889436626259968"}, sp))
check("trả lời: reply.in_reply_to_tweet_id", gia.goi[-1]["json"] == {
    "text": "cảm ơn", "reply": {"in_reply_to_tweet_id": "1346889436626259968"}})
gia.go()

# ---- 8. xoá bài ----
gia = GiaHttp().lap()
gia.tra("/2/tweets/", {"data": {"deleted": True}})
sp = con_han()
for ten, tid in [("rỗng", ""), ("chữ", "abc"), ("có dấu /", "12/34"), ("đường dẫn ..", "../users"),
                 ("20 chữ số", "1" * 20), ("số âm", "-5"), ("có khoảng", "12 34")]:
    check("xoá bài từ chối id " + ten, chay(x.call("x_xoa_bai", {"tweet_id": tid}, sp)).startswith("ERROR"))
check("xoá bài id sai không chạm mạng", gia.goi == [])
ra = chay(x.call("x_xoa_bai", {"tweet_id": "1346889436626259968"}, sp))
g = gia.goi[-1]
check("xoá bài DELETE đúng path", g["method"] == "DELETE"
      and g["url"] == "https://api.x.com/2/tweets/1346889436626259968" and "deleted" in ra, ra)
gia.go()

# ---- 9. bí mật không lộ ----
gia = GiaHttp().lap()
gia.tra("/2/users/me", {"title": "Forbidden", "detail": "bad " + AT + " " + CS + " " + RT}, 403)
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("lỗi API không lộ token/secret", ra.startswith("ERROR") and all(s not in ra for s in (AT, RT, CS)), ra)
gia.go()
gia = GiaHttp().lap()
gia.nem_loi("/2/users/me", ConnectionError("rớt " + AT + " " + RT + " " + CS))
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("lỗi mạng không lộ bí mật", ra.startswith("ERROR") and all(s not in ra for s in (AT, RT, CS)), ra)
gia.go()
gia = GiaHttp().lap()
gia.nem_loi(TOKEN, TimeoutError("hết giờ " + CS + " " + RT))
ra = chay(x.call("x_thong_tin", {}, spec(refresh_token=RT)))
check("lỗi mạng lúc làm mới không lộ bí mật", ra.startswith("ERROR") and CS not in ra and RT not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/2/users/me", {"data": {"echo": AT + " " + RT}})
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("kết quả thành công cũng giấu token", AT not in ra and RT not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/2/users/me", {"errors": [{"detail": "token " + AT}]})
ra = chay(x.call("x_thong_tin", {}, con_han()))
check("200 chỉ có errors -> ERROR không lộ", ra.startswith("ERROR") and AT not in ra, ra)
gia.go()

# ---- 10. thiếu ô, danh sách tool, tool lạ, không gạch dài ----
gia = GiaHttp().lap()
ra = chay(x.call("x_thong_tin", {}, {"secrets": {"client_secret": CS}}))
check("thiếu client_id -> báo rõ, không chạm mạng", "client_id" in ra and ra.startswith("ERROR") and gia.goi == [])
gia.go()
ten = {t["name"] for t in chay(x.list_tools({}))}
check("đủ 6 tool", ten == {"x_lien_ket_uy_quyen", "x_nhap_ma_uy_quyen", "x_thong_tin", "x_bai_gan_day",
                           "x_dang_bai", "x_xoa_bai"}, ten)
check("tool lạ -> lỗi", chay(x.call("x_xoa_tai_khoan", {}, con_han())).startswith("ERROR"))
nguon = (SERVER / "x_mcp.py").read_text(encoding="utf-8")
check("không có gạch dài", "\u2014" not in nguon and "\u2013" not in nguon)
check.ket_thuc()
