"""Plugin bundled: Biến động số dư - tra giao dịch ngân hàng (Casso Webhook V2) cho MỌI engine.

Trả lời những câu như "hôm nay vào bao nhiêu tiền", "chị Lan chuyển khoản chưa", "tuần này
nhận bao nhiêu khoản". Chỉ ĐỌC kho giao dịch (server/bien_dong.py); không gọi ngân hàng,
không gọi Casso. min_mode=readonly nên loop/agent chỉ-đọc vẫn dùng được.
"""
from __future__ import annotations

import json

import bien_dong


def _check():
    try:
        if bien_dong.cai_dat_cong_khai().get("da_co_khoa") or bien_dong.file_kho().exists():
            return None
    except Exception:
        pass
    return ("Biến động số dư chưa được cài: chưa có Key bảo mật Casso và chưa nhận giao dịch nào. "
            "Mở trang Biến động số dư trên dashboard để lấy địa chỉ webhook và dán vào Casso.")


def _gon(g: dict) -> dict:
    return {"luc": bien_dong.gio(g.get("luc")), "so_tien": g.get("so_tien"),
            "noi_dung": g.get("mo_ta") or "", "nguoi_chuyen": g.get("nguoi_chuyen") or "",
            "ngan_hang_chuyen": g.get("ngan_hang_chuyen") or "",
            "tai_khoan": (g.get("nhan_tk") or g.get("ngan_hang") or "") + (" " + g["tk4"] if g.get("tk4") else ""),
            "so_du": g.get("so_du"), "thu_nghiem": bool(g.get("thu_nghiem"))}


def _doc(args, ctx):
    args = args or {}
    tu, den = args.get("tu_ngay"), args.get("den_ngay")
    if not tu and not den:
        tu = bien_dong.dau_hom_nay()   # mặc định: hôm nay
    try:
        limit = int(args.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    try:
        # Tổng tính trên TOÀN BỘ khoảng lọc, không chỉ `limit` dòng trả về.
        tat_ca = bien_dong.danh_sach(limit=bien_dong.TRA_TOI_DA, chi_vao=bool(args.get("chi_tien_vao")),
                                     tu_ngay=tu, den_ngay=den, tim=args.get("tim") or "",
                                     co_thu_nghiem=False)
    except ValueError as e:
        return f"ERROR: {e}"
    kq = {"tong": bien_dong.tong(tat_ca), "giao_dich": [_gon(g) for g in tat_ca[:max(1, min(limit, 200))]],
          "don_vi": "VND", "ghi_chu": "so_tien > 0 là tiền vào, < 0 là tiền ra; mới nhất trước"}
    return json.dumps(kq, ensure_ascii=False)


def register(ctx):
    ctx.register_tool(
        name="bien_dong_doc",
        description=("Giao dịch ngân hàng Casso đẩy về (biến động số dư): tổng tiền vào/ra, số giao "
                     "dịch, danh sách mới nhất trước (giờ, số tiền, nội dung, người chuyển, số dư). "
                     "Lọc: tu_ngay/den_ngay (YYYY-MM-DD, mặc định hôm nay), chi_tien_vao, tim (nội "
                     "dung hoặc tên người chuyển), limit. Trả JSON."),
        handler=_doc, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "tu_ngay": {"type": "string", "description": "Từ ngày YYYY-MM-DD (hoặc ISO). Bỏ trống = hôm nay"},
            "den_ngay": {"type": "string", "description": "Đến ngày YYYY-MM-DD (tính hết ngày đó)"},
            "chi_tien_vao": {"type": "boolean", "description": "Chỉ giao dịch tiền vào"},
            "tim": {"type": "string", "description": "Tìm trong nội dung chuyển khoản / tên người chuyển"},
            "limit": {"type": "integer", "description": "Tối đa bao nhiêu giao dịch liệt kê (mặc định 50)"},
        }},
    )
