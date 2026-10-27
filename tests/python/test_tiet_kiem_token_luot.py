"""Tiết kiệm token mỗi lượt chat (26.10.271).

    python tests/run.py tiet_kiem_token_luot

Ghim năm thứ:
  1. Câu CHỈ có chào hỏi/cảm ơn đi đường tắt ở mọi mức tiết kiệm, và không câu có việc nào lọt theo.
     In ra số đo: capsule chào hỏi so với system prompt đầy đủ.
  2. Đường Claude Code không tool không gửi schema tool nào (`disallowed_tools=["*"]`).
  3. Mọi lượt Claude Code bỏ CLAUDE.md của repo khỏi phần tự nạp và gom gọn mạch ở ~180k.
  4. Lượt nối phiên Claude Code mang giờ gửi tin mới (system prompt đông cứng khi --resume).
  5. Dòng token dưới câu trả lời chỉ đếm token MỚI, phần cache nằm ở chú thích.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-tietkiem-"))
from capability_registry import CapabilityRegistry  # noqa: E402
from capability_resolver import DeterministicResolver  # noqa: E402
from context_compiler import ContextCompiler  # noqa: E402
from context_runtime import ObserveRuntime  # noqa: E402
import context_compiler  # noqa: E402
import fast_path_runtime as fp  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra) + "]") if extra and not cond else ""))
    if not cond:
        fails.append(name)


# ---- 1. Cái gì là chào hỏi ----
for text in ("chào em", "Chào em 👋", "cảm ơn em nhé", "Cảm ơn nhiều ạ", "hi MinMin", "thanks!",
             "Xin chào", "chào buổi sáng anh", "Thank you so much", "em cảm ơn ạ", "cảm ơn bố",
             "chào bố 🙏"):
    check(f"chào hỏi: {text!r}", fp.is_small_talk(text))
for text in ("ok", "ok làm đi", "ok cảm ơn", "👍", "được", "chào em, doanh thu hôm nay thế nào?",
             "cảm ơn, gửi tin cho Lan nhé", "cảm ơn em, nhắc anh 7h sáng mai", "em ơi",
             "hi, đọc file báo cáo giúp anh", "chào " * 20, "", "chào em\nxóa lịch họp mai",
             "thanks, now delete the draft", "mấy giờ rồi em"):
    check(f"không phải chào hỏi: {text[:40]!r}", not fp.is_small_talk(text))


def _stack(settings):
    tmp = Path(tempfile.mkdtemp(prefix="minmin-tietkiem-stack-"))
    brain = tmp / "brain"
    registry = CapabilityRegistry(tmp / "registry")
    registry.refresh_tools(brain, [], {})
    runtime = ObserveRuntime(tmp / "runtime", settings_reader=lambda: settings)
    trace = runtime.start_turn("session-chao-hoi", str(brain), "dashboard")
    trace.registry_revision = registry.revision(brain)
    canary = fp.FastPathCanary(registry, DeterministicResolver(registry), ContextCompiler(registry),
                               runtime, settings_reader=lambda: settings)
    return brain, trace, canary


# Mức "Tắt" trên trang Mức dùng là mode "shadow" bên dưới (config.py), cũng là mặc định.
TAT = {"context_runtime": {"mode": "shadow"}}
brain, trace, canary = _stack(TAT)
plan = canary.prepare(trace, "chào em", str(brain), "dashboard", "anthropic-cli", "claude-opus-5-5",
                      "cli", False, "", "")
check("chào hỏi khi mức tiết kiệm TẮT: đi đường tắt", plan.action == "execute", plan)
check("plan đánh dấu small_talk để chỗ gọi giữ mạch native", plan.small_talk is True)
_capsule = sum(len(str(m.get("content") or "")) for m in plan.messages)
check("capsule mang câu chào và system prompt nhỏ",
      plan.messages and plan.messages[-1].get("content", "").endswith("chào em") and _capsule < 6_000,
      _capsule)

brain, trace, canary = _stack(TAT)
plan = canary.prepare(trace, "chào em, doanh thu hôm nay thế nào?", str(brain), "dashboard",
                      "anthropic-cli", "claude-opus-5-5", "cli", False, "", "")
check("câu có việc khi mức TẮT vẫn đi đường đầy đủ",
      plan.action == "legacy" and plan.reason == "mode_not_canary", plan)

brain, trace, canary = _stack(TAT)
plan = canary.prepare(trace, "cảm ơn em", str(brain), "dashboard", "anthropic-cli",
                      "claude-opus-5-5", "cli", True, "", "")
check("chào hỏi kèm file đính kèm đi đường đầy đủ", plan.action == "legacy", plan)

brain, trace, canary = _stack(TAT)
plan = canary.prepare(trace, "thanks!", str(brain), "telegram", "groq", "llama-3.3-70b", "api",
                      False, "", "")
check("kênh khác và engine API cũng vậy", plan.action == "execute" and plan.small_talk, plan)


# ---- 2. Đường Claude Code không tool: không schema tool nào ----
import main  # noqa: E402

_goc = main._claude_sub_doc
main._claude_sub_doc = lambda cli, prompt, model: cli
try:
    cli = main._claude_sub_stream("", [{"role": "system", "content": "x"}, {"role": "user", "content": "chào em"}],
                                  tiet_kiem=True)
finally:
    main._claude_sub_doc = _goc
check("đường không tool cấm mọi tool", cli.disallowed_tools == ["*"], cli.disallowed_tools)
check("...với system prompt trần (không preset claude_code)", cli.system_prompt_raw is True)
try:
    opts = cli._options()
    check("...và SDK options mang theo", "*" in (getattr(opts, "disallowed_tools", None) or []),
          getattr(opts, "disallowed_tools", None))
except ImportError:
    print("skip SDK options (claude-agent-sdk chưa cài)")

# Số đo: system prompt đầy đủ (chỉ phần cố định, chưa kể schema tool và danh sách skill Claude
# Code tự thêm) so với capsule chào hỏi.
_pb = main.do_phan_bo_prompt("brain")
if "loi" not in _pb:
    _tong = int(_pb["tong_ky_tu"])
    print(f"      đo: câu chào trên đường đầy đủ ~{_tong:,} ký tự system prompt, đường tắt {_capsule:,} ký tự "
          f"(giảm {100 - _capsule * 100 // max(1, _tong)}%)")
    check("capsule chào hỏi nhỏ hơn system prompt đầy đủ ít nhất 10 lần", _capsule * 10 <= _tong,
          (_capsule, _tong))


# ---- 3. Settings Claude Code: bỏ CLAUDE.md của repo, gom gọn ở ~180k ----
import claude_cli  # noqa: E402

os.environ.pop("MINMIN_CLAUDE_COMPACT_WINDOW", None)
d = json.loads(claude_cli.cai_dat_claude_minmin())
_md = str((ROOT / "CLAUDE.md").resolve())
check("loại CLAUDE.md của repo khỏi phần Claude Code tự nạp", _md in d.get("claudeMdExcludes", []), d)
check("gom gọn mạch ở cửa sổ 200k", d.get("autoCompactWindow") == 200_000, d)
d = json.loads(claude_cli.cai_dat_claude_minmin('{"claudeMdExcludes": ["/x/CLAUDE.md"], "fastMode": true}'))
check("gộp lên trên settings có sẵn, không làm mất khoá cũ",
      d.get("fastMode") is True and "/x/CLAUDE.md" in d["claudeMdExcludes"] and _md in d["claudeMdExcludes"], d)
for v, want in (("auto", None), ("off", None), ("300k", 300_000), ("50000", 100_000), ("5000k", 1_000_000),
                ("rac", 200_000)):
    os.environ["MINMIN_CLAUDE_COMPACT_WINDOW"] = v
    d = json.loads(claude_cli.cai_dat_claude_minmin())
    check(f"MINMIN_CLAUDE_COMPACT_WINDOW={v} -> {want}", d.get("autoCompactWindow") == want, d)
os.environ.pop("MINMIN_CLAUDE_COMPACT_WINDOW", None)

eng = claude_cli.claude_engine(system_prompt="x", cwd=tempfile.gettempdir())
check("mọi engine Claude Code tạo qua factory đều mang settings", bool(eng.settings_json)
      and _md in json.loads(eng.settings_json)["claudeMdExcludes"])
try:
    opts = eng._options()
    check("...và đi xuống tiến trình `claude` qua --settings", getattr(opts, "settings", None) == eng.settings_json)
except ImportError:
    print("skip SDK options (claude-agent-sdk chưa cài)")


# ---- 4. Giờ gửi tin trên lượt nối phiên ----
_tz = timezone(timedelta(hours=7))
_now = datetime(2026, 10, 28, 9, 5, tzinfo=_tz)
_d = context_compiler.dong_ho_ngan(now=_now, lang="vi")
check("dòng giờ ngắn có giờ, thứ và ngày", "09:05" in _d and "28/10/2026" in _d and "Thứ Tư" in _d, _d)
check("dòng giờ ngắn đúng là ngắn", len(_d) < 90, len(_d))
check("tiếng Anh có nhãn tiếng Anh", "sent at" in context_compiler.dong_ho_ngan(now=_now, lang="en"))


class _Cli:
    session_id = None


c = _Cli()
check("phiên MỚI không gắn giờ (system prompt vừa dựng đã đúng giờ)",
      main._gio_luot_noi_mach(c, "mấy giờ rồi", "vi") == "mấy giờ rồi")
c.session_id = "abc"
_p = main._gio_luot_noi_mach(c, "mấy giờ rồi", "vi")
check("phiên NỐI LẠI gắn giờ gửi tin lên đầu", _p.startswith("[Giờ gửi tin này:") and _p.endswith("\nmấy giờ rồi"), _p)
check("prompt không phải chuỗi (có ảnh) thì để nguyên", main._gio_luot_noi_mach(c, [1], "vi") == [1])
_src = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
check("cả dashboard lẫn Telegram đều gắn giờ cho lượt Claude Code",
      _src.count("_gio_luot_noi_mach(cli, _cli_do_sau(cli, reasoning,") == 2)


# ---- 5. Dòng token chỉ đếm token mới ----
_f = main._ctx_frame(None, 60_000, 58_000)
check("khung response mang cả tổng lẫn phần cache", _f["ctx_in"] == 60_000 and _f["ctx_cache"] == 58_000, _f)
_app = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
_i = _app.index("function _renderCtxLine(")
_ham = _app[_i:_app.index("\n}\n", _i)]
check("dòng token trừ phần cache ra", "_fmtTok(tok - cache)" in _ham)
check("phần cache không vượt tổng", "Math.min(Number(data.ctx_cache) || 0, tok)" in _ham)
for lang in ("vi", "en"):
    j = json.loads((ROOT / "dashboard" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    check(f"chú thích cache ({lang}) có cả phần cache lẫn tổng",
          "{cache}" in j["app.ctx_hint_cache"] and "{tong}" in j["app.ctx_hint_cache"])
check("đường tắt cũng báo phần cache", "dem=_dem" in _src and '_dem.get("cache")' in _src)
check("Codex báo phần cache", '"tokens_cache": u.get("cached_input_tokens")'
      in (ROOT / "server" / "claude_cli.py").read_text(encoding="utf-8"))



# ---- 6. Trang Mức dùng: 24 giờ qua theo từng giờ ----
import usage_index  # noqa: E402

# Mốc giờ ở năm 2099 để không đụng dữ liệu thật nếu JAVIS_STATE_DIR trỏ vào một kho có sẵn.
_tzv = usage_index._tz()
_bay = datetime(2099, 1, 2, 10, 30, tzinfo=_tzv)
_c = usage_index._connect()
try:
    _c.execute("DELETE FROM file_hourly WHERE path='__test_gio_24__'")
    _c.executemany("INSERT INTO file_hourly(path,hour,provider,tokens,turns) VALUES(?,?,?,?,?)", [
        ("__test_gio_24__", "2099-01-02T10", "claude", 1000, 2),
        ("__test_gio_24__", "2099-01-02T10", "openrouter", 300, 1),
        ("__test_gio_24__", "2099-01-02T08", "codex", 500, 1),
        ("__test_gio_24__", "2099-01-01T10", "claude", 9999, 9),   # đúng 24 giờ trước: ngoài cửa sổ
    ])
    _c.commit()
finally:
    _c.close()
_g = usage_index.gio_24(now=_bay)
check("24 mốc giờ liên tục, mốc cuối là giờ hiện tại", len(_g) == 24 and _g[-1]["hour"] == "2099-01-02T10"
      and _g[0]["hour"] == "2099-01-01T11", [x["hour"] for x in _g[:1] + _g[-1:]])
check("tách theo provider, nhà API gộp vào cột api",
      _g[-1]["claude"] == 1000 and _g[-1]["api"] == 300 and _g[-1]["total"] == 1300 and _g[-1]["turns"] == 3, _g[-1])
check("giờ không dùng ra 0, giờ ngoài 24h không lọt vào",
      _g[-3]["codex"] == 500 and _g[-2]["total"] == 0 and sum(x["total"] for x in _g) == 1800)
_c = usage_index._connect()
try:
    _c.execute("DELETE FROM file_hourly WHERE path='__test_gio_24__'")
    _c.commit()
finally:
    _c.close()
check("/usage/tong-quan trả gio_24", '"gio_24": await asyncio.to_thread(usage_index.gio_24)' in _src)
_ujs = (ROOT / "dashboard" / "usage.js").read_text(encoding="utf-8")
check("trang Mức dùng vẽ biểu đồ 24 giờ", "chart += veGio24(t.gio_24);" in _ujs and "usage.sec.gio_24" in _ujs)
for lang in ("vi", "en"):
    j = json.loads((ROOT / "dashboard" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    check(f"nhãn 24 giờ ({lang})", j.get("usage.sec.gio_24") and "{gio}" in j.get("usage.chart.tip_gio", ""))

print()
if fails:
    raise SystemExit(f"FAIL {len(fails)}: " + "; ".join(fails[:4]))
print("All green.")
