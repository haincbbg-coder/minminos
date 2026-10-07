"""Cầu nối Giao Hàng Tiết Kiệm (GHTK) (transport "internal"). Mỗi kết nối = MỘT tài khoản GHTK.

Gọi API:
  host  = https://services.giaohangtietkiem.vn (môi trường test: https://services-staging.ghtklab.com)
  header Token: <API token>; thêm X-Client-Source: <mã đối tác> khi kết nối có ô ma_doi_tac
  trả về {success: true/false, message, ...}; success false là lỗi.

Đọc: tính phí, trạng thái đơn, danh sách địa chỉ lấy hàng.
Ghi (NGUY HIỂM, tốn tiền thật): tạo đơn, hủy đơn. Đầu vào được kiểm tra chặt TRƯỚC khi gọi mạng.
"""
import re

import ket_noi_api as k

HOST_LIVE = "https://services.giaohangtietkiem.vn"
HOST_TEST = "https://services-staging.ghtklab.com"
TEN = "GHTK"
COD_TOI_DA = 50_000_000
KHOI_LUONG_TOI_DA = 50_000          # gram, cho ghtk_tinh_phi
_MA = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_MA_DOI_TAC = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

TOOLS = [
    k.tool("ghtk_tinh_phi", "Tính phí giao hàng GHTK dự kiến (không tạo đơn).",
           {"pick_province": {"type": "string", "description": "tỉnh lấy hàng"},
            "pick_district": {"type": "string", "description": "quận lấy hàng"},
            "province": {"type": "string", "description": "tỉnh nhận"},
            "district": {"type": "string", "description": "quận nhận"},
            "address": {"type": "string", "description": "địa chỉ nhận chi tiết"},
            "weight": {"type": "integer", "description": "khối lượng gram"},
            "value": {"type": "integer", "description": "giá trị hàng để tính bảo hiểm (đồng)"},
            "transport": {"type": "string", "enum": ["road", "fly"]},
            "deliver_option": {"type": "string", "enum": ["none", "xteam"]}},
           ["pick_province", "pick_district", "province", "district", "weight"]),
    k.tool("ghtk_trang_thai_don", "Trạng thái một đơn GHTK theo mã vận đơn (label) hoặc mã đơn của shop.",
           {"ma_don": {"type": "string", "description": "mã vận đơn GHTK hoặc mã đơn của shop"}}, ["ma_don"]),
    k.tool("ghtk_dia_chi_lay_hang", "Danh sách địa chỉ lấy hàng đã khai trong tài khoản GHTK."),
    k.tool("ghtk_tao_don",
           "TẠO ĐƠN GIAO HÀNG THẬT trên GHTK (phát sinh phí, không hoàn tác được). Chỉ gọi khi chủ shop đã xác nhận "
           "đủ thông tin người gửi, người nhận, tiền thu hộ.",
           {"products": {"type": "array", "description": "[{name, weight (kg, số thực), quantity}]",
                         "items": {"type": "object"}},
            "order": {"type": "object",
                      "description": "{id, pick_name, pick_address, pick_province, pick_district, pick_tel, name, "
                                     "address, province, district, ward?, hamlet? (mặc định Khác), tel, pick_money "
                                     "(tiền thu hộ), value, note?, is_freeship 0|1}"}},
           ["products", "order"]),
    k.tool("ghtk_huy_don", "HỦY ĐƠN GHTK THẬT (không hoàn tác được) theo mã vận đơn, hoặc partner_id:<mã đơn shop>.",
           {"ma_don": {"type": "string"}}, ["ma_don"]),
]


async def list_tools(spec):
    return TOOLS


def host(sec):
    return HOST_TEST if str(sec.get("moi_truong") or "").strip().lower() == "test" else HOST_LIVE


def _so_nguyen(v, nho, lon):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, float):
        if not v.is_integer():
            return None
        v = int(v)
    try:
        n = int(str(v).strip())
    except ValueError:
        return None
    return n if nho <= n <= lon else None


def _so_thuc(v, nho, lon):
    if isinstance(v, bool) or v is None:
        return None
    try:
        n = float(str(v).strip())
    except ValueError:
        return None
    return n if nho <= n <= lon else None


def _mac_dinh(v, md):
    return md if v is None or (isinstance(v, str) and not v.strip()) else v


def _chuoi(v, toi_da=255):
    s = str(v if v is not None else "").strip()
    return s if 0 < len(s) <= toi_da else None


def _sdt(v):
    s = re.sub(r"[\s.\-]", "", str(v or ""))
    return s if re.fullmatch(r"\d{9,11}", s) else None


def _headers(sec):
    h = {"Token": str(sec["token"]).strip(), "Content-Type": "application/json"}
    ma = str(sec.get("ma_doi_tac") or "").strip()
    if ma:
        h["X-Client-Source"] = ma
    return h


async def _goi(sec, method, path, *, params=None, body=None):
    ok, d = await k.goi(TEN, method, host(sec) + path, secrets=sec, params=params, json_body=body,
                        headers=_headers(sec))
    if not ok:
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: GHTK trả về không đúng dạng: {str(d)[:300]}", sec)
    if d.get("success") is not True:
        return False, k.giau(f"ERROR: GHTK từ chối: {str(d.get('message', ''))[:400]}", sec)
    return True, d


def _ma_don(v, cho_partner=False):
    s = str(v or "").strip()
    if cho_partner and s.startswith("partner_id:"):
        return s if _MA.match(s[len("partner_id:"):]) else None
    return s if _MA.match(s) else None


def _don_tao(a):
    """Kiểm tra đầu vào tạo đơn. Trả (body, lỗi)."""
    loi = []
    sp_raw = a.get("products")
    products = []
    if not isinstance(sp_raw, list) or not sp_raw or len(sp_raw) > 100:
        loi.append("products phải là danh sách 1 đến 100 món [{name, weight (kg), quantity}]")
    else:
        for i, it in enumerate(sp_raw):
            if not isinstance(it, dict):
                loi.append(f"products[{i}] không đúng dạng")
                continue
            ten = _chuoi(it.get("name"), 200)
            w = _so_thuc(it.get("weight"), 0.001, 50)
            sl = _so_nguyen(it.get("quantity"), 1, 10000)
            if not ten or w is None or sl is None:
                loi.append(f"products[{i}] cần name, weight (kg, 0.001 đến 50) và quantity (1 đến 10000)")
                continue
            products.append({"name": ten, "weight": w, "quantity": sl})
    o = a.get("order")
    if not isinstance(o, dict):
        return None, "ERROR: không tạo đơn GHTK vì thiếu order (object)"
    order = {}
    oid = str(o.get("id") or "").strip()
    if not _MA.match(oid):
        loi.append("order.id (mã đơn của shop: chữ, số, . _ -, tối đa 64 ký tự)")
    order["id"] = oid
    for kk, td in (("pick_name", 100), ("pick_address", 500), ("pick_province", 100), ("pick_district", 100),
                   ("name", 100), ("address", 500), ("province", 100), ("district", 100)):
        v = _chuoi(o.get(kk), td)
        if not v:
            loi.append(f"order.{kk}")
        order[kk] = v
    for kk in ("pick_tel", "tel"):
        v = _sdt(o.get(kk))
        if not v:
            loi.append(f"order.{kk} phải là 9 đến 11 chữ số")
        order[kk] = v
    if o.get("ward") not in (None, ""):
        v = _chuoi(o.get("ward"), 100)
        if not v:
            loi.append("order.ward quá dài")
        order["ward"] = v
    order["hamlet"] = _chuoi(o.get("hamlet"), 100) or "Khác"
    pm = _so_nguyen(_mac_dinh(o.get("pick_money"), 0), 0, COD_TOI_DA)
    if pm is None:
        loi.append("order.pick_money (tiền thu hộ) phải từ 0 đến 50.000.000 đồng")
    order["pick_money"] = pm
    val = _so_nguyen(_mac_dinh(o.get("value"), 0), 0, COD_TOI_DA)
    if val is None:
        loi.append("order.value phải từ 0 đến 50.000.000 đồng")
    order["value"] = val
    fs = _so_nguyen(_mac_dinh(o.get("is_freeship"), 0), 0, 1)
    if fs is None:
        loi.append("order.is_freeship chỉ nhận 0 hoặc 1")
    order["is_freeship"] = fs
    if o.get("note") not in (None, ""):
        v = _chuoi(o.get("note"), 500)
        if not v:
            loi.append("order.note quá dài (tối đa 500 ký tự)")
        order["note"] = v
    if loi:
        return None, "ERROR: không tạo đơn GHTK vì đầu vào sai: " + "; ".join(loi)
    return {"products": products, "order": order}, None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    if k.thieu(sec, "token"):
        return "ERROR: kết nối GHTK thiếu token - sửa lại ở trang Kết nối"
    ma_dt = str(sec.get("ma_doi_tac") or "").strip()
    if ma_dt and not _MA_DOI_TAC.match(ma_dt):
        return "ERROR: mã đối tác (ma_doi_tac) chỉ gồm chữ, số, . _ - - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "ghtk_tinh_phi":
        p = {}
        for kk in ("pick_province", "pick_district", "province", "district"):
            v = _chuoi(a.get(kk), 100)
            if not v:
                return f"ERROR: thiếu {kk}"
            p[kk] = v
        w = _so_nguyen(a.get("weight"), 1, KHOI_LUONG_TOI_DA)
        if w is None:
            return f"ERROR: weight phải từ 1 đến {KHOI_LUONG_TOI_DA} gram"
        p["weight"] = w
        if a.get("address") not in (None, ""):
            v = _chuoi(a.get("address"), 500)
            if not v:
                return "ERROR: address quá dài"
            p["address"] = v
        if a.get("value") not in (None, ""):
            v = _so_nguyen(a.get("value"), 0, COD_TOI_DA)
            if v is None:
                return "ERROR: value phải từ 0 đến 50.000.000 đồng"
            p["value"] = v
        if a.get("transport") not in (None, ""):
            if a.get("transport") not in ("road", "fly"):
                return "ERROR: transport chỉ nhận road hoặc fly"
            p["transport"] = a["transport"]
        if a.get("deliver_option") not in (None, ""):
            if a.get("deliver_option") not in ("none", "xteam"):
                return "ERROR: deliver_option chỉ nhận none hoặc xteam"
            p["deliver_option"] = a["deliver_option"]
        ok, d = await _goi(sec, "GET", "/services/shipment/fee", params=p)
    elif tool == "ghtk_trang_thai_don":
        ma = _ma_don(a.get("ma_don"))
        if not ma:
            return "ERROR: ma_don chỉ gồm chữ, số, . _ -, tối đa 64 ký tự"
        ok, d = await _goi(sec, "GET", f"/services/shipment/v2/{ma}")
    elif tool == "ghtk_dia_chi_lay_hang":
        ok, d = await _goi(sec, "GET", "/services/shipment/list_pick_add")
    elif tool == "ghtk_tao_don":
        body, loi = _don_tao(a)
        if loi:
            return loi
        ok, d = await _goi(sec, "POST", "/services/shipment/order", body=body)
    elif tool == "ghtk_huy_don":
        ma = _ma_don(a.get("ma_don"), cho_partner=True)
        if not ma:
            return "ERROR: ma_don chỉ gồm chữ, số, . _ - (hoặc dạng partner_id:<mã>), tối đa 64 ký tự"
        ok, d = await _goi(sec, "POST", f"/services/shipment/cancel/{ma}")
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối GHTK"
    return k.json_ra(d) if ok else d
