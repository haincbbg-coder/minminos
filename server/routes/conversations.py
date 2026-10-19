"""Hộp thư hội thoại khách (Chatbot V2): đọc kho `conversations` cho trang Hội thoại.

Danh sách hội thoại, lịch sử tin, đánh dấu đã đọc, `mode` để người thật TIẾP QUẢN một cuộc
chat (bot im) và trả lại cho AI (phần chạy thật nằm ở `chatbot_runtime`, xem `che_do`), và từ
0.61.0 `reply`: chủ trả lời khách NGAY TỪ JAVIS qua năng lực gửi của kênh (sổ `channels`).

Kênh và tài khoản kênh có API riêng ở `routes/channels.py`; hai đường cũ
`/conversations/channels` và `/conversations/zalo/{id}/watch` giữ làm bí danh cho bookmark cũ.

Xác thực: như mọi route khác, đi qua `_auth_guard` của main.py (cookie phiên hoặc API token).
Không nhận `import main` - mọi thứ cần từ main đi qua `deps`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

import channel_accounts
import channels
import chatbot_store
import conversations
import routes.channels as channels_routes

router = APIRouter()


@dataclass
class ConversationsDeps:
    # Trạng thái sống của một bot (chatbot_runtime.status) - để mục Kênh nói bot đang chạy hay không.
    bot_status: Callable[[str], dict]


_DEPS: "ConversationsDeps" = None   # type: ignore


def _404(msg: str = "không có hội thoại nào id đó"):
    return JSONResponse({"ok": False, "error": msg}, status_code=404)


async def _gui_cho_khach(c: dict, txt: str):
    """Gửi một câu tới khách của hội thoại `c` qua kênh trong sổ. (ok, lỗi, raw account id)."""
    kenh = str(c.get("channel") or "")
    key = str(c.get("channel_account_id") or "")
    raw = key.split(":", 1)[1] if ":" in key else key
    s = channels.spec(kenh)
    if not s:
        return False, f"kênh '{kenh}' không có trong sổ đăng ký", raw
    tk = {"id": raw, "channel": kenh}
    if s.kind == "bot":
        a = channel_accounts.get_account(raw) or {}
        tk.update({k: a.get(k) for k in ("label", "external_id")})
        tk["token"] = channel_accounts.get_token(raw)
    ok, loi = await channels.gui(kenh, tk, str(c.get("external_chat_id") or ""), txt,
                                 str(c.get("chat_type") or "private"))
    return ok, loi, raw


_LOI_SOAN = {
    "khong_co_bot": "Cuộc chat này chưa gắn với bot nào nên không có ai để soạn câu trả lời.",
    "khong_co_tin_khach": "Chưa có tin nào của khách để trả lời.",
    "loi_engine": "Bộ não AI của bot đang lỗi hoặc không chạy được lượt này. Kiểm tra trang Bộ não AI.",
    "bot_chon_im": "Bot đọc tin này và chọn không trả lời (nó viết [IM_LANG]). Bố tự gõ câu trả lời ở ô bên dưới.",
    "gui_loi": "Soạn được câu trả lời nhưng gửi qua kênh bị lỗi.",
}


def _loi_soan(r: dict, status: int = 400):
    """Trả lỗi có CÂU TIẾNG VIỆT trong `error`: giao diện chỉ hiện trường đó, thiếu nó là chủ
    chỉ thấy "Lỗi 400" mà không biết bot im, bot hỏng hay chưa gắn bot."""
    r = dict(r)
    ct = str(r.get("chi_tiet") or "")
    r["error"] = _LOI_SOAN.get(r.get("ly_do"), "Không soạn được câu trả lời.") + (f" ({ct})" if ct else "")
    return JSONResponse(r, status_code=status)


def _tin_khach_cuoi(conv_id: int) -> dict:
    for m in reversed(conversations.tin_nhan(conv_id, limit=60)):
        if m.get("sender_type") == "customer" and str(m.get("text") or "").strip():
            return m
    return {}


def register(app, deps: ConversationsDeps):
    global _DEPS
    _DEPS = deps

    @router.post("/conversations/file-shelf/image")
    async def shelf_image(url: str = Form(...)):
        """Authenticated download of a Zalo image for the local editing shelf.

        Reuse the CDN allowlist/redirect checks and byte cap. Temporary files are
        removed before returning; never retain user URLs or fetch arbitrary hosts.
        """
        import asyncio
        import tempfile
        from pathlib import Path
        from fastapi.responses import Response
        import image_vision
        if not image_vision.url_allowed(url):
            return JSONResponse({"error": "Chỉ tải ảnh từ máy chủ ảnh Zalo."}, status_code=400)
        with tempfile.TemporaryDirectory(prefix="minmin-shelf-") as folder:
            try:
                path, error = await asyncio.wait_for(
                    image_vision.fetch_image(url, Path(folder), "image", max_bytes=20 * 1024 * 1024), 65)
            except asyncio.TimeoutError:
                return JSONResponse({"error": "Tải ảnh quá lâu. Thử lại sau."}, status_code=504)
            if not path:
                return JSONResponse({"error": error}, status_code=422)
            data = path.read_bytes()
            # Verify actual image bytes, not the remote content-type or filename.
            import io
            from PIL import Image
            try:
                with Image.open(io.BytesIO(data)) as im:
                    mime = Image.MIME.get(im.format, "")
                    if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                        raise ValueError("unsupported image")
                    im.verify()
            except Exception:
                return JSONResponse({"error": "File tải về không phải ảnh hợp lệ."}, status_code=422)
        return Response(data, media_type=mime, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @router.get("/conversations")
    async def conversations_list(channel: str = "", bot_id: str = "", account_id: str = "",
                                 q: str = "", mode: str = "", limit: int = 50, offset: int = 0):
        """Danh sách hội thoại mới nhất trước, kèm vài con số đầu trang (cùng bộ lọc)."""
        items = conversations.danh_sach(channel=channel, bot_id=bot_id, account_id=account_id,
                                        q=q, mode=mode, limit=limit, offset=offset)
        return {"ok": True, "items": items,
                "stats": conversations.thong_ke(bot_id=bot_id, channel=channel, account_id=account_id),
                "channels": channels.cho_giao_dien()}

    @router.get("/conversations/stats")
    async def conversations_stats(bot_id: str = "", channel: str = "", account_id: str = ""):
        return {"ok": True, "stats": conversations.thong_ke(bot_id=bot_id, channel=channel,
                                                              account_id=account_id)}

    @router.get("/conversations/channels")
    async def conversations_channels():
        """Bí danh của GET /channels/accounts (0.61.0): mọi tài khoản kênh, một khuôn."""
        return {"ok": True, "accounts": channels_routes._tai_khoan_thong_nhat(),
                "channels": channels.cho_giao_dien()}

    @router.post("/conversations/zalo/{conn_id}/watch")
    async def conversations_zalo_watch(conn_id: str, on: str = Form("1")):
        """Bí danh cũ của POST /channels/accounts/{id}/watch cho Zalo cá nhân."""
        m = channels.module("zalo_personal")
        if not m:
            return JSONResponse({"ok": False, "error": "kênh Zalo cá nhân chưa có trong sổ"}, status_code=400)
        r = m.bat(conn_id, str(on).strip().lower() in ("1", "true", "on", "yes"))
        return r if r.get("ok") else JSONResponse(r, status_code=400)

    @router.get("/conversations/{conv_id}")
    async def conversations_detail(conv_id: int):
        d = conversations.chi_tiet(conv_id)
        return {"ok": True, "conversation": d} if d else _404()

    @router.get("/conversations/{conv_id}/messages")
    async def conversations_messages(conv_id: int, limit: int = 100, before: int = 0, after: int = 0):
        """Tin của một hội thoại. `before` = cuộn lên xem tin cũ hơn, `after` = chỉ tin mới
        hơn (nhịp làm mới của Hộp thư). `giu_nhom` cho giao diện biết nhóm chỉ giữ bấy nhiêu tin."""
        d = conversations.chi_tiet(conv_id)
        if not d:
            return _404()
        return {"ok": True, "conversation": d, "giu_nhom": conversations.GIU_TIN_NHOM,
                "messages": conversations.tin_nhan(conv_id, limit=limit, before_id=before,
                                                   after_id=after)}

    @router.post("/conversations/{conv_id}/read")
    async def conversations_read(conv_id: int):
        return {"ok": True} if conversations.danh_dau_da_doc(conv_id) else _404()

    @router.post("/conversations/{conv_id}/reply")
    async def conversations_reply(conv_id: int, text: str = Form(...)):
        """Chủ trả lời khách ngay từ Hộp thư (Chatbot V2 bản V1.2).

        Gửi qua năng lực `gui` của kênh trong sổ đăng ký: bot Telegram/Zalo gửi bằng token của
        tài khoản, Zalo cá nhân gửi bằng MCP dưới danh tính chủ. Gửi được thì ghi vào kho như
        tin `human`, và nếu cuộc này có bot đang trực ở chế độ AI thì TIẾP QUẢN luôn (chuyển
        `human`): người vừa nhắn tay mà bot chen vào câu sau là khách đọc hai giọng một lúc.
        Trả `tiep_quan: true` để giao diện nói ra điều đó.
        """
        c = conversations.chi_tiet(conv_id)
        if not c:
            return _404()
        txt = str(text or "").strip()
        if not txt:
            return JSONResponse({"ok": False, "error": "tin rỗng"}, status_code=400)
        if len(txt) > conversations.MAX_CHU:
            return JSONResponse({"ok": False, "error": f"tin dài quá {conversations.MAX_CHU} ký tự"}, status_code=400)
        kenh = str(c.get("channel") or "")
        key = str(c.get("channel_account_id") or "")
        raw = key.split(":", 1)[1] if ":" in key else key
        s = channels.spec(kenh)
        if not s:
            return JSONResponse({"ok": False, "error": f"kênh '{kenh}' không có trong sổ đăng ký"}, status_code=400)
        tk = {"id": raw, "channel": kenh}
        if s.kind == "bot":
            a = channel_accounts.get_account(raw) or {}
            tk.update({k: a.get(k) for k in ("label", "external_id")})
            tk["token"] = channel_accounts.get_token(raw)
        ok, loi = await channels.gui(kenh, tk, str(c.get("external_chat_id") or ""), txt,
                                     str(c.get("chat_type") or "private"))
        if not ok:
            return JSONResponse({"ok": False, "error": loi or "không gửi được"}, status_code=400)
        r = conversations.ghi_su_kien({
            "channel": kenh, "account_id": raw, "account_name": c.get("account_name") or "",
            "bot_id": c.get("bot_id") or "",
            "external_chat_id": c.get("external_chat_id"), "chat_type": c.get("chat_type"),
            "chat_title": c.get("title") if c.get("chat_type") == "group" else "",
            "sender_type": "human", "sender_name": "Bạn", "message_type": "text", "text": txt,
            "metadata": {"tu_javis": True},
        })
        tiep_quan = False
        if c.get("bot_id") and str(c.get("mode") or "ai") == "ai":
            conversations.dat_che_do(conv_id, "human")
            tiep_quan = True
        return {"ok": True, "message_id": r.get("message_id"), "tiep_quan": tiep_quan,
                "conversation": conversations.chi_tiet(conv_id)}

    @router.post("/conversations/{conv_id}/goi-y")
    async def conversations_goi_y(conv_id: int):
        """Bot soạn NHÁP câu trả lời cho tin khách cuối. Không gửi gì: chủ đọc, sửa, tự gửi."""
        import chatbot_runtime
        c = conversations.chi_tiet(conv_id)
        if not c:
            return _404()
        tin = _tin_khach_cuoi(conv_id)
        r = await chatbot_runtime.soan_cau_tra_loi(c, tin)
        return r if r.get("ok") else _loi_soan(r)

    @router.post("/conversations/{conv_id}/tra-loi-giup")
    async def conversations_tra_loi_giup(conv_id: int):
        """Bot trả lời tin khách cuối NGAY, kể cả khi bộ phán xử đã chọn im. Gửi dưới vai bot
        và KHÔNG tiếp quản: đây vẫn là bot nói, chủ chỉ bấm hộ nó."""
        import chatbot_runtime
        c = conversations.chi_tiet(conv_id)
        if not c:
            return _404()
        r = await chatbot_runtime.soan_cau_tra_loi(c, _tin_khach_cuoi(conv_id))
        if not r.get("ok"):
            return _loi_soan(r)
        ok, loi, raw = await _gui_cho_khach(c, r["text"])
        if not ok:
            return _loi_soan({"ok": False, "ly_do": "gui_loi", "chi_tiet": loi or ""})
        conversations.ghi_su_kien({
            "channel": c.get("channel"), "account_id": raw, "account_name": c.get("account_name") or "",
            "bot_id": c.get("bot_id") or "", "external_chat_id": c.get("external_chat_id"),
            "chat_type": c.get("chat_type"),
            "chat_title": c.get("title") if c.get("chat_type") == "group" else "",
            "sender_type": "ai", "sender_name": "Bot", "message_type": "text", "text": r["text"],
            "metadata": {"tra_loi_giup": True},
        })
        return {"ok": True, "text": r["text"]}

    @router.get("/conversations/{conv_id}/phan-xu")
    async def conversations_phan_xu(conv_id: int):
        """Quyết định gần nhất của bộ phán xử ở cuộc chat này (để vẽ dòng "Bot im: lý do")."""
        import chatbot_phan_xu
        c = conversations.chi_tiet(conv_id)
        if not c:
            return _404()
        bid = str(c.get("bot_id") or "")
        cid = str(c.get("external_chat_id") or "")
        ds = [r for r in chatbot_phan_xu.nhat_ky(bid, 200) if r.get("chat_id") == cid][:5] if bid else []
        bot = chatbot_store.get_bot(bid) if bid else None
        rieng = c.get("chat_type") != "group" and bool(bot) and chatbot_store.pham_vi_rieng(bot) == "chon"
        cho = bool(bot) and cid in {str(x) for x in (bot.get("rieng_cho_phep") or [])}
        nk = [{"id": n["id"], "ten": n["ten"]} for n in ((bot or {}).get("nhom_khach") or [])]
        n_hien = chatbot_store.nhom_cua(bot, cid) if bot else None
        return {"ok": True, "items": ds, "bot_id": bid, "can_cho_phep": rieng, "da_cho_phep": cho,
                "nhom_khach": nk, "nhom_hien_tai": (n_hien or {}).get("id", "")}

    @router.post("/conversations/{conv_id}/nhom-khach")
    async def conversations_nhom_khach(conv_id: int, nhom_id: str = Form("")):
        """Xếp cuộc chat này vào một nhóm khách của bot (nhom_id rỗng = gỡ khỏi mọi nhóm).
        Mỗi cuộc chat chỉ ở MỘT nhóm: xếp vào nhóm mới là gỡ khỏi nhóm cũ."""
        c = conversations.chi_tiet(conv_id)
        if not c:
            return _404()
        bid = str(c.get("bot_id") or "")
        bot = chatbot_store.get_bot(bid) if bid else None
        if not bot:
            return JSONResponse({"ok": False, "error": "Cuộc chat này không thuộc bot nào."}, status_code=400)
        cid = str(c.get("external_chat_id") or "")
        ds = [dict(n) for n in (bot.get("nhom_khach") or [])]
        if nhom_id and not any(n["id"] == nhom_id for n in ds):
            return JSONResponse({"ok": False, "error": "Không có nhóm khách này."}, status_code=400)
        for n in ds:
            tv = [x for x in n.get("thanh_vien") or [] if str(x) != cid]
            if n["id"] == nhom_id:
                tv.append(cid)
            n["thanh_vien"] = tv
        ok, err = chatbot_store.update_bot(bid, {"nhom_khach": ds})
        if not ok:
            return JSONResponse({"ok": False, "error": err}, status_code=400)
        return {"ok": True, "nhom_hien_tai": nhom_id}

    @router.post("/conversations/{conv_id}/cho-phep")
    async def conversations_cho_phep(conv_id: int, bat: str = Form("1")):
        """Cho (hoặc thôi cho) bot trả lời cuộc chat RIÊNG này khi bot đang ở phạm vi 'chọn'."""
        c = conversations.chi_tiet(conv_id)
        if not c:
            return _404()
        bid = str(c.get("bot_id") or "")
        bot = chatbot_store.get_bot(bid) if bid else None
        if not bot:
            return JSONResponse({"ok": False, "error": "Cuộc chat này không thuộc bot nào."}, status_code=400)
        cid = str(c.get("external_chat_id") or "")
        ds = [str(x) for x in (bot.get("rieng_cho_phep") or [])]
        if str(bat) not in ("", "0", "false"):
            if cid not in ds:
                ds.append(cid)
        else:
            ds = [x for x in ds if x != cid]
        ok, err = chatbot_store.update_bot(bid, {"rieng_cho_phep": ds})
        if not ok:
            return JSONResponse({"ok": False, "error": err}, status_code=400)
        return {"ok": True, "da_cho_phep": str(bat) not in ("", "0", "false")}

    @router.post("/conversations/{conv_id}/mode")
    async def conversations_mode(conv_id: int, mode: str = Form(...)):
        """ai | human | waiting | closed. `human` = người thật tiếp quản, bot im ở cuộc chat đó."""
        ok, err = conversations.dat_che_do(conv_id, mode)
        if not ok:
            return JSONResponse({"ok": False, "error": err},
                                status_code=404 if "không có" in err else 400)
        return {"ok": True, "conversation": conversations.chi_tiet(conv_id)}

    app.include_router(router)
