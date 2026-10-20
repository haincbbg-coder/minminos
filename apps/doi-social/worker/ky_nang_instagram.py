"""Kỹ năng Instagram: đăng từ kho (ảnh / nhiều ảnh / Reel, chú thích <= 2200, không nhận webp), đăng bài
AI đã duyệt (cần ảnh), nuôi nick, tương tác theo link, tự trả lời bình luận, đăng nhập Threads bằng
Instagram, và dang_ban_nhap:instagram.

Instagram vẽ nút bằng <div role=button><svg aria-label="Thích|Like" height="24">. Nút chính của bài có
svg cao 24, nút thích bình luận nhỏ hơn - nên lọc theo height để không bấm nhầm. Ô bình luận gửi bằng
Enter, nên chữ luôn gộp một dòng trước khi gõ.
"""
from __future__ import annotations

import os
import re
import tempfile
import time

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "instagram"
GOC = "https://www.instagram.com"
GIOI_HAN_CHU_THICH = 2200
THICH = ("Thích", "Like")
BO_THICH = ("Bỏ thích", "Unlike")
LUU = ("Lưu", "Save")
BO_LUU = ("Gỡ", "Remove", "Bỏ lưu")


def _mo(nc, url: str) -> None:
    nc.mo(url)
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)


def _nut_icon(goc, nhan, lon: bool = True):
    """Nút (cha gần nhất) của svg có nhãn; lon=True chỉ lấy biểu tượng cỡ 24 (nút chính của bài)."""
    loc_svg = goc.locator(", ".join(f"svg[aria-label='{n}']" + ("[height='24']" if lon else "") for n in nhan))
    if not loc_svg.count() and lon:
        loc_svg = goc.locator(", ".join(f"svg[aria-label='{n}']" for n in nhan))
    if not loc_svg.count():
        return None
    return loc_svg.first.locator(w.XP_NUT_CHA)


def _trang_thai_icon(loc, nhan_bat) -> bool:
    try:
        lab = loc.first.evaluate("e => { const s = e.querySelector('svg[aria-label]'); "
                                 "return s ? s.getAttribute('aria-label') : (e.getAttribute('aria-label') || ''); }")
    except Exception:
        return False
    return bool(w.re_nhan(*nhan_bat).match(lab or ""))


def _ten_chu_nick(nc) -> str:
    a = w.tim(nc.page, role="link", ten=["Trang cá nhân", "Profile"], chua=True, timeout_ms=5000)
    h = (a.get_attribute("href") or "") if a else ""
    m = re.match(r"^/([A-Za-z0-9._]+)/?$", h)
    return m.group(1) if m else ""


def _bai_dau_ho_so(nc, ten: str) -> str:
    _mo(nc, f"{GOC}/{ten}/")
    a = nc.page.locator("main a[href*='/p/'], main a[href*='/reel/']")
    if not w.cho(lambda: a.count() > 0, 10):
        return ""
    h = a.first.get_attribute("href") or ""
    return h if h.startswith("http") else GOC + h


# --------------------------------------------------------------------------- đăng bài

def _chuan_bi_tep(nc, tep: list) -> list:
    """Bỏ webp (Instagram không nhận): đổi sang JPEG nếu có Pillow, không thì bỏ kèm ghi nhật ký."""
    out = []
    for t in tep or []:
        if not str(t).lower().endswith(".webp"):
            out.append(t)
            continue
        try:
            from PIL import Image   # tuỳ chọn
            d = os.path.join(tempfile.gettempdir(), os.path.basename(str(t))[:-5] + ".jpg")
            Image.open(t).convert("RGB").save(d, "JPEG", quality=92)
            out.append(d)
            nc.nhat_ky(f"Đổi {os.path.basename(str(t))} từ webp sang jpg")
        except Exception:
            nc.nhat_ky(f"Bỏ {os.path.basename(str(t))}: Instagram không nhận webp (máy chưa có Pillow để đổi)")
    return [t for t in out if str(t).lower().endswith(w.DUOI_ANH + w.DUOI_VIDEO)][:10]


def dang_bai(nc, chu_thich: str, tep: list, tt: w.TrangThaiDang = None) -> str:
    """Tạo -> Bài viết -> chọn tệp -> Tiếp -> Tiếp -> chú thích -> Chia sẻ. Thành công khi Instagram báo
    đã chia sẻ VÀ bài đầu trên trang cá nhân đổi (đọc lại)."""
    tt = tt or w.TrangThaiDang()
    page = nc.page
    tep = _chuan_bi_tep(nc, tep)
    if not tep:
        raise w.LoiDang("không có ảnh/video hợp lệ (Instagram bắt buộc có ảnh hoặc video)", False)
    chu_thich = str(chu_thich or "").strip()
    if len(chu_thich) > GIOI_HAN_CHU_THICH:
        nc.nhat_ky(f"Chú thích dài {len(chu_thich)} ký tự, cắt còn {GIOI_HAN_CHU_THICH}")
        chu_thich = chu_thich[:GIOI_HAN_CHU_THICH]
    _mo(nc, GOC + "/")
    ten = _ten_chu_nick(nc)
    truoc = _bai_dau_ho_so(nc, ten) if ten else ""
    if ten:
        _mo(nc, GOC + "/")
    tao = w.tim(page, role="link", ten=["Bài viết mới", "New post", "Tạo", "Create"], chua=True,
                nhan=["Bài viết mới", "New post"], timeout_ms=10000)
    if not tao:
        raise w.LoiDang("không thấy nút Tạo / Bài viết mới", False)
    nc.tay.bam(tao)
    nc.tay.nghi(0.8, 1.6)
    muc = w.tim(page, ten=["Bài viết", "Post"], role="link", timeout_ms=2500) or \
        w.tim(page, ten=["Bài viết", "Post"], role="menuitem", timeout_ms=1500)
    if muc:
        nc.tay.bam(muc)
        nc.tay.nghi(0.8, 1.6)
    hop = w.dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("input[type='file']"))], 15000)
    if not hop:
        raise w.LoiDang("hộp 'Tạo bài viết mới' không hiện", False)
    nc.nhat_ky(f"Chọn {len(tep)} tệp")
    hop.locator("input[type='file']").first.set_input_files(tep)
    nc.tay.nghi(2.0, 4.0)
    ok_reel = w.tim(page, ten=["OK"], timeout_ms=2500)      # "Bài video giờ được chia sẻ dưới dạng thước phim"
    if ok_reel:
        nc.tay.bam(ok_reel)
    for buoc in ("cắt", "bộ lọc"):
        tiep = w.tim(page.get_by_role("dialog"), ten=["Tiếp", "Next"], timeout_ms=20000)
        if not tiep:
            raise w.LoiDang(f"không thấy nút Tiếp ở bước {buoc}", False)
        nc.tay.bam(tiep)
        nc.tay.nghi(1.2, 2.5)
    if chu_thich:
        o = w.tim(page, role="textbox", ten=["Viết chú thích", "Write a caption"], chua=True,
                  nhan=["Viết chú thích...", "Write a caption..."], timeout_ms=10000)
        if not o:
            raise w.LoiDang("không thấy ô chú thích", False)
        nc.nhat_ky(f"Gõ chú thích ({len(chu_thich)} ký tự)")
        w.go_vao(nc, o, chu_thich)
        nc.tay.nghi(1.0, 2.0)
    chia = w.tim(page.get_by_role("dialog"), ten=["Chia sẻ", "Share"], timeout_ms=10000)
    if not chia:
        raise w.LoiDang("không thấy nút Chia sẻ", False)
    tt.da_bam = True
    if not w.bam_cong_khai(nc, chia, "Chia sẻ bài Instagram"):
        raise w.LoiDang("chạy thử", False)
    ok = w.cho(lambda: w.co_chu(page, "Đã chia sẻ bài viết", "Your post has been shared", "Đã chia sẻ thước phim",
                                "Your reel has been shared", "Bài viết của bạn đã được chia sẻ",
                                "Thước phim của bạn đã được chia sẻ"), 600, 2)
    w.kiem_chan(nc)
    if not ok:
        raise w.LoiDang("đã bấm Chia sẻ nhưng Instagram chưa báo đã chia sẻ", True)
    nc.page.keyboard.press("Escape")
    if not ten:
        nc.nhat_ky("Không đọc được tên hồ sơ để đối chiếu, dựa vào thông báo đã chia sẻ")
        return ""
    sau = ""
    for _ in range(3):
        sau = _bai_dau_ho_so(nc, ten)
        if sau and sau != truoc:
            return sau
        nc.tay.nghi(4.0, 8.0)
    raise w.LoiDang("Instagram báo đã chia sẻ nhưng trang cá nhân chưa thấy bài mới", True)


def ig_dang_kho(nc) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    return w.chay_kho(nc, "dang_tuong", nc.ts.get("so_bai", 1), "Đăng Instagram từ kho",
                      lambda bai, tt: dang_bai(nc, str(bai.get("noi_dung") or ""), bai.get("tep_cuc_bo") or [], tt),
                      kiem_bai=lambda b: "" if w.loc_tep(b.get("tep_cuc_bo") or [], w.DUOI_ANH + w.DUOI_VIDEO)
                      else "bài không có ảnh/video")


def ig_dang_ai(nc) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()

    def _dang(bn):
        tep = bn.get("tep_cuc_bo") or []
        if not tep:
            raise LoiKyNang("nháp chưa có ảnh tải sẵn trên máy (Instagram bắt buộc có ảnh)")
        return dang_bai(nc, str(bn.get("noi_dung") or ""), tep)
    return w.dang_ai_da_duyet(nc, NT, "dang_tuong", int(nc.ts.get("so_bai", 1) or 1), "Đăng bài AI lên Instagram",
                              _dang)


# --------------------------------------------------------------------------- bình luận

def _o_binh_luan(page):
    return w.tim(page, role="textbox", ten=["Thêm bình luận", "Add a comment"], chua=True,
                 css=["textarea[aria-label*='bình luận']", "textarea[aria-label*='comment']", "form textarea"],
                 timeout_ms=8000)


def binh_luan(nc, text: str) -> bool:
    page = nc.page
    o = _o_binh_luan(page)
    if not o:
        raise LoiKyNang("không thấy ô bình luận")
    return w.gui_noi_dung(nc, o, w.mot_dong(text),
                          nut_gui=lambda: w.tim(page, ten=["Đăng", "Post"], timeout_ms=4000),
                          enter_gui=True, mo_ta="Đăng bình luận Instagram")


# --------------------------------------------------------------------------- ig_tuong_tac_link

def ig_tuong_tac_link(nc) -> str:
    ts = nc.ts
    links = w.ds_dong(ts.get("links"))
    cau = w.ds_dong(ts.get("cau_binh_luan"))
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(links[0] if links else GOC + "/")
    nc.kiem_dang_nhap()
    for link in links:
        if nc.nen_dung():
            break
        try:
            _mo(nc, link)
            if ts.get("thich", True) and w.con_luot(nc, dem, "thich"):
                nut = _nut_icon(nc.page, THICH + BO_THICH)
                if nut is None:
                    w.bao(nc, dem, "thich", "loi", "không thấy nút Thích", link=link)
                else:
                    w.bam_va_xac_nhan(nc, dem, "thich", nut, lambda l: _trang_thai_icon(l, BO_THICH),
                                      "thích bài Instagram", link)
            if cau and w.con_luot(nc, dem, "binh_luan"):
                k = w.khoa(NT, "binh_luan", link)
                c = w.mot_dong(rng.choice(cau))
                if nc.da_lam(k):
                    w.bao(nc, dem, "binh_luan", "bo_qua", "nick đã bình luận bài này", link=link)
                elif nc.chay_thu:
                    w.bao_thu(nc, dem, "binh_luan", f"Chạy thử: sẽ bình luận \"{c[:80]}\"", link=link)
                elif binh_luan(nc, c):
                    nc.ghi_da_lam(k)
                    w.bao(nc, dem, "binh_luan", "thanh_cong", f"Bình luận \"{c[:60]}\" đã hiện", link=link)
                    nc.nghi_thao_tac()
                else:
                    w.bao(nc, dem, "binh_luan", "loi", "đã gửi nhưng chưa thấy bình luận hiện", link=link)
            if ts.get("luu") and w.con_luot(nc, dem, "luu"):
                nut = _nut_icon(nc.page, LUU + BO_LUU)
                if nut is None:
                    w.bao(nc, dem, "luu", "loi", "không thấy nút Lưu", link=link)
                else:
                    w.bam_va_xac_nhan(nc, dem, "luu", nut, lambda l: _trang_thai_icon(l, BO_LUU), "lưu bài", link)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "thich", e, link)
    return w.ket_thuc(nc, dem, "Tương tác Instagram")


# --------------------------------------------------------------------------- ig_nuoi_nick

def ig_nuoi_nick(nc) -> str:
    phut = float(nc.ts.get("phut", 10) or 10)
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    han = time.monotonic() + phut * 60
    # 1) xem vài tin
    tin = w.tim(nc.page, ten=["Tin của", "Story by"], chua=True, timeout_ms=4000)
    if tin:
        nc.nhat_ky("Xem tin (story)")
        nc.tay.bam(tin)
        w.nghi_co_dung(nc, rng.uniform(8, 25))
        nc.page.keyboard.press("Escape")
        nc.tay.nghi(1.0, 2.0)
    # 2) lướt bảng tin, rồi 3) Reels ở nửa sau thời gian
    da_reels = False
    while time.monotonic() < han and not nc.nen_dung():
        w.kiem_chan(nc)
        if not da_reels and time.monotonic() > han - phut * 30:
            da_reels = True
            _mo(nc, GOC + "/reels/")
        if da_reels:
            nc.page.keyboard.press("ArrowDown")
        else:
            nc.tay.luot(rng.randint(1, 3))
        if w.nghi_co_dung(nc, rng.uniform(4, 15)):
            break
        if rng.random() < 0.25 and w.con_luot(nc, dem, "thich"):
            loc = nc.page.locator(", ".join(f"svg[aria-label='{n}'][height='24']" for n in THICH))
            ung = w.trong_khung(nc.page, loc)
            if ung:
                nut = rng.choice(ung).locator(w.XP_NUT_CHA)
                w.bam_va_xac_nhan(nc, dem, "thich", nut, lambda l: _trang_thai_icon(l, BO_THICH),
                                  "thích bài trên bảng tin", nc.page.url)
    w.bao(nc, dem, "thich", "thong_tin", f"Nuôi nick Instagram: {phut:g} phút (tin, bảng tin, Reels), "
                                         f"thích {dem.ok.get('thich', 0)}")
    return f"{'Chạy thử - ' if nc.chay_thu else ''}Nuôi nick Instagram: {dem.tom_tat()}."


# --------------------------------------------------------------------------- ig_tra_loi_binh_luan

_JS_BL = """(ten_chu) => {
  const out = [];
  const nut = Array.from(document.querySelectorAll("[role='button'], button"))
      .filter(b => /^(Trả lời|Reply)$/i.test((b.innerText || '').trim()));
  nut.forEach((b, i) => {
    let c = b, a = null;
    for (let k = 0; k < 8 && c; k++) {
      c = c.parentElement;
      if (!c) break;
      a = c.querySelector("a[href^='/'][role='link'], a[href^='/']");
      if (a && /^\\/[A-Za-z0-9._]+\\/$/.test(a.getAttribute('href'))) break;
      a = null;
    }
    if (!a || !c) return;
    const tg = a.getAttribute('href').replace(/\\//g, '');
    const sp = Array.from(c.querySelectorAll("span[dir='auto'], span")).map(s => (s.innerText || '').trim())
      .filter(s => s && s !== tg && !/^(Trả lời|Reply|Thích|Like|\\d+\\s*(tuần|ngày|giờ|phút|w|d|h|m))$/i.test(s));
    sp.sort((x, y) => y.length - x.length);
    b.setAttribute('data-minmin-bl', String(i));
    out.push({i, tac_gia: tg, chu: (sp[0] || '').slice(0, 1000)});
  });
  return out.filter(x => x.tac_gia && x.tac_gia !== ten_chu && x.chu);
}"""


def _tra_loi_bl(nc, i: int, text: str) -> bool:
    nut = nc.page.locator(f"[data-minmin-bl='{i}']")
    if not nut.count():
        raise LoiKyNang("không tìm lại được nút Trả lời của bình luận")
    nc.tay.bam(nut.first)        # điền sẵn @tác_giả vào ô bình luận (chưa công khai)
    nc.tay.nghi(0.6, 1.2)
    return binh_luan(nc, text)


def ig_tra_loi_binh_luan(nc) -> str:
    sp = str(nc.ts.get("san_pham") or "")
    dem = w.Dem()
    hd = "tra_loi_binh_luan"
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    ten = _ten_chu_nick(nc)
    if not ten:
        raise LoiKyNang("không đọc được tên trang cá nhân Instagram của nick")
    _mo(nc, f"{GOC}/{ten}/")
    bai = []
    for a in nc.page.locator("main a[href*='/p/'], main a[href*='/reel/']").all()[:12]:
        h = a.get_attribute("href") or ""
        h = h if h.startswith("http") else GOC + h
        if h not in bai:
            bai.append(h)
        if len(bai) >= 3:
            break
    nc.nhat_ky(f"@{ten}: xét {len(bai)} bài gần nhất")
    for link in bai:
        if nc.nen_dung() or not w.con_luot(nc, dem, hd):
            break
        try:
            _mo(nc, link)
            cap = ""
            h1 = w.tim(nc.page, css=["h1"], timeout_ms=2000)
            if h1:
                cap = h1.inner_text()[:1000]
            for bl in nc.page.evaluate(_JS_BL, ten) or []:
                if nc.nen_dung() or not w.con_luot(nc, dem, hd):
                    break
                k = w.khoa(NT, "tra_loi", link, bl["tac_gia"], w.bam_chuoi(bl["chu"]))
                if nc.da_lam(k):
                    continue
                kq = w.lay_ai(nc, "tra_loi_binh_luan", {
                    "bai_cua_nick": True, "bai": {"chu": cap, "link": link},
                    "binh_luan": {"tac_gia": bl["tac_gia"], "chu": bl["chu"]}, "san_pham_id": sp})
                if kq.get("can_hoi_chu"):
                    nc.ghi_da_lam(k)
                    w.bao(nc, dem, hd, "bo_qua", f"Chuyển bạn trả lời: {bl['chu'][:80]}", link=link)
                    continue
                i = bl["i"]

                def _dang(nd, i=i):
                    if not _tra_loi_bl(nc, i, nd):
                        raise LoiKyNang("đã gửi trả lời nhưng chưa thấy hiện")
                    return link
                w.noi_dung_ai(nc, dem, hd, loai="tra_loi", noi_dang=NT,
                              link_goc=w.gan_muc_tieu(link, bl["tac_gia"], bl["chu"]), bai_goc=cap,
                              ly_do=f"@{bl['tac_gia']} bình luận: {bl['chu'][:150]}",
                              noi_dung=w.mot_dong(kq.get("noi_dung") or ""), khoa_lap=k, dang=_dang, san_pham_id=sp)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return w.ket_thuc(nc, dem, "Trả lời bình luận Instagram")


# --------------------------------------------------------------------------- ig_dang_nhap_threads

URL_THREADS_LOGIN = "https://www.threads.com/login"


def _vao_bang_tin_threads(page) -> bool:
    u = (page.url or "").lower()
    if "/login" in u:
        return False
    return w.co_chu(page, "Có gì mới", "What's new", "Dành cho bạn", "For you") or bool(
        w.tim(page, role="link", ten=["Trang chủ", "Home"], nhan=["Trang chủ", "Home"], timeout_ms=1500))


def ig_dang_nhap_threads(nc) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()                       # nick phải đang vào được Instagram trước
    nc.mo(URL_THREADS_LOGIN)
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc, cho_phep_trang_dang_nhap=True)
    page = nc.page
    if _vao_bang_tin_threads(page):
        nc.su_kien("dang_nhap", "thanh_cong", "Threads đã đăng nhập sẵn (đọc lại thấy bảng tin)", link=page.url)
        return "Threads đã đăng nhập sẵn."
    nut = w.tim(page, ten=["Tiếp tục bằng Instagram", "Continue with Instagram", "Đăng nhập bằng Instagram",
                           "Log in with Instagram"], chua=True,
                chu=["Tiếp tục bằng Instagram", "Continue with Instagram", "Đăng nhập bằng Instagram",
                     "Log in with Instagram"], role="link", timeout_ms=8000) or \
        w.tim(page, ten=["Tiếp tục bằng Instagram", "Continue with Instagram", "Instagram"], chua=True, timeout_ms=3000)
    if nc.chay_thu:
        ct = ("Chạy thử: Threads chưa đăng nhập; sẽ bấm 'Tiếp tục bằng Instagram'" if nut else
              "Chạy thử: Threads chưa đăng nhập và không thấy nút 'Tiếp tục bằng Instagram'")
        nc.su_kien("dang_nhap", "thong_tin", ct, link=page.url)
        return ct
    if not nut:
        raise LoiKyNang("không thấy nút 'Tiếp tục bằng Instagram' trên trang đăng nhập Threads")
    nc.tay.bam(nut)                            # đăng nhập: không công khai gì ra ngoài
    nc.tay.nghi(3.0, 6.0)
    # Có thể hỏi "Tiếp tục với tư cách <tên>", rồi các bước chào mừng (Tiếp / Nhập từ Instagram / Tham gia)
    for _ in range(6):
        if _vao_bang_tin_threads(page):
            break
        w.kiem_chan(nc, cho_phep_trang_dang_nhap=True)
        b = w.tim(page, ten=["Tiếp tục với tư cách", "Continue as", "Tiếp tục", "Continue", "Tiếp", "Next",
                             "Nhập từ Instagram", "Import from Instagram", "Tham gia Threads", "Join Threads",
                             "Bỏ qua", "Skip"], chua=True, timeout_ms=6000)
        if not b:
            break
        nc.nhat_ky(f"Bấm '{(b.inner_text() or '').strip()[:40]}'")
        nc.tay.bam(b)
        nc.tay.nghi(2.0, 4.0)
    if not w.cho(lambda: _vao_bang_tin_threads(page), 20):
        nc.su_kien("dang_nhap", "loi", f"Chưa vào được bảng tin Threads ({page.url[:80]})", link=page.url)
        raise LoiKyNang("đã bấm đăng nhập bằng Instagram nhưng chưa vào được bảng tin Threads")
    nc.su_kien("dang_nhap", "thanh_cong", "Đã đăng nhập Threads bằng Instagram (thấy bảng tin)", link=page.url)
    return "Đã đăng nhập Threads bằng Instagram."


# --------------------------------------------------------------------------- dang_ban_nhap:instagram

def _nhap_bai(nc, p: dict) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    tep = p.get("tep_cuc_bo") or []
    if not tep:
        raise LoiKyNang("nháp bài Instagram chưa có ảnh tải sẵn trên máy")
    return dang_bai(nc, str(p.get("noi_dung") or ""), tep)


def _nhap_bl(nc, p: dict) -> str:
    link, tg, chu = w.tach_muc_tieu(p.get("link_goc"))
    if not link:
        raise LoiKyNang("nháp không có link bài")
    nc.mo(link)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)
    nd = w.mot_dong(p.get("noi_dung") or "")
    if tg:
        ds = nc.page.evaluate(_JS_BL, "") or []
        dich = next((b for b in ds if b["tac_gia"] == tg and (not chu or chu[:20] in b["chu"])), None)
        if not dich:
            raise LoiKyNang(f"không tìm lại được bình luận của @{tg}")
        ok = _tra_loi_bl(nc, dich["i"], nd)
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
    "ig_dang_kho": ig_dang_kho,
    "ig_dang_ai": ig_dang_ai,
    "ig_nuoi_nick": ig_nuoi_nick,
    "ig_tuong_tac_link": ig_tuong_tac_link,
    "ig_tra_loi_binh_luan": ig_tra_loi_binh_luan,
    "ig_dang_nhap_threads": ig_dang_nhap_threads,
    "dang_ban_nhap:instagram": dang_ban_nhap,
}
