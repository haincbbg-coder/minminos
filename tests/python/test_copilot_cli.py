# -*- coding: utf-8 -*-
"""Bộ não GitHub Copilot CLI (`copilot`, gói Copilot) - chạy với binary GIẢ, KHÔNG mạng.

    python tests/python/test_copilot_cli.py

Binary giả đóng đúng những vai ĐÃ ĐO trên `@github/copilot` 1.0.103 (xem đầu server/copilot_cli.py):
- `copilot login --device-code` in "To authenticate, visit <url> and enter code <mã>" (ở đây in
  bằng `\\r` không xuống dòng cho khó), kèm chuỗi OSC 52, rồi HỎI "Store token in plaintext config
  file? (y/N)" và chỉ lưu token khi được trả lời y - đúng ca container không có keychain.
- `config.json` mở đầu bằng dòng chú thích `//` (JSONC).
- `-p` + `--output-format json` in JSONL theo sơ đồ `schemas/session-events.schema.json` của gói.
- Chưa đăng nhập: thoát 1, stdout rỗng, stderr "Error: No authentication information found."
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        if extra is not None:
            print("     ->", str(extra)[:600])
        _fails.append(name)


TMP = Path(tempfile.mkdtemp(prefix="copilot-gia-"))
HOME = TMP / "home"
(HOME / ".copilot").mkdir(parents=True)
os.environ["COPILOT_HOME"] = str(HOME / ".copilot")

GIA = textwrap.dedent(f'''\
    #!{sys.executable}
    import json, os, sys, time
    H = os.environ["COPILOT_HOME"]
    CFG = os.path.join(H, "config.json")
    a = sys.argv[1:]
    open(os.path.join({str(TMP)!r}, "argv.json"), "w").write(json.dumps(a))
    if a[:1] == ["--help"]:
        print("Usage: copilot [OPTIONS] [COMMAND]")
        for c in ("-p, --prompt <text>", "--model <model>", "--allow-all-tools", "--allow-all-paths",
                  "--allow-all-urls", "--deny-tool [<tools>...]", "--output-format <format>",
                  "--no-auto-update", "--no-ask-user", "--no-color", "--disable-builtin-mcps",
                  "--additional-mcp-config <json>", "--session-id <id>"):
            print("      " + c)
        print("      --reasoning-effort <level>")
        print("          Set the reasoning effort level [possible values: none, minimal, low, medium, high, xhigh, max]")
        sys.exit(0)
    if a[:2] == ["help", "config"]:
        print("  `logLevel`: log level.")
        print("")
        print("  `model`: AI model to use for Copilot CLI; can be changed with /model.")
        for m in ("claude-sonnet-5", "gpt-5.4", "gemini-3.8-flash", "grok-4.7"):
            print('    - "' + m + '"')
        print("")
        print("  `contextTier`: context window tier.")
        sys.exit(0)
    if a[:1] == ["login"]:
        sys.stdout.write("\\x1b]52;c;QUJDRC0xMjM0\\x07")
        sys.stdout.write("To authenticate, visit https://github.com/login/device and enter code WXYZ-9876\\r")
        sys.stdout.write("Waiting for authorization...\\r"); sys.stdout.flush()
        time.sleep(0.8)
        sys.stdout.write("System keychain unavailable. Store token in plaintext config file? (y/N) ")
        sys.stdout.flush()
        tl = sys.stdin.readline().strip().lower()
        if tl not in ("y", "yes"):
            print("Login succeeded, but the token was not saved."); sys.exit(1)
        tok = "gho_" + "S" * 36
        open(CFG, "w").write("// User settings belong in settings.json.\\n// managed\\n" + json.dumps({{
            "firstLaunchAt": "x", "authTokens": {{"https://github.com:bo:github": {{"token": tok}}}},
            "loggedInUsers": [{{"host": "https://github.com", "login": "bo"}}],
            "lastLoggedInUser": {{"host": "https://github.com", "login": "bo"}}}}))
        print("Signed in successfully as bo (https://github.com). token=" + tok)
        sys.exit(0)
    # ---- chế độ prompt ----
    try:
        d = json.loads("\\n".join(x for x in open(CFG).read().splitlines() if not x.lstrip().startswith("//")))
    except Exception:
        d = {{}}
    if not d.get("loggedInUsers"):
        print("Error: No authentication information found.", file=sys.stderr); sys.exit(1)
    prompt = a[a.index("-p") + 1] if "-p" in a else sys.stdin.read()
    sid = a[a.index("--session-id") + 1] if "--session-id" in a else "tu-sinh"
    def ev(t, **data): print(json.dumps({{"type": t, "data": data, "id": "x", "ephemeral": False}}), flush=True)
    ev("session.start", sessionId=sid, version=1, producer="copilot", copilotVersion="1.0.103", startTime="t")
    if os.environ.get("CP_GIA_CHINH_SACH") == "1":
        ev("session.warning", warningType="policy", message="Third-party MCP servers are disabled by your organization's Copilot policy. Only built-in servers are available.")
        ev("session.warning", warningType="mcp", message="1 MCP servers were blocked by policy: 'javis'")
    else:
        ev("session.mcp_server_status_changed", serverName="javis", status="connected")
    if os.environ.get("CP_GIA_HET_LUOT") == "1":
        ev("session.error", errorType="rate_limit", message="You've reached your weekly rate limit.")
        sys.exit(1)
    ev("assistant.message", messageId="m1", content="Để em xem số liệu.", toolRequests=[])
    ev("tool.execution_start", toolCallId="c1", toolName="javis-hoa_don", mcpServerName="javis",
       mcpToolName="hoa_don_tong_hop", arguments={{"thang": 9}})
    ev("tool.execution_complete", toolCallId="c1", success=True, result={{"content": "12 hoá đơn"}})
    ev("assistant.message_delta", messageId="m2", deltaContent="Tháng 9 ")
    ev("assistant.message_delta", messageId="m2", deltaContent="có 12 hoá đơn.")
    ev("assistant.message", messageId="m2", content="Tháng 9 có 12 hoá đơn. (prompt " + str(len(prompt)) + ")")
    ev("assistant.usage", model="auto", inputTokens=1200, outputTokens=30, cacheReadTokens=800)
    ev("session.shutdown", shutdownType="routine", totalApiDurationMs=1, sessionStartTime=1, codeChanges={{}}, modelMetrics={{}})
''')
BIN = TMP / "copilot"
BIN.write_text(GIA, encoding="utf-8")
BIN.chmod(0o755)
os.environ["JAVIS_COPILOT_BIN"] = str(BIN)

import copilot_cli as cp  # noqa: E402


def argv_lan_cuoi() -> list:
    return json.loads((TMP / "argv.json").read_text())


# 1. Dò cờ, model, effort, quyền ------------------------------------------------------------
check("tìm thấy binary qua JAVIS_COPILOT_BIN", cp.find_copilot_cli() == str(BIN))
ms = cp.list_models() or []
check("model lấy từ `copilot help config`, `auto` đứng đầu",
      ms[:1] == ["auto"] and "claude-sonnet-5" in ms and "grok-4.7" in ms and "contextTier" not in " ".join(ms), ms)
check("effort: giá trị CLI khai thì truyền", cp.co_effort("xhigh") == ["--reasoning-effort", "xhigh"])
check("effort: giá trị lạ thì KHÔNG truyền (đo: CLI thoát 'invalid value')", cp.co_effort("ultra") == [])
q = cp.permission_cho_mode("suggest")
check("suggest: chặn shell + ghi file bằng dạng có dấu bằng",
      "--allow-all-tools" in q and "--deny-tool=shell" in q and "--deny-tool=write" in q, q)
check("auto: chỉ chặn shell", cp.permission_cho_mode("auto").count("--deny-tool=shell") == 1
      and "--deny-tool=write" not in cp.permission_cho_mode("auto"))
f = cp.permission_cho_mode("full")
check("full: không chặn, bỏ rào đường dẫn", "--allow-all-paths" in f and not any("deny" in x for x in f), f)
check("mode lạ về nấc chặt nhất", cp.permission_cho_mode("toan-quyen") == q)

# 2. Môi trường: GH_TOKEN/GITHUB_TOKEN bị gỡ (đo: CLI ưu tiên chúng hơn phiên đã đăng nhập) ----
os.environ["GITHUB_TOKEN"] = "ghp_" + "x" * 36
os.environ["GH_TOKEN"] = "ghp_" + "y" * 36
env = cp._moi_truong()
check("gỡ GITHUB_TOKEN và GH_TOKEN khỏi tiến trình copilot",
      "GITHUB_TOKEN" not in env and "GH_TOKEN" not in env and env.get("COPILOT_AUTO_UPDATE") == "false")
os.environ.pop("GITHUB_TOKEN"); os.environ.pop("GH_TOKEN")

# 3. Chưa đăng nhập ---------------------------------------------------------------------------
st = cp.auth_status()
check("chưa đăng nhập: auth_status báo rõ", st["connected"] is False and "Đăng nhập GitHub" in st["error"], st)
k = cp.kiem_tra_nhanh(timeout=20)
check("chưa đăng nhập: Kiểm tra lại ra câu tiếng Việt", k.get("ok") is False
      and "chưa đăng nhập" in (k.get("error") or ""), k)


async def chay(g, prompt):
    ra = []
    async for e in g.query(prompt):
        ra.append(e)
    return ra

loi = asyncio.run(chay(cp.CopilotCLI(cwd=str(TMP)), "chào"))
check("chưa đăng nhập: lượt chat ra MỘT lỗi tiếng Việt, không bong bóng rỗng",
      [e["type"] for e in loi] == ["error"] and "Đăng nhập GitHub" in loi[0]["content"], loi)

# 4. Đăng nhập device code trong pty: bóc link + mã (in bằng \r), tự trả lời y ------------------
if os.name != "nt":
    r = cp.login_start(cho_giay=10)
    check("login_start trả link GitHub", r.get("ok") and r.get("url") == "https://github.com/login/device", r)
    check("và mã (CLI in bằng \\r, có chuỗi OSC 52 xen trước)", r.get("code") == "WXYZ-9876", r)
    import time
    t = {}
    for _ in range(40):
        t = cp.login_trang_thai()
        if t.get("connected") or not t.get("dang_cho"):
            break
        time.sleep(0.25)
    check("tự trả lời câu hỏi lưu plaintext -> đăng nhập xong", t.get("connected") is True, t)
    check("đọc được tài khoản từ config.json (JSONC có dòng //)", t.get("account") == "bo", t)
    nk = " ".join(t.get("nhat_ky") or [])
    check("nhật ký có ghi MinMin đã trả lời y", "trả lời y" in nk, nk)
    check("nhật ký che token gho_", "gho_SSSS" not in nk and "[đã che]" in nk, nk)
    check("nhật ký không còn mã OSC 52 (base64 của mã)", "QUJDRC0x" not in nk and "\x1b" not in nk, nk)
else:
    (HOME / ".copilot" / "config.json").write_text(
        '// x\n{"loggedInUsers":[{"login":"bo"}],"lastLoggedInUser":{"login":"bo"},"authTokens":{"a":{"token":"gho_' + "S" * 36 + '"}}}')

# 5. Một lượt chat dịch đúng sự kiện -----------------------------------------------------------
g = cp.CopilotCLI(cwd=str(TMP), model="claude-sonnet-5")
g.mode = "suggest"
evs = asyncio.run(chay(g, "tháng 9 có bao nhiêu hoá đơn"))
ty = [e["type"] for e in evs]
tc = [e for e in evs if e["type"] == "tool_call"]
check("tool MCP ra tên mcp__<server>__<tool>", tc and tc[0]["name"] == "mcp__javis__hoa_don_tong_hop"
      and tc[0]["input"] == {"thang": 9}, tc)
check("có tool_result thành công", any(e["type"] == "tool_result" and e["status"] == "completed" for e in evs))
us = [e for e in evs if e["type"] == "usage"]
check("usage đọc inputTokens/outputTokens/cacheReadTokens", us and us[0]["input_tokens"] == 1200
      and us[0]["output_tokens"] == 30 and us[0]["cached"] == 800, us)
fin = [e for e in evs if e["type"] == "final"]
check("final là assistant.message CUỐI (không gộp câu dạo đầu trước tool)",
      fin and fin[0]["content"].startswith("Tháng 9 có 12 hoá đơn.") and "Để em xem" not in fin[0]["content"], fin)
av = argv_lan_cuoi()
check("lượt mới mang --session-id do MinMin cấp, và id đọc lại khớp",
      "--session-id" in av and av[av.index("--session-id") + 1] == g.session_id and len(g.session_id) == 36, av)
check("lượt chat mang --model, --output-format json, --deny-tool",
      "--model" in av and "json" in av and "--deny-tool=write" in av and "--disable-builtin-mcps" in av, av)
sid1 = g.session_id
asyncio.run(chay(g, "tiếp"))
av = argv_lan_cuoi()
check("lượt sau nối lại đúng mạch cũ", av[av.index("--session-id") + 1] == sid1, av)

# 6. Prompt dài đi qua stdin thay vì argv (trần MAX_ARG_STRLEN 128 KiB của Linux) -------------
dai = "x" * (cp._TRAN_ARGV + 10)
evs = asyncio.run(chay(cp.CopilotCLI(cwd=str(TMP)), dai))
av = argv_lan_cuoi()
fin = [e for e in evs if e["type"] == "final"]
check("prompt dài: không có -p trong argv, CLI nhận đủ qua stdin",
      "-p" not in av and fin and f"(prompt {len(dai)})" in fin[0]["content"], (av[-4:], fin))

# 7. Hết hạn mức: câu gốc tiếng Anh còn nguyên cho limit_learner ------------------------------
os.environ["CP_GIA_HET_LUOT"] = "1"
evs = asyncio.run(chay(cp.CopilotCLI(cwd=str(TMP)), "chào"))
os.environ.pop("CP_GIA_HET_LUOT")
er = [e for e in evs if e["type"] == "error"]
check("session.error -> một lỗi, không báo đôi với mã thoát", len(er) == 1, evs)
check("câu hết lượt giữ chữ gốc", er and "weekly rate limit" in er[0]["content"], er)
import limit_learner  # noqa: E402
nd = limit_learner.parse_subscription_limit(er[0]["content"], engine_hint="copilot-cli")
check("limit_learner nhận ra hạn mức tuần của Copilot",
      nd is not None and nd.scope == "tuần" and nd.engine == "copilot-cli", nd)
nd2 = limit_learner.parse_subscription_limit("You've hit the rate limit for this model.", "copilot-cli")
check("và hạn mức theo model", nd2 is not None and nd2.engine == "copilot-cli", nd2)

# 8. MCP: entry đúng hình dạng `copilot mcp add` ghi ra, ghi + đọc lại theo brain ---------------
brain = TMP / "brain"
brain.mkdir()
e = cp.hub_entry("http://127.0.0.1:7777/mcp", {"Authorization": "Bearer t", "X-Javis-Mode": "full"})
check("hub_entry: type http + url + headers + tools *", e == {"type": "http", "url": "http://127.0.0.1:7777/mcp",
      "tools": ["*"], "headers": {"Authorization": "Bearer t", "X-Javis-Mode": "full"}}, e)
fp = cp.ghi_mcp_settings(brain, e)
tm = cp.trang_thai_mcp(brain)
check("ghi vào <brain>/.copilot/mcp-config.json và đọc lại thấy javis",
      fp and fp.endswith(os.path.join(".copilot", "mcp-config.json")) and tm["co_javis"] and tm["so_header"] == 2, tm)
g2 = cp.CopilotCLI(cwd=str(TMP)); g2.mcp_file = fp
asyncio.run(chay(g2, "chào"))
av = argv_lan_cuoi()
check("lượt chat truyền --additional-mcp-config @<file>",
      "--additional-mcp-config" in av and av[av.index("--additional-mcp-config") + 1] == "@" + fp, av)
check("cờ hiện ra khi lỗi không lộ đường file MCP", all(not x.startswith("@") for x in cp._cat_args(["c"] + av)))
(brain / ".copilot" / "mcp-config.json").write_text("{hỏng")
check("file MCP hỏng thì KHÔNG ghi đè", cp.ghi_mcp_settings(brain, e) is None
      and (brain / ".copilot" / "mcp-config.json").read_text() == "{hỏng")
cp.ghi_mcp_settings(brain.parent / "brain2", e)

# 9. Kiểm tra lại: soát được chính sách chặn MCP bên thứ ba ------------------------------------
k = cp.kiem_tra_nhanh(timeout=20, mcp_file=fp if Path(fp).exists() else cp.ghi_mcp_settings(brain.parent / "brain3", e))
check("Kiểm tra lại: chạy thật được + hub connected", k.get("ok") and (k.get("mcp_lan_chay") or {}).get("status") == "connected", k)
os.environ["CP_GIA_CHINH_SACH"] = "1"
k = cp.kiem_tra_nhanh(timeout=20, mcp_file=str(brain.parent / "brain3" / ".copilot" / "mcp-config.json"))
os.environ.pop("CP_GIA_CHINH_SACH")
check("Kiểm tra lại: nói ra khi chính sách tắt MCP bên thứ ba", "TẮT MCP bên thứ ba" in (k.get("mcp_bi_chan") or ""), k)

# 10. Ngắt: gỡ đúng ba khoá, giữ phần còn lại và dòng chú thích -------------------------------
lo = cp.logout()
raw = (HOME / ".copilot" / "config.json").read_text()
check("logout ok", lo.get("ok") is True, lo)
check("logout gỡ token + tài khoản", "gho_" not in raw and "loggedInUsers" not in raw, raw)
check("logout giữ khoá khác và dòng chú thích //", raw.lstrip().startswith("//") and "firstLaunchAt" in raw, raw)
check("sau logout auth_status về chưa đăng nhập", cp.auth_status()["connected"] is False)
(HOME / ".copilot" / "config.json").write_text("// x\n{hỏng")
check("config.json hỏng thì logout KHÔNG ghi", cp.logout().get("ok") is False
      and (HOME / ".copilot" / "config.json").read_text() == "// x\n{hỏng")

# 11. Đăng ký đủ chỗ ---------------------------------------------------------------------------
src = (SERVER / "main.py").read_text(encoding="utf-8")
for x in ('"/copilot/install"', '"/copilot/install-poll"', '"/copilot/login-start"', '"/copilot/login-poll"',
          '"/copilot/logout"', '"/copilot/check"', '"id": "copilot-cli"', 'elif prov == "copilot-cli":',
          'if prov == "copilot-cli":', '_copilot_sub_stream', '"copilot-cli",\n'):
    check(f"main.py có {x.strip()}", x in src)
js = (ROOT / "dashboard" / "console.js").read_text(encoding="utf-8")
check("thẻ Models có nút Cài đặt / Đăng nhập GitHub / Ngắt / Kiểm tra lại",
      all(x in js for x in ("data-copilotinstall", "data-copilotlogin", "data-copilotdisc", "data-copilotcheck")))
ep = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
# Soi đúng dòng vòng lặp, không bám vị trí cuối: các bộ não sau còn nối thêm thư mục vào sau.
check("entrypoint giữ ~/.copilot qua cập nhật",
      any(d.startswith("for d in ") and " .copilot " in d + " " for d in ep.splitlines()))
gb = (SERVER / "git_brain.py").read_text(encoding="utf-8")
check("file MCP (có hub token) không vào bản sao lưu git", '"/.copilot/"' in gb)
import aux_engine  # noqa: E402
check("aux_engine có builder cho copilot-cli", hasattr(aux_engine, "_build_copilot"))
import sessions  # noqa: E402
check("sessions có cột mạch riêng", sessions.SessionStore._MACH_NATIVE.get("copilot-cli") == "copilot_session_id"
      if hasattr(sessions, "SessionStore") else "copilot_session_id" in (SERVER / "sessions.py").read_text(encoding="utf-8"))

cp.huy_dang_nhap()
if _fails:
    print(f"\n{len(_fails)} FAIL")
    sys.exit(1)
print("\nTất cả OK")
