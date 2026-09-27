"""Plugin bundled: tool `javis_job` - lời dặn "xong thì làm tiếp", xem và dừng việc chạy nền.

Vì sao có tool này (0.64.66)
============================
Chủ repo báo 2026-09-27: Javis nói "Đang render nền, xong mình ghép tiếng và gửi video" rồi im,
video xong mà phải hỏi tới lần thứ ba mới biết. Máy chủ giờ TỰ nhận theo dõi mọi lệnh chạy ngầm
mà engine bỏ lại khi hết lượt (`server/tien_trinh_nen.py`), không cần model làm gì. Tool này chỉ
cho model nói thêm MỘT điều mà máy chủ không đoán được: xong rồi thì làm tiếp cái gì.

Tool KHÔNG chạy lệnh. Cấp quyền chạy shell cho engine API qua đường vòng này là mở ra đúng thứ
CLAUDE.md nói chúng không có. Engine có shell tự chạy lệnh ngầm như thường (`cmd > log 2>&1 &`),
còn việc theo dõi là của máy chủ.

Ba op:
- then: dặn việc cần làm khi việc chạy nền của lượt NÀY xong. Gọi trong cùng lượt đã bật lệnh
  ngầm. Nếu khung chat đã có việc đang được theo dõi (lượt trước), lời dặn gắn luôn vào việc đó.
- list: việc chạy nền gần đây của khung chat (đang chạy, xong, dừng).
- cancel: dừng một việc theo mã.
"""
from __future__ import annotations

import time

try:
    import tien_trinh_nen
except Exception:          # chạy ngoài máy chủ
    tien_trinh_nen = None
try:
    import luot_dang_chay
except Exception:
    luot_dang_chay = None

_TEN_TRANG_THAI = {"run": "đang chạy", "xong": "xong", "huy": "đã dừng",
                   "bo_theo_doi": "ngừng theo dõi (vẫn chạy)"}


def _chat(args, ctx) -> str:
    cid = str((args or {}).get("chat_id") or "").strip()
    if not cid and luot_dang_chay is not None and ctx.vault_root:
        try:
            cid = luot_dang_chay.doan_chat_id(ctx.vault_root) or ""
        except Exception:
            cid = ""
    return cid


def _then(args, ctx) -> str:
    text = str((args or {}).get("text") or "").strip()
    if not text:
        return "ERROR: thiếu text - nói rõ việc cần làm khi việc chạy nền xong."
    cid = _chat(args, ctx)
    if not cid:
        return ("ERROR: không xác định được khung chat đang hỏi, nên không có chỗ để làm tiếp. "
                "Truyền chat_id lấy từ khối KÊNH HỘI THOẠI HIỆN TẠI.")
    v = tien_trinh_nen.gan_loi_dan_cho_viec_dang_chay(cid, text)
    if v:
        return (f"Đã gắn lời dặn vào việc đang chạy {v['id']} (`{v.get('mo_ta', '')}`). Xong là Javis "
                "tự báo về khung chat này và làm tiếp đúng lời dặn.")
    tien_trinh_nen.dat_loi_dan(cid, text)
    return ("Đã ghi lời dặn. Hết lượt này, lệnh chạy ngầm nào của lượt còn sống sẽ được Javis theo "
            "dõi; xong là tự báo về khung chat này rồi mở một lượt mới để làm tiếp đúng lời dặn. "
            "Nếu hết lượt mà KHÔNG còn lệnh ngầm nào chạy thì lời dặn bị bỏ - hãy chắc lệnh đã "
            "được bật ngầm (vd `cmd > out.log 2>&1 &`) trước khi kết thúc lượt. Có thể nói với "
            "người dùng là kết quả sẽ tự về đây.")


def _list(args, ctx) -> str:
    cid = _chat(args, ctx)
    ds = tien_trinh_nen.gan_day(cid) if cid else tien_trinh_nen.dang_chay(brain_root=ctx.vault_root or "")
    if not ds:
        return "Không có việc chạy nền nào của khung chat này."
    now = time.time()
    dong = []
    for v in ds:
        tl = tien_trinh_nen.thoi_luong(float(v.get("ket_thuc") or now) - float(v.get("bat_dau") or now))
        dong.append(f"{v['id']} · {_TEN_TRANG_THAI.get(v.get('trang_thai'), v.get('trang_thai'))} · {tl} · "
                    f"{v.get('mo_ta', '')}" + (f" · làm tiếp: {v['sau_khi_xong']}" if v.get("sau_khi_xong") else ""))
    return "\n".join(dong)


def _cancel(args, ctx) -> str:
    jid = str((args or {}).get("id") or "").strip()
    if not jid:
        return "ERROR: thiếu id của việc cần dừng (xem op=list)."
    v = tien_trinh_nen.huy(jid)
    if not v:
        return f"Không có việc đang chạy nào mang mã {jid}."
    return f"Đã gửi lệnh dừng cho {jid} (`{v.get('mo_ta', '')}`). Javis sẽ báo khi nó dừng hẳn."


def _chay(args, ctx) -> str:
    if tien_trinh_nen is None:
        return "ERROR: bộ theo dõi việc chạy nền chưa sẵn sàng trên máy chủ này."
    if not tien_trinh_nen.POSIX:
        return ("ERROR: theo dõi việc chạy nền chưa hỗ trợ Windows. Hãy chạy lệnh trong lượt này "
                "(không chạy ngầm) để trả kết quả ngay, hoặc giao việc Kanban.")
    op = str((args or {}).get("op") or "").strip().lower()
    if op == "then":
        return _then(args, ctx)
    if op == "list":
        return _list(args, ctx)
    if op == "cancel":
        return _cancel(args, ctx)
    return "ERROR: op phải là then, list hoặc cancel."


def register(ctx):
    ctx.register_tool(
        "javis_job",
        "Việc chạy nền do chính bạn bật ngầm bằng shell (render video, build, tải file lớn). "
        "Hết lượt, Javis TỰ theo dõi mọi lệnh ngầm còn sống và báo về khung chat khi xong, "
        "bạn không cần hứa 'xong em báo'. "
        "op=then: dặn việc phải làm khi việc nền xong (vd 'ghép tiếng vào video, kiểm 8 khung "
        "hình, gửi file'); Javis sẽ mở một lượt mới để làm đúng việc đó. Gọi trong cùng lượt "
        "đã bật lệnh ngầm. op=list: xem việc chạy nền của khung chat. op=cancel id=...: dừng một "
        "việc. Tool này không chạy lệnh.",
        _chay,
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["then", "list", "cancel"]},
                "text": {"type": "string", "description": "Việc cần làm khi việc nền xong (op=then)"},
                "id": {"type": "string", "description": "Mã việc (op=cancel)"},
                "chat_id": {"type": "string", "description": "Khung chat, vd web:<mã phiên>; bỏ trống để tự nhận"},
            },
            "required": ["op"],
        },
        min_mode="safe",
        emoji="⏳",
    )
