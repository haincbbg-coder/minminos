"""test_thu_tu_dung.py - Thứ tự dùng mô hình và danh sách khoá đánh số (26.10.309).

    python tests/run.py thu_tu_dung      (KHÔNG mạng)
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import ROOT, SERVER  # noqa: E402,F401

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-tt-"))

import be_khoa as bk  # noqa: E402
import thu_tu_dung as tt  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- chuyển đổi cài đặt cũ ----------
m = {"main": {"provider": "openai-oauth", "model": "gpt-5.5"}, "reasoning": "high"}
check("chuyển đổi: có đổi", tt.chuyen_doi(m, ["anthropic-cli", "openai-oauth", "groq"]))
check("chuyển đổi: MAIN cũ đứng đầu, nhà kết nối khác theo sau", m["thu_tu"] == ["openai-oauth", "anthropic-cli", "groq"], m["thu_tu"])
check("chuyển đổi: MAIN giữ model + Effort", tt.the(m, "openai-oauth") == {"model": "gpt-5.5", "reasoning": "high"})
check("chuyển đổi: main/reasoning không đổi", m["main"] == {"provider": "openai-oauth", "model": "gpt-5.5"} and m["reasoning"] == "high")
snap = dict(m)
check("chuyển đổi chạy lại: không đổi gì", not tt.chuyen_doi(m, ["groq"]) and m["thu_tu"] == snap["thu_tu"])

# ---------- đổi thứ tự / lên đầu / Đảo ----------
tt.dat_the(m, "groq", model="llama-3.3", reasoning="low")
tt.dat_thu_tu(m, ["groq", "openai-oauth", "anthropic-cli"])
check("kéo thả: MAIN theo thẻ đầu", m["main"] == {"provider": "groq", "model": "llama-3.3"} and m["reasoning"] == "low")
check("kéo thả: thẻ cũ không nhảy model", tt.the(m, "openai-oauth")["model"] == "gpt-5.5")
tt.doi_cho(m, 0)
check("Đảo: MAIN và Dự phòng 1 đổi chỗ", m["thu_tu"][:2] == ["openai-oauth", "groq"] and m["main"]["provider"] == "openai-oauth")
tt.len_dau(m, "anthropic-cli", "opus")
check("chọn ở khung chat: thẻ lên đầu, các thẻ khác giữ thứ tự",
      m["thu_tu"] == ["anthropic-cli", "openai-oauth", "groq"] and m["main"]["model"] == "opus", m["thu_tu"])
tt.them_cuoi(m, "gemini")
check("nhà mới kết nối vào cuối", m["thu_tu"][-1] == "gemini")
tt.bo_ra(m, "anthropic-cli")
check("ngắt MAIN: thẻ kế lên làm MAIN", m["main"]["provider"] == "openai-oauth")
check("thu_tu theo kết nối: bỏ nhà mất kết nối, nối nhà mới",
      tt.thu_tu(m, ["groq", "openai-oauth", "xai"]) == ["openai-oauth", "groq", "xai"])

# ---------- hết lượt + đường kế ----------
tt.xoa_het_luot()
tt.ghi_het_luot("openai-oauth", den=10_000_000_000)
check("gói hết lượt: biết giờ mở lại", tt.het_luot_den("openai-oauth") == 10_000_000_000)
ke = tt.duong_ke(m, None, lambda p: not tt.het_luot_den(p))
check("đường kế: bỏ nhà hết lượt, lấy thẻ kế", ke == "groq", ke)
check("đường kế: bỏ nhà đã thử trong lượt", tt.duong_ke(m, None, lambda p: True, da_thu=("openai-oauth", "groq")) == "gemini")
check("không còn đường: rỗng", tt.duong_ke(m, None, lambda p: False) == "")
tt.xoa_het_luot()

# ---------- chuỗi việc nền ----------
m2 = {"thu_tu": ["anthropic-cli", "openai-oauth", "groq"], "auxiliary": {"provider": "anthropic-cli", "model": "haiku", "reasoning": "low"}}
c = tt.chuoi_nen(m2, mac_dinh={"groq": {"model": "llama"}}, mot_lan=("anthropic-cli", "openai-oauth"))
check("chuỗi nền: mô hình nền -> dự phòng -> MAIN sau cùng, gói chỉ một lần",
      [(b["provider"], b["model"]) for b in c] == [("anthropic-cli", "haiku"), ("openai-oauth", ""), ("groq", "llama")], c)
check("chuỗi nền: bước đầu giữ Effort riêng", c[0]["reasoning"] == "low")

# ---------- danh sách khoá đánh số ----------
bk.xoa_trang_thai()
mk = {"openrouter_key": "sk-A", "be_khoa": {"openrouter": ["sk-B", "sk-C"]}}
ds = bk.muc(mk, "openrouter", "openrouter_key")
check("bể cũ đọc thành danh sách đánh số, khoá chính là khoá 1", [a["khoa"] for a in ds] == ["sk-A", "sk-B", "sk-C"])
check("chuyển đổi bể khoá: có đổi", bk.chuyen_doi(mk, {"openrouter": "openrouter_key"}))
check("sau chuyển đổi: chất liệu khoá nằm ở be_khoa_ma, danh sách không chứa khoá",
      "sk-B" not in str(mk["be_khoa"]) and set(mk["be_khoa_ma"].values()) == {"sk-A", "sk-B", "sk-C"})
check("chuyển đổi lại: không nhân đôi", not bk.chuyen_doi(mk, {"openrouter": "openrouter_key"}) and len(mk["be_khoa"]["openrouter"]) == 3)
ids = [a["id"] for a in bk.muc(mk, "openrouter", "openrouter_key")]
check("id ổn định giữa đọc trước và sau chuyển đổi", ids == [a["id"] for a in ds])
# Tắt khoá 1, đổi tên khoá 2: trường cũ = khoá BẬT đầu tiên
ds = bk.muc(mk, "openrouter", "openrouter_key")
ds[0]["bat"] = False
ds[1]["ten"] = "Dự án B"
bk.luu_muc(mk, "openrouter", ds, "openrouter_key")
check("tắt khoá 1: trường cũ thành khoá 2", mk["openrouter_key"] == "sk-B")
check("tắt khoá 1: không còn trong danh sách dùng", bk.danh_sach("openrouter", mk, mk["openrouter_key"]) == ["sk-B", "sk-C"])
check("đổi tên lưu được", bk.muc(mk, "openrouter", "openrouter_key")[1]["ten"] == "Dự án B")
# Chuyển lên/xuống + gỡ
ds = bk.muc(mk, "openrouter", "openrouter_key")
bk.luu_muc(mk, "openrouter", [ds[2], ds[1]], "openrouter_key")
check("gỡ khoá: chất liệu khoá cũng bị xoá", "sk-A" not in mk["be_khoa_ma"].values())
check("đổi thứ tự: khoá C lên đầu", mk["openrouter_key"] == "sk-C")
# Hết lượt theo thứ tự
bk.xoa_trang_thai()
keys = bk.danh_sach("openrouter", mk, mk["openrouter_key"])
bk.bao_loi("openrouter", "sk-C", 429)
check("khoá 1 hết lượt: chọn khoá 2", bk.chon("openrouter", keys) == "sk-B")
check("khoá đang nghỉ có giờ mở lại", bk.nghi_den("openrouter", "sk-C") > 0)
check("còn khoá dùng được", bk.con_khoa_dung_duoc("openrouter", mk, mk["openrouter_key"]))
bk.bao_loi("openrouter", "sk-B", 429)
check("mọi khoá nghỉ: nhà tính là hết lượt", not bk.con_khoa_dung_duoc("openrouter", mk, mk["openrouter_key"]))
bk.xoa_trang_thai()

# ---------- máy chủ: không lộ khoá, có đủ đường ----------
src = (SERVER / "main.py").read_text(encoding="utf-8")
check("GET /settings bỏ be_khoa_ma và bể khoá thô", 'safe["model"].pop("be_khoa_ma", None)' in src and 'safe["model"].pop("be_khoa", None)' in src)
check("POST /settings nhận thu_tu, the, khoa", all(x in src for x in ('patch.get("thu_tu")', 'patch.get("the")', 'patch.get("khoa")')))
check("chat chạy lại bằng đường kế khi chưa nhả gì", "_hops_left=DOI_DUONG_TOI_DA" in src and '"type": "reroute"' in src)
check("hết lượt giữa chừng: thẻ Chạy lại ngay, không tự chạy", "partial=True" in src and "auto_default=False, partial=True" in src)
check("Telegram cũng đổi đường, bot chuyên trách thì không", "not bot and not _da_lam[0]" in src)
import config as cfgmod  # noqa: E402
check("khoá trong danh sách được mã hoá", "model.be_khoa_ma.*" in cfgmod._SECRET_PATHS)
# Từ chối xoay nhiều tài khoản gói thuê bao vẫn còn nguyên.
check("CANARY: bể khoá không áp cho gói thuê bao",
      not any(p in bk.API_CO_BE for p in ("anthropic-cli", "openai-oauth", "grok-cli", "antigravity-cli")))
check("CANARY: không em dash trong module mới",
      "\u2014" not in (SERVER / "thu_tu_dung.py").read_text(encoding="utf-8")
      and "\u2014" not in (SERVER / "be_khoa.py").read_text(encoding="utf-8"))

if fails:
    print("ĐỎ", len(fails), fails)
    sys.exit(1)
print("OK - test_thu_tu_dung: tất cả pass")
