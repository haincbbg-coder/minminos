"""ElevenLabs đọc tiếng Việt: câu có dấu phải đi model có tiếng Việt, không ra giọng tây."""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import tempfile

state = tempfile.mkdtemp(prefix="minmin-eleven-")
os.environ["JAVIS_STATE_DIR"] = state
import main  # noqa: E402

viet = "Hôm nay có 414 đơn mới, bố ạ."
anh = "Today we have 414 new orders."
f = main._eleven_model_cho
# Mặc định cũ (multilingual_v2 không có tiếng Việt) và Tự chọn -> Flash v2.5 + vi
assert f(viet, "eleven_multilingual_v2") == ("eleven_flash_v2_5", "vi")
assert f(viet, "auto") == ("eleven_flash_v2_5", "vi")
assert f(viet, "") == ("eleven_flash_v2_5", "vi")
# Câu tiếng Anh giữ model cũ, không ép ngôn ngữ
assert f(anh, "auto") == ("eleven_multilingual_v2", "")
assert f(anh, "eleven_multilingual_v2") == ("eleven_multilingual_v2", "")
# Người dùng chọn model có tiếng Việt thì giữ nguyên
assert f(viet, "eleven_v4_turbo") == ("eleven_v4_turbo", "")
assert f(viet, "eleven_v3") == ("eleven_v3", "")
assert f(viet, "eleven_flash_v2_5") == ("eleven_flash_v2_5", "vi")

# Gửi đúng payload lên ElevenLabs
sent = {}


class _Resp:
    content = b"mp3"

    def raise_for_status(self):
        pass


class _Client:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None, params=None):
        sent.update(url=url, json=json)
        return _Resp()


import httpx  # noqa: E402
_goc = httpx.AsyncClient
httpx.AsyncClient = _Client
try:
    cfg = {"voice": {"elevenlabs_key": "k", "elevenlabs_voice": "VOICEID", "elevenlabs_model": "eleven_multilingual_v2"}}
    assert asyncio.run(main._tts_elevenlabs(viet, cfg)) == b"mp3"
    assert sent["url"].endswith("/VOICEID")
    assert sent["json"] == {"text": viet, "model_id": "eleven_flash_v2_5", "language_code": "vi"}
finally:
    httpx.AsyncClient = _goc

# Lỗi ElevenLabs phải ra câu tiếng Việt nói rõ nguyên do (0.64.87), không phải câu chung chung
g = main._eleven_giai_thich
assert "gói Miễn phí" in g(401, {"detail": {"status": "detected_unusual_activity", "message": "Unusual activity"}})
assert "quyền Text to Speech" in g(401, {"detail": {"status": "missing_permissions"}})
assert "sai hoặc đã bị xóa" in g(401, {"detail": {"status": "invalid_api_key"}})
assert "sai hoặc đã bị xóa" in g(401, None)
assert "Thư viện" in g(402, {"detail": {"status": "paid_plan_required"}})
assert "Voice ID" in g(404, {"detail": {"status": "voice_not_found"}})
assert "hết số ký tự" in g(401, {"detail": {"status": "quota_exceeded"}})
assert g(500, {"detail": {"status": "boom", "message": "x" * 400}}).startswith("ElevenLabs báo lỗi 500: ")
assert len(g(500, {"detail": {"message": "x" * 400}})) < 200


class _RespLoi:
    status_code = 401

    def json(self):
        return {"detail": {"status": "detected_unusual_activity", "message": "Free Tier usage disabled"}}


class _ClientLoi(_Client):
    async def post(self, *a, **k):
        return _RespLoi()


httpx.AsyncClient = _ClientLoi
try:
    try:
        asyncio.run(main._tts_elevenlabs(viet, cfg))
        raise AssertionError("phải báo lỗi")
    except main._LoiGiong as e:
        assert "gói Miễn phí" in str(e)
    # /tts trả 502 kèm đúng câu giải thích
    from fastapi import HTTPException
    main.cfgmod.read_settings = lambda: {"voice": {"tts_provider": "elevenlabs", **cfg["voice"]}}
    try:
        asyncio.run(main.tts(text=viet, voice="x", rate="+0%"))
        raise AssertionError("phải 502")
    except HTTPException as e:
        assert e.status_code == 502 and "gói Miễn phí" in e.detail
finally:
    httpx.AsyncClient = _goc
print("ok")
