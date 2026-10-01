# -*- coding: utf-8 -*-
"""providers/_common.py - tiện ích dùng chung cho các module nhà cung cấp."""
from __future__ import annotations

import re

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0.0.0 Safari/537.36")

_RE_TCGP = re.compile(r"<MSTTCGP>\s*([0-9\-]+)\s*</MSTTCGP>", re.I)
_RE_KHMS = re.compile(r"<KHMSHDon>\s*([^<]+?)\s*</KHMSHDon>", re.I)
_RE_KHH = re.compile(r"<KHHDon>\s*([^<]+?)\s*</KHHDon>", re.I)
_RE_SH = re.compile(r"<SHDon>\s*([^<]+?)\s*</SHDon>", re.I)
_RE_NBMST = re.compile(r"<NBan>.*?<MST>\s*([0-9]+)\s*</MST>", re.I | re.S)


def tcgp(xml_text: str) -> str:
    """Mã số thuế tổ chức cung cấp giải pháp hóa đơn (thẻ MSTTCGP)."""
    m = _RE_TCGP.search(xml_text)
    return (m.group(1).replace("-", "") if m else "")


def khmshdon(xml_text: str) -> str:
    m = _RE_KHMS.search(xml_text)
    return m.group(1).strip() if m else ""


def khhdon(xml_text: str) -> str:
    m = _RE_KHH.search(xml_text)
    return m.group(1).strip() if m else ""


def shdon(xml_text: str) -> str:
    m = _RE_SH.search(xml_text)
    return m.group(1).strip() if m else ""


def seller_mst(xml_text: str) -> str:
    m = _RE_NBMST.search(xml_text)
    return m.group(1) if m else ""


def ttkhac(xml_text: str, field: str) -> str:
    """Đọc giá trị 1 trường trong <TTKhac> theo tên (TTruong)."""
    rx = re.compile(r"<TTruong>\s*" + re.escape(field) +
                    r"\s*</TTruong>\s*<KDLieu>[^<]*</KDLieu>\s*<DLieu>\s*([^<]*)", re.I)
    m = rx.search(xml_text)
    return m.group(1).strip() if m else ""


def transaction_id(xml_text: str) -> str:
    """Mã tra cứu chung = TransactionID trong TTKhac (nhiều NCC dùng chung quy ước này)."""
    return ttkhac(xml_text, "TransactionID")


def make_session():
    """Phiên HTTP giả lập vân tay Chrome (curl_cffi) nếu có, không thì requests."""
    from ..gdt_client import _safe_ca_bundle
    try:
        from curl_cffi import requests as cr
        s = cr.Session(impersonate="chrome")
        s.verify = _safe_ca_bundle()
        return s
    except Exception:
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = UA
        return s
