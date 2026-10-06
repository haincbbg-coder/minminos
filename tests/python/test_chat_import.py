"""Nhập lịch sử chat Claude Code / ChatGPT / claude.ai (26.10.74).

    python tests/run.py chat_import
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-import-")
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import chat_import  # noqa: E402
from sessions import get_store  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# Claude Code
g = Path(tempfile.mkdtemp()) / "-proj"; g.mkdir()
L = [
    {"type": "ai-title", "aiTitle": "MinMin OS Upgrade plan"},
    {"type": "user", "timestamp": "2026-10-06T02:00:00Z", "message": {"role": "user", "content": "<system-reminder>ẩn</system-reminder>Xin chào"}},
    {"type": "assistant", "timestamp": "2026-10-06T02:00:05Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "Chào bố"}, {"type": "tool_use", "name": "Bash"}]}},
    {"type": "user", "isSidechain": True, "message": {"role": "user", "content": "phụ"}},
    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "x"}]}},
]
(g / "abc-123.jsonl").write_text("\n".join(json.dumps(x) for x in L), encoding="utf-8")
cs = chat_import.quet_claude_code(g.parent)
check("đọc được 1 phiên Claude Code", len(cs) == 1, cs)
d = cs[0]
check("tên lấy theo tên Claude", d["title"] == "MinMin OS Upgrade plan", d["title"])
check("chỉ giữ chữ người và AI, bỏ khối ẩn/công cụ/nhánh phụ",
      [(m[0], m[1]) for m in d["msgs"]] == [("user", "Xin chào"), ("assistant", "Chào bố")], d["msgs"])

# ChatGPT + claude.ai
gpt = [{"title": "Hỏi ChatGPT", "conversation_id": "c1", "current_node": "b", "create_time": 1760000000, "mapping": {
    "a": {"parent": None, "message": {"author": {"role": "user"}, "content": {"parts": ["Câu hỏi"]}, "create_time": 1760000001}},
    "b": {"parent": "a", "message": {"author": {"role": "assistant"}, "content": {"parts": ["Trả lời"]}, "create_time": 1760000002}}}}]
cai = [{"uuid": "u1", "name": "Chat claude.ai", "chat_messages": [
    {"sender": "human", "text": "Hi", "created_at": "2026-10-01T00:00:00Z"},
    {"sender": "assistant", "text": "Hello", "created_at": "2026-10-01T00:00:03Z"}]}]
a = chat_import.doc_tep_xuat(json.dumps(gpt).encode())
b = chat_import.doc_tep_xuat(json.dumps(cai).encode())
check("ChatGPT: đúng thứ tự và vai", [m[0] for m in a[0]["msgs"]] == ["user", "assistant"] and a[0]["nguon"] == "chatgpt")
check("claude.ai: đọc được", b[0]["nguon"] == "claude-ai" and len(b[0]["msgs"]) == 2)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("export/conversations.json", json.dumps(gpt))
check("nhận cả .zip", len(chat_import.doc_tep_xuat(buf.getvalue())) == 1)

# Ghi + không trùng + project
st = get_store()
k1 = chat_import.ghi(st, cs + a + b, "brain")
k2 = chat_import.ghi(st, cs + a + b, "brain")
check("lần 1 nhập 3 cuộc", k1["moi"] == 3, k1)
check("chạy lại không đẻ trùng", k2["moi"] == 0 and k2["trung"] == 3, k2)
ss = st.get_session(chat_import.id_phien("chatgpt", "c1"))
check("phiên mang kênh import và tên", ss and ss["channel"] == "import:chatgpt" and ss["title"] == "Hỏi ChatGPT", ss)
check("có tin nhắn và đếm đúng", ss and ss["msg_count"] == 2 and len(st.get_messages(ss["id"])) == 2)
check("tự gom vào project ChatGPT", any(p["name"] == "ChatGPT" for p in st.list_projects("brain")))

# phiên MinMin sẵn có cùng mạch Claude Code: không nhân đôi, và chưa có tên thì lấy tên
st.create_session(brain="brain", engine="cli", session_id="minmin-sess", cli_session_id="zzz-9", channel="web")
d2 = dict(chat_import._cuoc("claude-code", "zzz-9", "Tên từ Claude", [("user", "a", 1.0)]), cli_session_id="zzz-9")
k3 = chat_import.ghi(st, [d2], "brain")
check("trùng mạch cli: không nhân đôi, đặt tên", k3["moi"] == 0 and k3["doi_ten"] == 1
      and st.get_session("minmin-sess")["title"] == "Tên từ Claude", (k3, st.get_session("minmin-sess")))

c = TestClient(main.app, base_url="http://localhost")
r = c.post("/sessions/import-file", files={"file": ("conversations.json", json.dumps(cai).encode())}, data={"brain": "brain"}).json()
check("endpoint import-file chạy", r.get("ok") and r.get("trung") == 1, r)
check("tệp rác bị từ chối", c.post("/sessions/import-file", files={"file": ("x.json", b"khong phai json")}).status_code == 400)
if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
