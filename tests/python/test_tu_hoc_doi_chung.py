"""Trụ 6 (26.10.217): lõi "Tự học có đối chứng" (harness2.py + harness2_noi.py), engine GIẢ tất định.

    python3 tests/python/test_tu_hoc_doi_chung.py     (KHÔNG mạng, KHÔNG model)

Canh đúng những gì Harness² chứng minh là tạo ra hiệu quả và những rào MinMin thêm vào:
  - validator: chặn đổi mức quyền/model, skill hệ thống, gạch dài, dấu điểm, vượt ngân sách chữ;
    skill mới phải được nêu tên (autotrigger), thử lại 1 lần kèm lỗi rồi fell_back;
  - song song k=1 và nối tiếp k=2: đúng 4k x số đề lượt chạy và 3k phiên cải tiến;
  - KEEP_BASE hợp lệ; chặn an toàn: điểm luật hạ hoặc bản ghép không giao được thì giữ nguyên;
  - chọn mù k>1 (mã ẩn danh xáo theo seed, ổn định);
  - thư viện: chỉ ghi khi đủ cue/lesson/evidence VÀ chủ áp dụng; INDEX dựng từ đĩa; cùng nhóm
    thấy, khác nhóm không;
  - áp dụng + hoàn tác (git và không git) chỉ đụng đúng file của cây, giữ khoá quyền;
  - brain tạm biến mất giữa chừng thì DỪNG, không rơi về brain thật;
  - engine chạy thử Claude luôn có allowlist + cờ shadow trong cấu hình MCP riêng.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-h2-")
os.environ["JAVIS_STATE_DIR"] = _STATE

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import che_do_thu  # noqa: E402
import git_brain  # noqa: E402
import harness2 as h2  # noqa: E402
import harness2_noi as noi  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:400] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


AGENT = """---
type: agent
name: Trợ lý báo cáo
slug: bao-cao
role: Báo cáo doanh thu ngày
group: Bán hàng
skills: [ghi-chu, bao-cao-ngay]
model: ''
muc_quyen: full
updated: 2026-10-01
---
Bạn là trợ lý báo cáo. Lấy số thật từ POS rồi tóm tắt.
"""
SKILL_GHI = """---
name: Ghi chú
description: Ghi chú ngắn cho chủ.
group: Năng suất
---
## Quy trình
1. Đọc yêu cầu.
2. Ghi gọn.
"""


def tao_brain(goc: Path, git: bool = False) -> Path:
    b = goc / "brain"
    (b / "agents").mkdir(parents=True)
    (b / "agents" / "bao-cao.md").write_text(AGENT, encoding="utf-8")
    (b / "skills" / "ghi-chu").mkdir(parents=True)
    (b / "skills" / "ghi-chu" / "SKILL.md").write_text(SKILL_GHI, encoding="utf-8")
    (b / "skills" / "bao-cao-ngay").mkdir(parents=True)
    (b / "skills" / "bao-cao-ngay" / "SKILL.md").write_text("---\nname: x\ndescription: hệ thống\n---\nthân\n",
                                                             encoding="utf-8")
    md = b / "memory" / "agents" / "bao-cao"
    (md / "runs").mkdir(parents=True)
    (md / "MEMORY.md").write_text("# Bộ nhớ\nChủ viết tay: shop HALIMI.\n\n## Bài học (tự học)\n- Luôn ghi kỳ báo cáo.\n",
                                  encoding="utf-8")
    (md / "runs" / "2026-10-20.md").write_text(
        "\n## 09:00\n**Task:** Báo cáo doanh thu hôm qua cho shop\n\n**Kết quả:** Doanh thu 12.500.000đ\n"
        "\n## 10:00\n**Task:** Tóm tắt đơn huỷ tuần này\n\n**Kết quả:** 3 đơn huỷ\n", encoding="utf-8")
    (md / "runs" / "2026-10-21.md").write_text(
        "\n## 08:30\n**Task:** So sánh doanh thu tuần này với tuần trước\n\n**Kết quả:** tăng 10%\n", encoding="utf-8")
    (b / "notes.md").write_text("ghi chú khác của chủ", encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", str(b)], check=True)
        subprocess.run(["git", "-C", str(b), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(b), "config", "user.name", "t"], check=True)
        subprocess.run(["git", "-C", str(b), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(b), "commit", "-qm", "chore: nền"], check=True)
    return b


is_sys = lambda s: s == "bao-cao-ngay"  # noqa: E731

# ============================================================ cây + validator
goc_tmp = Path(tempfile.mkdtemp(prefix="h2-brain-"))
B = tao_brain(goc_tmp)
cay, info = h2.doc_cay(B, "bao-cao", is_system=is_sys)
check("cây có agent, bài học, kinh nghiệm", {h2.FILE_AGENT, h2.FILE_BAI_HOC, h2.FILE_KINH_NGHIEM} <= set(cay))
check("skill người dùng vào cây", "skills/ghi-chu/SKILL.md" in cay)
check("skill hệ thống KHÔNG vào cây", "skills/bao-cao-ngay/SKILL.md" not in cay)
check("skill hệ thống được ghi lý do không sửa", any(x["skill"] == "bao-cao-ngay" for x in info["khong_sua"]))
check("bài học chỉ là dòng của mục tự học", cay[h2.FILE_BAI_HOC].strip() == "- Luôn ghi kỳ báo cáo.", cay[h2.FILE_BAI_HOC])
check("nhóm đọc từ frontmatter", info["group"] == "Bán hàng" and info["muc_quyen"] == "full")
kc = h2.KiemCtx(skill_co_san={"ghi-chu", "bao-cao-ngay"}, is_system=is_sys)
check("cây gốc hợp lệ", h2.kiem_cay(cay, cay, kc) == [], h2.kiem_cay(cay, cay, kc))


def doi(tree, rel, txt):
    t = dict(tree)
    t[rel] = txt
    return t


loi = h2.kiem_cay(doi(cay, h2.FILE_AGENT, AGENT.replace("muc_quyen: full", "muc_quyen: suggest")), cay, kc)
check("chặn đổi muc_quyen", any("muc_quyen" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, h2.FILE_AGENT, AGENT.replace("model: ''", "model: opus")), cay, kc)
check("chặn đổi model", any("model" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, h2.FILE_AGENT, AGENT.replace("Bạn là", "Bạn — là")), cay, kc)
check("chặn gạch dài", any("U+2014" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, "skills/bao-cao-ngay/SKILL.md", "---\nname: a\ndescription: b\ngroup: c\n---\nx\n"), cay, kc)
check("chặn tạo/sửa skill hệ thống", any("HỆ THỐNG" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, h2.FILE_AGENT, AGENT + "\nh2_diem_luat: 0.9\n"), cay, kc)
check("chặn dấu bảng điểm trong cây", any("bảng điểm" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, h2.FILE_AGENT, AGENT + ("Dặn rất dài. " * 1200)), cay, kc)
check("chặn vượt ngân sách chữ luôn nạp", any("vượt trần" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, "scripts/x.py", "print(1)"), cay, kc)
check("chặn file ngoài bề mặt (script)", any("ngoài bề mặt" in x for x in loi), loi)
loi = h2.kiem_cay(doi(cay, "skills/ghi-chu/SKILL.md", SKILL_GHI.replace("1. Đọc yêu cầu.\n", "")), cay, kc)
check("skill đã có chỉ được nối thêm", any("NỐI THÊM" in x for x in loi), loi)
check("skill đã có nối thêm thì qua",
      h2.kiem_cay(doi(cay, "skills/ghi-chu/SKILL.md", SKILL_GHI + "\n## Bẫy\n- Đừng ghi số tạm.\n"), cay, kc) == [])
moi = doi(cay, "skills/doi-chieu/SKILL.md", "---\nname: Đối chiếu\ndescription: Đối chiếu số POS với báo cáo.\n"
                                            "group: Bán hàng\n---\n## Quy trình\n1. Đối chiếu.\n")
loi = h2.kiem_cay(moi, cay, kc)
check("skill mới chưa nêu tên/chưa gán bị chặn", any("chưa được nêu tên" in x for x in loi)
      and any("chưa được gán" in x for x in loi), loi)
tk = h2.tu_kich_hoat(moi, cay)
check("autotrigger: nối dòng kích hoạt + gán skill", "`doi-chieu`" in tk[h2.FILE_AGENT]
      and "doi-chieu" in h2.chia_frontmatter(tk[h2.FILE_AGENT])[0]["skills"], tk[h2.FILE_AGENT])
check("autotrigger xong thì hợp lệ", h2.kiem_cay(tk, cay, kc) == [], h2.kiem_cay(tk, cay, kc))
check("autotrigger KHÔNG đổi khoá quyền", h2.chia_frontmatter(tk[h2.FILE_AGENT])[0]["muc_quyen"] == "full")
dai = doi(moi, "skills/doi-chieu/SKILL.md", "---\nname: x\ndescription: " + "a" * 200 + "\ngroup: g\n---\nb\n")
check("mô tả skill > 150 ký tự bị chặn", any("tối đa 150" in x for x in h2.kiem_cay(h2.tu_kich_hoat(dai, cay), cay, kc)))
check("bí mật bị chặn khi có bộ quét", any("bí mật" in x for x in h2.kiem_cay(
    doi(cay, h2.FILE_BAI_HOC, "- key sk-abcdefghijklmnop123\n"), cay, kc, quet_bao_mat=lambda t: ["api-key"] if "sk-" in t else [])))

# ============================================================ đề
de = h2.lay_de(B, "bao-cao", n=3, ten_agent=info["name"], de_tay=["Viết báo cáo tháng"])
check("đề: đề tay đứng đầu", de and de[0].nguon == "tay", [d.dau_vao for d in de])
check("đề: lấy việc mới nhất từ nhật ký", any("tuần này với tuần trước" in d.dau_vao for d in de), [d.dau_vao for d in de])
check("đề: tối đa n", len(de) == 3, len(de))
(B / "memory" / "agents" / "bao-cao" / "de-thi.json").write_text(json.dumps({"cases": [
    {"id": "dt1", "cau_hoi": "Doanh thu hôm qua?", "cham": {"kieu": "chua", "dap_an": "12"}}]}), encoding="utf-8")
import danh_gia  # noqa: E402
de2 = h2.lay_de(B, "bao-cao", n=2, doc_bo=danh_gia.doc_bo)
check("đề có đáp án từ de-thi.json", any(d.nguon == "de-thi" and d.case for d in de2))
(B / "memory" / "agents" / "bao-cao" / "de-thi.json").unlink()


# ============================================================ engine giả
class Gia:
    """Executor + improver tất định. Ghi lại số lần gọi để đếm 4k/3k."""

    def __init__(self, thu_muc: Path, *, ghep="merge", ban_chon_rong=False, rut=True, loi_lan_dau=False):
        self.dir = thu_muc
        self.cac_luot, self.cac_phien = [], []
        self.ghep, self.ban_chon_rong, self.rut, self.loi_lan_dau = ghep, ban_chon_rong, rut, loi_lan_dau

    async def chay_luot(self, tree, de, nhan):
        self.cac_luot.append((nhan, de.id))
        jl = self.dir / "qd" / nhan / f"{de.id}.jsonl"
        jl.parent.mkdir(parents=True, exist_ok=True)
        co_skill = "skills/doi-chieu/SKILL.md" in tree
        evs = [{"type": "tool_call", "name": "pos_doanh_thu", "input": {"ngay": "hom-qua"}},
               {"type": "tool_result", "content": "{\"doanh_thu\": 12500000}"},
               {"type": "final", "content": ("Doanh thu 12.500.000đ (đã đối chiếu)" if co_skill else "Doanh thu 12 triệu")}]
        jl.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in evs), encoding="utf-8")
        rong = self.ban_chon_rong and nhan.startswith(("agg", "c"))
        tra = "" if rong else evs[-1]["content"]
        return h2.LuotChay(nhan=nhan, de_id=de.id, ok=True, giao_duoc=bool(tra), tra_loi=tra,
                           tool_da_goi=["pos_doanh_thu"], quy_dao=str(jl), usd=0.01)

    async def phien(self, nhan, nv, goc):
        self.cac_phien.append(nhan)
        hien = {}
        hd = goc / "context" / "harness"
        for f in hd.rglob("*"):
            if f.is_file():
                hien[str(f.relative_to(hd))] = f.read_text(encoding="utf-8")
        ctx_text = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in (goc / "context").rglob("*.md"))
        assert "h2_diem" not in ctx_text and "\"dat\"" not in ctx_text, "điểm lọt vào ngữ cảnh!"
        base = nhan.split(".")[0]
        if self.loi_lan_dau and base.startswith("inv") and nhan.endswith(".a1"):
            return {"tra_loi": "<file path=\"agent.md\">" + hien["agent.md"].replace("muc_quyen: full", "muc_quyen: suggest")
                    + "</file><notes>thử hạ quyền</notes>", "usd": 0.02}
        if base == "chon":
            m = [l for l in nv.splitlines()]
            ids = sorted(p.name for p in (goc / "context" / "candidates").iterdir())
            return {"tra_loi": f"<why>chọn {ids[-1]}</why>\n```choice\n{ids[-1]}\n```", "usd": 0.01}
        if base == "rut":
            if not self.rut:
                return {"tra_loi": "<edits>component: agent.md\nverdict: confounded</edits>\nNO_ENTRY", "usd": 0.01}
            return {"tra_loi": "<edits>component: skills/doi-chieu\ncandidates: dom1\nchange: thêm skill\n"
                               "observed: đối chiếu số\nverdict: helped</edits>\n<experience>\ncue: báo cáo cộng số nhiều nguồn\n"
                               "lesson: thêm skill đối chiếu (skills/doi-chieu) trước khi tóm tắt\n"
                               "evidence: dom1 helped ở mọi đề\nconfidence: medium, một lượt mỗi đề\n</experience>", "usd": 0.01}
        if base.startswith("inv"):
            a = hien["agent.md"].replace("muc_quyen: suggest", "muc_quyen: full").rstrip() + "\nĐọc lại kết quả tool trước khi trả lời.\n"
            return {"tra_loi": f"<file path=\"agent.md\">\n{a}</file>\n<notes>kept -> đọc lại -> base1 bỏ qua</notes>",
                    "usd": 0.02}
        if base.startswith("dom"):
            sk = ("---\nname: Đối chiếu\ndescription: Đối chiếu số POS với báo cáo trước khi tóm tắt.\ngroup: Bán hàng\n"
                  "---\n## Quy trình\n1. Gọi POS.\n2. Đối chiếu.\n")
            return {"tra_loi": f"<file path=\"skills/doi-chieu/SKILL.md\">\n{sk}</file><notes>skill đối chiếu</notes>",
                    "usd": 0.02}
        # người ghép
        if self.ghep == "keep":
            return {"tra_loi": "<notes>KEEP_BASE -> không có bằng chứng</notes>", "usd": 0.02}
        pool = goc / "context" / "pool"
        out = []
        for lab in sorted(p.name for p in pool.iterdir()) if pool.is_dir() else []:
            ph = pool / lab / "harness"
            for f in ph.rglob("*"):
                if not f.is_file():
                    continue
                rel = str(f.relative_to(ph))
                txt = f.read_text(encoding="utf-8")
                if txt != hien.get(rel) and (rel.startswith("skills/doi-chieu") or rel == "agent.md"):
                    out.append(f"<file path=\"{rel}\">\n{txt}</file>")
        return {"tra_loi": "\n".join(out) + "<notes>kept -> inv+dom -> base1</notes>", "usd": 0.02}


def vong(gia: Gia, k, che_do, de_list, *, cham=None, thu_vien=None, nhom="Bán hàng"):
    rd = Path(tempfile.mkdtemp(prefix="h2-vong-"))
    return h2.Vong(slug="bao-cao", run_id="h2-test-1", k=k, che_do=che_do, de=de_list, cay_goc=cay, kiem=kc,
                   thu_muc=rd, chay_luot=gia.chay_luot, phien=gia.phien, mo_ta_viec="Trợ lý báo cáo", nhom=nhom,
                   thu_vien=thu_vien, cham_luat=cham, song_song=2)


DE3 = [h2.De(id=f"d{i}", dau_vao=f"Đề số {i}") for i in range(1, 4)]

# ---- song song k=1 ----
g = Gia(Path(tempfile.mkdtemp()))
kq = asyncio.run(h2.chay_vong(vong(g, 1, "song_song", DE3)))
check("song song k=1: 4k x số đề = 12 lượt", len(g.cac_luot) == 12 and kq.so_cai["so_luot"] == 12, (len(g.cac_luot), kq.so_cai))
check("song song k=1: 3k = 3 phiên trong sổ", kq.so_cai["so_phien"] == 3, kq.so_cai)
check("song song k=1: đẳng thức sổ cái đúng", kq.so_cai["dung_dang_thuc"], kq.so_cai)
check("song song k=1: không gọi bộ chọn (k=1)", "chon" not in [p.split(".")[0] for p in g.cac_phien], g.cac_phien)
check("song song k=1: có rút kinh nghiệm (ngoài sổ)", "rut" in g.cac_phien and "reflector" in kq.so_cai["ngoai_so"])
check("song song k=1: bản chọn là agg1", kq.chon == "agg1", kq.chon)
check("song song k=1: bản chọn có skill mới đã tự kích hoạt", "`doi-chieu`" in kq.cay_chon.get(h2.FILE_AGENT, ""))
check("song song k=1: bản chọn giữ muc_quyen", h2.chia_frontmatter(kq.cay_chon[h2.FILE_AGENT])[0]["muc_quyen"] == "full")
check("song song k=1: không giữ nguyên (có cải tiến)", not kq.giu_nguyen)
check("song song k=1: có bài học", h2.co_kinh_nghiem(kq.kinh_nghiem), kq.kinh_nghiem)
s_inv = kq.stage["inv1"]
check("stage INV mang notes", "đọc lại" in s_inv.notes, s_inv.to_dict())

# ---- nối tiếp k=2 ----
g2 = Gia(Path(tempfile.mkdtemp()))
v2 = vong(g2, 2, "noi_tiep", DE3[:2])
kq2 = asyncio.run(h2.chay_vong(v2))
check("nối tiếp k=2: 4k x số đề = 16 lượt", len(g2.cac_luot) == 16 and kq2.so_cai["so_luot"] == 16, (len(g2.cac_luot), kq2.so_cai))
check("nối tiếp k=2: 3k = 6 phiên trong sổ", kq2.so_cai["so_phien"] == 6, kq2.so_cai)
check("nối tiếp k=2: đẳng thức sổ cái đúng", kq2.so_cai["dung_dang_thuc"], kq2.so_cai)
check("nối tiếp k=2: có bộ chọn (k>1)", "chon" in [p.split(".")[0] for p in g2.cac_phien] and "selector" in kq2.so_cai["ngoai_so"])
check("nối tiếp k=2: bản cuối là c1/c2", set(kq2.finals) == {"c1", "c2"} and kq2.chon in ("c1", "c2"), kq2.finals)
check("nối tiếp k=2: mã ẩn danh A/B", set(kq2.id_map) == {"A", "B"}, kq2.id_map)
check("mã ẩn danh ổn định theo seed", h2.gan_ma(["c1", "c2"], slug="bao-cao", run_id="h2-test-1", k=2, che_do="noi_tiep")
      == kq2.id_map)
h_inv2 = (v2.thu_muc / "stages" / "inv2" / "context" / "harness" / "agent.md").read_text(encoding="utf-8")
check("nối tiếp: vòng 2 sửa trên checkpoint c1 (không phải vỏ gốc)", h_inv2 == kq2.cay["c1"][h2.FILE_AGENT]
      and h_inv2 != cay[h2.FILE_AGENT])
check("nối tiếp: vòng 2 thấy lịch sử vòng 1 trong pool",
      (v2.thu_muc / "stages" / "inv2" / "context" / "pool" / "c1" / "harness").is_dir())

# ---- song song k=2 có bộ chọn ----
g3 = Gia(Path(tempfile.mkdtemp()))
kq3 = asyncio.run(h2.chay_vong(vong(g3, 2, "song_song", DE3[:1])))
check("song song k=2: 8 lượt, 6 phiên", kq3.so_cai["so_luot"] == 8 and kq3.so_cai["so_phien"] == 6, kq3.so_cai)
check("song song k=2: chọn một trong agg1/agg2", kq3.chon in ("agg1", "agg2") and kq3.chon_ok, (kq3.chon, kq3.ly_do_chon))

# ---- KEEP_BASE hợp lệ ----
g4 = Gia(Path(tempfile.mkdtemp()), ghep="keep")
kq4 = asyncio.run(h2.chay_vong(vong(g4, 1, "song_song", DE3[:1])))
check("KEEP_BASE: bản ghép = vỏ gốc, giữ nguyên", kq4.giu_nguyen and kq4.cay_chon == cay)
check("KEEP_BASE: stage agg1 kept_base, không fell_back", kq4.stage["agg1"].kept_base and not kq4.stage["agg1"].fell_back)
check("KEEP_BASE: không tốn phiên rút kinh nghiệm", "rut" not in g4.cac_phien, g4.cac_phien)


# ---- chặn an toàn bằng luật ----
async def cham_ha(de_list, luot):
    # bản gốc đạt, bản ghép trượt (giả lập "composer chọn bản 55 thay 95")
    return {d.id: (luot[0].nhan.startswith("base") if luot else False) for d in de_list if d.case}

DE_DA = [h2.De(id="dt-1", dau_vao="Doanh thu?", nguon="de-thi", case={"id": "1", "cau_hoi": "x", "cham": {"kieu": "chua", "dap_an": "1"}})]
g5 = Gia(Path(tempfile.mkdtemp()))
kq5 = asyncio.run(h2.chay_vong(vong(g5, 1, "song_song", DE_DA, cham=cham_ha)))
check("chặn an toàn: điểm luật hạ thì tự KEEP_BASE", kq5.giu_nguyen and "thấp hơn vỏ gốc" in kq5.chan_an_toan, kq5.chan_an_toan)
check("chặn an toàn: điểm lưu ngoài ngữ cảnh", "h2_diem_luat" in kq5.diem)
check("chặn an toàn: không rút kinh nghiệm khi giữ nguyên", "rut" not in g5.cac_phien)

g6 = Gia(Path(tempfile.mkdtemp()), ban_chon_rong=True)
kq6 = asyncio.run(h2.chay_vong(vong(g6, 1, "song_song", DE3[:1])))
check("chặn an toàn: bản ghép không giao được (UNSAFE) thì giữ nguyên", kq6.giu_nguyen and "UNSAFE" in kq6.chan_an_toan,
      kq6.chan_an_toan)

# ---- thử lại 1 lần rồi fell_back ----
g7 = Gia(Path(tempfile.mkdtemp()), loi_lan_dau=True)
kq7 = asyncio.run(h2.chay_vong(vong(g7, 1, "song_song", DE3[:1])))
check("đề xuất hạ quyền bị loại, thử lại lần 2 thì qua", kq7.stage["inv1"].lan_thu == 2 and not kq7.stage["inv1"].fell_back,
      kq7.stage["inv1"].to_dict())
check("lần 2 nhận được lỗi validator nguyên văn", any(p == "inv1.a2" for p in g7.cac_phien))


class LuonSai(Gia):
    async def phien(self, nhan, nv, goc):
        self.cac_phien.append(nhan)
        if nhan.startswith("inv"):
            return {"tra_loi": "<file path=\"scripts/x.py\">print(1)</file><notes>x</notes>"}
        return await Gia.phien(self, nhan, nv, goc)

g8 = LuonSai(Path(tempfile.mkdtemp()))
kq8 = asyncio.run(h2.chay_vong(vong(g8, 1, "song_song", DE3[:1])))
check("hỏng cả 2 lần thì fell_back về vỏ gốc", kq8.stage["inv1"].fell_back and kq8.cay["inv1"] == cay, kq8.stage["inv1"].to_dict())
check("fell_back vẫn ghi đúng 1 phiên vào sổ", kq8.so_cai["dung_dang_thuc"], kq8.so_cai)

# ---- trần ----
g9 = Gia(Path(tempfile.mkdtemp()))
v9 = vong(g9, 1, "song_song", DE3)
v9.tran = h2.Tran(luot_max=5)
try:
    asyncio.run(h2.chay_vong(v9))
    check("vượt trần lượt thì dừng", False)
except h2.VuotTran:
    check("vượt trần lượt thì dừng", True)
check("dừng ở trần: không chạy quá trần", len(g9.cac_luot) + len(g9.cac_phien) <= 5, (len(g9.cac_luot), len(g9.cac_phien)))

# ---- trajectory render ----
txt = h2.ve_quy_dao([{"type": "tool_call", "name": "zalo_send", "input": {"m": "x"}},
                     {"type": "tool_result", "content": "GIẢ LẬP (chạy thử): đã không thực hiện zalo_send"},
                     {"type": "tool_result", "content": "ERROR: hỏng"},
                     {"type": "gia_lap", "tool": "zalo_send", "nguon": "plugin:z", "args": {}},
                     {"type": "tool_result", "content": "a" * (h2.OBS_TRUNC + 10)}])
check("render: ACTION / GIẢ LẬP / OBSERVATION ERROR", "[ACTION] zalo_send" in txt and "[GIẢ LẬP]" in txt
      and "[OBSERVATION ERROR]" in txt)
check("render: dấu cắt rõ ràng, không gạch dài", "cắt khi hiển thị" in txt and "—" not in txt)

# ============================================================ thư viện
tv = h2.them_vao_thu_vien(B, nhom="Bán hàng", slug="bao-cao", run_id="h2-x-1", cay=kq.cay_chon, kinh_nghiem={},
                          ly_do="", edits="", nhan="agg1", ngay="2026-10-24")
check("thư viện: không đủ cue/lesson/evidence thì KHÔNG ghi", tv is None and h2.ngu_canh_thu_vien(B, "Bán hàng") is None)
tv = h2.them_vao_thu_vien(B, nhom="Bán hàng", slug="bao-cao", run_id="h2-x-1", cay=kq.cay_chon, kinh_nghiem=kq.kinh_nghiem,
                          ly_do="vì", edits=kq.edits, nhan="agg1", ngay="2026-10-24")
check("thư viện: đủ thì ghi NGUYÊN cây + EXPERIENCE", tv and any(x.endswith("EXPERIENCE.md") for x in tv)
      and any("/harness/agent.md" in x for x in tv), tv)
d_tv = h2.thu_muc_thu_vien(B, "Bán hàng")
(d_tv / "INDEX.md").write_text("hỏng", encoding="utf-8")
idx = h2.dung_index(d_tv)
check("thư viện: INDEX dựng lại từ đĩa", "cue: báo cáo cộng số nhiều nguồn" in idx, idx)
check("thư viện: cùng nhóm đọc được", h2.ngu_canh_thu_vien(B, "Bán hàng") is not None)
check("thư viện: nhóm khác không thấy", h2.ngu_canh_thu_vien(B, "Marketing") is None)
check("thư viện: tên thư mục nhóm ASCII", d_tv.name == "ban-hang", d_tv.name)
g10 = Gia(Path(tempfile.mkdtemp()))
v10 = vong(g10, 1, "song_song", DE3[:1], thu_vien=h2.ngu_canh_thu_vien(B, "Bán hàng"))
asyncio.run(h2.chay_vong(v10))
check("thư viện: editor cùng nhóm nhận context/library",
      (v10.thu_muc / "stages" / "inv1" / "context" / "library" / "INDEX.md").is_file())
check("thư viện: người ghép cũng nhận context/library",
      (v10.thu_muc / "stages" / "agg1" / "context" / "library" / "INDEX.md").is_file())
check("thư viện: rút kinh nghiệm KHÔNG đọc thư viện",
      not (v10.thu_muc / "stages" / "rut" / "context" / "library").exists())
shutil.rmtree(d_tv.parent)

# ============================================================ áp dụng + hoàn tác (qua Harness2Feature, brain git tạm)


def feature(brain_dir: Path, engine_factory=None):
    deps = noi.Deps(
        brain_root=lambda b: str(brain_dir), state_dir=Path(_STATE),
        workflow_agent_helpers=lambda brain, tools, m: (None, lambda s: ("x", f"SYS {brain}", None, ""), None, None),
        boc_bai_hoc=lambda out: ([], out), claude_engine=engine_factory or (lambda **k: None),
        readonly_tools=["Read", "Glob", "Grep", "LS"], empty_mcp_file=lambda: None, aux_model=lambda: "",
        agent_model_provider=lambda m, p: p or "anthropic-cli", bo_vao_hom_thu=None, is_system_skill=is_sys,
        hub_url=lambda: "http://127.0.0.1:7777/hub/mcp", hub_token=lambda: "TOKEN", song_song=1)
    return noi.Harness2Feature(deps)


if shutil.which("git"):
    goc_g = Path(tempfile.mkdtemp(prefix="h2-git-"))
    BG = tao_brain(goc_g, git=True)
    cay_g, _ = h2.doc_cay(BG, "bao-cao", is_system=is_sys)
    f = feature(BG)
    rid = "h2-20261024-000000-ab12"
    rd = f.thu_muc(rid)
    ket = {"trang_thai": "xong", "giu_nguyen": False, "brain": "brain", "slug": "bao-cao", "nhom": "Bán hàng",
           "cay_goc": cay_g, "cay_chon": kq.cay_chon, "kinh_nghiem": kq.kinh_nghiem, "ly_do_chon": "vì", "edits": kq.edits,
           "chon": "agg1", "de": [{"id": "d1"}], "diem": {}}
    noi._ghi_json(rd / "ket-qua.json", ket)
    notes_truoc = (BG / "notes.md").read_text(encoding="utf-8")
    r = f.ap_dung(rid)
    check("áp dụng: ok + có commit harness:", r.get("ok") and r.get("commit"), r)
    log = subprocess.run(["git", "-C", str(BG), "log", "-1", "--pretty=%s"], capture_output=True, text=True).stdout
    check("áp dụng: tiêu đề commit tiền tố harness:", log.startswith("harness:"), log)
    check("áp dụng: harness: KHÔNG lọt vào danh sách commit học", git_brain.list_learn_commits(str(BG)) == [])
    meta_sau, body_sau, _c = h2.chia_frontmatter((BG / "agents" / "bao-cao.md").read_text(encoding="utf-8"))
    check("áp dụng: giữ khoá quyền/model/nhóm", meta_sau["muc_quyen"] == "full" and meta_sau["model"] == ""
          and meta_sau["group"] == "Bán hàng", meta_sau)
    check("áp dụng: gán skill mới", "doi-chieu" in meta_sau["skills"], meta_sau["skills"])
    check("áp dụng: skill mới được ghi", (BG / "skills" / "doi-chieu" / "SKILL.md").is_file())
    check("áp dụng: file ngoài cây không đổi", (BG / "notes.md").read_text(encoding="utf-8") == notes_truoc)
    mem = (BG / "memory" / "agents" / "bao-cao" / "MEMORY.md").read_text(encoding="utf-8")
    check("áp dụng: phần chủ viết tay trong MEMORY giữ nguyên", "Chủ viết tay: shop HALIMI." in mem)
    kn = (BG / "memory" / "agents" / "bao-cao" / "kinh-nghiem.md").read_text(encoding="utf-8")
    check("áp dụng: kinh-nghiem.md có run id, đề, trước/sau", rid in kn and "Đề: d1" in kn and "Trước/sau" in kn, kn)
    check("áp dụng: thư viện chỉ ghi khi đã áp dụng", h2.ngu_canh_thu_vien(BG, "Bán hàng") is not None)
    check("áp dụng lần 2 bị từ chối", not f.ap_dung(rid).get("ok"))
    u = f.hoan_tac(rid)
    check("hoàn tác bằng git revert", u.get("ok") and "git revert" in u.get("cach", ""), u)
    check("hoàn tác: agent về bản cũ", (BG / "agents" / "bao-cao.md").read_text(encoding="utf-8") == AGENT)
    check("hoàn tác: skill mới biến mất", not (BG / "skills" / "doi-chieu" / "SKILL.md").exists())
    check("hoàn tác: thư viện cũng gỡ theo", h2.ngu_canh_thu_vien(BG, "Bán hàng") is None)
    check("revert_commit từ chối commit khác tiền tố",
          not git_brain.revert_commit(str(BG), subprocess.run(["git", "-C", str(BG), "rev-parse", "--short", "HEAD~2"],
                                                               capture_output=True, text=True).stdout.strip(),
                                      prefix="harness:").get("ok"))
    # Trợ lý bị sửa sau lần chạy -> không áp dụng đề xuất cũ.
    rid2 = "h2-20261024-000001-cd34"
    noi._ghi_json(f.thu_muc(rid2) / "ket-qua.json", dict(ket, cay_goc=cay_g))
    (BG / "agents" / "bao-cao.md").write_text(AGENT + "\nChủ vừa sửa tay.\n", encoding="utf-8")
    check("áp dụng từ chối khi trợ lý đã đổi sau lần chạy", "đã bị sửa" in (f.ap_dung(rid2).get("error") or ""))
else:
    print("bỏ qua phần git: máy không có git")

# ---- không git: hoàn tác bằng bản cũ ----
goc_n = Path(tempfile.mkdtemp(prefix="h2-nogit-"))
BN = tao_brain(goc_n)
cay_n, _ = h2.doc_cay(BN, "bao-cao", is_system=is_sys)
fn = feature(BN)
rid3 = "h2-20261024-000002-ef56"
noi._ghi_json(fn.thu_muc(rid3) / "ket-qua.json", {"trang_thai": "xong", "giu_nguyen": False, "brain": "brain",
                                                  "slug": "bao-cao", "nhom": "Bán hàng", "cay_goc": cay_n,
                                                  "cay_chon": kq.cay_chon, "kinh_nghiem": {}, "de": [], "diem": {}})
r3 = fn.ap_dung(rid3)
check("không git: áp dụng ok, không commit", r3.get("ok") and not r3.get("commit"), r3)
check("không git: không ghi thư viện khi không có bài học", h2.ngu_canh_thu_vien(BN, "Bán hàng") is None)
u3 = fn.hoan_tac(rid3)
check("không git: hoàn tác bằng bản cũ", u3.get("ok") and (BN / "agents" / "bao-cao.md").read_text(encoding="utf-8") == AGENT, u3)
check("không git: skill tạo mới bị gỡ", not (BN / "skills" / "doi-chieu").joinpath("SKILL.md").exists())


# ============================================================ engine chạy thử + brain tạm biến mất
class EngGia:
    def __init__(self, **k):
        self.k = k
        self.allowed_tools = k.get("allowed_tools")
        self.mcp_config = None
        self.hanh_vi = None

    async def query(self, prompt):
        if callable(EngGia.hanh_vi):
            EngGia.hanh_vi(self)
        yield {"type": "text", "content": "đang làm"}
        yield {"type": "final", "content": "xong", "cost_usd": 0.001}

ENG = []


def eng_factory(**k):
    e = EngGia(**k)
    ENG.append(e)
    return e

goc_e = Path(tempfile.mkdtemp(prefix="h2-eng-"))
BE = tao_brain(goc_e)
fe = feature(BE, eng_factory)
cay_e, info_e = h2.doc_cay(BE, "bao-cao", is_system=is_sys)
rid4 = "h2-20261024-000003-aa11"
fe.thu_muc(rid4).mkdir(parents=True, exist_ok=True)
chay_luot, phien, don_dep, tk = fe._ngu_canh_chay(rid4, "brain", "bao-cao", info_e, {"provider": "anthropic-cli", "model": ""},
                                                   {"provider": "anthropic-cli", "model": ""})
check("brain nền: chép file chữ, bỏ nhật ký runs", (fe.thu_muc(rid4) / "nao-nen" / "notes.md").is_file()
      and not (fe.thu_muc(rid4) / "nao-nen" / "memory" / "agents" / "bao-cao" / "runs").exists(), tk)
EngGia.hanh_vi = None
l = asyncio.run(chay_luot(cay_e, h2.De(id="d1", dau_vao="Báo cáo"), "base1"))
e0 = ENG[-1]
check("lượt thử Claude: allowlist KHÔNG None, có mcp__javis", e0.allowed_tools and "mcp__javis" in e0.allowed_tools,
      e0.allowed_tools)
check("lượt thử Claude: cấm Bash/Write/Edit/Web/Task", all(x in e0.disallowed_tools for x in
                                                          ("Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task")))
check("lượt thử Claude: MCP strict (không nạp MCP sẵn của máy)", e0.mcp_strict is True)
cfg = json.loads(Path(e0.mcp_config).read_text(encoding="utf-8"))["mcpServers"]["javis"]["headers"]
check("cấu hình MCP riêng mang cờ chạy thử hợp lệ", che_do_thu.ma_hop_le(cfg.get(che_do_thu.HEADER, "")), cfg)
check("cấu hình MCP riêng trỏ brain TẠM, không phải brain thật",
      che_do_thu.la_brain_tam(cfg["X-Javis-Vault"]) and Path(cfg["X-Javis-Vault"]).resolve() != BE.resolve(), cfg)
check("cấu hình MCP liệt kê theo mức của trợ lý", cfg["X-Javis-Mode"] == "full")
check("lượt thử: giao được và có trajectory", l.giao_duoc and Path(l.quy_dao).is_file(), l.to_dict())


def xoa_slot(eng):
    shutil.rmtree(eng.k["cwd"], ignore_errors=True)

EngGia.hanh_vi = xoa_slot
anh_truoc = noi._anh_chup(BE)
try:
    asyncio.run(chay_luot(cay_e, h2.De(id="d2", dau_vao="Báo cáo"), "inv1"))
    check("brain tạm biến mất giữa chừng -> DỪNG", False)
except h2.NaoTamMat:
    check("brain tạm biến mất giữa chừng -> DỪNG", True)
check("brain thật không bị đụng sau khi brain tạm mất", noi._anh_chup(BE) == anh_truoc)
EngGia.hanh_vi = None
check("bộ não Codex bị từ chối chạy thử", not fe.ho_tro({"provider": "openai-oauth"})[0])
check("bộ não Grok bị từ chối chạy thử", not fe.ho_tro({"provider": "grok-cli"})[0])
don_dep()
check("dọn brain tạm sau lượt", not (fe.thu_muc(rid4) / "nao-nen").exists()
      and not (fe.thu_muc(rid4) / "nao-0").exists())

# ---- phiên cải tiến: Claude chỉ đọc, MCP rỗng; API chỉ có 2 tool khoá trong thư mục ----
ec = fe.dung_engine_cai_tien(Path(tempfile.mkdtemp()), {"provider": "anthropic-cli"})
check("phiên cải tiến Claude: chỉ server đọc thư mục bằng chứng", ec.allowed_tools == ["mcp__harness"], ec.allowed_tools)
check("phiên cải tiến Claude: cấm Write/Edit/Bash/Read", all(x in ec.disallowed_tools for x in ("Write", "Edit", "Bash", "Read")))
tg = Path(tempfile.mkdtemp())
(tg / "context").mkdir()
(tg / "context" / "a.md").write_text("bằng chứng", encoding="utf-8")
(tg.parent / "bi-mat.txt").write_text("không được đọc", encoding="utf-8")
tools, route = noi.tool_doc_thu_muc(tg)
check("tool API đọc được file trong thư mục", asyncio.run(route["doc_file"]["call"]({"path": "context/a.md"})) == "bằng chứng")
check("tool API không trèo ra ngoài thư mục", asyncio.run(route["doc_file"]["call"]({"path": "../bi-mat.txt"})).startswith("ERROR"))
check("tool API không có tool ghi", {t["fn"] for t in tools} == {"doc_file", "liet_ke"})

# ============================================================ mã nguồn
for f_ in ("harness2.py", "harness2_noi.py", "che_do_thu.py"):
    src = (SERVER / f_).read_text(encoding="utf-8")
    check(f"{f_}: không gạch dài", "—" not in src)
    import re as _re
    check(f"{f_}: không import main", not _re.search(r"^\s*(import main\b|from main\b)", src, _re.M))
check("harness2.py ghi nguồn Harness² Apache 2.0", "arXiv 2610.14224" in (SERVER / "harness2.py").read_text(encoding="utf-8")
      and "Apache 2.0" in (SERVER / "harness2.py").read_text(encoding="utf-8"))
check("git_brain: harness: KHÔNG nằm trong LEARN_COMMIT_PREFIXES", "harness:" not in git_brain.LEARN_COMMIT_PREFIXES)
check("docs/harness2.md có ghi nguồn", (ROOT / "docs" / "harness2.md").is_file()
      and "Apache 2.0" in (ROOT / "docs" / "harness2.md").read_text(encoding="utf-8"))

shutil.rmtree(_STATE, ignore_errors=True)
print()
print("FAIL: " + ", ".join(fails) if fails else "ALL OK")
raise SystemExit(1 if fails else 0)
