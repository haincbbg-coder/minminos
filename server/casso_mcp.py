"""Cầu nối Casso (transport "internal"). Mỗi kết nối = MỘT doanh nghiệp trên Casso.

Casso đọc biến động số dư các tài khoản ngân hàng đã liên kết vào doanh nghiệp. Một doanh nghiệp
có thể gắn nhiều tài khoản ngân hàng; doanh nghiệp Casso thứ hai thì thêm kết nối thứ hai.

API v2 (developer.casso.vn):
  base   https://oauth.casso.vn/v2
  header Authorization: Apikey <api_key>   (tạo ở casso.vn > Tích hợp > API Key)
  GET /userInfo                 thông tin user, doanh nghiệp, danh sách tài khoản ngân hàng
  GET /transactions             fromDate, toDate (YYYY-MM-DD), page, pageSize, sort ASC|DESC
  GET /transactions/{id}
Trả về {error: 0, message, data}. error khác 0 là lỗi. Giao dịch có `amount` dương = tiền vào,
âm = tiền ra.

GIỚI HẠN TẦN SUẤT: Casso chỉ cho 2 (gói SPONSOR), 5 (PIONEER) hoặc 20 (STANDARD) yêu cầu mỗi
phút. Vì vậy `casso_tong_hop` đọc TỐI ĐA 5 trang mỗi lần và báo rõ khi kết quả chưa đủ; không có
vòng lặp nào gọi Casso không giới hạn.

Bản này CHỈ ĐỌC.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime

import ket_noi_api as k

HOST = "https://oauth.casso.vn/v2"
TEN = "Casso"
TRANG_TOI_DA = 500          # pageSize tối đa MinMin gửi mỗi trang
SO_TRANG_TONG_HOP = 5       # casso_tong_hop đọc tối đa ngần này trang (tôn trọng giới hạn tần suất)

TOOLS = [
    k.tool("casso_thong_tin",
           "Thông tin doanh nghiệp trên Casso và các tài khoản ngân hàng đã liên kết (ngân hàng, số "
           "tài khoản, số dư, trạng thái kết nối)."),
    k.tool("casso_giao_dich",
           "Danh sách giao dịch ngân hàng theo khoảng ngày (mặc định 7 ngày gần nhất). amount dương là "
           "tiền vào, âm là tiền ra. Trang tiếp theo tăng page.",
           {**k.NGAY_PROPS,
            "page": {"type": "integer", "description": "trang, bắt đầu từ 1"},
            "pageSize": {"type": "integer", "description": "số giao dịch mỗi trang, mặc định 100, tối đa 500"},
            "sort": {"type": "string", "enum": ["DESC", "ASC"], "description": "mặc định DESC (mới nhất trước)"}}),
    k.tool("casso_chi_tiet_giao_dich", "Chi tiết 1 giao dịch theo id Casso.",
           {"id": {"type": "string", "description": "id giao dịch (dãy số)"}}, ["id"]),
    k.tool("casso_tong_hop",
           "Tổng tiền vào, tổng tiền ra, số giao dịch trong khoảng ngày (mặc định HÔM NAY). Đọc tối đa "
           f"{SO_TRANG_TONG_HOP} trang x {TRANG_TOI_DA} giao dịch vì Casso giới hạn số lần gọi mỗi phút.",
           {"tu_ngay": {"type": "string", "description": "từ ngày YYYY-MM-DD (giờ VN), mặc định hôm nay"},
            "den_ngay": {"type": "string", "description": "đến ngày YYYY-MM-DD, mặc định hôm nay"}}),
]


async def list_tools(spec):
    return TOOLS


def _ngay(ts):
    return datetime.fromtimestamp(ts, k.mui_gio()).strftime("%Y-%m-%d")


def _tien(v):
    try:
        d = Decimal(str(v if v not in (None, "") else "0").strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal(0)
    return d if d.is_finite() else Decimal(0)


def _so_ra(d):
    return int(d) if d == d.to_integral_value() else float(d)


async def _get(sec, path, params=None):
    ok, d = await k.goi(TEN, "GET", f"{HOST}{path}", secrets=sec, params=params,
                        headers={"Authorization": f"Apikey {sec['api_key']}"})
    if not ok:
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: Casso trả về không đúng dạng: {str(d)[:300]}", sec)
    if str(d.get("error", 0)) != "0":
        return False, k.giau(f"ERROR: Casso {d.get('error')}: {d.get('message', '')}", sec)
    return True, d.get("data")


def tong_hop(records):
    vao = ra = Decimal(0)
    n_vao = n_ra = 0
    for r in records or []:
        if not isinstance(r, dict):
            continue
        a = _tien(r.get("amount"))
        if a > 0:
            vao += a
            n_vao += 1
        elif a < 0:
            ra += -a
            n_ra += 1
    return {"tong_tien_vao": _so_ra(vao), "tong_tien_ra": _so_ra(ra), "chenh_lech": _so_ra(vao - ra),
            "so_giao_dich": len([r for r in records or [] if isinstance(r, dict)]),
            "so_giao_dich_vao": n_vao, "so_giao_dich_ra": n_ra}


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "api_key")
    if t:
        return "ERROR: kết nối Casso thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    sec["api_key"] = str(sec["api_key"]).strip()
    a = arguments or {}

    if tool == "casso_thong_tin":
        ok, d = await _get(sec, "/userInfo")
    elif tool == "casso_giao_dich":
        tu, den = k.khoang(a, mac_dinh_ngay=7)
        sort = str(a.get("sort") or "DESC").upper()
        p = {"fromDate": _ngay(tu), "toDate": _ngay(den),
             "page": k.so(a.get("page"), 1, 1, 100000),
             "pageSize": k.so(a.get("pageSize"), 100, 1, TRANG_TOI_DA),
             "sort": sort if sort in ("ASC", "DESC") else "DESC"}
        ok, d = await _get(sec, "/transactions", p)
    elif tool == "casso_chi_tiet_giao_dich":
        ma = str(a.get("id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu id giao dịch (dãy số)"
        ok, d = await _get(sec, f"/transactions/{ma}")
    elif tool == "casso_tong_hop":
        tu, den = k.khoang({"tu_ngay": a.get("tu_ngay"), "den_ngay": a.get("den_ngay")}, mac_dinh_ngay=0)
        p = {"fromDate": _ngay(tu), "toDate": _ngay(den), "pageSize": TRANG_TOI_DA, "sort": "ASC"}
        records, tong_so, da_doc = [], None, 0
        for trang in range(1, SO_TRANG_TONG_HOP + 1):
            ok, d = await _get(sec, "/transactions", {**p, "page": trang})
            if not ok:
                return d
            d = d if isinstance(d, dict) else {}
            ds_trang = d.get("records") or []
            records.extend(ds_trang)
            da_doc = trang
            if d.get("totalRecords") is not None:
                try:
                    tong_so = int(d["totalRecords"])
                except (TypeError, ValueError):
                    tong_so = None
            if len(ds_trang) < TRANG_TOI_DA or (tong_so is not None and len(records) >= tong_so):
                break
        kq = {"tu_ngay": p["fromDate"], "den_ngay": p["toDate"], **tong_hop(records), "so_trang_da_doc": da_doc}
        if tong_so is not None:
            kq["tong_so_giao_dich_casso_bao"] = tong_so
        if (tong_so is not None and len(records) < tong_so) or (
                tong_so is None and da_doc == SO_TRANG_TONG_HOP and len(records) >= SO_TRANG_TONG_HOP * TRANG_TOI_DA):
            kq["canh_bao"] = (f"Mới đọc {len(records)} giao dịch (giới hạn {SO_TRANG_TONG_HOP} trang mỗi lần vì Casso "
                              "giới hạn số lần gọi mỗi phút), tổng có thể THIẾU. Chia nhỏ khoảng ngày rồi cộng lại.")
        return k.json_ra(kq)
    else:
        return f"ERROR: tool '{tool}' không có trong cầu nối Casso"
    return k.json_ra(d) if ok else d
