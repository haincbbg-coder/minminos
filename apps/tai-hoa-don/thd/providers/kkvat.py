# -*- coding: utf-8 -*-
"""
providers/kkvat.py - Tải PDF gốc qua TS24 / KKVAT (tracuuhoadon.kkvat.com.vn).
Ví dụ: CÔNG TY TNHH TM-DV THIẾT BỊ CÔNG NGHIỆP HỮU TƯ.

Mã tra cứu NẰM TRONG XML: <TTKhac><TTin><TTruong>Số bảo mật</TTruong>...<DLieu>1202609...</DLieu>
Không cần email. Cổng: https://tracuuhoadon.kkvat.com.vn (có thể có captcha).

GHI CHÚ: thử endpoint ứng viên + GHI LOG để chốt sau 1 lần chạy thật (như EasyInvoice).
"""
from __future__ import annotations

import re
from typing import Callable

from . import ProviderError
from . import _common as C

NAME = "TS24 (KKVAT)"
HOST = "https://tracuuhoadon.kkvat.com.vn"

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
    return _field(xml_text, "Số bảo mật") or _field(xml_text, "So bao mat") or _field(xml_text, "MaBaoMat")


def detect(xml_text: str, inv: dict) -> bool:
    if "kkvat" in xml_text.lower():
        return True
    return bool(code(xml_text)) and "bảo mật" in xml_text.lower()


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    c = code(xml_text)
    mst = C.seller_mst(xml_text)
    if not c:
        raise ProviderError("KKVAT: không thấy 'Số bảo mật' trong XML")
    log(f"KKVAT/TS24: số bảo mật {c}, MST {mst}, cổng {HOST}")
    s = C.make_session()
    cands = [
        f"{HOST}/api/tracuu/pdf?mst={mst}&mabaomat={c}",
        f"{HOST}/TraCuu/DownloadPdf?mst={mst}&code={c}",
        f"{HOST}/api/Invoice/Pdf?taxcode={mst}&secret={c}",
        f"{HOST}/Handler/DownloadPDF.ashx?ma={c}",
    ]
    for u in cands:
        try:
            r = s.get(u, timeout=60, headers={"Accept": "application/pdf,*/*"})
        except Exception as e:  # noqa
            log(f"  {u} lỗi ({str(e)[:40]})"); continue
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            log("KKVAT: ✓ lấy được PDF gốc.")
            return r.content
        log(f"  {u} → HTTP {r.status_code}")
    raise ProviderError(f"KKVAT/TS24: chưa lấy được PDF qua cổng (mã {c}). "
                        f"Gửi Nhật ký 1 lần chạy thật để chốt endpoint, hoặc tra tay tại {HOST}.")
