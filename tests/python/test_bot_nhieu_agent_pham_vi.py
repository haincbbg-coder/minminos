"""Nhiều Agent cho một bot và lọc người được nhắn riêng.   python tests/run.py bot_nhieu_agent_pham_vi"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
import _paths  # noqa
import chatbot_store, chatbot_runtime

ok = True
def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)

check("làm sạch Agent phụ: bỏ trùng, bỏ Agent chính, tối đa 5",
      chatbot_store._clean_agents_phu("a,b,a,main,c,d,e,f,g", "main") == ["a", "b", "c", "d", "e"])
check("làm sạch id được phép", chatbot_store._clean_rieng_cho_phep("123\n456 abc!") == ["123", "456"])
check("Zalo cá nhân mặc định chỉ người được cho phép",
      chatbot_store.pham_vi_rieng({"channel": "zalo_personal"}) == "chon")
check("bot Telegram giữ hành vi cũ", chatbot_store.pham_vi_rieng({"channel": "telegram"}) == "tat_ca")
check("chủ chọn rõ thì theo chủ", chatbot_store.pham_vi_rieng({"channel": "zalo_personal", "rieng_pham_vi": "tat_ca"}) == "tat_ca")

bot = {"channel": "zalo_personal", "reply_when": "mention"}
check("người lạ nhắn riêng thì im", chatbot_runtime._ly_do_im(bot, {"chat_type": "private", "chat_id": "u9"}, "hi") == "rieng_chua_cho")
bot["rieng_cho_phep"] = ["u9"]
check("người được cho phép thì bot nói", chatbot_runtime._ly_do_im(bot, {"chat_type": "private", "chat_id": "u9"}, "hi") == "")
tg = {"channel": "telegram", "reply_when": "mention"}
check("bot Telegram vẫn trả lời mọi người", chatbot_runtime._ly_do_im(tg, {"chat_type": "private", "chat_id": "x"}, "hi") == "")
sys.exit(0 if ok else 1)
