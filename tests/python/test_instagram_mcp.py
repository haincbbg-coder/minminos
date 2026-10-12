"""Cầu nối Instagram (server/instagram_mcp.py). Không mạng, không chờ thật.

    python tests/run.py instagram_mcp

Phủ: chọn host theo loại token, appsecret_proof đúng HMAC-SHA256 độc lập, luồng container ->
hỏi trạng thái (IN_PROGRESS rồi FINISHED) -> media_publish, hỏi có giới hạn (hết lượt trả
creation_id, không đăng), ERROR / EXPIRED báo rõ và không đăng, carousel (con rồi cha), Reel,
hạn mức 24 giờ chặn trước khi tạo container, kiểm đầu vào không chạm mạng, làm mới token
Instagram Login lưu lại và không làm mới token còn hạn hoặc token Facebook Login, lỗi không lộ
bí mật, thiếu ô, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-instagram-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import instagram_mcp as ig  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

ngu_goi = []


async def _ngu_gia(giay):
    ngu_goi.append(giay)

ig._ngu = _ngu_gia

TOK_IG = "IGQWRtoken-dai-han-0000001"
TOK_FB = "EAAGtoken-facebook-0000001"
SECRET = "app-secret-ig-ABCDEF123456"
UID = "17841400000000001"
CON_LAU = str(int(time.time()) + 40 * 86400)


def spec(tok=TOK_IG, **them):
    sec = {"access_token": tok, "ig_user_id": UID, "token_het_han": CON_LAU}
    sec.update(them)
    return {"key": "conn-ig-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def han_muc(gia, dung=3, tran=100):
    gia.tra("/content_publishing_limit", {"data": [{"quota_usage": dung,
                                                    "config": {"quota_total": tran, "quota_duration": 86400}}]})


def luu_gop():
    ra = {}
    for _c, p in da_luu:
        ra.update(p["fields"])
    return ra


# ---- 1. thiếu ô, tool lạ ----
check("thiếu access_token -> báo rõ", "access_token" in chay(ig.call("instagram_tai_khoan", {}, {"secrets": {"ig_user_id": UID}})))
check("thiếu ig_user_id -> báo rõ", "ig_user_id" in chay(ig.call("instagram_tai_khoan", {}, {"secrets": {"access_token": TOK_IG}})))
check("ig_user_id lạ -> lỗi", chay(ig.call("instagram_tai_khoan", {}, spec(ig_user_id="a/b?c"))).startswith("ERROR"))
check("tool lạ -> lỗi", chay(ig.call("instagram_xoa_bai", {}, spec())).startswith("ERROR"))

# ---- 2. host + appsecret_proof ----
gia = GiaHttp().lap()
gia.tra("graph.", {"id": UID, "username": "halimi.official"})
ra = chay(ig.call("instagram_tai_khoan", {}, spec()))
g = gia.goi[-1]
check("token IG -> graph.instagram.com", g["url"] == f"https://graph.instagram.com/v26.0/{UID}", g["url"])
check("tài khoản: có fields followers_count", "followers_count" in g["params"]["fields"])
check("không có app_secret thì không gửi proof", "appsecret_proof" not in g["params"])
check("kết quả không lộ token", TOK_IG not in ra and "halimi.official" in ra, ra)
chay(ig.call("instagram_tai_khoan", {}, spec(TOK_FB, app_secret=SECRET)))
g = gia.goi[-1]
check("token EAA -> graph.facebook.com", g["url"].startswith("https://graph.facebook.com/v26.0/"), g["url"])
mong = hmac.new(SECRET.encode(), TOK_FB.encode(), hashlib.sha256).hexdigest()
check("appsecret_proof = HMAC-SHA256(secret, token) hex", g["params"].get("appsecret_proof") == mong)
check("hàm proof khớp HMAC độc lập", ig.appsecret_proof(SECRET, TOK_IG)
      == hmac.new(SECRET.encode(), TOK_IG.encode(), hashlib.sha256).hexdigest())
check("token đi ở access_token", g["params"].get("access_token") == TOK_FB)
gia.go()

# ---- 3. đăng ảnh: container -> IN_PROGRESS -> FINISHED -> publish ----
ngu_goi.clear()
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/media", {"id": "9001"})
gia.tra("/9001", {"status_code": "IN_PROGRESS"})
gia.tra("/9001", {"status_code": "IN_PROGRESS"})
gia.tra("/9001", {"status_code": "FINISHED"})
gia.tra(f"/{UID}/media_publish", {"id": "18000000000000001"})
gia.tra("/18000000000000001", {"permalink": "https://www.instagram.com/p/ABC/"})
ra = chay(ig.call("instagram_dang_anh", {"image_url": "https://cdn.vi.du/a.jpg", "caption": "Váy mới #halimi"},
                  spec(app_secret=SECRET)))
check("đăng ảnh thành công có permalink", '"da_dang": true' in ra and "instagram.com/p/ABC" in ra, ra)
tao = [x for x in gia.goi if x["url"].endswith(f"/{UID}/media")][0]
check("tạo container POST đúng form", tao["method"] == "POST"
      and tao["data"] == {"image_url": "https://cdn.vi.du/a.jpg", "caption": "Váy mới #halimi"}, tao["data"])
check("tạo container gửi proof", tao["params"].get("appsecret_proof") == ig.appsecret_proof(SECRET, TOK_IG))
hoi = [x for x in gia.goi if x["url"].endswith("/9001")]
check("hỏi trạng thái 3 lần tới FINISHED", len(hoi) == 3 and hoi[0]["params"]["fields"] == "status_code,status")
check("nghỉ giữa các lần hỏi (2 lần, sleep giả)", len(ngu_goi) == 2)
pub = [x for x in gia.goi if "media_publish" in x["url"]]
check("publish đúng một lần với creation_id", len(pub) == 1 and pub[0]["data"] == {"creation_id": "9001"}
      and pub[0]["method"] == "POST")
thu_tu = [x["url"].rsplit("/", 1)[-1] for x in gia.goi]
check("thứ tự: hạn mức -> tạo -> hỏi -> đăng", thu_tu.index("content_publishing_limit") < thu_tu.index("media")
      < thu_tu.index("9001") < thu_tu.index("media_publish"), thu_tu)
gia.go()

# ---- 4. hết lượt hỏi -> không đăng, trả creation_id ----
ngu_goi.clear()
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/media", {"id": "9002"})
gia.tra("/9002", {"status_code": "IN_PROGRESS"})
ra = chay(ig.call("instagram_dang_reel", {"video_url": "https://cdn.vi.du/v.mp4"}, spec()))
check("hết lượt: báo IN_PROGRESS + creation_id", "IN_PROGRESS" in ra and "9002" in ra and "instagram_dang_container" in ra, ra)
check("hết lượt: số lần hỏi có giới hạn", len([x for x in gia.goi if x["url"].endswith("/9002")]) == ig.HOI_VIDEO[0])
check("hết lượt: KHÔNG gọi publish", not any("media_publish" in x["url"] for x in gia.goi))
tao = [x for x in gia.goi if x["url"].endswith(f"/{UID}/media")][0]
check("reel: media_type REELS + share_to_feed", tao["data"] == {"media_type": "REELS", "video_url": "https://cdn.vi.du/v.mp4",
                                                              "share_to_feed": "true"}, tao["data"])
gia.go()

gia = GiaHttp().lap()
han_muc(gia)
gia.tra("/9002", {"status_code": "FINISHED"})
gia.tra(f"/{UID}/media_publish", {"id": "18000000000000002"})
gia.tra("/18000000000000002", {"permalink": "https://www.instagram.com/reel/X/"})
ra = chay(ig.call("instagram_dang_container", {"creation_id": "9002"}, spec()))
check("đăng container có sẵn khi đã FINISHED", "reel/X" in ra and any("media_publish" in x["url"] for x in gia.goi), ra)
gia.go()

# ---- 5. ERROR / EXPIRED ----
for ma in ("ERROR", "EXPIRED"):
    gia = GiaHttp().lap()
    han_muc(gia)
    gia.tra(f"/{UID}/media", {"id": "9003"})
    gia.tra("/9003", {"status_code": ma, "status": "Error: 2207026 định dạng không hỗ trợ"})
    ra = chay(ig.call("instagram_dang_anh", {"image_url": "https://cdn.vi.du/a.jpg"}, spec()))
    check(f"container {ma} -> ERROR có lý do", ra.startswith("ERROR") and ma in ra and "2207026" in ra, ra)
    check(f"container {ma} -> không publish", not any("media_publish" in x["url"] for x in gia.goi))
    gia.go()

# ---- 6. carousel ----
gia = GiaHttp().lap()
han_muc(gia)
gia.tra(f"/{UID}/media", {"id": "7001"})
gia.tra(f"/{UID}/media", {"id": "7002"})
gia.tra(f"/{UID}/media", {"id": "7100"})
for c in ("7001", "7002", "7100"):
    gia.tra("/" + c, {"status_code": "FINISHED"})
gia.tra(f"/{UID}/media_publish", {"id": "18000000000000003"})
ra = chay(ig.call("instagram_dang_carousel", {"media_urls": ["https://cdn.vi.du/1.jpg", "https://cdn.vi.du/2.mp4"],
                                              "caption": "Bộ sưu tập"}, spec()))
tao = [x["data"] for x in gia.goi if x["url"].endswith(f"/{UID}/media")]
check("carousel: 3 container (2 con + 1 cha)", len(tao) == 3, tao)
check("carousel: con ảnh is_carousel_item", tao[0] == {"image_url": "https://cdn.vi.du/1.jpg", "is_carousel_item": "true"})
check("carousel: con video media_type VIDEO", tao[1] == {"media_type": "VIDEO", "video_url": "https://cdn.vi.du/2.mp4",
                                                         "is_carousel_item": "true"})
check("carousel: cha CAROUSEL + children + caption",
      tao[2] == {"media_type": "CAROUSEL", "children": "7001,7002", "caption": "Bộ sưu tập"}, tao[2])
pub = [x for x in gia.goi if "media_publish" in x["url"]]
check("carousel: đăng container cha", len(pub) == 1 and pub[0]["data"] == {"creation_id": "7100"})
gia.go()

# ---- 7. hạn mức chạm trần -> không tạo container ----
gia = GiaHttp().lap()
han_muc(gia, dung=100, tran=100)
ra = chay(ig.call("instagram_dang_anh", {"image_url": "https://cdn.vi.du/a.jpg"}, spec()))
check("chạm hạn mức -> ERROR", ra.startswith("ERROR") and "100/100" in ra, ra)
check("chạm hạn mức -> không tạo container", not any(x["url"].endswith("/media") for x in gia.goi))
hm = [x for x in gia.goi if "content_publishing_limit" in x["url"]][0]
check("hạn mức hỏi quota_usage,config + since", hm["params"]["fields"] == "quota_usage,config"
      and abs(hm["params"]["since"] - (time.time() - 86400)) < 60)
gia.go()

# ---- 8. kiểm đầu vào, không chạm mạng ----
gia = GiaHttp().lap()
sai = [
    ("instagram_dang_anh", {"image_url": "http://cdn.vi.du/a.jpg"}, "http thường"),
    ("instagram_dang_anh", {"image_url": "file:///C:/anh.jpg"}, "file cục bộ"),
    ("instagram_dang_anh", {"image_url": "https://localhost/a.jpg"}, "localhost"),
    ("instagram_dang_anh", {"image_url": "https://192.168.1.5/a.jpg"}, "mạng LAN"),
    ("instagram_dang_anh", {"image_url": "C:\\anh.jpg"}, "đường dẫn máy"),
    ("instagram_dang_anh", {}, "thiếu ảnh"),
    ("instagram_dang_anh", {"image_url": "https://a.b/x.jpg", "caption": "a" * 2201}, "caption 2201"),
    ("instagram_dang_anh", {"image_url": "https://a.b/x.jpg", "caption": " ".join(f"#t{i}" for i in range(31))}, "31 hashtag"),
    ("instagram_dang_anh", {"image_url": "https://a.b/x.jpg", "caption": " ".join(f"@u{i}" for i in range(21))}, "21 @"),
    ("instagram_dang_reel", {"video_url": "ftp://a.b/v.mp4"}, "reel ftp"),
    ("instagram_dang_carousel", {"media_urls": ["https://a.b/1.jpg"]}, "carousel 1 mục"),
    ("instagram_dang_carousel", {"media_urls": [f"https://a.b/{i}.jpg" for i in range(11)]}, "carousel 11 mục"),
    ("instagram_dang_carousel", {"media_urls": ["https://a.b/1.jpg", "http://a.b/2.jpg"]}, "carousel có http"),
    ("instagram_dang_carousel", {}, "carousel rỗng"),
    ("instagram_tra_loi_binh_luan", {"comment_id": "12", "message": ""}, "trả lời rỗng"),
    ("instagram_tra_loi_binh_luan", {"comment_id": "abc", "message": "hi"}, "comment_id chữ"),
    ("instagram_tra_loi_binh_luan", {"comment_id": "12", "message": "a" * 2201}, "trả lời quá dài"),
    ("instagram_chi_so_bai", {"media_id": "1/../2"}, "media_id lạ"),
    ("instagram_chi_so_bai", {"media_id": "12", "metric": "reach&x=1"}, "metric lạ"),
    ("instagram_dang_container", {"creation_id": ""}, "creation_id rỗng"),
]
for tool, args, ten in sai:
    check("từ chối: " + ten, chay(ig.call(tool, args, spec())).startswith("ERROR"))
check("đầu vào sai không chạm mạng", gia.goi == [], [x["url"] for x in gia.goi][:3])
han_muc(gia)
gia.tra(f"/{UID}/media", {"id": "9010"})
gia.tra("/9010", {"status_code": "FINISHED"})
gia.tra(f"/{UID}/media_publish", {"id": "1"})
ra = chay(ig.call("instagram_dang_anh", {"image_url": "https://a.b/x.jpg", "caption": "a" * 2200}, spec()))
check("caption đúng 2200 ký tự được nhận", '"da_dang": true' in ra, ra)
ra = chay(ig.call("instagram_dang_carousel", {"media_urls": [f"https://a.b/{i}.jpg" for i in range(10)]}, spec()))
check("carousel 10 mục được nhận", "ERROR" not in ra[:6], ra)
gia.go()

# ---- 9. đọc: bài, chỉ số, bình luận, trả lời ----
gia = GiaHttp().lap()
gia.tra("graph.instagram.com", {"data": []})
chay(ig.call("instagram_bai_gan_day", {"limit": 500}, spec()))
g = gia.goi[-1]
check("bài gần đây: path + limit chặn 50", g["url"].endswith(f"/{UID}/media") and g["params"]["limit"] == 50)
chay(ig.call("instagram_chi_so_bai", {"media_id": "1801"}, spec()))
g = gia.goi[-1]
check("chỉ số bài: /insights + metric mặc định", g["url"].endswith("/1801/insights") and g["params"]["metric"] == ig.CHI_SO_MAC_DINH)
chay(ig.call("instagram_binh_luan", {"media_id": "1801"}, spec()))
check("bình luận: /comments", gia.goi[-1]["url"].endswith("/1801/comments"))
chay(ig.call("instagram_tra_loi_binh_luan", {"comment_id": "1777", "message": "Cảm ơn chị"}, spec()))
g = gia.goi[-1]
check("trả lời bình luận: POST /replies message", g["method"] == "POST" and g["url"].endswith("/1777/replies")
      and g["data"] == {"message": "Cảm ơn chị"})
gia.go()

# ---- 10. làm mới token ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra("refresh_access_token", {"access_token": "IGQWR-moi-2222222", "token_type": "bearer", "expires_in": 5184000})
gia.tra(f"/v26.0/{UID}", {"id": UID})
sp = spec(token_het_han=str(int(time.time()) + 2 * 86400))
chay(ig.call("instagram_tai_khoan", {}, sp))
lm = [x for x in gia.goi if "refresh_access_token" in x["url"]]
check("sắp hết hạn -> làm mới đúng endpoint", len(lm) == 1 and lm[0]["url"] == "https://graph.instagram.com/refresh_access_token"
      and lm[0]["params"] == {"grant_type": "ig_refresh_token", "access_token": TOK_IG}, lm and lm[0])
luu = luu_gop()
check("token mới được LƯU vào kết nối", luu.get("access_token") == "IGQWR-moi-2222222" and all(c == "conn-ig-1" for c, _ in da_luu))
check("lưu mốc hết hạn 60 ngày", abs(int(luu.get("token_het_han", 0)) - (time.time() + 5184000)) < 60)
check("gọi API bằng token mới", gia.goi[-1]["params"]["access_token"] == "IGQWR-moi-2222222")
n = len(gia.goi)
chay(ig.call("instagram_tai_khoan", {}, sp))
check("vừa làm mới -> không làm mới lại", len([x for x in gia.goi[n:] if "refresh_access_token" in x["url"]]) == 0)
gia.go()

gia = GiaHttp().lap()
gia.tra("graph.", {"id": UID})
chay(ig.call("instagram_tai_khoan", {}, spec()))
check("còn hạn lâu -> không làm mới", not any("refresh_access_token" in x["url"] for x in gia.goi))
chay(ig.call("instagram_tai_khoan", {}, spec(TOK_FB, token_het_han="")))
check("token Facebook Login -> không gọi refresh IG", not any("refresh_access_token" in x["url"] for x in gia.goi))
gia.go()

da_luu.clear()
gia = GiaHttp().lap()
gia.tra("refresh_access_token", {"error": {"message": "token " + TOK_IG + " invalid"}}, code=400)
gia.tra(f"/v26.0/{UID}", {"id": UID, "username": "van.chay"})
sp = spec(token_het_han="")
ra = chay(ig.call("instagram_tai_khoan", {}, sp))
check("làm mới hỏng -> lượt gọi vẫn chạy bằng token cũ", "van.chay" in ra and TOK_IG not in ra, ra)
check("làm mới hỏng -> ghi mốc lùi", "thu_lam_moi_luc" in luu_gop())
n = len(gia.goi)
chay(ig.call("instagram_tai_khoan", {}, sp))
check("làm mới hỏng -> không thử lại ngay", not any("refresh_access_token" in x["url"] for x in gia.goi[n:]))
gia.go()

# ---- 11. không lộ bí mật ----
gia = GiaHttp().lap()
proof = ig.appsecret_proof(SECRET, TOK_IG)
gia.tra(f"/v26.0/{UID}", {"error": {"message": f"Invalid {TOK_IG} {SECRET} {proof}", "type": "OAuthException",
                                    "code": 190}}, code=400)
ra = chay(ig.call("instagram_tai_khoan", {}, spec(app_secret=SECRET)))
check("lỗi API không lộ token/secret/proof", ra.startswith("ERROR") and all(s not in ra for s in (TOK_IG, SECRET, proof)), ra)
check("lỗi 190 -> chỉ cách lấy token mới", "token" in ra.lower() and "Kết nối" in ra, ra)
gia.nem_loi(f"/v26.0/{UID}", ConnectionError(f"rớt access_token={TOK_IG}&appsecret_proof={proof}"))
ra = chay(ig.call("instagram_tai_khoan", {}, spec(app_secret=SECRET)))
check("lỗi mạng không lộ token/proof", ra.startswith("ERROR") and TOK_IG not in ra and proof not in ra, ra)
gia.tra(f"/v26.0/{UID}", {"id": UID, "echo": TOK_IG, "uid": UID})
ra = chay(ig.call("instagram_tai_khoan", {}, spec()))
check("kết quả thành công cũng giấu token", TOK_IG not in ra, ra)
gia.go()

# ---- 12. danh sách tool, văn bản sạch ----
ten = {x["name"] for x in chay(ig.list_tools({}))}
check("đủ 11 tool", len(ten) == 11 and {"instagram_dang_anh", "instagram_dang_carousel", "instagram_dang_reel",
                                       "instagram_tra_loi_binh_luan"} <= ten, ten)
nguon = (SERVER / "instagram_mcp.py").read_text(encoding="utf-8")
check("không có gạch dài", "\u2014" not in nguon and "\u2013" not in nguon)
check.ket_thuc()
