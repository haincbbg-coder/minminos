# -*- coding: utf-8 -*-
"""
providers/xmllink.py - Tải PDF gốc từ ĐƯỜNG DẪN NHÚNG SẴN trong XML.

Nhiều nhà cung cấp (J&T Express/Thuận Phong, một số nền tảng khác) nhét thẳng link tải
bản PDF gốc vào XML - thường ở <TTKhac> dưới các trường External1/External2/External3,
LinkTraCuu, PdfUrl, DownloadUrl... Chỉ cần đọc link đó rồi tải về, KHÔNG cần captcha,
KHÔNG cần mã tra cứu.

Đây là module dự phòng: dùng link trong XML khi chưa nhận diện được hãng hoặc khi
cách tải riêng của hãng thất bại.
"""
from __future__ import annotations

import html
import re
import base64
import io
import ipaddress
import json
import socket
import zipfile
from urllib.parse import urlsplit, urljoin
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


MAX_BYTES = 25 * 1024 * 1024


def _public_url(url: str):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ProviderError("Link tải phải là HTTPS công khai, cổng 443")
    addresses = socket.getaddrinfo(p.hostname, 443, proto=socket.IPPROTO_TCP)
    if not addresses:
        raise ProviderError("Không phân giải được địa chỉ tải")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        ip = getattr(ip, "ipv4_mapped", None) or ip
        if not ip.is_global or ip.is_multicast:
            raise ProviderError("Không tải link trỏ vào mạng nội bộ")


def _pdf_payload(data: bytes, depth=0) -> Optional[bytes]:
    """Nhận PDF hoặc gói chứa đúng một PDF; không đoán chọn giữa nhiều hoá đơn."""
    if len(data) > MAX_BYTES or depth > 3:
        return None
    if data.lstrip().startswith(b"%PDF-"):
        return data
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                entries = [x for x in z.infolist() if x.filename.lower().endswith(".pdf") and not x.is_dir()]
                if len(entries) == 1 and entries[0].file_size <= MAX_BYTES:
                    return _pdf_payload(z.read(entries[0]), depth + 1)
        except (ValueError, RuntimeError, zipfile.BadZipFile):
            return None
        return None
    try:
        obj = json.loads(data)
    except (ValueError, UnicodeError):
        return None
    def unpack(value, level):
        if level > 3:
            return None
        if isinstance(value, str):
            raw = value.split(",", 1)[1] if value.startswith("data:application/pdf;base64,") else value
            try:
                return _pdf_payload(base64.b64decode(raw, validate=True), depth + 1)
            except (ValueError, TypeError):
                return None
        if isinstance(value, dict):
            found = [unpack(v, level + 1) for k, v in value.items()
                     if k.lower() in ("data", "pdf", "file", "content", "base64", "filecontent", "filedata", "result")]
            found = [v for v in found if v]
            return found[0] if len(found) == 1 else None
        return None
    return unpack(obj, 0)


def _try_download(s, url: str, log: Callable[[str], None]) -> Optional[bytes]:
    try:
        for _ in range(4):
            _public_url(url)
            with s.get(url, timeout=(10, 30), allow_redirects=False, stream=True,
                       headers={"Accept": "application/pdf,application/zip,application/json"}) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, r.headers.get("Location", ""))
                    continue
                if r.status_code != 200:
                    log(f"link trả HTTP {r.status_code}")
                    return None
                chunks, size = [], 0
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ProviderError("File tải vượt giới hạn 25 MB")
                    chunks.append(chunk)
                return _pdf_payload(b"".join(chunks))
    except Exception as e:
        log(f"Link chưa tải được ({type(e).__name__})")
    return None


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    urls = _candidate_urls(xml_text)
    if not urls:
        raise ProviderError("Không thấy link tải trong XML")
    # Phiên riêng, không mang token/cookie cổng thuế sang URL trong XML.
    import requests
    with requests.Session() as s:
        s.trust_env = False
        s.headers["User-Agent"] = C.UA
        tried = 0
        for u in urls:
            low = u.lower()
            if not any(k in low for k in ("pdf", "download", "dowload", "query", "tracuu",
                                          "lookup", "invoice", "hoadon", "einvoice")):
                continue
            tried += 1
            log(f"thử link tải trong XML tại {urlsplit(u).hostname}")
            pdf = _try_download(s, u, log)
            if pdf:
                log("✓ tải được PDF gốc từ link trong XML.")
                return pdf
            if tried >= 6:
                break
    raise ProviderError("Có link trong XML nhưng tải về không phải PDF (link hết hạn/chặn IP?) - "
                        "thử tải tay bằng link trong email nhà cung cấp.")
