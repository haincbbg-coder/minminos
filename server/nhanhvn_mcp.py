"""Cầu nối Nhanh.vn Open API v3 (transport "internal"). Mỗi kết nối = MỘT doanh nghiệp Nhanh.vn.

Nhanh.vn không có MCP chính chủ, nên MinMin tự bọc Open API v3.0 (apidocs.nhanh.vn/v3/readme.md):
- Host POS: https://pos.open.nhanh.vn/v3.0/<nhóm>/<hàm>?appId=<appId>&businessId=<businessId>
- Mọi request là POST thân JSON, header `Authorization: <accessToken>` (KHÔNG có chữ Bearer).
- Thành công: {"code": 1, "data": ..., "paginator": {"next": ...}}. Lỗi: {"code": 0, "errorCode",
  "messages"}. Trang sau: gửi lại NGUYÊN object `paginator.next` của trang trước.
- Giới hạn 150 request / 30 giây cho mỗi appId + businessId + endpoint.

Lấy accessToken (apidocs.nhanh.vn/app.md): chủ doanh nghiệp mở
https://nhanh.vn/oauth?appId=..&returnLink=.., đồng ý, được chuyển về returnLink kèm accessCode
(sống 10 phút). MinMin đổi accessCode + secretKey lấy accessToken qua
POST /v3.0/app/getaccesstoken?appId=.. rồi LƯU (mã hoá). Token sống khoảng 1 năm, không có
refresh: hết hạn thì ủy quyền lại. Ai đã có sẵn accessToken thì dán thẳng vào kết nối.

Bản này CHỈ ĐỌC: đơn hàng, chi tiết đơn, sản phẩm, chi tiết sản phẩm, tồn kho, khách hàng, kho.
Không có tool gọi thô: các API ghi của Nhanh cũng là POST nên không tách đọc/ghi theo phương thức được.
"""
from urllib.parse import urlencode

import ket_noi_api as k

HOST = "https://pos.open.nhanh.vn/v3.0"
TEN = "Nhanh.vn"
# Hằng số trạng thái đơn (apidocs.nhanh.vn/v3/modelconstant.md)
TRANG_THAI_DON = {40, 42, 43, 54, 55, 56, 57, 58, 59, 60, 61, 63, 64, 68, 71, 72, 73, 74}
TRANG_THAI_SP = {1, 2, 3, 4}
TOI_DA_NGAY = 31        # order/list chỉ cho lấy trong 31 ngày

_TRANG_TIEP = {"type": "object", "description": "dán nguyên paginator.next của trang trước để lấy trang sau"}
_SO_LUONG = {"type": "integer", "description": "số dòng mỗi trang, tối đa 100"}

TOOLS = [
    k.tool("nhanhvn_lien_ket_uy_quyen",
           "Tạo link để chủ doanh nghiệp ủy quyền app cho MinMin (khi kết nối mới hoặc token hết hạn). "
           "Mở link, đăng nhập Nhanh.vn, rồi dán accessCode trên địa chỉ trả về vào kết nối.",
           {"redirect_url": {"type": "string", "description": "địa chỉ trả về (Redirect URL) đã khai trong app Nhanh.vn"}}),
    k.tool("nhanhvn_don_hang",
           "Danh sách đơn hàng theo khoảng ngày tạo (tối đa 31 ngày mỗi lần).",
           {**k.NGAY_PROPS,
            "trang_thai": {"type": "string", "description": "mã trạng thái, cách nhau bởi dấu phẩy, ví dụ 60 (Thành công), 63 (Khách hủy)"},
            "kho": {"type": "string", "description": "các id kho, cách nhau bởi dấu phẩy"},
            "trang_tiep": _TRANG_TIEP, "so_luong": _SO_LUONG}),
    k.tool("nhanhvn_chi_tiet_don",
           "Chi tiết 1 đơn: khách, địa chỉ, sản phẩm, vận chuyển, thanh toán.",
           {"order_id": {"type": "string", "description": "id đơn hàng trên Nhanh.vn (dãy số)"}}, ["order_id"]),
    k.tool("nhanhvn_san_pham",
           "Danh sách sản phẩm: tên, mã, giá, tồn kho, ảnh.",
           {"tu_khoa": {"type": "string", "description": "tên, mã hoặc mã vạch"},
            "trang_thai": {"type": "string", "description": "1 Mới, 2 Đang bán, 3 Ngừng bán, 4 Hết hàng (có thể nhiều, cách nhau dấu phẩy)"},
            "trang_tiep": _TRANG_TIEP, "so_luong": _SO_LUONG}),
    k.tool("nhanhvn_chi_tiet_san_pham",
           "Chi tiết 1 sản phẩm theo id.",
           {"product_id": {"type": "string", "description": "id sản phẩm trên Nhanh.vn (dãy số)"}}, ["product_id"]),
    k.tool("nhanhvn_ton_kho",
           "Tồn kho từng sản phẩm, tách theo kho: còn lại, đang giao, tạm giữ, có thể bán.",
           {"tu_khoa": {"type": "string", "description": "tên, mã hoặc mã vạch"},
            "kho": {"type": "string", "description": "các id kho, cách nhau bởi dấu phẩy"},
            "trang_tiep": _TRANG_TIEP, "so_luong": _SO_LUONG}),
    k.tool("nhanhvn_khach_hang",
           "Danh sách khách hàng, lọc theo số điện thoại hoặc loại khách.",
           {"so_dien_thoai": {"type": "string"},
            "loai": {"type": "integer", "description": "1 khách lẻ, 2 khách buôn, 3 đại lý"},
            "trang_tiep": _TRANG_TIEP, "so_luong": _SO_LUONG}),
    k.tool("nhanhvn_kho", "Danh sách kho hàng của doanh nghiệp, dùng lấy id kho cho tồn kho và đơn hàng."),
]


async def list_tools(spec):
    return TOOLS


def _so_trong(v, cho_phep=None):
    ra = []
    for x in k.ds(v):
        if x.isdigit() and (cho_phep is None or int(x) in cho_phep):
            ra.append(int(x))
    return ra[:100]


def lien_ket_uy_quyen(sec, redirect_url):
    return "https://nhanh.vn/oauth?" + urlencode({"appId": sec["app_id"], "returnLink": redirect_url})


async def _doi_token(spec):
    sec = k.bi_mat(spec)
    code = str(sec.get("access_code") or "").strip()
    ok, d = await k.goi(TEN, "POST", f"{HOST}/app/getaccesstoken", secrets=sec,
                        params={"appId": str(sec["app_id"]).strip()},
                        json_body={"accessCode": code, "secretKey": sec["secret_key"]},
                        headers={"Content-Type": "application/json"})
    if not ok:
        return d
    goc = d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), dict) else d
    if not isinstance(goc, dict) or not goc.get("accessToken") or (isinstance(d, dict) and d.get("code") == 0):
        msg = (d.get("messages") or d.get("errorCode") or "") if isinstance(d, dict) else str(d)[:300]
        return k.giau(f"ERROR: Nhanh.vn từ chối cấp token: {str(msg)[:300]}. accessCode chỉ sống 10 phút, "
                      "tạo lại link bằng nhanhvn_lien_ket_uy_quyen.", sec)
    patch = {"access_token": goc["accessToken"], "access_code_da_dung": code}
    if goc.get("businessId"):
        patch["business_id"] = str(goc["businessId"])
    if goc.get("expiredAt"):
        patch["token_het_han"] = str(goc["expiredAt"])
    k.luu_bi_mat(spec, patch)
    return None


async def dam_bao_token(spec):
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("access_code") or "").strip()
        if code and code != str(sec.get("access_code_da_dung") or "") and str(sec.get("secret_key") or "").strip():
            return await _doi_token(spec)
        if sec.get("access_token"):
            if not k.con_han(sec, "token_het_han", du_phong=0):
                return ("ERROR: accessToken Nhanh.vn đã hết hạn. Gọi nhanhvn_lien_ket_uy_quyen để ủy quyền "
                        "lại, rồi dán accessCode mới vào kết nối.")
            return None
        return ("ERROR: doanh nghiệp chưa ủy quyền. Dán accessToken vào kết nối, hoặc điền Secret Key rồi "
                "gọi nhanhvn_lien_ket_uy_quyen để lấy accessCode.")


async def _post(spec, path, body):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    sec = k.bi_mat(spec)
    if not str(sec.get("business_id") or "").strip():
        return False, "ERROR: kết nối Nhanh.vn thiếu business_id (mã doanh nghiệp) - sửa lại ở trang Kết nối"
    ok, d = await k.goi(TEN, "POST", f"{HOST}{path}", secrets=sec,
                        params={"appId": str(sec["app_id"]).strip(), "businessId": str(sec["business_id"]).strip()},
                        json_body=body,
                        headers={"Authorization": str(sec["access_token"]), "Content-Type": "application/json"})
    if not ok:
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: Nhanh.vn trả về không đúng dạng: {str(d)[:300]}", sec)
    if d.get("code") != 1:
        return False, k.giau(f"ERROR: Nhanh.vn {d.get('errorCode', '')}: {str(d.get('messages', ''))[:300]}", sec)
    return True, {kk: d[kk] for kk in ("data", "paginator", "warning") if kk in d}


def _phan_trang(a, sort=None):
    p = {"size": k.so(a.get("so_luong"), 50, 1, 100)}
    if sort:
        p["sort"] = sort
    if isinstance(a.get("trang_tiep"), (dict, list)) and a.get("trang_tiep"):
        p["next"] = a["trang_tiep"]
    return p


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "app_id")
    if t:
        return "ERROR: kết nối Nhanh.vn thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "nhanhvn_lien_ket_uy_quyen":
        url = str(a.get("redirect_url") or sec.get("redirect_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return "ERROR: cần redirect_url (Redirect URL đã khai trong app Nhanh.vn), bắt đầu bằng https://"
        return lien_ket_uy_quyen(sec, url)

    if tool == "nhanhvn_don_hang":
        tu, den = k.khoang(a, mac_dinh_ngay=7, toi_da_ngay=TOI_DA_NGAY)
        f = {"createdAtFrom": tu, "createdAtTo": den}
        tt = _so_trong(a.get("trang_thai"), TRANG_THAI_DON)
        if tt:
            f["statuses"] = tt
        if _so_trong(a.get("kho")):
            f["depotIds"] = _so_trong(a.get("kho"))
        ok, d = await _post(spec, "/order/list", {"filters": f, "paginator": _phan_trang(a)})
    elif tool == "nhanhvn_chi_tiet_don":
        ma = str(a.get("order_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu order_id (dãy số)"
        ok, d = await _post(spec, "/order/list", {"filters": {"ids": [int(ma)]}, "paginator": {"size": 1}})
    elif tool == "nhanhvn_san_pham":
        f = {}
        if str(a.get("tu_khoa") or "").strip():
            f["name"] = str(a["tu_khoa"]).strip()[:200]
        tt = _so_trong(a.get("trang_thai"), TRANG_THAI_SP)
        if tt:
            f["status"] = tt
        ok, d = await _post(spec, "/product/list", {"filters": f, "paginator": _phan_trang(a, {"id": "desc"})})
    elif tool == "nhanhvn_chi_tiet_san_pham":
        ma = str(a.get("product_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu product_id (dãy số)"
        ok, d = await _post(spec, "/product/detail", {"filters": {"id": ma}})
    elif tool == "nhanhvn_ton_kho":
        f = {}
        if str(a.get("tu_khoa") or "").strip():
            f["name"] = str(a["tu_khoa"]).strip()[:200]
        if _so_trong(a.get("kho")):
            f["depotIds"] = _so_trong(a.get("kho"))
        ok, d = await _post(spec, "/product/inventory", {"filters": f, "paginator": _phan_trang(a)})
    elif tool == "nhanhvn_khach_hang":
        f = {}
        if str(a.get("so_dien_thoai") or "").strip():
            f["mobile"] = str(a["so_dien_thoai"]).strip()[:20]
        if str(a.get("loai") or "").strip() in ("1", "2", "3"):
            f["type"] = int(str(a["loai"]).strip())
        ok, d = await _post(spec, "/customer/list", {"filters": f, "paginator": _phan_trang(a)})
    elif tool == "nhanhvn_kho":
        ok, d = await _post(spec, "/business/depot", {"filters": {}})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Nhanh.vn"
    return k.json_ra(d) if ok else d

