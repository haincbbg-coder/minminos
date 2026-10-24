# -*- coding: utf-8 -*-
"""Ba bộ não CLI gói thuê bao 26.10.215: Kiro, Cursor, Mistral Vibe.

    python tests/run.py nao_kiro_cursor_vibe      (KHÔNG mạng)

Mỗi CLI có một binary GIẢ (script Python) đóng đúng vai đã biết của bản thật:
- Vibe: sơ đồ ĐÃ ĐO trên mistral-vibe 3.0.2 (NDJSON `message`/`effect`, export.json, câu lỗi
  "Missing MISTRAL_API_KEY", vibe-acp với `browser-auth-delegated`).
- Kiro, Cursor: theo tài liệu chính chủ (chưa đo được binary - domain cài bị chặn). Cursor theo
  sơ đồ stream-json đã công bố; Kiro thì sơ đồ chưa công bố nên binary giả cố ý dùng tên loại lạ
  để canh phần dịch "theo hình dạng".

Luồng phải chạy được: đăng nhập trên trang (link + mã, chờ người dùng xác nhận), một lượt chat,
lỗi chưa đăng nhập ra câu tiếng Việt, ghi + đọc lại cấu hình MCP trong brain, dán API key.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
import textwrap
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


TMP = Path(tempfile.mkdtemp(prefix="nao-cli-gia-"))
HOME = TMP / "home"
HOME.mkdir()
os.environ["HOME"] = str(HOME)
os.environ.pop("USERPROFILE", None)
for k in ("KIRO_API_KEY", "CURSOR_API_KEY", "MISTRAL_API_KEY", "VIBE_HOME"):
    os.environ.pop(k, None)
BIN = TMP / "bin"
BIN.mkdir()
DAU = TMP / "dau"          # thư mục cờ: file trong này = "người dùng đã bấm xác nhận"
DAU.mkdir()
ARGV = TMP / "argv"
ARGV.mkdir()


def viet(ten: str, ma: str) -> Path:
    p = BIN / ten
    p.write_text(f"#!{sys.executable}\n" + textwrap.dedent(ma), encoding="utf-8")
    p.chmod(0o755)
    return p


CHUNG = f'''
import os, sys, json, time
DAU = {str(DAU)!r}
ARGV = {str(ARGV)!r}
def ghi_argv(ten):
    open(os.path.join(ARGV, ten), "w").write(json.dumps(sys.argv[1:]))
def cho_dau(ten, giay=30):
    han = time.time() + giay
    while time.time() < han:
        if os.path.exists(os.path.join(DAU, ten)):
            return True
        time.sleep(0.1)
    return False
'''

# ---------------------------------------------------------------- Kiro (theo tài liệu)
viet("kiro-cli", CHUNG + '''
a = sys.argv[1:]
if a[-1:] == ["--help"]:
    if a[:1] == ["login"]:
        print("--license <TYPE>  --social <PROVIDER>  --identity-provider <URL>  --region  --use-device-flow")
    elif a[:1] == ["chat"]:
        print("--no-interactive --output-format <F> --trust-all-tools --trust-tools <IDS> --model <M> "
              "--effort <low|medium|high|xhigh|max> --resume-id <ID> --wrap <always|never|auto> --list-models")
    else:
        print("Usage: kiro-cli <login|logout|whoami|chat>")
    sys.exit(0)
dang_nhap = os.path.exists(os.path.join(DAU, "kiro"))
if a[:1] == ["whoami"]:
    if dang_nhap:
        print(json.dumps({"email": "bo@halimi.vn", "accountType": "BuilderId", "plan": "Pro"})); sys.exit(0)
    print("Not logged in", file=sys.stderr); sys.exit(1)
if a[:1] == ["logout"]:
    try: os.remove(os.path.join(DAU, "kiro"))
    except FileNotFoundError: pass
    sys.exit(0)
if a[:1] == ["login"]:
    ghi_argv("kiro-login")
    print("Confirm the following code in the browser", flush=True)
    print("Code: WXYZ-ABCD", flush=True)
    print("Open this URL: https://view.awsapps.com/start/#/device?user_code=WXYZ-ABCD", flush=True)
    if cho_dau("kiro-ok"):
        open(os.path.join(DAU, "kiro"), "w").write("x"); print("Logged in successfully"); sys.exit(0)
    sys.exit(1)
if a[:1] == ["chat"]:
    ghi_argv("kiro-chat")
    if "--list-models" in a:
        print(json.dumps([{"model_id": "auto"}, {"model_id": "claude-sonnet-4.5"}])); sys.exit(0)
    prompt = sys.stdin.read()
    open(os.path.join(ARGV, "kiro-stdin"), "w").write(prompt)
    if not dang_nhap and not os.environ.get("KIRO_API_KEY"):
        print("error: You are not logged in, please run kiro-cli login", file=sys.stderr); sys.exit(1)
    # Sơ đồ CHƯA công bố: dùng tên loại lạ để canh phần dịch theo hình dạng.
    for ev in ({"kind_of": "init", "type": "session_start", "conversation_id": "conv-77"},
               {"type": "tool_use_start", "name": "read_file", "input": {"path": "a.md"}},
               {"type": "assistant_text_delta", "text": "Xin "},
               {"type": "assistant_text_delta", "text": "chào bố"},
               {"type": "turn_complete", "usage": {"input_tokens": 120, "output_tokens": 4}}):
        print(json.dumps(ev), flush=True)
    sys.exit(0)
sys.exit(2)
''')
os.environ["JAVIS_KIRO_BIN"] = str(BIN / "kiro-cli")

# ---------------------------------------------------------------- Cursor (theo tài liệu)
viet("cursor-agent", CHUNG + '''
a = sys.argv[1:]
if a[-1:] == ["--help"]:
    print("-p, --print --output-format <format> --stream-partial-output --resume [chatId] --model <model> "
          "--mode <mode> -f, --force --approve-mcps --trust --workspace <path> --api-key <key>\\n"
          "Commands: login logout status models mcp")
    sys.exit(0)
dang_nhap = os.path.exists(os.path.join(DAU, "cursor"))
if a[:1] == ["status"]:
    print("Logged in as bo@halimi.vn" if dang_nhap else "Not logged in"); sys.exit(0)
if a[:1] == ["logout"]:
    try: os.remove(os.path.join(DAU, "cursor"))
    except FileNotFoundError: pass
    sys.exit(0)
if a[:1] == ["models"]:
    print("Available models:"); print("- auto"); print("- gpt-5 (GPT-5)"); print("- sonnet-4.5"); sys.exit(0)
if a[:1] == ["login"]:
    ghi_argv("cursor-login")
    print("Open the following URL to log in:", flush=True)
    print("https://cursor.com/loginDeepControl?challenge=abc&uuid=1234&mode=login", flush=True)
    if cho_dau("cursor-ok"):
        open(os.path.join(DAU, "cursor"), "w").write("x"); print("Login successful!"); sys.exit(0)
    sys.exit(1)
if "-p" in a:
    ghi_argv("cursor-chat")
    if not dang_nhap and not os.environ.get("CURSOR_API_KEY"):
        print("Error: Authentication required. Please run 'agent login' first.", file=sys.stderr); sys.exit(1)
    sid = "chat-42"
    for ev in ({"type": "system", "subtype": "init", "apiKeySource": "login", "cwd": "/x",
                "session_id": sid, "model": "auto", "permissionMode": "default"},
               {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}, "session_id": sid},
               {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Để em đọc file."}]}, "session_id": sid},
               {"type": "tool_call", "subtype": "started", "call_id": "c1",
                "tool_call": {"readToolCall": {"args": {"path": "a.md"}}}, "session_id": sid},
               {"type": "tool_call", "subtype": "completed", "call_id": "c1",
                "tool_call": {"readToolCall": {"args": {"path": "a.md"}, "result": {"success": {"content": "x"}}}}, "session_id": sid},
               {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Chào bố, file có chữ x."}]}, "session_id": sid},
               {"type": "result", "subtype": "success", "duration_ms": 10, "is_error": False,
                "result": "Để em đọc file.Chào bố, file có chữ x.", "session_id": sid}):
        print(json.dumps(ev, ensure_ascii=False), flush=True)
    sys.exit(0)
sys.exit(2)
''')
os.environ["JAVIS_CURSOR_BIN"] = str(BIN / "cursor-agent")

# ---------------------------------------------------------------- Vibe (sơ đồ ĐÃ ĐO)
VDIR = TMP / "vbin"
VDIR.mkdir()


def viet_v(ten, ma):
    p = VDIR / ten
    p.write_text(f"#!{sys.executable}\n" + textwrap.dedent(ma), encoding="utf-8")
    p.chmod(0o755)


viet_v("vibe", CHUNG + '''
a = sys.argv[1:]
if a[:1] == ["--help"]:
    print("-p, --prompt [<PROMPT>] --output <OUTPUT> [possible values: text, json, streaming] --max-turns "
          "--prompt-file <PATH> --output-dir <DIR> --agent <NAME> --auto-approve --trust --resume [<RESUME>]")
    sys.exit(0)
ghi_argv("vibe-chat")
home = os.environ.get("VIBE_HOME") or os.path.join(os.environ["HOME"], ".vibe")
key = os.environ.get("MISTRAL_API_KEY")
try:
    for l in open(os.path.join(home, ".env")):
        if l.startswith("MISTRAL_API_KEY="): key = l.split("=", 1)[1].strip().strip("'")
except FileNotFoundError:
    pass
print("Reading API keys from the system keyring (set them as environment variables to skip this)", file=sys.stderr)
if not key:
    print("Error: Missing MISTRAL_API_KEY environment variable for mistral provider", file=sys.stderr); sys.exit(1)
open(os.path.join(ARGV, "vibe-model"), "w").write(os.environ.get("VIBE_ACTIVE_MODEL", ""))
sid = "a7fca5f1-db53-7bbd-aedc-06a919f2ca7d"
base = {"sessionId": sid, "turnId": "turn-1", "generationStatus": "completed"}
for ev in ({**base, "id": "user-turn-1", "type": "message", "role": "user", "content": [{"type": "text", "text": "x"}], "outcome": None},
           {**base, "id": "assistant-1", "type": "message", "role": "assistant", "content": [{"type": "text", "text": "Để em xem."}], "outcome": None},
           {**base, "id": "effect-1", "type": "effect", "title": "file_system.bash",
            "detail": {"toolName": "file_system.bash", "kind": "shell", "input": {"command": "ls"}},
            "state": {"status": "completed", "outputText": "a.md\\n", "decision": "execute"}},
           {**base, "id": "assistant-2", "type": "message", "role": "assistant", "content": [{"type": "text", "text": "Xin chào bố"}], "outcome": {"type": "committed"}}):
    print(json.dumps(ev, ensure_ascii=False), flush=True)
if "--output-dir" in a:
    d = a[a.index("--output-dir") + 1]
    os.makedirs(d, exist_ok=True)
    json.dump({"outcome": "finished", "session_id": sid,
               "usage": {"input_tokens": 110, "output_tokens": 8, "cached_input_tokens": 0, "total_tokens": 118}},
              open(os.path.join(d, "export.json"), "w"))
sys.exit(0)
''')
viet_v("vibe-acp", CHUNG + '''
home = os.environ.get("VIBE_HOME") or os.path.join(os.environ["HOME"], ".vibe")
open(os.path.join(ARGV, "vibe-acp-keyring"), "w").write(os.environ.get("PYTHON_KEYRING_BACKEND", ""))
for l in sys.stdin:
    d = json.loads(l); i = d["id"]; m = d["method"]; p = d.get("params") or {}
    if m == "initialize":
        meta = ((p.get("clientCapabilities") or {}).get("_meta") or {})
        cach = [{"id": "browser-auth"}] + ([{"id": "browser-auth-delegated"}] if meta.get("browser-auth-delegated") else [])
        r = {"protocolVersion": 1, "authMethods": cach}
    elif m == "authenticate" and (p.get("_meta") or {}).get("action") == "start":
        r = {"_meta": {"browser-auth-delegated": {"attemptId": "proc123", "expiresAt": "2099-01-01T00:00:00Z",
             "signInUrl": "https://console.mistral.ai/vibe/sign-in?process=proc123"}}}
    elif m == "authenticate":
        if cho_dau("vibe-ok"):
            os.makedirs(home, exist_ok=True)
            open(os.path.join(home, ".env"), "w").write("MISTRAL_API_KEY='sk-FAKEKEYFAKEKEY1234567890'\\n")
            r = {"_meta": {"browser-auth-delegated": {"attemptId": "proc123", "status": "completed"}}}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": i, "error": {"code": -32600, "message": "Browser sign-in timed out."}}), flush=True); continue
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "Method not found"}}), flush=True); continue
    print(json.dumps({"jsonrpc": "2.0", "id": i, "result": r}), flush=True)
''')
os.environ["JAVIS_VIBE_BIN"] = str(VDIR / "vibe")

import cli_nao_chung as chung  # noqa: E402
import kiro_cli  # noqa: E402
import cursor_cli  # noqa: E402
import vibe_cli  # noqa: E402


def mot_luot(cls, mode="full", model=None, sid=None, prompt="chào"):
    async def _m():
        g = cls(cwd=str(TMP), tag="test", model=model)
        g.mode = mode
        g.session_id = sid
        g.timeout = 30
        evs = [ev async for ev in g.query(prompt)]
        return g, evs
    return asyncio.run(_m())


def cuoi(evs, loai):
    x = [e for e in evs if e.get("type") == loai]
    return x[-1] if x else {}


def doc_argv(ten):
    return json.loads((ARGV / ten).read_text())


def dang_nhap_tren_trang(mod, ten_dau, **kw):
    r = mod.login_start(**kw)
    check(f"{mod.ID}: login_start trả link", bool(r.get("ok")) and r.get("url", "").startswith("https://"))
    d = mod.login_trang_thai()
    check(f"{mod.ID}: đang chờ người dùng, chưa xanh", d.get("dang_cho") and not d.get("connected"))
    (DAU / ten_dau).write_text("x")       # người dùng bấm xác nhận trên trình duyệt
    han = time.time() + 20
    while time.time() < han:
        d = mod.login_trang_thai()
        if d.get("connected") or not d.get("dang_cho"):
            break
        time.sleep(0.3)
    check(f"{mod.ID}: đăng nhập xong thì xanh", bool(d.get("connected")))
    return r


# ================================================================= chung
check("chung: NAO đủ ba id", list(chung.NAO) == ["kiro-cli", "cursor-cli", "vibe-cli"])
check("chung: mo_dun trả module", chung.mo_dun("vibe-cli") is vibe_cli and chung.mo_dun("grok-cli") is None)
che = chung.che("token sk-abcdefghijklmnopqrstuvwxyz0123 và ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef0123")
check("chung: che khoá trong nhật ký", "sk-abc" not in che and "ABCDEFGHIJ" not in che)
check("chung: giữ nguyên link đăng nhập", chung.che("mở https://x.y/a?b=1").endswith("?b=1"))
check("chung: giữ mã device", "WXYZ-ABCD" in chung.che("Code: WXYZ-ABCD"))
check("chung: cat_args không lộ prompt",
      "bí mật" not in json.dumps(chung.cat_args(["x", "-p", "--output-format", "json", "bí mật dài " * 10])))

# ================================================================= Kiro
check("kiro: tìm thấy binary giả", kiro_cli.find_cli() == str(BIN / "kiro-cli"))
st = kiro_cli.auth_status(cho=True)
check("kiro: chưa đăng nhập thì không xanh", not st.get("connected"))
g, evs = mot_luot(kiro_cli.KiroCLI)
loi = cuoi(evs, "error").get("content", "")
check("kiro: lỗi chưa đăng nhập ra câu tiếng Việt", "chưa đăng nhập" in loi and "Đăng nhập" in loi)
check("kiro: chưa đăng nhập thì không có final", not cuoi(evs, "final"))

r = dang_nhap_tren_trang(kiro_cli, "kiro-ok", cach="google")
check("kiro: bóc được mã device", r.get("code") == "WXYZ-ABCD")
la = doc_argv("kiro-login")
check("kiro: login dùng device flow + Google", "--use-device-flow" in la and la[la.index("--social") + 1] == "google")
st = kiro_cli.auth_status(cho=True)
check("kiro: whoami đọc ra tài khoản + gói", st.get("account") == "bo@halimi.vn" and st.get("plan") == "Pro")
r_idc = kiro_cli.login_start(cach="identity-center", idc_url="")
check("kiro: Identity Center thiếu Start URL thì báo rõ", (not r_idc.get("ok")) or r_idc.get("xong"))

g, evs = mot_luot(kiro_cli.KiroCLI, mode="suggest", model="claude-sonnet-4.5", prompt="đọc a.md giúp")
check("kiro: một lượt chat ra final ghép từ delta", cuoi(evs, "final").get("content") == "Xin chào bố")
check("kiro: tool_call dịch theo hình dạng", cuoi(evs, "tool_call").get("name") == "read_file")
check("kiro: usage đọc được", cuoi(evs, "usage").get("input_tokens") == 120)
check("kiro: id mạch đọc từ conversation_id", g.session_id == "conv-77")
ca = doc_argv("kiro-chat")
check("kiro: suggest chỉ tin tool đọc", "--trust-tools=read_file,grep_search" in ca and "--trust-all-tools" not in ca)
check("kiro: truyền --model + --no-interactive + stream-json",
      "--no-interactive" in ca and ca[ca.index("--model") + 1] == "claude-sonnet-4.5"
      and ca[ca.index("--output-format") + 1] == "stream-json")
check("kiro: prompt đi qua stdin, không lên argv",
      "đọc a.md giúp" in (ARGV / "kiro-stdin").read_text() and not any("đọc a.md" in x for x in ca))
g, evs = mot_luot(kiro_cli.KiroCLI, mode="full", sid="conv-77")
ca = doc_argv("kiro-chat")
check("kiro: full tin mọi tool + resume đúng id",
      "--trust-all-tools" in ca and ca[ca.index("--resume-id") + 1] == "conv-77")
check("kiro: co_effort khai đủ cờ lẫn giá trị", kiro_cli.co_effort("ultra") == ["--effort", "max"])
check("kiro: list_models hỏi CLI", "claude-sonnet-4.5" in (kiro_cli.list_models() or []))
check("kiro: logout gỡ phiên", kiro_cli.logout().get("ok") and not kiro_cli.auth_status(cho=True).get("connected"))
check("kiro: dán API key thì xanh (gói Pro+)", kiro_cli.dat_api_key("ksk_" + "A" * 30).get("ok")
      and kiro_cli.auth_status(cho=True).get("method") == "api-key")
g, evs = mot_luot(kiro_cli.KiroCLI)
check("kiro: có API key thì chat chạy", cuoi(evs, "final").get("content") == "Xin chào bố")
check("kiro: khoá không nằm trong settings MinMin mà trong ~/.kiro (0600)",
      (HOME / ".kiro/minmin-api-key.env").exists()
      and oct((HOME / ".kiro/minmin-api-key.env").stat().st_mode & 0o777) == "0o600")
kiro_cli.logout()

# ================================================================= Cursor
check("cursor: tìm thấy binary giả", cursor_cli.find_cli() == str(BIN / "cursor-agent"))
g, evs = mot_luot(cursor_cli.CursorCLI)
check("cursor: lỗi chưa đăng nhập ra câu tiếng Việt", "chưa đăng nhập" in cuoi(evs, "error").get("content", ""))
dang_nhap_tren_trang(cursor_cli, "cursor-ok")
check("cursor: status đọc ra email", cursor_cli.auth_status(cho=True).get("account") == "bo@halimi.vn")
g, evs = mot_luot(cursor_cli.CursorCLI, mode="suggest", model="gpt-5")
check("cursor: final lấy từ sự kiện result", cuoi(evs, "final").get("content") == "Để em đọc file.Chào bố, file có chữ x.")
check("cursor: tool_call readToolCall -> read", cuoi(evs, "tool_call").get("name") == "read")
check("cursor: id mạch từ session_id", g.session_id == "chat-42")
ca = doc_argv("cursor-chat")
check("cursor: suggest = --mode ask, không --force",
      ca[ca.index("--mode") + 1] == "ask" and "--force" not in ca)
check("cursor: luôn --trust + --approve-mcps + --workspace", "--trust" in ca and "--approve-mcps" in ca
      and ca[ca.index("--workspace") + 1] == str(TMP))
g, evs = mot_luot(cursor_cli.CursorCLI, mode="full", sid="chat-42")
ca = doc_argv("cursor-chat")
check("cursor: full = --force + resume", "--force" in ca and "--resume=chat-42" in ca)
check("cursor: list_models đọc dòng `- id`", {"gpt-5", "sonnet-4.5", "auto"} <= set(cursor_cli.list_models() or []))
check("cursor: logout", cursor_cli.logout().get("ok") and not cursor_cli.auth_status(cho=True).get("connected"))
cursor_cli.dat_api_key("crsr_" + "B" * 40)
g, evs = mot_luot(cursor_cli.CursorCLI)
check("cursor: API key đi qua biến môi trường, không qua argv",
      cuoi(evs, "final") and not any("crsr_" in x for x in doc_argv("cursor-chat")))
cursor_cli.logout()

# ================================================================= Vibe
check("vibe: tìm thấy binary giả (có vibe-acp cạnh)", vibe_cli.find_cli() == str(VDIR / "vibe")
      and vibe_cli.find_vibe_acp() == str(VDIR / "vibe-acp"))
g, evs = mot_luot(vibe_cli.VibeCLI)
check("vibe: lỗi chưa có khoá ra câu tiếng Việt (câu đo thật)", "chưa đăng nhập" in cuoi(evs, "error").get("content", ""))
r = dang_nhap_tren_trang(vibe_cli, "vibe-ok")
check("vibe: link Mistral, không có mã", "console.mistral.ai" in r.get("url", "") and not r.get("code"))
check("vibe: vibe-acp chạy với keyring hỏng để khoá vào .env",
      (ARGV / "vibe-acp-keyring").read_text() == "keyring.backends.fail.Keyring")
st = vibe_cli.auth_status()
check("vibe: khoá đọc từ ~/.vibe/.env, chỉ lộ 4 ký tự cuối", st.get("method") == "vibe_home_env_file"
      and st.get("duoi_khoa") == "7890" and "FAKEKEY" not in json.dumps(st))
g, evs = mot_luot(vibe_cli.VibeCLI, mode="auto", model="mistral-medium-3.5")
check("vibe: final = tin trợ lý CUỐI", cuoi(evs, "final").get("content") == "Xin chào bố")
check("vibe: effect -> tool_call", cuoi(evs, "tool_call").get("name") == "file_system.bash")
check("vibe: usage đọc từ export.json", cuoi(evs, "usage").get("input_tokens") == 110)
check("vibe: id mạch", g.session_id == "a7fca5f1-db53-7bbd-aedc-06a919f2ca7d")
ca = doc_argv("vibe-chat")
check("vibe: auto = --agent accept-edits, có --trust + streaming + prompt-file",
      ca[ca.index("--agent") + 1] == "accept-edits" and "--trust" in ca
      and ca[ca.index("--output") + 1] == "streaming" and "--prompt-file" in ca)
check("vibe: model qua VIBE_ACTIVE_MODEL", (ARGV / "vibe-model").read_text() == "mistral-medium-3.5")
mot_luot(vibe_cli.VibeCLI, mode="suggest")
check("vibe: suggest = --agent ask", doc_argv("vibe-chat")[doc_argv("vibe-chat").index("--agent") + 1] == "ask")
mot_luot(vibe_cli.VibeCLI, mode="full", sid="s-9")
ca = doc_argv("vibe-chat")
check("vibe: full = --auto-approve + resume", "--auto-approve" in ca and ca[ca.index("--resume") + 1] == "s-9")
check("vibe: logout gỡ khoá", vibe_cli.logout().get("ok") and not vibe_cli.auth_status().get("connected"))
check("vibe: dán API key", vibe_cli.dat_api_key("A" * 32).get("ok") and vibe_cli.auth_status().get("connected"))
vibe_cli.logout()

# ================================================================= MCP trong brain
BR = TMP / "brain"
BR.mkdir()
hdr = {"Authorization": "Bearer tok", "X-Javis-Mode": "auto", "X-Javis-Vault": str(BR)}
for mod, tuong_doi in ((kiro_cli, ".kiro/settings/mcp.json"), (cursor_cli, ".cursor/mcp.json"),
                       (vibe_cli, ".vibe/config.toml")):
    p = mod.ghi_mcp_settings(BR, mod.hub_entry("http://127.0.0.1:8000/mcp/hub", hdr))
    tt = mod.trang_thai_mcp(BR)
    check(f"{mod.ID}: ghi MCP đúng chỗ ({tuong_doi})", p == str(BR / tuong_doi))
    check(f"{mod.ID}: đọc lại thấy javis + 3 header", tt.get("co_javis") and tt.get("so_header") == 3
          and tt.get("url") == "http://127.0.0.1:8000/mcp/hub")
    mod.ghi_mcp_settings(BR, None)
    check(f"{mod.ID}: hub tắt thì gỡ entry", not mod.trang_thai_mcp(BR).get("co_javis"))
# Giữ server khác của người dùng, và KHÔNG ghi đè file hỏng.
(BR / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {"cua-toi": {"url": "https://x"}}}))
cursor_cli.ghi_mcp_settings(BR, cursor_cli.hub_entry("http://h/mcp", hdr))
d = json.loads((BR / ".cursor/mcp.json").read_text())
check("cursor: giữ server khác của người dùng", set(d["mcpServers"]) == {"cua-toi", "javis"})
(BR / ".kiro/settings/mcp.json").write_text("{hỏng")
check("kiro: file MCP hỏng thì KHÔNG ghi đè", kiro_cli.ghi_mcp_settings(BR, {"url": "x"}) is None
      and (BR / ".kiro/settings/mcp.json").read_text() == "{hỏng")
(BR / ".vibe/config.toml").write_text('active_model = "x"\n\n[[mcp_servers]]\nname = "cua-toi"\nurl = "https://y"\n')
vibe_cli.ghi_mcp_settings(BR, vibe_cli.hub_entry("http://h/mcp", hdr))
import tomllib  # noqa: E402
v = tomllib.loads((BR / ".vibe/config.toml").read_text())
check("vibe: TOML giữ khoá cũ + server khác, thêm javis",
      v.get("active_model") == "x" and [x["name"] for x in v["mcp_servers"]] == ["cua-toi", "javis"]
      and v["mcp_servers"][1]["headers"]["X-Javis-Mode"] == "auto")

# ================================================================= đăng ký khắp app
src = (Path(SERVER) / "main.py").read_text(encoding="utf-8")
for pid in chung.NAO:
    check(f"main: {pid} có trong PROVIDER_DEFS", f'"id": "{pid}"' in src)
check("main: AGENT_PROVIDERS có đủ ba", all(f'"{p}"' in src.split("AGENT_PROVIDERS = (")[1].split(")")[0]
                                            for p in chung.NAO))
for r in ("status", "install", "install-poll", "login-start", "login-poll", "logout", "api-key", "check"):
    check(f"main: route /nao-cli/{{pid}}/{r}", f'"/nao-cli/{{pid}}/{r}"' in src)
import aux_engine  # noqa: E402
check("aux: ba bộ não dựng được engine nền", set(aux_engine.NAO_CLI_MOI) == set(chung.NAO))
import types  # noqa: E402
cl = types.SimpleNamespace(cwd=str(BR), tag="t", system_prompt="sys", javis_vault=str(BR), javis_mode="auto")
e = aux_engine._build_nao_cli({"provider": "vibe-cli", "model": "m"}, cl, "auto", "t")
check("aux: _build_nao_cli trả VibeCLI đúng mode/model", isinstance(e, vibe_cli.VibeCLI) and e.mode == "auto"
      and e.model == "m")
import sessions  # noqa: E402
check("sessions: mỗi bộ não một cột mạch riêng",
      all(sessions.SessionStore._MACH_NATIVE.get(p) for p in chung.NAO)
      and len({sessions.SessionStore._MACH_NATIVE[p] for p in chung.NAO}) == 3)
ep = (Path(ROOT) / "docker/entrypoint.sh").read_text(encoding="utf-8")
check("docker: .kiro .cursor .vibe sống qua cập nhật", all(x in ep.split("for d in")[1].split(";")[0]
                                                         for x in (".kiro", ".cursor", ".vibe")))

for mod in (kiro_cli, cursor_cli, vibe_cli):
    mod.huy_dang_nhap()

print()
if _fails:
    print(f"{len(_fails)} FAIL")
    sys.exit(1)
print("Tất cả OK")
