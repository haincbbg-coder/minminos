"""Bản tổng hợp tuần: đếm đúng ký ức mới, bỏ ký ức cũ, báo skill bị khoá (26.10.151).

    python tests/run.py tong_hop_tuan
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import pathlib
import tempfile
import time

import tong_hop_tuan

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


r = pathlib.Path(tempfile.mkdtemp(prefix="javis-th-"))
(r / "memory/facts").mkdir(parents=True)
(r / "memory/conversations").mkdir()
(r / "Wiki").mkdir()
(r / "Javis").mkdir()
(r / "skills/.disabled/xau").mkdir(parents=True)
moi = r / "memory/facts/moi.md"
moi.write_text("---\ntype: user\n---\nBố gọi con là con\n", encoding="utf-8")
cu = r / "memory/facts/cu.md"
cu.write_text("---\ntype: user\n---\nĐiều cũ\n", encoding="utf-8")
t = time.time() - 30 * 86400
os.utime(cu, (t, t))
(r / "memory/conversations/2026-10-12.md").write_text("x", encoding="utf-8")
(r / "Wiki/a.md").write_text("x", encoding="utf-8")
(r / "Javis/skill-usage.json").write_text(json.dumps({"chao": {"use_count": 4, "last_used_at": time.time()}}), encoding="utf-8")

d = tong_hop_tuan.thu_thap(r)
check("chỉ đếm ký ức trong 7 ngày", [f["ten"] for f in d["facts"]] == ["moi"], d["facts"])
check("đếm ngày trò chuyện", d["hoi_thoai_ngay"] == 1)
check("wiki mới", d["wiki"] == ["a.md"])
check("skill đã dùng", d["skill_dung"] == [("chao", 4)])
check("skill bị khoá", d["skill_khoa"] == ["xau"])
(r / "skills/cu-ky").mkdir(parents=True)
sm = r / "skills/cu-ky/SKILL.md"
sm.write_text("x", encoding="utf-8")
os.utime(sm, (t, t))
(r / "skills/he-thong").mkdir()
sm2 = r / "skills/he-thong/SKILL.md"
sm2.write_text("x", encoding="utf-8")
os.utime(sm2, (t, t))
d2 = tong_hop_tuan.thu_thap(r, bo_qua={"he-thong"})
check("skill lâu chưa thấy dùng, bỏ skill hệ thống", d2["skill_chua_thay"] == ["cu-ky"], d2["skill_chua_thay"])
v = tong_hop_tuan.xay(r)
check("văn bản có ý ký ức và cảnh báo khoá", "Bố gọi con là con" in v and "xau" in v and "—" not in v, v)
check("brain trống không raise", "Không có ký ức nào mới" in tong_hop_tuan.xay(pathlib.Path(tempfile.mkdtemp())))

if fails:
    print("\nĐỎ:", fails)
    raise SystemExit(1)
print("\nxanh")
