"""Cầu nối Threads API (graph.threads.net/v1.0, transport "internal"). Mỗi kết nối = MỘT hồ sơ Threads.

Luồng đăng (tài liệu "Threads Posts" của Meta):
  1. POST /{user-id}/threads tạo container: media_type TEXT (text) | IMAGE (image_url) |
     VIDEO (video_url) | CAROUSEL (children = các container con is_carousel_item=true).
     Trả lời một bài = cùng lệnh đó kèm reply_to_id.
  2. GET /{container-id}?fields=status,error_message hỏi tới khi FINISHED (ERROR / EXPIRED là
     hỏng). Meta khuyên chờ trung bình 30 giây; MinMin hỏi có GIỚI HẠN, hết lượt mà chưa xong
     thì trả creation_id để đăng sau bằng `threads_dang_container`, không treo lượt chat.
  3. POST /{user-id}/threads_publish creation_id=...
Trước khi đăng hỏi GET /{user-id}/threads_publishing_limit (250 bài và 1000 trả lời mỗi 24 giờ);
chạm trần thì từ chối luôn.

Giới hạn đã kiểm trên tài liệu Meta: chữ tối đa 500 ký tự, carousel 2 đến 20 mục, ảnh JPEG/PNG,
video MOV/MP4. Ảnh, video phải ở link https CÔNG KHAI.

Token dài hạn sống 60 ngày, làm mới bằng GET https://graph.threads.net/refresh_access_token
?grant_type=th_refresh_token khi token cũ hơn 24 giờ. MinMin tự làm mới khi còn dưới 7 ngày
(hoặc chưa biết hạn), qua khoá của kết nối, lưu token mới bằng luu_bi_mat. Làm mới hỏng thì
lùi 6 giờ mới thử lại; lượt gọi vẫn chạy bằng token cũ.

Có ô app_secret thì gửi kèm appsecret_proof = HMAC-SHA256(app_secret, access_token) dạng hex.

Tool nguy hiểm (mức Toàn quyền): đăng bài (chữ, ảnh, video, carousel), đăng container có sẵn, trả
lời bài. Bài đăng là CÔNG KHAI.
"""
import asyncio
import hashlib
import hmac
import re
import time
from urllib.parse import urlparse

import ket_noi_api as k

HOST = "https://graph.threads.net"
PHIEN_BAN = "v1.0"
TEN = "Threads"
CONG_KHAI = ("token_het_han", "token_lam_moi_luc", "thu_lam_moi_luc")
CHU_TOI_DA = 500
CAROUSEL_IT, CAROUSEL_NHIEU = 2, 20
DUOI_VIDEO = (".mp4", ".mov", ".m4v")
LOAI = ("TEXT", "IMAGE", "VIDEO", "CAROUSEL")
CHI_SO_BAI = "views,likes,replies,reposts,quotes,shares"
CHI_SO_TK = "views,likes,replies,reposts,quotes,followers_count"
_CHI_SO = re.compile(r"^[a-z_]{2,48}(,[a-z_]{2,48}){0,19}$")
_MA = re.compile(r"^[0-9]{1,40}$")
_MA_TK = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

HOI_ANH = (10, 3.0)
HOI_VIDEO = (36, 5.0)
LAM_MOI_TRUOC = 7 * 86400
TUOI_TOI_THIEU = 86400
LUI_KHI_HONG = 6 * 3600


async def _ngu(giay):       # tách ra để test thay bằng hàm không chờ
    await asyncio.sleep(giay)


_BAI = {"thread_id": {"type": "string", "description": "mã bài Threads (dãy số)"}}

TOOLS = [
    k.tool("threads_ho_so", "Hồ sơ Threads đang kết nối: mã, username, tên, tiểu sử, ảnh đại diện."),
    k.tool("threads_bai_gan_day",
           "Các bài gần nhất của hồ sơ: mã, nội dung, loại, link, thời gian.",
           {"limit": {"type": "integer", "description": "số bài, tối đa 50, mặc định 12"},
            "after": {"type": "string", "description": "con trỏ trang sau (paging.cursors.after)"}}),
    k.tool("threads_chi_so_bai",
           "Chỉ số một bài: lượt xem, thích, trả lời, đăng lại, trích dẫn, chia sẻ.",
           {**_BAI, "metric": {"type": "string", "description": "mặc định " + CHI_SO_BAI}}, ["thread_id"]),
    k.tool("threads_chi_so_tai_khoan",
           "Chỉ số cả hồ sơ trong một khoảng ngày: lượt xem, thích, trả lời, đăng lại, trích dẫn, số người "
           "theo dõi. Mặc định 7 ngày gần nhất.",
           {**k.NGAY_PROPS, "metric": {"type": "string", "description": "mặc định " + CHI_SO_TK}}),
    k.tool("threads_tra_loi_cua_bai",
           "Các trả lời của một bài (mặc định chỉ tầng đầu; tat_ca=true lấy cả trả lời lồng nhau).",
           {**_BAI, "tat_ca": {"type": "boolean", "description": "lấy mọi tầng trả lời"},
            "after": {"type": "string", "description": "con trỏ trang sau"}}, ["thread_id"]),
    k.tool("threads_han_muc_dang", "Số bài và số trả lời đã đăng qua API trong 24 giờ qua, so với hạn mức."),
    k.tool("threads_trang_thai_container",
           "Trạng thái một container đang xử lý (IN_PROGRESS, FINISHED, ERROR, EXPIRED, PUBLISHED).",
           {"creation_id": {"type": "string", "description": "mã container (dãy số)"}}, ["creation_id"]),
    k.tool("threads_dang_bai",
           "ĐĂNG CÔNG KHAI một bài Threads: chỉ chữ, một ảnh, một video, hoặc carousel 2 đến 20 ảnh/video "
           "(link .mp4/.mov là video). Ảnh, video ở link https công khai. Chỉ đăng khi người dùng yêu cầu rõ.",
           {"text": {"type": "string", "description": f"nội dung, tối đa {CHU_TOI_DA} ký tự"},
            "image_url": {"type": "string", "description": "link https công khai tới một ảnh JPEG/PNG"},
            "video_url": {"type": "string", "description": "link https công khai tới một video MP4/MOV"},
            "media_urls": {"type": "array", "items": {"type": "string"},
                           "description": f"carousel: {CAROUSEL_IT} đến {CAROUSEL_NHIEU} link https"}}),
    k.tool("threads_dang_container",
           "ĐĂNG CÔNG KHAI một container đã tạo trước đó (khi lần đăng trước báo video còn đang xử lý).",
           {"creation_id": {"type": "string", "description": "mã container (dãy số)"}}, ["creation_id"]),
    k.tool("threads_tra_loi",
           "TRẢ LỜI CÔNG KHAI một bài hoặc một trả lời trên Threads. Chỉ trả lời khi người dùng yêu cầu rõ.",
           {"reply_to_id": {"type": "string", "description": "mã bài hoặc trả lời cần đáp (dãy số)"},
            "text": {"type": "string", "description": f"nội dung, tối đa {CHU_TOI_DA} ký tự"}},
           ["reply_to_id", "text"]),
]


async def list_tools(spec):
    return TOOLS


def _an(sec):
    return {kk: v for kk, v in sec.items() if v and kk not in CONG_KHAI}


def appsecret_proof(app_secret, access_token):
    return hmac.new(str(app_secret).encode("utf-8"), str(access_token).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _so_thuc(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def kiem_url(url, ten="link"):
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


def kiem_chu(text, bat_buoc=False):
    if text in (None, ""):
        return "ERROR: thiếu nội dung (text)" if bat_buoc else None
    if not isinstance(text, str):
        return "ERROR: text phải là chuỗi"
    if bat_buoc and not text.strip():
        return "ERROR: thiếu nội dung (text)"
    if len(text) > CHU_TOI_DA:
        return f"ERROR: nội dung dài {len(text)} ký tự, Threads cho tối đa {CHU_TOI_DA}"
    return None


def _la_video(url):
    return urlparse(url.strip()).path.lower().endswith(DUOI_VIDEO)


# ------------------------------------------------------------------ token
async def _lam_moi_neu_can(spec):
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
        ok, d = await k.goi(TEN, "GET", f"{HOST}/refresh_access_token", secrets=_an(sec),
                            params={"grant_type": "th_refresh_token", "access_token": tok})
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


def _an_day_du(sec):
    an = _an(sec)
    if str(sec.get("app_secret") or "").strip():
        an["_proof"] = appsecret_proof(str(sec["app_secret"]).strip(), str(sec.get("access_token") or "").strip())
    return an


async def _api(spec, method, path, params=None, data=None):
    sec = k.bi_mat(spec)
    q = dict(params or {})
    q["access_token"] = str(sec.get("access_token") or "").strip()
    an = _an_day_du(sec)
    if "_proof" in an:
        q["appsecret_proof"] = an["_proof"]
    ok, d = await k.goi(TEN, method, f"{HOST}/{PHIEN_BAN}{path}", secrets=an, params=q, data=data, timeout=60)
    if not ok:
        if '"code": 190' in d or "OAuthException" in d:
            d += " | Token hỏng hoặc hết hạn: lấy token dài hạn mới rồi dán vào kết nối ở trang Kết nối."
        return False, d
    if isinstance(d, dict) and isinstance(d.get("error"), dict):
        return False, k.giau(f"ERROR: {TEN}: {d['error'].get('message', '')}", an)
    return True, d


# ------------------------------------------------------------------ đăng
async def _han_muc(spec, uid):
    return await _api(spec, "GET", f"/{uid}/threads_publishing_limit",
                      {"fields": "quota_usage,config,reply_quota_usage,reply_config"})


async def _con_han_muc(spec, uid, tra_loi=False):
    ok, d = await _han_muc(spec, uid)
    if not ok or not isinstance(d, dict):
        return None
    hang = d["data"][0] if isinstance(d.get("data"), list) and d["data"] else d
    if not isinstance(hang, dict):
        return None
    dung = _so_thuc(hang.get("reply_quota_usage" if tra_loi else "quota_usage"))
    tran = _so_thuc((hang.get("reply_config" if tra_loi else "config") or {}).get("quota_total"))
    if dung is not None and tran and dung >= tran:
        loai = "trả lời" if tra_loi else "bài"
        return (f"ERROR: hồ sơ đã đăng {int(dung)}/{int(tran)} {loai} qua API trong 24 giờ qua, chạm hạn mức "
                "của Meta. Chờ rồi đăng lại sau.")
    return None


async def _tao_container(spec, uid, form):
    ok, d = await _api(spec, "POST", f"/{uid}/threads", data=form)
    if not ok:
        return None, d
    cid = str((d or {}).get("id") or "") if isinstance(d, dict) else ""
    if not cid:
        return None, "ERROR: Threads không trả mã container"
    return cid, None


async def cho_container(spec, cid, so_lan, nghi):
    """Hỏi trạng thái tới khi FINISHED. Trả (trạng_thái, lỗi); 'CHUA_XONG' khi hết lượt."""
    for i in range(so_lan):
        ok, d = await _api(spec, "GET", f"/{cid}", {"fields": "status,error_message"})
        if not ok:
            return None, d
        ma = str((d or {}).get("status") or "").upper() if isinstance(d, dict) else ""
        if ma in ("FINISHED", "PUBLISHED"):
            return ma, None
        if ma in ("ERROR", "EXPIRED"):
            chi_tiet = str((d or {}).get("error_message") or "").strip()
            return None, (f"ERROR: container {cid} báo {ma}" + (f": {chi_tiet}" if chi_tiet else "")
                          + ". Kiểm tra định dạng (ảnh JPEG/PNG; video MP4/MOV) và link công khai rồi đăng lại.")
        if i < so_lan - 1:
            await _ngu(nghi)
    return "CHUA_XONG", None


def _chua_xong(cid):
    return k.json_ra({"trang_thai": "IN_PROGRESS", "creation_id": cid,
                      "ghi_chu": "Meta còn đang xử lý, CHƯA đăng. Vài phút nữa gọi threads_dang_container với "
                                 "creation_id này để đăng."})


async def _xuat_ban(spec, uid, cid):
    ok, d = await _api(spec, "POST", f"/{uid}/threads_publish", data={"creation_id": cid})
    if not ok:
        return d
    mid = str((d or {}).get("id") or "") if isinstance(d, dict) else ""
    ra = {"da_dang": True, "thread_id": mid, "creation_id": cid}
    if mid:
        ok2, d2 = await _api(spec, "GET", f"/{mid}", {"fields": "permalink"})
        if ok2 and isinstance(d2, dict) and d2.get("permalink"):
            ra["permalink"] = d2["permalink"]
    return k.json_ra(ra)


async def _dang(spec, uid, a, reply_to=None):
    loi = await _con_han_muc(spec, uid, tra_loi=bool(reply_to))
    if loi:
        return loi
    text = a.get("text") or ""
    urls = _ds_carousel(a)
    hoi = HOI_ANH
    if urls:
        con = []
        for u in urls:
            if _la_video(u):
                hoi = HOI_VIDEO
                form = {"media_type": "VIDEO", "video_url": u.strip(), "is_carousel_item": "true"}
            else:
                form = {"media_type": "IMAGE", "image_url": u.strip(), "is_carousel_item": "true"}
            cid, loi = await _tao_container(spec, uid, form)
            if loi:
                return loi
            con.append(cid)
        for cid in con:
            tt, loi = await cho_container(spec, cid, *hoi)
            if loi:
                return loi
            if tt == "CHUA_XONG":
                return k.json_ra({"trang_thai": "IN_PROGRESS", "children": con,
                                  "ghi_chu": "Meta còn xử lý video trong carousel, CHƯA đăng. Thử lại sau vài phút."})
        form = {"media_type": "CAROUSEL", "children": ",".join(con)}
        hoi = HOI_ANH
    elif str(a.get("video_url") or "").strip():
        form = {"media_type": "VIDEO", "video_url": a["video_url"].strip()}
        hoi = HOI_VIDEO
    elif str(a.get("image_url") or "").strip():
        form = {"media_type": "IMAGE", "image_url": a["image_url"].strip()}
    else:
        form = {"media_type": "TEXT"}
    if text:
        form["text"] = text
    if reply_to:
        form["reply_to_id"] = reply_to
    cid, loi = await _tao_container(spec, uid, form)
    if loi:
        return loi
    tt, loi = await cho_container(spec, cid, *hoi)
    if loi:
        return loi
    if tt == "CHUA_XONG":
        return _chua_xong(cid)
    return await _xuat_ban(spec, uid, cid)


def _ds_carousel(a):
    v = a.get("media_urls")
    if v in (None, "", []):
        return []
    return v if isinstance(v, list) else k.ds(v)


# ------------------------------------------------------------------ cổng
async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "access_token", "threads_user_id")
    if t:
        return "ERROR: kết nối Threads thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    if not _MA_TK.match(str(sec.get("threads_user_id")).strip()):
        return "ERROR: Threads User ID không hợp lệ (dãy số, hoặc ghi me)"
    if tool not in {x["name"] for x in TOOLS}:
        return f"ERROR: tool '{tool}' không có trong cầu nối Threads"
    a = arguments or {}
    loi = _kiem_dau_vao(tool, a)
    if loi:
        return loi
    await _lam_moi_neu_can(spec)
    ra = await _xu_ly(tool, a, spec)
    return k.giau(ra, _an_day_du(k.bi_mat(spec)))


def _ma(a, ten):
    v = str(a.get(ten) or "").strip()
    return v if _MA.match(v) else None


def _kiem_dau_vao(tool, a):
    if tool in ("threads_chi_so_bai", "threads_tra_loi_cua_bai") and not _ma(a, "thread_id"):
        return "ERROR: thread_id phải là dãy số (mã bài Threads)"
    if tool in ("threads_trang_thai_container", "threads_dang_container") and not _ma(a, "creation_id"):
        return "ERROR: creation_id phải là dãy số (mã container)"
    if tool in ("threads_chi_so_bai", "threads_chi_so_tai_khoan") and a.get("metric") not in (None, ""):
        if not _CHI_SO.match(str(a["metric"]).replace(" ", "")):
            return "ERROR: metric phải là các tên chỉ số cách nhau dấu phẩy, ví dụ views,likes"
    if tool == "threads_tra_loi":
        if not _ma(a, "reply_to_id"):
            return "ERROR: reply_to_id phải là dãy số (mã bài hoặc trả lời)"
        return kiem_chu(a.get("text"), bat_buoc=True)
    if tool == "threads_dang_bai":
        urls = _ds_carousel(a)
        if a.get("media_urls") not in (None, "", []) and not isinstance(a.get("media_urls"), (list, str)):
            return "ERROR: media_urls phải là danh sách link"
        co = [x for x in ("image_url", "video_url") if str(a.get(x) or "").strip()]
        if urls and co or len(co) > 1:
            return "ERROR: mỗi bài chỉ chọn MỘT kiểu: image_url, video_url hoặc media_urls (carousel)"
        if urls:
            if not (CAROUSEL_IT <= len(urls) <= CAROUSEL_NHIEU):
                return f"ERROR: carousel cần {CAROUSEL_IT} đến {CAROUSEL_NHIEU} mục, đang có {len(urls)}"
            for i, u in enumerate(urls, 1):
                loi = kiem_url(u, f"mục {i}")
                if loi:
                    return loi
        for x in co:
            loi = kiem_url(a.get(x), x)
            if loi:
                return loi
        return kiem_chu(a.get("text"), bat_buoc=not (urls or co))
    return None


async def _xu_ly(tool, a, spec):
    uid = str(k.bi_mat(spec)["threads_user_id"]).strip()
    if tool == "threads_ho_so":
        ok, d = await _api(spec, "GET", f"/{uid}", {
            "fields": "id,username,name,threads_profile_picture_url,threads_biography"})
    elif tool == "threads_bai_gan_day":
        q = {"fields": "id,media_product_type,media_type,permalink,text,timestamp,shortcode,is_quote_post",
             "limit": k.so(a.get("limit"), 12, 1, 50)}
        if str(a.get("after") or "").strip():
            q["after"] = str(a["after"]).strip()[:500]
        ok, d = await _api(spec, "GET", f"/{uid}/threads", q)
    elif tool == "threads_chi_so_bai":
        metric = str(a.get("metric") or "").replace(" ", "") or CHI_SO_BAI
        ok, d = await _api(spec, "GET", f"/{_ma(a, 'thread_id')}/insights", {"metric": metric})
    elif tool == "threads_chi_so_tai_khoan":
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        tu = max(tu, 1712991600)     # mốc sớm nhất Meta hỗ trợ (13/04/2024)
        metric = str(a.get("metric") or "").replace(" ", "") or CHI_SO_TK
        ok, d = await _api(spec, "GET", f"/{uid}/threads_insights", {"metric": metric, "since": tu, "until": den})
    elif tool == "threads_tra_loi_cua_bai":
        duong = "conversation" if a.get("tat_ca") is True else "replies"
        q = {"fields": "id,text,username,timestamp,media_type,has_replies,is_reply,hide_status", "reverse": "false"}
        if str(a.get("after") or "").strip():
            q["after"] = str(a["after"]).strip()[:500]
        ok, d = await _api(spec, "GET", f"/{_ma(a, 'thread_id')}/{duong}", q)
    elif tool == "threads_han_muc_dang":
        ok, d = await _han_muc(spec, uid)
    elif tool == "threads_trang_thai_container":
        ok, d = await _api(spec, "GET", f"/{_ma(a, 'creation_id')}", {"fields": "id,status,error_message"})
    elif tool == "threads_dang_bai":
        return await _dang(spec, uid, a)
    elif tool == "threads_tra_loi":
        return await _dang(spec, uid, {"text": a["text"]}, reply_to=_ma(a, "reply_to_id"))
    else:   # threads_dang_container
        cid = _ma(a, "creation_id")
        loi = await _con_han_muc(spec, uid)
        if loi:
            return loi
        tt, loi = await cho_container(spec, cid, 1, 0)
        if loi:
            return loi
        if tt == "CHUA_XONG":
            return _chua_xong(cid)
        if tt == "PUBLISHED":
            return k.json_ra({"da_dang": True, "creation_id": cid, "ghi_chu": "container này đã được đăng trước đó"})
        return await _xuat_ban(spec, uid, cid)
    return k.json_ra(d) if ok else d
