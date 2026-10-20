"""Kỹ năng Reddit (giao diện mới shreddit): đăng bài vào sub (tiêu đề <= 300, flair, một bài một sub),
nuôi nick (upvote), bình luận AI (luật 9:1), tham gia sub, và dang_ban_nhap:reddit.

Reddit mới dùng web component (shreddit-post, shreddit-join-button...). Playwright xuyên shadow DOM mở
nên role/aria-label vẫn dùng được; thuộc tính của component (permalink, post-title, author, subscribed)
là dữ liệu công khai của trang, không phải class băm.
"""
from __future__ import annotations

import re
import time

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "reddit"
GOC = "https://www.reddit.com"
GIOI_HAN_TIEU_DE = 300


def _mo(nc, url: str) -> None:
    nc.mo(url)
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)


def _link_day_du(h: str) -> str:
    h = h or ""
    return h if h.startswith("http") else GOC + h


# --------------------------------------------------------------------------- rd_dang_sub

def _chon_flair(nc, flair: str) -> None:
    page = nc.page
    nut = w.tim(page, ten=["Thêm thẻ và gắn cờ", "Add flair and tags", "Thêm flair", "Add flair", "Flair"],
                chua=True, timeout_ms=6000)
    if not nut:
        raise w.LoiDang("sub cần flair nhưng không thấy nút chọn flair", False)
    nc.tay.bam(nut)
    nc.tay.nghi(0.8, 1.5)
    chon = w.tim(page, role="radio", ten=[flair], chua=True, timeout_ms=5000) or \
        w.tim(page, role="option", ten=[flair], chua=True, timeout_ms=2000) or \
        w.tim(page, role="button", chu=[flair], chua=True, timeout_ms=2000)
    if not chon:
        raise w.LoiDang(f"không thấy flair '{flair}' trong danh sách của sub", False)
    nc.tay.bam(chon)
    nc.tay.nghi(0.5, 1.0)
    ok = w.tim(page, ten=["Thêm", "Add", "Áp dụng", "Apply", "Lưu", "Save"], timeout_ms=4000)
    if ok:
        nc.tay.bam(ok)          # đóng hộp flair (chưa đăng gì)
        nc.tay.nghi(0.5, 1.0)


def dang_sub(nc, sub: str, tieu_de: str, noi_dung: str, flair: str = "", tt: w.TrangThaiDang = None) -> str:
    tt = tt or w.TrangThaiDang()
    page = nc.page
    tieu_de = w.cat_gioi_han(tieu_de.replace("\n", " "), GIOI_HAN_TIEU_DE)
    noi_dung = str(noi_dung or "").strip()
    la_link = bool(re.fullmatch(r"https?://\S+", noi_dung))
    _mo(nc, f"{GOC}/r/{sub}/submit/?type={'LINK' if la_link else 'TEXT'}")
    if w.co_chu(page, "không tồn tại", "doesn't exist", "Sorry, nobody on Reddit goes by that name", "bị cấm",
                "banned", "private community", "cộng đồng riêng tư"):
        raise w.LoiDang(f"r/{sub} không đăng được (không tồn tại / riêng tư / bị cấm)", False)
    o_td = w.tim(page, role="textbox", ten=["Tiêu đề", "Title"], chua=True, css=["textarea[name='title']"],
                 timeout_ms=15000)
    if not o_td:
        raise w.LoiDang("không thấy ô Tiêu đề trên trang đăng bài", False)
    nc.nhat_ky(f"Gõ tiêu đề ({len(tieu_de)} ký tự)")
    w.go_vao(nc, o_td, tieu_de)
    nc.tay.nghi(0.6, 1.4)
    if noi_dung:
        if la_link:
            o = w.tim(page, role="textbox", ten=["URL", "Url", "Link"], chua=True, css=["textarea[name='link']"],
                      timeout_ms=8000)
        else:
            o = w.tim(page, role="textbox", ten=["Nội dung", "Body", "Post body", "Text"], chua=True,
                      css=["shreddit-composer [contenteditable='true']", "div[contenteditable='true'][role='textbox']",
                           "textarea[name='body']"], timeout_ms=8000)
        if not o:
            raise w.LoiDang("không thấy ô nội dung bài", False)
        nc.nhat_ky(f"Gõ {'link' if la_link else 'nội dung'} ({len(noi_dung)} ký tự)")
        w.go_vao(nc, o, noi_dung)
        nc.tay.nghi(0.8, 1.6)
    if flair:
        _chon_flair(nc, flair)
    nut = w.tim(page, ten=["Đăng", "Post"], css=["#inner-post-submit-button", "[slot='submit-button'] button"],
                timeout_ms=8000)
    if not nut or nut.get_attribute("aria-disabled") == "true" or nut.get_attribute("disabled") is not None:
        if w.co_chu(page, "flair", "Flair") and not flair:
            raise w.LoiDang("sub bắt buộc flair: nhập flair trong tham số mẫu", False)
        raise w.LoiDang("nút Đăng đang khoá", False)
    nc.tay.nghi(1.0, 2.5)
    tt.da_bam = True
    if not w.bam_cong_khai(nc, nut, "Đăng bài Reddit"):
        raise w.LoiDang("chạy thử", False)
    ok = w.cho(lambda: "/comments/" in (page.url or ""), 60, 1.0)
    w.kiem_chan(nc)
    if not ok:
        raise w.LoiDang("đã bấm Đăng nhưng chưa chuyển sang trang bài (sub có thể từ chối hoặc bắt duyệt)", True)
    return page.url


def rd_dang_sub(nc) -> str:
    ts = nc.ts
    sub = w.ten_sub(ts.get("sub"))
    tieu_de = str(ts.get("tieu_de") or "").strip()
    dem = w.Dem()
    hd = "dang_tuong"
    nc.mo(f"{GOC}/r/{sub}/")
    nc.kiem_dang_nhap()
    if not sub or not tieu_de:
        raise LoiKyNang("thiếu subreddit hoặc tiêu đề")
    k = w.khoa(NT, "dang", sub.lower(), w.bam_chuoi(tieu_de))
    if nc.da_lam(k):
        w.bao(nc, dem, hd, "bo_qua", f"Nick đã đăng bài này vào r/{sub} (một bài một sub)")
        return f"Bỏ qua: đã đăng bài này vào r/{sub}."
    if not w.con_luot(nc, dem, hd):
        return "Đã đủ giới hạn đăng hôm nay"
    if nc.chay_thu:
        w.bao_thu(nc, dem, hd, f"Chạy thử: sẽ đăng \"{tieu_de[:80]}\" vào r/{sub}"
                               + (f" (flair {ts.get('flair')})" if ts.get("flair") else ""))
        return w.ket_thuc(nc, dem, "Đăng Reddit")
    try:
        link = dang_sub(nc, sub, tieu_de, str(ts.get("noi_dung") or ""), str(ts.get("flair") or "").strip())
    except Exception as e:
        w.bao_loi_ngoai_le(nc, dem, hd, e)
        return w.ket_thuc(nc, dem, "Đăng Reddit")
    nc.ghi_da_lam(k)
    w.bao(nc, dem, hd, "thanh_cong", f"Đã đăng vào r/{sub} (đọc lại thấy trang bài)", link=link, nhom=f"r/{sub}")
    return w.ket_thuc(nc, dem, "Đăng Reddit")


# --------------------------------------------------------------------------- upvote / nuôi nick

def _da_upvote(loc) -> bool:
    return w.nhan_bat(loc)


def _nut_upvote(goc):
    return w.dau_tien_thay(w.ung_vien(goc, ten=["Upvote", "Bình chọn tán thành", "Ủng hộ", "Bình chọn ủng hộ"],
                                      chua=True, css=["button[upvote]"]), 4000)


def rd_nuoi_nick(nc) -> str:
    phut = float(nc.ts.get("phut", 10) or 10)
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    han = time.monotonic() + phut * 60
    while time.monotonic() < han and not nc.nen_dung():
        w.kiem_chan(nc)
        nc.tay.luot(rng.randint(1, 3))
        if w.nghi_co_dung(nc, rng.uniform(4, 14)):
            break
        if rng.random() < 0.25 and w.con_luot(nc, dem, "thich"):
            ung = w.trong_khung(nc.page, nc.page.locator("button[upvote]"))
            if ung:
                w.bam_va_xac_nhan(nc, dem, "thich", rng.choice(ung), _da_upvote, "upvote bài trên trang chủ",
                                  nc.page.url)
    w.bao(nc, dem, "thich", "thong_tin", f"Nuôi nick Reddit: lướt {phut:g} phút, upvote {dem.ok.get('thich', 0)}")
    return f"{'Chạy thử - ' if nc.chay_thu else ''}Nuôi nick Reddit: {dem.tom_tat()}."


# --------------------------------------------------------------------------- bình luận

def _o_binh_luan(nc):
    page = nc.page
    cands = w.ung_vien(page, role="textbox", ten=["Bình luận", "Comment", "Tham gia cuộc trò chuyện",
                                                  "Join the conversation"], chua=True,
                       css=["shreddit-composer [contenteditable='true']", "comment-composer-host [contenteditable='true']"])
    o = w.dau_tien_thay(cands, 3000)
    if o:
        return o
    mo = w.tim(page, ten=["Tham gia cuộc trò chuyện", "Join the conversation", "Thêm bình luận", "Add a comment"],
               chua=True, chu=["Tham gia cuộc trò chuyện", "Join the conversation", "Thêm bình luận", "Add a comment"],
               css=["comment-composer-host faceplate-textarea-input", "faceplate-textarea-input"], timeout_ms=5000)
    if mo:
        nc.tay.bam(mo)          # mở ô bình luận (chưa công khai)
        nc.tay.nghi(0.8, 1.5)
    return w.dau_tien_thay(cands, 6000)


def binh_luan(nc, text: str) -> bool:
    o = _o_binh_luan(nc)
    if not o:
        raise LoiKyNang("không thấy ô bình luận (sub có thể khoá bình luận hoặc nick bị cấm)")
    return w.gui_noi_dung(nc, o, text, nut_gui=lambda: w.tim(nc.page, ten=["Bình luận", "Comment"],
                                                             css=["button[slot='submit-button']"], timeout_ms=5000),
                          mo_ta="Đăng bình luận Reddit", giay_xac_nhan=25)


_JS_BAI = """() => Array.from(document.querySelectorAll('shreddit-post')).map(p => ({
  link: p.getAttribute('permalink') || '', tieu_de: p.getAttribute('post-title') || '',
  tac_gia: p.getAttribute('author') || '', loai: p.getAttribute('post-type') || '',
  qc: p.hasAttribute('is-promoted') || p.getAttribute('promoted') === 'true',
  chu: ((p.querySelector("[slot='text-body']") || {}).innerText || '').slice(0, 1500)
}))"""


def rd_binh_luan_ai(nc) -> str:
    ts = nc.ts
    subs = w.ds_sub(ts.get("sub"))
    sp = str(ts.get("san_pham") or "")
    toi_da = int(ts.get("toi_da", 3) or 3)
    rng = w.rng_nick(nc)
    dem = w.Dem()
    hd = "binh_luan"
    nc.mo(f"{GOC}/r/{subs[0]}/new/" if subs else GOC + "/")
    nc.kiem_dang_nhap()
    if not subs:
        raise LoiKyNang("thiếu subreddit")
    lam = 0
    for sub in subs:
        if nc.nen_dung() or lam >= toi_da or not w.con_luot(nc, dem, hd):
            break
        try:
            _mo(nc, f"{GOC}/r/{sub}/new/")
            nc.tay.luot(2)
            ds = [b for b in (nc.page.evaluate(_JS_BAI) or []) if b.get("link") and not b.get("qc")]
            nc.nhat_ky(f"r/{sub}: {len(ds)} bài mới")
            for b in ds:
                if nc.nen_dung() or lam >= toi_da or not w.con_luot(nc, dem, hd):
                    break
                link = _link_day_du(b["link"])
                k = w.khoa(NT, "binh_luan", link)
                if nc.da_lam(k, ca_doi=True):
                    continue
                # Luật 9:1: khoảng 1/10 bình luận được nhắc sản phẩm, còn lại chỉ giúp ích
                kieu = "tu_van" if (sp and rng.random() < 0.1) else "tu_nhien"
                kq = w.lay_ai(nc, "viet_binh_luan", {"bai": {"chu": f"{b['tieu_de']}\n\n{b.get('chu', '')}",
                                                             "tac_gia": b.get("tac_gia"), "link": link},
                                                     "san_pham_id": sp if kieu == "tu_van" else "", "kieu": kieu,
                                                     "ngon_ngu": "theo_bai"})
                lam += 1
                w.noi_dung_ai(nc, dem, hd, loai="binh_luan", noi_dang=NT, link_goc=link,
                              bai_goc=f"{b['tieu_de']}\n{b.get('chu', '')}"[:2000],
                              ly_do=f"Bài mới ở r/{sub}" + (" (lượt nhắc sản phẩm 1/10)" if kieu == "tu_van" else
                                                            " (bình luận giúp ích)"),
                              noi_dung=kq.get("noi_dung") or "", khoa_lap=k, nhom=f"r/{sub}",
                              san_pham_id=sp if kieu == "tu_van" else "",
                              dang=lambda nd, link=link: _binh_luan_link(nc, link, nd))
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e)
    return w.ket_thuc(nc, dem, "Bình luận Reddit bằng AI")


def _binh_luan_link(nc, link: str, nd: str) -> str:
    _mo(nc, link)
    if not binh_luan(nc, nd):
        raise LoiKyNang("đã gửi bình luận nhưng chưa thấy hiện")
    return link


# --------------------------------------------------------------------------- rd_tham_gia_sub

def _da_tham_gia(loc) -> bool:
    try:
        if loc.evaluate("e => { const j = e.closest('shreddit-join-button') || "
                        "(e.getRootNode && e.getRootNode().host); return !!(j && j.hasAttribute && "
                        "j.hasAttribute('subscribed')); }"):
            return True
    except Exception:
        pass
    s = w.doc_trang_thai(loc)
    return bool(re.search(r"(Đã tham gia|Joined|Rời|Leave)", s, re.I))


def rd_tham_gia_sub(nc) -> str:
    subs = w.ds_sub(nc.ts.get("sub"))
    dem = w.Dem()
    hd = "vao_nhom"
    nc.mo(f"{GOC}/r/{subs[0]}/" if subs else GOC + "/")
    nc.kiem_dang_nhap()
    for sub in subs:
        if nc.nen_dung() or not w.con_luot(nc, dem, hd):
            break
        link = f"{GOC}/r/{sub}/"
        try:
            _mo(nc, link)
            nut = w.dau_tien_thay(w.ung_vien(nc.page, ten=["Tham gia", "Join", "Đã tham gia", "Joined"],
                                             css=["shreddit-join-button button"]), 8000)
            if not nut:
                w.bao(nc, dem, hd, "loi", f"không thấy nút Tham gia ở r/{sub}", link=link, nhom=f"r/{sub}")
                continue
            w.bam_va_xac_nhan(nc, dem, hd, nut, _da_tham_gia, f"tham gia r/{sub}", link)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return w.ket_thuc(nc, dem, "Tham gia subreddit")


# --------------------------------------------------------------------------- dang_ban_nhap:reddit

def _nhap_bl(nc, p: dict) -> str:
    link, _, _ = w.tach_muc_tieu(p.get("link_goc"))
    if not link:
        raise LoiKyNang("nháp không có link bài")
    nc.mo(link)
    nc.kiem_dang_nhap()
    return _binh_luan_link(nc, link, str(p.get("noi_dung") or ""))


def _nhap_bai(nc, p: dict) -> str:
    sub = w.ten_sub(p.get("nhom"))
    if not sub:
        raise LoiKyNang("nháp bài Reddit thiếu subreddit (trường nhom)")
    dong = str(p.get("noi_dung") or "").strip().splitlines()
    tieu_de = dong[0] if dong else ""
    nc.mo(f"{GOC}/r/{sub}/")
    nc.kiem_dang_nhap()
    return dang_sub(nc, sub, tieu_de, "\n".join(dong[1:]).strip())


def dang_ban_nhap(nc) -> str:
    return w.dang_ban_nhap_chung(nc, NT, {"binh_luan": lambda p: _nhap_bl(nc, p),
                                          "tra_loi": lambda p: _nhap_bl(nc, p),
                                          "bai_dang": lambda p: _nhap_bai(nc, p)})


KICH_BAN = {
    "rd_dang_sub": rd_dang_sub,
    "rd_nuoi_nick": rd_nuoi_nick,
    "rd_binh_luan_ai": rd_binh_luan_ai,
    "rd_tham_gia_sub": rd_tham_gia_sub,
    "dang_ban_nhap:reddit": dang_ban_nhap,
}
