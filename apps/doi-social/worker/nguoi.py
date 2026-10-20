"""Thao tác giống người thật trên trình duyệt (Playwright, API đồng bộ).

Tách phần LẬP KẾ HOẠCH (hàm thuần, kiểm thử được, không cần trình duyệt) khỏi phần THỰC HIỆN
(gửi phím/chuột vào trang). Nhịp gõ không đều: mỗi chữ một độ trễ khác nhau, chậm hơn sau dấu
câu và khoảng trắng, thỉnh thoảng dừng như đang nghĩ, thỉnh thoảng gõ nhầm phím bên cạnh rồi
xoá lại. Không dán clipboard, không bơm cả đoạn vào ô nhập.

Gõ nhầm chỉ xảy ra với chữ cái ASCII nằm ngoài link, @nhắc tên và #hashtag, để không bao giờ
làm hỏng một đường link hay một thẻ. Chữ có dấu tiếng Việt và emoji được gõ đúng một lần.
"""
from __future__ import annotations

import math
import random
import time
from typing import List, Optional, Tuple

# Phím nằm cạnh nhau trên bàn phím QWERTY: gõ nhầm của người thật thường rơi vào phím bên cạnh.
_KE = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr", "f": "drtgvc", "g": "ftyhbv",
    "h": "gyujnb", "i": "ujko", "j": "huikmn", "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm",
    "o": "iklp", "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy", "u": "yhji",
    "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}

Buoc = Tuple[str, str, int]   # (loai, gia_tri, tre_ms) - loai: "go" | "phim" | "nghi"


def _vung_cam(text: str) -> List[bool]:
    """True ở vị trí không được phép gõ nhầm: trong link, @tên, #thẻ."""
    cam = [False] * len(text)
    i = 0
    n = len(text)
    while i < n:
        if text.startswith(("http://", "https://", "www."), i) or text[i] in "@#":
            j = i
            while j < n and not text[j].isspace():
                cam[j] = True
                j += 1
            i = j
        else:
            i += 1
    return cam


def tre_chu(ch: str, truoc: str, rng: random.Random, toc_do: float = 1.0) -> int:
    """Độ trễ (ms) TRƯỚC khi gõ chữ `ch`, theo phân phối log-chuẩn quanh ~110ms."""
    base = rng.lognormvariate(math.log(110), 0.35)
    if truoc in ".!?":
        base += rng.uniform(250, 700)
    elif truoc in ",;:":
        base += rng.uniform(120, 350)
    elif truoc == "\n":
        base += rng.uniform(300, 900)
    elif truoc == " ":
        base += rng.uniform(10, 90)
    return int(max(35, min(base, 1500)) / max(0.3, toc_do))


def ke_hoach_go(text: str, rng: Optional[random.Random] = None, ty_le_nham: float = 0.02,
                toc_do: float = 1.0) -> List[Buoc]:
    """Biến một đoạn chữ thành danh sách bước gõ. Ghép lại các bước "go"/"phim" (Backspace xoá
    một ký tự) luôn cho ra ĐÚNG `text` - test kiểm điều này."""
    rng = rng or random.Random()
    cam = _vung_cam(text)
    out: List[Buoc] = []
    truoc = ""
    ke_tu_nghi = rng.randint(25, 60)
    for i, ch in enumerate(text):
        tre = tre_chu(ch, truoc, rng, toc_do)
        ke_tu_nghi -= 1
        if ke_tu_nghi <= 0 and ch == " ":
            out.append(("nghi", "", int(rng.uniform(700, 2400) / max(0.3, toc_do))))
            ke_tu_nghi = rng.randint(25, 60)
        thap = ch.lower()
        if (not cam[i] and thap in _KE and ch.isascii() and rng.random() < ty_le_nham):
            sai = rng.choice(_KE[thap])
            sai = sai.upper() if ch.isupper() else sai
            out.append(("go", sai, tre))
            out.append(("phim", "Backspace", int(rng.uniform(180, 520))))
            tre = int(rng.uniform(90, 260))
        if ch == "\n":
            out.append(("phim", "Enter", tre))
        else:
            out.append(("go", ch, tre))
        truoc = ch
    return out


def ap_ke_hoach(buoc: List[Buoc]) -> str:
    """Mô phỏng kết quả của kế hoạch (dùng cho test)."""
    s: List[str] = []
    for loai, gt, _ in buoc:
        if loai == "go":
            s.append(gt)
        elif loai == "phim" and gt == "Backspace":
            if s:
                s.pop()
        elif loai == "phim" and gt == "Enter":
            s.append("\n")
    return "".join(s)


def duong_cong(x0: float, y0: float, x1: float, y1: float, rng: random.Random,
               so_buoc: Optional[int] = None) -> List[Tuple[float, float]]:
    """Đường Bézier bậc ba từ (x0,y0) tới (x1,y1), hai điểm điều khiển lệch ngẫu nhiên sang
    hai bên, tốc độ nhanh ở giữa chậm ở hai đầu (ease-in-out) như tay người cầm chuột."""
    d = math.hypot(x1 - x0, y1 - y0)
    n = so_buoc or max(12, min(60, int(d / 12)))
    lech = max(20.0, d * 0.25)
    c1 = (x0 + (x1 - x0) * 0.3 + rng.uniform(-lech, lech), y0 + (y1 - y0) * 0.3 + rng.uniform(-lech, lech))
    c2 = (x0 + (x1 - x0) * 0.7 + rng.uniform(-lech, lech), y0 + (y1 - y0) * 0.7 + rng.uniform(-lech, lech))
    pts = []
    for k in range(1, n + 1):
        t = k / n
        t = t * t * (3 - 2 * t)
        u = 1 - t
        x = u ** 3 * x0 + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * x1
        y = u ** 3 * y0 + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * y1
        pts.append((x, y))
    pts[-1] = (x1, y1)
    return pts


def chon_cau(ds, rng: Optional[random.Random] = None, tranh: Optional[List[str]] = None) -> str:
    """Chọn ngẫu nhiên một câu (chuỗi nhiều dòng hoặc list), bỏ dòng trống, ưu tiên câu chưa dùng
    trong `tranh`. Trả "" nếu không có câu nào."""
    rng = rng or random.Random()
    if isinstance(ds, str):
        ds = ds.splitlines()
    cau = [str(x).strip() for x in (ds or []) if str(x).strip()]
    if not cau:
        return ""
    moi = [c for c in cau if c not in (tranh or [])]
    return rng.choice(moi or cau)


class Nguoi:
    """Bàn tay ảo gắn với một trang Playwright (sync)."""

    def __init__(self, page, rng: Optional[random.Random] = None, toc_do: float = 1.0):
        self.page = page
        self.rng = rng or random.Random()
        self.toc_do = toc_do
        self.x, self.y = self.rng.uniform(200, 600), self.rng.uniform(150, 400)

    def nghi(self, a: float, b: float) -> None:
        time.sleep(self.rng.uniform(a, b) / max(0.3, self.toc_do))

    def di_toi(self, locator) -> Tuple[float, float]:
        locator.scroll_into_view_if_needed(timeout=15000)
        box = locator.bounding_box(timeout=15000)
        if not box:
            raise RuntimeError("không thấy vị trí phần tử trên màn hình")
        tx = box["x"] + box["width"] * self.rng.uniform(0.3, 0.7)
        ty = box["y"] + box["height"] * self.rng.uniform(0.35, 0.65)
        for px, py in duong_cong(self.x, self.y, tx, ty, self.rng):
            self.page.mouse.move(px, py)
            time.sleep(self.rng.uniform(0.004, 0.018))
        self.x, self.y = tx, ty
        return tx, ty

    def bam(self, locator) -> None:
        self.di_toi(locator)
        self.nghi(0.08, 0.35)
        self.page.mouse.down()
        time.sleep(self.rng.uniform(0.05, 0.14))
        self.page.mouse.up()

    def go(self, text: str, ty_le_nham: float = 0.02) -> None:
        kb = self.page.keyboard
        for loai, gt, tre in ke_hoach_go(text, self.rng, ty_le_nham, self.toc_do):
            time.sleep(tre / 1000.0)
            if loai == "nghi":
                continue
            if loai == "phim":
                kb.press(gt)
            elif ord(gt[0]) > 0xFFFF or len(gt) > 1:
                kb.insert_text(gt)          # emoji ngoài BMP: một lần chèn, như bộ gõ emoji
            else:
                kb.type(gt)

    def phim(self, ten: str) -> None:
        """Nhấn một phím/tổ hợp phím (vd 'Enter', 'Escape', 'Shift+Enter') sau một nhịp ngắn."""
        time.sleep(self.rng.uniform(0.12, 0.45) / max(0.3, self.toc_do))
        self.page.keyboard.press(ten)

    def go_binh_luan(self, text: str, ty_le_nham: float = 0.02) -> None:
        """Như go() nhưng xuống dòng bằng Shift+Enter: trong ô bình luận/tin nhắn, Enter là GỬI."""
        kb = self.page.keyboard
        for loai, gt, tre in ke_hoach_go(text, self.rng, ty_le_nham, self.toc_do):
            time.sleep(tre / 1000.0)
            if loai == "nghi":
                continue
            if loai == "phim":
                kb.press("Shift+Enter" if gt == "Enter" else gt)
            elif ord(gt[0]) > 0xFFFF or len(gt) > 1:
                kb.insert_text(gt)
            else:
                kb.type(gt)

    def re_chuot(self, locator, giay: float = 1.5) -> None:
        """Đưa chuột tới phần tử rồi giữ yên ở đó (để hiện bảng cảm xúc, xem trước video...)."""
        self.di_toi(locator)
        time.sleep(max(0.2, giay) * self.rng.uniform(0.85, 1.25) / max(0.3, self.toc_do))

    def luot_doc(self, giay: float) -> None:
        """Lướt đọc tự nhiên trong khoảng `giay` giây: cuộn từng đoạn dài ngắn khác nhau, dừng đọc,
        thỉnh thoảng kéo ngược lên xem lại."""
        han = time.monotonic() + max(0.0, giay) / max(0.3, self.toc_do)
        while time.monotonic() < han:
            r = self.rng.random()
            if r < 0.12:
                self.page.mouse.wheel(0, -self.rng.uniform(120, 420))
            elif r < 0.25:
                for _ in range(self.rng.randint(2, 4)):          # cuộn nhanh vài nấc như lướt qua
                    self.page.mouse.wheel(0, self.rng.uniform(90, 200))
                    time.sleep(self.rng.uniform(0.05, 0.15) / max(0.3, self.toc_do))
            else:
                self.page.mouse.wheel(0, self.rng.uniform(220, 650))
            con = han - time.monotonic()
            if con <= 0:
                break
            time.sleep(min(con, self.rng.uniform(1.2, 5.5) / max(0.3, self.toc_do)))

    def luot(self, lan: int = 2) -> None:
        """Cuộn xem trang một chút như người đang đọc."""
        for _ in range(lan):
            self.page.mouse.wheel(0, self.rng.uniform(180, 520))
            self.nghi(0.6, 1.8)
        if self.rng.random() < 0.5:
            self.page.mouse.wheel(0, -self.rng.uniform(100, 300))
            self.nghi(0.4, 1.0)
