# -*- coding: utf-8 -*-
"""providers/_common.py - tiện ích dùng chung cho các module nhà cung cấp."""
from __future__ import annotations

import xml.etree.ElementTree as ET

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0.0.0 Safari/537.36")

def tcgp(xml_text: str) -> str:
    """Mã số thuế tổ chức cung cấp giải pháp hóa đơn (thẻ MSTTCGP)."""
    return _tag(xml_text, "MSTTCGP").replace("-", "")


def khmshdon(xml_text: str) -> str:
    return _tag(xml_text, "KHMSHDon")


def khhdon(xml_text: str) -> str:
    return _tag(xml_text, "KHHDon")


def shdon(xml_text: str) -> str:
    return _tag(xml_text, "SHDon")


def seller_mst(xml_text: str) -> str:
    return _tag(xml_text, "MST", "NBan")


def _tag(xml_text: str, name: str, parent: str = "") -> str:
    try:
        root = ET.fromstring(xml_text)
        nodes = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].lower() == parent.lower()] if parent else [root]
        for node in nodes:
            for child in node.iter():
                if child.tag.rsplit("}", 1)[-1].lower() == name.lower():
                    return (child.text or "").strip()
    except ET.ParseError:
        pass
    return ""


def ttkhac(xml_text: str, field: str) -> str:
    """Đọc giá trị 1 trường trong <TTKhac> theo tên (TTruong)."""
    try:
        root = ET.fromstring(xml_text)
        for node in root.iter():
            fields = {c.tag.rsplit("}", 1)[-1].lower(): (c.text or "").strip() for c in node}
            if fields.get("ttruong", "").casefold() == field.casefold():
                return fields.get("dlieu", "")
    except ET.ParseError:
        pass
    return ""


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
