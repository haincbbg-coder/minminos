# -*- coding: utf-8 -*-
"""
providers/xmllink.py - Tải PDF gốc từ ĐƯỜNG DẪN NHÚNG SẴN trong XML.

Nhiều nhà cung cấp (J&T Express/Thuận Phong, một số nền tảng khác) nhét thẳng link tải
bản PDF gốc vào XML - thường ở <TTKhac> dưới các trường External1/External2/External3,
LinkTraCuu, PdfUrl, DownloadUrl... Chỉ cần đọc link đó rồi tải về, KHÔNG cần captcha,
KHÔNG cần mã tra cứu.

Đây là module DỰ PHÒNG, đặt CUỐI danh sách: chỉ dùng khi không hãng nào (MISA/Sapo/
EasyInvoice/BKAV) nhận, nhưng trong XML có sẵn link PDF.
"""
from __future__ import annotations

import html
import re
from typing import Callable, Optional

from . import ProviderError
from . import _common as C

NAME = "Link trong XML"

# Bắt mọi URL http/https trong XML (đã gỡ &amp;). Ưu tiên link có 'pdf'/'download'/'query'.
_RE_URL = re.compile(r"https?://[^\s\"'<>]+", re.I)


def _urls(xml_text: str) -> list[str]:
    txt = html.unescape(xml_text)
    seen, out = set(), []
    for m in _RE_URL.finditer(txt):
        u = m.group(0).rstrip(".,);]")
        # bỏ các link hạ tầng chữ ký số / cơ quan thuế (không phải link tải hóa đơn)
        low = u.lower()
        if any(b in low for b in ("w3.org", "gov.vn/pki", "rootca", "ocsp", "crl.", "/crt/",
                                  "ca.gov.vn", "bkavca", "safecert.com", "nc-ca.vn", "xmldsig")):
            continue
        if u not in seen:
            seen.add(u); out.append(u)
    # xếp ưu tiên: link giống link tải PDF lên trước
    def score(u: str) -> int:
        low = u.lower()
        s = 0
        if "pdf" in low: s -= 4
        if "download" in low or "/dowload" in low: s -= 3
        if "query" in low or "tracuu" in low or "lookup" in low: s -= 2
        if low.endswith(".pdf"): s -= 2
        return s
    out.sort(key=score)
    return out


def _candidate_urls(xml_text: str) -> list[str]:
    """Ưu tiên đọc từ các trường External/Link/Pdf trong TTKhac trước, rồi mới quét toàn bộ."""
    prefer = []
    for f in ("External3", "External2", "External1", "LinkTraCuu", "LinkHoaDon",
              "PdfUrl", "PdfLink", "DownloadUrl", "UrlPdf", "Url", "Link"):
        v = C.ttkhac(xml_text, f)
        if v and v.lower().startswith("http"):
            prefer.append(html.unescape(v).strip())
    # gộp với toàn bộ URL tìm được, giữ thứ tự ưu tiên, bỏ trùng
    all_urls = prefer + _urls(xml_text)
    seen, out = set(), []
    for u in all_urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def detect(xml_text: str, inv: dict) -> bool:
    """Có ít nhất 1 URL có khả năng là link tải hóa đơn (pdf/download/query...)."""
    for u in _candidate_urls(xml_text):
        low = u.lower()
        if any(k in low for k in ("pdf", "download", "dowload", "query", "tracuu",
                                  "lookup", "invoice", "hoadon", "einvoice")):
            return True
    return False


def _try_download(s, url: str, log: Callable[[str], None]) -> Optional[bytes]:
    try:
        r = s.get(url, timeout=90, headers={"Accept": "application/pdf,*/*"})
    except Exception as e:  # noqa
        log(f"link lỗi ({str(e)[:50]})"); return None
    if r.status_code != 200:
        log(f"link trả HTTP {r.status_code}"); return None
    data = r.content or b""
    if data[:4] == b"%PDF":
        return data
    # có nơi trả JSON chứa base64 / hoặc redirect tới file - thử bóc base64 PDF
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "pdf" in ctype and data[:4] != b"%PDF":
        return data if data else None
    return None


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    urls = _candidate_urls(xml_text)
    if not urls:
        raise ProviderError("Không thấy link tải trong XML")
    s = C.make_session()
    tried = 0
    for u in urls:
        low = u.lower()
        if not any(k in low for k in ("pdf", "download", "dowload", "query", "tracuu",
                                      "lookup", "invoice", "hoadon", "einvoice")):
            continue
        tried += 1
        log(f"thử link tải trong XML: {u[:90]}")
        pdf = _try_download(s, u, log)
        if pdf:
            log("✓ tải được PDF gốc từ link trong XML.")
            return pdf
        if tried >= 6:
            break
    raise ProviderError("Có link trong XML nhưng tải về không phải PDF (link hết hạn/chặn IP?) - "
                        "thử tải tay bằng link trong email nhà cung cấp.")
