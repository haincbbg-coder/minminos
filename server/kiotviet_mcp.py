"""Cầu nối KiotViet Public API (transport "internal"). Mỗi kết nối = MỘT gian hàng KiotViet.

KiotViet không có MCP chính chủ, nên MinMin tự bọc Public API. Theo tài liệu KiotViet
(kiotviet.vn/huong-dan-su-dung-public-api-retail, mục 2.1 và 2.2):
- Lấy token: POST https://id.kiotviet.vn/connect/token, form
  scopes=PublicApi.Access, grant_type=client_credentials, client_id, client_secret.
  Token sống 86400 giây (expires_in).
- Gọi API: https://public.kiotapi.com/<tài nguyên>, header `Retailer: <tên gian hàng>` và
  `Authorization: Bearer <token>`.

Token được lưu (mã hoá) vào kết nối kèm mốc hết hạn, và chỉ xin lại khi gần hết hạn. Xin token
đi qua khoá của kết nối: nhiều lượt gọi cùng lúc lúc token hết hạn chỉ xin MỘT lần.
Gặp 401 thì xin token mới và thử lại đúng một lần (token có thể bị thu hồi trước hạn).

Bản này CHỈ ĐỌC: chi nhánh, hàng hoá, tồn kho, đặt hàng, hoá đơn bán, khách hàng, và một tool
GET thô có rào chắn.
"""
import re
import time
from datetime import datetime

import ket_noi_api as k

HOST = "https://public.kiotapi.com"
TOKEN_URL = "https://id.kiotviet.vn/connect/token"
TEN = "KiotViet"
_PATH_THO = re.compile(r"^/[A-Za-z0-9_/]+$")

TOOLS = [
    k.tool("kiotviet_chi_nhanh", "Danh sách chi nhánh của gian hàng KiotViet (id, tên, địa chỉ)."),
    k.tool("kiotviet_hang_hoa",
           "Danh sách hàng hoá: mã, tên, giá bán, kèm tồn kho từng chi nhánh.",
           {"ten": {"type": "string", "description": "lọc theo tên hàng"},
            "chi_nhanh": {"type": "string", "description": "các id chi nhánh, cách nhau bởi dấu phẩy"},
            "vi_tri": {"type": "integer", "description": "bỏ qua bao nhiêu dòng đầu (currentItem)"},
            "so_luong": {"type": "integer", "description": "số dòng mỗi trang, tối đa 100"}}),
    k.tool("kiotviet_ton_kho",
           "Tồn kho theo chi nhánh (productOnHands): số tồn, đặt trước, đang về của từng hàng.",
           {"chi_nhanh": {"type": "string", "description": "các id chi nhánh, cách nhau bởi dấu phẩy"},
            "vi_tri": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 100"}}),
    k.tool("kiotviet_dat_hang",
           "Danh sách phiếu đặt hàng theo khoảng ngày, mới nhất trước.",
           {**k.NGAY_PROPS,
            "chi_nhanh": {"type": "string", "description": "các id chi nhánh"},
            "vi_tri": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 100"}}),
    k.tool("kiotviet_hoa_don",
           "Danh sách hoá đơn bán theo khoảng ngày bán, mới nhất trước: khách, tổng tiền, đã trả, chi nhánh.",
           {**k.NGAY_PROPS,
            "chi_nhanh": {"type": "string", "description": "các id chi nhánh"},
            "vi_tri": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 100"}}),
    k.tool("kiotviet_chi_tiet_hoa_don",
           "Chi tiết 1 hoá đơn: hàng bán, số lượng, giá, giảm giá, thanh toán.",
           {"invoice_id": {"type": "string", "description": "id hoá đơn (dãy số)"}}, ["invoice_id"]),
    k.tool("kiotviet_khach_hang",
           "Danh sách khách hàng, lọc theo tên, mã hoặc số điện thoại.",
           {"ten": {"type": "string"}, "ma": {"type": "string", "description": "mã khách hàng"},
            "so_dien_thoai": {"type": "string"},
            "vi_tri": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 100"}}),
    k.tool("kiotviet_goi_api",
           "Gọi một API ĐỌC (GET) bất kỳ của KiotViet chưa có tool riêng, ví dụ /categories. "
           "Chỉ GET, không ghi được.",
           {"path": {"type": "string", "description": "bắt đầu bằng /, ví dụ /categories"},
            "params": {"type": "object", "description": "tham số query"}},
           ["path"]),
]


async def list_tools(spec):
    return TOOLS


def _iso(ts):
    return datetime.fromtimestamp(ts, k.mui_gio()).strftime("%Y-%m-%dT%H:%M:%S")


def _ma_so(v):
    return ",".join([x for x in k.ds(v) if x.isdigit()][:50])


async def _xin_token(spec):
    sec = k.bi_mat(spec)
    ok, d = await k.goi(TEN, "POST", TOKEN_URL, secrets=sec, data={
        "scopes": "PublicApi.Access", "grant_type": "client_credentials",
        "client_id": sec["client_id"], "client_secret": sec["client_secret"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not ok:
        return d
    if not isinstance(d, dict) or not d.get("access_token"):
        loi = (d.get("error") or d.get("message") or "") if isinstance(d, dict) else str(d)[:300]
        return k.giau(f"ERROR: KiotViet từ chối cấp token: {loi}. Kiểm tra Client ID và mã bảo mật "
                      "ở Thiết lập cửa hàng > Thiết lập kết nối API.", sec)
    k.luu_bi_mat(spec, {"access_token": d["access_token"],
                        "token_het_han": int(time.time()) + int(d.get("expires_in") or 86400)})
    return None


async def dam_bao_token(spec, bat_buoc_moi=False, token_hong=None):
    """None khi có token dùng được, hoặc câu lỗi. `token_hong`: token vừa bị 401, chỉ xin lại
    nếu trong lúc chờ khoá chưa có lượt nào khác đã thay nó."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        tok = sec.get("access_token")
        if bat_buoc_moi and token_hong and tok and tok != token_hong:
            return None
        if not bat_buoc_moi and tok and k.con_han(sec, "token_het_han"):
            return None
        return await _xin_token(spec)


async def _get(spec, path, params=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    for lan in range(2):
        sec = k.bi_mat(spec)
        tok = sec["access_token"]
        ok, d = await k.goi(TEN, "GET", f"{HOST}{path}", secrets=sec, params=params or {},
                            headers={"Retailer": str(sec["retailer"]).strip(),
                                     "Authorization": f"Bearer {tok}"})
        if not ok and lan == 0 and f"{TEN} 401" in str(d):
            loi = await dam_bao_token(spec, bat_buoc_moi=True, token_hong=tok)
            if loi:
                return False, loi
            continue
        break
    if not ok:
        return False, d
    if isinstance(d, dict) and d.get("responseStatus"):
        rs = d["responseStatus"]
        return False, k.giau(f"ERROR: KiotViet {rs.get('errorCode', '')}: {rs.get('message', '')}", sec)
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: KiotViet trả về không đúng dạng: {str(d)[:300]}", sec)
    return True, d


def _trang(a, mac_dinh=50):
    return {"currentItem": k.so(a.get("vi_tri"), 0, 0, 10000000),
            "pageSize": k.so(a.get("so_luong"), mac_dinh, 1, 100)}


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "retailer", "client_id", "client_secret")
    if t:
        return "ERROR: kết nối KiotViet thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}
    cn = _ma_so(a.get("chi_nhanh"))

    if tool == "kiotviet_chi_nhanh":
        ok, d = await _get(spec, "/branches", {"pageSize": 100})
    elif tool == "kiotviet_hang_hoa":
        p = {**_trang(a, 20), "includeInventory": "true"}
        if str(a.get("ten") or "").strip():
            p["name"] = str(a["ten"]).strip()[:200]
        if cn:
            p["branchIds"] = cn
        ok, d = await _get(spec, "/products", p)
    elif tool == "kiotviet_ton_kho":
        p = _trang(a, 50)
        if cn:
            p["branchIds"] = cn
        ok, d = await _get(spec, "/productOnHands", p)
    elif tool in ("kiotviet_dat_hang", "kiotviet_hoa_don"):
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        p = {**_trang(a, 50), "fromPurchaseDate": _iso(tu), "toPurchaseDate": _iso(den),
             "orderBy": "purchaseDate", "orderDirection": "Desc"}
        if cn:
            p["branchIds"] = cn
        ok, d = await _get(spec, "/orders" if tool == "kiotviet_dat_hang" else "/invoices", p)
    elif tool == "kiotviet_chi_tiet_hoa_don":
        ma = str(a.get("invoice_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu invoice_id (dãy số)"
        ok, d = await _get(spec, f"/invoices/{ma}")
    elif tool == "kiotviet_khach_hang":
        p = _trang(a, 20)
        for src, dst in (("ten", "name"), ("ma", "code"), ("so_dien_thoai", "contactNumber")):
            if str(a.get(src) or "").strip():
                p[dst] = str(a[src]).strip()[:100]
        ok, d = await _get(spec, "/customers", p)
    elif tool == "kiotviet_goi_api":
        path = str(a.get("path") or "").strip()
        if ".." in path or "?" in path or "//" in path or not _PATH_THO.match(path) \
                or path.lower().startswith("/connect"):
            return ("ERROR: path phải bắt đầu bằng / (chữ, số, _ và /), không chứa '?', '//' hay '..', "
                    "và không gọi nhóm /connect")
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        ok, d = await _get(spec, path, {str(kk): str(v) for kk, v in params.items()})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối KiotViet"
    return k.json_ra(d) if ok else d
