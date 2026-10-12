"""Plugin bundled: việc trong NHÓM Zalo mà MCP chuẩn của zalo-agent-cli chưa phơi ra.

MCP 1.6.2 chỉ có đọc tin, tìm cuộc chat và gửi chữ. Nhưng CLI cùng gói có sẵn lệnh con
`group note-create`, `reminder create`, `poll create`, `group members` và `group members-info`.
Plugin này gọi đúng các lệnh đó với HOME trỏ vào phiên Zalo đã đăng nhập (cách đã dùng ở
plugin `zalo-image`), nên không quét QR lần hai và không viết lại giao thức.

Bảy tool (ba cái cuối thêm ở 26.10.146):
  - `zalo_group_note`   ghi chú của nhóm (có thể ghim)
  - `zalo_group_remind` nhắc việc của nhóm, giờ hiểu theo GIỜ VIỆT NAM (CLI hiểu theo múi giờ
                        máy chủ, nên đổi ở đây, nếu không "9h sáng" thành 16h)
  - `zalo_group_poll`   bình chọn trong nhóm
  - `zalo_group_find_member` tìm thành viên theo tên để lấy ID thật mà tag. Chỉ ĐỌC.

  - `zalo_group_list`    liệt kê nhóm đang tham gia (lọc theo tên). Chỉ ĐỌC.
  - `zalo_group_pending` xem người đang xin vào nhóm (cần là quản trị viên). Chỉ ĐỌC.
  - `zalo_group_decide`  DUYỆT hoặc TỪ CHỐI người xin vào nhóm (hành động thật, min_mode full).

Ba tool đầu là hành động thật trước mặt cả nhóm nên `min_mode: full`.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Optional

CONNECTOR_ID = "zalo"
_CLI_PACKAGE = "zalo-agent-cli@1.6.2"
_TIMEOUT = 60
_MAX_OPTIONS = 10
_LAP = {"none", "daily", "weekly", "monthly"}


def _ket_noi_zalo():
    try:
        import mcp_store
    except Exception:
        return []
    out = []
    for c in mcp_store.resolved(enabled_only=True):
        if c.get("connector_id") != CONNECTOR_ID:
            continue
        env = c.get("env") or {}
        home = env.get("HOME") or env.get("USERPROFILE") or ""
        if home:
            out.append({"id": c["id"], "label": c.get("label") or "Zalo", "home": home})
    return out


def _check():
    if not shutil.which("npx"):
        return "Máy chạy MinMin chưa có Node.js 20+ (lệnh npx) nên chưa dùng được công cụ nhóm Zalo."
    if not _ket_noi_zalo():
        return ("Chưa đấu tài khoản Zalo nào. Vào trang Kết nối, chọn 'Zalo Agent MCP' và quét QR "
                "rồi gọi lại.")
    return None


def _chon(args) -> tuple:
    conns = _ket_noi_zalo()
    cid = str((args or {}).get("connection_id") or "").strip()
    if cid:
        chon = [c for c in conns if c["id"] == cid]
        return (chon[0], None) if chon else (None, f"không có kết nối Zalo nào id '{cid}'.")
    if len(conns) == 1:
        return conns[0], None
    ds = "; ".join(f"{c['label']} (id={c['id']})" for c in conns)
    return None, f"đang có {len(conns)} tài khoản Zalo, hãy nêu rõ connection_id. Danh sách: {ds}"


def _van_ban(v, toi_da: int) -> str:
    """Chữ người dùng đưa vào làm ĐỐI SỐ dòng lệnh: bỏ gạch đầu để "--pin" gõ trong tiêu đề
    không bị CLI hiểu thành cờ."""
    return str(v or "").strip().lstrip("-").strip()[:toi_da]


def _dung_so(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


async def _cli(home: str, *dong_lenh: str):
    npx = shutil.which("npx")
    argv = [npx, "-y", _CLI_PACKAGE, "--json", *[str(x) for x in dong_lenh]]
    if npx.lower().endswith((".cmd", ".bat")):
        argv = ["cmd.exe", "/c"] + argv
    env = dict(os.environ)
    env["HOME"] = home
    env["USERPROFILE"] = home
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL, env=env, **kwargs)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return None, "", f"quá {_TIMEOUT} giây chưa xong"
    dec = lambda b: (b or b"").decode("utf-8", "replace")   # noqa: E731
    return proc.returncode, dec(out), dec(err)


def _loi_cli(rc, out, err) -> Optional[str]:
    if rc is None:
        return "ERROR: " + (err or "quá hạn")
    if rc != 0:
        return f"ERROR: zalo-agent-cli thoát mã {rc}. " + ((err or out or "").strip()[-400:])
    return None


def gio_cho_cli(thoi_gian: str) -> Optional[str]:
    """'YYYY-MM-DD HH:mm' (giờ Việt Nam) -> cùng thời điểm, viết theo giờ địa phương của máy chủ
    (thứ CLI hiểu). None nếu sai định dạng."""
    s = str(thoi_gian or "").strip().replace("T", " ")
    try:
        d = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    try:
        from zoneinfo import ZoneInfo
        d = d.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")).astimezone().replace(tzinfo=None)
    except Exception:
        pass    # không có dữ liệu múi giờ thì để nguyên, còn hơn từ chối
    return d.strftime("%Y-%m-%d %H:%M")


async def _note(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    gid, tieu_de = _dung_so(args.get("group_id")), _van_ban(args.get("title"), 500)
    if not gid or not tieu_de:
        return "ERROR: thiếu group_id hoặc title."
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    lenh = ["group", "note-create", gid, tieu_de] + (["--pin"] if args.get("pin") else [])
    rc, out, err = await _cli(c["home"], *lenh)
    return _loi_cli(rc, out, err) or json.dumps(
        {"ok": True, "group_id": gid, "title": tieu_de, "pinned": bool(args.get("pin"))}, ensure_ascii=False)


async def _remind(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    tid, tieu_de = _dung_so(args.get("thread_id")), _van_ban(args.get("title"), 300)
    if not tid or not tieu_de:
        return "ERROR: thiếu thread_id hoặc title."
    lap = str(args.get("repeat") or "none").lower()
    if lap not in _LAP:
        return "ERROR: repeat chỉ nhận none, daily, weekly, monthly."
    lenh = ["reminder", "create", tid, tieu_de, "-t", "1" if int(args.get("thread_type", 1)) == 1 else "0",
            "--repeat", lap]
    if args.get("time"):
        g = gio_cho_cli(args["time"])
        if not g:
            return 'ERROR: time phải dạng "YYYY-MM-DD HH:mm" theo giờ Việt Nam.'
        lenh += ["--time", g]
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    rc, out, err = await _cli(c["home"], *lenh)
    return _loi_cli(rc, out, err) or json.dumps(
        {"ok": True, "thread_id": tid, "title": tieu_de, "time": args.get("time") or "ngay bây giờ",
         "repeat": lap}, ensure_ascii=False)


async def _poll(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    gid, cau_hoi = _dung_so(args.get("group_id")), _van_ban(args.get("question"), 300)
    opts = [_van_ban(x, 200) for x in (args.get("options") or []) if _van_ban(x, 200)]
    if not gid or not cau_hoi:
        return "ERROR: thiếu group_id hoặc question."
    if not 2 <= len(opts) <= _MAX_OPTIONS:
        return f"ERROR: bình chọn cần từ 2 đến {_MAX_OPTIONS} lựa chọn."
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    lenh = ["poll", "create", gid, cau_hoi, *opts]
    if args.get("multi"):
        lenh.append("--multi")
    if args.get("expire_minutes"):
        lenh += ["--expire", str(int(args["expire_minutes"]))]
    rc, out, err = await _cli(c["home"], *lenh)
    return _loi_cli(rc, out, err) or json.dumps(
        {"ok": True, "group_id": gid, "question": cau_hoi, "options": opts}, ensure_ascii=False)


def _gom_nguoi(d, ra: dict):
    """Gom (id -> tên) từ JSON của `group members-info`, chấp nhận nhiều hình dạng."""
    if isinstance(d, dict):
        uid = d.get("userId") or d.get("uid") or d.get("id")
        ten = d.get("displayName") or d.get("zaloName") or d.get("name") or d.get("dName")
        if uid and ten:
            ra[str(uid)] = str(ten)
        for v in d.values():
            if isinstance(v, (dict, list)):
                _gom_nguoi(v, ra)
    elif isinstance(d, list):
        for v in d:
            _gom_nguoi(v, ra)


def _json_dau(text: str):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"[\[{].*[\]}]", text or "", re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except Exception:
            return None


async def _find(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    gid, ten = _dung_so(args.get("group_id")), str(args.get("name") or "").strip()
    if not gid or not ten:
        return "ERROR: thiếu group_id hoặc name."
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    rc, out, err = await _cli(c["home"], "group", "members", gid)
    e = _loi_cli(rc, out, err)
    if e:
        return e
    d = _json_dau(out)
    ids = list(d.keys()) if isinstance(d, dict) else [str(x) for x in (d or [])]
    ids = [_dung_so(x) for x in ids if _dung_so(x)][:300]
    bang: dict = {}
    for i in range(0, len(ids), 40):
        rc, out, err = await _cli(c["home"], "group", "members-info", *ids[i:i + 40])
        if rc == 0:
            _gom_nguoi(_json_dau(out), bang)
    import unicodedata
    chuan = lambda s: re.sub(r"\s+", " ", "".join(   # noqa: E731
        ch for ch in unicodedata.normalize("NFD", str(s).lower().replace("đ", "d"))
        if unicodedata.category(ch) != "Mn")).strip()
    q = chuan(ten)
    khop = [{"user_id": i, "name": n} for i, n in bang.items() if q and q in chuan(n)][:10]
    return json.dumps({"ok": True, "group_id": gid, "so_thanh_vien": len(ids),
                       "so_ten_doc_duoc": len(bang), "matches": khop,
                       "luu_y": "Nhiều kết quả = mơ hồ: HỎI LẠI người dùng, đừng đoán." if len(khop) > 1 else ""},
                      ensure_ascii=False)


def _rut(text: str, toi_da: int = 6000) -> str:
    t = (text or "").strip()
    return t if len(t) <= toi_da else t[:toi_da] + f"\n(đã cắt, còn {len(t) - toi_da} ký tự)"


async def _list(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    lenh = ["group", "list"]
    q = _van_ban(args.get("query"), 100)
    if q:
        lenh += ["--query", q]
    rc, out, err = await _cli(c["home"], *lenh)
    return _loi_cli(rc, out, err) or _rut(out)


async def _pending(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    gid = _dung_so(args.get("group_id"))
    if not gid:
        return "ERROR: thiếu group_id."
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    rc, out, err = await _cli(c["home"], "group", "pending", gid)
    e = _loi_cli(rc, out, err)
    if e:
        return e
    return _rut(out) or json.dumps({"ok": True, "group_id": gid, "ghi_chu": "Không có ai đang chờ duyệt."},
                                   ensure_ascii=False)


async def _decide(args, ctx):
    loi = _check()
    if loi:
        return "ERROR: " + loi
    gid = _dung_so(args.get("group_id"))
    quyet = str(args.get("action") or "").strip().lower()
    ids = [_dung_so(x) for x in (args.get("user_ids") or []) if _dung_so(x)][:50]
    if not gid or not ids:
        return "ERROR: thiếu group_id hoặc user_ids (lấy từ zalo_group_pending)."
    if quyet not in ("approve", "reject"):
        return "ERROR: action chỉ nhận approve hoặc reject."
    c, why = _chon(args)
    if why:
        return "ERROR: " + why
    lenh = ["group", "approve" if quyet == "approve" else "reject-member", gid, *ids]
    rc, out, err = await _cli(c["home"], *lenh)
    return _loi_cli(rc, out, err) or json.dumps(
        {"ok": True, "group_id": gid, "action": quyet, "user_ids": ids}, ensure_ascii=False)


def register(ctx):
    chung = {"connection_id": {"type": "string", "description": "id kết nối Zalo, chỉ cần khi có nhiều tài khoản"}}
    ctx.register_tool(
        name="zalo_group_note",
        description="Tạo GHI CHÚ trong nhóm Zalo (có thể ghim). Hiện cho cả nhóm thấy. Cần group_id (zalo_search_threads) và title.",
        handler=_note, min_mode="full", check_fn=_check,
        schema={"type": "object", "properties": {
            "group_id": {"type": "string"}, "title": {"type": "string", "description": "Nội dung ghi chú"},
            "pin": {"type": "boolean", "description": "Ghim ghi chú lên đầu nhóm"}, **chung},
            "required": ["group_id", "title"]})
    ctx.register_tool(
        name="zalo_group_remind",
        description=("Tạo NHẮC VIỆC trong nhóm Zalo. time theo giờ Việt Nam dạng \"YYYY-MM-DD HH:mm\" "
                     "(bỏ trống = ngay bây giờ); repeat: none/daily/weekly/monthly."),
        handler=_remind, min_mode="full", check_fn=_check,
        schema={"type": "object", "properties": {
            "thread_id": {"type": "string"}, "title": {"type": "string"}, "time": {"type": "string"},
            "repeat": {"type": "string", "enum": sorted(_LAP)},
            "thread_type": {"type": "integer", "enum": [0, 1], "description": "1 = nhóm (mặc định)"}, **chung},
            "required": ["thread_id", "title"]})
    ctx.register_tool(
        name="zalo_group_poll",
        description=f"Tạo BÌNH CHỌN trong nhóm Zalo: question và từ 2 đến {_MAX_OPTIONS} options.",
        handler=_poll, min_mode="full", check_fn=_check,
        schema={"type": "object", "properties": {
            "group_id": {"type": "string"}, "question": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "multi": {"type": "boolean", "description": "Cho chọn nhiều đáp án"},
            "expire_minutes": {"type": "integer", "description": "Tự đóng sau N phút"}, **chung},
            "required": ["group_id", "question", "options"]})
    ctx.register_tool(
        name="zalo_group_find_member",
        description=("Tìm THÀNH VIÊN của nhóm Zalo theo tên (không dấu cũng được) để lấy user_id thật khi cần "
                     "tag. Một kết quả: dùng được. Nhiều kết quả: hỏi lại người dùng, không đoán."),
        handler=_find, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "group_id": {"type": "string"}, "name": {"type": "string"}, **chung},
            "required": ["group_id", "name"]})
    ctx.register_tool(
        name="zalo_group_list",
        description="Liệt kê các nhóm Zalo tài khoản đang tham gia (tên, số thành viên, group_id). query lọc theo tên, không cần dấu.",
        handler=_list, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {"query": {"type": "string"}, **chung}})
    ctx.register_tool(
        name="zalo_group_pending",
        description="Xem NGƯỜI ĐANG XIN VÀO nhóm Zalo (chờ duyệt). Chỉ quản trị viên nhóm mới xem được. Cần group_id.",
        handler=_pending, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {"group_id": {"type": "string"}, **chung},
                "required": ["group_id"]})
    ctx.register_tool(
        name="zalo_group_decide",
        description=("DUYỆT (approve) hoặc TỪ CHỐI (reject) người xin vào nhóm Zalo. user_ids lấy từ "
                     "zalo_group_pending. Chỉ làm khi người dùng đã nói rõ duyệt ai, từ chối ai."),
        handler=_decide, min_mode="full", check_fn=_check,
        schema={"type": "object", "properties": {
            "group_id": {"type": "string"}, "action": {"type": "string", "enum": ["approve", "reject"]},
            "user_ids": {"type": "array", "items": {"type": "string"}}, **chung},
            "required": ["group_id", "action", "user_ids"]})
