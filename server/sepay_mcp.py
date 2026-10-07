"""Cầu nối SePay (transport "internal"). Mỗi kết nối = MỘT tài khoản SePay (một công ty).

SePay theo dõi biến động số dư các tài khoản ngân hàng đã liên kết. Một tài khoản SePay có thể
gắn nhiều tài khoản ngân hàng, lọc bằng `account_number`. Hai công ty SePay khác nhau thì thêm hai
kết nối.

API (docs.sepay.vn):
  base   https://my.sepay.vn/userapi
  header Authorization: Bearer <api_token>   (tạo ở my.sepay.vn > Cấu hình công ty > API Access)
  GET /bankaccounts/list
  GET /transactions/list    account_number, transaction_date_min, transaction_date_max, since_id,
                            limit (tối đa 5000), reference_number, amount_in, amount_out
  GET /transactions/details/{id}
  GET /transactions/count   account_number, transaction_date_min, transaction_date_max, since_id
Trả về {status: 200, error: null, messages: {success: true}, ...}. Số tiền là chuỗi "100000.00".

Ngày: tài liệu ghi định dạng yyyy-mm-dd nhưng so sánh với thời điểm giao dịch, nên chỉ gửi
"2026-10-07" làm mốc CUỐI sẽ hiểu là 00:00:00 và bỏ sót cả ngày hôm đó. Vì vậy gửi đủ giờ
("YYYY-MM-DD 00:00:00" và "YYYY-MM-DD 23:59:59", giờ Việt Nam), đúng như ví dụ URL của SePay.

Bản này CHỈ ĐỌC. `sepay_tong_hop` tự cộng tiền vào / tiền ra ngay trong MinMin từ danh sách giao
dịch, tiện cho câu hỏi kiểu "hôm nay vào bao nhiêu tiền".
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import ket_noi_api as k

HOST = "https://my.sepay.vn/userapi"
TEN = "SePay"
TOI_DA = 5000
_SO_TK = re.compile(r"^[A-Za-z0-9]{1,40}$")
_MA_THAM_CHIEU = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_LOC = {
    "account_number": {"type": "string", "description": "số tài khoản ngân hàng cần lọc (bỏ trống = mọi tài khoản)"},
    **k.NGAY_PROPS,
    "since_id": {"type": "string", "description": "chỉ lấy giao dịch có id >= số này"},
}
_LOC_THEM = {
    "reference_number": {"type": "string", "description": "mã tham chiếu giao dịch của ngân hàng"},
    "amount_in": {"type": "number", "description": "đúng số tiền vào (VND)"},
    "amount_out": {"type": "number", "description": "đúng số tiền ra (VND)"},
}

TOOLS = [
    k.tool("sepay_tai_khoan_ngan_hang",
           "Danh sách tài khoản ngân hàng đã liên kết với SePay: ngân hàng, số tài khoản, chủ tài khoản, "
           "số dư tích lũy."),
    k.tool("sepay_giao_dich",
           "Danh sách giao dịch ngân hàng (tiền vào, tiền ra, nội dung chuyển khoản) theo khoảng ngày, "
           "mặc định 7 ngày gần nhất, mới nhất trước.",
           {**_LOC, **_LOC_THEM,
            "limit": {"type": "integer", "description": "số giao dịch tối đa, mặc định 100, tối đa 5000"}}),
    k.tool("sepay_chi_tiet_giao_dich", "Chi tiết 1 giao dịch theo id SePay.",
           {"id": {"type": "string", "description": "id giao dịch (dãy số)"}}, ["id"]),
    k.tool("sepay_dem_giao_dich",
           "Đếm số giao dịch theo tài khoản và khoảng ngày (mặc định 7 ngày gần nhất).", _LOC),
    k.tool("sepay_tong_hop",
           "Tổng tiền vào, tổng tiền ra, số giao dịch và chia theo từng tài khoản trong khoảng ngày. "
           "Mặc định là HÔM NAY. Dùng cho câu hỏi 'hôm nay vào bao nhiêu tiền'.",
           {"account_number": _LOC["account_number"],
            "tu_ngay": {"type": "string", "description": "từ ngày YYYY-MM-DD (giờ VN), mặc định hôm nay"},
            "den_ngay": {"type": "string", "description": "đến ngày YYYY-MM-DD, mặc định hôm nay"}}),
]


async def list_tools(spec):
    return TOOLS


def _ngay(ts):
    return datetime.fromtimestamp(ts, k.mui_gio()).strftime("%Y-%m-%d")


def tien(v):
    """'100000.00' / 100000 / None -> Decimal. Sai dạng -> 0."""
    try:
        d = Decimal(str(v if v not in (None, "") else "0").strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal(0)
    return d if d.is_finite() else Decimal(0)


def _so_ra(d):
    """Decimal -> int nếu chẵn đồng, ngược lại float (để JSON gọn)."""
    return int(d) if d == d.to_integral_value() else float(d)


def _loc(a, mac_dinh_ngay=7, them=False):
    """Dựng tham số lọc. Trả (params, None) hoặc (None, câu lỗi)."""
    tu, den = k.khoang(a, mac_dinh_ngay=mac_dinh_ngay)
    p = {"transaction_date_min": _ngay(tu) + " 00:00:00",
         "transaction_date_max": _ngay(den) + " 23:59:59"}
    stk = str(a.get("account_number") or "").strip()
    if stk:
        if not _SO_TK.match(stk):
            return None, "ERROR: account_number chỉ gồm chữ và số"
        p["account_number"] = stk
    sid = str(a.get("since_id") or "").strip()
    if sid:
        if not sid.isdigit():
            return None, "ERROR: since_id phải là dãy số"
        p["since_id"] = sid
    if not them:
        return p, None
    ref = str(a.get("reference_number") or "").strip()
    if ref:
        if not _MA_THAM_CHIEU.match(ref):
            return None, "ERROR: reference_number chỉ gồm chữ, số, dấu chấm, gạch dưới, gạch nối"
        p["reference_number"] = ref
    for key in ("amount_in", "amount_out"):
        v = a.get(key)
        if v in (None, ""):
            continue
        so_tien = tien(v)
        if isinstance(v, bool) or so_tien <= 0:
            return None, f"ERROR: {key} phải là số tiền dương"
        p[key] = str(_so_ra(so_tien))
    return p, None


async def _get(sec, path, params=None):
    ok, d = await k.goi(TEN, "GET", f"{HOST}{path}", secrets=sec, params=params,
                        headers={"Authorization": f"Bearer {sec['api_token']}"})
    if not ok:
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: SePay trả về không đúng dạng: {str(d)[:300]}", sec)
    msgs = d.get("messages") if isinstance(d.get("messages"), dict) else {}
    if str(d.get("status", 200)) != "200" or msgs.get("success") is False or d.get("error"):
        loi = d.get("error") or d.get("messages") or d.get("status")
        return False, k.giau(f"ERROR: SePay {d.get('status', '')}: {loi}", sec)
    return True, d


def tong_hop(giao_dich):
    """Cộng tiền vào/ra theo từng tài khoản. Tính tại chỗ, không gọi mạng."""
    vao = ra = Decimal(0)
    theo_tk = {}
    for g in giao_dich or []:
        if not isinstance(g, dict):
            continue
        gv, gr = tien(g.get("amount_in")), tien(g.get("amount_out"))
        vao += gv
        ra += gr
        key = str(g.get("account_number") or "?")
        t = theo_tk.setdefault(key, {"account_number": key, "ngan_hang": g.get("bank_brand_name") or "",
                                     "tien_vao": Decimal(0), "tien_ra": Decimal(0), "so_giao_dich": 0})
        t["tien_vao"] += gv
        t["tien_ra"] += gr
        t["so_giao_dich"] += 1
    ds_tk = [{**t, "tien_vao": _so_ra(t["tien_vao"]), "tien_ra": _so_ra(t["tien_ra"]),
              "chenh_lech": _so_ra(t["tien_vao"] - t["tien_ra"])} for t in theo_tk.values()]
    return {"tong_tien_vao": _so_ra(vao), "tong_tien_ra": _so_ra(ra), "chenh_lech": _so_ra(vao - ra),
            "so_giao_dich": sum(t["so_giao_dich"] for t in ds_tk), "theo_tai_khoan": ds_tk}


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "api_token")
    if t:
        return "ERROR: kết nối SePay thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    sec["api_token"] = str(sec["api_token"]).strip()
    a = arguments or {}

    if tool == "sepay_tai_khoan_ngan_hang":
        ok, d = await _get(sec, "/bankaccounts/list")
        if ok:
            d = {"bankaccounts": d.get("bankaccounts", [])}
    elif tool == "sepay_giao_dich":
        p, loi = _loc(a, them=True)
        if loi:
            return loi
        p["limit"] = k.so(a.get("limit"), 100, 1, TOI_DA)
        ok, d = await _get(sec, "/transactions/list", p)
        if ok:
            ds_gd = d.get("transactions") or []
            d = {"so_giao_dich": len(ds_gd), "loc": p, "transactions": ds_gd}
    elif tool == "sepay_chi_tiet_giao_dich":
        ma = str(a.get("id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu id giao dịch (dãy số)"
        ok, d = await _get(sec, f"/transactions/details/{ma}")
        if ok:
            d = d.get("transaction", d)
    elif tool == "sepay_dem_giao_dich":
        p, loi = _loc(a)
        if loi:
            return loi
        ok, d = await _get(sec, "/transactions/count", p)
        if ok:
            d = {"so_giao_dich": d.get("count_transactions"), "loc": p}
    elif tool == "sepay_tong_hop":
        p, loi = _loc({kk: a.get(kk) for kk in ("account_number", "tu_ngay", "den_ngay")}, mac_dinh_ngay=0)
        if loi:
            return loi
        p["limit"] = TOI_DA
        ok, d = await _get(sec, "/transactions/list", p)
        if ok:
            ds_gd = d.get("transactions") or []
            kq = {"tu_ngay": p["transaction_date_min"][:10], "den_ngay": p["transaction_date_max"][:10],
                  **tong_hop(ds_gd)}
            if p.get("account_number"):
                kq["account_number"] = p["account_number"]
            if len(ds_gd) >= TOI_DA:
                kq["canh_bao"] = (f"Chạm giới hạn {TOI_DA} giao dịch mỗi lần, tổng có thể THIẾU. "
                                  "Chia nhỏ khoảng ngày rồi cộng lại.")
            d = kq
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối SePay"
    return k.json_ra(d) if ok else d
