"""26.10.141 (Trụ 5): dòng chứng cứ cho việc nền (chung_cu.py). Thuần.

    python tests/run.py chung_cu
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

import chung_cu as cc  # noqa: E402
import hanh_dong as hd  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:220] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


check("loop không việc mới -> rỗng", cc.dung([], [], "Không có việc mới.", []) == "")

g = cc.Gom(ai="viec:abc", luc_bat_dau="2026-10-11T12:00:00")
for ev in [{"type": "tool_call", "name": "javis_search_tools", "input": {"query": "đơn"}},
           {"type": "tool_call", "name": "mcp__javis__javis_run_tool", "input": {"name": "pancake_orders", "args": {}}},
           {"type": "tool_result", "name": "pancake_orders", "content": '{"tong": 12500000, "so_don": 37}'},
           {"type": "tool_call", "name": "hoa_don_tong_hop", "input": {"loai": "mua"}},
           {"type": "tool_result", "name": "hoa_don_tong_hop", "content": '{"thue": 2569434}'},
           {"type": "text", "content": "..."}]:
    g.nap(ev)
check("gom tool thật, bỏ tool tìm", g.tool_calls == ["pancake_orders", "hoa_don_tong_hop"], g.tool_calls)

hd.dat_duong(os.path.join(tempfile.mkdtemp(), "so.jsonl"))
hd.ghi(hd.dong_so(ai="viec:abc", tool="zalo_send_message", connector="zalo", label="Zalo", loai="nhan_tin",
                  cls="danger", mode="full", ok=True, ms=90, args={"to": "1"}, luc="2026-10-11T12:05:00"))
hd.ghi(hd.dong_so(ai="viec:khac", tool="create_order", connector="pancake", label="POS", loai="don_hang",
                  cls="write", mode="full", ok=True, ms=90, args={}, luc="2026-10-11T12:06:00"))
hd.ghi(hd.dong_so(ai="viec:abc", tool="update_budget", connector="meta_ads", label="BM", loai="tien",
                  cls="danger", mode="full", ok=False, ms=0, args={}, err="bị CHẶN theo chính sách", luc="2026-10-11T12:07:00"))
hd.ghi(hd.dong_so(ai="viec:abc", tool="old_action", connector="x", label="", loai="khac",
                  cls="write", mode="full", ok=True, ms=1, args={}, luc="2026-10-11T11:00:00"))
ng = g.hanh_dong_ngoai()
check("lọc đúng ai + từ lúc bắt đầu (bỏ việc khác, bỏ dòng cũ)", [r["tool"] for r in ng] == ["zalo_send_message", "update_budget"], [r["tool"] for r in ng])

d = g.dung("Hôm nay 37 đơn, doanh thu 12.500.000đ, thuế 2.569.434đ, dự kiến mai 20.000.000đ.")
check("có đọc tool", "đọc 2 lượt tool (pancake_orders, hoa_don_tong_hop)" in d, d)
check("có hành động ngoài + trạng thái", "2 hành động ngoài: zalo_send_message ✓, update_budget chặn" in d, d)
check("số liệu: 2 có nguồn, 1 chưa rõ", "số liệu: 2 có nguồn, 1 chưa rõ (20.000.000)" in d, d)
check("cảnh báo nhẹ khi có số chưa rõ", "⚠ Có số không thấy" in d, d)

d2 = cc.dung([], [], "Doanh thu tuần này 350.000.000đ.", [])
check("không đọc tool mà có số -> cảnh báo mạnh", "không đọc dữ liệu nào" in d2 and "Đừng dùng con số này" in d2, d2)
d3 = cc.dung(["pancake_orders"], ['{"tong": 5000000}'], "Tổng 5.000.000đ, không làm gì thêm.", [])
check("đủ nguồn, không ngoài -> không cảnh báo", "⚠" not in d3 and "không làm gì ra ngoài" in d3, d3)
check("không dùng gạch dài", "—" not in open(os.path.join(ROOT, "server/chung_cu.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
