"""CyberBill public lookup and issuer originals, verified against the tax XML."""
import base64
from urllib.parse import urlencode

from . import ProviderError, _common as C
from .smartsign import identity
from .vinhoadon import find_code

NAME = "CyberBill (xCyber)"
PORTAL = "https://tracuuhoadon1.xcyber.vn/"
BASE = "https://bill1app.xcyber.vn"
API = BASE + "/api/services/hddt/TraCuuHoaDon/"
MAX_FILE = 25 * 1024 * 1024


def detect(xml_text, inv):
    return C.tcgp(xml_text) == "0105232093"


def _result(response):
    if response.status_code != 200:
        raise ProviderError(f"CyberBill: HTTP {response.status_code}")
    obj = response.json()
    if not isinstance(obj, dict) or obj.get("success") is False or not isinstance(obj.get("result"), dict):
        raise ProviderError("CyberBill: cổng tra cứu không trả kết quả hợp lệ")
    return obj["result"]


def _decode(value):
    try:
        if value.startswith("data:"):
            value = value.split(",", 1)[1]
        if len(value) > 35 * 1024 * 1024:
            raise ValueError("oversized")
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError, AttributeError, IndexError) as exc:
        raise ProviderError("CyberBill: dữ liệu file không hợp lệ") from exc


def _file(session, info):
    if not isinstance(info, dict) or not info.get("fileToken"):
        raise ProviderError("CyberBill: chưa cấp file tải về")
    # Match the portal's DownloadTempFile button. Never follow a supplied URL or
    # redirect: tokens and names are query values on this fixed public endpoint.
    query = urlencode({key: str(info.get(key) or "") for key in ("fileType", "fileToken", "fileName")})
    response = session.get(BASE + "/File/DownloadTempFile?" + query,
                           timeout=90, stream=True, allow_redirects=False)
    try:
        if response.status_code != 200:
            raise ProviderError(f"CyberBill: tải file HTTP {response.status_code}")
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_FILE:
                raise ProviderError("CyberBill: file vượt giới hạn 25 MB")
        return bytes(data)
    finally:
        response.close()


def fetch_pdf(xml_text, inv, log, solver=None):
    inv["_manual_url"] = PORTAL
    code = find_code(xml_text, inv)
    if not code:
        raise ProviderError("CyberBill: chưa có mã tra cứu trong XML hoặc Gmail")
    if solver is None:
        raise ProviderError("CyberBill: cần dịch vụ giải CAPTCHA ảnh")
    expected = identity(xml_text)
    with C.make_session() as session:
        for attempt in range(3):
            cap = _result(session.post(API + "RefreshCaptcha", timeout=40, allow_redirects=False))
            answer = solver.image(_decode(cap.get("image")))
            found = _result(session.post(API + "TraCuu", json={
                "doanhNghiep_MST": C.seller_mst(xml_text), "maSoBiMat": code,
                "key": cap.get("key"), "captcha": answer,
            }, timeout=90, allow_redirects=False))
            if found.get("status") == 1:
                break
            if found.get("status") != 2:
                raise ProviderError("CyberBill: " + str(found.get("message") or "Không tìm thấy hóa đơn trên cổng tra cứu")[:250])
            log(f"CyberBill: CAPTCHA bị từ chối ({attempt + 1}/3)")
        else:
            raise ProviderError("CyberBill: CAPTCHA chưa được chấp nhận sau 3 lần")
        xml_file = found.get("fileData") or {}
        source = _file(session, xml_file) if xml_file.get("fileToken") else _decode(found.get("base64"))
        if identity(source.decode("utf-8-sig")) != expected:
            raise ProviderError("CyberBill: XML hãng không khớp MST, ký hiệu hoặc số hóa đơn")
        if not found.get("key"):
            raise ProviderError("CyberBill: cổng tra cứu thiếu khóa tải PDF")
        file_info = _result(session.post(API + "DownloadPdf", json={
            "doanhNghiep_MST": C.seller_mst(xml_text), "maSoBiMat": code, "key": found["key"],
        }, timeout=90, allow_redirects=False))
        pdf = _file(session, file_info)
        if not pdf.startswith(b"%PDF-"):
            raise ProviderError("CyberBill: kết quả chưa có PDF gốc")
        log("CyberBill: đã đối chiếu XML hãng và tải PDF gốc")
        return pdf
