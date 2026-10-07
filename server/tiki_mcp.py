"""Cầu nối Tiki Open Platform cho nhà bán (transport "internal"). Mỗi kết nối = MỘT nhà bán.

Tiki không có MCP chính chủ, nên MinMin tự bọc Open API (tài liệu: open.tiki.vn/docs). Đã đối
chiếu với tài liệu chính thức và mẫu mã tikivn/open-api-samples:

  Ủy quyền   https://api.tiki.vn/sc/oauth2/auth   (response_type=code, client_id, redirect_uri,
             scope, state tối thiểu 8 ký tự)
  Token      POST https://api.tiki.vn/sc/oauth2/token, form, header Basic base64(id:secret)
             grant_type = authorization_code | refresh_token | client_credentials
             trả access_token, refresh_token (không có ở client_credentials), expires_in, scope
  Gọi API    https://api.tiki.vn/integration/<phiên bản>/..., header Authorization: Bearer <token>

Hai kiểu app:
- App nội bộ (In-house): chỉ cần Client ID + Client Secret, MinMin tự lấy token client_credentials
  mỗi khi hết hạn (luồng này không có refresh token).
- App công khai: tool `tiki_lien_ket_uy_quyen` dựng link, nhà bán đồng ý, dán code trả về vào
  kết nối; MinMin đổi code lấy token rồi tự làm mới bằng refresh token.
Đổi và làm mới token luôn đi qua khoá của kết nối: hai lượt song song chỉ gọi Tiki một lần.

Bản này CHỈ ĐỌC: thông tin nhà bán, kho, đơn hàng, sản phẩm, tồn kho ở kho Tiki.
"""
import base64
import re
import secrets as _secrets
import time
from datetime import datetime
from urllib.parse import quote, urlencode

import ket_noi_api as k

HOST = "https://api.tiki.vn"
API = HOST + "/integration"
AUTH_URL = HOST + "/sc/oauth2/auth"
TOKEN_URL = HOST + "/sc/oauth2/token"
TEN = "Tiki"
SCOPE = "offline product order inventory"
# Tiki nhận mốc ngày dạng "yyyy-MM-dd HH:mm:ss" theo giờ của Tiki (UTC+07:00, ghi trong tài liệu
# Order API v2). Đây là múi giờ CỦA API, không phải của người dùng: ngày người dùng gõ vẫn hiểu
# theo múi giờ ở Cài đặt (k.khoang), rồi mới đổi sang giờ Tiki.
MUI_GIO_TIKI = "Asia/Ho_Chi_Minh"
TOI_DA_NGAY = 90
_MA_SO = re.compile(r"^\d{3,20}$")
_SLUG = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_MA_KHO = re.compile(r"^[a-z0-9]{1,10}$")

TOOLS = [
    k.tool("tiki_lien_ket_uy_quyen",
           "Tạo link để nhà bán ủy quyền app công khai cho MinMin. App nội bộ (In-house) không cần bước này. "
           "Mở link, đăng nhập Tiki Seller Center, đồng ý, rồi dán code trên địa chỉ trả về vào kết nối.",
           {"redirect_url": {"type": "string", "description": "địa chỉ trả về (Redirect URI) đã khai trong app Tiki"}}),
    k.tool("tiki_thong_tin_shop", "Tên, mã nhà bán, trạng thái hoạt động, mô hình vận hành của nhà bán đang kết nối."),
    k.tool("tiki_kho_hang", "Danh sách kho của nhà bán: tên, địa chỉ, kho chính, trạng thái."),
    k.tool("tiki_don_hang",
           "Danh sách đơn hàng theo khoảng ngày tạo (tối đa 90 ngày mỗi lần), mới nhất trước. Trang sau tăng trang.",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string",
                           "description": "lọc theo mã trạng thái Tiki, nhiều mã cách nhau dấu phẩy, ví dụ queueing,canceled"},
            "ma_don": {"type": "string", "description": "lọc theo mã đơn, nhiều mã cách nhau dấu phẩy"},
            "trang": {"type": "integer", "description": "số trang, bắt đầu từ 1"},
            "so_luong": {"type": "integer", "description": "số đơn mỗi trang, tối đa 100"}}),
    k.tool("tiki_chi_tiet_don",
           "Chi tiết 1 đơn: sản phẩm, phí, trạng thái, lịch sử trạng thái.",
           {"ma_don": {"type": "string", "description": "mã đơn Tiki (dãy số)"}}, ["ma_don"]),
    k.tool("tiki_san_pham",
           "Danh sách sản phẩm của nhà bán: tên, SKU, giá, trạng thái, có thể kèm tồn kho.",
           {"tu_khoa": {"type": "string", "description": "tìm theo tên sản phẩm"},
            "dang_ban": {"type": "boolean", "description": "true chỉ lấy đang bán, false chỉ lấy đang tắt"},
            "kem_ton_kho": {"type": "boolean", "description": "kèm thông tin tồn kho"},
            "trang": {"type": "integer"}, "so_luong": {"type": "integer", "description": "tối đa 50"}}),
    k.tool("tiki_chi_tiet_san_pham",
           "Chi tiết 1 sản phẩm: danh mục, thuộc tính, hình ảnh, tồn kho.",
           {"product_id": {"type": "string", "description": "mã sản phẩm Tiki (dãy số)"}}, ["product_id"]),
    k.tool("tiki_ton_kho_kho_tiki",
           "Tồn kho của nhà bán đang gửi tại kho Tiki, có thể lọc theo mã kho Tiki (ví dụ sgn,hn4).",
           {"ma_kho": {"type": "string", "description": "mã kho Tiki, nhiều mã cách nhau dấu phẩy"}}),
]


async def list_tools(spec):
    return TOOLS


def lien_ket_uy_quyen(sec, redirect_url, state=None):
    q = urlencode({"response_type": "code", "client_id": sec["client_id"], "redirect_uri": redirect_url,
                   "scope": SCOPE, "state": state or _secrets.token_urlsafe(12)}, quote_via=quote)
    return f"{AUTH_URL}?{q}"


def _basic(sec):
    raw = f"{sec['client_id']}:{sec['client_secret']}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _tz_tiki():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(MUI_GIO_TIKI)
    except Exception:
        return k.mui_gio()


def ngay_tiki(ts):
    return datetime.fromtimestamp(ts, _tz_tiki()).strftime("%Y-%m-%d %H:%M:%S")


async def _lay_token(spec, form):
    """Gọi endpoint token. Trả None khi đã lưu token mới, hoặc câu lỗi đã giấu bí mật."""
    sec = k.bi_mat(spec)
    form = {**form, "client_id": sec["client_id"]}
    ok, d = await k.goi(TEN, "POST", TOKEN_URL, secrets=sec, data=form,
                        headers={"Authorization": _basic(sec), "Accept": "application/json"})
    if not ok:
        return d + "\nKiểm tra Client ID, Client Secret; app công khai thì tạo lại link bằng tiki_lien_ket_uy_quyen."
    if not isinstance(d, dict) or not d.get("access_token"):
        loi = ""
        if isinstance(d, dict):
            loi = f"{d.get('error', '')} {d.get('error_description', '') or d.get('message', '')}".strip()
        else:
            loi = str(d)[:300]
        return k.giau(f"ERROR: Tiki từ chối cấp token: {loi}", sec)
    bay_gio = int(time.time())
    try:
        het = int(d.get("expires_in") or 3600)
    except (TypeError, ValueError):
        het = 3600
    patch = {"access_token": d["access_token"], "token_het_han": bay_gio + het}
    if d.get("refresh_token"):
        patch["refresh_token"] = d["refresh_token"]
    k.luu_bi_mat(spec, patch)
    return None


async def dam_bao_token(spec):
    """Trả None khi đã có access token dùng được, hoặc câu lỗi."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("auth_code") or "").strip()
        if code and code != str(sec.get("auth_code_da_dung") or ""):
            url = str(sec.get("redirect_url") or "").strip()
            if not url:
                return "ERROR: đổi mã ủy quyền Tiki cần Redirect URI đúng như lúc tạo link, điền vào ô Redirect URI rồi lưu."
            loi = await _lay_token(spec, {"grant_type": "authorization_code", "code": code, "redirect_uri": url})
            if loi:
                return loi
            k.luu_bi_mat(spec, {"auth_code_da_dung": code})
            return None
        if sec.get("access_token") and k.con_han(sec, "token_het_han"):
            return None
        if sec.get("refresh_token"):
            return await _lay_token(spec, {"grant_type": "refresh_token", "refresh_token": sec["refresh_token"]})
        # App nội bộ: không có refresh token, cứ hết hạn thì xin token mới bằng client_credentials.
        return await _lay_token(spec, {"grant_type": "client_credentials"})


async def _get(spec, path, params=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    sec = k.bi_mat(spec)
    p = {kk: str(v) for kk, v in (params or {}).items() if v not in (None, "")}
    ok, d = await k.goi(TEN, "GET", f"{API}{path}", secrets=sec, params=p,
                        headers={"Authorization": f"Bearer {sec['access_token']}", "Accept": "application/json"})
    if not ok:
        return False, d
    if isinstance(d, dict) and d.get("errors") and not d.get("data"):
        return False, k.giau(f"ERROR: Tiki báo lỗi: {str(d.get('errors'))[:300]}", sec)
    return True, d


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "client_id", "client_secret")
    if t:
        return "ERROR: kết nối Tiki thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "tiki_lien_ket_uy_quyen":
        url = str(a.get("redirect_url") or sec.get("redirect_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return "ERROR: cần redirect_url (Redirect URI đã khai trong app Tiki), bắt đầu bằng https://"
        return lien_ket_uy_quyen(sec, url)

    if tool == "tiki_thong_tin_shop":
        ok, d = await _get(spec, "/v2/sellers/me")
    elif tool == "tiki_kho_hang":
        ok, d = await _get(spec, "/v2/sellers/me/warehouses")
    elif tool == "tiki_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7, toi_da_ngay=TOI_DA_NGAY)
        p = {"created_from_date": ngay_tiki(tu), "created_to_date": ngay_tiki(den),
             "page": k.so(a.get("trang"), 1, 1, 10000), "limit": k.so(a.get("so_luong"), 20, 1, 100),
             "order_by": "created_at|desc"}
        tt = [x for x in k.ds(a.get("trang_thai")) if _SLUG.match(x)]
        if tt:
            p["status"] = "in|" + ",".join(tt[:20])
        ma = [x for x in k.ds(a.get("ma_don")) if _MA_SO.match(x)]
        if ma:
            p["code"] = ",".join(ma[:50])
        ok, d = await _get(spec, "/v2/orders", p)
    elif tool == "tiki_chi_tiet_don":
        ma = str(a.get("ma_don") or "").strip()
        if not _MA_SO.match(ma):
            return "ERROR: thiếu ma_don (dãy số)"
        ok, d = await _get(spec, f"/v2/orders/{ma}", {"include": "status_histories,item.fees"})
    elif tool == "tiki_san_pham":
        p = {"page": k.so(a.get("trang"), 1, 1, 10000), "limit": k.so(a.get("so_luong"), 20, 1, 50)}
        tk = str(a.get("tu_khoa") or "").strip()[:100]
        if tk:
            p["name"] = tk
        if isinstance(a.get("dang_ban"), bool):
            p["active"] = 1 if a["dang_ban"] else 0
        if a.get("kem_ton_kho") is True:
            p["include"] = "inventory"
        ok, d = await _get(spec, "/v2.1/products", p)
    elif tool == "tiki_chi_tiet_san_pham":
        ma = str(a.get("product_id") or "").strip()
        if not _MA_SO.match(ma):
            return "ERROR: thiếu product_id (dãy số)"
        ok, d = await _get(spec, f"/v2.1/products/{ma}",
                           {"includes": "seller,categories,inventory,attributes,images"})
    elif tool == "tiki_ton_kho_kho_tiki":
        kho = [x.lower() for x in k.ds(a.get("ma_kho")) if _MA_KHO.match(x.lower())]
        ok, d = await _get(spec, "/v2/seller-inventories",
                           {"tiki_warehouse_codes": ",".join(kho[:20])} if kho else None)
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Tiki"
    return k.json_ra(d) if ok else d
