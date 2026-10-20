"""Kỹ năng YouTube: đăng video từ kho qua YouTube Studio (yt_dang_video_kho). YouTube không có nháp.

Luồng Studio: youtube.com/upload -> studio.youtube.com (hộp 'Tải video lên') -> chọn tệp -> Chi tiết
(tiêu đề <= 100 ký tự, mô tả, 'Không dành cho trẻ em') -> Tiếp x3 -> Chế độ hiển thị -> Xuất bản/Lưu.
Bị đẩy sang accounts.google.com -> lỗi đăng xuất. Thành công chỉ khi hộp 'Đã xuất bản video' hiện
(đọc được link youtu.be) hoặc hộp tải lên đóng và Studio báo đã lưu.
"""
from __future__ import annotations

import time

from ngu_canh import LoiKyNang
import tien_ich_web as w

NT = "youtube"
URL_TAI_LEN = "https://www.youtube.com/upload"
HIEN = {
    "cong_khai": ["Công khai", "Public"],
    "khong_cong_khai": ["Không công khai", "Unlisted"],
    "rieng_tu": ["Riêng tư", "Private"],
}


def _dang_xuat(nc) -> None:
    if "accounts.google.com" in (nc.page.url or ""):
        raise LoiKyNang("YouTube đẩy sang trang đăng nhập Google: nick đã đăng xuất", "dang_xuat")


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


def _dang_video(nc, bai: dict, tt: w.TrangThaiDang) -> str:
    page = nc.page
    tep = w.loc_tep(bai.get("tep_cuc_bo") or [], w.DUOI_VIDEO)
    tieu_de = str(bai.get("tieu_de") or "").strip() or next(
        (d.strip() for d in str(bai.get("noi_dung") or "").splitlines() if d.strip()), "")
    tieu_de = w.cat_gioi_han(tieu_de or "Video mới", 100)
    mo_ta = str(bai.get("noi_dung") or "").strip()
    if mo_ta.startswith(tieu_de):
        mo_ta = mo_ta[len(tieu_de):].strip()
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
    nc.nhat_ky("Chọn tệp video")
    o_tep.first.set_input_files(tep[0])
    o_td = w.dau_tien_thay(w.ung_vien(page, role="textbox", ten=["Thêm tiêu đề", "Add a title", "Tiêu đề",
                                                                 "Title"], chua=True,
                                      css=["#title-textarea [contenteditable='true']", "#title-textarea #textbox"]),
                           120000)
    if not o_td:
        _dang_xuat(nc)
        raise w.LoiDang("không hiện ô tiêu đề sau khi chọn video", False)
    nc.nhat_ky(f"Gõ tiêu đề ({len(tieu_de)} ký tự)")
    w.go_vao(nc, o_td, tieu_de.replace("\n", " "), xoa_truoc=True)
    if mo_ta:
        o_mt = w.tim(page, role="textbox", ten=["Cho người xem biết", "Tell viewers", "Mô tả", "Description"],
                     chua=True, css=["#description-textarea [contenteditable='true']"], timeout_ms=8000)
        if o_mt:
            nc.nhat_ky(f"Gõ mô tả ({len(mo_ta)} ký tự)")
            w.go_vao(nc, o_mt, mo_ta[:5000])
    tre = w.tim(page, role="radio", ten=["Không, nội dung này không dành cho trẻ em", "No, it's not made for kids",
                                         "không dành cho trẻ em", "not made for kids"], chua=True, timeout_ms=8000)
    if tre:
        nc.tay.bam(tre)
    else:
        nc.nhat_ky("Không thấy lựa chọn 'không dành cho trẻ em' (có thể kênh đã đặt sẵn)")
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


KICH_BAN = {"yt_dang_video_kho": yt_dang_video_kho}
