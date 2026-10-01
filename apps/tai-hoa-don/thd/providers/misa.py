# -*- coding: utf-8 -*-
"""
providers/misa.py - Tải PDF gốc hóa đơn phát hành qua MISA meInvoice (meinvoice.vn).

Trang tra cứu công khai https://www.meinvoice.vn/tra-cuu/ cho phép tra bằng:
  (a) MÃ TRA CỨU  -> POST tra-cuu/GetInvoiceDataByTransactionID {transactionID}
                     -> {"success":true, "customData":"<ext>"}
  (b) FILE XML     -> POST tra-cuu/GetXMLData {invData:<nội dung xml>}
                     -> {"success":true, "data":"{\"txtCodeValue\":\"<mã tra cứu>\",...}",
                         "customData":"<ext>"}
  rồi tải PDF:   GET tra-cuu/DownloadHandler.ashx?Type=pdf&Viewer=1&Code=<mã>&ext=<ext>

Ưu điểm của (b): XML tải từ cổng thuế (có chữ ký số) là đủ, KHÔNG cần biết mã tra cứu.
Sau > 2 lần tra sai trong 1 phiên, MISA đòi captcha -> tool tạo phiên mới cho mỗi hóa đơn
và không thử lại bừa.
"""
from __future__ import annotations

import json
import re
import time
from typing import Callable

from . import ProviderError

NAME = "MISA meInvoice"
TCGP = ["0101243150"]   # MST tổ chức cung cấp giải pháp (MISA JSC)
BASE = "https://www.meinvoice.vn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0.0.0 Safari/537.36")

MST_TCGP = "0101243150"   # MST của MISA JSC - thẻ <MSTTCGP> trong XML (tổ chức cung cấp giải pháp)
ACCEPT_HTML = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"

_RE_TCGP = re.compile(r"<MSTTCGP>\s*([0-9\-]+)\s*</MSTTCGP>", re.I)
_RE_CODE_URL = re.compile(r"meinvoice\.vn/tra-cuu/?\?(?:[^\"'<\s]*&)?sc=([A-Za-z0-9]+)", re.I)
_RE_CODE_TRANS = re.compile(r"<TTruong>\s*TransactionID\s*</TTruong>\s*<KDLieu>[^<]*</KDLieu>\s*<DLieu>\s*([A-Za-z0-9]{6,})\s*</DLieu>", re.I)
_RE_CODE_ID = re.compile(r"<DLHDon\s+Id=\"([A-Za-z0-9]{8,})\"", re.I)


def detect(xml_text: str, inv: dict) -> bool:
    m = _RE_TCGP.search(xml_text)
    if m and m.group(1).replace("-", "") == MST_TCGP:
        return True
    t = xml_text.lower()
    return "meinvoice" in t or "misa jsc" in t


def find_code(xml_text: str) -> str:
    """Mã tra cứu MISA = TransactionID (12 ký tự) - nằm ở TTKhac/TransactionID hoặc Id của DLHDon."""
    for rx in (_RE_CODE_URL, _RE_CODE_TRANS, _RE_CODE_ID):
        m = rx.search(xml_text)
        if m:
            return m.group(1)
    return ""


def _session():
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


def _post_json(s, path: str, data: dict, referer: str) -> dict:
    r = s.post(BASE + path, data=data, timeout=60, headers={
        "Referer": referer, "Origin": BASE, "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    if r.status_code != 200:
        raise ProviderError(f"MISA trả về HTTP {r.status_code} khi gọi {path}")
    try:
        return json.loads(r.text)
    except ValueError:
        raise ProviderError("MISA trả về dữ liệu không phải JSON (có thể bị Cloudflare chặn)")


def fetch_pdf_by_code(code: str, log: Callable[[str], None]) -> bytes:
    """Tải PDF gốc MISA chỉ từ mã tra cứu (TransactionID) - dùng khi lấy mã từ email."""
    s = _session()
    referer = BASE + "/tra-cuu/"
    r0 = s.get(referer, timeout=60)
    if r0.status_code != 200:
        raise ProviderError(f"Không mở được trang tra cứu MISA (HTTP {r0.status_code})")
    res = _post_json(s, "/tra-cuu/GetInvoiceDataByTransactionID", {"transactionID": code}, referer)
    if not res.get("success"):
        raise ProviderError(f"MISA: mã tra cứu {code} không hợp lệ ({res.get('errorCode')})")
    ext = str(res.get("customData") or "")
    return _download(s, code, ext, referer)


def _download(s, code, ext, referer) -> bytes:
    url = f"{BASE}/tra-cuu/DownloadHandler.ashx?Type=pdf&Viewer=1&Code={code}&ext={ext}"
    time.sleep(0.3)
    r = s.get(url, timeout=120, headers={"Referer": referer, "Accept": ACCEPT_HTML,
                                         "Sec-Fetch-Dest": "iframe", "Sec-Fetch-Mode": "navigate",
                                         "Sec-Fetch-Site": "same-origin"})
    if r.status_code != 200:
        raise ProviderError(f"MISA không cho tải PDF (HTTP {r.status_code})")
    data = r.content
    if not data.lstrip().startswith(b"%PDF"):
        snippet = data[:200].decode("utf-8", "ignore").strip().replace("\n", " ")
        raise ProviderError(f"MISA trả về không phải PDF: {snippet[:120]}")
    return data


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    s = _session()
    referer = BASE + "/tra-cuu/"
    r0 = s.get(referer, timeout=60)
    if r0.status_code != 200:
        raise ProviderError(f"Không mở được trang tra cứu MISA (HTTP {r0.status_code})")

    code = find_code(xml_text)
    ext = ""
    if code:
        res = _post_json(s, "/tra-cuu/GetInvoiceDataByTransactionID", {"transactionID": code}, referer)
        if res.get("success"):
            ext = str(res.get("customData") or "")
        else:
            log(f"MISA: mã tra cứu {code} không hợp lệ ({res.get('errorCode')}), thử bằng file XML...")
            code = ""
    if not code:
        body = xml_text.lstrip("﻿")
        res = _post_json(s, "/tra-cuu/GetXMLData", {"invData": body}, referer)
        if not res.get("success"):
            err = res.get("errorCode") or "không rõ"
            msg = {"SignatureEmpty": "XML không có chữ ký số", "InvalidSignature": "chữ ký số không hợp lệ",
                   "InvoiceDataEmpty": "XML rỗng", "INVOICENOTEXIST": "không có hóa đơn này trên MISA",
                   "InvalidTransactionID": "MISA không nhận diện được hóa đơn"}.get(err, err)
            raise ProviderError(f"MISA từ chối XML: {msg}")
        try:
            info = json.loads(res.get("data") or "{}")
        except ValueError:
            info = {}
        code = str(info.get("txtCodeValue") or "").strip()
        ext = str(res.get("customData") or "")
        if not code:
            raise ProviderError("MISA không trả mã tra cứu cho XML này")
        log(f"MISA: mã tra cứu = {code}")

    return _download(s, code, ext, referer)
