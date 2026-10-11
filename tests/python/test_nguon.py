"""26.10.137 (Trụ 3): dẫn nguồn + neo số (nguon.py). Thuần, không mạng.

    python tests/run.py nguon
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys

import nguon as ng  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- rút số ----------
check("nhóm nghìn VN", ng.cac_so("thuế 2.569.434 đ") == {2569434})
check("nhóm nghìn Anh", 1550000 in ng.cac_so("total 1,550,000"))
check("số trần lẫn nhóm", {3, 1550000} <= ng.cac_so("3 đơn, tổng 1.550.000đ"))
check("đáng kể: bỏ số nhỏ và năm", ng.so_dang_ke("năm 2026 có 3 đơn, 1.550.000đ") == {1550000})
check("đáng kể: trừ số trong câu hỏi", ng.so_dang_ke("giá 250000", tru={250000}) == set())
check("đọc số thập phân JSON", 1550000 in ng._chuoi_so_trong('{"tong": 1550000.0}'))

# ---------- neo số ----------
kq = ['{"doanh_nghiep":[{"mua_vao":{"so_hd":769,"thue":1075924534}}]}']
n = ng.neo_so("Đã tải 769 hoá đơn, thuế 1.075.924.534 đ, ước lợi nhuận 99.999.999 đ.", "hoá đơn mua vào?", kq)
check("số có trong tool -> có nguồn", 1075924534 in n["co_nguon"], n)
check("769 < 1000 nên không xét (số nhỏ)", 769 not in n["co_nguon"] and 769 not in n["khong_nguon"])
check("số không có trong tool -> không nguồn", n["khong_nguon"] == [99999999], n)

# ---------- chân nguồn ----------
tc = [{"name": "hoa_don_tong_hop", "input": {"loai": "mua", "tu": "2026-01-01"}}]
c = ng.chan_nguon("Thuế mua vào 1.075.924.534 đ.", "thuế mua vào?", tc, kq, luc="09:31")
check("chân nguồn có tên tool + tham số + giờ", "hoa_don_tong_hop(loai=mua" in c and "lúc 09:31" in c, c)
check("số có nguồn thì KHÔNG cảnh báo", "⚠" not in c, c)
c2 = ng.chan_nguon("Thuế mua vào 1.075.924.534 đ, dự kiến 99.999.999 đ.", "thuế?", tc, kq)
check("số không nguồn -> cảnh báo nhẹ (có tool)", "⚠ Số chưa thấy" in c2 and "99.999.999" in c2, c2)
c3 = ng.chan_nguon("Doanh thu tháng này 350.000.000 đ.", "doanh thu tháng này bao nhiêu?", [], [])
check("hỏi dữ liệu + không gọi tool + có số -> cảnh báo mạnh", "KHÔNG đọc dữ liệu" in c3, c3)
c4 = ng.chan_nguon("3 áo x 250.000 = 750.000 đ.", "3 áo giá 250.000 thì bao nhiêu?", [], [])
check("chat tính nhẩm (không hỏi dữ liệu) -> không cằn nhằn", c4 == "", c4)
c5 = ng.chan_nguon("Chào bố, hôm nay bố cần gì?", "chào", [], [])
check("chat thường không số -> rỗng", c5 == "")
c6 = ng.chan_nguon("x", "y", [{"name": "mcp__javis__javis_run_tool", "input": {"name": "pancake_orders", "args": {"ngay": "10/10"}}},
                              {"name": "javis_search_tools", "input": {"query": "đơn"}}], ["{}"])
check("xuyên lazy: tên thật + bỏ tool tìm", "pancake_orders(ngay=10/10)" in c6 and "javis_search_tools" not in c6, c6)
check("tắt -> rỗng", ng.chan_nguon("1.000.000", "?", tc, kq, bat=False) == "")

# ---------- 26.10.142: não CLI - tool hub tên mcp__javis__*, tool nội bộ bị lọc ----------
c7 = ng.chan_nguon("Hôm nay 150 đơn, 51.740.000đ.", "báo cáo hôm nay", [
    {"name": "mcp__javis__javis_search_tools", "input": {"query": "pancake"}},
    {"name": "mcp__javis__javis_read_file", "input": {"path": "00 - Dashboard/x.json"}},
    {"name": "mcp__javis__javis_run_tool", "input": {"name": "pancake-pos-halimi__pos_order", "args": {"from": "2026-10-11"}}},
    {"name": "mcp__javis__meta_ads_get", "input": {"path": "owned_ad_accounts"}}],
    ['{"orders": 150, "revenue": 51740000}'])
check("CLI: tool thật + connector hiện, tool nội bộ bị lọc",
      "pos_order(from=2026-10-11)" in c7 and "meta_ads_get" in c7 and "javis_read_file" not in c7 and "javis_search_tools" not in c7, c7)
check("CLI: số có nguồn -> không cảnh báo", "⚠" not in c7, c7)

check("không dùng gạch dài", "—" not in open(os.path.join(ROOT, "server/nguon.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
