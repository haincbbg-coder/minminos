"""Cầu nối TikTok Shop Partner API (Open API 202309, transport "internal"). Mỗi kết nối = MỘT shop.

TikTok Shop không có MCP chính chủ, nên MinMin tự bọc Open API. Nhiều shop có thể dùng chung một
app đối tác (App Key + App Secret), mỗi shop ủy quyền riêng một lần và được một kết nối riêng.

Ký (theo tài liệu TikTok Shop Partner Center, bản 202309):
  tham số = mọi tham số query trừ `sign` và `access_token`, xếp theo tên
  chuỗi   = path + nối(tên + giá trị) [+ thân JSON nguyên văn nếu là POST không multipart]
  chuỗi   = app_secret + chuỗi + app_secret
  sign    = HMAC-SHA256(app_secret, chuỗi) dạng hex thường
  query   = app_key, timestamp (giây), shop_cipher (API của shop), sign
  header  = x-tts-access-token: <access_token>
Thân POST gửi đúng chuỗi JSON đã ký (content=), không để httpx tự dựng lại.

Ủy quyền: chủ shop mở link ủy quyền của app trên Partner Center, đăng nhập shop, được chuyển về
redirect kèm `?code=...`. Dán code vào kết nối, lần gọi đầu MinMin đổi code lấy token rồi tự lưu.
Token làm mới qua khoá của kết nối để hai lượt song song không làm mới hai lần.

`shop_cipher`: mã định danh shop dùng cho mọi API của shop. Chưa có thì MinMin tự hỏi
/authorization/202309/shops, lấy shop đầu tiên và lưu lại.

Bản này CHỈ ĐỌC: đơn hàng, sản phẩm, thông tin shop. Không sửa giá, không sửa tồn, không giao hàng.
"""
import hashlib
import hmac
import json
import re
import time

import ket_noi_api as k

HOST = "https://open-api.tiktokglobalshop.com"
AUTH_HOST = "https://auth.tiktok-shops.com"
TEN = "TikTok Shop"
TRANG_THAI_DON = ["UNPAID", "ON_HOLD", "AWAITING_SHIPMENT", "PARTIALLY_SHIPPING", "AWAITING_COLLECTION",
                  "IN_TRANSIT", "DELIVERED", "COMPLETED", "CANCELLED"]
TRANG_THAI_SP = ["ALL", "DRAFT", "PENDING", "FAILED", "ACTIVATE", "SELLER_DEACTIVATED",
                 "PLATFORM_DEACTIVATED", "FREEZE", "DELETED"]
THAM_SO_HE_THONG = ("app_key", "timestamp", "sign", "shop_cipher", "access_token", "version")
_PATH_THO = re.compile(r"^/[a-z_]+/\d{6}/[A-Za-z0-9_/-]+$")

TOOLS = [
    k.tool("tiktokshop_thong_tin_shop",
           "Các shop đã ủy quyền cho app: tên shop, khu vực, mã shop (dùng để kiểm tra kết nối)."),
    k.tool("tiktokshop_don_hang",
           "Danh sách đơn hàng theo khoảng ngày tạo. Trang tiếp theo dùng next_page_token của lần trước.",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string", "enum": TRANG_THAI_DON, "description": "lọc theo trạng thái đơn"},
            "page_token": {"type": "string", "description": "trang tiếp theo (next_page_token của lần trước)"},
            "so_luong": {"type": "integer", "description": "số đơn mỗi trang, tối đa 100"}}),
    k.tool("tiktokshop_chi_tiet_don",
           "Chi tiết tối đa 50 đơn: người mua, sản phẩm, tiền, trạng thái, vận chuyển.",
           {"order_id": {"type": "string", "description": "các mã đơn, cách nhau dấu phẩy"}},
           ["order_id"]),
    k.tool("tiktokshop_san_pham",
           "Danh sách sản phẩm của shop (tên, SKU, giá, tồn). Lấy chi tiết bằng tiktokshop_chi_tiet_san_pham.",
           {"trang_thai": {"type": "string", "enum": TRANG_THAI_SP,
                           "description": "lọc theo trạng thái, ví dụ ACTIVATE (đang bán)"},
            "page_token": {"type": "string", "description": "trang tiếp theo (next_page_token của lần trước)"},
            "so_luong": {"type": "integer", "description": "tối đa 100"}}),
    k.tool("tiktokshop_chi_tiet_san_pham",
           "Chi tiết 1 sản phẩm: mô tả, ảnh, các SKU, giá, tồn kho.",
           {"product_id": {"type": "string", "description": "mã sản phẩm (dãy số)"}},
           ["product_id"]),
    k.tool("tiktokshop_goi_api",
           "Gọi một API ĐỌC (GET) bất kỳ của TikTok Shop chưa có tool riêng, ví dụ "
           "/logistics/202309/warehouses. Chỉ GET, không ghi được.",
           {"path": {"type": "string", "description": "dạng /<nhóm>/<phiên bản 6 số>/<đường dẫn>"},
            "params": {"type": "object", "description": "tham số query"}},
           ["path"]),
]


async def list_tools(spec):
    return TOOLS


def ky(app_secret, path, params, body=""):
    """Chữ ký TikTok Shop 202309. `params` là query (sẽ tự bỏ sign và access_token)."""
    p = {kk: v for kk, v in (params or {}).items() if kk not in ("sign", "access_token")}
    s = path + "".join(f"{kk}{p[kk]}" for kk in sorted(p)) + (body or "")
    s = app_secret + s + app_secret
    return hmac.new(app_secret.encode(), s.encode(), hashlib.sha256).hexdigest()


def _loi_api(d, sec):
    if isinstance(d, dict):
        return k.giau(f"ERROR: TikTok Shop {d.get('code')}: {d.get('message', '')}", sec)
    return k.giau(f"ERROR: TikTok Shop trả về không đúng dạng: {str(d)[:300]}", sec)


async def _doi_token(spec, path, them):
    sec = k.bi_mat(spec)
    q = {"app_key": sec["app_key"], "app_secret": sec["app_secret"], **them}
    ok, d = await k.goi(TEN, "GET", f"{AUTH_HOST}{path}", secrets=sec, params=q)
    if not ok:
        return d
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(d, dict) or str(d.get("code")) != "0" or not isinstance(data, dict) \
            or not data.get("access_token"):
        msg = d.get("message", "") if isinstance(d, dict) else str(d)[:300]
        ma = d.get("code", "") if isinstance(d, dict) else ""
        return k.giau(f"ERROR: TikTok Shop từ chối cấp token: {ma} {msg}. Lấy lại code ủy quyền trên "
                      "Partner Center rồi dán vào kết nối.", sec)
    het = data.get("access_token_expire_in")
    k.luu_bi_mat(spec, {"access_token": data["access_token"],
                        "refresh_token": data.get("refresh_token", ""),
                        "token_het_han": het if het else int(time.time()) + 7 * 86400,
                        "refresh_het_han": data.get("refresh_token_expire_in", "")})
    return None


async def dam_bao_token(spec):
    """Trả None khi đã có access token dùng được, hoặc câu lỗi."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("auth_code") or "").strip()
        if code and code != str(sec.get("auth_code_da_dung") or ""):
            loi = await _doi_token(spec, "/api/v2/token/get",
                                   {"auth_code": code, "grant_type": "authorized_code"})
            if loi:
                return loi
            k.luu_bi_mat(spec, {"auth_code_da_dung": code})
            return None
        if sec.get("access_token") and k.con_han(sec, "token_het_han"):
            return None
        if sec.get("refresh_token") and k.con_han(sec, "refresh_het_han", du_phong=0):
            return await _doi_token(spec, "/api/v2/token/refresh",
                                    {"refresh_token": sec["refresh_token"], "grant_type": "refresh_token"})
        return ("ERROR: shop chưa ủy quyền hoặc ủy quyền đã hết hạn. Mở link ủy quyền của app trên TikTok "
                "Shop Partner Center, đăng nhập shop, rồi dán code trên địa chỉ trả về vào kết nối.")


async def _goi_api(spec, method, path, params=None, body=None, can_shop=True):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    if can_shop and not str(k.bi_mat(spec).get("shop_cipher") or "").strip():
        loi = await _tim_shop_cipher(spec)
        if loi:
            return False, loi
    sec = k.bi_mat(spec)
    q = {**(params or {}), "app_key": sec["app_key"], "timestamp": int(time.time())}
    if can_shop:
        q["shop_cipher"] = str(sec["shop_cipher"]).strip()
    than = json.dumps(body, ensure_ascii=False, separators=(",", ":")) if body is not None else ""
    q["sign"] = ky(sec["app_secret"], path, q, than)
    headers = {"x-tts-access-token": sec["access_token"], "content-type": "application/json"}
    ok, d = await k.goi(TEN, method, f"{HOST}{path}", secrets=sec, params=q, headers=headers,
                        content=than.encode("utf-8") if body is not None else None)
    if not ok:
        return False, d
    if not isinstance(d, dict) or str(d.get("code")) != "0":
        return False, _loi_api(d, sec)
    return True, d.get("data", {})


async def _tim_shop_cipher(spec):
    ok, d = await _goi_api(spec, "GET", "/authorization/202309/shops", can_shop=False)
    if not ok:
        return d
    shops = (d or {}).get("shops") if isinstance(d, dict) else None
    if not shops or not isinstance(shops, list) or not shops[0].get("cipher"):
        return "ERROR: app chưa được shop nào ủy quyền (không tìm thấy shop_cipher)"
    k.luu_bi_mat(spec, {"shop_cipher": shops[0]["cipher"], "ten_shop": shops[0].get("name", "")})
    return None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "app_key", "app_secret")
    if t:
        return "ERROR: kết nối TikTok Shop thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "tiktokshop_thong_tin_shop":
        ok, d = await _goi_api(spec, "GET", "/authorization/202309/shops", can_shop=False)
    elif tool == "tiktokshop_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        q = {"page_size": k.so(a.get("so_luong"), 50, 1, 100)}
        if a.get("page_token"):
            q["page_token"] = str(a["page_token"])
        body = {"create_time_ge": tu, "create_time_lt": den + 1}
        if a.get("trang_thai") in TRANG_THAI_DON:
            body["order_status"] = a["trang_thai"]
        ok, d = await _goi_api(spec, "POST", "/order/202309/orders/search", q, body)
    elif tool == "tiktokshop_chi_tiet_don":
        ma = [x for x in k.ds(a.get("order_id")) if x.isdigit()][:50]
        if not ma:
            return "ERROR: thiếu order_id (dãy số)"
        ok, d = await _goi_api(spec, "GET", "/order/202309/orders", {"ids": ",".join(ma)})
    elif tool == "tiktokshop_san_pham":
        q = {"page_size": k.so(a.get("so_luong"), 50, 1, 100)}
        if a.get("page_token"):
            q["page_token"] = str(a["page_token"])
        body = {}
        if a.get("trang_thai") in TRANG_THAI_SP:
            body["status"] = a["trang_thai"]
        ok, d = await _goi_api(spec, "POST", "/product/202309/products/search", q, body)
    elif tool == "tiktokshop_chi_tiet_san_pham":
        pid = str(a.get("product_id") or "").strip()
        if not pid.isdigit():
            return "ERROR: thiếu product_id (dãy số)"
        ok, d = await _goi_api(spec, "GET", f"/product/202309/products/{pid}")
    elif tool == "tiktokshop_goi_api":
        path = str(a.get("path") or "").strip()
        if ".." in path or "?" in path or not _PATH_THO.match(path):
            return ("ERROR: path phải dạng /<nhóm>/<phiên bản 6 số>/<đường dẫn>, ví dụ "
                    "/logistics/202309/warehouses, không chứa '?' hay '..'")
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        params = {kk: v for kk, v in params.items() if kk not in THAM_SO_HE_THONG}
        ok, d = await _goi_api(spec, "GET", path, params, can_shop=not path.startswith("/authorization/"))
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối TikTok Shop"
    return k.json_ra(d) if ok else d
