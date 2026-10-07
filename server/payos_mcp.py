"""Cầu nối payOS (transport "internal"). Mỗi kết nối = MỘT kênh thanh toán payOS.

payOS tạo link thanh toán kèm mã VietQR, tiền khách chuyển vào thẳng tài khoản ngân hàng của kênh.
Mỗi kênh thanh toán có bộ Client ID / API Key / Checksum Key riêng, nên nhiều kênh (nhiều tài
khoản nhận tiền) = nhiều kết nối.

API (payos.vn/docs):
  base    https://api-merchant.payos.vn
  header  x-client-id, x-api-key
  POST /v2/payment-requests               tạo link (body có `signature`)
  GET  /v2/payment-requests/{id}          id = orderCode hoặc paymentLinkId
  POST /v2/payment-requests/{id}/cancel   {cancellationReason}
Trả về {code: "00", desc, data, signature}. code khác "00" là lỗi.

Chữ ký yêu cầu tạo link:
  HMAC-SHA256(checksum_key,
    "amount=..&cancelUrl=..&description=..&orderCode=..&returnUrl=..")  dạng hex thường
Chữ ký phản hồi (kiểm tra khi tạo link, để chắc dữ liệu đúng là payOS trả về, nhất là checkoutUrl
mà MinMin sẽ đưa cho khách):
  các trường của `data` xếp theo tên, nối "tên=giá_trị" bằng "&"; None thành ""; list/dict thành
  JSON gọn (không khoảng trắng, khoá trong object xếp theo tên); bool thành true/false.

MỨC NGUY HIỂM: payos_tao_link tạo một yêu cầu thanh toán THẬT mà khách trả tiền được, payos_huy_link
huỷ link đang chờ trả. Cả hai được xếp "danger" trong catalog. payos_xem_link chỉ đọc.
"""
import hashlib
import hmac
import json
import re
import time

import ket_noi_api as k

HOST = "https://api-merchant.payos.vn"
TEN = "payOS"
MA_DON_TOI_DA = 9007199254740991      # Number.MAX_SAFE_INTEGER, giới hạn của payOS
TIEN_TOI_THIEU = 1000
TIEN_TOI_DA = 500_000_000
MO_TA_TOI_DA = 25
_ID = re.compile(r"^[A-Za-z0-9]{1,64}$")
_LOCAL = ("http://localhost", "http://127.0.0.1")

TOOLS = [
    k.tool("payos_tao_link",
           "Tạo link thanh toán payOS THẬT (kèm mã VietQR) để gửi khách chuyển khoản. Trả checkoutUrl, "
           "qrCode, paymentLinkId, orderCode.",
           {"amount": {"type": "integer", "description": f"số tiền VND, từ {TIEN_TOI_THIEU:,} đến {TIEN_TOI_DA:,}"},
            "description": {"type": "string",
                            "description": f"nội dung chuyển khoản, tối đa {MO_TA_TOI_DA} ký tự (tài khoản ngân hàng "
                                           "không liên kết qua payOS chỉ nhận 9 ký tự)"},
            "orderCode": {"type": "integer", "description": "mã đơn (số nguyên dương, không trùng). Bỏ trống để MinMin tự sinh"},
            "returnUrl": {"type": "string", "description": "trang chuyển về khi trả xong (mặc định lấy từ kết nối)"},
            "cancelUrl": {"type": "string", "description": "trang chuyển về khi khách huỷ (mặc định lấy từ kết nối)"},
            "items": {"type": "array", "description": "danh sách món: [{name, quantity, price}]",
                      "items": {"type": "object"}},
            "buyerName": {"type": "string"}, "buyerPhone": {"type": "string"},
            "expiredAt": {"type": "integer", "description": "hết hạn lúc (unix giây)"}},
           ["amount", "description"]),
    k.tool("payos_xem_link",
           "Xem trạng thái 1 link thanh toán (PENDING, PAID, CANCELLED...), số tiền đã trả và các giao dịch.",
           {"id": {"type": "string", "description": "orderCode hoặc paymentLinkId"}}, ["id"]),
    k.tool("payos_huy_link",
           "Huỷ 1 link thanh toán đang chờ trả, khách sẽ không trả được nữa.",
           {"id": {"type": "string", "description": "orderCode hoặc paymentLinkId"},
            "cancellationReason": {"type": "string", "description": "lý do huỷ (không bắt buộc)"}},
           ["id"]),
]


async def list_tools(spec):
    return TOOLS


def _hmac(key, chuoi):
    return hmac.new(str(key).encode("utf-8"), chuoi.encode("utf-8"), hashlib.sha256).hexdigest()


def ky_tao_link(checksum_key, amount, cancel_url, description, order_code, return_url):
    return _hmac(checksum_key, f"amount={amount}&cancelUrl={cancel_url}&description={description}"
                               f"&orderCode={order_code}&returnUrl={return_url}")


def _sap_xep(v):
    if isinstance(v, dict):
        return {kk: _sap_xep(v[kk]) for kk in sorted(v)}
    if isinstance(v, list):
        return [_sap_xep(x) for x in v]
    return v


def _gia_tri(v):
    if v is None or v in ("null", "undefined"):
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, dict)):
        return json.dumps(_sap_xep(v), ensure_ascii=False, separators=(",", ":"))
    return str(v)


def chuoi_du_lieu(data):
    return "&".join(f"{kk}={_gia_tri(data[kk])}" for kk in sorted(data))


def ky_du_lieu(checksum_key, data):
    return _hmac(checksum_key, chuoi_du_lieu(data))


def chu_ky_dung(checksum_key, data, signature):
    if not isinstance(data, dict) or not isinstance(signature, str) or not signature:
        return False
    return hmac.compare_digest(ky_du_lieu(checksum_key, data), signature.strip().lower())


def _url_hop_le(u):
    return u.startswith("https://") or any(u == p or u.startswith(p + ":") or u.startswith(p + "/") for p in _LOCAL)


def _so_nguyen(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    s = str(v if v is not None else "").strip()
    return int(s) if s.isdigit() else None


def _headers(sec):
    return {"x-client-id": sec["client_id"], "x-api-key": sec["api_key"], "Content-Type": "application/json"}


async def _goi(sec, method, path, body=None):
    ok, d = await k.goi(TEN, method, f"{HOST}{path}", secrets=sec, json_body=body, headers=_headers(sec))
    if not ok:
        return False, d, None
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: payOS trả về không đúng dạng: {str(d)[:300]}", sec), None
    if str(d.get("code")) != "00":
        return False, k.giau(f"ERROR: payOS {d.get('code')}: {d.get('desc', '')}", sec), None
    return True, d.get("data"), d.get("signature")


def _dung_body_tao(a, sec):
    """Kiểm tra đầu vào, dựng body chưa ký. Trả (body, None) hoặc (None, câu lỗi). Không gọi mạng."""
    amount = _so_nguyen(a.get("amount"))
    if amount is None or not TIEN_TOI_THIEU <= amount <= TIEN_TOI_DA:
        return None, f"ERROR: amount phải là số nguyên VND từ {TIEN_TOI_THIEU:,} đến {TIEN_TOI_DA:,}"
    mo_ta = str(a.get("description") or "").strip()
    if not mo_ta:
        return None, "ERROR: thiếu description (nội dung chuyển khoản, payOS bắt buộc)"
    if len(mo_ta) > MO_TA_TOI_DA:
        return None, f"ERROR: description tối đa {MO_TA_TOI_DA} ký tự (đang {len(mo_ta)})"
    if a.get("orderCode") not in (None, ""):
        ma = _so_nguyen(a.get("orderCode"))
        if ma is None or not 1 <= ma <= MA_DON_TOI_DA:
            return None, f"ERROR: orderCode phải là số nguyên dương, tối đa {MA_DON_TOI_DA}"
    else:
        ma = int(time.time() * 1000) % 10 ** 12 or 1
    ru = str(a.get("returnUrl") or sec.get("return_url") or "").strip()
    cu = str(a.get("cancelUrl") or sec.get("cancel_url") or "").strip()
    for ten, u in (("returnUrl", ru), ("cancelUrl", cu)):
        if not u:
            return None, (f"ERROR: thiếu {ten}. Truyền vào tool hoặc điền "
                          f"{'return_url' if ten == 'returnUrl' else 'cancel_url'} mặc định trong kết nối")
        if not _url_hop_le(u):
            return None, f"ERROR: {ten} phải bắt đầu bằng https:// (hoặc http://localhost khi thử)"
    body = {"orderCode": ma, "amount": amount, "description": mo_ta, "returnUrl": ru, "cancelUrl": cu}
    items = a.get("items")
    if items not in (None, "", []):
        if not isinstance(items, list):
            return None, "ERROR: items phải là danh sách [{name, quantity, price}]"
        sach = []
        for it in items[:100]:
            if not isinstance(it, dict) or not str(it.get("name") or "").strip():
                return None, "ERROR: mỗi món trong items cần name, quantity, price"
            sl, gia = _so_nguyen(it.get("quantity", 1)), _so_nguyen(it.get("price", 0))
            if sl is None or sl < 1 or gia is None:
                return None, "ERROR: quantity phải là số nguyên >= 1, price là số nguyên VND"
            sach.append({"name": str(it["name"]).strip()[:255], "quantity": sl, "price": gia})
        body["items"] = sach
    for key in ("buyerName", "buyerPhone"):
        v = str(a.get(key) or "").strip()
        if v:
            body[key] = v[:255]
    if a.get("expiredAt") not in (None, ""):
        het = _so_nguyen(a.get("expiredAt"))
        if het is None or het <= int(time.time()) or het > 2 ** 31 - 1:
            return None, "ERROR: expiredAt phải là mốc unix giây trong tương lai"
        body["expiredAt"] = het
    return body, None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "client_id", "api_key", "checksum_key")
    if t:
        return "ERROR: kết nối payOS thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    for key in ("client_id", "api_key", "checksum_key"):
        sec[key] = str(sec[key]).strip()
    a = arguments or {}

    if tool == "payos_tao_link":
        body, loi = _dung_body_tao(a, sec)
        if loi:
            return loi
        body["signature"] = ky_tao_link(sec["checksum_key"], body["amount"], body["cancelUrl"],
                                        body["description"], body["orderCode"], body["returnUrl"])
        ok, d, sig = await _goi(sec, "POST", "/v2/payment-requests", body)
        if not ok:
            return d
        if d is not None and not chu_ky_dung(sec["checksum_key"], d, sig):
            return ("ERROR: chữ ký phản hồi không khớp. Dữ liệu trả về có thể đã bị sửa trên đường "
                    "truyền hoặc Checksum Key trong kết nối không đúng kênh thanh toán; KHÔNG gửi link này cho khách.")
        return k.json_ra(d)

    if tool in ("payos_xem_link", "payos_huy_link"):
        ma = str(a.get("id") or "").strip()
        if not _ID.match(ma):
            return "ERROR: id phải là orderCode (dãy số) hoặc paymentLinkId (chữ và số, tối đa 64 ký tự)"
        if tool == "payos_xem_link":
            ok, d, _sig = await _goi(sec, "GET", f"/v2/payment-requests/{ma}")
        else:
            ly_do = str(a.get("cancellationReason") or "").strip()[:255]
            ok, d, _sig = await _goi(sec, "POST", f"/v2/payment-requests/{ma}/cancel",
                                     {"cancellationReason": ly_do} if ly_do else {})
        return k.json_ra(d) if ok else d

    return f"ERROR: tool '{tool}' không có trong cầu nối payOS"
