# -*- coding: utf-8 -*-
"""
gmail_scan.py - Quét hộp thư Gmail, gom hóa đơn điện tử nhà cung cấp gửi qua email.

Kết nối bằng IMAP + MẬT KHẨU ỨNG DỤNG (App Password) của Google - KHÔNG cần đăng ký
Google Cloud, không chờ Google duyệt. Khách bật xác minh 2 bước rồi tạo App Password 16
ký tự (myaccount.google.com/apppasswords) và dán vào tool.

Với mỗi email hóa đơn:
  1) Nếu có tệp đính kèm .xml / .pdf  -> lấy trực tiếp (nhanh nhất, chắc chắn nhất).
  2) Nếu chỉ có LINK/MÃ tra cứu       -> nhận diện nhà cung cấp từ email + link rồi
     gọi providers/ để tải PDF gốc (MISA, Sapo, EasyInvoice...).
  3) Hãng chặn captcha (BKAV...)       -> đánh dấu 'cần tải tay' (bán tự động), không bỏ sót.

Trả về danh sách bản ghi để hiển thị / lưu / xuất Excel.
"""
from __future__ import annotations

import email
import imaplib
import re
import io
import zipfile
from pathlib import PurePosixPath
from email.header import decode_header
from typing import Callable, Optional

from . import providers

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Người gửi -> nhà cung cấp giải pháp (để nhận diện nhanh, không phụ thuộc nội dung).
# Danh sách MỞ RỘNG: gom hầu hết nhà phát hành HĐĐT phổ biến ở VN -> mail nào từ các
# domain này đều được nhận là hóa đơn (dù có cào được bản gốc từ link hay không).
SENDER_PROVIDER = {
    # MISA
    "meinvoice.vn": "misa", "misa.com.vn": "misa", "misa.vn": "misa",
    # Sapo
    "sapo.vn": "sapo",
    # EasyInvoice / SoftDreams
    "easyinvoice.vn": "easyinvoice", "softdreams.vn": "easyinvoice", "easyinvoice.com.vn": "easyinvoice",
    # BKAV eHoadon (captcha)
    "ehoadon.vn": "bkav", "bkav.com": "bkav", "bkav.com.vn": "bkav",
    # TS24 / KKVAT (mã bảo mật riêng)
    "kkvat.com.vn": "kkvat", "ts24.com.vn": "kkvat",
    # Viettel (captcha trượt)
    "vinvoice.viettel.vn": "viettel", "viettel.vn": "viettel", "sinvoice.viettel.vn": "viettel",
    # EFY iHoaDon (captcha)
    "efy.com.vn": "efy", "ihoadon.vn": "efy", "efy.vn": "efy",
    # HTInvoice
    "htinvoice.vn": "htinvoice", "htinvoice.com.vn": "htinvoice",
    # VNPT
    "vnpt-invoice.com.vn": "vnpt", "vnpt.vn": "vnpt", "invoice.vnpt.vn": "vnpt",
    # FPT
    "fpt.com.vn": "fpt", "einvoice.fpt.com.vn": "fpt",
    # M-Invoice / Mobifone / Wininvoice / Hilo / CyberLotus / Vin-invoice / Thaison
    "minvoice.com.vn": "minvoice", "mobifoneinvoice.vn": "mobifone", "wininvoice.vn": "wininvoice",
    "hilo.com.vn": "hilo", "cyberlotus.com": "cyberlotus", "cyberbill.vn": "cyberlotus",
    "vin-invoice.com": "vininvoice", "vietinvoice.vn": "vietinvoice",
    "fast.com.vn": "fast",
    # khác
    "asiainvoice.vn": "asiainvoice", "pancake.vn": "pancake",
}

# email/tiêu đề gợi ý là hóa đơn (lọc bớt trước khi tải nội dung)
INVOICE_HINTS = ["hóa đơn", "hoá đơn", "hoa don", "e-invoice", "einvoice", "invoice",
                 "hđđt", "hddt", "hđ gtgt", "gtgt", "vat", "mã tra cứu", "ma tra cuu"]

# Dấu hiệu KHÔNG phải hóa đơn (hợp đồng, báo giá, biên bản...) -> KHÔNG nhận nhầm.
# Chỉ loại khi email KHÔNG có XML hóa đơn thật và KHÔNG có dấu hiệu hóa đơn rõ ràng.
CONTRACT_HINTS = ["hợp đồng", "hop dong", "phụ lục", "phu luc", "biên bản", "bien ban",
                  "báo giá", "bao gia", "quotation", "contract", "agreement", "đối soát",
                  "doi soat", "sao kê", "sao ke", "thanh lý", "thanh ly", "phiếu thu", "phieu thu"]

# Tên tệp đính kèm là hợp đồng/không phải hóa đơn -> bỏ qua tệp đó
_ATT_SKIP = ("hopdong", "hop_dong", "hop-dong", "phuluc", "phu_luc", "bienban", "bien_ban",
             "baogia", "bao_gia", "quotation", "contract", "thanhly", "thanh_ly")

# Nhận DẠNG nội dung XML đúng là HÓA ĐƠN điện tử (theo chuẩn TT78/QĐ1450 và bản cũ)
_RE_INV_XML = re.compile(r"<\s*(?:\w+:)?(TDiep|HDon|DLHDon|TTChung|NBan|NNMua|NMua|Invoice|inv:Invoice)\b", re.I)

# Nhà cung cấp chặn captcha -> chỉ tải tay (bán tự động)
PORTAL_CAPTCHA = {"bkav", "kkvat", "viettel", "efy", "htinvoice", "vnpt", "fpt", "minvoice",
                  "mobifone", "wininvoice", "hilo", "cyberlotus", "vininvoice", "vietinvoice"}


def _is_invoice_xml(blob: bytes) -> bool:
    """True nếu nội dung XML đúng là hóa đơn điện tử (không nhầm XML khác/hợp đồng)."""
    if not blob:
        return False
    try:
        head = blob[:6000].decode("utf-8", "ignore")
    except Exception:  # noqa
        return False
    return bool(_RE_INV_XML.search(head))


def _att_is_contract(fn: str) -> bool:
    low = re.sub(r"[\s\-_.]", "", (fn or "").lower())
    return any(k.replace("_", "").replace("-", "") in low for k in _ATT_SKIP)

_RE_EASY_TOKEN = re.compile(r"(?:ViewFromEmail|DownloadInvPdf)\?token=([A-Za-z0-9%+/=_\-]+)", re.I)
_RE_EASY_HOST = re.compile(r"https?://([a-z0-9.\-]*easyinvoice\.vn)", re.I)
_RE_MISA_SC = re.compile(r"[?&]sc=([A-Za-z0-9]+)", re.I)
_RE_SAPO_QR = re.compile(r"[?&]qrcode=([A-Za-z0-9]+)", re.I)
_RE_BKAV_MTC = re.compile(r"(?:MTC|Mã tra cứu|Ma tra cuu)\s*(?:là|la)?\s*[:*]?\s*\**([A-Za-z0-9]{6,})", re.I)
_RE_CODE_GENERIC = re.compile(r"(?:Mã tra cứu|Ma tra cuu|Mã số bí mật|Mã bảo mật)\s*(?:là|la)?\s*[:*]?\s*\**([A-Za-z0-9]{6,})", re.I)
# BKAV eHoadon: link tra cứu có 2 dạng
#   cũ:  http://tracuu.ehoadon.vn/<MTC>
#   mới: https://tchd.ehoadon.vn/TCHD?MTC=<MTC>   (chính là cổng tải, có reCAPTCHA)
_RE_EHOADON_URL = re.compile(r"(?:https?://)?tracuu\.ehoadon\.vn/([A-Za-z0-9]{6,})", re.I)
_RE_TCHD_URL = re.compile(r"(?:https?://)?tchd\.ehoadon\.vn/TCHD\?MTC=([A-Za-z0-9]{6,})", re.I)
# MTC nằm trong query của bất kỳ link nào: ...?MTC=XXX / ...&MTC=XXX
_RE_MTC_PARAM = re.compile(r"[?&]MTC=([A-Za-z0-9]{6,})", re.I)
# Bất kỳ URL nào + mã tra cứu chung trong query (cho nhà cung cấp chưa có bộ đọc riêng)
_RE_ANY_URL = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)
_RE_LOOKUP_PARM = re.compile(r"[?&](?:MTC|code|ma|makey|key|token|id|fkey|reservationCode|"
                             r"secureKey|vSecureKey|invoiceCode|tracuu)=([A-Za-z0-9%._\-]{4,})", re.I)
# từ khóa cho biết URL là trang TRA CỨU/xem/tải hóa đơn (không phải link rác)
_LOOKUP_URL_KW = ("tracuu", "tra-cuu", "tra_cuu", "lookup", "hoadon", "einvoice", "e-invoice",
                  "invoice", "viewinvoice", "viewfromemail", "downloadinv", "tchd", "mtc=",
                  "xem-hoa-don", "hddt")
_URL_SKIP_KW = ("unsubscribe", "facebook.com", "zalo.me", "youtube.com", "google.com/maps",
                "/logo", ".png", ".jpg", ".gif", "huongdan", "signinoptions", "apppasswords",
                "phaplyhd", "equanlyhoadon", "van.ehoadon")


def _find_lookup_link(body: str) -> str:
    """Tìm URL trang tra cứu/tải hóa đơn trong email (dùng cho NCC chưa có bộ đọc riêng)."""
    for m in _RE_ANY_URL.finditer(body or ""):
        url = m.group(0).rstrip(".,);'\"")
        low = url.lower()
        if any(b in low for b in _URL_SKIP_KW):
            continue
        if any(k in low for k in _LOOKUP_URL_KW):
            return url
    return ""

# Bóc thẻ HTML -> text sạch, để các regex theo "nhãn" (Mã tra cứu là: ...) bắt đúng
# ngay cả khi mail chỉ có bản HTML và mã bị kẹp giữa <strong>/<a> ...
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"[ \t \r\f\v]+")


def _html_to_text(s: str) -> str:
    if not s:
        return ""
    import html as _h
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = _RE_TAG.sub(" ", s)
    s = _h.unescape(s)
    s = _RE_WS.sub(" ", s)
    return s
# KKVAT/TS24: link CommonBill2.jsp?...&vTaxCode=..&vSecureKey=..&vIssue=..&vNum=..
_RE_KKVAT_LINK = re.compile(r"(hoadon\.kkvat\.com\.vn[^\s\"'\)]*CommonBill2\.jsp[^\s\"'\)]*)", re.I)
_RE_KKVAT_SECURE = re.compile(r"vSecureKey=?([0-9]{8,})", re.I)
# Số hóa đơn trong tiêu đề/nội dung email (nhiều cách viết)
_RE_SO_HD = re.compile(r"(?:Hóa đơn số|Số hóa đơn|Số Hóa đơn|Số HĐ|số\s*\(No\.\)|Invoice No\.?|No\.)\s*[:\)]*\s*0*([0-9]{1,10})", re.I)
# KÝ HIỆU (6-8 ký tự, vd C26TYY) và MẪU SỐ (1 chữ số) - để khớp hóa đơn khi mail KHÔNG kèm XML
_RE_KYHIEU = re.compile(r"(?:Ký hiệu(?:\s*hóa đơn)?|Ky hieu|Serial)\s*[:\-]?\s*([0-9]?[A-Z][0-9A-Z]{4,6})", re.I)
_RE_MAUSO = re.compile(r"(?:Mẫu số|Mau so|Form)\s*[:\-]?\s*([0-9])", re.I)
# Tên người bán: 'tại <TÊN>' (BKAV) hoặc 'của (... of) <TÊN>' (KKVAT)
_RE_SELLER1 = re.compile(r"\btại\s+(CÔNG TY[^\n\.,<]{3,70}|HỘ KINH DOANH[^\n\.,<]{3,70}|DOANH NGHIỆP[^\n\.,<]{3,70})", re.I)
_RE_SELLER2 = re.compile(r"của\s*\([^)]*\)\s*\*?\s*(CÔNG TY[^\n\.,<*]{3,70}|HỘ KINH DOANH[^\n\.,<*]{3,70})", re.I)


def _dec(raw) -> str:
    if not raw:
        return ""
    out = []
    for txt, enc in decode_header(raw):
        if isinstance(txt, bytes):
            try:
                out.append(txt.decode(enc or "utf-8", "ignore"))
            except LookupError:
                out.append(txt.decode("utf-8", "ignore"))
        else:
            out.append(txt)
    return "".join(out)


def sender_domain(from_hdr: str) -> str:
    m = re.search(r"@([A-Za-z0-9.\-]+)", from_hdr or "")
    return m.group(1).lower() if m else ""


def provider_of(from_hdr: str, body: str) -> str:
    dom = sender_domain(from_hdr)
    for key, prov in SENDER_PROVIDER.items():
        if dom.endswith(key):
            return prov
    low = (body or "").lower()
    for key, prov in SENDER_PROVIDER.items():
        if key in low:
            return prov
    return ""


def extract_link_info(provider: str, body: str) -> dict:
    """Lấy mã/token tra cứu từ nội dung email cho nhà cung cấp đã biết."""
    info = {"provider": provider}
    if provider == "easyinvoice":
        from urllib.parse import quote, unquote
        mt = _RE_EASY_TOKEN.search(body)
        if mt:
            info["token"] = mt.group(1)
        hosts = []
        for m in _RE_EASY_HOST.finditer(body):
            h = "http://" + m.group(1)
            if h not in hosts:
                hosts.append(h)
        if hosts:
            info["hosts"] = hosts
        if info.get("token"):
            valid = [h.replace("http://", "https://") for h in hosts
                     if h.split("//", 1)[-1] not in ("easyinvoice.vn", "www.easyinvoice.vn")]
            host = valid[0] if valid else "https://tracuu.easyinvoice.vn"
            info["lookup_url"] = host + "/Invoice/ViewFromEmail?token=" + quote(unquote(info["token"]), safe="")
    elif provider == "fast":
        # Keep the explicitly labelled PDF link, not the first generic portal or
        # the waybill list. Tracking wrappers otherwise hide the invoice URL.
        import html
        m = re.search(r"(?:To download the PDF file|tải tệp bản thể hiện của hóa đơn điện tử).*?<a\b[^>]*href=[\"']([^\"']+)", body, re.I | re.S)
        if m:
            info["lookup_url"] = html.unescape(m.group(1))
        elif "fast.com.vn" in body and "type=3" in body:
            info["lookup_url"] = _find_lookup_link(body)
    elif provider == "sapo":
        m = _RE_SAPO_QR.search(body) or _RE_CODE_GENERIC.search(body)
        if m:
            info["code"] = m.group(1)
    elif provider == "misa":
        m = _RE_MISA_SC.search(body) or _RE_CODE_GENERIC.search(body)
        if m:
            info["code"] = m.group(1)
    elif provider == "bkav":
        # MTC nằm ở TIÊU ĐỀ ("MTC: XXXX") hoặc trong link tracuu/tchd.ehoadon.vn
        m = (_RE_BKAV_MTC.search(body) or _RE_MTC_PARAM.search(body)
             or _RE_TCHD_URL.search(body) or _RE_EHOADON_URL.search(body)
             or _RE_CODE_GENERIC.search(body))
        if m:
            info["code"] = m.group(1)
        # Link tra cứu: luôn dựng dạng cổng TẢI tchd.ehoadon.vn/TCHD?MTC=<MTC> - cổng này
        # TỰ ĐIỀN sẵn MTC từ query, người dùng chỉ cần qua reCAPTCHA là tải được ngay.
        mtc = info.get("code")
        if not mtc:
            mt = _RE_TCHD_URL.search(body) or _RE_EHOADON_URL.search(body)
            if mt:
                mtc = mt.group(1); info["code"] = mtc
        if mtc:
            info["lookup_url"] = "https://tchd.ehoadon.vn/TCHD?MTC=" + mtc
    elif provider == "kkvat":
        ml = _RE_KKVAT_LINK.search(body)
        if ml:
            info["link"] = ml.group(1)
        ms = _RE_KKVAT_SECURE.search(body)
        if ms:
            info["code"] = ms.group(1)
    elif provider in PORTAL_CAPTCHA:
        # Viettel/EFY/HTInvoice/VNPT/FPT... - lấy mã tra cứu + link trang tra cứu (nếu có)
        m = (_RE_MTC_PARAM.search(body) or _RE_BKAV_MTC.search(body)
             or _RE_LOOKUP_PARM.search(body) or _RE_CODE_GENERIC.search(body))
        if m:
            info["code"] = m.group(1)
        lk = _find_lookup_link(body)
        if lk:
            info["lookup_url"] = lk
    else:
        # Nhà cung cấp CHƯA có bộ đọc riêng -> vẫn cố lấy mã + link tra cứu CHUNG,
        # để không bỏ sót (bảng kết quả vẫn có nút mở link).
        m = (_RE_MTC_PARAM.search(body) or _RE_CODE_GENERIC.search(body)
             or _RE_LOOKUP_PARM.search(body))
        if m:
            info["code"] = m.group(1)
        lk = _find_lookup_link(body)
        if lk:
            info["lookup_url"] = lk
    if not info.get("lookup_url") and not info.get("link"):
        info["lookup_url"] = _find_lookup_link(body) or ""
    return info


def fetch_from_link(info: dict, log: Callable[[str], None]) -> Optional[bytes]:
    """Tải PDF gốc dựa vào mã/token lấy từ email. Trả về PDF hoặc None (nếu cần tải tay)."""
    prov = info.get("provider")
    if prov == "easyinvoice" and info.get("token"):
        from .providers import easyinvoice
        hosts = info.get("hosts") or [easyinvoice.HOST_DEFAULT]
        return easyinvoice.download_by_token(info["token"], log, hosts=hosts)
    if prov == "fast" and info.get("lookup_url"):
        from .providers import fast_email
        return fast_email.fetch_pdf(info["lookup_url"], log)
    if prov == "sapo" and info.get("code"):
        from .providers import sapo
        return sapo.fetch_pdf_by_code(info["code"], log)
    if prov == "misa" and info.get("code"):
        from .providers import misa
        return misa.fetch_pdf_by_code(info["code"], log)
    if prov == "bkav" and info.get("code"):
        from .providers import bkav
        return bkav.fetch_pdf("", {"_code": info["code"]}, log)
    if info.get("lookup_url") or info.get("link"):
        from .providers import xmllink
        return xmllink.fetch_pdf(info.get("lookup_url") or info["link"], {}, log)
    return None


def _body_text(msg) -> str:
    parts = []
    if msg.is_multipart():
        for p in msg.walk():
            ct = p.get_content_type()
            if ct in ("text/plain", "text/html") and "attachment" not in str(p.get("Content-Disposition", "")):
                try:
                    parts.append(p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "ignore"))
                except Exception:  # noqa
                    pass
    else:
        try:
            parts.append(msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "ignore"))
        except Exception:  # noqa
            pass
    return "\n".join(parts)


def _attachments(msg):
    """XML/PDF đính kèm trực tiếp hoặc trong ZIP, không giải nén ra đĩa."""
    out = []
    if not msg.is_multipart():
        return out
    for p in msg.walk():
        fn = _dec(p.get_filename())
        if not fn:
            continue
        low = fn.lower()
        if low.endswith((".xml", ".pdf", ".zip")):
            try:
                data = p.get_payload(decode=True)
            except Exception:  # noqa
                data = None
            if data and low.endswith(".zip"):
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        entries = z.infolist()
                        if len(entries) > 200 or sum(e.file_size for e in entries) > 25 * 1024 * 1024:
                            continue
                        for e in entries:
                            if not e.is_dir() and e.filename.lower().endswith((".xml", ".pdf")):
                                out.append((fn + "/" + e.filename, z.read(e)))
                except (ValueError, RuntimeError, zipfile.BadZipFile):
                    continue
            elif data:
                out.append((fn, data))
    return out


def _invoice_attachments(atts):
    xmls = [(n, b) for n, b in atts if n.lower().endswith(".xml")
            and not _att_is_contract(n) and _is_invoice_xml(b)]
    pdfs = [(n, b) for n, b in atts if n.lower().endswith(".pdf")
            and not _att_is_contract(n) and b.lstrip().startswith(b"%PDF-")]
    if len(xmls) == 1 and len(pdfs) == 1:
        return [(xmls[0][1], pdfs[0][1])]
    if xmls:
        pairs = []
        stems = [str(PurePosixPath(n.replace("\\", "/")).with_suffix("")).casefold() for n, _ in xmls]
        for name, xml in xmls:
            stem = str(PurePosixPath(name.replace("\\", "/")).with_suffix("")).casefold()
            matches = [pdf for n, pdf in pdfs
                       if str(PurePosixPath(n.replace("\\", "/")).with_suffix("")).casefold() == stem]
            pairs.append((xml, matches[0] if len(matches) == 1 and stems.count(stem) == 1 else None))
        return pairs
    return [(None, pdfs[0][1])] if len(pdfs) == 1 else []


class GmailScanner:
    def __init__(self, email_addr: str, app_password: str,
                 log: Optional[Callable[[str], None]] = None, solver=None):
        self.email = email_addr.strip()
        self.pw = (app_password or "").replace(" ", "")  # app password hay dán kèm dấu cách
        self.log = log or (lambda s: None)
        self.solver = solver     # để tải hãng dùng reCAPTCHA (BKAV) khi có API giải captcha
        self.imap: Optional[imaplib.IMAP4_SSL] = None

    def connect(self):
        self.log(f"Kết nối Gmail {self.email} (IMAP)...")
        try:
            self.imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=60)
        except TypeError:      # Python cũ không có tham số timeout
            self.imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        try:
            self.imap.login(self.email, self.pw)
        except imaplib.IMAP4.error as e:
            raise RuntimeError(
                "Đăng nhập Gmail thất bại. Kiểm tra: (1) đã bật Xác minh 2 bước, "
                "(2) dùng MẬT KHẨU ỨNG DỤNG 16 ký tự (không phải mật khẩu Gmail thường), "
                f"(3) IMAP đã bật trong Cài đặt Gmail. Chi tiết: {e}")
        self.imap.select("INBOX")

    def close(self):
        if self.imap:
            try:
                self.imap.logout()
            except Exception:  # noqa
                pass
            self.imap = None

    def _reconnect(self) -> bool:
        """Kết nối lại Gmail khi bị rớt (socket EOF) để quét tiếp, không mất cả mẻ."""
        try:
            try:
                if self.imap:
                    self.imap.logout()
            except Exception:  # noqa
                pass
            try:
                self.imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=60)
            except TypeError:
                self.imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            self.imap.login(self.email, self.pw)
            self.imap.select("INBOX")
            self.log("✓ Đã kết nối lại Gmail, quét tiếp.")
            return True
        except Exception as e:  # noqa
            self.log(f"Kết nối lại Gmail thất bại: {str(e)[:80]}")
            return False

    def _fetch_raw(self, mid):
        """Lấy 1 email theo UID; nếu Gmail rớt kết nối thì kết nối lại rồi thử LẠI 1 lần."""
        import socket
        for attempt in (1, 2):
            try:
                typ, data = self.imap.uid("fetch", mid, "(RFC822)")
                if typ == "OK" and data and data[0]:
                    return data[0][1]
                return None
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError, socket.error) as e:  # noqa
                if attempt == 1:
                    self.log(f"Gmail ngắt kết nối ({str(e)[:50]}) - đang kết nối lại...")
                    if not self._reconnect():
                        return None
                else:
                    return None
        return None

    def _search_uids(self, d_from: str = None, d_to: str = None, since_uid: int = None) -> list:
        """Trả DANH SÁCH UID email. Nếu since_uid -> chỉ email MỚI hơn (quét tăng dần);
        ngược lại lọc theo khoảng ngày dd-Mon-YYYY."""
        if since_uid:
            typ, data = self.imap.uid("search", None, "UID", f"{since_uid + 1}:*")
        else:
            typ, data = self.imap.uid("search", None, "SINCE", d_from, "BEFORE", d_to)
        if typ != "OK" or not data or not data[0]:
            return []
        uids = data[0].split()
        if since_uid:  # IMAP 'N:*' có thể trả cả UID cuối -> lọc lại cho chắc
            uids = [u for u in uids if int(u) > since_uid]
        return uids

    def scan(self, d_from, d_to, want_download=True, progress=None, since_uid: int = None,
             cancel_check=None, pause_gate=None, auto_captcha: bool = False) -> list:
        """d_from/d_to: datetime.date. since_uid: chỉ quét email MỚI hơn UID này (tăng dần).
        cancel_check(): trả True để DỪNG; pause_gate(): chờ khi đang tạm dừng.
        Sau khi chạy, self.last_uid = UID email lớn nhất đã quét (để lưu mốc)."""
        import datetime as dt
        self.last_uid = int(since_uid or 0)
        if since_uid:
            self.log(f"Quét TĂNG DẦN: chỉ email mới hơn lần trước (UID > {since_uid})...")
            ids = self._search_uids(since_uid=int(since_uid))
        else:
            df = d_from.strftime("%d-%b-%Y"); dtb = (d_to + dt.timedelta(days=1)).strftime("%d-%b-%Y")
            ids = self._search_uids(df, dtb)
        self.log(f"Có {len(ids)} email cần xét, đang lọc hóa đơn...")
        out = []
        total = len(ids)
        for i, mid in enumerate(reversed(ids)):  # mới nhất trước
            if pause_gate:
                pause_gate()
            if cancel_check and cancel_check():
                self.log(f"⛔ Đã dừng quét Gmail theo yêu cầu (đã xử lý {i}/{total} email).")
                break
            if progress:
                progress(i + 1, total)
            try:
                self.last_uid = max(self.last_uid, int(mid))
            except (TypeError, ValueError):
                pass
            raw = self._fetch_raw(mid)     # tự kết nối lại nếu Gmail rớt giữa chừng
            if raw is None:
                continue
            msg = email.message_from_bytes(raw)
            subject = _dec(msg.get("Subject"))
            frm = _dec(msg.get("From"))
            date = _dec(msg.get("Date"))
            low = (subject + " " + frm).lower()
            atts = _attachments(msg)
            dom = sender_domain(frm)
            # đính kèm XML ĐÚNG là hóa đơn (đã kiểm nội dung, không nhầm hợp đồng)
            has_inv_xml = any(fn.lower().endswith(".xml") and not _att_is_contract(fn) and _is_invoice_xml(blob)
                              for fn, blob in atts)
            known_prov = any(dom.endswith(k) for k in SENDER_PROVIDER)
            hint_subj = any(h in low for h in INVOICE_HINTS)
            # TIỀN LỌC rẻ (chưa tải body): có khả năng là hóa đơn thì mới đọc tiếp
            maybe = (has_inv_xml or known_prov or hint_subj
                     or any(fn.lower().endswith((".xml", ".pdf")) for fn, _ in atts))
            if not maybe:
                continue
            body = _body_text(msg)
            body_clean = _html_to_text(body)         # bản đã bóc thẻ HTML
            # gộp: TIÊU ĐỀ (MTC/số HĐ của BKAV nằm ở đây) + body thô (giữ href link) + body sạch
            text = (subject or "") + "\n" + body + "\n" + body_clean
            low_full = (subject + " " + body_clean).lower()
            hint = hint_subj or any(h in low_full for h in INVOICE_HINTS)
            looks_contract = any(c in low_full for c in CONTRACT_HINTS)
            # QUYẾT ĐỊNH cuối: nhận là HÓA ĐƠN nếu có XML hóa đơn thật, HOẶC có dấu hiệu hóa đơn,
            # HOẶC từ nhà phát hành HĐĐT đã biết mà KHÔNG phải hợp đồng/báo giá.
            is_invoice = has_inv_xml or hint or (known_prov and not looks_contract)
            if not is_invoice:
                continue
            prov = provider_of(frm, body)
            # moi tên người bán + số HĐ từ email (để đặt tên file đúng quy ước khi không có XML)
            m_so = (_RE_SO_HD.search(subject or "") or _RE_SO_HD.search(body_clean)
                    or _RE_SO_HD.search(body or ""))
            m_sel = (_RE_SELLER1.search(subject or "") or _RE_SELLER2.search(subject or "")
                     or _RE_SELLER1.search(body_clean) or _RE_SELLER2.search(body_clean))
            seller = ""
            if m_sel:
                seller = m_sel.group(1).strip()
                # cắt các cụm đuôi thừa ("đã được phát hành", "gởi hóa đơn"...)
                seller = re.split(r"\s+(?:đã|được|gởi|gửi|xin|kính|ký|MST|Mã số)\b", seller, 1, re.I)[0].strip(" *-")
            m_kh = _RE_KYHIEU.search(subject or "") or _RE_KYHIEU.search(body_clean)
            m_ms = _RE_MAUSO.search(body_clean) or _RE_MAUSO.search(subject or "")
            kyhieu = m_kh.group(1).upper() if m_kh else ""
            mauso = m_ms.group(1) if m_ms else ""
            # ký hiệu có thể kèm mẫu số đứng trước (vd '1C25MAA') -> tách ra: mẫu số 1 + 'C25MAA'
            if len(kyhieu) == 7 and kyhieu[0].isdigit():
                mauso = mauso or kyhieu[0]; kyhieu = kyhieu[1:]
            rec = {"subject": subject, "from": frm, "date": date, "provider": prov,
                   "xml": None, "pdf": None, "status": "", "needs_manual": False, "code": "",
                   "_so_hd": (m_so.group(1) if m_so else ""),
                   "_khhdon": kyhieu, "_khmshdon": mauso,
                   "_seller": seller}
            # Không lấy XML đầu và PDF đầu của email nhiều hoá đơn rồi ghép nhầm.
            pairs = _invoice_attachments(atts)
            if pairs:
                for xml, pdf in pairs:
                    item = dict(rec, xml=xml, pdf=pdf)
                    item["needs_manual"] = not bool(pdf)
                    item["status"] = "Đính kèm: " + ", ".join(
                        (["XML"] if xml else []) + (["PDF"] if pdf else []))
                    if not pdf:
                        item["status"] += "; chưa có PDF khớp duy nhất"
                    out.append(item)
                continue
            # 2) chỉ có link -> cào PDF gốc
            info = extract_link_info(prov, text)
            rec["code"] = info.get("token") or info.get("code") or ""
            # LƯU sẵn mã tra cứu + link cổng cho MỌI hóa đơn (kể cả loại cần tải tay),
            # để bảng kết quả hiện được MTC và nút "Mở link tải (điền sẵn)".
            rec["lookup_url"] = info.get("lookup_url") or info.get("link") or ""
            rec["_mtc"] = info.get("code") or ""
            if prov in PORTAL_CAPTCHA and prov != "bkav":
                # Hãng dùng captcha: CHỈ lấy nhanh mã + link ở đây (KHÔNG giải captcha trong
                # vòng đọc email - việc đó chậm 15-40s/cái làm Gmail rớt kết nối). Giải captcha
                # (nếu có API) để SANG pha riêng sau khi đọc xong, xem _auto_download_captcha().
                rec["needs_manual"] = True
                hcode = f", mã {rec['code']}" if rec["code"] else ""
                url = f" - {rec['lookup_url']}" if rec.get("lookup_url") else ""
                rec["status"] = f"Link {prov.upper()} (captcha) - cần tải tay{hcode}{url}"
                out.append(rec); continue
            if want_download and prov:
                try:
                    pdf = fetch_from_link(info, self.log)
                    if pdf:
                        rec["pdf"] = pdf
                        rec["status"] = f"Đã cào PDF gốc từ {prov}"
                    else:
                        rec["needs_manual"] = True
                        rec["status"] = "Không đủ dữ liệu để cào tự động - cần tải tay"
                except providers.ProviderError as e:
                    rec["needs_manual"] = True
                    rec["status"] = f"Cào lỗi ({e}) - cần tải tay"
                except Exception as e:  # noqa
                    rec["needs_manual"] = True
                    rec["status"] = f"Lỗi: {e}"
            else:
                rec["needs_manual"] = not prov
                rec["status"] = "Chỉ có link" + (f" ({prov})" if prov else " (chưa nhận diện NCC)")
            out.append(rec)
        # ===== ĐỌC XONG EMAIL. Giờ mới (nếu bật) tự tải hãng captcha - TÁCH khỏi IMAP để
        # không giữ kết nối Gmail treo trong lúc chờ giải captcha (tránh 'socket error: EOF').
        if auto_captcha and self.solver and want_download:
            self._auto_download_captcha(out, cancel_check, pause_gate)
        self.log(f"Xong: {len(out)} hóa đơn"
                 + (f", cần tải tay {sum(1 for r in out if r.get('needs_manual'))}." if out else "."))
        return out

    def _auto_download_captcha(self, recs, cancel_check=None, pause_gate=None):
        """Sau khi ĐÃ đọc xong email: thử tự tải bản gốc các HĐ BKAV bằng API giải captcha.
        Chạy TÁCH RIÊNG, đóng kết nối Gmail trước, nên dù chậm cũng không làm rớt mẻ quét."""
        targets = [r for r in recs if r.get("needs_manual") and r.get("provider") == "bkav"
                   and (r.get("_mtc") or r.get("code"))]
        if not targets:
            return
        self.close()   # xong việc đọc mail -> đóng IMAP, khỏi treo khi chờ captcha
        self.log(f"Thử tự tải bản gốc {len(targets)} HĐ BKAV qua API giải captcha "
                 f"(mỗi hóa đơn ~15-40 giây)...")
        try:
            from .providers import bkav
        except Exception as e:  # noqa
            self.log(f"Không nạp được module BKAV: {str(e)[:80]}"); return
        done = 0
        for k, r in enumerate(targets, 1):
            if pause_gate:
                pause_gate()
            if cancel_check and cancel_check():
                self.log("⛔ Dừng tự tải bản gốc BKAV theo yêu cầu."); break
            code = r.get("_mtc") or r.get("code")
            try:
                pdf = bkav.fetch_pdf("", {"_bkav_mtc": code}, self.log, solver=self.solver)
                if pdf and pdf.lstrip().startswith(b"%PDF"):
                    r["pdf"] = pdf
                    r["needs_manual"] = False
                    r["status"] = f"Đã tải PDF gốc BKAV (MTC {code})"
                    done += 1
            except Exception as e:  # noqa
                self.log(f"BKAV {code}: tự tải chưa được ({str(e)[:70]}) - dùng nút '🌐 Mở link tải'.")
        self.log(f"Tự tải BKAV: được {done}/{len(targets)} HĐ.")
