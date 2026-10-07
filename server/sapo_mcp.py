"""Cầu nối Sapo Web (transport "internal"). Mỗi kết nối = MỘT cửa hàng Sapo.

Sapo không có MCP chính chủ, nên MinMin tự bọc Admin API dạng REST giống Shopify:
    https://<tên-cửa-hàng>.mysapo.net/admin/<tài nguyên>.json
Xác thực (theo support.sapo.vn, mục Ứng dụng riêng và OAuth):
- Ứng dụng riêng (Private App): API Key + API Secret gửi bằng Basic Authentication.
- Hoặc access token của app OAuth: header `X-Sapo-Access-Token`.
Có access token thì ưu tiên token, không thì dùng Basic.

CHỐNG SSRF: tên cửa hàng là phần DUY NHẤT người dùng điền vào host. Chỉ nhận chữ, số và
gạch nối (một nhãn tên miền), rồi MinMin tự ghép `.mysapo.net`. Nhờ vậy không cách nào trỏ
request (kèm khoá API) sang máy chủ khác, kể cả kiểu "a.mysapo.net.evil.com" hay "x@evil.com".
Ô này dùng khoá `shop_id` vì nó là định danh CÔNG KHAI của cửa hàng, không phải bí mật.

Bản này CHỈ ĐỌC: thông tin cửa hàng, đơn hàng, chi tiết đơn, sản phẩm, khách hàng, chi nhánh,
tồn kho theo chi nhánh, và một tool GET thô có rào chắn.
"""
import base64
import re
from datetime import datetime

import ket_noi_api as k

TEN = "Sapo"
TRANG_THAI = ["open", "closed", "cancelled", "any"]
THANH_TOAN = ["authorized", "pending", "paid", "partially_paid", "refunded", "voided",
              "partially_refunded", "unpaid"]
GIAO_HANG = ["fulfilled", "partial", "unfulfilled"]
_NHAN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_PATH_THO = re.compile(r"^/[a-z0-9_/]+\.json$")

TOOLS = [
    k.tool("sapo_thong_tin_cua_hang", "Tên, tên miền, email, tiền tệ, múi giờ của cửa hàng Sapo đang kết nối."),
    k.tool("sapo_don_hang",
           "Danh sách đơn hàng theo khoảng ngày tạo. Trang tiếp theo tăng trang.",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string", "enum": TRANG_THAI, "description": "mặc định any (mọi trạng thái)"},
            "thanh_toan": {"type": "string", "enum": THANH_TOAN, "description": "lọc theo trạng thái thanh toán"},
            "giao_hang": {"type": "string", "enum": GIAO_HANG, "description": "lọc theo trạng thái giao hàng"},
            "trang": {"type": "integer", "description": "số trang, bắt đầu từ 1"},
            "so_luong": {"type": "integer", "description": "số đơn mỗi trang, tối đa 250"}}),
    k.tool("sapo_chi_tiet_don",
           "Chi tiết 1 đơn: khách, địa chỉ, sản phẩm, tiền, thanh toán, giao hàng.",
           {"order_id": {"type": "string", "description": "mã đơn (dãy số, id nội bộ Sapo)"}}, ["order_id"]),
    k.tool("sapo_san_pham",
           "Danh sách sản phẩm kèm biến thể (SKU, giá, số lượng tồn).",
           {"trang": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 250"}}),
    k.tool("sapo_khach_hang",
           "Danh sách khách hàng (tên, số điện thoại, email, tổng chi tiêu), lọc theo ngày tạo nếu có.",
           {"tu_ngay": {"type": "string", "description": "chỉ lấy khách tạo từ ngày YYYY-MM-DD"},
            "trang": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 250"}}),
    k.tool("sapo_chi_nhanh", "Danh sách chi nhánh / kho (location) của cửa hàng, dùng lấy location_id cho tồn kho."),
    k.tool("sapo_ton_kho",
           "Tồn kho theo chi nhánh. Lọc theo location_id và/hoặc inventory_item_id (cách nhau bởi dấu phẩy).",
           {"location_ids": {"type": "string", "description": "các mã chi nhánh"},
            "inventory_item_ids": {"type": "string", "description": "các mã inventory item của biến thể"},
            "trang": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 250"}}),
    k.tool("sapo_goi_api",
           "Gọi một API ĐỌC (GET) bất kỳ của Sapo chưa có tool riêng, ví dụ /orders/count.json. "
           "Chỉ GET, không ghi được.",
           {"path": {"type": "string", "description": "sau /admin, bắt đầu bằng / và kết thúc .json"},
            "params": {"type": "object", "description": "tham số query"}},
           ["path"]),
]


async def list_tools(spec):
    return TOOLS


def ten_cua_hang(v):
    """Chuẩn hoá tên cửa hàng về một nhãn tên miền. Nhận 'halimi', 'halimi.mysapo.net',
    'https://halimi.mysapo.net/admin'. Trả None nếu có bất kỳ dấu hiệu trỏ đi chỗ khác."""
    s = str(v or "").strip().lower()
    for dau in ("https://", "http://"):
        if s.startswith(dau):
            s = s[len(dau):]
    if s.endswith("/admin"):
        s = s[:-len("/admin")]
    s = s.rstrip("/")
    if s.endswith(".mysapo.net"):
        s = s[:-len(".mysapo.net")]
    return s if _NHAN.match(s) else None


def _host(sec):
    ten = ten_cua_hang(sec.get("shop_id"))
    return f"https://{ten}.mysapo.net/admin" if ten else None


def _headers(sec):
    h = {"Content-Type": "application/json"}
    tok = str(sec.get("access_token") or "").strip()
    if tok:
        h["X-Sapo-Access-Token"] = tok
    else:
        cap = f"{sec['api_key']}:{sec['api_secret']}".encode()
        h["Authorization"] = "Basic " + base64.b64encode(cap).decode()
    return h


def _iso(ts):
    return datetime.fromtimestamp(ts, k.mui_gio()).isoformat(timespec="seconds")


def _ma_so(v):
    return ",".join([x for x in k.ds(v) if x.isdigit()][:50])


async def _get(sec, path, params=None):
    ok, d = await k.goi(TEN, "GET", f"{_host(sec)}{path}", secrets=sec, params=params or {},
                        headers=_headers(sec))
    if not ok:
        return False, d
    if isinstance(d, dict) and d.get("errors"):
        return False, k.giau(f"ERROR: Sapo báo lỗi: {str(d.get('errors'))[:300]}", sec)
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: Sapo trả về không đúng dạng: {str(d)[:300]}", sec)
    return True, d


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "shop_id")
    if not str(sec.get("access_token") or "").strip():
        t += k.thieu(sec, "api_key", "api_secret")
    if t:
        return "ERROR: kết nối Sapo thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    if not _host(sec):
        return ("ERROR: tên cửa hàng Sapo không hợp lệ. Chỉ điền phần trước .mysapo.net "
                "(chữ, số, gạch nối), ví dụ halimi cho halimi.mysapo.net")
    a = arguments or {}

    if tool == "sapo_thong_tin_cua_hang":
        ok, d = await _get(sec, "/store.json")
    elif tool == "sapo_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        p = {"created_on_min": _iso(tu), "created_on_max": _iso(den),
             "status": a.get("trang_thai") if a.get("trang_thai") in TRANG_THAI else "any",
             "page": k.so(a.get("trang"), 1, 1, 100000), "limit": k.so(a.get("so_luong"), 50, 1, 250)}
        if a.get("thanh_toan") in THANH_TOAN:
            p["financial_status"] = a["thanh_toan"]
        if a.get("giao_hang") in GIAO_HANG:
            p["fulfillment_status"] = a["giao_hang"]
        ok, d = await _get(sec, "/orders.json", p)
    elif tool == "sapo_chi_tiet_don":
        ma = str(a.get("order_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu order_id (dãy số)"
        ok, d = await _get(sec, f"/orders/{ma}.json")
    elif tool == "sapo_san_pham":
        ok, d = await _get(sec, "/products.json", {"page": k.so(a.get("trang"), 1, 1, 100000),
                                                   "limit": k.so(a.get("so_luong"), 20, 1, 250)})
    elif tool == "sapo_khach_hang":
        p = {"page": k.so(a.get("trang"), 1, 1, 100000), "limit": k.so(a.get("so_luong"), 20, 1, 250)}
        ts = k.ngay_sang_ts(a.get("tu_ngay"))
        if ts:
            p["created_on_min"] = _iso(ts)
        ok, d = await _get(sec, "/customers.json", p)
    elif tool == "sapo_chi_nhanh":
        ok, d = await _get(sec, "/locations.json")
    elif tool == "sapo_ton_kho":
        p = {"page": k.so(a.get("trang"), 1, 1, 100000), "limit": k.so(a.get("so_luong"), 50, 1, 250)}
        if _ma_so(a.get("location_ids")):
            p["location_ids"] = _ma_so(a.get("location_ids"))
        if _ma_so(a.get("inventory_item_ids")):
            p["inventory_item_ids"] = _ma_so(a.get("inventory_item_ids"))
        ok, d = await _get(sec, "/inventory_levels.json", p)
    elif tool == "sapo_goi_api":
        path = str(a.get("path") or "").strip()
        if path.startswith("/admin/"):
            path = path[len("/admin"):]
        if ".." in path or "?" in path or "//" in path or "@" in path or not _PATH_THO.match(path):
            return ("ERROR: path phải bắt đầu bằng / và kết thúc .json (chữ thường, số, _ và /), "
                    "không chứa '?', '//', '@' hay '..'")
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        ok, d = await _get(sec, path, {str(kk): str(v) for kk, v in params.items()})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Sapo"
    return k.json_ra(d) if ok else d
