"""Kỹ năng TikTok: đăng video từ kho, tương tác video, bình luận LIVE, nuôi nick, tự trả lời bình luận,
và đăng nháp đã duyệt (dang_ban_nhap:tiktok).

Chọn phần tử: role + nhãn trợ năng tiếng Việt/tiếng Anh, kèm `data-e2e` (thuộc tính kiểm thử cố định
của TikTok, không phải class băm). Mọi cú bấm công khai đi qua tien_ich_web.bam_cong_khai.
Ô bình luận/ô chat LIVE của TikTok gửi bằng Enter, nên chữ luôn được gộp thành một dòng trước khi gõ.
"""
from __future__ import annotations

import re
import time

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


def _dang_video(nc, bai: dict, tt: w.TrangThaiDang) -> str:
    page = nc.page
    video = w.loc_tep(bai.get("tep_cuc_bo") or [], w.DUOI_VIDEO)[0]
    mo_ta = str(bai.get("noi_dung") or bai.get("tieu_de") or "").strip()
    _mo(nc, URL_TAI_LEN)
    o_tep = page.locator("input[type='file'][accept*='video'], input[type='file']")
    if not w.cho(lambda: o_tep.count() > 0, 30):
        raise w.LoiDang("không thấy ô chọn video ở TikTok Studio", False)
    nc.nhat_ky(f"Chọn video {video.split('/')[-1].split(chr(92))[-1]}")
    o_tep.first.set_input_files(video)
    o_mo_ta = w.dau_tien_thay(w.ung_vien(page, role="textbox", ten=["Mô tả", "Description", "Caption"], chua=True,
                                         css=["[data-e2e='caption_container'] [contenteditable='true']",
                                              ".public-DraftEditor-content", "div[contenteditable='true']"]),
                              120000)
    if not o_mo_ta:
        raise w.LoiDang("tải video lên nhưng không hiện ô mô tả", False)
    if mo_ta:
        nc.nhat_ky(f"Gõ mô tả ({len(mo_ta)} ký tự)")
        w.go_vao(nc, o_mo_ta, mo_ta[:2200], xoa_truoc=True)
        nc.page.keyboard.press("Escape")   # đóng gợi ý #hashtag/@nhắc nếu đang mở
        nc.tay.nghi(0.8, 1.6)
    _dat_cong_khai(nc)
    nut = None
    han = time.monotonic() + 20 * 60

    def _nut_dang():
        return w.dau_tien_thay(w.ung_vien(page, ten=["Đăng", "Post"],
                                          css=["button[data-e2e='post_video_button']"]), 2000)
    nc.nhat_ky("Chờ TikTok tải video xong")
    while time.monotonic() < han:
        w.kiem_chan(nc)
        nut = _nut_dang()
        if nut and nut.is_enabled() and nut.get_attribute("aria-disabled") != "true" \
                and nut.get_attribute("data-disabled") != "true":
            break
        nut = None
        if nc.nen_dung():
            raise w.LoiDang("đợt bị huỷ khi đang tải video", False)
        time.sleep(3)
    if not nut:
        raise w.LoiDang("quá 20 phút video chưa tải xong hoặc nút Đăng vẫn khoá", False)
    nc.tay.nghi(1.5, 3.5)
    tt.da_bam = True
    if not w.bam_cong_khai(nc, nut, "Đăng video TikTok"):
        raise w.LoiDang("chạy thử", False)
    # Hộp kiểm tra nội dung / xác nhận đăng
    for _ in range(3):
        xn = w.dau_tien_thay(w.ung_vien(page, ten=["Đăng ngay", "Post now", "Vẫn đăng", "Post anyway",
                                                   "Tiếp tục đăng", "Continue to post"]), 4000)
        if not xn:
            break
        nc.nhat_ky("Xử lý hộp kiểm tra nội dung: bấm đăng tiếp")
        w.bam_cong_khai(nc, xn, "Xác nhận đăng video")
        nc.tay.nghi(1.0, 2.0)
    roi = w.cho(lambda: "/upload" not in (page.url or ""), 180, 1.5)
    w.kiem_chan(nc)
    if not roi:
        raise w.LoiDang("đã bấm Đăng nhưng trang chưa rời màn tải lên (TikTok có thể đang báo lỗi)", True)
    nc.nhat_ky(f"Trang đã rời màn tải lên: {page.url[:80]}")
    return page.url


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


# --------------------------------------------------------------------------- dang_ban_nhap:tiktok

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


def dang_ban_nhap(nc) -> str:
    return w.dang_ban_nhap_chung(nc, NT, {"binh_luan": lambda p: _nhap_binh_luan(nc, p),
                                          "tra_loi": lambda p: _nhap_binh_luan(nc, p)})


KICH_BAN = {
    "tt_dang_video_kho": tt_dang_video_kho,
    "tt_tuong_tac_video": tt_tuong_tac_video,
    "tt_binh_luan_live": tt_binh_luan_live,
    "tt_nuoi_nick": tt_nuoi_nick,
    "tt_tra_loi_binh_luan": tt_tra_loi_binh_luan,
    "dang_ban_nhap:tiktok": dang_ban_nhap,
}
