"""Cầu nối Zalo Official Account API (transport "internal"). Mỗi kết nối = MỘT Official Account.

Khác connector "zalo" (tài khoản Zalo CÁ NHÂN qua zalo-agent-cli, API không chính thức): cầu nối
này dùng API CHÍNH THỨC của Zalo cho OA, qua app trên developers.zalo.me. Nhiều OA thì thêm nhiều
kết nối (có thể dùng chung một app).

Ủy quyền (OAuth v4 cho OA):
  - Link: https://oauth.zaloapp.com/v4/oa/permission?app_id=..&redirect_uri=..  (tool
    `zalo_oa_lien_ket_uy_quyen`). Quản trị viên OA đồng ý, được chuyển về redirect kèm ?code=...
  - Đổi code: POST https://oauth.zaloapp.com/v4/oa/access_token, dạng form, header
    `secret_key: <app_secret>`, grant_type=authorization_code, code, app_id (+ code_verifier nếu
    app bật PKCE).
  - Hoặc dán thẳng refresh_token lấy từ Zalo API Explorer.
  - Làm mới: cùng địa chỉ, grant_type=refresh_token, refresh_token, app_id.
Access token sống khoảng 25 giờ. Refresh token sống 3 tháng và DÙNG MỘT LẦN: mỗi lần làm mới được
cặp mới, cặp cũ chết. Vì vậy làm mới luôn đi qua khoá của kết nối và LƯU NGAY cả hai token mới.

Gọi API: header `access_token: <token>`, kết quả {error: 0, message, data}; error khác 0 là lỗi.
Lỗi -216 / -124 (token sai hoặc hết hạn) thì làm mới đúng một lần rồi thử lại đúng một lần.

Tool ghi duy nhất: `zalo_oa_gui_tin` gửi tin tư vấn THẬT tới khách (mức Toàn quyền).
"""
import json
import time
from urllib.parse import urlencode

import ket_noi_api as k

HOST = "https://openapi.zalo.me"
OAUTH = "https://oauth.zaloapp.com/v4/oa"
TEN = "Zalo OA"
BI_MAT = ("app_secret", "access_token", "refresh_token", "auth_code", "code_verifier")
LOI_TOKEN = (-216, -124)
TIN_TOI_DA = 2000

_UID = {"user_id": {"type": "string", "description": "mã người dùng Zalo theo OA (dãy số)"}}

TOOLS = [
    k.tool("zalo_oa_lien_ket_uy_quyen",
           "Tạo link để quản trị viên OA ủy quyền app cho MinMin (dùng khi kết nối mới hoặc ủy quyền hết "
           "hạn). Mở link, chọn OA, đồng ý, rồi dán code trên địa chỉ trả về vào kết nối.",
           {"redirect_url": {"type": "string", "description": "Callback URL đã khai trong app Zalo"}}),
    k.tool("zalo_oa_thong_tin", "Tên, mã OA, mô tả, số người quan tâm của Official Account đang kết nối."),
    k.tool("zalo_oa_hoi_thoai_gan_day",
           "Các tin nhắn gần nhất của OA (mỗi cuộc trò chuyện một tin mới nhất), mới nhất trước.",
           {"offset": {"type": "integer", "description": "bỏ qua bao nhiêu dòng đầu"},
            "count": {"type": "integer", "description": "số dòng, tối đa 10"}}),
    k.tool("zalo_oa_hoi_thoai",
           "Lịch sử tin nhắn giữa OA và một người dùng, mới nhất trước.",
           {**_UID, "offset": {"type": "integer"}, "count": {"type": "integer", "description": "tối đa 10"}},
           ["user_id"]),
    k.tool("zalo_oa_nguoi_quan_tam",
           "Danh sách người dùng (mặc định chỉ người đang quan tâm OA), lọc theo nhãn nếu cần.",
           {"offset": {"type": "integer"}, "count": {"type": "integer", "description": "tối đa 50"},
            "tag_name": {"type": "string", "description": "chỉ lấy người có nhãn này"},
            "is_follower": {"type": "boolean", "description": "mặc định true"}}),
    k.tool("zalo_oa_thong_tin_nguoi_dung",
           "Hồ sơ một người dùng: tên hiển thị, nhãn, thông tin chia sẻ, đang quan tâm hay không.",
           _UID, ["user_id"]),
    k.tool("zalo_oa_gui_tin",
           "GỬI TIN NHẮN THẬT (tin tư vấn dạng chữ) từ OA tới một người dùng. Không rút lại được. Chỉ gửi "
           "khi người dùng yêu cầu rõ.",
           {**_UID, "text": {"type": "string", "description": "nội dung, 1 đến 2000 ký tự"}},
           ["user_id", "text"]),
]


async def list_tools(spec):
    return TOOLS


def _an(sec):
    return {kk: sec.get(kk) for kk in BI_MAT if sec.get(kk)}


def lien_ket_uy_quyen(sec, redirect_url):
    q = urlencode({"app_id": str(sec["app_id"]).strip(), "redirect_uri": redirect_url})
    return f"{OAUTH}/permission?{q}"


def _giay(v, mac_dinh):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return mac_dinh


async def _doi_token(spec, form):
    """Gọi OAuth, lưu ngay access + refresh token mới. Trả None hoặc câu lỗi."""
    sec = k.bi_mat(spec)
    ok, d = await k.goi(TEN, "POST", f"{OAUTH}/access_token", secrets=_an(sec),
                        data={**form, "app_id": str(sec["app_id"]).strip()},
                        headers={"secret_key": str(sec["app_secret"]).strip()})
    if not ok:
        return d
    if not isinstance(d, dict) or not d.get("access_token") or (d.get("error") not in (None, 0, "0")):
        if isinstance(d, dict):
            ly_do = f"{d.get('error', '')} {d.get('error_name', '')} {d.get('error_description', '')}".strip()
        else:
            ly_do = str(d)[:300]
        return k.giau(f"ERROR: Zalo từ chối cấp token: {ly_do}. Tạo lại link ủy quyền bằng "
                      "zalo_oa_lien_ket_uy_quyen rồi dán code mới (hoặc dán refresh token mới từ API "
                      "Explorer).", _an(sec))
    k.luu_bi_mat(spec, {"access_token": d["access_token"],
                        "refresh_token": d.get("refresh_token", ""),
                        "token_het_han": int(time.time()) + _giay(d.get("expires_in"), 90000)})
    return None


async def _lam_moi(spec):
    sec = k.bi_mat(spec)
    rt = str(sec.get("refresh_token") or "").strip()
    if not rt:
        return ("ERROR: OA chưa ủy quyền hoặc ủy quyền đã hết hạn. Gọi zalo_oa_lien_ket_uy_quyen để lấy "
                "link, rồi dán code vào kết nối ở trang Kết nối.")
    return await _doi_token(spec, {"grant_type": "refresh_token", "refresh_token": rt})


async def dam_bao_token(spec, tok_hong=None):
    """Trả None khi có access token dùng được, hoặc câu lỗi.

    `tok_hong`: token vừa bị Zalo từ chối (-216/-124). Chỉ làm mới nếu token hiện tại VẪN là nó;
    lượt song song khác đã làm mới rồi thì dùng luôn token mới, không đốt refresh token lần hai."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("auth_code") or "").strip()
        if code and code != str(sec.get("auth_code_da_dung") or ""):
            form = {"grant_type": "authorization_code", "code": code}
            if str(sec.get("code_verifier") or "").strip():
                form["code_verifier"] = str(sec["code_verifier"]).strip()
            loi = await _doi_token(spec, form)
            if loi:
                return loi
            k.luu_bi_mat(spec, {"auth_code_da_dung": code})
            return None
        tok = str(sec.get("access_token") or "").strip()
        if tok_hong is not None:
            if tok and tok != tok_hong:
                return None
            return await _lam_moi(spec)
        if tok and k.con_han(sec, "token_het_han"):
            return None
        return await _lam_moi(spec)


async def _api(spec, method, path, params=None, body=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    da_thu_lai = False
    while True:
        sec = k.bi_mat(spec)
        tok = str(sec["access_token"]).strip()
        ok, d = await k.goi(TEN, method, f"{HOST}{path}", secrets=_an(sec), params=params, json_body=body,
                            headers={"access_token": tok})
        if not ok:
            return False, d
        if not isinstance(d, dict):
            return False, k.giau(f"ERROR: Zalo trả về không đúng dạng: {str(d)[:300]}", _an(sec))
        ma = _giay(d.get("error"), 0)
        if ma == 0:
            return True, d.get("data", d)
        if ma in LOI_TOKEN and not da_thu_lai:
            da_thu_lai = True
            loi = await dam_bao_token(spec, tok_hong=tok)
            if loi:
                return False, loi
            continue
        return False, k.giau(f"ERROR: Zalo {ma}: {d.get('message', '')}", _an(k.bi_mat(spec)))


def _data(obj):
    return {"data": json.dumps(obj, ensure_ascii=False, separators=(",", ":"))}


def _uid(a):
    u = str((a or {}).get("user_id") or "").strip()
    return u if u.isdigit() and len(u) <= 30 else None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "app_id", "app_secret")
    if t:
        return "ERROR: kết nối Zalo OA thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    if not str(sec.get("app_id")).strip().isdigit():
        return "ERROR: App ID của Zalo phải là dãy số"
    a = arguments or {}
    ra = await _xu_ly(tool, a, spec)
    return k.giau(ra, _an(k.bi_mat(spec)))


async def _xu_ly(tool, a, spec):
    sec = k.bi_mat(spec)
    if tool == "zalo_oa_lien_ket_uy_quyen":
        url = str(a.get("redirect_url") or sec.get("redirect_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return "ERROR: cần redirect_url (Callback URL đã khai trong app Zalo), bắt đầu bằng https://"
        return lien_ket_uy_quyen(sec, url)

    if tool == "zalo_oa_gui_tin":
        uid = _uid(a)
        if not uid:
            return "ERROR: user_id phải là dãy số (mã người dùng theo OA)"
        text = a.get("text")
        if not isinstance(text, str) or not text.strip():
            return "ERROR: thiếu nội dung tin nhắn (text)"
        if len(text) > TIN_TOI_DA:
            return f"ERROR: tin nhắn dài {len(text)} ký tự, tối đa {TIN_TOI_DA}"
        ok, d = await _api(spec, "POST", "/v3.0/oa/message/cs",
                           body={"recipient": {"user_id": uid}, "message": {"text": text}})
    elif tool == "zalo_oa_thong_tin":
        ok, d = await _api(spec, "GET", "/v2.0/oa/getoa")
    elif tool == "zalo_oa_hoi_thoai_gan_day":
        ok, d = await _api(spec, "GET", "/v2.0/oa/listrecentchat", _data({
            "offset": k.so(a.get("offset"), 0, 0, 100000), "count": k.so(a.get("count"), 10, 1, 10)}))
    elif tool == "zalo_oa_hoi_thoai":
        uid = _uid(a)
        if not uid:
            return "ERROR: user_id phải là dãy số (mã người dùng theo OA)"
        ok, d = await _api(spec, "GET", "/v2.0/oa/conversation", _data({
            "user_id": int(uid), "offset": k.so(a.get("offset"), 0, 0, 100000),
            "count": k.so(a.get("count"), 10, 1, 10)}))
    elif tool == "zalo_oa_nguoi_quan_tam":
        q = {"offset": k.so(a.get("offset"), 0, 0, 100000), "count": k.so(a.get("count"), 50, 1, 50),
             "is_follower": a.get("is_follower") is not False}
        tag = str(a.get("tag_name") or "").strip()
        if tag:
            q["tag_name"] = tag[:100]
        ok, d = await _api(spec, "GET", "/v3.0/oa/user/getlist", _data(q))
    elif tool == "zalo_oa_thong_tin_nguoi_dung":
        uid = _uid(a)
        if not uid:
            return "ERROR: user_id phải là dãy số (mã người dùng theo OA)"
        ok, d = await _api(spec, "GET", "/v3.0/oa/user/detail", _data({"user_id": uid}))
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Zalo OA"
    return k.json_ra(d) if ok else d
