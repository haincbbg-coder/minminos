"""Zalo Bot: lấy id tin từ phản hồi và endpoint gửi ảnh thử (26.10.75).

    python tests/run.py zalo_bot_anh_id
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-zbot-")
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import zalo_bot  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


check("lấy được message_id", zalo_bot._lay_message_id({"ok": True, "result": {"message_id": "abc123"}}) == "abc123")
check("không có thì rỗng, không ném lỗi", zalo_bot._lay_message_id({"ok": True}) == "" and zalo_bot._lay_message_id(None) == "")
main._ZALO_BOT = None
r = TestClient(main.app, base_url="http://localhost").post("/zalo-bot/test-anh").json()
check("bot chưa chạy thì báo rõ", r.get("ok") is False and "chưa chạy" in r.get("error", ""), r)
if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
