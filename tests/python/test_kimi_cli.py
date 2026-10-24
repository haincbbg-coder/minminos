# -*- coding: utf-8 -*-
"""Bộ não Kimi Code (gói hội viên Kimi): cài, đăng nhập trên trang Models, một lượt chat.

    python tests/python/test_kimi_cli.py     (KHÔNG mạng)

Chạy một `kimi` GIẢ (script Python) đóng đúng những vai ĐÃ ĐO trên binary thật 2.3.1
(xem đầu server/kimi_cli.py):
  - `kimi login --region R` in link + mã ra stderr, ghi file phiên, in "Logged in to ...".
  - bản có menu chọn nền tảng (như `/login` tương tác) in menu rồi CHỜ phím: MinMin phải tự
    bấm xuống đúng mục "Kimi Code (kimi.ai/code)" rồi Enter.
  - link dài vài trăm ký tự: bản giả bẻ dòng nếu màn hình hẹp hơn link (pty phải rộng).
  - `kimi -p ... --output-format stream-json` in tin nhắn kiểu OpenAI, kèm một dòng chữ trần
    lọt ra từ lệnh Bash (đo được trên bản thật), rồi `session.resume_hint`.
  - lỗi chưa đăng nhập / hết quota: `error: failed to run prompt: ...` ở stderr, mã 1.
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


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  -> {extra!r}"))
    if not cond:
        _fails.append(name)


TMP = Path(tempfile.mkdtemp(prefix="kimi-gia-"))
HOME = TMP / "home"
HOME.mkdir()
os.environ["HOME"] = str(HOME)
os.environ["USERPROFILE"] = str(HOME)
os.environ.pop("KIMI_CODE_HOME", None)
KH = HOME / ".kimi-code"

LINK = ("https://www.kimi.ai/code/authorize_device?user_code=WXYZ-9876&client_id=17e5f671-d194-4dfb-"
        "9706-5516cb48c098&state=" + "a1b2c3d4" * 30)

GIA = textwrap.dedent(f'''\
    #!{sys.executable}
    import json, os, sys, time, shutil
    KH = os.path.join(os.environ["HOME"], ".kimi-code")
    a = sys.argv[1:]
    if a[:1] == ["--version"]:
        print("2.3.1"); sys.exit(0)
    if a[:1] == ["--help"]:
        print("Usage: kimi [options] [command]")
        print("  -m, --model <model>  -p, --prompt <prompt>  --output-format <format> stream-json")
        print("  -S, --session [id]  --agent-file <path>")
        if os.environ.get("KIMI_GIA_KHONG_LOGIN") != "1":
            print("  login [options]  Authenticate with Kimi Code CLI via the device-code flow.")
        print("  --region <region>")
        sys.exit(0)
    LINK = {LINK!r}

    def in_link():
        cot = 0
        try:
            cot = os.get_terminal_size(sys.stderr.fileno()).columns
        except OSError:
            cot = 0
        dong = "Opening browser for Kimi device login: " + LINK
        # Màn hình hẹp hơn dòng thì bẻ (như TUI thật); pty 1000 cột thì không.
        if cot and cot < len(dong):
            for i in range(0, len(dong), cot):
                sys.stderr.write(dong[i:i + cot] + "\\n")
        else:
            sys.stderr.write(dong + "\\n")
        sys.stderr.write("If the browser did not open, paste the URL above and enter code: WXYZ-9876\\n")
        sys.stderr.write("Code expires in 600s.\\nWaiting for authorization to complete...\\n")
        sys.stderr.flush()

    def ghi_phien(vung):
        os.makedirs(os.path.join(KH, "credentials"), exist_ok=True)
        json.dump({{"access_token": "AT" * 30, "refresh_token": "RT" * 30, "expires_at": 1}},
                  open(os.path.join(KH, "credentials", "kimi-code.json"), "w"))
        host = "https://auth.kimi.ai" if vung == "global" else "https://auth.kimi.com"
        open(os.path.join(KH, "config.toml"), "w").write(
            'default_model = "kimi-code/kimi-for-coding"\\n\\n'
            '[providers."managed:kimi-code"]\\ntype = "kimi"\\n\\n'
            '[providers."managed:kimi-code".oauth]\\nstorage = "file"\\noauth_host = "' + host + '"\\n\\n'
            '[models."kimi-code/k3"]\\nprovider = "managed:kimi-code"\\nmodel = "k3"\\n\\n'
            '[models."kimi-code/kimi-for-coding"]\\nprovider = "managed:kimi-code"\\nmodel = "kimi-for-coding"\\n')
        open(os.path.join(KH, "vung_da_chon"), "w").write(vung)

    def menu_va_chon():
        # Giống `/login` tương tác: menu nền tảng, mục 1 đang trỏ, chờ phím.
        sys.stdout.write("Select a platform\\n")
        sys.stdout.write("\\u276f Kimi Code (kimi.com/code)\\n")
        sys.stdout.write("  Kimi Code (kimi.ai/code)\\n")
        sys.stdout.write("  Kimi Platform (API key \\u00b7 platform.kimi.ai)\\n")
        sys.stdout.flush()
        import tty, termios
        fd = sys.stdin.fileno()
        try:
            cu = termios.tcgetattr(fd); tty.setraw(fd)
        except Exception:
            cu = None
        chon, buf = 0, ""
        while True:
            c = os.read(fd, 1).decode("latin-1")
            buf += c
            if buf.endswith("\\x1b[B"):
                chon = min(chon + 1, 2); buf = ""
            elif buf.endswith("\\x1b[A"):
                chon = max(chon - 1, 0); buf = ""
            elif c in "\\r\\n":
                break
        if cu:
            termios.tcsetattr(fd, termios.TCSADRAIN, cu)
        return ["mainland-cn", "global", "api"][chon]

    if a[:1] == ["login"] or a == []:
        vung = a[a.index("--region") + 1] if "--region" in a else "mainland-cn"
        if a == []:
            # bản không có lệnh login: chờ người dùng gõ /login rồi hiện menu
            line = ""
            while "/login" not in line:
                line += os.read(0, 64).decode("utf-8", "replace")
        if a == [] or os.environ.get("KIMI_GIA_MENU") == "1":
            vung = menu_va_chon()
            if vung == "api":
                sys.stdout.write("Enter API key:\\n"); sys.stdout.flush(); time.sleep(60); sys.exit(1)
        in_link()
        time.sleep(1.0)
        ghi_phien(vung)
        sys.stderr.write("Logged in to managed:kimi-code.\\n")
        if a == []:
            time.sleep(60)   # TUI không tự thoát
        sys.exit(0)
    if "-p" in a:
        che_do = os.environ.get("KIMI_GIA_CHAT", "ok")
        print(json.dumps({{"role": "meta", "type": "system.version", "version": "2.3.1"}}), flush=True)
        if che_do == "chua_dang_nhap":
            sys.stderr.write("error: failed to run prompt: No model configured. Run `kimi` and use /login to sign in, then retry; or set default_model in config.toml.\\n")
            sys.stderr.write("See log: /x/kimi-code.log\\n"); sys.exit(1)
        if che_do == "quota":
            sys.stderr.write("Warning: this folder is not trusted; skipped 1 project-level MCP server: javis (http: x).\\n")
            sys.stderr.write("error: failed to run prompt: provider.api_error: 429 You exceeded your current quota\\n"); sys.exit(1)
        json.dump({{"argv": a}}, open(os.path.join(KH, "argv_cuoi.json"), "w"))
        sid = a[a.index("-S") + 1] if "-S" in a else "session_11111111-2222-3333-4444-555555555555"
        print(json.dumps({{"role": "assistant", "content": "Để em xem.", "tool_calls": [
            {{"type": "function", "id": "call_1", "function": {{"name": "Bash", "arguments": "{{\\"command\\": \\"echo hi\\"}}"}}}}]}}), flush=True)
        print("hi", flush=True)       # lệnh con lọt ra stdout, như bản thật
        print(json.dumps({{"role": "tool", "tool_call_id": "call_1", "content": "hi\\n"}}), flush=True)
        print(json.dumps({{"role": "assistant", "content": "Xin chào bố"}}), flush=True)
        d = os.path.join(KH, "sessions", "ws_1", sid, "agents", "main")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "wire.jsonl"), "a") as f:
            f.write(json.dumps({{"type": "usage.record", "usage": {{"inputOther": 60, "output": 5, "inputCacheRead": 40, "inputCacheCreation": 0}}}}) + "\\n")
            f.write(json.dumps({{"type": "usage.record", "usage": {{"inputOther": 10, "output": 3, "inputCacheRead": 100, "inputCacheCreation": 0}}}}) + "\\n")
        print(json.dumps({{"role": "meta", "type": "session.resume_hint", "session_id": sid,
                          "command": "kimi -r " + sid}}), flush=True)
        sys.exit(0)
    sys.exit(2)
''')
BIN = TMP / "bin"
BIN.mkdir()
KIMI = BIN / "kimi"
KIMI.write_text(GIA, encoding="utf-8")
KIMI.chmod(0o755)
os.environ["JAVIS_KIMI_BIN"] = str(KIMI)

import kimi_cli as k  # noqa: E402

POSIX = os.name != "nt"

# ---- 1. Tìm binary, loại bản cũ ----
check("tìm thấy binary giả", k.find_kimi_cli() == str(KIMI), k.find_kimi_cli())
CU = BIN / "kimi-cu"
CU.write_text(f"#!{sys.executable}\nprint('kimi, version 1.52.0')\n"
              "print('kimi-cli is no longer maintained. Please use the new Kimi Code CLI.')\n",
              encoding="utf-8")
CU.chmod(0o755)
check("nhận ra bản kimi-cli cũ của PyPI", k._la_ban_cu(str(CU)) and not k._la_ban_cu(str(KIMI)))
os.environ["JAVIS_KIMI_BIN"] = str(CU)
_goc_tim = k.tim_binary
k.tim_binary = lambda ten: None
check("chỉ có bản cũ thì KHÔNG coi là đã cài", k.find_kimi_cli() is None or k.find_kimi_cli() != str(CU))
check("...và thẻ nói rõ là bản cũ", "CŨ" in k.auth_status().get("error", ""), k.auth_status())
os.environ["JAVIS_KIMI_BIN"] = str(KIMI)
k.tim_binary = _goc_tim

check("chưa đăng nhập", not k.auth_status()["connected"])
check("model dự phòng khi chưa đăng nhập", k.list_models() == [k.MODEL_DU_PHONG], k.list_models())


def dang_nhap(vung, env=None, cho=25):
    for kk in ("KIMI_GIA_MENU", "KIMI_GIA_KHONG_LOGIN"):
        os.environ.pop(kk, None)
    for kk, v in (env or {}).items():
        os.environ[kk] = v
    k._HELP_CACHE.update(path=None, text="", ts=0.0)
    for f in (KH / "credentials").glob("*.json") if (KH / "credentials").exists() else []:
        f.unlink()
    r = k.login_start(vung, cho_giay=15)
    han = time.time() + cho
    d = {}
    while time.time() < han:
        d = k.login_trang_thai()
        if d["connected"] or not d["dang_cho"]:
            break
        time.sleep(0.3)
    k.huy_dang_nhap()
    return r, d


if POSIX:
    # ---- 2. `kimi login --region global`: link dài đủ + mã ----
    r, d = dang_nhap("global")
    check("login-start trả link đăng nhập ĐỦ (không cụt dù dài)", r.get("url") == LINK,
          (len(r.get("url") or ""), len(LINK)))
    check("bóc được mã thiết bị", r.get("code") == "WXYZ-9876", r.get("code"))
    check("hỏi lặp tới khi đã đăng nhập", d.get("connected") is True, d)
    check("đúng vùng đã chọn được truyền xuống CLI",
          (KH / "vung_da_chon").read_text() == "global")
    check("nhật ký không lộ token", not any("ATAT" in x or "RTRT" in x for x in d.get("nhat_ky", [])))
    st = k.auth_status()
    check("auth_status đọc file phiên: đã đăng nhập, vùng kimi.ai",
          st["connected"] and st["region"] == "global", st)
    check("model lấy từ config.toml, model mặc định đứng đầu",
          k.list_models() == ["kimi-code/kimi-for-coding", "kimi-code/k3"], k.list_models())

    # ---- 3. Menu chọn nền tảng: tự bấm xuống đúng mục OAuth của vùng ----
    r, d = dang_nhap("global", {"KIMI_GIA_MENU": "1"})
    check("menu: tự chọn 'Kimi Code (kimi.ai/code)' (mũi tên xuống 1 lần)",
          d.get("connected") and (KH / "vung_da_chon").read_text() == "global",
          ((KH / "vung_da_chon").read_text() if (KH / "vung_da_chon").exists() else None, d.get("nhat_ky")))
    r, d = dang_nhap("mainland-cn", {"KIMI_GIA_MENU": "1"})
    check("menu: vùng kimi.com thì giữ mục đang trỏ, Enter",
          d.get("connected") and (KH / "vung_da_chon").read_text() == "mainland-cn")
    # Bản không có lệnh `login`: MinMin vào giao diện tương tác, gõ /login, chọn menu.
    r, d = dang_nhap("global", {"KIMI_GIA_KHONG_LOGIN": "1"})
    check("bản thiếu lệnh login: gõ /login + chọn menu + bóc link",
          r.get("url") == LINK and d.get("connected"), (r.get("error"), d.get("nhat_ky")))
    k.huy_dang_nhap()
    for kk in ("KIMI_GIA_MENU", "KIMI_GIA_KHONG_LOGIN"):
        os.environ.pop(kk, None)
    k._HELP_CACHE.update(path=None, text="", ts=0.0)

# Đăng nhập giả bằng tay cho phần còn lại (cũng chạy trên Windows).
(KH / "credentials").mkdir(parents=True, exist_ok=True)
(KH / "credentials" / "kimi-code.json").write_text(json.dumps({"access_token": "x" * 40,
                                                               "refresh_token": "y" * 40}))
check("đã đăng nhập (file phiên có token)", k.auth_status()["connected"])

# ---- 4. Một lượt chat: dịch sự kiện đúng ----
BRAIN = TMP / "brain"
BRAIN.mkdir()


async def chay(prompt, sid=None, mode="full", ins="Bạn là MinMin."):
    c = k.KimiCLI(cwd=str(BRAIN), instructions=ins, model="kimi-code/k3")
    c.mode = mode
    c.session_id = sid
    out = [ev async for ev in c.query(prompt)]
    return c, out


c, out = asyncio.run(chay("chào"))
loai = [e["type"] for e in out]
check("lượt chat ra tool_call -> tool_result -> usage -> final", loai == ["tool_call", "tool_result", "usage", "final"], out)
tc = out[0]
check("tool_call dịch đúng tên + input", tc["name"] == "Bash" and tc["input"] == {"command": "echo hi"}, tc)
check("final là câu trả lời, KHÔNG dính lời dẫn hay dòng 'hi' lọt ra",
      out[-1]["content"] == "Xin chào bố", out[-1])
u = out[2]
check("usage: input của bước cuối, output cộng dồn",
      u["input_tokens"] == 110 and u["output_tokens"] == 8 and u["cached"] == 100, u)
check("đọc lại id phiên từ resume_hint", c.session_id == "session_11111111-2222-3333-4444-555555555555")
argv = json.loads((KH / "argv_cuoi.json").read_text())["argv"]
check("lượt mới: --agent-file + stream-json + -m", "--agent-file" in argv and "stream-json" in argv
      and argv[argv.index("-m") + 1] == "kimi-code/k3", argv)
check("file agent tạm đã được dọn", not Path(argv[argv.index("--agent-file") + 1]).exists())
fa = k.file_agent("suggest", "Hệ thống")
check("mức suggest cấm Bash/Write/Edit trong file agent",
      all(x in fa.split("disallowedTools:")[1].split("\n")[0] for x in ("Bash", "Write", "Edit")), fa)
check("mức full chỉ cấm AskUserQuestion", "disallowedTools: AskUserQuestion\n" in k.file_agent("full", "x"))
check("mode lạ rơi về nấc chặt nhất", k.tool_cam("bừa") == k.tool_cam("suggest"))

c2, out2 = asyncio.run(chay("lần hai", sid=c.session_id))
argv = json.loads((KH / "argv_cuoi.json").read_text())["argv"]
check("lượt sau nối phiên bằng -S, không kèm --agent-file",
      "-S" in argv and "--agent-file" not in argv, argv)
check("phiên tạo ở full KHÔNG được nối ở mức suggest", not k.noi_lai_duoc(c.session_id, "suggest"))
check("phiên lạ (không rõ mức) chỉ nối ở full",
      k.noi_lai_duoc("session_la", "full") and not k.noi_lai_duoc("session_la", "auto"))

# ---- 5. Lỗi ra câu tiếng Việt rõ ----
os.environ["KIMI_GIA_CHAT"] = "chua_dang_nhap"
_, out = asyncio.run(chay("chào"))
loi = [e for e in out if e["type"] == "error"]
check("chưa đăng nhập -> bảo bấm Đăng nhập Kimi trên trang Models",
      loi and "chưa đăng nhập" in loi[0]["content"] and "Đăng nhập Kimi" in loi[0]["content"], out)
check("chưa đăng nhập: không kèm final rỗng", not any(e["type"] == "final" for e in out))
os.environ["KIMI_GIA_CHAT"] = "quota"
_, out = asyncio.run(chay("chào"))
loi = [e for e in out if e["type"] == "error"]
check("hết quota -> câu tiếng Việt về quota lập trình của gói, bỏ dòng Warning",
      loi and "quota lập trình" in loi[0]["content"] and "Warning" not in loi[0]["content"], out)
import limit_learner  # noqa: E402
hit = limit_learner.parse_subscription_limit(loi[0]["content"], engine_hint="kimi-cli") if loi else None
check("câu hết quota được bộ nhận dạng hết lượt bắt (thẻ chờ trong khung chat)",
      hit is not None and hit.engine == "kimi-cli", hit)
os.environ.pop("KIMI_GIA_CHAT", None)

# ---- 6. MCP: ghi vào brain, đọc lại, giữ server khác ----
mp = k.mcp_config_path(BRAIN)
mp.parent.mkdir(parents=True, exist_ok=True)
mp.write_text(json.dumps({"mcpServers": {"khac": {"command": "x"}}}))
k.ghi_mcp_settings(BRAIN, k.hub_entry("http://127.0.0.1:8000/mcp", {"Authorization": "Bearer t"}))
d = json.loads(mp.read_text())
check("entry javis đúng schema http + giữ server khác",
      d["mcpServers"]["javis"]["transport"] == "http" and "khac" in d["mcpServers"], d)
check("trang_thai_mcp đọc lại thấy javis", k.trang_thai_mcp(BRAIN)["co_javis"])
mp.write_text("{hỏng")
check("file hỏng thì KHÔNG ghi đè", k.ghi_mcp_settings(BRAIN, k.hub_entry("http://x/mcp")) is None
      and mp.read_text() == "{hỏng")
check("môi trường bật trust workspace (để CLI đọc mcp.json của brain)",
      k._moi_truong().get("KIMI_CODE_TRUST_WORKSPACE") == "1"
      and k._moi_truong().get("KIMI_CODE_NO_AUTO_UPDATE") == "1")

# ---- 7. Ngắt ----
r = k.logout()
check("Ngắt xoá file phiên -> chưa đăng nhập", r["ok"] and not k.auth_status()["connected"], r)

# ---- 8. Đăng ký provider đủ chỗ ----
src_main = (SERVER / "main.py").read_text(encoding="utf-8")
for mau in ('"id": "kimi-cli"', '@app.post("/kimi/login-start")', '@app.post("/kimi/install")',
            '@app.post("/kimi/check")', 'elif prov == "kimi-cli":', 'if prov == "kimi-cli":',
            '"kimi-cli",\n                   "antigravity-cli"'):
    check("main.py có " + mau.split("\n")[0], mau in src_main)
src_aux = (SERVER / "aux_engine.py").read_text(encoding="utf-8")
check("aux_engine dựng được agent Kimi", "_build_kimi" in src_aux and "KIMI_CLI" in src_aux)
ep = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
check("entrypoint giữ ~/.kimi-code qua lần cập nhật Docker", ".kimi-code" in ep)
check("không có ký tự gạch dài trong module", "—" not in (SERVER / "kimi_cli.py").read_text(encoding="utf-8"))

print()
if _fails:
    print(f"{len(_fails)} FAIL")
    sys.exit(1)
print("ALL PASS")
