"""MY SOFTWARE public invoice downloads, using the portal's reference code."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

from . import ProviderError
from . import _common as C

NAME = "MY SOFTWARE (myinvoice)"
PORTAL = "https://tracuu.myinvoice.vn"
API = PORTAL + "/erp/rest/s1/iam-entry/invoices/"


def valid_code(value):
    value = str(value or "").strip()
    return value if re.fullmatch(r"[0-9a-fA-F]{16}", value) else ""


def email_code(body):
    text = html.unescape(re.sub(r"<[^>]+>", " ", body or ""))
    match = re.search(r"(?:nhập mã|mã tra cứu(?: hóa đơn)?)\s*:\s*([0-9a-fA-F]{16})(?![0-9a-zA-Z])", text, re.I)
    return match.group(1) if match else ""


def find_code(xml_text, inv):
    for value in (inv.get("_ma_tra_cuu"), inv.get("_code"),
                  (inv.get("_gmail_lookup") or {}).get("ma_tra_cuu")):
        if valid_code(value):
            return valid_code(value)
    for field in ("MaTraCuu", "Mã tra cứu", "MTCuu"):
        value = valid_code(C.ttkhac(xml_text, field))
        if value:
            return value
    # MCCQT, XML Id and invoice number are not the issuer's reference code.
    return ""


def detect(xml_text, inv):
    return C.tcgp(xml_text) == "0108971656" or "tracuu.myinvoice.vn" in xml_text.lower()


def _identity(text):
    seller = C.seller_mst(text).replace("-", "")
    serial = C.khhdon(text).upper()
    model = C.khmshdon(text)
    if model and serial.startswith(model + "C"):
        serial = serial[len(model):]
    number = C.shdon(text).lstrip("0") or "0"
    if not seller or not serial or not C.shdon(text):
        raise ProviderError("MY SOFTWARE: XML thiếu định danh hóa đơn; chưa lưu bản gốc")
    return seller, model, serial, number


def fetch_documents(code, log, expected_xml=""):
    code = valid_code(code)
    if not code:
        raise ProviderError("MY SOFTWARE: chưa có mã tra cứu của hãng trong XML/email. Cần email hoặc PDF của đúng hóa đơn; mã CQT không thay thế mã tra cứu.")
    session = C.make_session()
    try:
        response = session.get(API + code + "/xml", timeout=45, allow_redirects=False)
        if response.status_code != 200:
            raise ProviderError(f"MY SOFTWARE: tải XML hãng thất bại (HTTP {response.status_code})")
        xml = response.content
        text = xml.decode("utf-8-sig")
        ET.fromstring(text)
        identity = _identity(text)
        if expected_xml and identity != _identity(expected_xml):
            raise ProviderError("MY SOFTWARE: mã tra cứu trả về hóa đơn khác MST/ký hiệu/số; không lưu PDF")
        response = session.get(API + code + "/pdf", timeout=60, allow_redirects=False)
        if response.status_code != 200 or not response.content.lstrip().startswith(b"%PDF-"):
            raise ProviderError(f"MY SOFTWARE: hãng chưa trả file PDF hợp lệ (HTTP {response.status_code})")
        log("MY SOFTWARE: đã tải XML hãng và PDF gốc")
        return xml, response.content
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError("MY SOFTWARE: không đọc được chứng từ từ hãng") from exc
    finally:
        session.close()


def fetch_pdf(xml_text, inv, log, solver=None):
    return fetch_documents(find_code(xml_text, inv), log, xml_text)[1]
