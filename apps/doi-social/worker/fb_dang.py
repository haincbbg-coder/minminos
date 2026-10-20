"""Kỹ năng Facebook nhóm ĐĂNG BÀI: fb_dang_tuong_kho, fb_dang_nhom_link, fb_dang_nhom_ai, fb_dang_tuong_ai,
và việc nội bộ dang_ban_nhap:facebook.

Lõi đăng (`dang_noi_dung`) đi đúng các bước của ky_nang_fb.dang_bai (đã đăng thật thành công trên máy
chủ nhà): mở nơi đăng, chuyển danh nghĩa Trang nếu được mời, bấm ô soạn, gõ từng chữ, tải tệp, chờ
thanh tải lên, Tiếp, Đăng, chờ hộp đóng, tìm lại bài. Khác: nút Đăng đi qua chốt chặn chạy thử, và
trả trạng thái có cấu trúc để kho/nháp biết đã bấm Đăng hay chưa. `dang_bai` cũ giữ nguyên cho
`fb_dang_bai`.
"""
from __future__ import annotations

import re
import time
from typing import List, Optional

from fb_chung import (FB, bam_cong_khai, chuan_link, dau_tien_thay, ds_bai, la_link_bai, link_bai,
                      mo_va_kiem, ms, phai_dung, re_nhan, ten_trang, trang_thai_nhom)
from ngu_canh import LoiKyNang

_MO_O_SOAN = re.compile(r"(Bạn đang nghĩ gì|What's on your mind|Bạn viết gì đi|Viết gì đó|Write something|"
                        r"Tạo bài viết công khai|Tạo bài viết|Create post|Create a public post)", re.I)
_ANH_VIDEO = re_nhan("Ảnh/video", "Photo/video")
_TIEP = re_nhan("Tiếp", "Next")
_DANG = re_nhan("Đăng", "Post", "Đăng bài")
_CHUYEN = re_nhan("Chuyển ngay", "Chuyển", "Switch now", "Switch")
_XAC_NHAN_CHUYEN = re_nhan("Chuyển", "Switch", "Tiếp tục", "Continue")
_CHO_DUYET = re.compile(r"(chờ (quản trị viên|phê duyệt|duyệt)|đang chờ duyệt|pending (approval|review)|"
                        r"is pending|submitted for (admin )?approval|đã gửi .* quản trị viên)", re.I)


_QUAY_LAI = re_nhan("Quay lại", "Trở lại", "Back")
_BO_NHAP = re_nhan("Bỏ", "Bỏ bài viết", "Rời khỏi", "Rời khỏi trang", "Discard", "Leave", "Leave page")


def _bo_hop_soan(nc) -> None:
    """Chạy thử: xoá chữ vừa gõ, đóng hộp soạn và bỏ bản nháp (không đăng). Facebook hỏi 'Bỏ bài viết?' thì chọn Bỏ."""
    try:   # đang ở bước 2 (sau Tiếp) thì quay lại bước soạn
        if not nc.page.get_by_role("dialog").filter(has=nc.page.locator("[contenteditable='true']")).count():
            lui = dau_tien_thay([nc.page.get_by_role("dialog").get_by_role("button", name=_QUAY_LAI)], 2500)
            if lui:
                lui.click(timeout=5000)
                nc.tay.nghi(1.0, 2.0)
    except Exception:
        pass
    try:   # xoá chữ trước, kẻo Facebook giữ bản nháp trong ô 'Bạn đang nghĩ gì?'
        hop = nc.page.get_by_role("dialog").filter(has=nc.page.locator("[contenteditable='true']")).last
        o = hop.locator("[contenteditable='true']").first
        if o.count():
            o.click(timeout=5000)
            nc.tay.phim("Control+a")
            nc.tay.phim("Delete")
            nc.tay.nghi(0.5, 1.0)
    except Exception:
        pass
    for _ in range(3):
        try:
            nc.tay.phim("Escape")
        except Exception:
            pass
        nc.tay.nghi(0.8, 1.5)
        nut = dau_tien_thay([nc.page.get_by_role("dialog").get_by_role("button", name=_BO_NHAP)], 2500)
        if nut:
            try:
                nut.click(timeout=5000)
            except Exception:
                pass
            nc.tay.nghi(0.8, 1.5)
        if not nc.page.get_by_role("dialog").filter(has=nc.page.locator("[contenteditable='true']")).count():
            nc.nhat_ky("Chạy thử: đã đóng hộp soạn và bỏ bản nháp")
            return


class KetQuaDang(dict):
    """{trang_thai: da_dang|cho_duyet|da_bam|chay_thu, link, da_bam_dang}."""


def _loi(thong_diep: str, da_bam: bool, ma: Optional[str] = None) -> LoiKyNang:
    e = LoiKyNang(thong_diep, ma)
    e.da_bam_dang = da_bam
    return e


def dang_noi_dung(nc, noi_dang: str, noi_dung: str, tep: Optional[List[str]] = None,
                  hanh_dong: str = "dang_tuong") -> KetQuaDang:
    """Đăng một bài vào `noi_dang` (link nhóm/Trang, hoặc '' = tường nick). Raise LoiKyNang có thuộc
    tính `da_bam_dang` (False: lỗi trước khi bấm Đăng, kho trả bài về hàng chờ)."""
    page, tay = nc.page, nc.tay
    tep = list(tep or [])
    url = noi_dang or FB + "/me"
    mo_va_kiem(nc, url)
    if noi_dang:
        nut = dau_tien_thay([page.get_by_role("button", name=_CHUYEN)], 4000)
        if nut:
            nc.nhat_ky("Chuyển sang danh nghĩa Trang")
            tay.bam(nut)
            tay.nghi(1.5, 3.0)
            xn = dau_tien_thay([page.get_by_role("dialog").get_by_role("button", name=_XAC_NHAN_CHUYEN)], 4000)
            if xn:
                tay.bam(xn)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            tay.nghi(4.0, 7.0)
            mo_va_kiem(nc, url)
        if "/groups/" in url:
            tt = trang_thai_nhom(page)
            if tt in ("chua_vao", "cho_duyet"):
                raise _loi("nick chưa tham gia nhóm này" if tt == "chua_vao" else "nick đang chờ duyệt vào nhóm", False,
                           "chua_vao_nhom")
    tay.luot(1)
    page.mouse.wheel(0, -2000)
    tay.nghi(0.8, 1.6)

    nc.nhat_ky("Tìm ô soạn bài")
    o_mo = dau_tien_thay([page.get_by_role("button", name=_MO_O_SOAN), page.get_by_text(_MO_O_SOAN)], 20000)
    if not o_mo:
        raise _loi("không thấy ô 'Bạn đang nghĩ gì?' / 'Tạo bài viết' ở nơi đăng này (nick có quyền đăng ở đây không?)",
                   False)
    tay.bam(o_mo)
    tay.nghi(1.5, 3.0)
    hop = dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("[contenteditable='true']"))], 20000)
    if not hop:
        raise _loi("bấm ô soạn bài nhưng hộp 'Tạo bài viết' không hiện ra", False)
    o_chu = hop.locator("[contenteditable='true'][role='textbox'], [contenteditable='true']").first
    if nc.chay_thu:
        nc.nhat_ky("Chạy thử: đã mở hộp soạn bài, gõ nội dung để kiểm đường đi (không tải tệp, không bấm Đăng)")
    if noi_dung:
        nc.nhat_ky(f"Gõ nội dung ({len(noi_dung)} ký tự, từng chữ)")
        tay.bam(o_chu)
        tay.nghi(0.6, 1.4)
        try:     # Facebook giữ bản nháp cũ trong ô soạn: xoá sạch trước khi gõ để không đăng lẫn chữ cũ
            if (o_chu.inner_text(timeout=2000) or "").strip():
                nc.nhat_ky("Ô soạn còn bản nháp cũ, xoá trước khi gõ")
                tay.phim("Control+a")
                tay.phim("Delete")
                tay.nghi(0.4, 0.9)
        except Exception:
            pass
        tay.go(noi_dung)
        tay.nghi(1.0, 2.2)
    if tep and not nc.chay_thu:
        nc.nhat_ky(f"Tải {len(tep)} ảnh/video")
        nut_anh = dau_tien_thay([hop.get_by_role("button", name=_ANH_VIDEO),
                                 hop.locator("[aria-label='Ảnh/video'], [aria-label='Photo/video']")], 10000)
        o_tep = hop.locator("input[type='file']")
        if nut_anh and not o_tep.count():
            tay.bam(nut_anh)
            tay.nghi(1.0, 2.0)
        if not o_tep.count():
            raise _loi("không tìm thấy chỗ chọn ảnh/video trong hộp soạn bài", False)
        o_tep.first.set_input_files(tep)
        han = time.monotonic() + 15 * 60
        tay.nghi(3.0, 5.0)
        while time.monotonic() < han:
            if not hop.get_by_role("progressbar").count():
                break
            time.sleep(2)
        tay.nghi(1.5, 3.0)
    tay.nghi(1.5, 4.0)
    nut_tiep = dau_tien_thay([hop.get_by_role("button", name=_TIEP)], 2500)
    if nut_tiep:
        nc.nhat_ky("Bấm Tiếp")
        tay.bam(nut_tiep)
        tay.nghi(1.5, 3.0)
        hop = dau_tien_thay([page.get_by_role("dialog")], 10000) or hop
    nut_dang = dau_tien_thay([hop.get_by_role("button", name=_DANG),
                              hop.locator("[aria-label='Đăng'], [aria-label='Post']")], 15000)
    if not nut_dang:
        raise _loi("không thấy nút Đăng trong hộp soạn bài", False)
    if nut_dang.get_attribute("aria-disabled") == "true" and not nc.chay_thu:
        raise _loi("nút Đăng đang bị khoá (Facebook chưa nhận nội dung hoặc tệp chưa tải xong)", False)
    noi = "nhóm" if "/groups/" in url else ("Trang" if noi_dang else "tường")
    if not bam_cong_khai(nc, nut_dang, f"bấm Đăng bài lên {noi} ({len(noi_dung)} ký tự, {len(tep)} tệp)", hanh_dong):
        _bo_hop_soan(nc)
        return KetQuaDang(trang_thai="chay_thu", link="", da_bam_dang=False)
    nc.nhat_ky("Đã bấm Đăng")
    han = time.monotonic() + (15 * 60 if tep else 120)
    while time.monotonic() < han:
        try:
            if not hop.is_visible():
                break
        except Exception:
            break
        if page.get_by_text(_CHO_DUYET).count():
            break
        time.sleep(1.5)
    else:
        raise _loi("đã bấm Đăng nhưng hộp soạn bài không đóng (Facebook có thể đang báo lỗi)", True)
    tay.nghi(3.0, 6.0)
    try:
        nc.kiem_dang_nhap()
    except LoiKyNang as e:
        e.da_bam_dang = True
        raise
    if page.get_by_text(_CHO_DUYET).count():
        nc.nhat_ky("Nhóm duyệt bài: bài đang chờ quản trị viên")
        return KetQuaDang(trang_thai="cho_duyet", link="", da_bam_dang=True)
    dau = next((d.strip() for d in (noi_dung or "").splitlines() if d.strip()), "")[:40]
    if dau:
        try:
            page.get_by_text(dau, exact=False).first.wait_for(timeout=ms(20000))
            link = ""
            for loc in ds_bai(page)[:6]:
                try:
                    if dau in (loc.inner_text(timeout=2000) or ""):
                        link = link_bai(loc)
                        break
                except Exception:
                    continue
            nc.nhat_ky("Đã thấy bài trên trang")
            return KetQuaDang(trang_thai="da_dang", link=link, da_bam_dang=True)
        except Exception:
            pass
    nc.nhat_ky("Đã bấm Đăng, hộp soạn đóng, chưa thấy bài ngay (video đang xử lý hoặc chờ duyệt)")
    return KetQuaDang(trang_thai="da_bam", link="", da_bam_dang=True)


def _bao_ket_qua(nc, kq: KetQuaDang, hanh_dong: str, nhom: str = "", link_noi: str = "") -> bool:
    """Báo sự kiện theo kết quả đăng. Trả True nếu tính là thành công."""
    tt = kq.get("trang_thai")
    if tt == "chay_thu":
        return False
    if tt == "da_dang":
        nc.su_kien(hanh_dong, "thanh_cong", "Đã đăng và thấy bài trên trang", link=kq.get("link") or link_noi, nhom=nhom)
        return True
    if tt == "cho_duyet":
        nc.su_kien(hanh_dong, "thanh_cong", "Nhóm yêu cầu duyệt bài: bài đang chờ quản trị viên", link=link_noi, nhom=nhom)
        return True
    nc.su_kien(hanh_dong, "thanh_cong", "Đã bấm Đăng, hộp soạn bài đã đóng (chưa thấy bài ngay)", link=link_noi, nhom=nhom)
    return True


# ---------------------------------------------------------------------------- mẫu
def fb_dang_tuong_kho(nc) -> str:
    so = int(nc.ts.get("so_bai") or 1)
    xong = 0
    for i in range(so):
        if phai_dung(nc) or nc.con_lai("dang_tuong") <= 0:
            break
        bai = nc.lay_kho()
        if not bai:
            nc.su_kien("dang_tuong", "bo_qua", "Hết bài trong kho", ma="het_bai")
            break
        noi_dung = str(bai.get("noi_dung") or "")
        try:
            kq = dang_noi_dung(nc, "", noi_dung, bai.get("tep_cuc_bo"), "dang_tuong")
        except LoiKyNang as e:
            da_bam = bool(getattr(e, "da_bam_dang", False))
            nc.xong_kho(bai["id"], False, da_bam, loi=str(e))
            raise
        if kq["trang_thai"] == "chay_thu":
            nc.xong_kho(bai["id"], False, False, loi="chạy thử: không đăng, trả bài về hàng chờ")
            break
        nc.xong_kho(bai["id"], True, True, link=kq.get("link") or "")
        if _bao_ket_qua(nc, kq, "dang_tuong"):
            xong += 1
        if i + 1 < so:
            nc.nghi_thao_tac()
    return f"Đăng tường từ kho: {xong} bài." if not nc.chay_thu else "Chạy thử: đã soạn bài từ kho, không bấm Đăng."


def fb_dang_nhom_link(nc) -> str:
    links = [chuan_link(l) for l in (nc.ts.get("links") or [])][: int(nc.ts.get("so_nhom") or 3)]
    bai = None
    if (nc.ts.get("nguon") or "nhap") == "kho":
        bai = nc.lay_kho()
        if not bai:
            nc.su_kien("dang_nhom", "bo_qua", "Hết bài trong kho", ma="het_bai")
            return "Hết bài trong kho."
        noi_dung, tep = str(bai.get("noi_dung") or ""), bai.get("tep_cuc_bo") or []
    else:
        noi_dung, tep = str(nc.ts.get("noi_dung") or ""), list(nc.tep_cuc_bo)
    if not noi_dung.strip() and not tep:
        raise LoiKyNang("chưa có nội dung bài để đăng")
    xong, da_bam_bat_ky, link_dau = 0, False, ""
    try:
        for i, link in enumerate(links):
            if phai_dung(nc) or nc.con_lai("dang_nhom") <= 0:
                break
            try:
                kq = dang_noi_dung(nc, link, noi_dung, tep, "dang_nhom")
            except LoiKyNang as e:
                if e.ma == "chua_vao_nhom":
                    nc.su_kien("dang_nhom", "bo_qua", f"Chưa tham gia nhóm: {e}", nhom=link)
                    continue
                if e.ma:
                    raise
                da_bam_bat_ky = da_bam_bat_ky or bool(getattr(e, "da_bam_dang", False))
                nc.su_kien("dang_nhom", "loi", str(e), nhom=link)
                continue
            if kq["trang_thai"] == "chay_thu":
                continue
            da_bam_bat_ky = True
            if _bao_ket_qua(nc, kq, "dang_nhom", nhom=ten_trang(nc.page) or link, link_noi=link):
                xong += 1
                link_dau = link_dau or kq.get("link") or ""
            if i + 1 < len(links):
                nc.nghi_thao_tac()
    finally:
        if bai:
            if xong:
                nc.xong_kho(bai["id"], True, True, link=link_dau)
            else:
                nc.xong_kho(bai["id"], False, da_bam_bat_ky, loi="không đăng được vào nhóm nào")
    return f"Đăng vào {xong}/{len(links)} nhóm."


def _da_vao(nhom: dict, nick_id: str) -> bool:
    tt = nhom.get("tinh_trang_vao")
    if isinstance(tt, dict):
        tt = tt.get(str(nick_id))
    return str(tt or nhom.get("tinh_trang") or "") == "da_vao"


def _so_tuan() -> str:
    import datetime
    nam, tuan, _ = datetime.date.today().isocalendar()
    return f"{nam}-W{tuan:02d}"


def fb_dang_nhom_ai(nc) -> str:
    so = int(nc.ts.get("so_bai") or 1)
    moi_nhom = int(nc.ts.get("moi_nhom_7_ngay") or 1)
    nhom = [n for n in nc.nhom_fb() if _da_vao(n, nc.viec.get("nick_id")) and n.get("trang_thai", "da_duyet") != "den"]
    if not nhom:
        nc.su_kien("dang_nhom", "bo_qua", "Nick chưa tham gia nhóm nào của sản phẩm trong Kho group FB")
        return "Không có nhóm đã tham gia."
    xong = 0
    for _ in range(so):
        if phai_dung(nc) or nc.con_lai("dang_nhom") <= 0:
            break
        bn = nc.lay_ban_nhap("fb_nhom")
        if not bn:
            nc.su_kien("dang_nhom", "bo_qua", "Không còn bài AI đã duyệt cho nhóm", ma="het_bai")
            break
        dich = None
        if bn.get("nhom"):
            dich = next((n for n in nhom if bn["nhom"] in (n.get("link"), n.get("ten"))), None) or {"link": bn["nhom"]}
        else:
            for n in nc.rng.sample(nhom, len(nhom)):
                khoa = [f"fb_dang_nhom:{chuan_link(n.get('link', ''))}:{_so_tuan()}:{k}" for k in range(moi_nhom)]
                trong = next((k for k in khoa if not nc.da_lam(k)), None)
                if trong:
                    dich = dict(n, _khoa=trong)
                    break
        if not dich:
            nc.su_kien("dang_nhom", "bo_qua", f"Mọi nhóm đã đủ {moi_nhom} bài trong tuần")
            break
        try:
            kq = dang_noi_dung(nc, chuan_link(dich["link"]), str(bn.get("noi_dung") or ""), bn.get("tep_cuc_bo") or [],
                               "dang_nhom")
        except LoiKyNang as e:
            if e.ma and e.ma != "chua_vao_nhom":
                nc.xong_ban_nhap(bn["id"], False, loi=str(e))
                raise
            nc.xong_ban_nhap(bn["id"], False, loi=str(e))
            nc.su_kien("dang_nhom", "loi", str(e), nhom=dich.get("ten") or dich["link"])
            continue
        if kq["trang_thai"] == "chay_thu":
            break
        nc.xong_ban_nhap(bn["id"], True, link=kq.get("link") or "")
        if dich.get("_khoa"):
            nc.ghi_da_lam(dich["_khoa"])
        if _bao_ket_qua(nc, kq, "dang_nhom", nhom=dich.get("ten") or dich["link"], link_noi=dich["link"]):
            xong += 1
        nc.nghi_thao_tac()
    return f"Đăng {xong} bài AI vào nhóm."


def fb_dang_tuong_ai(nc) -> str:
    so = int(nc.ts.get("so_bai") or 1)
    xong = 0
    for _ in range(so):
        if phai_dung(nc) or nc.con_lai("dang_tuong") <= 0:
            break
        bn = nc.lay_ban_nhap("fb_tuong")
        if not bn:
            nc.su_kien("dang_tuong", "bo_qua", "Không còn bài AI đã duyệt cho tường", ma="het_bai")
            break
        try:
            kq = dang_noi_dung(nc, "", str(bn.get("noi_dung") or ""), bn.get("tep_cuc_bo") or [], "dang_tuong")
        except LoiKyNang as e:
            nc.xong_ban_nhap(bn["id"], False, loi=str(e))
            raise
        if kq["trang_thai"] == "chay_thu":
            break
        nc.xong_ban_nhap(bn["id"], True, link=kq.get("link") or "")
        if _bao_ket_qua(nc, kq, "dang_tuong"):
            xong += 1
        nc.nghi_thao_tac()
    return f"Đăng {xong} bài AI lên tường."


# ---------------------------------------------------------------------------- dang_ban_nhap:facebook
def dang_ban_nhap_fb(nc) -> str:
    """Đăng một nháp đã duyệt: bình luận/trả lời dưới link_goc, hoặc bài vào nhóm/tường/Trang."""
    from fb_chung import binh_luan, ds_binh_luan, pham_vi_bai, tra_loi_binh_luan
    ts = nc.ts
    bid = int(ts.get("ban_nhap_id") or 0)
    loai = str(ts.get("loai") or "")
    noi_dang = str(ts.get("noi_dang") or "")
    noi_dung = str(ts.get("noi_dung") or "")
    nhom = str(ts.get("nhom") or "")
    link_goc = str(ts.get("link_goc") or "")
    if not noi_dung.strip():
        raise LoiKyNang("nháp không có nội dung")
    da_bao = []

    def bao_nhap(ok_: bool, link: str = "", loi: str = "") -> None:
        if bid and not da_bao:          # lõi không gọi lại; ở đây cũng chỉ gọi đúng một lần
            da_bao.append(1)
            nc.xong_ban_nhap(bid, ok_, link=link, loi=loi)

    try:
        if loai in ("binh_luan", "tra_loi"):
            if not link_goc:
                raise LoiKyNang("nháp bình luận thiếu link bài gốc")
            hd = "tra_loi_binh_luan" if loai == "tra_loi" else ("binh_luan_nhom" if noi_dang == "fb_nhom" else "binh_luan")
            mo_va_kiem(nc, link_goc)
            pv = pham_vi_bai(nc.page)
            kq = "khong_thay"
            if loai == "tra_loi" and "comment_id=" in link_goc:
                bl = ds_binh_luan(nc.page)
                if bl:
                    kq = tra_loi_binh_luan(nc, bl[0], noi_dung, hd)
            if kq == "khong_thay":
                kq = binh_luan(nc, pv, noi_dung, hd)
            if kq == "chay_thu":
                return "Chạy thử: không gửi bình luận của nháp."
            if kq != "thanh_cong":
                nc.su_kien(hd, "loi", "Đã gửi nhưng chưa thấy bình luận hiện" if kq == "khong_hien"
                           else "Không thấy ô bình luận dưới bài", link=link_goc, nhom=nhom)
                bao_nhap(False, loi="không thấy bình luận sau khi gửi")
                return "Không đăng được bình luận của nháp."
            nc.su_kien(hd, "thanh_cong", f"Đăng nháp #{bid}: {noi_dung[:80]}", link=link_goc, nhom=nhom)
            bao_nhap(True, link=link_goc)
            return "Đã đăng bình luận của nháp."
        hd = {"fb_nhom": "dang_nhom", "fb_trang": "dang_trang"}.get(noi_dang, "dang_tuong")
        dich = nhom if noi_dang in ("fb_nhom", "fb_trang") else ""
        if noi_dang in ("fb_nhom", "fb_trang") and not dich.startswith("http"):
            dich = link_goc if link_goc.startswith("http") else ""
            if not dich:
                raise LoiKyNang("nháp bài nhóm/Trang thiếu link nơi đăng")
        kq = dang_noi_dung(nc, chuan_link(dich) if dich else "", noi_dung,
                           list(ts.get("tep_cuc_bo") or nc.tep_cuc_bo), hd)
        if kq["trang_thai"] == "chay_thu":
            return "Chạy thử: đã soạn bài của nháp, không bấm Đăng."
        _bao_ket_qua(nc, kq, hd, nhom=nhom, link_noi=dich)
        bao_nhap(True, link=kq.get("link") or "")
        return "Đã đăng bài của nháp" + (" (chờ quản trị viên duyệt)." if kq["trang_thai"] == "cho_duyet" else ".")
    except LoiKyNang as e:
        try:
            bao_nhap(False, loi=str(e))
        except Exception:
            pass
        raise


__all__ = ["dang_noi_dung", "fb_dang_tuong_kho", "fb_dang_nhom_link", "fb_dang_nhom_ai", "fb_dang_tuong_ai",
           "dang_ban_nhap_fb", "la_link_bai"]
