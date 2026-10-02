# -*- coding: utf-8 -*-
"""
providers/bkav.py - Tải PDF GỐC hóa đơn phát hành qua BKAV eHoadon.

Cổng tra cứu: https://tchd.ehoadon.vn/TCHD?MTC=<Mã tra cứu>   (ASP.NET WebForms)
Bảo vệ bằng reCAPTCHA v2 (site key: 6LddSB4UAAAAAO2Ig9ZHpTMxue0dDpnodo3OYjUH).

Luồng (đã dò cấu trúc trực tiếp 2026-09):
  1) GET  /TCHD?MTC=<MTC>  -> lấy cookie phiên + __VIEWSTATE, __VIEWSTATEGENERATOR...
  2) Giải reCAPTCHA v2 qua 2Captcha  -> token g-recaptcha-response
  3) POST /TCHD?MTC=<MTC>  (postback WebForms) kèm:
        ctl00$bodySearch$lookupBase$txtInvoiceCode = <MTC>
        ctl00$bodySearch$lookupBase$Button1        = "Tra cứu"
        g-recaptcha-response                        = <token>
        (+ các __VIEWSTATE... lấy ở bước 1, hdfIsXML=false, hdfShowBanner=1)
     -> trang kết quả có nút tải: DownloadFile(filePath, BFType)
  4) GET  /DownloadFile?FilePath=<path>&BFType=<n>  -> PDF gốc (BFType PDF).

Mã tra cứu (MTC) lấy từ XML (<TTKhac>) nếu có, hoặc từ email (quét Gmail).
BKAV MSTTCGP = 0101360697.
"""
from __future__ import annotations

import html as _htmllib
import re
from typing import Callable
from urllib.parse import quote

from . import ProviderError
from . import _common as C

NAME = "BKAV eHoadon"
HOST = "https://tchd.ehoadon.vn"
SEARCH_PATH = "/TCHD"
RECAPTCHA_SITEKEY = "6LddSB4UAAAAAO2Ig9ZHpTMxue0dDpnodo3OYjUH"
MSTTCGP_BKAV = "0101360697"

# Tên MTC hay gặp trong <TTKhac> của XML
_CODE_FIELDS = ("MTC", "MaTraCuu", "MaTracuu", "Matracuu", "MTCuu", "LookupCode", "MaBaoMat")
_RE_HIDDEN = re.compile(r'<input[^>]+type="hidden"[^>]*>', re.I)
_RE_NAME = re.compile(r'name="([^"]+)"', re.I)
_RE_VALUE = re.compile(r'value="([^"]*)"', re.I)
# Nút tải trên trang kết quả: DownloadFile('<path>', '<BFType>')  và/hoặc /DownloadFile?FilePath=..&BFType=..
_RE_DLFUNC = re.compile(r"DownloadFile\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]?([A-Za-z0-9]+)", re.I)
_RE_DLURL = re.compile(r"/DownloadFile\?FilePath=([^\"'&]+)&BFType=([A-Za-z0-9]+)", re.I)
_RE_MTC_URL = re.compile(r"tracuu\.ehoadon\.vn/([A-Za-z0-9]{6,})", re.I)


def detect(xml_text: str, inv: dict) -> bool:
    if C.tcgp(xml_text) == MSTTCGP_BKAV:
        return True
    low = xml_text.lower()
    return ("ehoadon.vn" in low) or ("bkav" in low)


def find_code(xml_text: str, inv: dict) -> str:
    if inv.get("_ma_tra_cuu"):
        return str(inv["_ma_tra_cuu"]).strip()
    for f in _CODE_FIELDS:
        v = C.ttkhac(xml_text, f)
        if v and v.strip():
            return v.strip()
    m = _RE_MTC_URL.search(xml_text)
    if m:
        return m.group(1)
    return (inv.get("_bkav_mtc") or inv.get("_mtc") or inv.get("_code") or "").strip()


def _hidden_fields(html_text: str) -> dict:
    out = {}
    for m in _RE_HIDDEN.finditer(html_text):
        tag = m.group(0)
        nm = _RE_NAME.search(tag)
        if not nm:
            continue
        vl = _RE_VALUE.search(tag)
        out[nm.group(1)] = _htmllib.unescape(vl.group(1)) if vl else ""
    return out


def _try_download(s, path: str, bftype: str, log) -> bytes | None:
    url = f"{HOST}/DownloadFile?FilePath={quote(path, safe='')}&BFType={bftype}"
    try:
        r = s.get(url, timeout=120, headers={"Referer": HOST + SEARCH_PATH})
    except Exception:
        return None
    c = r.content
    if r.status_code == 200 and c.lstrip().startswith(b"%PDF"):
        return c
    if r.status_code == 200 and c[:2] == b"PK":   # ZIP -> lấy PDF trong đó
        import io, zipfile
        try:
            zf = zipfile.ZipFile(io.BytesIO(c))
            for n in zf.namelist():
                if n.lower().endswith(".pdf"):
                    d = zf.read(n)
                    if d.lstrip().startswith(b"%PDF"):
                        return d
        except Exception:
            pass
    return None


def _direct_invoice(s, body: str, log):
    """Follow the invoice opened by the portal, then its own PDF postback."""
    import time
    match = re.search(r"ViewInvoice\(\s*['\"]([0-9a-fA-F-]{36})['\"]", body)
    if not match:
        match = re.search(r"/Lookup\?InvoiceGUID=([0-9a-fA-F-]{36})", body)
    if not match:
        return None
    url = HOST + "/Lookup?InvoiceGUID=" + match.group(1) + "&ViewATF="
    r = s.get(url, timeout=60, headers={"Referer": HOST + SEARCH_PATH})
    if r.status_code != 200:
        return None
    page = r.text
    # Older templates already have a PDF and expose DownloadFile inside Lookup.
    # Newer templates generate it through the WebForms postback below.
    for match in _RE_DLFUNC.finditer(_htmllib.unescape(page)):
        if not match.group(1).lower().endswith(".pdf"):
            continue
        pdf = _try_download(s, match.group(1), match.group(2), log)
        if pdf:
            log("BKAV: đã tải PDF gốc có sẵn trong trang hoá đơn.")
            return pdf
    targets = re.findall(r"__doPostBack\(['\"]([^'\"]*(?:lbtnDownloadHtmlAsPdf|lbtDownloadAsPdf))['\"]", _htmllib.unescape(page))
    for target in dict.fromkeys(targets):
        fields = _hidden_fields(page)
        fields.update({"__EVENTTARGET": target, "__EVENTARGUMENT": "",
                       "UcHtmlPdfToolbar$txtLastTimeDownload_Cur": str(int(time.time()*10000000)+621355968000000000)})
        result = s.post(url, data=fields, timeout=120, headers={"Referer": url})
        if result.status_code == 200 and result.content.lstrip().startswith(b"%PDF-"):
            log("BKAV: đã tải PDF gốc từ hoá đơn mở trực tiếp.")
            return result.content
    return None


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    mtc = find_code(xml_text, inv)
    if not mtc:
        # TCT XML can omit the lookup code but retain BKAV's invoice UUID.
        # Verify the issuer XML before accepting any PDF reached through that UUID.
        import xml.etree.ElementTree as ET
        from .smartsign import identity
        try:
            root = ET.fromstring(xml_text)
            guid = next((e.get("Id", "") for e in root.iter()
                         if e.tag.split("}")[-1] == "DLHDon"), "")
        except ET.ParseError:
            guid = ""
        if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", guid):
            with C.make_session() as session:
                lookup = HOST + "/Lookup?InvoiceGUID=" + guid + "&ViewATF="
                page = session.get(lookup, timeout=60)
                if page.status_code == 200 and "LinkDownXML" in page.text:
                    fields = _hidden_fields(page.text)
                    fields.update({"__EVENTTARGET": "LinkDownXML", "__EVENTARGUMENT": ""})
                    source = session.post(lookup, data=fields, timeout=60)
                    if source.status_code != 200 or identity(source.content.decode("utf-8-sig")) != identity(xml_text):
                        raise ProviderError("BKAV: XML hãng không khớp định danh hóa đơn")
                    pdf = _direct_invoice(session, "ViewInvoice('" + guid + "')", log)
                    if pdf:
                        inv["_manual_url"] = lookup
                        return pdf
        raise ProviderError("Không có Mã tra cứu (MTC) của BKAV trong XML - cần lấy MTC "
                            "từ email (quét Gmail).")
    url = f"{HOST}{SEARCH_PATH}?MTC={quote(mtc)}"
    s = C.make_session()
    log(f"BKAV: mở cổng tra cứu MTC {mtc}...")
    try:
        r0 = s.get(url, timeout=60)
        page0 = r0.text if hasattr(r0, "text") else r0.content.decode("utf-8", "ignore")
    except Exception as e:  # noqa
        raise ProviderError(f"BKAV không mở được cổng ({str(e)[:80]})")
    direct = _direct_invoice(s, page0, log)
    if direct:
        return direct
    if not solver or not hasattr(solver, "recaptcha_v2"):
        raise ProviderError("BKAV chưa mở được hoá đơn trực tiếp. Kiểm tra mã tra cứu hoặc bật API captcha nếu trang yêu cầu.")
    hidden = _hidden_fields(page0)
    log("BKAV: giải reCAPTCHA v2 qua dịch vụ (có thể mất 15-40 giây)...")
    try:
        token = solver.recaptcha_v2(RECAPTCHA_SITEKEY, url)
    except Exception as e:  # noqa
        raise ProviderError(f"Giải reCAPTCHA thất bại ({str(e)[:80]})")
    if not token:
        raise ProviderError("Dịch vụ trả token reCAPTCHA rỗng (kiểm tra API key/số dư).")
    log("BKAV: đã có token reCAPTCHA, gửi tra cứu...")

    data = dict(hidden)  # giữ nguyên __VIEWSTATE... lấy từ trang
    data.update({
        "__LASTFOCUS": "",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "ctl00$bodySearch$lookupBase$txtInvoiceCode": mtc,
        "ctl00$bodySearch$lookupBase$hdfFileLastModifiedDate": "",
        "ctl00$bodySearch$lookupBase$hdfIsXML": "false",
        "ctl00$hdfShowBanner": "1",
        "ctl00$bodySearch$lookupBase$Button1": "Tra cứu",
        "g-recaptcha-response": token,
    })
    try:
        r = s.post(url, data=data, timeout=120,
                   headers={"Referer": url, "Content-Type": "application/x-www-form-urlencoded"})
        body = r.text if hasattr(r, "text") else r.content.decode("utf-8", "ignore")
    except Exception as e:  # noqa
        raise ProviderError(f"BKAV tra cứu lỗi ({str(e)[:80]})")
    log(f"BKAV: tra cứu trả HTTP {getattr(r,'status_code','?')}, trang {len(body)} ký tự.")

    direct = _direct_invoice(s, body, log)
    if direct:
        return direct

    # gom mọi (filePath, BFType) trên trang kết quả
    cands = []
    for m in _RE_DLFUNC.finditer(body):
        cands.append((_htmllib.unescape(m.group(1)), m.group(2)))
    for m in _RE_DLURL.finditer(body):
        cands.append((_htmllib.unescape(m.group(1)), m.group(2)))
    # bỏ trùng, ưu tiên cái có vẻ là PDF (BFType nhỏ) trước
    seen, uniq = set(), []
    for p, t in cands:
        k = (p, t)
        if k not in seen:
            seen.add(k); uniq.append((p, t))
    if not uniq:
        low = body.lower()
        if "recaptcha" in low or "xác thực" in low or "không hợp lệ" in low:
            raise ProviderError("BKAV: có thể reCAPTCHA/MTC chưa qua - trang không có nút tải. "
                                "Xem lại MTC hoặc thử lại.")
        raise ProviderError("BKAV: tra cứu xong nhưng không thấy nút tải file (trang đổi cấu trúc?).")
    log(f"BKAV: thấy {len(uniq)} nút tải, đang lấy PDF...")
    for path, bftype in uniq:
        pdf = _try_download(s, path, bftype, log)
        if pdf:
            log("BKAV: ✓ lấy được PDF gốc.")
            return pdf
    # thử các BFType phổ biến nếu BFType kèm theo không ra PDF
    for path, _ in uniq:
        for bft in ("1", "0", "2", "3"):
            pdf = _try_download(s, path, bft, log)
            if pdf:
                log(f"BKAV: ✓ lấy được PDF gốc (BFType={bft}).")
                return pdf
    raise ProviderError("BKAV: có nút tải nhưng máy chủ chưa trả PDF (gửi log để kiểm tra thêm).")
