"""Vá 26.10.96: agent nhận từ Chợ chia sẻ bị CHẶN CỨNG cả khi chat trực tiếp, không chỉ trong
workflow; và Codex ở mức nhẹ không còn gọi tool MCP ra ngoài với nhãn full.

    python tests/run.py chia_se_chan_chat
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-chanchat-")
BR = tempfile.mkdtemp(prefix="javis-chanchat-brain-")
import main  # noqa: E402
import mcp_hub  # noqa: E402
import aux_engine  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


main._ensure_brain_scaffold(Path(BR))
ag = Path(BR) / "agents"
ag.mkdir(exist_ok=True)
(ag / "nhan-ve.md").write_text("---\nname: Nhận về\nmuc_quyen: suggest\nnguon: x.vn\n---\nx", encoding="utf-8")
(ag / "nhap-auto.md").write_text("---\nname: Nháp\nmuc_quyen: auto\n---\nx", encoding="utf-8")
(ag / "tu-tao.md").write_text("---\nname: Tự tạo\n---\nx", encoding="utf-8")
(ag / "la.md").write_text("---\nname: Lạ\nmuc_quyen: sieu-quyen\n---\nx", encoding="utf-8")

m = main._muc_quyen_luot_chat
check("chat với agent nhận về: suggest", m({"id": "s1", "channel": "agent:nhan-ve"}, BR) == "suggest")
check("chat với agent nháp: auto", m({"id": "s1", "channel": "agent:nhap-auto"}, BR) == "auto")
check("chat với agent tự tạo: vẫn full như cũ", m({"id": "s1", "channel": "agent:tu-tao"}, BR) == "full")
check("mức lạ trong file không nới quyền thành thứ lạ", m({"id": "s1", "channel": "agent:la"}, BR) == "full")
check("chat thường không bị đụng", m({"id": "s1", "channel": "dashboard"}, BR) == "full")
check("slug độc hại không đọc file ngoài brain", m({"id": "s1", "channel": "agent:../../etc/passwd"}, BR) == "full")
check("gọi kiểu cũ không brain vẫn chạy", m({"id": "s1", "channel": "agent:nhan-ve"}) == "full")

src = (Path(SERVER) / "main.py").read_text(encoding="utf-8")
check("mọi chỗ khung chat hỏi mức quyền đều truyền brain",
      "_muc_quyen_luot_chat(_row0)" not in src, re.findall(r"_muc_quyen_luot_chat\(_row0\)", src)[:3])
check("Grok trong chat nhận mode theo lượt ở hub", "_apply_grok_hub(kcli, _brain_root(brain), mode=kcli.mode)" in src)
check("Antigravity trong chat nhận mode theo lượt ở hub", "_apply_antigravity_hub(acli, _brain_root(brain), mode=acli.mode)" in src)
check("engine API trong chat nhận mode theo lượt", "mode=_muc_quyen_luot_chat(_row0, brain)," in src)


class _Cli:
    allowed_tools = None
    disallowed_tools = ["mcp__x__xoa"]


c = main._siet_claude_theo_muc(_Cli(), "suggest")
check("Claude mức suggest: chỉ tool đọc", "Write" not in c.allowed_tools and "Edit" not in c.allowed_tools and "Read" in c.allowed_tools, c.allowed_tools)
check("Claude mức suggest: chặn Bash/Web/Task", all(x in c.disallowed_tools for x in ("Bash", "WebFetch", "WebSearch", "Task")))
check("Claude mức suggest: giữ chặn riêng có sẵn", "mcp__x__xoa" in c.disallowed_tools)
c2 = main._siet_claude_theo_muc(_Cli(), "auto")
check("Claude mức auto: được ghi nháp", "Write" in c2.allowed_tools)
c3 = _Cli()
main._siet_claude_theo_muc(c3, "full")
check("Claude mức full: không đụng gì", c3.allowed_tools is None)

ec = ["mcp_servers.javis.http_headers.X-Javis-Vault=\"/b\""]
mcp_hub.dat_codex_mode(ec, "suggest")
check("Codex suggest: thêm override mode", any(x.endswith('X-Javis-Mode="suggest"') for x in ec), ec)
check("Codex: giữ override brain", any("X-Javis-Vault" in x for x in ec))
mcp_hub.dat_codex_mode(ec, "auto")
check("Codex: đổi mode thay override cũ, không chồng", sum("X-Javis-Mode" in x for x in ec) == 1 and ec[-1].endswith('"auto"'), ec)
mcp_hub.dat_codex_mode(ec, "full")
check("Codex full: bỏ override (profile chung là full)", not any("X-Javis-Mode" in x for x in ec))
mcp_hub.dat_codex_mode(ec, "toan-quyen-gia")
check("Codex mode lạ: về suggest, không nới", ec[-1].endswith('"suggest"'))


class _Claude:
    cwd = BR
    tag = "t"
    system_prompt = "x"
    javis_vault = BR
    javis_mode = "suggest"


cc = aux_engine._build_codex({"model": ""}, _Claude(), "suggest", "loop")
check("việc nền Codex mức suggest mang mode suggest tới hub",
      any(str(x).endswith('X-Javis-Mode="suggest"') for x in cc.extra_config), cc.extra_config)
cc2 = aux_engine._build_codex({"model": ""}, _Claude(), "full", "loop")
check("việc nền Codex mức full không bị siết", not any("X-Javis-Mode" in str(x) for x in cc2.extra_config))

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
