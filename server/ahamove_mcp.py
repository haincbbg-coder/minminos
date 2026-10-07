"""Cầu nối Ahamove Partner API v3 (transport "internal"). Mỗi kết nối = MỘT tài khoản Ahamove.

Gọi API (đối chiếu developers.ahamove.com, mục API Reference):
  host  = https://partner-api.ahamove.com/v3 (môi trường thử: https://partner-apistg.ahamove.com/v3)
  lấy token: POST /accounts/token {mobile, api_key} -> {token (JWT), refresh_token}
  mọi API khác: header Authorization: Bearer <token>, Content-Type JSON
  lỗi trả về bằng mã HTTP (400, 401, 404, 406...).

Token được lưu (đã mã hoá) vào kết nối kèm mốc hết hạn đọc từ trường exp của JWT và dấu của
tài khoản; hết hạn, đổi tài khoản, hoặc bị trả 401 thì lấy token lại ĐÚNG MỘT lần rồi gọi lại.

Đọc: thành phố hoạt động, dịch vụ theo thành phố, ước tính phí, chi tiết đơn, đơn theo mã vận đơn.
Ghi (NGUY HIỂM, tốn tiền thật): tạo đơn, hủy đơn. Đầu vào kiểm chặt trước khi gọi mạng.
"""
import base64
import hashlib
import json
import re
import time

import ket_noi_api as k

HOST_LIVE = "https://partner-api.ahamove.com/v3"
HOST_TEST = "https://partner-apistg.ahamove.com/v3"
TEN = "Ahamove"
COD_TOI_DA = 50_000_000
TOKEN_MAC_DINH = 12 * 3600
DIEM_TOI_DA = 10
THANH_TOAN = ["CASH", "CASH_BY_RECIPIENT", "BALANCE"]
_MA_DON = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_MA_DV = re.compile(r"^[A-Z0-9_-]{2,40}$")
_MA_TP = re.compile(r"^[A-Z0-9]{2,10}$")

_DIEM = {"type": "array", "items": {"type": "object"},
         "description": "2 đến 10 điểm, điểm đầu là nơi lấy hàng: [{address, name, mobile, lat?, lng?, "
                        "short_address?, cod?, item_value?, tracking_number?, remarks?}]"}

TOOLS = [
    k.tool("aha_thanh_pho", "Danh sách thành phố Ahamove đang hoạt động kèm city_id (ví dụ SGN, HAN)."),
    k.tool("aha_dich_vu", "Danh sách dịch vụ Ahamove khả dụng theo thành phố (city_id) hoặc theo toạ độ lat, lng.",
           {"city_id": {"type": "string", "description": "mã thành phố, ví dụ SGN"},
            "lat": {"type": "number"}, "lng": {"type": "number"},
            "delivery_type": {"type": "string", "description": "lọc loại giao, ví dụ INSTANT"}}),
    k.tool("aha_uoc_tinh_phi", "Ước tính phí giao hàng Ahamove cho một hoặc nhiều dịch vụ (không tạo đơn).",
           {"path": _DIEM,
            "services": {"type": "array", "items": {"type": "string"},
                         "description": "các mã dịch vụ, ví dụ [\"SGN-BIKE\"] (lấy từ aha_dich_vu)"},
            "payment_method": {"type": "string", "enum": THANH_TOAN, "description": "mặc định CASH"},
            "order_time": {"type": "integer", "description": "giờ hẹn lấy hàng (unix giây), 0 = giao ngay"},
            "promo_code": {"type": "string"}},
           ["path", "services"]),
    k.tool("aha_chi_tiet_don", "Chi tiết và trạng thái một đơn Ahamove theo order_id.",
           {"order_id": {"type": "string", "description": "mã đơn Ahamove"}}, ["order_id"]),
    k.tool("aha_don_theo_ma_van_don", "Các đơn Ahamove gắn với một mã vận đơn (tracking_number) của shop.",
           {"tracking_number": {"type": "string"}}, ["tracking_number"]),
    k.tool("aha_tao_don",
           "TẠO ĐƠN GIAO HÀNG THẬT trên Ahamove (gọi tài xế, phát sinh phí, không hoàn tác được). Chỉ gọi khi chủ "
           "shop đã xác nhận điểm lấy, điểm giao, dịch vụ và tiền thu hộ.",
           {"path": _DIEM,
            "service_id": {"type": "string", "description": "mã dịch vụ, ví dụ SGN-BIKE"},
            "payment_method": {"type": "string", "enum": THANH_TOAN,
                               "description": "CASH = người gửi trả tiền mặt, CASH_BY_RECIPIENT = người nhận trả, "
                                              "BALANCE = trừ ví tài khoản"},
            "order_time": {"type": "integer", "description": "giờ hẹn lấy hàng (unix giây), 0 = giao ngay"},
            "requests": {"type": "array", "items": {"type": "object"},
                         "description": "yêu cầu đặc biệt [{_id, num?, tier_code?}]"},
            "remarks": {"type": "string"}, "promo_code": {"type": "string"},
            "items": {"type": "array", "items": {"type": "object"}, "description": "[{_id?, name, num, price}]"}},
           ["path", "service_id", "payment_method"]),
    k.tool("aha_huy_don", "HỦY ĐƠN AHAMOVE THẬT (không hoàn tác được) theo order_id. Đơn đã có tài xế nhận cần lý do.",
           {"order_id": {"type": "string"}, "ly_do": {"type": "string", "description": "lý do hủy"}},
           ["order_id"]),
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
    return n if nho <= n <= lon and n == n else None


def _chuoi(v, toi_da=255):
    s = str(v if v is not None else "").strip()
    return s if 0 < len(s) <= toi_da else None


def _sdt(v):
    s = re.sub(r"[\s.\-+]", "", str(v or ""))
    return s if re.fullmatch(r"\d{9,12}", s) else None


def _dau_tk(sec):
    raw = f"{sec.get('api_key', '')}\n{sec.get('mobile', '')}\n{host(sec)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _het_han_jwt(tok):
    """Mốc exp (unix giây) trong phần payload của JWT, không kiểm chữ ký. Không đọc được thì None."""
    try:
        phan = tok.split(".")[1]
        phan += "=" * (-len(phan) % 4)
        exp = json.loads(base64.urlsafe_b64decode(phan.encode()).decode()).get("exp")
        return float(exp) if exp else None
    except Exception:
        return None


def _ma_http(loi):
    m = re.match(rf"ERROR: {TEN} (\d{{3}}):", str(loi))
    return int(m.group(1)) if m else None


async def _lay_token(spec):
    sec = k.bi_mat(spec)
    ok, d = await k.goi(TEN, "POST", host(sec) + "/accounts/token", secrets=sec,
                        json_body={"mobile": str(sec["mobile"]).strip(), "api_key": str(sec["api_key"]).strip()},
                        headers={"Content-Type": "application/json"})
    if not ok:
        return d
    tok = str(d.get("token") or "") if isinstance(d, dict) else ""
    if not tok:
        return "ERROR: Ahamove không cấp token, kiểm tra API key và số điện thoại tài khoản"
    het = _het_han_jwt(tok)
    if not het or het <= time.time() + 120:
        het = time.time() + TOKEN_MAC_DINH
    k.luu_bi_mat(spec, {"access_token": tok, "token_het_han": int(het), "token_tk": _dau_tk(sec)})
    return None


async def _token(spec, cu=None):
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        tok = str(sec.get("access_token") or "")
        if tok and tok != cu and k.con_han(sec, "token_het_han") and sec.get("token_tk") == _dau_tk(sec):
            return tok, None
        loi = await _lay_token(spec)
        if loi:
            return None, loi
        return str(k.bi_mat(spec).get("access_token") or ""), None


async def _goi(spec, method, path, *, params=None, body=None):
    tok, loi = await _token(spec)
    if loi:
        return False, loi
    for lan in range(2):
        sec = {**k.bi_mat(spec), "access_token": tok}
        h = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
        ok, d = await k.goi(TEN, method, host(sec) + path, secrets=sec, params=params, json_body=body, headers=h)
        if ok:
            return True, d
        if _ma_http(d) == 401 and lan == 0:
            tok, loi = await _token(spec, cu=tok)
            if loi:
                return False, loi
            continue
        return False, d
    return False, d


def _duong_di(raw):
    """Kiểm tra danh sách điểm. Trả (path, lỗi)."""
    if not isinstance(raw, list) or not 2 <= len(raw) <= DIEM_TOI_DA:
        return None, f"path phải là danh sách 2 đến {DIEM_TOI_DA} điểm, điểm đầu là nơi lấy hàng"
    ra, loi = [], []
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            loi.append(f"path[{i}] không đúng dạng")
            continue
        dc, ten, sdt = _chuoi(p.get("address"), 500), _chuoi(p.get("name"), 100), _sdt(p.get("mobile"))
        if not dc or not ten or not sdt:
            loi.append(f"path[{i}] cần address, name và mobile (9 đến 12 chữ số)")
            continue
        diem = {"address": dc, "name": ten, "mobile": sdt}
        if p.get("lat") not in (None, "") or p.get("lng") not in (None, ""):
            lat, lng = _so_thuc(p.get("lat"), -90, 90), _so_thuc(p.get("lng"), -180, 180)
            if lat is None or lng is None:
                loi.append(f"path[{i}] lat/lng sai")
                continue
            diem.update({"lat": lat, "lng": lng})
        for kk, kt in (("short_address", 200), ("remarks", 500)):
            if p.get(kk) not in (None, ""):
                v = _chuoi(p.get(kk), kt)
                if v is None:
                    loi.append(f"path[{i}].{kk} quá dài")
                diem[kk] = v
        for kk in ("cod", "item_value"):
            if p.get(kk) not in (None, ""):
                v = _so_nguyen(p.get(kk), 0, COD_TOI_DA)
                if v is None:
                    loi.append(f"path[{i}].{kk} phải từ 0 đến 50.000.000 đồng")
                diem[kk] = v
        if p.get("tracking_number") not in (None, ""):
            v = str(p.get("tracking_number")).strip()
            if not _MA_DON.match(v):
                loi.append(f"path[{i}].tracking_number chỉ gồm chữ, số, _ và -")
            diem["tracking_number"] = v
        if i == 0 and diem.get("cod"):
            loi.append("path[0] là nơi lấy hàng, không đặt cod ở đây")
        ra.append(diem)
    return (None, "; ".join(loi)) if loi else (ra, None)


def _gio(v):
    """order_time: 0 = ngay, hoặc unix giây trong 7 ngày tới."""
    if v in (None, ""):
        return 0
    n = _so_nguyen(v, 0, 10**11)
    if n is None:
        return None
    if n == 0:
        return 0
    return n if time.time() - 300 <= n <= time.time() + 7 * 86400 else None


def _yeu_cau(raw):
    if raw in (None, ""):
        return [], None
    if not isinstance(raw, list) or len(raw) > 20:
        return None, "requests phải là danh sách tối đa 20 yêu cầu"
    ra = []
    for i, r in enumerate(raw):
        ma = str((r or {}).get("_id") or "").strip().upper() if isinstance(r, dict) else ""
        if not _MA_DV.match(ma):
            return None, f"requests[{i}]._id không hợp lệ"
        y = {"_id": ma}
        if r.get("num") not in (None, ""):
            n = _so_nguyen(r.get("num"), 1, 100)
            if n is None:
                return None, f"requests[{i}].num phải từ 1 đến 100"
            y["num"] = n
        if r.get("tier_code") not in (None, ""):
            t = str(r.get("tier_code")).strip().upper()
            if not re.fullmatch(r"[A-Z0-9_]{1,20}", t):
                return None, f"requests[{i}].tier_code không hợp lệ"
            y["tier_code"] = t
        ra.append(y)
    return ra, None


def _don_tao(a):
    loi = []
    path, e = _duong_di(a.get("path"))
    if e:
        loi.append(e)
    sv = str(a.get("service_id") or "").strip().upper()
    if not _MA_DV.match(sv):
        loi.append("service_id (mã dịch vụ, ví dụ SGN-BIKE)")
    pm = str(a.get("payment_method") or "").strip().upper()
    if pm not in THANH_TOAN:
        loi.append("payment_method chỉ nhận " + ", ".join(THANH_TOAN))
    ot = _gio(a.get("order_time"))
    if ot is None:
        loi.append("order_time phải là 0 hoặc unix giây trong 7 ngày tới")
    req, e = _yeu_cau(a.get("requests"))
    if e:
        loi.append(e)
    body = {"order_time": ot, "path": path, "service_id": sv, "requests": req or [], "payment_method": pm}
    for kk, kt in (("remarks", 500), ("promo_code", 40)):
        if a.get(kk) not in (None, ""):
            v = _chuoi(a.get(kk), kt)
            if v is None:
                loi.append(f"{kk} quá dài")
            body[kk] = v
    if a.get("items") not in (None, ""):
        raw = a.get("items")
        if not isinstance(raw, list) or len(raw) > 100:
            loi.append("items phải là danh sách tối đa 100 món")
        else:
            items = []
            for i, it in enumerate(raw):
                if not isinstance(it, dict):
                    loi.append(f"items[{i}] không đúng dạng")
                    continue
                ten = _chuoi(it.get("name"), 200)
                num = _so_nguyen(it.get("num"), 1, 10000)
                gia = _so_nguyen(it.get("price") if it.get("price") not in (None, "") else 0, 0, 10**9)
                if not ten or num is None or gia is None:
                    loi.append(f"items[{i}] cần name, num 1 đến 10000 và price không âm")
                    continue
                mon = {"_id": str(it.get("_id") or f"SP{i + 1}")[:40], "name": ten, "num": num, "price": gia}
                items.append(mon)
            body["items"] = items
    if loi:
        return None, "ERROR: không tạo đơn Ahamove vì đầu vào sai: " + "; ".join(loi)
    return body, None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "api_key", "mobile")
    if t:
        return "ERROR: kết nối Ahamove thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "aha_thanh_pho":
        ok, d = await _goi(spec, "GET", "/cities", params={"country_id": "VN"})
    elif tool == "aha_dich_vu":
        p = {}
        if a.get("city_id") not in (None, ""):
            ma = str(a.get("city_id")).strip().upper()
            if not _MA_TP.match(ma):
                return "ERROR: city_id chỉ gồm chữ in hoa và số, ví dụ SGN"
            p["city_id"] = ma
        elif a.get("lat") not in (None, "") and a.get("lng") not in (None, ""):
            lat, lng = _so_thuc(a.get("lat"), -90, 90), _so_thuc(a.get("lng"), -180, 180)
            if lat is None or lng is None:
                return "ERROR: lat/lng sai"
            p.update({"lat": lat, "lng": lng})
        else:
            return "ERROR: cần city_id (ví dụ SGN) hoặc cặp lat, lng"
        if a.get("delivery_type") not in (None, ""):
            dt = str(a.get("delivery_type")).strip().upper()
            if not re.fullmatch(r"[A-Z_]{1,20}", dt):
                return "ERROR: delivery_type không hợp lệ"
            p["delivery_type"] = dt
        ok, d = await _goi(spec, "GET", "/services", params=p)
    elif tool == "aha_uoc_tinh_phi":
        path, loi = _duong_di(a.get("path"))
        if loi:
            return "ERROR: " + loi
        dv = [x.upper() for x in k.ds(a.get("services"))]
        if not dv or len(dv) > 10 or not all(_MA_DV.match(x) for x in dv):
            return "ERROR: services phải là 1 đến 10 mã dịch vụ, ví dụ SGN-BIKE"
        pm = str(a.get("payment_method") or "CASH").strip().upper()
        if pm not in THANH_TOAN:
            return "ERROR: payment_method chỉ nhận " + ", ".join(THANH_TOAN)
        ot = _gio(a.get("order_time"))
        if ot is None:
            return "ERROR: order_time phải là 0 hoặc unix giây trong 7 ngày tới"
        body = {"order_time": ot, "path": path, "services": [{"_id": x, "requests": []} for x in dv],
                "payment_method": pm}
        if a.get("promo_code") not in (None, ""):
            v = _chuoi(a.get("promo_code"), 40)
            if v is None:
                return "ERROR: promo_code quá dài"
            body["promo_code"] = v
        ok, d = await _goi(spec, "POST", "/orders/estimates", body=body)
    elif tool == "aha_chi_tiet_don":
        ma = str(a.get("order_id") or "").strip()
        if not _MA_DON.match(ma):
            return "ERROR: order_id chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        ok, d = await _goi(spec, "GET", "/orders/" + ma)
    elif tool == "aha_don_theo_ma_van_don":
        ma = str(a.get("tracking_number") or "").strip()
        if not _MA_DON.match(ma):
            return "ERROR: tracking_number chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        ok, d = await _goi(spec, "GET", "/orders/tracks/" + ma)
    elif tool == "aha_tao_don":
        body, loi = _don_tao(a)
        if loi:
            return loi
        ok, d = await _goi(spec, "POST", "/orders", body=body)
    elif tool == "aha_huy_don":
        ma = str(a.get("order_id") or "").strip()
        if not _MA_DON.match(ma):
            return "ERROR: order_id chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        ly_do = str(a.get("ly_do") or "").strip()
        if len(ly_do) > 500:
            return "ERROR: ly_do quá dài (tối đa 500 ký tự)"
        ok, d = await _goi(spec, "DELETE", "/orders/" + ma, body={"comment": ly_do or "Shop hủy đơn"})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Ahamove"
    return k.giau(k.json_ra(d), k.bi_mat(spec)) if ok else d
