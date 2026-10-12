"""26.10.114: trạm đăng nhập Meta - đăng nhập Facebook không cần tự tạo app.

    python tests/run.py meta_tram

Máy trạm và máy người dùng giả lập chung một tiến trình (chung khoá danh tính). Không gọi
mạng thật: httpx của meta_tram được thay bằng bản giả, gọi tới trạm thì đi vào TestClient,
gọi tới Facebook thì trả số giả.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import base64
import os
import sys
import tempfile
import time
import urllib.parse

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-mt-")
os.environ["JAVIS_META_TRAM_APP_ID"] = "APP123"
os.environ["JAVIS_META_TRAM_APP_SECRET"] = "SECRET456"
os.environ["JAVIS_META_TRAM"] = "https://tram.test"
os.environ["JAVIS_META_TRAM_GOC"] = "https://tram.test"
os.environ["JAVIS_META_TRAM_LIEN_HE"] = "lien-he@vi-du.vn"

from fastapi.testclient import TestClient  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
import main  # noqa: E402
import meta_tram  # noqa: E402
import oauth_mcp  # noqa: E402
import secrets_store  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


tc = TestClient(main.app, base_url="http://localhost")
fb_goi = []


class _R:
    def __init__(self, d): self._d = d
    def json(self): return self._d


class _Fake:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def post(self, url, json=None):
        assert url.startswith("https://tram.test"), url
        return _R(tc.post(url[len("https://tram.test"):], json=json).json())

    async def get(self, url, params=None):
        params = params or {}
        if url.startswith("https://tram.test"):
            return _R(tc.get(url[len("https://tram.test"):]).json())
        fb_goi.append((url, dict(params)))
        if url == meta_tram.TOKEN_URL:
            if params.get("client_secret") != "SECRET456":
                return _R({"error": {"message": "sai secret"}})
            if params.get("grant_type") == "fb_exchange_token":
                return _R({"access_token": "LL_" + params["fb_exchange_token"], "expires_in": 5184000})
            return _R({"access_token": "SHORT_" + params.get("code", ""), "expires_in": 3600})
        if url.endswith("/me/permissions"):
            return _R({"data": [{"permission": "ads_read", "status": "granted"},
                                {"permission": "pages_manage_posts", "status": "declined"}]})
        return _R({})


class _FakeHttpx:
    AsyncClient = _Fake


meta_tram.httpx = _FakeHttpx

# ---------- mã hoá ----------
rieng, kx = meta_tram.khoa_tam()
goi = meta_tram.niem_phong({"access_token": "abc"}, kx)
check("niêm phong rồi mở được", meta_tram.mo_niem_phong(goi, rieng) == {"access_token": "abc"})
rieng2, _ = meta_tram.khoa_tam()
check("khoá khác không mở được", meta_tram.mo_niem_phong(goi, rieng2) is None)
check("gói không chứa token thô", "abc" not in str(goi))

# ---------- địa chỉ quay về ----------
for ve, dung in (("https://may.vi-du.vn/connect/oauth/callback", True),
                 ("http://localhost:7777/connect/oauth/callback", True),
                 ("http://127.0.0.1:7777/connect/oauth/callback", True),
                 ("http://may.vi-du.vn/connect/oauth/callback", False),
                 ("https://may.vi-du.vn/evil", False),
                 ("https://192.168.1.5/connect/oauth/callback", False),
                 ("https://intranet/connect/oauth/callback", False),
                 ("https://evil.vn/connect/oauth/callback?x=1", False)):
    check(f"địa chỉ quay về {'nhận' if dung else 'chặn'}: {ve}", meta_tram.ve_hop_le(ve) is dung)

# ---------- trạng thái + trang bắt buộc ----------
tt = tc.get("/mt/thong-tin").json()
check("trạm báo đang bật", tt["bat"] and "ads_read" in tt["quyen"])
check("thông tin trạm không lộ App Secret", "SECRET456" not in str(tt))
for duong in ("/mt/chinh-sach", "/mt/dieu-khoan", "/mt/xoa-du-lieu"):
    r = tc.get(duong)
    check(f"trang {duong} công khai, có CSP, song ngữ",
          r.status_code == 200 and "default-src 'none'" in r.headers.get("content-security-policy", "")
          and "English" in r.text and "lien-he@vi-du.vn" in r.text)
check("dashboard hỏi được trạm", tc.get("/connect/meta-tram").json().get("bat") is True)
check("/mt/ công khai, /connect/meta-tram thì không",
      any("/mt/x".startswith(p) for p in main._AUTH_PUBLIC_PREFIX)
      and not any("/connect/meta-tram".startswith(p) for p in main._AUTH_PUBLIC_PREFIX))

# ---------- luồng đăng nhập đầy đủ ----------
META_AUTH = {"provider": "meta", "authorize_url": "https://www.facebook.com/v26.0/dialog/oauth",
             "token_url": "https://graph.facebook.com/v26.0/oauth/access_token",
             "scopes": ["ads_read", "pages_manage_posts", "khong_cho_phep"]}
oauth_mcp._conn = lambda cid: {"id": cid, "url": "", "connector": {"auth": META_AUTH}}
oauth_mcp.mcp_store.connection_secrets = lambda cid: {}
VE = "https://may.vi-du.vn/connect/oauth/callback"


async def chay():
    res = await oauth_mcp.start_auth("cmeta", VE, qua_tram=True)
    check("mở phiên qua trạm", res.get("ok") and "/mt/xac-nhan/" in res.get("url", ""), res)
    pid = res["url"].rsplit("/", 1)[1]
    st = next(k for k, v in oauth_mcp._pending.items() if v.get("tram"))
    p = meta_tram._phien[pid]
    check("trạm lọc bỏ quyền không cho phép", p["quyen"] == ["ads_read", "pages_manage_posts"], p["quyen"])

    # kẻ khác gọi thẳng /mt/ve (không qua trang xác nhận) thì bị chặn và KHÔNG phá phiên
    r = TestClient(main.app, base_url="http://localhost").get(
        "/mt/ve", params={"state": pid, "code": "X"}, follow_redirects=False)
    check("vào /mt/ve không qua trang xác nhận: chặn", r.status_code == 400 and "xác nhận" in r.text)
    check("bị gọi bừa không làm mất phiên", pid in meta_tram._phien)

    r = tc.get(f"/mt/xac-nhan/{pid}")
    check("trang xác nhận hiện máy sẽ nhận token", r.status_code == 200 and "may.vi-du.vn" in r.text)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(
        r.text.split("href='")[1].split("'")[0].replace("&amp;", "&")).query)
    check("link Facebook đúng app, đúng chỗ quay về trạm",
          q["client_id"] == ["APP123"] and q["redirect_uri"] == ["https://tram.test/mt/ve"] and q["state"] == [pid])
    check("trang xác nhận không lộ App Secret", "SECRET456" not in r.text)

    r = tc.get("/mt/ve", params={"state": pid, "code": "CODE1"}, follow_redirects=False)
    check("Facebook trả về: chuyển hướng về đúng máy", r.status_code == 302
          and r.headers["location"].startswith(VE + "?"), r.headers.get("location"))
    loc = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers["location"]).query)
    check("địa chỉ chuyển hướng không chứa token", "LL_" not in r.headers["location"]
          and loc["state"] == [st] and loc["tram"] == [pid])
    check("trạm không giữ token thô trong RAM", "LL_SHORT_CODE1" not in str(meta_tram._hop))

    kq = await oauth_mcp.handle_callback(st, "", pid)
    check("máy nhận và lưu token", kq.get("ok"), kq)
    ent = oauth_mcp._load()["cmeta"]
    check("token dài hạn đúng", secrets_store.decrypt(ent["access_token"]) == "LL_SHORT_CODE1")
    check("ghi nhớ quyền thật được cấp", ent.get("scopes") == "ads_read", ent.get("scopes"))
    check("đánh dấu kết nối đi qua trạm", ent.get("qua_tram") is True)
    # khách chỉ cấp ads_read (fake /me/permissions từ chối pages_manage_posts) → callback báo thiếu
    thieu = set(kq.get("scopes_missing") or [])
    check("callback báo đúng quyền còn thiếu, không kể quyền đã cấp",
          "pages_manage_posts" in thieu and "khong_cho_phep" in thieu and "ads_read" not in thieu, thieu)

    d = tc.post("/mt/nhan", json=meta_tram.ky_than("/mt/nhan", {"phien": pid}))
    check("nhận lần hai: không còn", d.status_code == 404)

    # gia hạn tự động khi sắp hết hạn
    ent["expires_at"] = time.time() - 10
    st_ = oauth_mcp._load()
    st_["cmeta"] = ent
    oauth_mcp._save(st_)
    h = await oauth_mcp.auth_headers("cmeta")
    check("gia hạn qua trạm", h.get("Authorization") == "Bearer LL_LL_SHORT_CODE1", h)

    # kết nối lại không cần cờ qua_tram vẫn đi đường trạm
    res2 = await oauth_mcp.start_auth("cmeta", VE)
    check("kết nối lại tự đi qua trạm", res2.get("ok") and "/mt/xac-nhan/" in res2.get("url", ""), res2)


asyncio.run(chay())

# quyền Meta ngăn bằng dấu PHẨY phải tách đúng (trước 26.10.117 tách theo dấu cách nên hỏng)
st_ = oauth_mcp._load(); st_["cmeta"]["scopes"] = "ads_read,pages_manage_posts,read_insights"; oauth_mcp._save(st_)
check("tách quyền Meta theo dấu phẩy", set(oauth_mcp.granted_scopes("cmeta")) ==
      {"ads_read", "pages_manage_posts", "read_insights"}, oauth_mcp.granted_scopes("cmeta"))

# ---------- chữ ký ----------
than = meta_tram.ky_than("/mt/bat-dau", {"ve": VE, "st": "a" * 24, "kx": kx, "quyen": ["ads_read"]})
than["ve"] = "https://evil.vn/connect/oauth/callback"
check("sửa thân sau khi ký: 401", tc.post("/mt/bat-dau", json=than).status_code == 401)
cu = meta_tram.ky_than("/mt/bat-dau", {"ve": VE, "st": "a" * 24, "kx": kx})
cu["luc"] = str(int(time.time()) - 3600)
check("chữ ký quá cũ: 401", tc.post("/mt/bat-dau", json=cu).status_code == 401)
xau = meta_tram.ky_than("/mt/bat-dau", {"ve": "https://10.0.0.1/connect/oauth/callback", "st": "a" * 24, "kx": kx})
check("quay về IP nội bộ: 400", tc.post("/mt/bat-dau", json=xau).status_code == 400)

# máy khác không lấy được gói của phiên không phải của mình
meta_tram._hop["phienX"] = {"khoa": "khoa-cua-may-khac", "goi": goi, "ts": time.time()}
k2 = Ed25519PrivateKey.generate()
pub2 = base64.b64encode(k2.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
t2 = {"phien": "phienX", "khoa": pub2, "luc": str(int(time.time()))}
t2["ky"] = base64.b64encode(k2.sign(meta_tram.thong_diep("/mt/nhan", t2, t2["luc"]))).decode()
check("máy khác xin gói không phải của mình: 404", tc.post("/mt/nhan", json=t2).status_code == 404)
check("gói vẫn còn cho đúng chủ", "phienX" in meta_tram._hop)

# ---------- giới hạn tần suất ----------
check("giới hạn tần suất chặn spam", all(meta_tram.gioi_han("x", 3) for _ in range(3)) and not meta_tram.gioi_han("x", 3))

# ---------- trạm tắt ----------
os.environ.pop("JAVIS_META_TRAM_APP_SECRET")
check("máy không giữ App Secret: trạm báo tắt", tc.get("/mt/thong-tin").json()["bat"] is False)
r = tc.post("/mt/bat-dau", json=meta_tram.ky_than("/mt/bat-dau", {"ve": VE, "st": "b" * 24, "kx": kx}))
check("trạm tắt: 503", r.status_code == 503)
check("không lời nào dùng gạch dài", "—" not in open(meta_tram.__file__, encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
