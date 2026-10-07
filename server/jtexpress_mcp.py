"""Cầu nối J&T Express Việt Nam (transport "internal"). Mỗi kết nối = MỘT tài khoản đối tác J&T.

J&T Việt Nam CHỈ cấp API cho khách đã ký hợp đồng: mã nguồn khách (eccompanyid), khoá ký (key) và
địa chỉ máy chủ API do J&T gửi riêng, tài liệu đầy đủ không công khai. Bản này chỉ làm phần đã đối
chiếu được với tài liệu kết nối API của J&T Việt Nam (api-docs.jtexpress.vn và bản tài liệu PDF):

  gửi    = POST form (application/x-www-form-urlencoded) bốn ô:
           logistics_interface (chuỗi JSON nghiệp vụ), data_digest, msg_type, eccompanyid
  ký     = data_digest = base64( md5_hex( logistics_interface + key ) )
           (ví dụ trong tài liệu giải base64 ra đúng 32 ký tự hex, nên băm ra chuỗi hex rồi mới base64)
  trả về = {logisticproviderid, responseitems: [{success: "true"/"false", reason, ...}]}

Đọc: tra hành trình theo mã vận đơn (msg_type TRACKQUERY, /standart/trackAction!trackForJson).
Ghi (NGUY HIỂM): hủy đơn chưa được điều bưu tá đi lấy (msg_type UPDATE, fieldvalue WITHDRAW,
/order/orderAction!createOrder).

CHƯA làm (không đối chiếu được đủ trường): tạo đơn (thiếu đặc tả trường người gửi/nhận) và tra giá
(tài liệu không ghi msg_type). Địa chỉ máy chủ thật cũng không công khai nên người dùng tự điền.
"""
import base64
import hashlib
import json
import re

import ket_noi_api as k

TEN = "J&T"
_MA = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_DIA_CHI = re.compile(r"^(https?://)?([A-Za-z0-9._-]+)(:\d{1,5})?((?:/[A-Za-z0-9._~-]+)*)/?$")
NGON_NGU = ["en", "vn"]

TOOLS = [
    k.tool("jt_tra_hanh_trinh", "Hành trình (các mốc quét) của một vận đơn J&T Express theo mã vận đơn (billcode).",
           {"billcode": {"type": "string", "description": "mã vận đơn J&T"},
            "ngon_ngu": {"type": "string", "enum": NGON_NGU, "description": "ngôn ngữ mô tả mốc, mặc định en"}},
           ["billcode"]),
    k.tool("jt_huy_don",
           "HỦY ĐƠN J&T THẬT (không hoàn tác được) theo mã đơn của shop (txlogisticid). Chỉ hủy được khi J&T chưa "
           "điều bưu tá đi lấy hàng.",
           {"txlogisticid": {"type": "string", "description": "mã đơn của shop đã gửi khi tạo đơn"},
            "ly_do": {"type": "string", "description": "lý do hủy"}},
           ["txlogisticid"]),
]


async def list_tools(spec):
    return TOOLS


def ky(logistics_interface, key):
    """data_digest theo tài liệu J&T Việt Nam: base64 của md5 dạng hex (chữ thường)."""
    hx = hashlib.md5((logistics_interface + key).encode("utf-8")).hexdigest()
    return base64.b64encode(hx.encode("ascii")).decode("ascii")


def dia_chi(sec):
    """(base_url, lỗi). Chỉ nhận máy chủ + đường dẫn gốc, không query, không tài khoản trong URL.
    Không ghi giao thức thì dùng https; http chỉ dùng khi người dùng tự ghi rõ http://."""
    raw = str(sec.get("dia_chi_api") or "").strip()
    m = _DIA_CHI.match(raw)
    if not m or ".." in raw or "@" in raw:
        return None, ("ERROR: Địa chỉ máy chủ API J&T không hợp lệ: chỉ gồm tên máy chủ và đường dẫn gốc "
                      "(J&T gửi khi ký hợp đồng), không chứa ? # @ hay .. - sửa lại ở trang Kết nối")
    giao_thuc = m.group(1) or "https://"
    return f"{giao_thuc}{m.group(2)}{m.group(3) or ''}{m.group(4) or ''}", None


def _goi_dong_goi(sec, msg_type, nghiep_vu):
    li = json.dumps(nghiep_vu, ensure_ascii=False, separators=(",", ":"))
    return {"logistics_interface": li, "data_digest": ky(li, str(sec["api_key"])),
            "msg_type": msg_type, "eccompanyid": str(sec["eccompanyid"]).strip()}


async def _goi(sec, duong_dan, msg_type, nghiep_vu):
    base, loi = dia_chi(sec)
    if loi:
        return False, loi
    ok, d = await k.goi(TEN, "POST", base + duong_dan, secrets=sec, data=_goi_dong_goi(sec, msg_type, nghiep_vu),
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not ok:
        return False, d
    if not isinstance(d, dict) or not isinstance(d.get("responseitems"), list):
        return False, k.giau(f"ERROR: J&T trả về không đúng dạng: {str(d)[:300]}", sec)
    hong = [it for it in d["responseitems"] if not isinstance(it, dict) or str(it.get("success")).lower() != "true"]
    if hong or not d["responseitems"]:
        ly_do = ", ".join(str((it or {}).get("reason", "")) for it in hong if isinstance(it, dict)) or "không rõ"
        return False, k.giau(f"ERROR: J&T từ chối (mã lý do: {ly_do[:300]})", sec)
    return True, d


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "dia_chi_api", "eccompanyid", "api_key")
    if t:
        return "ERROR: kết nối J&T Express thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    a = arguments or {}

    if tool == "jt_tra_hanh_trinh":
        ma = str(a.get("billcode") or "").strip()
        if not _MA.match(ma):
            return "ERROR: billcode chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        nn = str(a.get("ngon_ngu") or "en").strip().lower()
        if nn not in NGON_NGU:
            return "ERROR: ngon_ngu chỉ nhận " + ", ".join(NGON_NGU)
        ok, d = await _goi(sec, "/standart/trackAction!trackForJson", "TRACKQUERY", {"billcode": ma, "lang": nn})
    elif tool == "jt_huy_don":
        ma = str(a.get("txlogisticid") or "").strip()
        if not _MA.match(ma):
            return "ERROR: txlogisticid chỉ gồm chữ, số, _ và -, tối đa 40 ký tự"
        ly_do = str(a.get("ly_do") or "").strip()
        if len(ly_do) > 200:
            return "ERROR: ly_do quá dài (tối đa 200 ký tự)"
        ok, d = await _goi(sec, "/order/orderAction!createOrder", "UPDATE", {
            "eccompanyid": str(sec["eccompanyid"]).strip(), "logisticproviderid": "JNT",
            "fieldlist": [{"txlogisticid": ma, "fieldname": "status", "fieldvalue": "WITHDRAW",
                           "remark": ly_do or "Shop hủy đơn"}]})
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối J&T Express"
    return k.giau(k.json_ra(d), sec) if ok else d
