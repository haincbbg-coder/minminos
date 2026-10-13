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

# ---------- 26.10.156: gộp chân nguồn ----------
_g = ng.gom_nguon([("pos_describe", "tool=pos_order"), ("pos_order", "action=list, shop_id=1"),
                      ("pos_order", "action=list, shop_id=2"), ("pos_order", "shop_id=1, update_status=3"),
                      ("meta_ads_get", "path=1470...")])
check("gom_nguon: gọi nhiều lần thành ×N, một lần giữ tham số",
      _g == ["pos_describe(tool=pos_order)", "pos_order ×3", "meta_ads_get(path=1470...)"], _g)
_g2 = ng.gom_nguon([(f"t{i}", "") for i in range(9)], toi_da=6)
check("gom_nguon: quá 6 tool thì nói còn bao nhiêu", _g2[-1] == "+3 tool khác" and len(_g2) == 7, _g2)
_cn = ng.chan_nguon("Có 12 đơn.", "hôm nay bao nhiêu đơn",
                       [{"name": "pos_order", "input": {"shop_id": 1}}, {"name": "pos_order", "input": {"shop_id": 2}}],
                       ['{"total":5}', '{"total":7}'], luc="09:20")
check("chan_nguon dùng gom_nguon", _cn.startswith("Nguồn: pos_order ×2 · lúc 09:20"), _cn)


# ---------- 26.10.157: số theo đơn vị / làm tròn không còn báo oan ----------
_kq = ['{"revenue":4306251000,"created_revenue":7224638000,"orders":23345,"spend":42312000}']
_n = ng.neo_so("Tạo đơn 7,225 tỷ đồng, đã nhận 4,306 tỷ (13.999 đơn), ads 42,3 triệu, 23.345 đơn, bịa 5.284.688",
               "tháng trước", _kq)
check("neo_so: 4,306 tỷ và 7,225 tỷ là xấp xỉ của số trong kho", _n["xap_xi"] == [4306, 7225], _n)
check("neo_so: số bịa và số không có trong kho vẫn bị bắt", _n["khong_nguon"] == [13999, 5284688], _n)
check("neo_so: số khớp đúng vẫn là có nguồn", _n["co_nguon"] == [23345], _n)
check("so_co_don_vi: đọc đơn vị tỷ/triệu/k", ng.so_co_don_vi("4,306 tỷ, 42,3 triệu, 5k") == {4306: 4.306e9, 423: 4.23e7, 5: 5000.0})
check("làm tròn: 42.310 là bản làm tròn của 42.312.000 (4 chữ số có nghĩa)", ng._la_ban_lam_tron(42310, {42312000}))
check("làm tròn: 3 chữ số có nghĩa thì KHÔNG khớp bừa", not ng._la_ban_lam_tron(423000, {42312000}) and not ng._la_ban_lam_tron(4230, {42312000}))
check("làm tròn: không khớp số nhỏ hơn", not ng._la_ban_lam_tron(7225, {722}))
_cn = ng.chan_nguon("Đã nhận 4,306 tỷ đồng.", "doanh số", [{"name": "pos_order", "input": {}}], _kq, luc="10:44")
check("chan_nguon: không cảnh báo số theo đơn vị", "⚠" not in _cn, _cn)


if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
