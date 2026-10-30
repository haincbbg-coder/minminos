"""Hàm dùng chung cho các kỹ năng TikTok, YouTube, Threads, Instagram, X, Reddit.

Gồm bốn nhóm:
  1. Tìm phần tử theo vai trò + nhãn trợ năng (tiếng Việt và tiếng Anh), chờ có hạn giờ, đọc lại trạng thái.
  2. CỔNG CÔNG KHAI: mọi cú bấm/phím Enter có thể làm người khác thấy (Đăng, Gửi, Thích, Đăng lại,
     Tham gia, Lưu...) PHẢI đi qua `bam_cong_khai` / `enter_cong_khai`. Ở chế độ chạy thử cổng từ chối,
     nên dù một kỹ năng viết sót nhánh kiểm `nc.chay_thu` thì cũng không có gì lọt ra ngoài.
  3. Chữ: chia chuỗi Threads (500 ký tự/phần, dòng --- tách), đếm ký tự kiểu X (chữ có dấu tính 2,
     link tính 23), chia chuỗi X (280).
  4. Khung chạy dùng chung: lấy bài kho đúng ngữ nghĩa trả bài, nhánh nháp/đăng của mẫu AI, chống lặp.

Không dựa vào class CSS băm. Có dùng `data-testid` (X) và `data-e2e` (TikTok) vì đó là thuộc tính
kiểm thử cố định của chính nền tảng, ổn định hơn class, nhưng luôn kèm phương án role/aria-label.
"""
from __future__ import annotations

import csv
import hashlib
import random
import re
import time
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from ngu_canh import LoiKyNang

THU_MUC = Path(__file__).resolve().parent
MA_DUNG = ("dang_xuat", "checkpoint", "captcha", "qua_nhanh")
# Nút gần nhất bao một biểu tượng svg (Threads/Instagram vẽ nút bằng <div role=button><svg aria-label>).
XP_NUT_CHA = "xpath=ancestor::*[@role='button' or local-name()='button'][1]"


# --------------------------------------------------------------------------- tìm phần tử

def re_nhan(*ds: str) -> "re.Pattern":
    """Khớp ĐÚNG cả nhãn (không phân biệt hoa thường)."""
    return re.compile(r"^\s*(" + "|".join(re.escape(x) for x in ds) + r")\s*$", re.I)


def re_chua(*ds: str) -> "re.Pattern":
    """Khớp nhãn CHỨA một trong các cụm."""
    return re.compile("(" + "|".join(re.escape(x) for x in ds) + ")", re.I)


def dau_tien_thay(cands: Sequence, timeout_ms: int = 15000):
    """Locator đầu tiên đang hiện trong danh sách, chờ tối đa timeout. Không thấy thì None."""
    han = time.monotonic() + max(0, timeout_ms) / 1000
    while True:
        for loc in cands:
            try:
                if loc.count() and loc.first.is_visible():
                    return loc.first
            except Exception:
                pass
        if time.monotonic() >= han:
            return None
        time.sleep(0.3)


def ung_vien(goc, role: str = "button", ten: Iterable[str] = (), nhan: Iterable[str] = (),
             css: Iterable[str] = (), chu: Iterable[str] = (), chua: bool = False) -> list:
    """Dựng danh sách locator dự phòng: role+tên, [aria-label], css cố định, chữ hiển thị."""
    ten, nhan, css, chu = list(ten), list(nhan), list(css), list(chu)
    out = []
    if ten:
        out.append(goc.get_by_role(role, name=(re_chua if chua else re_nhan)(*ten)))
    for x in nhan:
        x = x.replace('"', '\\"')
        out.append(goc.locator(f'[aria-label="{x}"]'))
        out.append(goc.locator(f'svg[aria-label="{x}"]').locator(XP_NUT_CHA))
    for c in css:
        out.append(goc.locator(c))
    if chu:
        out.append(goc.get_by_text((re_chua if chua else re_nhan)(*chu)))
    return out


def tim(goc, timeout_ms: int = 10000, **kw):
    return dau_tien_thay(ung_vien(goc, **kw), timeout_ms)


def cho(dieu_kien: Callable[[], bool], giay: float, buoc: float = 0.5) -> bool:
    """Chờ tới khi dieu_kien() đúng hoặc hết giờ. Lỗi trong dieu_kien coi như chưa đúng."""
    han = time.monotonic() + giay
    while True:
        try:
            if dieu_kien():
                return True
        except Exception:
            pass
        if time.monotonic() >= han:
            return False
        time.sleep(buoc)


def dang_hien(loc) -> bool:
    try:
        return bool(loc.count()) and loc.first.is_visible()
    except Exception:
        return False


def co_chu(goc, *ds: str) -> bool:
    """Trên trang (hoặc vùng) có đoạn chữ chứa một trong các cụm, đang hiện."""
    try:
        loc = goc.get_by_text(re_chua(*ds))
        n = min(loc.count(), 5)
        return any(loc.nth(i).is_visible() for i in range(n))
    except Exception:
        return False


def ghim(loc, goi_y: str = "") -> Optional[object]:
    """Gắn thuộc tính data-minmin cho phần tử để trỏ lại đúng nó sau khi trạng thái đổi (nhãn nút
    Thích -> Bỏ thích làm locator theo tên mất dấu). Trả locator mới, hoặc None."""
    ma = "mm" + hashlib.md5(f"{goi_y}{time.time()}{random.random()}".encode()).hexdigest()[:10]
    try:
        loc.evaluate("(e, m) => e.setAttribute('data-minmin', m)", ma)
        return loc.page.locator(f"[data-minmin='{ma}']")
    except Exception:
        return None


_JS_TRANG_THAI = """e => {
  const s = e.querySelector('svg[aria-label]');
  return [e.getAttribute('aria-pressed') || '', e.getAttribute('aria-label') || '',
          s ? s.getAttribute('aria-label') : '', e.getAttribute('data-testid') || '',
          (e.innerText || '').slice(0, 60)].join(' | ');
}"""


def doc_trang_thai(loc) -> str:
    """Chuỗi tóm tắt trạng thái nút: aria-pressed | aria-label | nhãn svg | data-testid | chữ."""
    try:
        return loc.first.evaluate(_JS_TRANG_THAI) or ""
    except Exception:
        return ""


def trong_khung(page, loc, toi_da: int = 30) -> list:
    """Các phần tử (locator nth) của loc đang nằm trong khung nhìn."""
    out = []
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        n = min(loc.count(), toi_da)
        for i in range(n):
            b = loc.nth(i).bounding_box(timeout=2000)
            if b and b["y"] >= 0 and b["y"] + b["height"] <= vp["height"] and b["width"] > 0:
                out.append(loc.nth(i))
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------- cổng công khai

def bam_cong_khai(nc, loc, mo_ta: str) -> bool:
    """Bấm một nút CÔNG KHAI. Chạy thử -> KHÔNG bấm, ghi nhật ký, trả False."""
    if not _duoc_cong_khai(nc, mo_ta):
        return False
    nc.tay.bam(loc)
    return True


def _duoc_cong_khai(nc, mo_ta: str) -> bool:
    """Chạy thử -> False (ghi nhật ký qua chốt chặn của lõi nếu lõi có, để lõi đếm số lần chặn)."""
    if not getattr(nc, "chay_thu", False):
        return True
    f = getattr(nc, "duoc_bam_cong_khai", None)
    if callable(f):
        try:
            f(mo_ta)
        except Exception:
            pass
    nc.nhat_ky(f"Chạy thử: không bấm/gửi '{mo_ta}'")
    return False


def enter_cong_khai(nc, mo_ta: str) -> bool:
    """Nhấn Enter để GỬI (ô chat/bình luận). Chạy thử -> không nhấn."""
    if not _duoc_cong_khai(nc, mo_ta):
        return False
    nc.page.keyboard.press("Enter")
    return True


def mot_dong(s: str) -> str:
    """Ô bình luận mà Enter là GỬI (TikTok, Instagram): bỏ xuống dòng để Nguoi.go không nhấn Enter."""
    return re.sub(r"\s*\n+\s*", " ", str(s or "")).strip()


def go_vao(nc, loc, text: str, xoa_truoc: bool = False) -> None:
    """Bấm vào ô nhập (không công khai) rồi gõ từng chữ bằng nc.tay.go."""
    nc.tay.bam(loc)
    nc.tay.nghi(0.4, 1.0)
    if xoa_truoc:
        nc.page.keyboard.press("Control+A")
        nc.page.keyboard.press("Backspace")
        nc.tay.nghi(0.3, 0.8)
    nc.tay.go(text)


def nghi_co_dung(nc, giay: float) -> bool:
    """Ngủ `giay` giây theo từng quãng ngắn (qua nc.tay.nghi), dừng sớm nếu đợt bị huỷ. True = nên dừng."""
    con = float(giay)
    while con > 0:
        if nc.nen_dung():
            return True
        q = min(5.0, con)
        nc.tay.nghi(q, q)
        con -= q
    return nc.nen_dung()


# --------------------------------------------------------------------------- nhận diện chặn

_QUA_NHANH = re_chua("quá nhanh", "too fast", "doing that too much", "làm điều đó quá nhiều",
                     "Try again later", "Thử lại sau", "rate limit", "Bạn đã đạt đến giới hạn",
                     "You've reached the limit", "Hành động bị chặn", "Action Blocked",
                     "We limit how often", "Chúng tôi giới hạn tần suất")
_CAPTCHA = re_chua("Kéo thanh trượt", "Drag the slider", "Xác minh để tiếp tục", "Verify to continue",
                   "Chọn 2 đối tượng", "Select 2 objects", "Xác minh bạn là người", "Verify you are human",
                   "Prove you're human", "Chứng minh bạn là người")
_CAPTCHA_CSS = ("#captcha-container, #captcha_container, [id^='captcha'], "
                "iframe[src*='captcha'], iframe[src*='arkoselabs'], iframe[src*='funcaptcha']")
_URL_DANG_XUAT = ("/login", "accounts.google.com", "/i/flow/login", "/accounts/login", "signin")
_URL_CHECKPOINT = ("/challenge", "/checkpoint", "/account/access", "/accounts/suspended", "/suspended")


def kiem_chan(nc, cho_phep_trang_dang_nhap: bool = False) -> None:
    """Đọc trang: đăng xuất / checkpoint / captcha / quá nhanh -> raise LoiKyNang(ma=...) ngay.
    cho_phep_trang_dang_nhap: kỹ năng cố ý mở trang đăng nhập (ig_dang_nhap_threads)."""
    page = nc.page
    url = (page.url or "").lower()
    if any(x in url for x in _URL_CHECKPOINT):
        raise LoiKyNang(f"{nc.nen_tang}: tài khoản đang bị kiểm tra/khoá ({page.url[:80]})", "checkpoint")
    if not cho_phep_trang_dang_nhap and any(x in url for x in _URL_DANG_XUAT):
        raise LoiKyNang(f"{nc.nen_tang}: bị đẩy về trang đăng nhập, nick đã đăng xuất", "dang_xuat")
    try:
        c = page.locator(_CAPTCHA_CSS)
        if any(c.nth(i).is_visible() for i in range(min(c.count(), 4))):
            raise LoiKyNang(f"{nc.nen_tang}: gặp captcha, dừng nick này", "captcha")
    except LoiKyNang:
        raise
    except Exception:
        pass
    if _co_re(page, _CAPTCHA):
        raise LoiKyNang(f"{nc.nen_tang}: gặp captcha, dừng nick này", "captcha")
    if not cho_phep_trang_dang_nhap:
        try:      # hộp "Đăng nhập vào TikTok"... hiện đè lên trang khi profile chưa đăng nhập
            nc.kiem_dang_nhap()
        except LoiKyNang:
            raise
        except Exception:
            pass
    if _co_re(page, _QUA_NHANH):
        raise LoiKyNang(f"{nc.nen_tang}: nền tảng báo thao tác quá nhanh / bị giới hạn", "qua_nhanh")


def _co_re(goc, rx) -> bool:
    try:
        loc = goc.get_by_text(rx)
        return any(loc.nth(i).is_visible() for i in range(min(loc.count(), 4)))
    except Exception:
        return False


def bam_va_xac_nhan(nc, dem: "Dem", hd: str, nut, da_xong: Callable[[object], bool], mo_ta: str,
                    link: str = "", giay: float = 8) -> bool:
    """Thao tác bật/tắt kiểu Thích, Lưu, Đăng lại, Tham gia: đọc trạng thái trước (đã làm -> bỏ qua),
    chạy thử -> chỉ báo, chạy thật -> bấm qua cổng rồi ĐỌC LẠI đúng nút đó. True khi thành công thật."""
    try:
        truoc = da_xong(nut)
    except Exception:
        truoc = False
    if truoc:
        bao(nc, dem, hd, "bo_qua", f"Đã {mo_ta} từ trước", link=link)
        return False
    if nc.chay_thu:
        bao_thu(nc, dem, hd, f"Chạy thử: sẽ {mo_ta}", link=link)
        return False
    pin = ghim(nut, mo_ta) or nut
    if not bam_cong_khai(nc, nut, mo_ta):
        return False
    ok = cho(lambda: da_xong(pin), giay)
    kiem_chan(nc)
    if ok:
        bao(nc, dem, hd, "thanh_cong", f"Đã {mo_ta} (đọc lại thấy trạng thái đổi)", link=link)
    else:
        bao(nc, dem, hd, "loi", f"Đã bấm {mo_ta} nhưng đọc lại chưa thấy trạng thái đổi "
                                f"({doc_trang_thai(pin)[:80]})", link=link)
    nc.nghi_thao_tac()
    return ok


_JS_CO_CHU = """(s) => {
  const norm = x => (x || '').replace(/\\s+/g, ' ').trim();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n, dem = 0;
  while ((n = w.nextNode())) {
    if (!norm(n.textContent).includes(s)) continue;
    const e = n.parentElement;
    if (!e || e.closest('[contenteditable], textarea, input')) continue;
    const r = e.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) dem++;
  }
  return dem;
}"""


def doan_nhan_dien(text: str, dai: int = 30) -> str:
    """Một đoạn ngắn của nội dung để tìm lại trên trang: bỏ @nhắc tên đầu câu, dừng trước link/#thẻ."""
    s = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text or ""))).strip()
    s = re.sub(r"^(@\S+\s*)+", "", s)
    s = re.split(r"(?:https?://|www\.|#)", s)[0].strip()
    return s[:dai].strip()


def dem_chu_ngoai_o_nhap(page, text: str) -> int:
    """Số chỗ đoạn chữ đang hiện trên trang ngoài ô nhập (tức là đã gửi đi, không phải còn nằm
    trong ô soạn)."""
    s = doan_nhan_dien(text)
    if not s:
        return 0
    try:
        return int(page.evaluate(_JS_CO_CHU, s) or 0)
    except Exception:
        return 0


def thay_chu_ngoai_o_nhap(page, text: str) -> bool:
    return dem_chu_ngoai_o_nhap(page, text) > 0


def gui_noi_dung(nc, o_nhap, text: str, nut_gui: Callable[[], object] = None, enter_gui: bool = False,
                 mo_ta: str = "Gửi bình luận", giay_xac_nhan: float = 20,
                 xac_nhan: Callable[[], bool] = None) -> bool:
    """Gõ text vào o_nhap rồi gửi qua cổng công khai, ĐỌC LẠI thấy chữ hiện ngoài ô nhập.
    nut_gui() trả locator nút gửi (tìm SAU khi gõ vì nút thường chỉ bật khi có chữ).
    Trả True khi thấy nội dung đã lên; chạy thử thì không gõ, không gửi, trả False."""
    if nc.chay_thu:
        nc.nhat_ky(f"Chạy thử: không gõ/không '{mo_ta}'")
        return False
    truoc = dem_chu_ngoai_o_nhap(nc.page, text)   # câu trùng đã có sẵn (LIVE nhiều nick) không tính
    go_vao(nc, o_nhap, text)
    nc.tay.nghi(0.8, 2.0)
    nut = nut_gui() if nut_gui else None
    if nut is not None:
        if not bam_cong_khai(nc, nut, mo_ta):
            return False
    elif enter_gui:
        if not enter_cong_khai(nc, mo_ta):
            return False
    else:
        raise LoiKyNang(f"không thấy nút '{mo_ta}'")
    ok = cho(xac_nhan or (lambda: dem_chu_ngoai_o_nhap(nc.page, text) > truoc), giay_xac_nhan, 0.8)
    kiem_chan(nc)
    return ok


def nhan_bat(loc, *ds_nhan: str) -> bool:
    """Nút đang ở trạng thái 'đã bật': aria-pressed=true, hoặc nhãn/nhãn svg/data-testid khớp một cụm."""
    s = doc_trang_thai(loc)
    if not s:
        return False
    p = s.split(" | ")
    if p and p[0] == "true":
        return True
    rx = re_nhan(*ds_nhan) if ds_nhan else None
    return bool(rx and any(rx.match(x) for x in p[1:4] if x))


# --------------------------------------------------------------------------- chữ

def chia_threads(text: str, gioi_han: int = 500) -> List[str]:
    """Tách bài Threads thành chuỗi: dòng chỉ gồm '---' là ranh giới; phần nào quá gioi_han ký tự thì
    cắt tiếp ở ranh giới câu/từ. Bỏ phần rỗng."""
    phan = re.split(r"(?m)^\s*-{3,}\s*$", str(text or ""))
    out: List[str] = []
    for p in phan:
        p = p.strip()
        if p:
            out.extend(_cat_theo(p, gioi_han, len))
    return out


_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
_X_MOT = ((0x0000, 0x00BF), (0x2000, 0x200D), (0x2010, 0x201F), (0x2032, 0x2037))


def _trong_so_x(ch: str) -> int:
    o = ord(ch)
    return 1 if any(a <= o <= b for a, b in _X_MOT) else 2


def dem_ky_tu_x(text: str) -> int:
    """Đếm ký tự theo cách X tính (bảo thủ, để không bao giờ vượt): link http(s)/www = 23,
    ASCII và dấu câu chung = 1, mọi chữ có dấu / chữ ngoài Latin / emoji = 2. Chuẩn hoá NFC trước
    (gõ kiểu tổ hợp 'a' + dấu cũng thành một chữ)."""
    s = unicodedata.normalize("NFC", str(text or ""))
    n, i = 0, 0
    for m in _URL_RE.finditer(s):
        n += sum(_trong_so_x(c) for c in s[i:m.start()]) + 23
        i = m.end()
    return n + sum(_trong_so_x(c) for c in s[i:])


def chia_x(text: str, gioi_han: int = 280) -> List[str]:
    """Chia bài X thành chuỗi: dòng '---' là ranh giới bắt buộc; phần quá gioi_han (theo dem_ky_tu_x)
    cắt ở ranh giới câu/từ, không bao giờ cắt đôi một link."""
    phan = re.split(r"(?m)^\s*-{3,}\s*$", unicodedata.normalize("NFC", str(text or "")))
    out: List[str] = []
    for p in phan:
        p = p.strip()
        if p:
            out.extend(_cat_theo(p, gioi_han, dem_ky_tu_x))
    return out


def _cat_theo(p: str, gioi_han: int, dem: Callable[[str], int]) -> List[str]:
    if dem(p) <= gioi_han:
        return [p]
    # token = (chữ, khoảng trắng theo sau); ưu tiên cắt sau dấu kết câu
    tok = re.findall(r"\S+\s*", p)
    out, cur = [], ""
    for t in tok:
        thu = cur + t
        if dem(thu.rstrip()) <= gioi_han:
            cur = thu
            continue
        if cur.strip():
            # lùi về ranh giới câu gần nhất nếu nó không quá ngắn
            m = list(re.finditer(r"[.!?…]\s+", cur))
            if m and m[-1].end() > len(cur) * 0.5:
                vt = m[-1].end()
                out.append(cur[:vt].strip())
                cur = cur[vt:]
                thu = cur + t
                if dem(thu.rstrip()) <= gioi_han:
                    cur = thu
                    continue
            out.append(cur.strip())
            cur = ""
        # một từ đơn quá dài (không phải link): cắt cứng theo ký tự
        while dem(t.rstrip()) > gioi_han and not _URL_RE.fullmatch(t.strip()):
            k = len(t)
            while k > 1 and dem(t[:k]) > gioi_han:
                k -= 1
            out.append(t[:k])
            t = t[k:]
        cur = t
    if cur.strip():
        out.append(cur.strip())
    return out


def cat_gioi_han(text: str, gioi_han: int) -> str:
    s = str(text or "").strip()
    return s if len(s) <= gioi_han else s[:gioi_han - 1].rstrip() + "…"


def ds_dong(s) -> List[str]:
    if isinstance(s, (list, tuple)):
        return [str(x).strip() for x in s if str(x).strip()]
    return [x.strip() for x in str(s or "").splitlines() if x.strip()]


def ten_sub(s: str) -> str:
    s = str(s or "").strip().rstrip("/")
    m = re.search(r"reddit\.com/r/([A-Za-z0-9_]+)", s)
    if m:
        return m.group(1)
    return re.sub(r"^/?r/", "", s, flags=re.I).strip()


def ds_sub(s: str) -> List[str]:
    return [t for t in (ten_sub(x) for x in re.split(r"[,\n;]+", str(s or ""))) if t]


def bam_chuoi(s: str) -> str:
    return hashlib.sha1(str(s or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def khoa(nen_tang: str, loai: str, *phan) -> str:
    """Khoá chống lặp có tiền tố nền tảng: 'tiktok:tuong_tac:<link>'."""
    return ":".join([nen_tang, loai] + [str(x) for x in phan])[:400]


# --------------------------------------------------------------------------- đếm + báo

class Dem:
    """Đếm cục bộ một lượt chạy. `thu[hd]` là số lần 'sẽ làm' (chạy thử / nháp) để vòng lặp chạy thử
    cũng dừng ở hạn mức như chạy thật."""

    def __init__(self):
        self.ok: Dict[str, int] = {}
        self.bo: Dict[str, int] = {}
        self.loi: Dict[str, int] = {}
        self.thu: Dict[str, int] = {}

    def tong(self, d: Dict[str, int]) -> int:
        return sum(d.values())

    def tom_tat(self) -> str:
        return f"thành công {self.tong(self.ok)}, bỏ qua {self.tong(self.bo)}, lỗi {self.tong(self.loi)}" + (
            f", chạy thử/nháp {self.tong(self.thu)}" if self.thu else "")


def bao(nc, dem: Dem, hd: str, ket_qua: str, chi_tiet: str = "", **kw) -> dict:
    bang = {"thanh_cong": dem.ok, "bo_qua": dem.bo, "loi": dem.loi}.get(ket_qua)
    if bang is not None:
        bang[hd] = bang.get(hd, 0) + 1
    nc.nhat_ky(f"{hd}: {ket_qua} - {chi_tiet}"[:300])
    try:
        return nc.su_kien(hd, ket_qua, chi_tiet[:500], **kw) or {}
    except LoiKyNang:
        raise
    except Exception as e:  # báo sự kiện hỏng không được làm sập kỹ năng
        nc.nhat_ky(f"Không gửi được sự kiện: {e}")
        return {}


def bao_thu(nc, dem: Dem, hd: str, chi_tiet: str, **kw) -> None:
    """Một thao tác 'sẽ làm' ở chạy thử / nháp: báo thong_tin và tính vào dem.thu."""
    dem.thu[hd] = dem.thu.get(hd, 0) + 1
    bao(nc, dem, hd, "thong_tin", chi_tiet, **kw)


def con_luot(nc, dem: Dem, hd: str) -> bool:
    """Còn được làm thêm một thao tác `hd` không (tính cả các lượt chạy thử đã 'tiêu')."""
    return nc.con_lai(hd) - dem.thu.get(hd, 0) > 0


def bao_loi_ngoai_le(nc, dem: Dem, hd: str, e: Exception, link: str = "") -> None:
    """Lỗi giữa vòng lặp: mã dừng thì ném tiếp, còn lại ghi sự kiện lỗi."""
    if isinstance(e, LoiKyNang) and getattr(e, "ma", None) in MA_DUNG:
        raise e
    bao(nc, dem, hd, "loi", (str(e) or type(e).__name__)[:300], link=link)


def ket_thuc(nc, dem: Dem, ten: str, co_thu: bool = True) -> str:
    """Câu tổng kết. Chạy thật mà có lỗi và không thành công lượt nào -> raise để việc báo thất bại."""
    if not nc.chay_thu and dem.tong(dem.loi) and not dem.tong(dem.ok) and not dem.tong(dem.thu):
        raise LoiKyNang(f"{ten}: không thành công lượt nào ({dem.tom_tat()})")
    tien_to = "Chạy thử - " if nc.chay_thu else ""
    return f"{tien_to}{ten}: {dem.tom_tat()}."


# --------------------------------------------------------------------------- AI: nháp hay đăng

def che_do_ai(nc) -> str:
    if getattr(nc, "chay_thu", False):
        return "chay_thu"
    cd = getattr(nc, "che_do", "") or (nc.ts or {}).get("che_do") or "chay_thu"
    return cd if cd in ("chay_thu", "duyet_truoc", "dang_luon") else "chay_thu"


def noi_dung_ai(nc, dem: Dem, hd: str, *, loai: str, noi_dang: str, link_goc: str, bai_goc: str,
                ly_do: str, noi_dung: str, khoa_lap: str, dang: Callable[[str], str],
                san_pham_id: str = "", nhom: str = "") -> None:
    """Một nội dung AI vừa viết: chạy thử / duyệt trước -> tạo nháp; đăng luôn -> gọi dang(noi_dung)
    (trả link, raise khi hỏng) rồi báo thành công. Cả hai đều ghi khoá chống lặp."""
    cd = che_do_ai(nc)
    if not str(noi_dung or "").strip():
        bao(nc, dem, hd, "bo_qua", "AI không viết được nội dung", link=link_goc)
        return
    if cd in ("chay_thu", "duyet_truoc"):
        kw = dict(loai=loai, noi_dang=noi_dang, link_goc=link_goc, bai_goc=str(bai_goc or "")[:2000],
                  ly_do=ly_do, noi_dung=noi_dung, san_pham_id=san_pham_id)
        if nhom:
            kw["nhom"] = nhom
        bid = nc.ban_nhap(**kw)
        nc.ghi_da_lam(khoa_lap)
        if cd == "chay_thu":
            bao_thu(nc, dem, hd, f"Chạy thử: sẽ {loai.replace('_', ' ')} \"{noi_dung[:80]}\" (nháp #{bid})",
                    link=link_goc, san_pham=san_pham_id)
        else:
            bao_thu(nc, dem, hd, f"Đã tạo nháp #{bid} chờ duyệt: \"{noi_dung[:80]}\"", link=link_goc,
                    san_pham=san_pham_id)
        return
    link = dang(noi_dung)
    nc.ghi_da_lam(khoa_lap)
    bao(nc, dem, hd, "thanh_cong", f"{ly_do[:120]} -> \"{noi_dung[:80]}\"", link=link or link_goc,
        san_pham=san_pham_id)
    nc.nghi_thao_tac()


def lay_ai(nc, muc_dich: str, du_lieu: dict, anh: Sequence[bytes] = ()) -> dict:
    kq = nc.ai(muc_dich, du_lieu, list(anh)) if anh else nc.ai(muc_dich, du_lieu)
    return kq if isinstance(kq, dict) else {}


# --------------------------------------------------------------------------- kho bài

class LoiDang(Exception):
    """Lỗi khi đăng một bài, mang cờ đã bấm Đăng hay chưa."""

    def __init__(self, thong_diep: str, da_bam_dang: bool, ma: Optional[str] = None):
        super().__init__(thong_diep)
        self.da_bam_dang = da_bam_dang
        self.ma = ma


class TrangThaiDang:
    """Truyền vào hàm đăng để nó đánh dấu thời điểm bấm Đăng (ngữ nghĩa xong_kho)."""

    def __init__(self):
        self.da_bam = False


def chay_kho(nc, hd: str, so_bai: int, ten: str,
             dang_mot: Callable[[dict, TrangThaiDang], str],
             kiem_bai: Optional[Callable[[dict], str]] = None,
             nghi_giua: Callable[[], bool] = lambda: False) -> str:
    """Khung chung cho mẫu *_kho. dang_mot(bai, tt) trả link khi thành công (đã ĐỌC LẠI thấy bài),
    raise khi hỏng; trước khi bấm Đăng nó đặt tt.da_bam = True. kiem_bai(bai) trả lý do bài không
    hợp lệ (rỗng = hợp lệ). nghi_giua() chạy giữa hai bài, trả True nếu nên dừng."""
    dem = Dem()
    for i in range(max(1, int(so_bai or 1))):
        if nc.nen_dung():
            nc.nhat_ky("Đợt bị huỷ / hết hạn mức, dừng")
            break
        if not con_luot(nc, dem, hd):
            nc.nhat_ky("Đã đủ giới hạn hôm nay")
            break
        if i and nghi_giua():
            break
        bai = nc.lay_kho()
        if not bai:
            bao(nc, dem, hd, "bo_qua", "Hết bài", ma="het_bai")
            if not dem.tong(dem.ok) and not dem.tong(dem.thu):
                return "Hết bài"
            break
        bid = bai.get("id")
        nc.nhat_ky(f"Lấy bài kho #{bid}: {str(bai.get('tieu_de') or bai.get('noi_dung') or '')[:60]}")
        ly_do = kiem_bai(bai) if kiem_bai else ""
        if ly_do:
            nc.xong_kho(bid, False, False, loi=ly_do)
            bao(nc, dem, hd, "loi", f"Bài #{bid}: {ly_do}")
            break   # bài trả về hàng chờ; dừng để không lấy lại đúng bài đó ngay
        if nc.chay_thu:
            nc.xong_kho(bid, False, False, loi="Chạy thử: không đăng, trả bài về hàng chờ")
            bao_thu(nc, dem, hd, f"Chạy thử: sẽ đăng bài kho #{bid} "
                                 f"({len(bai.get('tep_cuc_bo') or [])} tệp): {str(bai.get('noi_dung') or '')[:80]}")
            continue
        tt = TrangThaiDang()
        try:
            link = dang_mot(bai, tt)
        except Exception as e:
            da_bam = bool(getattr(e, "da_bam_dang", tt.da_bam))
            nc.xong_kho(bid, False, da_bam, loi=str(e)[:300])
            ma = getattr(e, "ma", None)
            if ma in MA_DUNG:
                raise LoiKyNang(str(e), ma)
            bao(nc, dem, hd, "loi", f"Bài #{bid}: {e}" + (" (đã bấm Đăng, không tự đăng lại)" if da_bam else
                                                            " (chưa bấm Đăng, bài về hàng chờ)"))
            break
        nc.xong_kho(bid, True, True, link=link or "")
        bao(nc, dem, hd, "thanh_cong", f"Đã đăng bài kho #{bid}", link=link or "")
        nc.nghi_thao_tac()
    return ket_thuc(nc, dem, ten)


def loc_tep(tep: Sequence[str], duoi: Iterable[str]) -> List[str]:
    d = tuple(x.lower() for x in duoi)
    return [t for t in (tep or []) if str(t).lower().endswith(d)]


DUOI_ANH = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")
DUOI_VIDEO = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")


# --------------------------------------------------------------------------- bản nháp đã duyệt

def tham_so_ban_nhap(nc) -> dict:
    """Tham số của việc nội bộ dang_ban_nhap (4.3), đọc được dù lõi để ở ts hay ở viec.tham_so."""
    for d in (getattr(nc, "ts", None) or {}, (getattr(nc, "viec", None) or {}).get("tham_so") or {}):
        if isinstance(d, dict) and (d.get("ban_nhap_id") or d.get("noi_dung")):
            return d
    return getattr(nc, "ts", None) or {}


_MUC_TIEU = "#minmin-tra-loi="


def gan_muc_tieu(link: str, tac_gia: str, chu: str) -> str:
    """Nháp trả lời bình luận: nhét (tác giả, đầu câu) của bình luận đích vào phân mảnh link_goc để
    dang_ban_nhap tìm lại đúng bình luận (máy chủ chưa có trường riêng cho việc này)."""
    return (str(link or "").split("#")[0] + _MUC_TIEU + urllib.parse.quote(str(tac_gia or "")[:60])
            + "~" + urllib.parse.quote(str(chu or "")[:40]))


def tach_muc_tieu(link: str):
    """-> (link sạch, tác giả, đầu câu) ; không có mục tiêu thì tác giả/câu rỗng."""
    s = str(link or "")
    if _MUC_TIEU not in s:
        return s, "", ""
    goc, _, mt = s.partition(_MUC_TIEU)
    tg, _, chu = mt.partition("~")
    return goc, urllib.parse.unquote(tg), urllib.parse.unquote(chu)


def dang_ban_nhap_chung(nc, nen_tang: str, ham: Dict[str, Callable[[dict], str]]) -> str:
    """Khung dang_ban_nhap:<nen_tang>. ham[loai](p) trả link khi đọc lại thấy nội dung đã lên."""
    p = tham_so_ban_nhap(nc)
    bid = p.get("ban_nhap_id")
    loai = str(p.get("loai") or "binh_luan")
    hd = {"bai_dang": "dang_tuong", "tra_loi": "tra_loi_binh_luan"}.get(loai, "binh_luan")
    dem = Dem()
    f = ham.get(loai)
    if not f:
        loi = f"{nen_tang} chưa hỗ trợ đăng nháp loại '{loai}'"
        if bid and not nc.chay_thu:
            nc.xong_ban_nhap(bid, False, loi=loi)
        raise LoiKyNang(loi)
    if nc.chay_thu:
        bao_thu(nc, dem, hd, f"Chạy thử: sẽ đăng nháp #{bid} ({loai}) lên {nen_tang}: "
                             f"\"{str(p.get('noi_dung') or '')[:80]}\"", link=str(p.get("link_goc") or ""))
        return f"Chạy thử: không đăng nháp #{bid}."
    try:
        link = f(p)
    except Exception as e:
        if bid:
            nc.xong_ban_nhap(bid, False, loi=str(e)[:300])
        ma = getattr(e, "ma", None)
        if ma in MA_DUNG:
            raise LoiKyNang(str(e), ma)
        bao(nc, dem, hd, "loi", f"Nháp #{bid}: {e}", link=str(p.get("link_goc") or ""))
        raise LoiKyNang(f"Không đăng được nháp #{bid}: {e}")
    if bid:
        nc.xong_ban_nhap(bid, True, link=link or "")
    bao(nc, dem, hd, "thanh_cong", f"Đã đăng nháp #{bid} ({loai})", link=link or str(p.get("link_goc") or ""))
    return f"Đã đăng nháp #{bid} lên {nen_tang}."


def dang_ai_da_duyet(nc, noi_dang: str, hd: str, so_bai: int, ten: str,
                     dang: Callable[[dict], str]) -> str:
    """Mẫu *_dang_ai: lấy nháp da_duyet qua nc.lay_ban_nhap, đăng, xong_ban_nhap. Chạy thử không lấy
    nháp (lay_ban_nhap GIỮ nháp cho việc) mà chỉ báo sẽ làm gì."""
    dem = Dem()
    if nc.chay_thu:
        bao_thu(nc, dem, hd, f"Chạy thử: sẽ lấy tối đa {so_bai} bài {noi_dang} đã duyệt và đăng")
        return ket_thuc(nc, dem, ten)
    for _ in range(max(1, int(so_bai or 1))):
        if nc.nen_dung() or not con_luot(nc, dem, hd):
            break
        bn = nc.lay_ban_nhap(noi_dang)
        if not bn:
            bao(nc, dem, hd, "bo_qua", f"Không còn bài {noi_dang} đã duyệt", ma="het_bai")
            break
        bid = bn.get("id")
        try:
            link = dang(bn)
        except Exception as e:
            nc.xong_ban_nhap(bid, False, loi=str(e)[:300])
            bao_loi_ngoai_le(nc, dem, hd, e)
            break
        nc.xong_ban_nhap(bid, True, link=link or "")
        bao(nc, dem, hd, "thanh_cong", f"Đã đăng nháp #{bid}", link=link or "",
            san_pham=str(bn.get("san_pham_id") or ""))
        nc.nghi_thao_tac()
    if not dem.tong(dem.ok) and dem.tong(dem.bo) and not dem.tong(dem.loi):
        return "Hết bài"
    return ket_thuc(nc, dem, ten)


# --------------------------------------------------------------------------- CSV

def ghi_csv(ten_tep: str, cot: Sequence[str], dong: Sequence[dict]) -> Path:
    """Ghi CSV UTF-8 có BOM (Excel đọc đúng tiếng Việt) vào thư mục quet/ cạnh worker.

    26.10.311: Worker Chrome tích hợp trên VPS chạy trong /app chỉ đọc -> ghi vào thư mục dữ liệu
    (JAVIS_STATE_DIR) hoặc thư mục tạm. Bên gọi vẫn gửi tệp về MinMin như cũ."""
    import os
    import tempfile
    ung_vien = [THU_MUC / "quet"]
    if os.environ.get("JAVIS_STATE_DIR"):
        ung_vien.append(Path(os.environ["JAVIS_STATE_DIR"]) / "doi-social-quet")
    ung_vien.append(Path(tempfile.gettempdir()) / "minmin-quet")
    tm = None
    for d in ung_vien:
        try:
            d.mkdir(parents=True, exist_ok=True)
            thu = d / ".ghi-thu"
            thu.write_text("1")
            thu.unlink()
            tm = d
            break
        except OSError:
            continue
    if tm is None:
        raise OSError("không có thư mục ghi được để lưu bảng CSV")
    p = tm / ten_tep
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cot), extrasaction="ignore")
        w.writeheader()
        for d in dong:
            w.writerow(d)
    return p


def rng_nick(nc) -> random.Random:
    """Bộ ngẫu nhiên riêng mỗi nick mỗi lượt (trộn câu bình luận khác nhau giữa các nick)."""
    v = getattr(nc, "viec", None) or {}
    return random.Random(f"{v.get('nick_id')}-{v.get('id')}-{time.time()}")
