# -*- coding: utf-8 -*-
"""
providers/sapo.py - Tải PDF gốc hóa đơn phát hành qua Sapo Invoice (sapo.vn).

API công khai (không cần captcha):
  POST https://invoice.sapo.vn/api/invoices/look_up
       {"invoice": {"reference_code": "<mã tra cứu>"}}      -> tra bằng mã
       {"invoice": {"base64_xml": "<b64 của file xml>"}}    -> tra bằng file XML
  Trả về {"invoice": {"base64": "<PDF b64>", "base64_zip": "<zip chứa xml>", ...}}
  -> invoice.base64 chính là file PDF gốc (rất gọn, không cần tải thêm).
"""
from __future__ import annotations

import base64
import json
from typing import Callable

from . import ProviderError
from . import _common as C

NAME = "Sapo Invoice"
TCGP = ["0103243195"]     # MST tổ chức cung cấp giải pháp (Sapo)
API = "https://invoice.sapo.vn/api/invoices/look_up"


def detect(xml_text: str, inv: dict) -> bool:
    if C.tcgp(xml_text) in TCGP:
        return True
    return "sapo" in xml_text.lower()


def _lookup(s, payload: dict) -> dict:
    r = s.post(API, data=json.dumps(payload), timeout=90,
               headers={"Content-Type": "application/json", "Accept": "application/json",
                        "Origin": "https://www.sapo.vn", "Referer": "https://www.sapo.vn/"})
    if r.status_code != 200:
        raise ProviderError(f"Sapo trả về HTTP {r.status_code}")
    try:
        return json.loads(r.text)
    except ValueError:
        raise ProviderError("Sapo trả về dữ liệu không phải JSON")


def fetch_pdf_by_code(code: str, log: Callable[[str], None]) -> bytes:
    """Tải PDF gốc Sapo chỉ từ mã tra cứu (dùng khi lấy mã từ email)."""
    s = C.make_session()
    data = _lookup(s, {"invoice": {"reference_code": code}})
    errs = data.get("errors") or []
    if errs:
        raise ProviderError(f"Sapo: {errs[0].get('message') or errs[0].get('fields') or 'không tra được'}")
    pdf_b64 = (data.get("invoice") or {}).get("base64")
    if not pdf_b64:
        raise ProviderError("Sapo không trả PDF cho mã này")
    return base64.b64decode(pdf_b64)


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    s = C.make_session()
    code = C.transaction_id(xml_text)
    data = None
    if code:
        data = _lookup(s, {"invoice": {"reference_code": code}})
        if data.get("errors"):
            log(f"Sapo: mã tra cứu {code} lỗi, thử bằng file XML...")
            data = None
    if data is None:
        b64 = base64.b64encode(xml_text.lstrip("﻿").encode("utf-8")).decode()
        data = _lookup(s, {"invoice": {"base64_xml": b64}})
    errs = data.get("errors") or []
    if errs:
        raise ProviderError(f"Sapo: {errs[0].get('message') or errs[0].get('fields') or 'không tra được'}")
    invd = data.get("invoice") or {}
    pdf_b64 = invd.get("base64")
    if not pdf_b64:
        raise ProviderError("Sapo không trả PDF cho hóa đơn này")
    try:
        return base64.b64decode(pdf_b64)
    except Exception:
        raise ProviderError("Sapo trả PDF base64 không hợp lệ")
