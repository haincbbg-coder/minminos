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
    """Verify the slider once, then submit the public portal's download form."""
    import base64
    import io
    from PIL import Image
    mst = C.seller_mst(xml_text)
    secret = inv.get("_ma_tra_cuu") or _secret(xml_text)
    if not mst or not secret:
        raise ProviderError("Viettel: thiếu MST người bán hoặc mã số bí mật trong XML")
    inv["_manual_url"] = search_url(mst, secret)
    if not solver or not hasattr(solver, "slider"):
        raise ProviderError("Viettel: cần bật API giải captcha trượt (OmoCaptcha hoặc 2Captcha)")
    s = C.make_session()
    r = s.get(HOST + CAPTCHA_GENERATE, timeout=30)
    r.raise_for_status()
    challenge = r.json()
    def decode_image(value):
        if not isinstance(value, str) or not value.startswith("data:image/") or ";base64," not in value:
            raise ProviderError("Viettel: định dạng ảnh captcha đã thay đổi")
        return base64.b64decode(value.split(",", 1)[1], validate=True)
    bg = decode_image(challenge.get("backgroundUrl"))
    piece = decode_image(challenge.get("puzzleUrl"))
    with Image.open(io.BytesIO(bg)) as im:
        width, height = im.size
    with Image.open(io.BytesIO(piece)) as im:
        piece_width = im.width
    offset = solver.slider(bg, piece, "vinvoice.viettel.vn", width, height, piece_width)
    r = s.post(HOST + "/api/services/einvoiceuaa/api/captcha/verify",
               json={"token": challenge.get("token"), "offsetX": offset}, timeout=30)
    r.raise_for_status()
    verified = r.json()
    if not verified.get("success") or not verified.get("token"):
        raise ProviderError("Viettel: cổng không chấp nhận kết quả captcha trượt; chưa tải PDF")
    log("Viettel: captcha trượt đã được cổng xác nhận.")
    payload = {"supplierTaxCode": mst, "reservationCode": secret, "recaptcha": verified["token"]}
    # Both routes are the portal's own current/legacy download sequence.
    routes = ["/api/services/einvoicequery/sync/utility/downloadPDF",
              "/api/services/einvoiceadminapplication/no-auth/invoice-v1/downloadPDF"]
    for route in routes:
        r = s.post(HOST + route, params={"taxCode": mst}, json=payload, timeout=60)
        if r.status_code == 200:
            pdf = _pdf_from_bytes(r.content)
            if pdf:
                log("Viettel: đã tải PDF gốc.")
                return pdf
    raise ProviderError("Viettel: đã xác thực captcha nhưng cổng chưa trả PDF hợp lệ")
