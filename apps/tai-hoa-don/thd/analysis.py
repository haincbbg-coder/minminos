# -*- coding: utf-8 -*-
"""
analysis.py - Lọc hóa đơn, cảnh báo (thiếu số, lệch thuế, trùng, hủy/thay thế),
bảng kê theo thuế suất, dữ liệu mẫu nhập MISA.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .gdt_client import TTHAI


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _rate(s) -> Optional[float]:
    s = str(s or "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ lọc
def match_filter(inv: dict, loai: str, f: dict) -> bool:
    """f: {text, min, max, rate, status, only_xml, only_warn}"""
    text = (f.get("text") or "").strip().lower()
    if text:
        partner = (inv.get("nbten") if loai == "purchase" else (inv.get("nmten") or inv.get("nmtnmua"))) or ""
        hay = " ".join(str(x or "") for x in (partner, inv.get("nbmst"), inv.get("nmmst"), inv.get("shdon"),
                                                inv.get("khhdon"), inv.get("mccqt"))).lower()
        if text not in hay:
            d = inv.get("_detail") or {}
            if not any(text in str(l.get("ten", "")).lower() for l in d.get("lines", [])):
                return False
    tong = _f(inv.get("tgtttbso"))
    if f.get("min") is not None and tong < f["min"]:
        return False
    if f.get("max") is not None and tong > f["max"]:
        return False
    rate = f.get("rate")
    if rate not in (None, "", "Tất cả"):
        d = inv.get("_detail") or {}
        rates = {str(l.get("tsuat", "")).replace("%", "").strip() for l in d.get("lines", [])}
        if not rates:  # chưa có XML -> ước theo tổng
            r = round(_f(inv.get("tgtthue")) * 100 / _f(inv.get("tgtcthue"))) if _f(inv.get("tgtcthue")) else 0
            rates = {str(r)}
        if str(rate).replace("%", "").strip() not in rates:
            return False
    st = f.get("status")
    if st == "Hợp lệ" and inv.get("tthai") in (4, 5, 6):
        return False
    if st == "Bị hủy/thay thế/điều chỉnh" and inv.get("tthai") not in (4, 5, 6):
        return False
    if f.get("only_xml") and not inv.get("_xml_path"):
        return False
    if f.get("only_warn") and not inv.get("_warns"):
        return False
    return True


def is_ban_hang(inv: dict) -> bool:
    """Hóa đơn BÁN HÀNG (Hộ kinh doanh / không thuế GTGT): KHMSHDon = '2'.
    Loại này KHÔNG tách thuế - cổng thuế trả tiền hàng/thuế = 0, tổng = tiền hàng."""
    return str(inv.get("khmshdon") or "").strip() == "2"


def normalize_hkd(inv: dict):
    """Hóa đơn bán hàng không thuế: nếu cổng thuế để trống tiền hàng thì lấy = tổng, thuế = 0.
    Nhờ vậy cột 'Tiền hàng', bảng kê và cảnh báo không bị lệch."""
    if not is_ban_hang(inv):
        return
    tong = _f(inv.get("tgtttbso"))
    if tong and not _f(inv.get("tgtcthue")):
        inv["tgtcthue"] = tong
        if inv.get("tgtthue") in (None, "", 0):
            inv["tgtthue"] = 0


# ---------------------------------------------------------------- cảnh báo
def check_invoices(purchase: list[dict], sold: list[dict], mst_cty: str = "") -> list[dict]:
    """
    Trả về danh sách cảnh báo [{muc, loai, ma, so, khhdon, ngay, doi_tac, noi_dung}] và gắn
    inv["_warns"] = [chuỗi] cho từng hóa đơn.
    """
    warns: list[dict] = []
    for lst in (purchase, sold):
        for inv in lst:
            inv["_warns"] = []
            normalize_hkd(inv)

    def add(muc, loai, inv, msg):
        inv["_warns"].append(msg)
        partner = inv.get("nbten") if loai == "purchase" else (inv.get("nmten") or inv.get("nmtnmua") or "")
        warns.append({"muc": muc, "loai": "Mua vào" if loai == "purchase" else "Bán ra",
                      "so": inv.get("shdon"), "khhdon": f"{inv.get('khmshdon') or ''}{inv.get('khhdon') or ''}",
                      "ngay": str(inv.get("tdlap") or "")[:10], "doi_tac": partner, "noi_dung": msg, "_inv": inv})

    for loai, lst in (("purchase", purchase), ("sold", sold)):
        # 1) trạng thái bất thường
        for inv in lst:
            t = inv.get("tthai")
            if t in (4, 5, 6):
                add("Cao", loai, inv, f"{TTHAI.get(t)} - không đưa vào bảng kê")
            elif t in (2, 3):
                add("Thấp", loai, inv, f"{TTHAI.get(t)} - kiểm tra hóa đơn gốc bị thay thế/điều chỉnh")
            if inv.get("ttxly") in (2, 4):
                add("Cao", loai, inv, "CQT từ chối / không đủ điều kiện cấp mã")
        # 2) lệch số học tổng: tiền hàng + thuế - CK ≠ tổng thanh toán
        #    (BỎ QUA hóa đơn bán hàng của Hộ kinh doanh - không tách thuế nên không so được)
        for inv in lst:
            if is_ban_hang(inv):
                continue
            ch, th, tt = _f(inv.get("tgtcthue")), _f(inv.get("tgtthue")), _f(inv.get("tgtttbso"))
            ck = _f(inv.get("ttcktmai"))
            if not ch and not th:      # cổng thuế không tách tiền hàng/thuế -> không đủ dữ liệu để so
                continue
            if tt and abs(ch + th - ck - tt) > 1.0:
                add("Vừa", loai, inv, f"Tiền hàng {ch:,.0f} + thuế {th:,.0f} − CK {ck:,.0f} ≠ tổng {tt:,.0f}")
        # 3) lệch thuế theo dòng hàng (từ XML)
        for inv in lst:
            d = inv.get("_detail")
            if not d or not d.get("lines"):
                continue
            exp_tax = 0.0; ok = True
            for l in d["lines"]:
                if str(l.get("tchat", "1")) not in ("1", "2", "3"):
                    continue
                r = _rate(l.get("tsuat"))
                if r is None:
                    ok = False; break
                sign = -1 if str(l.get("tchat")) == "3" else 1
                exp_tax += sign * _f(l.get("thtien")) * r / 100
            th = _f(inv.get("tgtthue"))
            if ok and abs(exp_tax - th) > max(2.0, th * 0.005):
                add("Vừa", loai, inv, f"Thuế theo dòng hàng ≈ {exp_tax:,.0f} nhưng tổng thuế ghi {th:,.0f}")
            if abs(_f(d.get("tong_tien")) - _f(inv.get("tgtttbso"))) > 1.0 and _f(d.get("tong_tien")):
                add("Vừa", loai, inv, f"Tổng trong XML {_f(d.get('tong_tien')):,.0f} ≠ tổng trên cổng {_f(inv.get('tgtttbso')):,.0f}")
        # 4) trùng số hóa đơn cùng người bán + ký hiệu
        seen: dict = defaultdict(list)
        for inv in lst:
            seen[(inv.get("nbmst"), inv.get("khmshdon"), inv.get("khhdon"), str(inv.get("shdon")))].append(inv)
        for k, group in seen.items():
            if len(group) > 1:
                for inv in group:
                    add("Vừa", loai, inv, f"Trùng số hóa đơn {k[3]} ({len(group)} bản ghi)")
    # 5) thiếu số hóa đơn BÁN RA (số do chính công ty phát hành phải liên tục theo ký hiệu)
    by_serial: dict = defaultdict(list)
    for inv in sold:
        try:
            by_serial[(inv.get("khmshdon"), inv.get("khhdon"))].append(int(inv.get("shdon")))
        except (TypeError, ValueError):
            pass
    for (khms, khhd), nums in by_serial.items():
        nums = sorted(set(nums))
        if len(nums) < 2:
            continue
        missing = []
        for a, b in zip(nums, nums[1:]):
            if b - a > 1:
                missing.append(f"{a + 1}" if b - a == 2 else f"{a + 1}–{b - 1}")
        if missing:
            shown = ", ".join(missing[:15]) + (" ..." if len(missing) > 15 else "")
            warns.append({"muc": "Cao", "loai": "Bán ra", "so": "", "khhdon": f"{khms or ''}{khhd or ''}",
                          "ngay": "", "doi_tac": "", "_inv": None,
                          "noi_dung": f"THIẾU số hóa đơn trong kỳ tra cứu: {shown} "
                                      f"(có thể thuộc kỳ khác, bị hủy khi chưa gửi CQT, hoặc chưa tra đủ)"})
    order = {"Cao": 0, "Vừa": 1, "Thấp": 2}
    warns.sort(key=lambda w: (order.get(w["muc"], 9), w["loai"], w["ngay"]))
    return warns


# --------------------------------------------------------- theo thuế suất
def by_vat_rate(invoices: list[dict]) -> list[dict]:
    """Gộp theo thuế suất từ dòng hàng XML; HĐ chưa có XML -> ước từ tổng. -> [{tsuat, so_hd, tien_hang, tien_thue}]"""
    agg: dict = defaultdict(lambda: {"so_hd": set(), "tien_hang": 0.0, "tien_thue": 0.0})
    for inv in invoices:
        if inv.get("tthai") in (4, 5, 6):
            continue
        key_inv = (inv.get("nbmst"), inv.get("khhdon"), inv.get("shdon"))
        d = inv.get("_detail")
        if d and d.get("lines"):
            for l in d["lines"]:
                if str(l.get("tchat", "1")) not in ("1", "3"):
                    continue
                r = str(l.get("tsuat") or "").strip() or "?"
                sign = -1 if str(l.get("tchat")) == "3" else 1
                a = agg[r]; a["so_hd"].add(key_inv)
                a["tien_hang"] += sign * _f(l.get("thtien")); a["tien_thue"] += sign * _f(l.get("tthue"))
        else:
            ch, th = _f(inv.get("tgtcthue")), _f(inv.get("tgtthue"))
            r = f"{round(th * 100 / ch)}% (ước)" if ch else "0% (ước)"
            a = agg[r]; a["so_hd"].add(key_inv); a["tien_hang"] += ch; a["tien_thue"] += th
    out = [{"tsuat": k, "so_hd": len(v["so_hd"]), "tien_hang": v["tien_hang"], "tien_thue": v["tien_thue"]}
           for k, v in agg.items()]
    out.sort(key=lambda x: x["tsuat"])
    return out


# =============================================== Bảng kê & Tờ khai thuế GTGT
def rate_bucket(tsuat) -> str:
    """Chuẩn hóa thuế suất về nhóm: '0%','5%','8%','10%','KCT' (không chịu thuế),
    'KKKNT' (không kê khai), hoặc 'Khác'."""
    s = str(tsuat or "").strip().upper().replace(" ", "")
    if not s or s in ("-", "\\", "/", "N/A"):
        return "KCT"
    if "KCT" in s or "KHÔNGCHỊU" in s or "KHONGCHIU" in s:
        return "KCT"
    if "KKK" in s or "KHÔNGKÊKHAI" in s or "KHONGKEKHAI" in s:
        return "KKKNT"
    import re as _re
    m = _re.search(r"(\d+(?:[.,]\d+)?)", s)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            return f"{int(v)}%" if v == int(v) else f"{v}%"
        except ValueError:
            pass
    return "Khác"


# thứ tự hiển thị các nhóm thuế suất
RATE_ORDER = ["0%", "5%", "8%", "10%", "KCT", "KKKNT", "Khác"]


def _rate_sort_key(b: str) -> tuple:
    return (RATE_ORDER.index(b) if b in RATE_ORDER else 99, b)


def _inv_rate_amounts(inv: dict):
    """Trả [(bucket, tien_hang_chua_thue, tien_thue)] cho 1 hóa đơn.
    Có XML -> tách theo từng dòng; chưa có -> 1 dòng tổng, suy thuế suất từ tổng."""
    d = inv.get("_detail")
    out = []
    if d and d.get("lines"):
        for l in d["lines"]:
            if str(l.get("tchat", "1")) not in ("1", "3"):
                continue
            sign = -1 if str(l.get("tchat")) == "3" else 1
            out.append((rate_bucket(l.get("tsuat")),
                        sign * _f(l.get("thtien")), sign * _f(l.get("tthue"))))
        if out:
            return out
    # không có dòng: dùng tổng, suy thuế suất
    ch, th = _f(inv.get("tgtcthue")), _f(inv.get("tgtthue"))
    if is_ban_hang(inv):        # hóa đơn bán hàng HKD: không tách thuế
        return [("KCT", _f(inv.get("tgtttbso")) or ch, 0.0)]
    if ch:
        rate = round(th * 100 / ch) if th else 0
        return [(f"{rate}%", ch, th)]
    return [("KCT", _f(inv.get("tgtttbso")), 0.0)]


def vat_declaration(purchase: list[dict], sold: list[dict]) -> dict:
    """Tổng hợp phục vụ TỜ KHAI 01/GTGT + đối chiếu đầu ra/đầu vào.
    -> {ban_ra:{bucket:{so_hd,doanh_so,thue}}, mua_vao:{...}, và các tổng, số phải nộp/khấu trừ}."""
    def agg(invs):
        g = defaultdict(lambda: {"so_hd": set(), "doanh_so": 0.0, "thue": 0.0})
        for inv in invs:
            if inv.get("tthai") in (4, 5, 6):     # hủy/thay thế/điều chỉnh bị loại -> bỏ
                continue
            key = (inv.get("nbmst"), inv.get("nmmst"), inv.get("khhdon"), inv.get("shdon"))
            for bucket, tien, thue in _inv_rate_amounts(inv):
                a = g[bucket]; a["so_hd"].add(key)
                a["doanh_so"] += tien; a["thue"] += thue
        return {b: {"so_hd": len(v["so_hd"]), "doanh_so": v["doanh_so"], "thue": v["thue"]}
                for b, v in g.items()}

    ban = agg(sold); mua = agg(purchase)
    tong_ds_ban = sum(v["doanh_so"] for v in ban.values())
    thue_dau_ra = sum(v["thue"] for v in ban.values())
    tong_gt_mua = sum(v["doanh_so"] for v in mua.values())
    thue_dau_vao = sum(v["thue"] for v in mua.values())
    chenh = thue_dau_ra - thue_dau_vao
    return {
        "ban_ra": ban, "mua_vao": mua,
        "tong_ds_ban": tong_ds_ban, "thue_dau_ra": thue_dau_ra,
        "tong_gt_mua": tong_gt_mua, "thue_dau_vao": thue_dau_vao,
        "phai_nop": max(0.0, chenh),
        "con_khau_tru": max(0.0, -chenh),
    }


# cột bảng kê hóa đơn (mẫu 01-1/01-2 GTGT)
BANGKE_HEADERS = ["STT", "Ký hiệu mẫu số", "Ký hiệu HĐ", "Số hóa đơn", "Ngày lập",
                  "Tên người bán/mua", "Mã số thuế", "Doanh số/Giá trị chưa thuế",
                  "Thuế suất", "Thuế GTGT", "Tổng thanh toán", "Loại chi phí", "Ghi chú"]


def bang_ke_rows(invoices: list[dict], loai: str) -> list[list]:
    """Bảng kê 1 dòng / 1 hóa đơn (mẫu PL 01-1 bán ra / 01-2 mua vào)."""
    rows = []
    stt = 0
    # xếp theo ngày rồi số HĐ
    def sk(inv):
        return (str(inv.get("tdlap") or ""), str(inv.get("khhdon") or ""), str(inv.get("shdon") or ""))
    for inv in sorted(invoices, key=sk):
        tt = inv.get("tthai")
        huy = tt in (4, 5, 6)
        stt += 1
        mst = inv.get("nbmst") if loai == "purchase" else inv.get("nmmst")
        ten = inv.get("nbten") if loai == "purchase" else (inv.get("nmten") or inv.get("nmtnmua") or "")
        # thuế suất hiển thị: gộp các bucket của hóa đơn
        buckets = {}
        for b, tien, thue in _inv_rate_amounts(inv):
            x = buckets.setdefault(b, [0.0, 0.0]); x[0] += tien; x[1] += thue
        rate_txt = ", ".join(sorted(buckets, key=_rate_sort_key))
        ghi = []
        if huy:
            ghi.append(TTHAI.get(tt, "hủy/thay thế"))
        if is_ban_hang(inv):
            ghi.append("HĐ bán hàng (HKD, không thuế GTGT)")
        rows.append([stt, inv.get("khmshdon"), inv.get("khhdon"), inv.get("shdon"),
                     fmt_ddmmyyyy(inv.get("tdlap")), ten, mst,
                     _f(inv.get("tgtcthue")), rate_txt, _f(inv.get("tgtthue")),
                     _f(inv.get("tgtttbso")), inv.get("_cost_type") or "", "; ".join(ghi)])
    return rows


def fmt_ddmmyyyy(tdlap) -> str:
    s = str(tdlap or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[0:4]}" if len(s) == 10 else s


# ------------------------------------------------------------ mẫu MISA
MISA_HEADERS = ["Ngày hạch toán", "Ngày chứng từ", "Số chứng từ", "Diễn giải", "Mẫu số HĐ", "Ký hiệu HĐ",
                "Số hóa đơn", "Ngày hóa đơn", "Mã đối tượng (MST)", "Tên đối tượng", "Địa chỉ",
                "Tên hàng hóa/dịch vụ", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "% thuế GTGT",
                "Tiền thuế GTGT", "Tổng thanh toán", "Nhóm HHDV mua vào", "Trạng thái HĐ"]


def misa_rows(invoices: list[dict], loai: str) -> list[list]:
    """Mỗi dòng hàng 1 dòng (HĐ chưa có XML -> 1 dòng tổng). Dạng bảng kê chung để import/copy vào MISA."""
    rows = []
    for inv in invoices:
        if inv.get("tthai") in (4, 5, 6):
            continue
        ngay = str(inv.get("tdlap") or "")[:10]
        ngay = f"{ngay[8:10]}/{ngay[5:7]}/{ngay[0:4]}" if len(ngay) == 10 else ngay
        partner_mst = inv.get("nbmst") if loai == "purchase" else inv.get("nmmst")
        partner_ten = inv.get("nbten") if loai == "purchase" else (inv.get("nmten") or inv.get("nmtnmua") or "")
        dchi = inv.get("nbdchi") if loai == "purchase" else inv.get("nmdchi")
        dien_giai = f"{'Mua' if loai == 'purchase' else 'Bán'} hàng theo HĐ {inv.get('khhdon')} số {inv.get('shdon')} - {partner_ten}"
        d = inv.get("_detail")
        lines = [l for l in (d or {}).get("lines", []) if str(l.get("tchat", "1")) in ("1", "3")]
        if lines:
            for l in lines:
                sign = -1 if str(l.get("tchat")) == "3" else 1
                rows.append([ngay, ngay, "", dien_giai, inv.get("khmshdon"), inv.get("khhdon"), inv.get("shdon"), ngay,
                             partner_mst, partner_ten, dchi or "", l.get("ten"), l.get("dvt"), l.get("sluong"), l.get("dgia"),
                             sign * _f(l.get("thtien")), str(l.get("tsuat") or ""), sign * _f(l.get("tthue")),
                             sign * (_f(l.get("thtien")) + _f(l.get("tthue"))), "1", TTHAI.get(inv.get("tthai"), "")])
        else:
            ch, th = _f(inv.get("tgtcthue")), _f(inv.get("tgtthue"))
            rows.append([ngay, ngay, "", dien_giai, inv.get("khmshdon"), inv.get("khhdon"), inv.get("shdon"), ngay,
                         partner_mst, partner_ten, dchi or "", "(chưa tải XML - tổng HĐ)", "", "", "", ch,
                         f"{round(th * 100 / ch)}%" if ch else "", th, _f(inv.get("tgtttbso")), "1",
                         TTHAI.get(inv.get("tthai"), "")])
    return rows
