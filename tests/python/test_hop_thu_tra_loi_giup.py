"""Hộp thư: soạn nháp / trả lời giúp / nhật ký phán xử theo cuộc chat.

    python tests/python/test_hop_thu_tra_loi_giup.py      (KHÔNG mạng)
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-trlg-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import conversations  # noqa: E402
import chatbot_runtime  # noqa: E402
import chatbot_store  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + ((" [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


BRAIN = Path(tempfile.mkdtemp(prefix="javis-trlg-brain-"))
bid, err = chatbot_store.create_bot({"name": "Bot", "agent_slug": "ban-hang", "brain": "b",
                                     "token": "1:x", "channel": "telegram"})
chatbot_store.update_bot(bid, {"groups": ["-5"], "reply_when": "judge"})
goi = {"n": 0, "ngu_canh": None}


async def _answer(text, meta, progress, channel=None, bot=None):
    goi["n"] += 1
    goi["ngu_canh"] = bot.get("_ngu_canh_nhom")
    return {"text": "Dạ áo này 250k ạ", "files": []}


chatbot_runtime.wire(answer=_answer, brain_root=lambda b: BRAIN, read_agent=lambda *a, **k: "")

for i, (loai, ten, t) in enumerate([("customer", "Lan", "shop ơi"), ("customer", "Lan", "áo này giá bao nhiêu?")]):
    conversations.ghi_su_kien({"channel": "telegram", "account_id": bid, "bot_id": bid,
                               "external_chat_id": "-5", "chat_type": "group", "chat_title": "Nhóm",
                               "sender_type": loai, "sender_id": "u1", "sender_name": ten, "text": t,
                               "external_message_id": f"m{i}"})
conv = conversations.danh_sach(bot_id=bid)[0]
conv = conversations.chi_tiet(conv["id"])
tin = [m for m in conversations.tin_nhan(conv["id"]) if m["sender_type"] == "customer"][-1]

r = asyncio.run(chatbot_runtime.soan_cau_tra_loi(conv, tin))
check("soạn được nháp", r.get("ok") and "250k" in r.get("text", ""))
check("nháp KHÔNG ghi tin bot vào Hộp thư",
      not [m for m in conversations.tin_nhan(conv["id"]) if m["sender_type"] == "ai"])
check("nháp trong nhóm có ngữ cảnh, không lặp chính tin đang hỏi",
      goi["ngu_canh"] is not None and all(m.get("id") != tin["id"] for m in goi["ngu_canh"]))
check("cuộc chat không có bot thì từ chối",
      not asyncio.run(chatbot_runtime.soan_cau_tra_loi({"bot_id": ""}, tin)).get("ok"))
check("không có tin khách thì từ chối",
      asyncio.run(chatbot_runtime.soan_cau_tra_loi(conv, {})).get("ly_do") == "khong_co_tin_khach")


async def _chon_im(text, meta, progress, channel=None, bot=None):
    return {"text": "[IM_LANG]", "files": []}


chatbot_runtime.wire(answer=_chon_im, brain_root=lambda b: BRAIN, read_agent=lambda *a, **k: "")
check("bot chọn im thì nháp trả lý do rõ",
      asyncio.run(chatbot_runtime.soan_cau_tra_loi(conv, tin)).get("ly_do") == "bot_chon_im")

import routes.conversations as rc  # noqa: E402
import json as _j  # noqa: E402
for ly in ("khong_co_bot", "khong_co_tin_khach", "loi_engine", "bot_chon_im", "gui_loi"):
    d = _j.loads(rc._loi_soan({"ok": False, "ly_do": ly}).body)
    check(f"lỗi '{ly}' có câu tiếng Việt cho giao diện (không chỉ 'Lỗi 400')",
          d["error"] and "400" not in d["error"] and d["ly_do"] == ly, d)
check("kèm chi tiết kỹ thuật khi có",
      "boom" in _j.loads(rc._loi_soan({"ly_do": "loi_engine", "chi_tiet": "boom"}).body)["error"])

for f in (ROOT / "server" / "routes" / "conversations.py", ROOT / "dashboard" / "conversations.js"):
    t = f.read_text(encoding="utf-8")
    check(f"không có em dash trong {f.name}", "—" not in t)
js = (ROOT / "dashboard" / "conversations.js").read_text(encoding="utf-8")
check("giao diện có nút gợi ý và trả lời giúp", "aiReply(c, ta.value.trim()," in js and "sendDraft(c)" in js and "/ai-reply" in js)

if _fails:
    print(f"\nFAIL: {_fails}"); sys.exit(1)
print("\nOK - test_hop_thu_tra_loi_giup: tất cả pass")
