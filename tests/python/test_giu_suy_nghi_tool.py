"""DeepSeek / Kimi K3 (26.10.2): phần SUY NGHĨ của model phải được gửi lại ở vòng gọi tool sau.

    python tests/python/test_giu_suy_nghi_tool.py      (KHÔNG mạng: httpx giả)

Kimi K3 và DeepSeek bản suy nghĩ đòi tin assistant có tool_calls ở vòng sau mang nguyên phần
suy nghĩ của chính nó (`reasoning_content` ở API gốc, `reasoning` / `reasoning_details` qua
OpenRouter). Trước 26.10.2 vòng tool bỏ mất các trường đó. Canh:
1. OpenRouter và OpenAI Compatible GỬI LẠI đủ các trường suy nghĩ.
2. Groq (và nhà khác) KHÔNG nhận trường lạ: tin gửi lại chỉ có content + tool_calls.
3. Model không trả suy nghĩ thì không chèn trường rỗng nào.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import sys

import engine  # noqa: E402
import mcp_client  # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


class R:
    def __init__(self, data):
        self._d, self.status_code, self.text, self.headers = data, 200, json.dumps(data), {}

    def json(self):
        return self._d


class FakeClient:
    payloads, responses = [], []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        FakeClient.payloads.append(json)
        return FakeClient.responses.pop(0)


TOOL = [{"fn": "pos_doanh_thu", "description": "Doanh thu", "schema": {"type": "object", "properties": {}}}]
TC = [{"id": "call_1", "type": "function", "function": {"name": "pos_doanh_thu", "arguments": "{}"}}]


def luot(suy_nghi):
    msg = {"content": "", "tool_calls": TC}
    msg.update(suy_nghi)
    return [R({"choices": [{"message": msg}]}),
            R({"choices": [{"message": {"content": "Doanh thu hôm nay 12 triệu."}}]})]


async def chay(ham):
    FakeClient.payloads = []
    return [e async for e in ham]


async def main():
    old_client, old_call = engine.httpx.AsyncClient, mcp_client.call_route
    engine.httpx.AsyncClient = FakeClient

    async def fake_call(route, name, args):
        return "12000000"
    mcp_client.call_route = fake_call
    hoi = [{"role": "user", "content": "doanh thu hôm nay bao nhiêu"}]
    try:
        # 1. OpenRouter + Kimi K3: reasoning + reasoning_details
        sn = {"reasoning": "Cần gọi POS.", "reasoning_details": [{"type": "reasoning.text", "text": "Cần gọi POS."}]}
        FakeClient.responses = luot(sn)
        ev = await chay(engine.openrouter_chat_with_mcp("k", "moonshotai/kimi-k3", hoi, None, TOOL, {"pos_doanh_thu": {}}))
        tin = [m for m in FakeClient.payloads[1]["messages"] if m.get("role") == "assistant"][-1]
        check("OpenRouter gửi lại reasoning + reasoning_details ở vòng 2",
              tin.get("reasoning") == sn["reasoning"] and tin.get("reasoning_details") == sn["reasoning_details"], tin)
        check("OpenRouter: câu trả lời cuối tới nơi", any(e.get("content") == "Doanh thu hôm nay 12 triệu." for e in ev))

        # 2. OpenAI Compatible trỏ thẳng DeepSeek / Moonshot: reasoning_content
        old_url = engine.openai_compat_url
        engine.openai_compat_url = lambda: "https://api.deepseek.com/v1/chat/completions"
        try:
            FakeClient.responses = luot({"reasoning_content": "Gọi tool POS trước."})
            await chay(engine.openai_compat_chat_with_mcp("k", "deepseek-v4-pro", hoi, None, TOOL, {"pos_doanh_thu": {}}))
        finally:
            engine.openai_compat_url = old_url
        tin = [m for m in FakeClient.payloads[1]["messages"] if m.get("role") == "assistant"][-1]
        check("OpenAI Compatible gửi lại reasoning_content", tin.get("reasoning_content") == "Gọi tool POS trước.", tin)

        # 3. Groq: không gửi trường lạ
        FakeClient.responses = luot({"reasoning": "nghĩ", "reasoning_content": "nghĩ"})
        await chay(engine._cc_tool_loop("https://fake", {}, "kimi-k3", hoi, TOOL, {"pos_doanh_thu": {}}, {}, "Groq"))
        tin = [m for m in FakeClient.payloads[1]["messages"] if m.get("role") == "assistant"][-1]
        check("Groq: tin gửi lại chỉ có role/content/tool_calls",
              set(tin) == {"role", "content", "tool_calls"}, sorted(tin))

        # 4. Không có suy nghĩ thì không chèn trường rỗng
        FakeClient.responses = luot({"reasoning": "", "reasoning_details": None})
        await chay(engine.openrouter_chat_with_mcp("k", "deepseek/deepseek-v4.1-flash", hoi, None, TOOL, {"pos_doanh_thu": {}}))
        tin = [m for m in FakeClient.payloads[1]["messages"] if m.get("role") == "assistant"][-1]
        check("không có suy nghĩ: không chèn trường rỗng", set(tin) == {"role", "content", "tool_calls"}, sorted(tin))
    finally:
        engine.httpx.AsyncClient, mcp_client.call_route = old_client, old_call

asyncio.run(main())

src = (ROOT / "server" / "config.py").read_text(encoding="utf-8")
check("gợi ý OpenRouter có DeepSeek V4.1 Flash và Kimi K3",
      "deepseek/deepseek-v4.1-flash" in src and "moonshotai/kimi-k3" in src)

if _fails:
    print(f"\nFAIL - test_giu_suy_nghi_tool: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_giu_suy_nghi_tool: tất cả pass")
