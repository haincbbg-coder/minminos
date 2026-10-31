"""Bộ chỉ huy thông báo của MinMin (26.10.312, ý từ Javis 0.403/0.408, viết lại cho MinMin).

Vì sao có file này
==================
Chuông của MinMin kêu cho MỌI thứ đi qua `_notify_owner`: việc nền chạy xong, loop báo vòng,
kết nối chập chờn, bản cập nhật kho... Bố nói thẳng là nhiều quá, và cái thật sự cần (một câu
hỏi đang chờ, một cái nhắc lịch, một khách đang đợi người) bị chìm giữa đống tin không cần làm gì.

Mỗi thông báo giờ có:
  - NHÓM (nói về chuyện gì): Nhắc lịch, Câu hỏi chờ bố, Chatbot và khách, Kết nối và đăng nhập,
    Sự cố, Kết quả việc, Chi phí, Cập nhật, Khác.
  - MỨC: bình thường (info) / đáng chú ý (important) / khẩn (urgent).
Mỗi nhóm có một CHẾ ĐỘ là mức thấp nhất vẫn được kêu: tất cả / đáng chú ý trở lên / chỉ tin khẩn
/ tắt. Mặc định MỌI nhóm "chỉ tin khẩn": tin khẩn thì kêu (chấm đỏ, thông báo đẩy, Telegram),
còn lại vẫn vào chuông nhưng ở dạng ĐÃ ĐỌC trong ngăn "Đã lọc", không đẩy, không Telegram.

Bố bấm "Không cần báo" trên một tin thì loại tin đó (cùng nhóm, cùng dáng tiêu đề) bị lọc từ
lần sau, kể cả khi nó là tin khẩn (bố đã nói). "Nên báo" trên một tin đã lọc thì loại đó luôn kêu.
Mọi thay đổi đều ghi lại và hoàn tác được. Một loại tin không khẩn kêu quá REPEAT_N lần trong
REPEAT_WINDOW_S thì phần còn lại của cửa sổ đó tự vào ngăn Đã lọc (tin khẩn thì không bao giờ).

`decide` là CHỖ DUY NHẤT biến (nhóm, mức, tiêu đề) thành kêu / lọc / bỏ. main.py gọi nó trong
`_bo_vao_hom_thu`; inbox.add gọi nó cho các nơi bỏ thư thẳng. Module này chỉ giữ luật và lịch sử,
trong `STATE_DIR/muc_thong_bao.json`, dưới một khoá.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
import uuid
from typing import Any, List, Optional

from config import STATE_DIR

STORE = STATE_DIR / "muc_thong_bao.json"
_LOCK = threading.RLock()

GROUPS = ("reminder", "question", "chatbot", "connection", "incident", "job", "cost", "update", "other")
LEVELS = ("info", "important", "urgent")
RANK = {"info": 0, "important": 1, "urgent": 2}
MODES = ("all", "important", "urgent", "off")
THRESHOLD = {"all": 0, "important": 1, "urgent": 2}
DEFAULT_MODE = "urgent"            # mặc định chỉ tin khẩn mới kêu

GROUP_NAMES = {
    "reminder": "Nhắc lịch", "question": "Câu hỏi chờ bố", "chatbot": "Chatbot và khách",
    "connection": "Kết nối và đăng nhập", "incident": "Sự cố", "job": "Kết quả việc",
    "cost": "Chi phí", "update": "Cập nhật", "other": "Khác",
}
LEVEL_NAMES = {"info": "Bình thường", "important": "Đáng chú ý", "urgent": "Khẩn"}
MODE_NAMES = {"all": "Tất cả", "important": "Đáng chú ý trở lên", "urgent": "Chỉ tin khẩn", "off": "Tắt"}

# `source` của thư -> nhóm (khi nơi gửi không nói nhóm).
SOURCE_GROUP = {
    "reminder": "reminder",
    "job": "job", "loop": "job", "webhook": "job", "gate": "job", "github": "job", "goal": "job",
    "doi-social": "job", "up-bai": "job", "xuong_video": "job",
    "watch": "connection", "engine": "connection", "connections": "connection", "zalo": "connection",
    "mat-nha": "incident", "incident": "incident",
    "chatbot": "chatbot", "zalo-group": "chatbot", "trich-tin": "chatbot", "khach": "chatbot",
    "zalo_personal": "chatbot",
    "cost": "cost", "bien-dong": "cost",
    "store": "update",
}
# Mức mặc định theo nhóm khi nơi gửi không nói mức và tin không lặng.
GROUP_LEVEL = {
    "reminder": "urgent",       # bố tự đặt giờ nhắc
    "question": "urgent",       # có việc đang đứng chờ bố
    "chatbot": "urgent",        # có khách đang đợi người
    "connection": "important", "incident": "important", "job": "important",
    "cost": "important", "update": "info", "other": "important",
}

REPEAT_N = 3                  # cùng một loại tin kêu ngần này lần ...
REPEAT_WINDOW_S = 6 * 3600    # ... trong ngần này giây thì phần còn lại vào Đã lọc (trừ tin khẩn)
CHANGES_KEEP = 100
LOUD_KEEP = 20


def _now() -> float:
    return time.time()


def _blank() -> dict:
    return {"version": 1, "groups": {}, "rules": {}, "loud": {}, "changes": [], "dropped": {}}


def _load() -> dict:
    try:
        d = json.loads(STORE.read_text(encoding="utf-8"))
    except OSError:
        return _blank()
    except ValueError as e:
        print(f"[muc thong bao] hỏng {STORE.name}: {e}", file=sys.stderr)
        return _blank()
    if not isinstance(d, dict):
        return _blank()
    for k, v in _blank().items():
        if not isinstance(d.get(k), type(v)):
            d[k] = v
    return d


def _save(d: dict) -> None:
    try:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(STORE)
    except OSError as e:
        print(f"[muc thong bao] không ghi được: {e}", file=sys.stderr)


# ── phân loại ─────────────────────────────────────────────────────────────────────────────
def group_of(source: str = "", kind: str = "", viec: Optional[dict] = None, group: str = "") -> str:
    """Nhóm của một tin. `group` nói thẳng thì thắng; một việc đang hỏi bố, xin quyền hay chờ
    duyệt là Câu hỏi chờ bố; còn lại theo `source`."""
    g = str(group or "").strip()
    if g in GROUPS:
        return g
    v = viec if isinstance(viec, dict) else {}
    if str(v.get("status") or "") in ("hoi", "review", "cho_quyen"):
        return "question"
    s = str(source or "").strip()
    if s in SOURCE_GROUP:
        return SOURCE_GROUP[s]
    if v.get("kind") in ("task", "job") or str(kind or "") in ("answer", "report"):
        return "job"
    return "other"


def level_of(level: str = "", quiet: bool = False, group: str = "") -> str:
    """Mức của một tin. `level` nói thẳng thì thắng; tin lặng là bình thường; còn lại theo nhóm."""
    lv = str(level or "").strip()
    if lv in LEVELS:
        return lv
    if quiet:
        return "info"
    return GROUP_LEVEL.get(group, "important")


_URL = re.compile(r"https?://\S+")
_NUM = re.compile(r"\d+")
_HEX = re.compile(r"\b[0-9a-f]{6,}\b")
_PUNCT = re.compile(r"[^\w#' ]+")


def signature(title: str) -> str:
    """Dáng của một tiêu đề: bỏ số, mã, giờ và link. "Việc 'X' lỗi lần 3" và "lần 4" là một loại,
    còn hai việc khác tên (phần trong ngoặc) thì không."""
    t = str(title or "").lower()
    t = _URL.sub(" ", t)
    t = _HEX.sub("#", t)
    t = _NUM.sub("#", t)
    t = _PUNCT.sub(" ", t)
    return " ".join(t.split())[:100]


def _key(group: str, sig: str) -> str:
    return f"{group}|{sig}"


def mode_of(group: str, d: Optional[dict] = None) -> dict:
    d = d if d is not None else _load()
    m = d["groups"].get(group) or {}
    mode = m.get("mode") if m.get("mode") in MODES else DEFAULT_MODE
    return {"mode": mode, "set_by": m.get("set_by") or "default", "since": float(m.get("since") or 0)}


# ── quyết định ─────────────────────────────────────────────────────────────────────────────
def decide(group: str, level: str, title: str, now: Optional[float] = None, record: bool = True) -> dict:
    """{"group", "level", "sig", "verdict": "loud"|"quiet"|"drop", "why"} cho một tin.

    `why`: "mode" (dưới chế độ của nhóm), "off" (bố tắt nhóm: bỏ hẳn), "muted" / "always" (luật
    riêng của loại tin), "repeat" (loại này đã kêu REPEAT_N lần trong cửa sổ), "" (kêu đúng mức).
    `record` ghi giờ của một lần kêu cho luật lặp."""
    now = _now() if now is None else float(now)
    g = group if group in GROUPS else "other"
    lv = level if level in LEVELS else "important"
    sig = signature(title)
    out = {"group": g, "level": lv, "sig": sig, "verdict": "loud", "why": ""}
    with _LOCK:
        d = _load()
        m = mode_of(g, d)
        rule = d["rules"].get(_key(g, sig)) or {}
        if m["mode"] == "off":
            out.update(verdict="drop", why="off")
            d["dropped"][g] = int(d["dropped"].get(g) or 0) + 1
            _save(d)
            return out
        if rule.get("rule") == "mute":
            out.update(verdict="quiet", why="muted")
            return out
        if rule.get("rule") == "always":
            out["why"] = "always"
        elif RANK[lv] < THRESHOLD.get(m["mode"], 2):
            out.update(verdict="quiet", why="mode")
            return out
        key = _key(g, sig)
        times = [t for t in (d["loud"].get(key) or []) if now - float(t) < REPEAT_WINDOW_S]
        if lv != "urgent" and rule.get("rule") != "always" and len(times) >= REPEAT_N:
            out.update(verdict="quiet", why="repeat")
            return out
        if record:
            d["loud"][key] = (times + [now])[-LOUD_KEEP:]
            if len(d["loud"]) > 1000:
                for k in sorted(d["loud"], key=lambda k: max(d["loud"][k] or [0]))[:500]:
                    d["loud"].pop(k, None)
            _save(d)
    return out


def safe_decide(title: str, *, source: str = "", kind: str = "", quiet: bool = False,
                level: str = "", group: str = "", viec: Optional[dict] = None) -> dict:
    """`decide` không bao giờ ném lỗi: kho luật hỏng thì tin vẫn kêu như trước bản này."""
    try:
        g = group_of(source=source, kind=kind, viec=viec, group=group)
        lv = level_of(level=level, quiet=quiet, group=g)
        return decide(g, lv, title)
    except Exception as e:  # noqa: BLE001
        print(f"[muc thong bao] quyết định lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return {"group": group or "other", "level": level or ("info" if quiet else "important"), "sig": "",
                "verdict": "quiet" if quiet else "loud", "why": ""}


# ── thay đổi (của bố) ──────────────────────────────────────────────────────────────────────
def _change(d: dict, kind: str, target: str, frm: Any, to: Any, reason: str, label: str = "") -> dict:
    c = {"id": uuid.uuid4().hex[:10], "ts": _now(), "kind": kind, "target": target, "from": frm, "to": to,
         "reason": str(reason or "")[:300], "label": str(label or "")[:120], "undone": False}
    d["changes"].append(c)
    d["changes"] = d["changes"][-CHANGES_KEEP:]
    return c


def set_mode(group: str, mode: str, reason: str = "") -> Optional[dict]:
    """Đặt chế độ của một nhóm. Trả thay đổi, None khi không đổi gì hoặc sai đầu vào."""
    if group not in GROUPS or mode not in MODES:
        return None
    with _LOCK:
        d = _load()
        cur = mode_of(group, d)
        if cur["mode"] == mode and cur["set_by"] != "default":
            return None
        d["groups"][group] = {"mode": mode, "set_by": "owner", "since": _now()}
        c = _change(d, "group", group, cur["mode"], mode, reason, GROUP_NAMES.get(group, group))
        _save(d)
        return c


def set_rule(group: str, sig: str, rule: Optional[str], label: str = "", reason: str = "") -> Optional[dict]:
    """Luật riêng cho một loại tin: "mute" (lọc), "always" (luôn kêu trừ khi nhóm tắt), None (gỡ)."""
    if group not in GROUPS or not sig or rule not in ("mute", "always", None):
        return None
    with _LOCK:
        d = _load()
        k = _key(group, sig)
        cur = (d["rules"].get(k) or {}).get("rule")
        if cur == rule:
            return None
        if rule is None:
            d["rules"].pop(k, None)
        else:
            d["rules"][k] = {"rule": rule, "label": str(label or sig)[:120], "at": _now()}
        c = _change(d, "kind", k, cur, rule, reason, label or sig)
        _save(d)
        return c


def undo(change_id: str) -> Optional[dict]:
    """Trả lại thứ một thay đổi đã thay. Trả thay đổi vừa hoàn tác, hoặc None."""
    with _LOCK:
        d = _load()
        c = next((x for x in d["changes"] if x.get("id") == change_id and not x.get("undone")), None)
        if c is None:
            return None
        if c["kind"] == "group":
            d["groups"][c["target"]] = {"mode": c["from"] if c["from"] in MODES else DEFAULT_MODE,
                                        "set_by": "owner", "since": _now()}
        elif c["from"] in ("mute", "always"):
            old = d["rules"].get(c["target"]) or {}
            d["rules"][c["target"]] = {"rule": c["from"], "label": old.get("label") or c.get("label"), "at": _now()}
        else:
            d["rules"].pop(c["target"], None)
        c["undone"] = True
        _save(d)
        return c


def react(item: dict, axis: str) -> Optional[dict]:
    """Bố phản hồi một tin trong chuông. "not_needed" lọc loại tin đó (cả tin khẩn, vì bố đã nói);
    "needed" trên một tin đã lọc thì loại đó luôn kêu. Trả thay đổi, hoặc None."""
    g = str(item.get("group") or "") or group_of(source=item.get("source") or "", kind=item.get("kind") or "")
    g = g if g in GROUPS else "other"
    sig = str(item.get("sig") or signature(item.get("title") or ""))
    label = str(item.get("title") or sig)[:120]
    if axis == "not_needed":
        return set_rule(g, sig, "mute", label=label, reason="Bố bấm Không cần báo.")
    if axis == "needed":
        return set_rule(g, sig, "always", label=label, reason="Bố bấm Nên báo trên một tin đã lọc.")
    return None


def describe(c: dict) -> str:
    """Một câu về một thay đổi, cho chuông và ngăn Bộ lọc."""
    if c.get("kind") == "group":
        g = GROUP_NAMES.get(str(c.get("target")), str(c.get("target")))
        return (f"Nhóm {g}: từ {MODE_NAMES.get(c.get('from'), c.get('from'))} "
                f"sang {MODE_NAMES.get(c.get('to'), c.get('to'))}.")
    lab = str(c.get("label") or "")
    to = c.get("to")
    if to == "mute":
        return f"Lần sau MinMin sẽ lọc các tin kiểu \"{lab}\"."
    if to == "always":
        return f"Lần sau MinMin sẽ luôn báo các tin kiểu \"{lab}\"."
    return f"Đã bỏ luật riêng cho các tin kiểu \"{lab}\"."


def status(changes: int = 20) -> dict:
    """Chế độ của mọi nhóm, các luật riêng, thay đổi gần đây (cho dashboard)."""
    with _LOCK:
        d = _load()
    groups = [{"group": g, "name": GROUP_NAMES[g], **mode_of(g, d), "dropped": int(d["dropped"].get(g) or 0),
               "default_level": GROUP_LEVEL[g]} for g in GROUPS]
    rules = [{"key": k, "group": k.split("|", 1)[0], "sig": k.split("|", 1)[1] if "|" in k else "", **v}
             for k, v in d["rules"].items()]
    rules.sort(key=lambda r: -float(r.get("at") or 0))
    recent = [dict(c, text=describe(c)) for c in list(reversed(d["changes"]))[:max(0, int(changes))]]
    return {"groups": groups, "rules": rules, "changes": recent, "default": DEFAULT_MODE,
            "modes": [{"id": m, "name": MODE_NAMES[m]} for m in MODES],
            "levels": [{"id": lv, "name": LEVEL_NAMES[lv]} for lv in LEVELS]}
