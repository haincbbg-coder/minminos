"""Tiện ích Facebook dùng chung cho các kỹ năng fb_* (tìm nút, đọc bài, cảm xúc, bình luận, chia sẻ).

Nguyên tắc (KIEN-TRUC.md 4.2):
  - chọn phần tử theo VAI TRÒ + NHÃN trợ năng, cả tiếng Việt và tiếng Anh, nhiều phương án dự phòng,
    chờ có hạn giờ; không dựa vào class CSS;
  - mọi cú bấm/phím CÔNG KHAI đi qua `bam_cong_khai` / `phim_cong_khai`, hai hàm này hỏi
    `nc.duoc_bam_cong_khai()` trước (chạy thử → không bấm);
  - chỉ báo thành công khi đọc lại trang thấy trạng thái đã đổi.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from typing import Iterable, List, Optional

from ngu_canh import LoiKyNang

HE_SO_CHO = 1.0          # test hạ xuống để không phải chờ đủ hạn khi phần tử vắng mặt
FB = "https://www.facebook.com"


def ms(x: float) -> int:
    return max(200, int(x * HE_SO_CHO))


def re_nhan(*nhan: str, chinh_xac: bool = True):
    tho = "|".join(re.escape(n) for n in nhan if n)
    return re.compile(f"^\\s*({tho})\\s*$" if chinh_xac else f"({tho})", re.I)


def dau_tien_thay(cands: Iterable, timeout_ms: int = 10000):
    """Locator đầu tiên (trong danh sách phương án) đang hiện, chờ tối đa timeout."""
    cands = list(cands)
    han = time.monotonic() + ms(timeout_ms) / 1000
    while True:
        for loc in cands:
            try:
                n = loc.count()
                for i in range(min(n, 6)):
                    if loc.nth(i).is_visible():
                        return loc.nth(i)
            except Exception:
                pass
        if time.monotonic() >= han:
            return None
        time.sleep(0.3)


def tim_nut(pham_vi, nhan: List[str], timeout_ms: int = 8000, chinh_xac: bool = True, vai=("button",)):
    """Tìm nút theo danh sách nhãn: role+name, rồi aria-label, rồi chữ hiển thị."""
    rx = re_nhan(*nhan, chinh_xac=chinh_xac)
    cands = [pham_vi.get_by_role(v, name=rx) for v in vai]
    if chinh_xac:
        cands += [pham_vi.locator(f"[aria-label=\"{n}\"]") for n in nhan]
    else:
        cands += [pham_vi.locator(f"[aria-label*=\"{n}\" i]") for n in nhan]
    cands.append(pham_vi.locator("[role='button'], button, a").filter(has_text=rx))
    return dau_tien_thay(cands, timeout_ms)


def bam_cong_khai(nc, loc, mo_ta: str, hanh_dong: str = "") -> bool:
    """Bấm một nút làm thay đổi thứ người khác thấy. Chạy thử → không bấm, trả False."""
    if not nc.duoc_bam_cong_khai(mo_ta, hanh_dong):
        return False
    nc.tay.bam(loc)
    return True


def phim_cong_khai(nc, ten: str, mo_ta: str, hanh_dong: str = "") -> bool:
    if not nc.duoc_bam_cong_khai(mo_ta, hanh_dong):
        return False
    nc.tay.phim(ten)
    return True


def mo_va_kiem(nc, url: str) -> None:
    nc.nhat_ky(f"Mở {url}")
    nc.mo(url)
    nc.tay.nghi(2.0, 4.5)
    nc.kiem_dang_nhap()


# ---------------------------------------------------------------------------- link
LINK_BAI = re.compile(r"/posts/|/permalink/|story_fbid=|/videos/|/reel/|/watch/?\?v=|multi_permalinks=|"
                      r"/share/p/|/share/v/|/photo/?\?fbid=|/photos/", re.I)
_GIU_Q = ("story_fbid", "id", "fbid", "v", "multi_permalinks")


def chuan_link(href: str) -> str:
    """Link tuyệt đối gọn: bỏ tham số theo dõi (__cft__, __tn__...), giữ tham số định danh bài."""
    if not href:
        return ""
    href = urllib.parse.urljoin(FB + "/", href.strip())
    p = urllib.parse.urlsplit(href)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if k in _GIU_Q]
    host = p.netloc.lower().replace("m.facebook.com", "www.facebook.com").replace("web.facebook.com", "www.facebook.com")
    if host == "facebook.com":
        host = "www.facebook.com"
    duong = re.sub(r"/+$", "", p.path) or "/"
    return urllib.parse.urlunsplit(("https", host, duong, urllib.parse.urlencode(q), ""))


def la_link_bai(href: str) -> bool:
    return bool(href) and bool(LINK_BAI.search(href)) and "comment_id=" not in href.split("?")[0]


def link_bai(pham_vi) -> str:
    """Link của một bài trong feed/nhóm. Facebook chỉ điền href thật cho link giờ đăng khi chuột rê
    qua, nên nếu chưa thấy thì rê qua các link ngắn đầu bài rồi đọc lại."""
    def doc() -> str:
        try:
            hrefs = pham_vi.locator("a[href]").evaluate_all("els => els.slice(0, 60).map(e => e.href)")
        except Exception:
            hrefs = []
        for h in hrefs:
            if la_link_bai(h):
                return chuan_link(h)
        return ""

    l = doc()
    if l:
        return l
    try:
        ung_vien = pham_vi.locator("a[role='link'][href='#'], a[href*='__cft__'], span > a[role='link']")
        for i in range(min(ung_vien.count(), 4)):
            try:
                ung_vien.nth(i).hover(timeout=ms(2500))
                time.sleep(0.4)
            except Exception:
                continue
            l = doc()
            if l:
                return l
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------- đọc bài
_BAI_FEED = "div[aria-posinset]"
_BAI_ARTICLE = ("div[role='article']:not([aria-label*='Bình luận']):not([aria-label*='Comment'])"
                ":not([aria-label*='Phản hồi']):not([aria-label*='Reply'])")
_BL_ARTICLE = ("[role='article'][aria-label*='Bình luận'], [role='article'][aria-label*='Comment'], "
               "[role='article'][aria-label*='Phản hồi'], [role='article'][aria-label*='Reply']")


def ds_bai(page) -> list:
    """Các bài đang có trong DOM của bảng tin / nhóm (locator từng bài)."""
    for sel in (_BAI_FEED, _BAI_ARTICLE):
        loc = page.locator(sel)
        try:
            n = loc.count()
        except Exception:
            n = 0
        if n:
            return [loc.nth(i) for i in range(n)]
    return []


def pham_vi_bai(page):
    """Phạm vi của bài đang mở theo link: hộp thoại bài (nếu Facebook mở dạng popup), bài đầu tiên,
    rồi vùng chính của trang."""
    hop = page.get_by_role("dialog").filter(has=page.locator("[role='article'], [contenteditable='true']"))
    for loc in (hop, page.locator(_BAI_FEED), page.locator(_BAI_ARTICLE), page.locator("[role='main']")):
        try:
            if loc.count() and loc.first.is_visible():
                return loc.first
        except Exception:
            pass
    return page.locator("body")


def mo_rong_bai(nc, pham_vi) -> None:
    nut = tim_nut(pham_vi, ["Xem thêm", "See more"], 1200)
    if nut:
        try:
            nc.tay.bam(nut)
            nc.tay.nghi(0.4, 1.0)
        except Exception:
            pass


def doc_bai(pham_vi, toi_da_bl: int = 8) -> dict:
    """{chu, tac_gia, link, binh_luan:[...]} của một bài."""
    chu = ""
    for sel in ("[data-ad-preview='message']", "[data-ad-comet-preview='message']",
                "div[dir='auto'][style*='text-align']"):
        try:
            loc = pham_vi.locator(sel)
            if loc.count():
                chu = "\n".join(t.strip() for t in loc.all_inner_texts() if t.strip())
                if chu:
                    break
        except Exception:
            pass
    if not chu:
        try:
            chu = pham_vi.inner_text(timeout=ms(5000))
        except Exception:
            chu = ""
    tac_gia = ""
    for sel in ("h2", "h3", "h4", "strong"):
        try:
            loc = pham_vi.locator(sel)
            if loc.count():
                tac_gia = loc.first.inner_text(timeout=ms(2000)).strip().splitlines()[0][:80]
                if tac_gia:
                    break
        except Exception:
            pass
    bl = []
    try:
        loc = pham_vi.locator(_BL_ARTICLE)
        for i in range(min(loc.count(), toi_da_bl)):
            t = loc.nth(i).inner_text(timeout=ms(2000)).strip()
            if t:
                bl.append(re.sub(r"\s+", " ", t)[:300])
    except Exception:
        pass
    return {"chu": chu.strip()[:3000], "tac_gia": tac_gia, "link": link_bai(pham_vi), "binh_luan": bl}


def chup_jpeg(loc) -> bytes:
    try:
        return loc.screenshot(type="jpeg", quality=60, timeout=ms(10000))
    except Exception:
        return b""


def thay_chu(pham_vi, chu: str, timeout_ms: int = 15000) -> bool:
    dau = re.sub(r"\s+", " ", (chu or "").strip())[:40]
    if not dau:
        return False
    try:
        pham_vi.get_by_text(dau, exact=False).first.wait_for(state="visible", timeout=ms(timeout_ms))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------- cảm xúc
_THICH_CHUA = ["Thích", "Like"]
_THICH_DA = re.compile(r"^\s*(Gỡ |Remove |Bỏ thích|Unlike|Thay đổi cảm xúc|Change .*reaction)", re.I)
CAM_XUC = {
    "thich": ["Thích", "Like"],
    "yeu_thich": ["Yêu thích", "Love"],
    "thuong_thuong": ["Thương thương", "Care"],
    "haha": ["Haha"],
    "wow": ["Wow"],
}


def da_tha_cam_xuc(pham_vi) -> bool:
    try:
        loc = pham_vi.get_by_role("button", name=_THICH_DA)
        return loc.count() > 0 and loc.first.is_visible()
    except Exception:
        return False


def tha_cam_xuc(nc, pham_vi, cam_xuc: str = "thich") -> str:
    """Thả cảm xúc lên bài. Trả 'thanh_cong' | 'da_co' | 'chay_thu' | 'khong_thay' | 'khong_doi'."""
    if cam_xuc == "ngau_nhien":
        cam_xuc = nc.rng.choice(["thich", "thich", "yeu_thich", "yeu_thich", "thuong_thuong", "haha", "wow"])
    if da_tha_cam_xuc(pham_vi):
        return "da_co"
    nut = tim_nut(pham_vi, _THICH_CHUA, 6000)
    if not nut:
        return "khong_thay"
    ten = {"thich": "Thích", "yeu_thich": "Yêu thích", "thuong_thuong": "Thương thương"}.get(cam_xuc, cam_xuc)
    if not nc.duoc_bam_cong_khai(f"thả cảm xúc '{ten}'", "thich"):
        return "chay_thu"
    if cam_xuc == "thich":
        nc.tay.bam(nut)
    else:
        # Rê và giữ chuột trên nút Thích để bảng cảm xúc hiện ra, rồi chọn đúng cảm xúc.
        nc.tay.re_chuot(nut, 1.8)
        trang = nut.page
        bang = [trang.locator("[role='toolbar']"), trang.locator("[aria-label='Cảm xúc'], [aria-label='Reactions']"),
                trang.locator("[role='dialog']")]
        rx = re_nhan(*CAM_XUC.get(cam_xuc, ["Thích", "Like"]))
        chon = dau_tien_thay([b.get_by_role("button", name=rx) for b in bang]
                             + [b.locator("[aria-label]").filter(has_text=rx) for b in bang]
                             + [trang.locator("div[aria-label]").filter(has=trang.get_by_role("button", name=rx))
                                .get_by_role("button", name=rx)], 4000)
        if not chon:
            nc.nhat_ky(f"Không hiện bảng cảm xúc, thả Thích thay cho '{ten}'")
            chon = nut
        nc.tay.bam(chon)
    nc.tay.nghi(1.2, 2.5)
    han = time.monotonic() + ms(6000) / 1000
    while time.monotonic() < han:
        if da_tha_cam_xuc(pham_vi):
            return "thanh_cong"
        time.sleep(0.4)
    return "khong_doi"


# ---------------------------------------------------------------------------- bình luận
_O_BL = re.compile(r"(Viết bình luận|Write a (public )?comment|Bình luận dưới tên|Comment as|"
                   r"Viết câu trả lời|Write a (public )?reply|Trả lời|Reply to|Phản hồi)", re.I)
_MO_BL = ["Bình luận", "Comment", "Viết bình luận", "Leave a comment"]


def o_binh_luan(pham_vi, timeout_ms: int = 8000):
    return dau_tien_thay([pham_vi.get_by_role("textbox", name=_O_BL),
                          pham_vi.locator("[contenteditable='true'][role='textbox']")], timeout_ms)


def _go_va_gui(nc, o, noi_dung: str, hanh_dong: str, mo_ta: str, pham_vi_kiem) -> str:
    if not nc.duoc_bam_cong_khai(mo_ta, hanh_dong):
        return "chay_thu"
    nc.tay.bam(o)
    nc.tay.nghi(0.5, 1.2)
    nc.tay.go_binh_luan(noi_dung)
    nc.tay.nghi(1.0, 2.5)          # đọc lại trước khi gửi
    nc.tay.phim("Enter")
    # Gửi xong thì ô soạn trống lại và chữ hiện trong danh sách bình luận.
    han = time.monotonic() + ms(15000) / 1000
    trong = False
    while time.monotonic() < han:
        try:
            if not (o.inner_text(timeout=1000) or "").strip():
                trong = True
                break
        except Exception:
            trong = True
            break
        time.sleep(0.5)
    if trong and thay_chu(pham_vi_kiem, noi_dung, 12000):
        return "thanh_cong"
    return "khong_hien"


def binh_luan(nc, pham_vi, noi_dung: str, hanh_dong: str = "binh_luan", mo_ta: str = "") -> str:
    """Bình luận dưới bài. Trả 'thanh_cong' | 'chay_thu' | 'khong_thay' | 'khong_hien'."""
    o = o_binh_luan(pham_vi, 3000)
    if not o:
        nut = tim_nut(pham_vi, _MO_BL, 5000)
        if nut and not nc.chay_thu:
            nc.tay.bam(nut)            # chỉ mở ô bình luận, chưa gửi gì
            nc.tay.nghi(0.8, 1.8)
        o = o_binh_luan(pham_vi, 6000) or o_binh_luan(nut.page if nut else pham_vi, 3000)
    if not o:
        if nc.chay_thu:
            nc.duoc_bam_cong_khai(mo_ta or f"bình luận: {noi_dung[:80]}", hanh_dong)
            return "chay_thu"
        return "khong_thay"
    return _go_va_gui(nc, o, noi_dung, hanh_dong, mo_ta or f"bình luận: {noi_dung[:80]}", pham_vi)


def ds_binh_luan(pham_vi) -> list:
    loc = pham_vi.locator(_BL_ARTICLE)
    try:
        return [loc.nth(i) for i in range(loc.count())]
    except Exception:
        return []


def tra_loi_binh_luan(nc, bl, noi_dung: str, hanh_dong: str = "tra_loi_binh_luan", mo_ta: str = "") -> str:
    """Trả lời một bình luận (locator article của bình luận đó)."""
    mo_ta = mo_ta or f"trả lời bình luận: {noi_dung[:80]}"
    nut = tim_nut(bl, ["Phản hồi", "Trả lời", "Reply"], 5000)
    if not nut:
        return "khong_thay"
    if nc.chay_thu:
        nc.duoc_bam_cong_khai(mo_ta, hanh_dong)
        return "chay_thu"
    nc.tay.bam(nut)                     # mở ô trả lời (chưa gửi gì)
    nc.tay.nghi(0.8, 1.6)
    trang = bl.page
    o = dau_tien_thay([trang.get_by_role("textbox", name=re.compile(r"(Trả lời|Reply|Phản hồi|Viết câu trả lời|"
                                                                     r"Write a reply)", re.I)),
                       trang.locator("[contenteditable='true'][role='textbox']:focus")], 6000)
    if not o:
        return "khong_thay"
    return _go_va_gui(nc, o, noi_dung, hanh_dong, mo_ta, trang.locator("body"))


# ---------------------------------------------------------------------------- chia sẻ
_NUT_CHIA_SE = ["Chia sẻ", "Share", "Gửi nội dung này cho bạn bè hoặc đăng lên trang cá nhân của bạn.",
                "Send this to friends or post it on your profile."]
_CHIA_SE_NGAY = re.compile(r"^\s*(Chia sẻ ngay|Share now)", re.I)
_DA_CHIA_SE = re.compile(r"(Đã chia sẻ|đã được chia sẻ|Shared to your|Shared|Đã đăng)", re.I)


def chia_se(nc, pham_vi) -> str:
    """Chia sẻ bài lên tường (Chia sẻ ngay). Trả 'thanh_cong' | 'chay_thu' | 'khong_thay' | 'khong_chac'."""
    nut = tim_nut(pham_vi, _NUT_CHIA_SE, 6000)
    if not nut:
        return "khong_thay"
    if not nc.duoc_bam_cong_khai("chia sẻ bài lên tường", "chia_se"):
        return "chay_thu"
    nc.tay.bam(nut)                     # mở menu chia sẻ
    nc.tay.nghi(1.2, 2.5)
    trang = nut.page
    ngay = dau_tien_thay([trang.get_by_role("menuitem", name=_CHIA_SE_NGAY),
                          trang.get_by_role("button", name=_CHIA_SE_NGAY),
                          trang.get_by_role("dialog").get_by_role("button", name=re_nhan("Chia sẻ", "Share",
                                                                                          "Chia sẻ ngay", "Share now")),
                          trang.get_by_text(_CHIA_SE_NGAY)], 8000)
    if not ngay:
        try:
            nc.tay.phim("Escape")
        except Exception:
            pass
        return "khong_thay"
    nc.tay.bam(ngay)
    try:
        trang.get_by_text(_DA_CHIA_SE).first.wait_for(state="visible", timeout=ms(10000))
        return "thanh_cong"
    except Exception:
        return "khong_chac"


# ---------------------------------------------------------------------------- nhóm
_THAM_GIA = ["Tham gia nhóm", "Join group", "Tham gia", "Join"]
_DA_VAO = re.compile(r"^\s*(Đã tham gia|Joined|Thành viên|Member)\s*$", re.I)
_CHO_DUYET_VAO = re.compile(r"^\s*(Đã yêu cầu|Requested|Hủy yêu cầu|Huỷ yêu cầu|Cancel request|"
                            r"Đang chờ duyệt|Pending)\s*$", re.I)
_SOAN_NHOM = re.compile(r"(Bạn viết gì đi|Write something|Tạo bài viết công khai|Create a public post)", re.I)


def trang_thai_nhom(page) -> str:
    """'da_vao' | 'cho_duyet' | 'chua_vao' | 'khong_ro' theo nút và ô soạn trên trang nhóm."""
    for vai in ("button", "link"):
        try:
            if page.get_by_role(vai, name=_DA_VAO).count():
                return "da_vao"
            if page.get_by_role(vai, name=_CHO_DUYET_VAO).count():
                return "cho_duyet"
        except Exception:
            pass
    try:
        if page.get_by_role("button", name=_SOAN_NHOM).count() or page.get_by_text(_SOAN_NHOM).count():
            return "da_vao"
    except Exception:
        pass
    try:
        if page.get_by_role("button", name=re_nhan(*_THAM_GIA)).count():
            return "chua_vao"
    except Exception:
        pass
    return "khong_ro"


def ten_trang(page) -> str:
    try:
        h = page.locator("h1")
        if h.count():
            return h.first.inner_text(timeout=ms(2000)).strip().splitlines()[0][:120]
    except Exception:
        pass
    try:
        return (page.title() or "").replace("| Facebook", "").strip()[:120]
    except Exception:
        return ""


def link_nhom_moi(link: str) -> str:
    """Link nhóm sắp xếp bài mới nhất."""
    p = urllib.parse.urlsplit(chuan_link(link))
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path + "/", "sorting_setting=CHRONOLOGICAL", ""))


def doc_bai_nhom(nc, so_bai: int, phut_toi_da: float = 6.0) -> list:
    """Cuộn trang nhóm, đọc tối đa `so_bai` bài khác nhau: [{bai, loc, anh}]."""
    page = nc.page
    thay: dict = {}
    han = time.monotonic() + phut_toi_da * 60 / max(1.0, nc.toc_do)
    lan_khong_moi = 0
    while len(thay) < so_bai and time.monotonic() < han and lan_khong_moi < 4:
        moi = 0
        for loc in ds_bai(page):
            if len(thay) >= so_bai:
                break
            try:
                if not loc.is_visible():
                    continue
                loc.scroll_into_view_if_needed(timeout=ms(5000))
            except Exception:
                continue
            mo_rong_bai(nc, loc)
            bai = doc_bai(loc)
            khoa = bai["link"] or bai["chu"][:120]
            if not khoa or khoa in thay or len(bai["chu"]) < 3:
                continue
            thay[khoa] = {"bai": bai, "loc": loc, "anh": chup_jpeg(loc)}
            moi += 1
            nc.tay.nghi(1.0, 3.0)        # đọc bài như người
        lan_khong_moi = 0 if moi else lan_khong_moi + 1
        nc.tay.luot(2)
    return list(thay.values())


def phai_dung(nc) -> bool:
    if nc.nen_dung():
        nc.nhat_ky("Dừng: đợt bị huỷ hoặc đã hết hạn mức hôm nay")
        return True
    return False


def bao_loi_cung(nc, e: Exception) -> None:
    """LoiKyNang có mã dừng ngay (đăng xuất, checkpoint...) thì ném tiếp; lỗi khác để vòng gọi xử lý."""
    if isinstance(e, LoiKyNang) and e.ma:
        raise e
