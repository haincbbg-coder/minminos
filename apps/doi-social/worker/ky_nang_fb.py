"""Kỹ năng Facebook. `dang_bai` (việc cũ `fb_dang_bai`) giữ NGUYÊN hành vi đã chạy thật; 13 mẫu fb_*
cùng việc nội bộ `dang_ban_nhap:facebook` và `fb_gui_tin` khai trong `KICH_BAN` ở cuối tệp (mã nằm ở
fb_dang.py, fb_tuong_tac.py, fb_nhom.py, fb_tin.py, tiện ích chung ở fb_chung.py).

Đăng một bài Facebook (tường cá nhân, Trang hoặc nhóm) như người thật:

Các bước, mỗi bước ghi vào nhật ký để gửi về MinMin:
  1. Mở nơi đăng (link Trang/nhóm, hoặc tường của nick), đọc lướt một chút.
  2. Kiểm tra nick còn đăng nhập (không bị đẩy về trang login/checkpoint).
  3. Bấm ô "Bạn đang nghĩ gì?" / "Tạo bài viết" bằng chuột di theo đường cong.
  4. Gõ nội dung từng chữ (nguoi.Nguoi.go).
  5. Bấm "Ảnh/video", chọn tệp, chờ tải lên xong.
  6. Đọc lại vài giây, bấm "Tiếp" nếu có, rồi "Đăng".
  7. Chờ hộp soạn bài đóng, tìm lại câu đầu của bài trên trang, chụp màn hình.

Chọn phần tử theo VAI TRÒ + NHÃN (role/aria-label) bằng cả tiếng Việt và tiếng Anh thay vì
class CSS, vì class của Facebook đổi liên tục còn nhãn trợ năng thì hiếm khi đổi.
"""
from __future__ import annotations

import re
import time

from ngu_canh import LoiKyNang  # noqa: F401  - ky_nang_fb.LoiKyNang LÀ ngu_canh.LoiKyNang
from nguoi import Nguoi

_MO_O_SOAN = re.compile(r"(Bạn đang nghĩ gì|What's on your mind|Viết gì đó|Write something|"
                        r"Tạo bài viết công khai|Tạo bài viết|Create post|Create a public post)", re.I)
_ANH_VIDEO = re.compile(r"^(Ảnh/video|Ảnh/Video|Photo/video|Photo/Video)$", re.I)
_TIEP = re.compile(r"^(Tiếp|Next)$", re.I)
_DANG = re.compile(r"^(Đăng|Post|Đăng bài)$", re.I)
_CHUYEN = re.compile(r"^(Chuyển ngay|Chuyển|Switch now|Switch)$", re.I)
_XAC_NHAN_CHUYEN = re.compile(r"^(Chuyển|Switch|Tiếp tục|Continue)$", re.I)


def _dau_tien_thay(cands, timeout_ms: int = 15000):
    """Locator đầu tiên trong danh sách đang hiện trên trang, chờ tối đa timeout."""
    han = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < han:
        for loc in cands:
            try:
                if loc.count() and loc.first.is_visible():
                    return loc.first
            except Exception:
                pass
        time.sleep(0.4)
    return None


def mo_trang(page, url: str) -> None:
    """page.goto chịu được Facebook tự chuyển hướng (vd thêm &_ps=dest_url khi mở Trang): Playwright
    báo 'interrupted by another navigation' dù trang vẫn tới nơi. Gặp lỗi đó thì chờ trang ổn định."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        if "interrupted by another navigation" not in str(e):
            raise
        page.wait_for_load_state("domcontentloaded", timeout=60000)


def dang_bai(page, viec: dict, tep_cuc_bo: list, nhat_ky) -> str:
    """Thực hiện đăng. Raise LoiKyNang với câu dễ hiểu khi hỏng. Trả thông điệp thành công."""
    ts = viec.get("tham_so") or {}
    noi_dung = str(ts.get("noi_dung") or "")
    noi_dang = str(ts.get("noi_dang") or "") or "https://www.facebook.com/me"
    tay = Nguoi(page)

    nhat_ky(f"Mở {noi_dang}")
    mo_trang(page, noi_dang)
    tay.nghi(2.5, 5.0)
    url = page.url.lower()
    if "/login" in url or "checkpoint" in url or page.locator("input[name='pass']").count():
        raise LoiKyNang("nick chưa đăng nhập Facebook hoặc đang bị checkpoint - mở profile của nick (GPM hoặc Chrome MinMin) kiểm tra tay")
    if ts.get("noi_dang"):
        # Trang (kiểu mới) mà nick là quản trị: Facebook mời "Chuyển sang Trang" mới đăng được
        # với danh nghĩa Trang. Bấm chuyển, đợi tải lại, rồi mở lại đúng nơi đăng.
        nut = _dau_tien_thay([page.get_by_role("button", name=_CHUYEN)], 4000)
        if nut:
            nhat_ky("Chuyển sang danh nghĩa Trang")
            tay.bam(nut)
            tay.nghi(1.5, 3.0)
            xn = _dau_tien_thay([page.get_by_role("dialog").get_by_role("button", name=_XAC_NHAN_CHUYEN)], 4000)
            if xn:
                tay.bam(xn)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            tay.nghi(4.0, 7.0)
            mo_trang(page, noi_dang)
            tay.nghi(2.5, 5.0)
    tay.luot(1)
    page.mouse.wheel(0, -2000)
    tay.nghi(0.8, 1.6)

    nhat_ky("Tìm ô soạn bài")
    o_mo = _dau_tien_thay([page.get_by_role("button", name=_MO_O_SOAN),
                           page.get_by_text(_MO_O_SOAN)], 20000)
    if not o_mo:
        raise LoiKyNang("không thấy ô 'Bạn đang nghĩ gì?' / 'Tạo bài viết' ở nơi đăng này "
                        "(nick có quyền đăng ở đây không?)")
    tay.bam(o_mo)
    tay.nghi(1.5, 3.0)

    hop = _dau_tien_thay([page.get_by_role("dialog").filter(has=page.locator("[contenteditable='true']"))], 20000)
    if not hop:
        raise LoiKyNang("bấm ô soạn bài nhưng hộp 'Tạo bài viết' không hiện ra")
    o_chu = hop.locator("[contenteditable='true'][role='textbox'], [contenteditable='true']").first

    if noi_dung:
        nhat_ky(f"Gõ nội dung ({len(noi_dung)} ký tự, từng chữ)")
        tay.bam(o_chu)
        tay.nghi(0.6, 1.4)
        tay.go(noi_dung)
        tay.nghi(1.0, 2.2)

    if tep_cuc_bo:
        nhat_ky(f"Tải {len(tep_cuc_bo)} ảnh/video")
        nut_anh = _dau_tien_thay([hop.get_by_role("button", name=_ANH_VIDEO),
                                  hop.locator("[aria-label='Ảnh/video'], [aria-label='Photo/video']")], 10000)
        o_tep = hop.locator("input[type='file']")
        if nut_anh and not o_tep.count():
            tay.bam(nut_anh)
            tay.nghi(1.0, 2.0)
        if not o_tep.count():
            raise LoiKyNang("không tìm thấy chỗ chọn ảnh/video trong hộp soạn bài")
        o_tep.first.set_input_files(tep_cuc_bo)
        han = time.monotonic() + 15 * 60
        tay.nghi(3.0, 5.0)
        while time.monotonic() < han:      # chờ thanh tải lên biến mất
            if not hop.get_by_role("progressbar").count():
                break
            time.sleep(2)
        tay.nghi(1.5, 3.0)

    tay.nghi(1.5, 4.0)    # đọc lại bài như người trước khi bấm Đăng
    nut_tiep = _dau_tien_thay([hop.get_by_role("button", name=_TIEP)], 2500)
    if nut_tiep:
        nhat_ky("Bấm Tiếp")
        tay.bam(nut_tiep)
        tay.nghi(1.5, 3.0)
        hop = _dau_tien_thay([page.get_by_role("dialog")], 10000) or hop
    nut_dang = _dau_tien_thay([hop.get_by_role("button", name=_DANG),
                               hop.locator("[aria-label='Đăng'], [aria-label='Post']")], 15000)
    if not nut_dang:
        raise LoiKyNang("không thấy nút Đăng trong hộp soạn bài")
    if nut_dang.get_attribute("aria-disabled") == "true":
        raise LoiKyNang("nút Đăng đang bị khoá (Facebook chưa nhận nội dung hoặc tệp chưa tải xong)")
    nhat_ky("Bấm Đăng")
    tay.bam(nut_dang)

    han = time.monotonic() + (15 * 60 if tep_cuc_bo else 120)
    while time.monotonic() < han:
        try:
            if not hop.is_visible():
                break
        except Exception:
            break
        time.sleep(1.5)
    else:
        raise LoiKyNang("đã bấm Đăng nhưng hộp soạn bài không đóng (Facebook có thể đang báo lỗi)")
    tay.nghi(3.0, 6.0)

    dau = next((d.strip() for d in noi_dung.splitlines() if d.strip()), "")[:40]
    if dau:
        try:
            page.get_by_text(dau, exact=False).first.wait_for(timeout=20000)
            nhat_ky("Đã thấy bài trên trang")
            return "Đã đăng và thấy bài trên trang."
        except Exception:
            nhat_ky("Đăng xong nhưng chưa thấy bài ngay (có thể chờ duyệt nhóm hoặc video đang xử lý)")
            return "Đã bấm Đăng, hộp soạn bài đã đóng; chưa thấy bài ngay trên trang (nhóm chờ duyệt hoặc video đang xử lý)."
    return "Đã bấm Đăng, hộp soạn bài đã đóng."


# ---------------------------------------------------------------------------- đăng ký mẫu
# Nạp ở cuối tệp: các tệp fb_*.py dùng ngu_canh/nguoi, không vòng ngược về đây lúc import.
import fb_dang  # noqa: E402
import fb_nhom  # noqa: E402
import fb_tin  # noqa: E402
import fb_tuong_tac  # noqa: E402

KICH_BAN = {
    "fb_dang_nhom_ai": fb_dang.fb_dang_nhom_ai,
    "fb_dang_tuong_kho": fb_dang.fb_dang_tuong_kho,
    "fb_dang_nhom_link": fb_dang.fb_dang_nhom_link,
    "fb_dang_tuong_ai": fb_dang.fb_dang_tuong_ai,
    "fb_tuong_tac_link": fb_tuong_tac.fb_tuong_tac_link,
    "fb_nuoi_nick": fb_tuong_tac.fb_nuoi_nick,
    "fb_binh_luan_nhom_sp": fb_nhom.fb_binh_luan_nhom_sp,
    "fb_binh_luan_nhom_link": fb_nhom.fb_binh_luan_nhom_link,
    "fb_tra_loi_binh_luan": fb_tin.fb_tra_loi_binh_luan,
    "fb_tra_loi_tin_nhan": fb_tin.fb_tra_loi_tin_nhan,
    "fb_tuong_tac_bai_app": fb_tuong_tac.fb_tuong_tac_bai_app,
    "fb_nhan_tin_ds": fb_tin.fb_nhan_tin_ds,
    "fb_tham_gia_nhom_sp": fb_nhom.fb_tham_gia_nhom_sp,
    # nội bộ (máy chủ tạo, không có trong danh mục)
    "dang_ban_nhap:facebook": fb_dang.dang_ban_nhap_fb,
    "fb_gui_tin": fb_tin.fb_gui_tin,
}
