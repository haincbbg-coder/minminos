"""Đội Social - Worker lõi (26.10.187): nạp kỹ năng động, NguCanh, chọn hàm đăng nháp, tự cập nhật an toàn,
so phiên bản, điều phối song song, và CHẠY THỬ không bấm nút công khai (Chromium headless trên một trang
HTML giả lập giao diện Facebook tối thiểu).

    .venv/bin/python tests/python/test_doi_social_worker.py
"""
import glob
import io
import json
import os
import random
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from _paths import ROOT  # noqa: E402

WORKER = ROOT / "apps" / "doi-social" / "worker"
sys.path.insert(0, str(WORKER))

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


import minmin_worker as mw  # noqa: E402
import ngu_canh  # noqa: E402
from ngu_canh import LoiKyNang, NguCanh  # noqa: E402

mw.NHAT_KY = Path(tempfile.mkdtemp()) / "worker.log"     # không ghi log test vào thư mục Worker thật

check("PHIEN_BAN là 26.10.187", mw.PHIEN_BAN == "26.10.187")


# ---------------------------------------------------------------------------- MinMin giả
class LoiMang(ConnectionError):
    pass


class LoiHttpGia(RuntimeError):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class MinMinGia(mw.MayChuGia):
    """Ghi mọi lời gọi; cho phép cài sẵn phản hồi và lỗi mạng."""

    def __init__(self, ts=None, **kw):
        super().__init__(ts or {}, in_ra=lambda s: None)
        self.loi_truoc = 0           # số lần đầu ném lỗi mạng
        self.loi_http = None
        self.con_lai_tra = None
        self.dung = False
        self.nhom = None
        self.da_lam_set = set()
        self.ket_qua_ds = []
        self.kw = kw

    def goi(self, method, duong, body=None, timeout=60):
        if self.loi_http:
            raise LoiHttpGia(self.loi_http)
        if self.loi_truoc > 0:
            self.loi_truoc -= 1
            self.goi_ds.append((method, duong, "LOI"))
            raise LoiMang("máy chủ tạm mất")
        d = duong.split("?")[0].replace("/doi-social/may/", "")
        if d.startswith("su-kien/") and self.con_lai_tra is not None:
            self.goi_ds.append((method, duong, body))
            return {"con_lai": self.con_lai_tra, "dung": self.dung}
        if d.startswith("dung/"):
            self.goi_ds.append((method, duong, body))
            return {"dung": self.dung}
        if d == "nhom-fb" and method == "GET" and self.nhom is not None:
            self.goi_ds.append((method, duong, body))
            return {"nhom": self.nhom}
        if d == "da-tuong-tac":
            self.goi_ds.append((method, duong, body))
            if method == "POST":
                self.da_lam_set.add(body["khoa"])
                return {"ok": True}
            import urllib.parse as up
            q = dict(up.parse_qsl(duong.split("?", 1)[1]))
            return {"da_lam": q.get("khoa") in self.da_lam_set}
        return super().goi(method, duong, body, timeout)

    def ket_qua(self, vid, ok_, thong_diep, buoc, anh=b"", dem=None):
        self.ket_qua_ds.append({"vid": vid, "ok": ok_, "thong_diep": thong_diep, "dem": dem, "anh": bool(anh)})

    def su_kien_ds(self):
        return [b for m, d, b in self.goi_ds if "/su-kien/" in d and isinstance(b, dict)]


def viec_mau(ky_nang="fb_tuong_tac_link", ts=None, chay_thu=False, han_muc=None, nghi=(0, 0), nick="n1", vid=7):
    return {"id": vid, "ky_nang": ky_nang, "nick_id": nick, "nick_ten": "Nick " + nick,
            "tham_so": {"kich_ban": ky_nang, "tham_so": ts or {}, "chay_thu": chay_thu,
                        "han_muc": han_muc if han_muc is not None else {}, "nghi_giay": list(nghi),
                        "nen_tang": ngu_canh.doan_nen_tang(ky_nang, ts or {})}}


# ---------------------------------------------------------------------------- 1. nạp động kỹ năng
tm = Path(tempfile.mkdtemp())
(tm / "ky_nang_thu_tot.py").write_text(
    "from ngu_canh import LoiKyNang\n"
    "def a(nc):\n    return 'a'\n"
    "def dn(nc):\n    return 'dn'\n"
    "KICH_BAN = {'tt_thu_a': a, 'dang_ban_nhap:tiktok': dn, 'khong_goi_duoc': 5}\n", encoding="utf-8")
(tm / "ky_nang_thu_hong.py").write_text("def x(:\n    pass\n", encoding="utf-8")
(tm / "ky_nang_thu_thoat.py").write_text("import sys\nsys.exit(4)\n", encoding="utf-8")
(tm / "ky_nang_thu_thieu.py").write_text("import khong_co_module_nay\n", encoding="utf-8")
(tm / "khong_phai_ky_nang.py").write_text("raise RuntimeError('không được nạp')\n", encoding="utf-8")
kb, loi = mw.nap_ky_nang(tm)
ten_loi = sorted(t for t, _ in loi)
check("nạp tệp tốt, bỏ giá trị không gọi được", set(kb) == {"tt_thu_a", "dang_ban_nhap:tiktok"}, kb)
check("tệp lỗi cú pháp / sys.exit / thiếu module bị bỏ qua và ghi lại",
      ten_loi == ["ky_nang_thu_hong.py", "ky_nang_thu_thieu.py", "ky_nang_thu_thoat.py"], ten_loi)
check("chỉ nạp tệp ky_nang_*.py", "khong_phai_ky_nang" not in sys.modules)
gui = mw.ds_kich_ban_gui(kb)
check("nhịp gửi id mẫu, bỏ khoá có ':' nhưng báo dang_ban_nhap", gui == ["dang_ban_nhap", "tt_thu_a"], gui)

kb_that, loi_that = mw.nap_ky_nang(WORKER)
MAU_FB = ["fb_dang_nhom_ai", "fb_dang_tuong_kho", "fb_dang_nhom_link", "fb_dang_tuong_ai", "fb_tuong_tac_link",
          "fb_nuoi_nick", "fb_binh_luan_nhom_sp", "fb_binh_luan_nhom_link", "fb_tra_loi_binh_luan",
          "fb_tra_loi_tin_nhan", "fb_tuong_tac_bai_app", "fb_nhan_tin_ds", "fb_tham_gia_nhom_sp"]
check("Worker thật nạp đủ 13 mẫu Facebook + dang_ban_nhap:facebook + fb_gui_tin",
      all(m in kb_that for m in MAU_FB + ["dang_ban_nhap:facebook", "fb_gui_tin"]),
      [m for m in MAU_FB if m not in kb_that])
check("tệp kỹ năng của Worker thật không lỗi", not loi_that, loi_that)
import ky_nang_fb  # noqa: E402
check("ky_nang_fb.LoiKyNang là ngu_canh.LoiKyNang", ky_nang_fb.LoiKyNang is ngu_canh.LoiKyNang)
check("ky_nang_fb.dang_bai cũ vẫn còn", callable(ky_nang_fb.dang_bai) and callable(ky_nang_fb.mo_trang))
check("mã Worker không chứa em dash",
      not any("\u2014" in p.read_text(encoding="utf-8") for p in list(WORKER.glob("*.py")) + list(WORKER.glob("*.txt"))))

import ast  # noqa: E402
cu_phap_38 = []
for p in [WORKER / f for f in ("minmin_worker.py", "ngu_canh.py", "ky_nang_fb.py", "nguoi.py", "fb_chung.py",
                               "fb_dang.py", "fb_nhom.py", "fb_tin.py", "fb_tuong_tac.py")]:
    try:
        ast.parse(p.read_text(encoding="utf-8"), feature_version=(3, 8))
    except SyntaxError as e:
        cu_phap_38.append(f"{p.name}: {e}")
check("cú pháp hợp Python 3.8", not cu_phap_38, cu_phap_38)

# ---------------------------------------------------------------------------- 2. chọn hàm theo việc
kb2 = dict(kb_that)
kb2["dang_ban_nhap:threads"] = lambda nc: "th"
h, _ = mw.chon_ham(kb2, {"ky_nang": "dang_ban_nhap", "tham_so": {"tham_so": {"noi_dang": "fb_nhom"}}})
check("dang_ban_nhap noi_dang fb_nhom -> hàm Facebook", h is kb_that["dang_ban_nhap:facebook"])
h, _ = mw.chon_ham(kb2, {"ky_nang": "dang_ban_nhap", "tham_so": {"noi_dang": "fb_tuong", "ban_nhap_id": 3}})
check("dang_ban_nhap (tham số phẳng) noi_dang fb_tuong -> hàm Facebook", h is kb_that["dang_ban_nhap:facebook"])
h, _ = mw.chon_ham(kb2, {"ky_nang": "dang_ban_nhap", "tham_so": {"tham_so": {"noi_dang": "threads"}}})
check("dang_ban_nhap noi_dang threads -> dang_ban_nhap:threads", h is kb2["dang_ban_nhap:threads"])
h, ly = mw.chon_ham({}, {"ky_nang": "dang_ban_nhap", "tham_so": {"tham_so": {"noi_dang": "reddit"}}})
check("nền tảng chưa có hàm đăng nháp -> từ chối có lý do", h is None and "reddit" in ly, ly)
h, ly = mw.chon_ham(kb2, {"ky_nang": "zz_khong_co"})
check("kỹ năng lạ -> từ chối 'cập nhật Worker'", h is None and "cập nhật Worker" in ly)
check("fb_dang_bai cũ đi đường riêng", mw.chon_ham({}, {"ky_nang": "fb_dang_bai"})[0] == "fb_dang_bai")

# ---------------------------------------------------------------------------- 3. NguCanh với MinMin giả
mc = MinMinGia()
ngu = []
nc = NguCanh(mc, viec_mau(han_muc={"thich": 2, "binh_luan": 1}, nghi=(3, 9)), ngu=ngu.append, rng=random.Random(1))
check("NguCanh đọc ts, nền tảng, chế độ", nc.ts == {} and nc.nen_tang == "facebook" and nc.che_do == "dang_luon"
      and not nc.chay_thu)
check("con_lai khởi tạo từ han_muc; hành động lạ = không giới hạn",
      nc.con_lai("thich") == 2 and nc.con_lai("chia_se") >= 10 ** 6)
r = nc.su_kien("thich", "thanh_cong", "đã thích", link="https://fb/1", nhom="N")
check("su_kien thành công giảm con_lai cục bộ", nc.con_lai("thich") == 1 and r["con_lai"]["thich"] == 1)
b = mc.su_kien_ds()[-1]
check("sự kiện gửi đúng dạng hợp đồng",
      set(b) == {"hanh_dong", "ket_qua", "chi_tiet", "link", "nhom", "san_pham", "ma"}
      and b["hanh_dong"] == "thich" and b["ket_qua"] == "thanh_cong" and b["link"] == "https://fb/1"
      and [d for m, d, _ in mc.goi_ds if "/su-kien/" in d][-1] == "/doi-social/may/su-kien/7", b)
nc.su_kien("thich", "bo_qua", "x")
nc.su_kien("binh_luan", "thong_tin", "chỉ thông tin")
check("đếm thành công/bỏ qua/lỗi (thong_tin không đếm)", nc.dem == {"thanh_cong": 1, "bo_qua": 1, "loi": 0}, nc.dem)
mc.con_lai_tra = {"thich": 0, "binh_luan": 5}
nc.su_kien("thich", "thanh_cong", "y")
check("con_lai máy chủ trả về ghi đè số cục bộ", nc.con_lai("thich") == 0 and nc.con_lai("binh_luan") == 5)
check("chưa dừng khi còn hạn mức hành động khác", not nc.nen_dung())
mc.con_lai_tra = {"thich": 0, "binh_luan": 0}
nc.su_kien("binh_luan", "thanh_cong", "z")
check("dừng khi mọi hạn mức về 0", nc.nen_dung())
nc2 = NguCanh(mc, viec_mau(), ngu=ngu.append)
mc.con_lai_tra = None
mc.dung = True
check("dừng khi máy chủ báo đợt bị huỷ (/may/dung)", nc2.nen_dung()
      and any(d == "/doi-social/may/dung/7" for _, d, _ in mc.goi_ds))
mc.dung = False
ngu.clear()
nc.nghi_thao_tac()
check("nghi_thao_tac ngủ trong [3, 9] giây", len(ngu) == 1 and 3 <= ngu[0] <= 9, ngu)

ngu.clear()
mc3 = MinMinGia()
mc3.loi_truoc = 2
nc3 = NguCanh(mc3, viec_mau(), ngu=ngu.append)
nc3.su_kien("thich", "thanh_cong", "sau khi mạng chập chờn")
check("mạng lỗi 2 lần: thử lại có giãn cách rồi thành công",
      ngu == [2.0, 5.0] and len([1 for _, d, b in mc3.goi_ds if "/su-kien/" in d]) == 3, (ngu, mc3.goi_ds))
mc3.loi_truoc = 10
ngu.clear()
try:
    nc3.su_kien("thich", "thanh_cong", "mất hẳn")
    mat = None
except LoiKyNang as e:
    mat = e
check("mạng lỗi quá 3 lần thử lại thì raise LoiKyNang", mat is not None and mat.ma == "mat_ket_noi"
      and ngu == [2.0, 5.0, 10.0], (mat, ngu))
mc3.loi_truoc = 0
mc3.loi_http = 400
ngu.clear()
try:
    nc3.ai("viet_binh_luan", {})
    e400 = None
except LoiKyNang as e:
    e400 = e
check("lỗi 4xx không thử lại", e400 is not None and ngu == [])
mc3.loi_http = None
kq_ai = nc3.ai("cham_bai", {"bai": {"chu": "x"}}, [b"\xff\xd8anh"])
goi_ai = [b for m, d, b in mc3.goi_ds if d == "/doi-social/may/ai"][-1]
check("ai() gửi viec_id/muc_dich/du_lieu/anh base64 và trả ket_qua",
      kq_ai.get("chon") is True and goi_ai["viec_id"] == 7 and goi_ai["muc_dich"] == "cham_bai"
      and goi_ai["anh"] == ["/9hhbmg="], goi_ai)

mc4 = MinMinGia()
mc4.kho = None


def _kho(method, duong, body=None, timeout=60, _goc=mc4.goi):
    if duong.startswith("/doi-social/may/kho/lay"):
        mc4.goi_ds.append((method, duong, body))
        return {"bai": {"id": 9, "noi_dung": "x", "tep": [{"luu": "a.jpg"}, {"luu": "../thoat.jpg"}, {"luu": "b.mp4"}]}}
    return _goc(method, duong, body, timeout)


mc4.goi = _kho
tai = []
mc4.tai_ve = lambda duong, dich: (tai.append(duong), Path(dich).write_bytes(b"1"))
nc4 = NguCanh(mc4, viec_mau("fb_dang_tuong_kho"))
bai = nc4.lay_kho()
check("lay_kho tải tệp về thư mục tạm của việc, bỏ tên tệp thoát thư mục",
      len(bai["tep_cuc_bo"]) == 2 and all(Path(p).is_file() and str(nc4.thu_muc_tam) in p for p in bai["tep_cuc_bo"])
      and tai == ["/doi-social/may/kho/tep/9/a.jpg", "/doi-social/may/kho/tep/9/b.mp4"], (bai, tai))
nc4.don_dep()

nc5 = NguCanh(MinMinGia(), viec_mau("fb_binh_luan_nhom_sp", {"che_do": "dang_luon"}, chay_thu=True))
check("cờ chay_thu của việc thắng che_do của tham số", nc5.chay_thu and nc5.che_do == "chay_thu")
nc6 = NguCanh(MinMinGia(), viec_mau("fb_binh_luan_nhom_sp", {"che_do": "duyet_truoc"}))
check("che_do duyet_truoc giữ nguyên khi không chạy thử", nc6.che_do == "duyet_truoc" and not nc6.chay_thu)
nc7 = NguCanh(MinMinGia(), {"id": 3, "ky_nang": "fb_gui_tin", "tham_so": {"khach_link": "x", "noi_dung": "y"}})
check("việc nội bộ tham số phẳng vẫn đọc được qua nc.ts", nc7.ts.get("noi_dung") == "y")
check("duoc_bam_cong_khai: chạy thử -> False, thật -> True",
      nc5.duoc_bam_cong_khai("bấm Đăng", "dang_tuong") is False and nc6.duoc_bam_cong_khai("x") is True)

dt = ngu_canh.doan_trang_thai
khong = (lambda s: False)
check("nhận biết đăng xuất/checkpoint/captcha theo nền tảng",
      dt("facebook", "https://www.facebook.com/login/?next=x", khong, khong) == "dang_xuat"
      and dt("facebook", "https://www.facebook.com/checkpoint/1501092823525282/", khong, khong) == "checkpoint"
      and dt("facebook", "https://www.facebook.com/", khong, khong) is None
      and dt("facebook", "https://www.facebook.com/", lambda s: "name='pass'" in s, khong) == "dang_xuat"
      and dt("facebook", "https://www.facebook.com/", khong, lambda m: "quá nhanh" in m) == "qua_nhanh"
      and dt("youtube", "https://accounts.google.com/v3/signin", khong, khong) == "dang_xuat"
      and dt("tiktok", "https://www.tiktok.com/foryou", lambda s: "captcha-verify" in s, khong) == "captcha"
      and dt("instagram", "https://www.instagram.com/challenge/abc", khong, khong) == "checkpoint"
      and dt("x", "https://x.com/i/flow/login", khong, khong) == "dang_xuat"
      and dt("reddit", "https://www.reddit.com/r/vietnam", lambda s: "recaptcha" in s, khong) == "captcha")
check("đoán nền tảng theo tiền tố mẫu và noi_dang",
      ngu_canh.doan_nen_tang("tt_nuoi_nick") == "tiktok" and ngu_canh.doan_nen_tang("x_dang_kho") == "x"
      and ngu_canh.doan_nen_tang("dang_ban_nhap", {"noi_dang": "instagram"}) == "instagram"
      and ngu_canh.doan_nen_tang("dang_ban_nhap", {"noi_dang": "fb_trang"}) == "facebook")
check("nhãn nút công khai", all(ngu_canh.la_nut_cong_khai(x) for x in ("Đăng", "Post", "Gửi", "Thích", "Like",
                                                                      "Tham gia nhóm", "Chia sẻ ngay", "Bình luận"))
      and not any(ngu_canh.la_nut_cong_khai(x) for x in ("Bạn đang nghĩ gì?", "Xem thêm", "Ảnh/video", "Đóng", "")))

# ---------------------------------------------------------------------------- 4. tự cập nhật + phiên bản
sp = mw.so_phien_ban
check("so phiên bản dạng số", sp("26.10.187") == (26, 10, 187) and sp("26.10.187") > sp("26.10.186")
      and sp("26.10.200") > sp("26.10.187") and sp("26.11.1") > sp("26.10.999") and sp("26.10.9") < sp("26.10.10")
      and sp("") == (0,) and sp("26.10.188b") == (26, 10, 188))


def _zip(muc: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for ten, noi in muc.items():
            z.writestr(ten, noi)
    return buf.getvalue()


td = Path(tempfile.mkdtemp())
(td / "worker.json").write_text('{"token": "bi-mat"}', encoding="utf-8")
(td / "worker.log").write_text("log cũ", encoding="utf-8")
(td / "minmin_worker.py").write_text("PHIEN_BAN = '1'", encoding="utf-8")
(td / "chay.bat").write_bytes(b"@echo off\r\n")
mt_bat = (td / "chay.bat").stat().st_mtime_ns
time.sleep(0.01)
ghi = mw.ap_dung_cap_nhat(_zip({"MinMinWorker/minmin_worker.py": "PHIEN_BAN = '2'",
                                "MinMinWorker/ky_nang_moi.py": "KICH_BAN = {}",
                                "MinMinWorker/worker.json": '{"token": "ke-gian"}',
                                "MinMinWorker/worker.log": "x",
                                "MinMinWorker/HUONG-DAN.txt": "hd",
                                "MinMinWorker/chay.bat": b"@echo off\r\n",
                                "MinMinWorker/la.exe": "MZ",
                                "MinMinWorker/__pycache__/a.py": "x"}), td)
check("cập nhật đè .py/.txt, thêm tệp mới",
      (td / "minmin_worker.py").read_text() == "PHIEN_BAN = '2'" and (td / "ky_nang_moi.py").is_file()
      and (td / "HUONG-DAN.txt").read_text() == "hd", ghi)
check("cập nhật giữ nguyên worker.json và worker.log",
      json.loads((td / "worker.json").read_text())["token"] == "bi-mat" and (td / "worker.log").read_text() == "log cũ")
check("cập nhật bỏ tệp lạ (.exe, __pycache__)", not (td / "la.exe").exists() and not (td / "__pycache__").exists())
check("tệp giống hệt (chay.bat đang chạy) không bị ghi lại",
      (td / "chay.bat").stat().st_mtime_ns == mt_bat and "chay.bat" not in ghi, ghi)
for ten_xau in ("../thoat.py", "MinMinWorker/../../thoat.py", "/etc/thoat.py", "C:/Windows/thoat.py",
                "MinMinWorker/..\\..\\thoat.py"):
    try:
        mw.ap_dung_cap_nhat(_zip({"MinMinWorker/minmin_worker.py": "PHIEN_BAN = '3'", ten_xau: "x"}), td)
        bi_chan = False
    except ValueError:
        bi_chan = True
    check(f"gói có đường thoát thư mục bị chặn cả gói: {ten_xau}",
          bi_chan and (td / "minmin_worker.py").read_text() == "PHIEN_BAN = '2'"
          and not (td.parent / "thoat.py").exists())
try:
    mw.ap_dung_cap_nhat(_zip({"MinMinWorker/a.py": "x", "MinMinWorker/b.txt": "y"}), td)
    thieu = False
except ValueError:
    thieu = True
check("gói thiếu minmin_worker.py bị từ chối", thieu and not (td / "a.py").exists())
ghi2 = mw.ap_dung_cap_nhat(_zip({"minmin_worker.py": "PHIEN_BAN = '4'"}), td)
check("gói không có thư mục bọc ngoài vẫn cập nhật được", (td / "minmin_worker.py").read_text() == "PHIEN_BAN = '4'")

# ---------------------------------------------------------------------------- 5. điều phối song song
dp = mw.DieuPhoi(2)
dp.nhan({"id": 1, "nick_id": "A"})
check("rảnh -> có chỗ", dp.con_cho())
dp.nhan({"id": 2, "nick_id": "A"})
chay1 = [v["id"] for v in dp.lay_de_chay()]
check("không giao 2 việc cùng nick cùng lúc", chay1 == [1] and dp.ds_dang() == [1] and [v["id"] for v in dp.cho] == [2])
check("việc chờ nick bận vẫn chiếm chỗ (không nhận thêm)", not dp.con_cho())
dp.xong(1)
chay2 = [v["id"] for v in dp.lay_de_chay()]
check("nick rảnh thì việc chờ chạy", chay2 == [2] and dp.con_cho())
dp.nhan({"id": 3, "nick_id": "B"})
check("nick khác chạy song song", [v["id"] for v in dp.lay_de_chay()] == [3] and sorted(dp.ds_dang()) == [2, 3]
      and not dp.con_cho())
check("song_song có trần 3, tối thiểu 1", mw.DieuPhoi(9).song_song == 3 and mw.DieuPhoi(0).song_song == 1)

# ---------------------------------------------------------------------------- 6. lam_viec đầu-cuối (trình duyệt thật)
exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")) or sorted(
    glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")))
if not exe:
    print("SKIP các test trình duyệt: không thấy Chromium ở /opt/pw-browsers")
else:
    EXE = exe[-1]
    mw.NGHI_TRUOC_DONG = 0

    def connect(pw, cdp):
        return pw.chromium.launch(executable_path=EXE, headless=True)

    class GPMGia:
        mo_ds, dong_ds = [], []

        def __init__(self, nk):
            self.nk = nk

        def mo(self, nick):
            GPMGia.mo_ds.append(nick)
            return "http://127.0.0.1:1"

        def dong(self, nick):
            GPMGia.dong_ds.append(nick)

    def ham_tot(nc):
        nc.page.set_content("<h1>xin chào</h1>")
        nc.su_kien("thich", "thanh_cong", "ok")
        return "làm xong"

    def ham_chi_bo_qua(nc):
        nc.su_kien("dang_tuong", "bo_qua", "Hết bài", ma="het_bai")
        return "Hết bài trong kho."

    def ham_chi_loi(nc):
        nc.su_kien("thich", "loi", "không thấy nút")
        return "không làm được gì"

    def ham_checkpoint(nc):
        nc.su_kien("binh_luan", "thanh_cong", "1 cái")
        raise LoiKyNang("nick bị checkpoint", ma="checkpoint")

    kb_t = {"tt_tot": ham_tot, "tt_bo_qua": ham_chi_bo_qua, "tt_loi": ham_chi_loi, "tt_cp": ham_checkpoint}
    dong_buoc = []
    m = MinMinGia()
    r = mw.lam_viec(m, GPMGia, viec_mau("tt_tot", vid=11), kb_t, day_buoc=lambda v, s: dong_buoc.append((v, s)),
                    connect=connect)
    kq = m.ket_qua_ds[-1]
    check("lam_viec: thành công -> ok, có dem, có ảnh chụp, đóng profile",
          kq["ok"] and kq["dem"] == {"thanh_cong": 1, "bo_qua": 0, "loi": 0} and kq["anh"]
          and kq["thong_diep"] == "làm xong" and GPMGia.dong_ds[-1] == "n1", kq)
    check("mỗi dòng nhật ký được đẩy lên /may/buoc", dong_buoc and all(v == 11 for v, _ in dong_buoc))
    mw.lam_viec(m, GPMGia, viec_mau("tt_bo_qua"), kb_t, connect=connect)
    kq = m.ket_qua_ds[-1]
    check("chỉ bỏ qua (hết bài) -> ok=true kèm thông điệp", kq["ok"] and "Hết bài" in kq["thong_diep"], kq)
    mw.lam_viec(m, GPMGia, viec_mau("tt_loi"), kb_t, connect=connect)
    kq = m.ket_qua_ds[-1]
    check("không thành công nào mà có lỗi -> ok=false", not kq["ok"] and kq["dem"]["loi"] == 1, kq)
    n_sk = len(m.su_kien_ds())
    mw.lam_viec(m, GPMGia, viec_mau("tt_cp"), kb_t, connect=connect)
    kq = m.ket_qua_ds[-1]
    sk = m.su_kien_ds()[n_sk:]
    check("LoiKyNang có mã -> thêm sự kiện loi mang mã đó trước khi trả kết quả",
          not kq["ok"] and sk[-1]["ket_qua"] == "loi" and sk[-1]["ma"] == "checkpoint"
          and sk[-1]["hanh_dong"] == "binh_luan" and "checkpoint" in kq["thong_diep"]
          and "đã làm được 1" in kq["thong_diep"], (kq, sk))
    so_mo = len(GPMGia.mo_ds)
    mw.lam_viec(m, GPMGia, viec_mau("zz_khong_biet"), kb_t, connect=connect)
    check("kỹ năng lạ -> báo lỗi ngay, không mở profile", not m.ket_qua_ds[-1]["ok"] and len(GPMGia.mo_ds) == so_mo)

    # ------------------------------------------------------------------ 7. CHẠY THỬ không bấm nút công khai
    import fb_chung  # noqa: E402
    from nguoi import Nguoi  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402
    fb_chung.HE_SO_CHO = 0.05

    HTML = r"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Facebook</title>
<style>body{font:14px sans-serif;width:900px} [role=dialog]{border:1px solid #888;padding:8px;background:#fff}
[contenteditable]{border:1px solid #ccc;min-height:20px;margin:4px 0} .post{border:1px solid #ddd;margin:10px;padding:8px}</style>
</head><body><div role="banner">Facebook</div><div role="main" id="main"></div>
<script>
const CK = /^(Đăng|Gửi|Bình luận|Thích|Yêu thích|Tham gia nhóm|Tham gia|Chia sẻ|Chia sẻ ngay|Phản hồi)$/;
function bao(n){ try { window.baoCongKhai(n); } catch(e){} }
document.addEventListener('click', e => {
  const el = e.target.closest('[aria-label],button,[role=button],[role=menuitem]'); if (!el) return;
  const n = (el.getAttribute('aria-label') || el.innerText || '').trim(); if (CK.test(n)) bao(n);
}, true);
function nutBL(o, khung, nhan){
  o.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); bao('Enter');
      const t = o.innerText.trim(); if (!t) return;
      const c = document.createElement('div'); c.setAttribute('role','article'); c.setAttribute('aria-label', nhan);
      c.innerText = t; khung.appendChild(c); o.innerText = ''; }
  });
}
const p = location.pathname, main = document.getElementById('main');
function baiViet(i){
  const d = document.createElement('div'); d.className='post'; d.setAttribute('aria-posinset', i);
  d.innerHTML = `<h3>Chị Lan ${i}</h3><div data-ad-preview="message">Ai biết chỗ mua váy lụa đẹp không ạ? bài ${i}</div>
   <a href="https://www.facebook.com/groups/123/posts/45${i}/">2 giờ</a>
   <div role="button" aria-label="Thích" class="thich">Thích</div> <div role="button" aria-label="Bình luận">Bình luận</div>
   <div role="button" aria-label="Chia sẻ" class="cs">Chia sẻ</div>
   <div class="bl"><div role="article" aria-label="Bình luận của Lan">Lan: Shop ơi giá bao nhiêu? <div role="button">Phản hồi</div></div></div>
   <div contenteditable="true" role="textbox" aria-label="Viết bình luận công khai..."></div>`;
  d.querySelector('.thich').onclick = function(){ this.setAttribute('aria-label', 'Gỡ Thích'); this.innerText = 'Đã thích'; };
  d.querySelector('.cs').onclick = function(){
    const m = document.createElement('div'); m.setAttribute('role','menu');
    m.innerHTML = '<div role="menuitem">Chia sẻ ngay (Công khai)</div>';
    m.firstChild.onclick = () => { m.remove(); const t = document.createElement('div'); t.innerText = 'Đã chia sẻ'; document.body.appendChild(t); };
    document.body.appendChild(m); };
  nutBL(d.querySelector('[contenteditable]'), d.querySelector('.bl'), 'Bình luận của Tôi');
  d.querySelectorAll('.bl [role=button]').forEach(b => b.onclick = () => {
    const o = document.createElement('div'); o.contentEditable = 'true'; o.setAttribute('role','textbox');
    o.setAttribute('aria-label','Trả lời Lan'); b.parentNode.appendChild(o); nutBL(o, b.parentNode, 'Phản hồi của Tôi'); o.focus(); });
  return d;
}
if (p.startsWith('/messages')) {
  main.innerHTML = `<div role="navigation"><a href="/messages/t/1001/"><span style="font-weight:700">Khách Hoa</span> Tin nhắn chưa đọc</a></div>
   <div role="row" style="margin-right:600px"><div dir="auto">Cho mình hỏi giá váy lụa</div></div>
   <div contenteditable="true" role="textbox" aria-label="Tin nhắn"></div>`;
  nutBL(main.querySelector('[contenteditable]'), main, 'tin');
} else if (p.startsWith('/notifications')) {
  main.innerHTML = `<a href="/groups/123/posts/451/?comment_id=99">Lan đã bình luận về bài viết của bạn: Shop ơi giá bao nhiêu?</a>`;
} else if (p.startsWith('/search/groups')) {
  main.innerHTML = `<div role="article"><a href="https://www.facebook.com/groups/777/">Nhóm Váy Đẹp</a><div>12K thành viên · 10 bài viết/ngày</div></div>`;
} else {
  if (p.startsWith('/groups/')) {
    const h = document.createElement('h1'); h.innerText = 'Nhóm Mẹ Bỉm'; main.appendChild(h);
    if (p.indexOf('777') >= 0 || p.indexOf('chua-vao') >= 0) {
      const j = document.createElement('div'); j.setAttribute('role','button'); j.setAttribute('aria-label','Tham gia nhóm'); j.innerText='Tham gia nhóm';
      j.onclick = () => { const dl = document.createElement('div'); dl.setAttribute('role','dialog');
        dl.innerHTML = '<div>Bạn biết nhóm qua đâu?</div><textarea></textarea><input type="checkbox"><div role="button" aria-label="Gửi">Gửi</div>';
        dl.querySelector('[aria-label=Gửi]').onclick = () => { dl.remove(); j.setAttribute('aria-label','Đã yêu cầu'); j.innerText='Đã yêu cầu'; };
        document.body.appendChild(dl); };
      main.appendChild(j);
    }
  }
  const soan = document.createElement('div'); soan.setAttribute('role','button'); soan.innerText = 'Bạn đang nghĩ gì?';
  soan.onclick = () => { const dl = document.createElement('div'); dl.setAttribute('role','dialog');
    dl.innerHTML = '<div contenteditable="true" role="textbox"></div><input type="file" style="display:none"><div role="button" aria-label="Đăng">Đăng</div>';
    dl.querySelector('[aria-label=Đăng]').onclick = () => { const t = dl.querySelector('[contenteditable]').innerText; dl.remove();
      const b = baiViet(9); b.querySelector('[data-ad-preview]').innerText = t; main.prepend(b); };
    document.body.appendChild(dl); };
  main.appendChild(soan);
  const feed = document.createElement('div'); feed.setAttribute('role','feed'); main.appendChild(feed);
  for (let i = 1; i <= 3; i++) feed.appendChild(baiViet(i));
}
</script></body></html>"""

    cong_khai = []

    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=EXE, headless=True)
        ctx = br.new_context(viewport={"width": 1100, "height": 900})
        ctx.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=HTML))
        page = ctx.new_page()
        page.expose_function("baoCongKhai", lambda n: cong_khai.append(n))

        def tao_nc(ky_nang, ts, chay_thu=True, mc_=None):
            mc_ = mc_ or MinMinGia(ts)
            v = viec_mau(ky_nang, ts, chay_thu=chay_thu, han_muc={})
            n = NguCanh(mc_, v, page, ctx, nhat_ky=lambda s: None, rng=random.Random(5), toc_do=400,
                        ngu=lambda s: None)
            return n, mc_

        LINK = "https://www.facebook.com/groups/123/posts/451/"
        tong_chan = 0
        cac_mau = [
            ("fb_tuong_tac_link", {"links": [LINK], "cam_xuc": "yeu_thich", "binh_luan": True, "chia_se": True,
                                   "cau_binh_luan": "Đẹp quá"}),
            ("fb_tuong_tac_link", {"links": [LINK], "cam_xuc": "thich", "binh_luan": True, "cau_binh_luan": ""}),
            ("fb_nuoi_nick", {"phut": 3}),
            ("fb_dang_tuong_kho", {"so_bai": 1, "kho": "chung"}),
            ("fb_dang_nhom_link", {"links": ["https://www.facebook.com/groups/123"], "nguon": "nhap",
                                   "noi_dung": "Bài thử", "so_nhom": 1}),
            ("fb_dang_tuong_ai", {"so_bai": 1}),
            ("fb_dang_nhom_ai", {"so_bai": 1, "moi_nhom_7_ngay": 1, "san_pham": "1"}),
            ("fb_binh_luan_nhom_link", {"links": ["https://www.facebook.com/groups/777"], "san_pham": "1", "toi_da": 2,
                                        "tu_tham_gia": True, "che_do": "dang_luon"}),
            ("fb_binh_luan_nhom_sp", {"san_pham": "1", "toi_da": 2, "so_bai_quet": 3, "che_do": "dang_luon"}),
            ("fb_tham_gia_nhom_sp", {"san_pham": "1", "so_nhom": 1, "tu_tim": True, "tu_khoa": "váy lụa"}),
            ("fb_tra_loi_binh_luan", {"so_thong_bao": 5, "che_do": "dang_luon"}),
            ("fb_tra_loi_tin_nhan", {"so_hoi_thoai": 3, "che_do": "dang_luon"}),
            ("fb_tuong_tac_bai_app", {"so_bai": 1, "che_do": "dang_luon"}),
            ("fb_nhan_tin_ds", {"nguoi_nhan": "100012345\nhttps://www.facebook.com/nguyen.van.a", "noi_dung": "Chào bạn",
                                "moi_nick": 2}),
            ("fb_gui_tin", {"khach_link": "https://www.facebook.com/messages/t/1001/", "noi_dung": "Dạ em gửi giá"}),
            ("dang_ban_nhap:facebook", {"ban_nhap_id": 5, "loai": "binh_luan", "noi_dang": "fb_nhom", "link_goc": LINK,
                                        "nhom": "N", "noi_dung": "Nháp đã duyệt"}),
            ("dang_ban_nhap:facebook", {"ban_nhap_id": 6, "loai": "bai_dang", "noi_dang": "fb_tuong",
                                        "noi_dung": "Bài nháp tường"}),
        ]
        loi_mau = []
        for kn, ts in cac_mau:
            ts = dict(ts)
            mcx = MinMinGia(dict(ts, links=ts.get("links") or [LINK]))
            mcx.nhom = [{"link": "https://www.facebook.com/groups/123", "ten": "Nhóm Mẹ Bỉm", "vai": "chinh",
                         "tinh_trang_vao": "da_vao", "trang_thai": "da_duyet"},
                        {"link": "https://www.facebook.com/groups/777", "ten": "Nhóm Váy", "vai": "tuong_tac",
                         "tinh_trang_vao": "", "trang_thai": "da_duyet"}]
            n, _ = tao_nc(kn.split(":")[0] if kn.startswith("dang_ban_nhap") else kn, ts, True, mcx)
            truoc = len(cong_khai)
            try:
                kb_that[kn](n)
            except Exception as e:      # noqa: BLE001
                loi_mau.append(f"{kn}: {type(e).__name__}: {e}")
            if len(cong_khai) != truoc:
                loi_mau.append(f"{kn}: đã bấm công khai {cong_khai[truoc:]}")
            tong_chan += n.so_lan_chan + len(getattr(n.tay, "bi_chan", []))
            n.don_dep()
        check("CHẠY THỬ: 13 mẫu FB + dang_ban_nhap + fb_gui_tin chạy hết trên trang giả mà KHÔNG bấm nút công khai nào",
              not loi_mau and not cong_khai, loi_mau or cong_khai)
        check("CHẠY THỬ: chốt chặn trung tâm thật sự được hỏi (có cú bấm bị chặn)", tong_chan >= 10, tong_chan)

        # Chặn lớp thứ hai: kỹ năng quên hỏi duoc_bam_cong_khai mà gọi thẳng nc.tay.bam / phím Enter.
        n, _ = tao_nc("fb_tuong_tac_link", {"links": [LINK]}, True)
        n.mo(LINK)
        truoc = len(cong_khai)
        n.tay.bam(page.get_by_role("button", name="Thích").first)
        o = page.get_by_role("textbox", name="Viết bình luận công khai...").first
        n.tay.bam(o)
        n.tay.go_binh_luan("dòng 1\ndòng 2")
        n.tay.phim("Enter")
        check("TayChayThu tự chặn nút Thích và phím Enter kể cả khi kỹ năng quên hỏi",
              len(cong_khai) == truoc and "Thích" in n.tay.bi_chan and "Enter" in n.tay.bi_chan
              and page.get_by_role("button", name="Gỡ Thích").count() == 0, (cong_khai[truoc:], n.tay.bi_chan))
        nut_soan = page.get_by_role("button", name="Bạn đang nghĩ gì?")
        n.tay.bam(nut_soan)
        check("TayChayThu vẫn bấm nút không công khai (mở ô soạn)", page.get_by_role("dialog").count() == 1)

        # Đối chứng: KHÔNG chạy thử thì cùng trang giả ghi nhận cú bấm và thao tác thành công (bằng chứng
        # bộ đếm cú bấm hoạt động và đường thả cảm xúc / bình luận / đăng bài làm đúng trên giao diện mẫu).
        n, mcx = tao_nc("fb_tuong_tac_link", {"links": [LINK], "cam_xuc": "thich", "binh_luan": True,
                                              "cau_binh_luan": "Váy xinh quá", "chia_se": True}, False)
        truoc = len(cong_khai)
        msg = kb_that["fb_tuong_tac_link"](n)
        sk = [(b["hanh_dong"], b["ket_qua"]) for b in mcx.su_kien_ds()]
        check("đối chứng chạy thật: thích + bình luận + chia sẻ đều đọc lại thấy và báo thành công",
              ("thich", "thanh_cong") in sk and ("binh_luan", "thanh_cong") in sk and ("chia_se", "thanh_cong") in sk
              and "Thích" in cong_khai[truoc:] and "Enter" in cong_khai[truoc:]
              and any(k.startswith("fb_tt:") for k in mcx.da_lam_set), (sk, cong_khai[truoc:], msg))
        n, mcx = tao_nc("fb_dang_tuong_kho", {"so_bai": 1}, False)
        msg = kb_that["fb_dang_tuong_kho"](n)
        kho_kq = [b for m_, d, b in mcx.goi_ds if d == "/doi-social/may/kho/0/ket-qua"]
        check("đối chứng chạy thật: đăng tường từ kho thấy bài mới, báo kho đã đăng",
              ("dang_tuong", "thanh_cong") in [(b["hanh_dong"], b["ket_qua"]) for b in mcx.su_kien_ds()]
              and kho_kq and kho_kq[-1]["ok"] and kho_kq[-1]["da_bam_dang"], (msg, kho_kq))
        n, mcx = tao_nc("fb_tuong_tac_link", {}, True)
        msg = None
        n2, mc2 = tao_nc("fb_dang_tuong_kho", {"so_bai": 1}, True)
        kb_that["fb_dang_tuong_kho"](n2)
        kho_kq = [b for m_, d, b in mc2.goi_ds if d == "/doi-social/may/kho/0/ket-qua"]
        check("chạy thử đăng kho: trả bài về hàng chờ (ok=false, chưa bấm Đăng)",
              kho_kq and not kho_kq[-1]["ok"] and not kho_kq[-1]["da_bam_dang"], kho_kq)
        n3, mc3_ = tao_nc("fb_binh_luan_nhom_link", {"links": ["https://www.facebook.com/groups/123"], "san_pham": "1",
                                                     "toi_da": 2, "tu_tham_gia": True}, True)
        kb_that["fb_binh_luan_nhom_link"](n3)
        nhap = [b for m_, d, b in mc3_.goi_ds if d == "/doi-social/may/ban-nhap"]
        check("chạy thử bình luận nhóm: AI chấm + tạo nháp kèm lý do, link bài, nhóm",
              len(nhap) == 2 and nhap[0]["loai"] == "binh_luan" and nhap[0]["noi_dang"] == "fb_nhom"
              and nhap[0]["link_goc"].startswith("https://www.facebook.com/groups/123/posts/45")
              and nhap[0]["ly_do"] and nhap[0]["nhom"] == "Nhóm Mẹ Bỉm", nhap)
        ai_cham = [b for m_, d, b in mc3_.goi_ds if d == "/doi-social/may/ai" and b["muc_dich"] == "cham_bai"]
        check("chấm bài có gửi kèm ảnh chụp bài", ai_cham and all(len(b["anh"]) == 1 for b in ai_cham))
        br.close()

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
