"""Kỹ năng Facebook về NHÓM: fb_binh_luan_nhom_sp, fb_binh_luan_nhom_link, fb_tham_gia_nhom_sp."""
from __future__ import annotations

import re
import urllib.parse

from fb_chung import (FB, bam_cong_khai, binh_luan, chuan_link, dau_tien_thay, ds_binh_luan, doc_bai_nhom,
                      link_nhom_moi, mo_va_kiem, phai_dung, re_nhan, ten_trang, thay_chu, tim_nut,
                      tra_loi_binh_luan, trang_thai_nhom)
from ngu_canh import LoiKyNang

_THAM_GIA = ["Tham gia nhóm", "Join group", "Tham gia", "Join"]
_GUI = ["Gửi", "Submit", "Gửi câu trả lời", "Submit answers"]
_DONG = ["Đóng", "Close", "Hủy", "Huỷ", "Cancel"]
_DONG_Y = re.compile(r"(Tôi đồng ý|I agree|đồng ý với quy tắc|agree to the group rules)", re.I)
_DOI_LIEN_HE = re.compile(r"(số điện thoại|sđt|phone number|e-?mail|địa chỉ email|zalo)", re.I)


def _vai(nhom: dict, nick_id) -> str:
    v = nhom.get("vai")
    if isinstance(v, dict):
        v = v.get(str(nick_id))
    if v:
        return str(v)
    if str(nhom.get("nick_chinh") or "") == str(nick_id):
        return "chinh"
    tt = nhom.get("nick_tuong_tac") or []
    return "tuong_tac" if str(nick_id) in [str(x) for x in tt] else "chua_gan"


def _tinh_trang(nhom: dict, nick_id) -> str:
    tt = nhom.get("tinh_trang_vao")
    if isinstance(tt, dict):
        tt = tt.get(str(nick_id))
    return str(tt or "")


# ---------------------------------------------------------------------------- vào nhóm
def vao_nhom(nc, link: str, san_pham: str = "") -> str:
    """Mở nhóm, bấm Tham gia, trả lời câu hỏi duyệt (AI). Trả 'da_vao' | 'cho_duyet' | 'bo_nhom' |
    'chay_thu' | 'khong_thay' | 'khong_doi'. Đã báo sự kiện vao_nhom khi có bấm."""
    page = nc.page
    mo_va_kiem(nc, link)
    tt = trang_thai_nhom(page)
    ten = ten_trang(page) or link
    if tt in ("da_vao", "cho_duyet"):
        return tt
    nut = tim_nut(page, _THAM_GIA, 6000)
    if not nut:
        return "khong_thay"
    if not bam_cong_khai(nc, nut, f"bấm Tham gia nhóm '{ten}'", "vao_nhom"):
        return "chay_thu"
    nc.tay.nghi(2.0, 4.0)
    hop = dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("textarea, [contenteditable='true'], "
                                                                             "input[type='checkbox'], [role='checkbox'], "
                                                                             "[role='radio']"))], 5000)
    if hop:
        try:
            chu_hop = hop.inner_text(timeout=5000)
        except Exception:
            chu_hop = ""
        cau_hoi = [d.strip() for d in chu_hop.splitlines() if d.strip().endswith("?")][:10]
        o_tra_loi = hop.locator("textarea, [contenteditable='true'][role='textbox'], input[type='text']")
        n_o = o_tra_loi.count()
        if not cau_hoi and n_o:
            cau_hoi = [d.strip() for d in chu_hop.splitlines() if len(d.strip()) > 12][:n_o]
        nc.nhat_ky(f"Nhóm có {len(cau_hoi)} câu hỏi duyệt thành viên")
        kq = nc.ai("tra_loi_cau_hoi_nhom", {"nhom": ten, "cau_hoi": cau_hoi, "san_pham_id": san_pham}) if cau_hoi else {}
        if kq.get("bo_nhom") or (cau_hoi and any(_DOI_LIEN_HE.search(c) for c in cau_hoi) and not kq.get("tra_loi")):
            nc.nhat_ky("Câu hỏi đòi thông tin liên hệ: bỏ nhóm, đóng hộp")
            dong = tim_nut(hop, _DONG, 3000, vai=("button",)) or tim_nut(hop, ["Đóng", "Close"], 1500, chinh_xac=False)
            if dong:
                nc.tay.bam(dong)
            else:
                nc.tay.phim("Escape")
            nc.su_kien("vao_nhom", "bo_qua", "Câu hỏi duyệt đòi số điện thoại/email: bỏ nhóm", nhom=ten)
            return "bo_nhom"
        tra_loi = [str(x) for x in (kq.get("tra_loi") or [])]
        for i in range(min(n_o, len(tra_loi))):
            o = o_tra_loi.nth(i)
            try:
                nc.tay.bam(o)
                nc.tay.nghi(0.4, 1.0)
                nc.tay.go(tra_loi[i][:500])
                nc.tay.nghi(0.8, 2.0)
            except Exception as e:      # noqa: BLE001
                nc.nhat_ky(f"Không gõ được câu trả lời {i + 1}: {e}")
        for cb in (hop.get_by_role("checkbox", name=_DONG_Y), hop.locator("input[type='checkbox']")):
            try:
                if cb.count() and cb.first.get_attribute("aria-checked") != "true" and not cb.first.is_checked():
                    nc.tay.bam(cb.first)
                    nc.tay.nghi(0.4, 1.0)
                    break
            except Exception:
                continue
        gui = tim_nut(hop, _GUI, 5000)
        if gui:
            nc.tay.bam(gui)          # đã qua chốt chặn ở nút Tham gia; TayChayThu vẫn canh lớp thứ hai
            nc.tay.nghi(2.0, 4.0)
    page_tt = "khong_doi"
    for _ in range(3):
        tt = trang_thai_nhom(page)
        if tt in ("da_vao", "cho_duyet"):
            page_tt = tt
            break
        nc.tay.nghi(1.5, 3.0)
    if page_tt == "khong_doi":
        nc.su_kien("vao_nhom", "loi", "Đã bấm Tham gia nhưng nút không đổi trạng thái", nhom=ten)
    else:
        nc.su_kien("vao_nhom", "thanh_cong",
                   "Đã vào nhóm" if page_tt == "da_vao" else "Đã gửi yêu cầu, chờ quản trị viên duyệt", nhom=ten)
    return page_tt


# ---------------------------------------------------------------------------- bình luận nhóm
def _binh_luan_mot_nhom(nc, link: str, ten: str, so_quet: int, con_toi_da: int) -> int:
    """Quét bài mới của một nhóm, AI chấm, bình luận/tạo nháp. Trả số bình luận (hoặc nháp) đã làm."""
    sp = str(nc.ts.get("san_pham") or "")
    mo_va_kiem(nc, link_nhom_moi(link))
    ten = ten_trang(nc.page) or ten or link
    ds = doc_bai_nhom(nc, so_quet)
    nc.nhat_ky(f"Đọc được {len(ds)} bài mới trong nhóm, AI chấm từng bài")
    hop, lam = 0, 0
    for i, muc in enumerate(ds, 1):
        if lam >= con_toi_da or phai_dung(nc) or nc.con_lai("binh_luan_nhom") <= 0:
            break
        bai = muc["bai"]
        lb = bai.get("link") or ""
        khoa = f"fb_bl:{lb or bai['chu'][:80]}"
        if nc.da_lam(khoa, ca_doi=True):
            nc.su_kien("binh_luan_nhom", "bo_qua", "Bỏ qua: bài đã có bình luận của nick khác trong đội", link=lb, nhom=ten)
            continue
        cham = nc.ai("cham_bai", {"bai": bai, "san_pham_id": sp}, [muc["anh"]] if muc.get("anh") else [])
        nc.nhat_ky(f"Bài {i}/{len(ds)}: điểm {cham.get('diem', '?')}"
                   + (" (đối thủ)" if cham.get("la_doi_thu") else "") + (" -> chọn" if cham.get("chon") else ""))
        if cham.get("la_doi_thu") or not cham.get("chon"):
            continue
        hop += 1
        viet = nc.ai("viet_binh_luan", {"bai": bai, "san_pham_id": sp, "kieu": "tu_van"})
        noi_dung = str(viet.get("noi_dung") or "").strip()
        con = str(viet.get("tra_loi_con") or "").strip()
        if not noi_dung:
            continue
        if nc.che_do in ("chay_thu", "duyet_truoc"):
            nc.ban_nhap(loai="binh_luan", noi_dang="fb_nhom", nhom=ten, link_goc=lb, bai_goc=bai["chu"][:1000],
                        ly_do=str(cham.get("ly_do") or ""), noi_dung=noi_dung + (f"\n\n[Trả lời con] {con}" if con else ""),
                        san_pham_id=sp)
            nc.su_kien("binh_luan_nhom", "thong_tin",
                       ("Chạy thử: " if nc.chay_thu else "") + f"tạo nháp chờ duyệt (điểm {cham.get('diem', '?')}): "
                       f"{noi_dung[:100]}", link=lb, nhom=ten, san_pham=sp)
            if nc.che_do == "duyet_truoc":
                nc.ghi_da_lam(khoa)          # giữ chỗ để nick khác trong đội không viết trùng
            lam += 1
            continue
        kq = binh_luan(nc, muc["loc"], noi_dung, "binh_luan_nhom")
        if kq != "thanh_cong":
            nc.su_kien("binh_luan_nhom", "loi", "Không thấy ô bình luận" if kq == "khong_thay"
                       else "Đã gửi nhưng chưa thấy bình luận hiện ra", link=lb, nhom=ten)
            continue
        nc.ghi_da_lam(khoa)
        nc.su_kien("binh_luan_nhom", "thanh_cong", f"Bình luận: {noi_dung[:120]}", link=lb, nhom=ten, san_pham=sp)
        lam += 1
        if con:
            nc.tay.nghi(4.0, 9.0)
            cua_minh = [b for b in ds_binh_luan(muc["loc"]) if thay_chu(b, noi_dung, 1500)]
            if cua_minh:
                kq2 = tra_loi_binh_luan(nc, cua_minh[-1], con, "binh_luan_nhom", "trả lời con chứa link")
                nc.nhat_ky("Đã thêm trả lời con chứa link" if kq2 == "thanh_cong" else "Chưa thêm được trả lời con")
        nc.nghi_thao_tac()
    nc.su_kien("binh_luan_nhom", "thong_tin", f"Quét {len(ds)} bài mới, {hop} bài đúng nhu cầu", nhom=ten, san_pham=sp)
    try:
        nc.bao_nhom(link, ten=ten, lan_quet=True)
    except LoiKyNang:
        pass
    return lam


def _chay_binh_luan_nhom(nc, nhom: list, tu_tham_gia: bool) -> str:
    toi_da = int(nc.ts.get("toi_da") or 3)
    so_quet = int(nc.ts.get("so_bai_quet") or 15)
    tong = 0
    for n in nhom:
        if tong >= toi_da or phai_dung(nc) or nc.con_lai("binh_luan_nhom") <= 0:
            break
        link = chuan_link(n.get("link") or "")
        if not link:
            continue
        try:
            if tu_tham_gia is not None:
                mo_va_kiem(nc, link)
                tt = trang_thai_nhom(nc.page)
                if tt == "khong_ro":
                    nc.nhat_ky("Không đọc được trạng thái thành viên của nhóm, vẫn thử quét bài")
                elif tt != "da_vao":
                    if tt == "cho_duyet":
                        nc.bao_nhom(link, tinh_trang="cho_duyet")
                        nc.su_kien("binh_luan_nhom", "bo_qua", "Nick đang chờ duyệt vào nhóm", nhom=link)
                        continue
                    if not tu_tham_gia or nc.con_lai("vao_nhom") <= 0:
                        nc.su_kien("binh_luan_nhom", "bo_qua", "Nick chưa tham gia nhóm", nhom=link)
                        continue
                    kq = vao_nhom(nc, link, str(nc.ts.get("san_pham") or ""))
                    if kq in ("da_vao", "cho_duyet"):
                        nc.bao_nhom(link, ten=ten_trang(nc.page), tinh_trang=kq, them_moi=True)
                    if kq == "chay_thu":
                        # Chạy thử: chưa vào nhóm nhưng nhóm công khai vẫn đọc được bài, nên vẫn quét và
                        # viết nháp để chủ xem AI sẽ làm gì (nhóm kín thì quét ra 0 bài).
                        nc.nhat_ky("Chạy thử: nick chưa vào nhóm, vẫn đọc bài công khai để viết nháp")
                        mo_va_kiem(nc, link)
                    elif kq != "da_vao":
                        continue
                    nc.nghi_thao_tac()
            tong += _binh_luan_mot_nhom(nc, link, str(n.get("ten") or ""), so_quet, toi_da - tong)
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien("binh_luan_nhom", "loi", str(e), nhom=link)
        nc.nghi_thao_tac()
    if nc.che_do != "dang_luon":
        return f"Đã tạo {tong} nháp bình luận chờ duyệt" + (" (chạy thử)." if nc.chay_thu else ".")
    return f"Đã bình luận {tong} bài trong {len(nhom)} nhóm."


def fb_binh_luan_nhom_sp(nc) -> str:
    nid = nc.viec.get("nick_id")
    nhom = [n for n in nc.nhom_fb() if _vai(n, nid) == "chinh" and n.get("trang_thai", "da_duyet") != "den"]
    if not nhom:
        nc.su_kien("binh_luan_nhom", "bo_qua", "Nick không phụ trách nhóm nào của sản phẩm trong Kho group FB")
        return "Nick không phụ trách nhóm nào."
    return _chay_binh_luan_nhom(nc, nhom, None)


def fb_binh_luan_nhom_link(nc) -> str:
    nhom = [{"link": l} for l in (nc.ts.get("links") or []) if l]
    return _chay_binh_luan_nhom(nc, nhom, bool(nc.ts.get("tu_tham_gia", True)))


# ---------------------------------------------------------------------------- tham gia nhóm
def _tim_nhom(nc, tu_khoa: str, toi_da: int = 12) -> list:
    mo_va_kiem(nc, FB + "/search/groups/?q=" + urllib.parse.quote(tu_khoa))
    nc.tay.luot_doc(nc.rng.uniform(4, 8))
    page = nc.page
    ra, thay = [], set()
    for a in page.locator("a[href*='/groups/']").all()[:80]:
        try:
            href = a.get_attribute("href") or ""
        except Exception:
            continue
        m = re.search(r"/groups/([^/?#]+)", href)
        if not m or m.group(1) in ("feed", "discover", "joins", "search", "create"):
            continue
        link = f"{FB}/groups/{m.group(1)}"
        if link in thay:
            continue
        thay.add(link)
        try:
            khung = a.locator("xpath=ancestor::div[@role='article' or @role='listitem' or @role='row'][1]")
            chu = (khung.first.inner_text(timeout=1500) if khung.count() else a.inner_text(timeout=1500)) or ""
        except Exception:
            chu = ""
        dong = [d.strip() for d in chu.splitlines() if d.strip()]
        tv = next((d for d in dong if re.search(r"(thành viên|members)", d, re.I)), "")
        ra.append({"ten": dong[0] if dong else link, "link": link, "thanh_vien": tv,
                   "mo_ta": " · ".join(dong[1:4])[:300]})
        if len(ra) >= toi_da:
            break
    return ra


def fb_tham_gia_nhom_sp(nc) -> str:
    nid = nc.viec.get("nick_id")
    sp = str(nc.ts.get("san_pham") or "")
    so = int(nc.ts.get("so_nhom") or 2)
    ds = nc.nhom_fb()
    ung_vien = [n for n in ds if _tinh_trang(n, nid) not in ("da_vao", "cho_duyet", "bi_tu_choi")
                and n.get("trang_thai", "da_duyet") == "da_duyet" and _vai(n, nid) in ("chinh", "tuong_tac", "chua_gan")]
    ung_vien.sort(key=lambda n: {"chinh": 0, "tuong_tac": 1}.get(_vai(n, nid), 2))
    if len(ung_vien) < so and nc.ts.get("tu_tim", True):
        meta = nc.nhom_fb_tho if isinstance(nc.nhom_fb_tho, dict) else {}
        spm = meta.get("san_pham") if isinstance(meta.get("san_pham"), dict) else {}
        tu_khoa = [t.strip() for t in re.split(r"[,\n;]", str(nc.ts.get("tu_khoa") or meta.get("tu_khoa")
                                                                or spm.get("tu_khoa") or spm.get("ten") or ""))
                   if t.strip()]
        if not tu_khoa:
            nc.nhat_ky("Không có từ khoá sản phẩm để tự tìm nhóm (MinMin chưa gửi tu_khoa)")
        da_co = {chuan_link(n.get("link") or "") for n in ds}
        for kw in tu_khoa[:3]:
            if len(ung_vien) >= so or phai_dung(nc):
                break
            kq_tim = [r for r in _tim_nhom(nc, kw) if r["link"] not in da_co]
            if not kq_tim:
                continue
            chon = nc.ai("chon_nhom", {"ket_qua_tim": kq_tim, "san_pham_id": sp}).get("chon") or []
            for l in chon:
                l = chuan_link(str(l))
                if l and l not in da_co:
                    da_co.add(l)
                    ung_vien.append({"link": l, "ten": next((r["ten"] for r in kq_tim if r["link"] == l), ""), "_moi": True})
            nc.nghi_thao_tac()
    vao = 0
    for n in ung_vien[:max(so, 0) * 2]:
        if vao >= so or phai_dung(nc) or nc.con_lai("vao_nhom") <= 0:
            break
        link = chuan_link(n.get("link") or "")
        try:
            kq = vao_nhom(nc, link, sp)
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien("vao_nhom", "loi", str(e), nhom=link)
            continue
        ten = n.get("ten") or ten_trang(nc.page)
        if kq in ("da_vao", "cho_duyet"):
            nc.bao_nhom(link, ten=ten, tinh_trang=kq, them_moi=bool(n.get("_moi")))
            vao += 1
        elif kq == "bo_nhom":
            nc.bao_nhom(link, ten=ten, tinh_trang="bi_tu_choi", them_moi=bool(n.get("_moi")),
                        ghi_chu="câu hỏi duyệt đòi số điện thoại/email")
        elif kq == "chay_thu" and n.get("_moi"):
            nc.su_kien("vao_nhom", "thong_tin", f"Chạy thử: AI chọn nhóm {ten or link}", nhom=link)
            try:    # ghi vào Kho group FB ở trạng thái chờ duyệt để chủ xem (không phải thao tác công khai)
                nc.bao_nhom(link, ten=ten, them_moi=True)
            except Exception as e:
                nc.nhat_ky(f"Chưa ghi được nhóm vào kho: {e}")
        nc.nghi_thao_tac()
    if nc.chay_thu:
        return f"Chạy thử: xem {min(len(ung_vien), so * 2)} nhóm, không bấm Tham gia."
    return f"Đã xin vào {vao} nhóm."


__all__ = ["vao_nhom", "fb_binh_luan_nhom_sp", "fb_binh_luan_nhom_link", "fb_tham_gia_nhom_sp", "re_nhan"]
