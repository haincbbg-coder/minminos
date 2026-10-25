"""Điểm hiệu suất sale 100 điểm, chấm theo VAI (26.10.245).

Vì sao không xếp theo tỷ lệ chốt trần: trong một đội, người gõ nhanh thường nhận nhắn tin mở khách
(nhiều khách, ít đơn), người ăn nói khéo ngồi gọi chốt (ít khách, nhiều đơn). So tỷ lệ chốt thì
người mở khách luôn thua oan. Chủ shop duyệt cách chấm này ngày 26/10/2026 (skill
xep-hang-hieu-suat-sale-pancake trong brain):

  Mở khách 40 = số điện thoại lấy được 20 + khách đã trả lời 15 + tin nhắn gửi 5
  Chốt 45     = đơn chốt 35 + tỷ lệ chốt 10
  Tốc độ 15   = phản hồi trung bình (nhanh nhất đội 15 điểm, chậm gấp đôi 7,5 điểm)

Mỗi chỉ số so với người tốt nhất đội ở chỉ số đó: tốt nhất được đủ điểm, người khác theo tỷ lệ.
Trọng số đọc được từ file cấu hình của brain (`00 - Dashboard/hieu-suat-sale.json`), thiếu thì
dùng mặc định trên. File đó cũng giữ danh sách người được tính (`chi_tinh`) hoặc bị bỏ (`bo_qua`),
để tài khoản chung hay bot không lọt vào bảng xếp hạng.

Hàm ở đây THUẦN: không mạng, không đọc file. Nhận danh sách đã có số, trả danh sách đã chấm.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

CAU_HINH = "00 - Dashboard/hieu-suat-sale.json"
TRONG_SO = {"so_dien_thoai": 20, "khach_da_tra_loi": 15, "tin_inbox": 5,
            "don_chot": 35, "ty_le_chot": 10, "phan_hoi": 15}
NHOM = {"mo_khach": ("so_dien_thoai", "khach_da_tra_loi", "tin_inbox"),
        "chot": ("don_chot", "ty_le_chot"),
        "toc_do": ("phan_hoi",)}


def khoa_ten(ten) -> str:
    """'Khánh Vy', 'Khanh  vy' -> 'khanh vy'."""
    t = unicodedata.normalize("NFD", str(ten or "").replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def _so(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if x == x and x not in (float("inf"), float("-inf")) else 0.0


def doc_cau_hinh(root) -> dict:
    """{trong_so, chi_tinh: set khoá tên, bo_qua: set khoá tên}. File hỏng hay thiếu -> mặc định."""
    ts, chi, bo = dict(TRONG_SO), set(), set()
    try:
        raw = json.loads((Path(root) / CAU_HINH).read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    if isinstance(raw, dict):
        for kk, v in (raw.get("trong_so") or {}).items():
            if kk in ts and _so(v) >= 0:
                ts[kk] = _so(v)
        chi = {khoa_ten(x) for x in raw.get("chi_tinh") or [] if khoa_ten(x)}
        bo = {khoa_ten(x) for x in raw.get("bo_qua") or [] if khoa_ten(x)}
    return {"trong_so": ts, "chi_tinh": chi, "bo_qua": bo}


def loc(ds, cau_hinh) -> list:
    chi, bo = cau_hinh.get("chi_tinh") or set(), cau_hinh.get("bo_qua") or set()
    out = []
    for r in ds or []:
        kh = khoa_ten(r.get("ten"))
        if not kh or kh in bo or (chi and kh not in chi):
            continue
        out.append(r)
    return out


def _vai(mo, chot, ts):
    """Vai nổi bật theo phần trăm điểm đạt được của hai nhóm chính."""
    tmo = sum(ts[k] for k in NHOM["mo_khach"]) or 1
    tch = sum(ts[k] for k in NHOM["chot"]) or 1
    a, b = mo / tmo, chot / tch
    if a < 0.3 and b < 0.3:
        return "Xem lại"
    if a - b > 0.25:
        return "Mở khách"
    if b - a > 0.25:
        return "Chốt"
    return "Cân bằng"


def cham(ds, trong_so=None) -> list:
    """ds: [{ten, khach_da_tra_loi, tin_inbox, so_dien_thoai, don_chot, ty_le_chot, phan_hoi_tb_giay}]
    -> bản sao thêm {diem, mo_khach, chot, toc_do, vai, hang}, xếp điểm giảm dần."""
    ts = dict(TRONG_SO)
    ts.update({k: _so(v) for k, v in (trong_so or {}).items() if k in ts})
    rows = [dict(r) for r in ds or []]
    for r in rows:
        kh = _so(r.get("khach_da_tra_loi"))
        r["ty_le_chot"] = round(_so(r.get("don_chot")) * 100 / kh, 1) if kh else 0.0
    tot = {k: max([_so(r.get(k)) for r in rows] + [0]) for k in ("so_dien_thoai", "khach_da_tra_loi", "tin_inbox",
                                                                 "don_chot", "ty_le_chot")}
    ph = [_so(r.get("phan_hoi_tb_giay")) for r in rows if _so(r.get("phan_hoi_tb_giay")) > 0]
    nhanh_nhat = min(ph) if ph else 0
    for r in rows:
        p = {k: (ts[k] * _so(r.get(k)) / tot[k] if tot[k] else 0.0) for k in tot}
        t = _so(r.get("phan_hoi_tb_giay"))
        # Không trả lời ai thì không có tốc độ để chấm: 0 điểm, không phải điểm tối đa.
        p["phan_hoi"] = ts["phan_hoi"] * nhanh_nhat / t if (t > 0 and nhanh_nhat and _so(r.get("khach_da_tra_loi"))) else 0.0
        r["mo_khach"] = round(sum(p[k] for k in NHOM["mo_khach"]), 1)
        r["chot"] = round(sum(p[k] for k in NHOM["chot"]), 1)
        r["toc_do"] = round(p["phan_hoi"], 1)
        r["diem"] = round(r["mo_khach"] + r["chot"] + r["toc_do"], 1)
        r["vai"] = _vai(r["mo_khach"], r["chot"], ts)
    rows.sort(key=lambda r: (-r["diem"], -_so(r.get("don_chot")), khoa_ten(r.get("ten"))))
    for i, r in enumerate(rows):
        r["hang"] = i + 1
    return rows


def tong_doi(rows) -> dict:
    """Số cả phòng (đã lọc): cộng khách, tin, SĐT, đơn; tỷ lệ và phản hồi tính lại, không cộng."""
    t = {k: int(sum(_so(r.get(k)) for r in rows)) for k in ("khach_da_tra_loi", "tin_inbox", "so_dien_thoai", "don_chot")}
    t["ty_le_chot"] = round(t["don_chot"] * 100 / t["khach_da_tra_loi"], 1) if t["khach_da_tra_loi"] else 0.0
    w = [(_so(r.get("phan_hoi_tb_giay")), _so(r.get("khach_da_tra_loi"))) for r in rows
         if _so(r.get("phan_hoi_tb_giay")) > 0 and _so(r.get("khach_da_tra_loi")) > 0]
    t["phan_hoi_tb_giay"] = round(sum(a * b for a, b in w) / sum(b for _, b in w), 1) if w else None
    return t
