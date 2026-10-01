# -*- coding: utf-8 -*-
"""
providers/htinvoice.py - Tải PDF gốc qua HTInvoice (laphoadon.htinvoice.vn).
Ví dụ: CÔNG TY TNHH IN ẤN MAY MẶC THỜI TRANG NTP (MSTTCGP 0315638251).

Mã tra cứu NẰM TRONG XML:
    <TTKhac><TTin><TTruong>MTCuu</TTruong>...<DLieu>81F48166...</DLieu></TTin>
    <TTin><TTruong>DDTC</TTruong>...<DLieu>laphoadon.htinvoice.vn/TraCuu</DLieu></TTin>
Không cần email. Cổng tra cứu công khai (có thể có captcha).

GHI CHÚ: cổng dùng JavaScript nên module thử các endpoint ứng viên + GHI LOG để chốt sau 1
lần chạy thật (như đã làm EasyInvoice). Chưa ra -> ProviderError (đánh dấu 'cần tải tay').
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
    return _field(xml_text, "MTCuu") or _field(xml_text, "MaTraCuu")


def portal(xml_text: str) -> str:
    d = _field(xml_text, "DDTC") or "laphoadon.htinvoice.vn/TraCuu"
    return d if d.startswith("http") else "https://" + d.lstrip("/")


def detect(xml_text: str, inv: dict) -> bool:
    if C.tcgp(xml_text) == MSTTCGP:
        return True
    return "htinvoice.vn" in xml_text.lower() and bool(code(xml_text))


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    mtc = code(xml_text)
    base = portal(xml_text).split("/TraCuu")[0].rstrip("/")
    if not mtc:
        raise ProviderError("HTInvoice: không thấy mã tra cứu (MTCuu) trong XML")
    log(f"HTInvoice: mã tra cứu {mtc}, cổng {base}")
    s = C.make_session()
    # các endpoint ứng viên tải PDF theo mã tra cứu (chốt lại sau 1 lần chạy thật)
    cands = [
        f"{base}/api/tracuu/pdf?ma={mtc}",
        f"{base}/TraCuu/DownloadPdf?ma={mtc}",
        f"{base}/api/Invoice/Pdf/{mtc}",
        f"{base}/TraCuu/Pdf?code={mtc}",
    ]
    for u in cands:
        try:
            r = s.get(u, timeout=60, headers={"Accept": "application/pdf,*/*"})
        except Exception as e:  # noqa
            log(f"  {u} lỗi ({str(e)[:40]})"); continue
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            log("HTInvoice: ✓ lấy được PDF gốc.")
            return r.content
        log(f"  {u} → HTTP {r.status_code}")
    raise ProviderError(f"HTInvoice: chưa lấy được PDF qua cổng (mã {mtc}). "
                        f"Gửi Nhật ký 1 lần chạy thật để chốt đúng endpoint, hoặc tra tay tại {base}/TraCuu.")
