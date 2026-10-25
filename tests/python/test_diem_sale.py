"""Điểm hiệu suất sale (server/diem_sale.py). Không mạng.

    python tests/run.py diem_sale

Phủ: người tốt nhất mỗi chỉ số được đủ điểm, tổng 100 khi một người dẫn mọi mặt, tốc độ chậm
gấp đôi được một nửa, không trả lời ai thì 0 điểm tốc độ, tỷ lệ chốt tính lại từ đơn/khách,
vai nổi bật, trọng số đổi được, lọc chi_tinh/bo_qua theo tên bỏ dấu, cấu hình hỏng về mặc định,
số rác không làm hỏng, tổng cả đội.
"""
from _paths import ROOT, SERVER  # noqa: F401
import json
import tempfile
from pathlib import Path

from _gia_http import KiemTra
import diem_sale as d

check = KiemTra()

# ---- một người dẫn mọi mặt: đủ 100 ----
r = d.cham([{"ten": "A", "khach_da_tra_loi": 10, "tin_inbox": 20, "so_dien_thoai": 5, "don_chot": 5, "phan_hoi_tb_giay": 10},
            {"ten": "B", "khach_da_tra_loi": 5, "tin_inbox": 10, "so_dien_thoai": 2, "don_chot": 1, "phan_hoi_tb_giay": 20}])
a, b = r[0], r[1]
check("người dẫn mọi mặt = 100 điểm", a["ten"] == "A" and a["diem"] == 100.0, a)
check("tốc độ chậm gấp đôi = 7,5", b["toc_do"] == 7.5, b)
check("B: SĐT 2/5*20 + khách 5/10*15 + tin 10/20*5 = 18", b["mo_khach"] == 18.0, b)
check("B: đơn 1/5*35 + tỷ lệ 20%/50%*10 = 11", b["chot"] == 11.0, b)
check("hạng theo điểm", a["hang"] == 1 and b["hang"] == 2)

# ---- ví dụ thật 25/10 (số MinMin đã chấm, đã bỏ TEN) ----
ds = [{"ten": "Hồng Cẩm", "khach_da_tra_loi": 33, "tin_inbox": 88, "so_dien_thoai": 3, "don_chot": 16, "phan_hoi_tb_giay": 54},
      {"ten": "Bích Hoàng", "khach_da_tra_loi": 77, "tin_inbox": 167, "so_dien_thoai": 8, "don_chot": 14, "phan_hoi_tb_giay": 61},
      {"ten": "Phương Nguyên", "khach_da_tra_loi": 60, "tin_inbox": 131, "so_dien_thoai": 2, "don_chot": 11, "phan_hoi_tb_giay": 44},
      {"ten": "Khánh Vy", "khach_da_tra_loi": 195, "tin_inbox": 367, "so_dien_thoai": 22, "don_chot": 4, "phan_hoi_tb_giay": 18},
      {"ten": "Bích Vân", "khach_da_tra_loi": 103, "tin_inbox": 204, "so_dien_thoai": 10, "don_chot": 3, "phan_hoi_tb_giay": 49}]
r = {x["ten"]: x for x in d.cham(ds)}
check("Khánh Vy: đủ điểm mở khách 40 và tốc độ 15", r["Khánh Vy"]["mo_khach"] == 40.0 and r["Khánh Vy"]["toc_do"] == 15.0, r["Khánh Vy"])
check("Hồng Cẩm: đủ điểm chốt 45", r["Hồng Cẩm"]["chot"] == 45.0, r["Hồng Cẩm"])
check("vai: Khánh Vy mở khách, Hồng Cẩm chốt", r["Khánh Vy"]["vai"] == "Mở khách" and r["Hồng Cẩm"]["vai"] == "Chốt",
      (r["Khánh Vy"]["vai"], r["Hồng Cẩm"]["vai"]))
check("tỷ lệ chốt tính lại 16/33", r["Hồng Cẩm"]["ty_le_chot"] == 48.5, r["Hồng Cẩm"]["ty_le_chot"])
check("tổng từng người = mở + chốt + tốc độ", all(abs(x["diem"] - (x["mo_khach"] + x["chot"] + x["toc_do"])) < 0.11 for x in r.values()))
check("điểm trong 0..100", all(0 <= x["diem"] <= 100 for x in r.values()))

# ---- không trả lời ai: 0 điểm tốc độ, không chia cho 0 ----
r = d.cham([{"ten": "X", "khach_da_tra_loi": 0, "don_chot": 2, "phan_hoi_tb_giay": 0},
            {"ten": "Y", "khach_da_tra_loi": 4, "phan_hoi_tb_giay": 30}])
x = [z for z in r if z["ten"] == "X"][0]
check("không trả lời ai -> 0 điểm tốc độ, tỷ lệ 0", x["toc_do"] == 0 and x["ty_le_chot"] == 0, x)
check("đội rỗng -> rỗng", d.cham([]) == [])
check("số rác không làm hỏng", d.cham([{"ten": "Z", "so_dien_thoai": "abc", "don_chot": None, "phan_hoi_tb_giay": "nan"}])[0]["diem"] == 0)

# ---- trọng số đổi được ----
r = d.cham([{"ten": "A", "so_dien_thoai": 10, "khach_da_tra_loi": 1}, {"ten": "B", "don_chot": 1, "khach_da_tra_loi": 1}],
           {"so_dien_thoai": 25, "don_chot": 30})
check("đổi trọng số SĐT 25", [z for z in r if z["ten"] == "A"][0]["mo_khach"] >= 25, r)

# ---- cấu hình + lọc ----
with tempfile.TemporaryDirectory() as tmp:
    ch = d.doc_cau_hinh(tmp)
    check("không có file -> trọng số mặc định", ch["trong_so"] == d.TRONG_SO and not ch["chi_tinh"] and not ch["bo_qua"])
    f = Path(tmp) / d.CAU_HINH
    f.parent.mkdir(parents=True)
    f.write_text("{hỏng", encoding="utf-8")
    check("file hỏng -> mặc định", d.doc_cau_hinh(tmp)["trong_so"] == d.TRONG_SO)
    f.write_text(json.dumps({"bo_qua": ["TEN"], "trong_so": {"so_dien_thoai": 25, "la": 9, "don_chot": -3}}), encoding="utf-8")
    ch = d.doc_cau_hinh(tmp)
    check("đọc bo_qua", ch["bo_qua"] == {"ten"}, ch["bo_qua"])
    check("trọng số: nhận khoá đúng, bỏ khoá lạ và số âm", ch["trong_so"]["so_dien_thoai"] == 25 and "la" not in ch["trong_so"]
          and ch["trong_so"]["don_chot"] == 35, ch["trong_so"])
    ds2 = [{"ten": "TEN"}, {"ten": "Khanh  Vy"}, {"ten": "Vũ Hằng Huyền"}]
    check("bo_qua loại TEN", [z["ten"] for z in d.loc(ds2, ch)] == ["Khanh  Vy", "Vũ Hằng Huyền"])
    f.write_text(json.dumps({"chi_tinh": ["Khánh Vy"]}), encoding="utf-8")
    check("chi_tinh khớp tên bỏ dấu", [z["ten"] for z in d.loc(ds2, d.doc_cau_hinh(tmp))] == ["Khanh  Vy"])

# ---- tổng cả đội ----
t = d.tong_doi(d.cham(ds))
check("tổng đơn 48, khách 468", t["don_chot"] == 48 and t["khach_da_tra_loi"] == 468, t)
check("tỷ lệ cả đội = 48/468", t["ty_le_chot"] == 10.3, t)
check("phản hồi TB có trọng số theo khách", t["phan_hoi_tb_giay"] and 30 < t["phan_hoi_tb_giay"] < 50, t)

check.ket_thuc()
