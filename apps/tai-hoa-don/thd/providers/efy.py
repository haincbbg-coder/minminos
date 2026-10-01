# -*- coding: utf-8 -*-
"""
providers/efy.py - Nhà phát hành EFY Việt Nam (iHoaDon / eHoaDon).

Nhận diện: MSTTCGP = 0102519041 (CÔNG TY CP CÔNG NGHỆ TIN HỌC EFY VIỆT NAM),
ví dụ Ngọc Thuỷ Hà. (0100727825 EFY-eHoaDon còn nhét link PDF thẳng trong XML -> xmllink lo.)

Cổng tra cứu công khai: https://ihoadon.vn/kiem-tra - tra cứu theo SỐ HÓA ĐƠN + MÃ TRA CỨU,
HOẶC upload file XML. Trang này bảo vệ bằng reCAPTCHA (chống bot).

QUAN TRỌNG (nguyên tắc): phần mềm KHÔNG tự vượt reCAPTCHA/cơ chế chống bot của cổng.
Với hóa đơn EFY, tool:
  • đọc MÃ TRA CỨU trong XML (nếu có) và tạo LINK/hướng dẫn tra cứu điền sẵn để tải tay;
  • bản thể hiện hợp lệ ĐÃ có sẵn: XML tải từ cổng Tổng Cục Thuế được tool tự dựng thành
    bản thể hiện (nút 👁 Xem / tải HTML) - đủ giá trị lưu trữ & khai thuế.
Bản gốc NCC chỉ là bản in đẹp của nhà cung cấp, KHÔNG bắt buộc về mặt pháp lý.
"""
from __future__ import annotations

from typing import Callable

from . import ProviderError
from . import _common as C

NAME = "EFY (iHoaDon)"
MSTTCGP_EFY = "0102519041"
LOOKUP_PAGE = "https://ihoadon.vn/kiem-tra/?lang=vn"     # số HĐ + mã tra cứu (có reCAPTCHA)

# Tên trường <TTKhac> chứa MÃ TRA CỨU của EFY (thử lần lượt - chốt sau 1 XML thật).
CODE_FIELDS = [
    "Mã tra cứu", "Ma tra cuu", "MaTraCuu",
    "Mã nhận hóa đơn", "Ma nhan hoa don",
    "Chuỗi xác thực", "Chuoi xac thuc", "Chuỗi xác thực hóa đơn",
    "Mã bảo mật", "Ma bao mat", "Số bảo mật", "Fkey", "fkey",
]


def _code(xml_text: str) -> str:
    for f in CODE_FIELDS:
        v = C.ttkhac(xml_text, f)
        if v and v.strip():
            return v.strip()
    return ""


def detect(xml_text: str, inv: dict) -> bool:
    if C.tcgp(xml_text) == MSTTCGP_EFY:
        return True
    return "ihoadon.vn" in (xml_text or "").lower()


def lookup_url(sh: str, code: str) -> str:
    """Link trang tra cứu iHoaDon (khách nhập số HĐ + mã tra cứu rồi qua reCAPTCHA để tải tay)."""
    from urllib.parse import urlencode
    q = {}
    if sh:
        q["so_hd"] = sh
    if code:
        q["ma_tra_cuu"] = code
    return LOOKUP_PAGE + (("&" + urlencode(q)) if q else "")


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    sh = C.shdon(xml_text)
    khh = C.khhdon(xml_text)
    code = _code(xml_text)
    log(f"EFY (iHoaDon): HĐ {khh} số {sh}" + (f", mã tra cứu {code}" if code else ""))

    url = lookup_url(sh, code)
    inv["_manual_url"] = url
    if code:
        raise ProviderError(
            "EFY (iHoaDon) tra cứu có reCAPTCHA chống bot nên cần tải tay: mở "
            f"ihoadon.vn/kiem-tra, nhập SỐ HĐ {sh} + MÃ TRA CỨU {code}. "
            "Hoặc dùng bản thể hiện từ XML cổng thuế (đã đủ pháp lý). Link: " + url)
    raise ProviderError(
        "EFY (iHoaDon): chưa đọc được 'mã tra cứu' trong XML này (cần 1 XML thật để chốt tên "
        "trường). Trước mắt tra cứu tay tại ihoadon.vn/kiem-tra bằng số HĐ, hoặc dùng bản thể "
        "hiện từ XML cổng thuế. Link: " + url)
