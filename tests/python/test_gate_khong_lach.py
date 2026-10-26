"""Bước TRƯỚC GATE của job Đội AI không được tự thao tác ra ngoài hay tự nâng quyền (26.10.246).

    python tests/run.py gate_khong_lach      (KHÔNG mạng, KHÔNG cần Claude CLI)

Lời hứa với chủ: bước trước GATE chạy ở mức thấp; chỉ bước sau GATE được cấp toàn quyền khi chủ
bấm Duyệt. Phase 03 kiểm quyền tìm ra bốn đường lách có thật trong mã, file này canh từng đường:

1. Bash ở capability `code` mức auto: lệnh shell không qua mcp_hub._guard -> curl/script ra ngoài.
2. Tool tạo việc (`javis_task`, `javis_schedule`) mặc định full: bước auto tự giao việc toàn quyền.
3. Ghi file trong brain: `.claude/settings.json` (permissions.allow xét TRƯỚC can_use_tool, phiên
   có rào nạp settings dự án), `.mcp.json`, loop/agent/workflow/skill/plugin chạy được ở full.
4. Engine không rào được ở mức thấp: Antigravity (--dangerously-skip-permissions) và Codex khi
   JAVIS_CODEX_SANDBOX=off (bản Docker).

Việc lẻ ngoài job và mọi lượt full giữ nguyên hành vi cũ: test_full_quyen_ungated canh phần đó.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from _paths import ROOT, SERVER  # noqa: E402,F401

import aux_engine      # noqa: E402
import plugins_host    # noqa: E402
import tasks           # noqa: E402
from claude_sdk_engine import ClaudeSDK   # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  [{extra}]" if (not cond and extra) else ""))
    if not cond:
        fails.append(name)


class _Deps:
    safe_tools = ["Read", "Write", "Edit", "Glob", "Grep", "LS"]
    mcp_allow_patterns = staticmethod(lambda: ["mcp__javis"])


class _F:
    """Chỉ cần _lane_tools: dựng đối tượng không qua __init__ (không mở kho, không chạy luồng)."""
    deps = _Deps()


lane = tasks.TasksFeature._lane_tools if hasattr(tasks, "TasksFeature") else None
if lane is None:
    # Tên lớp có thể khác: lấy lớp nào có _lane_tools.
    for v in vars(tasks).values():
        if isinstance(v, type) and hasattr(v, "_lane_tools") and hasattr(v, "_siet_buoc_job"):
            lane = v._lane_tools
            Lop = v
            break
else:
    Lop = tasks.TasksFeature
check("tìm được lớp điều phối có _lane_tools và _siet_buoc_job", lane is not None)

# ---- 1. Bash ----
f = _F()
tools, mode, cam = lane(f, {"capability": "code", "execution_mode": "auto", "job_id": "j1"})
check("bước job capability code mức auto: KHÔNG có Bash", "Bash" not in (tools or []), tools)
check("bước job capability code mức auto: Bash nằm trong danh sách chặn", "Bash" in cam, cam)
tools2, _, _ = lane(f, {"capability": "code", "execution_mode": "auto"})
check("việc lẻ ngoài job giữ Bash như cũ (không phá việc code thường)", "Bash" in (tools2 or []), tools2)
tools3, mode3, _ = lane(f, {"capability": "code", "execution_mode": "full", "job_id": "j1"})
check("bước job mức full (sau GATE được duyệt) vẫn không rào", tools3 is None and mode3 == "full")
for cap in ("files", "research", "mcp-read", "external-write", "auto"):
    t, _, c = lane(f, {"capability": cap, "execution_mode": "auto", "job_id": "j1"})
    check(f"bước job capability {cap} mức auto: không có Bash", "Bash" not in (t or []) and "Bash" in c)

# ---- 2. Tool tạo việc mới ----
kq = plugins_host.kep_quyen_viec_moi
check("javis_task từ lượt auto xin full -> bị kẹp về auto",
      kq("javis_task", {"title": "x", "mode": "full"}, "auto").get("mode") == "auto")
check("javis_task từ lượt auto không ghi mode (mặc định full) -> auto",
      kq("javis_task", {"title": "x"}, "auto").get("mode") == "auto")
check("javis_task từ lượt suggest -> suggest",
      kq("javis_task", {"mode": "full"}, "suggest").get("mode") == "suggest")
check("javis_task từ lượt auto xin suggest -> giữ suggest (chỉ hạ, không nâng)",
      kq("javis_task", {"mode": "suggest"}, "auto").get("mode") == "suggest")
check("javis_schedule từ lượt auto -> muc_quyen auto",
      kq("javis_schedule", {"op": "create"}, "auto").get("muc_quyen") == "auto")
check("lượt full giữ nguyên mức xin",
      kq("javis_task", {"mode": "full"}, "full").get("mode") == "full")
check("tool khác không bị đụng",
      kq("social_ke_hoach", {"mode": "full"}, "auto").get("mode") == "full")
goc = {"mode": "full"}
kq("javis_task", goc, "auto")
check("không sửa args gốc của người gọi", goc == {"mode": "full"})


async def _goi_qua_make_call():
    nhan = {}

    def handler(a, ctx):
        nhan.update(a)
        return "ok"
    tool = {"handler": handler, "min_mode": "readonly", "name": "javis_task"}
    call = plugins_host._make_call(tool, ctx=None, mode="auto")
    await call({"title": "x", "mode": "full"})
    return nhan

check("đường gọi thật (_make_call) cũng kẹp", asyncio.run(_goi_qua_make_call()).get("mode") == "auto")

# ---- 3. Ghi file tự nâng quyền ----
class _Cli:
    mcp_config = "/tmp/x.json"
    mcp_strict = False
    setting_sources = None
    duong_cam_ghi = None

c = _Cli()
Lop._siet_buoc_job(c)
check("siết bước job: chỉ MCP do MinMin đưa vào (strict)", c.mcp_strict is True)
check("siết bước job: không nạp settings filesystem nào", c.setting_sources == [])
check("siết bước job: có danh sách đường cấm ghi", ".claude" in (c.duong_cam_ghi or []) and "Javis/loops" in c.duong_cam_ghi)
src = (Path(SERVER) / "tasks.py").read_text(encoding="utf-8")
check("_base_cli gọi _siet_buoc_job đúng cho bước job dưới full",
      'if task.get("job_id") and mode != "full":\n            self._siet_buoc_job(cli)' in src)

with tempfile.TemporaryDirectory() as td:
    eng = ClaudeSDK(cwd=td, tag="t", allowed_tools=_Deps.safe_tools + ["mcp__javis"])
    eng.duong_cam_ghi = list(Lop.DUONG_CAM_GHI_BUOC_JOB)
    g = eng._ghi_vao_duong_cam
    check("cấm ghi .claude/settings.json", g({"file_path": ".claude/settings.json"}) == ".claude")
    check("cấm lách bằng a/../.claude", g({"file_path": "nhap/../.claude/settings.local.json"}) == ".claude")
    check("cấm ghi .mcp.json", g({"file_path": ".mcp.json"}) == ".mcp.json")
    check("cấm ghi loop bằng đường tuyệt đối", g({"file_path": os.path.join(td, "Javis/loops/x.md")}) == "Javis/loops")
    check("cấm ghi agent", g({"file_path": "agents/ban-hang.md"}) == "agents")
    check("cấm ghi ra ngoài brain", g({"file_path": "../ngoai.txt"}) != "")
    check("được ghi bản nháp trong brain", g({"file_path": "nhap/bai-1.md"}) == "")
    check("được ghi file tên giống nhưng không phải thư mục cấm", g({"file_path": "agents-ghi-chu.md"}) == "")

    async def _gate(tool, data):
        return await eng._permission_gate(tool, data, None)
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
    check("gate: Write vào .claude bị từ chối",
          isinstance(asyncio.run(_gate("Write", {"file_path": ".claude/settings.json"})), PermissionResultDeny))
    check("gate: Edit vào Javis/loops bị từ chối",
          isinstance(asyncio.run(_gate("Edit", {"file_path": "Javis/loops/a.md"})), PermissionResultDeny))
    check("gate: Write bản nháp được cho phép",
          isinstance(asyncio.run(_gate("Write", {"file_path": "nhap/a.md"})), PermissionResultAllow))
    check("gate: Bash ngoài whitelist vẫn bị từ chối",
          isinstance(asyncio.run(_gate("Bash", {"command": "curl x"})), PermissionResultDeny))
    opts = eng._options() if hasattr(eng, "_options") else None
    allowed = list(getattr(opts, "allowed_tools", []) or [])
    check("tool ghi rút khỏi danh sách tự duyệt để đi qua gate soi đường",
          opts is not None and "Write" not in allowed and "Edit" not in allowed and "Read" in allowed, allowed)
    eng2 = ClaudeSDK(cwd=td, tag="t2", allowed_tools=_Deps.safe_tools)
    opts2 = eng2._options()
    check("phiên có rào thường (không phải bước job) giữ Write tự duyệt như cũ",
          "Write" in list(getattr(opts2, "allowed_tools", []) or []))

# ---- 4. Engine không rào được ----
_goc_spec = aux_engine.read_spec
_goc_env = os.environ.get("JAVIS_CODEX_SANDBOX")
try:
    aux_engine.read_spec = lambda settings=None: {"provider": aux_engine.ANTIGRAVITY, "model": ""}
    check("Antigravity: bước trước GATE dừng kèm lý do", "Antigravity" in Lop._engine_khong_rao())
    aux_engine.read_spec = lambda settings=None: {"provider": aux_engine.CODEX, "model": ""}
    os.environ["JAVIS_CODEX_SANDBOX"] = "off"
    check("Codex không rào (Docker): dừng kèm lý do", "Codex" in Lop._engine_khong_rao())
    os.environ["JAVIS_CODEX_SANDBOX"] = "auto"
    check("Codex có sandbox: chạy được", Lop._engine_khong_rao() == "")
    aux_engine.read_spec = lambda settings=None: {"provider": aux_engine.CLAUDE, "model": ""}
    check("Claude Code: chạy được", Lop._engine_khong_rao() == "")
finally:
    aux_engine.read_spec = _goc_spec
    if _goc_env is None:
        os.environ.pop("JAVIS_CODEX_SANDBOX", None)
    else:
        os.environ["JAVIS_CODEX_SANDBOX"] = _goc_env
check("_execute chặn bước job dưới full khi engine không rào được (block_kind engine)",
      'ly_do = self._engine_khong_rao()' in src and '"engine", ly_do' in src)

if fails:
    raise SystemExit(f"\nFAIL - test_gate_khong_lach: {len(fails)} lỗi")
print("\nOK - test_gate_khong_lach: tất cả pass")
