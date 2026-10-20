"""Đội Social - kỹ năng Worker cho TikTok, YouTube, Threads, Instagram, X, Reddit.

    python tests/run.py doi_social_nen_tang

Phủ:
  - mọi id mẫu tt_/yt_/th_/ig_/x_/rd_ trong doi_social_kich_ban.MAU có trong KICH_BAN của đúng tệp,
    kèm dang_ban_nhap:<nen_tang> (YouTube không có nháp);
  - chia chuỗi Threads (500, dòng --- tách) và X (280, chữ có dấu tính 2, link tính 23);
  - mẫu kho: hết bài -> 'het_bai'; ngữ nghĩa xong_kho trước/sau khi bấm Đăng; chạy thử trả bài về;
  - CHẠY THẬT trình duyệt Chromium headless (Playwright, không mạng: mọi URL được chặn và trả trang giả)
    cho ít nhất một kỹ năng mỗi nền tảng ở chế độ chạy thử: không có cú bấm/Enter công khai nào;
    và vài kỹ năng ở chế độ chạy thật để chắc thành công chỉ được báo khi đọc lại thấy trạng thái đổi.

ngu_canh.py (lớp NguCanh thật) do lõi viết song song; test dùng NguCanh GIẢ ghi lại mọi lời gọi, và nếu
module ngu_canh chưa import được thì chèn module giả vào sys.modules trước khi nạp các tệp kỹ năng.
"""
import os
import sys
import tempfile
import types
from pathlib import Path

from _paths import ROOT  # noqa: E402

WORKER = ROOT / "apps" / "doi-social" / "worker"
sys.path.insert(0, str(WORKER))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


try:
    import ngu_canh  # noqa: F401
    from ngu_canh import LoiKyNang
    print("dùng ngu_canh thật")
except Exception:
    m = types.ModuleType("ngu_canh")

    class LoiKyNang(RuntimeError):
        def __init__(self, thong_diep, ma=None):
            super().__init__(thong_diep)
            self.ma = ma
    m.LoiKyNang = LoiKyNang
    sys.modules["ngu_canh"] = m
    print("ngu_canh chưa có: dùng module giả")

import doi_social_kich_ban as kb  # noqa: E402
import tien_ich_web as w  # noqa: E402
import ky_nang_tiktok, ky_nang_youtube, ky_nang_threads, ky_nang_instagram, ky_nang_x, ky_nang_reddit  # noqa: E402,E401
from nguoi import Nguoi  # noqa: E402

TEP = {"tiktok": ky_nang_tiktok, "youtube": ky_nang_youtube, "threads": ky_nang_threads,
       "instagram": ky_nang_instagram, "x": ky_nang_x, "reddit": ky_nang_reddit}

# ---------------------------------------------------------------- 1. danh mục
tong = 0
for m in kb.MAU:
    if m["nen_tang"] in TEP:
        tong += 1
        check(f"{m['id']} có trong ky_nang_{m['nen_tang']}.KICH_BAN",
              callable(TEP[m["nen_tang"]].KICH_BAN.get(m["id"])))
check("đủ 28 mẫu ngoài Facebook", tong == 28, tong)
for nt, mod in TEP.items():
    k = f"dang_ban_nhap:{nt}"
    if nt == "youtube":
        check("YouTube không khai dang_ban_nhap", k not in mod.KICH_BAN)
    else:
        check(f"{k} có trong KICH_BAN", callable(mod.KICH_BAN.get(k)))
    la = [x for x in mod.KICH_BAN if not x.startswith("dang_ban_nhap:") and x not in kb.THEO_ID]
    check(f"ky_nang_{nt} không khai id lạ", not la, la)

# ---------------------------------------------------------------- 2. chia chuỗi
p = w.chia_threads("Phần một\n---\nPhần hai\n  ---  \n\n---\nPhần ba")
check("Threads: dòng --- tách chuỗi, bỏ phần rỗng", p == ["Phần một", "Phần hai", "Phần ba"], p)
dai = " ".join(f"Câu số {i} nói về sản phẩm rất hay." for i in range(60))
p = w.chia_threads(dai)
check("Threads: mỗi phần <= 500 ký tự", all(len(x) <= 500 for x in p) and len(p) >= 4, [len(x) for x in p])
check("Threads: ghép lại không mất chữ", " ".join(p).split() == dai.split())
check("Threads: cắt ở ranh giới câu khi được", all(x.endswith(".") for x in p[:-1]), [x[-10:] for x in p])
check("Threads: từ dài quá giới hạn bị cắt cứng", all(len(x) <= 500 for x in w.chia_threads("a" * 1200)))

check("X: chữ ASCII tính 1", w.dem_ky_tu_x("abc def") == 7)
check("X: chữ có dấu tính 2", w.dem_ky_tu_x("ữ") == 2 and w.dem_ky_tu_x("Việt") == 5 and w.dem_ky_tu_x("à") == 2)
check("X: dạng tổ hợp (NFD) đếm như dựng sẵn", w.dem_ky_tu_x("Việt") == 5)
check("X: link tính 23 dù dài/ngắn", w.dem_ky_tu_x("https://example.com/rat/dai/" + "x" * 80) == 23
      and w.dem_ky_tu_x("https://a.b") == 23)
check("X: câu trộn link", w.dem_ky_tu_x("xem https://a.b/c nhé") == 4 + 23 + 3 + 2, w.dem_ky_tu_x("xem https://a.b/c nhé"))
check("X: emoji tính 2", w.dem_ky_tu_x("😀") == 2)
viet = " ".join(["Sản phẩm dưỡng ẩm cho làn da khô, mùa đông này chị em nhớ dùng nhé."] * 12) + \
    " https://shop.vi/san-pham/kem-duong-am-rat-dai-" + "x" * 60
p = w.chia_x(viet)
check("X: mỗi phần <= 280 theo cách X đếm", all(w.dem_ky_tu_x(x) <= 280 for x in p) and len(p) >= 3,
      [w.dem_ky_tu_x(x) for x in p])
check("X: không cắt đôi link", any(x.endswith("x" * 60) and "https://shop.vi/" in x for x in p))
check("X: dòng --- là ranh giới bắt buộc", w.chia_x("một\n---\nhai") == ["một", "hai"])
check("X: bài ngắn giữ nguyên một phần", w.chia_x("Chào buổi sáng") == ["Chào buổi sáng"])
check("Mục tiêu trả lời đi khứ hồi qua link_goc",
      w.tach_muc_tieu(w.gan_muc_tieu("https://x.y/p/1", "an_nhi", "Giá bao nhiêu vậy shop?")) ==
      ("https://x.y/p/1", "an_nhi", "Giá bao nhiêu vậy shop?") and w.tach_muc_tieu("https://a.b") == ("https://a.b", "", ""))
check("tên sub chuẩn hoá", w.ds_sub("r/vietnam, https://www.reddit.com/r/AskVN/ ,  python") == ["vietnam", "AskVN", "python"])


# ---------------------------------------------------------------- NguCanh giả
class NguCanhGia:
    def __init__(self, nen_tang, ts=None, chay_thu=False, che_do=None, page=None, kho=None, ai=None,
                 ban_nhap_duyet=None, bai_doi=None, con=10, viec=None):
        self.ctx = page.context if page is not None else None
        self.page = page if page is not None else types.SimpleNamespace(url="about:blank")
        self.nen_tang = nen_tang
        self.ts = dict(ts or {})
        self.chay_thu = chay_thu
        self.che_do = che_do or ("chay_thu" if chay_thu else "dang_luon")
        self.viec = viec or {"id": 7, "nick_id": "n1", "tham_so": {"tham_so": self.ts}}
        self.tay = Nguoi(page, toc_do=400) if page is not None else types.SimpleNamespace(
            nghi=lambda a, b: None, bam=lambda l: None, go=lambda t: None, luot=lambda n=2: None)
        self.goi = []
        self.su = []
        self._kho = list(kho or [])
        self._ai = ai or {}
        self._duyet = list(ban_nhap_duyet or [])
        self._bai_doi = list(bai_doi or [])
        self._con = con
        self._dem = {}
        self._da = set()
        self._id = 100

    def _g(self, ten, *a, **k):
        self.goi.append((ten, a, k))

    def nhat_ky(self, s):
        self._g("nhat_ky", s)

    def su_kien(self, hanh_dong, ket_qua, chi_tiet="", link="", nhom="", san_pham="", ma=""):
        self.su.append({"hd": hanh_dong, "kq": ket_qua, "ct": chi_tiet, "link": link, "ma": ma})
        if ket_qua == "thanh_cong":
            self._dem[hanh_dong] = self._dem.get(hanh_dong, 0) + 1
        return {"con_lai": {hanh_dong: self.con_lai(hanh_dong)}, "dung": False}

    def con_lai(self, hd):
        return self._con - self._dem.get(hd, 0)

    def nen_dung(self):
        return False

    def nghi_thao_tac(self):
        self._g("nghi_thao_tac")

    def ai(self, muc_dich, du_lieu, anh=()):
        self._g("ai", muc_dich, du_lieu)
        return dict(self._ai)

    def ban_nhap(self, **kw):
        self._id += 1
        self._g("ban_nhap", **kw)
        return self._id

    def lay_ban_nhap(self, noi_dang):
        self._g("lay_ban_nhap", noi_dang)
        return self._duyet.pop(0) if self._duyet else None

    def xong_ban_nhap(self, id, ok, link="", loi=""):
        self._g("xong_ban_nhap", id, ok, link=link, loi=loi)

    def lay_kho(self):
        self._g("lay_kho")
        return self._kho.pop(0) if self._kho else None

    def xong_kho(self, id, ok, da_bam_dang, link="", loi=""):
        self._g("xong_kho", id, ok, da_bam_dang, link=link, loi=loi)

    def nhom_fb(self):
        return []

    def bao_nhom(self, link, **kw):
        pass

    def da_lam(self, khoa, ca_doi=False):
        return khoa in self._da

    def ghi_da_lam(self, khoa):
        self._g("ghi_da_lam", khoa)
        self._da.add(khoa)

    def hoi_thoai(self, **kw):
        return {}

    def bai_doi_da_dang(self):
        return list(self._bai_doi)

    def chup(self):
        return b""

    def mo(self, url):
        self._g("mo", url)
        if hasattr(self.page, "goto"):
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def kiem_dang_nhap(self):
        self._g("kiem_dang_nhap")

    def ten_goi(self, ten):
        return [g for g in self.goi if g[0] == ten]


# ---------------------------------------------------------------- 3. kho bài (không cần trình duyệt)
for nt, ham in (("tiktok", ky_nang_tiktok.tt_dang_video_kho), ("youtube", ky_nang_youtube.yt_dang_video_kho),
                ("threads", ky_nang_threads.th_dang_kho), ("instagram", ky_nang_instagram.ig_dang_kho),
                ("x", ky_nang_x.x_dang_kho)):
    nc = NguCanhGia(nt, {"kho": "chung", "so_bai": 2})
    kq = ham(nc)
    hb = [s for s in nc.su if s["kq"] == "bo_qua"]
    check(f"{nt}: kho rỗng -> 'Hết bài' + sự kiện bo_qua ma=het_bai",
          kq == "Hết bài" and len(hb) == 1 and hb[0]["ma"] == "het_bai" and hb[0]["ct"] == "Hết bài", (kq, nc.su))
    check(f"{nt}: mở trang + kiểm đăng nhập trước", [g[0] for g in nc.goi[:2]] == ["mo", "kiem_dang_nhap"],
          nc.goi[:2])


def _chay_kho(dang_mot, kho=None, chay_thu=False, kiem=None):
    nc = NguCanhGia("x", chay_thu=chay_thu, kho=kho or [{"id": 5, "noi_dung": "bài", "tep_cuc_bo": []}])
    try:
        kq = w.chay_kho(nc, "dang_tuong", 1, "Thử", dang_mot, kiem_bai=kiem)
    except LoiKyNang as e:
        kq = e
    return nc, kq, nc.ten_goi("xong_kho")


def _loi_truoc(bai, tt):
    raise w.LoiDang("không thấy ô soạn", False)


def _loi_sau(bai, tt):
    tt.da_bam = True
    raise RuntimeError("bấm Đăng rồi mà hộp không đóng")


nc, kq, xk = _chay_kho(_loi_truoc)
check("kho: lỗi TRƯỚC khi bấm Đăng -> xong_kho(ok=False, da_bam_dang=False)",
      len(xk) == 1 and xk[0][1][:3] == (5, False, False), xk)
check("kho: không thành công lượt nào -> việc báo thất bại", isinstance(kq, LoiKyNang), kq)
nc, kq, xk = _chay_kho(_loi_sau)
check("kho: lỗi SAU khi bấm Đăng -> xong_kho(ok=False, da_bam_dang=True)",
      len(xk) == 1 and xk[0][1][:3] == (5, False, True), xk)
nc, kq, xk = _chay_kho(lambda bai, tt: "https://x.com/a/status/1")
check("kho: đăng được -> xong_kho(ok=True, da_bam_dang=True, link)",
      len(xk) == 1 and xk[0][1][:3] == (5, True, True) and xk[0][2]["link"].endswith("/1")
      and any(s["kq"] == "thanh_cong" for s in nc.su), xk)
nc, kq, xk = _chay_kho(lambda b, t: (_ for _ in ()).throw(LoiKyNang("captcha", "captcha")))
check("kho: captcha -> trả bài (chưa bấm) và ném tiếp mã dừng",
      isinstance(kq, LoiKyNang) and getattr(kq, "ma", None) == "captcha" and xk[0][1][:3] == (5, False, False), (kq, xk))
goi_dang = []
nc, kq, xk = _chay_kho(lambda b, t: goi_dang.append(1), chay_thu=True)
check("kho: chạy thử không gọi hàm đăng, trả bài về hàng chờ",
      not goi_dang and xk[0][1][:3] == (5, False, False) and any(s["kq"] == "thong_tin" for s in nc.su), xk)
nc, kq, xk = _chay_kho(lambda b, t: "x", kiem=lambda b: "bài không có video")
check("kho: bài không hợp lệ -> trả về (chưa bấm), báo lỗi", xk[0][1][:3] == (5, False, False))

# mẫu AI đăng nháp đã duyệt: chạy thử không giữ nháp
nc = NguCanhGia("threads", {"so_bai": 1}, chay_thu=True)
ky_nang_threads.th_dang_ai(nc)
check("th_dang_ai chạy thử: không gọi lay_ban_nhap (không giữ nháp)", not nc.ten_goi("lay_ban_nhap"))
nc = NguCanhGia("instagram", {"so_bai": 1})
kq = ky_nang_instagram.ig_dang_ai(nc)
check("ig_dang_ai: không còn nháp đã duyệt -> Hết bài", kq == "Hết bài" and nc.su[-1]["ma"] == "het_bai", (kq, nc.su))
nc = NguCanhGia("instagram", {"so_bai": 1}, ban_nhap_duyet=[{"id": 9, "noi_dung": "Bài AI"}])
try:
    ky_nang_instagram.ig_dang_ai(nc)
except LoiKyNang:
    pass
xb = nc.ten_goi("xong_ban_nhap")
check("ig_dang_ai: nháp không có ảnh -> xong_ban_nhap(ok=False) có lý do", xb and xb[0][1][:2] == (9, False)
      and "ảnh" in xb[0][2]["loi"], xb)

# dang_ban_nhap chạy thử
nc = NguCanhGia("x", {"ban_nhap_id": 3, "loai": "tra_loi", "noi_dung": "hay", "link_goc": "https://x.com/a/status/1"},
                chay_thu=True)
kq = ky_nang_x.dang_ban_nhap(nc)
check("dang_ban_nhap chạy thử: không mở trang, không đánh dấu nháp", not nc.ten_goi("mo")
      and not nc.ten_goi("xong_ban_nhap") and nc.su[-1]["kq"] == "thong_tin", nc.goi)
nc = NguCanhGia("tiktok", {"ban_nhap_id": 4, "loai": "bai_dang", "noi_dung": "x"})
try:
    ky_nang_tiktok.dang_ban_nhap(nc)
    loi = None
except LoiKyNang as e:
    loi = e
check("dang_ban_nhap:tiktok loại bài đăng -> lỗi rõ + xong_ban_nhap(ok=False)",
      loi is not None and nc.ten_goi("xong_ban_nhap")[0][1][:2] == (4, False))

# cổng công khai
nc = NguCanhGia("x", chay_thu=True)
bam = []
nc.tay = types.SimpleNamespace(bam=lambda l: bam.append(l), nghi=lambda a, b: None)
check("cổng: chạy thử không bấm", w.bam_cong_khai(nc, object(), "Đăng") is False and not bam)
nc.chay_thu = False
check("cổng: chạy thật bấm", w.bam_cong_khai(nc, "nut", "Đăng") is True and bam == ["nut"])

# ---------------------------------------------------------------- 4. trình duyệt thật (headless, không mạng)
JS = """<script>
window.__ck = [];
function ck(n){ window.__ck.push(n); }
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.closest && e.target.closest('[data-gui-enter]')) ck('enter:' + e.target.tagName);
}, true);
</script>"""


def _trang(than):
    return "<!doctype html><html><head><meta charset='utf-8'>" + JS + "</head><body>" + than + "</body></html>"


TRANG = {
    # TikTok video
    "tiktok.com/@shop/video/1": _trang("""
<p data-e2e="browse-video-desc">Kem dưỡng ẩm mùa đông</p>
<button aria-label="Like video" aria-pressed="false" onclick="ck('like');this.setAttribute('aria-pressed','true')">
  <span data-e2e="like-icon">&#9829;</span></button>
<button aria-label="Add to Favorites" aria-pressed="false" onclick="ck('save');this.setAttribute('aria-pressed','true')">
  <span data-e2e="undefined-icon">*</span></button>
<div data-e2e="comment-input" data-gui-enter><div contenteditable="true" role="textbox" aria-label="Add comment..."
  style="min-width:300px;min-height:24px;border:1px solid #999"></div></div>
<button data-e2e="comment-post" onclick="ck('post');var t=document.querySelector('[data-e2e=comment-input] [contenteditable]');
  var p=document.createElement('p');p.textContent=t.innerText;document.getElementById('ds').appendChild(p);t.innerText=''">Post</button>
<div id="ds"><p>Bình luận cũ của người khác</p></div>"""),
    # TikTok LIVE
    "tiktok.com/@shop/live": _trang("""
<div data-gui-enter><div contenteditable="plaintext-only" placeholder="Say something nice"
  style="min-width:300px;min-height:24px;border:1px solid"></div></div>
<button aria-label="Send" onclick="ck('send_live')">Send</button><div id="chat"></div>"""),
    # Threads bài
    "threads.com/@ban/post/abc": _trang("""
<div data-pressable-container="true"><a href="/@ban">ban</a><span dir="auto">Bài gốc trên Threads nói về da khô</span>
 <div role="button" onclick="ck('like');this.querySelector('svg').setAttribute('aria-label','Unlike')">
   <svg aria-label="Like" role="img" width="20" height="20"><rect width="20" height="20"></rect></svg></div>
 <div role="button" onclick="ck('repost_menu')"><svg aria-label="Repost" role="img" width="20" height="20"><rect width="20" height="20"></rect></svg></div>
</div>"""),
    # Threads tìm kiếm (quét)
    "threads.com/search": _trang("""
<div data-pressable-container="true"><a href="/@u1">u1</a><a href="/@u1/post/p1"><time datetime="2026-10-20T01:00:00Z">2 giờ</time></a>
 <span dir="auto">Ai biết chỗ mua kem dưỡng ẩm tốt không</span></div>
<div data-pressable-container="true"><a href="/@u2">u2</a><a href="/@u2/post/p2"><time datetime="2026-10-20T02:00:00Z">1 giờ</time></a>
 <span dir="auto">Da mình khô quá, xin review</span></div>"""),
    # Instagram bài
    "instagram.com/p/xyz": _trang("""
<ul><li><a href="/khach1/">khach1</a><span>Đẹp quá</span>
  <div role="button" onclick="ck('like_comment')"><svg aria-label="Like" height="12" width="12" role="img"><rect width="12" height="12"></rect></svg></div></li></ul>
<section>
 <div role="button" onclick="ck('like');this.querySelector('svg').setAttribute('aria-label','Unlike')">
   <svg aria-label="Like" height="24" width="24" role="img"><rect width="24" height="24"></rect></svg></div>
 <div role="button" onclick="ck('save');this.querySelector('svg').setAttribute('aria-label','Remove')">
   <svg aria-label="Save" height="24" width="24" role="img"><rect width="24" height="24"></rect></svg></div>
</section>
<form data-gui-enter><textarea aria-label="Add a comment…" placeholder="Add a comment…"></textarea>
 <div role="button" onclick="ck('post')">Post</div></form>"""),
    # Threads đăng nhập
    "threads.com/login": _trang("""<h1>Log in</h1><a href="#" onclick="ck('ig_login')">Continue with Instagram</a>"""),
    # X bài
    "x.com/ban/status/1": _trang("""
<article data-testid="tweet"><div data-testid="User-Name">Bạn <span>@ban</span></div>
 <div data-testid="tweetText">Bài trên X</div>
 <button data-testid="reply" aria-label="Reply" onclick="ck('reply_open')">r</button>
 <button data-testid="retweet" aria-label="Repost" onclick="ck('rt_menu')">rt</button>
 <button data-testid="like" aria-label="Like" onclick="ck('like');this.setAttribute('data-testid','unlike')">lk</button>
</article>"""),
    # X tìm kiếm
    "x.com/search": _trang("""
<article data-testid="tweet"><div data-testid="User-Name">An <span>@an_nhi</span></div>
 <div data-testid="tweetText">Có ai dùng kem dưỡng ẩm cho da khô mùa đông chưa, chỉ mình với</div>
 <a href="/an_nhi/status/111"><time>1 giờ</time></a>
 <button data-testid="reply" onclick="ck('reply_open')">r</button><button data-testid="like" onclick="ck('like')">l</button></article>
<article data-testid="tweet"><div data-testid="User-Name">Lớn <span>@to</span><svg data-testid="icon-verified"></svg></div>
 <div data-testid="tweetText">Bài của tài khoản tích xanh về kem dưỡng ẩm</div>
 <a href="/to/status/222"><time>1 giờ</time></a></article>
<article data-testid="tweet"><div data-testid="User-Name">Coin <span>@coin</span></div>
 <div data-testid="tweetText">Kem dưỡng ẩm và crypto airdrop miễn phí</div>
 <a href="/coin/status/333"><time>1 giờ</time></a></article>"""),
    # Reddit sub
    "reddit.com/r/vietnam": _trang("""
<shreddit-join-button><button onclick="ck('join');this.textContent='Joined';this.parentElement.setAttribute('subscribed','')">Join</button></shreddit-join-button>"""),
    "reddit.com/r/AskVN": _trang("""
<shreddit-join-button subscribed><button>Joined</button></shreddit-join-button>"""),
    # YouTube
    "youtube.com/upload": _trang("""<input type="file"><button id="done-button" onclick="ck('publish')">Publish</button>"""),
}


def _phuc_vu(route):
    url = route.request.url
    for k, html in TRANG.items():
        if k in url:
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
    return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=_trang("<p>trống</p>"))


try:
    from playwright.sync_api import sync_playwright
    co_pw = True
except Exception as e:
    co_pw = False
    check("có playwright", False, e)

if co_pw:
    w.THU_MUC = Path(tempfile.mkdtemp())       # CSV quét không ghi vào thư mục Worker của repo
    with sync_playwright() as pw:
        trinh = pw.chromium.launch(headless=True)
        ctx = trinh.new_context(viewport={"width": 1280, "height": 900})
        ctx.route("**/*", _phuc_vu)

        def chay(nt, ham, ts, **kw):
            page = ctx.new_page()
            nc = NguCanhGia(nt, ts, page=page, **kw)
            try:
                kq = ham(nc)
            except Exception as e:  # noqa: BLE001
                kq = e
            ck = page.evaluate("window.__ck || []")
            page.close()
            return nc, kq, ck

        def thu(ten, nc, kq, ck, them=lambda nc: True):
            check(f"{ten} chạy thử: không cú bấm/Enter công khai nào", ck == [], ck)
            check(f"{ten} chạy thử: không báo thành công giả, có báo 'sẽ ...'",
                  not any(s["kq"] == "thanh_cong" for s in nc.su) and any(s["kq"] == "thong_tin" for s in nc.su)
                  and not isinstance(kq, Exception) and them(nc), (kq, nc.su))

        # TikTok
        ts = {"links": ["https://www.tiktok.com/@shop/video/1"], "thich": True, "cau_binh_luan": "Xinh quá\nHay nha",
              "luu": True}
        nc, kq, ck = chay("tiktok", ky_nang_tiktok.tt_tuong_tac_video, ts, chay_thu=True)
        thu("tt_tuong_tac_video", nc, kq, ck, lambda nc: {s["hd"] for s in nc.su} >= {"thich", "binh_luan", "luu"})
        nc, kq, ck = chay("tiktok", ky_nang_tiktok.tt_tuong_tac_video, ts)
        ok_hd = {s["hd"] for s in nc.su if s["kq"] == "thanh_cong"}
        check("tt_tuong_tac_video chạy thật: tim + bình luận + lưu đều đọc lại thấy",
              ok_hd == {"thich", "binh_luan", "luu"} and "like" in ck and "post" in ck and "save" in ck, (nc.su, ck))
        check("tt_tuong_tac_video chạy thật: bình luận gửi bằng nút, không Enter", not [c for c in ck if c.startswith("enter")], ck)
        check("tt_tuong_tac_video: ghi khoá chống lặp có tiền tố tiktok",
              any(g[1][0].startswith("tiktok:") for g in nc.ten_goi("ghi_da_lam")), nc.ten_goi("ghi_da_lam"))
        nc, kq, ck = chay("tiktok", ky_nang_tiktok.tt_binh_luan_live,
                          {"links": ["https://www.tiktok.com/@shop/live"], "cau_binh_luan": "Chào shop\nCho xin giá",
                           "so_cau": 2, "gian_cach": 10}, chay_thu=True)
        thu("tt_binh_luan_live", nc, kq, ck)

        # YouTube (chạy thử: bài kho được trả về, không bấm Xuất bản)
        nc, kq, ck = chay("youtube", ky_nang_youtube.yt_dang_video_kho, {"kho": "chung", "che_do_hien": "cong_khai"},
                          chay_thu=True, kho=[{"id": 21, "tieu_de": "Video", "tep_cuc_bo": ["/tmp/a.mp4"]}])
        thu("yt_dang_video_kho", nc, kq, ck, lambda nc: nc.ten_goi("xong_kho")[0][1][:3] == (21, False, False))

        # Threads
        ts = {"links": ["https://www.threads.com/@ban/post/abc"], "thich": True, "cau_binh_luan": "Hay quá",
              "dang_lai": True}
        nc, kq, ck = chay("threads", ky_nang_threads.th_tuong_tac, ts, chay_thu=True)
        thu("th_tuong_tac", nc, kq, ck, lambda nc: {s["hd"] for s in nc.su} >= {"thich", "binh_luan", "chia_se"})
        nc, kq, ck = chay("threads", ky_nang_threads.th_tuong_tac,
                          {"links": ["https://www.threads.com/@ban/post/abc"], "thich": True})
        check("th_tuong_tac chạy thật: thích xong đọc lại thấy 'Unlike'",
              ck == ["like"] and [s["kq"] for s in nc.su if s["hd"] == "thich"] == ["thanh_cong"], (nc.su, ck))
        nc, kq, ck = chay("threads", ky_nang_threads.th_quet_csv,
                          {"kieu_quet": "tim_kiem", "dau_vao": "kem dưỡng ẩm", "so_dong": 10}, chay_thu=True)
        csvs = list((w.THU_MUC / "quet").glob("threads_tim_kiem_*.csv"))
        noi = csvs[0].read_text(encoding="utf-8-sig") if csvs else ""
        check("th_quet_csv: ghi CSV vào quet/ và báo đường dẫn trong chi_tiet",
              ck == [] and len(csvs) == 1 and "u1" in noi and "Da mình khô" in noi
              and any(s["hd"] == "quet" and s["kq"] == "thanh_cong" and str(csvs[0]) in s["ct"] for s in nc.su),
              (nc.su, noi[:200]))

        # Instagram
        ts = {"links": ["https://www.instagram.com/p/xyz/"], "thich": True, "cau_binh_luan": "Đẹp quá ạ", "luu": True}
        nc, kq, ck = chay("instagram", ky_nang_instagram.ig_tuong_tac_link, ts, chay_thu=True)
        thu("ig_tuong_tac_link", nc, kq, ck)
        nc, kq, ck = chay("instagram", ky_nang_instagram.ig_tuong_tac_link,
                          {"links": ["https://www.instagram.com/p/xyz/"], "thich": True, "luu": True})
        check("ig_tuong_tac_link chạy thật: thích đúng nút chính (svg 24), không nhầm nút thích bình luận",
              "like" in ck and "like_comment" not in ck and
              {s["hd"] for s in nc.su if s["kq"] == "thanh_cong"} == {"thich", "luu"}, (nc.su, ck))
        nc, kq, ck = chay("instagram", ky_nang_instagram.ig_dang_nhap_threads, {}, chay_thu=True)
        check("ig_dang_nhap_threads chạy thử: chỉ kiểm trạng thái, không bấm đăng nhập",
              ck == [] and "Continue with Instagram" not in str(kq) and "sẽ bấm" in str(kq), (kq, ck))

        # X
        nc, kq, ck = chay("x", ky_nang_x.x_tuong_tac_link, {"links": ["https://x.com/ban/status/1"], "thich": True,
                                                            "dang_lai": True}, chay_thu=True)
        thu("x_tuong_tac_link", nc, kq, ck)
        nc, kq, ck = chay("x", ky_nang_x.x_tuong_tac_link, {"links": ["https://x.com/ban/status/1"], "thich": True})
        check("x_tuong_tac_link chạy thật: like -> unlike đọc lại thấy",
              ck == ["like"] and [s["kq"] for s in nc.su] == ["thanh_cong"], (nc.su, ck))
        nc, kq, ck = chay("x", ky_nang_x.x_tra_loi_tu_khoa, {"tu_khoa": "kem dưỡng ẩm", "san_pham": "sp1",
                                                             "so_tra_loi": 3, "che_do": "dang_luon"},
                          chay_thu=True, ai={"noi_dung": "Da khô thì nên chọn kem có ceramide nha."})
        bn = nc.ten_goi("ban_nhap")
        check("x_tra_loi_tu_khoa chạy thử: không bấm, chỉ tạo nháp cho bài hợp lệ (bỏ tích xanh + crypto)",
              ck == [] and len(bn) == 1 and bn[0][2]["noi_dang"] == "x" and bn[0][2]["loai"] == "tra_loi"
              and bn[0][2]["link_goc"].endswith("/an_nhi/status/111")
              and any(g[1][0] == "x:tra_loi:111" for g in nc.ten_goi("ghi_da_lam")), (bn, ck, nc.su))

        # Reddit
        nc, kq, ck = chay("reddit", ky_nang_reddit.rd_tham_gia_sub, {"sub": "r/vietnam, AskVN"}, chay_thu=True)
        thu("rd_tham_gia_sub", nc, kq, ck,
            lambda nc: [s["kq"] for s in nc.su] == ["thong_tin", "bo_qua"])
        nc, kq, ck = chay("reddit", ky_nang_reddit.rd_tham_gia_sub, {"sub": "vietnam, AskVN"})
        check("rd_tham_gia_sub chạy thật: Join -> subscribed, sub đã vào thì bỏ qua",
              ck == ["join"] and [s["kq"] for s in nc.su] == ["thanh_cong", "bo_qua"], (nc.su, ck))
        nc, kq, ck = chay("reddit", ky_nang_reddit.rd_dang_sub, {"sub": "r/vietnam", "tieu_de": "Hỏi về kem dưỡng",
                                                                 "noi_dung": "Nội dung"}, chay_thu=True)
        thu("rd_dang_sub", nc, kq, ck)
        trinh.close()

# ---------------------------------------------------------------- 5. quy ước mã nguồn
for p in sorted(WORKER.glob("ky_nang_*.py")) + [WORKER / "tien_ich_web.py"]:
    if p.name == "ky_nang_fb.py":
        continue
    s = p.read_text(encoding="utf-8")
    check(f"{p.name}: không em dash", "—" not in s)
    check(f"{p.name}: không subprocess", "subprocess" not in s)
    check(f"{p.name}: không bấm .click() thẳng (mọi cú bấm qua nc.tay / cổng)", ".click(" not in s)
    check(f"{p.name}: không gõ bằng fill/type cả đoạn", ".fill(" not in s and ".type(" not in s)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
