"""Bot nhìn ảnh khách gửi bằng chính model đang chạy nó (26.10.68).

Ảnh đi thẳng vào tin user của lượt đó. Model không nhận ảnh thì chạy lại bằng chữ có nhãn "không
xem được ảnh" để khách vẫn có câu trả lời. Lịch sử chỉ giữ chữ, không ôm base64.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import types

import bot_anh
import chatbot_runtime as cr
import main

DATA = "data:image/png;base64,QUJD"


def test_chuyen_doi_openai_anthropic_responses():
    c = bot_anh.noi_dung_co_anh("giá bao nhiêu", DATA)
    assert bot_anh.co_anh(c) and bot_anh.chi_chu(c) == "giá bao nhiêu"
    a = bot_anh.sang_anthropic(c)
    assert a[0] == {"type": "text", "text": "giá bao nhiêu"}
    assert a[1] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}}
    assert bot_anh.sang_anthropic("chữ thường") == "chữ thường"
    r = bot_anh.sang_responses(c)
    assert r == [{"type": "input_text", "text": "giá bao nhiêu"}, {"type": "input_image", "image_url": DATA}]


def test_codex_input_va_anthropic_giu_chu_cu_nguyen():
    import engine
    sys_, inp = engine._codex_input([{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}])
    assert inp == [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]
    _, inp2 = engine._codex_input([{"role": "user", "content": bot_anh.noi_dung_co_anh("x", DATA)}])
    assert inp2[0]["content"][1]["type"] == "input_image"


def _chay_bot_tra_loi(monkeypatch, kich_ban, anh):
    goi = []

    def fake_stream(prov, key, model, messages, reasoning="off"):
        goi.append(messages)

        async def gen():
            kq = kich_ban(len(goi), messages)
            if kq is None:
                yield {"type": "error", "content": "HTTP 400 model does not support images"}
            else:
                yield {"type": "text", "content": kq}
        return gen()

    monkeypatch.setattr(main, "_api_stream", fake_stream)

    async def prog(s):
        return None

    sess = {}
    out = asyncio.run(main._bot_tra_loi("giá cái này?", sess=sess, sysprompt="S", prov="openai", api_key="k",
                                        api_model="m", reasoning="off", progress=prog, runtime_trace=None,
                                        anh=anh))
    return out, goi, sess


def test_anh_vao_tin_user_cua_luot_do_va_lich_su_chi_giu_chu(monkeypatch):
    out, goi, sess = _chay_bot_tra_loi(monkeypatch, lambda n, m: "Dạ 100k ạ",
                                       {"data_url": DATA, "text_du_phong": "(không xem được ảnh) giá cái này?"})
    assert out["text"] == "Dạ 100k ạ" and len(goi) == 1
    cuoi = goi[0][-1]
    assert bot_anh.co_anh(cuoi["content"])
    assert all(isinstance(m["content"], str) for m in sess["bot"]), "lịch sử không được ôm ảnh"


def test_model_tu_choi_anh_thi_chay_lai_bang_chu(monkeypatch):
    out, goi, sess = _chay_bot_tra_loi(monkeypatch, lambda n, m: None if n == 1 else "Dạ em chưa xem được ảnh ạ",
                                       {"data_url": DATA, "text_du_phong": "(không xem được ảnh) giá cái này?"})
    assert out["text"].startswith("Dạ em chưa")
    assert len(goi) == 2 and bot_anh.co_anh(goi[0][-1]["content"])
    assert goi[1][-1]["content"] == "(không xem được ảnh) giá cái này?"
    assert sess["bot"][-2]["content"] == "(không xem được ảnh) giá cái này?"


def test_khong_anh_thi_hanh_vi_cu(monkeypatch):
    out, goi, sess = _chay_bot_tra_loi(monkeypatch, lambda n, m: "ok", None)
    assert out["text"] == "ok" and len(goi) == 1 and goi[0][-1]["content"] == "giá cái này?"


def test_anh_cho_bot_dua_thang_khi_engine_nhan_anh(monkeypatch, tmp_path):
    import image_vision as iv

    async def fake_fetch(url, dest, stem, max_bytes=0):
        dest.mkdir(parents=True, exist_ok=True)
        f = dest / (stem + ".png")
        f.write_bytes(b"\x89PNG\r\n\x1a\nxx")
        return f, ""

    monkeypatch.setattr(iv, "fetch_image", fake_fetch)
    monkeypatch.setattr(iv, "connected", lambda: False)    # KHÔNG cần ChatGPT
    monkeypatch.setattr(cr, "_deps", {"brain_root": lambda b: str(tmp_path), "engine_anh": lambda bot: "openai"})
    meta = {"co_anh": True, "image_url": "https://cdn.example/a.png", "chat_id": "C", "message_id": "m1"}
    cfg = {"brain": "brain", "muc_quyen": "suggest"}
    out = asyncio.run(cr.anh_cho_bot("cái này giá sao", meta, cfg))
    assert "đính kèm" in out and out.endswith("cái này giá sao")
    assert meta["_anh_goc"]["data_url"].startswith("data:image/png;base64,")
    assert cr._KEM_ANH in meta["_anh_goc"]["text_du_phong"]


def test_anh_cho_bot_engine_khong_nhan_anh_hoac_co_tool_thi_khong_dua_thang(monkeypatch, tmp_path):
    import image_vision as iv
    monkeypatch.setattr(iv, "connected", lambda: False)
    for prov, muc in (("grok-cli", "suggest"), ("anthropic-cli", "suggest"), ("openai", "auto")):
        monkeypatch.setattr(cr, "_deps", {"brain_root": lambda b: str(tmp_path), "engine_anh": lambda bot, p=prov: p})
        meta = {"co_anh": True, "image_url": "https://cdn.example/a.png", "chat_id": "C", "message_id": "m1"}
        out = asyncio.run(cr.anh_cho_bot("hi", meta, {"brain": "brain", "muc_quyen": muc}))
        assert "_anh_goc" not in meta
        assert out.startswith(cr._KEM_ANH)      # không ChatGPT thì nói thật là không xem được
