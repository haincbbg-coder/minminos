"""Cầu nối Viettel Post Partner API v2 (transport "internal"). Mỗi kết nối = MỘT tài khoản Viettel Post.

Gọi API (đối chiếu tài liệu kết nối API TMĐT của Viettel Post và các bản tích hợp đang chạy):
  host  = https://partner.viettelpost.vn (môi trường thử: https://partnerdev.viettelpost.vn)
  đăng nhập: POST /v2/user/Login {USERNAME, PASSWORD} -> data.token (token ngắn hạn)
             POST /v2/user/ownerconnect, header Token: <token ngắn hạn>, cùng body -> token dài hạn
  mọi API khác: header Token: <token>, Content-Type JSON
  trả về {status: 200, error: false, message, data}; error true hoặc status khác 200 là lỗi.

Token được lưu (đã mã hoá) vào kết nối kèm mốc hết hạn và dấu của tài khoản đã đăng nhập; đổi
tài khoản hoặc hết hạn thì đăng nhập lại. Bị từ chối vì token (401/403) thì đăng nhập lại ĐÚNG
MỘT lần rồi gọi lại. Đăng nhập đi qua khoá của kết nối để hai lượt gọi không cùng đăng nhập.

Đọc: tỉnh/quận/phường, kho hàng (điểm lấy hàng), dịch vụ khả dụng kèm giá, tính phí một dịch vụ.
Ghi (NGUY HIỂM, tốn tiền thật): tạo đơn, hủy đơn (UpdateOrder TYPE=4). Đầu vào kiểm chặt trước
khi gọi mạng. Chưa có tool tra hành trình: tài liệu đối tác không công bố API tra cứu đơn.
"""
import hashlib
import re
import time
from datetime import datetime

import ket_noi_api as k

HOST_LIVE = "https://partner.viettelpost.vn"
HOST_TEST = "https://partnerdev.viettelpost.vn"
TEN = "ViettelPost"
COD_TOI_DA = 50_000_000
GIA_TRI_TOI_DA = 1_000_000_000
KHOI_LUONG_TOI_DA = 100_000          # gram
TOKEN_MAC_DINH = 3 * 86400           # giây, khi API không trả mốc hết hạn
_MA_DON = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
_MA_DV = re.compile(r"^[A-Za-z0-9_]{1,20}$")
_MA_DV_THEM = re.compile(r"^[A-Za-z0-9_,]{0,100}$")

_DIA_GIOI = {
    "sender_province": {"type": "integer", "description": "mã tỉnh gửi (PROVINCE_ID của Viettel Post)"},
    "sender_district": {"type": "integer", "description": "mã quận gửi (DISTRICT_ID)"},
    "receiver_province": {"type": "integer", "description": "mã tỉnh nhận"},
    "receiver_district": {"type": "integer", "description": "mã quận nhận"},
}
_HANG = {
    "product_type": {"type": "string", "enum": ["HH", "TH"], "description": "HH = hàng hoá (mặc định), TH = thư"},
    "product_weight": {"type": "integer", "description": "khối lượng gram"},
    "product_price": {"type": "integer", "description": "giá trị hàng (đồng)"},
    "money_collection": {"type": "integer", "description": "tiền thu hộ (đồng), mặc định 0"},
}

TOOLS = [
    k.tool("vtp_tinh_thanh", "Danh sách tỉnh/thành theo mã Viettel Post (PROVINCE_ID)."),
    k.tool("vtp_quan_huyen", "Danh sách quận/huyện của một tỉnh theo mã Viettel Post (DISTRICT_ID).",
           {"province_id": {"type": "integer", "description": "mã tỉnh Viettel Post"}}, ["province_id"]),
    k.tool("vtp_phuong_xa", "Danh sách phường/xã của một quận theo mã Viettel Post (WARDS_ID).",
           {"district_id": {"type": "integer", "description": "mã quận Viettel Post"}}, ["district_id"]),
    k.tool("vtp_kho_hang", "Danh sách kho hàng (điểm lấy hàng) của tài khoản: GROUPADDRESS_ID, CUS_ID, tên, địa chỉ."),
    k.tool("vtp_dich_vu_va_gia", "Các dịch vụ Viettel Post khả dụng giữa hai quận kèm giá dự kiến (không tạo đơn).",
           {**_DIA_GIOI, **_HANG}, ["sender_province", "sender_district", "receiver_province",
                                    "receiver_district", "product_weight"]),
    k.tool("vtp_tinh_phi", "Tính phí một dịch vụ Viettel Post cụ thể (không tạo đơn).",
           {**_DIA_GIOI, **_HANG,
            "order_service": {"type": "string", "description": "mã dịch vụ, ví dụ VCN, VTK (lấy từ vtp_dich_vu_va_gia)"},
            "order_service_add": {"type": "string", "description": "mã dịch vụ cộng thêm, cách nhau dấu phẩy"}},
           ["sender_province", "sender_district", "receiver_province", "receiver_district",
            "product_weight", "order_service"]),
    k.tool("vtp_tao_don",
           "TẠO ĐƠN GIAO HÀNG THẬT trên Viettel Post (phát sinh phí, không hoàn tác được). Chỉ gọi khi chủ shop đã "
           "xác nhận đủ người nhận, khối lượng, tiền thu hộ. Người gửi: truyền groupaddress_id + cus_id (từ "
           "vtp_kho_hang) hoặc đủ thông tin người gửi.",
           {"order_number": {"type": "string", "description": "mã đơn riêng của shop (chữ, số, _ và -)"},
            "groupaddress_id": {"type": "integer", "description": "mã kho lấy hàng (GROUPADDRESS_ID)"},
            "cus_id": {"type": "integer", "description": "mã khách hàng (CUS_ID) đi kèm kho"},
            "sender_fullname": {"type": "string"}, "sender_phone": {"type": "string"},
            "sender_address": {"type": "string"},
            "sender_province": {"type": "integer"}, "sender_district": {"type": "integer"},
            "sender_ward": {"type": "integer"},
            "receiver_fullname": {"type": "string"}, "receiver_phone": {"type": "string", "description": "9 đến 11 chữ số"},
            "receiver_address": {"type": "string"},
            "receiver_province": {"type": "integer"}, "receiver_district": {"type": "integer"},
            "receiver_ward": {"type": "integer"},
            "product_name": {"type": "string"}, "product_description": {"type": "string"},
            "product_quantity": {"type": "integer", "description": "mặc định 1"},
            **_HANG,
            "product_length": {"type": "integer", "description": "cm"},
            "product_width": {"type": "integer", "description": "cm"},
            "product_height": {"type": "integer", "description": "cm"},
            "order_payment": {"type": "integer", "enum": [1, 2, 3],
                              "description": "1 = không thu tiền, 2 = thu hộ tiền hàng và cước, 3 = chỉ thu hộ tiền hàng"},
            "order_service": {"type": "string", "description": "mã dịch vụ, ví dụ VCN"},
            "order_service_add": {"type": "string"},
            "order_note": {"type": "string"},
            "list_item": {"type": "array", "description": "[{name, quantity, price?, weight?}]", "items": {"type": "object"}}},
           ["order_number", "receiver_fullname", "receiver_phone", "receiver_address", "receiver_province",
            "receiver_district", "receiver_ward", "product_name", "product_weight", "order_payment", "order_service"]),
    k.tool("vtp_huy_don", "HỦY ĐƠN VIETTEL POST THẬT (không hoàn tác được) theo mã vận đơn.",
           {"order_number": {"type": "string", "description": "mã vận đơn Viettel Post"},
            "ghi_chu": {"type": "string", "description": "lý do hủy"}}, ["order_number"]),
]


async def list_tools(spec):
    return TOOLS


def host(sec):
    return HOST_TEST if str(sec.get("moi_truong") or "").strip().lower() == "test" else HOST_LIVE


def _so_nguyen(v, nho, lon):
    """Số nguyên trong [nho, lon] hoặc None. Không nhận bool, số lẻ, chuỗi rác."""
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


def _mac_dinh(v, md):
    return md if v is None or (isinstance(v, str) and not v.strip()) else v


def _chuoi(v, toi_da=255):
    s = str(v if v is not None else "").strip()
    return s if 0 < len(s) <= toi_da else None


def _sdt(v):
    s = re.sub(r"[\s.\-]", "", str(v or ""))
    return s if re.fullmatch(r"\d{9,11}", s) else None


def _dau_tk(sec):
    """Dấu của tài khoản đã đăng nhập: đổi tên đăng nhập hoặc mật khẩu thì token cũ bỏ đi."""
    raw = f"{sec.get('username', '')}\n{sec.get('password', '')}\n{host(sec)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _ma_http(loi):
    m = re.match(rf"ERROR: {TEN} (\d{{3}}):", str(loi))
    return int(m.group(1)) if m else None


def _phong_bi(sec, d):
    """Mở lớp {status, error, message, data}. Trả (ok, data hoặc câu lỗi, mã status).
    getPriceAll có bản trả thẳng một danh sách dịch vụ không bọc lớp nào: nhận luôn."""
    if isinstance(d, list):
        return True, d, 200
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: {TEN} trả về không đúng dạng: {str(d)[:300]}", sec), None
    st = d.get("status")
    if d.get("error") is True or (st is not None and st != 200):
        return False, k.giau(f"ERROR: {TEN} {st}: {str(d.get('message', ''))[:400]}", sec), st
    return True, d.get("data"), st


async def _dang_nhap(spec):
    """Đăng nhập lấy token, ưu tiên token dài hạn (ownerconnect). Trả câu lỗi hoặc None."""
    sec = k.bi_mat(spec)
    tk = {"USERNAME": str(sec["username"]).strip(), "PASSWORD": str(sec["password"])}
    h = {"Content-Type": "application/json"}
    ok, d = await k.goi(TEN, "POST", host(sec) + "/v2/user/Login", secrets=sec, json_body=tk, headers=h)
    if not ok:
        return d
    ok, data, _ = _phong_bi(sec, d)
    if not ok:
        return data
    tok = str((data or {}).get("token") or "") if isinstance(data, dict) else ""
    if not tok:
        return "ERROR: Viettel Post không trả token khi đăng nhập, kiểm tra tên đăng nhập và mật khẩu"
    het = (data or {}).get("expired")
    # Token dài hạn: không lấy được thì vẫn dùng token đăng nhập (tài khoản chủ shop thường đủ quyền).
    sec2 = {**sec, "access_token": tok}
    ok2, d2 = await k.goi(TEN, "POST", host(sec) + "/v2/user/ownerconnect", secrets=sec2, json_body=tk,
                          headers={**h, "Token": tok})
    if ok2:
        ok2, data2, _ = _phong_bi(sec2, d2)
        if ok2 and isinstance(data2, dict) and data2.get("token"):
            tok, het = str(data2["token"]), data2.get("expired")
    try:
        het = float(het or 0)
    except (TypeError, ValueError):
        het = 0
    if het > 1e12:              # mili giây
        het = het / 1000
    if het <= time.time() + 600:
        het = time.time() + TOKEN_MAC_DINH
    k.luu_bi_mat(spec, {"access_token": tok, "token_het_han": int(het), "token_tk": _dau_tk(sec)})
    return None


async def _token(spec, cu=None):
    """(token, lỗi). `cu` = token vừa bị từ chối: chỉ đăng nhập lại nếu chưa ai làm mới nó."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        tok = str(sec.get("access_token") or "")
        hop_le = tok and k.con_han(sec, "token_het_han") and sec.get("token_tk") == _dau_tk(sec)
        if hop_le and tok != cu:
            return tok, None
        loi = await _dang_nhap(spec)
        if loi:
            return None, loi
        return str(k.bi_mat(spec).get("access_token") or ""), None


async def _goi(spec, method, path, *, params=None, body=None):
    """Gọi API có token; bị từ chối vì token thì đăng nhập lại đúng một lần."""
    tok, loi = await _token(spec)
    if loi:
        return False, loi
    for lan in range(2):
        sec = k.bi_mat(spec)
        h = {"Token": tok, "Content-Type": "application/json"}
        ok, d = await k.goi(TEN, method, host(sec) + path, secrets={**sec, "access_token": tok},
                            params=params, json_body=body, headers=h)
        if ok:
            ok, data, st = _phong_bi({**sec, "access_token": tok}, d)
            if ok:
                return True, data
            ma = st
        else:
            data, ma = d, _ma_http(d)
        if ma in (401, 403) and lan == 0:
            tok, loi = await _token(spec, cu=tok)
            if loi:
                return False, loi
            continue
        return False, data
    return False, data


def _dia_gioi(a):
    """(body, lỗi) cho bốn mã tỉnh/quận gửi-nhận."""
    body, sai = {}, []
    for kk in ("sender_province", "sender_district", "receiver_province", "receiver_district"):
        v = _so_nguyen(a.get(kk), 1, 10**9)
        if v is None:
            sai.append(kk)
        body[kk.upper()] = v
    return body, ("ERROR: cần mã số cho " + ", ".join(sai)) if sai else None


def _hang(a, body):
    """Thêm PRODUCT_TYPE/WEIGHT/PRICE/MONEY_COLLECTION vào body. Trả lỗi hoặc None."""
    pt = str(_mac_dinh(a.get("product_type"), "HH")).strip().upper()
    if pt not in ("HH", "TH"):
        return "ERROR: product_type chỉ nhận HH hoặc TH"
    w = _so_nguyen(a.get("product_weight"), 1, KHOI_LUONG_TOI_DA)
    if w is None:
        return f"ERROR: product_weight phải từ 1 đến {KHOI_LUONG_TOI_DA} gram"
    gia = _so_nguyen(_mac_dinh(a.get("product_price"), 0), 0, GIA_TRI_TOI_DA)
    if gia is None:
        return "ERROR: product_price phải là số đồng không âm"
    cod = _so_nguyen(_mac_dinh(a.get("money_collection"), 0), 0, COD_TOI_DA)
    if cod is None:
        return "ERROR: money_collection phải từ 0 đến 50.000.000 đồng"
    body.update({"PRODUCT_TYPE": pt, "PRODUCT_WEIGHT": w, "PRODUCT_PRICE": gia, "MONEY_COLLECTION": cod})
    return None


def _dich_vu(a, body, bat_buoc):
    sv = str(a.get("order_service") or "").strip().upper()
    if not sv:
        return "ERROR: cần order_service (mã dịch vụ, ví dụ VCN)" if bat_buoc else None
    if not _MA_DV.match(sv):
        return "ERROR: order_service chỉ gồm chữ, số và _"
    add = str(a.get("order_service_add") or "").strip().upper().replace(" ", "")
    if not _MA_DV_THEM.match(add):
        return "ERROR: order_service_add chỉ gồm mã dịch vụ cách nhau dấu phẩy"
    body.update({"ORDER_SERVICE": sv, "ORDER_SERVICE_ADD": add})
    return None


def _don_tao(a):
    """Kiểm tra đầu vào tạo đơn. Trả (body, lỗi)."""
    loi = []
    body = {}
    ma = str(a.get("order_number") or "").strip()
    if not _MA_DON.match(ma):
        loi.append("order_number chỉ gồm chữ, số, _ và -, tối đa 50 ký tự")
    body["ORDER_NUMBER"] = ma
    # Người gửi: kho đã khai (GROUPADDRESS_ID + CUS_ID) hoặc đủ thông tin người gửi.
    gid, cid = a.get("groupaddress_id"), a.get("cus_id")
    co_kho = gid not in (None, "") or cid not in (None, "")
    if co_kho:
        g, c = _so_nguyen(gid, 1, 10**12), _so_nguyen(cid, 1, 10**12)
        if g is None or c is None:
            loi.append("groupaddress_id và cus_id phải đi cùng nhau và là số (lấy từ vtp_kho_hang)")
        body.update({"GROUPADDRESS_ID": g, "CUS_ID": c})
    gui_du = True
    for kk, kt in (("sender_fullname", 100), ("sender_address", 500)):
        if a.get(kk) not in (None, ""):
            v = _chuoi(a.get(kk), kt)
            if v is None:
                loi.append(f"{kk} quá dài")
            body[kk.upper()] = v
        else:
            gui_du = False
    if a.get("sender_phone") not in (None, ""):
        v = _sdt(a.get("sender_phone"))
        if v is None:
            loi.append("sender_phone phải là 9 đến 11 chữ số")
        body["SENDER_PHONE"] = v
    else:
        gui_du = False
    for kk in ("sender_province", "sender_district", "sender_ward"):
        if a.get(kk) not in (None, ""):
            v = _so_nguyen(a.get(kk), 1, 10**9)
            if v is None:
                loi.append(f"{kk} phải là mã số")
            body[kk.upper()] = v
        else:
            gui_du = False
    if not co_kho and not gui_du:
        loi.append("thiếu người gửi: truyền groupaddress_id + cus_id, hoặc đủ sender_fullname, sender_phone, "
                   "sender_address, sender_province, sender_district, sender_ward")
    ten = _chuoi(a.get("receiver_fullname"), 100)
    if not ten:
        loi.append("receiver_fullname (tên người nhận)")
    sdt = _sdt(a.get("receiver_phone"))
    if not sdt:
        loi.append("receiver_phone phải là 9 đến 11 chữ số")
    dc = _chuoi(a.get("receiver_address"), 500)
    if not dc:
        loi.append("receiver_address (địa chỉ nhận)")
    body.update({"RECEIVER_FULLNAME": ten, "RECEIVER_PHONE": sdt, "RECEIVER_ADDRESS": dc})
    for kk in ("receiver_province", "receiver_district", "receiver_ward"):
        v = _so_nguyen(a.get(kk), 1, 10**9)
        if v is None:
            loi.append(f"{kk} (mã số Viettel Post)")
        body[kk.upper()] = v
    tsp = _chuoi(a.get("product_name"), 200)
    if not tsp:
        loi.append("product_name (tên hàng)")
    body["PRODUCT_NAME"] = tsp
    sl = _so_nguyen(_mac_dinh(a.get("product_quantity"), 1), 1, 10000)
    if sl is None:
        loi.append("product_quantity phải từ 1 đến 10000")
    body["PRODUCT_QUANTITY"] = sl
    e = _hang(a, body)
    if e:
        loi.append(e.replace("ERROR: ", ""))
    for kk in ("product_length", "product_width", "product_height"):
        if a.get(kk) not in (None, ""):
            v = _so_nguyen(a.get(kk), 1, 300)
            if v is None:
                loi.append(f"{kk} phải từ 1 đến 300 cm")
            body[kk.upper()] = v
    for kk, kt in (("product_description", 500), ("order_note", 500)):
        if a.get(kk) not in (None, ""):
            v = _chuoi(a.get(kk), kt)
            if v is None:
                loi.append(f"{kk} quá dài")
            body[kk.upper()] = v
    op = _so_nguyen(a.get("order_payment"), 1, 3)
    if op is None:
        loi.append("order_payment chỉ nhận 1, 2 hoặc 3")
    body["ORDER_PAYMENT"] = op
    e = _dich_vu(a, body, bat_buoc=True)
    if e:
        loi.append(e.replace("ERROR: ", ""))
    items = []
    raw = a.get("list_item")
    if raw not in (None, ""):
        if not isinstance(raw, list) or len(raw) > 100:
            loi.append("list_item phải là danh sách tối đa 100 món")
        else:
            for i, it in enumerate(raw):
                if not isinstance(it, dict):
                    loi.append(f"list_item[{i}] không đúng dạng")
                    continue
                n = _chuoi(it.get("name"), 200)
                q = _so_nguyen(it.get("quantity"), 1, 10000)
                p = _so_nguyen(_mac_dinh(it.get("price"), 0), 0, GIA_TRI_TOI_DA)
                w = _so_nguyen(_mac_dinh(it.get("weight"), 0), 0, KHOI_LUONG_TOI_DA)
                if not n or q is None or p is None or w is None:
                    loi.append(f"list_item[{i}] cần name, quantity 1 đến 10000, price và weight là số không âm")
                    continue
                items.append({"PRODUCT_NAME": n, "PRODUCT_QUANTITY": q, "PRODUCT_PRICE": p, "PRODUCT_WEIGHT": w})
    if not items and tsp and sl and body.get("PRODUCT_WEIGHT"):
        items = [{"PRODUCT_NAME": tsp, "PRODUCT_QUANTITY": sl, "PRODUCT_PRICE": body.get("PRODUCT_PRICE") or 0,
                  "PRODUCT_WEIGHT": body["PRODUCT_WEIGHT"]}]
    body["LIST_ITEM"] = items
    if loi:
        return None, "ERROR: không tạo đơn Viettel Post vì đầu vào sai: " + "; ".join(loi)
    body["DELIVERY_DATE"] = datetime.now(k.mui_gio()).strftime("%d/%m/%Y %H:%M:%S")
    return body, None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "username", "password")
    if t:
        return "ERROR: kết nối Viettel Post thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "vtp_tinh_thanh":
        ok, d = await _goi(spec, "GET", "/v2/categories/listProvince")
    elif tool == "vtp_quan_huyen":
        pid = _so_nguyen(a.get("province_id"), 1, 10**9)
        if pid is None:
            return "ERROR: thiếu province_id (số)"
        ok, d = await _goi(spec, "GET", "/v2/categories/listDistrict", params={"provinceId": pid})
    elif tool == "vtp_phuong_xa":
        did = _so_nguyen(a.get("district_id"), 1, 10**9)
        if did is None:
            return "ERROR: thiếu district_id (số)"
        ok, d = await _goi(spec, "GET", "/v2/categories/listWards", params={"districtId": did})
    elif tool == "vtp_kho_hang":
        ok, d = await _goi(spec, "GET", "/v2/user/listInventory")
    elif tool in ("vtp_dich_vu_va_gia", "vtp_tinh_phi"):
        body, loi = _dia_gioi(a)
        if loi:
            return loi
        loi = _hang(a, body)
        if loi:
            return loi
        if tool == "vtp_dich_vu_va_gia":
            body["TYPE"] = 1
            ok, d = await _goi(spec, "POST", "/v2/order/getPriceAll", body=body)
        else:
            loi = _dich_vu(a, body, bat_buoc=True)
            if loi:
                return loi
            body["NATIONAL_TYPE"] = 1
            ok, d = await _goi(spec, "POST", "/v2/order/getPrice", body=body)
    elif tool == "vtp_tao_don":
        body, loi = _don_tao(a)
        if loi:
            return loi
        ok, d = await _goi(spec, "POST", "/v2/order/createOrder", body=body)
    elif tool == "vtp_huy_don":
        ma = str(a.get("order_number") or "").strip()
        if not _MA_DON.match(ma):
            return "ERROR: order_number chỉ gồm chữ, số, _ và -, tối đa 50 ký tự"
        note = str(a.get("ghi_chu") or "").strip()
        if len(note) > 500:
            return "ERROR: ghi_chu quá dài (tối đa 500 ký tự)"
        ok, d = await _goi(spec, "POST", "/v2/order/UpdateOrder",
                           body={"TYPE": 4, "ORDER_NUMBER": ma, "NOTE": note or "Hủy đơn"})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Viettel Post"
    return k.giau(k.json_ra(d), k.bi_mat(spec)) if ok else d
