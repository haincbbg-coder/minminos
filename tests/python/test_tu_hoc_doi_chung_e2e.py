"""Trụ 6 (26.10.217): đầu-cuối đường chạy nền của "Cải tiến có đối chứng", engine GIẢ.

    python3 tests/python/test_tu_hoc_doi_chung_e2e.py     (KHÔNG mạng, KHÔNG model)

Đi đúng đường thật: endpoint /harness/uoc-luong -> chuan_bi -> _chay_nen (brain tạm, engine chạy thử
dựng bằng claude_engine giả, phiên cải tiến giả đọc thư mục bằng chứng) -> ket-qua.json -> áp dụng ->
hoàn tác. Engine chạy thử giả GỌI plugin THẬT `javis_task` (giao việc Kanban) và `javis_write_file`
trong lúc chạy: phải thấy chúng bị giả lập (ý định nằm trong trajectory) và brain thật không đổi.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-h2e-")
os.environ["JAVIS_STATE_DIR"] = _STATE

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import che_do_thu  # noqa: E402
import harness2 as h2  # noqa: E402
import harness2_noi as noi  # noqa: E402
import mcp_hub  # noqa: E402
import plugins_host  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:400] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


goc = Path(tempfile.mkdtemp(prefix="h2e-brain-"))
B = goc / "brain"
(B / "agents").mkdir(parents=True)
(B / "agents" / "ban-hang.md").write_text(
    "---\ntype: agent\nname: Bán hàng\nslug: ban-hang\nrole: Chốt đơn\ngroup: Bán hàng\nskills: []\nmodel: ''\n"
    "muc_quyen: full\n---\nBạn chốt đơn cho khách.\n", encoding="utf-8")
md = B / "memory" / "agents" / "ban-hang"
(md / "runs").mkdir(parents=True)
(md / "runs" / "2026-10-22.md").write_text(
    "\n## 09:00\n**Task:** Lên đơn cho chị Lan váy hoa size M\n\n**Kết quả:** Đã lên đơn\n"
    "\n## 11:00\n**Task:** Nhắn khách xác nhận địa chỉ giao hàng\n\n**Kết quả:** Đã nhắn\n", encoding="utf-8")
(B / "wiki.md").write_text("bảng size", encoding="utf-8")
anh_that = noi._anh_chup(B)

PLUGIN_ROUTE = {}
DA_CHAY = []


class EngThu:
    """Executor giả: gọi plugin javis_task THẬT và javis_write_file của hub, như một agent full."""

    def __init__(self, **k):
        self.k = k
        self.allowed_tools = k.get("allowed_tools")
        self.mcp_config = None
        self.tag = k.get("tag")

    async def query(self, prompt):
        if self.tag == "harness-cai-tien":
            async for ev in self._cai_tien(prompt):
                yield ev
            return
        vault = self.k["cwd"]
        _t, route = plugins_host.plugin_tools("full", vault)
        _b, broute = mcp_hub._builtin_tools("full", vault)
        yield {"type": "tool_call", "name": "mcp__javis__javis_task", "input": {"op": "add", "title": "giao hàng"}}
        r1 = await route["javis_task"]["call"]({"op": "add", "title": "giao hàng"})
        yield {"type": "tool_result", "content": r1}
        DA_CHAY.append(r1)
        r2 = await broute["javis_write_file"]["call"]({"path": "don-nhap.md", "content": "đơn chị Lan"})
        yield {"type": "tool_result", "content": r2}
        # cố tình ghi vào brain THẬT bằng đường dẫn tuyệt đối: _safe_path phải chặn
        r3 = await broute["javis_write_file"]["call"]({"path": str(B / "bi-ghi.md"), "content": "x"})
        yield {"type": "tool_result", "content": str(r3)}
        co_skill = "chot-don" in (Path(vault) / "agents" / "ban-hang.md").read_text(encoding="utf-8")
        yield {"type": "final", "content": "Đã lên đơn (đã kiểm size)" if co_skill else "Đã lên đơn", "cost_usd": 0.002}

    async def _cai_tien(self, prompt):
        goc_ = Path(self.k["cwd"])
        nhan = goc_.name
        hd = goc_ / "context" / "harness"
        agent = (hd / "agent.md").read_text(encoding="utf-8") if (hd / "agent.md").is_file() else ""
        tat_ca = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in (goc_ / "context").rglob("*.md"))
        check(f"{nhan}: ngữ cảnh KHÔNG chứa điểm", "h2_diem" not in tat_ca)
        if nhan.startswith("inv"):
            check(f"{nhan}: trajectory gốc có dòng GIẢ LẬP của javis_task", "[GIẢ LẬP]" in tat_ca and "javis_task" in tat_ca)
            ra = f"<file path=\"agent.md\">{agent.rstrip()}\nKiểm lại size trước khi lên đơn.\n</file><notes>đọc lại</notes>"
        elif nhan.startswith("dom"):
            ra = ("<file path=\"skills/chot-don/SKILL.md\">---\nname: Chốt đơn\ndescription: Kiểm size và địa chỉ trước khi "
                  "lên đơn.\ngroup: Bán hàng\n---\n## Quy trình\n1. Hỏi size.\n</file><notes>skill chốt đơn</notes>")
        elif nhan.startswith("agg"):
            pool = goc_ / "context" / "pool"
            blk = []
            for lab in sorted(p.name for p in pool.iterdir()):
                for f in (pool / lab / "harness").rglob("*"):
                    if f.is_file():
                        rel = str(f.relative_to(pool / lab / "harness"))
                        txt = f.read_text(encoding="utf-8")
                        if rel == "skills/chot-don/SKILL.md" or (rel == "agent.md" and "Kiểm lại size" in txt):
                            blk.append(f"<file path=\"{rel}\">{txt}</file>")
            ra = "\n".join(blk) + "<notes>kept -> cả hai</notes>"
        elif nhan == "rut":
            ra = ("<edits>component: skills/chot-don\ncandidates: dom1\nchange: thêm skill\nobserved: kiểm size\n"
                  "verdict: confounded</edits>\n<experience>\ncue: lên đơn thời trang\nlesson: thêm skill chot-don "
                  "kiểm size\nevidence: dom1 confounded, agg1 kiểm size ở cả 2 đề\nconfidence: low, một lượt\n</experience>")
        else:
            ra = "<notes>KEEP_BASE</notes>"
        yield {"type": "final", "content": ra, "cost_usd": 0.01}


def tao_feature():
    deps = noi.Deps(
        brain_root=lambda b: str(B), state_dir=Path(_STATE),
        workflow_agent_helpers=lambda brain, tools, m: (None, lambda s: ("x", f"SYS ở {brain}", None, ""), None, None),
        boc_bai_hoc=lambda out: ([], out), claude_engine=lambda **k: EngThu(**k),
        readonly_tools=["Read", "Glob", "Grep", "LS"], empty_mcp_file=lambda: None, aux_model=lambda: "",
        agent_model_provider=lambda m, p: "anthropic-cli", bo_vao_hom_thu=_hom_thu,
        is_system_skill=lambda s: False, hub_url=lambda: "http://127.0.0.1:7777/hub/mcp", hub_token=lambda: "T",
        song_song=2)
    return noi.Harness2Feature(deps)


THU = []


async def _hom_thu(chat, text, **k):
    THU.append(text)


feat = tao_feature()
app = FastAPI()
app.include_router(feat.router)
cli = TestClient(app)

r = cli.post("/harness/uoc-luong", json={"brain": "brain", "slug": "ban-hang", "k": 1}).json()
check("ước lượng: ok", r.get("ok"), r)
check("ước lượng: 2 đề từ nhật ký", len(r.get("de") or []) == 2, r.get("de"))
check("ước lượng: k=1 x 2 đề = 8 lượt, 3 phiên", r["uoc"]["luot_agent"] == 8 and r["uoc"]["phien_cai_tien"] == 3, r["uoc"])
check("ước lượng: cảnh báo trợ lý Toàn quyền vẫn không làm gì thật", any("KHÔNG làm hành động" in c for c in r["canh_bao"]))
r_sai = cli.post("/harness/uoc-luong", json={"brain": "brain", "slug": "khong-co"}).json()
check("ước lượng: trợ lý không có thì báo lỗi rõ", not r_sai.get("ok") and "Không thấy" in r_sai.get("error", ""), r_sai)
r_codex = cli.post("/harness/chay", json={"brain": "brain", "slug": "ban-hang", "nao_chay": {"provider": "openai-oauth"}}).json()
check("chạy: bộ não Codex bị từ chối trước khi chạy", not r_codex.get("ok") and "chưa chạy thử an toàn" in r_codex.get("error", ""),
      r_codex)

# Chạy thật đường nền (gọi thẳng _chay_nen để chờ được, y hệt task nền mà /harness/chay tạo).
cb = feat.chuan_bi({"brain": "brain", "slug": "ban-hang", "k": 1})
run_id = "h2-20261024-120000-e2e1"
cfg = {"brain": "brain", "slug": "ban-hang", "k": 1, "che_do": "song_song",
       "de": [d.to_dict(kem_case=True) for d in cb["de"]], "spec_chay": cb["spec_chay"],
       "spec_cai_tien": cb["spec_cai_tien"], "tran_usd": 5, "tran_luot": 40, "chat_id": "web:s1",
       "bat_dau": "2026-10-24T12:00:00"}
noi._ghi_json(feat.thu_muc(run_id) / "cau-hinh.json", cfg)
feat.dang = {"run_id": run_id, "tran": h2.Tran(luot_max=40, usd_max=5)}
asyncio.run(feat._chay_nen(run_id, cfg))
ket = json.loads((feat.thu_muc(run_id) / "ket-qua.json").read_text(encoding="utf-8"))
check("chạy nền: xong", ket.get("trang_thai") == "xong", ket.get("trang_thai"))
check("chạy nền: đúng 8 lượt, 3 phiên, đẳng thức đúng", ket["so_cai"]["so_luot"] == 8 and ket["so_cai"]["so_phien"] == 3
      and ket["so_cai"]["dung_dang_thuc"], ket["so_cai"])
check("chạy nền: có đề xuất (không giữ nguyên)", not ket["giu_nguyen"], ket.get("chan_an_toan"))
check("chạy nền: javis_task bị GIẢ LẬP ở mọi lượt", DA_CHAY and all(x.startswith("GIẢ LẬP") for x in DA_CHAY), DA_CHAY[:2])
yd = [r for ls in ket["y_dinh"].values() for r in ls]
check("chạy nền: ý định javis_task được ghi cho từng lượt", sum(1 for r in yd if r["tool"] == "javis_task") == 8, len(yd))
check("chạy nền: ghi ra brain thật bị chặn (ý định ghi file ngoài brain tạm)", not (B / "bi-ghi.md").exists())
check("chạy nền: brain thật KHÔNG đổi một file nào", noi._anh_chup(B) == anh_that)
luot_b = ket["luot"]["base1"][0]
check("chạy nền: file nháp nằm trong brain tạm của lượt (được thu làm sản phẩm)", "don-nhap.md" in luot_b["tep"], luot_b["tep"])
qd = h2.doc_su_kien(luot_b["quy_dao"])
check("trajectory JSONL có sự kiện gia_lap", any(e.get("type") == "gia_lap" and e.get("tool") == "javis_task" for e in qd))
check("chạy nền: báo hòm thư một thư", len(THU) == 1 and "CHƯA áp dụng" in THU[0], THU)
check("chạy nền: dọn brain tạm", not (feat.thu_muc(run_id) / "nao-nen").exists() and not (feat.thu_muc(run_id) / "nao-0").exists())
check("chạy nền: không còn ý định treo trong RAM", not che_do_thu._SO, list(che_do_thu._SO)[:3])
check("chạy nền: hết lượt thì trả cờ đang chạy", feat.dang == {})

r = cli.get("/harness/ket-qua", params={"run_id": run_id}).json()
check("GET ket-qua: có diff từng file", r.get("ok") and any(d["file"] == "skills/chot-don/SKILL.md" for d in r["diff"]), r.get("diff"))
check("GET ket-qua: không lộ đáp án đề", all("case" not in d for d in r["de"]))
r = cli.get("/harness/lich-su", params={"slug": "ban-hang", "brain": "brain"}).json()
check("lịch sử: thấy lần chạy", any(x["run_id"] == run_id and x["trang_thai"] == "xong" for x in r["lan"]), r)
r = cli.post("/harness/ap-dung", json={"run_id": run_id}).json()
check("áp dụng qua endpoint", r.get("ok") and "skills/chot-don/SKILL.md" in r["files"], r)
check("áp dụng: agent thật được gán skill chot-don, giữ muc_quyen",
      "chot-don" in (B / "agents" / "ban-hang.md").read_text(encoding="utf-8")
      and "muc_quyen: full" in (B / "agents" / "ban-hang.md").read_text(encoding="utf-8"))
check("áp dụng: thư viện nhóm Bán hàng có mục", h2.ngu_canh_thu_vien(B, "Bán hàng") is not None)
r = cli.post("/harness/bo", json={"run_id": run_id}).json()
check("Bỏ một đề xuất đã áp dụng bị từ chối (phải dùng Hoàn tác)", not r.get("ok"))
r = cli.post("/harness/hoan-tac", json={"run_id": run_id}).json()
check("hoàn tác qua endpoint", r.get("ok"), r)
# .javis-learn.lock là file khoá của BrainLock (tự học cũng tạo y vậy), không phải nội dung brain.
sau_ht = {k: v for k, v in noi._anh_chup(B).items() if k != ".javis-learn.lock"}
check("hoàn tác: brain về đúng như trước", sau_ht == anh_that, sorted(set(sau_ht.items()) ^ set(anh_that.items()))[:4])
r = cli.get("/harness/trang-thai", params={"run_id": run_id}).json()
check("trạng thái sau hoàn tác", r.get("trang_thai") == "da_hoan_tac", r)
mo_coi = "h2-20261024-120500-moco"
noi._ghi_json(feat.thu_muc(mo_coi) / "trang-thai.json", {"trang_thai": "dang_chay", "buoc": "đang chạy"})
r = cli.get("/harness/trang-thai", params={"run_id": mo_coi}).json()
check("lượt 'đang chạy' mồ côi sau khi máy chủ khởi động lại báo là đã dừng", r.get("trang_thai") == "dung", r)
r = cli.get("/harness/ket-qua", params={"run_id": "../../etc"}).json()
check("mã lần chạy lạ bị từ chối (không đọc ngoài thư mục harness)", not r.get("ok"))

shutil.rmtree(_STATE, ignore_errors=True)
shutil.rmtree(goc, ignore_errors=True)
print()
print("FAIL: " + ", ".join(fails) if fails else "ALL OK")
raise SystemExit(1 if fails else 0)
