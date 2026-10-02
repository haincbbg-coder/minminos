"""SmartSign's public ASP.NET lookup and original XML/PDF download flow."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

from . import ProviderError
from . import _common as C

NAME = "SmartSign"
PORTAL = "https://tracuuhd.smartsign.com.vn/"
PREFIX = "ctl00$ContentPlaceHolder1$"


class Form(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.fields = {}
        self.buttons = {}
        self.captcha = ""
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name"):
            kind = a.get("type", "text").lower()
            if kind in ("hidden", "text"):
                self.fields[a["name"]] = a.get("value", "")
            elif kind == "submit":
                self.buttons[a["name"]] = a.get("value", "")
        if tag == "img" and a.get("id") == "ContentPlaceHolder1_Image1":
            self.captcha = a.get("src", "")


def detect(xml_text, inv):
    return C.tcgp(xml_text) == "0309612872"


def find_code(xml_text, inv):
    return str(inv.get("_ma_tra_cuu") or inv.get("_code") or
               (inv.get("_gmail_lookup") or {}).get("ma_tra_cuu") or
               C.ttkhac(xml_text, "Matracuu") or C.ttkhac(xml_text, "MaTraCuu")).strip()


def identity(text):
    try:
        ET.fromstring(text)
    except ET.ParseError as exc:
        raise ProviderError("SmartSign: phản hồi XML hãng không hợp lệ") from exc
    seller = C.seller_mst(text).replace("-", "")
    model, serial, number = C.khmshdon(text), C.khhdon(text).upper(), C.shdon(text)
    if model and serial.startswith(model + "C"):
        serial = serial[len(model):]
    if not seller or not serial or not number:
        raise ProviderError("SmartSign: XML thiếu định danh; chưa lưu bản gốc")
    return seller, model, serial, number.lstrip("0") or "0"


def fetch_pdf(xml_text, inv, log, solver=None):
    code = find_code(xml_text, inv)
    inv["_manual_url"] = PORTAL
    if not code:
        raise ProviderError("SmartSign: chưa có mã nhận hóa đơn trong XML hoặc email")
    if solver is None:
        raise ProviderError("SmartSign: cần cấu hình dịch vụ giải CAPTCHA để tải bản gốc")
    expected = identity(xml_text)
    with C.make_session() as session:
        response = session.get(PORTAL, timeout=45, allow_redirects=False)
        if response.status_code != 200:
            raise ProviderError(f"SmartSign: mở trang tra cứu HTTP {response.status_code}")
        for attempt in range(3):
            form = Form(response.text)
            captcha_url = urljoin(PORTAL, form.captcha)
            if not form.captcha or urlsplit(captcha_url).netloc != urlsplit(PORTAL).netloc:
                raise ProviderError("SmartSign: không tìm thấy ảnh CAPTCHA trên trang tra cứu")
            image = session.get(captcha_url, timeout=30, allow_redirects=False)
            if image.status_code != 200 or not image.content:
                raise ProviderError("SmartSign: không tải được ảnh CAPTCHA")
            answer = solver.image(image.content)
            data = dict(form.fields)
            data.update({PREFIX + "txtCode":code, PREFIX + "txtCapcha":answer, "Action":"SHOW_INVOICE"})
            response = session.post(PORTAL, data=data, timeout=60, allow_redirects=False)
            if response.status_code != 200:
                raise ProviderError(f"SmartSign: tra cứu HTTP {response.status_code}")
            ready = Form(response.text)
            if PREFIX + "ButtonDownLoadXML" in ready.buttons and PREFIX + "ButtonDownLoadPDF" in ready.buttons:
                break
            if "captcha không đúng" not in response.text.lower():
                raise ProviderError("SmartSign: chưa thấy nút tải XML/PDF sau tra cứu; kiểm tra mã nhận hóa đơn")
            log(f"SmartSign: CAPTCHA bị từ chối, thử lại {attempt + 1}/3")
        else:
            raise ProviderError("SmartSign: CAPTCHA chưa được chấp nhận sau 3 lần")
        # Verify the supplier XML before accepting its PDF for the requested invoice.
        data = dict(ready.fields)
        data[PREFIX + "ButtonDownLoadXML"] = ready.buttons[PREFIX + "ButtonDownLoadXML"]
        source = session.post(PORTAL, data=data, timeout=60, allow_redirects=False)
        if source.status_code != 200 or identity(source.content.decode("utf-8-sig")) != expected:
            raise ProviderError("SmartSign: XML hãng không khớp MST, ký hiệu hoặc số hóa đơn")
        data = dict(ready.fields)
        data[PREFIX + "ButtonDownLoadPDF"] = ready.buttons[PREFIX + "ButtonDownLoadPDF"]
        pdf = session.post(PORTAL, data=data, timeout=90, allow_redirects=False)
        if pdf.status_code != 200 or not pdf.content.startswith(b"%PDF-"):
            raise ProviderError("SmartSign: nút tải chưa trả về PDF gốc")
        log("SmartSign: đã đối chiếu XML hãng và tải PDF gốc")
        return pdf.content
