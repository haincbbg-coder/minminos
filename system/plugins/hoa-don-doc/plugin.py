"""hoa-don-doc - cho bộ não đọc kho hoá đơn TCT của app Tải hoá đơn (26.10.123).

Vì sao cần: app "Tải hoá đơn" lưu hoá đơn vào `STATE_DIR/tai-hoa-don/du-lieu/<MST>/`, NẰM NGOÀI
vault, nên bộ não không thấy và không có tool nào trả dữ liệu đó. Người dùng hỏi "tháng này mua
vào bao nhiêu hoá đơn, tổng thuế bao nhiêu" thì MinMin phải trả lời được từ chính dữ liệu đã tải.

Hai tool, đều CHỈ ĐỌC (readonly), dùng chung hàm đọc kho của app (`routes.hoa_don`):
  hoa_don_tong_hop   - số hoá đơn + tiền hàng + thuế + tổng, theo từng doanh nghiệp, mua/bán, lọc kỳ.
  hoa_don_danh_sach  - liệt kê hoá đơn (có trần), lọc theo đối tác, kỳ.

Không gọi mạng, không ghi gì: chỉ đọc file JSON app đã lưu.
"""
from __future__ import annotations

import json

LOAI_MAP = {"mua": "purchase", "mua_vao": "purchase", "ban": "sold", "ban_ra": "sold"}


def _hd():
    import routes.hoa_don as hd
    return hd


def _cac_mst(hd, mst_loc):
    dn = (hd.doc_cau_hinh() or {}).get("doanh_nghiep", {}) or {}
    if mst_loc:
        try:
            m = hd.chuan_mst(mst_loc)
        except ValueError as e:
            return None, str(e)
        if m not in dn:
            return None, f"Doanh nghiệp {m} chưa đăng nhập trong app Tải hoá đơn."
        return {m: dn[m]}, ""
    return dn, ""


def _trong_ky(ngay, tu, den):
    if not ngay:
        return not (tu or den)      # không có ngày thì chỉ tính khi không lọc kỳ
    if tu and ngay < tu:
        return False
    if den and ngay > den:
        return False
    return True


def _gom(hd, mst, loai_kho, tu, den):
    """(so_hd, tien_hang, thue, tong) của một MST + một loại kho, trong kỳ."""
    kho = hd.doc_kho(mst, loai_kho) or {}
    so = th = td = tg = 0
    for inv in kho.values():
        if not _trong_ky(hd.ngay_hd(inv), tu, den):
            continue
        so += 1
        th += float(inv.get("tgtcthue") or 0)
        td += float(inv.get("tgtthue") or 0)
        tg += float(inv.get("tgtttbso") or 0)
    return {"so_hd": so, "tien_hang": round(th), "thue": round(td), "tong": round(tg)}


def _chuan_ky(args):
    tu = str(args.get("tu") or "").strip() or None
    den = str(args.get("den") or "").strip() or None
    import re
    for v in (tu, den):
        if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            return None, None, "Kỳ 'tu'/'den' phải dạng YYYY-MM-DD."
    return tu, den, ""


def _tong_hop(args, ctx):
    args = args or {}
    hd = _hd()
    dn, err = _cac_mst(hd, args.get("mst"))
    if err:
        return "ERROR: " + err
    if not dn:
        return json.dumps({"doanh_nghiep": [], "ghi_chu": "Chưa có doanh nghiệp nào đăng nhập trong app Tải hoá đơn."}, ensure_ascii=False)
    tu, den, err = _chuan_ky(args)
    if err:
        return "ERROR: " + err
    loai = str(args.get("loai") or "ca_hai").lower()
    muon_mua = loai in ("mua", "mua_vao", "ca_hai")
    muon_ban = loai in ("ban", "ban_ra", "ca_hai")
    ra = []
    for mst, info in sorted(dn.items()):
        muc = {"mst": mst, "ten": (info or {}).get("ten", "")}
        if muon_mua:
            muc["mua_vao"] = _gom(hd, mst, "purchase", tu, den)
        if muon_ban:
            muc["ban_ra"] = _gom(hd, mst, "sold", tu, den)
        ra.append(muc)
    return json.dumps({"ky": {"tu": tu, "den": den} if (tu or den) else "tất cả",
                       "doanh_nghiep": ra}, ensure_ascii=False)


def _danh_sach(args, ctx):
    args = args or {}
    hd = _hd()
    dn, err = _cac_mst(hd, args.get("mst"))
    if err:
        return "ERROR: " + err
    tu, den, err = _chuan_ky(args)
    if err:
        return "ERROR: " + err
    try:
        gioi_han = max(1, min(200, int(args.get("gioi_han") or 50)))
    except (TypeError, ValueError):
        gioi_han = 50
    doi_tac = str(args.get("doi_tac") or "").strip().lower()
    loai = str(args.get("loai") or "ca_hai").lower()
    kho_loai = []
    if loai in ("mua", "mua_vao", "ca_hai"):
        kho_loai.append("purchase")
    if loai in ("ban", "ban_ra", "ca_hai"):
        kho_loai.append("sold")
    rows = []
    for mst in dn:
        for lk in kho_loai:
            for inv in (hd.doc_kho(mst, lk) or {}).values():
                ng = hd.ngay_hd(inv)
                if not _trong_ky(ng, tu, den):
                    continue
                t = hd.tom_tat(inv)
                if doi_tac and doi_tac not in str(t.get("doi_tac") or "").lower():
                    continue
                rows.append({"mst_cua_toi": mst, "loai": "mua_vao" if lk == "purchase" else "ban_ra",
                             "ngay": ng, "so": t.get("so"), "ky_hieu": t.get("ky_hieu"),
                             "doi_tac": t.get("doi_tac"), "mst_doi_tac": t.get("mst_doi_tac"),
                             "tien_hang": t.get("tien_hang"), "thue": t.get("thue"), "tong": t.get("tong"),
                             "co_xml": t.get("co_xml"), "co_goc": t.get("co_goc")})
    rows.sort(key=lambda r: r["ngay"] or "", reverse=True)
    return json.dumps({"tong_so_khop": len(rows), "tra_ve": min(len(rows), gioi_han),
                       "hoa_don": rows[:gioi_han]}, ensure_ascii=False)


def register(ctx):
    ctx.register_tool(
        name="hoa_don_tong_hop",
        description=("Tổng hợp hoá đơn ĐÃ TẢI từ Tổng cục Thuế trong app Tải hoá đơn: số hoá đơn, "
                     "tiền hàng, thuế, tổng - theo từng doanh nghiệp, tách mua vào / bán ra. "
                     "Tham số (tuỳ chọn): mst (lọc 1 doanh nghiệp), loai (mua|ban|ca_hai), "
                     "tu/den (YYYY-MM-DD lọc kỳ). Dùng khi hỏi 'tháng này bao nhiêu hoá đơn, tổng thuế'."),
        handler=_tong_hop, min_mode="readonly",
        schema={"type": "object", "properties": {
            "mst": {"type": "string", "description": "Mã số thuế doanh nghiệp (bỏ trống = tất cả đã đăng nhập)"},
            "loai": {"type": "string", "enum": ["mua", "ban", "ca_hai"], "description": "Mua vào, bán ra, hay cả hai (mặc định ca_hai)"},
            "tu": {"type": "string", "description": "Từ ngày YYYY-MM-DD"},
            "den": {"type": "string", "description": "Đến ngày YYYY-MM-DD"}}},
    )
    ctx.register_tool(
        name="hoa_don_danh_sach",
        description=("Liệt kê hoá đơn đã tải từ Tổng cục Thuế: ngày, số, ký hiệu, đối tác, tiền, thuế, "
                     "có XML/bản gốc chưa. Tham số (tuỳ chọn): mst, loai (mua|ban|ca_hai), tu/den "
                     "(YYYY-MM-DD), doi_tac (lọc theo tên đối tác), gioi_han (mặc định 50, tối đa 200)."),
        handler=_danh_sach, min_mode="readonly",
        schema={"type": "object", "properties": {
            "mst": {"type": "string", "description": "Mã số thuế doanh nghiệp (bỏ trống = tất cả)"},
            "loai": {"type": "string", "enum": ["mua", "ban", "ca_hai"]},
            "tu": {"type": "string", "description": "Từ ngày YYYY-MM-DD"},
            "den": {"type": "string", "description": "Đến ngày YYYY-MM-DD"},
            "doi_tac": {"type": "string", "description": "Lọc theo tên đối tác (chứa chuỗi)"},
            "gioi_han": {"type": "integer", "description": "Số hoá đơn tối đa trả về (mặc định 50, tối đa 200)"}}},
    )
