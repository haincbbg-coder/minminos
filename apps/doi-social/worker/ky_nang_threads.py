"""Kỹ năng Threads (threads.com): đăng từ kho / bài AI đã duyệt (chuỗi bài, --- tách, <=500 ký tự/phần,
<=20 ảnh), tương tác theo link (thích, trả lời, đăng lại), nuôi nick, tự trả lời bình luận, tương tác bài
đội đã đăng, quét ra CSV, và dang_ban_nhap:threads.

Threads web vẽ nút bằng <div role="button"> chứa <svg aria-label="Thích|Like">; sau khi thích nhãn
svg đổi thành "Bỏ thích|Unlike" - đó là tín hiệu đọc lại. Mỗi bài/trả lời nằm trong
`div[data-pressable-container]` (thuộc tính cố định, không phải class băm).
"""
from __future__ import annotations

import re
import time
import urllib.parse

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "threads"
GOC = "https://www.threads.com"
GIOI_HAN = 500
TOI_DA_ANH = 20
KHOI = "div[data-pressable-container='true']"


def _mo(nc, url: str) -> None:
    nc.mo(url)
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)


def _link_day_du(h: str) -> str:
    h = (h or "").split("?")[0]
    return h if h.startswith("http") else GOC + h


def _nut_svg(goc, *nhan: str):
    """Nút <div role=button> chứa svg có nhãn (cả trạng thái trước và sau)."""
    return w.dau_tien_thay(w.ung_vien(goc, ten=list(nhan), nhan=list(nhan)), 4000)


def _da_thich(loc) -> bool:
    return w.nhan_bat(loc, "Bỏ thích", "Unlike")


def _khoi_chinh(page):
    k = page.locator(KHOI)
    return k.first if k.count() else page


def _ten_chu_nick(nc) -> str:
    a = w.tim(nc.page, role="link", ten=["Trang cá nhân", "Profile"], nhan=["Trang cá nhân", "Profile"],
              timeout_ms=4000)
    if a:
        h = a.get_attribute("href") or ""
        if not h:
            try:
                h = a.locator("xpath=ancestor-or-self::a[1]").get_attribute("href") or ""
            except Exception:
                h = ""
        m = re.search(r"/@([^/?#]+)", h)
        if m:
            return m.group(1)
    return ""


# --------------------------------------------------------------------------- soạn + đăng bài

def _mo_hop_soan(nc):
    page = nc.page
    mo = w.tim(page, ten=["Có gì mới", "What's new", "Tạo", "Create", "Bắt đầu thread", "Start a thread"],
               chua=True, nhan=["Tạo", "Create"], chu=["Có gì mới?", "What's new?"], timeout_ms=15000)
    if not mo:
        raise w.LoiDang("không thấy ô 'Có gì mới?' để soạn bài Threads", False)
    nc.tay.bam(mo)
    nc.tay.nghi(1.0, 2.0)
    hop = w.dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("[contenteditable='true']"))], 15000)
    if not hop:
        raise w.LoiDang("bấm soạn bài nhưng hộp soạn không hiện", False)
    return hop


def dang_chuoi(nc, noi_dung: str, tep: list, tt: w.TrangThaiDang = None) -> str:
    """Soạn và đăng một chuỗi bài Threads. Trả link bài (hoặc trang hồ sơ) khi đọc lại thấy bài lên."""
    tt = tt or w.TrangThaiDang()
    page = nc.page
    phan = w.chia_threads(noi_dung, GIOI_HAN)
    anh = w.loc_tep(tep or [], w.DUOI_ANH + w.DUOI_VIDEO)[:TOI_DA_ANH]
    if not phan and not anh:
        raise w.LoiDang("bài rỗng", False)
    if len(tep or []) > len(anh):
        nc.nhat_ky(f"Bỏ bớt {len(tep) - len(anh)} tệp (Threads nhận tối đa {TOI_DA_ANH} ảnh/video)")
    _mo(nc, GOC + "/")
    hop = _mo_hop_soan(nc)
    for i, p in enumerate(phan or [""]):
        if i:
            them = w.tim(hop, ten=["Thêm vào chuỗi", "Add to thread"], chua=True,
                         chu=["Thêm vào chuỗi", "Add to thread"], timeout_ms=5000)
            if not them:
                raise w.LoiDang("không thấy nút 'Thêm vào chuỗi' để nối phần tiếp theo", False)
            nc.tay.bam(them)
            nc.tay.nghi(0.8, 1.5)
        o = hop.locator("[contenteditable='true']")
        if not w.cho(lambda: o.count() > i, 5):
            raise w.LoiDang(f"không thấy ô gõ cho phần {i + 1}", False)
        if p:
            nc.nhat_ky(f"Gõ phần {i + 1}/{len(phan)} ({len(p)} ký tự)")
            w.go_vao(nc, o.nth(i), p)
            nc.tay.nghi(0.6, 1.4)
        if i == 0 and anh:
            o_tep = hop.locator("input[type='file']")
            if not o_tep.count():
                raise w.LoiDang("không thấy chỗ đính kèm ảnh trong hộp soạn", False)
            nc.nhat_ky(f"Đính kèm {len(anh)} ảnh/video")
            o_tep.first.set_input_files(anh)
            nc.tay.nghi(3.0, 6.0)
            w.cho(lambda: not hop.get_by_role("progressbar").count(), 600, 2)
    nut = w.tim(hop, ten=["Đăng", "Post"], timeout_ms=8000)
    if not nut or nut.get_attribute("aria-disabled") == "true":
        raise w.LoiDang("nút Đăng của Threads đang khoá", False)
    nc.tay.nghi(1.0, 2.5)
    tt.da_bam = True
    if not w.bam_cong_khai(nc, nut, "Đăng bài Threads"):
        raise w.LoiDang("chạy thử", False)
    dong = w.cho(lambda: not hop.is_visible(), 180, 1.0)
    w.kiem_chan(nc)
    if not dong:
        raise w.LoiDang("đã bấm Đăng nhưng hộp soạn chưa đóng", True)
    xem = w.tim(page, role="link", ten=["Xem", "View"], timeout_ms=15000)
    if xem:
        h = xem.get_attribute("href") or ""
        if "/post/" in h:
            return _link_day_du(h)
    # Không bắt được thông báo: mở hồ sơ, đọc lại thấy đầu bài
    ten = _ten_chu_nick(nc)
    if ten:
        _mo(nc, f"{GOC}/@{ten}")
        dau = w.doan_nhan_dien(phan[0] if phan else "")
        if not dau or w.cho(lambda: w.thay_chu_ngoai_o_nhap(page, dau), 20):
            k = page.locator(f"{KHOI} a[href*='/post/']")
            return _link_day_du(k.first.get_attribute("href")) if k.count() else page.url
    raise w.LoiDang("đã đăng nhưng đọc lại hồ sơ chưa thấy bài mới", True)


def th_dang_kho(nc) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    return w.chay_kho(nc, "dang_tuong", nc.ts.get("so_bai", 1), "Đăng Threads từ kho",
                      lambda bai, tt: dang_chuoi(nc, str(bai.get("noi_dung") or ""), bai.get("tep_cuc_bo") or [], tt))


def th_dang_ai(nc) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    return w.dang_ai_da_duyet(nc, NT, "dang_tuong", int(nc.ts.get("so_bai", 1) or 1), "Đăng bài AI lên Threads",
                              lambda bn: dang_chuoi(nc, str(bn.get("noi_dung") or ""), bn.get("tep_cuc_bo") or []))


# --------------------------------------------------------------------------- trả lời một bài

def tra_loi_bai(nc, khoi, text: str) -> bool:
    """Bấm Trả lời trong khối bài, gõ vào hộp, bấm Đăng, đọc lại thấy chữ hiện."""
    page = nc.page
    nut = _nut_svg(khoi, "Trả lời", "Reply")
    if not nut:
        raise LoiKyNang("không thấy nút Trả lời")
    nc.tay.bam(nut)
    nc.tay.nghi(1.0, 2.0)
    hop = w.dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("[contenteditable='true']"))], 8000)
    goc = hop or page
    o = w.dau_tien_thay([goc.locator("[contenteditable='true']")], 5000)
    if not o:
        raise LoiKyNang("không thấy ô gõ trả lời")
    return w.gui_noi_dung(nc, o, w.cat_gioi_han(text, GIOI_HAN),
                          nut_gui=lambda: w.tim(goc, ten=["Đăng", "Post"], timeout_ms=5000),
                          mo_ta="Đăng trả lời Threads", giay_xac_nhan=25)


# --------------------------------------------------------------------------- th_tuong_tac

def _dang_lai(nc, dem, khoi, link) -> None:
    nut = _nut_svg(khoi, "Đăng lại", "Repost")
    if not nut:
        w.bao(nc, dem, "chia_se", "loi", "không thấy nút Đăng lại", link=link)
        return
    if nc.chay_thu:
        w.bao_thu(nc, dem, "chia_se", "Chạy thử: sẽ đăng lại bài", link=link)
        return
    nc.tay.bam(nut)                      # mở menu (chưa công khai)
    nc.tay.nghi(0.6, 1.2)
    if w.tim(nc.page, role="menuitem", ten=["Xoá", "Remove"], chua=True, timeout_ms=1500):
        nc.page.keyboard.press("Escape")
        w.bao(nc, dem, "chia_se", "bo_qua", "Đã đăng lại từ trước", link=link)
        return
    muc = w.tim(nc.page, role="menuitem", ten=["Đăng lại", "Repost"], chu=["Đăng lại", "Repost"], timeout_ms=4000)
    if not muc:
        nc.page.keyboard.press("Escape")
        w.bao(nc, dem, "chia_se", "loi", "menu không có mục Đăng lại", link=link)
        return
    w.bam_cong_khai(nc, muc, "Đăng lại bài Threads")
    ok = w.cho(lambda: w.co_chu(nc.page, "Đã đăng lại", "Reposted"), 10)
    if not ok:     # đọc lại bằng menu: đã đăng lại thì menu có 'Xoá'
        nc.tay.bam(nut)
        ok = bool(w.tim(nc.page, role="menuitem", ten=["Xoá", "Remove"], chua=True, timeout_ms=3000))
        nc.page.keyboard.press("Escape")
    w.bao(nc, dem, "chia_se", "thanh_cong" if ok else "loi",
          "Đã đăng lại (đọc lại thấy)" if ok else "bấm Đăng lại nhưng chưa thấy xác nhận", link=link)
    nc.nghi_thao_tac()


def th_tuong_tac(nc) -> str:
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
            khoi = _khoi_chinh(nc.page)
            if ts.get("thich", True) and w.con_luot(nc, dem, "thich"):
                nut = _nut_svg(khoi, "Thích", "Like", "Bỏ thích", "Unlike")
                if nut:
                    w.bam_va_xac_nhan(nc, dem, "thich", nut, _da_thich, "thích bài Threads", link)
                else:
                    w.bao(nc, dem, "thich", "loi", "không thấy nút Thích", link=link)
            if cau and w.con_luot(nc, dem, "binh_luan"):
                k = w.khoa(NT, "binh_luan", link)
                c = rng.choice(cau)
                if nc.da_lam(k):
                    w.bao(nc, dem, "binh_luan", "bo_qua", "nick đã trả lời bài này", link=link)
                elif nc.chay_thu:
                    w.bao_thu(nc, dem, "binh_luan", f"Chạy thử: sẽ trả lời \"{c[:80]}\"", link=link)
                elif tra_loi_bai(nc, khoi, c):
                    nc.ghi_da_lam(k)
                    w.bao(nc, dem, "binh_luan", "thanh_cong", f"Trả lời \"{c[:60]}\" đã hiện", link=link)
                    nc.nghi_thao_tac()
                else:
                    w.bao(nc, dem, "binh_luan", "loi", "đã gửi trả lời nhưng chưa thấy hiện", link=link)
            if ts.get("dang_lai") and w.con_luot(nc, dem, "chia_se"):
                _dang_lai(nc, dem, _khoi_chinh(nc.page), link)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "thich", e, link)
    return w.ket_thuc(nc, dem, "Tương tác Threads")


# --------------------------------------------------------------------------- th_nuoi_nick

def th_nuoi_nick(nc) -> str:
    phut = float(nc.ts.get("phut", 10) or 10)
    rng = w.rng_nick(nc)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    han = time.monotonic() + phut * 60
    vong = 0
    while time.monotonic() < han and not nc.nen_dung():
        vong += 1
        w.kiem_chan(nc)
        nc.tay.luot(rng.randint(1, 3))
        if w.nghi_co_dung(nc, rng.uniform(3, 12)):
            break
        if rng.random() < 0.3 and w.con_luot(nc, dem, "thich"):
            loc = nc.page.get_by_role("button", name=w.re_nhan("Thích", "Like"))
            ung = w.trong_khung(nc.page, loc)
            if ung:
                w.bam_va_xac_nhan(nc, dem, "thich", rng.choice(ung), _da_thich, "thích bài trên bảng tin",
                                  nc.page.url)
    w.bao(nc, dem, "thich", "thong_tin", f"Nuôi nick Threads: lướt {phut:g} phút ({vong} lượt cuộn), "
                                         f"thích {dem.ok.get('thich', 0)}")
    return f"{'Chạy thử - ' if nc.chay_thu else ''}Nuôi nick Threads: {dem.tom_tat()}."


# --------------------------------------------------------------------------- đọc khối bài

_JS_KHOI = """(sel) => Array.from(document.querySelectorAll(sel)).map((e, i) => {
  const a = e.querySelector("a[href^='/@']");
  const p = e.querySelector("a[href*='/post/']");
  const t = e.querySelector('time');
  const m = a ? (a.getAttribute('href').match(/^\\/@([^/?#]+)/) || []) : [];
  const ten = m[1] || '';
  const dong = (e.innerText || '').split('\\n').map(x => x.trim()).filter(x => x && x !== ten
      && !/^\\d+([.,]\\d+)?\\s*(K|N|M|Tr)?$/i.test(x) && !/^\\d+\\s*(giây|phút|giờ|ngày|tuần|s|m|h|d|w)$/i.test(x)
      && !/^(Thích|Like|Trả lời|Reply|Đăng lại|Repost|Chia sẻ|Share|Đã chỉnh sửa|Edited|Dịch|Translate)$/i.test(x));
  return {i, tac_gia: ten, link: p ? p.getAttribute('href') : '', thoi_gian: t ? (t.getAttribute('datetime') || '') : '',
          chu: dong.join(' ').slice(0, 2000)};
})"""


def doc_khoi(page) -> list:
    try:
        return page.evaluate(_JS_KHOI, KHOI) or []
    except Exception:
        return []


# --------------------------------------------------------------------------- th_tra_loi_binh_luan

def th_tra_loi_binh_luan(nc) -> str:
    sp = str(nc.ts.get("san_pham") or "")
    dem = w.Dem()
    hd = "tra_loi_binh_luan"
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    ten = _ten_chu_nick(nc)
    if not ten:
        raise LoiKyNang("không đọc được tên hồ sơ Threads của nick")
    _mo(nc, f"{GOC}/@{ten}")
    bai = []
    for k in doc_khoi(nc.page):
        h = k.get("link") or ""
        if f"/@{ten}/post/" in h and h not in bai:
            bai.append(h)
        if len(bai) >= 3:
            break
    nc.nhat_ky(f"@{ten}: xét {len(bai)} bài gần nhất")
    for h in bai:
        if nc.nen_dung() or not w.con_luot(nc, dem, hd):
            break
        link = _link_day_du(h)
        try:
            _mo(nc, link)
            khoi = doc_khoi(nc.page)
            if not khoi:
                continue
            goc = khoi[0]
            for bl in khoi[1:]:
                if nc.nen_dung() or not w.con_luot(nc, dem, hd):
                    break
                if not bl.get("chu") or bl.get("tac_gia") in ("", ten):
                    continue
                k = w.khoa(NT, "tra_loi", link, bl["tac_gia"], w.bam_chuoi(bl["chu"]))
                if nc.da_lam(k):
                    continue
                kq = w.lay_ai(nc, "tra_loi_binh_luan", {
                    "bai_cua_nick": True, "bai": {"chu": goc.get("chu"), "link": link},
                    "binh_luan": {"tac_gia": bl["tac_gia"], "chu": bl["chu"]}, "san_pham_id": sp})
                if kq.get("can_hoi_chu"):
                    nc.ghi_da_lam(k)
                    w.bao(nc, dem, hd, "bo_qua", f"Chuyển bạn trả lời: {bl['chu'][:80]}", link=link)
                    continue
                idx = bl["i"]

                def _dang(nd, idx=idx):
                    if not tra_loi_bai(nc, nc.page.locator(KHOI).nth(idx), nd):
                        raise LoiKyNang("đã gửi trả lời nhưng chưa thấy hiện")
                    return link
                w.noi_dung_ai(nc, dem, hd, loai="tra_loi", noi_dang=NT,
                              link_goc=w.gan_muc_tieu(link, bl["tac_gia"], bl["chu"]), bai_goc=goc.get("chu", ""),
                              ly_do=f"@{bl['tac_gia']} trả lời: {bl['chu'][:150]}",
                              noi_dung=kq.get("noi_dung") or "", khoa_lap=k, dang=_dang, san_pham_id=sp)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, hd, e, link)
    return w.ket_thuc(nc, dem, "Trả lời bình luận Threads")


# --------------------------------------------------------------------------- th_tuong_tac_bai_app

def _bai_doi(nc) -> list:
    out = []
    for b in nc.bai_doi_da_dang() or []:
        if isinstance(b, str):
            b = {"link": b}
        if "threads." in str(b.get("link") or ""):
            out.append(b)
    return out


def th_tuong_tac_bai_app(nc) -> str:
    so_bai = int(nc.ts.get("so_bai", 3) or 3)
    dem = w.Dem()
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    ds = _bai_doi(nc)
    nc.nhat_ky(f"Có {len(ds)} bài Threads của đội cần tương tác")
    if not ds:
        w.bao(nc, dem, "thich", "bo_qua", "Không có bài Threads nào của đội trong 2-48 giờ qua")
    lam = 0
    for b in ds:
        if nc.nen_dung() or lam >= so_bai:
            break
        link = str(b["link"])
        k = w.khoa(NT, "bai_doi", link)
        if nc.da_lam(k):
            continue
        lam += 1
        try:
            _mo(nc, link)
            khoi = _khoi_chinh(nc.page)
            if w.con_luot(nc, dem, "thich"):
                nut = _nut_svg(khoi, "Thích", "Like", "Bỏ thích", "Unlike")
                if nut:
                    w.bam_va_xac_nhan(nc, dem, "thich", nut, _da_thich, "thích bài của đội", link)
            if w.con_luot(nc, dem, "binh_luan"):
                chu = (doc_khoi(nc.page) or [{}])[0].get("chu", "")
                kq = w.lay_ai(nc, "viet_binh_luan", {"bai": {"chu": chu, "link": link}, "kieu": "tu_nhien",
                                                     "san_pham_id": str(b.get("san_pham") or "")})
                w.noi_dung_ai(nc, dem, "binh_luan", loai="binh_luan", noi_dang=NT, link_goc=link, bai_goc=chu,
                              ly_do="Tương tác bài đội vừa đăng", noi_dung=kq.get("noi_dung") or "",
                              khoa_lap=k, san_pham_id=str(b.get("san_pham") or ""),
                              dang=lambda nd: _tra_loi_hoac_loi(nc, link, nd))
            else:
                nc.ghi_da_lam(k)
        except Exception as e:
            w.bao_loi_ngoai_le(nc, dem, "binh_luan", e, link)
    return w.ket_thuc(nc, dem, "Tương tác bài đội trên Threads")


def _tra_loi_hoac_loi(nc, link: str, nd: str) -> str:
    if not tra_loi_bai(nc, _khoi_chinh(nc.page), nd):
        raise LoiKyNang("đã gửi trả lời nhưng chưa thấy hiện")
    return link


# --------------------------------------------------------------------------- th_quet_csv

COT_CSV = ["stt", "tac_gia", "noi_dung", "link", "thoi_gian"]


def th_quet_csv(nc) -> str:
    ts = nc.ts
    kieu = str(ts.get("kieu_quet") or "tim_kiem")
    vao = str(ts.get("dau_vao") or "").strip()
    toi_da = int(ts.get("so_dong", 50) or 50)
    dem = w.Dem()
    if not vao:
        raise LoiKyNang("thiếu từ khoá hoặc link để quét")
    if kieu == "tim_kiem":
        url = f"{GOC}/search?q={urllib.parse.quote(vao)}&serp_type=default"
    elif kieu == "ho_so":
        url = vao if vao.startswith("http") else f"{GOC}/@{vao.lstrip('@')}"
    else:
        url = vao
    nc.mo(url)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)
    if not w.con_luot(nc, dem, "quet"):
        return "Đã đủ giới hạn quét hôm nay"
    dong, da_co, dung_yen = [], set(), 0
    while len(dong) < toi_da and dung_yen < 4 and not nc.nen_dung():
        moi = 0
        ds = doc_khoi(nc.page)
        if kieu == "tra_loi":
            ds = ds[1:]          # khối đầu là bài gốc
        for k in ds:
            khoa_dong = k.get("link") or (k.get("tac_gia", "") + k.get("chu", "")[:80])
            if not k.get("chu") or khoa_dong in da_co:
                continue
            da_co.add(khoa_dong)
            dong.append({"stt": len(dong) + 1, "tac_gia": k.get("tac_gia", ""), "noi_dung": k.get("chu", ""),
                         "link": _link_day_du(k["link"]) if k.get("link") else "", "thoi_gian": k.get("thoi_gian", "")})
            moi += 1
            if len(dong) >= toi_da:
                break
        dung_yen = 0 if moi else dung_yen + 1
        nc.tay.luot(2)
        nc.tay.nghi(1.0, 2.5)
    ten_tep = f"threads_{kieu}_{time.strftime('%Y%m%d-%H%M%S')}.csv"
    p = w.ghi_csv(ten_tep, COT_CSV, dong)
    xem = "; ".join(f"@{d['tac_gia']}: {d['noi_dung'][:40]}" for d in dong[:3])
    ct = f"Quét {len(dong)} dòng ({kieu}: {vao[:60]}). Tệp CSV trên máy: {p}. {xem}"
    w.bao(nc, dem, "quet", "thanh_cong" if dong else "bo_qua", ct, link=url)
    return f"Quét Threads: {len(dong)} dòng, lưu {p}."


# --------------------------------------------------------------------------- dang_ban_nhap:threads

def _nhap_bai(nc, p: dict) -> str:
    nc.mo(GOC + "/")
    nc.kiem_dang_nhap()
    return dang_chuoi(nc, str(p.get("noi_dung") or ""), p.get("tep_cuc_bo") or [])


def _nhap_tra_loi(nc, p: dict) -> str:
    link, tg, chu = w.tach_muc_tieu(p.get("link_goc"))
    if not link:
        raise LoiKyNang("nháp không có link bài")
    nc.mo(link)
    nc.kiem_dang_nhap()
    nc.tay.nghi(2.0, 4.0)
    w.kiem_chan(nc)
    khoi = nc.page.locator(KHOI)
    dich = _khoi_chinh(nc.page)
    if tg:
        for k in doc_khoi(nc.page):
            if k.get("tac_gia") == tg and (not chu or chu[:20] in k.get("chu", "")):
                dich = khoi.nth(k["i"])
                break
        else:
            raise LoiKyNang(f"không tìm lại được trả lời của @{tg}")
    if not tra_loi_bai(nc, dich, str(p.get("noi_dung") or "")):
        raise LoiKyNang("đã gửi trả lời nhưng chưa thấy hiện")
    return link


def dang_ban_nhap(nc) -> str:
    return w.dang_ban_nhap_chung(nc, NT, {"bai_dang": lambda p: _nhap_bai(nc, p),
                                          "binh_luan": lambda p: _nhap_tra_loi(nc, p),
                                          "tra_loi": lambda p: _nhap_tra_loi(nc, p)})


KICH_BAN = {
    "th_dang_kho": th_dang_kho,
    "th_dang_ai": th_dang_ai,
    "th_tuong_tac": th_tuong_tac,
    "th_nuoi_nick": th_nuoi_nick,
    "th_tra_loi_binh_luan": th_tra_loi_binh_luan,
    "th_tuong_tac_bai_app": th_tuong_tac_bai_app,
    "th_quet_csv": th_quet_csv,
    "dang_ban_nhap:threads": dang_ban_nhap,
}
