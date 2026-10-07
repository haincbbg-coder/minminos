"""Cầu nối Instagram Graph API, phần đăng bài (Content Publishing) và đọc số liệu (transport "internal").

Mỗi kết nối = MỘT tài khoản Instagram chuyên nghiệp (Business hoặc Creator). Nhiều tài khoản thì
thêm nhiều kết nối.

Hai đường đăng nhập Meta cho phép, MinMin nhận cả hai:
  - Instagram Login (token bắt đầu bằng "IG"): gọi https://graph.instagram.com.
  - Facebook Login (tài khoản IG gắn với một Trang Facebook, token bắt đầu bằng "EAA"): gọi
    https://graph.facebook.com.
MinMin chọn host theo tiền tố token: "IG" đi graph.instagram.com, còn lại đi graph.facebook.com.

Luồng đăng (tài liệu "Content Publishing" của Meta):
  1. POST /{ig-user-id}/media tạo container (image_url | video_url + media_type=REELS |
     các container con is_carousel_item=true rồi container cha media_type=CAROUSEL + children).
  2. GET /{container-id}?fields=status_code,status hỏi tới khi FINISHED (ERROR / EXPIRED là hỏng).
     Số lần hỏi có GIỚI HẠN; hết lượt mà chưa xong thì trả creation_id để đăng sau bằng
     `instagram_dang_container`, không treo lượt chat.
  3. POST /{ig-user-id}/media_publish creation_id=...
Trước khi đăng hỏi GET /{ig-user-id}/content_publishing_limit; đã chạm trần thì từ chối luôn.
Ảnh, video phải ở một đường link https CÔNG KHAI (Meta tự tải về), không nhận file trong máy.

appsecret_proof: có ô app_secret thì mọi request gửi kèm appsecret_proof =
HMAC-SHA256(app_secret, access_token) dạng hex (bắt buộc khi app bật "Require App Secret").

Làm mới token: chỉ token Instagram Login dài hạn (60 ngày) làm mới được bằng
GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token. Token phải
cũ hơn 24 giờ. MinMin tự làm mới khi còn dưới 7 ngày (hoặc chưa biết hạn), qua khoá của kết
nối, lưu token mới bằng luu_bi_mat. Làm mới hỏng thì lùi 6 giờ rồi mới thử lại, lượt gọi vẫn
chạy bằng token cũ. Token Facebook Login không làm mới ở đây (Meta gia hạn qua app Facebook).

Tool nguy hiểm (mức Toàn quyền): đăng ảnh, đăng carousel, đăng Reel, đăng container có sẵn, trả
lời bình luận. Bài đăng là CÔNG KHAI và API không có lệnh xoá bài.
"""
import asyncio
import hashlib
import hmac
import re
import time
from urllib.parse import urlparse

import ket_noi_api as k

PHIEN_BAN = "v25.0"
HOST_IG = "https://graph.instagram.com"
HOST_FB = "https://graph.facebook.com"
TEN = "Instagram"
# Giấu MỌI ô kết nối trừ vài mốc thời gian / lựa chọn công khai: ô bí mật thêm sau tự được giấu.
CONG_KHAI = ("token_het_han", "token_lam_moi_luc", "thu_lam_moi_luc")
CAPTION_TOI_DA = 2200
HASHTAG_TOI_DA = 30
NHAC_TEN_TOI_DA = 20
BINH_LUAN_TOI_DA = 2200
CAROUSEL_IT, CAROUSEL_NHIEU = 2, 10
DUOI_VIDEO = (".mp4", ".mov", ".m4v")
CHI_SO_MAC_DINH = "reach,likes,comments,saved,shares,total_interactions,views"
_CHI_SO = re.compile(r"^[a-z_]{2,48}(,[a-z_]{2,48}){0,19}$")
_MA = re.compile(r"^[0-9]{1,40}$")
_MA_TK = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

# Hỏi trạng thái container: (số lần tối đa, giây giữa hai lần). Ảnh xử lý nhanh, video lâu hơn.
HOI_ANH = (10, 2.0)
HOI_VIDEO = (36, 5.0)
LAM_MOI_TRUOC = 7 * 86400
TUOI_TOI_THIEU = 86400
LUI_KHI_HONG = 6 * 3600


async def _ngu(giay):       # tách ra để test thay bằng hàm không chờ
    await asyncio.sleep(giay)


_CAPTION = {"caption": {"type": "string", "description": f"chú thích, tối đa {CAPTION_TOI_DA} ký tự, "
                                                         f"{HASHTAG_TOI_DA} hashtag, {NHAC_TEN_TOI_DA} @"}}
_MEDIA_ID = {"media_id": {"type": "string", "description": "mã bài Instagram (dãy số)"}}

TOOLS = [
    k.tool("instagram_tai_khoan",
           "Thông tin tài khoản Instagram đang kết nối: tên, username, tiểu sử, số người theo dõi, số bài."),
    k.tool("instagram_bai_gan_day",
           "Các bài gần nhất của tài khoản: mã, chú thích, loại, link, thời gian, số thích, số bình luận.",
           {"limit": {"type": "integer", "description": "số bài, tối đa 50, mặc định 12"},
            "after": {"type": "string", "description": "con trỏ trang sau (paging.cursors.after)"}}),
    k.tool("instagram_chi_so_bai",
           "Chỉ số một bài: tiếp cận, lượt xem, thích, bình luận, lưu, chia sẻ, tổng tương tác.",
           {**_MEDIA_ID, "metric": {"type": "string",
                                    "description": "các chỉ số cách nhau dấu phẩy, mặc định " + CHI_SO_MAC_DINH}},
           ["media_id"]),
    k.tool("instagram_binh_luan",
           "Bình luận của một bài: mã bình luận, nội dung, người viết, thời gian, số thích.",
           {**_MEDIA_ID, "limit": {"type": "integer", "description": "tối đa 50, mặc định 25"},
            "after": {"type": "string", "description": "con trỏ trang sau"}},
           ["media_id"]),
    k.tool("instagram_han_muc_dang",
           "Số bài đã đăng qua API trong 24 giờ qua và hạn mức Meta cho phép (carousel tính là một)."),
    k.tool("instagram_trang_thai_container",
           "Trạng thái một container đang xử lý (IN_PROGRESS, FINISHED, ERROR, EXPIRED, PUBLISHED).",
           {"creation_id": {"type": "string", "description": "mã container (dãy số)"}}, ["creation_id"]),
    k.tool("instagram_dang_anh",
           "ĐĂNG CÔNG KHAI một bài ảnh lên Instagram. Ảnh JPEG ở link https công khai. Không xoá được qua "
           "API. Chỉ đăng khi người dùng yêu cầu rõ.",
           {"image_url": {"type": "string", "description": "link https công khai tới ảnh JPEG"}, **_CAPTION},
           ["image_url"]),
    k.tool("instagram_dang_carousel",
           f"ĐĂNG CÔNG KHAI một bài nhiều ảnh/video ({CAROUSEL_IT} đến {CAROUSEL_NHIEU} mục). Link kết "
           "thúc bằng .mp4/.mov là video, còn lại là ảnh. Không xoá được qua API.",
           {"media_urls": {"type": "array", "items": {"type": "string"},
                           "description": "các link https công khai, theo thứ tự hiển thị"}, **_CAPTION},
           ["media_urls"]),
    k.tool("instagram_dang_reel",
           "ĐĂNG CÔNG KHAI một Reel từ link video https công khai (MP4/MOV). Meta xử lý video có thể mất "
           "vài phút. Không xoá được qua API.",
           {"video_url": {"type": "string", "description": "link https công khai tới video"}, **_CAPTION,
            "share_to_feed": {"type": "boolean", "description": "hiện cả ở lưới bài, mặc định true"}},
           ["video_url"]),
    k.tool("instagram_dang_container",
           "ĐĂNG CÔNG KHAI một container đã tạo trước đó (dùng khi lần đăng trước báo video còn đang xử "
           "lý). Không xoá được qua API.",
           {"creation_id": {"type": "string", "description": "mã container (dãy số)"}}, ["creation_id"]),
    k.tool("instagram_tra_loi_binh_luan",
           "TRẢ LỜI CÔNG KHAI một bình luận gốc trên bài Instagram. Chỉ trả lời khi người dùng yêu cầu rõ.",
           {"comment_id": {"type": "string", "description": "mã bình luận (dãy số)"},
            "message": {"type": "string", "description": f"nội dung, tối đa {BINH_LUAN_TOI_DA} ký tự"}},
           ["comment_id", "message"]),
]


async def list_tools(spec):
    return TOOLS


def _an(sec):
    return {kk: v for kk, v in sec.items() if v and kk not in CONG_KHAI}


def appsecret_proof(app_secret, access_token):
    return hmac.new(str(app_secret).encode("utf-8"), str(access_token).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _host(sec):
    return HOST_IG if str(sec.get("access_token") or "").strip().startswith("IG") else HOST_FB


def _so_thuc(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def kiem_url(url, ten="link"):
    """None nếu là link https công khai dùng được, không thì câu lỗi."""
    if not isinstance(url, str) or not url.strip():
        return f"ERROR: thiếu {ten}"
    u = url.strip()
    if len(u) > 2000 or any(c.isspace() for c in u):
        return f"ERROR: {ten} không hợp lệ (quá dài hoặc có khoảng trắng)"
    p = urlparse(u)
    if p.scheme != "https" or not p.hostname:
        return f"ERROR: {ten} phải là link https:// công khai (Meta tự tải file về, không nhận file trong máy)"
    h = p.hostname.lower()
    if (h in ("localhost", "0.0.0.0") or h.endswith((".local", ".internal", ".lan")) or h.startswith(("127.", "10.", "192.168.", "169.254."))
            or re.match(r"^172\.(1[6-9]|2[0-9]|3[01])\.", h)):
        return f"ERROR: {ten} trỏ vào mạng nội bộ, Meta không tải được. Cần link công khai trên Internet"
    return None


def kiem_caption(cap):
    if cap in (None, ""):
        return None
    if not isinstance(cap, str):
        return "ERROR: caption phải là chuỗi"
    if len(cap) > CAPTION_TOI_DA:
        return f"ERROR: caption dài {len(cap)} ký tự, tối đa {CAPTION_TOI_DA}"
    if len(re.findall(r"(?:^|\s)#\w", cap)) > HASHTAG_TOI_DA:
        return f"ERROR: caption có quá {HASHTAG_TOI_DA} hashtag"
    if len(re.findall(r"(?:^|\s)@\w", cap)) > NHAC_TEN_TOI_DA:
        return f"ERROR: caption nhắc quá {NHAC_TEN_TOI_DA} tài khoản (@)"
    return None


def _la_video(url):
    return urlparse(url.strip()).path.lower().endswith(DUOI_VIDEO)


# ------------------------------------------------------------------ token
async def _lam_moi_neu_can(spec):
    """Tự làm mới token Instagram Login sắp hết hạn. Không bao giờ chặn lượt gọi."""
    sec = k.bi_mat(spec)
    if _host(sec) != HOST_IG:
        return
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        bay_gio = time.time()
        het = _so_thuc(sec.get("token_het_han"))
        if het is not None and het - bay_gio > LAM_MOI_TRUOC:
            return
        moi = _so_thuc(sec.get("token_lam_moi_luc"))
        if moi is not None and bay_gio - moi < TUOI_TOI_THIEU:
            return
        thu = _so_thuc(sec.get("thu_lam_moi_luc"))
        if thu is not None and bay_gio - thu < LUI_KHI_HONG:
            return
        tok = str(sec.get("access_token") or "").strip()
        ok, d = await k.goi(TEN, "GET", f"{HOST_IG}/refresh_access_token", secrets=_an(sec),
                            params={"grant_type": "ig_refresh_token", "access_token": tok})
        if ok and isinstance(d, dict) and d.get("access_token"):
            try:
                song = int(float(d.get("expires_in") or 5184000))
            except (TypeError, ValueError):
                song = 5184000
            k.luu_bi_mat(spec, {"access_token": d["access_token"],
                                "token_het_han": int(bay_gio) + song,
                                "token_lam_moi_luc": int(bay_gio)})
        else:
            k.luu_bi_mat(spec, {"thu_lam_moi_luc": int(bay_gio)})


async def _api(spec, method, path, params=None, data=None):
    sec = k.bi_mat(spec)
    tok = str(sec.get("access_token") or "").strip()
    q = dict(params or {})
    q["access_token"] = tok
    an = _an(sec)
    if str(sec.get("app_secret") or "").strip():
        proof = appsecret_proof(str(sec["app_secret"]).strip(), tok)
        q["appsecret_proof"] = proof
        an["_proof"] = proof
    ok, d = await k.goi(TEN, method, f"{_host(sec)}/{PHIEN_BAN}{path}", secrets=an, params=q, data=data,
                        timeout=60)
    if not ok:
        if '"code": 190' in d or "OAuthException" in d:
            d += (" | Token hỏng hoặc hết hạn: lấy token dài hạn mới rồi dán vào kết nối ở trang Kết nối.")
        return False, d
    if isinstance(d, dict) and isinstance(d.get("error"), dict):
        return False, k.giau(f"ERROR: {TEN}: {d['error'].get('message', '')}", an)
    return True, d


# ------------------------------------------------------------------ đăng
async def _han_muc(spec, ig):
    return await _api(spec, "GET", f"/{ig}/content_publishing_limit",
                      {"fields": "quota_usage,config", "since": int(time.time()) - 86400})


async def _con_han_muc(spec, ig):
    """Trả câu lỗi khi đã chạm trần đăng 24 giờ. Đọc hạn mức hỏng thì không chặn (Meta tự chặn)."""
    ok, d = await _han_muc(spec, ig)
    if not ok or not isinstance(d, dict):
        return None
    hang = (d.get("data") or [d])[0] if isinstance(d.get("data"), list) else d
    if not isinstance(hang, dict):
        return None
    dung = _so_thuc(hang.get("quota_usage"))
    tran = _so_thuc((hang.get("config") or {}).get("quota_total"))
    if dung is not None and tran and dung >= tran:
        return (f"ERROR: tài khoản đã đăng {int(dung)}/{int(tran)} bài qua API trong 24 giờ qua, chạm hạn "
                "mức của Meta. Chờ rồi đăng lại sau.")
    return None


async def _tao_container(spec, ig, form):
    ok, d = await _api(spec, "POST", f"/{ig}/media", data=form)
    if not ok:
        return None, d
    cid = str((d or {}).get("id") or "") if isinstance(d, dict) else ""
    if not cid:
        return None, "ERROR: Instagram không trả mã container"
    return cid, None


async def cho_container(spec, cid, so_lan, nghi):
    """Hỏi trạng thái tới khi FINISHED. Trả (trạng_thái, lỗi). trạng_thái 'CHUA_XONG' khi hết lượt."""
    for i in range(so_lan):
        ok, d = await _api(spec, "GET", f"/{cid}", {"fields": "status_code,status"})
        if not ok:
            return None, d
        ma = str((d or {}).get("status_code") or "").upper() if isinstance(d, dict) else ""
        if ma in ("FINISHED", "PUBLISHED"):
            return ma, None
        if ma in ("ERROR", "EXPIRED"):
            chi_tiet = str((d or {}).get("status") or "").strip()
            return None, (f"ERROR: container {cid} báo {ma}" + (f": {chi_tiet}" if chi_tiet else "")
                          + ". Kiểm tra định dạng (ảnh JPEG; video MP4/MOV) và link công khai rồi đăng lại.")
        if i < so_lan - 1:
            await _ngu(nghi)
    return "CHUA_XONG", None


def _chua_xong(cid):
    return k.json_ra({"trang_thai": "IN_PROGRESS", "creation_id": cid,
                      "ghi_chu": "Meta còn đang xử lý, CHƯA đăng. Vài phút nữa gọi instagram_dang_container "
                                 "với creation_id này để đăng."})


async def _xuat_ban(spec, ig, cid):
    ok, d = await _api(spec, "POST", f"/{ig}/media_publish", data={"creation_id": cid})
    if not ok:
        return d
    mid = str((d or {}).get("id") or "") if isinstance(d, dict) else ""
    ra = {"da_dang": True, "media_id": mid, "creation_id": cid}
    if mid:
        ok2, d2 = await _api(spec, "GET", f"/{mid}", {"fields": "permalink"})
        if ok2 and isinstance(d2, dict) and d2.get("permalink"):
            ra["permalink"] = d2["permalink"]
    return k.json_ra(ra)


async def _dang_mot(spec, ig, form, hoi):
    loi = await _con_han_muc(spec, ig)
    if loi:
        return loi
    cid, loi = await _tao_container(spec, ig, form)
    if loi:
        return loi
    tt, loi = await cho_container(spec, cid, *hoi)
    if loi:
        return loi
    if tt == "CHUA_XONG":
        return _chua_xong(cid)
    return await _xuat_ban(spec, ig, cid)


async def _dang_carousel(spec, ig, urls, caption):
    loi = await _con_han_muc(spec, ig)
    if loi:
        return loi
    con = []
    co_video = False
    for u in urls:
        if _la_video(u):
            co_video = True
            form = {"media_type": "VIDEO", "video_url": u.strip(), "is_carousel_item": "true"}
        else:
            form = {"image_url": u.strip(), "is_carousel_item": "true"}
        cid, loi = await _tao_container(spec, ig, form)
        if loi:
            return loi
        con.append(cid)
    hoi = HOI_VIDEO if co_video else HOI_ANH
    for cid in con:
        tt, loi = await cho_container(spec, cid, *hoi)
        if loi:
            return loi
        if tt == "CHUA_XONG":
            return k.json_ra({"trang_thai": "IN_PROGRESS", "children": con,
                              "ghi_chu": "Meta còn xử lý video trong carousel, CHƯA đăng. Thử đăng lại sau vài phút."})
    form = {"media_type": "CAROUSEL", "children": ",".join(con)}
    if caption:
        form["caption"] = caption
    cha, loi = await _tao_container(spec, ig, form)
    if loi:
        return loi
    tt, loi = await cho_container(spec, cha, *HOI_ANH)
    if loi:
        return loi
    if tt == "CHUA_XONG":
        return _chua_xong(cha)
    return await _xuat_ban(spec, ig, cha)


# ------------------------------------------------------------------ cổng
async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "access_token", "ig_user_id")
    if t:
        return "ERROR: kết nối Instagram thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    if not _MA_TK.match(str(sec.get("ig_user_id")).strip()):
        return "ERROR: Instagram User ID không hợp lệ (thường là dãy số, ví dụ 17841400000000000)"
    if tool not in {x["name"] for x in TOOLS}:
        return f"ERROR: tool '{tool}' không có trong cầu nối Instagram"
    a = arguments or {}
    loi = _kiem_dau_vao(tool, a)
    if loi:
        return loi
    await _lam_moi_neu_can(spec)
    ra = await _xu_ly(tool, a, spec)
    sec = k.bi_mat(spec)
    an = _an(sec)
    if str(sec.get("app_secret") or "").strip():
        an["_proof"] = appsecret_proof(str(sec["app_secret"]).strip(), str(sec.get("access_token") or "").strip())
    return k.giau(ra, an)


def _ma(a, ten):
    v = str(a.get(ten) or "").strip()
    return v if _MA.match(v) else None


def _kiem_dau_vao(tool, a):
    """Kiểm mọi tham số TRƯỚC khi chạm mạng."""
    if tool in ("instagram_chi_so_bai", "instagram_binh_luan") and not _ma(a, "media_id"):
        return "ERROR: media_id phải là dãy số (mã bài Instagram)"
    if tool in ("instagram_trang_thai_container", "instagram_dang_container") and not _ma(a, "creation_id"):
        return "ERROR: creation_id phải là dãy số (mã container)"
    if tool == "instagram_chi_so_bai" and a.get("metric") not in (None, ""):
        if not _CHI_SO.match(str(a["metric"]).replace(" ", "")):
            return "ERROR: metric phải là các tên chỉ số cách nhau dấu phẩy, ví dụ reach,likes"
    if tool == "instagram_dang_anh":
        return kiem_url(a.get("image_url"), "image_url") or kiem_caption(a.get("caption"))
    if tool == "instagram_dang_reel":
        return kiem_url(a.get("video_url"), "video_url") or kiem_caption(a.get("caption"))
    if tool == "instagram_dang_carousel":
        urls = a.get("media_urls")
        if isinstance(urls, str):
            urls = k.ds(urls)
        if not isinstance(urls, list) or not (CAROUSEL_IT <= len(urls) <= CAROUSEL_NHIEU):
            n = len(urls) if isinstance(urls, list) else 0
            return f"ERROR: carousel cần {CAROUSEL_IT} đến {CAROUSEL_NHIEU} mục, đang có {n}"
        for i, u in enumerate(urls, 1):
            loi = kiem_url(u, f"mục {i}")
            if loi:
                return loi
        return kiem_caption(a.get("caption"))
    if tool == "instagram_tra_loi_binh_luan":
        if not _ma(a, "comment_id"):
            return "ERROR: comment_id phải là dãy số (mã bình luận)"
        m = a.get("message")
        if not isinstance(m, str) or not m.strip():
            return "ERROR: thiếu nội dung trả lời (message)"
        if len(m) > BINH_LUAN_TOI_DA:
            return f"ERROR: trả lời dài {len(m)} ký tự, tối đa {BINH_LUAN_TOI_DA}"
    return None


async def _xu_ly(tool, a, spec):
    ig = str(k.bi_mat(spec)["ig_user_id"]).strip()
    if tool == "instagram_tai_khoan":
        ok, d = await _api(spec, "GET", f"/{ig}", {
            "fields": "id,username,name,biography,website,followers_count,follows_count,media_count,"
                      "profile_picture_url"})
    elif tool == "instagram_bai_gan_day":
        q = {"fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count",
             "limit": k.so(a.get("limit"), 12, 1, 50)}
        if str(a.get("after") or "").strip():
            q["after"] = str(a["after"]).strip()[:500]
        ok, d = await _api(spec, "GET", f"/{ig}/media", q)
    elif tool == "instagram_chi_so_bai":
        metric = str(a.get("metric") or "").replace(" ", "") or CHI_SO_MAC_DINH
        ok, d = await _api(spec, "GET", f"/{_ma(a, 'media_id')}/insights", {"metric": metric})
    elif tool == "instagram_binh_luan":
        q = {"fields": "id,text,username,timestamp,like_count", "limit": k.so(a.get("limit"), 25, 1, 50)}
        if str(a.get("after") or "").strip():
            q["after"] = str(a["after"]).strip()[:500]
        ok, d = await _api(spec, "GET", f"/{_ma(a, 'media_id')}/comments", q)
    elif tool == "instagram_han_muc_dang":
        ok, d = await _han_muc(spec, ig)
    elif tool == "instagram_trang_thai_container":
        ok, d = await _api(spec, "GET", f"/{_ma(a, 'creation_id')}", {"fields": "id,status_code,status"})
    elif tool == "instagram_dang_anh":
        form = {"image_url": a["image_url"].strip()}
        if a.get("caption"):
            form["caption"] = a["caption"]
        return await _dang_mot(spec, ig, form, HOI_ANH)
    elif tool == "instagram_dang_reel":
        form = {"media_type": "REELS", "video_url": a["video_url"].strip(),
                "share_to_feed": "false" if a.get("share_to_feed") is False else "true"}
        if a.get("caption"):
            form["caption"] = a["caption"]
        return await _dang_mot(spec, ig, form, HOI_VIDEO)
    elif tool == "instagram_dang_carousel":
        urls = a["media_urls"] if isinstance(a["media_urls"], list) else k.ds(a["media_urls"])
        return await _dang_carousel(spec, ig, urls, a.get("caption") or "")
    elif tool == "instagram_dang_container":
        cid = _ma(a, "creation_id")
        loi = await _con_han_muc(spec, ig)
        if loi:
            return loi
        tt, loi = await cho_container(spec, cid, 1, 0)
        if loi:
            return loi
        if tt == "CHUA_XONG":
            return _chua_xong(cid)
        if tt == "PUBLISHED":
            return k.json_ra({"da_dang": True, "creation_id": cid, "ghi_chu": "container này đã được đăng trước đó"})
        return await _xuat_ban(spec, ig, cid)
    else:   # instagram_tra_loi_binh_luan
        ok, d = await _api(spec, "POST", f"/{_ma(a, 'comment_id')}/replies", data={"message": a["message"]})
    return k.json_ra(d) if ok else d
