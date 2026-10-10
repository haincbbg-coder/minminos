"""Gỡ ký tự vô hình khỏi tin người ngoài gửi tới (lệnh giấu)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
from text_clean import strip_hidden  # noqa: E402

ok = True


def check(ten, dieu_kien):
    global ok
    print(("  ok   " if dieu_kien else "  FAIL ") + ten)
    ok = ok and bool(dieu_kien)


check("gỡ ký tự rộng bằng không và đảo chiều", strip_hidden("ab​c‮d⁠e﻿") == "abcde")
check("gỡ khối tag ẩn", strip_hidden("x\U000E0041\U000E0042y") == "xy")
check("giữ xuống dòng và tab, gỡ ký tự điều khiển", strip_hidden("a\nb\tc\x00\x07") == "a\nb\tc")
fam = "👨‍👩‍👧"
check("giữ emoji ghép", strip_hidden(fam) == fam)
check("gỡ ZWJ chen giữa chữ thường", strip_hidden("a‍b") == "ab")
check("giữ tiếng Việt và emoji thường", strip_hidden("Xin chào ❤️ anh Hải") == "Xin chào ❤️ anh Hải")
check("không phải chuỗi thì trả nguyên", strip_hidden(None) is None and strip_hidden("") == "")

if not ok:
    sys.exit(1)
print("\nđạt")
