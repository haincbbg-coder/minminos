"""Bốn bộ não API key riêng (26.10.212): DeepSeek, Qwen, GLM, MiniMax.

Chốt ba thứ, không cần mạng:
  1. Bốn provider có mặt ở MỌI chỗ đăng ký (sót một chỗ là lỗi câm: thẻ hiện ra mà chat rơi về
     nhánh mặc định, key ghi plaintext, việc nền nổ KeyError, usage bị vứt...).
  2. URL theo vùng đúng tài liệu chính hãng, tự nhận vùng theo tiền tố key, ô Base URL thắng.
  3. Một lượt chat thật qua máy chủ HTTP giả cục bộ: đúng endpoint, đúng header Authorization,
     vòng tool gửi lại reasoning_content, DeepSeek tắt/bật suy nghĩ đúng nấc và tự cứu 400.

Chạy:
    python3 tests/python/test_nha_api_rieng.py
"""
import asyncio
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-nha-rieng-test-"))
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path

import aux_engine  # noqa: E402
import be_khoa  # noqa: E402
import config as cfgmod  # noqa: E402
import engine  # noqa: E402
import main  # noqa: E402
import nha_api_rieng as nar  # noqa: E402
import usage_index  # noqa: E402

CONSOLE_JS = (ROOT / "dashboard" / "console.js").read_text(encoding="utf-8")
VI = json.loads((ROOT / "dashboard" / "i18n" / "vi.json").read_text(encoding="utf-8"))
EN = json.loads((ROOT / "dashboard" / "i18n" / "en.json").read_text(encoding="utf-8"))
IDS = ("deepseek", "qwen", "glm", "minimax")

fails = []


def check(name, cond):
    print(("PASS: " if cond else "FAIL: ") + name)
    if not cond:
        fails.append(name)


# ─────────── 1. Có mặt ở mọi chỗ đăng ký ───────────
check("bảng có đúng bốn hãng", nar.IDS == IDS)
_MAIN_SRC = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
_mcp_src = _MAIN_SRC[_MAIN_SRC.index("async def _api_stream_mcp"):_MAIN_SRC.index("def _last_user_text")]
check("tên chữ trong _api_stream_mcp khớp bảng", all(f'"{p}"' in _mcp_src for p in IDS))
_defs = {p["id"]: p for p in main.PROVIDER_DEFS}
for pid in IDS:
    kf = f"{pid}_api_key"
    d = _defs.get(pid) or {}
    check(f"{pid}: PROVIDER_DEFS kind=api, key_field={kf}", d.get("kind") == "api" and d.get("key_field") == kf)
    check(f"{pid}: có model mặc định", bool(d.get("default_models")))
    check(f"{pid}: config có ô key/vùng/base", all(k in cfgmod._DEFAULT["model"]
                                                    for k in (kf, f"{pid}_vung", f"{pid}_base")))
    check(f"{pid}: config có catalog", pid in cfgmod._DEFAULT["model"]["catalog"])
    check(f"{pid}: key nằm trong danh sách MÃ HOÁ", f"model.{kf}" in cfgmod._SECRET_PATHS)
    check(f"{pid}: key bị che ở GET /settings", kf in main._PROVIDER_KEY_FIELDS)
    check(f"{pid}: aux_engine coi là API + map key", pid in aux_engine.API_PROVIDERS
          and aux_engine._KEY_FIELD.get(pid) == kf)
    check(f"{pid}: engine có hàm stream + MCP", engine.nha_rieng_ham(pid) is getattr(engine, f"{pid}_stream")
          and engine.nha_rieng_ham(pid, True) is getattr(engine, f"{pid}_chat_with_mcp"))
    check(f"{pid}: bể khoá", pid in be_khoa.API_CO_BE)
    check(f"{pid}: agent/việc nền chọn được", pid in main.AGENT_PROVIDERS)
    check(f"{pid}: đi vòng tool + hub", pid in main._API_CO_VONG_TOOL)
    check(f"{pid}: bộ chấm đánh giá", pid in main._DG_NAO_API)
    check(f"{pid}: nhãn tên", main._api_label(pid) != pid and pid in main._TG_NHAN_NGAN)
    check(f"{pid}: usage không bị vứt", pid in usage_index._API_PROVIDERS)
    check(f"{pid}: giao diện KEYFIELD", f'"{pid}": "{kf}"' in CONSOLE_JS)
    check(f"{pid}: giao diện MCP_PROVIDERS", f'"{pid}"' in CONSOLE_JS.split("const MCP_PROVIDERS", 1)[1][:400])
    check(f"{pid}: mô tả thẻ vi/en", f"models.rg_note_{pid}" in VI and f"models.rg_note_{pid}" in EN)
    _cfg = {"model": {}}
    main._set_main_model(_cfg, pid, "x")
    check(f"{pid}: _set_main_model ghi engine", _cfg["model"]["engine"] == pid)
    view = {p["id"]: p for p in main._providers_view({"model": {kf: "sk-abc"}})}
    check(f"{pid}: thẻ có phần riêng + đã kết nối", view[pid]["configured"] and "rieng" in view[pid]
          and view[pid]["agent_ok"])
for k in ("models.rg_terms", "models.rg_plan_warn", "models.rg_auto", "models.rg_check", "models.rg_ok_n"):
    check(f"i18n {k}", k in VI and k in EN)
check("mô tả thẻ nói thật về điều khoản Coding Plan", "điều khoản" in VI["models.rg_plan_warn"]
      and "API key" in VI["models.rg_terms"])

# ─────────── 2. URL theo vùng ───────────
check("DeepSeek", nar.chat_url("deepseek", {}) == "https://api.deepseek.com/chat/completions")
check("Qwen key sk-sp- -> Coding Plan quốc tế",
      nar.chat_url("qwen", {"qwen_api_key": "sk-sp-123"}) == "https://coding-intl.dashscope.aliyuncs.com/v1/chat/completions")
check("Qwen key sk- -> DashScope Singapore",
      nar.chat_url("qwen", {"qwen_api_key": "sk-123"}) == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
check("Qwen chọn vùng Coding Plan Trung Quốc",
      nar.base_url("qwen", {"qwen_api_key": "sk-sp-1", "qwen_vung": "coding-cn"}) == "https://coding.dashscope.aliyuncs.com/v1")
check("Qwen key dự phòng khác loại -> URL theo key đó",
      nar.base_url("qwen", {"qwen_api_key": "sk-sp-1"}, key="sk-2") == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
check("GLM mặc định endpoint Coding Plan z.ai", nar.base_url("glm", {}) == "https://api.z.ai/api/coding/paas/v4")
check("GLM Trung Quốc", nar.base_url("glm", {"glm_vung": "trung-quoc"}) == "https://open.bigmodel.cn/api/coding/paas/v4")
check("MiniMax quốc tế", nar.base_url("minimax", {}) == "https://api.minimax.io/v1")
check("MiniMax Trung Quốc", nar.base_url("minimax", {"minimax_vung": "trung-quoc"}) == "https://api.minimax.cn/v1")
check("vùng lạ -> tự động", nar.base_url("glm", {"glm_vung": "sao-hoa"}) == "https://api.z.ai/api/coding/paas/v4")
check("Base URL tự dán thắng, cắt đuôi /chat/completions",
      nar.base_url("minimax", {"minimax_base": "https://x.example/v9/chat/completions/"}) == "https://x.example/v9")
check("Base URL rác bị bỏ qua", nar.base_url("deepseek", {"deepseek_base": "abc"}) == "https://api.deepseek.com")
check("mọi URL trong bảng là https", all(u.startswith("https://") for d in nar.NHA.values() for u, _ in d["vung"].values()))

# Suy nghĩ
check("DeepSeek off -> tắt suy nghĩ", nar.payload_suy_nghi("deepseek", "", "off") == {"thinking": {"type": "disabled"}})
check("DeepSeek ultra -> max", nar.payload_suy_nghi("deepseek", "", "ultra")["reasoning_effort"] == "max")
check("MiniMax off -> low (không tắt được)", nar.payload_suy_nghi("minimax", "", "off") == {"reasoning_effort": "low"})
check("Qwen/GLM không gửi trường lạ", nar.payload_suy_nghi("qwen", "", "high") == {} == nar.payload_suy_nghi("glm", "", "high"))

# Lưu vùng/base qua POST /settings, và giá trị rác bị chặn.
asyncio.run(main.settings_set(section="model", data=json.dumps(
    {"qwen_vung": "coding-cn", "glm_vung": "rac", "minimax_base": "ftp://x", "deepseek_base": "http://127.0.0.1:1/v1/"})))
_m = cfgmod.read_settings()["model"]
check("lưu vùng hợp lệ", _m.get("qwen_vung") == "coding-cn")
check("vùng rác -> rỗng", _m.get("glm_vung") == "")
check("base không phải http(s) không lưu", _m.get("minimax_base") == "")
check("base hợp lệ lưu đã chuẩn hoá", _m.get("deepseek_base") == "http://127.0.0.1:1/v1")

# ─────────── 3. Chạy thật với máy chủ giả ───────────
SEEN = []
MODE = {"deepseek_400": False}


class _Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": None})
        self._json(200, {"data": [{"id": "m-1"}, {"id": "m-2"}, {"id": "text-embed-x"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        if MODE["deepseek_400"] and body.get("tools") and (body.get("thinking") or {}).get("type") != "disabled":
            self._json(400, {"error": {"message": "Missing reasoning_content in assistant message"}})
            return
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for ch in ("Xin ", "chào"):
                self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": ch}}]}).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")
            return
        first = bool(body.get("tools")) and not any(m.get("role") == "tool" for m in body["messages"])
        msg = ({"role": "assistant", "content": None, "reasoning_content": "nghĩ đã",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "javis_connections", "arguments": "{}"}}]}
               if first else {"role": "assistant", "content": "Xong"})
        self._json(200, {"choices": [{"message": msg, "finish_reason": "tool_calls" if first else "stop"}],
                         "usage": {"prompt_tokens": 3, "completion_tokens": 2}})


_srv = HTTPServer(("127.0.0.1", 0), _Fake)
threading.Thread(target=_srv.serve_forever, daemon=True).start()
PORT = _srv.server_address[1]
_s = cfgmod.read_settings()
for pid in IDS:
    _s["model"][f"{pid}_base"] = f"http://127.0.0.1:{PORT}/{pid}/v1"
    _s["model"][f"{pid}_api_key"] = f"sk-{pid}-test"
cfgmod.write_settings(_s)

TOOLS = [{"fn": "javis_connections", "server": "javis", "name": "javis_connections",
          "description": "liệt kê nguồn", "schema": {"type": "object", "properties": {}, "required": []}}]


async def _call(_args):
    return "Kết nối: POS"


ROUTE = {"javis_connections": {"call": _call}}


async def _run():
    for pid in IDS:
        key = f"sk-{pid}-test"
        SEEN.clear()
        text = ""
        async for ev in main._api_stream(pid, key, "", [{"role": "user", "content": "chào"}], "off"):
            if ev["type"] == "text":
                text += ev["content"]
        check(f"{pid}: stream ra chữ ({text!r})", text == "Xin chào")
        check(f"{pid}: đúng endpoint chat", SEEN and SEEN[0]["path"] == f"/{pid}/v1/chat/completions")
        check(f"{pid}: header Authorization Bearer", SEEN and SEEN[0]["auth"] == f"Bearer {key}")
        check(f"{pid}: model mặc định của bảng", SEEN and SEEN[0]["body"]["model"] == nar.model_mac_dinh(pid))

        SEEN.clear()
        called, text = [], ""
        async for ev in engine.nha_rieng_ham(pid, True)(key, "", [{"role": "user", "content": "có gì"}],
                                                  "high", TOOLS, ROUTE):
            if ev["type"] == "tool_call":
                called.append(ev.get("name"))
            if ev["type"] == "text":
                text += ev["content"]
        check(f"{pid}: vòng tool gọi được tool rồi trả lời", called == ["javis_connections"] and "Xong" in text)
        lai = [m for m in SEEN[-1]["body"]["messages"] if m.get("role") == "assistant"]
        check(f"{pid}: vòng sau gửi lại reasoning_content", lai and lai[-1].get("reasoning_content") == "nghĩ đã")

    SEEN.clear()
    async for _ in engine.deepseek_stream("k", "deepseek-v4-pro", [{"role": "user", "content": "x"}], "off"):
        pass
    check("DeepSeek off: payload có thinking disabled", SEEN[0]["body"].get("thinking") == {"type": "disabled"})

    # Lịch sử cũ thiếu reasoning_content -> DeepSeek 400 -> tắt suy nghĩ, thử lại, vẫn trả lời.
    MODE["deepseek_400"] = True
    SEEN.clear()
    text = ""
    async for ev in engine.deepseek_chat_with_mcp("k", "deepseek-v4-pro", [{"role": "user", "content": "x"}],
                                                  "high", TOOLS, ROUTE):
        if ev["type"] == "text":
            text += ev["content"]
    MODE["deepseek_400"] = False
    check(f"DeepSeek 400 reasoning_content -> tự cứu ({text!r})", "Xong" in text)
    check("sau khi cứu không còn reasoning_effort", "reasoning_effort" not in SEEN[-1]["body"])

    # Danh sách model live từ {base}/models, lọc model không chat được.
    SEEN.clear()
    r = await main.provider_models_index("minimax", refresh=True)
    check(f"/provider/models hỏi {{base}}/models ({r.get('models')})",
          SEEN and SEEN[0]["path"] == "/minimax/v1/models" and "text-embed-x" not in r["models"]
          and set(r["models"]) == {"m-1", "m-2"})

    class _Req:
        async def json(self):
            return {"prov": "glm"}
    r = await main.nha_rieng_kiem(_Req())
    check(f"nút Kiểm tra kết nối ({r})", r.get("ok") and r.get("so_model") == 3)


asyncio.run(_run())

_gen = main._api_stream_goc("qwen", "k", "m", [{"role": "user", "content": "x"}], "off")
check("_api_stream_goc chọn đúng generator", _gen.__qualname__.startswith("nha_rieng_stream"))
del _gen

if fails:
    raise SystemExit(f"\nFAIL - test_nha_api_rieng: {len(fails)} lỗi")
print("\nOK - test_nha_api_rieng: tất cả pass")
