# -*- coding: utf-8 -*-
"""EFY public lookup via invoice number, lookup code and configured reCAPTCHA solver."""
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


def find_code(xml_text: str, inv: dict) -> str:
    """Use the code recovered from email/user input before the XML fallback."""
    return str(inv.get("_ma_tra_cuu") or inv.get("_code") or
               (inv.get("_gmail_lookup") or {}).get("ma_tra_cuu") or
               _code(xml_text)).strip()


def lookup_url(sh: str, code: str) -> str:
    """Link trang tra cứu iHoaDon (khách nhập số HĐ + mã tra cứu rồi qua reCAPTCHA để tải tay)."""
    from urllib.parse import urlencode
    q = {}
    if sh:
        q["shd"] = sh
    if code:
        q["mtc"] = code
    return LOOKUP_PAGE + (("&" + urlencode(q)) if q else "")


def _download(session, url):
    from urllib.parse import urljoin
    from .xmllink import _public_url, MAX_BYTES
    for _ in range(4):
        _public_url(url)
        with session.get(url, timeout=60, allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            if response.status_code != 200:
                raise ProviderError(f"EFY: tải file HTTP {response.status_code}")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ProviderError("EFY: file vượt giới hạn 25 MB")
                chunks.append(chunk)
            return b"".join(chunks)
    raise ProviderError("EFY: đường dẫn tải chuyển hướng quá nhiều lần")


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    import re
    from urllib.parse import urljoin
    from .smartsign import identity
    code = find_code(xml_text, inv)
    inv["_manual_url"] = lookup_url(C.shdon(xml_text), code)
    if not code:
        raise ProviderError("EFY: chưa có mã tra cứu trong XML hoặc Gmail đã ghép")
    if solver is None:
        raise ProviderError("EFY: cần cấu hình dịch vụ giải reCAPTCHA")
    expected = identity(xml_text)
    with C.make_session() as session:
        page = session.get(LOOKUP_PAGE, timeout=40, allow_redirects=False)
        if page.status_code != 200:
            raise ProviderError(f"EFY: mở trang tra cứu HTTP {page.status_code}")
        match = re.search(r"site_key_recaptcha\s*=\s*['\"]([^'\"]+)['\"]", page.text)
        if not match:
            raise ProviderError("EFY: chưa đọc được cấu hình reCAPTCHA của trang tra cứu")
        for attempt in range(2):
            token = solver.recaptcha_v2(match.group(1), LOOKUP_PAGE)
            response = session.post("https://ihoadon.vn/kiem-tra/check", json={
                "certificate_id": C.shdon(xml_text), "signature": code,
                "gRecaptchaResponse": token,
            }, timeout=90, allow_redirects=False)
            if response.status_code != 200:
                raise ProviderError(f"EFY: tra cứu HTTP {response.status_code}")
            obj = response.json()
            if obj.get("status") == "success":
                break
            message = str(obj.get("message") or "Không tìm thấy hóa đơn")
            if not any(word in message.lower() for word in ("captcha", "xác minh", "xác thực")):
                raise ProviderError("EFY: " + message[:250])
            log(f"EFY: reCAPTCHA bị từ chối ({attempt + 1}/2)")
        else:
            raise ProviderError("EFY: reCAPTCHA chưa được chấp nhận sau 2 lần")
        data = obj.get("data") or {}
        if not isinstance(data, dict):
            raise ProviderError("EFY: cấu trúc kết quả tra cứu không hợp lệ")
        # Download the supplier XML too, so a wrong/stale lookup cannot attach another
        # company's PDF to the current invoice. Do not use local HTML rendering here.
        files = data.get("attach_file") or []
        xmls = [f for f in files if isinstance(f, dict) and
                (str(f.get("name", "")).lower().endswith(".xml") or f.get("code") == "HD01")]
        if len(xmls) != 1 or not xmls[0].get("link"):
            raise ProviderError("EFY: thiếu XML hãng để đối chiếu hóa đơn; chưa lưu PDF")
        source = _download(session, urljoin(LOOKUP_PAGE, xmls[0]["link"]))
        if identity(source.decode("utf-8-sig")) != expected:
            raise ProviderError("EFY: XML hãng không khớp MST, ký hiệu hoặc số hóa đơn")
        pdf_file = data.get("pdf_file") or {}
        if not isinstance(pdf_file, dict) or not pdf_file.get("link"):
            raise ProviderError("EFY: kết quả tra cứu chưa có đường dẫn PDF gốc")
        pdf = _download(session, urljoin(LOOKUP_PAGE, pdf_file["link"]))
        if not pdf.startswith(b"%PDF-"):
            raise ProviderError("EFY: đường dẫn tải chưa trả về PDF gốc")
        log("EFY: đã đối chiếu XML hãng và tải PDF gốc")
        return pdf
