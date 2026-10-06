"""chat_import.py - đưa lịch sử chat của nền tảng AI khác vào MinMin (26.10.74).

Ba nguồn, mỗi nguồn một bộ đọc thuần (không chạm DB, test được bằng tệp mẫu):
  - claude-code : các phiên Claude Code lưu trên CHÍNH máy MinMin chạy (~/.claude/projects/*/*.jsonl)
  - chatgpt     : tệp conversations.json trong bản "Xuất dữ liệu" của ChatGPT
  - claude-ai   : tệp conversations.json trong bản xuất dữ liệu của claude.ai

Mỗi cuộc vào MinMin thành MỘT phiên kênh `import:<nguồn>`, gom vào project cùng tên nền tảng, và
chạy lại nhiều lần vẫn không đẻ trùng (id phiên suy từ id gốc). Chỉ giữ chữ người và AI nói; công
cụ, khối hệ thống, ghi chú ẩn bị bỏ. Gemini chưa có bộ đọc vì Google không cho xuất hội thoại web
thành tệp có cấu trúc.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

_ANT = re.compile(r"<(system-reminder|artifact-content-authored-by-others|command-[a-z-]+|local-command-[a-z-]+)[^>]*?(?:/>|>.*?</\1>)", re.S)
TOI_DA_TIN = 4000
TOI_DA_CUOC = 5000


def _sach(text: str) -> str:
    return _ANT.sub("", str(text or "")).strip()


def _epoch(v) -> float:
    if v is None or v == "":
        return time.time()
    if isinstance(v, (int, float)):
        return float(v) / (1000.0 if v > 1e11 else 1.0)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time()


def _cuoc(nguon, ext_id, title, msgs):
    msgs = [(r, t, ts) for r, t, ts in msgs if t][:TOI_DA_TIN]
    if not msgs:
        return None
    return {"nguon": nguon, "ext_id": str(ext_id), "title": (title or "").strip()[:200], "msgs": msgs}


def id_phien(nguon: str, ext_id: str) -> str:
    return f"imp-{nguon}-" + hashlib.sha1(f"{nguon}:{ext_id}".encode()).hexdigest()[:16]


# ───────────────────────── Claude Code (.jsonl) ─────────────────────────
def doc_claude_code(path) -> dict | None:
    sid, title, msgs = Path(path).stem, "", []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for ln in f:
                try:
                    j = json.loads(ln)
                except ValueError:
                    continue
                t = j.get("type")
                if t in ("custom-title", "ai-title"):
                    title = j.get("customTitle") or j.get("aiTitle") or title
                    continue
                if t == "summary" and not title:
                    title = j.get("summary") or ""
                    continue
                if t not in ("user", "assistant") or j.get("isSidechain") or j.get("isMeta") or j.get("isCompactSummary"):
                    continue
                c = (j.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                c = _sach(c)
                if c:
                    msgs.append(("user" if t == "user" else "assistant", c, _epoch(j.get("timestamp"))))
    except OSError:
        return None
    if not title and msgs:
        title = next((m[1] for m in msgs if m[0] == "user"), "")[:60].replace("\n", " ")
    d = _cuoc("claude-code", sid, title, msgs)
    if d:
        d["cli_session_id"] = sid
    return d


def quet_claude_code(goc=None, toi_da=TOI_DA_CUOC) -> list:
    goc = Path(goc) if goc else Path.home() / ".claude" / "projects"
    ra = []
    if not goc.is_dir():
        return ra
    for f in sorted(goc.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:toi_da]:
        d = doc_claude_code(f)
        if d:
            ra.append(d)
    return ra


# ───────────────────────── ChatGPT / claude.ai (conversations.json) ─────────────────────────
def _chatgpt(conv):
    mp = conv.get("mapping") or {}
    node, chain = conv.get("current_node"), []
    while node and node in mp and len(chain) < 20000:
        chain.append(mp[node])
        node = mp[node].get("parent")
    msgs = []
    for n in reversed(chain):
        m = n.get("message") or {}
        role = (m.get("author") or {}).get("role")
        if role not in ("user", "assistant") or (m.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
            continue
        parts = (m.get("content") or {}).get("parts") or []
        txt = _sach("\n".join(p for p in parts if isinstance(p, str)))
        if txt:
            msgs.append((role, txt, _epoch(m.get("create_time") or conv.get("create_time"))))
    return _cuoc("chatgpt", conv.get("conversation_id") or conv.get("id") or conv.get("title"), conv.get("title"), msgs)


def _claude_ai(conv):
    msgs = []
    for m in conv.get("chat_messages") or []:
        role = "user" if m.get("sender") == "human" else "assistant"
        txt = m.get("text")
        if not txt and isinstance(m.get("content"), list):
            txt = "\n".join(b.get("text", "") for b in m["content"] if isinstance(b, dict) and b.get("type") == "text")
        txt = _sach(txt)
        if txt:
            msgs.append((role, txt, _epoch(m.get("created_at"))))
    return _cuoc("claude-ai", conv.get("uuid") or conv.get("name"), conv.get("name"), msgs)


def doc_tep_xuat(data: bytes) -> list:
    """Nhận bytes của conversations.json (hoặc .zip chứa nó). Tự nhận ChatGPT hay claude.ai."""
    if data[:2] == b"PK":
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            ten = next((n for n in z.namelist() if n.endswith("conversations.json")), None)
            if not ten:
                raise ValueError("Trong .zip không có conversations.json")
            if z.getinfo(ten).file_size > 300 * 1024 * 1024:
                raise ValueError("conversations.json quá lớn")
            data = z.read(ten)
    arr = json.loads(data.decode("utf-8", errors="replace"))
    if isinstance(arr, dict):
        arr = arr.get("conversations") or []
    ra = []
    for c in arr[:TOI_DA_CUOC]:
        if not isinstance(c, dict):
            continue
        d = _chatgpt(c) if "mapping" in c else _claude_ai(c) if "chat_messages" in c else None
        if d:
            ra.append(d)
    return ra


# ───────────────────────── Ghi vào MinMin ─────────────────────────
TEN_PROJECT = {"claude-code": "Claude", "claude-ai": "Claude", "chatgpt": "ChatGPT"}
ENGINE = {"claude-code": "cli", "claude-ai": "cli", "chatgpt": "codex"}


def ghi(store, cuocs, brain="brain") -> dict:
    """Ghi các cuộc vào kho phiên. Trả {moi, trung, doi_ten}."""
    kq = {"moi": 0, "trung": 0, "doi_ten": 0}
    for d in cuocs:
        sid = id_phien(d["nguon"], d["ext_id"])
        cli = d.get("cli_session_id")
        goc = store._read("SELECT id, title FROM sessions WHERE id = ? OR (? != '' AND cli_session_id = ?)",
                          (sid, cli or "", cli or ""))
        if goc:
            kq["trung"] += 1
            # phiên MinMin đã có (cùng mạch Claude Code) mà chưa có tên: lấy tên như bên Claude
            if d.get("title") and not (goc[0]["title"] or "").strip():
                store.rename(goc[0]["id"], d["title"]); kq["doi_ten"] += 1
            continue
        first, last = d["msgs"][0][2], d["msgs"][-1][2]

        def _do(conn, d=d, sid=sid, cli=cli, first=first, last=last):
            conn.execute(
                "INSERT INTO sessions (id, title, brain, engine, model, channel, cli_session_id, created_at, updated_at, msg_count) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sid, d["title"] or None, brain, ENGINE.get(d["nguon"], "cli"), "", "import:" + d["nguon"], cli,
                 first, last, len(d["msgs"])))
            conn.executemany("INSERT INTO messages (session_id, role, content, ts) VALUES (?,?,?,?)",
                             [(sid, r, t, ts) for r, t, ts in d["msgs"]])
        store._write(_do)
        try:
            pid = store._project_nen_tang(brain, TEN_PROJECT.get(d["nguon"], d["nguon"]))
            if pid:
                store.set_project(sid, pid) if hasattr(store, "set_project") else None
        except Exception:
            pass
        kq["moi"] += 1
    return kq
