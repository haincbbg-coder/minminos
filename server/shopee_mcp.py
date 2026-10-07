"""Cầu nối Shopee Open Platform v2 (transport "internal"). Mỗi kết nối = MỘT shop.

Shopee không có MCP chính chủ, nên MinMin tự bọc Open API v2. Nhiều shop dùng chung một app
đối tác (Partner ID + Partner Key), mỗi shop ủy quyền riêng một lần và được một kết nối riêng.

Ký (đã đối chiếu tài liệu Shopee Open Platform v2):
  base  = partner_id + api_path + timestamp [+ access_token + shop_id]   (API của shop)
  sign  = HMAC-SHA256(partner_key, base) dạng hex thường
  query = partner_id, timestamp, sign [, access_token, shop_id]

Ủy quyền: người dùng mở link ủy quyền (tool `shopee_lien_ket_uy_quyen`), đăng nhập shop, được
chuyển về redirect kèm `?code=...&shop_id=...`. Dán `code` và `shop_id` vào kết nối, lần gọi đầu
MinMin đổi code lấy token rồi tự lưu. Access token sống 4 giờ, refresh token 30 ngày và DÙNG MỘT
LẦN (mỗi lần làm mới được cặp mới), nên làm mới luôn đi qua khoá của kết nối.

Bản này CHỈ ĐỌC: đơn hàng, sản phẩm, tài chính đơn, thông tin shop. Không sửa giá, không sửa tồn,
không xác nhận giao hàng.
"""
import hashlib
import hmac
import time
from urllib.parse import urlencode

import ket_noi_api as k

HOST = {"live": "https://partner.shopeemobile.com",
        "test": "https://partner.test-stable.shopeemobile.com"}
TEN = "Shopee"
TRANG_THAI = ["UNPAID", "READY_TO_SHIP", "PROCESSED", "SHIPPED", "COMPLETED",
              "IN_CANCEL", "CANCELLED", "INVOICE_PENDING", "TO_RETURN"]

TOOLS = [
    k.tool("shopee_lien_ket_uy_quyen",
           "Tạo link để chủ shop ủy quyền app cho MinMin (dùng khi kết nối mới hoặc token hết hạn). "
           "Mở link, đăng nhập shop, rồi dán code và shop_id trên địa chỉ trả về vào kết nối.",
           {"redirect_url": {"type": "string", "description": "địa chỉ trả về đã khai trong app Shopee"}}),
    k.tool("shopee_thong_tin_shop", "Tên shop, khu vực, trạng thái của shop đang kết nối."),
    k.tool("shopee_don_hang",
           "Danh sách mã đơn (order_sn) theo khoảng ngày tạo, tối đa 15 ngày mỗi lần. Lấy chi tiết bằng "
           "shopee_chi_tiet_don.",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string", "enum": TRANG_THAI, "description": "lọc theo trạng thái"},
            "cursor": {"type": "string", "description": "trang tiếp theo (next_cursor của lần trước)"},
            "so_luong": {"type": "integer", "description": "số đơn mỗi trang, tối đa 100"}}),
    k.tool("shopee_chi_tiet_don",
           "Chi tiết tối đa 50 đơn: người mua, sản phẩm, tiền, trạng thái, vận chuyển.",
           {"order_sn": {"type": "string", "description": "các mã đơn, cách nhau dấu phẩy"}},
           ["order_sn"]),
    k.tool("shopee_tai_chinh_don",
           "Tiền shop thực nhận của 1 đơn sau phí sàn, phí vận chuyển, voucher (escrow).",
           {"order_sn": {"type": "string"}}, ["order_sn"]),
    k.tool("shopee_san_pham",
           "Danh sách item_id sản phẩm của shop. Lấy chi tiết bằng shopee_chi_tiet_san_pham.",
           {"trang_thai": {"type": "string", "enum": ["NORMAL", "BANNED", "UNLIST"],
                           "description": "mặc định NORMAL (đang bán)"},
            "offset": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 100"}}),
    k.tool("shopee_chi_tiet_san_pham",
           "Thông tin cơ bản tối đa 50 sản phẩm: tên, SKU, giá, tồn kho.",
           {"item_id": {"type": "string", "description": "các item_id, cách nhau dấu phẩy"}},
           ["item_id"]),
    k.tool("shopee_goi_api",
           "Gọi một API ĐỌC (GET) bất kỳ của Shopee v2 chưa có tool riêng, ví dụ "
           "/api/v2/logistics/get_tracking_number. Chỉ GET, không ghi được.",
           {"path": {"type": "string", "description": "bắt đầu bằng /api/v2/"},
            "params": {"type": "object", "description": "tham số query"}},
           ["path"]),
]


async def list_tools(spec):
    return TOOLS


def _ky(partner_key, base):
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def _host(sec):
    return HOST.get(str(sec.get("moi_truong") or "live").strip().lower(), HOST["live"])


def _pid(sec):
    try:
        return int(str(sec.get("partner_id") or "").strip())
    except ValueError:
        return None


def lien_ket_uy_quyen(sec, redirect_url, ts=None):
    ts = int(ts or time.time())
    path = "/api/v2/shop/auth_partner"
    pid = _pid(sec)
    sign = _ky(sec["partner_key"], f"{pid}{path}{ts}")
    q = urlencode({"partner_id": pid, "timestamp": ts, "sign": sign, "redirect": redirect_url})
    return f"{_host(sec)}{path}?{q}"


async def _doi_token(spec, path, body):
    sec = k.bi_mat(spec)
    pid = _pid(sec)
    ts = int(time.time())
    sign = _ky(sec["partner_key"], f"{pid}{path}{ts}")
    ok, d = await k.goi(TEN, "POST", f"{_host(sec)}{path}", secrets=sec,
                        params={"partner_id": pid, "timestamp": ts, "sign": sign},
                        json_body={**body, "partner_id": pid})
    if not ok:
        return d
    if not isinstance(d, dict) or d.get("error") or not d.get("access_token"):
        msg = (d or {}).get("message") if isinstance(d, dict) else d
        return k.giau(f"ERROR: Shopee từ chối cấp token: {(d or {}).get('error', '') if isinstance(d, dict) else ''} "
                      f"{msg}. Tạo lại link ủy quyền bằng shopee_lien_ket_uy_quyen.", sec)
    k.luu_bi_mat(spec, {"access_token": d["access_token"],
                        "refresh_token": d.get("refresh_token", ""),
                        "token_het_han": int(time.time()) + int(d.get("expire_in") or 14400)})
    return None


async def dam_bao_token(spec):
    """Trả None khi đã có access token dùng được, hoặc câu lỗi."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("auth_code") or "").strip()
        shop = str(sec.get("shop_id") or "").strip()
        if code and code != str(sec.get("auth_code_da_dung") or ""):
            loi = await _doi_token(spec, "/api/v2/auth/token/get", {"code": code, "shop_id": int(shop)})
            if loi:
                return loi
            k.luu_bi_mat(spec, {"auth_code_da_dung": code})
            return None
        if sec.get("access_token") and k.con_han(sec, "token_het_han"):
            return None
        if sec.get("refresh_token"):
            return await _doi_token(spec, "/api/v2/auth/access_token/get",
                                    {"refresh_token": sec["refresh_token"], "shop_id": int(shop)})
        return ("ERROR: shop chưa ủy quyền. Gọi shopee_lien_ket_uy_quyen để lấy link, mở link đăng nhập "
                "shop, rồi dán code và shop_id vào kết nối ở trang Kết nối.")


async def _get(spec, path, params=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    sec = k.bi_mat(spec)
    pid, shop, tok = _pid(sec), int(sec["shop_id"]), sec["access_token"]
    ts = int(time.time())
    sign = _ky(sec["partner_key"], f"{pid}{path}{ts}{tok}{shop}")
    q = {**(params or {}), "partner_id": pid, "timestamp": ts, "sign": sign,
         "access_token": tok, "shop_id": shop}
    ok, d = await k.goi(TEN, "GET", f"{_host(sec)}{path}", secrets=sec, params=q)
    if not ok:
        return False, d
    if isinstance(d, dict) and d.get("error"):
        return False, k.giau(f"ERROR: Shopee {d.get('error')}: {d.get('message', '')}", sec)
    return True, d


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "partner_id", "partner_key", "shop_id")
    if t:
        return "ERROR: kết nối Shopee thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    if _pid(sec) is None or not str(sec.get("shop_id")).strip().isdigit():
        return "ERROR: Partner ID và Shop ID phải là dãy số"
    a = arguments or {}

    if tool == "shopee_lien_ket_uy_quyen":
        url = str(a.get("redirect_url") or sec.get("redirect_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return "ERROR: cần redirect_url (địa chỉ trả về đã khai trong app Shopee), bắt đầu bằng https://"
        return lien_ket_uy_quyen(sec, url)

    if tool == "shopee_thong_tin_shop":
        ok, d = await _get(spec, "/api/v2/shop/get_shop_info")
    elif tool == "shopee_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7, toi_da_ngay=15)
        p = {"time_range_field": "create_time", "time_from": tu, "time_to": den,
             "page_size": k.so(a.get("so_luong"), 50, 1, 100),
             "response_optional_fields": "order_status"}
        if a.get("trang_thai") in TRANG_THAI:
            p["order_status"] = a["trang_thai"]
        if a.get("cursor"):
            p["cursor"] = str(a["cursor"])
        ok, d = await _get(spec, "/api/v2/order/get_order_list", p)
    elif tool == "shopee_chi_tiet_don":
        ma = k.ds(a.get("order_sn"))[:50]
        if not ma:
            return "ERROR: thiếu order_sn"
        ok, d = await _get(spec, "/api/v2/order/get_order_detail", {
            "order_sn_list": ",".join(ma),
            "response_optional_fields": "buyer_username,item_list,total_amount,shipping_carrier,"
                                        "payment_method,recipient_address,pay_time,package_list"})
    elif tool == "shopee_tai_chinh_don":
        ma = str(a.get("order_sn") or "").strip()
        if not ma:
            return "ERROR: thiếu order_sn"
        ok, d = await _get(spec, "/api/v2/payment/get_escrow_detail", {"order_sn": ma})
    elif tool == "shopee_san_pham":
        tt = a.get("trang_thai") if a.get("trang_thai") in ("NORMAL", "BANNED", "UNLIST") else "NORMAL"
        ok, d = await _get(spec, "/api/v2/product/get_item_list", {
            "offset": k.so(a.get("offset"), 0, 0, 100000),
            "page_size": k.so(a.get("so_luong"), 50, 1, 100), "item_status": tt})
    elif tool == "shopee_chi_tiet_san_pham":
        ids = [x for x in k.ds(a.get("item_id")) if x.isdigit()][:50]
        if not ids:
            return "ERROR: thiếu item_id (dãy số)"
        ok, d = await _get(spec, "/api/v2/product/get_item_base_info", {"item_id_list": ",".join(ids)})
    elif tool == "shopee_goi_api":
        path = str(a.get("path") or "").strip()
        if not path.startswith("/api/v2/") or ".." in path or "?" in path or "auth" in path.split("/")[3:4]:
            return "ERROR: path phải bắt đầu bằng /api/v2/, không chứa '?' hay '..', và không gọi nhóm auth"
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        params = {kk: v for kk, v in params.items()
                  if kk not in ("partner_id", "timestamp", "sign", "access_token", "shop_id")}
        ok, d = await _get(spec, path, params)
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Shopee"
    return k.json_ra(d) if ok else d
