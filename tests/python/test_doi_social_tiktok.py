"""Đội Social - các mẫu TikTok mới (26.10.229): đăng AI / ảnh slide / video gắn giỏ hàng, bình luận theo từ
khoá (AI), theo dõi người xem kênh đối thủ, quét CSV, quét giỏ hàng.

    python tests/run.py doi_social_tiktok

Phủ:
  - hàm thuần: doc_so ('1.2M', '12,3K', '1,2 Tr'...), ten_tiktok, link_video, url_quet, tach_gia, chon_san_pham,
    trang_thai_follow;
  - danh mục: mẫu mới hợp lệ (kiem_tham_so, hành động có giới hạn ngày TikTok), có trong KICH_BAN;
  - không trình duyệt: tt_dang_ai (chạy thử không giữ nháp; nháp thiếu video bị bỏ qua có lý do),
    dang_ban_nhap:tiktok bài đăng thiếu video;
  - Chromium headless với trang TikTok giả (dựng theo DOM thật 25/10/2026): chạy thử không có cú bấm công khai
    nào, chạy thật chỉ báo thành công khi đọc lại thấy trạng thái đổi; gắn sản phẩm giỏ hàng đi hết các bước.
"""
import csv
import json
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


from ngu_canh import LoiKyNang  # noqa: E402
import doi_social_kich_ban as kb  # noqa: E402
import tien_ich_web as w  # noqa: E402
import ky_nang_tiktok as tt  # noqa: E402
from nguoi import Nguoi  # noqa: E402

# ---------------------------------------------------------------- 1. hàm thuần
for s, mong in (("1.2M", 1200000), ("12,3K", 12300), ("1,2 Tr", 1200000), ("45,6 N", 45600), ("1.234", 1234),
                ("1,234,567", 1234567), ("987", 987), ("987 lượt xem", 987), ("175.4K", 175400), ("2.5B", 2500000000),
                ("5415", 5415), ("Nhiều người thích 5415", 5415), ("3K", 3000), ("12.5", 12), ("", None), ("abc", None)):
    check(f"doc_so({s!r}) = {mong}", tt.doc_so(s) == mong, tt.doc_so(s))
check("ten_tiktok: @, link, tên trần", tt.ten_tiktok("@Shop.A") == "shop.a"
      and tt.ten_tiktok("https://www.tiktok.com/@shop_b?lang=vi-VN") == "shop_b" and tt.ten_tiktok("shop.c") == "shop.c"
      and tt.ten_tiktok("có dấu cách") == "")
check("link_video chuẩn hoá (tuyệt đối, bỏ tham số), không phải video -> ''",
      tt.link_video("/@a/video/123?is_from_webapp=1") == "https://www.tiktok.com/@a/video/123"
      and tt.link_video("https://www.tiktok.com/@a/photo/9") == "https://www.tiktok.com/@a/photo/9"
      and tt.link_video("https://www.tiktok.com/@a") == "")
check("url_quet: từ khoá / hashtag / hồ sơ / link",
      tt.url_quet("tim_kiem", "kem dưỡng") == "https://www.tiktok.com/search/video?q=kem%20d%C6%B0%E1%BB%A1ng"
      and tt.url_quet("hashtag", "#kemduong") == "https://www.tiktok.com/tag/kemduong"
      and tt.url_quet("ho_so", "@shop") == "https://www.tiktok.com/@shop"
      and tt.url_quet("hashtag", "https://www.tiktok.com/tag/x") == "https://www.tiktok.com/tag/x"
      and tt.url_quet("ho_so", "") == "")
check("tach_gia: ₫ / $ / không có", tt.tach_gia("Áo thun 199.000₫ freeship") == "199.000₫"
      and tt.tach_gia("$12.99 Shirt") == "$12.99" and tt.tach_gia("Áo đẹp") == "")
hang = [{"chu": "\tÁo thun basic trắng\n199.000₫", "ma": "a"}, {"chu": "Váy hoa nhí dáng dài\nID 1729000333", "ma": "b"},
        {"chu": "Quần jean ống rộng cạp cao...", "ma": "c"}]
check("chon_san_pham: đúng cả dòng", (tt.chon_san_pham(hang, "áo thun basic trắng") or {}).get("ma") == "a")
check("chon_san_pham: chứa / theo ID", (tt.chon_san_pham(hang, "hoa nhí") or {}).get("khop") == "chua"
      and (tt.chon_san_pham(hang, "1729000333") or {}).get("ma") == "b")
check("chon_san_pham: tên bị cắt '...' vẫn khớp", (tt.chon_san_pham(hang, "Quần jean ống rộng cạp cao màu xanh") or {})
      .get("khop") == "gan_dung")
check("chon_san_pham: không khớp -> None (không gắn bừa)", tt.chon_san_pham(hang, "Mũ lưỡi trai") is None
      and tt.chon_san_pham(hang, "") is None)
check("trang_thai_follow", [tt.trang_thai_follow(x) for x in ("Theo dõi", "Follow back", "Đang theo dõi", "Following",
                                                                "Bạn bè", "Tin nhắn")] == ["chua", "chua", "da", "da", "da", "?"])

# ---------------------------------------------------------------- 2. danh mục
MOI = {"tt_dang_ai": {}, "tt_dang_anh_kho": {}, "tt_dang_video_gio_hang": {"san_pham_shop": "Áo thun"},
       "tt_binh_luan_tu_khoa": {"tu_khoa": "kem dưỡng", "san_pham": "1"}, "tt_follow_doi_thu": {"doi_thu": "@shop"},
       "tt_quet_csv": {"dau_vao": "kem"}, "tt_quet_gio_hang": {"tu_khoa": "áo thun"}}
gh_tt = kb.GIOI_HAN_MAC_DINH["nen_tang"]["tiktok"]
for mid, ts in MOI.items():
    m = kb.THEO_ID.get(mid)
    check(f"{mid}: có trong danh mục, nền tảng tiktok", m and m["nen_tang"] == "tiktok" and m["nhom"] in dict(kb.NHOM), m)
    if not m:
        continue
    check(f"{mid}: có trong ky_nang_tiktok.KICH_BAN", callable(tt.KICH_BAN.get(mid)))
    check(f"{mid}: hành động có tên và có giới hạn ngày TikTok",
          m["hanh_dong"] and all(h in kb.HANH_DONG and h in gh_tt for h in m["hanh_dong"]), m["hanh_dong"])
    try:
        ra = kb.kiem_tham_so(mid, ts)
        check(f"{mid}: tham số mặc định hợp lệ", all(f["key"] in ra for f in m["tham_so"]), ra)
    except ValueError as e:
        check(f"{mid}: tham số mặc định hợp lệ", False, e)
    bb = [f["key"] for f in m["tham_so"] if f.get("bat_buoc")]
    if bb:
        try:
            kb.kiem_tham_so(mid, {})
            check(f"{mid}: thiếu tham số bắt buộc bị từ chối", False)
        except ValueError:
            check(f"{mid}: thiếu tham số bắt buộc bị từ chối", True)
    chu = json.dumps(m, ensure_ascii=False)
    check(f"{mid}: không em dash", "—" not in chu)
check("theo dõi TikTok mặc định thận trọng (<= 30/ngày)", gh_tt["theo_doi"][1] <= 30 and gh_tt["theo_doi"][0] <= gh_tt["theo_doi"][1])
check("mẫu AI có chế độ nội dung", any(f["key"] == "che_do" for f in kb.THEO_ID["tt_binh_luan_tu_khoa"]["tham_so"])
      and kb.THEO_ID["tt_binh_luan_tu_khoa"]["ai"])


# ---------------------------------------------------------------- NguCanh giả
class NguCanhGia:
    def __init__(self, ts=None, chay_thu=False, che_do=None, page=None, kho=None, ai=None, ban_nhap_duyet=None, con=10):
        self.ctx = page.context if page is not None else None
        self.page = page if page is not None else types.SimpleNamespace(url="about:blank")
        self.nen_tang = "tiktok"
        self.ts = dict(ts or {})
        self.chay_thu = chay_thu
        self.che_do = che_do or ("chay_thu" if chay_thu else "dang_luon")
        self.viec = {"id": 7, "nick_id": "n1", "tham_so": {"tham_so": self.ts}}
        self.tay = Nguoi(page, toc_do=400) if page is not None else types.SimpleNamespace(
            nghi=lambda a, b: None, bam=lambda l: None, go=lambda t: None, luot=lambda n=2: None)
        self.goi, self.su, self.tep = [], [], []
        self._kho = list(kho or [])
        self._ai = ai or {}
        self._duyet = list(ban_nhap_duyet or [])
        self._con, self._dem, self._da, self._id = con, {}, set(), 100

    def _g(self, ten, *a, **k):
        self.goi.append((ten, a, k))

    def nhat_ky(self, s):
        self._g("nhat_ky", s)

    def su_kien(self, hanh_dong, ket_qua, chi_tiet="", link="", nhom="", san_pham="", ma=""):
        self.su.append({"hd": hanh_dong, "kq": ket_qua, "ct": chi_tiet, "link": link, "ma": ma})
        if ket_qua == "thanh_cong":
            self._dem[hanh_dong] = self._dem.get(hanh_dong, 0) + 1
        return {}

    def con_lai(self, hd):
        return self._con - self._dem.get(hd, 0)

    def nen_dung(self):
        return False

    def nghi_thao_tac(self):
        pass

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

    def da_lam(self, khoa, ca_doi=False):
        return khoa in self._da

    def ghi_da_lam(self, khoa):
        self._g("ghi_da_lam", khoa)
        self._da.add(khoa)

    def gui_tep_ket_qua(self, p):
        self.tep.append(Path(p))
        return {"ten": Path(p).name}

    def mo(self, url):
        self._g("mo", url)
        if hasattr(self.page, "goto"):
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def kiem_dang_nhap(self):
        self._g("kiem_dang_nhap")

    def ten_goi(self, ten):
        return [g for g in self.goi if g[0] == ten]


# ---------------------------------------------------------------- 3. không trình duyệt
nc = NguCanhGia({"so_bai": 2}, chay_thu=True)
kq = tt.tt_dang_ai(nc)
check("tt_dang_ai chạy thử: không giữ nháp, báo 'sẽ', câu cuối nói rõ chạy thử",
      not nc.ten_goi("lay_ban_nhap") and nc.su[-1]["kq"] == "thong_tin" and kq.startswith("Chạy thử") and "Sẽ làm" in kq, kq)
nc = NguCanhGia({"so_bai": 1}, ban_nhap_duyet=[{"id": 9, "loai": "bai_dang", "noi_dung": "Caption AI", "tep_cuc_bo": []}])
kq = tt.tt_dang_ai(nc)
xb = nc.ten_goi("xong_ban_nhap")
check("tt_dang_ai: nháp không có video -> bỏ qua có lý do, lấy tiếp nháp sau",
      xb and xb[0][1][:2] == (9, False) and "video" in xb[0][2]["loi"] and len(nc.ten_goi("lay_ban_nhap")) == 2
      and nc.su[-1]["ma"] == "het_bai" and not nc.ten_goi("mo")[1:], (xb, nc.su, kq))
nc = NguCanhGia({"so_bai": 1})
check("tt_dang_ai: không còn nháp -> Hết bài", tt.tt_dang_ai(nc) == "Hết bài")
nc = NguCanhGia({"ban_nhap_id": 4, "loai": "bai_dang", "noi_dung": "x", "tep_cuc_bo": []})
try:
    tt.dang_ban_nhap(nc)
    loi = None
except LoiKyNang as e:
    loi = e
check("dang_ban_nhap:tiktok bài đăng thiếu video -> lỗi nói rõ video, không mở trang, xong_ban_nhap(ok=False)",
      loi is not None and "video" in str(loi) and not nc.ten_goi("mo")
      and nc.ten_goi("xong_ban_nhap")[0][1][:2] == (4, False), (loi, nc.goi))
for mid, ts in (("tt_dang_anh_kho", {}), ("tt_dang_video_gio_hang", {"san_pham_shop": "Áo"})):
    for thu in (False, True):
        nc = NguCanhGia(ts, chay_thu=thu)
        kq = tt.KICH_BAN[mid](nc)
        check(f"{mid} ({'chạy thử' if thu else 'thật'}): kho rỗng -> Hết bài", kq == "Hết bài"
              and nc.su[-1]["ma"] == "het_bai", (kq, nc.su))
try:
    tt.tt_dang_video_gio_hang(NguCanhGia({}))
    loi = None
except LoiKyNang as e:
    loi = e
check("tt_dang_video_gio_hang: thiếu sản phẩm -> lỗi rõ", loi is not None and "sản phẩm" in str(loi))
nc = NguCanhGia({"kho": "chung"}, chay_thu=True, kho=[{"id": 3, "noi_dung": "x", "tep_cuc_bo": ["/tmp/1.jpg"]}])
tt.tt_dang_anh_kho(nc)
check("tt_dang_anh_kho: 1 ảnh -> trả bài về, lỗi 'cần từ 2 ảnh'", nc.ten_goi("xong_kho")[0][1][:3] == (3, False, False)
      and any("từ 2 ảnh" in s["ct"] for s in nc.su), nc.su)

# ---------------------------------------------------------------- 4. trình duyệt (headless, không mạng)
# Cú bấm ghi vào sessionStorage để giữ qua các lần chuyển trang trong cùng một tab.
JS = """<script>
window.__ck = JSON.parse(sessionStorage.getItem('ck') || '[]');
function ck(n){ window.__ck.push(n); sessionStorage.setItem('ck', JSON.stringify(window.__ck)); }
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.closest && e.target.closest('[data-gui-enter]')) ck('enter:' + e.target.tagName);
}, true);
</script>"""
NAV = '<a data-e2e="nav-profile" href="/@chu_nick">Hồ sơ</a>'


def _trang(than, dau=""):
    return "<!doctype html><html><head><meta charset='utf-8'>" + JS + dau + "</head><body>" + NAV + than + "</body></html>"


def _bl(*nguoi):
    return "".join(f'<div><a href="/@{n}">{n}</a><p data-e2e="comment-level-1">Bình luận của {n}</p></div>' for n in nguoi)


def _video(mo_ta, nguoi=(), them="", json_=None):
    dau = ""
    if json_:
        dau = ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
               + json.dumps({"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": json_}}}},
                            ensure_ascii=False) + "</script>")
    return _trang(f"""
<p data-e2e="browse-video-desc">{mo_ta}</p>{them}
<button aria-label="Like video" aria-pressed="false" onclick="ck('like');this.setAttribute('aria-pressed','true')">
  <span data-e2e="like-icon">&#9829;</span></button>
<div data-e2e="comment-input" data-gui-enter><div contenteditable="true" role="textbox" aria-label="Add comment..."
  style="min-width:300px;min-height:24px;border:1px solid #999"></div></div>
<button data-e2e="comment-post" onclick="ck('post');var t=document.querySelector('[data-e2e=comment-input] [contenteditable]');
  var p=document.createElement('p');p.textContent=t.innerText;document.getElementById('ds').appendChild(p);t.innerText=''">Post</button>
<div id="ds">{_bl(*nguoi)}</div>""", dau)


J111 = {"id": "111", "desc": "Kem dưỡng da khô mùa đông #kem", "author": {"uniqueId": "ban_a"}, "createTime": 1761350400,
        "stats": {"playCount": 45000, "diggCount": 1200, "commentCount": 33},
        "anchors": [{"id": "a1", "keyword": "Áo thun basic trắng",
                     "extra": json.dumps([{"product_id": "1729000111", "title": "Áo thun basic trắng", "price": "199.000₫"}],
                                         ensure_ascii=False)}]}
STUDIO = _trang("""
<input type="file" accept="video/*" onchange="hien()"><input type="file" accept="image/*" multiple onchange="hien()">
<div id="form" style="display:none">
 <div data-e2e="caption_container"><div contenteditable="true" role="textbox" aria-label="Caption"
   style="min-width:300px;min-height:24px;border:1px solid"></div></div>
 <div><span>Thêm liên kết</span> <button onclick="document.getElementById('dlg').style.display='block'">+ Thêm</button></div>
 <div id="chip"></div>
 <button data-e2e="post_video_button" onclick="ck('post');location.href='https://www.tiktok.com/tiktokstudio/content'">Đăng</button>
</div>
<div id="dlg" role="dialog" style="display:none">
 <div id="b1"><div role="combobox" tabindex="0" onclick="document.getElementById('opt').style.display='block'">Loại liên kết</div>
  <div id="opt" role="option" style="display:none" onclick="this.textContent='Sản phẩm ✓'">Sản phẩm</div>
  <button onclick="document.getElementById('b1').style.display='none';document.getElementById('b2').style.display='block'">Tiếp</button></div>
 <div id="b2" style="display:none"><input placeholder="Tìm kiếm sản phẩm">
  <table><thead><tr><th><input type="checkbox"></th><th>Sản phẩm</th></tr></thead><tbody>
   <tr><td><input type="radio" name="sp" value="Áo thun basic trắng"></td><td>Áo thun basic trắng<br>199.000₫</td></tr>
   <tr><td><input type="radio" name="sp" value="Váy hoa nhí"></td><td>Váy hoa nhí<br>299.000₫</td></tr></tbody></table>
  <button onclick="document.getElementById('b2').style.display='none';document.getElementById('b3').style.display='block'">Tiếp</button></div>
 <div id="b3" style="display:none"><input aria-label="Tên sản phẩm" maxlength="30">
  <button onclick="var r=document.querySelector('input[name=sp]:checked');var v=document.querySelector('#b3 input').value;
   document.getElementById('chip').textContent='Sản phẩm: '+(v||(r?r.value:'?'));document.getElementById('dlg').style.display='none'">Thêm</button></div>
</div>
<script>function hien(){ setTimeout(function(){ document.getElementById('form').style.display='block'; }, 300); }</script>""")

TRANG = {
    "tiktok.com/tiktokstudio/upload": STUDIO,
    "tiktok.com/search/video": _trang("""
<div role="button" data-e2e="search_video-item" aria-label="Xem ở chế độ toàn màn hình">
 <a href="https://www.tiktok.com/@ban_a/video/111"><img alt="Kem dưỡng da khô" width="40" height="40"></a><div>175.4K</div>
 <a data-e2e="search-card-user-link" href="/@ban_a" aria-label="Hồ sơ của A">A</a></div>
<div role="button" data-e2e="search_video-item"><a href="https://www.tiktok.com/@chu_nick/video/222"><img alt="Video của mình"></a>
 <a data-e2e="search-card-user-link" href="/@chu_nick">Mình</a></div>
<div role="button" data-e2e="search_video-item"><a href="https://www.tiktok.com/@ban_b/video/333?is_from_webapp=1"><img alt="Váy đẹp"></a>
 <div>Nhiều người thích</div><div>5415</div><a data-e2e="search-card-user-link" href="/@ban_b">B</a></div>"""),
    "tiktok.com/tag/kemduong": _trang("""<h1 data-e2e="challenge-title">#kemduong</h1>
<div data-e2e="challenge-item"><a href="https://www.tiktok.com/@ban_a/video/111"><strong data-e2e="video-views">12,3K</strong></a>
 <a data-e2e="challenge-item-avatar" href="/@ban_a?lang=vi-VN">a</a><div data-e2e="challenge-item-desc">Kem dưỡng da khô</div></div>
<div data-e2e="challenge-item"><a href="https://www.tiktok.com/@ban_b/video/333"><strong data-e2e="video-views">1,2 Tr</strong></a>
 <a data-e2e="challenge-item-avatar" href="/@ban_b?lang=vi-VN">b</a><div data-e2e="challenge-item-desc">Váy đẹp</div></div>"""),
    "tiktok.com/@ban_a/video/111": _video("Kem dưỡng da khô mùa đông", ("khach9",), json_=J111),
    "tiktok.com/@ban_b/video/333": _video("Váy hoa nhí mặc đi biển", (), them=
                                          '<a href="https://shop.tiktok.com/view/product/1729000333?region=VN">Váy hoa nhí 299.000₫</a>'),
    "tiktok.com/@doi_thu/video/444": _video("Video đối thủ", ("khach1", "khach2", "doi_thu", "chu_nick")),
    "tiktok.com/@doi_thu": _trang('<div data-e2e="user-post-item"><a href="https://www.tiktok.com/@doi_thu/video/444">v</a></div>'),
    "tiktok.com/@khach1": _trang("""<h1 data-e2e="user-title">khach1</h1>
<button data-e2e="follow-button" onclick="ck('follow');this.textContent='Đang theo dõi'">Theo dõi</button>"""),
    "tiktok.com/@khach2": _trang('<button data-e2e="follow-button">Đang theo dõi</button>'),
    "tiktok.com/@chu_nick": _trang('<button data-e2e="follow-button" onclick="ck(\'follow_minh\')">Theo dõi</button>'),
    "tiktok.com/@doi_thu_khac": _trang("<p>trống</p>"),
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
    print(f"SKIP các test trình duyệt: máy này không có playwright ({e})")


def _mo_trinh(pw):
    try:
        return pw.chromium.launch(headless=True)
    except Exception:
        goc_pw = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
        exe = sorted(goc_pw.glob("chromium-*/chrome-linux*/chrome")) + sorted(goc_pw.glob("chromium-*/chrome-win*/chrome.exe"))
        return pw.chromium.launch(headless=True, executable_path=str(exe[-1])) if exe else None


if co_pw:
    tam = Path(tempfile.mkdtemp())
    w.THU_MUC = tam                       # CSV quét không ghi vào thư mục Worker của repo
    for ten in ("a.mp4", "1.jpg", "2.jpg"):
        (tam / ten).write_bytes(b"\0" * 64)
    VIDEO, ANH = [str(tam / "a.mp4")], [str(tam / "1.jpg"), str(tam / "2.jpg")]
    with sync_playwright() as pw:
        trinh = _mo_trinh(pw)
        if trinh is None:
            print("SKIP các test trình duyệt: không có Chromium trên máy này")
        else:
            ctx = trinh.new_context(viewport={"width": 1280, "height": 900})
            ctx.route("**/*", _phuc_vu)

            def chay(ham, ts, doc="", **kw):
                page = ctx.new_page()
                nc = NguCanhGia(ts, page=page, **kw)
                try:
                    kq = ham(nc)
                except Exception as e:  # noqa: BLE001
                    kq = e
                ck = page.evaluate("window.__ck || []")
                them = page.evaluate(doc) if doc else None
                page.close()
                return nc, kq, ck, them

            def thu(ten, nc, kq, ck, them=True):
                check(f"{ten} chạy thử: không cú bấm/Enter công khai nào", ck == [], ck)
                check(f"{ten} chạy thử: không báo thành công giả, có báo 'sẽ', câu cuối nói rõ chạy thử",
                      not any(s["kq"] == "thanh_cong" for s in nc.su) and any(s["kq"] == "thong_tin" for s in nc.su)
                      and isinstance(kq, str) and kq.startswith("Chạy thử") and them, (kq, nc.su))

            CHIP = "(document.getElementById('chip') || {}).textContent || ''"

            # bình luận theo từ khoá
            ts = {"tu_khoa": "kem dưỡng", "san_pham": "sp1", "so_video": 10, "toi_da": 3, "thich": True, "che_do": "dang_luon"}
            ai = {"noi_dung": "Da mình cũng khô, dùng loại có ceramide thấy đỡ hẳn"}
            nc, kq, ck, _ = chay(tt.tt_binh_luan_tu_khoa, ts, chay_thu=True, ai=ai)
            bn = nc.ten_goi("ban_nhap")
            thu("tt_binh_luan_tu_khoa", nc, kq, ck, len(bn) == 2 and "Sẽ làm" in str(kq))
            check("tt_binh_luan_tu_khoa chạy thử: nháp bình luận TikTok cho 2 video, bỏ video của chính nick",
                  [b[2]["link_goc"] for b in bn] == ["https://www.tiktok.com/@ban_a/video/111",
                                                      "https://www.tiktok.com/@ban_b/video/333"]
                  and all(b[2]["noi_dang"] == "tiktok" and b[2]["loai"] == "binh_luan" and b[2]["san_pham_id"] == "sp1"
                          for b in bn) and nc.ten_goi("ai")[0][1][0] == "viet_binh_luan", (bn, nc.su))
            nc, kq, ck, _ = chay(tt.tt_binh_luan_tu_khoa, ts, ai=ai)
            okb = [s for s in nc.su if s["kq"] == "thanh_cong"]
            check("tt_binh_luan_tu_khoa chạy thật: thả tim + bình luận đọc lại thấy, gửi bằng nút",
                  ck.count("like") == 2 and ck.count("post") == 2 and len([s for s in okb if s["hd"] == "binh_luan"]) == 2
                  and not [c for c in ck if c.startswith("enter")]
                  and "tiktok:binh_luan:https://www.tiktok.com/@ban_a/video/111" in nc._da, (nc.su, ck))

            # theo dõi người xem của đối thủ
            ts = {"doi_thu": "@doi_thu\nhttps://www.tiktok.com/@doi_thu_khac", "so_video": 3, "toi_da": 10}
            nc, kq, ck, _ = chay(tt.tt_follow_doi_thu, ts, chay_thu=True)
            sk = [(s["kq"], s["link"].rsplit("@", 1)[-1]) for s in nc.su if s["hd"] == "theo_doi"]
            mo = [g[1][0] for g in nc.ten_goi("mo")]
            thu("tt_follow_doi_thu", nc, kq, ck, ("thong_tin", "khach1") in sk and ("bo_qua", "khach2") in sk)
            check("tt_follow_doi_thu: không xét chính nick và kênh đối thủ",
                  "https://www.tiktok.com/@chu_nick" not in mo and mo.count("https://www.tiktok.com/@doi_thu") == 1, mo)
            nc, kq, ck, _ = chay(tt.tt_follow_doi_thu, ts)
            check("tt_follow_doi_thu chạy thật: bấm Theo dõi, đọc lại 'Đang theo dõi', ghi khoá",
                  ck == ["follow"] and [s["kq"] for s in nc.su if s["hd"] == "theo_doi" and "khach1" in s["link"]] == ["thanh_cong"]
                  and "tiktok:theo_doi:khach1" in nc._da, (nc.su, ck))

            # quét CSV theo hashtag
            nc, kq, ck, _ = chay(tt.tt_quet_csv, {"kieu_quet": "hashtag", "dau_vao": "#kemduong", "so_dong": 10,
                                                  "mo_tung_video": True}, chay_thu=True)
            dong = list(csv.DictReader(open(nc.tep[0], encoding="utf-8-sig"))) if nc.tep else []
            check("tt_quet_csv: CSV gửi về MinMin, không bấm gì",
                  ck == [] and len(nc.tep) == 1 and nc.tep[0].name.startswith("tiktok_hashtag_") and len(dong) == 2
                  and any(s["hd"] == "quet" and s["kq"] == "thanh_cong" and "MinMin" in s["ct"] for s in nc.su), (kq, nc.su))
            d = {x["link"].rsplit("/", 1)[-1]: x for x in dong}
            check("tt_quet_csv: lượt xem từ JSON nhúng, thiếu thì từ thẻ; tác giả; giỏ hàng",
                  d.get("111", {}).get("luot_xem") == "45000" and d.get("333", {}).get("luot_xem") == "1200000"
                  and d.get("111", {}).get("tac_gia") == "ban_a" and d.get("111", {}).get("luot_thich") == "1200"
                  and d.get("111", {}).get("co_gio_hang") == "có" and d.get("333", {}).get("co_gio_hang") == "có"
                  and d.get("111", {}).get("ngay_dang", "").startswith("2025-10-25"), dong)
            nc, kq, ck, _ = chay(tt.tt_quet_csv, {"kieu_quet": "tim_kiem", "dau_vao": "kem", "so_dong": 10,
                                                  "mo_tung_video": False})
            dong = list(csv.DictReader(open(nc.tep[0], encoding="utf-8-sig"))) if nc.tep else []
            check("tt_quet_csv tìm kiếm không mở video: đủ 3 thẻ, số trên thẻ, tác giả từ search-card-user-link",
                  len(dong) == 3 and dong[0]["so_tren_the"] == "175.4K" and dong[2]["so_tren_the"] == "5415"
                  and dong[2]["tac_gia"] == "ban_b" and dong[0]["co_gio_hang"] == "chưa mở video", dong)

            # quét giỏ hàng
            nc, kq, ck, _ = chay(tt.tt_quet_gio_hang, {"tu_khoa": "áo thun", "so_video": 10, "chi_co_gio": True})
            dong = list(csv.DictReader(open(nc.tep[0], encoding="utf-8-sig"))) if nc.tep else []
            check("tt_quet_gio_hang: chỉ video có giỏ hàng, tên + giá + link sản phẩm (JSON và DOM)",
                  ck == [] and [x["ten_san_pham"] for x in dong] == ["Áo thun basic trắng", "Váy hoa nhí 299.000₫"]
                  and [x["gia"] for x in dong] == ["199.000₫", "299.000₫"]
                  and dong[0]["link_san_pham"] == "https://www.tiktok.com/view/product/1729000111"
                  and "view/product/1729000333" in dong[1]["link_san_pham"] and dong[0]["luot_xem"] == "45000", (dong, nc.su))

            # đăng video gắn giỏ hàng
            kho = lambda: [{"id": 31, "noi_dung": "Áo thun mới về", "tep_cuc_bo": list(VIDEO)}]  # noqa: E731
            ts = {"kho": "chung", "san_pham_shop": "Áo thun basic trắng", "ten_hien_thi": "Áo basic giá tốt", "so_bai": 1}
            nc, kq, ck, chip = chay(tt.tt_dang_video_gio_hang, ts, CHIP,
                                    chay_thu=True, kho=kho())
            thu("tt_dang_video_gio_hang", nc, kq, ck, nc.ten_goi("xong_kho")[0][1][:3] == (31, False, False))
            check("tt_dang_video_gio_hang chạy thử: đi hết bước chọn sản phẩm + tên hiển thị, dừng trước Đăng",
                  chip == "Sản phẩm: Áo basic giá tốt" and any("dừng trước nút Đăng" in s["ct"] for s in nc.su), (chip, nc.su))
            nc, kq, ck, chip = chay(tt.tt_dang_video_gio_hang, ts, CHIP, kho=kho())
            xk = nc.ten_goi("xong_kho")
            check("tt_dang_video_gio_hang chạy thật: gắn sản phẩm rồi bấm Đăng, xong_kho(ok)",
                  ck == ["post"] and xk and xk[0][1][:3] == (31, True, True) and "tiktokstudio/content" in xk[0][2]["link"]
                  and any(s["kq"] == "thanh_cong" for s in nc.su), (kq, nc.su, ck))
            nc, kq, ck, chip = chay(tt.tt_dang_video_gio_hang, dict(ts, san_pham_shop="Mũ lưỡi trai"),
                                    CHIP, chay_thu=True, kho=kho())
            check("tt_dang_video_gio_hang: không khớp sản phẩm -> lỗi rõ, không gắn bừa, bài về hàng chờ",
                  ck == [] and chip == "" and nc.ten_goi("xong_kho")[0][1][:3] == (31, False, False)
                  and any(s["kq"] == "loi" and "không có sản phẩm nào khớp" in s["ct"] for s in nc.su), (nc.su, chip))

            # đăng ảnh slide
            nc, kq, ck, _ = chay(tt.tt_dang_anh_kho, {"kho": "chung"}, chay_thu=True,
                                 kho=[{"id": 41, "noi_dung": "Lookbook thu", "tep_cuc_bo": list(ANH)}])
            thu("tt_dang_anh_kho", nc, kq, ck, nc.ten_goi("xong_kho")[0][1][:3] == (41, False, False)
                and any("Chọn 2 ảnh" in g[1][0] for g in nc.ten_goi("nhat_ky")))
            nc, kq, ck, _ = chay(tt.tt_dang_anh_kho, {"kho": "chung"}, kho=[{"id": 41, "noi_dung": "Lookbook thu",
                                                                           "tep_cuc_bo": list(ANH)}])
            check("tt_dang_anh_kho chạy thật: chọn ô nhận ảnh, bấm Đăng, xong_kho(ok)",
                  ck == ["post"] and nc.ten_goi("xong_kho")[0][1][:3] == (41, True, True), (kq, nc.su))

            # nháp bài đăng có video
            nc, kq, ck, _ = chay(tt.dang_ban_nhap, {"ban_nhap_id": 5, "loai": "bai_dang", "noi_dung": "Caption AI",
                                                    "tep_cuc_bo": list(VIDEO)})
            check("dang_ban_nhap:tiktok bài đăng có video: đăng qua TikTok Studio, xong_ban_nhap(ok)",
                  ck == ["post"] and nc.ten_goi("xong_ban_nhap")[0][1][:2] == (5, True), (kq, nc.su))
            nc, kq, ck, _ = chay(tt.tt_dang_ai, {"so_bai": 1}, ban_nhap_duyet=[
                {"id": 6, "loai": "bai_dang", "noi_dung": "Caption AI", "tep_cuc_bo": list(VIDEO)}])
            check("tt_dang_ai chạy thật: đăng nháp có video",
                  ck == ["post"] and nc.ten_goi("xong_ban_nhap")[0][1][:2] == (6, True)
                  and [s["hd"] for s in nc.su if s["kq"] == "thanh_cong"] == ["dang_video"], (kq, nc.su))
            trinh.close()

# ---------------------------------------------------------------- 5. quy ước mã nguồn
s = (WORKER / "ky_nang_tiktok.py").read_text(encoding="utf-8")
check("ky_nang_tiktok.py: không em dash, không .click/.fill/.type", "—" not in s and ".click(" not in s
      and ".fill(" not in s and ".type(" not in s)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
