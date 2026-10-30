"""Pancake vào Hộp thư hội thoại (26.10.315): mỗi Fanpage trong Pancake là MỘT tài khoản của kênh `pancake`.

Chủ quyết định (2026-10-30): khách Fanpage vào hộp thư của MinMin ĐI QUA PANCAKE, không nối Messenger thẳng. Nhân viên
sale vẫn trả lời trong Pancake như mọi ngày, khách không bao giờ nhận hai câu trả lời từ hai hệ thống.

Nguồn page và token: CHÍNH kết nối "Thống kê Pancake" ở trang Kết nối (ô `pages`, mỗi dòng
`page_id | page_access_token | tên`), đọc bằng `pancake_chat_mcp.doc_pages`. Không có kho token thứ hai.
HTTP đi qua `pancake_hoi_thoai.request` (chỉ host pages.fm, không theo chuyển hướng, giấu token).

Đồng bộ tăng dần, mỗi `NHIP` giây cho từng Page đang bật:

  1. `GET /pages/{id}/conversations` (public_api v2, `type=INBOX`, `order_by=updated_at`, `since`/`until` giây unix).
     Đây đúng là lời gọi tool `pancake_conversations_list` đang dùng. Mỗi hội thoại có `updated_at`; MinMin nhớ
     `updated_at` lần trước của từng hội thoại (sync_state), chỉ hội thoại ĐỔI mới đọc tin.
  2. `GET /pages/{id}/conversations/{cid}/messages` (public_api v1), lấy khúc tin mới nhất.
  3. Mỗi tin Pancake có `id`: ghi vào kho với `external_message_id` = id đó, kho tự chặn trùng.

Ai gửi tin nào:
  - `from.id` khác page_id: KHÁCH.
  - `from.id` là page và trùng một câu MinMin vừa gửi (nhớ chữ trước khi gửi, nhớ mã tin Pancake trả về): tiếng vọng
    của chính MinMin, gắn mã tin vào dòng đã ghi rồi bỏ qua.
  - Tên người gửi là Botcake/POS/bot tự động: tin hệ thống (`system`), không tính là người trực.
  - Còn lại: NHÂN VIÊN trả lời trong Pancake (`human`). Tin mới loại này chuyển cuộc chat sang "Bạn đang xử lý"
    (mode `human`) và bỏ nháp đang chờ, y như chủ tự gõ ở Hộp thư: A.I. nhường lời.

Mặc định an toàn: cuộc chat Pancake KHÔNG BAO GIỜ tự gửi trừ khi chủ bật "A.I. tự trả lời" cho đúng Page đó (công tắc
riêng, có cảnh báo nhân viên cũng đang trả lời). Chưa bật thì mọi cuộc chat ở chế độ "A.I. soạn, tôi duyệt" (có bot)
hoặc "Chỉ ghi lại" (không bot). `channels.pancake.Transport` chặn lần nữa ngay trước khi gửi.

Lần đầu bật một Page: chỉ ghi mốc, không kéo lịch sử. Tin cũ hơn mốc bật vào kho làm ngữ cảnh (không tính chưa đọc,
không đổi người trực, không gọi A.I.).

Điểm nối webhook: `bao_co_su_kien(page_id)` đánh thức vòng đọc để đọc Page đó ngay. Hòm webhook bền (lane D) chỉ cần
gọi hàm này khi nhận sự kiện tin nhắn Pancake; nội dung sự kiện không được tin, vẫn đọc lại qua API như trên.
"""
from __future__ import annotations

import asyncio
import html
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config as cfgmod
import conversations

KENH = "pancake"
CONNECTORS = ("pancake-thong-ke", "pancake-chat")
NHIP = 30                 # giây giữa hai lượt đọc một Page
NHIP_LOI = 120            # Page vừa lỗi thì nghỉ lâu hơn
CHONG_LAP = 900           # giây lùi lại khi hỏi `since`: đồng hồ hai bên lệch, tin tới muộn
TOI_DA_HOI_THOAI = 40     # hội thoại đổi tối đa mỗi lượt mỗi Page (phần còn lại để lượt sau)
NHO_HOI_THOAI = 600       # số `updated_at` nhớ mỗi Page
TUOI_GOI_AI = 900         # tin khách cũ hơn thế không gọi A.I. soạn (tin dồn lúc máy tắt)
CUA_SO_FB = 24 * 3600     # Facebook chỉ cho Page nhắn trong 24 giờ kể từ tin cuối của khách
ECHO_TTL = 1800
DS_TTL = 15               # giây giữ danh sách page đọc từ kết nối
TEN_TTL = 900             # giây giữ bảng tên thẻ / nhân viên của Page

_task: Optional[asyncio.Task] = None
_stop = False
_danh_thuc: Optional[asyncio.Event] = None
_GAP: set = set()                     # page_id cần đọc ngay (webhook)
_TT: Dict[str, dict] = {}             # page_id -> {lan_cuoi, loi, so_tin, nghi_toi}
_DS: dict = {"ts": 0.0, "pages": []}
_TEN: Dict[str, dict] = {}            # page_id -> {"ts", "tags": {id: ten}, "users": {id: ten}}
_DA_GUI: Dict[tuple, list] = {}       # (page_id, cid) -> [(ts, chữ chuẩn hoá)]
_MA_DA_GUI: Dict[str, float] = {}     # mã tin Pancake trả về khi MinMin gửi -> ts
_BOTS: Dict[str, Any] = {}            # page_id -> Transport đang trực
_VIEC: set = set()


# ============================================================
# Page và cấu hình
# ============================================================
def _ket_noi() -> List[dict]:
    try:
        import mcp_store
        return [c for c in mcp_store.resolved(enabled_only=True) if c.get("connector_id") in CONNECTORS]
    except Exception as e:      # noqa: BLE001
        print(f"[pancake-inbox] đọc kết nối lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def pages(force: bool = False) -> List[dict]:
    """[{id, token, ten, conn_id, perm}] mọi Page của mọi kết nối Pancake đang bật, bỏ trùng theo page_id."""
    if not force and time.time() - float(_DS["ts"]) < DS_TTL:
        return list(_DS["pages"])
    import pancake_chat_mcp as pk
    out, thay = [], set()
    for c in _ket_noi():
        for p in pk.doc_pages((c.get("secrets") or {}).get("pages")):
            if p["id"] in thay:
                continue
            thay.add(p["id"])
            out.append(dict(p, conn_id=c.get("id") or "", perm=c.get("perm") or ""))
    _DS.update(ts=time.time(), pages=out)
    return list(out)


def page(page_id: str) -> Optional[dict]:
    pid = str(page_id or "")
    return next((p for p in pages() if p["id"] == pid), None)


_CH: dict = {"ts": 0.0, "v": {}}


def _cau_hinh() -> dict:
    # Giữ 2 giây: danh sách Hộp thư hỏi "Page này tự trả lời chưa" cho từng dòng.
    if time.time() - float(_CH["ts"]) < 2:
        return _CH["v"]
    ht = cfgmod.read_settings().get("conversations") or {}
    pk = ht.get("pancake") if isinstance(ht, dict) else None
    _CH.update(ts=time.time(), v=pk if isinstance(pk, dict) else {})
    return _CH["v"]


def _cua(page_id: str) -> dict:
    v = _cau_hinh().get(str(page_id))
    return v if isinstance(v, dict) else {}


def dang_theo_doi(page_id: str) -> bool:
    return bool(_cua(page_id).get("theo_doi"))


def tu_tra_loi(page_id: str) -> bool:
    """Chủ đã bật "A.I. tự trả lời" cho riêng Page này chưa. Mặc định KHÔNG."""
    return bool(_cua(page_id).get("tu_tra_loi"))


def _ghi_cau_hinh(page_id: str, **sua) -> dict:
    cfg = cfgmod.read_settings()
    ht = cfg.setdefault("conversations", {})
    if not isinstance(ht, dict):
        ht = cfg["conversations"] = {}
    pk = ht.setdefault("pancake", {})
    if not isinstance(pk, dict):
        pk = ht["pancake"] = {}
    cu = pk.get(str(page_id)) if isinstance(pk.get(str(page_id)), dict) else {}
    cu.update(sua)
    pk[str(page_id)] = cu
    cfgmod.write_settings(cfg)
    _CH["ts"] = 0.0
    return cu


def bat(page_id: str, on: bool) -> dict:
    """Bật/tắt đưa tin của một Page vào Hộp thư. Bật lại là bắt đầu từ BÂY GIỜ (mốc mới)."""
    pid = str(page_id or "").strip()
    if not page(pid):
        return {"ok": False, "error": "Không có Page Pancake nào id đó trong kết nối Thống kê Pancake đang bật."}
    if on:
        _ghi_cau_hinh(pid, theo_doi=True, bat_tu=time.time())
        conversations.ghi_trang_thai(_khoa(pid, "seen"), "")
        _TT.pop(pid, None)
        start()
    else:
        _ghi_cau_hinh(pid, theo_doi=False)
    return {"ok": True, "id": pid, "theo_doi": bool(on)}


def dat_tu_tra_loi(page_id: str, on: bool, xac_nhan: bool = False) -> dict:
    """Bật/tắt A.I. tự trả lời cho MỘT Page. Bật cần `xac_nhan` (chủ đã đọc cảnh báo). Tắt thì cuộc chat đang ở
    "A.I. tự trả lời" của Page đó về lại "A.I. soạn, tôi duyệt" ngay."""
    pid = str(page_id or "").strip()
    if not page(pid):
        return {"ok": False, "error": "Không có Page Pancake nào id đó."}
    if on and not xac_nhan:
        return {"ok": False, "code": "can_xac_nhan", "error": CANH_BAO}
    _ghi_cau_hinh(pid, tu_tra_loi=bool(on))
    doi = 0
    for _ in range(0 if on else 100):
        ds = [c for c in conversations.danh_sach(account_id=f"{KENH}:{pid}", mode="ai",
                                                 limit=conversations.MAX_DANH_SACH) or []
              if str(c.get("mode") or "") == "ai"]
        if not ds:
            break
        for c in ds:
            conversations.dat_che_do(int(c["id"]), "draft")
            doi += 1
    return {"ok": True, "id": pid, "tu_tra_loi": bool(on), "doi_ve_nhap": doi}


CANH_BAO = ("Bật A.I. tự trả lời cho Page này thì A.I. gửi thẳng cho khách, không chờ duyệt. Nhân viên sale đang trả lời "
            "trong Pancake có thể trả lời cùng lúc, khách sẽ nhận hai câu. A.I. chỉ nhường khi thấy nhân viên đã nhắn trong "
            "cuộc chat đó. Bố chắc chắn muốn bật?")


def cho_che_do(page_id: str, mode: str) -> tuple:
    """(ok, lỗi): chế độ `mode` có được đặt cho một cuộc chat của Page này không."""
    if str(mode or "") == "ai" and not tu_tra_loi(page_id):
        return False, ("Page này chưa bật A.I. tự trả lời. Bật ở tab Kênh (có cảnh báo nhân viên Pancake cũng đang "
                       "trả lời), hoặc chọn A.I. soạn, tôi duyệt.")
    return True, ""


def tai_khoan() -> List[dict]:
    cfg = _cau_hinh()
    out = []
    for p in pages():
        c = cfg.get(p["id"]) if isinstance(cfg.get(p["id"]), dict) else {}
        tt = _TT.get(p["id"]) or {}
        out.append({
            "id": p["id"], "label": p.get("ten") or p["id"], "channel": KENH,
            "theo_doi": bool(c.get("theo_doi")), "tu_tra_loi": bool(c.get("tu_tra_loi")),
            "lan_cuoi": tt.get("lan_cuoi") or 0, "loi": tt.get("loi") or "", "so_tin": int(tt.get("so_tin") or 0),
            # Ảnh đại diện công khai của Fanpage (chỉ cần page_id, không token).
            "avatar": f"https://graph.facebook.com/{p['id']}/picture?type=square",
        })
    return out


def trang_thai() -> dict:
    return {"dang_chay": bool(_task and not _task.done()), "nhip": NHIP, "tai_khoan": tai_khoan()}


# ============================================================
# Chuẩn hoá dữ liệu Pancake
# ============================================================
def _khoa(pid: str, ten: str) -> str:
    return f"{KENH}:{pid}:{ten}"


def _ds(d: Any, *khoa) -> list:
    if isinstance(d, list):
        return d
    if not isinstance(d, dict):
        return []
    for k in khoa:
        v = d.get(k)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in khoa:
                if isinstance(v.get(k2), list):
                    return v[k2]
    return []


def ts_cua(v: Any) -> float:
    """Thời điểm Pancake -> epoch giây. Nhận số (giây hoặc mili giây) hoặc ISO 8601. ISO KHÔNG có múi giờ coi là UTC
    (cần đối chiếu với tài khoản thật). Hỏng thì 0."""
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)) or re.fullmatch(r"\d{9,14}(\.\d+)?", str(v).strip()):
        f = float(v)
        return f / 1000.0 if f > 1e12 else f
    s = str(v).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        try:
            d = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return 0.0
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def _bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_TU_DONG = re.compile(r"\b(botcake|chatbot|bot|pos|tu dong|auto ?reply|automation)\b")


def la_tu_dong(ten: str) -> bool:
    return bool(_TU_DONG.search(_bo_dau(ten)))


def _chu(m: dict) -> str:
    for k in ("original_message", "message", "text", "content"):
        v = m.get(k)
        if isinstance(v, str) and v.strip():
            v = re.sub(r"<br\s*/?>", "\n", v, flags=re.I)
            return html.unescape(re.sub(r"<[^>]+>", "", v)).strip()
    return ""


def _loai_va_media(m: dict) -> tuple:
    atts = m.get("attachments") if isinstance(m.get("attachments"), list) else []
    for a in atts:
        if not isinstance(a, dict):
            continue
        t = str(a.get("type") or a.get("mime_type") or "").lower()
        url = ""
        for k in ("url", "preview_url", "image_data", "src"):
            v = a.get(k)
            if isinstance(v, dict):
                v = v.get("url")
            if isinstance(v, str) and v.startswith("https://"):
                url = v
                break
        loai = ("image" if ("photo" in t or "image" in t) else "video" if "video" in t else
                "audio" if ("audio" in t or "voice" in t) else "sticker" if "sticker" in t else "file")
        return loai, url, str(a.get("name") or "")
    return "text", "", ""


def _from(m: dict) -> dict:
    f = m.get("from")
    return f if isinstance(f, dict) else {}


def nguoi_gui(m: dict, page_id: str) -> tuple:
    """("customer" | "page", id, tên). Phía page gồm MinMin, nhân viên và tin tự động."""
    f = _from(m)
    fid = str(f.get("id") or m.get("from_id") or "")
    phia_page = (fid == str(page_id)) or bool(m.get("is_page") or m.get("from_page")) or bool(f.get("admin_id"))
    if phia_page:
        ten = str(f.get("admin_name") or m.get("admin_name") or m.get("sender_name") or f.get("name") or "").strip()
        return "page", str(f.get("admin_id") or m.get("admin_id") or fid), ten
    return "customer", fid, str(f.get("name") or "").strip()


def thong_tin_hoi_thoai(c: dict, ten_the: Dict[str, str], ten_nv: Dict[str, str]) -> dict:
    """Khách, điện thoại, thẻ và nhân viên phụ trách của một hội thoại Pancake (đọc khoan dung, thiếu thì bỏ)."""
    kh = next((x for x in (c.get("customers") or []) if isinstance(x, dict)), None) or _from(c)
    sdt = ""
    for x in c.get("recent_phone_numbers") or []:
        v = x.get("phone_number") or x.get("captured") if isinstance(x, dict) else x
        if v:
            sdt = str(v)
            break
    the = []
    for t in c.get("tags") or []:
        tid = str(t.get("id") if isinstance(t, dict) else t)
        ten = (t.get("text") or t.get("name") if isinstance(t, dict) else "") or ten_the.get(tid) or ""
        if ten:
            the.append(str(ten)[:40])
    nv = []
    for u in c.get("current_assign_users") or c.get("assignees") or []:
        if isinstance(u, dict) and (u.get("name") or ten_nv.get(str(u.get("id")))):
            nv.append(str(u.get("name") or ten_nv.get(str(u.get("id")))))
    if not nv:
        for uid in c.get("assignee_ids") or []:
            if ten_nv.get(str(uid)):
                nv.append(ten_nv[str(uid)])
    return {"khach_id": str(kh.get("fb_id") or kh.get("psid") or kh.get("id") or ""),
            "khach_ten": str(kh.get("name") or "").strip(), "sdt": sdt, "the": the[:15], "nhan_vien": nv[:10]}


# ============================================================
# Tiếng vọng của câu MinMin gửi
# ============================================================
def _chuan(t: str) -> str:
    return " ".join(str(t or "").split())


def ghi_da_gui(page_id: str, cid: str, text: str) -> None:
    k = (str(page_id), str(cid))
    now = time.time()
    ds = [x for x in _DA_GUI.get(k, []) if now - x[0] < ECHO_TTL]
    ds.append((now, _chuan(text)))
    _DA_GUI[k] = ds[-20:]
    if len(_DA_GUI) > 1000:
        for kk in list(_DA_GUI)[:500]:
            _DA_GUI.pop(kk, None)


def ghi_ma_da_gui(mid: str) -> None:
    if mid:
        _MA_DA_GUI[str(mid)] = time.time()
        if len(_MA_DA_GUI) > 2000:
            for kk in sorted(_MA_DA_GUI, key=_MA_DA_GUI.get)[:1000]:
                _MA_DA_GUI.pop(kk, None)


def la_tieng_vong(page_id: str, cid: str, mid: str, text: str) -> bool:
    if mid and _MA_DA_GUI.pop(str(mid), None):
        return True
    k = (str(page_id), str(cid))
    now = time.time()
    ds = [x for x in _DA_GUI.get(k, []) if now - x[0] < ECHO_TTL]
    t = _chuan(text)
    for i, (_, g) in enumerate(ds):
        if t and g and (t == g or t.startswith(g[:80]) or g.startswith(t[:80])):
            del ds[i]
            _DA_GUI[k] = ds
            return True
    _DA_GUI[k] = ds
    return False


def _gan_ma_tieng_vong(pid: str, cid: str, mid: str, text: str) -> None:
    """Gắn mã tin Pancake vào dòng MinMin đã ghi (để lượt sau kho tự chặn trùng). Không gắn được thì nhớ mã vào sổ."""
    t = _chuan(text)
    for r in conversations.own_messages_without_id(KENH, pid, cid, time.time() - 6 * 3600, 20):
        g = _chuan(r.get("text"))
        if t and g and (t == g or t.startswith(g[:80]) or g.startswith(t[:80])):
            if conversations.set_message_id(int(r["id"]), mid):
                return
    _nho_ma(pid, mid)


def _ma_da_xu_ly(pid: str) -> list:
    try:
        v = json.loads(conversations.doc_trang_thai(_khoa(pid, "echo"), "[]") or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def _nho_ma(pid: str, mid: str) -> None:
    if not mid:
        return
    ds = _ma_da_xu_ly(pid)
    if mid not in ds:
        ds.append(mid)
    conversations.ghi_trang_thai(_khoa(pid, "echo"), json.dumps(ds[-500:]))


# ============================================================
# Gọi Pancake
# ============================================================
async def _goi(p: dict, method: str, version: str, path: str, params=None, body=None):
    import pancake_hoi_thoai as ph
    return await ph.request(p, method, version, path, params or {}, body)


async def _bang_ten(p: dict) -> dict:
    """Tên thẻ và tên nhân viên của Page (giữ TEN_TTL giây; hỏng thì giữ bảng cũ)."""
    cu = _TEN.get(p["id"]) or {}
    if cu and time.time() - float(cu.get("ts") or 0) < TEN_TTL:
        return cu
    bang = {"ts": time.time(), "tags": dict(cu.get("tags") or {}), "users": dict(cu.get("users") or {})}
    try:
        d = await _goi(p, "GET", "v1", "/tags")
        for t in _ds(d, "tags", "data"):
            if isinstance(t, dict) and t.get("id") is not None:
                bang["tags"][str(t["id"])] = str(t.get("text") or t.get("name") or "")
    except Exception as e:      # noqa: BLE001
        print(f"[pancake-inbox {p['id']}] đọc thẻ: {type(e).__name__}", file=sys.stderr)
    try:
        d = await _goi(p, "GET", "v1", "/users")
        for u in _ds(d, "users", "data"):
            if isinstance(u, dict) and u.get("id") is not None:
                bang["users"][str(u["id"])] = str(u.get("name") or u.get("fb_name") or "")
    except Exception as e:      # noqa: BLE001
        print(f"[pancake-inbox {p['id']}] đọc nhân viên: {type(e).__name__}", file=sys.stderr)
    _TEN[p["id"]] = bang
    return bang


# ============================================================
# Một lượt đọc
# ============================================================
def _da_thay(pid: str) -> Optional[dict]:
    raw = conversations.doc_trang_thai(_khoa(pid, "seen"), "")
    if not raw:
        return None
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else None
    except ValueError:
        return None


async def doc_mot_lan(p: dict) -> dict:
    """Một lượt cho một Page. Trả {"moi", "trung", "hoi_thoai"} hoặc ném lỗi (giấu token ở tầng request)."""
    pid = p["id"]
    tt = _TT.setdefault(pid, {})
    bat_tu = float(_cua(pid).get("bat_tu") or 0) or time.time()
    now = time.time()
    seen = _da_thay(pid)
    lan_dau = seen is None
    seen = seen or {}
    since = int(max(bat_tu, float(tt.get("ok_luc") or bat_tu)) - CHONG_LAP)
    d = await _goi(p, "GET", "v2", "/conversations",
                   {"type": "INBOX", "order_by": "updated_at", "since": since, "until": int(now) + 60})
    ds = [c for c in _ds(d, "conversations", "data") if isinstance(c, dict) and c.get("id")]
    doi = []
    for c in ds:
        cid, up = str(c["id"]), str(c.get("updated_at") or "")
        if lan_dau:
            seen[cid] = up          # lần đầu: chỉ ghi mốc, không kéo lịch sử
        elif seen.get(cid) != up:
            doi.append(c)
    moi = trung = 0
    xong = []
    if doi:
        ten = await _bang_ten(p)
        # Cũ trước, mới sau: một lượt bị cắt ở TOI_DA_HOI_THOAI thì lượt sau đọc tiếp phần mới hơn.
        doi.sort(key=lambda c: str(c.get("updated_at") or ""))
        for c in doi[:TOI_DA_HOI_THOAI]:
            kq = await dong_bo_hoi_thoai(p, c, ten, bat_tu)
            moi += kq["moi"]
            trung += kq["trung"]
            seen[str(c["id"])] = str(c.get("updated_at") or "")
            xong.append(str(c["id"]))
    if len(seen) > NHO_HOI_THOAI:
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1])[-NHO_HOI_THOAI:])
    conversations.ghi_trang_thai(_khoa(pid, "seen"), json.dumps(seen))
    if len(doi) <= TOI_DA_HOI_THOAI:
        tt["ok_luc"] = now
    tt.update(lan_cuoi=time.time(), loi="", so_tin=int(tt.get("so_tin") or 0) + moi)
    return {"moi": moi, "trung": trung, "hoi_thoai": len(xong)}


async def dong_bo_hoi_thoai(p: dict, c: dict, ten: dict, bat_tu: float) -> dict:
    """Đọc khúc tin mới nhất của MỘT hội thoại và đổ vào kho."""
    import pancake_hoi_thoai as ph
    pid, cid = p["id"], str(c["id"])
    d = await _goi(p, "GET", "v1", f"/conversations/{ph.ident(cid)}/messages")
    tin = [m for m in _ds(d, "messages", "data") if isinstance(m, dict)]
    tin.sort(key=lambda m: (ts_cua(m.get("inserted_at") or m.get("created_at")), str(m.get("id") or "")))
    info = thong_tin_hoi_thoai(c, ten.get("tags") or {}, ten.get("users") or {})
    da_xu_ly = set(_ma_da_xu_ly(pid))
    moi = trung = 0
    conv_id = 0
    khach_moi: List[dict] = []      # tin khách mới (sau tin phía page cuối cùng) để gọi A.I. soạn
    nv_moi = ""                     # tên nhân viên vừa nhắn tay trong Pancake
    now = time.time()
    for m in tin:
        mid = str(m.get("id") or "")
        if mid and mid in da_xu_ly:
            trung += 1
            continue
        ai_gui, uid, ten_gui = nguoi_gui(m, pid)
        text = _chu(m)
        loai, url, ten_tep = _loai_va_media(m)
        if loai != "text" and not text:
            text = f"[Pancake: khách gửi {loai}]" if ai_gui == "customer" else f"[{loai}]"
        ts = ts_cua(m.get("inserted_at") or m.get("created_at")) or now
        ts = min(ts, now + 5)
        cu = ts < bat_tu - 60
        if ai_gui == "page" and la_tieng_vong(pid, cid, mid, text):
            _gan_ma_tieng_vong(pid, cid, mid, text)
            trung += 1
            continue
        if ai_gui == "customer":
            sender_type, sender_name = "customer", ten_gui or info["khach_ten"]
        elif la_tu_dong(ten_gui):
            sender_type, sender_name = "system", ten_gui or "Tự động"
        else:
            sender_type, sender_name = "human", (f"{ten_gui} (Pancake)" if ten_gui else "Nhân viên (Pancake)")
        md = {"pancake": True}
        if url:
            md["image_url" if loai == "image" else "url"] = url
        if ten_tep:
            md["fileName"] = ten_tep
        r = conversations.ghi_su_kien({
            "channel": KENH, "account_id": pid, "account_name": p.get("ten") or pid,
            "external_chat_id": cid, "chat_type": "private",
            "sender_type": sender_type, "sender_id": (uid or info["khach_id"]) if sender_type == "customer" else "",
            "sender_name": sender_name, "message_type": loai, "text": text,
            "external_message_id": mid, "created_at": ts, "metadata": md,
        }, dem_chua_doc=not cu)
        if not r.get("ok"):
            continue
        conv_id = int(r.get("conversation_id") or conv_id)
        if r.get("trung"):
            trung += 1
            continue
        moi += 1
        if cu:
            continue
        if sender_type == "customer":
            khach_moi.append({"text": text, "id": mid, "ts": ts, "sender_id": uid or info["khach_id"],
                              "sender_name": sender_name, "loai": loai, "url": url})
        elif sender_type == "human":
            nv_moi = sender_name
            khach_moi = []          # nhân viên đã trả lời những tin khách trước đó
    if not conv_id:
        conv_id = conversations.conversation_id_of(KENH, pid, cid)
    if conv_id:
        _cap_nhat_thong_tin(conv_id, pid, info)
        if nv_moi:
            nhan_vien_dang_xu_ly(conv_id)
        elif str((conversations.chi_tiet(conv_id) or {}).get("mode") or "") == "ai" and not tu_tra_loi(pid):
            # Mặc định an toàn: Page chưa bật tự trả lời thì cuộc chat ở "A.I. soạn, tôi duyệt".
            conversations.dat_che_do(conv_id, "draft")
        if khach_moi and now - float(khach_moi[-1]["ts"]) < TUOI_GOI_AI:
            _giao_cho_bot(pid, cid, khach_moi)
    return {"moi": moi, "trung": trung}


def nhan_vien_dang_xu_ly(conv_id: int) -> None:
    """Nhân viên vừa nhắn trong Pancake: cuộc chat thành "Bạn đang xử lý", A.I. nhường, nháp cũ không còn đúng."""
    c = conversations.chi_tiet(conv_id) or {}
    if str(c.get("mode") or "ai") in ("ai", "draft", "waiting"):
        conversations.dat_che_do(conv_id, "human")
    if conversations.draft_of(c):
        d = conversations.draft_of(c) or {}
        # Nháp đang gửi dở thì để nguyên: chủ cần thấy kết quả chưa rõ để tự kiểm tra.
        if d.get("delivery") not in ("sending", "uncertain"):
            conversations.clear_draft(conv_id)


def _cap_nhat_thong_tin(conv_id: int, pid: str, info: dict) -> None:
    c = conversations.chi_tiet(conv_id) or {}
    moi = {"the": info["the"], "nhan_vien": info["nhan_vien"], "sdt": info["sdt"]}
    if (c.get("metadata") or {}).get("pancake") != moi:
        conversations._set_meta_key(conv_id, "pancake", moi)
    if info["sdt"] and info["khach_id"]:
        try:
            conversations.gan_sdt_khach(KENH, pid, info["khach_id"], info["sdt"], info["khach_ten"])
        except Exception as e:      # noqa: BLE001
            print(f"[pancake-inbox] gắn số điện thoại: {type(e).__name__}", file=sys.stderr)


# ============================================================
# Bot (A.I. soạn / tự trả lời)
# ============================================================
def dang_ky_bot(page_id: str, tb: Any) -> None:
    _BOTS[str(page_id)] = tb
    start()


def huy_dang_ky_bot(page_id: str, tb: Any = None) -> None:
    if tb is None or _BOTS.get(str(page_id)) is tb:
        _BOTS.pop(str(page_id), None)


def _giao_cho_bot(pid: str, cid: str, evs: List[dict]) -> None:
    tb = _BOTS.get(str(pid))
    if not tb:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    t = loop.create_task(tb.xu_ly(cid, evs))
    _VIEC.add(t)
    t.add_done_callback(_VIEC.discard)


# ============================================================
# Gửi (dùng chung cho chủ gõ tay, gửi nháp và A.I. tự trả lời)
# ============================================================
_LOI_24H = re.compile(r"(24|outside of allowed window|allowed window|ngoai khung|qua han|10903|2018278|551)", re.I)
CAU_24H = ("Đã quá 24 giờ kể từ tin cuối của khách, Facebook không cho Page nhắn tiếp. Nhân viên xử lý trong Pancake "
           "(ví dụ gửi tin có thẻ được phép) hoặc chờ khách nhắn lại.")
GIOI_HAN = 1900


def qua_24h(pid: str, cid: str, now: Optional[float] = None) -> bool:
    """Tin cuối của KHÁCH trong kho đã quá 24 giờ chưa. Không biết (chưa có tin khách) thì False: để Pancake quyết."""
    tin = conversations.tin_gan_day(KENH, pid, cid, 60)
    ts = max((float(m.get("created_at") or 0) for m in tin if m.get("sender_type") == "customer"), default=0.0)
    return bool(ts) and ((now or time.time()) - ts) > CUA_SO_FB


def _ma_tra_ve(d: Any) -> str:
    if not isinstance(d, dict):
        return ""
    for k in ("id", "message_id"):
        if d.get(k):
            return str(d[k])
    x = d.get("data") or d.get("message")
    return _ma_tra_ve(x) if isinstance(x, dict) else ""


def _quyen_gui(p: dict) -> str:
    """Lý do KHÔNG được gửi theo quyền chủ đã đặt, hoặc rỗng."""
    if p.get("perm") and p.get("perm") != "full":
        return ("Kết nối Thống kê Pancake đang ở mức chỉ đọc. Đổi sang Toàn quyền ở trang Kết nối thì MinMin mới gửi được "
                "tin vào Pancake.")
    try:
        import hanh_dong
        import mcp_hub
        ok, why = hanh_dong.cho_phep(mcp_hub._chinh_sach_loai_viec(), "nhan_tin")
        if not ok:
            return str(why or "Bố đang chặn loại việc nhắn tin.")
    except Exception:      # noqa: BLE001 - không đọc được chính sách thì không tự nới quyền
        pass
    return ""


async def gui(page_id: str, cid: str, text: str) -> tuple:
    """Gửi MỘT câu chữ vào hội thoại Pancake. (ok, lỗi). Không tự thử lại: kết quả chưa rõ để người gọi đánh dấu."""
    import pancake_hoi_thoai as ph
    from channels.zalo_personal import chia_tin
    p = page(page_id) or next((x for x in pages(force=True) if x["id"] == str(page_id)), None)
    if not p:
        return False, "Page này không còn trong kết nối Thống kê Pancake (hoặc kết nối đang tắt)."
    why = _quyen_gui(p)
    if why:
        return False, why
    if qua_24h(p["id"], cid):
        return False, CAU_24H
    manh = chia_tin(text, GIOI_HAN) or [str(text or "")]
    da = 0
    for m in manh:
        ghi_da_gui(p["id"], cid, m)     # nhớ TRƯỚC khi gửi: tiếng vọng có thể về ngay lượt đọc sau
        try:
            method, ver, path, q, body = ph.plan("pancake_send_message", {"conversation_id": cid, "message": m})
            d = await ph.request(p, method, ver, path, q, body)
        except Exception as e:      # noqa: BLE001
            loi = str(e)
            them = f" Đã gửi {da}/{len(manh)} phần trước lỗi." if da else ""
            if _LOI_24H.search(loi):
                return False, CAU_24H + them
            return False, (loi[:300] or "Pancake từ chối") + them
        ghi_ma_da_gui(_ma_tra_ve(d))
        da += 1
    return True, ""


# ============================================================
# Vòng đọc
# ============================================================
def bao_co_su_kien(page_id: str = "") -> bool:
    """Điểm nối webhook: có sự kiện tin nhắn của Page này, đọc ngay thay vì chờ nhịp. Trả True nếu Page đang bật."""
    pid = str(page_id or "")
    if pid and not (dang_theo_doi(pid) or pid in _BOTS):
        return False
    if pid:
        _GAP.add(pid)
        (_TT.get(pid) or {}).pop("nghi_toi", None)
    if _danh_thuc is not None:
        _danh_thuc.set()
    return True


async def mot_vong() -> None:
    cfg = _cau_hinh()
    bat_ids = {k for k, v in cfg.items() if isinstance(v, dict) and v.get("theo_doi")} | set(_BOTS)
    if not bat_ids:
        return
    for p in pages():
        if _stop or p["id"] not in bat_ids:
            continue
        tt = _TT.setdefault(p["id"], {})
        gap = p["id"] in _GAP
        _GAP.discard(p["id"])
        if not gap and (time.time() < float(tt.get("nghi_toi") or 0) or time.time() - float(tt.get("lan_cuoi") or 0) < NHIP - 1):
            continue
        try:
            await doc_mot_lan(p)
        except asyncio.CancelledError:
            raise
        except Exception as e:      # noqa: BLE001
            tt["loi"] = f"{type(e).__name__}: {e}"[:300]
            tt["nghi_toi"] = time.time() + NHIP_LOI
            print(f"[pancake-inbox {p.get('ten')}] {tt['loi']}", file=sys.stderr)


async def _vong() -> None:
    global _danh_thuc
    _danh_thuc = asyncio.Event()
    print("[pancake-inbox] vòng đọc bắt đầu", file=sys.stderr)
    while not _stop:
        try:
            await mot_vong()
        except asyncio.CancelledError:
            raise
        except Exception as e:      # noqa: BLE001
            print(f"[pancake-inbox vòng] {type(e).__name__}: {e}", file=sys.stderr)
        try:
            await asyncio.wait_for(_danh_thuc.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass
        _danh_thuc.clear()
    print("[pancake-inbox] vòng đọc dừng", file=sys.stderr)


def start() -> bool:
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
