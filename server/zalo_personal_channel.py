"""Adapter kênh Zalo CÁ NHÂN cho Hộp thư hội thoại: đọc tin mới từ MCP `zalo-agent-cli` rồi
đổ vào kho `conversations`.

Ở Việt Nam khách nhắn qua Zalo cá nhân nhiều hơn mọi kênh khác, và không phải ai bán hàng cũng
có Zalo OA. Nên tài khoản Zalo đã quét QR ở trang Kết nối phải là một KÊNH của Hộp thư, không
phải một tool mà chỉ khi chủ hỏi Javis mới đọc.

Cách làm: vòng lặp nền, mỗi `NHIP` giây gọi `zalo_get_messages` với cursor lần trước, chuẩn hoá
từng tin về sự kiện chung rồi `conversations.ghi_su_kien`. Cursor lưu ở `sync_state` của kho,
nên khởi động lại server không đọc trùng (và có trùng thì kho tự chặn theo id tin).

Ba quyết định đáng ghi lại:

  1. **Chỉ ghi khi chủ BẬT cho từng tài khoản** (trang Hộp thư, mục Kênh). Vòng lặp này giữ
     tiến trình MCP sống liên tục (mỗi lần gọi là một lần chạm phiên), tức tài khoản Zalo đăng
     nhập 24/7 qua API không chính thức. Đó là lựa chọn của chủ tài khoản, không phải của Javis.
  2. **Không gọi `zalo_mark_read`.** Cursor của kho là cursor của kho; bộ đệm của MCP để nguyên
     cho chủ hỏi Javis "có tin Zalo mới không" như trước. Tool này là tool ĐỌC, không đụng quyền.
  3. **Không đồng bộ lịch sử cũ.** Lần đầu bật chỉ lấy tin từ lúc bật trở đi (bộ đệm MCP vốn
     chỉ giữ tin từ khi tiến trình chạy), đúng luật của kho: lưu từ lúc kênh được nối.

Gọi MCP đi THẲNG qua `mcp_client.pool` (không qua hub `_guard`): hub bọc quyền và audit cho
model gọi; ở đây là vòng lặp hệ thống, tool đọc, và mỗi 20 giây một dòng audit chỉ là rác.

Bot tự trả lời (0.64.80): tài khoản này gắn được Bot chuyên trách như Telegram hay Zalo Bot.
Chủ quyết định 29/09/2026: bot TỰ TRẢ LỜI và TỰ QUYẾT có nên trả lời không, không cần công tắc
từng người, vì nick này chủ tự quản lý và đã có Hộp thư để giám sát. Đây là chỗ đảo lại quyết
định bỏ tự trả lời Zalo hồi 21/07 (bản khi đó dựa trên listener luật, nay là bot chuyên trách
có Agent, mức quyền, giới hạn tần suất và Hộp thư). Xem "Bot trả lời" ở cuối file: chỉ trả lời
chat RIÊNG dạng chữ, bỏ tin cũ, im khi chủ đang tự nhắn.

Chưa có: tải media. Tin ảnh/file ghi loại tin kèm mô tả, không tải về, và bot không trả lời chúng.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any, Dict, List, Optional

import config as cfgmod
import conversations

CONNECTOR_ID = "zalo"
KENH = "zalo_personal"
NHIP = 20               # giây giữa hai lần đọc
NHIP_LOI = 90           # nghỉ dài hơn khi một tài khoản vừa lỗi (MCP chết, chưa đăng nhập)
LIMIT = 100             # tin mỗi lần đọc
TEN_TTL = 300           # giây giữ bảng tên thread (zalo_list_threads) trước khi hỏi lại
MAX_TEN = 2000

_task: Optional[asyncio.Task] = None
_stop = False
# conn_id -> {"lan_cuoi": ts, "loi": str, "so_tin": int, "ten": {threadId: {...}}, "ten_ts": ts,
#             "nghi_toi": ts}
_TT: Dict[str, dict] = {}


# ============================================================
# Cấu hình: chủ bật/tắt cho TỪNG tài khoản
# ============================================================
def _cau_hinh() -> dict:
    cfg = cfgmod.read_settings()
    ht = cfg.get("conversations") or {}
    zp = ht.get("zalo_personal") or {}
    return zp if isinstance(zp, dict) else {}


def dang_bat(conn_id: str) -> bool:
    return bool(_cau_hinh().get(str(conn_id)))


def bat(conn_id: str, on: bool) -> dict:
    """Bật/tắt ghi hội thoại cho một tài khoản Zalo. Trả về trạng thái sau khi đổi."""
    cid = str(conn_id or "").strip()
    if not cid:
        return {"ok": False, "error": "thiếu id kết nối"}
    if not any(c["id"] == cid for c in _ket_noi()):
        return {"ok": False, "error": "không có kết nối Zalo nào id đó (hoặc đang tắt ở trang Kết nối)"}
    cfg = cfgmod.read_settings()
    ht = cfg.setdefault("conversations", {})
    if not isinstance(ht, dict):
        ht = cfg["conversations"] = {}
    zp = ht.setdefault("zalo_personal", {})
    if not isinstance(zp, dict):
        zp = ht["zalo_personal"] = {}
    zp[cid] = bool(on)
    cfgmod.write_settings(cfg)
    if on:
        # Bật là bắt đầu từ BÂY GIỜ: bỏ cursor cũ để không kéo lại bộ đệm cũ của một lần bật trước.
        _TT.pop(cid, None)
        start()
    return {"ok": True, "id": cid, "theo_doi": bool(on)}


# ============================================================
# Kết nối Zalo đang có
# ============================================================
def _ket_noi() -> List[dict]:
    """Kết nối Zalo đang BẬT ở trang Kết nối, bản đầy đủ (có env HOME) cho dial spec."""
    try:
        import mcp_store
        return [c for c in mcp_store.resolved(enabled_only=True)
                if c.get("connector_id") == CONNECTOR_ID]
    except Exception as e:
        print(f"[zalo-personal] đọc kết nối lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def ket_noi_theo_id(conn_id: str) -> Optional[dict]:
    """Bản đầy đủ (có env) của một kết nối Zalo đang bật, để gọi MCP. None nếu không có."""
    for c in _ket_noi():
        if c.get("id") == str(conn_id or ""):
            return c
    return None


def tai_khoan() -> List[dict]:
    """Cho trang Hộp thư: mỗi tài khoản Zalo kèm cờ theo dõi và trạng thái vòng đọc."""
    cfg = _cau_hinh()
    out = []
    for c in _ket_noi():
        tt = _TT.get(c["id"]) or {}
        out.append({
            "id": c["id"], "label": c.get("label") or "Zalo", "channel": KENH,
            "theo_doi": bool(cfg.get(c["id"])),
            "lan_cuoi": tt.get("lan_cuoi") or 0, "loi": tt.get("loi") or "",
            "so_tin": int(tt.get("so_tin") or 0),
        })
    return out


# ============================================================
# Gọi MCP
# ============================================================
async def _goi(conn: dict, tool: str, args: dict) -> Any:
    import mcp_client
    spec = mcp_client._conn_spec(conn)
    raw = await mcp_client.pool.call_tool(spec, tool, args or {})
    if isinstance(raw, str) and raw.startswith("ERROR:"):
        raise RuntimeError(raw[6:].strip()[:300])
    return _json_cua(raw)


def _json_cua(raw: Any) -> Any:
    """Kết quả MCP về dạng chữ; bóc JSON nếu có, không thì trả nguyên."""
    if isinstance(raw, (dict, list)):
        return raw
    s = str(raw or "").strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        pass
    # Có server bọc JSON trong text kèm vài dòng chữ: lấy khối {...} hoặc [...] đầu tiên.
    for mo, dong in (("{", "}"), ("[", "]")):
        a, b = s.find(mo), s.rfind(dong)
        if 0 <= a < b:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                continue
    return {"text": s}


# ============================================================
# Chuẩn hoá một tin Zalo về sự kiện chung
# ============================================================
def _lay(d: dict, *khoa, mac_dinh=None):
    for k in khoa:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return mac_dinh


def _ts(v: Any) -> float:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return time.time()
    if f <= 0:
        return time.time()
    return f / 1000.0 if f > 1e12 else f


def _la_nhom(msg: dict, ten: dict) -> bool:
    t = _lay(msg, "threadType", "thread_type", "type_thread", mac_dinh=None)
    if t is not None:
        s = str(t).strip().lower()
        if s in ("1", "group", "true"):
            return True
        if s in ("0", "dm", "user", "private", "false"):
            return False
    if isinstance(msg.get("isGroup"), bool):
        return msg["isGroup"]
    return str((ten or {}).get("type") or "").lower() == "group"


def _la_cua_minh(msg: dict) -> bool:
    for k in ("isSelf", "fromMe", "isOwn", "self", "is_self", "from_me"):
        v = msg.get(k)
        if isinstance(v, bool):
            return v
    return False


def _loai_tin(msg: dict) -> str:
    t = str(_lay(msg, "type", "msgType", "message_type", mac_dinh="text") or "text").lower()
    if t in conversations.LOAI_TIN:
        return t
    if "image" in t or "photo" in t or t == "chat.photo":
        return "image"
    if "voice" in t or "audio" in t:
        return "audio"
    if "video" in t:
        return "video"
    if "sticker" in t:
        return "sticker"
    if "file" in t or "doc" in t:
        return "file"
    if t in ("text", "chat", "webchat"):
        return "text"
    return "other"


def _link_anh(msg: dict) -> str:
    """Link of the photo in an image message (0.74.1), or "".

    The MCP normalizes a photo as `attachment: {type, url: content.href, description: content.title}` (zalo-agent-cli 1.6.2,
    `normalizeMessage` in src/commands/mcp.js). Before 0.74.1 this was dropped here, so the inbox and the customer bot only ever got
    the caption and the bot answered "I can only see the caption". A bare photo also carries the link as its `text`."""
    att = msg.get("attachment") if isinstance(msg.get("attachment"), dict) else {}
    for v in (att.get("url"), msg.get("mediaUrl"), msg.get("url"), msg.get("text")):
        v = str(v or "").strip()
        if v.startswith("https://"):
            return v
    return ""


def chuan_hoa_tin(conn: dict, msg: dict, ten: Dict[str, dict]) -> Optional[dict]:
    """Một tin của `zalo_get_messages` -> sự kiện chung của kho. None nếu không biết thread."""
    if not isinstance(msg, dict):
        return None
    thread = str(_lay(msg, "threadId", "thread_id", "chatId", mac_dinh="") or "").strip()
    if not thread:
        return None
    th = ten.get(thread) or {}
    nhom = _la_nhom(msg, th)
    sender_id = str(_lay(msg, "from", "senderId", "sender_id", "uidFrom", mac_dinh="") or "").strip()
    sender_name = str(_lay(msg, "senderName", "sender_name", "fromName", "dName", mac_dinh="") or "").strip()
    if not sender_name and not nhom:
        sender_name = str(th.get("name") or "")
    loai = _loai_tin(msg)
    text = _lay(msg, "text", "content", "msg", "message", mac_dinh="")
    if isinstance(text, dict):
        text = _lay(text, "text", "title", "description", "href", mac_dinh="")
    text = str(text or "")
    if loai != "text" and not text.strip():
        text = f"[{conversations.KENH_NHAN[KENH]}: khách gửi {loai}]"
    cua_minh = _la_cua_minh(msg)
    return {
        "channel": KENH,
        "account_id": conn["id"],
        "account_name": conn.get("label") or "Zalo",
        "bot_id": "",
        "external_chat_id": thread,
        "chat_type": "group" if nhom else "private",
        "chat_title": str(th.get("name") or "") if nhom else "",
        # Tin do CHÍNH chủ gửi (từ điện thoại) là tin người thật, không phải tin khách.
        "sender_type": "human" if cua_minh else "customer",
        "sender_id": "" if cua_minh else (sender_id or ("" if nhom else thread)),
        "sender_name": sender_name,
        "message_type": loai,
        "text": text,
        "external_message_id": str(_lay(msg, "id", "msgId", "message_id", mac_dinh="") or ""),
        "created_at": _ts(_lay(msg, "ts", "timestamp", "time", mac_dinh=0)),
        "metadata": dict({k: msg.get(k) for k in ("replyTo", "mentions", "mediaUrl", "url", "fileName")
                          if msg.get(k) not in (None, "")},
                         **({"image_url": _link_anh(msg)} if loai == "image" and _link_anh(msg) else {}),
                         **(_tep_md(msg) if loai == "file" else {})),
    }


def _tep_md(msg: dict) -> dict:
    """Link tải và tên của một tin file (26.10.306): MCP đưa ở `attachment.url` / `.description`
    (zalo-agent-cli 1.6.2, `normalizeMessage`). Không có thì {}: bot nói thật là chưa mở được."""
    att = msg.get("attachment") if isinstance(msg.get("attachment"), dict) else {}
    out = {}
    url = str(att.get("url") or msg.get("mediaUrl") or msg.get("url") or "").strip()
    if url.startswith("https://"):
        out["file_url"] = url
    ten = str(msg.get("fileName") or att.get("description") or "").strip()
    if ten and not msg.get("fileName"):
        out["fileName"] = ten[:200]
    return out


# ============================================================
# Vòng đọc
# ============================================================
async def _nap_ten(conn: dict, tt: dict) -> Dict[str, dict]:
    """Bảng threadId -> {name, type}. Hỏi lại sau TEN_TTL giây, hỏng thì giữ bảng cũ."""
    if tt.get("ten") is not None and time.time() - float(tt.get("ten_ts") or 0) < TEN_TTL:
        return tt["ten"]
    try:
        d = await _goi(conn, "zalo_list_threads", {"limit": 200})
        ds = d.get("threads") if isinstance(d, dict) else d
        bang: Dict[str, dict] = dict(tt.get("ten") or {})
        for t in (ds or []):
            if not isinstance(t, dict):
                continue
            tid = str(_lay(t, "threadId", "id", mac_dinh="") or "")
            if tid:
                bang[tid] = {"name": str(t.get("name") or "")[:120], "type": str(t.get("type") or "")}
        if len(bang) > MAX_TEN:
            bang = dict(list(bang.items())[-MAX_TEN:])
        tt["ten"], tt["ten_ts"] = bang, time.time()
    except Exception as e:
        tt["ten_ts"] = time.time()      # đừng hỏi dồn dập khi đang hỏng
        if tt.get("ten") is None:
            tt["ten"] = {}
        print(f"[zalo-personal {conn.get('label')}] list_threads: {e}", file=sys.stderr)
    return tt["ten"]


def _chuan_ten(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


async def danh_ba(conn_id: str, q: str = "", loai: str = "") -> dict:
    """Danh bạ để chủ TÍCH CHỌN thay vì chép id tay: bạn bè và nhóm của một nick Zalo, lọc theo tên
    (không phân biệt hoa thường và dấu). `loai` = "private" | "group" | "" (cả hai).
    Gộp ba nguồn: danh sách cuộc chat của Zalo, kết quả tìm của Zalo cho đúng từ khoá, và các
    cuộc chat bot đã từng thấy (có tên). Nguồn nào hỏng thì bỏ nguồn đó, không làm cả danh sách lỗi."""
    conn = ket_noi_theo_id(conn_id)
    if not conn:
        return {"ok": False, "error": "Tài khoản Zalo này chưa bật hoặc chưa kết nối."}
    bang: Dict[str, dict] = {}

    def them(t):
        if not isinstance(t, dict):
            return
        tid = str(_lay(t, "threadId", "id", mac_dinh="") or "")
        if not tid:
            return
        ten = str(t.get("name") or t.get("displayName") or t.get("title") or "").strip()
        ty = str(t.get("type") or "").lower()
        nhom = ty == "group" or str(t.get("threadType")) == "1"
        cu = bang.get(tid) or {}
        bang[tid] = {"id": tid, "name": ten or cu.get("name") or "", "type": "group" if nhom else "private"}

    loi = ""
    try:
        d = await _goi(conn, "zalo_list_threads", {"limit": 500})
        for t in ((d.get("threads") if isinstance(d, dict) else d) or []):
            them(t)
    except Exception as e:
        loi = str(e)[:200]
    if str(q or "").strip():
        try:
            d = await _goi(conn, "zalo_search_threads", {"query": str(q).strip()})
            for t in ((d.get("threads") or d.get("results") or d.get("items")) if isinstance(d, dict) else d) or []:
                them(t)
        except Exception as e:
            loi = loi or str(e)[:200]
    try:
        for c in conversations.danh_sach(channel=KENH, account_id=str(conn_id), limit=300) or []:
            tid = str(c.get("external_chat_id") or "")
            if tid:
                them({"threadId": tid, "name": c.get("title") or c.get("customer_name") or "",
                      "type": "group" if c.get("chat_type") == "group" else "user"})
    except Exception:
        pass
    k = _chuan_ten(q)
    ds = [v for v in bang.values()
          if (not loai or v["type"] == loai) and (not k or k in _chuan_ten(v["name"]) or k in v["id"])]
    ds.sort(key=lambda v: (v["type"] != "group", _chuan_ten(v["name"]) or "~", v["id"]))
    if not ds and loi:
        return {"ok": False, "error": "Chưa lấy được danh bạ Zalo: " + loi}
    return {"ok": True, "items": ds[:400]}


async def doc_mot_lan(conn: dict) -> dict:
    """Một lượt đọc cho một tài khoản. Trả {"moi": n, "trung": n} hoặc ném lỗi."""
    tt = _TT.setdefault(conn["id"], {})
    khoa_cursor = f"{KENH}:{conn['id']}:cursor"
    cursor = conversations.doc_trang_thai(khoa_cursor, "")
    args: Dict[str, Any] = {"limit": LIMIT}
    if cursor:
        args["cursor"] = cursor
    d = await _goi(conn, "zalo_get_messages", args)
    if not isinstance(d, dict):
        d = {"messages": d if isinstance(d, list) else []}
    tin = d.get("messages") or []
    ten = await _nap_ten(conn, tt) if tin else (tt.get("ten") or {})
    moi = trung = 0
    bo_lo: Dict[str, str] = {}   # khách chat riêng nhắn lúc bot không kịp trả lời (tin quá cũ)
    for m in tin:
        ev = chuan_hoa_tin(conn, m, ten)
        if not ev:
            continue
        if ev["sender_type"] == "human":
            # Tin chủ gửi đi. Tiếng vọng của câu BOT vừa gửi thì bỏ (bot đã tự ghi câu đó vào
            # Hộp thư, ghi thêm lần nữa là hiện hai lần, lần hai mang nhãn "người thật"). Còn
            # lại là chủ tự tay nhắn: nhớ giờ để bot nhường cuộc chat đó.
            if _la_tieng_vong(conn["id"], ev["external_chat_id"], ev["text"]) or \
                    _la_tieng_vong_tep(conn["id"], ev["external_chat_id"], str(ev.get("message_type") or "text")):
                trung += 1
                continue
            _TAY[(conn["id"], ev["external_chat_id"])] = float(ev.get("created_at") or time.time())
        kq = conversations.ghi_su_kien(ev)
        if kq.get("ok"):
            if kq.get("trung"):
                trung += 1
            else:
                moi += 1
                if (ev.get("sender_type") == "customer" and ev.get("chat_type") == "private"
                        and TUOI_TOI_DA < time.time() - float(ev.get("created_at") or 0) < TUOI_BAO_LO):
                    bo_lo[str(ev.get("external_chat_id") or "")] = str(ev.get("sender_name") or "một khách")
                _giao_cho_bot(conn, ev)
    if bo_lo and cursor and conn["id"] in _BOTS:
        bao_tin_bo_lo(conn, list(bo_lo.values()))
    nc = _lay(d, "nextCursor", "next_cursor", "cursor", mac_dinh="")
    if nc:
        conversations.ghi_trang_thai(khoa_cursor, str(nc))
    tt["lan_cuoi"] = time.time()
    tt["loi"] = ""
    tt["so_tin"] = int(tt.get("so_tin") or 0) + moi
    return {"moi": moi, "trung": trung}


TUOI_BAO_LO = 6 * 3600   # tin cũ hơn mức này mà tới giờ mới thấy: coi là lịch sử, không báo


def bao_tin_bo_lo(conn: dict, ten: list) -> None:
    """Mất kết nối / MinMin tắt một lúc rồi đọc lại được: tin khách trong khoảng đó vào Hộp thư
    nhưng bot không trả lời (quá cũ). Báo chủ MỘT lần để tự xem, thay vì để khách chờ trong im lặng."""
    try:
        import inbox
        ds = ", ".join(sorted(set(str(t) for t in ten))[:8])
        inbox.add(f"Có {len(ten)} tin khách nhắn lúc Zalo \"{conn.get('label') or conn.get('id')}\" "
                  f"chưa đọc được (mất kết nối hoặc MinMin vừa khởi động lại): {ds}. "
                  f"Bot không tự trả lời vì tin đã quá cũ. Mở Hộp thư hội thoại để xem và trả lời.",
                  kind="system", title="Có khách nhắn lúc bot vắng", source="zalo_personal")
    except Exception as e:
        print(f"[zalo-personal] báo tin bỏ lỡ lỗi: {e}", file=sys.stderr)


async def _vong() -> None:
    print("[zalo-personal] vòng đọc bắt đầu", file=sys.stderr)
    while not _stop:
        try:
            cfg = _cau_hinh()
            # Có bot trực thì đọc dù công tắc Ghi hội thoại tắt: bot không đọc thì không trả lời được.
            bat_ids = {k for k, v in cfg.items() if v} | set(_BOTS)
            if bat_ids:
                for conn in _ket_noi():
                    if _stop or conn["id"] not in bat_ids:
                        continue
                    tt = _TT.setdefault(conn["id"], {})
                    if time.time() < float(tt.get("nghi_toi") or 0):
                        continue
                    try:
                        await doc_mot_lan(conn)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        tt["loi"] = f"{type(e).__name__}: {e}"[:300]
                        tt["nghi_toi"] = time.time() + NHIP_LOI
                        print(f"[zalo-personal {conn.get('label')}] {tt['loi']}", file=sys.stderr)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[zalo-personal vòng] {type(e).__name__}: {e}", file=sys.stderr)
        try:
            await asyncio.sleep(NHIP)
        except asyncio.CancelledError:
            raise
    print("[zalo-personal] vòng đọc dừng", file=sys.stderr)


def start() -> bool:
    """Bật vòng đọc nếu chưa chạy. Không có tài khoản nào được bật thì vòng vẫn chạy nhẹ (chỉ
    đọc cấu hình mỗi nhịp) để bật từ giao diện là có tác dụng ngay, không cần khởi động lại."""
    global _task, _stop
    if _task and not _task.done():
        return True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    _stop = False
    _task = loop.create_task(_vong())
    return True


def stop() -> None:
    global _task, _stop
    _stop = True
    if _task and not _task.done():
        _task.cancel()
    _task = None


def trang_thai() -> dict:
    return {"dang_chay": bool(_task and not _task.done()), "nhip": NHIP,
            "tai_khoan": tai_khoan()}


# ============================================================
# Bot trả lời (0.64.80)
# ============================================================
# Vòng đọc ở trên là NGUỒN tin duy nhất của tài khoản này (một con trỏ cursor, không được có
# hai người đọc). Bot chuyên trách không tự đọc mà đăng ký ở đây; tin khách mới ghi xong thì
# được đưa cho nó. Các rào để bot không nhắn bậy dưới tên chủ nằm ở `channels.zalo_personal.
# Transport.xu_ly` và ở hằng số dưới.
TUOI_TOI_DA = 180       # giây: tin cũ hơn thế thì KHÔNG trả lời. Lần đầu bật, bộ đệm của MCP
                        # còn cả những tin từ trước; trả lời chúng là dội lại câu hỏi của hôm qua.
TAY_IM = 600            # giây bot im sau khi chủ TỰ TAY nhắn cuộc chat đó (chủ đang nói chuyện rồi)
ECHO_TTL = 900          # giây nhớ câu bot vừa gửi để nhận ra tiếng vọng của nó ở vòng đọc

_BOTS: Dict[str, Any] = {}          # conn_id -> Transport đang trực
_DA_GUI: Dict[tuple, list] = {}     # (conn_id, thread) -> [(ts, chữ đã chuẩn hoá)]
_TAY: Dict[tuple, float] = {}       # (conn_id, thread) -> giờ tin chủ tự nhắn gần nhất
_VIEC: set = set()                  # giữ tham chiếu task đang chạy, kẻo bị thu gom giữa chừng


def dang_ky_bot(conn_id: str, tb: Any) -> None:
    _BOTS[str(conn_id)] = tb
    start()


def huy_dang_ky_bot(conn_id: str, tb: Any = None) -> None:
    cid = str(conn_id)
    if tb is None or _BOTS.get(cid) is tb:
        _BOTS.pop(cid, None)


def co_bot(conn_id: str) -> bool:
    return str(conn_id) in _BOTS


def _chuan(text: str) -> str:
    return " ".join(str(text or "").split())


def ghi_da_gui(conn_id: str, thread: str, text: str) -> None:
    """Bot vừa gửi `text`: nhớ lại để vòng đọc nhận ra tiếng vọng của nó."""
    khoa = (str(conn_id), str(thread))
    now = time.time()
    ds = [x for x in _DA_GUI.get(khoa, []) if now - x[0] < ECHO_TTL]
    ds.append((now, _chuan(text)))
    _DA_GUI[khoa] = ds[-20:]
    if len(_DA_GUI) > 500:      # trần thô: thà quên một tiếng vọng còn hơn phình mãi
        for k in list(_DA_GUI)[:250]:
            _DA_GUI.pop(k, None)


_TEP_DA_GUI: Dict[tuple, List[float]] = {}


def ghi_tep_da_gui(conn_id: str, thread: str) -> None:
    """Bot sắp gửi một ảnh/video/file: tiếng vọng của nó (tin người gửi là chủ, loại không phải
    chữ) không được tính là chủ tự tay nhắn, nếu không bot tự câm trong cuộc chat đó."""
    khoa = (str(conn_id), str(thread))
    now = time.time()
    ds = [t for t in _TEP_DA_GUI.get(khoa, []) if now - t < ECHO_TTL]
    ds.append(now)
    _TEP_DA_GUI[khoa] = ds[-20:]
    if len(_TEP_DA_GUI) > 500:
        for k in list(_TEP_DA_GUI)[:250]:
            _TEP_DA_GUI.pop(k, None)


def _la_tieng_vong_tep(conn_id: str, thread: str, loai: str) -> bool:
    if loai == "text":
        return False
    khoa = (str(conn_id), str(thread))
    now = time.time()
    ds = [t for t in _TEP_DA_GUI.get(khoa, []) if now - t < ECHO_TTL]
    _TEP_DA_GUI[khoa] = ds
    if not ds:
        return False
    ds.pop(0)
    return True


def _la_tieng_vong(conn_id: str, thread: str, text: str) -> bool:
    khoa = (str(conn_id), str(thread))
    now = time.time()
    ds = [x for x in _DA_GUI.get(khoa, []) if now - x[0] < ECHO_TTL]
    if not ds:
        _DA_GUI.pop(khoa, None)
        return False
    t = _chuan(text)
    for i, (_, gui) in enumerate(ds):
        # So bằng hoặc đầu-câu: Zalo có thể cắt/đổi chút ở đuôi tin dài.
        if t and gui and (t == gui or t.startswith(gui[:80]) or gui.startswith(t[:80])):
            del ds[i]
            _DA_GUI[khoa] = ds
            return True
    _DA_GUI[khoa] = ds
    return False


def la_tra_loi_bot(conn_id: str, thread: str, reply_to) -> bool:
    """Tin này là TRẢ LỜI một câu bot vừa nói không (khách bấm Trả lời vào tin của bot).
    Đối chiếu nội dung tin được trích với những câu bot đã gửi gần đây; không có thông tin
    trích thì False, không đoán."""
    if not reply_to:
        return False
    trich = reply_to.get("text") or reply_to.get("content") or reply_to.get("msg") \
        if isinstance(reply_to, dict) else reply_to
    t = _chuan(trich if isinstance(trich, str) else "")
    if len(t) < 8:
        return False
    now = time.time()
    for ts, gui in _DA_GUI.get((str(conn_id), str(thread)), []):
        if now - ts < 6 * 3600 and gui and (gui.startswith(t[:60]) or t.startswith(gui[:60])):
            return True
    return False


def chu_vua_nhan_tay(conn_id: str, thread: str, now: Optional[float] = None) -> bool:
    """Chủ vừa tự tay nhắn cuộc chat này (trong `TAY_IM` giây) - bot nhường."""
    t = _TAY.get((str(conn_id), str(thread)))
    return bool(t) and ((time.time() if now is None else now) - t) < TAY_IM


def _giao_cho_bot(conn: dict, ev: dict) -> None:
    tb = _BOTS.get(str(conn.get("id") or ""))
    if not tb or ev.get("sender_type") != "customer":
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    t = loop.create_task(tb.xu_ly(ev))
    _VIEC.add(t)
    t.add_done_callback(_VIEC.discard)


# ============================================================
# File khách gửi (26.10.306) - phần đọc file ở `zalo_tep`
# ============================================================
def tep_cua_tin(ev: dict) -> Optional[dict]:
    import zalo_tep
    return zalo_tep.tep_cua_tin(ev)


def xu_ly_tep_nhom(conn_id: str, ev: dict) -> None:
    """File trơn trong nhóm (không ai gọi bot): nhớ link cho người gửi, không tải gì."""
    import zalo_tep
    tep = zalo_tep.tep_cua_tin(ev)
    if tep and ev.get("sender_type") == "customer":
        zalo_tep.nho_tep_tron(conn_id, str(ev.get("external_chat_id") or ""), str(ev.get("sender_id") or ""),
                              tep, float(ev.get("created_at") or 0))


def lay_tep_tron(conn_id: str, thread: str, nguoi: str) -> list:
    import zalo_tep
    return zalo_tep.lay_tep_tron(conn_id, thread, nguoi)


# ============================================================
# Tag Zalo của cuộc chat (26.10.306, học Javis 0.282)
# ============================================================
# Tag chủ gắn trong app Zalo (Gia đình, Bạn bè, Khách...) cho bot biết người nhắn là ai với chủ,
# và form bot có ô "không trả lời các chat mang tag này". zalo-agent-cli 1.6.2 không có tool MCP
# đọc tag, nhưng CLI của chính gói đã ghim có `label list` (cùng thư mục đăng nhập). Đọc NỀN và
# giữ trong bộ nhớ: một lượt bot không bao giờ chờ Zalo chỉ để biết chat có tag hay không.
NHAN_TTL = 600            # giây giữ bảng tag trước khi đọc lại
NHAN_THU_LAI = 1800       # đọc hỏng (CLI lỗi, chưa có Node) thì nghỉ lâu hơn
_NHAN: Dict[str, dict] = {}     # conn_id -> {"luc", "ok", "ten": [...], "theo_chat": {thread: [tên]}}
_NHAN_DANG_DOC: set = set()


def bang_nhan(data: Any) -> dict:
    """Kết quả `label list --json` -> {"ten": [tên tag theo thứ tự], "theo_chat": {threadId: [tên]}}.

    Bản ghi của zca-js: `{labelData: [{id, text, conversations: ["<id>" | "g<id>"], ...}]}`. Id nhóm
    có tiền tố "g"; bỏ đi để khớp threadId của kho."""
    ten, theo_chat = [], {}
    ds = data.get("labelData") if isinstance(data, dict) else data
    for lb in ds if isinstance(ds, list) else []:
        if not isinstance(lb, dict):
            continue
        t = " ".join(str(lb.get("text") or lb.get("name") or "").split())[:60]
        if not t:
            continue
        if t not in ten:
            ten.append(t)
        for c in lb.get("conversations") or []:
            cid = str(c or "").strip()
            if cid[:1] in ("g", "u") and cid[1:].isdigit():
                cid = cid[1:]
            if cid:
                ds_t = theo_chat.setdefault(cid, [])
                if t not in ds_t:
                    ds_t.append(t)
    return {"ten": ten, "theo_chat": theo_chat}


async def _doc_nhan(conn_id: str) -> None:
    import os
    import shutil
    from channels import zalo_personal as zp
    now = time.time()
    try:
        conn = ket_noi_theo_id(conn_id)
        argv = zp.lenh_cli(conn, "--json", "label", "list") if conn else None
        if not argv or not shutil.which("npx"):
            raise RuntimeError("không dựng được lệnh CLI")
        env = dict(os.environ)
        env.update({k: str(v) for k, v in ((conn or {}).get("env") or {}).items()})
        import winproc
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL, env=env, **winproc.kwargs_no_window())
        try:
            out, _e = await asyncio.wait_for(proc.communicate(), timeout=40)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("CLI quá hạn")
        if proc.returncode != 0:
            raise RuntimeError(f"CLI thoát mã {proc.returncode}")
        _NHAN[conn_id] = dict(bang_nhan(_json_cua(out.decode("utf-8", "replace"))), luc=now, ok=True)
    except Exception as e:      # noqa: BLE001 - tag chỉ là gợi ý cho bot; thiếu thì bot chạy như cũ
        cu = _NHAN.get(conn_id) or {"ten": [], "theo_chat": {}}
        _NHAN[conn_id] = dict(cu, luc=now, ok=False)
        print(f"[zalo-personal {conn_id}] đọc tag Zalo lỗi: {type(e).__name__}: {str(e)[:160]}", file=sys.stderr)
    finally:
        _NHAN_DANG_DOC.discard(conn_id)


def _lam_moi_nhan(conn_id: str) -> None:
    c = _NHAN.get(conn_id)
    if c and time.time() - float(c.get("luc") or 0) < (NHAN_TTL if c.get("ok") else NHAN_THU_LAI):
        return
    if conn_id in _NHAN_DANG_DOC:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _NHAN_DANG_DOC.add(conn_id)
    t = loop.create_task(_doc_nhan(conn_id))
    _VIEC.add(t)
    t.add_done_callback(_VIEC.discard)


def nhan_cua_chat(conn_id: str, thread: str) -> List[str]:
    """Tên tag Zalo trên một cuộc chat (vd ["Gia đình"]), [] khi không có hoặc chưa đọc được.
    Không chờ: đọc bảng đang có, bảng cũ thì đọc lại ở nền cho lượt sau."""
    cid = str(conn_id or "")
    _lam_moi_nhan(cid)
    return list(((_NHAN.get(cid) or {}).get("theo_chat") or {}).get(str(thread or ""), []))


def ten_nhan(conn_id: str) -> List[str]:
    """Mọi tên tag của một tài khoản (cho form bot). Có thể rỗng ở lần hỏi đầu, lần sau sẽ có."""
    cid = str(conn_id or "")
    _lam_moi_nhan(cid)
    return list((_NHAN.get(cid) or {}).get("ten") or [])


# ============================================================
# Câu bot gửi không tới khách (26.10.306, học Javis 0.282)
# ============================================================
GUI_HONG_CHUONG = 1800      # giây: mỗi tài khoản báo chuông nhiều nhất một lần mỗi 30 phút
_GUI_HONG: Dict[str, float] = {}


def bao_gui_hong(conn_id: str, thread: str, cau: str, loi: str, chat_type: str = "") -> None:
    """Zalo từ chối câu bot vừa soạn: ghi một dòng hệ thống vào đúng cuộc chat trong Hộp thư (để
    chủ thấy khách CHƯA nhận được gì) và báo chuông, không lặng lẽ như đã gửi."""
    try:
        cid = conversations.conversation_id_of(KENH, str(conn_id), str(thread))
        truoc = (conversations.chi_tiet(cid) or {}).get("last_sender_type") if cid else ""
        kq = conversations.ghi_su_kien({
            "channel": KENH, "account_id": str(conn_id), "external_chat_id": str(thread),
            "chat_type": chat_type or "private", "sender_type": "system", "message_type": "text",
            "text": "Bot soạn được câu trả lời nhưng Zalo không gửi đi, khách chưa nhận được: "
                    + " ".join(str(cau or "").split())[:300],
            "metadata": {"loi": str(loi or "")[:300], "gui_hong": True},
        })
        # Khách vẫn CHƯA được trả lời: giữ cuộc chat ở "Cần trả lời" của hộp thư (26.10.284 xét
        # last_sender_type='customer'). Câu bot đã ghi vào kho TRƯỚC khi gửi (tin "ai" cuối) không
        # tới khách, nên nó và dòng hệ thống này không được làm cuộc chat trông như đã đáp.
        if truoc in ("customer", "ai") and kq.get("conversation_id"):
            with conversations._lock:
                db = conversations._conn()
                db.execute("UPDATE conversations SET last_sender_type='customer' WHERE id=?",
                           (int(kq["conversation_id"]),))
                db.commit()
    except Exception as e:      # noqa: BLE001
        print(f"[zalo-personal] ghi gửi hỏng lỗi: {e}", file=sys.stderr)
    now = time.time()
    if now - _GUI_HONG.get(str(conn_id), 0) < GUI_HONG_CHUONG:
        return
    _GUI_HONG[str(conn_id)] = now
    try:
        import inbox
        c = ket_noi_theo_id(conn_id) or {}
        inbox.add(f"Bot trên Zalo \"{c.get('label') or conn_id}\" soạn được câu trả lời nhưng Zalo không gửi đi: "
                  f"{str(loi or '')[:200]}. Thường là nick đang mở ở nơi khác (Zalo Web, máy khác) giành kết nối. "
                  f"Mở trang Khách để xem khách nào chưa nhận được tin.",
                  kind="system", title="Bot Zalo gửi tin không được", source="zalo_personal")
    except Exception as e:      # noqa: BLE001
        print(f"[zalo-personal] báo gửi hỏng lỗi: {e}", file=sys.stderr)
