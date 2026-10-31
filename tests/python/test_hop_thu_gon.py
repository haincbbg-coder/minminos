"""Hộp thư gọn (0.64.97): nhóm chỉ giữ 100 tin, sao lưu trước lần cắt đầu, bot nhóm đọc 30 tin.

    python tests/python/test_hop_thu_gon.py      (KHÔNG mạng)

Canh ba lời hứa trong nhật ký cập nhật:
1. Nhóm chỉ giữ GIU_TIN_NHOM tin gần nhất; chat RIÊNG với khách giữ hết.
2. Kho cũ đã phình: lần mở đầu tiên SAO LƯU file rồi mới cắt, làm đúng một lần, bản sao lưu
   quá 14 ngày tự xoá.
3. Bot trong nhóm: câu không gọi bot vẫn vào kho làm ngữ cảnh (không bật chưa đọc), và lượt gọi
   bot có khối "Tin gần đây trong nhóm" với tối đa 30 tin, không lặp câu đang hỏi.
Kèm `after_id` cho nhịp làm mới của Hộp thư.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-hopthugon-")
os.environ["JAVIS_STATE_DIR"] = _STATE

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import conversations  # noqa: E402
import chatbot_runtime  # noqa: E402
import chatbot_store  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


if _STATE not in str(conversations.DB_PATH):
    print(f"FAIL kho không nằm trong thư mục tạm: {conversations.DB_PATH}. DỪNG.")
    sys.exit(1)

N = conversations.GIU_TIN_NHOM


def ghi(chat, loai, i, **them):
    ev = {"channel": "telegram", "account_id": "bot_x", "bot_id": "bot_x",
          "external_chat_id": chat, "chat_type": loai, "chat_title": "Nhóm sỉ" if loai == "group" else "",
          "sender_type": "customer", "sender_id": f"u{i % 5}", "sender_name": f"Khách {i % 5}",
          "text": f"tin {i}", "external_message_id": f"{chat}-{i}"}
    ev.update(them)
    return conversations.ghi_su_kien(ev)


# ============================================================
# 1. Cắt khi ghi
# ============================================================
for i in range(N + 30):
    r = ghi("-100", "group", i)
nhom_id = r["conversation_id"]
for i in range(N + 30):
    r2 = ghi("555", "private", i)
rieng_id = r2["conversation_id"]

db = conversations._conn()
dem = lambda cid: conversations._conn().execute("SELECT COUNT(*) FROM messages WHERE conversation_id=?", (cid,)).fetchone()[0]
check(f"nhóm chỉ giữ {N} tin gần nhất", dem(nhom_id) == N)
tin = conversations.tin_nhan(nhom_id, limit=500)
# 26.10.314: N = 1000 lớn hơn trần một trang (500), nên tin CŨ nhất còn giữ đọc thẳng từ kho.
cu_nhat = db.execute("SELECT text FROM messages WHERE conversation_id=? ORDER BY created_at, id LIMIT 1", (nhom_id,)).fetchone()[0]
check("tin còn lại là tin MỚI nhất (tin cuối là tin vừa ghi)",
      tin[-1]["text"] == f"tin {N + 29}" and cu_nhat == "tin 30")
check("nhóm giữ 1000 tin (26.10.314)", N == 1000)
check("chat riêng với khách giữ HẾT", dem(rieng_id) == N + 30)
check("số tin cộng dồn của hội thoại vẫn đếm mọi tin đã từng tới",
      conversations.chi_tiet(nhom_id)["message_count"] == N + 30)

# after_id: chỉ tin mới hơn, cũ trước mới sau
moc = tin[-5]["id"]
sau = conversations.tin_nhan(nhom_id, limit=200, after_id=moc)
check("after_id trả đúng 4 tin mới hơn, theo thứ tự cũ tới mới",
      [t["id"] for t in sau] == [t["id"] for t in tin[-4:]])
check("after_id tại tin cuối: rỗng", conversations.tin_nhan(nhom_id, after_id=tin[-1]["id"]) == [])
truoc = conversations.tin_nhan(nhom_id, limit=10, before_id=tin[20]["id"])
check("before_id vẫn như cũ: 10 tin ngay trước mốc", [t["id"] for t in truoc] == [t["id"] for t in tin[10:20]])

# ============================================================
# 2. Kho cũ đã phình: sao lưu rồi cắt, đúng một lần
# ============================================================
conversations.close()
path = Path(conversations.DB_PATH)
raw = sqlite3.connect(str(path))
cid_cu = raw.execute("SELECT id FROM conversations WHERE id=?", (nhom_id,)).fetchone()[0]
now = time.time()
raw.executemany("INSERT INTO messages(conversation_id, sender_type, text, created_at) VALUES(?,?,?,?)",
                [(cid_cu, "customer", f"cũ {i}", now) for i in range(250)])
raw.execute("DELETE FROM sync_state WHERE key=?", (conversations._KHOA_DA_CAT,))
raw.commit()
raw.close()
thu_muc = path.parent / "backups"
# Một bản sao lưu cũ 20 ngày: phải bị dọn
thu_muc.mkdir(parents=True, exist_ok=True)
cu = thu_muc / (conversations._TIEN_TO_SAO_LUU + "20000101-000000.sqlite3")
cu.write_bytes(b"x")
os.utime(cu, (now - 20 * 86400, now - 20 * 86400))
la = thu_muc / "khac.sqlite3"
la.write_bytes(b"x")
os.utime(la, (now - 20 * 86400, now - 20 * 86400))

db = conversations._conn()
check("mở kho lần đầu sau cập nhật: nhóm phình được cắt về 100", dem(nhom_id) == N)
bk = sorted(thu_muc.glob(conversations._TIEN_TO_SAO_LUU + "*.sqlite3"))
check("có đúng MỘT bản sao lưu mới, bản quá 14 ngày đã dọn", len(bk) == 1 and not cu.exists())
check("file lạ trong thư mục sao lưu không bị đụng", la.exists())
if bk:
    b = sqlite3.connect(str(bk[0]))
    so = b.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=?", (nhom_id,)).fetchone()[0]
    b.close()
    check("bản sao lưu chứa ĐỦ tin trước khi cắt", so == N + 250)
check("khoá đã-cắt được ghi", db.execute("SELECT 1 FROM sync_state WHERE key=?",
                                          (conversations._KHOA_DA_CAT,)).fetchone() is not None)
conversations.close()
conversations._conn()
check("mở lại lần nữa: không sao lưu thêm", len(list(thu_muc.glob(conversations._TIEN_TO_SAO_LUU + "*"))) == 1)

# ============================================================
# 3. Bot trong nhóm: ngữ cảnh 30 tin
# ============================================================
BRAIN = Path(tempfile.mkdtemp(prefix="javis-hopthugon-brain-"))
bid, err = chatbot_store.create_bot({"name": "Bot Nhóm", "agent_slug": "ban-hang", "brain": "b",
                                     "token": "1:x", "channel": "telegram"})
if not bid:
    print(f"FAIL không tạo được bot thử: {err}"); sys.exit(1)
chatbot_store.update_bot(bid, {"groups": ["-777"], "reply_when": "mention"})

_bat = {}


async def _answer(text, meta, progress, channel=None, bot=None):
    _bat["prompt"] = chatbot_runtime.build_bot_prompt(bot)
    return {"text": "Dạ em đây.", "files": []}

chatbot_runtime.wire(answer=_answer, brain_root=lambda b: str(BRAIN),
                     read_agent=lambda b, s: ({"name": "Bot Nhóm"}, "Bán hàng lịch sự."))
pre = chatbot_runtime._make_precheck_fn(bid)
fn = chatbot_runtime._make_answer_fn(bid)
base = {"chat_id": "-777", "chat_type": "group", "chat_title": "Nhóm khách"}
for i in range(35):
    ra = pre(f"tán gẫu {i}", {**base, "user_name": f"Người {i % 3}", "user_id": f"p{i % 3}", "message_id": 1000 + i})
    if ra != {}:
        break
check("câu không gọi bot: precheck vẫn im tuyệt đối", ra == {})
ds = conversations.danh_sach(bot_id=bid)
check("câu không gọi bot vẫn VÀO kho làm ngữ cảnh", ds and dem(ds[0]["id"]) == 35)
check("...nhưng không bật chấm chưa đọc", ds and ds[0]["unread_count"] == 0)

out = asyncio.run(fn("bot ơi còn áo size M không?",
                     {**base, "user_name": "Lan", "user_id": "lan", "message_id": 2000, "mentioned": True}))
p = _bat.get("prompt", "")
check("bot trả lời bình thường", (out or {}).get("text") == "Dạ em đây.")
check("prompt có khối Tin gần đây trong nhóm", "Tin gần đây trong nhóm" in p)
dong = [x for x in p.splitlines() if x.startswith("- Người")]
check("khối ngữ cảnh có đúng 30 tin, mới nhất cuối", len(dong) == 30 and dong[-1].endswith("tán gẫu 34"))
check("không lặp lại câu đang hỏi trong khối ngữ cảnh", "còn áo size M" not in p)
ds = conversations.danh_sach(bot_id=bid)
check("câu gọi bot thì có tính chưa đọc", ds[0]["unread_count"] == 1)

# Chat riêng: không có khối nhóm
asyncio.run(fn("chào shop", {"chat_id": "9", "chat_type": "private", "user_name": "B", "message_id": 3000}))
check("chat riêng: không có khối ngữ cảnh nhóm", "Tin gần đây trong nhóm" not in _bat.get("prompt", ""))

check("khối rỗng khi không có tin", chatbot_runtime.khoi_ngu_canh_nhom([]) == "")
dai = chatbot_runtime.khoi_ngu_canh_nhom([{"sender_type": "customer", "sender_name": "A", "text": "x" * 900}])
check("mỗi tin ngữ cảnh bị cắt gọn", len(dai) < 700 and dai.rstrip().endswith("..."))

for f in (ROOT / "server" / "conversations.py", ROOT / "server" / "chatbot_runtime.py",
          ROOT / "dashboard" / "conversations.js"):
    check(f"không có em dash trong {f.name}", "—" not in f.read_text(encoding="utf-8"))

if _fails:
    print(f"\nFAIL - test_hop_thu_gon: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_hop_thu_gon: tất cả pass")
