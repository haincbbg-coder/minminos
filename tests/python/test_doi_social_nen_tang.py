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
check("đủ mẫu ngoài Facebook (>= 34)", tong >= 34, tong)
so_yt = sum(1 for m in kb.MAU if m["nen_tang"] == "youtube")
check("YouTube đủ 7 mẫu", so_yt == 7, so_yt)
for nt, mod in TEP.items():
    k = f"dang_ban_nhap:{nt}"
    check(f"{k} có trong KICH_BAN", callable(mod.KICH_BAN.get(k)))
    la = [x for x in mod.KICH_BAN if not x.startswith("dang_ban_nhap:") and x not in kb.THEO_ID]
    check(f"ky_nang_{nt} không khai id lạ", not la, la)

# ---------------------------------------------------------------- 1b. YouTube: hàm thuần
import ky_nang_quet  # noqa: E402
check("quét tài khoản có YouTube, giữ nền tảng cũ",
      set(ky_nang_quet._QUET) >= {"facebook", "instagram", "tiktok", "threads", "youtube"})
yt = ky_nang_youtube
check("YT: chuẩn link shorts / youtu.be / &pp= về watch?v=",
      yt.chuan_link("https://www.youtube.com/shorts/AbCdEfGhIjK?feature=share") ==
      ("https://www.youtube.com/watch?v=AbCdEfGhIjK", "AbCdEfGhIjK")
      and yt.chuan_link("https://youtu.be/AbCdEfGhIjK")[1] == "AbCdEfGhIjK"
      and yt.chuan_link("https://www.youtube.com/watch?v=AbCdEfGhIjK&pp=ygUF")[0].endswith("v=AbCdEfGhIjK")
      and yt.chuan_link("https://www.youtube.com/@kenh")[1] == "")
td, mt = yt.tach_tieu_de({"noi_dung": "Kem <dưỡng> ẩm " + "x" * 120 + "\nMô tả dòng 1\nDòng 2"})
check("YT: dòng đầu là tiêu đề <= 100 ký tự, bỏ < >, phần còn lại là mô tả",
      len(td) <= 100 and "<" not in td and mt == "Mô tả dòng 1\nDòng 2", (td, mt))
td, mt = yt.tach_tieu_de({"tieu_de": "Tiêu đề", "noi_dung": "Tiêu đề\nMô tả"})
check("YT: có trường tieu_de thì mô tả bỏ phần trùng", (td, mt) == ("Tiêu đề", "Mô tả"), (td, mt))
mt = yt.them_link_tiep_thi("Mô tả", "https://s.shopee.vn/abc\nGiảm 10%: https://lazada.vn/x")
check("YT: link tiếp thị nối cuối mô tả, link trần thêm 'Mua tại:'",
      mt == "Mô tả\n\nMua tại: https://s.shopee.vn/abc\nGiảm 10%: https://lazada.vn/x", mt)
check("YT: mô tả kèm link vẫn <= 5000", len(yt.them_link_tiep_thi("a" * 6000, "https://x.y/z")) <= 5000)
import random as _r
r = _r.Random(1)
ra = {yt.spin("{Mua|Đặt} tại {đây|link}: https://x.y", r) for _ in range(40)}
check("YT: spin {a|b} ra đủ biến thể, giữ link", len(ra) == 4 and all(x.endswith("https://x.y") for x in ra), ra)
check("YT: spin lồng nhau", yt.spin("{a|{b|c}}", _r.Random(2)) in ("a", "b", "c"))
check("YT: đọc lượt xem kiểu Việt",
      yt.so_luot_xem("973 N lượt xem") == 973000 and yt.so_luot_xem("1,2 Tr lượt xem") == 1200000
      and yt.so_luot_xem("1.234 lượt xem") == 1234 and yt.so_luot_xem("1.2M views") == 1200000
      and yt.so_luot_xem("2 Tỷ lượt xem") == 2000000000 and yt.so_luot_xem("") == 0)
check("YT: mẫu nhận diện bỏ link", yt.mau_nhan_dien("https://x.y/z Mua ở đây nhé") == "Mua ở đây nhé")

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

# YouTube: mẫu AI + nháp + ghim link (không cần trình duyệt)
nc = NguCanhGia("youtube", {"so_bai": 1}, chay_thu=True)
ky_nang_youtube.yt_dang_ai(nc)
check("yt_dang_ai chạy thử: không giữ nháp, có báo 'sẽ ...'", not nc.ten_goi("lay_ban_nhap")
      and any(s["kq"] == "thong_tin" for s in nc.su), nc.goi)
nc = NguCanhGia("youtube", {"so_bai": 1}, ban_nhap_duyet=[{"id": 11, "noi_dung": "Tiêu đề\nMô tả", "tep_cuc_bo": []}])
try:
    ky_nang_youtube.yt_dang_ai(nc)
except LoiKyNang:
    pass
xb = nc.ten_goi("xong_ban_nhap")
check("yt_dang_ai: nháp không có video -> xong_ban_nhap(ok=False) nêu rõ 'video'",
      xb and xb[0][1][:2] == (11, False) and "video" in xb[0][2]["loi"], xb)
nc = NguCanhGia("youtube", {"ban_nhap_id": 12, "loai": "bai_dang", "noi_dung": "T\nM"}, chay_thu=True)
kq = ky_nang_youtube.dang_ban_nhap(nc)
check("dang_ban_nhap:youtube chạy thử: không mở trang, không đánh dấu nháp",
      not nc.ten_goi("mo") and not nc.ten_goi("xong_ban_nhap") and nc.su[-1]["kq"] == "thong_tin", nc.goi)
nc = NguCanhGia("youtube", {"ban_nhap_id": 13, "loai": "bai_dang", "noi_dung": "T\nM", "tep_cuc_bo": ["/tmp/a.jpg"]})
try:
    ky_nang_youtube.dang_ban_nhap(nc)
    loi = None
except LoiKyNang as e:
    loi = e
check("dang_ban_nhap:youtube bài không có video -> lỗi rõ + xong_ban_nhap(ok=False)",
      loi is not None and "video" in str(loi) and nc.ten_goi("xong_ban_nhap")[0][1][:2] == (13, False), loi)
nc = NguCanhGia("youtube", {"noi_dung": "{Mua|Đặt} tại: https://s.shopee.vn/abc",
                            "links": ["https://www.youtube.com/shorts/AbCdEfGhIjK", "https://youtu.be/ZZZZZZZZZZZ"],
                            "ghim": True}, chay_thu=True)
nc._da.add("youtube:ghim_link:ZZZZZZZZZZZ")
kq = ky_nang_youtube.yt_binh_luan_ghim_link(nc)
check("yt_binh_luan_ghim_link chạy thử: báo 'sẽ bình luận ... ghim', video đã làm thì bỏ qua, không ghi khoá",
      [s["kq"] for s in nc.su] == ["thong_tin", "bo_qua"] and "ghim" in nc.su[0]["ct"]
      and "https://s.shopee.vn/abc" in nc.su[0]["ct"] and not nc.ten_goi("ghi_da_lam")
      and str(kq).startswith("Chạy thử"), (kq, nc.su))

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


YT_JS = """<script>
function themLuong(tg, chu, dau, cuaChu) {
  var t = document.createElement('ytd-comment-thread-renderer');
  t.innerHTML = '<ytd-comment-view-model id="comment"><a id="author-text" href="/' + tg + '">' + tg + '</a> '
    + (cuaChu ? '<ytd-author-comment-badge-renderer creator></ytd-author-comment-badge-renderer>' : '')
    + '<span id="content-text"></span><div id="action-menu"><button aria-label="Menu tác vụ">m</button></div>'
    + '<div id="reply-button-end"><button aria-label="Phản hồi">Phản hồi</button></div></ytd-comment-view-model>';
  t.querySelector('#content-text').textContent = chu;
  t.querySelector('#action-menu button').onclick = function () { moMenu(t); };
  t.querySelector('#reply-button-end button').onclick = function () { moTraLoi(t); };
  var ds = document.getElementById('ds');
  if (dau) ds.insertBefore(t, ds.firstChild); else ds.appendChild(t);
}
function moMenu(t) {
  var p = document.createElement('ytd-menu-popup-renderer');
  p.innerHTML = '<ytd-menu-service-item-renderer>Báo vi phạm</ytd-menu-service-item-renderer><ytd-menu-service-item-renderer>Ghim</ytd-menu-service-item-renderer>';
  p.children[1].onclick = function () {
    p.remove();
    var d = document.createElement('yt-confirm-dialog-renderer');
    d.innerHTML = 'Ghim bình luận này? <div id="confirm-button"><button>Ghim</button></div>';
    d.querySelector('button').onclick = function () {
      ck('pin'); d.remove();
      var b = document.createElement('ytd-pinned-comment-badge-renderer'); b.textContent = 'Đã ghim bởi @kenhtoi';
      t.querySelector('#comment').prepend(b);
    };
    document.body.appendChild(d);
  };
  document.body.appendChild(p);
}
function moTraLoi(t) {
  ck('reply_open');
  var d = document.createElement('ytd-comment-reply-dialog-renderer');
  d.innerHTML = '<div id="contenteditable-root" contenteditable="true" style="min-width:200px;min-height:20px;border:1px solid"></div>'
    + '<div id="submit-button"><button aria-label="Phản hồi">Phản hồi</button></div>';
  d.querySelector('button').onclick = function () {
    ck('reply'); var r = document.createElement('div'); r.id = 'replies';
    r.textContent = d.querySelector('#contenteditable-root').innerText; d.remove(); t.appendChild(r);
  };
  t.appendChild(d);
}
</script>"""


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
    "youtube.com/watch?v=": _trang(YT_JS + """
<ytd-watch-metadata><div id="title"><h1>Kem dưỡng ẩm review</h1></div>
 <div id="owner"><div id="subscribe-button"><button onclick="ck('sub');this.textContent='Đã đăng ký'">Đăng ký</button></div></div>
 <like-button-view-model><button aria-label="Thích video này cùng với 10 người khác" aria-pressed="false"
   onclick="ck('like');this.setAttribute('aria-pressed','true')">10</button></like-button-view-model>
 <like-button-view-model><button aria-label="Không thích video này" aria-pressed="false" onclick="ck('dislike')">x</button></like-button-view-model>
 <div id="description">Mô tả video kem dưỡng</div></ytd-watch-metadata>
<ytd-comments id="comments"><ytd-comments-header-renderer>
 <div id="placeholder-area" onclick="document.getElementById('box').style.display='block'">Viết bình luận...</div>
 <div id="box" style="display:none"><div id="contenteditable-root" contenteditable="true"
   style="min-width:300px;min-height:24px;border:1px solid"></div>
  <div id="submit-button"><button aria-label="Bình luận" onclick="ck('comment');var t=document.getElementById('contenteditable-root');
    themLuong('@kenhtoi', t.innerText, true);t.innerText=''">Bình luận</button></div></div>
</ytd-comments-header-renderer><div id="ds"></div></ytd-comments>
<script>themLuong('@kenhtoi', 'Cảm ơn mọi người đã xem', false, true); themLuong('@khach1', 'Giá bao nhiêu vậy shop?', false);</script>"""),
    "youtube.com/results": _trang("""
<ytd-video-renderer><a id="thumbnail" href="/watch?v=BBBBBBBBBBB&amp;pp=ygU">1:13 Đang phát<badge-shape aria-label="1 phút, 13 giây">1:13</badge-shape></a>
 <h3><a href="/watch?v=BBBBBBBBBBB&amp;pp=ygU" aria-label="Kem dưỡng ẩm tốt nhất 1 phút"><yt-formatted-string>Kem dưỡng ẩm tốt nhất</yt-formatted-string></a></h3>
 <a href="/@kenhA" aria-label="Chuyển đến kênh Kênh A"></a><a href="/@kenhA">Kênh A</a>
 <div id="metadata-line"><span class="inline-metadata-item">153 N lượt xem</span><span class="inline-metadata-item">2 ngày trước</span></div>
 <button aria-label="Menu tác vụ">m</button></ytd-video-renderer>
<ytd-video-renderer><a aria-label="Quảng cáo: Mua kem" href="https://www.googleadservices.com/pagead/aclk?x">ad</a>
 <a href="/watch?v=CCCCCCCCCCC">Video quảng cáo</a></ytd-video-renderer>
<h2>Shorts</h2><div class="ke"><div class="o"><a href="/shorts/DDDDDDDDDDD"><h3>Shorts da khô</h3></a><span>973 N lượt xem</span></div>
 <div class="o"><a href="/shorts/EEEEEEEEEEE"><h3>Shorts thứ hai</h3></a><span>1,2 Tr lượt xem</span></div></div>"""),
    "youtube.com/@kenhtoi/videos": _trang("""<ytd-rich-grid-renderer><a href="/watch?v=AAAAAAAAAAA">Video 1</a></ytd-rich-grid-renderer>"""),
    "youtube.com/@kenhtoi/shorts": _trang("""<ytd-rich-grid-renderer><a href="/shorts/FFFFFFFFFFF">Shorts 1</a></ytd-rich-grid-renderer>"""),
    "www.youtube.com/": _trang("""<ytd-masthead><button id="avatar-btn" aria-label="Trình đơn tài khoản"
  onclick="document.getElementById('acc').style.display='block'">A</button></ytd-masthead>
<div id="acc" style="display:none"><ytd-active-account-header-renderer><span id="account-name">Kênh Tôi</span>
 <span id="channel-handle">@kenhtoi</span><a href="/@kenhtoi">Xem kênh của bạn</a></ytd-active-account-header-renderer></div>"""),
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
        # Bản playwright trong .venv có thể mới hơn trình duyệt cài sẵn: dùng thẳng chromium có trong
        # PLAYWRIGHT_BROWSERS_PATH (KHÔNG chạy `playwright install`). Máy CI không có trình duyệt -> bỏ qua.
        goc_pw = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
        exe = sorted(goc_pw.glob("chromium-*/chrome-linux*/chrome")) + \
            sorted(goc_pw.glob("chromium-*/chrome-win*/chrome.exe"))
        if not exe:
            return None
        return pw.chromium.launch(headless=True, executable_path=str(exe[-1]))


if co_pw:
    w.THU_MUC = Path(tempfile.mkdtemp())       # CSV quét không ghi vào thư mục Worker của repo
    with sync_playwright() as pw:
        trinh = _mo_trinh(pw)
        if trinh is None:
            print("SKIP các test trình duyệt: không có Chromium trên máy này")
        if trinh is not None:
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

            # YouTube tương tác theo link (Shorts chuẩn về watch?v=)
            ts = {"links": ["https://www.youtube.com/shorts/AAAAAAAAAAA"], "thich": True, "dang_ky": True,
                  "binh_luan": True, "cau_binh_luan": "Video hay quá shop ơi"}
            nc, kq, ck = chay("youtube", ky_nang_youtube.yt_tuong_tac_link, ts, chay_thu=True)
            thu("yt_tuong_tac_link", nc, kq, ck, lambda nc: {s["hd"] for s in nc.su} >= {"thich", "binh_luan", "theo_doi"}
                and any("watch?v=AAAAAAAAAAA" in g[1][0] for g in nc.ten_goi("mo")))
            nc, kq, ck = chay("youtube", ky_nang_youtube.yt_tuong_tac_link, ts)
            ok_hd = {s["hd"] for s in nc.su if s["kq"] == "thanh_cong"}
            check("yt_tuong_tac_link chạy thật: thích + đăng ký + bình luận đều đọc lại thấy, không bấm Không thích",
                  ok_hd == {"thich", "binh_luan", "theo_doi"} and {"like", "sub", "comment"} <= set(ck)
                  and "dislike" not in ck, (nc.su, ck, kq))
            check("yt_tuong_tac_link: khoá chống lặp theo mã video",
                  [g[1][0] for g in nc.ten_goi("ghi_da_lam")] == ["youtube:binh_luan:AAAAAAAAAAA"], nc.ten_goi("ghi_da_lam"))
            # Bình luận + ghim link tiếp thị (chạy thật)
            nc, kq, ck = chay("youtube", ky_nang_youtube.yt_binh_luan_ghim_link,
                              {"noi_dung": "Mua tại đây nha: https://s.shopee.vn/abc", "ghim": True,
                               "links": ["https://www.youtube.com/watch?v=AAAAAAAAAAA&pp=x"]})
            check("yt_binh_luan_ghim_link chạy thật: bình luận hiện rồi ghim (thấy 'Đã ghim bởi')",
                  ck == ["comment", "pin"] and [(s["hd"], s["kq"]) for s in nc.su] ==
                  [("binh_luan", "thanh_cong"), ("quan_ly_bai", "thanh_cong")], (nc.su, ck, kq))
            # Trả lời bình luận AI (chạy thử -> nháp, bỏ bình luận của chính kênh)
            nc, kq, ck = chay("youtube", ky_nang_youtube.yt_tra_loi_binh_luan,
                              {"so_video": 2, "nguon_video": "ca_hai", "che_do": "chay_thu", "san_pham": "sp1"},
                              chay_thu=True, ai={"noi_dung": "Bạn nhắn tin riêng cho shop nhé."})
            bn = nc.ten_goi("ban_nhap")
            check("yt_tra_loi_binh_luan chạy thử: kênh đọc từ menu ảnh đại diện, video + Shorts, chỉ nháp cho khách",
                  ck == [] and len(bn) == 2 and all(b[2]["noi_dang"] == "youtube" and b[2]["loai"] == "tra_loi"
                                                    and "khach1" in b[2]["link_goc"] for b in bn)
                  and {b[2]["link_goc"].split("#")[0] for b in bn} ==
                  {"https://www.youtube.com/watch?v=AAAAAAAAAAA", "https://www.youtube.com/watch?v=FFFFFFFFFFF"},
                  (bn, nc.su, kq, [g[1][0] for g in nc.ten_goi("nhat_ky")][-20:]))
            # dang_ban_nhap:youtube trả lời đúng bình luận (chạy thật)
            nc, kq, ck = chay("youtube", ky_nang_youtube.dang_ban_nhap,
                              {"ban_nhap_id": 31, "loai": "tra_loi", "noi_dung": "Shop gửi giá qua tin nhắn nhé",
                               "link_goc": w.gan_muc_tieu("https://www.youtube.com/watch?v=AAAAAAAAAAA", "@khach1",
                                                          "Giá bao nhiêu vậy shop?")})
            xb = nc.ten_goi("xong_ban_nhap")
            check("dang_ban_nhap:youtube tra_loi: bấm Phản hồi đúng bình luận, đọc lại thấy câu trả lời",
                  ck == ["reply_open", "reply"] and xb and xb[0][1][:2] == (31, True), (ck, xb, kq))
            # Quét CSV
            NguCanhGia.gui_tep_ket_qua = lambda self, p: self._g("gui_tep", str(p))
            nc, kq, ck = chay("youtube", ky_nang_youtube.yt_quet_csv, {"kieu_quet": "tim_kiem", "dau_vao": "kem dưỡng",
                                                                         "so_dong": 10})
            del NguCanhGia.gui_tep_ket_qua
            csvs = list((w.THU_MUC / "quet").glob("youtube_tim_kiem_*.csv"))
            noi = csvs[0].read_text(encoding="utf-8-sig") if csvs else ""
            check("yt_quet_csv: video + Shorts, bỏ quảng cáo, chuẩn link, lượt xem số, gửi tệp về MinMin",
                  ck == [] and len(csvs) == 1 and "https://www.youtube.com/watch?v=BBBBBBBBBBB," in noi
                  and "Kem dưỡng ẩm tốt nhất" in noi and "Kênh A" in noi and "153000" in noi and "1:13" in noi
                  and "https://www.youtube.com/shorts/DDDDDDDDDDD" in noi and "1200000" in noi
                  and "CCCCCCCCCCC" not in noi and nc.ten_goi("gui_tep"), (noi, nc.su))

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
            check("rd_tham_gia_sub chạy thật: Join -> subscribed (đọc lại), sub đã vào thì bỏ qua",
                  [s["kq"] for s in nc.su] == ["thanh_cong", "bo_qua"], (nc.su, ck))
            nc, kq, ck = chay("reddit", ky_nang_reddit.rd_dang_sub, {"sub": "r/vietnam", "tieu_de": "Hỏi về kem dưỡng",
                                                                     "noi_dung": "Nội dung"}, chay_thu=True)
            thu("rd_dang_sub", nc, kq, ck)
            trinh.close()

# ---------------------------------------------------------------- 5. quy ước mã nguồn
for p in sorted(WORKER.glob("ky_nang_*.py")) + [WORKER / "tien_ich_web.py"]:
    if p.name == "ky_nang_fb.py":
        continue
    s = p.read_text(encoding="utf-8")
    check(f"{p.name}: không em dash", "\u2014" not in s)
    check(f"{p.name}: không subprocess", "subprocess" not in s)
    check(f"{p.name}: không bấm .click() thẳng (mọi cú bấm qua nc.tay / cổng)", ".click(" not in s)
    check(f"{p.name}: không gõ bằng fill/type cả đoạn", ".fill(" not in s and ".type(" not in s)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
