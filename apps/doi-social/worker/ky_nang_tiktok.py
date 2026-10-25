"""Kỹ năng TikTok: đăng video / ảnh (slide) từ kho, đăng video gắn sản phẩm giỏ hàng, đăng nháp AI đã duyệt,
tương tác video, bình luận LIVE, nuôi nick, tự trả lời bình luận, bình luận theo từ khoá (AI), theo dõi người
xem kênh đối thủ, quét ra CSV (video / giỏ hàng), và đăng nháp đã duyệt (dang_ban_nhap:tiktok).

DOM thật quan sát 25/10/2026 (vi-VN): thẻ tìm kiếm `div[role=button][data-e2e=search_video-item]` chứa
`a[href*=/video/]` tuyệt đối và tác giả `a[data-e2e=search-card-user-link]`; trang hashtag thẻ
`div[data-e2e=challenge-item]`, tác giả `a[data-e2e=challenge-item-avatar]`, mô tả `challenge-item-desc`;
thanh trái `a[data-e2e=nav-profile]` (href "/@" khi chưa đăng nhập). Mẫu quét chỉ đọc nên chạy được cả khi
chưa đăng nhập (đóng hộp login-modal bằng Escape); mẫu có thao tác thì đòi đăng nhập.

Chọn phần tử: role + nhãn trợ năng tiếng Việt/tiếng Anh, kèm `data-e2e` (thuộc tính kiểm thử cố định
của TikTok, không phải class băm). Mọi cú bấm công khai đi qua tien_ich_web.bam_cong_khai.
Ô bình luận/ô chat LIVE của TikTok gửi bằng Enter, nên chữ luôn được gộp thành một dòng trước khi gõ.
"""
from __future__ import annotations

import re
import time

import unicodedata
import urllib.parse
from typing import List, Optional

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "tiktok"
URL_TAI_LEN = "https://www.tiktok.com/tiktokstudio/upload"
URL_FYP = "https://www.tiktok.com/foryou"
URL_HO_SO = "https://www.tiktok.com/profile"
GIOI_HAN_BL = 150


# --------------------------------------------------------------------------- phần tử dùng chung

def _nut_thich(page):
    return w.tim(page, timeout_ms=8000, ten=["Thích video", "Like video", "Bỏ thích video", "Unlike video"],
                 chua=True, css=["button:has([data-e2e='like-icon'])", "button:has([data-e2e='browse-like-icon'])",
                                 "[data-e2e='like-icon']", "[data-e2e='browse-like-icon']"])


def _nut_luu(page):
    return w.tim(page, timeout_ms=6000, ten=["Thêm vào Yêu thích", "Add to Favorites", "Yêu thích", "Favorites",
                                             "Xoá khỏi Yêu thích", "Remove from Favorites"], chua=True,
                 css=["button:has([data-e2e='undefined-icon'])", "button:has([data-e2e='browse-favorite-icon'])",
                      "[data-e2e='undefined-icon']", "[data-e2e='favorite-icon']"])


def _da_bat(loc) -> bool:
    return w.nhan_bat(_nut_cha(loc), "Bỏ thích video", "Unlike video", "Xoá khỏi Yêu thích",
                      "Remove from Favorites")


def _nut_cha(loc):
    """data-e2e thường gắn trên <span> trong <button>; trạng thái aria-pressed nằm ở button."""
    try:
        if loc.evaluate("e => e.tagName") != "BUTTON":
            cha = loc.locator("xpath=ancestor::button[1]")
            if cha.count():
                return cha.first
    except Exception:
        pass
    return loc


def _o_binh_luan(nc, timeout_ms=8000):
    page = nc.page
    cands = w.ung_vien(page, role="textbox", ten=["Thêm bình luận", "Add comment", "Nói gì đó", "Say something",
                                                  "Thêm bình luận...", "Add comment..."], chua=True,
                       css=["[data-e2e='comment-input'] [contenteditable='true']",
                            "[data-e2e='comment-input'] [contenteditable]",
                            "div[contenteditable='plaintext-only']"])
    o = w.dau_tien_thay(cands, timeout_ms)
    if o:
        return o
    # Bảng bình luận đóng: mở bằng biểu tượng bình luận (không công khai)
    mo = w.tim(page, timeout_ms=3000, ten=["Đọc hoặc thêm bình luận", "Read or add comments", "Bình luận",
                                           "Comments"], chua=True,
               css=["[data-e2e='comment-icon']", "[data-e2e='browse-comment-icon']"])
    if mo:
        nc.tay.bam(mo)
        nc.tay.nghi(0.8, 1.6)
        return w.dau_tien_thay(cands, timeout_ms)
    return None


def _nut_gui_bl(page):
    return w.tim(page, timeout_ms=4000, ten=["Đăng", "Post", "Gửi", "Send"],
                 css=["[data-e2e='comment-post']"])


def _binh_luan(nc, text: str) -> bool:
    o = _o_binh_luan(nc)
    if not o:
        raise LoiKyNang("không thấy ô bình luận dưới video")
    return w.gui_noi_dung(nc, o, w.mot_dong(text), nut_gui=lambda: _nut_gui_bl(nc.page), enter_gui=True,
                          mo_ta="Đăng bình luận TikTok")


def _mo(nc, url: str) -> None:
    nc.mo(url)
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)


# --------------------------------------------------------------------------- tt_dang_video_kho

def _kiem_bai_video(bai: dict) -> str:
    if not w.loc_tep(bai.get("tep_cuc_bo") or [], w.DUOI_VIDEO):
        return "bài không có video (TikTok chỉ nhận video ở mẫu này)"
    return ""


class DungTruocDang(w.LoiDang):
    """Chạy thử đã đi hết các bước (tải tệp, mô tả, gắn sản phẩm...) và dừng ngay trước nút Đăng."""

    def __init__(self):
        super().__init__("chạy thử: dừng trước nút Đăng", False)


def _ten_tep(p: str) -> str:
    return str(p).split("/")[-1].split(chr(92))[-1]


def _cho_o_mo_ta(page, timeout_ms: int = 120000):
    return w.dau_tien_thay(w.ung_vien(page, role="textbox", ten=["Mô tả", "Description", "Caption"], chua=True,
                                      css=["[data-e2e='caption_container'] [contenteditable='true']",
                                           ".public-DraftEditor-content", "div[contenteditable='true']"]),
                           timeout_ms)


def _go_mo_ta(nc, o_mo_ta, mo_ta: str) -> None:
    if mo_ta:
        nc.nhat_ky(f"Gõ mô tả ({len(mo_ta)} ký tự)")
        w.go_vao(nc, o_mo_ta, mo_ta[:2200], xoa_truoc=True)
        nc.page.keyboard.press("Escape")   # đóng gợi ý #hashtag/@nhắc nếu đang mở
        nc.tay.nghi(0.8, 1.6)
    else:
        nc.nhat_ky("Bài không có chữ: để trống mô tả")


def _cho_nut_dang(nc, phut: float = 20, mo_ta: str = "video"):
    """Chờ nút Đăng của TikTok Studio bật (tệp đã tải xong). Trả locator nút; quá hạn thì LoiDang."""
    page = nc.page
    han = time.monotonic() + phut * 60

    def _nut_dang():
        return w.dau_tien_thay(w.ung_vien(page, ten=["Đăng", "Post"],
                                          css=["button[data-e2e='post_video_button']"]), 2000)
    nc.nhat_ky(f"Chờ TikTok tải {mo_ta} xong (nút Đăng bật)")
    while time.monotonic() < han:
        w.kiem_chan(nc)
        nut = _nut_dang()
        if nut and nut.is_enabled() and nut.get_attribute("aria-disabled") != "true" \
                and nut.get_attribute("data-disabled") != "true":
            nc.nhat_ky("Nút Đăng đã bật")
            return nut
        if nc.nen_dung():
            raise w.LoiDang(f"đợt bị huỷ khi đang tải {mo_ta}", False)
        time.sleep(3)
    raise w.LoiDang(f"quá {phut:g} phút {mo_ta} chưa tải xong hoặc nút Đăng vẫn khoá", False)


def _bam_dang(nc, nut, tt: w.TrangThaiDang, mo_ta: str = "Đăng video TikTok") -> str:
    """Bấm Đăng (cổng công khai), xử lý hộp xác nhận, chờ trang rời màn tải lên. Chạy thử -> DungTruocDang."""
    page = nc.page
    nc.tay.nghi(1.5, 3.5)
    if nc.chay_thu:
        nc.nhat_ky(f"Chạy thử: mọi bước đã xong, KHÔNG bấm '{mo_ta}'")
        raise DungTruocDang()
    tt.da_bam = True
    if not w.bam_cong_khai(nc, nut, mo_ta):
        raise DungTruocDang()
    # Hộp kiểm tra nội dung / xác nhận đăng
    for _ in range(3):
        xn = w.dau_tien_thay(w.ung_vien(page, ten=["Đăng ngay", "Post now", "Vẫn đăng", "Post anyway",
                                                   "Tiếp tục đăng", "Continue to post"]), 4000)
        if not xn:
            break
        nc.nhat_ky("Xử lý hộp kiểm tra nội dung: bấm đăng tiếp")
        w.bam_cong_khai(nc, xn, "Xác nhận đăng")
        nc.tay.nghi(1.0, 2.0)
    roi = w.cho(lambda: "/upload" not in (page.url or ""), 180, 1.5)
    w.kiem_chan(nc)
    if not roi:
        raise w.LoiDang("đã bấm Đăng nhưng trang chưa rời màn tải lên (TikTok có thể đang báo lỗi)", True)
    nc.nhat_ky(f"Trang đã rời màn tải lên: {page.url[:80]}")
    return page.url


def _dang_video(nc, bai: dict, tt: w.TrangThaiDang, gio_hang: dict = None) -> str:
    """Đăng một video lên TikTok Studio. gio_hang={"ten": tên/ID sản phẩm, "ten_hien_thi": ...} thì gắn
    sản phẩm TikTok Shop trước khi bấm Đăng."""
    page = nc.page
    video = w.loc_tep(bai.get("tep_cuc_bo") or [], w.DUOI_VIDEO)[0]
    mo_ta = str(bai.get("noi_dung") or bai.get("tieu_de") or "").strip()
    _mo(nc, URL_TAI_LEN)
    o_tep = page.locator("input[type='file'][accept*='video'], input[type='file']")
    if not w.cho(lambda: o_tep.count() > 0, 30):
        _chan_doan(nc, "Không thấy ô chọn video", ["input[type='file']", "button", "iframe"])
        raise w.LoiDang("không thấy ô chọn video ở TikTok Studio", False)
    nc.nhat_ky(f"Chọn video {_ten_tep(video)}")
    o_tep.first.set_input_files(video)
    o_mo_ta = _cho_o_mo_ta(page)
    if not o_mo_ta:
        raise w.LoiDang("tải video lên nhưng không hiện ô mô tả", False)
    _go_mo_ta(nc, o_mo_ta, mo_ta)
    _dat_cong_khai(nc)
    nut = _cho_nut_dang(nc)
    if gio_hang:
        _gan_san_pham(nc, str(gio_hang.get("ten") or ""), str(gio_hang.get("ten_hien_thi") or ""))
        nut = _cho_nut_dang(nc, 2)
    return _bam_dang(nc, nut, tt, "Đăng video TikTok")


def _dat_cong_khai(nc) -> None:
    page = nc.page
    chon = w.tim(page, timeout_ms=3000, role="combobox", ten=["Ai có thể xem", "Who can watch"], chua=True)
    if not chon:
        nc.nhat_ky("Không thấy ô quyền xem, giữ mặc định của TikTok")
        return
    if w.re_chua("Mọi người", "Everyone", "Công khai", "Public").search(chon.inner_text() or ""):
        return
    nc.tay.bam(chon)
    nc.tay.nghi(0.5, 1.0)
    opt = w.tim(page, timeout_ms=3000, role="option", ten=["Mọi người", "Everyone", "Công khai", "Public"], chua=True)
    if opt:
        nc.tay.bam(opt)
        nc.nhat_ky("Đặt quyền xem: Mọi người")


def tt_dang_video_kho(nc) -> str:
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    return w.chay_kho(nc, "dang_video", nc.ts.get("so_bai", 1), "Đăng video TikTok",
                      lambda bai, tt: _dang_video(nc, bai, tt), kiem_bai=_kiem_bai_video)


# --------------------------------------------------------------------------- tt_tuong_tac_video

def tt_tuong_tac_video(nc) -> str:
    ts = nc.ts
    links = w.ds_dong(ts.get("links"))
    cau = w.ds_dong(ts.get("cau_binh_luan"))
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(links[0] if links else URL_FYP)
    nc.kiem_dang_nhap()
    for link in links:
        if nc.nen_dung():
            break
        try:
            _mo(nc, link)
            nc.tay.luot(1)
            if ts.get("thich", True) and w.con_luot(nc, dem, "thich"):
                nut = _nut_thich(nc.page)
                if not nut:
                    w.bao(nc, dem, "thich", "loi", "không thấy nút tim", link=link)
                else:
                    w.bam_va_xac_nhan(nc, dem, "thich", _nut_cha(nut), _da_bat, "thả tim video", link)
            if cau and w.con_luot(nc, dem, "binh_luan"):
                k = w.khoa(NT, "binh_luan", link)
                if nc.da_lam(k):
                    w.bao(nc, dem, "binh_luan", "bo_qua", "nick đã bình luận video này", link=link)
                else:
                    c = w.cat_gioi_han(w.mot_dong(rng.choice(cau)), GIOI_HAN_BL)
                    if nc.chay_thu:
                        w.bao_thu(nc, dem, "binh_luan", f"Chạy thử: sẽ bình luận \"{c}\"", link=link)
                    elif _binh_luan(nc, c):
                        nc.ghi_da_lam(k)
                        w.bao(nc, dem, "binh_luan", "thanh_cong", f"Bình luận \"{c[:60]}\" đã hiện", link=link)
                        nc.nghi_thao_tac()
                    else:
                        w.bao(nc, dem, "binh_luan", "loi", "đã gửi nhưng chưa thấy bình luận hiện", link=link)
            if ts.get("luu") and w.con_luot(nc, dem, "luu"):
                nut = _nut_luu(nc.page)
                if not nut:
                    w.bao(nc, dem, "luu", "loi", "không thấy nút Lưu/Yêu thích", link=link)
                else:
                    w.bam_va_xac_nhan(nc, dem, "luu", _nut_cha(nut), _da_bat, "lưu video", link)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "binh_luan" if cau else "thich", e, link)
    return w.ket_thuc(nc, dem, "Tương tác video TikTok")


# --------------------------------------------------------------------------- tt_binh_luan_live

def tt_binh_luan_live(nc) -> str:
    ts = nc.ts
    links = w.ds_dong(ts.get("links"))
    rng = w.rng_nick(nc)
    cau = [w.cat_gioi_han(w.mot_dong(c), GIOI_HAN_BL) for c in w.ds_dong(ts.get("cau_binh_luan"))]
    rng.shuffle(cau)
    so_cau = int(ts.get("so_cau", 5) or 5)
    gian = float(ts.get("gian_cach", 40) or 40)
    dem = w.Dem()
    hd = "binh_luan_live"
    nc.mo(links[0] if links else URL_FYP)
    nc.kiem_dang_nhap()
    if not links or not cau:
        raise LoiKyNang("thiếu link LIVE hoặc câu bình luận")
    con_song = list(links)
    dang_mo = ""
    for i in range(so_cau):
        if nc.nen_dung() or not con_song or not w.con_luot(nc, dem, hd):
            break
        url = con_song[i % len(con_song)]          # xoay vòng các phiên LIVE
        c = cau[i % len(cau)]
        try:
            if url != dang_mo:
                _mo(nc, url)
                dang_mo = url
            if w.co_chu(nc.page, "LIVE đã kết thúc", "LIVE has ended", "Phiên LIVE đã kết thúc"):
                w.bao(nc, dem, hd, "bo_qua", "LIVE đã kết thúc, bỏ link này", link=url)
                con_song.remove(url)
                continue
            if nc.chay_thu:
                w.bao_thu(nc, dem, hd, f"Chạy thử: sẽ gửi \"{c}\" vào LIVE", link=url)
            else:
                o = _o_binh_luan(nc, 15000)
                if not o:
                    raise LoiKyNang("không thấy ô chat LIVE")
                if w.gui_noi_dung(nc, o, c, nut_gui=lambda: _nut_gui_bl(nc.page), enter_gui=True,
                                  mo_ta="Gửi bình luận LIVE", giay_xac_nhan=12):
                    w.bao(nc, dem, hd, "thanh_cong", f"Đã gửi \"{c[:60]}\" (thấy trong khung chat)", link=url)
                else:
                    w.bao(nc, dem, hd, "loi", "gửi nhưng không thấy câu hiện trong khung chat", link=url)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, url)
        if i + 1 < so_cau and w.nghi_co_dung(nc, gian * rng.uniform(0.7, 1.4)):
            break
    return w.ket_thuc(nc, dem, "Bình luận LIVE TikTok")


# --------------------------------------------------------------------------- tt_nuoi_nick

def tt_nuoi_nick(nc) -> str:
    phut = float(nc.ts.get("phut", 10) or 10)
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(URL_FYP)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    han = time.monotonic() + phut * 60
    so_video = 0
    while time.monotonic() < han and not nc.nen_dung():
        w.kiem_chan(nc)
        so_video += 1
        if w.nghi_co_dung(nc, rng.uniform(5, 20)):
            break
        if rng.random() < 0.25 and w.con_luot(nc, dem, "thich"):
            loc = nc.page.locator("button:has([data-e2e='like-icon']), button:has([data-e2e='browse-like-icon'])")
            nut = (w.trong_khung(nc.page, loc) or [None])[0]
            if nut is not None:
                w.bam_va_xac_nhan(nc, dem, "thich", nut, _da_bat, "thả tim video đang xem", nc.page.url)
        nc.page.keyboard.press("ArrowDown")      # sang video kế (cuộn, không công khai)
        nc.tay.nghi(0.8, 1.8)
    w.bao(nc, dem, "thich", "thong_tin", f"Nuôi nick: xem {so_video} video trong {phut:g} phút, "
                                             f"thả tim {dem.ok.get('thich', 0)}")
    return f"{'Chạy thử - ' if nc.chay_thu else ''}Nuôi nick TikTok: {so_video} video, {dem.tom_tat()}."


# --------------------------------------------------------------------------- tt_tra_loi_binh_luan

_JS_BINH_LUAN = """() => {
  const out = [];
  document.querySelectorAll("[data-e2e='comment-level-1']").forEach((e, i) => {
    let c = e, a = null;
    for (let k = 0; k < 6 && c; k++) {
      a = c.querySelector("a[href*='/@']");
      if (a) break;
      c = c.parentElement;
    }
    const href = a ? a.getAttribute('href') : '';
    const m = href.match(/\\/@([^/?#]+)/);
    out.push({i, tac_gia: m ? m[1] : '', chu: (e.innerText || '').trim()});
  });
  return out;
}"""


def _ten_chu_nick(page) -> str:
    m = re.search(r"tiktok\.com/@([^/?#]+)", page.url or "")
    return m.group(1) if m else ""


def _tra_loi_bl(nc, tac_gia: str, chu: str, text: str) -> bool:
    """Bấm 'Trả lời' dưới đúng bình luận (tìm theo tác giả + đầu câu), gõ, đăng, đọc lại."""
    page = nc.page
    goc = page.locator("[data-e2e='comment-level-1']").filter(has_text=chu[:30])
    if not goc.count():
        raise LoiKyNang(f"không tìm lại được bình luận của @{tac_gia}")
    o = goc.first
    for _ in range(4):        # leo lên khối bình luận để tìm nút Trả lời
        nut = w.dau_tien_thay(w.ung_vien(o, ten=["Trả lời", "Reply"], chu=["Trả lời", "Reply"],
                                         css=["[data-e2e='comment-reply-1']"]), 800)
        if nut:
            break
        o = o.locator("xpath=..")
    else:
        nut = None
    if not nut:
        raise LoiKyNang("không thấy nút Trả lời dưới bình luận")
    nc.tay.bam(nut)            # mở ô trả lời (chưa công khai)
    nc.tay.nghi(0.6, 1.2)
    return _binh_luan(nc, text)


def tt_tra_loi_binh_luan(nc) -> str:
    ts = nc.ts
    sp = str(ts.get("san_pham") or "")
    so_video = int(ts.get("so_video", 3) or 3)
    dem = w.Dem()
    hd = "tra_loi_binh_luan"
    nc.mo(URL_HO_SO)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    chu_nick = _ten_chu_nick(nc.page)
    videos = []
    for a in nc.page.locator("a[href*='/video/']").all()[:40]:
        h = (a.get_attribute("href") or "").split("?")[0]
        if h and h not in videos and (not chu_nick or f"/@{chu_nick}/" in h):
            videos.append(h if h.startswith("http") else "https://www.tiktok.com" + h)
        if len(videos) >= so_video:
            break
    nc.nhat_ky(f"Nick @{chu_nick or '?'}: xét {len(videos)} video gần nhất")
    for v in videos:
        if nc.nen_dung() or not w.con_luot(nc, dem, hd):
            break
        try:
            _mo(nc, v)
            _o_binh_luan(nc, 5000)        # mở bảng bình luận nếu đang đóng
            cap = ""
            c = w.tim(nc.page, timeout_ms=3000, css=["[data-e2e='browse-video-desc']", "[data-e2e='video-desc']"])
            if c:
                cap = c.inner_text()[:1000]
            ds = nc.page.evaluate(_JS_BINH_LUAN) or []
            for bl in ds:
                if nc.nen_dung() or not w.con_luot(nc, dem, hd):
                    break
                if not bl.get("chu") or (chu_nick and bl.get("tac_gia") == chu_nick):
                    continue
                k = w.khoa(NT, "tra_loi", v, bl.get("tac_gia"), w.bam_chuoi(bl["chu"]))
                if nc.da_lam(k):
                    continue
                kq = w.lay_ai(nc, "tra_loi_binh_luan", {
                    "bai_cua_nick": True, "bai": {"chu": cap, "link": v},
                    "binh_luan": {"tac_gia": bl.get("tac_gia"), "chu": bl["chu"]}, "san_pham_id": sp})
                if kq.get("can_hoi_chu"):
                    nc.ghi_da_lam(k)
                    w.bao(nc, dem, hd, "bo_qua", f"Câu hỏi chưa có trong Kiến thức, đã chuyển bạn trả lời: "
                                                 f"{bl['chu'][:80]}", link=v)
                    continue
                tg, chu = bl.get("tac_gia") or "", bl["chu"]

                def _dang(nd, tg=tg, chu=chu):
                    if not _tra_loi_bl(nc, tg, chu, w.cat_gioi_han(nd, GIOI_HAN_BL)):
                        raise LoiKyNang("đã gửi trả lời nhưng chưa thấy hiện")
                    return v
                w.noi_dung_ai(nc, dem, hd, loai="tra_loi", noi_dang=NT, link_goc=w.gan_muc_tieu(v, tg, chu),
                              bai_goc=cap, ly_do=f"@{tg} bình luận: {chu[:150]}",
                              noi_dung=w.cat_gioi_han(w.mot_dong(kq.get("noi_dung") or ""), GIOI_HAN_BL),
                              khoa_lap=k, dang=_dang, san_pham_id=sp)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, v)
    return w.ket_thuc(nc, dem, "Trả lời bình luận TikTok")


# --------------------------------------------------------------------------- hàm thuần (có test)

_HE_SO = {"k": 1e3, "n": 1e3, "ng": 1e3, "nghìn": 1e3, "ngàn": 1e3,
          "m": 1e6, "tr": 1e6, "triệu": 1e6, "trieu": 1e6,
          "b": 1e9, "t": 1e9, "tỷ": 1e9, "tỉ": 1e9, "ty": 1e9}


def doc_so(s) -> Optional[int]:
    """Số lượt kiểu TikTok -> số nguyên: '1.2M' 1200000, '12,3K' 12300, '1,2 Tr' 1200000, '45,6 N' 45600,
    '1.234' 1234, '987 lượt xem' 987. Không có số -> None."""
    t = unicodedata.normalize("NFC", str(s or "")).replace(" ", " ").strip().lower()
    m = re.search(r"(\d+(?:[.,\s]\d+)*)\s*([^\W\d_]+)?", t)
    if not m:
        return None
    so = re.sub(r"\s+", "", m.group(1))
    he = _HE_SO.get((m.group(2) or "").rstrip("."), 1)
    try:
        if he > 1:
            so = so.replace(",", ".")
            if so.count(".") > 1:
                so = so.replace(".", "", so.count(".") - 1)
            return int(round(float(so) * he))
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", so):
            return int(re.sub(r"[.,]", "", so))
        return int(round(float(so.replace(",", "."))))
    except ValueError:
        return None


def ten_tiktok(s) -> str:
    """'@Shop.A', 'https://www.tiktok.com/@shop.a?lang=vi', 'shop.a' -> 'shop.a' (chữ thường). Sai -> ''."""
    s = str(s or "").strip()
    m = re.search(r"tiktok\.com/@([A-Za-z0-9._-]+)", s) or re.match(r"^@?([A-Za-z0-9._-]{2,40})/?$", s)
    return m.group(1).lower() if m else ""


def link_video(h) -> str:
    """Link video/ảnh TikTok chuẩn (tuyệt đối, bỏ tham số); không phải link video -> ''."""
    m = re.search(r"(/@[^/?#\s]+/(?:video|photo)/\d+)", str(h or ""))
    return "https://www.tiktok.com" + m.group(1) if m else ""


def url_tim(tu_khoa: str) -> str:
    return "https://www.tiktok.com/search/video?q=" + urllib.parse.quote(str(tu_khoa or "").strip())


def url_quet(kieu: str, vao: str) -> str:
    """kieu: tim_kiem | hashtag | ho_so. Link https dán thẳng thì giữ nguyên."""
    vao = str(vao or "").strip()
    if not vao:
        return ""
    if vao.startswith("https://"):
        return vao
    if kieu == "hashtag":
        return "https://www.tiktok.com/tag/" + urllib.parse.quote(vao.lstrip("#").strip())
    if kieu == "ho_so":
        ten = ten_tiktok(vao)
        return f"https://www.tiktok.com/@{ten}" if ten else ""
    return url_tim(vao)


_RE_GIA = re.compile(r"(?:₫|đ|vnđ|vnd|\$|usd)\s?\d[\d.,]*|\d[\d.,]*\s?(?:₫|đ\b|vnđ|vnd|k\b)", re.I)


def tach_gia(s) -> str:
    """Chuỗi giá đầu tiên trong chữ: 'Áo 199.000₫' -> '199.000₫', '$12.99 Shirt' -> '$12.99'."""
    m = _RE_GIA.search(str(s or ""))
    return m.group(0).strip() if m else ""


def _chuan(s) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s or ""))).strip().casefold()


def chon_san_pham(hang: list, ten: str) -> Optional[dict]:
    """Chọn dòng sản phẩm khớp `ten` (tên hoặc ID): đúng cả dòng -> chứa -> dòng bị TikTok cắt '...'
    nằm trong tên. Không khớp -> None (không bao giờ gắn bừa sản phẩm đầu danh sách)."""
    q = _chuan(ten)
    if not q:
        return None
    for h in hang:
        if any(_chuan(d) == q for d in str(h.get("chu") or "").splitlines()):
            return dict(h, khop="dung")
    for h in hang:
        if q in _chuan(h.get("chu")):
            return dict(h, khop="chua")
    for h in hang:
        for d in str(h.get("chu") or "").splitlines():
            d = _chuan(d).rstrip(".…").strip()
            if len(d) >= 8 and d in q:
                return dict(h, khop="gan_dung")
    return None


# --------------------------------------------------------------------------- đọc trang (chỉ đọc)

_JS_CHAN_DOAN = """(sels) => sels.map(s => { try { return s + '=' + document.querySelectorAll(s).length; }
  catch (e) { return s + '=?'; } }).join(', ')"""


def _chan_doan(nc, mo_ta: str, sels) -> None:
    """Ghi nhật ký khi thiếu phần tử: URL, tiêu đề và số ứng viên của từng bộ chọn, để test thật biết dừng ở đâu."""
    page = nc.page
    try:
        dem = page.evaluate(_JS_CHAN_DOAN, list(sels))
    except Exception as e:
        dem = f"không đọc được ({type(e).__name__})"
    try:
        td = page.title()[:60]
    except Exception:
        td = ""
    nc.nhat_ky(f"{mo_ta}: URL {str(getattr(page, 'url', ''))[:140]} | tiêu đề '{td}' | {dem}"[:600])


_JS_TEN_NICK = r"""() => {
  const ds = [...document.querySelectorAll("a[href*='/@']")];
  const uu = ds.find(a => (a.getAttribute('data-e2e') || '').includes('nav-profile') || a.closest("[data-e2e*='nav-profile']"))
    || ds.find(a => /(Hồ sơ|Profile|Trang cá nhân)/i.test((a.getAttribute('aria-label') || '') + ' ' + (a.innerText || '')));
  const m = uu ? (uu.getAttribute('href') || '').match(/\/@([^\/?#]+)/) : null;
  return m ? m[1] : '';
}"""


def _ten_nick(nc) -> str:
    """@ của nick đang đăng nhập, đọc từ link Hồ sơ ở thanh trái (a[data-e2e=nav-profile]). Chưa đăng nhập -> ''."""
    try:
        return ten_tiktok(nc.page.evaluate(_JS_TEN_NICK) or "")
    except Exception:
        return ""


def _mo_doc(nc, url: str) -> None:
    """Mở trang để CHỈ ĐỌC: chưa đăng nhập vẫn đọc được thẻ video, nên hộp đăng nhập chỉ bị đóng (Escape)
    và ghi nhật ký; captcha / checkpoint / quá nhanh vẫn dừng như thường."""
    nc.mo(url)
    nc.tay.nghi(2.0, 4.0)
    try:
        w.kiem_chan(nc)
    except LoiKyNang as e:
        if getattr(e, "ma", None) != "dang_xuat":
            raise
        nc.nhat_ky("TikTok đang hiện hộp đăng nhập: đóng (Escape) và chỉ đọc dữ liệu công khai")
        try:
            nc.page.keyboard.press("Escape")
        except Exception:
            pass
        nc.tay.nghi(0.8, 1.5)


# Thẻ video ở trang tìm kiếm (search_video-item), hashtag (challenge-item), hồ sơ (user-post-item).
_JS_THE_VIDEO = r"""() => {
  const out = []; const seen = new Set();
  const re = /\/@([^\/?#]+)\/(video|photo)\/(\d+)/;
  const KHOI = "[data-e2e='search_video-item'],[data-e2e='search_top-item'],[data-e2e='challenge-item'],"
    + "[data-e2e='user-post-item'],[data-e2e='user-liked-item']";
  const chu = (k, s) => { const e = k.querySelector(s); return e ? (e.innerText || e.textContent || '').trim() : ''; };
  for (const a of document.querySelectorAll("a[href*='/video/'], a[href*='/photo/']")) {
    const h = a.getAttribute('href') || ''; const m = h.match(re);
    if (!m || seen.has(m[3])) continue;
    seen.add(m[3]);
    const k = a.closest(KHOI) || (a.parentElement && a.parentElement.parentElement) || a;
    const tg = k.querySelector("a[data-e2e='search-card-user-link'], a[data-e2e='challenge-item-avatar']");
    const mt = tg ? (tg.getAttribute('href') || '').match(/\/@([^\/?#]+)/) : null;
    const img = k.querySelector('img[alt]');
    const dong = (k.innerText || '').split('\n').map(x => x.trim()).filter(x => /^\d[\d.,]*\s*[KMBNTr]?$/i.test(x));
    out.push({link: m[0], tac_gia: (mt ? mt[1] : m[1]), id: m[3],
      khoi: k.getAttribute('data-e2e') || '',
      xem: chu(k, "[data-e2e='video-views']"),
      so_the: dong.length ? dong[0] : '',
      thich: chu(k, "[data-e2e='search-card-like-container']"),
      chu: (chu(k, "[data-e2e='challenge-item-desc']") || chu(k, "[data-e2e='search-card-video-caption']")
            || chu(k, "[data-e2e='search-card-desc']") || chu(k, "[data-e2e='video-desc']")
            || (img ? img.getAttribute('alt') || '' : '')).slice(0, 1000)});
  }
  return out;
}"""

_SEL_THE = ["[data-e2e='search_video-item']", "[data-e2e='challenge-item']", "[data-e2e='user-post-item']",
            "a[href*='/video/']", "[data-e2e='login-modal']", "[data-e2e='search-card-user-link']"]


def _gom_video(nc, toi_da: int, mo_ta: str, tac_gia: str = "", luot_toi_da: int = 10) -> List[dict]:
    """Cuộn trang đang mở, gom thẻ video (link chuẩn, tác giả, số trên thẻ, mô tả). tac_gia: chỉ giữ video
    của @ đó (trang hồ sơ)."""
    page = nc.page
    out, da, dung_yen = [], set(), 0
    for lan in range(luot_toi_da):
        if nc.nen_dung() or len(out) >= toi_da:
            break
        try:
            ds = page.evaluate(_JS_THE_VIDEO) or []
        except Exception as e:
            nc.nhat_ky(f"{mo_ta}: lỗi đọc thẻ video ({type(e).__name__})")
            ds = []
        moi = 0
        for t in ds:
            link = link_video(t.get("link"))
            if not link or link in da:
                continue
            t["tac_gia"] = ten_tiktok(t.get("tac_gia")) or ten_tiktok(link)
            if tac_gia and t["tac_gia"] != tac_gia:
                continue
            da.add(link)
            t["link"] = link
            out.append(t)
            moi += 1
            if len(out) >= toi_da:
                break
        dung_yen = 0 if moi else dung_yen + 1
        if dung_yen >= 3 or len(out) >= toi_da:
            break
        nc.tay.luot(2)
        nc.tay.nghi(1.0, 2.5)
    nc.nhat_ky(f"{mo_ta}: gom được {len(out)} video")
    if not out:
        _chan_doan(nc, f"{mo_ta}: không thấy thẻ video nào", _SEL_THE)
    return out


_JS_DOC_VIDEO = r"""() => {
  const r = {nguon: 'dom', tac_gia: '', chu: '', xem: '', thich: '', binh_luan: '', ngay: '', sp_json: [], sp_dom: []};
  const txt = (s) => { const e = document.querySelector(s); return e ? (e.innerText || '').trim() : ''; };
  let it = null;
  try {
    const s = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
    if (s) { const d = JSON.parse(s.textContent); const v = (d.__DEFAULT_SCOPE__ || {})['webapp.video-detail'];
             it = v && v.itemInfo && v.itemInfo.itemStruct; }
  } catch (e) {}
  if (!it) { try { const s = document.getElementById('SIGI_STATE');
    if (s) { const d = JSON.parse(s.textContent); const im = d.ItemModule || {}; const k = Object.keys(im)[0]; it = k ? im[k] : null; }
  } catch (e) {} }
  if (it) {
    r.nguon = 'json';
    r.tac_gia = (it.author && (it.author.uniqueId || (typeof it.author === 'string' ? it.author : ''))) || '';
    r.chu = it.desc || '';
    const st = it.statsV2 || it.stats || {};
    r.xem = String(st.playCount ?? ''); r.thich = String(st.diggCount ?? ''); r.binh_luan = String(st.commentCount ?? '');
    if (it.createTime) { try { r.ngay = new Date(Number(it.createTime) * 1000).toISOString(); } catch (e) {} }
    const gap = r.sp_json;
    const walk = (o, d) => {
      if (o === null || o === undefined || d > 7 || gap.length > 20) return;
      if (typeof o === 'string') { const t = o.trim();
        if ((t[0] === '{' || t[0] === '[') && t.length < 300000) { try { walk(JSON.parse(t), d + 1); } catch (e) {} } return; }
      if (Array.isArray(o)) { o.forEach(x => walk(x, d + 1)); return; }
      if (typeof o !== 'object') return;
      const ten = o.title || o.product_name || o.productName || o.keyword || o.name || '';
      const id = o.product_id || o.productId || o.item_id || '';
      let gia = o.format_price || o.formatPrice || o.price_str || o.real_price || o.min_price || '';
      if (!gia && o.price !== undefined) gia = (typeof o.price === 'object' && o.price)
          ? (o.price.format_price || o.price.real_price || o.price.price_str || o.price.min_price || '') : o.price;
      if (ten && (id || gia)) gap.push({ten: String(ten).slice(0, 200), gia: String(gia).slice(0, 60), id: String(id),
                                        link: String(o.seo_url || o.detail_url || o.product_url || '')});
      for (const k of Object.keys(o)) walk(o[k], d + 1);
    };
    for (const k of Object.keys(it)) if (/anchor|product|shop|commerce|ecom/i.test(k)) walk(it[k], 0);
  }
  r.chu = r.chu || txt("[data-e2e='browse-video-desc']") || txt("[data-e2e='video-desc']");
  r.tac_gia = r.tac_gia || txt("[data-e2e='browse-username']") || txt("[data-e2e='video-author-uniqueid']");
  r.thich = r.thich || txt("[data-e2e='like-count']") || txt("[data-e2e='browse-like-count']");
  r.binh_luan = r.binh_luan || txt("[data-e2e='comment-count']") || txt("[data-e2e='browse-comment-count']");
  if (!r.ngay) { const n = txt("[data-e2e='browser-nickname']"); const p = n.split('·'); if (p.length > 1) r.ngay = p[p.length - 1].trim(); }
  const SP = "a[href*='/view/product/'], a[href*='shop.tiktok.com'], a[href*='/shop/pdp'], a[href*='tiktok.com/shop'], "
    + "[data-e2e*='product'], [data-e2e*='anchor'], [data-e2e*='ecommerce']";
  document.querySelectorAll(SP).forEach(e => {
    const a = e.tagName === 'A' ? e : (e.closest('a') || e.querySelector('a'));
    r.sp_dom.push({ten: (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 200), link: a ? a.href : '',
                   de: e.getAttribute('data-e2e') || ''});
  });
  return r;
}"""

_RE_LINK_SP = re.compile(r"/view/product/|shop\.tiktok\.com|/shop/pdp|tiktok\.com/shop", re.I)
_RE_CHU_SP = re.compile(r"(Sản phẩm|Product|Mua ngay|Buy|Giỏ hàng|Shop|₫|\$)", re.I)


def _doc_video(nc) -> dict:
    """Đọc trang video đang mở: tác giả, mô tả, lượt xem/thích/bình luận, ngày đăng, sản phẩm giỏ hàng.
    Ưu tiên JSON nhúng (__UNIVERSAL_DATA_FOR_REHYDRATION__), thiếu thì đọc DOM."""
    try:
        r = nc.page.evaluate(_JS_DOC_VIDEO) or {}
    except Exception as e:
        nc.nhat_ky(f"Không đọc được trang video ({type(e).__name__}: {str(e)[:80]})")
        r = {}
    sp, da = [], set()
    for x in r.get("sp_json") or []:
        link = x.get("link") or (f"https://www.tiktok.com/view/product/{x['id']}" if x.get("id") else "")
        k = (x.get("id") or x.get("ten") or "").lower()
        if k and k not in da:
            da.add(k)
            g = str(x.get("gia") or "").strip()
            if g in ("0", "0.0", "0.00"):      # JSON neo sản phẩm thường để price 0 (soi thật 25/10)
                g = ""
            sp.append({"ten": x.get("ten", ""), "gia": g or tach_gia(x.get("ten")), "link": link})
    tho = r.get("sp_dom") or []
    for x in tho:
        de = str(x.get("de") or "")
        # 26.10.235: "recommend-list-item-container" chứa chuỗi "ecom" (r-ECOM-mend) làm mọi video bị báo có giỏ
        # hàng (soi thật 25/10). Chỉ nhận link sản phẩm, hoặc data-e2e có từ product/ecommerce/anchor đứng riêng.
        la_sp = bool(_RE_LINK_SP.search(x.get("link") or "")) or \
            bool(re.search(r"(^|[-_])(product|ecommerce)([-_]|$)", de, re.I)) or \
            (bool(re.search(r"(^|[-_])anchor([-_]|$)", de, re.I)) and bool(_RE_CHU_SP.search(x.get("ten") or "")))
        if not la_sp:
            continue
        m = re.search(r"/view/product/(\d+)", x.get("link") or "")
        k = (m.group(1) if m else (x.get("ten") or x.get("link") or "")).lower()
        if k and k not in da and not any(m and m.group(1) in (s.get("link") or "") for s in sp):
            da.add(k)
            sp.append({"ten": x.get("ten", ""), "gia": tach_gia(x.get("ten")), "link": x.get("link", "")})
    ra = {"tac_gia": ten_tiktok(r.get("tac_gia")) or ten_tiktok(nc.page.url), "chu": str(r.get("chu") or "")[:2200],
          "xem": doc_so(r.get("xem")), "thich": doc_so(r.get("thich")), "binh_luan": doc_so(r.get("binh_luan")),
          "ngay": str(r.get("ngay") or ""), "san_pham": sp, "nguon": r.get("nguon") or "dom"}
    nc.nhat_ky(f"Đọc video ({ra['nguon']}): @{ra['tac_gia'] or '?'}, xem {ra['xem']}, thích {ra['thich']}, "
               f"sản phẩm {len(sp)} (JSON {len(r.get('sp_json') or [])}, phần tử DOM {len(tho)}"
               + (f": {'; '.join((x.get('de') or '') + '=' + (x.get('ten') or '')[:30] for x in tho[:3])}" if tho else "")
               + ")")
    return ra


def _gui_csv(nc, ten_tep: str, cot, dong) -> str:
    """Ghi CSV (UTF-8 BOM) rồi gửi về MinMin để tải ở chi tiết việc. Trả câu mô tả nơi lưu."""
    p = w.ghi_csv(ten_tep, cot, dong)
    f = getattr(nc, "gui_tep_ket_qua", None)
    if not callable(f):
        return f"lưu trên máy: {p}"
    try:
        f(p)
        nc.nhat_ky(f"Đã gửi {p.name} về MinMin")
        return f"đã gửi tệp {p.name} về MinMin (tải ở chi tiết việc); bản trên máy: {p}"
    except Exception as e:
        nc.nhat_ky(f"Không gửi được CSV về MinMin: {e}")
        return f"CHƯA gửi được về MinMin ({str(e)[:120]}); bản trên máy: {p}"


_TEN_HD = {"binh_luan": "bình luận", "thich": "thả tim", "theo_doi": "theo dõi", "dang_video": "đăng",
           "quet": "quét", "luu": "lưu"}


def _ket(nc, dem: w.Dem, ten: str) -> str:
    """Câu tổng kết. Chạy thử nói rõ đã làm gì (không bấm gì công khai, sẽ làm bao nhiêu)."""
    if nc.chay_thu:
        se = ", ".join(f"{_TEN_HD.get(k, k)} {v}" for k, v in dem.thu.items() if v)
        return (f"Chạy thử - {ten}: không bấm gì công khai. "
                + (f"Sẽ làm: {se}" if se else "Không có mục nào đủ điều kiện để làm")
                + f"; bỏ qua {dem.tong(dem.bo)}, lỗi {dem.tong(dem.loi)}.")
    return w.ket_thuc(nc, dem, ten)


# --------------------------------------------------------------------------- kho: chạy thử đi tới nút Đăng

def _chay_kho_sau(nc, hd: str, so_bai: int, ten: str, dang_mot, kiem_bai) -> str:
    """Như w.chay_kho, nhưng CHẠY THỬ cũng đi thật mọi bước không công khai (tải tệp, mô tả, gắn sản phẩm)
    với MỘT bài, dừng trước nút Đăng rồi trả bài về hàng chờ."""
    if not nc.chay_thu:
        return w.chay_kho(nc, hd, so_bai, ten, dang_mot, kiem_bai=kiem_bai)
    dem = w.Dem()
    bai = nc.lay_kho()
    if not bai:
        w.bao(nc, dem, hd, "bo_qua", "Hết bài", ma="het_bai")
        return "Hết bài"
    bid = bai.get("id")
    nc.nhat_ky(f"Chạy thử với bài kho #{bid}: {str(bai.get('tieu_de') or bai.get('noi_dung') or '')[:60]}")
    ly_do = kiem_bai(bai)
    if ly_do:
        nc.xong_kho(bid, False, False, loi=ly_do)
        w.bao(nc, dem, hd, "loi", f"Bài #{bid}: {ly_do}")
        return _ket(nc, dem, ten)
    try:
        dang_mot(bai, w.TrangThaiDang())
        nc.xong_kho(bid, False, False, loi="Chạy thử: không đăng, trả bài về hàng chờ")
        w.bao_thu(nc, dem, hd, f"Chạy thử: bài kho #{bid} đi hết các bước, không đăng")
    except DungTruocDang:
        nc.xong_kho(bid, False, False, loi="Chạy thử: đã chuẩn bị xong tới nút Đăng, không đăng, trả bài về hàng chờ")
        w.bao_thu(nc, dem, hd, f"Chạy thử: bài kho #{bid} đã tải lên và điền đủ, dừng trước nút Đăng "
                               f"(bài về hàng chờ): {str(bai.get('noi_dung') or '')[:80]}")
    except Exception as e:
        nc.xong_kho(bid, False, False, loi=f"Chạy thử: {e}"[:300])
        if getattr(e, "ma", None) in w.MA_DUNG:
            raise LoiKyNang(str(e), e.ma)
        w.bao(nc, dem, hd, "loi", f"Chạy thử bài #{bid}: {e}")
    return _ket(nc, dem, ten)


# --------------------------------------------------------------------------- tt_dang_anh_kho (photo mode)

DUOI_ANH_TT = (".jpg", ".jpeg", ".png", ".webp")
ANH_TOI_THIEU, ANH_TOI_DA = 2, 35


def _anh_hop_le(tep) -> List[str]:
    return w.loc_tep(tep or [], DUOI_ANH_TT)


def _kiem_bai_anh(bai: dict) -> str:
    tep = bai.get("tep_cuc_bo") or []
    if w.loc_tep(tep, w.DUOI_VIDEO):
        return "bài có video: dùng mẫu 'Đăng video TikTok từ kho'"
    n = len(_anh_hop_le(tep))
    if n < ANH_TOI_THIEU:
        return f"bài có {n} ảnh jpg/png/webp, đăng dạng ảnh (slide) cần từ {ANH_TOI_THIEU} ảnh"
    return ""


def _o_tep_anh(nc):
    """Ô chọn tệp nhận ảnh. accept chỉ có video thì thử bấm tab/nút Ảnh rồi tìm lại."""
    page = nc.page

    def _tim():
        loc = page.locator("input[type='file']")
        acc = []
        for i in range(loc.count()):
            a = (loc.nth(i).get_attribute("accept") or "").lower()
            acc.append(a or "(trống)")
            if not a or "image" in a or ".jpg" in a or ".png" in a or ".jpeg" in a or ".webp" in a:
                return loc.nth(i), acc
        return None, acc
    if not w.cho(lambda: page.locator("input[type='file']").count() > 0, 30):
        _chan_doan(nc, "Không thấy ô chọn tệp", ["input[type='file']", "button", "iframe"])
        raise w.LoiDang("không thấy ô chọn tệp ở TikTok Studio", False)
    o, acc = _tim()
    nc.nhat_ky(f"Ô chọn tệp: {len(acc)} ô, accept = {acc}")
    if o is None:
        tab = w.tim(page, timeout_ms=4000, role="tab", ten=["Ảnh", "Photo", "Photos", "Hình ảnh", "Image", "Images"]) or \
            w.tim(page, timeout_ms=3000, ten=["Ảnh", "Photo", "Photos", "Đăng ảnh", "Upload photos", "Tải ảnh lên"],
                  chu=["Đăng ảnh", "Upload photos", "Tải ảnh lên"])
        if tab:
            nc.nhat_ky("Bấm tab/nút Ảnh để chuyển sang đăng ảnh")
            nc.tay.bam(tab)
            nc.tay.nghi(1.5, 3.0)
            o, acc = _tim()
            nc.nhat_ky(f"Sau khi chuyển tab, accept = {acc}")
    if o is None:
        raise w.LoiDang(f"TikTok Studio của nick này chưa cho tải ảnh lên (ô chọn tệp chỉ nhận: {', '.join(acc)}). "
                        "Chế độ ảnh có thể chưa mở cho tài khoản/khu vực này.", False)
    return o


def _dang_anh(nc, bai: dict, tt: w.TrangThaiDang) -> str:
    page = nc.page
    anh = _anh_hop_le(bai.get("tep_cuc_bo"))
    if len(anh) > ANH_TOI_DA:
        nc.nhat_ky(f"Bài có {len(anh)} ảnh, TikTok nhận tối đa {ANH_TOI_DA}: lấy {ANH_TOI_DA} ảnh đầu")
        anh = anh[:ANH_TOI_DA]
    mo_ta = str(bai.get("noi_dung") or bai.get("tieu_de") or "").strip()
    _mo(nc, URL_TAI_LEN)
    o = _o_tep_anh(nc)
    nc.nhat_ky(f"Chọn {len(anh)} ảnh: {', '.join(_ten_tep(a) for a in anh[:5])}{'...' if len(anh) > 5 else ''}")
    try:
        o.set_input_files(anh)
    except Exception as e:
        raise w.LoiDang(f"ô chọn tệp không nhận {len(anh)} ảnh cùng lúc ({str(e)[:120]})", False)
    o_mo_ta = _cho_o_mo_ta(page)
    if not o_mo_ta:
        _chan_doan(nc, "Tải ảnh xong nhưng không thấy ô mô tả", ["[contenteditable='true']", "input", "img"])
        raise w.LoiDang("tải ảnh lên nhưng không hiện ô mô tả", False)
    tieu_de = str(bai.get("tieu_de") or "").strip()
    if tieu_de:
        o_td = w.tim(page, timeout_ms=2000, role="textbox", ten=["Tiêu đề", "Title"], chua=True)
        if o_td:
            nc.nhat_ky(f"Gõ tiêu đề bài ảnh ({len(tieu_de[:90])} ký tự)")
            w.go_vao(nc, o_td, tieu_de[:90], xoa_truoc=True)
    _go_mo_ta(nc, o_mo_ta, mo_ta)
    _dat_cong_khai(nc)
    nut = _cho_nut_dang(nc, 10, "ảnh")
    return _bam_dang(nc, nut, tt, "Đăng bài ảnh TikTok")


def tt_dang_anh_kho(nc) -> str:
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    return _chay_kho_sau(nc, "dang_video", int(nc.ts.get("so_bai", 1) or 1), "Đăng ảnh TikTok từ kho",
                         lambda bai, tt: _dang_anh(nc, bai, tt), _kiem_bai_anh)


# --------------------------------------------------------------------------- giỏ hàng: gắn sản phẩm khi đăng

KHONG_SHOP = ("Tài khoản chưa gắn được sản phẩm: cần quyền TikTok Shop (người bán) hoặc Tiếp thị liên kết "
              "(TikTok Shop Affiliate) và sản phẩm đã có trong Showcase/cửa hàng. Mở TikTok Studio của nick, xem "
              "mục 'Thêm liên kết' có lựa chọn 'Sản phẩm' không")
_NUT_TIEP = ["Tiếp", "Tiếp theo", "Next", "Tiếp tục", "Continue"]
_NUT_XONG = ["Thêm", "Add", "Xác nhận", "Confirm", "Xong", "Done", "Lưu", "Save"]
_SEL_SP = ["[role='dialog']", "[aria-modal='true']", "input[type='radio']", "input[type='checkbox']",
           "[role='radio']", "[role='checkbox']", "input[type='search']", "button"]

_JS_NUT_THEM_LK = r"""() => {
  const reNhan = /^(Thêm liên kết|Add link|Add links|Liên kết|Link|Links|Sản phẩm|Products?)$/i;
  const reNut = /^\+?\s*(Thêm|Add|Thêm liên kết|Add link|Thêm sản phẩm|Add products?)$/i;
  const nhin = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  for (const e of document.querySelectorAll('body *')) {
    if (e.children.length > 2 || e.closest("[role='dialog']")) continue;
    const t = (e.innerText || '').trim();
    if (!t || t.length > 40 || !reNhan.test(t) || !nhin(e)) continue;
    let c = e;
    for (let k = 0; k < 5 && c; k++, c = c.parentElement) {
      const nut = [...c.querySelectorAll("button,[role='button']")].find(b => nhin(b)
        && reNut.test((b.innerText || b.getAttribute('aria-label') || '').trim()));
      if (nut) { const ma = 'mm-lk-' + Date.now(); nut.setAttribute('data-minmin', ma); return ma; }
    }
  }
  return '';
}"""

_JS_HANG_SP = r"""(goc) => {
  const nhin = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const out = [];
  goc.querySelectorAll("input[type='radio'], input[type='checkbox'], [role='radio'], [role='checkbox']").forEach((e, i) => {
    if (e.closest('thead')) return;
    let hang = e.closest("tr, [role='row'], li, label");
    if (!hang || (hang.innerText || '').trim().length < 2) {
      hang = e; for (let k = 0; k < 5 && hang.parentElement; k++) { hang = hang.parentElement; if ((hang.innerText || '').trim().length > 3) break; }
    }
    const chu = (hang.innerText || '').trim();
    if (!chu || /^(Chọn tất cả|Select all)$/i.test(chu)) return;
    const dich = nhin(e) ? e : hang;
    if (!nhin(dich)) return;
    const ma = 'mm-sp-' + i + '-' + Date.now();
    dich.setAttribute('data-minmin', ma);
    out.push({i, chu: chu.slice(0, 300), ma, da_chon: !!(e.checked || e.getAttribute('aria-checked') === 'true')});
  });
  return out;
}"""

_JS_DA_CHON = """e => { const i = e.matches("input, [role='radio'], [role='checkbox']") ? e
  : e.querySelector("input, [role='radio'], [role='checkbox']");
  return i ? !!(i.checked || i.getAttribute('aria-checked') === 'true') : null; }"""


def _hop_tren_cung(page):
    loc = page.locator("[role='dialog'], [aria-modal='true']")
    try:
        for i in range(loc.count() - 1, -1, -1):
            if loc.nth(i).is_visible():
                return loc.nth(i)
    except Exception:
        pass
    return None


def _bam_tiep(nc, goc) -> bool:
    nut = w.tim(goc, timeout_ms=2500, ten=_NUT_TIEP)
    if nut and nut.is_enabled() and nut.get_attribute("aria-disabled") != "true":
        nc.nhat_ky("Giỏ hàng: bấm 'Tiếp'")
        nc.tay.bam(nut)
        nc.tay.nghi(1.2, 2.5)
        return True
    return False


def _hang_sp(goc) -> list:
    try:
        return goc.evaluate(_JS_HANG_SP) or []
    except Exception:
        return []


def _gan_san_pham(nc, ten_sp: str, ten_hien_thi: str = "") -> str:
    """TikTok Studio: Thêm liên kết -> Sản phẩm -> tìm theo tên/ID -> chọn dòng khớp -> Tiếp -> tên hiển thị
    (<=30 ký tự) -> Thêm. Không công khai (bài chưa đăng), nên chạy thử cũng đi hết. Trả tên sản phẩm đã gắn."""
    page = nc.page
    if not ten_sp.strip():
        raise w.LoiDang("thiếu tên hoặc ID sản phẩm TikTok Shop", False)
    nc.nhat_ky(f"Giỏ hàng: tìm mục 'Thêm liên kết' để gắn sản phẩm '{ten_sp}'")
    nut = w.tim(page, timeout_ms=5000, ten=["Thêm liên kết", "Add link", "Thêm sản phẩm", "Add product", "Add products"])
    if not nut:
        try:
            ma = page.evaluate(_JS_NUT_THEM_LK)
        except Exception:
            ma = ""
        nut = w.dau_tien_thay([page.locator(f"[data-minmin='{ma}']")], 1000) if ma else None
    if not nut:
        _chan_doan(nc, "Giỏ hàng: không thấy nút Thêm liên kết", ["button", "[role='button']", "[data-e2e]"])
        raise w.LoiDang(KHONG_SHOP + " (không thấy mục 'Thêm liên kết'/'Add link' trên trang tải lên)", False)
    nc.nhat_ky("Giỏ hàng: bấm 'Thêm liên kết'")
    nc.tay.bam(nut)
    nc.tay.nghi(1.2, 2.5)
    hop = w.cho(lambda: _hop_tren_cung(page) is not None, 8) and _hop_tren_cung(page)
    nc.nhat_ky(f"Giỏ hàng: hộp thoại {'đã mở' if hop else 'không thấy (tìm trên cả trang)'}")
    goc = hop or page.locator("body")
    # 1. loại liên kết = Sản phẩm (nếu hộp hỏi)
    if not _hang_sp(goc):
        opt = w.tim(goc, timeout_ms=2000, role="option", ten=["Sản phẩm", "Products", "Product"]) or \
            w.tim(goc, timeout_ms=1000, role="radio", ten=["Sản phẩm", "Products", "Product"])
        if not opt:
            cb = w.dau_tien_thay([goc.locator("[role='combobox']"), goc.locator("[aria-haspopup='listbox']")], 2000)
            if cb:
                nc.nhat_ky("Giỏ hàng: mở ô chọn loại liên kết")
                nc.tay.bam(cb)
                nc.tay.nghi(0.6, 1.2)
                opt = w.tim(page, timeout_ms=3000, role="option", ten=["Sản phẩm", "Products", "Product"],
                            chu=["Sản phẩm", "Products"])
        if not opt:
            opt = w.tim(goc, timeout_ms=1000, chu=["Sản phẩm", "Products"])
        if opt:
            nc.nhat_ky("Giỏ hàng: chọn loại liên kết 'Sản phẩm'")
            nc.tay.bam(opt)
            nc.tay.nghi(0.8, 1.5)
        elif w.co_chu(goc, "không đủ điều kiện", "chưa đủ điều kiện", "not eligible", "không khả dụng", "unavailable"):
            raise w.LoiDang(KHONG_SHOP + " (TikTok báo tài khoản chưa đủ điều kiện)", False)
        else:
            nc.nhat_ky("Giỏ hàng: hộp thoại không có lựa chọn 'Sản phẩm', thử đi tiếp")
        _bam_tiep(nc, goc)
    # 2. tìm sản phẩm
    hop = _hop_tren_cung(page)
    goc = hop or page.locator("body")
    o_tim = w.dau_tien_thay(w.ung_vien(goc, role="textbox", ten=["Tìm", "Search"], chua=True,
                                       css=["input[type='search']", "input[placeholder*='Tìm' i]",
                                            "input[placeholder*='Search' i]"]) + [goc.get_by_role("searchbox")], 8000)
    if o_tim:
        nc.nhat_ky(f"Giỏ hàng: gõ tìm sản phẩm '{ten_sp}'")
        w.go_vao(nc, o_tim, ten_sp, xoa_truoc=True)
        nc.page.keyboard.press("Enter")       # ô tìm kiếm, không phải gửi gì công khai
        nc.tay.nghi(2.5, 4.5)
    else:
        nc.nhat_ky("Giỏ hàng: không thấy ô tìm sản phẩm, chọn trong danh sách đang hiện")
    hang = []
    w.cho(lambda: bool(hang.extend(_hang_sp(goc)) or hang), 10, 1.0)
    if not hang:
        _chan_doan(nc, "Giỏ hàng: không thấy dòng sản phẩm nào", _SEL_SP)
        if w.co_chu(goc, "Không có sản phẩm", "Không tìm thấy", "No products", "No results", "No data", "Không có dữ liệu"):
            raise w.LoiDang(f"không tìm thấy sản phẩm '{ten_sp}' trong cửa hàng/Showcase của nick. Kiểm tra tên/ID "
                            "và sản phẩm đã được thêm vào Showcase", False)
        raise w.LoiDang(KHONG_SHOP + " (không hiện danh sách sản phẩm để chọn)", False)
    chon = chon_san_pham(hang, ten_sp)
    nc.nhat_ky(f"Giỏ hàng: thấy {len(hang)} dòng sản phẩm: " + " | ".join(h["chu"].splitlines()[0][:40] for h in hang[:4]))
    if not chon:
        raise w.LoiDang(f"không có sản phẩm nào khớp '{ten_sp}' trong {len(hang)} dòng đang hiện (không gắn bừa)", False)
    ten_chon = (chon["chu"].strip().splitlines() or [""])[0].strip()[:120]
    nc.nhat_ky(f"Giỏ hàng: chọn '{ten_chon}' (khớp: {chon['khop']})")
    o_chon = page.locator(f"[data-minmin='{chon['ma']}']")
    if not chon.get("da_chon"):
        nc.tay.bam(o_chon)
        nc.tay.nghi(0.6, 1.2)
    try:
        da = o_chon.evaluate(_JS_DA_CHON)
    except Exception:
        da = None
    nc.nhat_ky(f"Giỏ hàng: ô chọn sản phẩm {'đã tick' if da else ('chưa thấy tick' if da is False else 'không đọc được trạng thái')}")
    _bam_tiep(nc, goc)
    # 3. tên hiển thị + xác nhận (có thể qua 1-3 hộp liên tiếp)
    for buoc in range(3):
        hop = _hop_tren_cung(page)
        if not hop:
            break
        if ten_hien_thi and buoc == 0:
            o_ten = w.dau_tien_thay(w.ung_vien(hop, role="textbox", ten=["Tên sản phẩm", "Product name", "Tên hiển thị",
                                                                         "Display name"], chua=True,
                                               css=["input[maxlength='30']"]), 4000)
            if o_ten:
                nc.nhat_ky(f"Giỏ hàng: gõ tên hiển thị '{ten_hien_thi[:30]}'")
                w.go_vao(nc, o_ten, ten_hien_thi[:30], xoa_truoc=True)
                nc.tay.nghi(0.5, 1.0)
            else:
                nc.nhat_ky("Giỏ hàng: không thấy ô tên hiển thị, giữ tên mặc định của TikTok")
        xong = w.tim(hop, timeout_ms=4000, ten=_NUT_XONG)
        if not xong:
            if _bam_tiep(nc, hop):
                continue
            _chan_doan(nc, "Giỏ hàng: không thấy nút Thêm/Xác nhận", _SEL_SP)
            raise w.LoiDang("không thấy nút Thêm/Xác nhận để gắn sản phẩm", False)
        nc.nhat_ky(f"Giỏ hàng: bấm '{(xong.inner_text() or '').strip()[:20]}'")
        nc.tay.bam(xong)
        w.cho(lambda: _hop_tren_cung(page) is None, 8)
    if _hop_tren_cung(page) is not None:
        _chan_doan(nc, "Giỏ hàng: hộp thoại chưa đóng", _SEL_SP)
        raise w.LoiDang("bấm Thêm nhưng hộp chọn sản phẩm chưa đóng (có thể nút bị khoá)", False)
    dau = [x for x in ((ten_hien_thi or "")[:12], ten_chon[:12], ten_sp[:12]) if x.strip()]
    if not w.cho(lambda: any(w.thay_chu_ngoai_o_nhap(page, d) for d in dau), 10):
        _chan_doan(nc, "Giỏ hàng: chưa thấy sản phẩm trên trang tải lên", ["[data-e2e]", "button"])
        raise w.LoiDang("đã bấm Thêm nhưng chưa thấy sản phẩm hiện trên trang tải lên", False)
    nc.nhat_ky(f"Giỏ hàng: đã gắn sản phẩm '{ten_chon}' (thấy trên trang tải lên)")
    return ten_chon


def tt_dang_video_gio_hang(nc) -> str:
    sp = str(nc.ts.get("san_pham_shop") or "").strip()
    if not sp:
        raise LoiKyNang("thiếu tên hoặc ID sản phẩm TikTok Shop")
    gh = {"ten": sp, "ten_hien_thi": str(nc.ts.get("ten_hien_thi") or "").strip()[:30]}
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    return _chay_kho_sau(nc, "dang_video", int(nc.ts.get("so_bai", 1) or 1), "Đăng video gắn giỏ hàng TikTok",
                         lambda bai, tt: _dang_video(nc, bai, tt, gio_hang=gh), _kiem_bai_video)


# --------------------------------------------------------------------------- tt_dang_ai + dang_ban_nhap

def _ly_do_nhap_khong_dang(bn: dict) -> str:
    tep = bn.get("tep_cuc_bo") or []
    if w.loc_tep(tep, w.DUOI_VIDEO) or len(_anh_hop_le(tep)) >= ANH_TOI_THIEU:
        return ""
    return (f"nháp #{bn.get('id')} không có tệp video (TikTok cần video, hoặc từ {ANH_TOI_THIEU} ảnh để đăng dạng "
            "ảnh). Đính kèm video vào nháp rồi duyệt lại")


def _dang_nhap_bai(nc, bn: dict) -> str:
    """Nháp bài đăng: có video -> đăng video, không video mà có >=2 ảnh -> đăng dạng ảnh."""
    ly_do = _ly_do_nhap_khong_dang(bn)
    if ly_do:
        raise LoiKyNang(ly_do)
    bai = {"tep_cuc_bo": bn.get("tep_cuc_bo") or [], "noi_dung": str(bn.get("noi_dung") or "")}
    tt = w.TrangThaiDang()
    if w.loc_tep(bai["tep_cuc_bo"], w.DUOI_VIDEO):
        return _dang_video(nc, bai, tt)
    return _dang_anh(nc, bai, tt)


def _nhap_binh_luan(nc, p: dict) -> str:
    link, tg, chu = w.tach_muc_tieu(p.get("link_goc"))
    if not link:
        raise LoiKyNang("nháp không có link video")
    nc.mo(link)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)
    nd = w.cat_gioi_han(w.mot_dong(p.get("noi_dung") or ""), GIOI_HAN_BL)
    if chu:
        _o_binh_luan(nc, 5000)
        ok = _tra_loi_bl(nc, tg, chu, nd)
    else:
        ok = _binh_luan(nc, nd)
    if not ok:
        raise LoiKyNang("đã gửi nhưng chưa thấy bình luận hiện")
    return link


def _nhap_video(nc, p: dict) -> str:
    ly_do = _ly_do_nhap_khong_dang(p)
    if ly_do:                       # báo trước khi mở trang
        raise LoiKyNang(ly_do)
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    return _dang_nhap_bai(nc, p)


def dang_ban_nhap(nc) -> str:
    return w.dang_ban_nhap_chung(nc, NT, {"bai_dang": lambda p: _nhap_video(nc, p),
                                          "binh_luan": lambda p: _nhap_binh_luan(nc, p),
                                          "tra_loi": lambda p: _nhap_binh_luan(nc, p)})


def tt_dang_ai(nc) -> str:
    so_bai = max(1, int(nc.ts.get("so_bai", 1) or 1))
    hd = "dang_video"
    ten = "Đăng video TikTok kèm caption AI"
    dem = w.Dem()
    nc.mo(URL_TAI_LEN)
    nc.kiem_dang_nhap()
    if nc.chay_thu:
        w.bao_thu(nc, dem, hd, f"Chạy thử: sẽ lấy tối đa {so_bai} nháp TikTok đã duyệt có video và đăng "
                               "(không giữ nháp nào, nháp vẫn chờ)")
        return _ket(nc, dem, ten)
    het = False
    for _ in range(so_bai + 5):          # nháp hỏng (thiếu video) được bỏ qua, không tính vào số bài
        if nc.nen_dung() or dem.tong(dem.ok) >= so_bai or not w.con_luot(nc, dem, hd):
            break
        bn = nc.lay_ban_nhap(NT)
        if not bn:
            w.bao(nc, dem, hd, "bo_qua", "Không còn nháp TikTok đã duyệt", ma="het_bai")
            het = True
            break
        bid = bn.get("id")
        loai = str(bn.get("loai") or "bai_dang")
        nc.nhat_ky(f"Nháp #{bid} ({loai}): {str(bn.get('noi_dung') or '')[:60]}, {len(bn.get('tep_cuc_bo') or [])} tệp")
        if loai == "bai_dang":
            ly_do = _ly_do_nhap_khong_dang(bn)
            if ly_do:
                nc.xong_ban_nhap(bid, False, loi=ly_do)
                w.bao(nc, dem, hd, "bo_qua", ly_do)
                continue
        try:
            link = _nhap_binh_luan(nc, bn) if loai in ("binh_luan", "tra_loi") else _dang_nhap_bai(nc, bn)
        except Exception as e:
            nc.xong_ban_nhap(bid, False, loi=str(e)[:300])
            w.bao_loi_ngoai_le(nc, dem, hd, e)
            break
        nc.xong_ban_nhap(bid, True, link=link or "")
        w.bao(nc, dem, "binh_luan" if loai in ("binh_luan", "tra_loi") else hd, "thanh_cong",
              f"Đã đăng nháp #{bid} ({loai})", link=link or "", san_pham=str(bn.get("san_pham_id") or ""))
        nc.nghi_thao_tac()
    if het and dem.tong(dem.bo) == 1 and not dem.tong(dem.ok) and not dem.tong(dem.loi):
        return "Hết bài"
    return _ket(nc, dem, ten)


# --------------------------------------------------------------------------- tt_binh_luan_tu_khoa

def _dang_bl(nc, link: str, nd: str) -> str:
    if not _binh_luan(nc, w.cat_gioi_han(w.mot_dong(nd), GIOI_HAN_BL)):
        raise LoiKyNang("đã gửi nhưng chưa thấy bình luận hiện")
    return link


def tt_binh_luan_tu_khoa(nc) -> str:
    ts = nc.ts
    tu = w.ds_dong(ts.get("tu_khoa"))
    sp = str(ts.get("san_pham") or "")
    so_moi = int(ts.get("so_video", 10) or 10)
    toi_da = int(ts.get("toi_da", 3) or 3)
    thich = bool(ts.get("thich"))
    hd = "binh_luan"
    dem = w.Dem()
    if not tu:
        raise LoiKyNang("thiếu từ khoá (mỗi dòng một từ khoá)")
    nc.mo(url_tim(tu[0]))
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    chu_nick = _ten_nick(nc)
    nc.nhat_ky(f"Nick @{chu_nick or '?'}: bình luận theo {len(tu)} từ khoá, tối đa {toi_da} video")

    def du() -> bool:
        return dem.ok.get(hd, 0) + dem.thu.get(hd, 0) >= toi_da

    for kw in tu:
        if nc.nen_dung() or du() or not w.con_luot(nc, dem, hd):
            break
        _mo(nc, url_tim(kw))
        the = _gom_video(nc, so_moi, f"Tìm '{kw}'")
        ung, n_minh, n_da = [], 0, 0
        for t in the:
            if chu_nick and t["tac_gia"] == chu_nick:
                n_minh += 1
                continue
            if nc.da_lam(w.khoa(NT, "binh_luan", t["link"])):
                n_da += 1
                continue
            ung.append(t)
        nc.nhat_ky(f"Từ khoá '{kw}': {len(the)} video, bỏ {n_minh} của chính nick, {n_da} đã bình luận, còn {len(ung)}")
        for t in ung:
            if nc.nen_dung() or du() or not w.con_luot(nc, dem, hd):
                break
            link = t["link"]
            k = w.khoa(NT, "binh_luan", link)
            try:
                _mo(nc, link)
                nc.tay.nghi(3.0, 8.0)                # xem video một lúc như người thật
                v = _doc_video(nc)
                cap = v["chu"] or t.get("chu") or ""
                tg = v["tac_gia"] or t["tac_gia"]
                if chu_nick and tg == chu_nick:
                    nc.nhat_ky(f"Bỏ video của chính nick: {link}")
                    continue
                if thich and w.con_luot(nc, dem, "thich"):
                    nut = _nut_thich(nc.page)
                    if not nut:
                        w.bao(nc, dem, "thich", "loi", "không thấy nút tim", link=link)
                    else:
                        w.bam_va_xac_nhan(nc, dem, "thich", _nut_cha(nut), _da_bat, "thả tim video", link)
                kq = w.lay_ai(nc, "viet_binh_luan", {
                    "bai": {"chu": cap, "link": link, "tac_gia": tg}, "san_pham_id": sp, "kieu": "tu_nhien",
                    "yeu_cau": "bình luận ngắn tự nhiên dưới video TikTok, đúng nội dung video, không link, không hashtag"})
                nd = w.cat_gioi_han(w.mot_dong(kq.get("noi_dung") or ""), GIOI_HAN_BL)
                if kq.get("bo_qua") or not nd:
                    w.bao(nc, dem, hd, "bo_qua", f"AI bỏ video này: {kq.get('ly_do') or 'không viết được'}", link=link)
                    continue
                w.noi_dung_ai(nc, dem, hd, loai="binh_luan", noi_dang=NT, link_goc=link, bai_goc=cap,
                              ly_do=f"Video '{kw}' của @{tg}: {cap[:100]}", noi_dung=nd, khoa_lap=k,
                              dang=lambda x, link=link: _dang_bl(nc, link, x), san_pham_id=sp)
            except Exception as e:
                w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return _ket(nc, dem, "Bình luận TikTok theo từ khoá")


# --------------------------------------------------------------------------- tt_follow_doi_thu

_THEO_DOI = ("Theo dõi", "Follow", "Theo dõi lại", "Follow back")
_DA_THEO = ("Đang theo dõi", "Following", "Bạn bè", "Friends", "Đã yêu cầu", "Requested", "Đã gửi yêu cầu")
_RE_DA_THEO = w.re_chua(*_DA_THEO)
_RE_THEO = w.re_chua("Theo dõi", "Follow")

_JS_NGUOI_BL = r"""() => {
  const out = [];
  document.querySelectorAll("[data-e2e='comment-username-1'], [data-e2e='comment-level-1'], [data-e2e='comment-item']").forEach(e => {
    let c = e, a = null;
    for (let k = 0; k < 6 && c; k++) { a = c.matches("a[href*='/@']") ? c : c.querySelector("a[href*='/@']"); if (a) break; c = c.parentElement; }
    const m = a ? (a.getAttribute('href') || '').match(/\/@([^\/?#]+)/) : null;
    if (m) out.push(m[1]);
  });
  return [...new Set(out)];
}"""


def trang_thai_follow(chu: str) -> str:
    """Chữ/nhãn nút -> 'da' (đang theo dõi / bạn bè / đã yêu cầu), 'chua' (Theo dõi / Follow back), '?'."""
    s = str(chu or "")
    if _RE_DA_THEO.search(s):
        return "da"
    if _RE_THEO.search(s):
        return "chua"
    return "?"


def _doc_nut(loc) -> str:
    try:
        return ((loc.inner_text(timeout=2000) or "") + " " + (loc.get_attribute("aria-label", timeout=2000) or "")).strip()
    except Exception:
        return ""


def _nut_follow(page):
    """Nút Theo dõi của HỒ SƠ (data-e2e=follow-button), không phải nút ở mục tài khoản đề xuất."""
    return w.dau_tien_thay(
        [page.locator("button[data-e2e='follow-button']"), page.locator("[data-e2e='follow-button']"),
         page.locator("[data-e2e='user-page'], #main-content-others_homepage").get_by_role(
             "button", name=w.re_nhan(*(_THEO_DOI + _DA_THEO))),
         page.get_by_role("button", name=w.re_nhan(*(_THEO_DOI + _DA_THEO)))], 8000)


def _da_theo_doi(page, pin) -> bool:
    if pin is not None and trang_thai_follow(_doc_nut(pin)) == "da":
        return True
    loc = page.locator("[data-e2e='follow-button']")
    if loc.count() and trang_thai_follow(_doc_nut(loc.first)) == "da":
        return True
    return w.dang_hien(page.locator("[data-e2e='unfollow-button']"))


def _doc_nguoi_binh_luan(nc) -> List[str]:
    page = nc.page
    _o_binh_luan(nc, 4000)               # mở bảng bình luận nếu đang đóng (không công khai)
    ds: List[str] = []
    for lan in range(3):
        try:
            for h in page.evaluate(_JS_NGUOI_BL) or []:
                h = ten_tiktok(h)
                if h and h not in ds:
                    ds.append(h)
        except Exception:
            pass
        bl = page.locator("[data-e2e='comment-level-1']")
        try:
            if not bl.count():
                break
            nc.tay.di_toi(bl.last)
            page.mouse.wheel(0, 900)
            nc.tay.nghi(1.2, 2.5)
        except Exception:
            break
    if not ds:
        _chan_doan(nc, "Không đọc được người bình luận", ["[data-e2e='comment-level-1']", "[data-e2e='comment-username-1']",
                                                          "[data-e2e='comment-icon']", "a[href*='/@']"])
    return ds


def _theo_doi(nc, dem: w.Dem, ten: str, k: str, nguon: str) -> None:
    hd = "theo_doi"
    page = nc.page
    url = f"https://www.tiktok.com/@{ten}"
    _mo(nc, url)
    if w.co_chu(page, "Không thể tìm thấy tài khoản này", "Couldn't find this account"):
        w.bao(nc, dem, hd, "bo_qua", f"@{ten}: tài khoản không còn", link=url)
        return
    nut = _nut_follow(page)
    if not nut:
        _chan_doan(nc, f"@{ten}: không thấy nút Theo dõi", ["[data-e2e='follow-button']", "[data-e2e='unfollow-button']",
                                                             "[data-e2e='message-button']", "button"])
        w.bao(nc, dem, hd, "loi", f"@{ten}: không thấy nút Theo dõi trên hồ sơ", link=url)
        return
    chu = _doc_nut(nut)
    tt = trang_thai_follow(chu)
    if tt == "da":
        if not nc.chay_thu:
            nc.ghi_da_lam(k)
        w.bao(nc, dem, hd, "bo_qua", f"@{ten}: đã theo dõi từ trước ('{chu[:30]}')", link=url)
        return
    if tt != "chua":
        w.bao(nc, dem, hd, "loi", f"@{ten}: nút ở trạng thái lạ '{chu[:40]}'", link=url)
        return
    if nc.chay_thu:
        w.bao_thu(nc, dem, hd, f"Chạy thử: sẽ theo dõi @{ten} (người bình luận ở {nguon})", link=url)
        return
    pin = w.ghim(nut, "follow") or nut
    nc.tay.nghi(1.0, 3.0)
    if not w.bam_cong_khai(nc, nut, f"Theo dõi @{ten}"):
        return
    ok = w.cho(lambda: _da_theo_doi(page, pin), 10)
    w.kiem_chan(nc)
    if ok:
        nc.ghi_da_lam(k)
        w.bao(nc, dem, hd, "thanh_cong", f"Đã theo dõi @{ten} (nút đổi sang '{_doc_nut(pin)[:30]}')", link=url)
    else:
        w.bao(nc, dem, hd, "loi", f"Đã bấm Theo dõi @{ten} nhưng nút chưa đổi sang Đang theo dõi "
                                  f"('{_doc_nut(pin)[:30]}')", link=url)
    nc.nghi_thao_tac()


def tt_follow_doi_thu(nc) -> str:
    ts = nc.ts
    doi_thu = [t for t in (ten_tiktok(x) for x in w.ds_dong(ts.get("doi_thu"))) if t]
    so_video = int(ts.get("so_video", 3) or 3)
    toi_da = int(ts.get("toi_da", 10) or 10)
    hd = "theo_doi"
    dem = w.Dem()
    if not doi_thu:
        raise LoiKyNang("thiếu @kênh đối thủ (mỗi dòng một @tên hoặc link hồ sơ)")
    nc.mo(URL_FYP)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    chu_nick = _ten_nick(nc)
    bo = set(doi_thu) | ({chu_nick} if chu_nick else set())
    nc.nhat_ky(f"Nick @{chu_nick or '?'}: theo dõi người xem của {len(doi_thu)} kênh, tối đa {toi_da} người")
    da_xet = set()

    def dung() -> bool:
        return nc.nen_dung() or dem.ok.get(hd, 0) + dem.thu.get(hd, 0) >= toi_da or not w.con_luot(nc, dem, hd)

    for dt in doi_thu:
        if dung():
            break
        try:
            _mo(nc, f"https://www.tiktok.com/@{dt}")
            if w.co_chu(nc.page, "Không thể tìm thấy tài khoản này", "Couldn't find this account"):
                w.bao(nc, dem, hd, "loi", f"Không thấy kênh @{dt}")
                continue
            vids = _gom_video(nc, so_video, f"Hồ sơ @{dt}", tac_gia=dt, luot_toi_da=3)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, f"https://www.tiktok.com/@{dt}")
            continue
        for v in vids:
            if dung():
                break
            try:
                _mo(nc, v["link"])
                nguoi = _doc_nguoi_binh_luan(nc)
            except Exception as e:
                w.bao_loi_ngoai_le(nc, dem, hd, e, v["link"])
                continue
            moi = [h for h in nguoi if h not in bo and h not in da_xet]
            nc.nhat_ky(f"Video {v['link']}: {len(nguoi)} người bình luận, {len(moi)} người cần xét")
            for h in moi:
                if dung():
                    break
                da_xet.add(h)
                k = w.khoa(NT, "theo_doi", h)
                if nc.da_lam(k):
                    nc.nhat_ky(f"@{h}: nick đã theo dõi trước đây, bỏ qua")
                    continue
                try:
                    _theo_doi(nc, dem, h, k, v["link"])
                except Exception as e:
                    w.bao_loi_ngoai_le(nc, dem, hd, e, f"https://www.tiktok.com/@{h}")
    if not dem.tong(dem.ok) and not dem.tong(dem.thu) and not dem.tong(dem.loi) and not dem.tong(dem.bo):
        w.bao(nc, dem, hd, "bo_qua", "Không tìm được người bình luận nào cần theo dõi")
    return _ket(nc, dem, "Theo dõi người xem kênh đối thủ")


# --------------------------------------------------------------------------- tt_quet_csv

COT_QUET = ["stt", "link", "tac_gia", "mo_ta", "luot_xem", "so_tren_the", "luot_thich", "luot_binh_luan",
            "ngay_dang", "co_gio_hang", "san_pham", "gia", "link_san_pham", "nguon"]


def _dong_csv(t: dict, v: Optional[dict]) -> dict:
    v = v or {}
    sp = (v.get("san_pham") or [{}])[0] if v.get("san_pham") else {}
    xem = v.get("xem") if v.get("xem") is not None else doc_so(t.get("xem"))
    thich = v.get("thich") if v.get("thich") is not None else doc_so(t.get("thich"))
    return {"link": t["link"], "tac_gia": v.get("tac_gia") or t.get("tac_gia", ""),
            "mo_ta": (v.get("chu") or t.get("chu") or "").replace("\n", " ")[:1000],
            "luot_xem": "" if xem is None else xem, "so_tren_the": t.get("so_the") or "",
            "luot_thich": "" if thich is None else thich,
            "luot_binh_luan": "" if v.get("binh_luan") is None else v.get("binh_luan"),
            "ngay_dang": v.get("ngay", ""),
            "co_gio_hang": ("có" if v.get("san_pham") else "không") if v else "chưa mở video",
            "san_pham": sp.get("ten", ""), "gia": sp.get("gia", ""), "link_san_pham": sp.get("link", ""),
            "nguon": t.get("khoi") or ""}


def tt_quet_csv(nc) -> str:
    ts = nc.ts
    kieu = str(ts.get("kieu_quet") or "tim_kiem")
    vao = str(ts.get("dau_vao") or "").strip()
    toi_da = int(ts.get("so_dong", 30) or 30)
    mo = bool(ts.get("mo_tung_video", True))
    dem = w.Dem()
    url = url_quet(kieu, vao)
    if not url:
        raise LoiKyNang("thiếu hoặc sai từ khoá / #hashtag / @hồ sơ để quét")
    nc.nhat_ky(f"Quét TikTok ({kieu}): {url}")
    _mo_doc(nc, url)
    if not w.con_luot(nc, dem, "quet"):
        return "Đã đủ giới hạn quét hôm nay"
    tg = ten_tiktok(vao) if kieu == "ho_so" else ""
    the = _gom_video(nc, toi_da, f"Quét {kieu} '{vao[:40]}'", tac_gia=tg, luot_toi_da=max(4, toi_da // 6))
    dong = []
    for t in the:
        if nc.nen_dung():
            break
        v = None
        if mo:
            try:
                _mo_doc(nc, t["link"])
                v = _doc_video(nc)
            except LoiKyNang as e:
                if getattr(e, "ma", None) in w.MA_DUNG:
                    raise
                nc.nhat_ky(f"Không đọc được {t['link']}: {e}")
            except Exception as e:
                nc.nhat_ky(f"Không đọc được {t['link']}: {type(e).__name__}")
            nc.tay.nghi(1.0, 3.0)
        d = _dong_csv(t, v)
        d["stt"] = len(dong) + 1
        dong.append(d)
    if not dong:
        w.bao(nc, dem, "quet", "bo_qua", f"Không quét được video nào ({kieu}: {vao[:60]})", link=url)
        return f"Quét TikTok: 0 dòng ({kieu}: {vao[:60]})."
    noi = _gui_csv(nc, f"tiktok_{kieu}_{time.strftime('%Y%m%d-%H%M%S')}.csv", COT_QUET, dong)
    co_gio = sum(1 for d in dong if d["co_gio_hang"] == "có")
    ct = f"Quét {len(dong)} video ({kieu}: {vao[:60]}), {co_gio} video có giỏ hàng; {noi}"
    w.bao(nc, dem, "quet", "thanh_cong", ct, link=url)
    return f"Quét TikTok: {len(dong)} dòng, {co_gio} có giỏ hàng; {noi}."


# --------------------------------------------------------------------------- tt_quet_gio_hang

COT_GIO = ["stt", "tu_khoa", "link_video", "tac_gia", "luot_xem", "luot_thich", "ten_san_pham", "gia",
           "link_san_pham", "mo_ta_video", "ngay_dang"]


def tt_quet_gio_hang(nc) -> str:
    ts = nc.ts
    tu = w.ds_dong(ts.get("tu_khoa"))
    so = int(ts.get("so_video", 20) or 20)
    chi_co = bool(ts.get("chi_co_gio", True))
    dem = w.Dem()
    if not tu:
        raise LoiKyNang("thiếu từ khoá (mỗi dòng một từ khoá)")
    _mo_doc(nc, url_tim(tu[0]))
    if not w.con_luot(nc, dem, "quet"):
        return "Đã đủ giới hạn quét hôm nay"
    dong, so_video, so_co = [], 0, 0
    for i, kw in enumerate(tu):
        if nc.nen_dung():
            break
        if i:
            _mo_doc(nc, url_tim(kw))
        the = _gom_video(nc, so, f"Tìm '{kw}'", luot_toi_da=max(4, so // 6))
        for t in the:
            if nc.nen_dung():
                break
            try:
                _mo_doc(nc, t["link"])
                v = _doc_video(nc)
            except LoiKyNang as e:
                if getattr(e, "ma", None) in w.MA_DUNG:
                    raise
                nc.nhat_ky(f"Không đọc được {t['link']}: {e}")
                continue
            except Exception as e:
                nc.nhat_ky(f"Không đọc được {t['link']}: {type(e).__name__}")
                continue
            so_video += 1
            sp = v.get("san_pham") or []
            so_co += 1 if sp else 0
            xem = v.get("xem") if v.get("xem") is not None else doc_so(t.get("xem"))
            goc = {"tu_khoa": kw, "link_video": t["link"], "tac_gia": v.get("tac_gia") or t.get("tac_gia", ""),
                   "luot_xem": "" if xem is None else xem, "luot_thich": "" if v.get("thich") is None else v["thich"],
                   "mo_ta_video": (v.get("chu") or t.get("chu") or "").replace("\n", " ")[:500],
                   "ngay_dang": v.get("ngay", "")}
            for s in (sp or ([{}] if not chi_co else [])):
                dong.append(dict(goc, stt=len(dong) + 1, ten_san_pham=s.get("ten", ""), gia=s.get("gia", ""),
                                 link_san_pham=s.get("link", "")))
            nc.tay.nghi(1.0, 3.0)
    if not dong:
        w.bao(nc, dem, "quet", "bo_qua", f"Xem {so_video} video, không video nào có giỏ hàng ({', '.join(tu)[:80]})")
        return f"Quét giỏ hàng TikTok: xem {so_video} video, không thấy video nào có giỏ hàng."
    noi = _gui_csv(nc, f"tiktok_gio_hang_{time.strftime('%Y%m%d-%H%M%S')}.csv", COT_GIO, dong)
    w.bao(nc, dem, "quet", "thanh_cong", f"Xem {so_video} video, {so_co} video có giỏ hàng, {len(dong)} dòng sản phẩm; {noi}")
    return f"Quét giỏ hàng TikTok: {so_video} video, {so_co} có giỏ hàng, {len(dong)} dòng; {noi}."


KICH_BAN = {
    "tt_dang_video_kho": tt_dang_video_kho,
    "tt_dang_ai": tt_dang_ai,
    "tt_dang_anh_kho": tt_dang_anh_kho,
    "tt_dang_video_gio_hang": tt_dang_video_gio_hang,
    "tt_tuong_tac_video": tt_tuong_tac_video,
    "tt_binh_luan_live": tt_binh_luan_live,
    "tt_nuoi_nick": tt_nuoi_nick,
    "tt_tra_loi_binh_luan": tt_tra_loi_binh_luan,
    "tt_binh_luan_tu_khoa": tt_binh_luan_tu_khoa,
    "tt_follow_doi_thu": tt_follow_doi_thu,
    "tt_quet_csv": tt_quet_csv,
    "tt_quet_gio_hang": tt_quet_gio_hang,
    "dang_ban_nhap:tiktok": dang_ban_nhap,
}
