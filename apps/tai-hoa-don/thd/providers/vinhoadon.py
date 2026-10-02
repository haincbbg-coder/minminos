"""VIN-HOADON's public lookup, matching the portal's XML/PDF download buttons."""
import base64
import tempfile
from pathlib import Path

from . import ProviderError, _common as C
from .smartsign import identity

NAME = "VIN-HOADON (Visnam)"
PORTAL = "https://tracuu.vin-hoadon.com/"
API = PORTAL + "api/services/hddt/TraCuuHoaDon/"


def detect(xml_text, inv):
    return C.tcgp(xml_text) in ("0401486901", "0402024593")


def find_code(xml_text, inv):
    return str(inv.get("_ma_tra_cuu") or inv.get("_code") or
               (inv.get("_gmail_lookup") or {}).get("ma_tra_cuu") or next(
                   (v for f in ("MaTraCuu", "Matracuu", "MTCuu", "QuanLy_SoBaoMat", "MaTimKiem", "Mã tra cứu")
                    if (v := C.ttkhac(xml_text, f))), "")).strip()


def decode(value):
    try:
        value = value or ""
        if value.startswith("data:"):
            value = value.split(",", 1)[1]
        if len(value) > 35 * 1024 * 1024:
            raise ValueError("oversized")
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError, IndexError) as exc:
        raise ProviderError("VIN-HOADON: dữ liệu file không hợp lệ") from exc


def result(response):
    if response.status_code != 200:
        raise ProviderError(f"VIN-HOADON: HTTP {response.status_code}")
    obj = response.json()
    value = obj.get("result")
    if obj.get("success") is False or not isinstance(value, dict):
        raise ProviderError("VIN-HOADON: cổng tra cứu không trả kết quả hợp lệ")
    return value


def fetch_pdf(xml_text, inv, log, solver=None):
    code = find_code(xml_text, inv)
    inv["_manual_url"] = PORTAL
    if not code:
        raise ProviderError("VIN-HOADON: chưa có mã tra cứu trong XML hoặc Gmail")
    if solver is None:
        raise ProviderError("VIN-HOADON: cần dịch vụ giải CAPTCHA ảnh")
    expected = identity(xml_text)
    # The issuer omits its RapidSSL intermediate. Supply that public CA certificate
    # alongside certifi's roots; hostname and full chain verification remain enabled.
    import certifi
    with tempfile.TemporaryDirectory(prefix="minmin-vin-ca-") as tmp, C.make_session() as session:
        bundle = Path(tmp) / "ca.pem"
        bundle.write_bytes(Path(certifi.where()).read_bytes() + b"\n" +
                          Path(__file__).with_name("certs").joinpath("rapidssl-tls-rsa-ca-g1.pem").read_bytes())
        session.verify = str(bundle)
        for attempt in range(3):
            cap = result(session.post(API + "RefreshCaptcha", timeout=40, allow_redirects=False))
            answer = solver.image(decode(cap.get("image")))
            found = result(session.post(API + "TraCuu", json={
                "doanhNghiep_MST": C.seller_mst(xml_text), "maSoBiMat": code,
                "key": cap.get("key"), "captcha": answer,
            }, timeout=90, allow_redirects=False))
            if found.get("status") == 1:
                break
            if found.get("status") != 2:
                raise ProviderError("VIN-HOADON: " + str(found.get("message") or "Không tìm thấy hóa đơn")[:250])
            log(f"VIN-HOADON: CAPTCHA bị từ chối ({attempt + 1}/3)")
        else:
            raise ProviderError("VIN-HOADON: CAPTCHA chưa được chấp nhận sau 3 lần")
        source = decode((found.get("fileData") or {}).get("fileData") or found.get("base64"))
        if identity(source.decode("utf-8-sig")) != expected:
            raise ProviderError("VIN-HOADON: XML hãng không khớp MST, ký hiệu hoặc số hóa đơn")
        pdf = decode((found.get("filePdf") or {}).get("fileData"))
        if not pdf.startswith(b"%PDF-"):
            raise ProviderError("VIN-HOADON: kết quả chưa có PDF gốc")
        log("VIN-HOADON: đã đối chiếu XML hãng và tải PDF gốc")
        return pdf
