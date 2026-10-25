"""Plugin bundled: nạp dữ liệu cho bộ tra mã hàng (server/goi_y_ma.py) và tra thử.

Bộ não tự lấy dữ liệu từ POS (mã, tồn, ảnh), Meta (quảng cáo, chiến dịch) và Pancake (bài viết) bằng
MCP đã nối, rồi gọi `javis_goi_y_ma_nap` để đổ vào kho. Tiện ích trên trình duyệt của nhân viên chỉ
đọc kho này, không gọi POS hay Meta.
"""
from __future__ import annotations

import json
from pathlib import Path

import goi_y_anh
import goi_y_ma


def register(ctx):
    async def _nap(args, cctx):
        a = dict(args or {})
        tep = str(a.pop("tep", "") or "").strip()
        if tep:
            goc = Path(cctx.vault_root).resolve()
            p = (goc / tep).resolve()
            if goc not in p.parents or p.suffix.lower() != ".json" or not p.is_file():
                return "ERROR: 'tep' phải là file .json nằm trong bộ não (đường dẫn tương đối)"
            if p.stat().st_size > 8_000_000:
                return "ERROR: file quá lớn (trên 8 MB), chia nhỏ ra"
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError as e:
                return f"ERROR: file không phải JSON hợp lệ: {e}"
            if not isinstance(d, dict):
                return "ERROR: JSON phải là object có khoá sku, quang_cao, bai_viet hoặc bi_danh"
            for k in ("sku", "quang_cao", "bai_viet", "bi_danh"):
                if d.get(k) and not a.get(k):
                    a[k] = d[k]
        kq = goi_y_ma.nap_tu_dict(a)
        if not kq:
            return "ERROR: không có dữ liệu để nạp (cần sku, quang_cao, bai_viet, bi_danh hoặc tep)"
        return json.dumps({"da_nap": kq, "kho_hien_co": goi_y_ma.thong_ke()}, ensure_ascii=False)

    async def _tra(args, cctx):
        a = args or {}
        return json.dumps(goi_y_ma.phan_giai(a.get("text") or "", a.get("ad_id") or "", a.get("post_id") or ""),
                          ensure_ascii=False)

    async def _ma_ghep(args, cctx):
        return json.dumps({"ma": goi_y_ma.tao_ma_ghep(), "het_han_sau_phut": goi_y_ma.MA_SONG // 60,
                           "cach_dung": "Bấm biểu tượng tiện ích MinMin Gợi ý mã hàng trên Cốc Cốc, nhập mã này rồi Ghép máy."},
                          ensure_ascii=False)

    async def _hoc_anh(args, cctx):
        a = args or {}
        kq = await goi_y_anh.hoc_anh_mau(a.get("ma") if isinstance(a.get("ma"), list) else None)
        return json.dumps({**kq, **goi_y_anh.thong_ke()}, ensure_ascii=False)

    ctx.register_tool(
        name="javis_goi_y_ma_hoc_anh",
        description=("Tải ảnh mẫu của các mã đã nạp (từ POS), thu nhỏ và tính đặc trưng màu để tiện ích so ảnh khách gửi. "
                     "Chạy sau khi nạp mã, chạy lại an toàn (chỉ học mã chưa có). Tham số tuỳ chọn: ma (danh sách mã)."),
        handler=_hoc_anh, min_mode="safe",
        schema={"type": "object", "properties": {"ma": {"type": "array", "items": {"type": "string"}}}},
    )
    ctx.register_tool(
        name="javis_goi_y_ma_ma_ghep",
        description="Tạo mã ghép 6 số (sống 15 phút) để ghép tiện ích Gợi ý mã hàng trên trình duyệt của nhân viên với MinMin.",
        handler=_ma_ghep, min_mode="safe", schema={"type": "object", "properties": {}},
    )
    ctx.register_tool(
        name="javis_goi_y_ma_nap",
        description=("Nạp dữ liệu vào bộ tra mã hàng của tiện ích Pancake. Mọi tham số đều là danh sách, ghi đè theo "
                     "khoá: sku [{ma, ten, ton, anh:[url]}], quang_cao [{ad_id, ma? hoặc ten_chien_dich, tai_khoan}] "
                     "(thiếu ma thì tách từ tên chiến dịch dạng 'CÔNG TY ... - TÊN PAGE - P720'), bai_viet "
                     "[{post_id, ma, page_id}], bi_danh [{chuoi, ma}]. sku cũng nhận dạng gọn \"P664:508\" (mã:tồn). "
                     "Hoặc đưa tep: đường dẫn file .json trong bộ não chứa các khoá trên."),
        handler=_nap, min_mode="safe",
        schema={"type": "object", "properties": {
            "sku": {"type": "array", "items": {}},
            "quang_cao": {"type": "array", "items": {"type": "object"}},
            "bai_viet": {"type": "array", "items": {"type": "object"}},
            "bi_danh": {"type": "array", "items": {"type": "object"}},
            "tep": {"type": "string", "description": "File .json trong bộ não, vd attachments/goi-y-ma-sku.json"}}},
    )
    ctx.register_tool(
        name="javis_goi_y_ma_tra",
        description=("Tra thử mã hàng từ tin nhắn khách (text), ID quảng cáo (ad_id) hoặc ID bài viết (post_id). "
                     "Trả danh sách ứng viên kèm độ chắc, bằng chứng và tồn kho."),
        handler=_tra, min_mode="readonly",
        schema={"type": "object", "properties": {
            "text": {"type": "string"}, "ad_id": {"type": "string"}, "post_id": {"type": "string"}}},
    )
