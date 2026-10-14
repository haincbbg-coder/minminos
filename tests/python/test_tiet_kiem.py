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

# ---------- 26.10.155: đo ngữ cảnh cố định + cache ----------
_p = ("# MinMin\nluật " * 50 + "\n\n# === BỘ NHỚ DÀI HẠN (nạp sẵn) ===\n- nhớ 1\n- nhớ 2\n"
      "\n# === ROUTER SKILL (đa engine) ===\nskill a\n\n# === NGÔN NGỮ ===\nvi\n")
_kh = tk.chia_khoi(_p, ratio=4)
check("chia_khoi: đúng tên khối theo thứ tự", [x["ten"] for x in _kh] == ["CLAUDE.md", "bộ nhớ", "skill", "ngôn ngữ"], [x["ten"] for x in _kh])
check("chia_khoi: khối đầu là phần trước tiêu đề", _kh[0]["ky_tu"] == len("# MinMin\nluật " * 50 + "\n\n"))
check("chia_khoi: token = ký tự / ratio", _kh[0]["token_uoc"] == round(_kh[0]["ky_tu"] / 4))
check("chia_khoi: tổng ký tự khớp prompt", sum(x["ky_tu"] for x in _kh) == len(_p))
check("chia_khoi: không tiêu đề thì một khối", len(tk.chia_khoi("chỉ CLAUDE.md")) == 1 and tk.chia_khoi("") == [])
check("cache_cua: Anthropic", tk.cache_cua({"input_tokens": 5, "cache_read_input_tokens": 1200}) == 1200)
check("cache_cua: OpenAI/OpenRouter", tk.cache_cua({"prompt_tokens": 9, "prompt_tokens_details": {"cached_tokens": 800}}) == 800)
check("cache_cua: Responses API", tk.cache_cua({"input_tokens": 9, "input_tokens_details": {"cached_tokens": 7}}) == 7)
check("cache_cua: không có / rác → 0", tk.cache_cua({"input_tokens": 9}) == 0 and tk.cache_cua(None) == 0 and tk.cache_cua({"cache_read_input_tokens": "x"}) == 0)


# ---------- 26.10.160: tràn kết quả tool ra file ----------
import tempfile
from pathlib import Path as _P
_tmp = _P(tempfile.mkdtemp())
tk.KHO_TRAN = _tmp / "tool-cache"
_lon = "{" + ",".join(f'"d{i}":{i * 1000}' for i in range(3000)) + "}"
_f = tk.ghi_tran(_lon, "mcp__javis__pancake__pos_order")
check("ghi_tran: ghi trọn file trong kho", _f.is_file() and _f.read_text(encoding="utf-8") == _lon)
check("ghi_tran: cùng nội dung -> cùng băm trong tên", _f.name.endswith(tk.ghi_tran(_lon, "pos_order").name[-14:]))
_xt = tk.xem_truoc_tran(_lon, _f, max_chars=2000)
check("xem_truoc_tran: có đầu, có đuôi, có đường dẫn và chỉ dẫn offset", _xt.startswith(_lon[:1200]) and _xt.endswith(_lon[-800:]) and str(_f) in _xt and "offset" in _xt)
check("la_file_tran: trong kho thì đúng, ngoài kho thì sai", tk.la_file_tran(_f) and not tk.la_file_tran(__file__))
import engine as _eng
_cl = _eng._clip_tool_result(_lon, max_chars=2000, ten_tool="pos_order")
check("_clip_tool_result: kết quả dài không còn mất phần giữa, trỏ sang file", "ĐÃ LƯU TRỌN" in _cl and "BỊ CẮT" not in _cl)
check("_clip_tool_result: kết quả ngắn giữ nguyên", _eng._clip_tool_result("ngắn") == "ngắn")


if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
