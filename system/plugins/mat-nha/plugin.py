"""Plugin bundled: MinMin Mắt Nhà - tra cứu sự kiện camera ở nhà cho MỌI engine.

Trả lời những câu như "hôm nay ai đến nhà", "xe biển 29-B1... về lúc nào", "có người lạ không".
Chỉ ĐỌC kho sự kiện mà cầu nối ở nhà đẩy lên (server/mat_nha.py); không mở camera, không gọi
ra ngoài. min_mode=readonly nên loop/agent chỉ-đọc vẫn dùng được.
"""
from __future__ import annotations

import mat_nha


def _check():
    try:
        if mat_nha.thong_tin_ma().get("da_co") or (mat_nha.thu_muc() / "su-kien").is_dir():
            return None
    except Exception:
        pass
    return ("Mắt Nhà chưa được cài: chưa có mã ghép nối và chưa nhận sự kiện nào. "
            "Mở trang /mat-nha trên dashboard để tạo mã và tải bộ cài cho máy tính ở nhà.")


def _tra(args, ctx):
    args = args or {}
    tu = args.get("tu")
    if not tu and str(args.get("hom_nay", "")).lower() in ("1", "true", "yes", "co"):
        tu = mat_nha.dau_hom_nay()
    if not tu and not args.get("den"):
        tu = mat_nha.dau_hom_nay()   # mặc định: hôm nay
    try:
        ds = mat_nha.tim(tu=tu, den=args.get("den"), camera=args.get("camera"),
                         loai=args.get("loai"), ten=args.get("ten"), bien_so=args.get("bien_so"),
                         chi_nguoi_la=bool(args.get("chi_nguoi_la")),
                         chi_canh_bao=bool(args.get("chi_canh_bao")),
                         limit=args.get("limit") or 200)
    except ValueError as e:
        return f"ERROR: {e}"
    tt = mat_nha.trang_thai()
    dau = ""
    if not tt.get("cau_noi_song"):
        dau = ("Lưu ý: cầu nối ở nhà chưa báo nhịp trong 10 phút gần đây (máy ở nhà tắt, mất mạng, "
               "hoặc chưa cài), nên dữ liệu có thể chưa đủ.\n")
    return dau + mat_nha.tom_tat(ds)


def register(ctx):
    ctx.register_tool(
        name="mat_nha_su_kien",
        description=("Sự kiện camera ở nhà: ai đến (tên người nhà đã học mặt, hoặc người lạ), xe và "
                     "biển số, con vật, giọng nói chép lại. Lọc: tu/den (YYYY-MM-DD hoặc ISO, mặc định "
                     "hôm nay), camera, loai (nguoi|xe|con_vat|vat|giong), ten, bien_so (khớp một phần), "
                     "chi_nguoi_la, chi_canh_bao (canh rào: tiến sát / lảng vảng / vào khu cấm / vượt rào). "
                     "Trả tóm tắt tiếng Việt, mới nhất trước."),
        handler=_tra, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "tu": {"type": "string", "description": "Từ lúc (YYYY-MM-DD hoặc ISO). Bỏ trống = đầu hôm nay"},
            "den": {"type": "string", "description": "Đến lúc (YYYY-MM-DD = hết ngày đó)"},
            "camera": {"type": "string", "description": "Tên camera, vd cong, san"},
            "loai": {"type": "string", "enum": ["nguoi", "xe", "con_vat", "vat", "giong"]},
            "ten": {"type": "string", "description": "Tên người nhà (khớp một phần)"},
            "bien_so": {"type": "string", "description": "Biển số, vd 29B1 hoặc 29-B1 123.45 (khớp một phần)"},
            "chi_nguoi_la": {"type": "boolean", "description": "Chỉ người không nhận ra mặt"},
            "chi_canh_bao": {"type": "boolean", "description": "Chỉ cảnh báo canh rào (vượt rào, vào khu cấm...)"},
            "limit": {"type": "integer", "description": "Tối đa bao nhiêu sự kiện (mặc định 200)"},
        }},
    )
