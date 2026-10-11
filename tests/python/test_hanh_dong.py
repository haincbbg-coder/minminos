"""26.10.139 (Trụ 4): sổ hành động + quyền theo loại việc (hanh_dong.py). Thuần, không mạng.

    python tests/run.py hanh_dong
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

import hanh_dong as hd  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- phân loại ----------
for cid, tool, mong in [("zalo", "zalo_send_message", "nhan_tin"), ("pancake", "create_order", "don_hang"),
                        ("meta_ads", "update_adset_budget", "tien"), ("facebook_page", "create_post", "dang_bai"),
                        ("pancake", "delete_order", "xoa"), ("meta_ads", "update", "tien"),
                        ("pancake", "update", "don_hang"), ("gmail", "write", "nhan_tin"),
                        ("gì đó", "frobnicate", "khac"), ("facebook_page", "unpublish_post", "xoa")]:
    check(f"{cid}/{tool} -> {mong}", hd.loai_viec(cid, tool) == mong, hd.loai_viec(cid, tool))

# ---------- chính sách ----------
check("mặc định (rỗng) cho phép", hd.cho_phep({}, "tien")[0])
ok, why = hd.cho_phep({"tien": "chan"}, "tien")
check("chặn tiền -> không ok + lý do có chữ CHẶN", not ok and "CHẶN" in why, why)
check("chặn tiền không ảnh hưởng nhắn tin", hd.cho_phep({"tien": "chan"}, "nhan_tin")[0])
check("chuẩn hoá bỏ khoá/giá trị lạ", hd.chuan_hoa_chinh_sach({"tien": "CHAN", "xyz": "chan", "xoa": "bừa"}) == {"tien": "chan"})

# ---------- tóm tắt args che nhạy cảm ----------
tt = hd.tom_tat_args({"to": "0912", "access_token": "EAAB...", "text": "x" * 100})
check("che token", "access_token=***" in tt and "EAAB" not in tt, tt)
check("cắt giá trị dài", "..." in tt and len(tt) <= 160)

# ---------- sổ ----------
hd.dat_duong(os.path.join(tempfile.mkdtemp(), "so.jsonl"))
hd.dat_nguoi_lam("web:abc12345")
hd.ghi(hd.dong_so(ai=hd.nguoi_lam(), tool="zalo_send_message", connector="zalo", label="Zalo chủ",
                  loai="nhan_tin", cls="danger", mode="full", ok=True, ms=120, args={"to": "1", "text": "hi"}))
hd.ghi(hd.dong_so(ai="loop:ads", tool="update_adset_budget", connector="meta_ads", label="BM",
                  loai="tien", cls="danger", mode="full", ok=False, ms=0, args={"budget": 1}, err="bị CHẶN theo chính sách"))
ds = hd.doc(10)
check("đọc 2 dòng, mới nhất trước", len(ds) == 2 and ds[0]["loai"] == "tien", ds)
check("dòng có ai/hoan_tac/args", ds[1]["ai"] == "web:abc12345" and ds[1]["hoan_tac"] and "to=1" in ds[1]["args"])
check("lọc theo loại", [r["loai"] for r in hd.doc(10, loai="nhan_tin")] == ["nhan_tin"])
check("lọc chỉ lỗi", len(hd.doc(10, chi_loi=True)) == 1)
tk = hd.thong_ke()
check("thống kê: tổng 2, bị chặn 1", tk["tong"] == 2 and tk["bi_chan"] == 1, tk)
check("không dùng gạch dài", "—" not in open(os.path.join(ROOT, "server/hanh_dong.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
