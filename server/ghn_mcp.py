"""Cầu nối Giao Hàng Nhanh (GHN) public API (transport "internal"). Mỗi kết nối = MỘT tài khoản GHN.

Một token GHN quản lý được nhiều cửa hàng (shop). Kết nối có ô `shop_id` làm cửa hàng mặc định;
từng lượt gọi có thể truyền `shop_id` để dùng cửa hàng khác của cùng tài khoản.

Gọi API:
  host  = https://online-gateway.ghn.vn/shiip/public-api (môi trường test: dev-online-gateway...)
  header Token: <token>, ShopId: <mã cửa hàng> (với API theo cửa hàng), Content-Type JSON
  trả về {code: 200, message, data}; code khác 200 là lỗi.

Đọc: danh sách cửa hàng, tỉnh/quận/phường, dịch vụ khả dụng, tính phí, chi tiết đơn.
Ghi (NGUY HIỂM, tốn tiền thật): tạo đơn, hủy đơn. Đầu vào được kiểm tra chặt TRƯỚC khi gọi mạng.
"""
import re

import ket_noi_api as k

HOST_LIVE = "https://online-gateway.ghn.vn/shiip/public-api"
HOST_TEST = "https://dev-online-gateway.ghn.vn/shiip/public-api"
TEN = "GHN"
GHI_CHU = ["CHOTHUHANG", "CHOXEMHANGKHONGTHU", "KHONGCHOXEMHANG"]
_MA_DON = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_SO = re.compile(r"^\d{1,12}$")
COD_TOI_DA = 50_000_000
KHOI_LUONG_TOI_DA = 50_000
HUY_TOI_DA = 20

_SHOP_PROP = {"shop_id": {"type": "string", "description": "mã cửa hàng GHN, bỏ trống thì dùng cửa hàng mặc định của kết nối"}}

TOOLS = [
    k.tool("ghn_danh_sach_shop", "Danh sách cửa hàng (shop) thuộc tài khoản GHN: mã, tên, địa chỉ, quận.",
           {"offset": {"type": "integer", "description": "bỏ qua bao nhiêu cửa hàng đầu"},
            "limit": {"type": "integer", "description": "số cửa hàng mỗi trang, tối đa 200"}}),
    k.tool("ghn_tinh_thanh", "Danh sách tỉnh/thành theo mã GHN (ProvinceID)."),
    k.tool("ghn_quan_huyen", "Danh sách quận/huyện của một tỉnh theo mã GHN (DistrictID).",
           {"province_id": {"type": "integer", "description": "mã tỉnh GHN"}}, ["province_id"]),
    k.tool("ghn_phuong_xa", "Danh sách phường/xã của một quận theo mã GHN (WardCode).",
           {"district_id": {"type": "integer", "description": "mã quận GHN"}}, ["district_id"]),
    k.tool("ghn_dich_vu", "Các dịch vụ giao hàng khả dụng giữa hai quận (service_id, service_type_id).",
           {**_SHOP_PROP,
            "from_district": {"type": "integer", "description": "mã quận gửi"},
            "to_district": {"type": "integer", "description": "mã quận nhận"}},
           ["from_district", "to_district"]),
    k.tool("ghn_tinh_phi", "Tính phí giao hàng dự kiến (không tạo đơn). Cần service_type_id hoặc service_id.",
           {**_SHOP_PROP,
            "service_type_id": {"type": "integer", "description": "loại dịch vụ, 2 = hàng nhẹ"},
            "service_id": {"type": "integer", "description": "mã dịch vụ cụ thể (lấy từ ghn_dich_vu)"},
            "from_district_id": {"type": "integer", "description": "mã quận gửi, bỏ trống thì theo cửa hàng"},
            "to_district_id": {"type": "integer"},
            "to_ward_code": {"type": "string"},
            "weight": {"type": "integer", "description": "khối lượng gram"},
            "length": {"type": "integer", "description": "cm"}, "width": {"type": "integer", "description": "cm"},
            "height": {"type": "integer", "description": "cm"},
            "insurance_value": {"type": "integer", "description": "giá trị khai giá (đồng)"}},
           ["to_district_id", "to_ward_code", "weight"]),
    k.tool("ghn_chi_tiet_don", "Chi tiết và trạng thái một đơn GHN theo mã vận đơn.",
           {**_SHOP_PROP, "order_code": {"type": "string", "description": "mã vận đơn GHN"}}, ["order_code"]),
    k.tool("ghn_chi_tiet_don_theo_ma_khach", "Chi tiết đơn GHN theo mã đơn riêng của shop (client_order_code).",
           {**_SHOP_PROP, "client_order_code": {"type": "string"}}, ["client_order_code"]),
    k.tool("ghn_tao_don",
           "TẠO ĐƠN GIAO HÀNG THẬT trên GHN (phát sinh phí, không hoàn tác được). Chỉ gọi khi chủ shop đã xác nhận "
           "đủ thông tin người nhận, khối lượng, tiền thu hộ.",
           {**_SHOP_PROP,
            "to_name": {"type": "string"}, "to_phone": {"type": "string", "description": "9 đến 11 chữ số"},
            "to_address": {"type": "string"}, "to_ward_code": {"type": "string"},
            "to_district_id": {"type": "integer"},
            "weight": {"type": "integer", "description": "gram, 1 đến 50000"},
            "length": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"},
            "service_type_id": {"type": "integer", "description": "mặc định 2 (hàng nhẹ)"},
            "service_id": {"type": "integer"},
            "payment_type_id": {"type": "integer", "enum": [1, 2], "description": "1 = shop trả phí, 2 = người nhận trả (mặc định)"},
            "required_note": {"type": "string", "enum": GHI_CHU, "description": "mặc định KHONGCHOXEMHANG"},
            "items": {"type": "array", "description": "[{name, quantity, weight?}]",
                      "items": {"type": "object"}},
            "cod_amount": {"type": "integer", "description": "tiền thu hộ, 0 đến 50.000.000"},
            "insurance_value": {"type": "integer"},
            "content": {"type": "string"}, "note": {"type": "string"},
            "client_order_code": {"type": "string"}},
           ["to_name", "to_phone", "to_address", "to_ward_code", "to_district_id", "weight", "items"]),
    k.tool("ghn_huy_don", "HỦY ĐƠN GHN THẬT (không hoàn tác được). Tối đa 20 mã vận đơn mỗi lần.",
           {**_SHOP_PROP, "order_codes": {"type": "array", "items": {"type": "string"}}}, ["order_codes"]),
]


async def list_tools(spec):
    return TOOLS


def host(sec):
    return HOST_TEST if str(sec.get("moi_truong") or "").strip().lower() == "test" else HOST_LIVE


def _so_nguyen(v, nho, lon):
    """Số nguyên trong [nho, lon] hoặc None. Không chấp nhận bool, số lẻ, chuỗi rác."""
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


def _mac_dinh(v, md):
    return md if v is None or (isinstance(v, str) and not v.strip()) else v


def _chuoi(v, toi_da=255):
    s = str(v if v is not None else "").strip()
    return s if 0 < len(s) <= toi_da else None


def _sdt(v):
    s = re.sub(r"[\s.\-]", "", str(v or ""))
    return s if re.fullmatch(r"\d{9,11}", s) else None


def _shop(a, sec):
    """(shop_id, lỗi). Ưu tiên shop_id của lượt gọi, rồi mặc định của kết nối."""
    raw = str(a.get("shop_id") or sec.get("shop_id") or "").strip()
    if not raw:
        return None, None
    if not _SO.match(raw):
        return None, "ERROR: shop_id phải là dãy số"
    return raw, None


async def _goi(sec, method, path, *, shop=None, params=None, body=None):
    h = {"Token": str(sec["token"]).strip(), "Content-Type": "application/json"}
    if shop:
        h["ShopId"] = shop
    ok, d = await k.goi(TEN, method, host(sec) + path, secrets=sec, params=params, json_body=body, headers=h)
    if not ok:
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: GHN trả về không đúng dạng: {str(d)[:300]}", sec)
    if d.get("code") != 200:
        return False, k.giau(f"ERROR: GHN {d.get('code')}: {d.get('message', '')} {d.get('code_message', '') or ''}".strip(), sec)
    return True, d.get("data")


def _don_tao(a):
    """Kiểm tra đầu vào tạo đơn. Trả (body, lỗi)."""
    loi = []
    to_name = _chuoi(a.get("to_name"), 100)
    if not to_name:
        loi.append("to_name (tên người nhận)")
    to_phone = _sdt(a.get("to_phone"))
    if not to_phone:
        loi.append("to_phone phải là 9 đến 11 chữ số")
    to_address = _chuoi(a.get("to_address"), 500)
    if not to_address:
        loi.append("to_address (địa chỉ nhận)")
    ward = str(a.get("to_ward_code") or "").strip()
    if not re.fullmatch(r"[0-9A-Za-z]{1,20}", ward):
        loi.append("to_ward_code (mã phường GHN)")
    district = _so_nguyen(a.get("to_district_id"), 1, 10**9)
    if district is None:
        loi.append("to_district_id (mã quận GHN, số)")
    weight = _so_nguyen(a.get("weight"), 1, KHOI_LUONG_TOI_DA)
    if weight is None:
        loi.append(f"weight phải từ 1 đến {KHOI_LUONG_TOI_DA} gram")
    sti = _so_nguyen(_mac_dinh(a.get("service_type_id"), 2), 1, 100)
    if sti is None:
        loi.append("service_type_id phải là số")
    pti = _so_nguyen(_mac_dinh(a.get("payment_type_id"), 2), 1, 2)
    if pti is None:
        loi.append("payment_type_id chỉ nhận 1 (shop trả) hoặc 2 (người nhận trả)")
    note = str(a.get("required_note") or "KHONGCHOXEMHANG").strip()
    if note not in GHI_CHU:
        loi.append("required_note chỉ nhận " + ", ".join(GHI_CHU))
    cod = _so_nguyen(_mac_dinh(a.get("cod_amount"), 0), 0, COD_TOI_DA)
    if cod is None:
        loi.append(f"cod_amount phải từ 0 đến {COD_TOI_DA:,} đồng".replace(",", "."))
    items_raw = a.get("items")
    items = []
    if not isinstance(items_raw, list) or not items_raw or len(items_raw) > 100:
        loi.append("items phải là danh sách 1 đến 100 món [{name, quantity, weight?}]")
    else:
        for i, it in enumerate(items_raw):
            if not isinstance(it, dict):
                loi.append(f"items[{i}] không đúng dạng")
                continue
            ten = _chuoi(it.get("name"), 200)
            sl = _so_nguyen(it.get("quantity"), 1, 10000)
            if not ten or sl is None:
                loi.append(f"items[{i}] cần name và quantity (1 đến 10000)")
                continue
            mon = {"name": ten, "quantity": sl}
            if it.get("weight") not in (None, ""):
                w = _so_nguyen(it.get("weight"), 1, KHOI_LUONG_TOI_DA)
                if w is None:
                    loi.append(f"items[{i}].weight phải từ 1 đến {KHOI_LUONG_TOI_DA} gram")
                    continue
                mon["weight"] = w
            items.append(mon)
    body = {"to_name": to_name, "to_phone": to_phone, "to_address": to_address, "to_ward_code": ward,
            "to_district_id": district, "weight": weight, "service_type_id": sti, "payment_type_id": pti,
            "required_note": note, "cod_amount": cod, "items": items}
    for kk in ("length", "width", "height"):
        if a.get(kk) not in (None, ""):
            v = _so_nguyen(a.get(kk), 1, 200)
            if v is None:
                loi.append(f"{kk} phải từ 1 đến 200 cm")
            body[kk] = v
    if a.get("service_id") not in (None, ""):
        v = _so_nguyen(a.get("service_id"), 1, 10**9)
        if v is None:
            loi.append("service_id phải là số")
        body["service_id"] = v
    if a.get("insurance_value") not in (None, ""):
        v = _so_nguyen(a.get("insurance_value"), 0, COD_TOI_DA)
        if v is None:
            loi.append("insurance_value phải từ 0 đến 50.000.000 đồng")
        body["insurance_value"] = v
    for kk, td in (("content", 2000), ("note", 5000)):
        if a.get(kk) not in (None, ""):
            v = _chuoi(a.get(kk), td)
            if v is None:
                loi.append(f"{kk} quá dài")
            body[kk] = v
    if a.get("client_order_code") not in (None, ""):
        v = str(a.get("client_order_code")).strip()
        if not _MA_DON.match(v):
            loi.append("client_order_code chỉ gồm chữ, số, _ và -, tối đa 40 ký tự")
        body["client_order_code"] = v
    if loi:
        return None, "ERROR: không tạo đơn GHN vì đầu vào sai: " + "; ".join(loi)
    return body, None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    if k.thieu(sec, "token"):
        return "ERROR: kết nối GHN thiếu token - sửa lại ở trang Kết nối"
    a = arguments or {}
    shop, loi = _shop(a, sec)
    if loi:
        return loi

    if tool == "ghn_danh_sach_shop":
        ok, d = await _goi(sec, "GET", "/v2/shop/all", params={
            "offset": k.so(a.get("offset"), 0, 0, 1000000), "limit": k.so(a.get("limit"), 50, 1, 200)})
    elif tool == "ghn_tinh_thanh":
        ok, d = await _goi(sec, "GET", "/master-data/province")
    elif tool == "ghn_quan_huyen":
        pid = _so_nguyen(a.get("province_id"), 1, 10**9)
        if pid is None:
            return "ERROR: thiếu province_id (số)"
        ok, d = await _goi(sec, "POST", "/master-data/district", body={"province_id": pid})
    elif tool == "ghn_phuong_xa":
        did = _so_nguyen(a.get("district_id"), 1, 10**9)
        if did is None:
            return "ERROR: thiếu district_id (số)"
        ok, d = await _goi(sec, "POST", "/master-data/ward", body={"district_id": did})
    elif tool == "ghn_dich_vu":
        if not shop:
            return "ERROR: cần shop_id (truyền vào hoặc điền cửa hàng mặc định ở kết nối)"
        fd = _so_nguyen(a.get("from_district"), 1, 10**9)
        td = _so_nguyen(a.get("to_district"), 1, 10**9)
        if fd is None or td is None:
            return "ERROR: cần from_district và to_district (mã quận GHN, số)"
        ok, d = await _goi(sec, "POST", "/v2/shipping-order/available-services", shop=shop,
                           body={"shop_id": int(shop), "from_district": fd, "to_district": td})
    elif tool == "ghn_tinh_phi":
        if not shop:
            return "ERROR: cần shop_id (truyền vào hoặc điền cửa hàng mặc định ở kết nối)"
        body = {}
        sti = _so_nguyen(a.get("service_type_id"), 1, 100) if a.get("service_type_id") not in (None, "") else None
        sid = _so_nguyen(a.get("service_id"), 1, 10**9) if a.get("service_id") not in (None, "") else None
        if sti is None and sid is None:
            return "ERROR: cần service_type_id hoặc service_id (số)"
        if sti is not None:
            body["service_type_id"] = sti
        if sid is not None:
            body["service_id"] = sid
        td = _so_nguyen(a.get("to_district_id"), 1, 10**9)
        ward = str(a.get("to_ward_code") or "").strip()
        w = _so_nguyen(a.get("weight"), 1, KHOI_LUONG_TOI_DA)
        if td is None or not re.fullmatch(r"[0-9A-Za-z]{1,20}", ward) or w is None:
            return f"ERROR: cần to_district_id (số), to_ward_code và weight 1 đến {KHOI_LUONG_TOI_DA} gram"
        body.update({"to_district_id": td, "to_ward_code": ward, "weight": w})
        for kk, nho, lon in (("length", 1, 200), ("width", 1, 200), ("height", 1, 200),
                             ("insurance_value", 0, COD_TOI_DA), ("from_district_id", 1, 10**9)):
            if a.get(kk) not in (None, ""):
                v = _so_nguyen(a.get(kk), nho, lon)
                if v is None:
                    return f"ERROR: {kk} phải là số từ {nho} đến {lon}"
                body[kk] = v
        ok, d = await _goi(sec, "POST", "/v2/shipping-order/fee", shop=shop, body=body)
    elif tool == "ghn_chi_tiet_don":
        ma = str(a.get("order_code") or "").strip()
        if not _MA_DON.match(ma):
            return "ERROR: order_code chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        ok, d = await _goi(sec, "POST", "/v2/shipping-order/detail", shop=shop, body={"order_code": ma})
    elif tool == "ghn_chi_tiet_don_theo_ma_khach":
        ma = str(a.get("client_order_code") or "").strip()
        if not _MA_DON.match(ma):
            return "ERROR: client_order_code chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        ok, d = await _goi(sec, "POST", "/v2/shipping-order/detail-by-client-code", shop=shop,
                           body={"client_order_code": ma})
    elif tool == "ghn_tao_don":
        if not shop:
            return "ERROR: cần shop_id (truyền vào hoặc điền cửa hàng mặc định ở kết nối)"
        body, loi = _don_tao(a)
        if loi:
            return loi
        ok, d = await _goi(sec, "POST", "/v2/shipping-order/create", shop=shop, body=body)
    elif tool == "ghn_huy_don":
        if not shop:
            return "ERROR: cần shop_id (truyền vào hoặc điền cửa hàng mặc định ở kết nối)"
        ma = k.ds(a.get("order_codes"))
        if not ma:
            return "ERROR: thiếu order_codes"
        if len(ma) > HUY_TOI_DA:
            return f"ERROR: chỉ hủy tối đa {HUY_TOI_DA} đơn mỗi lần"
        sai = [m for m in ma if not _MA_DON.match(m)]
        if sai:
            return "ERROR: mã vận đơn không hợp lệ (chỉ chữ, số, _ và -): " + ", ".join(s[:40] for s in sai[:5])
        ok, d = await _goi(sec, "POST", "/v2/switch-status/cancel", shop=shop, body={"order_codes": ma})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối GHN"
    return k.json_ra(d) if ok else d
