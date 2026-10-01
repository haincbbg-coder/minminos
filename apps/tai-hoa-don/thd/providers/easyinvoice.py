# -*- coding: utf-8 -*-
"""
providers/easyinvoice.py - Tải PDF GỐC hóa đơn phát hành qua EasyInvoice (Softdreams).

Đã kiểm chứng trực tiếp trên tracuu.easyinvoice.vn (2026-09):

ĐƯỜNG B - TRA CỨU CỔNG (ưu tiên, khi có mã tra cứu trong XML):
  1) GET  /Search/Index                     -> lấy cookie phiên
  2) GET  /Captcha/Show                      -> ảnh captcha -> giải bằng 2Captcha
  3) POST /Search/Search {typeSearch:"", TaxCode:<MST>, FKey:<Mã tra cứu>, Capcha:<mã>}
        -> trang kết quả có hidden #InvData = {"str":<html HĐ>, "idInvoice":..} và nút
           downloadPdfAndFileAttachFromAvailableHtml('<token>')
  4) POST /Invoice/DownloadPdfAndFileAttachFromAvailableHtml {token, html=b64(InvData.str)}
        -> {fileGuid, fileName}
  5) GET  /Invoice/Download?fileGuid=..&fileName=..  -> ZIP (PDF gốc + XML) -> lấy .pdf
  (LƯU Ý: trang kết quả KHÔNG có sẵn link GetInvoice?token - link tải dựng bằng JS,
   nên phải đi đúng 2 bước 4+5 như trên.)

ĐƯỜNG A - LINK EMAIL (dự phòng): .../DownloadInvPdf?token=<b64 có id thật> hoặc
  ViewFromEmail?token=... -> GET /Invoice/GetInvoice?token=<đó> -> PDF, KHÔNG cần captcha.
  Xem download_by_token().

Mã tra cứu (Fkey) nằm trong <TTKhac> của XML (trường "Fkey").
Softdreams MSTTCGP = 0105987432 (nhận diện chắc chắn).
"""
from __future__ import annotations

import base64
import html as _htmllib
import io
import json
import re
import zipfile
from typing import Callable, Optional

from . import ProviderError
from . import _common as C

NAME = "EasyInvoice (Softdreams)"
HOST_DEFAULT = "http://tracuu.easyinvoice.vn"
MSTTCGP_SOFTDREAMS = "0105987432"

# Token tải trên TRANG KẾT QUẢ tra cứu, trong: downloadPdfAndFileAttachFromAvailableHtml('<token>')
# Máy chủ HTML-encode dấu nháy (' -> &#39;) nên KHÔNG bám vào dấu nháy - lấy chuỗi base64 dài ngay sau tên hàm.
_DL_FUNC = "downloadPdfAndFileAttachFromAvailableHtml("
_RE_DL_TOKEN_RUN = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")


def _extract_dl_token(body: str):
    i = body.find(_DL_FUNC)
    if i < 0:
        return None
    seg = body[i + len(_DL_FUNC): i + len(_DL_FUNC) + 600]
    m = _RE_DL_TOKEN_RUN.search(seg)   # token là chuỗi base64 dài (>20), bỏ qua &#39; ; ...
    return m.group(0) if m else None
# Hidden field InvData chứa {"str": <html hóa đơn>, "idInvoice":..., "pattern":...}
_RE_INVDATA = re.compile(r'id="InvData"[^>]*\bvalue="(.*?)"\s*/?>', re.S)
# Token trong LINK email (đường A)
_RE_TOKEN_URL = re.compile(r"(?:GetInvoice|DownloadInvPdf|ViewFromEmail)\?token=([A-Za-z0-9+/=%]+)")
_RE_CAPTCHA_WRONG = re.compile(r"(xác thực không đúng|sai mã xác thực|mã xác thực không|captcha (?:sai|invalid|không đúng))", re.I)
_RE_IMGCANCEL = re.compile(r'<img id="imgCancel"[^>]*>')


def detect(xml_text: str, inv: dict) -> bool:
    # Chắc chắn nhất: MSTTCGP của Softdreams
    if C.tcgp(xml_text) == MSTTCGP_SOFTDREAMS:
        return True
    portal = C.ttkhac(xml_text, "PortalLink").lower()
    if "easyinvoice" in portal:
        return True
    if C.ttkhac(xml_text, "Fkey"):
        return "easyinvoice" in xml_text.lower() or "softdreams" in xml_text.lower()
    return False


# Các tên trường mã tra cứu mà NCC hay nhúng vào <TTKhac> của XML
_CODE_FIELDS = ("Fkey", "FKey", "MaTraCuu", "MaTracuu", "Matracuu", "LookupCode",
                "MaBaoMat", "MaBM", "SecretCode", "TransactionID", "TransID", "MaHDon")
_RE_FKEY_INLINE = re.compile(r"[?&](?:Fkey|MaTraCuu|code)=([A-Za-z0-9]{6,})", re.I)


def find_code(xml_text: str, inv: dict) -> str:
    """Tìm MÃ TRA CỨU trong XML (nhiều tên trường) hoặc trong link nhúng - để tra cứu cổng NCC."""
    for f in _CODE_FIELDS:
        v = C.ttkhac(xml_text, f)
        if v and v.strip():
            return v.strip()
    # thử moi từ link tra cứu nhúng trong XML (PortalLink/ghi chú)
    m = _RE_FKEY_INLINE.search(xml_text)
    if m:
        return m.group(1)
    return (inv.get("_fkey") or inv.get("_ma_tra_cuu") or inv.get("_code") or "").strip()


def _hosts(xml_text: str, inv: dict):
    """Host để thử. ƯU TIÊN host chung tracuu.easyinvoice.vn (LUÔN phân giải được);
    tên miền riêng <MST>hd.easyinvoice.vn thử SAU CÙNG (nhiều khi không tồn tại -> lỗi DNS)."""
    hosts = [HOST_DEFAULT]                    # tracuu.easyinvoice.vn - chắc chắn resolve
    portal = C.ttkhac(xml_text, "PortalLink").strip()
    if portal:
        p = portal if portal.startswith("http") else "http://" + portal
        m = re.match(r"(https?://[^/]+)", p)
        if m and "easyinvoice.vn" in m.group(1):
            hosts.append(m.group(1))
    mst = C.seller_mst(xml_text) or (inv.get("nbmst") or "")
    if mst:
        hosts.append(f"http://{mst}hd.easyinvoice.vn")   # thử cuối
    seen, out = set(), []
    for h in hosts:
        if h not in seen:
            seen.add(h); out.append(h)
    return out


def _get_pdf(s, host: str, token: str, timeout=90):
    """GET GetInvoice bằng token -> trả PDF bytes hoặc None."""
    for path in ("/Invoice/GetInvoice?token=", "/Invoice/DownloadInvPdf?token="):
        url = f"{host}{path}{token}"
        try:
            r = s.get(url, timeout=timeout, allow_redirects=True,
                      headers={"Accept": "application/pdf,*/*",
                               "Referer": host + "/Search/Index"})
        except Exception:
            continue
        if r.status_code == 200 and r.content.lstrip().startswith(b"%PDF"):
            return r.content
    return None


def _token_id(token_b64: str) -> str:
    """Đọc <id> cuối trong token base64 (để bỏ token id=0)."""
    try:
        raw = base64.b64decode(token_b64 + "===").decode("utf-8", "ignore")
        return raw.rsplit("|", 1)[-1].strip()
    except Exception:
        return ""


def download_by_token(token_b64: str, log: Callable[[str], None], hosts=None) -> bytes:
    """Tải PDF gốc bằng token lấy NGUYÊN từ link trong email (đã có id thật) - KHÔNG cần captcha."""
    from urllib.parse import unquote
    token_b64 = unquote(token_b64).strip()  # bỏ %-encoding nếu email mã hóa URL
    s = C.make_session()
    hosts = hosts or [HOST_DEFAULT]
    last = ""
    for host in hosts:
        pdf = _get_pdf(s, host, token_b64)
        if pdf:
            return pdf
        last = f"{host}: không trả PDF"
    raise ProviderError(f"EasyInvoice không tải được PDF từ token email ({last})")


def _pdf_from_zip(zbytes: bytes):
    """Lấy tệp .pdf trong ZIP mà EasyInvoice trả về (ZIP gồm PDF gốc + XML)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zbytes))
        for name in zf.namelist():
            if name.lower().endswith(".pdf"):
                data = zf.read(name)
                if data.lstrip().startswith(b"%PDF"):
                    return data
    except Exception:
        pass
    return None


def _token_candidates(body: str, exclude: str = "") -> list:
    """Gom mọi chuỗi base64 dài trong trang kết quả để thử làm 'mã tải'.
    (Nút tải do JS dựng nên tên hàm không có trong HTML thô - mã token nằm rải trong trang.)"""
    cands = []
    t1 = _extract_dl_token(body)      # nếu tình cờ có tên hàm trong HTML
    if t1:
        cands.append(t1)
    for m in re.finditer(r"[A-Za-z0-9+/=]{50,220}", body):
        v = m.group(0)
        if v and v != exclude and v not in cands:
            cands.append(v)
    # ưu tiên độ dài ~100-140 (độ dài mã tải quan sát được là 128)
    cands.sort(key=lambda v: abs(len(v) - 128))
    return cands[:12]


def _try_download(s, host: str, token: str, html_b64: str, log):
    """Gọi 2 bước tải với 1 token; trả PDF nếu ra file, None nếu token này không đúng."""
    try:
        r = s.post(host + "/Invoice/DownloadPdfAndFileAttachFromAvailableHtml",
                   data={"token": token, "html": html_b64}, timeout=120,
                   headers={"X-Requested-With": "XMLHttpRequest",
                            "Referer": host + "/Search/Search"})
        rs = json.loads(r.text if hasattr(r, "text") else r.content.decode("utf-8", "ignore"))
    except Exception:
        return None
    if rs.get("msg") or not rs.get("fileGuid"):
        return None
    from urllib.parse import quote
    guid = rs["fileGuid"]; fname = rs.get("fileName") or "hoadon.zip"
    try:
        dl = s.get(host + f"/Invoice/Download?fileGuid={guid}&fileName={quote(fname)}",
                   timeout=120, headers={"Referer": host + "/Search/Search"})
        content = dl.content
    except Exception:
        return None
    if content[:2] == b"PK":
        pdf = _pdf_from_zip(content)
        if pdf:
            return pdf
    if content.lstrip().startswith(b"%PDF"):
        return content
    return None


def _download_result_pdf(s, host: str, body: str, log: Callable[[str], None]):
    """Từ TRANG KẾT QUẢ tra cứu, tải PDF gốc (đã kiểm chứng):
      POST /Invoice/DownloadPdfAndFileAttachFromAvailableHtml {token, html=b64(InvData.str)}
        -> {fileGuid} -> GET /Invoice/Download?fileGuid=.. -> ZIP (PDF gốc + XML) -> lấy PDF.
    Vì nút tải do JS dựng, ta thử lần lượt các 'mã tải' ứng viên có trong trang."""
    mi = _RE_INVDATA.search(body)
    if not mi:
        log("EasyInvoice: không đọc được dữ liệu hóa đơn (InvData) trên trang."); return None
    try:
        inv_json = json.loads(_htmllib.unescape(mi.group(1)))
    except Exception as e:  # noqa
        log(f"EasyInvoice: đọc InvData lỗi: {str(e)[:80]}"); return None
    inv_html = _RE_IMGCANCEL.sub("", inv_json.get("str") or "")
    html_b64 = base64.b64encode(inv_html.encode("utf-8")).decode()
    cands = _token_candidates(body, exclude=html_b64)
    if not cands:
        log("EasyInvoice: không thấy mã tải nào trên trang kết quả."); return None
    log(f"EasyInvoice: thử {len(cands)} mã tải ứng viên để lấy file...")
    for idx, tok in enumerate(cands, 1):
        pdf = _try_download(s, host, tok, html_b64, log)
        if pdf:
            log(f"EasyInvoice: mã tải thứ {idx} hợp lệ, đã lấy file.")
            return pdf
    log("EasyInvoice: đã thử hết mã tải ứng viên nhưng máy chủ chưa trả file "
        "(có thể cần token đặc thù - gửi log để kiểm tra thêm)."); return None


def _portal_download(xml_text: str, inv: dict, code: str, mst: str,
                     solver, log: Callable[[str], None]) -> bytes:
    """Đường B: tra cứu công khai + giải captcha -> tải PDF gốc (ZIP PDF+XML)."""
    hosts = _hosts(xml_text, inv)
    serial = C.khmshdon(xml_text) + C.khhdon(xml_text)
    num = C.shdon(xml_text)
    log(f"EasyInvoice: bắt đầu tra cứu cổng - MST {mst}, mã tra cứu {code}, HĐ {serial} số {num}.")
    log(f"EasyInvoice: sẽ thử {len(hosts)} địa chỉ: {', '.join(hosts)}")
    reached_portal = False   # đã kết nối được ít nhất 1 cổng chưa (để báo lỗi đúng)
    for host in hosts:
        try:
            s = C.make_session()
            s.get(host + "/Search/Index", timeout=60)  # lấy cookie phiên
        except Exception as e:  # noqa
            log(f"EasyInvoice: bỏ qua {host} (không kết nối được: {str(e)[:80]})")
            continue
        reached_portal = True
        log(f"EasyInvoice: đã vào cổng {host}, bắt đầu giải captcha...")
        for attempt in range(1, 4):  # captcha có thể sai, thử lại tối đa 3 lần
            try:
                img = s.get(host + "/Captcha/Show", timeout=60,
                            headers={"Referer": host + "/Search/Index"}).content
                if not img:
                    log(f"EasyInvoice {host}: không lấy được ảnh captcha."); break
                log(f"EasyInvoice: lấy ảnh captcha ({len(img)} byte), gửi dịch vụ giải (lần {attempt})...")
                cap = (solver(img) or "").strip()
                if not cap:
                    log("EasyInvoice: dịch vụ giải captcha trả về RỖNG "
                        "(kiểm tra API key / số dư 2Captcha). Thử lại..."); continue
                log(f"EasyInvoice: captcha giải ra '{cap}', gửi tra cứu...")
                data = {"typeSearch": "", "TaxCode": mst, "FKey": code, "Capcha": cap}
                r = s.post(host + "/Search/Search", data=data, timeout=90,
                           headers={"X-Requested-With": "XMLHttpRequest",
                                    "Referer": host + "/Search/Index"})
                body = r.text if hasattr(r, "text") else r.content.decode("utf-8", "ignore")
                log(f"EasyInvoice: tra cứu trả HTTP {getattr(r,'status_code','?')}, "
                    f"trang {len(body)} ký tự.")
                if _RE_INVDATA.search(body):
                    log("EasyInvoice: tra cứu RA hóa đơn, đang tạo & tải PDF gốc...")
                    pdf = _download_result_pdf(s, host, body, log)
                    if pdf:
                        log("EasyInvoice: ✓ lấy được PDF gốc.")
                        return pdf
                    log(f"EasyInvoice {host}: có hóa đơn nhưng tạo file PDF chưa được "
                        f"(xem dòng trên)."); break
                # Không có kết quả -> nhiều khả năng captcha sai / sai mã tra cứu
                log("EasyInvoice: chưa ra hóa đơn (captcha sai hoặc sai MST/mã tra cứu), "
                    "thử captcha mới..."); continue
            except Exception as e:  # noqa
                log(f"EasyInvoice {host}: lỗi khi tra cứu: {str(e)[:120]}"); break
    if not reached_portal:
        raise ProviderError("Không kết nối được cổng EasyInvoice (mạng/DNS bị chặn). "
                            "Kiểm tra Internet/tường lửa của máy.")
    raise ProviderError("Tra cứu cổng EasyInvoice chưa ra PDF (captcha sai nhiều lần "
                        "hoặc sai mã tra cứu). Xem Nhật ký để biết chi tiết; "
                        "hoặc quét Gmail để lấy link tải.")


def fetch_pdf(xml_text: str, inv: dict, log: Callable[[str], None], solver=None) -> bytes:
    """ƯU TIÊN tra cứu THẲNG trên cổng EasyInvoice (MST + mã tra cứu + captcha).
    Chỉ khi cổng không xong mới quay về token lấy từ email (nếu có)."""
    code = find_code(xml_text, inv)
    mst = C.seller_mst(xml_text) or (inv.get("nbmst") or "")
    tok = (inv.get("_ei_token") or inv.get("_email_token") or inv.get("_pdf_token"))

    # A. TRA CỨU CỔNG NCC (ưu tiên) - cần mã tra cứu + API giải captcha
    if code and solver:
        try:
            return _portal_download(xml_text, inv, code, mst, solver, log)
        except ProviderError as e:
            log(f"EasyInvoice: tra cứu cổng chưa xong ({e})")

    # B. Token từ email (dự phòng khi không có mã trong XML / chưa khai báo captcha)
    if tok:
        try:
            return download_by_token(tok, log, hosts=_hosts(xml_text, inv))
        except ProviderError as e:
            log(f"EasyInvoice: token email cũng chưa tải được ({e})")

    # Báo lỗi rõ theo nguyên nhân
    if code and not solver:
        raise ProviderError("EasyInvoice cần MÃ XÁC THỰC (captcha) để tra cứu cổng. "
                            "Hãy khai báo API giải captcha (2Captcha/OmoCaptcha) trong Cài đặt.")
    if not code:
        raise ProviderError("Không tìm thấy Mã tra cứu trong XML để tra cứu cổng EasyInvoice "
                            "- hóa đơn này cần lấy mã/link từ email NCC (quét Gmail).")
    raise ProviderError("EasyInvoice: chưa tải được PDF gốc qua cổng.")
