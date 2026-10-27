"""Công tắc "Trả lời gọn" (26.10.269): mặc định TẮT, bật thì cả hai đường dựng prompt đều nhận luật.

    python tests/run.py tra_loi_gon

Vì sao phải kiểm cả hai đường: mức Siêu tiết kiệm (mặc định) dựng capsule qua
`context_compiler`, KHÔNG đi qua `build_system_prompt`. Bật công tắc mà chỉ một đường nhận
luật thì người dùng bật xong vẫn thấy MinMin dài dòng y như cũ.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-tlg-")

import config as cfg  # noqa: E402
import context_compiler as cc  # noqa: E402
import main  # noqa: E402

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {extra}" if not cond and extra else ""))
    if not cond:
        _fails.append(name)


# ---- 1. khối luật
khoi = cc.khoi_tra_loi_gon(True)
check("tắt -> không thêm chữ nào", cc.khoi_tra_loi_gon(False) == "")
check("bật -> có khối TRẢ LỜI GỌN", "TRẢ LỜI GỌN" in khoi, khoi)
check("luật giữ nguyên số liệu và chữ phủ định", "con số" in khoi and "không" in khoi, khoi)
check("ngoại lệ: nội dung viết cho khách/quảng cáo vẫn viết đầy đủ", "quảng cáo" in khoi and "khách" in khoi, khoi)
check("không có em dash (TTS vấp)", "—" not in khoi)
check("khối ngắn (dưới 700 ký tự, không đánh thuế lượt chat)", len(khoi) < 700, len(khoi))

# ---- 2. công tắc: mặc định tắt, bật/tắt qua endpoint, /runtime/muc báo trạng thái
check("máy mới: mặc định TẮT", main._tra_loi_gon_bat() is False)
r = asyncio.run(main.runtime_tra_loi_gon_set(bat="1"))
check("bật qua endpoint", json.loads(r.body)["tra_loi_gon"] is True if hasattr(r, "body") else r["tra_loi_gon"] is True, r)
check("settings ghi lại", cfg.read_settings().get("tra_loi_gon") is True)
check("hàm đọc thấy bật", main._tra_loi_gon_bat() is True)

# ---- 3. hai đường dựng prompt
sp = main.build_system_prompt("brain")
check("đường đầy đủ (build_system_prompt) có luật khi bật", "TRẢ LỜI GỌN" in sp)
hd = cc.ContextCompiler._output_contract_text("dashboard")
check("đường tiết kiệm (hợp đồng đầu ra capsule) có luật khi bật", "TRẢ LỜI GỌN" in hd, hd)

asyncio.run(main.runtime_tra_loi_gon_set(bat="0"))
check("tắt lại -> settings false", cfg.read_settings().get("tra_loi_gon") is False)
check("tắt -> đường đầy đủ không còn luật", "TRẢ LỜI GỌN" not in main.build_system_prompt("brain"))
check("tắt -> đường tiết kiệm không còn luật",
      "TRẢ LỜI GỌN" not in cc.ContextCompiler._output_contract_text("dashboard"))

muc = asyncio.run(main.runtime_muc("brain"))
check("/runtime/muc báo trạng thái công tắc", muc.get("tra_loi_gon") is False, muc.get("tra_loi_gon"))

if _fails:
    print(f"\n{len(_fails)} FAIL")
    raise SystemExit(1)
print("\nOK - test_tra_loi_gon: tất cả pass")
