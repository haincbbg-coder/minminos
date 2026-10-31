"""Tab Thống kê của Chatbot: A.I. giúp được gì, khách mới, tốc độ A.I. so với người, giờ đông khách, tách theo tài
khoản (26.10.314, theo Javis 0.399 và 0.401).

    python tests/run.py thong_ke_loi_ich
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="minmin-tkli-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ["JAVIS_SESSIONS_DB"] = str(Path(_STATE) / "sessions.db")

import conversations  # noqa: E402
import localefmt  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


tz = localefmt.tz()
hom_nay = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
GIO_10 = hom_nay.replace(hour=10).timestamp()
GIO_23 = hom_nay.replace(hour=23).timestamp() - 86400     # tối hôm qua, chủ đang nghỉ


def put(acc, chat, who, ts, text="x", chat_type="private"):
    conversations.ghi_su_kien({"channel": "zalo", "account_id": acc, "account_name": acc, "external_chat_id": chat,
                               "chat_type": chat_type, "sender_type": who, "sender_name": who, "text": text,
                               "message_type": "text", "created_at": ts})


# Nick A: A.I. lo hết. Nick B: chủ trả lời tay. Khách k3 là khách cũ (tin đầu từ tuần trước).
put("A", "k1", "customer", GIO_10)
put("A", "k1", "ai", GIO_10 + 20)
put("A", "k2", "customer", GIO_23)
put("A", "k2", "ai", GIO_23 + 40)
put("B", "k3", "customer", GIO_10 - 8 * 86400)
put("B", "k3", "customer", GIO_10 + 60)
put("B", "k3", "human", GIO_10 + 660)

tu, den = GIO_10 - 2 * 86400, GIO_10 + 86400   # không dựa vào giờ chạy test (trước 10h sáng vẫn đúng)
st = conversations.insights(tu, den)
check("đếm A.I., người, khách", (st["ai"], st["human"], st["customer"]) == (2, 1, 3), st)
check("A.I. trả lời lúc chủ nghỉ (21h-7h)", st["ai_rest"] == 1, st["ai_rest"])
check("khách được phục vụ và khách mới", st["chats"] == 3 and st["new_chats"] == 2, (st["chats"], st["new_chats"]))
check("tốc độ trả lời: trung vị A.I. và người riêng", st["wait_ai"] == 30.0 and st["wait_human"] == 600.0,
      (st["wait_ai"], st["wait_human"]))
check("giờ đông khách 24 cột", len(st["hours"]) == 24 and st["hours"][10] == 2
      and st["hours"][23] == 1, st["hours"])
check("tách theo tài khoản", st["by_account"].get("zalo:A") == {"customer": 2, "ai": 2, "human": 0}
      and st["by_account"].get("zalo:B") == {"customer": 1, "ai": 0, "human": 1}, st["by_account"])
a = conversations.insights(tu, den, "zalo:A")
check("chọn nick A: tin tay ở nick B không kéo tỉ lệ A.I. xuống", (a["ai"], a["human"], a["chats"]) == (2, 0, 2), a)
b = conversations.insights(tu, den, "zalo:B")
check("chọn nick B: không có khách mới", b["new_chats"] == 0 and b["human"] == 1, b)
check("kỳ trống: số 0, không trung vị", conversations.insights(0, 1)["wait_ai"] is None
      and conversations.insights(0, 1)["hours"] == [0] * 24)
acc = conversations.stats_accounts()
check("danh sách tài khoản cho ô chọn", {x["id"] for x in acc} == {"zalo:A", "zalo:B"} and all(x["channel"] == "zalo" for x in acc), acc)

print("\nXANH" if not fails else f"\nFAILED: {fails}")
raise SystemExit(1 if fails else 0)
