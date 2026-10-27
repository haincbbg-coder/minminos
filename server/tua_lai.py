"""Nút Tua lại dưới câu hỏi trong khung chat (26.10.274).

Bố bấm Tua lại dưới một câu hỏi cũ: câu đó cùng mọi thứ bên dưới bị xoá, câu hỏi quay về ô gõ để sửa
rồi gửi lại, hội thoại đi tiếp từ chỗ đó. Bong bóng chỉ biết CHỮ bố gõ, còn bản lưu trên server có thể
kèm các khối ngữ cảnh dashboard chèn phía trước (file đang mở, file đính kèm, ngữ cảnh giao diện, skill).
Module này bóc các khối đó theo ĐÚNG luật `chuNguoiGo` của app.js rồi tìm câu hỏi đếm từ cuối lên.

Sau khi xoá, mạch native của mọi engine CLI (Claude Code resume id, Codex thread...) phải bỏ đi: mạch đó
vẫn nhớ các lượt vừa xoá, nối tiếp là model trả lời như thể chưa tua.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

# Cùng danh sách với _KHOI_NGU_CANH trong dashboard/app.js. Khối file đang mở neo ở phần đầu chung để
# nhận cả bản cũ ghi "của Javis" lẫn bản ghi "của MinMin".
KHOI_NGU_CANH = ("[FILE ĐANG MỞ trong trình sửa", "[File đính kèm", "[NGỮ CẢNH GIAO DIỆN:", "[SKILL: ", "[MỤC TIÊU:")


def chu_nguoi_go(text: Any) -> str:
    """Bóc tối đa 4 khối ngữ cảnh lồng nhau ở đầu tin, mỗi khối kết thúc bằng "]\\n\\n". Không thấy chỗ
    kết thúc thì giữ nguyên, thà thừa chữ còn hơn cắt mất câu hỏi."""
    s = "" if text is None else str(text)
    for _ in range(4):
        t = s.lstrip()
        if not t.startswith(KHOI_NGU_CANH):
            break
        i = t.find("]\n\n")
        if i < 0:
            break
        s = t[i + 3:]
    return s


def _gon(s: Any) -> str:
    return " ".join(str(s or "").split())


def tim_cau_hoi(msgs: Iterable[Dict[str, Any]], text: str, nth: int = 0) -> Optional[Dict[str, Any]]:
    """Tin người dùng mà nút Tua lại chỉ vào: đếm từ CUỐI lên, tin thứ nth+1 có chữ gõ BẰNG `text`
    (gộp khoảng trắng). So bằng chứ không "chứa": "ok" không được khớp nhầm "ok làm đi" phía sau,
    vì dashboard cũng đếm nth theo phép bằng."""
    can = _gon(text)
    if not can:
        return None
    con = max(0, int(nth or 0))
    for m in reversed(list(msgs)):
        if m.get("role") != "user" or _gon(chu_nguoi_go(m.get("content"))) != can:
            continue
        if con == 0:
            return m
        con -= 1
    return None


def tua_lai(store, session_id: str, text: str, nth: int = 0, huy_cho_chay_lai=None) -> Dict[str, Any]:
    """Xoá câu hỏi khớp và mọi tin sau nó, rồi dọn trạng thái engine. Trả dict kết quả cho route.

    - Bỏ tóm tắt nén nếu nó phủ cả lượt đã xoá (giữ khi nó chỉ phủ lượt còn lại).
    - Bỏ mạch native của MỌI engine CLI: lượt sau mở mạch mới, mồi từ phần hội thoại còn lại.
    - Đặt lại đồng hồ ngữ cảnh, huỷ lượt chờ chạy lại khi hết hạn mức (nó sẽ trả lời câu đã xoá).
    """
    tin = tim_cau_hoi(store.get_messages(session_id), text, nth)
    if not tin:
        return {"ok": False, "ly_do": "khong_thay"}
    da_xoa = store.cat_tu_tin(session_id, int(tin["id"]))
    con = [m for m in store.get_messages(session_id)
           if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()]
    phien = store.get_session(session_id) or {}
    if int(phien.get("compact_count") or 0) > len(con):
        store.set_compact(session_id, "", 0)
    mach = store.clear_native_threads(session_id)
    store.mark_thread_rotated(session_id)
    store.set_last_input_tokens(session_id, 0)
    if huy_cho_chay_lai:
        try:
            huy_cho_chay_lai(session_id)
        except Exception:
            pass
    return {"ok": True, "deleted": da_xoa, "remaining": store.count_messages(session_id), "threads": mach}


def register(app, get_store, dang_chay, huy_cho_chay_lai=None) -> None:
    """POST /sessions/{id}/rewind. Phụ thuộc vào main đi qua tham số để module không import main."""
    from fastapi import Form
    from fastapi.responses import JSONResponse

    @app.post("/sessions/{session_id}/rewind")
    async def sessions_rewind(session_id: str, text: str = Form(...), nth: int = Form(0)):
        st = get_store()
        if not st.get_session(session_id):
            return JSONResponse({"ok": False, "error": "Không có hội thoại này.", "ly_do": "khong_co_phien"},
                                status_code=404)
        if dang_chay(session_id):
            return JSONResponse({"ok": False, "error": "MinMin đang trả lời, bấm Dừng trước đã.",
                                 "ly_do": "dang_chay"}, status_code=409)
        kq = tua_lai(st, session_id, text, nth, huy_cho_chay_lai)
        if not kq.get("ok"):
            return JSONResponse({"ok": False, "error": "Không tìm thấy câu này trong hội thoại đã lưu.",
                                 "ly_do": "khong_thay"}, status_code=404)
        return kq
