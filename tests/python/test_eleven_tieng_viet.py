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
print("ok")
