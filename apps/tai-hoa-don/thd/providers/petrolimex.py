"""Petrolimex public lookup: Fkey, image CAPTCHA, issuer XML and issuer rendering."""
import re
import tempfile
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

from . import ProviderError, _common as C
from .smartsign import identity

NAME = "Petrolimex"
PORTAL = "https://hoadon.petrolimex.com.vn"


def detect(xml_text, inv):
    # VNPT's issuer tax number is shared by unrelated portals. Match seller, too.
    return C.tcgp(xml_text) == "0100684378" and "PETROLIMEX" in C._tag(xml_text, "Ten", "NBan").upper()


def find_code(xml_text, inv):
    return str(inv.get("_ma_tra_cuu") or C.ttkhac(xml_text, "Fkey") or C._tag(xml_text, "Fkey")).strip()


def fetch_pdf(xml_text, inv, log, solver=None):
    from .. import exporter
    code = find_code(xml_text, inv)
    inv["_manual_url"] = PORTAL
    if not code:
        raise ProviderError("Petrolimex: thiếu Fkey trong XML hoặc mã tra cứu đã lưu")
    if solver is None:
        raise ProviderError("Petrolimex: cần cấu hình API giải CAPTCHA ảnh")
    browser = exporter.find_browser()
    if not browser:
        raise ProviderError("Petrolimex: cần cài Trình duyệt ở Công cụ để xuất mẫu PDF của hãng")
    with C.make_session() as session:
        page = session.get(PORTAL + "/SearchInvoicebycode/Index", timeout=45, allow_redirects=False)
        for attempt in range(3):
            token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page.text)
            if page.status_code != 200 or not token:
                raise ProviderError("Petrolimex: không đọc được biểu mẫu tra cứu")
            cap = session.get(PORTAL + "/Captcha/Show", timeout=30, allow_redirects=False)
            if cap.status_code != 200 or not cap.content:
                raise ProviderError("Petrolimex: không tải được CAPTCHA")
            page = session.post(PORTAL + "/SearchInvoicebycode/Index", data={
                "__RequestVerificationToken": unescape(token.group(1)), "tab":"content1",
                "strFkey":code, "captch":solver.image(cap.content), "submit":"Tìm kiếm",
            }, timeout=60, allow_redirects=False)
            match = re.search(r'href=[\"\'](/SearchInvoicebycode/DownloadXml/\?[^\"\']+)',page.text,re.I)
            if match:
                break
            if "Mã xác nhận không đúng" not in page.text:
                raise ProviderError("Petrolimex: không tìm thấy hóa đơn theo Fkey")
            log(f"Petrolimex: thử lại CAPTCHA ({attempt+1}/3)")
        else:
            raise ProviderError("Petrolimex: CAPTCHA chưa được chấp nhận sau 3 lần")
        path=unescape(match.group(1))
        source=session.get(PORTAL+path,timeout=60,allow_redirects=False)
        if source.status_code != 200 or identity(source.content.decode('utf-8-sig')) != identity(xml_text):
            raise ProviderError("Petrolimex: XML hãng không khớp định danh hóa đơn")
        # The portal's PDF button itself converts this issuer HTML to PDF in the browser.
        # Preserve literal '+' in the encrypted code just as its JavaScript POST does.
        query=urlsplit(path).query
        check=query.split('checkCode=',1)[1].split('&',1)[0]
        preview=session.post(PORTAL+'/SearchInvoicebycode/ajxPreview/',data='checkCode='+check,
                             headers={'Content-Type':'application/x-www-form-urlencoded'},timeout=60,allow_redirects=False)
        body=preview.json().get('str','') if preview.status_code==200 else ''
        if not isinstance(body,str) or not body or len(body)>5*1024*1024:
            raise ProviderError('Petrolimex: không có bản thể hiện của hãng')
        # Issuer content is untrusted. Disallow scripts, local-file and external loads.
        csp='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; font-src data:">'
        body=re.sub(r'<head[^>]*>',lambda m:m.group(0)+csp,body,count=1,flags=re.I)
        if csp not in body:
            raise ProviderError('Petrolimex: cấu trúc bản thể hiện không hợp lệ')
        with tempfile.TemporaryDirectory(prefix='petrolimex-pdf-') as tmp:
            src=Path(tmp)/'invoice.html'; dst=Path(tmp)/'invoice.pdf'
            src.write_text(body,encoding='utf-8')
            exporter.html_to_pdf(str(src),str(dst),browser)
            pdf=dst.read_bytes()
        log('Petrolimex: đối chiếu XML và xuất PDF từ bản thể hiện của chính hãng')
        return pdf
