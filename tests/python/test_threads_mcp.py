"""Cầu nối Threads (server/threads_mcp.py). Không mạng, không chờ thật.

    python tests/run.py threads_mcp

Phủ: đăng chữ / ảnh / video / carousel qua container -> hỏi trạng thái (IN_PROGRESS rồi
FINISHED) -> threads_publish, hỏi có giới hạn, ERROR báo rõ và không đăng, trả lời bằng
reply_to_id và hạn mức trả lời riêng, hạn mức 24 giờ chặn trước khi tạo container, kiểm đầu
vào (500 ký tự, carousel 2 đến 20, https công khai, một kiểu mỗi bài) không chạm mạng,
appsecret_proof đúng HMAC độc lập, làm mới token th_refresh_token lưu lại, lỗi không lộ bí
mật, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-threads-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import threads_mcp as th  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

ngu_goi = []


async def _ngu_gia(giay):
    ngu_goi.append(giay)

th._ngu = _ngu_gia

TOK = "THQWJtoken-dai-han-0000001"
SECRET = "threads-app-secret-ABC12345"
UID = "26000000000000001"
CON_LAU = str(int(time.time()) + 40 * 86400)
G = "https://graph.threads.net/v1.0"


def spec(**them):
    sec = {"access_token": TOK, "threads_user_id": UID, "token_het_han": CON_LAU}
    sec.update(them)
    return {"key": "conn-threads-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def han_muc(gia, dung=3, tran=250, rdung=0, rtran=1000):
    gia.tra("/threads_publishing_limit", {"data": [{
        "quota_usage": dung, "config": {"quota_total": tran, "quota_duration": 86400},
        "reply_quota_usage": rdung, "reply_config": {"quota_total": rtran, "quota_duration": 86400}}]})


def luu_gop():
    ra = {}
    for _c, p in da_luu:
        ra.update(p["fields"])
    return ra


def tao(gia):
    return [x for x in gia.goi if x["url"] == f"{G}/{UID}/threads" and x["method"] == "POST"]


def pub(gia):
    return [x for x in gia.goi if x["url"].endswith("/threads_publish")]


# ---- 1. thiếu ô, tool lạ ----
check("thiếu access_token -> báo rõ", "access_token" in chay(th.call("threads_ho_so", {}, {"secrets": {"threads_user_id": UID}})))
check("thiếu threads_user_id -> báo rõ", "threads_user_id" in chay(th.call("threads_ho_so", {}, {"secrets": {"access_token": TOK}})))
check("tool lạ -> lỗi", chay(th.call("threads_xoa_bai", {}, spec())).startswith("ERROR"))

# ---- 2. hồ sơ + appsecret_proof ----
gia = GiaHttp().lap()
gia.tra("graph.threads.net", {"id": UID, "username": "halimi.vn"})
ra = chay(th.call("threads_ho_so", {}, spec(app_secret=SECRET)))
g = gia.goi[-1]
check("hồ sơ: đúng host + path", g["url"] == f"{G}/{UID}", g["url"])
check("hồ sơ: fields username", "username" in g["params"]["fields"] and "threads_biography" in g["params"]["fields"])
mong = hmac.new(SECRET.encode(), TOK.encode(), hashlib.sha256).hexdigest()
check("appsecret_proof = HMAC-SHA256(secret, token) hex", g["params"].get("appsecret_proof") == mong)
check("hàm proof khớp HMAC độc lập", th.appsecret_proof(SECRET, TOK) == mong)
check("kết quả có username, không lộ token", "halimi.vn" in ra and TOK not in ra)
chay(th.call("threads_ho_so", {}, spec()))
check("không app_secret thì không gửi proof", "appsecret_proof" not in gia.goi[-1]["params"])
gia.go()

# ---- 3. đăng chữ: container -> IN_PROGRESS -> FINISHED -> publish ----
ngu_goi.clear()
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/threads", {"id": "5001"})
gia.tra("/5001", {"status": "IN_PROGRESS"})
gia.tra("/5001", {"status": "FINISHED"})
gia.tra(f"/{UID}/threads_publish", {"id": "18100000000000001"})
gia.tra("/18100000000000001", {"permalink": "https://www.threads.net/@halimi.vn/post/ABC"})
ra = chay(th.call("threads_dang_bai", {"text": "Xin chào Threads"}, spec()))
check("đăng chữ thành công có permalink", '"da_dang": true' in ra and "post/ABC" in ra, ra)
t = tao(gia)
check("container TEXT đúng form", len(t) == 1 and t[0]["data"] == {"media_type": "TEXT", "text": "Xin chào Threads"}, t and t[0]["data"])
hoi = [x for x in gia.goi if x["url"].endswith("/5001")]
check("hỏi trạng thái 2 lần, fields status,error_message", len(hoi) == 2 and hoi[0]["params"]["fields"] == "status,error_message")
check("nghỉ 1 lần giữa hai lần hỏi (sleep giả)", len(ngu_goi) == 1)
p = pub(gia)
check("publish một lần với creation_id", len(p) == 1 and p[0]["data"] == {"creation_id": "5001"} and p[0]["method"] == "POST")
gia.go()

# ---- 4. ảnh, video, hết lượt hỏi ----
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/threads", {"id": "5002"})
gia.tra("/5002", {"status": "FINISHED"})
gia.tra(f"/{UID}/threads_publish", {"id": "1"})
chay(th.call("threads_dang_bai", {"text": "Ảnh mới", "image_url": "https://cdn.vi.du/a.png"}, spec()))
check("container IMAGE đúng form", tao(gia)[0]["data"] == {"media_type": "IMAGE", "image_url": "https://cdn.vi.du/a.png",
                                                           "text": "Ảnh mới"}, tao(gia)[0]["data"])
gia.go()

gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/threads", {"id": "5003"})
gia.tra("/5003", {"status": "IN_PROGRESS"})
ra = chay(th.call("threads_dang_bai", {"video_url": "https://cdn.vi.du/v.mp4"}, spec()))
check("video: container VIDEO", tao(gia)[0]["data"] == {"media_type": "VIDEO", "video_url": "https://cdn.vi.du/v.mp4"})
check("hết lượt: IN_PROGRESS + creation_id", "IN_PROGRESS" in ra and "5003" in ra and "threads_dang_container" in ra, ra)
check("hết lượt: số lần hỏi có giới hạn", len([x for x in gia.goi if x["url"].endswith("/5003")]) == th.HOI_VIDEO[0])
check("hết lượt: KHÔNG publish", not pub(gia))
gia.go()

gia = GiaHttp().lap()
han_muc(gia)
gia.tra("/5003", {"status": "FINISHED"})
gia.tra(f"/{UID}/threads_publish", {"id": "18100000000000003"})
ra = chay(th.call("threads_dang_container", {"creation_id": "5003"}, spec()))
check("đăng container có sẵn khi FINISHED", len(pub(gia)) == 1 and '"da_dang": true' in ra, ra)
gia.go()

# ---- 5. ERROR ----
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/threads", {"id": "5004"})
gia.tra("/5004", {"status": "ERROR", "error_message": "FAILED_DOWNLOADING_VIDEO"})
ra = chay(th.call("threads_dang_bai", {"video_url": "https://cdn.vi.du/v.mp4"}, spec()))
check("ERROR -> báo lý do", ra.startswith("ERROR") and "FAILED_DOWNLOADING_VIDEO" in ra, ra)
check("ERROR -> không publish", not pub(gia))
gia.go()

# ---- 6. carousel ----
gia = GiaHttp().lap()
han_muc(gia)
for c in ("6001", "6002", "6100"):
    gia.tra(f"/{UID}/threads", {"id": c})
    gia.tra("/" + c, {"status": "FINISHED"})
gia.tra(f"/{UID}/threads_publish", {"id": "1"})
chay(th.call("threads_dang_bai", {"text": "BST", "media_urls": ["https://a.b/1.jpg", "https://a.b/2.mov"]}, spec()))
d = [x["data"] for x in tao(gia)]
check("carousel: 3 container", len(d) == 3, d)
check("carousel: con IMAGE + VIDEO is_carousel_item",
      d[0] == {"media_type": "IMAGE", "image_url": "https://a.b/1.jpg", "is_carousel_item": "true"}
      and d[1] == {"media_type": "VIDEO", "video_url": "https://a.b/2.mov", "is_carousel_item": "true"}, d[:2])
check("carousel: cha CAROUSEL + children + text", d[2] == {"media_type": "CAROUSEL", "children": "6001,6002", "text": "BST"}, d[2])
check("carousel: publish cha", pub(gia)[0]["data"] == {"creation_id": "6100"})
gia.go()

# ---- 7. trả lời ----
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/threads", {"id": "5005"})
gia.tra("/5005", {"status": "FINISHED"})
gia.tra(f"/{UID}/threads_publish", {"id": "1"})
chay(th.call("threads_tra_loi", {"reply_to_id": "18100000000000009", "text": "Cảm ơn bạn"}, spec()))
check("trả lời: container TEXT + reply_to_id", tao(gia)[0]["data"] == {"media_type": "TEXT", "text": "Cảm ơn bạn",
                                                                       "reply_to_id": "18100000000000009"})
gia.go()

gia = GiaHttp().lap()
han_muc(gia, rdung=1000)
ra = chay(th.call("threads_tra_loi", {"reply_to_id": "1810", "text": "hi"}, spec()))
check("chạm hạn mức trả lời -> ERROR", ra.startswith("ERROR") and "1000/1000" in ra, ra)
check("chạm hạn mức trả lời -> không tạo container", not tao(gia))
gia.go()

# ---- 8. hạn mức bài ----
gia = GiaHttp().lap()
han_muc(gia, dung=250)
ra = chay(th.call("threads_dang_bai", {"text": "x"}, spec()))
check("chạm hạn mức bài -> ERROR", ra.startswith("ERROR") and "250/250" in ra, ra)
check("chạm hạn mức bài -> không tạo container", not tao(gia))
gia.go()

# ---- 9. kiểm đầu vào, không chạm mạng ----
gia = GiaHttp().lap()
sai = [
    ({"text": "a" * 501}, "chữ 501 ký tự"),
    ({}, "bài rỗng"),
    ({"text": "   "}, "chỉ khoảng trắng"),
    ({"image_url": "http://a.b/x.jpg"}, "ảnh http"),
    ({"video_url": "file:///v.mp4"}, "video file"),
    ({"image_url": "https://127.0.0.1/x.jpg"}, "ảnh localhost"),
    ({"image_url": "https://a.b/x.jpg", "video_url": "https://a.b/v.mp4"}, "hai kiểu một lúc"),
    ({"media_urls": ["https://a.b/1.jpg"]}, "carousel 1 mục"),
    ({"media_urls": [f"https://a.b/{i}.jpg" for i in range(21)]}, "carousel 21 mục"),
    ({"media_urls": ["https://a.b/1.jpg", "http://a.b/2.jpg"]}, "carousel có http"),
    ({"media_urls": ["https://a.b/1.jpg", "https://a.b/2.jpg"], "image_url": "https://a.b/3.jpg"}, "carousel + ảnh"),
    ({"text": "a" * 501, "image_url": "https://a.b/x.jpg"}, "ảnh kèm chữ quá dài"),
]
for args, ten in sai:
    check("đăng bài từ chối: " + ten, chay(th.call("threads_dang_bai", args, spec())).startswith("ERROR"))
for args, ten in [({"reply_to_id": "12", "text": ""}, "trả lời rỗng"), ({"reply_to_id": "x1", "text": "hi"}, "reply_to_id chữ"),
                  ({"reply_to_id": "12", "text": "a" * 501}, "trả lời quá dài")]:
    check("trả lời từ chối: " + ten, chay(th.call("threads_tra_loi", args, spec())).startswith("ERROR"))
check("chỉ số bài thread_id lạ", chay(th.call("threads_chi_so_bai", {"thread_id": "../me"}, spec())).startswith("ERROR"))
check("đầu vào sai không chạm mạng", gia.goi == [], [x["url"] for x in gia.goi][:3])
han_muc(gia)
gia.tra(f"/{UID}/threads", {"id": "5010"})
gia.tra("/5010", {"status": "FINISHED"})
gia.tra(f"/{UID}/threads_publish", {"id": "1"})
ra = chay(th.call("threads_dang_bai", {"text": "a" * 500}, spec()))
check("đúng 500 ký tự được nhận", '"da_dang": true' in ra, ra)
ra = chay(th.call("threads_dang_bai", {"media_urls": [f"https://a.b/{i}.jpg" for i in range(20)]}, spec()))
check("carousel 20 mục, không chữ được nhận", '"da_dang": true' in ra, ra)
ra = chay(th.call("threads_dang_bai", {"image_url": "https://a.b/x.jpg"}, spec()))
check("ảnh không chữ được nhận", '"da_dang": true' in ra, ra)
gia.go()

# ---- 10. đọc ----
gia = GiaHttp().lap()
gia.tra("graph.threads.net", {"data": []})
chay(th.call("threads_bai_gan_day", {"limit": 999}, spec()))
g = gia.goi[-1]
check("bài gần đây: GET /threads + limit 50", g["method"] == "GET" and g["url"] == f"{G}/{UID}/threads" and g["params"]["limit"] == 50)
chay(th.call("threads_chi_so_bai", {"thread_id": "1811"}, spec()))
g = gia.goi[-1]
check("chỉ số bài: /insights metric mặc định", g["url"].endswith("/1811/insights") and g["params"]["metric"] == th.CHI_SO_BAI)
chay(th.call("threads_chi_so_tai_khoan", {"tu_ngay": "2026-09-01", "den_ngay": "2026-09-07"}, spec()))
g = gia.goi[-1]
check("chỉ số tài khoản: /threads_insights since<until", g["url"].endswith(f"/{UID}/threads_insights")
      and g["params"]["since"] < g["params"]["until"])
chay(th.call("threads_chi_so_tai_khoan", {"tu_ngay": "2020-01-01", "den_ngay": "2024-05-01"}, spec()))
check("chỉ số tài khoản: không sớm hơn 13/04/2024", gia.goi[-1]["params"]["since"] >= 1712991600)
chay(th.call("threads_tra_loi_cua_bai", {"thread_id": "1811"}, spec()))
check("trả lời của bài: /replies", gia.goi[-1]["url"].endswith("/1811/replies"))
chay(th.call("threads_tra_loi_cua_bai", {"thread_id": "1811", "tat_ca": True}, spec()))
check("tất cả tầng: /conversation", gia.goi[-1]["url"].endswith("/1811/conversation"))
chay(th.call("threads_han_muc_dang", {}, spec()))
check("hạn mức: fields đủ", gia.goi[-1]["params"]["fields"] == "quota_usage,config,reply_quota_usage,reply_config")
gia.go()

# ---- 11. làm mới token ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra("refresh_access_token", {"access_token": "THQWJ-moi-3333333", "token_type": "bearer", "expires_in": 5183944})
gia.tra(f"{G}/{UID}", {"id": UID})
sp = spec(token_het_han=str(int(time.time()) + 86400))
chay(th.call("threads_ho_so", {}, sp))
lm = [x for x in gia.goi if "refresh_access_token" in x["url"]]
check("sắp hết hạn -> làm mới đúng endpoint", len(lm) == 1 and lm[0]["url"] == "https://graph.threads.net/refresh_access_token"
      and lm[0]["params"] == {"grant_type": "th_refresh_token", "access_token": TOK}, lm and lm[0])
luu = luu_gop()
check("token mới được LƯU", luu.get("access_token") == "THQWJ-moi-3333333" and all(c == "conn-threads-1" for c, _ in da_luu))
check("gọi API bằng token mới", gia.goi[-1]["params"]["access_token"] == "THQWJ-moi-3333333")
n = len(gia.goi)
chay(th.call("threads_ho_so", {}, sp))
check("không làm mới lần hai", not any("refresh_access_token" in x["url"] for x in gia.goi[n:]))
gia.go()


async def hai_luot(sp):
    return await asyncio.gather(th.call("threads_ho_so", {}, sp), th.call("threads_ho_so", {}, sp))

gia = GiaHttp().lap()
gia.tra("refresh_access_token", {"access_token": "THQWJ-moi-4444444", "expires_in": 5184000})
gia.tra(f"{G}/{UID}", {"id": UID})
asyncio.run(hai_luot(spec(token_het_han="")))
check("hai lượt song song chỉ làm mới một lần", len([x for x in gia.goi if "refresh_access_token" in x["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra("refresh_access_token", {"error": {"message": "bad " + TOK}}, code=400)
gia.tra(f"{G}/{UID}", {"id": UID, "username": "van.chay"})
ra = chay(th.call("threads_ho_so", {}, spec(token_het_han="")))
check("làm mới hỏng -> vẫn chạy bằng token cũ, không lộ", "van.chay" in ra and TOK not in ra, ra)
gia.go()

# ---- 12. không lộ bí mật ----
gia = GiaHttp().lap()
proof = th.appsecret_proof(SECRET, TOK)
gia.tra(f"{G}/{UID}", {"error": {"message": f"bad {TOK} {SECRET} {proof}", "type": "OAuthException", "code": 190}}, code=400)
ra = chay(th.call("threads_ho_so", {}, spec(app_secret=SECRET)))
check("lỗi API không lộ token/secret/proof", ra.startswith("ERROR") and all(s not in ra for s in (TOK, SECRET, proof)), ra)
gia.nem_loi(f"{G}/{UID}", ConnectionError(f"rớt access_token={TOK}&appsecret_proof={proof} {SECRET}"))
ra = chay(th.call("threads_ho_so", {}, spec(app_secret=SECRET)))
check("lỗi mạng không lộ bí mật", ra.startswith("ERROR") and all(s not in ra for s in (TOK, SECRET, proof)), ra)
gia.go()

# ---- 13. danh sách tool, văn bản sạch ----
ten = {x["name"] for x in chay(th.list_tools({}))}
check("đủ 10 tool", len(ten) == 10 and {"threads_dang_bai", "threads_tra_loi", "threads_dang_container"} <= ten, ten)
nguon = (SERVER / "threads_mcp.py").read_text(encoding="utf-8")
check("không có gạch dài", "\u2014" not in nguon and "\u2013" not in nguon)
check.ket_thuc()
