"""Kỹ năng YouTube (26.10.229): đăng video từ kho / nháp AI qua YouTube Studio, nuôi nick, tương tác theo
link, tự trả lời bình luận (AI), bình luận + ghim link tiếp thị, quét ra bảng CSV, dang_ban_nhap:youtube.

Luồng Studio: youtube.com/upload -> studio.youtube.com (hộp 'Tải video lên') -> chọn tệp -> Chi tiết
(tiêu đề <= 100 ký tự, mô tả <= 5000, 'Không dành cho trẻ em', tuỳ chọn: Hiện thêm -> quảng cáo trả phí,
gắn sản phẩm YouTube Shopping) -> Tiếp x3 -> Chế độ hiển thị -> Xuất bản/Lưu. Bị đẩy sang
accounts.google.com -> lỗi đăng xuất. Thành công chỉ khi hộp 'Đã xuất bản video' hiện.

Trang xem: mọi link (kể cả /shorts/ID, youtu.be/ID, &pp=...) được chuẩn về /watch?v=ID để dùng một bộ
chọn phần tử: like-button-view-model button[aria-pressed], #owner #subscribe-button, ytd-comments
(#placeholder-area -> #contenteditable-root -> #submit-button), ytd-comment-thread-renderer (#author-text,
#content-text, #reply-button-end, #action-menu). Bình luận YouTube: Enter là xuống dòng, gửi bằng nút.
Mọi cú bấm công khai (Thích, Đăng ký, Bình luận, Phản hồi, Ghim, Xuất bản) đi qua w.bam_cong_khai.
"""
from __future__ import annotations

import random
import re
import time
import urllib.parse

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "youtube"
GOC = "https://www.youtube.com"
URL_TAI_LEN = "https://www.youtube.com/upload"
URL_STUDIO = "https://studio.youtube.com/"
GIOI_HAN_BL = 10000
HIEN = {
    "cong_khai": ["Công khai", "Public"],
    "khong_cong_khai": ["Không công khai", "Unlisted"],
    "rieng_tu": ["Riêng tư", "Private"],
}
_RE_ID = re.compile(r"(?:(?:youtube\.com)?/(?:shorts|live|embed)/|youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])")
_RE_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)


def _dang_xuat(nc) -> None:
    if "accounts.google.com" in (nc.page.url or ""):
        raise LoiKyNang("YouTube đẩy sang trang đăng nhập Google: nick đã đăng xuất", "dang_xuat")


def _mo(nc, url: str) -> None:
    nc.mo(url)
    nc.tay.nghi(2.5, 4.5)
    _dang_xuat(nc)
    w.kiem_chan(nc)


# --------------------------------------------------------------------------- chữ (hàm thuần)

def chuan_link(link: str):
    """-> (https://www.youtube.com/watch?v=ID, ID). Link không nhận ra ID thì trả nguyên link, ID rỗng."""
    m = _RE_ID.search(str(link or ""))
    if not m:
        return str(link or "").strip(), ""
    return f"{GOC}/watch?v={m.group(1)}", m.group(1)


def spin(mau: str, rng=None) -> str:
    """`{a|b|{c|d}}` lồng nhau, chọn ngẫu nhiên. Ngoặc không đóng thì giữ nguyên chữ."""
    rng = rng or random
    s = str(mau or "")
    for _ in range(50):
        m = re.search(r"\{([^{}]*\|[^{}]*)\}", s)       # nhóm trong cùng có '|'
        if not m:
            break
        s = s[:m.start()] + rng.choice(m.group(1).split("|")) + s[m.end():]
    return s


def tach_tieu_de(bai: dict):
    """-> (tiêu đề <= 100 ký tự, mô tả). Có trường tieu_de thì dùng; không thì dòng đầu là tiêu đề, phần
    còn lại là mô tả. YouTube không nhận '<' '>' trong tiêu đề và mô tả."""
    nd = str(bai.get("noi_dung") or "").strip()
    td = str(bai.get("tieu_de") or "").strip()
    if td:
        mo_ta = nd[len(td):].strip() if nd.startswith(td) else nd
    else:
        dong = nd.splitlines()
        td = dong[0].strip() if dong else ""
        mo_ta = "\n".join(dong[1:]).strip()
    td = re.sub(r"\s+", " ", td.replace("<", "").replace(">", "")).strip()
    mo_ta = mo_ta.replace("<", "").replace(">", "")
    return w.cat_gioi_han(td or "Video mới", 100), mo_ta


def them_link_tiep_thi(mo_ta: str, link_tiep_thi) -> str:
    """Nối các dòng link tiếp thị vào cuối mô tả (dòng chỉ là link thì thêm 'Mua tại: '). Tổng <= 5000."""
    dong = []
    for x in w.ds_dong(link_tiep_thi):
        dong.append(f"Mua tại: {x}" if _RE_URL.fullmatch(x) else x)
    khoi = "\n".join(dong)
    mo_ta = str(mo_ta or "").strip()
    if not khoi:
        return mo_ta[:5000]
    cho = 5000 - len(khoi) - 2
    return ((mo_ta[:max(0, cho)].rstrip() + "\n\n") if mo_ta and cho > 0 else "") + khoi


def mau_nhan_dien(text: str) -> str:
    """Đoạn chữ dùng để tìm lại bình luận vừa gửi: bỏ link (YouTube có thể rút gọn link hiển thị)."""
    return w.doan_nhan_dien(_RE_URL.sub(" ", str(text or "")))


def so_luot_xem(s: str) -> int:
    """'973 N lượt xem' -> 973000, '1,2 Tr lượt xem' -> 1200000, '1.234 lượt xem' -> 1234,
    '1.2M views' -> 1200000. Không đọc được -> 0."""
    s = str(s or "").strip()
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(N|K|Tr|M|Tỷ|B)?\b", s, re.I)
    if not m:
        return 0
    so, dv = m.group(1), (m.group(2) or "").lower()
    if dv:
        so = so.replace(",", ".")
        if so.count(".") > 1:
            so = so.replace(".", "")
        try:
            v = float(so)
        except ValueError:
            return 0
        return int(round(v * {"n": 1e3, "k": 1e3, "tr": 1e6, "m": 1e6, "tỷ": 1e9, "b": 1e9}[dv]))
    try:
        return int(re.sub(r"[.,]", "", so))
    except ValueError:
        return 0


def _tuy_chon(ts: dict) -> dict:
    ts = ts or {}
    return {"link_tiep_thi": ts.get("link_tiep_thi") or "", "gan_san_pham": str(ts.get("gan_san_pham") or "").strip(),
            "quang_cao_tra_phi": bool(ts.get("quang_cao_tra_phi")) and str(ts.get("quang_cao_tra_phi")).lower()
            not in ("0", "false", "off", "no")}


# --------------------------------------------------------------------------- Studio: đăng video

def _link_video(page) -> str:
    try:
        a = page.locator("a[href*='youtu.be/'], a[href*='youtube.com/shorts/'], a[href*='/watch?v=']")
        for i in range(min(a.count(), 5)):
            h = a.nth(i).get_attribute("href") or ""
            if h:
                return h
    except Exception:
        pass
    return ""


def _hien_them(nc) -> None:
    nut = w.tim(nc.page, ten=["Hiện thêm", "Hiển thị thêm", "Show more"], chua=True,
                css=["ytcp-video-metadata-editor #toggle-button", "#toggle-button"], timeout_ms=5000)
    if nut and w.re_chua("Hiện thêm", "Hiển thị thêm", "Show more").search(nut.inner_text() or ""):
        nc.nhat_ky("Studio: bấm 'Hiện thêm' để mở phần cài đặt nâng cao")
        nc.tay.bam(nut)
        nc.tay.nghi(1.0, 2.0)
    elif not nut:
        nc.nhat_ky("Studio: không thấy nút 'Hiện thêm' (có thể đã mở sẵn)")


def _dat_quang_cao(nc) -> bool:
    """Tích 'Video của tôi có quảng cáo trả phí...'. Không công khai (chỉ là ô trong form)."""
    page = nc.page
    o = w.tim(page, role="checkbox", ten=["quảng cáo trả phí", "paid promotion"], chua=True,
              css=["#paid-promotion-section [role='checkbox']", "ytcp-checkbox-lit#has-ppp", "#has-ppp"],
              timeout_ms=6000)
    if not o:
        nhan = w.tim(page, role="none", chu=["quảng cáo trả phí", "paid promotion"], chua=True, timeout_ms=2000)
        if not nhan:
            nc.nhat_ky("Studio: không thấy ô 'quảng cáo trả phí', bỏ qua bước này")
            return False
        o = nhan
    if (o.get_attribute("aria-checked") or "") == "true":
        nc.nhat_ky("Studio: ô 'quảng cáo trả phí' đã tích sẵn")
        return True
    nc.tay.bam(o)
    nc.tay.nghi(0.8, 1.5)
    ok = w.cho(lambda: (o.get_attribute("aria-checked") or "") == "true", 4)
    nc.nhat_ky("Studio: đã tích 'Nội dung có quảng cáo trả phí'" if ok else
               f"Studio: đã bấm ô quảng cáo trả phí nhưng đọc lại chưa thấy tích ({w.doc_trang_thai(o)[:60]})")
    return ok


def _gan_san_pham(nc, ten_sp: str) -> bool:
    """Gắn sản phẩm YouTube Shopping ở bước Chi tiết. Kênh chưa bật Shopping thì ghi nhật ký, trả False."""
    page = nc.page
    nut = w.tim(page, ten=["Thêm sản phẩm", "Add products", "Gắn thẻ sản phẩm", "Tag products", "Chỉnh sửa sản phẩm",
                           "Edit products"], chua=True,
                css=["#product-tagging-section ytcp-button", "ytcp-product-tagging-section ytcp-button",
                     "#products-section ytcp-button"], timeout_ms=5000)
    if not nut:
        nc.nhat_ky("Studio không có mục 'Thêm sản phẩm': kênh chưa bật YouTube Shopping, đăng không gắn sản phẩm")
        return False
    nc.nhat_ky(f"Studio: mở hộp gắn sản phẩm, tìm '{ten_sp[:60]}'")
    nc.tay.bam(nut)
    nc.tay.nghi(1.5, 3.0)
    hop = w.dau_tien_thay([page.locator("tp-yt-paper-dialog:visible").last, page.locator("ytcp-dialog:visible").last,
                           page.get_by_role("dialog").last], 10000) or page
    o = w.tim(hop, role="textbox", ten=["Tìm kiếm", "Search", "Tìm sản phẩm", "Search products"], chua=True,
              css=["input[type='search']", "input#search-input", "input"], timeout_ms=6000) or \
        w.tim(hop, role="searchbox", ten=["Tìm", "Search"], chua=True, timeout_ms=1500)
    if o:
        w.go_vao(nc, o, ten_sp[:80], xoa_truoc=True)
        nc.tay.nghi(2.0, 3.5)
    else:
        nc.nhat_ky("Hộp sản phẩm không có ô tìm kiếm, chọn theo tên trong danh sách")
    muc = w.dau_tien_thay([hop.get_by_role("checkbox", name=w.re_chua(ten_sp[:40])),
                           hop.get_by_role("option", name=w.re_chua(ten_sp[:40])),
                           hop.get_by_text(w.re_chua(ten_sp[:40]))], 8000)
    if not muc:
        nc.nhat_ky(f"Không thấy sản phẩm '{ten_sp[:60]}' trong YouTube Shopping của kênh, đăng không gắn sản phẩm")
        page.keyboard.press("Escape")
        nc.tay.nghi(0.8, 1.5)
        return False
    nc.tay.bam(muc)
    nc.tay.nghi(0.8, 1.6)
    xong = w.tim(hop, ten=["Lưu", "Save", "Xong", "Done", "Tiếp tục", "Continue", "Thêm", "Add"],
                 css=["#save-button", "#done-button"], timeout_ms=5000)
    if xong:
        nc.tay.bam(xong)            # nút trong hộp gắn sản phẩm, chưa công khai gì
        nc.tay.nghi(1.5, 2.5)
    ok = w.co_chu(page, ten_sp[:30])
    nc.nhat_ky(f"Studio: {'đã gắn' if ok else 'đã chọn nhưng chưa đọc lại thấy'} sản phẩm '{ten_sp[:60]}'")
    return ok


def _dang_video(nc, bai: dict, tt: w.TrangThaiDang, tuy_chon: dict = None) -> str:
    page = nc.page
    to = tuy_chon if tuy_chon is not None else _tuy_chon(nc.ts)
    tep = w.loc_tep(bai.get("tep_cuc_bo") or [], w.DUOI_VIDEO)
    if not tep:
        raise w.LoiDang("bài không có video", False)
    tieu_de, mo_ta = tach_tieu_de(bai)
    mo_ta = them_link_tiep_thi(mo_ta, to.get("link_tiep_thi"))
    nc.mo(URL_TAI_LEN)
    nc.tay.nghi(3.0, 5.0)
    _dang_xuat(nc)
    w.kiem_chan(nc)
    o_tep = page.locator("input[type='file']")
    if not w.cho(lambda: o_tep.count() > 0, 30):
        # Studio mở mà chưa có hộp tải lên: Tạo -> Tải video lên
        tao = w.tim(page, ten=["Tạo", "Create"], nhan=["Tạo", "Create"], timeout_ms=8000)
        if tao:
            nc.tay.bam(tao)
            nc.tay.nghi(0.8, 1.6)
            muc = w.tim(page, role="menuitem", ten=["Tải video lên", "Upload videos"], chua=True, timeout_ms=5000)
            if muc:
                nc.tay.bam(muc)
        if not w.cho(lambda: o_tep.count() > 0, 20):
            raise w.LoiDang("không mở được hộp Tải video lên của YouTube Studio", False)
    nc.nhat_ky(f"Chọn tệp video {str(tep[0]).replace(chr(92), '/').split('/')[-1]}")
    o_tep.first.set_input_files(tep[0])
    o_td = w.dau_tien_thay(w.ung_vien(page, role="textbox", ten=["Thêm tiêu đề", "Add a title", "Tiêu đề",
                                                                 "Title"], chua=True,
                                      css=["#title-textarea [contenteditable='true']", "#title-textarea #textbox"]),
                           120000)
    if not o_td:
        _dang_xuat(nc)
        raise w.LoiDang("không hiện ô tiêu đề sau khi chọn video", False)
    nc.nhat_ky(f"Gõ tiêu đề ({len(tieu_de)} ký tự): {tieu_de[:60]}")
    w.go_vao(nc, o_td, tieu_de.replace("\n", " "), xoa_truoc=True)
    if mo_ta:
        o_mt = w.tim(page, role="textbox", ten=["Cho người xem biết", "Tell viewers", "Mô tả", "Description"],
                     chua=True, css=["#description-textarea [contenteditable='true']"], timeout_ms=8000)
        if o_mt:
            nc.nhat_ky(f"Gõ mô tả ({len(mo_ta)} ký tự)")
            w.go_vao(nc, o_mt, mo_ta[:5000])
        else:
            nc.nhat_ky("Không thấy ô mô tả trong Studio, đăng chỉ có tiêu đề")
    tre = w.tim(page, role="radio", ten=["Không, nội dung này không dành cho trẻ em", "No, it's not made for kids",
                                         "không dành cho trẻ em", "not made for kids"], chua=True, timeout_ms=8000)
    if tre:
        nc.tay.bam(tre)
    else:
        nc.nhat_ky("Không thấy lựa chọn 'không dành cho trẻ em' (có thể kênh đã đặt sẵn)")
    if to.get("gan_san_pham") or to.get("quang_cao_tra_phi"):
        _hien_them(nc)
        if to.get("gan_san_pham"):
            _gan_san_pham(nc, to["gan_san_pham"])
        if to.get("quang_cao_tra_phi"):
            _dat_quang_cao(nc)
    for _ in range(3):
        tiep = w.tim(page, ten=["Tiếp", "Next"], css=["#next-button"], timeout_ms=8000)
        if not tiep:
            break
        nc.tay.bam(tiep)
        nc.tay.nghi(1.2, 2.5)
    nhan = HIEN.get(str(nc.ts.get("che_do_hien") or "cong_khai"), HIEN["cong_khai"])
    r = w.tim(page, role="radio", ten=nhan, timeout_ms=10000)
    if not r:
        raise w.LoiDang(f"không thấy lựa chọn hiển thị '{nhan[0]}'", False)
    nc.tay.bam(r)
    nc.tay.nghi(1.0, 2.0)
    # Chờ tải lên xong rồi mới xuất bản (tránh xuất bản khi video còn dở)
    han = time.monotonic() + 30 * 60
    nc.nhat_ky("Chờ YouTube tải video xong")
    while time.monotonic() < han and not w.co_chu(page, "Tải lên hoàn tất", "Upload complete", "Đã tải lên",
                                                   "Checks complete", "Đã kiểm tra xong", "Processing",
                                                   "Đang xử lý", "Đã xử lý", "Processed"):
        _dang_xuat(nc)
        if nc.nen_dung():
            raise w.LoiDang("đợt bị huỷ khi đang tải video", False)
        time.sleep(4)
    nut = w.tim(page, ten=["Xuất bản", "Publish", "Lưu", "Save"], css=["#done-button"], timeout_ms=10000)
    if not nut or nut.get_attribute("aria-disabled") == "true":
        raise w.LoiDang("nút Xuất bản/Lưu không bấm được", False)
    link_som = _link_video(page)
    tt.da_bam = True
    if not w.bam_cong_khai(nc, nut, "Xuất bản video YouTube"):
        raise w.LoiDang("chạy thử", False)
    ok = w.cho(lambda: w.co_chu(page, "Đã xuất bản video", "Video published", "Video đã được xuất bản",
                                "Đã lưu video", "Video saved", "Đã lên lịch", "Video scheduled",
                                "Video đã được lưu"), 120, 1.5)
    _dang_xuat(nc)
    if not ok:
        raise w.LoiDang("đã bấm Xuất bản nhưng YouTube chưa báo đã xuất bản/đã lưu", True)
    link = _link_video(page) or link_som
    nc.nhat_ky(f"YouTube báo đã xuất bản: {link or '(chưa đọc được link)'}")
    dong = w.tim(page, ten=["Đóng", "Close"], timeout_ms=3000)
    if dong:
        nc.tay.bam(dong)
    return link


def _kiem_bai(bai: dict) -> str:
    if not w.loc_tep(bai.get("tep_cuc_bo") or [], w.DUOI_VIDEO):
        return "bài không có video"
    return ""


def yt_dang_video_kho(nc) -> str:
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    _dang_xuat(nc)
    return w.chay_kho(nc, "dang_video", nc.ts.get("so_bai", 1), "Đăng video YouTube",
                      lambda bai, tt: _dang_video(nc, bai, tt), kiem_bai=_kiem_bai)


def yt_dang_ai(nc) -> str:
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    _dang_xuat(nc)

    def _dang(bn):
        if not w.loc_tep(bn.get("tep_cuc_bo") or [], w.DUOI_VIDEO):
            raise LoiKyNang(f"nháp #{bn.get('id')} chưa có video kèm (YouTube bắt buộc có video), bỏ qua nháp này")
        nc.nhat_ky(f"Đăng nháp #{bn.get('id')}: dòng đầu là tiêu đề, phần còn lại là mô tả")
        return _dang_video(nc, {"noi_dung": bn.get("noi_dung"), "tep_cuc_bo": bn.get("tep_cuc_bo")},
                           w.TrangThaiDang())
    return w.dang_ai_da_duyet(nc, NT, "dang_video", int(nc.ts.get("so_bai", 1) or 1),
                              "Đăng video AI lên YouTube", _dang)


# --------------------------------------------------------------------------- trang xem: thích, đăng ký

def _nut_thich(page, timeout_ms=10000):
    css = ["ytd-watch-metadata like-button-view-model button", "#top-level-buttons-computed like-button-view-model button",
           "segmented-like-dislike-button-view-model like-button-view-model button",
           "ytd-reel-video-renderer[is-active] like-button-view-model button", "like-button-view-model button",
           "#segmented-like-button button", "#like-button button"]
    cands = [page.locator(c) for c in css]
    cands.append(page.get_by_role("button", name=re.compile(
        r"^(?!.*(dislike|không thích)).*(thích video này|like this video)", re.I)))
    return w.dau_tien_thay(cands, timeout_ms)


def _da_thich(loc) -> bool:
    return w.doc_trang_thai(loc).split(" | ")[0] == "true"


_JS_DA_DK = r"""e => !!(e.hasAttribute('subscribed') || e.querySelector('ytd-subscribe-button-renderer[subscribed]')
  || /(Đã đăng ký|Subscribed)/i.test(e.innerText || '')
  || e.querySelector('[aria-label^="Hủy đăng ký"], [aria-label^="Huỷ đăng ký"], [aria-label^="Unsubscribe"]'))"""


def _o_dang_ky(page, timeout_ms=8000):
    return w.dau_tien_thay([page.locator("ytd-watch-metadata #owner #subscribe-button"),
                            page.locator("#owner #subscribe-button"),
                            page.locator("ytd-reel-video-renderer[is-active] #subscribe-button"),
                            page.locator("#subscribe-button")], timeout_ms)


def _da_dang_ky(o) -> bool:
    try:
        return bool(o.evaluate(_JS_DA_DK))
    except Exception:
        return False


def _dang_ky(nc, dem, link: str) -> bool:
    o = _o_dang_ky(nc.page)
    if not o:
        w.bao(nc, dem, "theo_doi", "bo_qua", "không thấy nút Đăng ký (video của chính kênh nick?)", link=link)
        return False
    pin = w.ghim(o, "dk") or o
    nut = w.dau_tien_thay([o.locator("button").filter(has_text=w.re_nhan("Đăng ký", "Subscribe")),
                           o.get_by_role("button", name=w.re_chua("Đăng ký", "Subscribe")), o.locator("button")], 3000)
    if not nut:
        w.bao(nc, dem, "theo_doi", "loi", f"thấy khung Đăng ký nhưng không có nút ({(o.inner_text() or '')[:60]})",
              link=link)
        return False
    return w.bam_va_xac_nhan(nc, dem, "theo_doi", nut, lambda _l: _da_dang_ky(pin), "đăng ký kênh", link)


def _thich(nc, dem, link: str, mo_ta: str = "thích video") -> bool:
    nut = _nut_thich(nc.page)
    if not nut:
        w.bao(nc, dem, "thich", "loi", "không thấy nút Thích (like-button-view-model)", link=link)
        return False
    return w.bam_va_xac_nhan(nc, dem, "thich", nut, _da_thich, mo_ta, link)


def _doc_video(page) -> dict:
    td, mt = "", ""
    e = w.tim(page, css=["ytd-watch-metadata #title h1", "h1.ytd-watch-metadata", "#title h1"], timeout_ms=5000)
    if e:
        td = (e.inner_text() or "").strip()
    e = w.tim(page, css=["ytd-watch-metadata #description", "#description-inline-expander", "#description"],
              timeout_ms=2000)
    if e:
        mt = (e.inner_text() or "").strip()[:800]
    return {"tieu_de": td, "mo_ta": mt}


# --------------------------------------------------------------------------- bình luận

def _tai_binh_luan(nc, giay: float = 30) -> bool:
    """Cuộn tới khi khu bình luận nạp (ô viết bình luận hoặc luồng bình luận). Tắt bình luận -> lỗi."""
    page = nc.page
    han = time.monotonic() + giay
    while time.monotonic() < han:
        if w.co_chu(page, "Tính năng bình luận đã bị tắt", "Bình luận đã bị tắt", "Comments are turned off"):
            raise LoiKyNang("video đã tắt bình luận")
        if w.dang_hien(page.locator("ytd-comments #placeholder-area, ytd-comment-simplebox-renderer")) or \
                page.locator("ytd-comment-thread-renderer").count():
            return True
        page.mouse.wheel(0, random.uniform(400, 800))
        nc.tay.nghi(0.8, 1.6)
    nc.nhat_ky("Cuộn 30 giây vẫn chưa thấy khu bình luận (ytd-comments)")
    return False


def _o_binh_luan(nc):
    page = nc.page
    if not _tai_binh_luan(nc):
        raise LoiKyNang("không nạp được khu bình luận dưới video")
    o_css = ["ytd-comments-header-renderer #contenteditable-root", "ytd-comment-simplebox-renderer #contenteditable-root"]
    o = w.dau_tien_thay([page.locator(c) for c in o_css], 1000)
    if o:
        return o
    ph = w.tim(page, css=["ytd-comments #placeholder-area", "ytd-comments #simplebox-placeholder"],
               role="button", ten=["Viết bình luận", "Add a comment"], chua=True, timeout_ms=8000)
    if not ph:
        raise LoiKyNang("không thấy ô 'Viết bình luận...' (#placeholder-area)")
    nc.tay.bam(ph)        # mở ô soạn, chưa công khai
    nc.tay.nghi(0.8, 1.5)
    o = w.dau_tien_thay([page.locator(c) for c in o_css], 8000)
    if not o:
        raise LoiKyNang("đã bấm ô bình luận nhưng không hiện #contenteditable-root")
    return o


def _gui(nc, o, nut_gui, text: str, mo_ta: str) -> bool:
    page = nc.page
    mau = mau_nhan_dien(text)
    so_luong = page.locator("ytd-comment-thread-renderer").count()
    truoc = w.dem_chu_ngoai_o_nhap(page, mau) if mau else 0

    def xac_nhan():
        if mau:
            return w.dem_chu_ngoai_o_nhap(page, mau) > truoc
        return page.locator("ytd-comment-thread-renderer").count() > so_luong

    def nut():
        n = nut_gui()
        if n is not None and (n.get_attribute("aria-disabled") == "true" or n.get_attribute("disabled") is not None):
            nc.tay.nghi(0.8, 1.5)
            n = nut_gui()
        return n
    return w.gui_noi_dung(nc, o, text, nut_gui=nut, mo_ta=mo_ta, giay_xac_nhan=25, xac_nhan=xac_nhan)


def binh_luan(nc, text: str) -> bool:
    """Viết bình luận cấp 1 dưới video đang mở, gửi bằng nút Bình luận, đọc lại thấy chữ hiện."""
    page = nc.page
    o = _o_binh_luan(nc)
    return _gui(nc, o, lambda: w.dau_tien_thay(
        [page.locator(c) for c in ("ytd-comments-header-renderer #submit-button button",
                                   "ytd-comment-simplebox-renderer #submit-button button",
                                   "ytd-comments-header-renderer #submit-button")]
        + [page.locator("ytd-comments-header-renderer").get_by_role("button", name=w.re_nhan("Bình luận", "Comment"))],
        4000),
                text[:GIOI_HAN_BL], "Đăng bình luận YouTube")


_JS_BL = r"""() => {
  const out = [];
  const txt = e => (e ? (e.innerText || e.textContent || '') : '').replace(/\s+/g, ' ').trim();
  document.querySelectorAll('ytd-comment-thread-renderer').forEach((t, i) => {
    const c = t.querySelector('#comment') || t.querySelector('ytd-comment-view-model, ytd-comment-renderer');
    if (!c) return;
    const a = c.querySelector('#author-text');
    const ct = c.querySelector('#content-text');
    const rep = t.querySelector('#replies');
    const ct_img = rep ? rep.querySelector('#creator-thumbnail') : null;
    const chu_kenh_tl = !!(ct_img && !ct_img.hidden && ct_img.getBoundingClientRect().width > 0);
    t.setAttribute('data-minmin-yt', String(i));
    out.push({i, tac_gia: txt(a), href: a ? (a.getAttribute('href') || '') : '', chu: ct ? (ct.innerText || '').trim() : '',
              cua_chu_kenh: !!c.querySelector('ytd-author-comment-badge-renderer[creator], #author-comment-badge ytd-author-comment-badge-renderer'),
              chu_kenh_da_tl: chu_kenh_tl,
              ghim: !!c.querySelector('ytd-pinned-comment-badge-renderer, #pinned-comment-badge yt-formatted-string')});
  });
  return out;
}"""


def doc_binh_luan(nc, toi_da: int = 20) -> list:
    """Bình luận cấp 1 đang có trên trang (cuộn thêm tới khi đủ toi_da hoặc không nạp thêm)."""
    page = nc.page
    ds, dung_yen = [], 0
    for _ in range(12):
        ds = page.evaluate(_JS_BL) or []
        if len(ds) >= toi_da or dung_yen >= 2 or nc.nen_dung():
            break
        n = len(ds)
        page.mouse.wheel(0, random.uniform(900, 1500))
        nc.tay.nghi(1.2, 2.2)
        dung_yen = dung_yen + 1 if len(page.evaluate(_JS_BL) or []) == n else 0
    return ds[:toi_da]


def _luong(page, tac_gia: str, chu: str):
    """Luồng bình luận (ytd-comment-thread-renderer) theo tác giả + đầu câu."""
    loc = page.locator("ytd-comment-thread-renderer")
    if chu:
        loc = loc.filter(has_text=re.sub(r"\s+", " ", chu).strip()[:30])
    if tac_gia:
        loc2 = loc.filter(has=page.locator("#author-text").filter(has_text=tac_gia))
        if loc2.count():
            return loc2.first
    return loc.first if loc.count() else None


def tra_loi(nc, luong, text: str) -> bool:
    """Bấm 'Phản hồi' dưới bình luận cấp 1 của `luong`, gõ, gửi, đọc lại thấy chữ."""
    page = nc.page
    goc = w.dau_tien_thay([luong.locator("#comment #reply-button-end button"),
                           luong.locator("ytd-comment-view-model #reply-button-end button"),
                           luong.locator("#reply-button-end button"),
                           luong.get_by_role("button", name=w.re_nhan("Phản hồi", "Reply"))], 6000)
    if not goc:
        raise LoiKyNang("không thấy nút Phản hồi (#reply-button-end) dưới bình luận")
    nc.tay.bam(goc)       # mở ô trả lời, chưa công khai
    nc.tay.nghi(0.8, 1.5)
    o = w.dau_tien_thay([luong.locator("ytd-comment-reply-dialog-renderer #contenteditable-root"),
                         luong.locator("#reply-dialog #contenteditable-root"),
                         luong.locator("#contenteditable-root")], 8000)
    if not o:
        raise LoiKyNang("đã bấm Phản hồi nhưng không hiện ô trả lời")
    # Chỉ tìm nút gửi TRONG hộp trả lời: nút "Phản hồi" mở hộp cũng mang đúng nhãn đó.
    return _gui(nc, o, lambda: w.dau_tien_thay(
        [luong.locator(c) for c in ("ytd-comment-reply-dialog-renderer #submit-button button",
                                    "#reply-dialog #submit-button button",
                                    "ytd-comment-reply-dialog-renderer #submit-button")]
        + [luong.locator("ytd-comment-reply-dialog-renderer").get_by_role("button", name=w.re_nhan("Phản hồi", "Reply"))],
        4000),
                text[:GIOI_HAN_BL], "Gửi trả lời bình luận YouTube")


def ghim_binh_luan(nc, luong) -> bool:
    """Menu tác vụ của bình luận -> Ghim -> xác nhận -> đọc lại thấy nhãn 'Đã ghim bởi'. Chỉ làm được trên
    video của chính kênh nick."""
    page = nc.page
    c = w.dau_tien_thay([luong.locator("#comment"), luong.locator("ytd-comment-view-model"),
                         luong.locator("ytd-comment-renderer")], 3000) or luong
    try:
        nc.tay.di_toi(c)          # nút ba chấm chỉ hiện khi rê chuột
    except Exception:
        pass
    nc.tay.nghi(0.6, 1.2)
    menu = w.dau_tien_thay([c.locator("#action-menu button"), c.locator("#action-menu yt-icon-button"),
                            c.get_by_role("button", name=w.re_chua("Tác vụ", "Action menu", "Menu tác vụ")),
                            c.locator("ytd-menu-renderer button")], 6000)
    if not menu:
        raise LoiKyNang("không thấy nút menu tác vụ (#action-menu) của bình luận")
    nc.tay.bam(menu)
    nc.tay.nghi(0.8, 1.5)
    muc = w.dau_tien_thay([page.locator("ytd-menu-popup-renderer ytd-menu-service-item-renderer, "
                                        "ytd-menu-popup-renderer tp-yt-paper-item, [role='menuitem']")
                           .filter(has_text=w.re_nhan("Ghim", "Pin")),
                           page.get_by_role("menuitem", name=w.re_nhan("Ghim", "Pin"))], 5000)
    if not muc:
        page.keyboard.press("Escape")
        raise LoiKyNang("menu bình luận không có mục 'Ghim' (video không thuộc kênh của nick?)")
    if not w.bam_cong_khai(nc, muc, "Ghim bình luận YouTube"):
        page.keyboard.press("Escape")
        return False
    nc.tay.nghi(0.8, 1.5)
    xn = w.dau_tien_thay([page.locator("yt-confirm-dialog-renderer #confirm-button button"),
                          page.locator("yt-confirm-dialog-renderer #confirm-button"),
                          page.locator("tp-yt-paper-dialog #confirm-button"),
                          page.get_by_role("dialog").get_by_role("button", name=w.re_nhan("Ghim", "Pin"))], 6000)
    if xn:
        nc.nhat_ky("Hộp xác nhận ghim (thay bình luận đang ghim nếu có): bấm Ghim")
        w.bam_cong_khai(nc, xn, "Xác nhận ghim bình luận")
    else:
        nc.nhat_ky("Không thấy hộp xác nhận ghim, đọc lại xem đã ghim chưa")
    ok = w.cho(lambda: w.dang_hien(luong.locator("ytd-pinned-comment-badge-renderer, #pinned-comment-badge"))
               or w.co_chu(luong, "Đã ghim bởi", "Được ghim bởi", "Ghim bởi", "Pinned by"), 15)
    w.kiem_chan(nc)
    return ok


# --------------------------------------------------------------------------- kênh của nick

def kenh_cua_nick(nc, mo_trang: bool = True) -> dict:
    """{handle, ten, link} kênh đang đăng nhập. {} nếu chưa đăng nhập; {'chua_co_kenh': True} nếu tài khoản
    Google chưa tạo kênh. Đọc từ menu ảnh đại diện (#avatar-btn), dự phòng studio.youtube.com/channel/UC..."""
    page = nc.page
    if mo_trang:
        nc.mo(GOC + "/")
        nc.tay.nghi(3.0, 5.0)
    nc.kiem_dang_nhap()
    nut = w.tim(page, css=["ytd-masthead #avatar-btn", "button#avatar-btn", "ytd-topbar-menu-button-renderer #avatar-btn"],
                ten=["Trình đơn tài khoản", "Account menu", "Ảnh đại diện"], chua=True, timeout_ms=10000)
    handle = ten = link = ""
    if nut:
        nc.tay.bam(nut)        # mở menu tài khoản (chỉ đọc)
        nc.tay.nghi(1.0, 2.0)
        hdr = w.dau_tien_thay([page.locator("ytd-active-account-header-renderer")], 6000)
        if hdr:
            e = hdr.locator("#channel-handle")
            handle = (e.first.inner_text() or "").strip() if e.count() else ""
            e = hdr.locator("#account-name")
            ten = (e.first.inner_text() or "").strip() if e.count() else ""
            for a in hdr.locator("a[href]").all()[:6]:
                h = a.get_attribute("href") or ""
                if re.search(r"^/(@|channel/)|youtube\.com/(@|channel/)", h):
                    link = h
                    break
        if not link:
            a = w.tim(page, role="link", ten=["Kênh của bạn", "Your channel", "Xem kênh của bạn", "View your channel"],
                      chua=True, timeout_ms=2000)
            link = (a.get_attribute("href") or "") if a else ""
        if not handle and not link and w.co_chu(page, "Tạo kênh", "Create a channel"):
            page.keyboard.press("Escape")
            nc.nhat_ky("Tài khoản Google này chưa tạo kênh YouTube")
            return {"chua_co_kenh": True}
        page.keyboard.press("Escape")
        nc.tay.nghi(0.4, 0.9)
    else:
        nc.nhat_ky("Không thấy nút ảnh đại diện (#avatar-btn) trên thanh trên cùng YouTube")
    if handle and not handle.startswith("@"):
        handle = "@" + handle if re.fullmatch(r"[\w.\-]+", handle) else ""
    if not handle:
        m = re.search(r"/(@[^/?#]+)", link)
        handle = urllib.parse.unquote(m.group(1)) if m else ""
    if link and link.startswith("/"):
        link = GOC + link
    if handle and not link:
        link = f"{GOC}/{handle}"
    if not link:
        nc.nhat_ky("Menu tài khoản không cho link kênh, thử YouTube Studio")
        nc.mo(URL_STUDIO)
        if w.cho(lambda: "/channel/UC" in (page.url or ""), 25):
            m = re.search(r"/channel/(UC[\w-]+)", page.url)
            link = f"{GOC}/channel/{m.group(1)}" if m else ""
        _dang_xuat(nc)
    if not link:
        return {}
    nc.nhat_ky(f"Kênh của nick: {handle or ten or link}")
    return {"handle": handle, "ten": ten or handle, "link": link.split("?")[0].rstrip("/")}


_JS_LINK_KENH = r"""() => {
  const goc = document.querySelector('ytd-rich-grid-renderer') || document.querySelector('ytd-browse #contents')
    || document.querySelector('#contents') || document.body;
  const out = [];
  goc.querySelectorAll("a[href*='/watch?v='], a[href*='/shorts/']").forEach(a => {
    const h = a.getAttribute('href') || '';
    if (!out.includes(h)) out.push(h);
  });
  return out;
}"""


def video_cua_kenh(nc, kenh: str, so: int, nguon: str = "ca_hai") -> list:
    """[(link watch, id, là_shorts)] gần nhất của kênh, theo tab /videos và/hoặc /shorts."""
    tabs = {"video": ["/videos"], "shorts": ["/shorts"]}.get(nguon, ["/videos", "/shorts"])
    nhom = []
    for tab in tabs:
        _mo(nc, kenh.rstrip("/") + tab)
        w.cho(lambda: bool(nc.page.evaluate(_JS_LINK_KENH)), 12)
        ds, thay = [], set()
        for h in nc.page.evaluate(_JS_LINK_KENH) or []:
            lk, vid = chuan_link(h)
            if vid and vid not in thay:
                thay.add(vid)
                ds.append((lk, vid, tab == "/shorts"))
            if len(ds) >= so:
                break
        nc.nhat_ky(f"Kênh {tab}: thấy {len(ds)} video")
        nhom.append(ds)
    out = []
    for i in range(so):              # xen kẽ video thường và Shorts
        for ds in nhom:
            if i < len(ds) and len(out) < so:
                out.append(ds[i])
    return out


# --------------------------------------------------------------------------- yt_nuoi_nick

_JS_THUMB = r"""() => {
  const out = [];
  document.querySelectorAll("a[href^='/watch?v=']").forEach(a => {
    if (a.closest('ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer, ytd-promoted-video-renderer')) return;
    if ((a.getAttribute('aria-label') || '').startsWith('Quảng cáo')) return;
    const r = a.getBoundingClientRect();
    if (r.width < 80 || r.height < 40) return;
    const h = a.getAttribute('href');
    if (!out.includes(h)) out.push(h);
  });
  return out.slice(0, 24);
}"""

_JS_VIDEO = r"""() => { const v = document.querySelector('video.html5-main-video') || document.querySelector('video');
  return v ? {paused: v.paused, dur: v.duration || 0, t: v.currentTime || 0, ad: !!document.querySelector('.ad-showing')} : null; }"""


def _bo_qua_qc(nc) -> None:
    nut = w.dau_tien_thay([nc.page.locator(".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern")], 300)
    if nut:
        nc.nhat_ky("Bỏ qua quảng cáo")
        try:
            nc.tay.bam(nut)
        except Exception:
            pass


def _xem(nc, giay: float, han: float) -> bool:
    """Xem video đang mở trong `giay` giây (không quá hạn tổng). Bỏ qua quảng cáo, bấm phát nếu đứng.
    True = nên dừng."""
    giay = giay / max(1.0, float(getattr(nc.tay, "toc_do", 1) or 1))     # test chạy nhanh (toc_do lớn)
    het = min(time.monotonic() + giay, han)
    da_bam_phat = False
    while time.monotonic() < het:
        if nc.nen_dung():
            return True
        _bo_qua_qc(nc)
        try:
            v = nc.page.evaluate(_JS_VIDEO)
        except Exception:
            v = None
        if v and v.get("paused") and not da_bam_phat:
            p = w.tim(nc.page, css=["button.ytp-play-button"], timeout_ms=1000)
            if p:
                nc.nhat_ky("Video đang dừng, bấm phát")
                nc.tay.bam(p)
                da_bam_phat = True
        nc.tay.nghi(min(5.0, max(0.5, het - time.monotonic())), min(5.0, max(0.5, het - time.monotonic())))
    return nc.nen_dung()


def _xem_mot_video(nc, dem, rng, han, ts) -> None:
    page = nc.page
    tt = _doc_video(page)
    try:
        v = page.evaluate(_JS_VIDEO) or {}
    except Exception:
        v = {}
    dai = float(v.get("dur") or 0)
    giay = rng.uniform(25, 150)
    if 0 < dai < 6 * 3600 and not v.get("ad"):
        giay = min(giay, dai * rng.uniform(0.5, 0.95))
    nc.nhat_ky(f"Xem \"{tt['tieu_de'][:60]}\" khoảng {giay:.0f} giây" + (f" (video dài {dai:.0f}s)" if dai else ""))
    if _xem(nc, giay * 0.6, han):
        return
    if rng.random() < 0.35:
        nc.nhat_ky("Cuộn xuống đọc bình luận")
        nc.tay.luot(rng.randint(2, 4))
        nc.tay.nghi(3.0, 8.0)
        page.mouse.wheel(0, -4000)
        nc.tay.nghi(1.0, 2.0)
    if ts.get("thich", True) and rng.random() < 0.2 and w.con_luot(nc, dem, "thich"):
        _thich(nc, dem, page.url, "thích video đang xem")
    if ts.get("cho_dang_ky") and rng.random() < 0.1 and w.con_luot(nc, dem, "theo_doi"):
        _dang_ky(nc, dem, page.url)
    _xem(nc, giay * 0.4, han)


def _luot_shorts(nc, dem, rng, han, ts) -> int:
    page = nc.page
    _mo(nc, GOC + "/shorts")
    if not w.cho(lambda: page.locator("ytd-reel-video-renderer, ytd-shorts").count() > 0, 15):
        nc.nhat_ky("Không mở được trang Shorts (ytd-reel-video-renderer)")
        return 0
    so = 0
    for _ in range(rng.randint(3, 8)):
        if time.monotonic() >= han or nc.nen_dung():
            break
        so += 1
        if _xem(nc, rng.uniform(5, 25), han):
            break
        if ts.get("thich", True) and rng.random() < 0.2 and w.con_luot(nc, dem, "thich"):
            loc = page.locator("ytd-reel-video-renderer[is-active] like-button-view-model button, "
                               "ytd-reel-video-renderer[is-active] #like-button button")
            nut = loc.first if loc.count() else (w.trong_khung(page, page.locator("like-button-view-model button")) or
                                                  [None])[0]
            if nut is not None:
                w.bam_va_xac_nhan(nc, dem, "thich", nut, _da_thich, "thích Shorts đang xem", page.url)
        page.keyboard.press("ArrowDown")       # sang Shorts kế (không công khai)
        nc.tay.nghi(0.8, 1.8)
    nc.nhat_ky(f"Lướt {so} Shorts")
    return so


def yt_nuoi_nick(nc) -> str:
    ts = nc.ts
    phut = float(ts.get("phut", 10) or 10)
    tu_khoa = w.ds_dong(ts.get("tu_khoa"))
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)
    han = time.monotonic() + phut * 60
    so_video = so_shorts = 0
    nc.nhat_ky(f"Nuôi nick YouTube {phut:g} phút" + (f", từ khoá: {', '.join(tu_khoa[:5])}" if tu_khoa else ""))
    while time.monotonic() < han and not nc.nen_dung():
        try:
            w.kiem_chan(nc)
            if ts.get("xem_shorts", True) and rng.random() < 0.3:
                so_shorts += _luot_shorts(nc, dem, rng, han, ts)
                continue
            if tu_khoa and rng.random() < 0.7:
                k = rng.choice(tu_khoa)
                nc.nhat_ky(f"Tìm \"{k}\"")
                _mo(nc, f"{GOC}/results?search_query={urllib.parse.quote(k)}")
            else:
                _mo(nc, GOC + "/")
            nc.tay.luot(rng.randint(1, 3))
            ds = nc.page.evaluate(_JS_THUMB) or []
            if not ds:
                nc.nhat_ky("Không thấy video nào để mở (a[href^='/watch?v=']), nghỉ rồi thử lại")
                if w.nghi_co_dung(nc, 10):
                    break
                continue
            h = rng.choice(ds[:12])
            a = nc.page.locator(f"a[href='{h}']").first
            try:
                nc.tay.bam(a)
                w.cho(lambda: "/watch" in (nc.page.url or ""), 10)
            except Exception:
                pass
            if "/watch" not in (nc.page.url or ""):
                nc.mo(GOC + h)
            nc.tay.nghi(2.0, 4.0)
            so_video += 1
            _xem_mot_video(nc, dem, rng, han, ts)
        except LoiKyNang as e:
            if getattr(e, "ma", None) in w.MA_DUNG:
                raise
            nc.nhat_ky(f"Nuôi nick: {e}")
    w.bao(nc, dem, "thich", "thong_tin", f"Nuôi nick YouTube: {phut:g} phút, xem {so_video} video, "
                                         f"{so_shorts} Shorts, thích {dem.ok.get('thich', 0)}, "
                                         f"đăng ký {dem.ok.get('theo_doi', 0)}")
    return (f"{'Chạy thử - ' if nc.chay_thu else ''}Nuôi nick YouTube: {so_video} video, {so_shorts} Shorts, "
            f"{dem.tom_tat()}.")


# --------------------------------------------------------------------------- yt_tuong_tac_link

def yt_tuong_tac_link(nc) -> str:
    ts = nc.ts
    links = w.ds_dong(ts.get("links"))
    cau = w.ds_dong(ts.get("cau_binh_luan"))
    co_bl = bool(ts.get("binh_luan")) or bool(cau)
    sp = str(ts.get("san_pham") or "")
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    for goc in links:
        if nc.nen_dung():
            break
        link, vid = chuan_link(goc)
        try:
            if not vid:
                w.bao(nc, dem, "thich", "bo_qua", f"không đọc được mã video từ link {goc[:80]}", link=goc)
                continue
            nc.nhat_ky(f"Mở video {vid}")
            _mo(nc, link)
            _xem(nc, rng.uniform(6, 15), time.monotonic() + 60)
            if ts.get("thich", True) and w.con_luot(nc, dem, "thich"):
                _thich(nc, dem, link)
            if ts.get("dang_ky") and w.con_luot(nc, dem, "theo_doi"):
                _dang_ky(nc, dem, link)
            if co_bl and w.con_luot(nc, dem, "binh_luan"):
                k = w.khoa(NT, "binh_luan", vid)
                if nc.da_lam(k):
                    w.bao(nc, dem, "binh_luan", "bo_qua", "nick đã bình luận video này", link=link)
                elif cau:
                    c = spin(rng.choice(cau), rng)
                    if nc.chay_thu:
                        w.bao_thu(nc, dem, "binh_luan", f"Chạy thử: sẽ bình luận \"{c[:80]}\"", link=link)
                    elif binh_luan(nc, c):
                        nc.ghi_da_lam(k)
                        w.bao(nc, dem, "binh_luan", "thanh_cong", f"Bình luận \"{c[:60]}\" đã hiện", link=link)
                        nc.nghi_thao_tac()
                    else:
                        w.bao(nc, dem, "binh_luan", "loi", "đã gửi nhưng chưa thấy bình luận hiện", link=link)
                else:
                    tt = _doc_video(nc.page)
                    kq = w.lay_ai(nc, "viet_binh_luan", {"bai": {"chu": f"{tt['tieu_de']}\n{tt['mo_ta']}", "link": link},
                                                         "san_pham_id": sp, "kieu": "tu_nhien"})
                    nd = str(kq.get("noi_dung") or "").strip()

                    def _dang(x):
                        if not binh_luan(nc, x):
                            raise LoiKyNang("đã gửi bình luận nhưng chưa thấy hiện")
                        return link
                    w.noi_dung_ai(nc, dem, "binh_luan", loai="binh_luan", noi_dang=NT, link_goc=link,
                                  bai_goc=tt["tieu_de"], ly_do=f"Bình luận video: {tt['tieu_de'][:120]}",
                                  noi_dung=nd, khoa_lap=k, dang=_dang, san_pham_id=sp)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "binh_luan" if co_bl else "thich", e, link)
    return w.ket_thuc(nc, dem, "Tương tác video YouTube")


# --------------------------------------------------------------------------- yt_tra_loi_binh_luan

def _sap_moi_nhat(nc) -> None:
    page = nc.page
    chip = w.dau_tien_thay([page.locator("ytd-comments-header-renderer yt-chip-cloud-chip-renderer, "
                                         "ytd-comments-header-renderer chip-shape button")
                            .filter(has_text=w.re_chua("Mới nhất", "Newest"))], 1500)
    if chip:
        nc.tay.bam(chip)
        nc.tay.nghi(1.5, 3.0)
        nc.nhat_ky("Xếp bình luận: Mới nhất")
        return
    nut = w.tim(page, css=["ytd-comments-header-renderer #sort-menu tp-yt-paper-button",
                           "ytd-comments-header-renderer #sort-menu yt-dropdown-menu",
                           "ytd-comments-header-renderer #sort-menu"],
                ten=["Sắp xếp bình luận", "Sort comments"], chua=True, timeout_ms=4000)
    if not nut:
        nc.nhat_ky("Không thấy nút 'Sắp xếp theo' bình luận, giữ thứ tự mặc định")
        return
    nc.tay.bam(nut)
    nc.tay.nghi(0.8, 1.5)
    muc = w.dau_tien_thay([page.locator("tp-yt-paper-listbox a, tp-yt-paper-listbox tp-yt-paper-item, "
                                        "[role='menuitem'], [role='option']")
                           .filter(has_text=w.re_chua("Mới nhất", "Newest"))], 4000)
    if muc:
        nc.tay.bam(muc)
        nc.tay.nghi(1.5, 3.0)
        nc.nhat_ky("Xếp bình luận: Mới nhất")
    else:
        page.keyboard.press("Escape")
        nc.nhat_ky("Menu sắp xếp không có 'Mới nhất'")


def _la_chu_kenh(bl: dict, kenh: dict) -> bool:
    h = (kenh.get("handle") or "").lower()
    tg = (bl.get("tac_gia") or "").strip().lower()
    if bl.get("cua_chu_kenh"):
        return True
    if h and (tg == h or (bl.get("href") or "").lower().rstrip("/").endswith("/" + h)):
        return True
    return bool(kenh.get("ten") and tg == str(kenh["ten"]).strip().lower())


def yt_tra_loi_binh_luan(nc) -> str:
    ts = nc.ts
    sp = str(ts.get("san_pham") or "")
    so_video = int(ts.get("so_video", 3) or 3)
    toi_da_bl = int(ts.get("so_binh_luan", 20) or 20)
    dem = w.Dem()
    hd = "tra_loi_binh_luan"
    kenh = kenh_cua_nick(nc)
    if not kenh.get("link"):
        raise LoiKyNang("nick chưa có kênh YouTube" if kenh.get("chua_co_kenh") else
                        "không đọc được kênh YouTube của nick (menu ảnh đại diện / Studio)")
    videos = video_cua_kenh(nc, kenh["link"], so_video, str(ts.get("nguon_video") or "ca_hai"))
    nc.nhat_ky(f"Kênh {kenh.get('handle') or kenh['link']}: xét {len(videos)} video gần nhất")
    if not videos:
        w.bao(nc, dem, hd, "bo_qua", "kênh chưa có video nào để trả lời bình luận", link=kenh["link"])
    for link, vid, la_shorts in videos:
        if nc.nen_dung() or not w.con_luot(nc, dem, hd):
            break
        try:
            _mo(nc, link)
            tt = _doc_video(nc.page)
            if not _tai_binh_luan(nc):
                w.bao(nc, dem, hd, "bo_qua", "chưa nạp được bình luận", link=link)
                continue
            _sap_moi_nhat(nc)
            ds = doc_binh_luan(nc, toi_da_bl)
            nc.nhat_ky(f"Video {vid}{' (Shorts)' if la_shorts else ''}: đọc {len(ds)} bình luận")
            for bl in ds:
                if nc.nen_dung() or not w.con_luot(nc, dem, hd):
                    break
                if not bl.get("chu") or _la_chu_kenh(bl, kenh):
                    continue
                k = w.khoa(NT, "tra_loi", vid, bl.get("tac_gia"), w.bam_chuoi(bl["chu"]))
                if nc.da_lam(k):
                    continue
                if bl.get("chu_kenh_da_tl"):
                    nc.ghi_da_lam(k)
                    nc.nhat_ky(f"Bỏ qua {bl.get('tac_gia')}: chủ kênh đã trả lời từ trước")
                    continue
                kq = w.lay_ai(nc, "tra_loi_binh_luan", {
                    "bai_cua_nick": True, "bai": {"chu": f"{tt['tieu_de']}\n{tt['mo_ta']}", "link": link},
                    "binh_luan": {"tac_gia": bl.get("tac_gia"), "chu": bl["chu"]}, "san_pham_id": sp})
                if kq.get("can_hoi_chu"):
                    nc.ghi_da_lam(k)
                    w.bao(nc, dem, hd, "bo_qua", f"Câu hỏi chưa có trong Kiến thức, đã chuyển bạn trả lời: "
                                                 f"{bl['chu'][:80]}", link=link)
                    continue
                tg, chu = bl.get("tac_gia") or "", bl["chu"]

                def _dang(nd, tg=tg, chu=chu):
                    luong = _luong(nc.page, tg, chu)
                    if luong is None:
                        raise LoiKyNang(f"không tìm lại được bình luận của {tg}")
                    if not tra_loi(nc, luong, nd):
                        raise LoiKyNang("đã gửi trả lời nhưng chưa thấy hiện")
                    return link
                w.noi_dung_ai(nc, dem, hd, loai="tra_loi", noi_dang=NT, link_goc=w.gan_muc_tieu(link, tg, chu),
                              bai_goc=tt["tieu_de"], ly_do=f"{tg} bình luận: {chu[:150]}",
                              noi_dung=str(kq.get("noi_dung") or "").strip(), khoa_lap=k, dang=_dang, san_pham_id=sp)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return w.ket_thuc(nc, dem, "Trả lời bình luận YouTube")


# --------------------------------------------------------------------------- yt_binh_luan_ghim_link

def yt_binh_luan_ghim_link(nc) -> str:
    ts = nc.ts
    mau = w.ds_dong(ts.get("noi_dung"))
    if not mau:
        raise LoiKyNang("thiếu nội dung bình luận chứa link tiếp thị")
    co_ghim = ts.get("ghim", True) not in (False, 0, "0", "false")
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    links = w.ds_dong(ts.get("links"))
    if links:
        videos = [chuan_link(x) + (False,) for x in links]
    else:
        kenh = kenh_cua_nick(nc, mo_trang=False)
        if not kenh.get("link"):
            raise LoiKyNang("nick chưa có kênh YouTube" if kenh.get("chua_co_kenh") else
                            "không đọc được kênh YouTube của nick để lấy video gần nhất")
        videos = video_cua_kenh(nc, kenh["link"], int(ts.get("so_video", 3) or 3), str(ts.get("nguon_video") or "ca_hai"))
    nc.nhat_ky(f"Bình luận link tiếp thị dưới {len(videos)} video" + (" và ghim" if co_ghim else ""))
    for link, vid, _s in videos:
        if nc.nen_dung() or not w.con_luot(nc, dem, "binh_luan"):
            break
        try:
            if not vid:
                w.bao(nc, dem, "binh_luan", "bo_qua", f"không đọc được mã video: {link[:80]}", link=link)
                continue
            k = w.khoa(NT, "ghim_link", vid)
            if nc.da_lam(k):
                w.bao(nc, dem, "binh_luan", "bo_qua", "video này đã có bình luận link tiếp thị của nick", link=link)
                continue
            c = spin(rng.choice(mau), rng).strip()
            if nc.chay_thu:
                w.bao_thu(nc, dem, "binh_luan", f"Chạy thử: sẽ bình luận \"{c[:100]}\"" +
                          (" rồi ghim lên đầu" if co_ghim else ""), link=link)
                continue
            _mo(nc, link)
            if not binh_luan(nc, c):
                w.bao(nc, dem, "binh_luan", "loi", "đã gửi nhưng chưa thấy bình luận hiện", link=link)
                continue
            nc.ghi_da_lam(k)
            w.bao(nc, dem, "binh_luan", "thanh_cong", f"Bình luận link tiếp thị \"{c[:60]}\" đã hiện", link=link)
            if co_ghim and w.con_luot(nc, dem, "quan_ly_bai"):
                nc.tay.nghi(2.0, 4.0)
                mau_tim = mau_nhan_dien(c)
                luong = _luong(nc.page, "", mau_tim) if mau_tim else nc.page.locator("ytd-comment-thread-renderer").first
                if luong is None:
                    w.bao(nc, dem, "quan_ly_bai", "loi", "không tìm lại được bình luận vừa đăng để ghim", link=link)
                else:
                    try:
                        if ghim_binh_luan(nc, luong):
                            w.bao(nc, dem, "quan_ly_bai", "thanh_cong", "Đã ghim bình luận (thấy nhãn 'Đã ghim bởi')",
                                  link=link)
                        else:
                            w.bao(nc, dem, "quan_ly_bai", "loi", "đã bấm Ghim nhưng chưa thấy nhãn 'Đã ghim bởi'",
                                  link=link)
                    except Exception as e:
                        w.bao_loi_ngoai_le(nc, dem, "quan_ly_bai", e, link)
            nc.nghi_thao_tac()
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "binh_luan", e, link)
    return w.ket_thuc(nc, dem, "Bình luận + ghim link tiếp thị YouTube")


# --------------------------------------------------------------------------- yt_quet_csv

COT_CSV = ["stt", "link", "tieu_de", "kenh", "luot_xem", "luot_xem_so", "dang_luc", "thoi_luong", "loai"]

_JS_QUET = r"""() => {
  const out = [], seen = new Set();
  const txt = e => (e ? (e.innerText || e.textContent || '') : '').replace(/\s+/g, ' ').trim();
  const KHOI = 'ytd-video-renderer, ytd-rich-item-renderer, ytd-grid-video-renderer, ytd-reel-item-renderer, '
    + 'ytm-shorts-lockup-view-model, ytm-shorts-lockup-view-model-v2, yt-lockup-view-model, ytd-compact-video-renderer';
  const idOf = h => { const m = (h || '').match(/(?:[?&]v=|\/shorts\/)([A-Za-z0-9_-]{11})/); return m ? m[1] : ''; };
  document.querySelectorAll("a[href^='/watch?v='], a[href^='/shorts/'], a[href*='youtube.com/watch?v='], a[href*='youtube.com/shorts/']").forEach(a => {
    const href = a.getAttribute('href') || '';
    const id = idOf(href);
    if (!id || seen.has(id)) return;
    if ((a.getAttribute('aria-label') || '').startsWith('Quảng cáo') || /aclk|googleadservices/.test(href)) return;
    if (a.closest('ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer, ytd-promoted-video-renderer, #masthead')) return;
    let e = a.closest(KHOI);
    if (!e) {          // khối không biết tên: leo lên tới khi cha chứa video khác
      e = a;
      for (let k = 0; k < 8 && e.parentElement; k++) {
        const ids = new Set([...e.parentElement.querySelectorAll("a[href*='watch?v='], a[href*='/shorts/']")].map(x => idOf(x.getAttribute('href'))));
        if (ids.size > 1) break;
        e = e.parentElement;
      }
    }
    if ([...e.querySelectorAll('a')].some(x => (x.getAttribute('aria-label') || '').startsWith('Quảng cáo'))) return;
    seen.add(id);
    const shorts = /\/shorts\//.test(href);
    const tEl = e.querySelector('#video-title, #video-title-link, h3 a, h3, [class*="metadata-title"]');
    let tieu_de = tEl ? (tEl.getAttribute('title') || txt(tEl)) : '';
    if (!tieu_de) tieu_de = a.getAttribute('title') || '';
    const kEl = [...e.querySelectorAll('ytd-channel-name a, #channel-name a, a[href^="/@"], a[href^="/channel/"]')].find(x => txt(x));
    const meta = [...e.querySelectorAll('#metadata-line span, .inline-metadata-item, span, [class*="metadata-text"]')]
      .filter(x => !x.children.length).map(txt).filter(Boolean);
    const lx = meta.find(s => /(lượt xem|views?|người đang xem|watching)/i.test(s)) || '';
    const dl = meta.find(s => /(trước|ago|Đã phát trực tiếp|Streamed|Công chiếu|Premiered)/i.test(s)) || '';
    let tl = '';
    for (const b of e.querySelectorAll('badge-shape, ytd-thumbnail-overlay-time-status-renderer, [class*="badge"], #time-status')) {
      const m = txt(b).match(/\d{1,2}(:\d{2}){1,2}/); if (m) { tl = m[0]; break; }
    }
    if (!tl) { const m = txt(a).match(/\d{1,2}(:\d{2}){1,2}/); if (m) tl = m[0]; }
    out.push({id, shorts, tieu_de, kenh: txt(kEl), luot_xem: lx, dang_luc: dl, thoi_luong: tl});
  });
  return out;
}"""


def yt_quet_csv(nc) -> str:
    ts = nc.ts
    kieu = str(ts.get("kieu_quet") or "tim_kiem")
    vao = str(ts.get("dau_vao") or "").strip()
    chi_shorts = bool(ts.get("chi_shorts"))
    toi_da = int(ts.get("so_dong", 50) or 50)
    dem = w.Dem()
    if not vao:
        raise LoiKyNang("thiếu từ khoá hoặc kênh để quét")
    ten_kenh = ""
    if kieu == "kenh":
        if vao.startswith("http"):
            goc = re.sub(r"/(videos|shorts|featured|streams)/?$", "", vao.split("?")[0].rstrip("/"))
        elif vao.startswith("UC"):
            goc = f"{GOC}/channel/{vao}"
        else:
            goc = f"{GOC}/@{vao.lstrip('@')}"
        url = goc + ("/shorts" if chi_shorts else "/videos")
    else:
        url = f"{GOC}/results?search_query={urllib.parse.quote(vao)}"
    nc.mo(url)
    try:          # 26.10.235: quét chỉ đọc dữ liệu công khai, nick chưa đăng nhập YouTube vẫn quét được
        nc.kiem_dang_nhap()
    except LoiKyNang as e:
        if getattr(e, "ma", "") != "dang_xuat":
            raise
        nc.nhat_ky("Nick chưa đăng nhập YouTube: chỉ đọc dữ liệu công khai")
    nc.tay.nghi(2.5, 4.5)
    w.kiem_chan(nc, cho_phep_trang_dang_nhap=True)
    if not w.con_luot(nc, dem, "quet"):
        return "Đã đủ giới hạn quét hôm nay"
    page = nc.page
    if kieu == "kenh":
        e = w.tim(page, css=["yt-page-header-view-model h1", "#page-header h1", "ytd-channel-name#channel-name #text"],
                  timeout_ms=4000)
        ten_kenh = (e.inner_text() or "").strip() if e else ""
    elif chi_shorts:
        chip = w.dau_tien_thay([page.locator("yt-chip-cloud-chip-renderer, chip-shape button, [role='tab']")
                                .filter(has_text=w.re_nhan("Shorts"))], 4000)
        if chip:
            nc.nhat_ky("Bấm bộ lọc 'Shorts' trên trang kết quả")
            nc.tay.bam(chip)
            nc.tay.nghi(2.5, 4.0)
        else:
            nc.nhat_ky("Không thấy nút lọc 'Shorts', quét tất cả rồi chỉ giữ link /shorts/")
    nc.nhat_ky(f"Quét {url}")
    dong, da_co, dung_yen = [], set(), 0
    while len(dong) < toi_da and dung_yen < 4 and not nc.nen_dung():
        moi = 0
        for r in page.evaluate(_JS_QUET) or []:
            if r["id"] in da_co or (chi_shorts and not r.get("shorts")):
                continue
            da_co.add(r["id"])
            link = f"{GOC}/shorts/{r['id']}" if r.get("shorts") else f"{GOC}/watch?v={r['id']}"
            dong.append({"stt": len(dong) + 1, "link": link, "tieu_de": r.get("tieu_de", ""),
                         "kenh": r.get("kenh") or ten_kenh, "luot_xem": r.get("luot_xem", ""),
                         "luot_xem_so": so_luot_xem(r.get("luot_xem", "")), "dang_luc": r.get("dang_luc", ""),
                         "thoi_luong": r.get("thoi_luong", ""), "loai": "Shorts" if r.get("shorts") else "Video"})
            moi += 1
            if len(dong) >= toi_da:
                break
        dung_yen = 0 if moi else dung_yen + 1
        if len(dong) < toi_da:
            page.mouse.wheel(0, random.uniform(1500, 2500))
            nc.tay.nghi(1.5, 3.0)
    if not dong:
        nc.nhat_ky("Không đọc được dòng nào (không thấy a[href^='/watch?v='] hay a[href^='/shorts/'])")
    ten_tep = f"youtube_{kieu}_{time.strftime('%Y%m%d-%H%M%S')}.csv"
    p = w.ghi_csv(ten_tep, COT_CSV, dong)
    gui = ""
    f = getattr(nc, "gui_tep_ket_qua", None)
    if callable(f) and dong:
        try:
            f(p)
            gui = " Đã gửi tệp về MinMin (tải ở chi tiết việc)."
        except Exception as e:
            nc.nhat_ky(f"Không gửi được tệp CSV về MinMin: {e}")
    xem = "; ".join(f"{d['tieu_de'][:40]} ({d['luot_xem'] or '?'})" for d in dong[:3])
    ct = f"Quét {len(dong)} dòng ({kieu}: {vao[:60]}). Tệp CSV trên máy: {p}.{gui} {xem}"
    w.bao(nc, dem, "quet", "thanh_cong" if dong else "bo_qua", ct, link=url)
    return f"Quét YouTube: {len(dong)} dòng, lưu {p}.{gui}"


# --------------------------------------------------------------------------- dang_ban_nhap:youtube

def _nhap_bai(nc, p: dict) -> str:
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    _dang_xuat(nc)
    tep = p.get("tep_cuc_bo") or []
    if not w.loc_tep(tep, w.DUOI_VIDEO):
        raise LoiKyNang("nháp bài YouTube chưa có video tải sẵn trên máy (YouTube bắt buộc có video)")
    return _dang_video(nc, {"noi_dung": p.get("noi_dung"), "tep_cuc_bo": tep}, w.TrangThaiDang(), _tuy_chon(p))


def _nhap_bl(nc, p: dict) -> str:
    goc, tg, chu = w.tach_muc_tieu(p.get("link_goc"))
    link, vid = chuan_link(goc)
    if not vid:
        raise LoiKyNang("nháp không có link video YouTube")
    nc.mo(link)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)
    nd = str(p.get("noi_dung") or "").strip()
    if chu:
        if not _tai_binh_luan(nc):
            raise LoiKyNang("không nạp được bình luận dưới video")
        doc_binh_luan(nc, 40)
        luong = _luong(nc.page, tg, chu)
        if luong is None:
            _sap_moi_nhat(nc)
            doc_binh_luan(nc, 60)
            luong = _luong(nc.page, tg, chu)
        if luong is None:
            raise LoiKyNang(f"không tìm lại được bình luận của {tg}")
        ok = tra_loi(nc, luong, nd)
    else:
        ok = binh_luan(nc, nd)
    if not ok:
        raise LoiKyNang("đã gửi nhưng chưa thấy bình luận hiện")
    return link


def dang_ban_nhap(nc) -> str:
    return w.dang_ban_nhap_chung(nc, NT, {"bai_dang": lambda p: _nhap_bai(nc, p),
                                          "binh_luan": lambda p: _nhap_bl(nc, p),
                                          "tra_loi": lambda p: _nhap_bl(nc, p)})


KICH_BAN = {
    "yt_dang_video_kho": yt_dang_video_kho,
    "yt_dang_ai": yt_dang_ai,
    "yt_nuoi_nick": yt_nuoi_nick,
    "yt_tuong_tac_link": yt_tuong_tac_link,
    "yt_tra_loi_binh_luan": yt_tra_loi_binh_luan,
    "yt_binh_luan_ghim_link": yt_binh_luan_ghim_link,
    "yt_quet_csv": yt_quet_csv,
    "dang_ban_nhap:youtube": dang_ban_nhap,
}
