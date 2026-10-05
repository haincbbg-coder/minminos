"""THỬ BOT (26.10.68): hỏi thử một câu xem bot trả lời gì, chỉ đọc và không để lại dấu vết.

Điều phải giữ: ép mức Chỉ đọc cho lượt thử dù bot đang Toàn quyền, không ghi kho hội thoại
(`ghi_kho=False`), không ghi Hộp thư, không ghi nhật ký bot, không gửi gì ra kênh.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio

import chatbot_runtime
import chatbot_store


def _bot(muc="full"):
    return {"id": "b1", "slug": "b1", "name": "B", "brain": "brain", "muc_quyen": muc,
            "nguon_tra_loi": "agent", "account_ids": []}


def _chay(monkeypatch, tra_ve, muc="full"):
    ghi = {"answer": [], "log": [], "tin": []}
    monkeypatch.setattr(chatbot_store, "get_bot", lambda i: _bot(muc) if i == "b1" else None)
    monkeypatch.setattr(chatbot_store, "hieu_luc", lambda cfg, cid, ct: (cfg, {}))

    async def answer(text, meta, progress, channel="", bot=None, **kw):
        ghi["answer"].append({"bot": dict(bot), "kw": kw, "channel": channel, "text": text})
        return tra_ve

    monkeypatch.setattr(chatbot_runtime, "_deps", {"answer": answer, "brain_root": lambda b: "/khong/co"})
    monkeypatch.setattr(chatbot_runtime.chatbot_log, "ghi", lambda *a, **k: ghi["log"].append(a))
    monkeypatch.setattr(chatbot_runtime, "ghi_tin_khach", lambda *a, **k: ghi["tin"].append(a))
    monkeypatch.setattr(chatbot_runtime, "ghi_tin_bot", lambda *a, **k: ghi["tin"].append(a))
    return ghi


def test_thu_bot_ep_chi_doc_va_khong_ghi_gi(monkeypatch):
    ghi = _chay(monkeypatch, {"text": "Dạ giá 100k ạ", "files": []})
    r = asyncio.run(chatbot_runtime.thu_bot("b1", "giá bao nhiêu"))
    assert r["ok"] and r["text"] == "Dạ giá 100k ạ" and not r["im_lang"]
    goi = ghi["answer"][0]
    assert goi["bot"]["muc_quyen"] == "suggest", "lượt thử không được có tool dù bot đang Toàn quyền"
    assert goi["kw"].get("ghi_kho") is False
    assert goi["channel"] == "thu"
    assert ghi["log"] == [] and ghi["tin"] == []


def test_thu_bot_bot_chon_im(monkeypatch):
    _chay(monkeypatch, {"text": chatbot_runtime.IM_LANG, "files": []})
    r = asyncio.run(chatbot_runtime.thu_bot("b1", "alo"))
    assert r["ok"] and r["im_lang"] and r["text"] == ""


def test_thu_bot_loi_engine_va_dau_vao_xau(monkeypatch):
    _chay(monkeypatch, "engine hết lượt")
    r = asyncio.run(chatbot_runtime.thu_bot("b1", "hi"))
    assert not r["ok"] and r["ly_do"] == "loi_engine"
    assert asyncio.run(chatbot_runtime.thu_bot("b1", "  "))["ly_do"] == "khong_co_cau_hoi"
    assert asyncio.run(chatbot_runtime.thu_bot("khong-co", "hi"))["ly_do"] == "khong_co_bot"
