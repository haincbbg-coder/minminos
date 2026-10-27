"""Nút Tua lại dưới câu hỏi trong khung chat (26.10.274).

    python tests/run.py tua_lai_chat      (không cần mạng)

Bấm Tua lại: câu đó cùng mọi thứ bên dưới bị xoá, câu hỏi về ô gõ, hội thoại đi tiếp từ đó. Ghim ở đây
nửa server (nút nằm ở chat-acts.js + app.js, xem tests/js/test_chat_acts.js):
  1. Kho xoá từ tin người dùng đó tới cuối, không đụng phía trước, sửa msg_count.
  2. Route tìm câu hỏi theo chữ đếm từ cuối (nth cho câu trùng chữ), cả khi bản lưu kèm khối ngữ cảnh;
     "ok" không bao giờ khớp "ok làm đi" phía sau.
  3. Mạch native của engine CLI (Claude Code resume id, Codex thread) bị bỏ; tóm tắt nén phủ lượt đã
     xoá bị bỏ, tóm tắt chỉ phủ lượt còn lại được giữ.
  4. Từ chối khi đang trả lời; chữ lạ không xoá gì.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-tualai-")
os.environ["JAVIS_ALLOWED_HOSTS"] = "testserver"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import sessions  # noqa: E402
import tua_lai  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


def noi_dung(st, sid):
    return [(m["role"], m["content"]) for m in st.get_messages(sid)]


# ---- 0. Bóc khối ngữ cảnh đúng luật chuNguoiGo ----
check("bóc khối file đang mở (bản ghi MinMin)",
      tua_lai.chu_nguoi_go("[FILE ĐANG MỞ trong trình sửa của MinMin: a.md]\n\nviết lại") == "viết lại")
check("bóc hai khối lồng nhau",
      tua_lai.chu_nguoi_go("[SKILL: x]\n\n[File đính kèm (đường dẫn):\n- a.png]\n\nxem ảnh") == "xem ảnh")
check("khối không đóng thì giữ nguyên", tua_lai.chu_nguoi_go("[SKILL: x không đóng") == "[SKILL: x không đóng")
check("ngoặc vuông do người gõ không bị bóc", tua_lai.chu_nguoi_go("[ghi chú] hỏi") == "[ghi chú] hỏi")

# ---- 1. Kho ----
store = sessions.SessionStore(Path(tempfile.mkdtemp(prefix="sess-")) / "s.db")
sid = store.create_session(brain="brain", engine="cli", title="t", channel="web")
ids = [store.append_message(sid, r, c) for r, c in
       (("user", "một"), ("assistant", "đáp một"), ("user", "hai"), ("assistant", "đáp hai"),
        ("user", "ba"), ("assistant", "đáp ba"))]
check("tin trả lời không phải mốc tua", store.cat_tu_tin(sid, ids[1]) == 0 and len(store.get_messages(sid)) == 6)
check("tin của phiên khác không phải mốc tua",
      store.cat_tu_tin(store.create_session(brain="brain"), ids[2]) == 0 and len(store.get_messages(sid)) == 6)
n = store.cat_tu_tin(sid, ids[2])
check("tua về 'hai' xoá nó và mọi thứ sau", n == 4, n)
check("...giữ nguyên phần trước", noi_dung(store, sid) == [("user", "một"), ("assistant", "đáp một")],
      noi_dung(store, sid))
check("...msg_count theo đúng", int(store.get_session(sid)["msg_count"]) == 2, store.get_session(sid)["msg_count"])

# ---- 2-4. Route ----
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

cl = TestClient(main.app)
ms = main.get_store()


def phien(tin, **cot):
    s = ms.create_session(brain="brain", engine="cli", title="t", channel="web")
    for r, c in tin:
        ms.append_message(s, r, c)
    if cot.get("cli"):
        ms.set_cli_session_id(s, cot["cli"])
    if cot.get("codex"):
        ms.set_codex_thread_id(s, cot["codex"])
    if cot.get("compact"):
        ms.set_compact(s, "tóm tắt", cot["compact"])
    return s


HOI = [("user", "[FILE ĐANG MỞ trong trình sửa của Javis: notes/a.md]\n\nviết lại đoạn mở bài"),
       ("assistant", "bản một"), ("user", "ok"), ("assistant", "xong"),
       ("user", "viết lại đoạn mở bài"), ("assistant", "bản hai"), ("user", "ok"), ("assistant", "xong hai")]

s1 = phien(HOI, cli="mach-claude", codex="mach-codex", compact=6)
r = cl.post(f"/sessions/{s1}/rewind", data={"text": "ok", "nth": "0"})
check("tua về câu 'ok' CUỐI trả ok", r.status_code == 200 and r.json().get("ok"), r.text)
check("...chỉ xoá câu đó và câu trả lời của nó", r.json().get("deleted") == 2
      and [c for _, c in noi_dung(ms, s1)][-1] == "bản hai", noi_dung(ms, s1))
row = ms.get_session(s1)
check("...bỏ mạch Claude Code và Codex", not row.get("cli_session_id") and not row.get("codex_thread_id"),
      (row.get("cli_session_id"), row.get("codex_thread_id")))
check("...báo lại các mạch đã bỏ", set(r.json().get("threads") or []) >= {"cli", "codex"}, r.json())
check("...tóm tắt chỉ phủ lượt còn lại thì giữ", int(row.get("compact_count") or 0) == 6
      and (row.get("compact_summary") or "") == "tóm tắt", (row.get("compact_count"), row.get("compact_summary")))
check("...đồng hồ ngữ cảnh về 0", int(row.get("last_input_tokens") or 0) == 0)

s2 = phien(HOI, compact=6)
r = cl.post(f"/sessions/{s2}/rewind", data={"text": "viết lại đoạn mở bài", "nth": "1"})
check("nth=1 tìm bản SỚM hơn, nằm trong khối ngữ cảnh", r.status_code == 200
      and r.json().get("deleted") == 8 and noi_dung(ms, s2) == [], (r.text, noi_dung(ms, s2)))
row = ms.get_session(s2)
check("...tóm tắt phủ lượt đã xoá thì bỏ", int(row.get("compact_count") or 0) == 0
      and not (row.get("compact_summary") or ""), (row.get("compact_count"), row.get("compact_summary")))

s4 = phien([("user", "ok"), ("assistant", "a"), ("user", "ok làm đi"), ("assistant", "b")])
r = cl.post(f"/sessions/{s4}/rewind", data={"text": "ok"})
check("'ok' không khớp 'ok làm đi' phía sau", r.status_code == 200 and r.json().get("deleted") == 4
      and noi_dung(ms, s4) == [], (r.text, noi_dung(ms, s4)))

s3 = phien(HOI)
r = cl.post(f"/sessions/{s3}/rewind", data={"text": "câu chưa từng hỏi"})
check("chữ lạ: 404 và không xoá gì", r.status_code == 404 and r.json().get("ly_do") == "khong_thay"
      and len(ms.get_messages(s3)) == 8, r.text)
r = cl.post(f"/sessions/{s3}/rewind", data={"text": "bản hai"})
check("chữ của câu trả lời không bao giờ là mốc tua", r.status_code == 404 and len(ms.get_messages(s3)) == 8, r.text)
r = cl.post("/sessions/khong-co/rewind", data={"text": "ok"})
check("phiên lạ: 404", r.status_code == 404, r.text)

_goc = main._CHAT_RUNTIME.get_job
main._CHAT_RUNTIME.get_job = lambda s: object() if s == s3 else None
try:
    r = cl.post(f"/sessions/{s3}/rewind", data={"text": "ok"})
finally:
    main._CHAT_RUNTIME.get_job = _goc
check("từ chối khi đang trả lời", r.status_code == 409 and r.json().get("ly_do") == "dang_chay"
      and len(ms.get_messages(s3)) == 8, r.text)

# Lượt chờ chạy lại khi hết hạn mức sẽ trả lời đúng câu vừa xoá, nên phải huỷ.
_huy = []
_goc_cancel = main.limit_resume.REGISTRY.cancel
s5 = phien([("user", "hỏi"), ("assistant", "đáp")])
try:
    main.limit_resume.REGISTRY.cancel = lambda s: _huy.append(s)
    # register() đã giữ tham chiếu hàm cũ, nên kiểm thẳng hàm tua_lai với hàm huỷ giả.
    tua_lai.tua_lai(ms, s5, "hỏi", 0, main.limit_resume.REGISTRY.cancel)
finally:
    main.limit_resume.REGISTRY.cancel = _goc_cancel
check("huỷ lượt chờ chạy lại của phiên", _huy == [s5], _huy)

print()
if _fails:
    raise SystemExit(f"FAIL {len(_fails)}: " + "; ".join(_fails[:4]))
print("All green.")
