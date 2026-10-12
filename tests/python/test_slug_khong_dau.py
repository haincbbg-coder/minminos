"""Slug agent/workflow mới KHÔNG DẤU và không ghi đè (26.10.145).

    python tests/run.py slug_khong_dau
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import pathlib
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-slug-")
import main  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


d = pathlib.Path(tempfile.mkdtemp(prefix="javis-slugd-"))
check("bỏ dấu tiếng Việt", main._slug_moi("Viết email chăm khách", d) == "viet-email-cham-khach", main._slug_moi("Viết email chăm khách", d))
check("đ thành d", main._slug_moi("Đặt hàng Pancake", d) == "dat-hang-pancake")
(d / "dat-hang-pancake.md").write_text("x", encoding="utf-8")
check("trùng thì thêm -2", main._slug_moi("Dat hang Pancake", d) == "dat-hang-pancake-2")
(d / "dat-hang-pancake-2.md").write_text("x", encoding="utf-8")
check("trùng tiếp thì -3", main._slug_moi("Đặt hàng Pancake", d) == "dat-hang-pancake-3")
check("tên toàn ký tự lạ vẫn ra slug", main._slug_moi("???", d) == "item")

if fails:
    print("\nFAIL:", fails)
    raise SystemExit(1)
print("\nOK")
