"""Trang "Điều MinMin đang nhớ" (26.10.149): liệt kê, sửa, xoá ký ức. Không mạng.

    python tests/run.py memory_facts_ui
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="javis-memfacts-")
os.environ.setdefault("JAVIS_STATE_DIR", _TMP)
import main  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


root = Path(_TMP) / "brainx"
facts = root / "memory" / "facts"
facts.mkdir(parents=True)
(facts / "gia-si.md").write_text("---\ntype: business\nupdated: 2026-10-01\n---\nGiá sỉ áo 120k\n", encoding="utf-8")
(facts / "xung-ho.md").write_text("---\ntype: preference\nupdated: 2026-10-02\n---\nGọi bố\n", encoding="utf-8")
(root / "memory" / "MEMORY.md").write_text("# Index\n- [gia si](facts/gia-si.md) giá sỉ\n- [xung ho](facts/xung-ho.md) xưng hô\n", encoding="utf-8")
B = str(root)


def run(c):
    return asyncio.run(c)


d = run(main.memory_facts(B))
check("liệt kê 2 ký ức", d["total"] == 2 and {f["slug"] for f in d["facts"]} == {"gia-si", "xung-ho"}, d)
check("có loại và nội dung", any(f["type"] == "business" and "120k" in f["text"] for f in d["facts"]))

r = run(main.memory_fact_save("gia-si", "Giá sỉ áo 135k", B))
check("sửa ký ức ok", r.get("ok"), r)
t = (facts / "gia-si.md").read_text(encoding="utf-8")
check("giữ frontmatter, đổi thân, cập nhật ngày", "type: business" in t and "135k" in t and "120k" not in t, t)

r = run(main.memory_fact_save("../../etc/passwd", "x", B))
check("chặn tên đường dẫn lạ", getattr(r, "status_code", 200) == 404)
r = run(main.memory_fact_save("khong-co", "x", B))
check("ký ức không tồn tại thì 404", getattr(r, "status_code", 200) == 404)
r = run(main.memory_fact_save("gia-si", "x" * 20001, B))
check("nội dung quá dài bị từ chối", getattr(r, "status_code", 200) == 400)

r = run(main.memory_fact_delete("gia-si", B))
check("xoá ok, file mất", r.get("ok") and not (facts / "gia-si.md").exists(), r)
idx = (root / "memory" / "MEMORY.md").read_text(encoding="utf-8")
check("dòng chỉ mục được bỏ, dòng khác giữ", "gia-si" not in idx and "xung-ho" in idx, idx)
r = run(main.memory_fact_delete("../x", B))
check("xoá tên lạ bị chặn", getattr(r, "status_code", 200) == 404)

if fails:
    print("\nFAIL:", fails)
    raise SystemExit(1)
print("\nOK")
