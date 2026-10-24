"""Plugin bundled: nạp dữ liệu cho bộ tra mã hàng (server/goi_y_ma.py) và tra thử.

Bộ não tự lấy dữ liệu từ POS (mã, tồn, ảnh), Meta (quảng cáo, chiến dịch) và Pancake (bài viết) bằng
MCP đã nối, rồi gọi `javis_goi_y_ma_nap` để đổ vào kho. Tiện ích trên trình duyệt của nhân viên chỉ
đọc kho này, không gọi POS hay Meta.
"""
from __future__ import annotations

import json

import goi_y_ma


def register(ctx):
    async def _nap(args, cctx):
        a = args or {}
        kq = {}
        if a.get("sku"):
            kq["sku"] = goi_y_ma.nap_sku(a["sku"])
        if a.get("quang_cao"):
            kq["quang_cao"] = goi_y_ma.nap_quang_cao(a["quang_cao"])
        if a.get("bai_viet"):
            kq["bai_viet"] = goi_y_ma.nap_bai_viet(a["bai_viet"])
        if a.get("bi_danh"):
            kq["bi_danh"] = goi_y_ma.nap_bi_danh(a["bi_danh"])
        if not kq:
            return "ERROR: không có dữ liệu để nạp (cần ít nhất một trong sku, quang_cao, bai_viet, bi_danh)"
        return json.dumps({"da_nap": kq, "kho_hien_co": goi_y_ma.thong_ke()}, ensure_ascii=False)

    async def _tra(args, cctx):
        a = args or {}
        return json.dumps(goi_y_ma.phan_giai(a.get("text") or "", a.get("ad_id") or "", a.get("post_id") or ""),
                          ensure_ascii=False)

    async def _ma_ghep(args, cctx):
        return json.dumps({"ma": goi_y_ma.tao_ma_ghep(), "het_han_sau_phut": goi_y_ma.MA_SONG // 60,
                           "cach_dung": "Bấm biểu tượng tiện ích MinMin Gợi ý mã hàng trên Cốc Cốc, nhập mã này rồi Ghép máy."},
                          ensure_ascii=False)

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
                     "[{post_id, ma, page_id}], bi_danh [{chuoi, ma}]. Nạp theo lô vài trăm dòng mỗi lần."),
        handler=_nap, min_mode="safe",
        schema={"type": "object", "properties": {
            "sku": {"type": "array", "items": {"type": "object"}},
            "quang_cao": {"type": "array", "items": {"type": "object"}},
            "bai_viet": {"type": "array", "items": {"type": "object"}},
            "bi_danh": {"type": "array", "items": {"type": "object"}}}},
    )
    ctx.register_tool(
        name="javis_goi_y_ma_tra",
        description=("Tra thử mã hàng từ tin nhắn khách (text), ID quảng cáo (ad_id) hoặc ID bài viết (post_id). "
                     "Trả danh sách ứng viên kèm độ chắc, bằng chứng và tồn kho."),
        handler=_tra, min_mode="readonly",
        schema={"type": "object", "properties": {
            "text": {"type": "string"}, "ad_id": {"type": "string"}, "post_id": {"type": "string"}}},
    )
