# -*- coding: utf-8 -*-
"""
providers/htinvoice.py - Tải PDF gốc qua HTInvoice (laphoadon.htinvoice.vn).
Ví dụ: CÔNG TY TNHH IN ẤN MAY MẶC THỜI TRANG NTP (MSTTCGP 0315638251).

Mã tra cứu NẰM TRONG XML:
    <TTKhac><TTin><TTruong>MTCuu</TTruong>...<DLieu>81F48166...</DLieu></TTin>
    <TTin><TTruong>DDTC</TTruong>...<DLieu>laphoadon.htinvoice.vn/TraCuu</DLieu></TTin>
Không cần email. Cổng tra cứu công khai (có thể có captcha).

Luồng tra cứu sử dụng reCAPTCHA, token phiên và PDF gốc nhúng trong trang nhà phát hành.
"""
from __future__ import annotations

import re
from typing import Callable

from . import ProviderError
from . import _common as C

NAME = "HTInvoice"
MSTTCGP = "0315638251"

_RE_TTIN = re.compile(r"<TTin>(.*?)</TTin>", re.S | re.I)
_RE_TR = re.compile(r"<TTruong>\s*(.*?)\s*</TTruong>", re.S | re.I)
_RE_DL = re.compile(r"<DLieu>\s*(.*?)\s*</DLieu>", re.S | re.I)


def _field(xml_text: str, name: str) -> str:
    nl = name.strip().lower()
    for b in _RE_TTIN.findall(xml_text):
        mt = _RE_TR.search(b)
        if mt and mt.group(1).strip().lower() == nl:
            md = _RE_DL.search(b)
            return md.group(1).strip() if md else ""
    return ""


def code(xml_text: str) -> str:
    return C.ttkhac(xml_text, "MTCuu") or C.ttkhac(xml_text, "MaTraCuu")


def portal(xml_text: str) -> str:
    d = C.ttkhac(xml_text, "DDTC") or "laphoadon.htinvoice.vn/TraCuu"
    return d if d.startswith("http") else "https://" + d.lstrip("/")


def detect(xml_text: str, inv: dict) -> bool:
    if C.tcgp(xml_text) == MSTTCGP:
        return True
    return "htinvoice.vn" in xml_text.lower() and bool(code(xml_text))


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    """Public portal flow, inspected 2026-10-02: lookup token -> embedded supplier PDF."""
    import base64
    from urllib.parse import urlsplit
    mtc = inv.get("_ma_tra_cuu") or code(xml_text)
    page = portal(xml_text)
    host = urlsplit(page).hostname or ""
    if host != "htinvoice.vn" and not host.endswith(".htinvoice.vn"):
        raise ProviderError("HTInvoice: địa chỉ cổng không hợp lệ")
    base = "https://" + host
    if not mtc:
        raise ProviderError("HTInvoice: XML chưa có mã tra cứu")
    if not solver or not hasattr(solver, "recaptcha_v2"):
        raise ProviderError("HTInvoice: cần bật API giải reCAPTCHA v2 (2Captcha)")
    s = C.make_session()
    r = s.get(base + "/TraCuu", timeout=30)
    r.raise_for_status()
    sitekey = re.search(r"['\"]sitekey['\"]\s*:\s*['\"]([^'\"]+)", r.text)
    if not sitekey:
        raise ProviderError("HTInvoice: cổng đã thay đổi cấu hình reCAPTCHA")
    captcha = solver.recaptcha_v2(sitekey.group(1), base + "/TraCuu")
    r = s.post(base + "/TraCuu/TimTheoMaTraCuu", json={"MaTraCuu": mtc, "recaptchaResponse": captcha}, timeout=60)
    r.raise_for_status()
    token = r.json()
    if not isinstance(token, str) or not token.strip():
        raise ProviderError("HTInvoice: tra cứu không trả mã phiên hóa đơn; kiểm tra mã và captcha")
    r = s.get(base + "/TraCuu/HienThiHoaDon", params={"token": token}, timeout=60)
    r.raise_for_status()
    if r.content.startswith(b"%PDF"):
        return r.content
    match = re.search(r"(?:const|var|let)\s+pdfBase64\s*=\s*['\"]([A-Za-z0-9+/=\s]+)['\"]", r.text)
    if match:
        data = base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)
        if data.startswith(b"%PDF"):
            log("HTInvoice: đã tải PDF gốc từ trang hóa đơn.")
            return data
    raise ProviderError("HTInvoice: trang hóa đơn chưa trả PDF gốc hợp lệ")
