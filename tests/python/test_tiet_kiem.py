"""26.10.154 (Lớp 6): tiết kiệm token không mất dữ liệu (tiet_kiem.py). Thuần.

    python tests/run.py tiet_kiem
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import sys

import tiet_kiem as tk  # noqa: E402
import nguon  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:220] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- nén JSON ----------
goc = json.dumps({"data": [{"id": 1, "total": 1550000, "note": "", "tags": [], "meta": None, "qty": 0,
                             "ok": False, "items": [{"sku": "A", "price": 250000.0, "x": {}}]}] * 50,
                  "summary": {"revenue": 51740000, "orders": 150, "cancelled": None}}, indent=2, ensure_ascii=False)
nen = tk.nen_json(goc)
check("ngắn hơn nhiều (>= 40%)", len(nen) <= len(goc) * 0.6, (len(goc), len(nen)))
o = json.loads(nen)
check("vẫn là JSON hợp lệ, giữ số phần tử danh sách", len(o["data"]) == 50)
check("giữ 0 và False, bỏ null/''/[]/{}", o["data"][0]["qty"] == 0 and o["data"][0]["ok"] is False
      and "note" not in o["data"][0] and "tags" not in o["data"][0] and "cancelled" not in o["summary"])
check("mọi số đáng kể còn nguyên", {51740000, 1550000, 250000} <= nguon._chuoi_so_trong(nen) and nguon.so_dang_ke(nen) <= nguon._chuoi_so_trong(goc))
check("văn bản thường: gom khoảng trắng, giữ nội dung", tk.nen_json("a   b\n\n\n\nc") == "a b\n\nc")
check("không phải JSON hợp lệ thì không nổ", tk.nen_json("{không phải json") == "{không phải json")

# ---------- bộ đệm ----------
bd = tk.BoDem(ttl_giay=60)
k = tk.khoa_dem("c1", "pos_order", {"from": "2026-10-11", "shop": "halimi"})
k2 = tk.khoa_dem("c1", "pos_order", {"shop": "halimi", "from": "2026-10-11"})
check("khoá tất định, không phụ thuộc thứ tự tham số", k == k2)
check("chưa có -> None (miss)", bd.lay(k, now=1000.0) is None and bd.miss == 1)
bd.cat(k, "c1", '{"orders":150}', now=1000.0)
check("có -> trả lại (hit)", bd.lay(k, now=1030.0) == '{"orders":150}' and bd.hit == 1)
check("hết hạn -> None", bd.lay(k, now=1100.0) is None)
bd.cat(k, "c1", "x", now=2000.0); bd.cat(tk.khoa_dem("c2", "t", {}), "c2", "y", now=2000.0)
check("ghi lên c1 xoá đúng đệm của c1", bd.xoa_ket_noi("c1") == 1 and bd.lay(tk.khoa_dem("c2", "t", {}), now=2001.0) == "y")
check("ttl 0 = tắt", tk.BoDem(ttl_giay=0).lay("k") is None)
small = tk.BoDem(ttl_giay=60, toi_da=10)
for i in range(12):
    small.cat(f"k{i}", "c", "v", now=1000.0 + i)
check("không phình quá trần", len(small._kho) <= 10)

# ---------- tool nóng ----------
route = {"pancake-pos-halimi__pos_order": {"conn": {"id": "c1"}, "tool": "pos_order"},
         "meta__meta_ads_get": {"conn": {"id": "c2"}, "tool": "meta_ads_get"},
         "zalo__send": {"conn": {"id": "c3"}, "tool": "send"}}
audit = [{"conn_id": "c1", "tool": "pos_order", "ok": True}] * 5 + [{"conn_id": "c2", "tool": "meta_ads_get", "ok": True}] * 3 \
      + [{"conn_id": "c9", "tool": "da_go", "ok": True}] * 9 + [{"conn_id": "c3", "tool": "send", "ok": False}] * 4
check("xếp theo số lần gọi, bỏ kết nối đã gỡ và lượt lỗi",
      tk.tool_nong(audit, route, k=5) == ["pancake-pos-halimi__pos_order", "meta__meta_ads_get"], tk.tool_nong(audit, route, k=5))
check("k giới hạn", tk.tool_nong(audit, route, k=1) == ["pancake-pos-halimi__pos_order"])
check("không nhật ký -> rỗng", tk.tool_nong([], route) == [])
check("không dùng gạch dài", "—" not in open(os.path.join(ROOT, "server/tiet_kiem.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
