"""Cầu nối Haravan Omni API (transport "internal"). Mỗi kết nối = MỘT cửa hàng Haravan.

Haravan không có MCP chính chủ, nên MinMin tự bọc REST API. Xác thực bằng Private App:
chủ shop tạo ứng dụng riêng trong trang quản trị Haravan, chép Token rồi dán vào kết nối.
Mọi request gửi header `Authorization: Bearer <token>` tới https://apis.haravan.com/com/...
(theo docs.haravan.com, mục Private App Authentication).

Bản này CHỈ ĐỌC: thông tin shop, đơn hàng, chi tiết đơn, sản phẩm, khách hàng, chi nhánh,
tồn kho theo chi nhánh, và một tool GET thô có rào chắn cho API đọc chưa có tool riêng.
"""
import re
from datetime import datetime

import ket_noi_api as k

HOST = "https://apis.haravan.com/com"
TEN = "Haravan"
TRANG_THAI = ["open", "closed", "cancelled", "any"]
THANH_TOAN = ["pending", "paid", "partially_paid", "refunded", "voided", "partially_refunded"]
GIAO_HANG = ["unshipped", "shipped", "partial"]
_PATH_THO = re.compile(r"^/[a-z0-9_/]+\.json$")

TOOLS = [
    k.tool("haravan_thong_tin_shop", "Tên cửa hàng, tên miền, email, tiền tệ, múi giờ của shop Haravan đang kết nối."),
    k.tool("haravan_don_hang",
           "Danh sách đơn hàng theo khoảng ngày tạo. Trang tiếp theo tăng trang.",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string", "enum": TRANG_THAI, "description": "mặc định any (mọi trạng thái)"},
            "thanh_toan": {"type": "string", "enum": THANH_TOAN, "description": "lọc theo trạng thái thanh toán"},
            "giao_hang": {"type": "string", "enum": GIAO_HANG, "description": "lọc theo trạng thái giao hàng"},
            "trang": {"type": "integer", "description": "số trang, bắt đầu từ 1"},
            "so_luong": {"type": "integer", "description": "số đơn mỗi trang, tối đa 50"}}),
    k.tool("haravan_chi_tiet_don",
           "Chi tiết 1 đơn: khách, địa chỉ, sản phẩm, tiền, thanh toán, giao hàng.",
           {"order_id": {"type": "string", "description": "mã đơn (dãy số, id nội bộ Haravan)"}}, ["order_id"]),
    k.tool("haravan_san_pham",
           "Danh sách sản phẩm kèm biến thể (SKU, giá, tồn kho tổng).",
           {"sku": {"type": "string", "description": "lọc theo SKU biến thể"},
            "loai": {"type": "string", "description": "lọc theo loại sản phẩm (product_type)"},
            "nha_cung_cap": {"type": "string", "description": "lọc theo vendor"},
            "trang": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 50"}}),
    k.tool("haravan_khach_hang",
           "Danh sách khách hàng, hoặc tìm theo tên, số điện thoại, email khi có tu_khoa.",
           {"tu_khoa": {"type": "string", "description": "chữ cần tìm trong dữ liệu khách"},
            "trang": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 50"}}),
    k.tool("haravan_chi_nhanh", "Danh sách chi nhánh / kho (location) của shop, dùng lấy location_id cho tồn kho."),
    k.tool("haravan_ton_kho",
           "Tồn kho từng biến thể theo chi nhánh. Lọc theo location_id và variant_id (mỗi loại tối đa 50).",
           {"location_ids": {"type": "string", "description": "các mã chi nhánh, cách nhau bởi dấu phẩy"},
            "variant_ids": {"type": "string", "description": "các mã biến thể, cách nhau bởi dấu phẩy"},
            "since_id": {"type": "string", "description": "lấy các dòng sau id này (phân trang)"},
            "so_luong": {"type": "integer", "description": "tối đa 250"}}),
    k.tool("haravan_goi_api",
           "Gọi một API ĐỌC (GET) bất kỳ của Haravan chưa có tool riêng, ví dụ /orders/count.json. "
           "Chỉ GET, không ghi được.",
           {"path": {"type": "string", "description": "sau /com, bắt đầu bằng / và kết thúc .json, ví dụ /orders/count.json"},
            "params": {"type": "object", "description": "tham số query"}},
           ["path"]),
]


async def list_tools(spec):
    return TOOLS


def _iso(ts):
    return datetime.fromtimestamp(ts, k.mui_gio()).isoformat(timespec="seconds")


def _ma_so(v):
    """Danh sách id số, bỏ mọi thứ không phải số. Trả chuỗi 'a,b,c' (tối đa 50) hoặc ''."""
    return ",".join([x for x in k.ds(v) if x.isdigit()][:50])


async def _get(sec, path, params=None):
    ok, d = await k.goi(TEN, "GET", f"{HOST}{path}", secrets=sec, params=params or {},
                        headers={"Authorization": f"Bearer {sec['access_token']}",
                                 "Content-Type": "application/json"})
    if not ok:
        return False, d
    if isinstance(d, dict) and d.get("errors"):
        return False, k.giau(f"ERROR: Haravan báo lỗi: {str(d.get('errors'))[:300]}", sec)
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: Haravan trả về không đúng dạng: {str(d)[:300]}", sec)
    return True, d


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "access_token")
    if t:
        return "ERROR: kết nối Haravan thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "haravan_thong_tin_shop":
        ok, d = await _get(sec, "/shop.json")
    elif tool == "haravan_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        p = {"created_at_min": _iso(tu), "created_at_max": _iso(den),
             "status": a.get("trang_thai") if a.get("trang_thai") in TRANG_THAI else "any",
             "page": k.so(a.get("trang"), 1, 1, 100000), "limit": k.so(a.get("so_luong"), 50, 1, 50)}
        if a.get("thanh_toan") in THANH_TOAN:
            p["financial_status"] = a["thanh_toan"]
        if a.get("giao_hang") in GIAO_HANG:
            p["fulfillment_status"] = a["giao_hang"]
        ok, d = await _get(sec, "/orders.json", p)
    elif tool == "haravan_chi_tiet_don":
        ma = str(a.get("order_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu order_id (dãy số)"
        ok, d = await _get(sec, f"/orders/{ma}.json")
    elif tool == "haravan_san_pham":
        p = {"page": k.so(a.get("trang"), 1, 1, 100000), "limit": k.so(a.get("so_luong"), 20, 1, 50)}
        for src, dst in (("sku", "sku"), ("loai", "product_type"), ("nha_cung_cap", "vendor")):
            if str(a.get(src) or "").strip():
                p[dst] = str(a[src]).strip()[:200]
        ok, d = await _get(sec, "/products.json", p)
    elif tool == "haravan_khach_hang":
        p = {"page": k.so(a.get("trang"), 1, 1, 100000), "limit": k.so(a.get("so_luong"), 20, 1, 50)}
        q = str(a.get("tu_khoa") or "").strip()[:200]
        if q:
            p["query"] = q
        ok, d = await _get(sec, "/customers/search.json" if q else "/customers.json", p)
    elif tool == "haravan_chi_nhanh":
        ok, d = await _get(sec, "/locations.json")
    elif tool == "haravan_ton_kho":
        p = {"limit": k.so(a.get("so_luong"), 100, 1, 250)}
        if _ma_so(a.get("location_ids")):
            p["location_ids"] = _ma_so(a.get("location_ids"))
        if _ma_so(a.get("variant_ids")):
            p["variant_ids"] = _ma_so(a.get("variant_ids"))
        if str(a.get("since_id") or "").strip().isdigit():
            p["since_id"] = str(a["since_id"]).strip()
        ok, d = await _get(sec, "/inventory_locations.json", p)
    elif tool == "haravan_goi_api":
        path = str(a.get("path") or "").strip()
        if path.startswith("/com/"):
            path = path[4:]
        if ".." in path or "?" in path or "//" in path or not _PATH_THO.match(path):
            return ("ERROR: path phải bắt đầu bằng / và kết thúc .json (chữ thường, số, _ và /), "
                    "không chứa '?', '//' hay '..'")
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        ok, d = await _get(sec, path, {str(kk): str(v) for kk, v in params.items()})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Haravan"
    return k.json_ra(d) if ok else d
