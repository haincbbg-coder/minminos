"""Kỹ năng X (x.com): đăng từ kho (<= 4 ảnh hoặc 1 video, > 280 thì tự chia chuỗi, chữ có dấu tính 2,
hai bài cách nhau >= 10 phút), ghim / bỏ ghim / xoá bài của nick, trả lời theo từ khoá bằng AI,
tương tác theo link (thích, đăng lại), nuôi nick, và dang_ban_nhap:x.

Chọn phần tử: `data-testid` cố định của X (tweetTextarea_0, tweetButton, like/unlike, retweet/unretweet,
caret, confirmationSheetConfirm) kèm role + aria-label tiếng Việt/tiếng Anh dự phòng.
Ô soạn của X: Enter là xuống dòng (gửi là Ctrl+Enter), nên gõ nhiều dòng an toàn.
"""
from __future__ import annotations

import re
import time
import urllib.parse

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "x"
GOC = "https://x.com"
URL_SOAN = GOC + "/compose/post"
GIOI_HAN = 280
BAI = "article[data-testid='tweet']"

# Bỏ qua khi trả lời theo từ khoá: quảng cáo, crypto, 18+, chính trị.
_TU_CAM = re.compile(r"(crypto|bitcoin|btc|eth\b|airdrop|nft|memecoin|forex|casino|cá cược|cờ bạc|18\+|nsfw|onlyfans|"
                     r"sex|khiêu dâm|chính trị|bầu cử|election|politic|đảng|trump|biden|tổng thống|quốc hội)", re.I)


def _mo(nc, url: str) -> None:
    nc.mo(url)
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)


def _bai_chinh(page):
    b = page.locator(BAI)
    return b.first if b.count() else page


def _testid(goc, *ids: str):
    return goc.locator(", ".join(f"[data-testid='{i}']" for i in ids))


def _cho_bao_da_gui(page, giay: float = 30) -> str:
    """Chờ thông báo 'Bài đăng của bạn đã được gửi' và lấy link 'Xem'. Trả link ('' nếu không có link)."""
    def _co():
        return w.co_chu(page, "Bài đăng của bạn đã được gửi", "Your post was sent", "Đã gửi bài đăng",
                        "Your posts were sent", "Các bài đăng của bạn đã được gửi")
    if not w.cho(_co, giay):
        return None
    a = page.locator("[data-testid='toast'] a[href*='/status/'], [role='alert'] a[href*='/status/']")
    if a.count():
        h = a.first.get_attribute("href") or ""
        return h if h.startswith("http") else GOC + h
    return ""


# --------------------------------------------------------------------------- soạn + đăng

def _hop_soan(page):
    hop = w.dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("[data-testid='tweetTextarea_0']")),
                           page.locator("[data-testid='tweetTextarea_0']").locator("xpath=ancestor::*[@role='dialog'][1]")],
                          8000)
    return hop or page


def soan_va_dang(nc, phan: list, tep: list, tt: w.TrangThaiDang = None, tra_loi: bool = False) -> str:
    """Gõ các phần (chuỗi) vào hộp soạn đang mở, đính kèm tệp, bấm Đăng qua cổng, đọc lại thông báo."""
    tt = tt or w.TrangThaiDang()
    page = nc.page
    hop = _hop_soan(page)
    for i, p in enumerate(phan):
        if i:
            them = w.dau_tien_thay(w.ung_vien(hop, ten=["Thêm bài đăng", "Add post", "Thêm", "Add"],
                                              css=["[data-testid='addButton']"]), 5000)
            if not them:
                raise w.LoiDang("không thấy nút thêm bài vào chuỗi", False)
            nc.tay.bam(them)
            nc.tay.nghi(0.6, 1.2)
        o = w.dau_tien_thay([hop.locator(f"[data-testid='tweetTextarea_{i}']"),
                             hop.get_by_role("textbox").nth(i)], 8000)
        if not o:
            raise w.LoiDang(f"không thấy ô gõ cho phần {i + 1}", False)
        nc.nhat_ky(f"Gõ phần {i + 1}/{len(phan)} ({w.dem_ky_tu_x(p)}/{GIOI_HAN} theo cách X đếm)")
        w.go_vao(nc, o, p)
        nc.tay.nghi(0.6, 1.4)
        if i == 0 and tep:
            o_tep = hop.locator("input[data-testid='fileInput'], input[type='file']")
            if not o_tep.count():
                raise w.LoiDang("không thấy chỗ đính kèm ảnh/video", False)
            nc.nhat_ky(f"Đính kèm {len(tep)} tệp")
            o_tep.first.set_input_files(tep)
            nc.tay.nghi(2.0, 4.0)
            w.cho(lambda: not hop.get_by_role("progressbar").count(), 900, 2)
    nut = w.dau_tien_thay(w.ung_vien(hop, ten=["Đăng tất cả", "Post all", "Đăng", "Post", "Trả lời", "Reply"],
                                     css=["[data-testid='tweetButton']", "[data-testid='tweetButtonInline']"]), 8000)
    if not nut or nut.get_attribute("aria-disabled") == "true":
        raise w.LoiDang("nút Đăng của X đang khoá (quá giới hạn ký tự hoặc tệp chưa tải xong)", False)
    nc.tay.nghi(1.0, 2.5)
    tt.da_bam = True
    if not w.bam_cong_khai(nc, nut, "Trả lời trên X" if tra_loi else "Đăng bài X"):
        raise w.LoiDang("chạy thử", False)
    link = _cho_bao_da_gui(page, 60)
    w.kiem_chan(nc)
    if link is None:
        if w.co_chu(page, "đã nói điều này", "already said that", "Đã xảy ra lỗi", "Something went wrong"):
            raise w.LoiDang("X từ chối bài (trùng nội dung hoặc lỗi)", True)
        # không bắt được thông báo: đọc lại xem chữ đã hiện ngoài ô soạn chưa
        if not w.cho(lambda: w.thay_chu_ngoai_o_nhap(page, phan[0]), 10):
            raise w.LoiDang("đã bấm Đăng nhưng không thấy X xác nhận", True)
        link = ""
    return link or page.url


def _chon_tep(nc, tep: list) -> list:
    video = w.loc_tep(tep, w.DUOI_VIDEO)
    if video:
        if len(tep) > 1:
            nc.nhat_ky("X chỉ nhận 1 video mỗi bài: dùng video đầu, bỏ các tệp khác")
        return video[:1]
    anh = w.loc_tep(tep, w.DUOI_ANH)
    if len(anh) > 4:
        nc.nhat_ky(f"X nhận tối đa 4 ảnh: bỏ {len(anh) - 4} ảnh")
    return anh[:4]


def dang_bai(nc, noi_dung: str, tep: list, tt: w.TrangThaiDang = None) -> str:
    phan = w.chia_x(noi_dung, GIOI_HAN) or [""]
    tep = _chon_tep(nc, tep or [])
    if not phan[0] and not tep:
        raise w.LoiDang("bài rỗng", False)
    if len(phan) > 1:
        nc.nhat_ky(f"Bài dài: chia thành chuỗi {len(phan)} phần")
    _mo(nc, URL_SOAN)
    return soan_va_dang(nc, phan, tep, tt)


def x_dang_kho(nc) -> str:
    nc.mo(GOC + "/home")
    nc.kiem_dang_nhap()

    def _nghi():
        nc.nhat_ky("Chờ ít nhất 10 phút trước bài kế (luật X của MinMin)")
        return w.nghi_co_dung(nc, 600 + w.rng_nick(nc).uniform(0, 180))
    return w.chay_kho(nc, "dang_tuong", nc.ts.get("so_bai", 1), "Đăng X từ kho",
                      lambda bai, tt: dang_bai(nc, str(bai.get("noi_dung") or ""), bai.get("tep_cuc_bo") or [], tt),
                      nghi_giua=_nghi)


# --------------------------------------------------------------------------- x_quan_ly_bai

_MUC = {
    "ghim": (["Ghim vào trang cá nhân của bạn", "Pin to your profile", "Ghim vào hồ sơ", "Ghim"],
             ["Bỏ ghim khỏi trang cá nhân", "Unpin from profile", "Bỏ ghim"], ["Ghim", "Pin"], "ghim bài"),
    "bo_ghim": (["Bỏ ghim khỏi trang cá nhân", "Unpin from profile", "Bỏ ghim"],
                ["Ghim vào trang cá nhân của bạn", "Pin to your profile", "Ghim vào hồ sơ"], ["Bỏ ghim", "Unpin"],
                "bỏ ghim bài"),
    "xoa": (["Xoá", "Xóa", "Delete"], [], ["Xoá", "Xóa", "Delete"], "xoá bài"),
}


def _mo_menu(nc, bai):
    nut = w.dau_tien_thay(w.ung_vien(bai, ten=["Thêm", "More"], css=["[data-testid='caret']"]), 6000)
    if not nut:
        raise LoiKyNang("không thấy nút menu (...) của bài")
    nc.tay.bam(nut)
    nc.tay.nghi(0.6, 1.2)


def x_quan_ly_bai(nc) -> str:
    links = w.ds_dong(nc.ts.get("links"))
    viec = str(nc.ts.get("hanh_dong") or "ghim")
    muc_lam, muc_da, xn, mo_ta = _MUC.get(viec, _MUC["ghim"])
    dem = w.Dem()
    hd = "quan_ly_bai"
    nc.mo(links[0] if links else GOC + "/home")
    nc.kiem_dang_nhap()
    for link in links:
        if nc.nen_dung() or not w.con_luot(nc, dem, hd):
            break
        try:
            _mo(nc, link)
            bai = _bai_chinh(nc.page)
            _mo_menu(nc, bai)
            menu = nc.page.get_by_role("menu")
            if muc_da and w.tim(menu, role="menuitem", ten=muc_da, chua=True, timeout_ms=1500):
                nc.page.keyboard.press("Escape")
                w.bao(nc, dem, hd, "bo_qua", f"Bài đã ở trạng thái mong muốn, không cần {mo_ta}", link=link)
                continue
            muc = w.tim(menu, role="menuitem", ten=muc_lam, chua=(viec != "xoa"), timeout_ms=4000)
            if not muc:
                nc.page.keyboard.press("Escape")
                w.bao(nc, dem, hd, "loi", f"menu không có mục {mo_ta} (bài không phải của nick?)", link=link)
                continue
            if nc.chay_thu:
                nc.page.keyboard.press("Escape")
                w.bao_thu(nc, dem, hd, f"Chạy thử: sẽ {mo_ta}", link=link)
                continue
            nc.tay.bam(muc)                  # mở hộp xác nhận (chưa đổi gì)
            nc.tay.nghi(0.6, 1.2)
            ok_nut = w.dau_tien_thay(w.ung_vien(nc.page, ten=xn, css=["[data-testid='confirmationSheetConfirm']"]),
                                     5000)
            if not ok_nut:
                raise LoiKyNang(f"không thấy hộp xác nhận {mo_ta}")
            w.bam_cong_khai(nc, ok_nut, mo_ta)
            nc.tay.nghi(1.5, 3.0)
            if viec == "xoa":
                ok = w.cho(lambda: w.co_chu(nc.page, "Bài đăng của bạn đã bị xoá", "Bài đăng của bạn đã bị xóa",
                                            "Your post was deleted", "Bài đăng này đã bị xoá", "This post was deleted",
                                            "Trang này không tồn tại", "this page doesn"), 15)
            else:
                ok = w.co_chu(nc.page, "Đã ghim", "pinned", "Đã bỏ ghim", "unpinned")
                if not ok:      # đọc lại bằng menu
                    _mo_menu(nc, _bai_chinh(nc.page))
                    ok = bool(w.tim(nc.page.get_by_role("menu"), role="menuitem", ten=muc_da, chua=True,
                                    timeout_ms=3000))
                    nc.page.keyboard.press("Escape")
            w.bao(nc, dem, hd, "thanh_cong" if ok else "loi",
                  f"Đã {mo_ta} (đọc lại thấy)" if ok else f"đã bấm {mo_ta} nhưng đọc lại chưa thấy đổi", link=link)
            nc.nghi_thao_tac()
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return w.ket_thuc(nc, dem, "Quản lý bài X")


# --------------------------------------------------------------------------- tương tác

def _da(id_bat: str):
    """Nút X đổi data-testid khi bật: like -> unlike, retweet -> unretweet."""
    def f(loc):
        p = w.doc_trang_thai(loc).split(" | ")
        return len(p) > 3 and p[3] == id_bat
    return f


def _thich(nc, dem, bai, link) -> None:
    nut = w.dau_tien_thay([_testid(bai, "like", "unlike")] + w.ung_vien(bai, ten=["Thích", "Like"]), 5000)
    if not nut:
        w.bao(nc, dem, "thich", "loi", "không thấy nút Thích", link=link)
        return
    w.bam_va_xac_nhan(nc, dem, "thich", nut, _da("unlike"), "thích bài X", link)


def _dang_lai(nc, dem, bai, link) -> None:
    nut = w.dau_tien_thay([_testid(bai, "retweet", "unretweet")], 5000)
    if not nut:
        w.bao(nc, dem, "chia_se", "loi", "không thấy nút Đăng lại", link=link)
        return
    if _da("unretweet")(nut):
        w.bao(nc, dem, "chia_se", "bo_qua", "Đã đăng lại từ trước", link=link)
        return
    if nc.chay_thu:
        w.bao_thu(nc, dem, "chia_se", "Chạy thử: sẽ đăng lại bài", link=link)
        return
    pin = w.ghim(nut, "rt") or nut
    nc.tay.bam(nut)                     # mở menu Đăng lại / Trích dẫn (chưa công khai)
    nc.tay.nghi(0.5, 1.0)
    xn = w.dau_tien_thay(w.ung_vien(nc.page, role="menuitem", ten=["Đăng lại", "Repost"],
                                    css=["[data-testid='retweetConfirm']"]), 4000)
    if not xn:
        nc.page.keyboard.press("Escape")
        w.bao(nc, dem, "chia_se", "loi", "menu không có mục Đăng lại", link=link)
        return
    w.bam_cong_khai(nc, xn, "Đăng lại bài X")
    ok = w.cho(lambda: _da("unretweet")(pin), 8)
    w.kiem_chan(nc)
    w.bao(nc, dem, "chia_se", "thanh_cong" if ok else "loi",
          "Đã đăng lại (nút chuyển sang đã đăng lại)" if ok else "bấm Đăng lại nhưng nút chưa đổi", link=link)
    nc.nghi_thao_tac()


def x_tuong_tac_link(nc) -> str:
    ts = nc.ts
    links = w.ds_dong(ts.get("links"))
    dem = w.Dem()
    nc.mo(links[0] if links else GOC + "/home")
    nc.kiem_dang_nhap()
    for link in links:
        if nc.nen_dung():
            break
        try:
            _mo(nc, link)
            bai = _bai_chinh(nc.page)
            if ts.get("thich", True) and w.con_luot(nc, dem, "thich"):
                _thich(nc, dem, bai, link)
            if ts.get("dang_lai") and w.con_luot(nc, dem, "chia_se"):
                _dang_lai(nc, dem, _bai_chinh(nc.page), link)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "thich", e, link)
    return w.ket_thuc(nc, dem, "Tương tác X")


def x_nuoi_nick(nc) -> str:
    phut = float(nc.ts.get("phut", 10) or 10)
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/home")
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    han = time.monotonic() + phut * 60
    while time.monotonic() < han and not nc.nen_dung():
        w.kiem_chan(nc)
        nc.tay.luot(rng.randint(1, 3))
        if w.nghi_co_dung(nc, rng.uniform(3, 12)):
            break
        if rng.random() < 0.3 and w.con_luot(nc, dem, "thich"):
            ung = w.trong_khung(nc.page, _testid(nc.page, "like"))
            if ung:
                w.bam_va_xac_nhan(nc, dem, "thich", rng.choice(ung), _da("unlike"), "thích bài trên bảng tin",
                                  nc.page.url)
    w.bao(nc, dem, "thich", "thong_tin", f"Nuôi nick X: lướt {phut:g} phút, thích {dem.ok.get('thich', 0)}")
    return f"{'Chạy thử - ' if nc.chay_thu else ''}Nuôi nick X: {dem.tom_tat()}."


# --------------------------------------------------------------------------- x_tra_loi_tu_khoa

_JS_BAI = """(sel) => Array.from(document.querySelectorAll(sel)).map((a, i) => {
  const t = a.querySelector("[data-testid='tweetText']");
  const u = a.querySelector("[data-testid='User-Name']");
  const l = a.querySelector("a[href*='/status/'] time");
  const link = l ? l.parentElement.getAttribute('href') : '';
  const ten = u ? ((u.innerText || '').match(/@([A-Za-z0-9_]+)/) || [])[1] || '' : '';
  const tich = !!(u && u.querySelector("[data-testid='icon-verified'], svg[aria-label*='xác minh'], svg[aria-label*='Verified']"));
  const qc = !!a.querySelector("[data-testid='placementTracking']") ||
      /(^|\\n)(Quảng cáo|Ad|Promoted|Được quảng bá)(\\n|$)/.test(a.innerText || '');
  return {i, chu: t ? t.innerText : '', tac_gia: ten, link, tich, qc};
})"""


def x_tra_loi_tu_khoa(nc) -> str:
    ts = nc.ts
    tu_khoa = str(ts.get("tu_khoa") or "").strip()
    sp = str(ts.get("san_pham") or "")
    toi_da = int(ts.get("so_tra_loi", 3) or 3)
    dem = w.Dem()
    hd = "binh_luan"
    if not tu_khoa:
        raise LoiKyNang("thiếu từ khoá")
    url = f"{GOC}/search?q={urllib.parse.quote(tu_khoa)}&src=typed_query&f=live"
    nc.mo(url)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.5, 4.5)
    w.kiem_chan(nc)
    da_xet, lam, cuon = set(), 0, 0
    ung = []
    while len(ung) < toi_da * 4 and cuon < 6 and not nc.nen_dung():
        for b in nc.page.evaluate(_JS_BAI, BAI) or []:
            if not b.get("link") or b["link"] in da_xet:
                continue
            da_xet.add(b["link"])
            ly_do_bo = ("tích xanh/xám" if b.get("tich") else "quảng cáo" if b.get("qc") else
                        "chủ đề cấm (crypto/18+/chính trị)" if _TU_CAM.search(b.get("chu") or "") else
                        "bài quá ngắn" if len((b.get("chu") or "").strip()) < 15 else "")
            if ly_do_bo:
                nc.nhat_ky(f"Bỏ @{b.get('tac_gia')}: {ly_do_bo}")
                continue
            ung.append(b)
        nc.tay.luot(2)
        cuon += 1
    nc.nhat_ky(f"Từ khoá '{tu_khoa}': {len(ung)} bài hợp lệ")
    for b in ung:
        if nc.nen_dung() or lam >= toi_da or not w.con_luot(nc, dem, hd):
            break
        link = b["link"] if b["link"].startswith("http") else GOC + b["link"]
        m = re.search(r"/status/(\d+)", link)
        k = w.khoa(NT, "tra_loi", m.group(1) if m else link)
        if nc.da_lam(k, ca_doi=True):
            continue
        try:
            kq = w.lay_ai(nc, "viet_binh_luan", {"bai": {"chu": b["chu"], "tac_gia": b["tac_gia"], "link": link},
                                                 "san_pham_id": sp, "kieu": "tu_van" if sp else "tu_nhien"})
            nd = (w.chia_x(kq.get("noi_dung") or "", GIOI_HAN) or [""])[0]
            lam += 1
            w.noi_dung_ai(nc, dem, hd, loai="tra_loi", noi_dang=NT, link_goc=link, bai_goc=b["chu"],
                          ly_do=f"Bài của @{b['tac_gia']} khớp từ khoá '{tu_khoa}'", noi_dung=nd, khoa_lap=k,
                          dang=lambda s, link=link: tra_loi_link(nc, link, s), san_pham_id=sp)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return w.ket_thuc(nc, dem, "Trả lời X theo từ khoá")


def tra_loi_link(nc, link: str, noi_dung: str) -> str:
    _mo(nc, link)
    bai = _bai_chinh(nc.page)
    nut = w.dau_tien_thay([_testid(bai, "reply")] + w.ung_vien(bai, ten=["Trả lời", "Reply"]), 6000)
    if not nut:
        raise LoiKyNang("không thấy nút Trả lời")
    nc.tay.bam(nut)
    nc.tay.nghi(0.8, 1.6)
    phan = (w.chia_x(noi_dung, GIOI_HAN) or [""])[:1]
    try:
        return soan_va_dang(nc, phan, [], tra_loi=True)
    except w.LoiDang as e:
        raise LoiKyNang(str(e))


# --------------------------------------------------------------------------- dang_ban_nhap:x

def _nhap_bai(nc, p: dict) -> str:
    nc.mo(GOC + "/home")
    nc.kiem_dang_nhap()
    return dang_bai(nc, str(p.get("noi_dung") or ""), p.get("tep_cuc_bo") or [])


def _nhap_tra_loi(nc, p: dict) -> str:
    link, _, _ = w.tach_muc_tieu(p.get("link_goc"))
    if not link:
        raise LoiKyNang("nháp không có link bài")
    nc.mo(link)
    nc.kiem_dang_nhap()
    return tra_loi_link(nc, link, str(p.get("noi_dung") or ""))


def dang_ban_nhap(nc) -> str:
    return w.dang_ban_nhap_chung(nc, NT, {"bai_dang": lambda p: _nhap_bai(nc, p),
                                          "binh_luan": lambda p: _nhap_tra_loi(nc, p),
                                          "tra_loi": lambda p: _nhap_tra_loi(nc, p)})


KICH_BAN = {
    "x_dang_kho": x_dang_kho,
    "x_quan_ly_bai": x_quan_ly_bai,
    "x_tra_loi_tu_khoa": x_tra_loi_tu_khoa,
    "x_tuong_tac_link": x_tuong_tac_link,
    "x_nuoi_nick": x_nuoi_nick,
    "dang_ban_nhap:x": dang_ban_nhap,
}
