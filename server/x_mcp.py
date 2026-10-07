"""Cầu nối X (Twitter) API v2 (transport "internal"). Mỗi kết nối = MỘT tài khoản X.

Ủy quyền: OAuth 2.0 user context, Authorization Code + PKCE (S256), theo docs.x.com:
  - Link: https://x.com/i/oauth2/authorize?response_type=code&client_id=..&redirect_uri=..
    &scope=tweet.read tweet.write users.read offline.access&state=..&code_challenge=..
    &code_challenge_method=S256  (tool `x_lien_ket_uy_quyen`). code_verifier được LƯU vào kết
    nối (mã hoá) để đổi code về sau; link tạo lại vẫn dùng verifier cũ tới khi nó được dùng.
  - Đổi code: POST https://api.x.com/2/oauth2/token, dạng form: code, grant_type=
    authorization_code, redirect_uri, code_verifier. Client bí mật (có Client Secret) gửi header
    `Authorization: Basic base64(client_id:client_secret)`; client công khai gửi client_id trong form.
    X ghi rõ code chỉ sống 30 GIÂY, nên đổi ngay bằng tool `x_nhap_ma_uy_quyen` trong chat.
  - Làm mới: cùng địa chỉ, grant_type=refresh_token, refresh_token. Access token sống 2 giờ.
    Refresh token XOAY VÒNG (mỗi lần được cái mới, cái cũ chết), nên làm mới luôn đi qua khoá
    của kết nối và lưu ngay cả hai token mới.

Gọi API: header `Authorization: Bearer <token>`. 401 thì làm mới đúng một lần rồi thử lại một lần.
X API tính tiền theo lượt gọi (pay-per-use, mua credit trước), nên tool đọc mặc định lấy ít.

Tool ghi (mức Toàn quyền): đăng bài / trả lời (`x_dang_bai`) và xoá bài của chính mình
(`x_xoa_bai`). Không có tải ảnh/video.
"""
import base64
import hashlib
import re
import secrets as _secrets
import time
import unicodedata
from urllib.parse import parse_qs, urlencode, urlparse

import ket_noi_api as k

HOST = "https://api.x.com"
AUTHORIZE = "https://x.com/i/oauth2/authorize"
TOKEN = "https://api.x.com/2/oauth2/token"
TEN = "X"
SCOPES = "tweet.read tweet.write users.read offline.access"
# Giấu MỌI ô kết nối trừ vài mã công khai: ô bí mật thêm sau tự được giấu luôn.
# pkce_state nằm lộ trên link ủy quyền nên phải được hiện (giấu đi là hỏng link).
CONG_KHAI = ("client_id", "redirect_url", "user_id", "username", "token_het_han", "pkce_state")
BAI_TOI_DA = 280
_ID = re.compile(r"^[0-9]{1,19}$")
_URL = re.compile(r"https?://[^\s]+", re.IGNORECASE)
# Bảng trọng số chữ của twitter-text v3 (config/v3.json): các khoảng dưới tính 1, còn lại tính 2.
_NHE = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
_DI_KEM = {0xFE0E, 0xFE0F, 0x200D}

TOOLS = [
    k.tool("x_lien_ket_uy_quyen",
           "Tạo link để chủ tài khoản X ủy quyền app cho MinMin (khi kết nối mới hoặc ủy quyền hỏng). Mở "
           "link, đồng ý, rồi dán NGAY địa chỉ trả về vào chat để gọi x_nhap_ma_uy_quyen (code chỉ sống 30 giây).",
           {"redirect_url": {"type": "string", "description": "Callback URL đã khai trong app X"}}),
    k.tool("x_nhap_ma_uy_quyen",
           "Đổi code ủy quyền X lấy token và lưu vào kết nối. Nhận code hoặc nguyên địa chỉ trả về "
           "(...?state=..&code=..). Gọi ngay khi người dùng dán, vì code hết hạn sau 30 giây.",
           {"code": {"type": "string", "description": "code, hoặc cả địa chỉ trả về có ?code="}},
           ["code"]),
    k.tool("x_thong_tin", "Tài khoản X đang kết nối: tên, username, mô tả, số người theo dõi, số bài."),
    k.tool("x_bai_gan_day",
           "Các bài gần nhất của tài khoản (hoặc của user_id khác), mới nhất trước, kèm lượt xem, thích, "
           "trả lời, đăng lại. Mỗi bài đọc về đều bị X tính phí, nên lấy vừa đủ.",
           {"user_id": {"type": "string", "description": "mã người dùng X (dãy số), bỏ trống = chính mình"},
            "max_results": {"type": "integer", "description": "số bài, 5 đến 100, mặc định 10"},
            "pagination_token": {"type": "string", "description": "next_token của lần trước để xem tiếp"},
            "bo_tra_loi": {"type": "boolean", "description": "bỏ các bài trả lời"},
            "bo_dang_lai": {"type": "boolean", "description": "bỏ các bài đăng lại (repost)"}}),
    k.tool("x_dang_bai",
           "ĐĂNG BÀI THẬT lên X (hoặc trả lời một bài). Công khai ngay, chỉ đăng khi người dùng yêu cầu rõ. "
           "Tối đa 280 theo cách X đếm: link tính 23, emoji, chữ Hán và chữ Việt có dấu như ạ, ế tính 2.",
           {"text": {"type": "string", "description": "nội dung bài"},
            "tra_loi_bai": {"type": "string", "description": "mã bài (dãy số) muốn trả lời, không bắt buộc"}},
           ["text"]),
    k.tool("x_xoa_bai",
           "XOÁ VĨNH VIỄN một bài của chính tài khoản đang kết nối. Không khôi phục được. Chỉ xoá khi "
           "người dùng yêu cầu rõ đúng mã bài.",
           {"tweet_id": {"type": "string", "description": "mã bài (dãy số)"}},
           ["tweet_id"]),
]


async def list_tools(spec):
    return TOOLS


def _an(sec):
    return {kk: v for kk, v in (sec or {}).items() if v and kk not in CONG_KHAI}


def pkce_challenge(verifier):
    """S256: base64url(sha256(verifier)) bỏ dấu '='."""
    so = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(so).decode("ascii").rstrip("=")


def do_dai_x(text):
    """Độ dài bài theo cách X đếm (twitter-text v3): NFC, link = 23, ngoài bảng nhẹ = 2,
    chuỗi emoji ghép (ZWJ, biến thể, màu da, cờ) tính như một emoji."""
    s = unicodedata.normalize("NFC", text)
    n = 23 * len(_URL.findall(s))
    s = _URL.sub("", s)
    sau_zwj = False
    co_le = False   # đang giữa một cặp chữ cái cờ (regional indicator)
    for ch in s:
        cp = ord(ch)
        if cp in _DI_KEM or 0x1F3FB <= cp <= 0x1F3FF:
            sau_zwj = cp == 0x200D
            continue
        if sau_zwj:
            sau_zwj = False
            continue
        if 0x1F1E6 <= cp <= 0x1F1FF:
            if co_le:
                co_le = False
                continue
            co_le = True
        else:
            co_le = False
        n += 1 if any(a <= cp <= b for a, b in _NHE) else 2
    return n


def _basic(sec):
    cid = str(sec.get("client_id") or "").strip()
    cs = str(sec.get("client_secret") or "").strip()
    if not cs:
        return {}
    return {"Authorization": "Basic " + base64.b64encode(f"{cid}:{cs}".encode()).decode()}


def _form(sec, form):
    """Client công khai (không Client Secret) phải gửi client_id trong form."""
    if not str(sec.get("client_secret") or "").strip():
        form = {**form, "client_id": str(sec.get("client_id") or "").strip()}
    return form


def _giay(v, mac_dinh):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return mac_dinh


async def _doi_token(spec, form):
    """Gọi token endpoint, lưu ngay access + refresh mới. Trả None hoặc câu lỗi."""
    sec = k.bi_mat(spec)
    ok, d = await k.goi(TEN, "POST", TOKEN, secrets=_an(sec), data=_form(sec, form), headers=_basic(sec))
    if not ok:
        return d + (" Ủy quyền lại: gọi x_lien_ket_uy_quyen, mở link, rồi dán ngay địa chỉ trả về."
                    if " 400:" in d or " 401:" in d else "")
    if not isinstance(d, dict) or not d.get("access_token"):
        return k.giau(f"ERROR: X không cấp token: {str(d)[:300]}", _an(sec))
    k.luu_bi_mat(spec, {"access_token": d["access_token"],
                        "refresh_token": d.get("refresh_token", ""),
                        "token_het_han": int(time.time()) + _giay(d.get("expires_in"), 7200)})
    return None


async def _lam_moi(spec):
    rt = str(k.bi_mat(spec).get("refresh_token") or "").strip()
    if not rt:
        return ("ERROR: tài khoản X chưa ủy quyền hoặc ủy quyền đã hỏng. Gọi x_lien_ket_uy_quyen để lấy "
                "link, đồng ý, rồi dán ngay địa chỉ trả về vào chat.")
    return await _doi_token(spec, {"grant_type": "refresh_token", "refresh_token": rt})


async def dam_bao_token(spec, tok_hong=None):
    """None khi có access token dùng được, hoặc câu lỗi. `tok_hong`: token X vừa trả 401. Chỉ làm
    mới nếu token hiện tại VẪN là nó, để hai lượt song song không đốt refresh token hai lần."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        tok = str(sec.get("access_token") or "").strip()
        if tok_hong is not None:
            if tok and tok != tok_hong:
                return None
            return await _lam_moi(spec)
        if tok and k.con_han(sec, "token_het_han", 120):
            return None
        return await _lam_moi(spec)


def _goi_y(loi):
    if " 429:" in loi:
        return loi + " (X giới hạn tần suất, thử lại sau 15 phút.)"
    if " 402:" in loi or " 403:" in loi:
        return loi + " (Kiểm tra credit X API trong Developer Console và quyền Read and write của app.)"
    return loi


async def _api(spec, method, path, params=None, body=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    da_thu_lai = False
    while True:
        sec = k.bi_mat(spec)
        tok = str(sec["access_token"]).strip()
        ok, d = await k.goi(TEN, method, f"{HOST}{path}", secrets=_an(sec), params=params, json_body=body,
                            headers={"Authorization": f"Bearer {tok}"})
        if ok:
            if isinstance(d, dict) and d.get("errors") and "data" not in d:
                return False, k.giau(f"ERROR: X: {k.json_ra(d['errors'], 400)}", _an(sec))
            return True, d
        if f"ERROR: {TEN} 401:" in d and not da_thu_lai:
            da_thu_lai = True
            loi = await dam_bao_token(spec, tok_hong=tok)
            if loi:
                return False, loi
            continue
        return False, _goi_y(d)


def _ma_tu_chuoi(v):
    """(code, state) từ code trơn hoặc cả địa chỉ trả về."""
    s = str(v or "").strip()
    if "code=" in s:
        q = parse_qs(urlparse(s).query if "?" in s else s)
        return (q.get("code") or [""])[0].strip(), (q.get("state") or [""])[0].strip()
    return s, ""


async def _nhap_ma(spec, a):
    code, state = _ma_tu_chuoi(a.get("code"))
    if not code or len(code) > 2000 or any(c.isspace() for c in code):
        return "ERROR: thiếu code (dán code hoặc cả địa chỉ trả về có ?code=)"
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        ver = str(sec.get("code_verifier") or "").strip()
        if not ver or ver == str(sec.get("code_verifier_da_dung") or ""):
            return "ERROR: chưa có link ủy quyền đang chờ. Gọi x_lien_ket_uy_quyen trước, rồi mở link mới."
        if state and state != str(sec.get("pkce_state") or ""):
            return "ERROR: state không khớp link ủy quyền gần nhất. Mở lại link mới nhất từ x_lien_ket_uy_quyen."
        url = str(sec.get("redirect_url") or "").strip()
        loi = await _doi_token(spec, {"code": code, "grant_type": "authorization_code",
                                      "redirect_uri": url, "code_verifier": ver})
        if loi:
            return loi
        k.luu_bi_mat(spec, {"code_verifier_da_dung": ver})
    ok, d = await _api(spec, "GET", "/2/users/me")
    if ok and isinstance(d.get("data"), dict):
        u = d["data"]
        k.luu_bi_mat(spec, {"user_id": u.get("id", ""), "username": u.get("username", "")})
        return f"Đã ủy quyền tài khoản X @{u.get('username', '')} ({u.get('name', '')})."
    return "Đã lưu token X nhưng chưa đọc được tài khoản: " + str(d)


async def _lien_ket(spec, a):
    sec = k.bi_mat(spec)
    url = str(a.get("redirect_url") or sec.get("redirect_url") or "").strip()
    if not url.startswith(("https://", "http://")):
        return "ERROR: cần redirect_url (Callback URL đã khai trong app X), bắt đầu bằng https://"
    ver = str(sec.get("code_verifier") or "").strip()
    state = str(sec.get("pkce_state") or "").strip()
    if not ver or ver == str(sec.get("code_verifier_da_dung") or "") or not state:
        ver = _secrets.token_urlsafe(48)       # 64 ký tự, trong giới hạn 43..128 của PKCE
        state = _secrets.token_urlsafe(16)
    k.luu_bi_mat(spec, {"code_verifier": ver, "pkce_state": state, "redirect_url": url})
    q = urlencode({"response_type": "code", "client_id": str(sec["client_id"]).strip(), "redirect_uri": url,
                   "scope": SCOPES, "state": state, "code_challenge": pkce_challenge(ver),
                   "code_challenge_method": "S256"})
    return (f"{AUTHORIZE}?{q}\n\nMở link, đăng nhập đúng tài khoản X và bấm đồng ý. Trang sẽ chuyển về "
            "Callback URL kèm ?code=... Chép NGUYÊN địa chỉ đó dán vào chat ngay (code sống 30 giây).")


async def _ma_toi(spec):
    sec = k.bi_mat(spec)
    uid = str(sec.get("user_id") or "").strip()
    if _ID.match(uid):
        return uid, None
    ok, d = await _api(spec, "GET", "/2/users/me")
    if not ok:
        return None, d
    u = (d or {}).get("data") or {}
    if not _ID.match(str(u.get("id") or "")):
        return None, "ERROR: X không trả mã người dùng"
    k.luu_bi_mat(spec, {"user_id": u["id"], "username": u.get("username", "")})
    return u["id"], None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "client_id")
    if t:
        return "ERROR: kết nối X thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    ra = await _xu_ly(tool, arguments or {}, spec)
    return k.giau(ra, _an(k.bi_mat(spec)))


async def _xu_ly(tool, a, spec):
    if tool == "x_lien_ket_uy_quyen":
        return await _lien_ket(spec, a)
    if tool == "x_nhap_ma_uy_quyen":
        return await _nhap_ma(spec, a)

    if tool == "x_thong_tin":
        ok, d = await _api(spec, "GET", "/2/users/me", {
            "user.fields": "created_at,description,public_metrics,verified,profile_image_url,url"})
        if ok and isinstance((d or {}).get("data"), dict):
            k.luu_bi_mat(spec, {"user_id": d["data"].get("id", ""), "username": d["data"].get("username", "")})
    elif tool == "x_bai_gan_day":
        uid = str(a.get("user_id") or "").strip()
        if uid and not _ID.match(uid):
            return "ERROR: user_id phải là dãy số (tối đa 19 chữ số)"
        q = {"max_results": k.so(a.get("max_results"), 10, 5, 100),
             "tweet.fields": "created_at,public_metrics,conversation_id,in_reply_to_user_id,referenced_tweets"}
        pt = str(a.get("pagination_token") or "").strip()
        if pt:
            if not re.match(r"^[A-Za-z0-9_-]{1,200}$", pt):
                return "ERROR: pagination_token không hợp lệ"
            q["pagination_token"] = pt
        bo = [x for x, co in (("replies", a.get("bo_tra_loi")), ("retweets", a.get("bo_dang_lai"))) if co is True]
        if bo:
            q["exclude"] = ",".join(bo)
        if not uid:
            uid, loi = await _ma_toi(spec)
            if loi:
                return loi
        ok, d = await _api(spec, "GET", f"/2/users/{uid}/tweets", q)
    elif tool == "x_dang_bai":
        text = a.get("text")
        if not isinstance(text, str) or not text.strip():
            return "ERROR: thiếu nội dung bài (text)"
        n = do_dai_x(text)
        if n > BAI_TOI_DA:
            return f"ERROR: bài dài {n} theo cách X đếm, tối đa {BAI_TOI_DA}. Rút gọn rồi thử lại."
        body = {"text": text}
        rep = str(a.get("tra_loi_bai") or "").strip()
        if rep:
            if not _ID.match(rep):
                return "ERROR: tra_loi_bai phải là mã bài (dãy số, tối đa 19 chữ số)"
            body["reply"] = {"in_reply_to_tweet_id": rep}
        ok, d = await _api(spec, "POST", "/2/tweets", body=body)
    elif tool == "x_xoa_bai":
        tid = str(a.get("tweet_id") or "").strip()
        if not _ID.match(tid):
            return "ERROR: tweet_id phải là mã bài (dãy số, tối đa 19 chữ số)"
        ok, d = await _api(spec, "DELETE", f"/2/tweets/{tid}")
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối X"
    return k.json_ra(d) if ok else d
