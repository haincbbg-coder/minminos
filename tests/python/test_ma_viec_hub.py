"""26.10.199: mã việc nền tới hub (cổng từ Javis 0.238.0, bản MinMin không có turn_context).

    python3 tests/python/test_ma_viec_hub.py

Ba chỗ riêng của MinMin: ContextVar `bind_job`, cấu hình MCP RIÊNG theo việc cho Claude Code
(`TasksFeature._gan_ma_viec`) và header `X-Javis-Job` ở route hub. Không mạng, không model.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import once_ledger as ol
import tasks

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- ContextVar mã việc ----------
check("ngoài việc nền: không có mã", ol.current_job() == "")
tok = ol.bind_job("kanban:t_abc123")
check("gắn mã hợp lệ", ol.current_job() == "kanban:t_abc123")
ol.reset_job(tok)
check("trả về rỗng sau reset", ol.current_job() == "")
for xau in ("", "t_abc", "kanban:", "kanban:a b", "kanban:../../x", "kanban:" + "x" * 80, "web:abc"):
    tok = ol.bind_job(xau)
    check(f"mã lạ bị bỏ: {xau[:20]!r}", ol.current_job() == "")
    ol.reset_job(tok)

# ---------- cấu hình MCP riêng theo việc ----------
with tempfile.TemporaryDirectory() as d:
    goc = Path(d) / ".mcp_hub_full.json"
    goc.write_text(json.dumps({"mcpServers": {"javis": {
        "type": "http", "url": "http://x/hub", "headers": {"Authorization": "Bearer T", "X-Javis-Mode": "full"}}}}),
        encoding="utf-8")
    cli = SimpleNamespace(mcp_config=str(goc))
    ft = tasks.TasksFeature.__new__(tasks.TasksFeature)
    ft._gan_ma_viec(cli, {"id": "t_1234abcd"})
    moi = Path(cli.mcp_config)
    check("engine trỏ sang file riêng, không phải file chung", moi != goc and moi.name.startswith(".mcp_job_"), cli.mcp_config)
    dl = json.loads(moi.read_text(encoding="utf-8"))["mcpServers"]["javis"]["headers"]
    check("file riêng có header mã việc", dl.get("X-Javis-Job") == "kanban:t_1234abcd", dl)
    check("giữ nguyên token và mode", dl.get("Authorization") == "Bearer T" and dl.get("X-Javis-Mode") == "full")
    chung = json.loads(goc.read_text(encoding="utf-8"))["mcpServers"]["javis"]["headers"]
    check("file chung KHÔNG bị sửa", "X-Javis-Job" not in chung, chung)
    check("file riêng siết quyền 600", (os.stat(moi).st_mode & 0o777) == 0o600 or os.name == "nt")
    # file không phải cấu hình hub: không đụng
    khac = Path(d) / "mcp.json"
    khac.write_text("{}", encoding="utf-8")
    c2 = SimpleNamespace(mcp_config=str(khac))
    ft._gan_ma_viec(c2, {"id": "t_zzz"})
    check("cấu hình lạ giữ nguyên", c2.mcp_config == str(khac))
    c3 = SimpleNamespace(mcp_config=None)
    ft._gan_ma_viec(c3, {"id": "t_zzz"})
    check("không có cấu hình thì bỏ qua", c3.mcp_config is None)
    # file cũ quá 2 ngày bị dọn
    cu = Path(d) / ".mcp_job_cu.json"
    cu.write_text("{}", encoding="utf-8")
    os.utime(cu, (1, 1))
    ft._gan_ma_viec(SimpleNamespace(mcp_config=str(goc)), {"id": "t_moi"})
    check("dọn file cấu hình việc cũ", not cu.exists())

# ---------- header ở route hub ----------
src = (SERVER / "mcp_hub.py").read_text(encoding="utf-8")
check("route hub đọc header X-Javis-Job", "once_ledger.JOB_HEADER.lower()" in src and "bind_job" in src)
check("không có gạch dài", "—" not in (SERVER / "once_ledger.py").read_text(encoding="utf-8"))

print()
print("FAIL: " + ", ".join(fails) if fails else "ALL OK")
raise SystemExit(1 if fails else 0)
