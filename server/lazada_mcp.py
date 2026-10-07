"""Cầu nối Lazada Open Platform, Việt Nam (transport "internal"). Mỗi kết nối = MỘT shop.

Lazada không có MCP chính chủ, nên MinMin tự bọc Open API. Nhiều shop có thể dùng chung một app
(App Key + App Secret), mỗi shop ủy quyền riêng một lần và được một kết nối riêng.

Ký (theo tài liệu Lazada Open Platform, sign_method=sha256):
  tham số = tham số hệ thống (app_key, timestamp mili giây, sign_method, access_token nếu là API
            của shop) + tham số của API, xếp theo tên
  chuỗi   = api_path + nối(tên + giá trị)
  sign    = HMAC-SHA256(app_secret, chuỗi) dạng hex IN HOA
GET gửi mọi tham số trên query; POST (đổi và làm mới token) gửi dạng form.

Ủy quyền: tool `lazada_lien_ket_uy_quyen` dựng link, chủ shop đăng nhập, được chuyển về redirect
kèm `?code=...`. Dán code vào kết nối, lần gọi đầu MinMin đổi code lấy token rồi tự lưu. Refresh
token có thể chỉ dùng được một lần, nên làm mới luôn đi qua khoá của kết nối.

Bản này CHỈ ĐỌC: đơn hàng, sản phẩm trong đơn, sản phẩm, thông tin shop.
"""
import hashlib
import hmac
import re
import time
from datetime import datetime
from urllib.parse import urlencode

import ket_noi_api as k

HOST = "https://api.lazada.vn/rest"
AUTH_HOST = "https://auth.lazada.com/rest"
TEN = "Lazada"
TRANG_THAI = ["unpaid", "pending", "ready_to_ship", "shipped", "delivered", "canceled", "returned", "failed"]
LOC_SP = ["live", "all", "inactive", "sold-out"]
THAM_SO_HE_THONG = ("app_key", "timestamp", "sign", "sign_method", "access_token")
_PATH_THO = re.compile(r"^/[a-z0-9_/]+$")

TOOLS = [
    k.tool("lazada_lien_ket_uy_quyen",
           "Tạo link để chủ shop ủy quyền app cho MinMin (dùng khi kết nối mới hoặc token hết hạn). "
           "Mở link, đăng nhập shop, rồi dán code trên địa chỉ trả về vào kết nối.",
           {"redirect_url": {"type": "string", "description": "địa chỉ trả về (Callback URL) đã khai trong app Lazada"}}),
    k.tool("lazada_thong_tin_shop", "Tên shop, mã người bán, email, trạng thái của shop đang kết nối."),
    k.tool("lazada_don_hang",
           "Danh sách đơn hàng theo khoảng ngày tạo, mới nhất trước. Trang tiếp theo tăng offset.",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string", "enum": TRANG_THAI, "description": "lọc theo trạng thái"},
            "offset": {"type": "integer", "description": "bỏ qua bao nhiêu đơn đầu"},
            "so_luong": {"type": "integer", "description": "số đơn mỗi trang, tối đa 100"}}),
    k.tool("lazada_chi_tiet_don",
           "Chi tiết 1 đơn: người mua, địa chỉ, tiền, phương thức thanh toán, trạng thái.",
           {"order_id": {"type": "string", "description": "mã đơn (dãy số)"}}, ["order_id"]),
    k.tool("lazada_san_pham_don",
           "Các sản phẩm trong 1 đơn: SKU, giá, phí vận chuyển, trạng thái từng món.",
           {"order_id": {"type": "string", "description": "mã đơn (dãy số)"}}, ["order_id"]),
    k.tool("lazada_san_pham",
           "Danh sách sản phẩm của shop: tên, SKU, giá, tồn kho.",
           {"loc": {"type": "string", "enum": LOC_SP, "description": "mặc định live (đang bán)"},
            "offset": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 50"}}),
    k.tool("lazada_goi_api",
           "Gọi một API ĐỌC (GET) bất kỳ của Lazada chưa có tool riêng, ví dụ /finance/transaction/details/get. "
           "Chỉ GET, không ghi được.",
           {"path": {"type": "string", "description": "bắt đầu bằng /, ví dụ /seller/metrics/get"},
            "params": {"type": "object", "description": "tham số query"}},
           ["path"]),
]


async def list_tools(spec):
    return TOOLS


def ky(app_secret, api_path, params):
    """Chữ ký Lazada sha256: hex IN HOA. `params` chưa có sign."""
    p = {kk: v for kk, v in (params or {}).items() if kk != "sign"}
    s = api_path + "".join(f"{kk}{p[kk]}" for kk in sorted(p))
    return hmac.new(app_secret.encode(), s.encode(), hashlib.sha256).hexdigest().upper()


def lien_ket_uy_quyen(sec, redirect_url):
    q = urlencode({"response_type": "code", "force_auth": "true", "redirect_uri": redirect_url,
                   "client_id": sec["app_key"]})
    return f"https://auth.lazada.com/oauth/authorize?{q}"


def _he_thong(sec):
    return {"app_key": sec["app_key"], "timestamp": str(int(time.time() * 1000)), "sign_method": "sha256"}


def _iso(ts):
    return datetime.fromtimestamp(ts, k.mui_gio()).isoformat(timespec="seconds")


async def _doi_token(spec, path, them):
    sec = k.bi_mat(spec)
    p = {**_he_thong(sec), **them}
    p["sign"] = ky(sec["app_secret"], path, p)
    ok, d = await k.goi(TEN, "POST", f"{AUTH_HOST}{path}", secrets=sec, data=p)
    if not ok:
        return d
    if not isinstance(d, dict) or str(d.get("code", "0")) != "0" or not d.get("access_token"):
        ma = d.get("code", "") if isinstance(d, dict) else ""
        msg = d.get("message", "") if isinstance(d, dict) else str(d)[:300]
        return k.giau(f"ERROR: Lazada từ chối cấp token: {ma} {msg}. Tạo lại link ủy quyền bằng "
                      "lazada_lien_ket_uy_quyen.", sec)
    bay_gio = int(time.time())
    patch = {"access_token": d["access_token"], "refresh_token": d.get("refresh_token", ""),
             "token_het_han": bay_gio + int(d.get("expires_in") or 7 * 86400)}
    if d.get("refresh_expires_in"):
        patch["refresh_het_han"] = bay_gio + int(d["refresh_expires_in"])
    k.luu_bi_mat(spec, patch)
    return None


async def dam_bao_token(spec):
    """Trả None khi đã có access token dùng được, hoặc câu lỗi."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("auth_code") or "").strip()
        if code and code != str(sec.get("auth_code_da_dung") or ""):
            loi = await _doi_token(spec, "/auth/token/create", {"code": code})
            if loi:
                return loi
            k.luu_bi_mat(spec, {"auth_code_da_dung": code})
            return None
        if sec.get("access_token") and k.con_han(sec, "token_het_han"):
            return None
        if sec.get("refresh_token") and k.con_han(sec, "refresh_het_han", du_phong=0):
            return await _doi_token(spec, "/auth/token/refresh", {"refresh_token": sec["refresh_token"]})
        return ("ERROR: shop chưa ủy quyền hoặc ủy quyền đã hết hạn. Gọi lazada_lien_ket_uy_quyen để lấy "
                "link, mở link đăng nhập shop, rồi dán code vào kết nối ở trang Kết nối.")


async def _get(spec, path, params=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    sec = k.bi_mat(spec)
    p = {**{kk: str(v) for kk, v in (params or {}).items()}, **_he_thong(sec),
         "access_token": sec["access_token"]}
    p["sign"] = ky(sec["app_secret"], path, p)
    ok, d = await k.goi(TEN, "GET", f"{HOST}{path}", secrets=sec, params=p)
    if not ok:
        return False, d
    if not isinstance(d, dict) or str(d.get("code", "")) != "0":
        if isinstance(d, dict):
            return False, k.giau(f"ERROR: Lazada {d.get('code')}: {d.get('message', '')}", sec)
        return False, k.giau(f"ERROR: Lazada trả về không đúng dạng: {str(d)[:300]}", sec)
    return True, d.get("data", {})


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "app_key", "app_secret")
    if t:
        return "ERROR: kết nối Lazada thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "lazada_lien_ket_uy_quyen":
        url = str(a.get("redirect_url") or sec.get("redirect_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return "ERROR: cần redirect_url (Callback URL đã khai trong app Lazada), bắt đầu bằng https://"
        return lien_ket_uy_quyen(sec, url)

    if tool == "lazada_thong_tin_shop":
        ok, d = await _get(spec, "/seller/get")
    elif tool == "lazada_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        p = {"created_after": _iso(tu), "created_before": _iso(den),
             "limit": k.so(a.get("so_luong"), 50, 1, 100),
             "offset": k.so(a.get("offset"), 0, 0, 1000000),
             "sort_by": "created_at", "sort_direction": "DESC"}
        if a.get("trang_thai") in TRANG_THAI:
            p["status"] = a["trang_thai"]
        ok, d = await _get(spec, "/orders/get", p)
    elif tool in ("lazada_chi_tiet_don", "lazada_san_pham_don"):
        ma = str(a.get("order_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu order_id (dãy số)"
        path = "/order/get" if tool == "lazada_chi_tiet_don" else "/order/items/get"
        ok, d = await _get(spec, path, {"order_id": ma})
    elif tool == "lazada_san_pham":
        loc = a.get("loc") if a.get("loc") in LOC_SP else "live"
        ok, d = await _get(spec, "/products/get", {
            "filter": loc, "offset": k.so(a.get("offset"), 0, 0, 1000000),
            "limit": k.so(a.get("so_luong"), 20, 1, 50)})
    elif tool == "lazada_goi_api":
        path = str(a.get("path") or "").strip()
        if ".." in path or "?" in path or not _PATH_THO.match(path) or path.startswith("/auth"):
            return ("ERROR: path phải bắt đầu bằng / (chữ thường, số, _ và /), không chứa '?' hay '..', "
                    "và không gọi nhóm /auth")
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        params = {kk: v for kk, v in params.items() if kk not in THAM_SO_HE_THONG}
        ok, d = await _get(spec, path, params)
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Lazada"
    return k.json_ra(d) if ok else d
