"""26.10.176: kiem_bao_cao.py (lãi tạm tính + tổng bảng) và kiểu chấm "bao_cao" của danh_gia.

    python3 tests/python/test_kiem_bao_cao.py
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
from pathlib import Path

import danh_gia as dg
import kiem_bao_cao as kb

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- đọc số kiểu Việt ----------
check("6.457,5 = 6457.5", kb.doc_so_vn("6.457,5") == 6457.5)
check("20.294 = 20294 (nghìn)", kb.doc_so_vn("20.294") == 20294)
check("12,64% = 12.64", kb.doc_so_vn("12,64%") == 12.64)
check("chữ trần không phải số", kb.doc_so_vn("Đơn chốt") is None)

# ---------- bảng quý 3 thật (ảnh bố 19/10): cột Q3 = T7+T8+T9 ----------
BANG_DUNG = """
| Chỉ số | T7 | T8 | T9 | Q3 | T10 (1-19/10) |
|---|---|---|---|---|---|
| Đơn chốt | 20.294 | 28.020 | 22.376 | 70.690 | 8.828 |
| Doanh thu chốt (tr đ) | 6.457,5 | 8.555,0 | 6.941,5 | 21.954,0 | 2.780,1 |
| Đơn đã nhận | 12.345 | 12.638 | 14.034 | 39.017 | 8.900 |
| Chi ads (tr đ) | 920,3 | 1.010,5 | 844,2 | 2.775,0 | 320,7 |
| CPO (đ/đơn) | 45.350 | 36.065 | 37.726 | 39.256 | 36.322 |
| Ads / doanh thu chốt | 14,25% | 11,81% | 12,16% | 12,64% | 11,53% |
"""
check("bảng quý đúng -> không lỗi", kb.kiem_tong_bang(BANG_DUNG) == [], kb.kiem_tong_bang(BANG_DUNG))
check("CPO và % không bị cộng", all("CPO" not in x and "Ads /" not in x for x in kb.kiem_tong_bang(BANG_DUNG)))

BANG_SAI = BANG_DUNG.replace("21.954,0", "22.954,0")
l = kb.kiem_tong_bang(BANG_SAI)
check("tổng doanh thu quý sai 1.000 triệu -> bắt", len(l) == 1 and "Doanh thu chốt" in l[0], l)

# ---------- dòng Tổng: lỗi 319,52 so với 319,88 ----------
ADS = """
| Nhóm | Chi ads (triệu) |
|---|---|
| HALIMI 1 | 120,10 |
| HALIMI 2 | 99,42 |
| MeiMei | 100,00 |
| Tổng | 319,88 |
"""
l = kb.kiem_tong_bang(ADS)
check("nhóm cộng 319,52 mà tổng ghi 319,88 -> bắt", len(l) == 1 and "319,88" in l[0], l)
check("tổng khớp -> sạch", kb.kiem_tong_bang(ADS.replace("319,88", "319,52")) == [])
check("sai số làm tròn nhỏ được bỏ qua",
      kb.kiem_tong_bang(ADS.replace("319,88", "319,53")) == [])
check("không có bảng -> không lỗi", kb.kiem_tong_bang("Doanh thu 100 triệu, ads 20 triệu.") == [])
check("bảng một dòng không bị ép cộng", kb.kiem_tong_bang("| a | b |\n|---|---|\n| Tổng | 5 |\n") == [])

# ---------- lãi tạm tính ----------
TOT = ("Lãi tạm tính quý 3 khoảng 4,2 tỷ, giá vốn ước tính 45% doanh thu, đã trừ ads 2,78 tỷ.")
check("có lãi + ước tính + giá vốn -> đạt", kb.kiem_lai(TOT) == [], kb.kiem_lai(TOT))
check("không có phần lãi -> lỗi", any("không có phần lãi" in x for x in kb.kiem_lai("Doanh thu 21,9 tỷ, ads 2,7 tỷ.")))
check("lãi trần không nói ước tính -> lỗi",
      any("tạm tính" in x for x in kb.kiem_lai("Lãi quý 3 là 4,2 tỷ, giá vốn 45%.")))
check("lãi không nói giả định giá vốn -> lỗi",
      any("giá vốn" in x for x in kb.kiem_lai("Lãi tạm tính quý 3 là 4,2 tỷ.")))
CHOI = "Chưa tính được lãi quý 3 vì chưa có giá vốn trong dữ liệu. Doanh thu 21,9 tỷ."
check("từ chối vì thiếu giá vốn -> lỗi riêng", any("từ chối" in x for x in kb.kiem_lai(CHOI)), kb.kiem_lai(CHOI))
check("báo cáo ngày không bắt lãi", kb.kiem_bao_cao("Hôm nay 120 đơn.", can_lai=False) == [])

# ---------- tích hợp danh_gia: kiểu chấm bao_cao ----------
check("KIEU_CHAM có bao_cao", "bao_cao" in dg.KIEU_CHAM)
dat, _ = dg.cham_noi_dung(TOT + "\n" + BANG_DUNG, {"kieu": "bao_cao"}, None)
check("danh_gia: báo cáo tốt -> đạt", dat)
dat, ly = dg.cham_noi_dung(CHOI, {"kieu": "bao_cao"}, None)
check("danh_gia: từ chối lãi -> trượt, lý do rõ", (not dat) and "từ chối" in ly, ly)
dat, _ = dg.cham_noi_dung(BANG_SAI, {"kieu": "bao_cao", "can_lai": False}, None)
check("danh_gia: tổng sai -> trượt", not dat)

# ---------- bộ đề mẫu nạp được, có ca bao_cao, không cần su_that ----------
cases = dg.doc_bo(ROOT / "system" / "danh-gia" / "bo-cham-diem.json")
bc = [c for c in cases if (c.get("cham") or {}).get("kieu") == "bao_cao"]
check("bộ mẫu có ít nhất 3 ca bao_cao", len(bc) >= 3, [c["id"] for c in bc])

# ---------- skill hệ thống nói rõ luật ----------
sk = (ROOT / ".claude" / "skills" / "bao-cao-ngay" / "SKILL.md").read_text(encoding="utf-8")
check("skill có mục lãi tạm tính", "LUÔN có lãi tạm tính" in sk)
check("skill cấm từ chối lãi vì thiếu giá vốn", "KHÔNG được từ chối" in sk)
mo = {l.split(":", 1)[0]: l.split(":", 1)[1].strip() for l in sk.splitlines()[1:8] if ":" in l}
check("description skill không quá 150 ký tự", len(mo.get("description", "x" * 999)) <= 150, mo.get("description"))
check("không có gạch dài trong skill và module",
      "—" not in sk and "—" not in (SERVER / "kiem_bao_cao.py").read_text(encoding="utf-8"))

print()
print("FAIL: " + ", ".join(fails) if fails else "ALL OK")
raise SystemExit(1 if fails else 0)
