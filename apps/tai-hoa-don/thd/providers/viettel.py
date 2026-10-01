# -*- coding: utf-8 -*-
"""
providers/viettel.py - Tải PDF GỐC hóa đơn phát hành qua Viettel S-Invoice / vinvoice.

Nhận diện: MSTTCGP = 0100109106 (Tập đoàn CN-VT Quân đội / Viettel), hoặc XML có trường
<TTKhac> "Mã số bí mật".

Luồng tra cứu công khai của Viettel (khách không cần đăng nhập):
    MST bên bán + "Mã số bí mật" (có sẵn trong XML) + Mã bảo mật (captcha ảnh).
Tool tự giải captcha ảnh bằng dịch vụ (2Captcha...) rồi tải bản thể hiện PDF.

GHI CHÚ KỸ THUẬT: cổng vinvoice chạy JavaScript (SPA) gọi API ở api-vinvoice.viettel.vn,
KHÔNG lộ endpoint trong HTML. Module thử LẦN LƯỢT các endpoint ứng viên và GHI LOG rõ ràng
để chốt đúng endpoint sau 1 lần chạy thật (giống cách đã hoàn thiện EasyInvoice).
Nếu chưa lấy được PDF -> raise ProviderError (đánh dấu mềm 'cần tải tay', KHÔNG hỏng hóa đơn).
"""
from __future__ import annotations

import base64
import io
import json
import re
import zipfile
from typing import Callable, Optional

from . import ProviderError
from . import _common as C

NAME = "Viettel S-Invoice"
MSTTCGP_VIETTEL = "0100109106"

# Cổng tra cứu công khai của Viettel (đã xác minh thực tế 19/09/2026).
HOST = "https://vinvoice.viettel.vn"
SEARCH_PAGE = HOST + "/utilities/invoice-search"     # trang tra cứu (khách nhập MST + mã số bí mật)
# Endpoint captcha THẬT: là captcha TRƯỢT (slider puzzle) - CHỐNG BOT, không phải captcha ảnh chữ.
CAPTCHA_GENERATE = "/api/services/einvoiceuaa/api/captcha/generate"
# Trường dữ liệu form: 'Mã số bí mật' = reservationCode, MST bên bán = supplierTaxCode.


# Viettel xếp <TTin> theo THỨ TỰ NGƯỢC: <DLieu>..</DLieu><KDLieu>..</KDLieu><TTruong>tên</TTruong>
# (khác các hãng khác) nên phải đọc riêng, chấp nhận cả 2 chiều.
_RE_TTIN = re.compile(r"<TTin>(.*?)</TTin>", re.S | re.I)
_RE_TRUONG = re.compile(r"<TTruong>\s*(.*?)\s*</TTruong>", re.S | re.I)
_RE_DLIEU = re.compile(r"<DLieu>\s*(.*?)\s*</DLieu>", re.S | re.I)


def _ttin(xml_text: str, field: str) -> str:
    """Đọc giá trị 1 trường <TTin> theo tên TTruong, không phụ thuộc thứ tự con."""
    fl = field.strip().lower()
    for block in _RE_TTIN.findall(xml_text):
        mt = _RE_TRUONG.search(block)
        if mt and mt.group(1).strip().lower() == fl:
            md = _RE_DLIEU.search(block)
            return (md.group(1).strip() if md else "")
    return ""


def _secret(xml_text: str) -> str:
    """Mã số bí mật của Viettel (trong TTKhac)."""
    for f in ("Mã số bí mật", "Ma so bi mat", "MaSoBiMat", "SecretCode"):
        v = _ttin(xml_text, f) or C.ttkhac(xml_text, f)
        if v:
            return v.strip()
    return ""


def _invoice_uuid(xml_text: str) -> str:
    """Một số hóa đơn Viettel còn có 'Mã số' = UUID nội bộ (dùng tải trực tiếp nếu API cần)."""
    for f in ("Mã số", "Ma so"):
        v = _ttin(xml_text, f) or C.ttkhac(xml_text, f)
        if v and re.fullmatch(r"[0-9a-fA-F-]{20,}", v.strip()):
            return v.strip()
    return ""


def detect(xml_text: str, inv: dict) -> bool:
    if C.tcgp(xml_text) == MSTTCGP_VIETTEL:
        return True
    return bool(_secret(xml_text)) and "viettel" in xml_text.lower()


def _pdf_from_bytes(data: bytes) -> Optional[bytes]:
    if not data:
        return None
    if data[:4] == b"%PDF":
        return data
    # có thể là ZIP (PDF + XML)
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for n in z.namelist():
                    if n.lower().endswith(".pdf"):
                        b = z.read(n)
                        if b[:4] == b"%PDF":
                            return b
        except Exception:  # noqa
            return None
    return None


def _pdf_from_json(obj) -> Optional[bytes]:
    """Bóc PDF base64 từ JSON kết quả (nhiều tên trường khác nhau)."""
    if not isinstance(obj, dict):
        return None
    for k in ("fileToBytes", "fileContent", "data", "pdf", "base64", "content", "result"):
        v = obj.get(k)
        if isinstance(v, str) and len(v) > 500:
            try:
                b = base64.b64decode(v)
                p = _pdf_from_bytes(b)
                if p:
                    return p
            except Exception:  # noqa
                pass
        if isinstance(v, dict):
            p = _pdf_from_json(v)
            if p:
                return p
    return None


def search_url(mst: str, secret: str) -> str:
    """Link trang tra cứu Viettel để khách TỰ tải (điền sẵn MST + mã số bí mật trên URL)."""
    from urllib.parse import urlencode
    q = urlencode({"supplierTaxCode": mst, "reservationCode": secret})
    return f"{SEARCH_PAGE}?{q}"


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    """Tra cứu & tải bản gốc từ cổng công khai Viettel.

    CẬP NHẬT 20/09/2026 (đã kiểm chứng thực tế trên vinvoice.viettel.vn):
    cổng tra cứu Viettel nay bảo vệ bằng CAPTCHA TRƯỢT (slider puzzle) - một cơ chế
    CHỐNG BOT, không phải captcha ảnh chữ. Phần mềm KHÔNG tự vượt cơ chế chống bot này.
    Thay vào đó tool xác nhận đúng cổng + mã số bí mật rồi hướng dẫn tải tay bằng LINK
    ĐIỀN SẴN (chỉ còn kéo thanh trượt + bấm Tìm kiếm). Bản gốc Viettel cũng thường được
    đính kèm sẵn trong EMAIL người bán - dùng '📧 Quét Gmail' để lấy tự động, khỏi captcha.
    """
    mst = C.seller_mst(xml_text)
    secret = _secret(xml_text)
    sh = C.shdon(xml_text)
    khh = C.khhdon(xml_text)
    if not mst:
        raise ProviderError("Viettel: thiếu MST người bán trong XML")
    if not secret:
        raise ProviderError("Viettel: XML không có 'Mã số bí mật' để tra cứu")

    log(f"Viettel: HĐ {khh} số {sh} - MST {mst}, mã số bí mật {secret}")
    # Kiểm tra nhanh cổng còn sống + xác nhận là captcha trượt (để báo lý do chính xác).
    slider = False
    try:
        s = C.make_session()
        r = s.get(HOST + CAPTCHA_GENERATE, timeout=30)
        if r.status_code == 200 and ("backgroundUrl" in r.text or "image" in (r.headers.get("Content-Type") or "")):
            slider = True
            log("Viettel: cổng dùng captcha TRƯỢT (slider) chống bot - không tự vượt, chuyển tải tay.")
    except Exception:  # noqa
        pass

    url = search_url(mst, secret)
    inv["_manual_url"] = url          # để giao diện mở link điền sẵn khi bấm 'tải tay'
    raise ProviderError(
        "Viettel dùng captcha TRƯỢT chống bot nên cần tải tay (hoặc lấy tự động qua "
        f"'📧 Quét Gmail' vì bản gốc thường đính kèm email). Mở link đã điền sẵn: {url}"
        if slider else
        "Viettel: cần tải tay tại cổng tra cứu. Mở link đã điền sẵn MST + mã số bí mật: " + url)
