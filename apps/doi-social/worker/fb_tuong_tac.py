"""Kỹ năng Facebook nhóm TƯƠNG TÁC: fb_tuong_tac_link, fb_nuoi_nick, fb_tuong_tac_bai_app."""
from __future__ import annotations

import time

from fb_chung import (FB, binh_luan, chia_se, chuan_link, da_tha_cam_xuc, doc_bai, ds_bai, mo_rong_bai,
                      mo_va_kiem, pham_vi_bai, phai_dung, tha_cam_xuc, tim_nut)
from ngu_canh import LoiKyNang
from nguoi import chon_cau

_TEN_CX = {"thich": "Thích", "yeu_thich": "Yêu thích", "thuong_thuong": "Thương thương", "haha": "Haha",
           "wow": "Wow", "ngau_nhien": "cảm xúc ngẫu nhiên"}


def _bao_cam_xuc(nc, kq: str, link: str, nhom: str = "") -> bool:
    if kq == "thanh_cong":
        nc.su_kien("thich", "thanh_cong", "Đã thả cảm xúc (đọc lại thấy nút đã đổi)", link=link, nhom=nhom)
        return True
    if kq == "da_co":
        nc.su_kien("thich", "bo_qua", "Bài đã được nick thả cảm xúc từ trước", link=link, nhom=nhom)
    elif kq == "khong_thay":
        nc.su_kien("thich", "loi", "Không thấy nút Thích trên bài", link=link, nhom=nhom)
    elif kq == "khong_doi":
        nc.su_kien("thich", "loi", "Đã bấm nhưng nút Thích không đổi trạng thái", link=link, nhom=nhom)
    return False


def _bao_binh_luan(nc, kq: str, hd: str, noi_dung: str, link: str, nhom: str = "") -> bool:
    if kq == "thanh_cong":
        nc.su_kien(hd, "thanh_cong", f"Bình luận: {noi_dung[:120]}", link=link, nhom=nhom)
        return True
    if kq == "khong_thay":
        nc.su_kien(hd, "loi", "Không thấy ô bình luận (bài khoá bình luận?)", link=link, nhom=nhom)
    elif kq == "khong_hien":
        nc.su_kien(hd, "loi", "Đã gửi nhưng chưa thấy bình luận hiện ra", link=link, nhom=nhom)
    return False


def fb_tuong_tac_link(nc) -> str:
    ts = nc.ts
    links = [chuan_link(l) for l in (ts.get("links") or []) if l]
    cam_xuc = str(ts.get("cam_xuc") or "thich")
    co_bl = bool(ts.get("binh_luan"))
    co_cs = bool(ts.get("chia_se"))
    da_dung: list = []
    ok = 0
    for i, link in enumerate(links):
        if phai_dung(nc):
            break
        khoa = f"fb_tt:{link}"
        if nc.da_lam(khoa):
            nc.su_kien("thich" if cam_xuc != "khong" else ("binh_luan" if co_bl else "chia_se"), "bo_qua",
                       "Nick đã tương tác bài này trước đó", link=link)
            continue
        try:
            mo_va_kiem(nc, link)
            pv = pham_vi_bai(nc.page)
            nc.tay.luot_doc(nc.rng.uniform(4, 10))
            nc.page.mouse.wheel(0, -3000)
            nc.tay.nghi(0.8, 1.6)
            lam_duoc = False
            if cam_xuc != "khong" and nc.con_lai("thich") > 0:
                lam_duoc |= _bao_cam_xuc(nc, tha_cam_xuc(nc, pv, cam_xuc), link)
                nc.nghi_thao_tac()
            if co_bl and nc.con_lai("binh_luan") > 0 and not phai_dung(nc):
                cau = chon_cau(ts.get("cau_binh_luan") or "", nc.rng, da_dung)
                if not cau:
                    bai = doc_bai(pv)
                    cau = str(nc.ai("viet_binh_luan", {"bai": bai, "san_pham_id": ts.get("san_pham", ""),
                                                        "kieu": "tu_nhien"}).get("noi_dung") or "").strip()
                if cau:
                    da_dung.append(cau)
                    lam_duoc |= _bao_binh_luan(nc, binh_luan(nc, pv, cau, "binh_luan"), "binh_luan", cau, link)
                    nc.nghi_thao_tac()
            if co_cs and nc.con_lai("chia_se") > 0 and not phai_dung(nc):
                kq = chia_se(nc, pv)
                if kq == "thanh_cong":
                    nc.su_kien("chia_se", "thanh_cong", "Đã chia sẻ lên tường", link=link)
                    lam_duoc = True
                elif kq == "khong_chac":
                    nc.su_kien("chia_se", "bo_qua", "Đã bấm Chia sẻ ngay nhưng chưa thấy thông báo xác nhận", link=link)
                elif kq == "khong_thay":
                    nc.su_kien("chia_se", "loi", "Không thấy nút/menu Chia sẻ", link=link)
                nc.nghi_thao_tac()
            if lam_duoc:
                nc.ghi_da_lam(khoa)
                ok += 1
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien(nc.hanh_dong_cuoi or "thich", "loi", str(e), link=link)
        except Exception as e:      # noqa: BLE001 - một link hỏng không làm hỏng cả lượt
            nc.su_kien(nc.hanh_dong_cuoi or "thich", "loi", f"Lỗi khi mở/tương tác: {type(e).__name__}: {e}"[:300], link=link)
        if i + 1 < len(links):
            nc.nghi_thao_tac()
    if nc.chay_thu:
        return f"Chạy thử: đã mở {len(links)} link, không thả cảm xúc/bình luận/chia sẻ."
    return f"Tương tác xong {ok}/{len(links)} bài."


def fb_nuoi_nick(nc) -> str:
    """Lướt bảng tin `phut` phút; xem video vài giây; thỉnh thoảng Thích (có trần). Không bình luận,
    không kết bạn, không chia sẻ."""
    try:
        phut = float(nc.ts.get("phut") or 10)
    except (TypeError, ValueError):
        phut = 10.0
    mo_va_kiem(nc, FB + "/")
    page = nc.page
    bat_dau = time.monotonic()
    han = bat_dau + phut * 60 / max(1.0, nc.toc_do)
    so_thich, da_xem = 0, set()
    lan_kiem = 0
    while time.monotonic() < han:
        if phai_dung(nc):
            break
        nc.tay.luot_doc(min(nc.rng.uniform(8, 25), max(0.5, han - time.monotonic())))
        lan_kiem += 1
        if lan_kiem % 3 == 0:
            nc.kiem_dang_nhap()
        # Video đang trong khung nhìn: rê chuột lên xem vài giây như người dừng lại xem.
        try:
            vid = page.locator("video")
            for k in range(min(vid.count(), 3)):
                v = vid.nth(k)
                if v.is_visible() and nc.rng.random() < 0.5:
                    nc.tay.re_chuot(v, nc.rng.uniform(4, 12))
                    break
        except Exception:
            pass
        if nc.rng.random() >= 0.3 or nc.con_lai("thich") <= 0:
            continue
        for bai in ds_bai(page):
            try:
                if not bai.is_visible():
                    continue
                box = bai.bounding_box(timeout=2000)
                vp = page.viewport_size or {"height": 900}
                if not box or box["y"] < 0 or box["y"] > vp["height"] * 0.7:
                    continue
                khoa = (bai.inner_text(timeout=2000) or "")[:80]
            except Exception:
                continue
            if khoa in da_xem or da_tha_cam_xuc(bai):
                continue
            da_xem.add(khoa)
            kq = tha_cam_xuc(nc, bai, "thich")
            if kq == "thanh_cong":
                so_thich += 1
                nc.su_kien("thich", "thanh_cong", "Nuôi nick: thích một bài trên bảng tin")
                nc.nghi_thao_tac()
            elif kq == "khong_doi":
                nc.su_kien("thich", "loi", "Nuôi nick: bấm Thích nhưng nút không đổi trạng thái")
            break
    phut_that = (time.monotonic() - bat_dau) * max(1.0, nc.toc_do) / 60
    nc.su_kien("thich", "thong_tin", f"Nuôi nick: lướt bảng tin {phut_that:.0f} phút, thích {so_thich} bài")
    return f"Nuôi nick: lướt {phut_that:.0f} phút, thích {so_thich} bài" + (" (chạy thử, không bấm Thích)." if nc.chay_thu else ".")


def fb_tuong_tac_bai_app(nc) -> str:
    so = int(nc.ts.get("so_bai") or 3)
    ds = nc.bai_doi_da_dang()
    if not ds:
        nc.su_kien("thich", "bo_qua", "Chưa có bài đội đăng trong 2-48 giờ qua để tương tác")
        return "Không có bài đội cần tương tác."
    nc.rng.shuffle(ds)
    ok = 0
    da_xu_ly = 0
    for muc in ds:
        if da_xu_ly >= so or phai_dung(nc):
            break
        link = chuan_link(str((muc or {}).get("link") or ""))
        nhom = str((muc or {}).get("nhom") or "")
        if not link:
            continue
        khoa = f"fb_app:{link}"
        if nc.da_lam(khoa):
            continue
        da_xu_ly += 1
        try:
            mo_va_kiem(nc, link)
            pv = pham_vi_bai(nc.page)
            mo_rong_bai(nc, pv)
            nc.tay.luot_doc(nc.rng.uniform(5, 15))
            nc.page.mouse.wheel(0, -3000)
            lam = False
            if nc.con_lai("thich") > 0:
                lam |= _bao_cam_xuc(nc, tha_cam_xuc(nc, pv, nc.rng.choice(["thich", "thich", "yeu_thich"])), link, nhom)
                nc.nghi_thao_tac()
            if nc.con_lai("binh_luan") > 0 and not phai_dung(nc):
                bai = doc_bai(pv)
                kq_ai = nc.ai("viet_binh_luan", {"bai": bai, "san_pham_id": nc.ts.get("san_pham", ""), "kieu": "tu_nhien",
                                                 "yeu_cau": "câu ngắn tự nhiên như thành viên nhóm, không chèn link, "
                                                            "không biểu tượng, không khen lố"})
                cau = str(kq_ai.get("noi_dung") or "").strip()
                if cau and nc.che_do in ("chay_thu", "duyet_truoc"):
                    nc.ban_nhap(loai="binh_luan", noi_dang="fb_nhom", nhom=nhom, link_goc=link,
                                bai_goc=bai.get("chu", "")[:1000], ly_do="Tương tác bài đội đã đăng",
                                noi_dung=cau, san_pham_id=nc.ts.get("san_pham", ""))
                    nc.su_kien("binh_luan", "thong_tin",
                               ("Chạy thử: " if nc.chay_thu else "") + f"tạo nháp bình luận chờ duyệt: {cau[:100]}",
                               link=link, nhom=nhom)
                    lam = True
                elif cau:
                    lam |= _bao_binh_luan(nc, binh_luan(nc, pv, cau, "binh_luan"), "binh_luan", cau, link, nhom)
                    nc.nghi_thao_tac()
            if lam and not nc.chay_thu:
                nc.ghi_da_lam(khoa)
                ok += 1
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien(nc.hanh_dong_cuoi or "thich", "loi", str(e), link=link, nhom=nhom)
        nc.nghi_thao_tac()
    return f"Tương tác {ok} bài đội đã đăng."


__all__ = ["fb_tuong_tac_link", "fb_nuoi_nick", "fb_tuong_tac_bai_app", "tim_nut"]
