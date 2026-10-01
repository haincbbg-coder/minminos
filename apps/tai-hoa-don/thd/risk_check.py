# -*- coding: utf-8 -*-
"""
risk_check.py - KIỂM TRA RỦI RO HÓA ĐƠN CHI TIẾT (từng hóa đơn).

Học từ app lớn (mục "Kiểm tra rủi ro HĐ"): với mỗi hóa đơn, chấm các tiêu chí:
  1. Mã cơ quan thuế (MCCQT): hóa đơn CÓ MÃ của CQT hay không.
  2. Chữ ký số người bán: có chứng thư số không, còn HẠN tại thời điểm lập HĐ không,
     MST trong chứng thư có KHỚP MST người bán không (chống hóa đơn giả mạo chữ ký).
  3. Thông tin BÊN MUA khớp công ty mình: MST / tên / địa chỉ.
  4. Số học: tiền hàng + thuế − chiết khấu = tổng thanh toán.
  5. Trạng thái người bán (NNT) đang hoạt động - nếu đã tra cứu online (tracuunnt) và truyền vào.

Toàn bộ tiêu chí 1–4 chạy CỤC BỘ, không cần mạng. Tiêu chí 5 dùng kết quả tra cứu sẵn có.
Trả về dict để hiện bảng + tô màu theo mức rủi ro (Cao/Vừa/Thấp/OK).

Không phụ thuộc mạng, không sửa dữ liệu hóa đơn.
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Optional

OK, WARN, FAIL, NA = "ok", "warn", "fail", "na"


# ------------------------------------------------------------------ tiện ích
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _norm(s: str) -> str:
    """Bỏ dấu, hạ chữ thường, gộp khoảng trắng - để so tên/địa chỉ 'gần đúng'."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def _inv_date(inv: dict) -> Optional[_dt.date]:
    s = str(inv.get("tdlap") or inv.get("ngay") or "")[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ------------------------------------------------------- đọc chữ ký số từ XML
def read_seller_cert(xml_bytes: bytes) -> Optional[dict]:
    """Đọc chứng thư số NGƯỜI BÁN từ XML (thẻ DSCKS/…/X509Certificate).
    Trả {subject, mst, not_before, not_after, signing_time} hoặc None nếu không có / lỗi."""
    if not xml_bytes:
        return None
    # 1) lấy chuỗi base64 của cert đầu tiên (ưu tiên khối NBan nếu có)
    try:
        raw = xml_bytes.decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r"<(?:\w+:)?X509Certificate>\s*([A-Za-z0-9+/=\s]+?)\s*</", raw)
    if not m:
        return None
    b64 = re.sub(r"\s+", "", m.group(1))
    info: dict = {"subject": "", "mst": "", "not_before": None, "not_after": None, "signing_time": None}
    # 2) thời điểm ký (SigningTime / SigningTime trong SignatureProperty)
    ms = re.search(r"<(?:\w+:)?SigningTime>\s*([0-9T:\-\+\.Z]+)", raw)
    if ms:
        info["signing_time"] = ms.group(1)[:19]
    # 3) giải mã cert bằng 'cryptography' (đã có sẵn trong app cho bản quyền)
    try:
        import base64
        from cryptography import x509
        der = base64.b64decode(b64)
        cert = x509.load_der_x509_certificate(der)
        info["subject"] = cert.subject.rfc4514_string()
        try:
            info["not_before"] = cert.not_valid_before_utc.date()
            info["not_after"] = cert.not_valid_after_utc.date()
        except AttributeError:      # cryptography cũ
            info["not_before"] = cert.not_valid_before.date()
            info["not_after"] = cert.not_valid_after.date()
        # MST nằm trong UID=MST:xxxxxxxx của subject
        mm = re.search(r"MST:?\s*([0-9\-]{10,14})", info["subject"])
        if mm:
            info["mst"] = _digits(mm.group(1))
    except Exception:
        # không giải mã được cert -> vẫn báo 'có chữ ký' nhưng không đọc được chi tiết
        info["subject"] = info["subject"] or "(không đọc được chứng thư)"
    return info


# ------------------------------------------------------------- chấm 1 hóa đơn
def check_one(inv: dict, xml_bytes: Optional[bytes],
              company_mst: str = "", company_name: str = "", company_addr: str = "",
              seller_active: Optional[bool] = None,
              seller_status_text: str = "") -> dict:
    """Chấm rủi ro 1 hóa đơn. Trả {level, score, items:[{ten, trang_thai, chi_tiet}]}."""
    items: list[dict] = []

    def add(ten, st, ct=""):
        items.append({"ten": ten, "trang_thai": st, "chi_tiet": ct})

    is_ban_vao = bool(company_mst) and _digits(inv.get("nmmst") or inv.get("mua_mst")) == _digits(company_mst)

    # 1) Mã cơ quan thuế
    mccqt = (inv.get("mccqt") or inv.get("_detail", {}).get("mccqt") or "").strip()
    thd = str(inv.get("thdon") or "")
    khong_ma = "không mã" in thd.lower() or "khong ma" in _norm(thd)
    if mccqt:
        add("Mã cơ quan thuế", OK, f"Có mã CQT: {mccqt}")
    elif khong_ma:
        add("Mã cơ quan thuế", WARN, "Hóa đơn KHÔNG MÃ (loại không có mã CQT) - đối chiếu bảng tổng hợp đã gửi CQT")
    else:
        add("Mã cơ quan thuế", WARN, "Không thấy mã CQT trong dữ liệu - kiểm tra lại loại hóa đơn")

    # 2) Chữ ký số người bán
    cert = read_seller_cert(xml_bytes) if xml_bytes else None
    if not cert:
        add("Chữ ký số người bán", WARN, "Không tìm thấy chữ ký số trong XML (có thể chưa tải XML gốc)")
    else:
        seller_mst = _digits(inv.get("nbmst") or inv.get("ban_mst"))
        det = []
        st = OK
        # còn hạn tại thời điểm lập HĐ?
        d = _inv_date(inv)
        if cert.get("not_before") and cert.get("not_after") and d:
            if d < cert["not_before"] or d > cert["not_after"]:
                st = FAIL
                det.append(f"chứng thư HẾT HẠN so với ngày HĐ (hiệu lực {cert['not_before']}→{cert['not_after']}, HĐ {d})")
            else:
                det.append(f"còn hạn ({cert['not_before']}→{cert['not_after']})")
        elif cert.get("not_after"):
            det.append(f"hiệu lực đến {cert['not_after']}")
        # MST trong chứng thư khớp người bán?
        if cert.get("mst") and seller_mst:
            if cert["mst"] != seller_mst:
                st = FAIL
                det.append(f"MST chứng thư {cert['mst']} ≠ MST người bán {seller_mst} (nghi giả mạo)")
            else:
                det.append("MST chứng thư khớp người bán")
        elif not cert.get("mst"):
            if st == OK:
                st = WARN
            det.append("không đọc được MST trong chứng thư")
        if cert.get("signing_time"):
            det.append(f"ký lúc {cert['signing_time']}")
        add("Chữ ký số người bán", st, "; ".join(det))

    # 3) Bên mua khớp công ty mình (chỉ xét hóa đơn ĐẦU VÀO)
    if company_mst and is_ban_vao:
        buyer_mst = _digits(inv.get("nmmst") or inv.get("mua_mst"))
        if buyer_mst == _digits(company_mst):
            det = ["MST bên mua khớp"]
            st = OK
            bn = _norm(inv.get("nmten") or inv.get("mua_ten") or inv.get("nmtnmua"))
            if company_name and bn and _norm(company_name) not in bn and bn not in _norm(company_name):
                st = WARN; det.append("tên bên mua lệch với tên công ty")
            ba = _norm(inv.get("nmdchi") or inv.get("mua_dchi"))
            if company_addr and ba and _norm(company_addr) not in ba and ba not in _norm(company_addr):
                if st == OK:
                    st = WARN
                det.append("địa chỉ bên mua lệch")
            add("Thông tin bên mua", st, "; ".join(det))
        else:
            add("Thông tin bên mua", FAIL, f"MST bên mua {buyer_mst} ≠ MST công ty {_digits(company_mst)}")
    elif company_mst and not is_ban_vao:
        add("Thông tin bên mua", NA, "Hóa đơn bán ra - không đối chiếu bên mua")

    # 4) Số học
    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0
    thd_l = _norm(thd)
    is_ban_hang = "ban hang" in thd_l and "gia tri gia tang" not in thd_l
    ch = _f(inv.get("tgtcthue")); th = _f(inv.get("tgtthue"))
    ck = _f(inv.get("ttcktmai")); tt = _f(inv.get("tgtttbso"))
    if is_ban_hang or (not ch and not th):
        add("Số học tổng tiền", NA, "Hóa đơn bán hàng/không tách thuế - không đối chiếu được")
    elif tt and abs(ch + th - ck - tt) > 1.0:
        add("Số học tổng tiền", FAIL,
            f"tiền hàng {ch:,.0f} + thuế {th:,.0f} − CK {ck:,.0f} = {ch+th-ck:,.0f} ≠ tổng {tt:,.0f}")
    else:
        add("Số học tổng tiền", OK, f"khớp ({ch:,.0f} + {th:,.0f} − {ck:,.0f} = {tt:,.0f})")

    # 5) Trạng thái người bán (NNT) - nếu đã tra cứu online
    if seller_active is True:
        add("Người bán đang hoạt động", OK, seller_status_text or "NNT đang hoạt động")
    elif seller_active is False:
        add("Người bán đang hoạt động", FAIL,
            seller_status_text or "NNT NGỪNG hoạt động / bỏ địa chỉ - RỦI RO CAO")
    else:
        add("Người bán đang hoạt động", NA, "Chưa tra cứu online (dùng '🏢 Kiểm tra NCC' để chấm mục này)")

    # ------ tổng hợp mức rủi ro
    n_fail = sum(1 for it in items if it["trang_thai"] == FAIL)
    n_warn = sum(1 for it in items if it["trang_thai"] == WARN)
    if n_fail:
        level = "Cao"
    elif n_warn >= 2:
        level = "Vừa"
    elif n_warn == 1:
        level = "Thấp"
    else:
        level = "OK"
    return {"level": level, "n_fail": n_fail, "n_warn": n_warn, "items": items}


def summarize(results: list[dict]) -> dict:
    """Đếm số HĐ theo mức rủi ro cho dòng tổng."""
    out = {"Cao": 0, "Vừa": 0, "Thấp": 0, "OK": 0}
    for r in results:
        out[r.get("level", "OK")] = out.get(r.get("level", "OK"), 0) + 1
    return out
