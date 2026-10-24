"""Trụ 2 (26.10.217): nối với main THẬT - deps thật, engine Claude thật (KHÔNG gọi model).

    python3 tests/python/test_tu_hoc_doi_chung_main.py     (KHÔNG mạng)

Test lõi dùng engine giả; file này chốt rằng phần main tiêm vào đúng hợp đồng:
  - /harness/uoc-luong chạy được trên brain thật dựng tạm;
  - prompt của trợ lý dựng trên brain TẠM trỏ về brain tạm (không phải brain thật), và khối kinh
    nghiệm chỉ có khi file kinh-nghiem.md tồn tại;
  - engine chạy thử là ClaudeSDK thật có allowlist (không bao giờ None -> không nạp connector tài
    khoản Claude), cấm Bash/Write/Edit/Web/Task, MCP strict, cấu hình MCP riêng mang cờ chạy thử;
  - phiên cải tiến Claude chỉ có server đọc thư mục bằng chứng (`mcp__harness`), không tool native nào.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-h2m-"))
_BR = tempfile.mkdtemp(prefix="javis-h2m-brains-")
os.environ["BRAINS_DIR"] = _BR

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import main  # noqa: E402
import che_do_thu  # noqa: E402
import harness2 as h2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:400] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


B = Path(_BR) / "shop"
(B / "agents").mkdir(parents=True)
(B / "agents" / "cskh.md").write_text("---\ntype: agent\nname: CSKH\nslug: cskh\nrole: Trả lời khách\ngroup: Bán hàng\n"
                                      "skills: []\nmuc_quyen: auto\n---\nBạn trả lời khách lịch sự.\n", encoding="utf-8")
md = B / "memory" / "agents" / "cskh"
(md / "runs").mkdir(parents=True)
(md / "runs" / "2026-10-23.md").write_text("\n## 08:00\n**Task:** Trả lời khách hỏi size váy\n\n**Kết quả:** Size M\n",
                                           encoding="utf-8")
feat = main.harness2_feature
check("main đăng ký harness2_feature", isinstance(feat, main.harness2_noi.Harness2Feature))
check("gốc brain tạm đã đặt cho cờ chạy thử", che_do_thu.goc_tam() is not None
      and che_do_thu.goc_tam() == (Path(main.cfgmod.STATE_DIR) / "harness").resolve())

cli = TestClient(main.app, base_url="http://localhost")
r = cli.post("/harness/uoc-luong", json={"brain": str(B), "slug": "cskh", "k": 1})
d = r.json() if r.status_code == 200 else {"status": r.status_code, "text": r.text[:300]}
check("POST /harness/uoc-luong qua main thật", d.get("ok") and len(d.get("de") or []) == 1, d)
check("trợ lý mức auto: chạy thử liệt kê theo mức auto", d.get("muc_quyen") == "auto", d.get("muc_quyen"))

# Prompt của trợ lý trên brain tạm (đúng hàm main dùng cho workflow/chat).
cay, info = h2.doc_cay(B, "cskh")
rid = "h2-20261024-130000-main"
feat.thu_muc(rid).mkdir(parents=True, exist_ok=True)
chay_luot, phien, don_dep, tk = feat._ngu_canh_chay(rid, str(B), "cskh", info,
                                                     {"provider": "anthropic-cli", "model": ""},
                                                     {"provider": "anthropic-cli", "model": ""})
slot = feat.thu_muc(rid) / "nao-0"
main.harness2_noi.vat_chat_hoa(slot, feat.thu_muc(rid) / "nao-nen", cay, slug="cskh", agent_rel=info["agent_rel"])
_mk, agent_sp, _l, _le = main._workflow_agent_helpers(str(slot), None, "full")
_ten, sp, _m, _p = agent_sp("cskh")
check("prompt dựng trên brain TẠM trỏ về brain tạm", str(slot) in sp and str(B) not in sp)
check("trợ lý chưa cải tiến: không có khối kinh nghiệm", "Kinh nghiệm đã kiểm chứng" not in sp)
check("prompt mang chế độ an toàn đúng mức auto", "GHI NHÁP" in sp)
(slot / "memory" / "agents" / "cskh" / "kinh-nghiem.md").write_text("## [2026-10-24] mục\n- Bài học: hỏi chiều cao.\n",
                                                                    encoding="utf-8")
_ten, sp2, _m, _p = agent_sp("cskh")
check("có kinh-nghiem.md thì prompt nạp khối kinh nghiệm", "Kinh nghiệm đã kiểm chứng" in sp2 and "hỏi chiều cao" in sp2)

eng = feat.dung_engine_chay(slot, sp, {"provider": "anthropic-cli", "model": ""}, "auto", "h2-x-y",
                            feat.thu_muc(rid) / "mcp" / "x.json")
check("engine chạy thử là ClaudeSDK thật", type(eng).__name__ == "ClaudeSDK", type(eng).__name__)
check("ClaudeSDK có allowlist (không bao giờ None)", eng.allowed_tools and "mcp__javis" in eng.allowed_tools, eng.allowed_tools)
check("allowlist chỉ có hub, không tool native nào (kể cả Read)", eng.allowed_tools == ["mcp__javis"], eng.allowed_tools)
check("cấm Bash/Write/Edit/WebFetch/WebSearch/Task", all(x in eng.disallowed_tools for x in
                                                         ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task")))
check("MCP strict", eng.mcp_strict is True)
opts = eng._options()
check("tuỳ chọn SDK: permission default + can_use_tool (không bypassPermissions)",
      opts.permission_mode == "default" and opts.can_use_tool is not None, opts.permission_mode)
check("tuỳ chọn SDK: setting_sources == [] (không ambient, không hook/allow-rule của máy)", opts.setting_sources == [],
      opts.setting_sources)
srv = opts.mcp_servers if isinstance(opts.mcp_servers, dict) else {}
check("tuỳ chọn SDK: chỉ server javis, không plugin in-process", set(srv) == {"javis"}, list(srv))
hd = (srv.get("javis") or {}).get("headers") or {}
check("header MCP mang cờ chạy thử + brain tạm + mức auto",
      hd.get(che_do_thu.HEADER) == "h2-x-y" and hd.get("X-Javis-Vault") == str(slot) and hd.get("X-Javis-Mode") == "auto", hd)

ect = feat.dung_engine_cai_tien(feat.thu_muc(rid), {"provider": "anthropic-cli"})
check("phiên cải tiến: chỉ server harness", ect.allowed_tools == ["mcp__harness"], ect.allowed_tools)
oct_ = ect._options()
check("phiên cải tiến: setting_sources == [] và server harness in-process",
      oct_.setting_sources == [] and set(oct_.mcp_servers or {}) == {"harness"}, (oct_.setting_sources, oct_.mcp_servers))
don_dep()
check("dọn brain tạm", not slot.exists())

shutil.rmtree(_BR, ignore_errors=True)
print()
print("FAIL: " + ", ".join(fails) if fails else "ALL OK")
raise SystemExit(1 if fails else 0)
