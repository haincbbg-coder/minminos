"""Lượt học không xoá trang wiki vừa viết (26.10.171, học Javis 0.217.0).

Lỗi gốc: danh sách thư mục được ghi chỉ có "Wiki" viết hoa; brain mới dùng `wiki/` thường nên mọi
trang wiki bị coi là ngoài phạm vi, và `git clean -fd` xoá cả trang chat vừa tạo (chưa commit).

    python tests/run.py hoc_khong_xoa_wiki
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import subprocess
import tempfile
from pathlib import Path

import git_brain
from learn import LearnFeature

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)


root = Path(tempfile.mkdtemp(prefix="javis-wiki-"))
git(root, "init", "-q")
git(root, "config", "user.email", "t@t")
git(root, "config", "user.name", "t")
(root / "wiki").mkdir()
(root / "wiki" / "Cu.md").write_text("cu\n", encoding="utf-8")
git(root, "add", "-A")
git(root, "commit", "-qm", "đầu")

# 1. phạm vi: wiki thường, "07 - Wiki", memory đều được phép
for ten in ("wiki", "07 - Wiki"):
    d = root / ten
    d.mkdir(exist_ok=True)
    pham_vi = LearnFeature._scope_cho_phep(str(root), root / "memory", d)
    bad = git_brain.paths_within([f"{ten}/Trang.md", "memory/facts/a.md"], pham_vi)
    check(f"thư mục '{ten}' nằm trong phạm vi ghi", bad == [], bad)
check("bản cũ (chỉ 'Wiki' hoa) từng chặn wiki/ thường",
      git_brain.paths_within(["wiki/Trang.md"], ["Wiki", "memory"]) == ["wiki/Trang.md"])
check("ngoài phạm vi vẫn bị chặn", git_brain.paths_within(["bi-mat/x.md"], LearnFeature._scope_cho_phep(str(root), root / "wiki")) == ["bi-mat/x.md"])
check("thư mục ngoài brain không lọt vào phạm vi",
      "etc" not in " ".join(LearnFeature._scope_cho_phep(str(root), "/etc")))

# 2. hard_reset_paths: file đã commit thì khôi phục, file chưa commit thì GIỮ
(root / "wiki" / "Cu.md").write_text("bị sửa ngoài phạm vi\n", encoding="utf-8")
(root / "wiki" / "Moi.md").write_text("trang chat vừa viết, chưa commit\n", encoding="utf-8")
xong = git_brain.hard_reset_paths(str(root), ["wiki/Cu.md", "wiki/Moi.md"])
check("file đã commit được khôi phục", (root / "wiki" / "Cu.md").read_text(encoding="utf-8") == "cu\n" and xong == ["wiki/Cu.md"], xong)
check("file chưa commit KHÔNG bị xoá", (root / "wiki" / "Moi.md").exists())
check("nội dung file chưa commit còn nguyên", "chat vừa viết" in (root / "wiki" / "Moi.md").read_text(encoding="utf-8"))
check("path rỗng không lỗi", git_brain.hard_reset_paths(str(root), []) == [])

print("PASS" if not fails else f"FAILED: {fails}")
raise SystemExit(1 if fails else 0)
