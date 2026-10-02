from _paths import ROOT, SERVER  # noqa
import asyncio
import json
import unittest
import voice_preview
import voice_live


class PreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_sample_once_no_audio_or_tools_and_cleanup(self):
        class Provider:
            def __init__(self):
                self.texts, self.offers, self.closed = [], [], False
            async def connect(self): pass
            async def close(self): self.closed = True
            async def start_webrtc(self, sdp):
                self.offers.append(sdp)
                return "answer"
            async def send_text(self, text): self.texts.append(text)
            async def events(self):
                yield {"type": "tool_call", "name": "ask_javis"}
                await asyncio.Event().wait()
        class Socket:
            def __init__(self): self.sent, self.closed = [], False
            async def send_json(self, data): self.sent.append(data)
            async def close(self): self.closed = True
            async def receive(self):
                await asyncio.sleep(0)
                return messages.pop(0)
        def msg(**kw): return {"text": json.dumps(kw)}
        messages = [msg(type="sample"), {"bytes": b"microphone"},
                    msg(type="webrtc_offer", sdp="offer"), msg(type="webrtc_offer", sdp="duplicate"),
                    msg(type="sample", text="Run a task"), msg(type="sample"), msg(type="stop")]
        provider, socket = Provider(), Socket()
        await voice_preview.serve(socket, provider)
        self.assertEqual(provider.offers, ["offer"])
        self.assertEqual(len(provider.texts), 1)
        self.assertIn("Min Min", provider.texts[0])
        self.assertNotIn("Run a task", provider.texts[0])
        self.assertNotIn("8%", provider.texts[0])
        self.assertEqual([e["type"] for e in socket.sent], ["ready", "webrtc_answer"])
        self.assertTrue(provider.closed and socket.closed)

    async def test_identity_and_vietnamese_pronunciation_reach_live_session(self):
        provider = voice_live.ChatGPTLive(voice="maple")
        params = provider.start_params("offer")
        self.assertEqual(params["voice"], "maple")
        self.assertIn("Min Min", params["prompt"])
        self.assertIn("native Vietnamese accent", params["prompt"])
        self.assertNotIn("Bạn là Javis", params["prompt"])
        english = voice_live.ChatGPTLive(recognition_lang="en-US")
        self.assertNotIn("native Vietnamese accent", english.start_params("offer")["prompt"])


if __name__ == "__main__":
    unittest.main()
