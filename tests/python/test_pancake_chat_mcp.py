"""Cầu nối Thống kê Pancake (server/pancake_chat_mcp.py). Không mạng.

    python tests/run.py pancake_chat

Phủ: đọc danh sách page nhiều dòng, đúng URL + page_access_token + date_range giờ VN, tổng mọi page
bằng cộng từng page, tỷ lệ chốt, nhân viên cộng dồn qua nhiều page theo tên, bỏ POS/Botcake,
lọc page theo tên, nhận cả dạng engagement_statistics (màn web), bộ nhớ đệm 60 giây, lỗi một
page không làm hỏng page khác, lỗi không lộ token, không page nào -> ERROR.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
from datetime import datetime

from _gia_http import GiaHttp, KiemTra
import ket_noi_api as k
import pancake_chat_mcp as m

check = KiemTra()
T1 = "eyJhbGciOiJIUzI1NiJ9.token_page_mot_bi_mat"
T2 = "eyJhbGciOiJIUzI1NiJ9.token_page_hai_bi_mat"
PAGES = f"""
# trang chính
598364820025920 | {T1} | Hoa Trà Boutique
120769791116649, {T2}, Vân Trinh Shop
khong-phai-so | abc | Rác
598364820025920 | trung | trùng page bị bỏ
"""


def spec(pages=PAGES):
    return {"key": "conn-pk-1", "secrets": {"pages": pages}}


def chay(x):
    return asyncio.run(x)


hom_nay = datetime.now(k.mui_gio())
dr_hom_nay = f"{hom_nay:%d/%m/%Y} 00:00:00 - {hom_nay:%d/%m/%Y} 23:59:59"

# ---- đọc cấu hình ----
ds = m.doc_pages(PAGES)
check("đọc 2 page hợp lệ, bỏ chú thích/rác/trùng", [p["id"] for p in ds] == ["598364820025920", "120769791116649"], ds)
check("giữ tên có dấu cách", ds[1]["ten"] == "Vân Trinh Shop" and ds[0]["token"] == T1, ds)
ra = chay(m.call("pancake_tk_ds_page", {}, spec()))
check("ds page không lộ token", T1 not in ra and "Hoa Trà Boutique" in ra, ra)
ra = chay(m.call("pancake_tk_tong_quan", {}, spec("")))
check("chưa có page -> ERROR rõ", ra.startswith("ERROR") and "page_id" in ra, ra)
check("đủ 3 tool", [t["name"] for t in chay(m.list_tools({}))] ==
      ["pancake_tk_ds_page", "pancake_tk_tong_quan", "pancake_tk_nhan_vien"])


def khach(rows):
    return {"success": True, "data": rows}


def tuong_tac(cats, series, users=None):
    return {"success": True, "data": {"categories": cats,
                                      "series": [{"name": n, "data": d} for n, d in series.items()],
                                      "users_engagements": users or []}}


# ---- tổng quan ----
m._DEM.clear()
gia = GiaHttp().lap()
gia.tra("/pages/598364820025920/statistics/page_customers",
        khach([{"date": "24/10/2026", "new_customer_count": 3, "new_page_inbox_count": 4, "new_phone_number_count": 2, "phone_number_count": 2},
               {"date": "25/10/2026", "new_customer_count": 5, "new_page_inbox_count": 6, "new_phone_number_count": 3, "phone_number_count": 4}]))
gia.tra("/pages/598364820025920/statistics/customer_engagements",
        tuong_tac(["25/10/2026", "24/10/2026"], {"inbox": [10, 10], "comment": [1, 0], "total": [11, 10], "order_count": [3, 2], "old_order_count": [1, 0]}))
gia.tra("/pages/120769791116649/statistics/page_customers",
        khach([{"date": "25/10/2026", "new_customer_count": 1, "new_page_inbox_count": 1, "new_phone_number_count": 1, "phone_number_count": 1}]))
# page 2 trả dạng bảng như màn web
gia.tra("/pages/120769791116649/statistics/customer_engagements",
        {"success": True, "engagement_statistics": [{"time": "25/10/2026", "inbox": 5, "comment": 0, "total": 5, "order_count": 1, "old_order_count": 0}]})
ra = chay(m.call("pancake_tk_tong_quan", {"tu_ngay": "2026-10-24", "den_ngay": "2026-10-25", "theo_ngay": True}, spec()))
d = json.loads(ra)
t = d["tong_tat_ca_page"]
check("tổng khách nhắn = 20 + 5", t["khach_nhan_tin"] == 25, t)
check("tổng đơn chốt = 5 + 1", t["don_chot"] == 6, t)
check("tổng số điện thoại = 6 + 1", t["so_dien_thoai"] == 7, t)
check("tỷ lệ chốt = 6/25 = 24%", t["ty_le_chot"] == 24.0, t)
check("tỷ lệ chốt trên SĐT = 6/7", t["ty_le_chot_tren_sdt"] == 85.7, t)
p1 = [r for r in d["tung_page"] if r["page_id"] == "598364820025920"][0]
check("từng page: page 1 riêng", p1["don_chot"] == 5 and p1["khach_nhan_tin"] == 20 and p1["ty_le_chot"] == 25.0, p1)
check("xếp page nhiều đơn lên đầu", d["tung_page"][0]["page_id"] == "598364820025920", d["tung_page"])
ngay = {r["ngay"]: r for r in d["theo_ngay"]}
check("theo ngày: 25/10 = 10 + 5 khách nhắn", ngay["2026-10-25"]["khach_nhan_tin"] == 15, ngay)
check("theo ngày: 24/10 = 2 đơn", ngay["2026-10-24"]["don_chot"] == 2, ngay)
g = [x for x in gia.goi if "page_customers" in x["url"]][0]
check("URL Public API v1", g["url"] == "https://pages.fm/api/public_api/v1/pages/598364820025920/statistics/page_customers", g["url"])
check("gửi page_access_token đúng page", g["params"]["page_access_token"] == T1, g["params"])
check("date_range giờ VN đủ ngày", g["params"]["date_range"] == "24/10/2026 00:00:00 - 25/10/2026 23:59:59", g["params"])
check("group_by=day", g["params"]["group_by"] == "day", g["params"])
check("kết quả không lộ token", T1 not in ra and T2 not in ra, ra[:200])

# ---- bộ nhớ đệm ----
truoc = len(gia.goi)
chay(m.call("pancake_tk_tong_quan", {"tu_ngay": "2026-10-24", "den_ngay": "2026-10-25"}, spec()))
check("gọi lại trong 60 giây dùng bộ nhớ đệm", len(gia.goi) == truoc, len(gia.goi) - truoc)

# ---- mặc định hôm nay + lọc page ----
m._DEM.clear()
gia.goi.clear()
chay(m.call("pancake_tk_tong_quan", {"page": "vân trinh"}, spec()))
check("lọc theo tên không dấu chỉ gọi page 2", gia.goi and all("120769791116649" in x["url"] for x in gia.goi), [x["url"] for x in gia.goi])
check("mặc định hôm nay", gia.goi[0]["params"]["date_range"] == dr_hom_nay, gia.goi[0]["params"])
ra = chay(m.call("pancake_tk_tong_quan", {"page": "không có"}, spec()))
check("page không khớp -> ERROR", ra.startswith("ERROR"), ra)

# ---- nhân viên ----
m._DEM.clear()
gia = GiaHttp().lap()
gia.tra("/pages/598364820025920/statistics/users", {"success": True, "data": {"users": {
    "u-vy": {"user_name": "Khanh Vy  ", "unique_inbox_count": 10, "inbox_count": 30, "phone_number_count": 3, "average_response_time": 20000},
    "u-pos": {"user_name": "POS", "unique_inbox_count": 0, "phone_number_count": 0},
    "u-hoang": {"user_name": "Bích Hoàng", "unique_inbox_count": 4, "phone_number_count": 1, "average_response_time": 60}}}})
gia.tra("/pages/598364820025920/statistics/customer_engagements",
        tuong_tac([], {}, [{"user_id": "u-vy", "name": "Khanh Vy", "order_count": 4, "old_order_count": 1},
                           {"user_id": "u-hoang", "name": "Bích Hoàng", "order_count": 0}]))
gia.tra("/pages/120769791116649/statistics/users", {"success": True, "data": {"users": {
    "u-vy": {"user_name": "Khanh Vy", "unique_inbox_count": 10, "phone_number_count": 1, "average_response_time": 40000}}}})
gia.tra("/pages/120769791116649/statistics/customer_engagements",
        tuong_tac([], {}, [{"user_id": "u-vy", "name": "Khanh Vy", "order_count": 2}]))
d = json.loads(chay(m.call("pancake_tk_nhan_vien", {}, spec())))
nv = {x["ten"].strip(): x for x in d["nhan_vien"]}
check("bỏ POS khỏi xếp hạng", "POS" not in nv, list(nv))
vy = nv["Khanh Vy"]
check("cộng dồn 2 page theo tên", vy["khach_da_tra_loi"] == 20 and vy["don_chot"] == 6 and vy["so_dien_thoai"] == 4, vy)
check("tỷ lệ chốt nhân viên = 6/20", vy["ty_le_chot"] == 30.0, vy)
check("phản hồi TB: mili giây -> giây, bình quân theo khách", vy["phan_hoi_tb_giay"] == 30.0, vy)
check("chi tiết từng page của mỗi người", len(vy["tung_page"]) == 2, vy["tung_page"])
check("người nhiều đơn đứng đầu", d["nhan_vien"][0]["ten"].strip() == "Khanh Vy", d["nhan_vien"])
check("số nhỏ coi là giây", nv["Bích Hoàng"]["phan_hoi_tb_giay"] == 60.0, nv["Bích Hoàng"])
check("tổng nhân viên", d["tong"]["don_chot"] == 6 and d["tong"]["khach_da_tra_loi"] == 24, d["tong"])

# ---- lỗi ----
m._DEM.clear()
gia = GiaHttp().lap()
gia.tra("/pages/598364820025920/statistics/page_customers", {"success": False, "message": f"invalid token {T1}"}, code=200)
gia.tra("/pages/598364820025920/statistics/customer_engagements", {"message": f"bad {T1}"}, code=401)
gia.tra("/pages/120769791116649/statistics/page_customers", khach([{"date": "25/10/2026", "new_customer_count": 1}]))
gia.tra("/pages/120769791116649/statistics/customer_engagements", tuong_tac(["25/10/2026"], {"inbox": [2], "order_count": [1]}))
ra = chay(m.call("pancake_tk_tong_quan", {}, spec()))
d = json.loads(ra)
check("một page lỗi, page kia vẫn có số", d["tong_tat_ca_page"]["don_chot"] == 1 and len(d["tung_page"]) == 1, d)
check("báo page lỗi", d.get("loi") and "Hoa Trà" in d["loi"][0], d.get("loi"))
check("lỗi không lộ token", T1 not in ra, ra)
m._DEM.clear()
gia = GiaHttp().lap()
gia.tra("/statistics/", {"message": f"bad {T1} {T2}"}, code=401)
ra = chay(m.call("pancake_tk_tong_quan", {}, spec()))
check("mọi page lỗi -> ERROR", ra.startswith("ERROR"), ra)
check("ERROR không lộ token", T1 not in ra and T2 not in ra, ra)
ra = chay(m.call("pancake_tk_xyz", {}, spec()))
check("tool lạ -> ERROR", ra.startswith("ERROR"), ra)

check.ket_thuc()
