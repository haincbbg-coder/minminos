"""Cầu nối MISA meInvoice, API tích hợp (transport "internal"). Mỗi kết nối = MỘT mã số thuế.

MISA không có MCP chính chủ, nên MinMin tự bọc API tích hợp (tài liệu: doc.meinvoice.vn/itg).
Đã đối chiếu với tài liệu chính thức:

  Gốc      https://api.meinvoice.vn/api/integration      (thử: https://testapi.meinvoice.vn/...)
  Token    POST <gốc>/auth/token, JSON {appid, taxcode, username, password}
           trả {Success, ErrorCode, Errors, Data: "<JWT>"}; JWT có mốc hết hạn `exp`
  Gọi API  <gốc>/invoice/..., header Authorization: Bearer <JWT>
           trả {success, errorCode, descriptionErrorCode, errors, data, customData}; `data` nhiều
           khi là CHUỖI JSON nên phải parse thêm một lần.

Token không có luồng làm mới trong tài liệu tích hợp, nên hết hạn thì đăng nhập lại bằng ô đã lưu.
Việc đó đi qua khoá của kết nối: hai lượt song song chỉ đăng nhập MISA một lần.

Bản này CHỈ ĐỌC: danh sách mẫu/ký hiệu hoá đơn, trạng thái hoá đơn theo mã tra cứu hoặc refID,
link xem bản PDF đã phát hành. KHÔNG phát hành, không huỷ, không gửi email hoá đơn.
Tài liệu tích hợp không có API liệt kê hoá đơn theo khoảng ngày, nên bản này không bịa ra tool đó.
"""
import base64
import json
import re
import time

import ket_noi_api as k

HOST = {"live": "https://api.meinvoice.vn/api/integration",
        "test": "https://testapi.meinvoice.vn/api/integration"}
TEN = "MISA meInvoice"
TOI_DA_MA = 50
_MA = re.compile(r"^[A-Za-z0-9_\-]{4,64}$")
HAN_MAC_DINH = 14 * 86400

_MA_THEO = {"type": "array", "items": {"type": "string"},
            "description": "danh sách mã (hoặc chuỗi cách nhau dấu phẩy), tối đa 50"}

TOOLS = [
    k.tool("meinvoice_mau_hoa_don",
           "Danh sách mẫu số và ký hiệu hoá đơn (hoặc vé) của doanh nghiệp, kèm trạng thái đang dùng.",
           {"co_ma_cqt": {"type": "boolean", "description": "true lấy mẫu hoá đơn có mã của cơ quan thuế"},
            "ve": {"type": "boolean", "description": "true lấy mẫu vé thay vì hoá đơn"},
            "nam": {"type": "integer", "description": "năm của mẫu, mặc định năm nay"}}),
    k.tool("meinvoice_trang_thai",
           "Trạng thái hoá đơn đã phát hành: đã phát hành chưa, đã gửi cơ quan thuế chưa, mã CQT, đã huỷ chưa, "
           "người mua đã nhận chưa. Tra theo mã tra cứu (TransactionID) hoặc refID.",
           {"ma": _MA_THEO,
            "loai_ma": {"type": "string", "enum": ["ma_tra_cuu", "ref_id"], "description": "mặc định ma_tra_cuu"},
            "co_ma_cqt": {"type": "boolean", "description": "true nếu là hoá đơn có mã của cơ quan thuế"},
            "may_tinh_tien": {"type": "boolean", "description": "true nếu là hoá đơn khởi tạo từ máy tính tiền"}},
           ["ma"]),
    k.tool("meinvoice_link_xem",
           "Link xem bản PDF của hoá đơn đã phát hành (link chỉ sống 5 phút). Tra theo mã tra cứu.",
           {"ma": _MA_THEO}, ["ma"]),
]


async def list_tools(spec):
    return TOOLS


def _goc(sec):
    return HOST.get(str(sec.get("moi_truong") or "live").strip().lower(), HOST["live"])


def han_jwt(tok):
    """Mốc `exp` trong JWT (unix giây), hoặc None nếu không đọc được. Không kiểm chữ ký: chỉ để
    biết khi nào nên đăng nhập lại, MISA vẫn là bên quyết định token còn dùng được hay không."""
    try:
        phan = str(tok).split(".")[1]
        phan += "=" * (-len(phan) % 4)
        exp = json.loads(base64.urlsafe_b64decode(phan.encode()).decode()).get("exp")
        return int(exp) if exp else None
    except Exception:
        return None


def _lay(d, *ten):
    """Đọc trường bất kể MISA trả PascalCase hay camelCase."""
    if not isinstance(d, dict):
        return None
    for t in ten:
        for bien in (t, t[:1].upper() + t[1:], t[:1].lower() + t[1:]):
            if bien in d:
                return d[bien]
    return None


def _loi_misa(d):
    ma = _lay(d, "errorCode") or ""
    mo_ta = _lay(d, "descriptionErrorCode") or ""
    errs = _lay(d, "errors") or ""
    return " ".join(str(x) for x in (ma, mo_ta, errs if errs not in ([], "") else "") if x).strip()


async def _dang_nhap(spec):
    sec = k.bi_mat(spec)
    body = {"appid": sec["app_id"], "taxcode": sec["ma_so_thue"],
            "username": sec["ten_dang_nhap"], "password": sec["mat_khau"]}
    ok, d = await k.goi(TEN, "POST", f"{_goc(sec)}/auth/token", secrets=sec, json_body=body,
                        headers={"Content-Type": "application/json"})
    if not ok:
        return d
    tok = _lay(d, "data")
    if not isinstance(d, dict) or not _lay(d, "success") or not isinstance(tok, str) or not tok.strip():
        loi = _loi_misa(d) if isinstance(d, dict) else str(d)[:300]
        goi_y = ""
        if "UnAuthorize" in loi:
            goi_y = " Sai tên đăng nhập hoặc mật khẩu."
        elif "AppID" in loi:
            goi_y = " AppID sai hoặc đã bị MISA dừng, liên hệ MISA để cấp lại."
        return k.giau(f"ERROR: MISA meInvoice từ chối đăng nhập: {loi}.{goi_y}", sec)
    het = han_jwt(tok) or int(time.time()) + HAN_MAC_DINH
    k.luu_bi_mat(spec, {"access_token": tok.strip(), "token_het_han": het})
    return None


async def dam_bao_token(spec):
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        if sec.get("access_token") and k.con_han(sec, "token_het_han", du_phong=600):
            return None
        return await _dang_nhap(spec)


async def _goi_api(spec, method, path, params=None, body=None, thu_lai=True):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    sec = k.bi_mat(spec)
    ok, d = await k.goi(TEN, method, f"{_goc(sec)}{path}", secrets=sec, params=params, json_body=body,
                        headers={"Authorization": f"Bearer {sec['access_token']}",
                                 "Content-Type": "application/json"})
    if not ok:
        # Token bị MISA thu hồi trước hạn: xoá token, đăng nhập lại đúng một lần.
        if thu_lai and " 401:" in d:
            k.luu_bi_mat(spec, {"token_het_han": "1"})
            return await _goi_api(spec, method, path, params, body, thu_lai=False)
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: MISA meInvoice trả về không đúng dạng: {str(d)[:300]}", sec)
    if not _lay(d, "success"):
        if thu_lai and "TokenExpired" in str(_lay(d, "errorCode") or ""):
            k.luu_bi_mat(spec, {"token_het_han": "1"})
            return await _goi_api(spec, method, path, params, body, thu_lai=False)
        return False, k.giau(f"ERROR: MISA meInvoice báo lỗi: {_loi_misa(d) or 'không rõ lý do'}", sec)
    data = _lay(d, "data")
    if isinstance(data, str) and data.strip()[:1] in ("[", "{"):
        try:
            data = json.loads(data)
        except ValueError:
            pass
    return True, data


def _ds_ma(v):
    ma = k.ds(v)
    if not ma:
        return None, "ERROR: thiếu ma (mã tra cứu hoặc refID)"
    sai = [x for x in ma if not _MA.match(x)]
    if sai:
        return None, "ERROR: mã không hợp lệ (chỉ chữ, số, _ và -, dài 4 đến 64 ký tự): " + ", ".join(sai[:3])[:120]
    return ma[:TOI_DA_MA], None


def _bool(v):
    return "true" if v is True else "false"


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "app_id", "ma_so_thue", "ten_dang_nhap", "mat_khau")
    if t:
        return "ERROR: kết nối MISA meInvoice thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "meinvoice_mau_hoa_don":
        from datetime import datetime
        nam = k.so(a.get("nam"), datetime.now(k.mui_gio()).year, 2000, 2100)
        ok, d = await _goi_api(spec, "GET", "/invoice/templates",
                               {"invoiceWithCode": _bool(a.get("co_ma_cqt")), "ticket": _bool(a.get("ve")),
                                "year": str(nam)})
    elif tool == "meinvoice_trang_thai":
        ma, loi = _ds_ma(a.get("ma"))
        if loi:
            return loi
        loai = "2" if a.get("loai_ma") == "ref_id" else "1"
        ok, d = await _goi_api(spec, "POST", "/invoice/status",
                               {"invoiceWithCode": _bool(a.get("co_ma_cqt")),
                                "invoiceCalcu": _bool(a.get("may_tinh_tien")), "inputType": loai}, ma)
    elif tool == "meinvoice_link_xem":
        ma, loi = _ds_ma(a.get("ma"))
        if loi:
            return loi
        ok, d = await _goi_api(spec, "POST", "/invoice/publishview", None, ma)
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối MISA meInvoice"
    return k.json_ra(d) if ok else d
