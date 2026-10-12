"""Gói học từ Javis (26.10.143): git ép LC_ALL=C, tên đăng nhập không phân biệt hoa thường, Server-Timing.

    python tests/run.py hoc_javis_goi1
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-hocjavis-"))
sys.path.insert(0, str(SERVER))
_fails = []


def check(n, c):
    print(("ok   " if c else "FAIL ") + n)
    if not c:
        _fails.append(n)


import git_brain  # noqa: E402
e = git_brain._env_git()
check("git env LC_ALL=C", e.get("LC_ALL") == "C" and e.get("LANG") == "C")
r = git_brain._git(str(ROOT), "--version")
check("git chạy được với env ép", r.returncode == 0 and "git version" in r.stdout)

src = (SERVER / "main.py").read_text(encoding="utf-8")
check("đăng nhập so casefold", 'username.strip().casefold()' in src)
check("có middleware Server-Timing", '"Server-Timing"' in src)

if _fails:
    print("\nFAIL:", _fails)
    sys.exit(1)
print("\nOK")
