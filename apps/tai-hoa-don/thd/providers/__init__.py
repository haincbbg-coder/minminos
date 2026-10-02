# -*- coding: utf-8 -*-
"""
providers - Tải "PDF GỐC" (bản PDF do nhà cung cấp hóa đơn điện tử phát hành, có mẫu/logo
bên bán) từ trang tra cứu công khai của từng nhà cung cấp (T-VAN).

Cổng hoadondientu.gdt.gov.vn chỉ trả XML + bản thể hiện; PDF gốc nằm ở website của
nhà cung cấp (MISA, Viettel, VNPT, BKAV, ...). Mỗi nhà cung cấp một module trong thư mục
này, cùng giao diện:

    NAME        : tên hiển thị
    detect(xml_bytes, inv) -> bool            # XML này có phải của nhà cung cấp đó không
    fetch_pdf(xml_bytes, inv, log) -> bytes   # trả về nội dung PDF, hoặc raise ProviderError

Thêm nhà cung cấp mới: viết module mới, thêm vào danh sách PROVIDERS. Không cần sửa app.
"""
from __future__ import annotations

import re
from typing import Callable, Optional


class ProviderError(Exception):
    """Lỗi khi tải PDF gốc từ nhà cung cấp (mã tra cứu sai, hết hạn, chặn bot...)."""


class NotSupported(ProviderError):
    """Không nhận diện được nhà cung cấp của hóa đơn này."""


def _xml_text(xml_bytes: bytes) -> str:
    try:
        return xml_bytes.decode("utf-8", "ignore")
    except Exception:
        return ""


# ---- các module nhà cung cấp -----------------------------------------------
from . import misa          # noqa: E402
from . import sapo          # noqa: E402
from . import easyinvoice   # noqa: E402
from . import bkav          # noqa: E402
from . import viettel       # noqa: E402
from . import htinvoice     # noqa: E402
from . import kkvat         # noqa: E402
from . import efy           # noqa: E402
from . import xmllink       # noqa: E402

# Thứ tự = thứ tự thử nhận diện. Thêm hãng mới: viết module rồi thêm vào đây.
# xmllink đặt cuối để nhận link độc lập, đồng thời làm dự phòng khi hãng tải thất bại.
PROVIDERS = [misa, sapo, easyinvoice, bkav, viettel, htinvoice, kkvat, efy, xmllink]


def detect(xml_bytes: bytes, inv: Optional[dict] = None):
    """Trả về module nhà cung cấp phù hợp, hoặc None."""
    txt = _xml_text(xml_bytes)
    for p in PROVIDERS:
        try:
            if p.detect(txt, inv or {}):
                return p
        except Exception:
            continue
    return None


def provider_names() -> list[str]:
    return [p.NAME for p in PROVIDERS]


# MSTTCGP (MST tổ chức cung cấp giải pháp hóa đơn) -> tên NHÀ PHÁT HÀNH, để hiện trên bảng.
TCGP_NAME = {
    "0309612872": "SmartSign",
    "0101243150": "MISA meInvoice",
    "0103243195": "Sapo",
    "0105987432": "EasyInvoice (Softdreams)",
    "0101360697": "BKAV eHoadon",
    "0100109106": "Viettel (S-Invoice)",
    "0106870211": "VNPT Invoice",
    "0100686209": "VNPT",
    "0101300842": "FPT.eInvoice",
    "0301472379": "TS24 (KKVAT)",
    "0304281106": "M-Invoice",
    "0100727825": "EFY-eHoaDon / iHoaDon",   # J&T Express (Thuận Phong)... nhét link PDF trong XML
    "0108971656": "MY SOFTWARE (myinvoice)", # xác nhận từ footer email (Phương Chi Bắc Ninh...)
    "0315638251": "HTInvoice",               # NTP... - mã tra cứu MTCuu trong XML
    "0313963672": "TS24 (KKVAT)",            # mã 'Số bảo mật' trong XML
    "0102519041": "EFY (iHoaDon)",           # Ngọc Thuỷ Hà... - tra cứu số HĐ + mã tra cứu (reCAPTCHA)
}

# Hãng KHÓA bản gốc bằng MÃ BÍ MẬT gửi qua EMAIL (không có trong XML) -> phải Quét Gmail.
# Nhiều hãng còn ĐÍNH KÈM SẴN PDF trong email nên Quét Gmail lấy được ngay, khỏi cần mã.
EMAIL_CODE_TCGP = {
    "0101360697": ("BKAV eHoadon", "https://tracuu.ehoadon.vn"),
    "0108971656": ("MY SOFTWARE (myinvoice)", "https://tracuu.myinvoice.vn"),
}


# MSTTCGP các hãng ĐÃ tự tải được bản gốc (để lọc ra hãng CHƯA hỗ trợ).
SUPPORTED_TCGP = {
    "0101243150",  # MISA
    "0103243195",  # Sapo
    "0105987432",  # EasyInvoice (Softdreams)
    "0101360697",  # BKAV (qua Gmail lấy MTC)
    "0100109106",  # Viettel S-Invoice
    "0100727825",  # J&T/EFY (link trong XML)
    "0315638251",  # HTInvoice (NTP)
    "0313963672",  # TS24/KKVAT
}


def issuer_name(inv: dict) -> str:
    """Tên nhà phát hành hóa đơn của 1 hóa đơn (dựa MSTTCGP trong XML đã bóc)."""
    d = inv.get("_detail") or {}
    code = str(d.get("msttcgp") or "").strip()
    if not code:
        return ""
    return TCGP_NAME.get(code, f"NPH {code}")


def manual_download_info(xml_bytes: bytes, inv: Optional[dict] = None) -> Optional[dict]:
    """HƯỚNG A (bán tự động): với hóa đơn vướng captcha/chống bot, trả thông tin để MỞ CỔNG
    ĐIỀN SẴN cho người dùng TỰ tải tay nhanh (phần mềm KHÔNG tự vượt captcha).
    Trả dict {provider, url, code, method, mst} hoặc None nếu không thuộc nhóm này / không đủ mã."""
    from . import _common as C
    txt = _xml_text(xml_bytes)
    code = C.tcgp(txt)
    mst = C.seller_mst(txt)
    sh = C.shdon(txt)

    def std(d, sh_=""):
        """Gắn tham số chuẩn hddt_* vào URL để EXTENSION trình duyệt tự điền vào ô.
        (Chỉ gắn mã khi là mã THẬT, không gắn placeholder '(mã ở email)'.)"""
        from urllib.parse import urlencode
        q = {}
        if d.get("mst"):
            q["hddt_mst"] = d["mst"]
        cval = d.get("code") or ""
        if cval and not cval.startswith("("):
            q["hddt_ma"] = cval
        if sh_:
            q["hddt_so"] = sh_
        if q:
            url = d["url"]
            d["url"] = url + ("&" if "?" in url else "?") + urlencode(q)
        return d

    # Viettel S-Invoice - captcha trượt; mã bí mật có trong XML
    if easyinvoice.detect(txt, inv or {}):
        c = easyinvoice.find_code(txt, inv or {})
        return std({"provider": easyinvoice.NAME, "url": easyinvoice.HOST_DEFAULT,
                    "code": c, "method": "Nhập MST + mã + captcha", "mst": mst})
    if misa.detect(txt, inv or {}):
        from urllib.parse import quote
        c = (inv or {}).get("_ma_tra_cuu") or misa.find_code(txt)
        return {"provider": misa.NAME, "url": "https://www.meinvoice.vn/tra-cuu/?sc=" + quote(c or "", safe=""),
                "code": c, "method": "Mã tra cứu", "mst": mst}
    if code == "0100109106":
        secret = viettel._secret(txt)
        if secret:
            return std({"provider": "Viettel S-Invoice", "url": viettel.search_url(mst, secret),
                        "code": secret, "method": "Kéo thanh trượt", "mst": mst})
    # EFY iHoaDon - reCAPTCHA; tra theo số HĐ + mã tra cứu
    if code == "0102519041":
        c = efy.find_code(txt, inv or {})
        return std({"provider": "EFY (iHoaDon)", "url": efy.lookup_url(sh, c),
                    "code": c or "(mã ở email)", "method": "reCAPTCHA", "mst": mst}, sh)
    # BKAV eHoadon - reCAPTCHA; MTC trong XML hoặc email
    if code == "0101360697":
        from urllib.parse import quote
        mtc = bkav.find_code(txt, inv or {})
        url = "https://tchd.ehoadon.vn/TCHD" + ("?MTC=" + quote(mtc, safe="") if mtc else "")
        return std({"provider": "BKAV eHoadon", "url": url,
                    "code": mtc or "(mã ở email - Quét Gmail)", "method": "reCAPTCHA", "mst": mst})
    # MY SOFTWARE (myinvoice) - mã bảo mật gửi qua email
    if code == "0108971656":
        return std({"provider": "MY SOFTWARE (myinvoice)", "url": "https://tracuu.myinvoice.vn",
                    "code": "(mã ở email - Quét Gmail)", "method": "Nhập mã + captcha", "mst": mst})
    # HTInvoice - mã MTCuu trong XML, cổng laphoadon.htinvoice.vn/TraCuu
    if code == "0315638251":
        c = htinvoice.code(txt)
        base = htinvoice.portal(txt).split("/TraCuu")[0].rstrip("/")
        return std({"provider": "HTInvoice", "url": base + "/TraCuu",
                    "code": c or "(không có mã)", "method": "Nhập số HĐ + mã + captcha", "mst": mst}, sh)
    # TS24 / KKVAT - số bảo mật trong XML
    if code == "0313963672":
        c = kkvat.code(txt)
        return std({"provider": "TS24 (KKVAT)", "url": kkvat.HOST,
                    "code": c or "(không có mã)", "method": "Nhập MST + mã + captcha", "mst": mst})
    if code == "0309612872":
        c = (inv or {}).get("_ma_tra_cuu") or C.ttkhac(txt, "Matracuu")
        return std({"provider": "SmartSign", "url": "https://tracuuhd.smartsign.com.vn",
                    "code": c, "method": "Mã tra cứu", "mst": mst}, sh)
    # A known lookup field remains useful even when no downloader exists yet.
    # Never substitute the invoice number/Fkey or invent an issuer URL.
    lookup = (inv or {}).get("_ma_tra_cuu") or next(
        (v for field in ("MaTraCuu", "Matracuu", "MTCuu", "QuanLy_SoBaoMat", "MaTimKiem")
         if (v := C.ttkhac(txt, field))), "")
    if lookup:
        return {"provider": TCGP_NAME.get(code, f"NPH {code}" if code else ""),
                "code": lookup, "url": "", "method": "Mã trong XML", "mst": mst}
    return None


# Nhà cung cấp KHÔNG tự cào được (trang tra cứu dùng captcha / reCAPTCHA / mã bảo mật riêng).
# Nhận diện qua MSTTCGP (điền dần khi biết) hoặc chữ trong XML. Mỗi mục: (tên, trang tra cứu tay).
CAPTCHA_TCGP = {
    "0101360697": ("BKAV eHoadon", "https://tracuu.ehoadon.vn"),   # xác minh từ hóa đơn thật
}
CAPTCHA_TEXT = [
    ("ehoadon", ("BKAV eHoadon", "https://tracuu.ehoadon.vn")),
    ("bkav", ("BKAV eHoadon", "https://tracuu.ehoadon.vn")),
    ("kkvat", ("TS24 (kkvat)", "https://tracuuhoadon.kkvat.com.vn")),
    ("ts24", ("TS24 (kkvat)", "https://tracuuhoadon.kkvat.com.vn")),
]


def captcha_hint(xml_bytes) -> tuple:
    """Nếu hóa đơn thuộc hãng chặn captcha -> trả (tên hãng, trang tra cứu tay), ngược lại (None, None)."""
    from . import _common as C
    txt = _xml_text(xml_bytes)
    code = C.tcgp(txt)
    if code in CAPTCHA_TCGP:
        return CAPTCHA_TCGP[code]
    low = txt.lower()
    for key, val in CAPTCHA_TEXT:
        if key in low:
            return val
    return (None, None)


def fetch_original_pdf(xml_bytes: bytes, inv: Optional[dict] = None,
                       log: Optional[Callable[[str], None]] = None,
                       force: Optional[str] = None,
                       solver: Optional[Callable[[bytes], str]] = None) -> tuple[str, bytes]:
    """Nhận diện nhà cung cấp rồi tải PDF gốc. -> (tên NCC, pdf_bytes). Raise ProviderError.

    solver: hàm(ảnh_captcha_bytes) -> chuỗi mã (dùng cho hãng bắt captcha như EasyInvoice).
    """
    log = log or (lambda s: None)
    txt = _xml_text(xml_bytes)
    p = None
    if force:
        p = next((x for x in PROVIDERS if x.NAME.lower() == force.lower()), None)
    if p is None:
        p = detect(xml_bytes, inv)
    if p is None:
        from . import _common as C
        code = C.tcgp(txt)
        extra = f" [MSTTCGP={code}]" if code else ""
        raise NotSupported("Không nhận diện được nhà cung cấp hóa đơn" + extra +
                           " - hiện hỗ trợ: " + ", ".join(provider_names()))
    candidates = [p]
    if not force and p is not xmllink and xmllink.detect(txt, inv or {}):
        candidates.append(xmllink)
    errors = []
    for candidate in candidates:
        try:
            pdf = candidate.fetch_pdf(txt, inv or {}, log, solver=solver)
            if not pdf or not pdf.lstrip().startswith(b"%PDF-"):
                raise ProviderError("dữ liệu trả về không phải PDF")
            return candidate.NAME, pdf
        except Exception as e:
            errors.append(f"{candidate.NAME}: {str(e)[:200]}")
            log(f"Chưa lấy được PDF qua {candidate.NAME}; thử nguồn tiếp theo nếu có.")
    raise ProviderError("; ".join(errors))
