"""Bộ não thứ 15: Meta Muse Code CLI (gói thuê bao Muse Code, binary `muse`).

    python tests/run.py muse_cli        (KHÔNG mạng, KHÔNG cần cài muse)

Những chỗ dễ hỏng, cùng khuôn test_grok_cli.py cộng hai chỗ riêng của engine này:

1. **Dựng argv của `muse exec`.** Mức quyền phải xuống đúng cờ (suggest chặn ghi + lệnh máy),
   cờ chung luôn có mặt (--json, --disable-request-user-input...), `off` thành `minimal` chứ
   KHÔNG BAO GIỜ `none` (CLI từ chối), prompt đi qua file.
2. **Dịch sự kiện JSONL CHƯA có tài liệu.** Ba hình dạng: MSP (`item/delta`...), kiểu Claude
   Code (`assistant`/`result`), kiểu chung. Delta rồi completed cùng một item KHÔNG được đếm
   chữ hai lần. Id phiên nhặt ở mọi tầng; usage nhặt ở mọi tầng.
3. **`--session-id` tự cấp bị từ chối -> thử lại đúng một lần không cờ.**
4. **MCP gộp vào `~/.config/muse/settings.json`:** giữ server khác của người dùng, có sao lưu,
   KHÔNG ghi đè file hỏng.
5. **Không đăng nhập / không binary** -> câu tiếng Việt làm theo được.

Test dựng một `muse` GIẢ bằng script Python nên chạy được ở CI không có binary thật.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-musetest-")
os.environ["JAVIS_MUSE_HOME"] = tempfile.mkdtemp(prefix="javis-musehome-")
os.environ.pop("META_API_KEY", None)

import muse_cli          # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name
          + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


def chay(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


_HELP = """Usage: muse exec [OPTIONS] [PROMPT]
      --prompt-file <PATH>
      --json
      --max-model-steps <N>
      --disable-reminders
      --disable-request-user-input
      --disable-write
      --disable-shell
      --session-id <UUID>
      --allow-workspace-switch
      --model <ID>
      --reasoning-effort <none|minimal|low|medium|high|xhigh|max|ultra>
      --approval-mode <on-request|untrusted|never>
      --disable-approval
      --disable-sandbox
      --yolo
      --trust-workspace
"""


def _nap_help(txt=_HELP, path="/fake/muse"):
    muse_cli.find_muse_cli = lambda: path
    muse_cli._HELP_CACHE.update(path=path, text=txt, ts=float("inf"))


# ============================================================
# 0. Không có binary
# ============================================================
muse_cli._HELP_CACHE.update(path=None, text="", ts=0.0)
_that_find = muse_cli.find_muse_cli
muse_cli.find_muse_cli = lambda: None
_a0 = muse_cli.auth_status()
check("chưa cài -> connected=False và câu lỗi kèm lệnh cài",
      _a0["connected"] is False and "install.sh" in _a0["error"], _a0)
check("chưa cài -> list_models trả None (thẻ không bày model giả)", muse_cli.list_models() is None)
check("chưa cài -> co_co fail-closed với cờ lạ, nhưng cờ CÓ TÀI LIỆU vẫn được tin",
      muse_cli.co_co("--khong-he-co") is False and muse_cli.co_co("--json") is True)
_ls = muse_cli.login_start(cho_giay=1)
check("chưa cài -> login_start báo lỗi rõ", _ls["ok"] is False and "install" in _ls["error"])
_nap_help()
check("đọc được --help thì nhận đúng cờ có thật", muse_cli.co_co("--yolo") is True)
check("list_models: bảng tĩnh, model mặc định đứng đầu, contributor xếp CUỐI",
      muse_cli.list_models()[0] == "muse-spark-1.3"
      and all("contributor" in m for m in muse_cli.list_models()[-2:]))


# ============================================================
# 1. Mức quyền -> cờ của `muse exec`
# ============================================================
def _co(mode):
    return muse_cli.permission_cho_mode(mode)


check("suggest CHẶN ghi file VÀ lệnh máy (CLI cưỡng chế, không phải lời hứa trong prompt)",
      {"--disable-write", "--disable-shell"} <= set(_co("suggest")))
check("suggest không hỏi duyệt (headless mà dừng hỏi là treo)",
      "--approval-mode" in _co("suggest") and _co("suggest")[_co("suggest").index("--approval-mode") + 1] == "never")
check("auto cho ghi file nhưng vẫn CHẶN lệnh máy",
      "--disable-shell" in _co("auto") and "--disable-write" not in _co("auto")
      and "--disable-approval" in _co("auto"))
check("full = --yolo + --disable-sandbox (Docker không có bubblewrap)",
      {"--yolo", "--disable-sandbox"} <= set(_co("full")) and "--disable-write" not in _co("full"))
for xau in ("", None, "FULL_QUYEN", "bậy bạ", "readonly"):
    check(f"CANARY: mode lạ ({xau!r}) rơi về nấc CHẶT NHẤT, không phải toàn quyền",
          {"--disable-write", "--disable-shell"} <= set(_co(xau)) and "--yolo" not in _co(xau))
check("viết hoa vẫn nhận", "--yolo" in _co("Full"))


# ============================================================
# 2. Effort: off -> minimal, KHÔNG BAO GIỜ none
# ============================================================
check("off -> --reasoning-effort minimal", muse_cli.co_effort("off") == ["--reasoning-effort", "minimal"])
check("CANARY: không bao giờ truyền `none` (CLI từ chối)",
      "none" not in " ".join(muse_cli.co_effort("off") + muse_cli.co_effort("none")))
for m, g in (("low", "low"), ("medium", "medium"), ("high", "high"), ("xhigh", "xhigh"),
             ("ultra", "ultra"), ("max", "max")):
    check(f"{m} -> {g}", muse_cli.co_effort(m) == ["--reasoning-effort", g])
check("mức lạ -> không truyền gì", muse_cli.co_effort("bậy") == [])
check("rỗng -> không truyền gì", muse_cli.co_effort("") == [])


# ============================================================
# 3. argv dựng ra
# ============================================================
_u = muse_cli.MuseCLI(cwd="/tmp", model="muse-spark-1.3", mode="suggest")
_u.cli_path = "/fake/muse"
_argv = _u._build_args(prompt_file="/tmp/p.txt", prompt_argv="dài" * 20000,
                       session_id="11111111-2222-4333-8444-555555555555")
check("lệnh con là `exec`", _argv[1] == "exec")
check("có --json (không có thì không đọc được sự kiện nào)", "--json" in _argv)
for co in ("--disable-request-user-input", "--disable-reminders", "--trust-workspace"):
    check(f"luôn có {co}", co in _argv)
check("có --max-model-steps 60",
      "--max-model-steps" in _argv and _argv[_argv.index("--max-model-steps") + 1] == "60")
check("model đi qua --model", _argv[_argv.index("--model") + 1] == "muse-spark-1.3")
check("CANARY: prompt đi qua FILE, KHÔNG nằm trong argv (Windows chặn ở 32767 ký tự)",
      "--prompt-file" in _argv and not any(len(x) > 30000 for x in _argv))
check("session id đi qua --session-id",
      _argv[_argv.index("--session-id") + 1] == "11111111-2222-4333-8444-555555555555")
check("mạch MỚI thì không --allow-workspace-switch", "--allow-workspace-switch" not in _argv)
_argv_r = _u._build_args(prompt_file="/tmp/p.txt", session_id="x", noi_mach=True)
check("nối mạch cũ thì cho phép đổi workspace (cwd có thể đã đổi)",
      "--allow-workspace-switch" in _argv_r)
_argv_n = _u._build_args(prompt_argv="chào", session_id=None)
check("không session id thì không truyền cờ, prompt là positional cuối",
      "--session-id" not in _argv_n and _argv_n[-1] == "chào")
_u.max_turns = 1
_argv_m = _u._build_args(prompt_argv="chào")
check("max_turns của người gọi (bộ não giọng) ghi đè trần bước",
      _argv_m[_argv_m.index("--max-model-steps") + 1] == "1")
_u.max_turns = 0
_cat = muse_cli._cat_args(_argv_n)
check("CANARY: _cat_args KHÔNG lộ prompt (nội dung riêng người dùng)",
      "chào" not in _cat and "<prompt>" in _cat, _cat)


# ============================================================
# 4. Dịch sự kiện: ba hình dạng JSONL
# ============================================================
def _gia(dong_ra, ma=0, stderr="", ma_khi_session=None):
    """`muse` giả. `ma_khi_session`: thoát mã đó nếu argv có --session-id (giả lập bị từ chối)."""
    d = Path(tempfile.mkdtemp(prefix="javis-fakemuse-"))
    p = d / "muse"
    body = json.dumps(dong_ra)
    p.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        f"if {ma_khi_session!r} != None and '--session-id' in sys.argv:\n"
        "    sys.stderr.write('error: unknown session id\\n')\n"
        f"    sys.exit({ma_khi_session!r})\n"
        f"for l in {body}:\n"
        "    print(l, flush=True)\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({ma})\n",
        encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(p)


def _chay_gia(dong_ra, ma=0, stderr="", prompt="xin chào", session_id=None, ma_khi_session=None,
              instructions=None):
    g = muse_cli.MuseCLI(cwd="/tmp", session_id=session_id, instructions=instructions)
    g.cli_path = _gia(dong_ra, ma, stderr, ma_khi_session)

    async def _go():
        return [ev async for ev in g.query(prompt)]
    return chay(_go()), g


# (a) MSP
_MSP = [
    json.dumps({"method": "session/started", "params": {"session_id": "0199aaaa-1111-4222-8333-444444444444"}}),
    json.dumps({"method": "item/started", "params": {"item": {"id": "r1", "type": "reasoning"}}}),
    json.dumps({"method": "item/delta", "params": {"item_id": "r1", "item": {"id": "r1", "type": "reasoning"}, "delta": "nghĩ đã"}}),
    json.dumps({"method": "item/started", "params": {"item": {"id": "t1", "type": "tool_call", "name": "mcp__javis__javis_read_file", "arguments": {"path": "MEMORY.md"}}}}),
    json.dumps({"method": "item/completed", "params": {"item": {"id": "t1", "type": "tool_call", "name": "mcp__javis__javis_read_file", "output": "nội dung file", "status": "completed"}}}),
    json.dumps({"method": "item/started", "params": {"item": {"id": "m1", "type": "message", "role": "assistant"}}}),
    json.dumps({"method": "item/delta", "params": {"item_id": "m1", "delta": {"text": "Chào "}}}),
    json.dumps({"method": "item/delta", "params": {"item_id": "m1", "delta": {"text": "bạn."}}}),
    json.dumps({"method": "item/completed", "params": {"item": {"id": "m1", "type": "message", "role": "assistant", "content": [{"type": "text", "text": "Chào bạn."}]}}}),
    json.dumps({"method": "turn/completed", "params": {"status": "completed", "usage": {"input_tokens": 1200, "output_tokens": 45, "cached_tokens": 900}}}),
]
_evs, _g1 = _chay_gia(_MSP, session_id=None)
_final = next((e for e in _evs if e["type"] == "final"), None)
check("MSP: mảnh delta GHÉP thành một câu trả lời, completed KHÔNG đếm hai lần",
      _final is not None and _final["content"] == "Chào bạn.", _final)
check("CANARY: reasoning KHÔNG lọt vào câu trả lời",
      _final is not None and "nghĩ" not in _final["content"])
check("MSP: tool_call có tên tool (mcp__javis__...)",
      any(e["type"] == "tool_call" and e.get("name") == "mcp__javis__javis_read_file" for e in _evs))
check("MSP: item/started + item/completed cùng tool -> đúng MỘT tool_call",
      len([e for e in _evs if e["type"] == "tool_call"]) == 1, [e["type"] for e in _evs])
check("MSP: completed của tool -> tool_result",
      any(e["type"] == "tool_result" and "nội dung file" in e.get("content", "") for e in _evs))
check("MSP: usage trong turn/completed -> token vào/ra",
      any(e["type"] == "usage" and e.get("input_tokens") == 1200 and e.get("output_tokens") == 45 for e in _evs))
check("MSP: id phiên nhặt từ session/started (ưu tiên id CLI phát hơn id tự cấp)",
      _g1.session_id == "0199aaaa-1111-4222-8333-444444444444", _g1.session_id)
check("final mang session_id và tokens theo hợp đồng",
      _final.get("session_id") == _g1.session_id and _final.get("tokens_in") == 1200
      and _final.get("tokens_out") == 45, _final)

# (b) kiểu Claude Code
_CC = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "0199bbbb-1111-4222-8333-444444444444"}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "hm"},
                                                             {"type": "tool_use", "id": "x", "name": "javis_list_dir", "input": {"path": "."}}]}}),
    json.dumps({"type": "tool_result", "id": "x", "content": "a.md b.md"}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Có hai file."}]}}),
    json.dumps({"type": "result", "subtype": "success", "result": "Có hai file.",
                "usage": {"input_tokens": 10, "output_tokens": 3}}),
]
_evs2, _g2 = _chay_gia(_CC)
_f2 = next((e for e in _evs2 if e["type"] == "final"), None)
check("Claude-style: text block -> câu trả lời, `result` không đếm lại",
      _f2 is not None and _f2["content"] == "Có hai file.", _f2)
check("Claude-style: tool_use -> tool_call",
      any(e["type"] == "tool_call" and e.get("name") == "javis_list_dir" for e in _evs2))
check("Claude-style: tool_result -> tool_result",
      any(e["type"] == "tool_result" and "a.md" in e.get("content", "") for e in _evs2))
check("Claude-style: usage trong result", any(e["type"] == "usage" and e["input_tokens"] == 10 for e in _evs2))
check("Claude-style: session_id ở tầng ngoài", _g2.session_id == "0199bbbb-1111-4222-8333-444444444444")

# (c) chung
_GEN = [
    json.dumps({"kind": "step", "tool": "javis_use_skill", "input": {"slug": "notes"}}),
    json.dumps({"text": "Xong "}),
    json.dumps({"delta": "rồi."}),
    json.dumps({"event": "done", "data": {"session": "0199cccc-1111-4222-8333-444444444444",
                                           "token_usage": {"prompt_tokens": 7, "completion_tokens": 2}}}),
]
_evs3, _g3 = _chay_gia(_GEN)
_f3 = next((e for e in _evs3 if e["type"] == "final"), None)
check("chung: text/delta chuỗi -> câu trả lời", _f3 is not None and _f3["content"] == "Xong rồi.", _f3)
check("chung: tool + input -> tool_call",
      any(e["type"] == "tool_call" and e.get("name") == "javis_use_skill" for e in _evs3))
check("chung: usage dict ở tầng sâu vẫn nhặt (prompt_tokens/completion_tokens)",
      any(e["type"] == "usage" and e["input_tokens"] == 7 and e["output_tokens"] == 2 for e in _evs3))
check("chung: `session` chuỗi ở tầng sâu -> id phiên",
      _g3.session_id == "0199cccc-1111-4222-8333-444444444444", _g3.session_id)

# Loại lạ hoàn toàn: vớt chữ, và vòng đệm thô giữ lại để chẩn đoán
_LA = [json.dumps({"type": "muse/weird", "payload": {"response": "câu trả lời nằm đây"}})]
_evs4, _ = _chay_gia(_LA)
check("loại lạ: vớt được chữ ở tầng sâu thay vì ô trống",
      any(e["type"] == "final" and "nằm đây" in e["content"] for e in _evs4), _evs4)
check("vòng đệm sự kiện thô giữ dòng vừa chạy (để dán lại cho dev)",
      any("muse/weird" in x for x in muse_cli.su_kien_tho()))
check("chan_doan() lộ vòng đệm thô", any("muse/weird" in x for x in muse_cli.chan_doan()["su_kien_tho"]))

# Không ra gì cả
_evs5, _ = _chay_gia([], ma=0)
check("chạy xong mà không có nội dung -> nói thẳng, kèm cách chạy tay để xem",
      any(e["type"] == "error" and ("Kiểm tra lại" in e["content"] or "KHÔNG in ra gì" in e["content"])
          for e in _evs5), _evs5)

# Chưa đăng nhập
_evs6, _ = _chay_gia([], ma=1, stderr="Error: not authenticated. Please sign in.")
_e6 = next((e for e in _evs6 if e["type"] == "error"), None)
check("chưa đăng nhập -> câu tiếng Việt làm theo được",
      _e6 is not None and "đăng nhập" in _e6["content"].lower() and "muse" in _e6["content"], _e6)
check("và KHÔNG bịa thêm câu trả lời rỗng", not any(e["type"] == "final" for e in _evs6))

# stderr có log nhưng thoát 0 -> không phải lỗi; và id phiên in ở stderr vẫn nhặt được
_evs7, _g7 = _chay_gia([json.dumps({"text": "ok"})], ma=0,
                       stderr="INFO session 0199dddd-1111-4222-8333-444444444444 started\n")
check("CANARY: thoát 0 mà stderr có log thì KHÔNG thành lỗi",
      not any(e["type"] == "error" for e in _evs7), [e["type"] for e in _evs7])
check("id phiên in ở stderr vẫn được nhặt",
      _g7.session_id == "0199dddd-1111-4222-8333-444444444444", _g7.session_id)

# turn/completed status=error
_evs8, _ = _chay_gia([json.dumps({"method": "turn/completed", "params": {"status": "error", "error": "model bận"}})])
check("turn/completed status=error -> sự kiện error",
      any(e["type"] == "error" and "model bận" in e.get("content", "") for e in _evs8))

# Dòng không phải JSON thì GIỮ làm chữ
_evs9, _ = _chay_gia(["đây không phải json"], ma=0)
check("CANARY: dòng không phải JSON được giữ làm chữ", any(e["type"] == "final" and "không phải json" in e["content"] for e in _evs9))


# ============================================================
# 5. --session-id tự cấp bị từ chối -> thử lại ĐÚNG MỘT lần không cờ
# ============================================================
_evs10, _g10 = _chay_gia([json.dumps({"text": "chào lại"})], ma_khi_session=2)
check("CLI thoát 2 với --session-id tự cấp -> thử lại không cờ và vẫn ra câu trả lời",
      any(e["type"] == "final" and e["content"] == "chào lại" for e in _evs10), _evs10)
check("và KHÔNG báo lỗi của lần đầu ra ngoài", not any(e["type"] == "error" for e in _evs10))
check("và KHÔNG lưu một id mạch không tồn tại", _g10.session_id is None, _g10.session_id)
# Mạch CŨ từ kho mà hỏng thì KHÔNG thử lại ở đây (nơi gọi xoá id và mồi lại)
_evs11, _g11 = _chay_gia([json.dumps({"text": "x"})], session_id="dead-dead-dead", ma_khi_session=2)
check("mạch cũ từ kho hỏng -> báo lỗi, không tự thử lại (nơi gọi quyết)",
      any(e["type"] == "error" for e in _evs11) and not any(e["type"] == "final" for e in _evs11))


# ============================================================
# 6. System prompt: gộp vào lượt MỞ MẠCH, không gộp khi nối mạch cũ
# ============================================================
_ghi = Path(tempfile.mkdtemp(prefix="javis-museprompt-")) / "muse"
_ghi.write_text("#!/usr/bin/env python3\nimport sys, json\n"
                "p = open(sys.argv[sys.argv.index('--prompt-file') + 1], encoding='utf-8').read()\n"
                "print(json.dumps({'text': 'LEN=' + str(len(p)) + ' SYS=' + str('HỆ THỐNG' in p)}))\n",
                encoding="utf-8")
_ghi.chmod(_ghi.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _chay_prompt(session_id):
    g = muse_cli.MuseCLI(cwd="/tmp", session_id=session_id, instructions="HỆ THỐNG: luật")
    g.cli_path = str(_ghi)

    async def _go():
        return [ev async for ev in g.query("hỏi")]
    return chay(_go())


_fa = next(e for e in _chay_prompt(None) if e["type"] == "final")["content"]
_fb = next(e for e in _chay_prompt("0199eeee-1111-4222-8333-444444444444") if e["type"] == "final")["content"]
check("mở mạch mới: system prompt nằm trong prompt", "SYS=True" in _fa, _fa)
check("nối mạch cũ: KHÔNG gửi lại system prompt (phí token thuê bao)", "SYS=False" in _fb, _fb)


# ============================================================
# 7. Watchdog: CLI treo im bị cắt
# ============================================================
_treo = Path(tempfile.mkdtemp(prefix="javis-musehang-")) / "muse"
_treo.write_text("#!/usr/bin/env python3\nimport sys, time\n"
                 "if '--help' in sys.argv:\n    print('  --json')\n"
                 "else:\n    time.sleep(60)\n", encoding="utf-8")
_treo.chmod(_treo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
_gh = muse_cli.MuseCLI(cwd="/tmp")
_gh.cli_path = str(_treo)
_gh.timeout = 2


async def _go_treo():
    return [e async for e in _gh.query("hi")]


_t0 = __import__("time").time()
_evsh = chay(_go_treo())
_giay = __import__("time").time() - _t0
check("CANARY: CLI treo im bị watchdog cắt", _giay < 20, f"{_giay:.1f}s")
check("và nói rõ là bị cắt vì quá giờ", any("quá 2s" in str(e.get("content", "")) for e in _evsh), _evsh)
import glob  # noqa: E402
check("CANARY: file prompt tạm được dọn", glob.glob(os.path.join(tempfile.gettempdir(), "javis-muse-*.txt")) == [])


# ============================================================
# 8. Trạng thái đăng nhập đọc từ file, META_API_KEY thắng
# ============================================================
_a = muse_cli.auth_status()
check("chưa đăng nhập -> nói rõ phải làm gì", _a["connected"] is False and "Đăng nhập" in _a["error"], _a)
os.environ["META_API_KEY"] = "meta-abc"
check("có META_API_KEY thì coi như đã cấu hình, method nói rõ là API key",
      muse_cli.auth_status()["method"] == "meta-api-key")
os.environ.pop("META_API_KEY", None)
Path(os.environ["JAVIS_MUSE_HOME"], "auth.json").write_text(
    json.dumps({"credentials": {"access_token": "m-" + "t" * 32}, "user": {"email": "ai@meta.com"},
                "plan": "Power"}), encoding="utf-8")
_a2 = muse_cli.auth_status()
check("có auth.json (token lồng sâu) thì đọc ra cả tài khoản và gói",
      _a2["connected"] and _a2["account"] == "ai@meta.com" and _a2["plan"] == "Power", _a2)
_cd = muse_cli.chan_doan()
check("chan_doan chỉ lộ TÊN khoá, không lộ giá trị token",
      _cd["co_token"] and _cd["khoa_token"] == "access_token"
      and "t" * 32 not in json.dumps(_cd, ensure_ascii=False), _cd)
check("đã đăng nhập -> login_start trả xong ngay, không mở tiến trình",
      muse_cli.login_start(cho_giay=1).get("xong") is True)


# ============================================================
# 9. MCP: gộp vào settings.json, giữ server khác, sao lưu, không phá file hỏng
# ============================================================
_brain = Path(tempfile.mkdtemp(prefix="javis-musebrain-"))
_hub = muse_cli.hub_entry("http://127.0.0.1:8790/mcp",
                          {"Authorization": "Bearer tok", "X-Javis-Mode": "full",
                           "X-Javis-Vault": str(_brain)})
check("CANARY: entry MCP có transport streamable_http + url (không phải httpUrl/serverUrl)",
      _hub.get("transport") == "streamable_http" and "url" in _hub and "httpUrl" not in _hub
      and _hub.get("enabled") is True, _hub)
_cfg = muse_cli.mcp_config_path(_brain)
_cfg.parent.mkdir(parents=True, exist_ok=True)
_cfg.write_text(json.dumps({"schema_version": 1, "theme": "dark",
                            "mcp_servers": {"github": {"transport": "stdio", "command": "gh-mcp"}}}),
                encoding="utf-8")
_p = muse_cli.ghi_mcp_settings(_brain, _hub)
check("ghi vào cấu hình cá nhân của muse (settings.json), không phải trong brain",
      _p is not None and _p.endswith("settings.json") and str(_brain) not in _p, _p)
_d = json.loads(Path(_p).read_text(encoding="utf-8"))
check("GIỮ server khác của người dùng và các khoá khác",
      _d["mcp_servers"].get("github", {}).get("command") == "gh-mcp" and _d.get("theme") == "dark", _d)
check("schema_version giữ nguyên", _d.get("schema_version") == 1)
check("có sao lưu bản trước", (Path(_p).parent / "settings.json.bak").exists())
_st = muse_cli.trang_thai_mcp(_brain)
check("đọc LẠI thấy entry javis, đúng url, đủ header, và biết trỏ brain nào",
      _st["co_javis"] and _st["url"] == "http://127.0.0.1:8790/mcp" and _st["so_header"] == 3
      and _st["vault_khop"] is True, _st)
try:
    check("file chứa hub token nên phải chmod 600", (os.stat(_p).st_mode & 0o077) == 0 or os.name == "nt")
except Exception:
    pass
muse_cli.ghi_mcp_settings(_brain, None)
_st2 = muse_cli.trang_thai_mcp(_brain)
_d2 = json.loads(Path(_p).read_text(encoding="utf-8"))
check("hub=None -> gỡ entry javis, server khác vẫn còn",
      _st2["co_javis"] is False and "github" in _d2["mcp_servers"], _d2)
# File hỏng -> KHÔNG ghi đè
Path(_p).write_text("{ hỏng json", encoding="utf-8")
_p3 = muse_cli.ghi_mcp_settings(_brain, _hub)
check("CANARY: settings.json hỏng thì KHÔNG ghi đè (thà không có tool còn hơn xoá cấu hình)",
      _p3 is None and Path(_p).read_text(encoding="utf-8") == "{ hỏng json")
# Ghi lần hai không đổi gì -> không chạm file
Path(_p).write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
muse_cli.ghi_mcp_settings(_brain, _hub)
_mt = Path(_p).stat().st_mtime_ns
__import__("time").sleep(0.01)
muse_cli.ghi_mcp_settings(_brain, _hub)
check("ghi lại cùng nội dung thì không chạm file (không sao lưu thừa mỗi lượt)",
      Path(_p).stat().st_mtime_ns == _mt)


# ============================================================
# 10. main.py đã nối đủ các chỗ (canary chống "thêm nhà mà quên dây")
# ============================================================
import main   # noqa: E402
_pd = next((p for p in main.PROVIDER_DEFS if p["id"] == "muse-cli"), None)
check("PROVIDER_DEFS có muse-cli kind=cli", _pd is not None and _pd["kind"] == "cli" and _pd["key_field"] is None)
check("AGENT_PROVIDERS có muse-cli (agent/việc nền chạy được)", "muse-cli" in main.AGENT_PROVIDERS)
check("_DG_NAO_CLI có muse-cli (chấm điểm não)", "muse-cli" in main._DG_NAO_CLI)
check("_TG_ENGINE_MACH có muse-cli", any(n == "muse-cli" for n, _ in main._TG_ENGINE_MACH))
check("nhãn Telegram ngắn", main._TG_NHAN_NGAN.get("muse-cli") == "Muse Code")
check("có hàm _muse_sub_stream và _apply_muse_hub", callable(main._muse_sub_stream) and callable(main._apply_muse_hub))
_routes = {r.path for r in main.app.routes if hasattr(r, "path")}
for _r in ("/muse/status", "/muse/login-start", "/muse/login-poll", "/muse/logout", "/muse/check"):
    check(f"route {_r}", _r in _routes)
import sessions  # noqa: E402
check("sessions: cột muse_session_id trong bảng mạch native", sessions.SessionStore._MACH_NATIVE.get("muse-cli") == "muse_session_id")
import aux_engine  # noqa: E402
check("aux_engine: MUSE_CLI + _build_muse", aux_engine.MUSE_CLI == "muse-cli" and callable(aux_engine._build_muse))
import limit_learner, model_limits  # noqa: E402
check("limit_learner biết muse-cli", limit_learner.ENGINE_HINT_BY_PROVIDER.get("muse-cli") == "muse-cli")
check("model_limits có nhãn gói", "muse-cli" in model_limits.SUBSCRIPTION_LABEL)
_lim = limit_learner.parse_subscription_limit("Your plan limit reached. Resets in 3 hours.", "muse-cli")
check("câu hết lượt kiểu gói -> nhận ra, gắn đúng engine", _lim is not None and _lim.engine == "muse-cli", _lim)
check("CANARY: 429 của API thuần KHÔNG bị coi là hết gói",
      limit_learner.parse_subscription_limit("rate limit exceeded, retry after 20s", "") is None)

muse_cli.find_muse_cli = _that_find

print()
if _fails:
    print(f"FAIL {len(_fails)}: " + "; ".join(_fails))
    sys.exit(1)
print("Tất cả xanh.")
