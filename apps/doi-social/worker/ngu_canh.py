"""Ngữ cảnh một việc (NguCanh) - giao diện CỐ ĐỊNH mà mọi tệp kỹ năng `ky_nang_*.py` dùng.

Hợp đồng ở docs/doi-social/KIEN-TRUC.md mục 4.2. Không đổi chữ ký các hàm công khai: kỹ sư khác
đang viết kỹ năng TikTok/Instagram/Threads/YouTube/X/Reddit dựa trên đúng các tên này.

Lớp này không biết gì về Facebook. Nó lo:
  - gọi các đường /doi-social/may/* của MinMin (qua đối tượng MayChu có `goi()` và `tai_ve()`),
    thử lại 3 lần có giãn cách khi mạng hỏng;
  - đếm hạn mức còn lại cục bộ (khởi tạo từ `tham_so.han_muc`, máy chủ trả số mới sau mỗi sự kiện);
  - cờ dừng (đợt bị huỷ, hết hạn mức);
  - nghỉ ngẫu nhiên giữa thao tác;
  - nhận biết đăng xuất / checkpoint / captcha / "quá nhanh" theo nền tảng;
  - CHẠY THỬ: chặn mọi cú bấm công khai ở một chỗ (`duoc_bam_cong_khai`) và bọc bàn tay ảo
    (`TayChayThu`) để kể cả kỹ năng quên hỏi cũng không bấm được nút Đăng/Gửi/Thích...
"""
from __future__ import annotations

import base64
import random
import re
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Dict, List, Optional

from nguoi import Nguoi

MA_DUNG_NGAY = ("dang_xuat", "checkpoint", "captcha", "qua_nhanh")
CHE_DO_HOP_LE = ("chay_thu", "duyet_truoc", "dang_luon")
VO_HAN = 10 ** 6


class LoiKyNang(RuntimeError):
    """Kỹ năng hỏng với câu dễ hiểu. `ma`: dang_xuat|checkpoint|captcha|qua_nhanh|het_bai|ma_pin|..."""

    def __init__(self, thong_diep: str, ma: Optional[str] = None):
        super().__init__(thong_diep)
        self.thong_diep = thong_diep
        self.ma = ma or None


# ---------------------------------------------------------------------------- nhận biết trạng thái
# Mỗi dòng: (mã, kiểu, mẫu). kiểu: "url" (regex trên url), "css" (có phần tử khớp), "chu" (chữ hiện
# trên trang, regex). Dòng đầu khớp thì thắng, nên xếp mã nghiêm trọng trước.
_CAPTCHA_CHUNG = [
    ("captcha", "css", "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='arkoselabs'], "
                       "iframe[src*='funcaptcha'], iframe[title*='captcha' i]"),
]
BANG_NHAN_BIET: Dict[str, list] = {
    "facebook": [
        ("checkpoint", "url", r"/checkpoint|/two_step_verification|/confirmemail|/disabled"),
        ("captcha", "url", r"/captcha"),
        ("dang_xuat", "url", r"/login(\.php|/|\?|$)|/recover/"),
        ("dang_xuat", "css", "input[name='pass']"),
        ("qua_nhanh", "chu", r"(quá nhanh|going too fast|tạm thời bị chặn|temporarily blocked|"
                             r"bạn bị tạm chặn|you can't use this feature right now|bạn hiện không dùng được tính năng này)"),
    ] + _CAPTCHA_CHUNG,
    "tiktok": [
        ("dang_xuat", "url", r"/login(/|\?|$)"),
        ("captcha", "css", "#captcha-verify-image, .captcha_verify_container, #tiktok-verify-ele, "
                           "div[class*='captcha_verify']"),
        ("captcha", "chu", r"(Kéo thanh trượt|Drag the slider|Xác minh để tiếp tục|Verify to continue)"),
        ("qua_nhanh", "chu", r"(quá nhanh|too fast|Maximum number of attempts|thử lại sau)"),
    ] + _CAPTCHA_CHUNG,
    "instagram": [
        ("checkpoint", "url", r"/challenge|/accounts/suspended|/accounts/disabled"),
        ("dang_xuat", "url", r"/accounts/login"),
        ("dang_xuat", "css", "input[name='password']"),
        ("qua_nhanh", "chu", r"(Try Again Later|Hãy thử lại sau|We restrict certain activity|hạn chế một số hoạt động)"),
    ] + _CAPTCHA_CHUNG,
    "threads": [
        ("checkpoint", "url", r"/challenge|/accounts/suspended"),
        ("dang_xuat", "url", r"/login(/|\?|$)|/accounts/login"),
        ("qua_nhanh", "chu", r"(Try Again Later|Hãy thử lại sau)"),
    ] + _CAPTCHA_CHUNG,
    "x": [
        ("checkpoint", "url", r"/account/access|/account/locked"),
        ("dang_xuat", "url", r"/i/flow/login|/login(/|\?|$)"),
        ("qua_nhanh", "chu", r"(rate limit|quá giới hạn|Try again later)"),
    ] + _CAPTCHA_CHUNG,
    "reddit": [
        ("dang_xuat", "url", r"/login(/|\?|$)|/account/login"),
        ("qua_nhanh", "chu", r"(you are doing that too much|you're doing that too much)"),
    ] + _CAPTCHA_CHUNG,
    "youtube": [
        ("captcha", "url", r"google\.[a-z.]+/sorry/"),
        ("dang_xuat", "url", r"accounts\.google\.com"),
    ] + _CAPTCHA_CHUNG,
}
THONG_DIEP_MA = {
    "dang_xuat": "nick đã bị đăng xuất {nt} - mở profile trong GPM đăng nhập lại",
    "checkpoint": "nick đang bị {nt} kiểm tra bảo mật (checkpoint) - mở profile trong GPM xử lý tay",
    "captcha": "{nt} đòi giải captcha - dừng nick này, mở profile giải tay",
    "qua_nhanh": "{nt} báo thao tác quá nhanh / tạm chặn - dừng nick này, để nghỉ vài giờ",
}


def doan_trang_thai(nen_tang: str, url: str, co_css: Callable[[str], bool],
                    co_chu: Callable[[str], bool]) -> Optional[str]:
    """Hàm thuần: trả mã sự cố đầu tiên khớp (hoặc None). `co_css`/`co_chu` do bên gọi cung cấp."""
    for ma, kieu, mau in BANG_NHAN_BIET.get(nen_tang, _CAPTCHA_CHUNG):
        try:
            if kieu == "url" and re.search(mau, url or "", re.I):
                return ma
            if kieu == "css" and co_css(mau):
                return ma
            if kieu == "chu" and co_chu(mau):
                return ma
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------- chặn bấm công khai
# Nhãn nút làm thay đổi thứ người khác nhìn thấy. Ở chạy thử, TayChayThu từ chối bấm mọi phần tử có
# nhãn/chữ khớp mẫu này, dù kỹ năng có quên hỏi `duoc_bam_cong_khai()`.
CONG_KHAI = re.compile(
    r"^\s*(Đăng|Đăng bài|Post|Gửi|Send|Submit|Bình luận|Comment|Thích|Like|Yêu thích|Love|Thương thương|Care|"
    r"Haha|Wow|Buồn|Sad|Phẫn nộ|Angry|Tham gia|Tham gia nhóm|Join|Join group|Chia sẻ|Share|Chia sẻ ngay|"
    r"Share now|Chia sẻ ngay \(Công khai\)|Share now \(Public\)|Phản hồi|Reply|Theo dõi|Follow|Đăng lại|Repost|"
    r"Retweet|Lưu|Save|Upvote|Gửi yêu cầu|Đăng ngay|Publish|Tweet|Nhấn nút Gửi|Press enter to send|"
    r"Nhấn Enter để gửi)\s*$", re.I)


def la_nut_cong_khai(nhan: str) -> bool:
    return bool(CONG_KHAI.match(nhan or ""))


class TayChayThu(Nguoi):
    """Bàn tay ảo cho chế độ chạy thử: đi chuột, cuộn, đọc như thường nhưng KHÔNG bấm nút công
    khai và KHÔNG nhấn Enter (Enter trong ô bình luận/tin nhắn là gửi)."""

    def __init__(self, page, rng=None, toc_do: float = 1.0, nhat_ky=None):
        super().__init__(page, rng, toc_do)
        self.bi_chan: List[str] = []
        self._nk = nhat_ky or (lambda s: None)

    @staticmethod
    def _nhan(locator) -> str:
        for lay in (lambda: locator.get_attribute("aria-label", timeout=1500),
                    lambda: locator.inner_text(timeout=1500)):
            try:
                s = (lay() or "").strip()
                if s:
                    return s.splitlines()[0][:80]
            except Exception:
                pass
        return ""

    def bam(self, locator) -> None:
        nhan = self._nhan(locator)
        if la_nut_cong_khai(nhan):
            self.bi_chan.append(nhan)
            self._nk(f"Chạy thử: KHÔNG bấm nút công khai '{nhan}'")
            try:
                self.di_toi(locator)
            except Exception:
                pass
            return
        super().bam(locator)

    def go(self, text: str, ty_le_nham: float = 0.02) -> None:
        super().go((text or "").replace("\n", " "), ty_le_nham)

    def go_binh_luan(self, text: str, ty_le_nham: float = 0.02) -> None:
        super().go_binh_luan((text or "").replace("\n", " "), ty_le_nham)

    def phim(self, ten: str) -> None:
        if ten.split("+")[-1].lower() in ("enter", "return"):
            self.bi_chan.append(ten)
            self._nk("Chạy thử: KHÔNG nhấn Enter (sẽ gửi)")
            return
        super().phim(ten)


# ---------------------------------------------------------------------------- NguCanh
class NguCanh:
    """Xem docstring đầu tệp. Mọi tham số ngoài `may_chu`, `viec` đều có mặc định để test dựng được
    ngữ cảnh không cần trình duyệt."""

    SO_LAN_THU = 3
    GIAN_CACH_THU = (2.0, 5.0, 10.0)
    HOI_DUNG_MOI_GIAY = 15.0

    def __init__(self, may_chu, viec: dict, page=None, ctx=None, nhat_ky=None,
                 thu_muc_tam=None, rng: Optional[random.Random] = None, toc_do: float = 1.0,
                 ngu: Callable[[float], None] = time.sleep):
        self.may_chu = may_chu
        self.viec = viec or {}
        self.vid = self.viec.get("id", 0)
        self.page = page
        self.ctx = ctx
        tsv = self.viec.get("tham_so") or {}
        self.tham_so_viec: dict = tsv if isinstance(tsv, dict) else {}
        ts = self.tham_so_viec.get("tham_so")
        # Việc nội bộ (dang_ban_nhap, fb_gui_tin) có thể để tham số thẳng ở tham_so của việc.
        self.ts: dict = ts if isinstance(ts, dict) else dict(self.tham_so_viec)
        self.ky_nang = str(self.viec.get("ky_nang") or self.tham_so_viec.get("kich_ban") or "")
        self.nen_tang = str(self.tham_so_viec.get("nen_tang") or doan_nen_tang(self.ky_nang, self.ts))
        self.chay_thu = bool(self.tham_so_viec.get("chay_thu") or self.ts.get("chay_thu"))
        cd = str(self.ts.get("che_do") or "")
        self.che_do = "chay_thu" if self.chay_thu else (cd if cd in CHE_DO_HOP_LE else "dang_luon")
        if self.che_do == "chay_thu":
            self.chay_thu = True
        self.rng = rng or random.Random()
        self._ngu = ngu
        self._nk = nhat_ky or (lambda s: None)
        self.toc_do = toc_do
        if page is not None:
            self.tay = (TayChayThu(page, self.rng, toc_do, self.nhat_ky) if self.chay_thu
                        else Nguoi(page, self.rng, toc_do))
        else:
            self.tay = None
        hm = self.tham_so_viec.get("han_muc")
        self._han_muc: Dict[str, int] = {}
        if isinstance(hm, dict):
            for k, v in hm.items():
                try:
                    self._han_muc[str(k)] = int(v)
                except (TypeError, ValueError):
                    pass
        ng = self.tham_so_viec.get("nghi_giay") or self.ts.get("nghi_giay") or [6, 25]
        try:
            a, b = float(ng[0]), float(ng[1])
            self.nghi_giay = (min(a, b), max(a, b))
        except Exception:
            self.nghi_giay = (6.0, 25.0)
        self.dem = {"thanh_cong": 0, "bo_qua": 0, "loi": 0}
        self.hanh_dong_cuoi = ""
        self.so_lan_chan = 0
        self._dung = False
        self._lan_hoi_dung = 0.0
        self._tu_tao_tam = thu_muc_tam is None
        self.thu_muc_tam = Path(thu_muc_tam or tempfile.mkdtemp(prefix="minmin-nc-"))
        self.tep_cuc_bo: List[str] = []
        self.nhom_fb_tho: dict = {}

    # ------------------------------------------------------------------ mạng
    def _goi(self, method: str, duong: str, body=None):
        """Gọi MinMin, thử lại khi mạng hỏng hoặc máy chủ 5xx. Lỗi 4xx (yêu cầu sai) không thử lại."""
        loi = None
        for lan in range(self.SO_LAN_THU + 1):
            try:
                return self.may_chu.goi(method, duong, body)
            except Exception as e:      # noqa: BLE001
                ma_http = getattr(e, "code", None)
                if isinstance(ma_http, int) and ma_http < 500:
                    raise LoiKyNang(f"MinMin từ chối {duong.split('?')[0]}: {e}") from None
                loi = e
                if lan < self.SO_LAN_THU:
                    cho = self.GIAN_CACH_THU[min(lan, len(self.GIAN_CACH_THU) - 1)]
                    self._nk(f"Mất kết nối MinMin ({type(e).__name__}), thử lại sau {cho:g}s")
                    self._ngu(cho)
        raise LoiKyNang(f"không liên lạc được MinMin sau {self.SO_LAN_THU + 1} lần thử: {loi}", ma="mat_ket_noi")

    def _tai(self, duong: str, dich: Path) -> None:
        loi = None
        for lan in range(self.SO_LAN_THU + 1):
            try:
                self.may_chu.tai_ve(duong, dich)
                return
            except Exception as e:      # noqa: BLE001
                loi = e
                if lan < self.SO_LAN_THU:
                    self._ngu(self.GIAN_CACH_THU[min(lan, len(self.GIAN_CACH_THU) - 1)])
        raise LoiKyNang(f"không tải được tệp từ MinMin: {loi}")

    def _q(self, **q) -> str:
        return urllib.parse.urlencode({k: v for k, v in q.items() if v not in (None, "")})

    # ------------------------------------------------------------------ nhật ký, sự kiện, hạn mức
    def nhat_ky(self, s: str) -> None:
        self._nk(str(s))

    def su_kien(self, hanh_dong: str, ket_qua: str, chi_tiet: str = "", link: str = "", nhom: str = "",
                san_pham: str = "", ma: str = "") -> dict:
        if hanh_dong:
            self.hanh_dong_cuoi = hanh_dong
        if ket_qua in self.dem:
            self.dem[ket_qua] += 1
        if ket_qua == "thanh_cong" and hanh_dong in self._han_muc:
            self._han_muc[hanh_dong] -= 1
        body = {"hanh_dong": hanh_dong, "ket_qua": ket_qua, "chi_tiet": str(chi_tiet or "")[:1000],
                "link": link or "", "nhom": nhom or "", "san_pham": str(san_pham or self.ts.get("san_pham") or ""),
                "ma": ma or ""}
        self.nhat_ky(f"[{ket_qua}] {hanh_dong}: {chi_tiet}" + (f" ({ma})" if ma else ""))
        d = self._goi("POST", f"/doi-social/may/su-kien/{self.vid}", body) or {}
        cl = d.get("con_lai")
        if isinstance(cl, dict):
            for k, v in cl.items():
                try:
                    self._han_muc[str(k)] = int(v)
                except (TypeError, ValueError):
                    pass
        if d.get("dung"):
            self._dung = True
        return {"con_lai": dict(self._han_muc), "dung": bool(d.get("dung"))}

    def con_lai(self, hanh_dong: str) -> int:
        self.hanh_dong_cuoi = hanh_dong or self.hanh_dong_cuoi
        return self._han_muc.get(hanh_dong, VO_HAN)

    def nen_dung(self) -> bool:
        if self._dung:
            return True
        if self._han_muc and all(v <= 0 for v in self._han_muc.values()):
            return True
        bay_gio = time.monotonic()
        if bay_gio - self._lan_hoi_dung >= self.HOI_DUNG_MOI_GIAY:
            self._lan_hoi_dung = bay_gio
            try:
                d = self.may_chu.goi("GET", f"/doi-social/may/dung/{self.vid}", None) or {}
                if d.get("dung"):
                    self._dung = True
                    self.nhat_ky("MinMin báo dừng (đợt bị huỷ)")
            except Exception:
                pass        # hỏi cờ dừng hỏng thì làm tiếp, lần sau hỏi lại
        return self._dung

    def nghi_thao_tac(self) -> None:
        a, b = self.nghi_giay
        self._ngu(self.rng.uniform(a, b) / max(1.0, self.toc_do))

    def duoc_bam_cong_khai(self, mo_ta: str = "", hanh_dong: str = "") -> bool:
        """CHỐT CHẶN TRUNG TÂM: kỹ năng hỏi trước MỌI cú bấm/phím làm thay đổi thứ người khác thấy.
        Chạy thử → False, ghi nhật ký và (nếu có hanh_dong) báo sự kiện thong_tin 'Chạy thử: sẽ ...'."""
        if not self.chay_thu:
            return True
        self.so_lan_chan += 1
        if hanh_dong:
            self.su_kien(hanh_dong, "thong_tin", f"Chạy thử: sẽ {mo_ta}".strip())
        else:
            self.nhat_ky(f"Chạy thử: sẽ {mo_ta}")
        return False

    # ------------------------------------------------------------------ AI, nháp, kho
    def ai(self, muc_dich: str, du_lieu: dict, anh: list = ()) -> dict:
        body = {"viec_id": self.vid, "muc_dich": muc_dich, "du_lieu": du_lieu or {},
                "anh": [base64.b64encode(a).decode("ascii") for a in list(anh or [])[:4] if a]}
        d = self._goi("POST", "/doi-social/may/ai", body) or {}
        if not d.get("ok", True) or not isinstance(d.get("ket_qua"), dict):
            raise LoiKyNang(f"AI không trả lời được ({muc_dich}): {d.get('error') or 'kết quả rỗng'}")
        return d["ket_qua"]

    def ban_nhap(self, **kw) -> int:
        d = self._goi("POST", "/doi-social/may/ban-nhap", {"viec_id": self.vid, **kw}) or {}
        return int(d.get("id") or 0)

    def lay_ban_nhap(self, noi_dang: str) -> Optional[dict]:
        q = self._q(viec_id=self.vid, noi_dang=noi_dang, san_pham=self.ts.get("san_pham"))
        d = self._goi("GET", f"/doi-social/may/ban-nhap/lay?{q}") or {}
        bn = d.get("ban_nhap")
        return bn if isinstance(bn, dict) else None

    def xong_ban_nhap(self, id: int, ok: bool, link: str = "", loi: str = "") -> None:
        self._goi("POST", f"/doi-social/may/ban-nhap/{int(id)}/ket-qua", {"ok": bool(ok), "link": link, "loi": loi})

    def lay_kho(self) -> Optional[dict]:
        d = self._goi("GET", f"/doi-social/may/kho/lay?{self._q(viec_id=self.vid)}") or {}
        bai = d.get("bai")
        if not isinstance(bai, dict):
            return None
        bai["tep_cuc_bo"] = []
        thu_muc = self.thu_muc_tam / f"kho-{bai.get('id')}"
        thu_muc.mkdir(parents=True, exist_ok=True)
        for t in bai.get("tep") or []:
            luu = str((t or {}).get("luu") or "")
            if not luu or "/" in luu or "\\" in luu or luu.startswith("."):
                continue
            dich = thu_muc / luu
            self._tai(f"/doi-social/may/kho/tep/{bai.get('id')}/{urllib.parse.quote(luu)}", dich)
            bai["tep_cuc_bo"].append(str(dich))
        if bai["tep_cuc_bo"]:
            self.nhat_ky(f"Đã tải {len(bai['tep_cuc_bo'])} tệp của bài kho #{bai.get('id')}")
        return bai

    def xong_kho(self, id: int, ok: bool, da_bam_dang: bool, link: str = "", loi: str = "") -> None:
        self._goi("POST", f"/doi-social/may/kho/{int(id)}/ket-qua",
                  {"ok": bool(ok), "da_bam_dang": bool(da_bam_dang), "link": link, "loi": loi})

    # ------------------------------------------------------------------ nhóm, trí nhớ, hội thoại
    def nhom_fb(self) -> list:
        d = self._goi("GET", f"/doi-social/may/nhom-fb?{self._q(viec_id=self.vid)}") or {}
        if isinstance(d, list):
            return d
        self.nhom_fb_tho = d
        for k in ("nhom", "muc", "ds"):
            if isinstance(d.get(k), list):
                return d[k]
        return []

    def bao_nhom(self, link: str, **kw) -> None:
        self._goi("POST", "/doi-social/may/nhom-fb", {"viec_id": self.vid, "link": link, **kw})

    def da_lam(self, khoa: str, ca_doi: bool = False) -> bool:
        q = self._q(nick_id=self.viec.get("nick_id"), khoa=khoa, ca_doi=1 if ca_doi else None, viec_id=self.vid)
        d = self._goi("GET", f"/doi-social/may/da-tuong-tac?{q}") or {}
        for k in ("da_lam", "co", "ket_qua"):
            if k in d:
                return bool(d[k])
        return False

    def ghi_da_lam(self, khoa: str) -> None:
        self._goi("POST", "/doi-social/may/da-tuong-tac",
                  {"khoa": khoa, "nick_id": self.viec.get("nick_id"), "viec_id": self.vid})

    def hoi_thoai(self, **kw) -> dict:
        return self._goi("POST", "/doi-social/may/hoi-thoai", {"viec_id": self.vid, **kw}) or {}

    def bai_doi_da_dang(self) -> list:
        d = self._goi("GET", f"/doi-social/may/bai-doi-da-dang?{self._q(viec_id=self.vid)}") or {}
        if isinstance(d, list):
            return d
        for k in ("bai", "muc", "ds"):
            if isinstance(d.get(k), list):
                return d[k]
        return []

    # ------------------------------------------------------------------ trình duyệt
    def chup(self) -> bytes:
        if self.page is None:
            return b""
        try:
            return self.page.screenshot(full_page=False, timeout=20000)
        except Exception:
            return b""

    def mo(self, url: str) -> None:
        mo_trang(self.page, url)

    def kiem_dang_nhap(self) -> None:
        if self.page is None:
            return
        page = self.page

        def co_css(sel: str) -> bool:
            loc = page.locator(sel)
            return loc.count() > 0 and loc.first.is_visible()

        def co_chu(mau: str) -> bool:
            loc = page.get_by_text(re.compile(mau, re.I))
            return loc.count() > 0 and loc.first.is_visible()

        ma = doan_trang_thai(self.nen_tang, page.url, co_css, co_chu)
        if ma:
            ten = {"facebook": "Facebook", "tiktok": "TikTok", "instagram": "Instagram", "threads": "Threads",
                   "x": "X", "reddit": "Reddit", "youtube": "YouTube"}.get(self.nen_tang, self.nen_tang)
            raise LoiKyNang(THONG_DIEP_MA[ma].format(nt=ten), ma=ma)

    # ------------------------------------------------------------------ tiện ích không thuộc hợp đồng
    def don_dep(self) -> None:
        if self._tu_tao_tam:
            import shutil
            shutil.rmtree(str(self.thu_muc_tam), ignore_errors=True)


def mo_trang(page, url: str) -> None:
    """Cùng cách với ky_nang_fb.mo_trang (chép lại ở đây để kỹ năng nền tảng khác không phụ thuộc
    tệp Facebook): goto chịu được trang tự chuyển hướng ('interrupted by another navigation')."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        if "interrupted by another navigation" not in str(e):
            raise
        page.wait_for_load_state("domcontentloaded", timeout=60000)


_TIEN_TO = {"fb_":"facebook", "tt_": "tiktok", "yt_": "youtube", "th_": "threads", "ig_": "instagram",
            "x_": "x", "rd_": "reddit"}
NOI_DANG_NEN_TANG = {"fb_nhom": "facebook", "fb_tuong": "facebook", "fb_trang": "facebook", "threads": "threads",
                     "instagram": "instagram", "reddit": "reddit", "x": "x", "tiktok": "tiktok", "youtube": "youtube"}


def doan_nen_tang(ky_nang: str, ts: Optional[dict] = None) -> str:
    if ky_nang == "dang_ban_nhap":
        return NOI_DANG_NEN_TANG.get(str((ts or {}).get("noi_dang") or ""), "facebook")
    for tt, nt in _TIEN_TO.items():
        if ky_nang.startswith(tt):
            return nt
    return "facebook"
