# -*- coding: utf-8 -*-
"""
exporter.py - Xuất Excel (openpyxl) và in PDF (Edge/Chrome headless).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .gdt_client import TTHAI, TTXLY
from . import analysis

HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BBBBBB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MONEY = '#,##0'


def fmt_date(tdlap: str) -> str:
    s = str(tdlap or "")[:10]
    if len(s) == 10 and s[4] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def write_index(path: str, loai: str, rows: list) -> str:
    """Ghi file MỤC LỤC hóa đơn đã tải: mỗi dòng 1 hóa đơn, có LINK bấm mở thẳng file.
    rows: list dict từ Store.index_rows(). loai: 'purchase'|'sold'. -> đường dẫn file."""
    is_mua = loai == "purchase"
    wb = Workbook(); ws = wb.active; ws.title = "MucLuc"
    title = "MỤC LỤC HÓA ĐƠN MUA VÀO" if is_mua else "MỤC LỤC HÓA ĐƠN BÁN RA"
    ws.append([title]); ws.append([f"Tổng: {len(rows)} hóa đơn - bấm vào ô 'Mở file' để xem"])
    headers = ["STT", "Ngày", "Ký hiệu", "Số HĐ",
               ("Nhà cung cấp" if is_mua else "Khách hàng"),
               "MST", "Chưa thuế", "Tiền thuế", "Tổng tiền", "Trạng thái HĐ",
               "Trạng thái tải", "Lý do lỗi", "Loại PDF", "Mở file"]
    hrow = ws.max_row + 1
    ws.append(headers)
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(hrow, c)
        cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center"); cell.border = border
    base_dir = os.path.dirname(os.path.abspath(path))
    for i, r in enumerate(rows, 1):
        ten = (r.get("nbten") if is_mua else r.get("nmten")) or ""
        mst = (r.get("nbmst") if is_mua else r.get("nmmst")) or ""
        if r.get("goc_path"):
            fpath = r["goc_path"]; kind = "Bản gốc NCC"
        elif r.get("pdf_path"):
            fpath = r["pdf_path"]; kind = "Cổng thuế (TCT)"
        elif r.get("html_path"):
            fpath = r["html_path"]; kind = "PDF Trống đồng"
        elif r.get("xml_path"):
            fpath = r["xml_path"]; kind = "Chỉ có XML"
        else:
            fpath = ""; kind = ""
        # trạng thái tải: done/error từ DB, hoặc suy ra từ có file / chưa có file
        st = r.get("dl_status") or ""
        if st == "error":
            tai = "❌ Tải lỗi"
        elif fpath or st == "done":
            tai = "✔ Đã tải"
        else:
            tai = "⏳ Chưa tải"
        ws.append([i, fmt_date(r.get("tdlap") or r.get("ngay")),
                   f"{r.get('khmshdon') or ''}{r.get('khhdon') or ''}", r.get("shdon"),
                   ten, mst, r.get("tgtcthue"), r.get("tgtthue"), r.get("tgtttbso"),
                   TTXLY.get(r.get("ttxly"), ""), tai, r.get("dl_error") or "", kind, ""])
        rr = ws.max_row
        for c in range(1, len(headers) + 1):
            ws.cell(rr, c).border = border
        for c in (7, 8, 9):
            ws.cell(rr, c).number_format = '#,##0'
        link = ws.cell(rr, len(headers))
        if fpath:
            try:
                rel = os.path.relpath(fpath, base_dir)
            except ValueError:
                rel = fpath
            link.value = "📄 " + os.path.basename(fpath)
            link.hyperlink = rel
            link.font = Font(color="0563C1", underline="single")
        else:
            link.value = "(chưa có file)"
    ws.freeze_panes = f"A{hrow + 1}"
    _autosize(ws, {1: 6, 2: 12, 3: 12, 4: 12, 5: 42, 6: 16, 7: 15, 8: 14, 9: 16, 10: 16,
                   11: 13, 12: 34, 13: 16, 14: 40})
    ws.auto_filter.ref = f"A{hrow}:{get_column_letter(len(headers))}{ws.max_row}"
    wb.save(path)
    return path


def _autosize(ws, widths: dict[int, int] | None = None):
    for col in ws.columns:
        idx = col[0].column
        if widths and idx in widths:
            ws.column_dimensions[get_column_letter(idx)].width = widths[idx]
            continue
        m = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(idx)].width = min(max(m + 2, 8), 60)


def _write_sheet(ws, headers: list[str], rows: list[list], money_cols: set[int],
                 widths: dict[int, int] | None = None):
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font, c.border = HEAD_FILL, HEAD_FONT, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in row:
            c.border = BORDER
            if c.column in money_cols:
                c.number_format = MONEY
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autosize(ws, widths)


def _summary_rows(invoices: list[dict], loai: str) -> list[list]:
    rows = []
    for i, inv in enumerate(invoices, 1):
        partner_mst = inv.get("nbmst") if loai == "purchase" else inv.get("nmmst")
        partner_ten = inv.get("nbten") if loai == "purchase" else (inv.get("nmten") or inv.get("nmtnmua"))
        rows.append([
            i, fmt_date(inv.get("tdlap")), inv.get("shdon"), inv.get("khmshdon"), inv.get("khhdon"),
            partner_mst, partner_ten,
            inv.get("tgtcthue") or 0, inv.get("tgtthue") or 0, inv.get("tgtttbso") or 0,
            inv.get("dvtte") or "VND",
            TTHAI.get(inv.get("tthai"), str(inv.get("tthai") or "")),
            TTXLY.get(inv.get("ttxly"), str(inv.get("ttxly") or "")),
            "Máy tính tiền" if inv.get("_system") == "sco-query" else "HĐ điện tử",
            inv.get("mccqt") or "",
            "Có" if inv.get("_xml_path") else "",
        ])
    return rows


SUMMARY_HEADERS_P = ["STT", "Ngày HĐ", "Số HĐ", "Ký hiệu mẫu", "Ký hiệu HĐ", "MST người bán",
                     "Tên người bán", "Tiền hàng", "Thuế GTGT", "Tổng tiền", "Tiền tệ",
                     "Trạng thái", "Kết quả kiểm tra CQT", "Loại", "Mã CQT", "Đã tải XML"]
SUMMARY_HEADERS_S = [h.replace("người bán", "người mua") for h in SUMMARY_HEADERS_P]


def export_excel(path: str, purchase: list[dict], sold: list[dict],
                 details: dict[str, dict] | None = None) -> str:
    """
    details: {key: dict đã bóc từ XML (có 'lines')} - để xuất sheet chi tiết dòng hàng.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "MuaVao"
    _write_sheet(ws, SUMMARY_HEADERS_P, _summary_rows(purchase, "purchase"), {8, 9, 10},
                 {7: 45, 12: 22, 13: 30})
    ws2 = wb.create_sheet("BanRa")
    _write_sheet(ws2, SUMMARY_HEADERS_S, _summary_rows(sold, "sold"), {8, 9, 10},
                 {7: 45, 12: 22, 13: 30})

    # --- chi tiết dòng hàng
    ws3 = wb.create_sheet("ChiTiet")
    det_rows = []
    details = details or {}
    n = 0
    for loai, lst in (("Mua vào", purchase), ("Bán ra", sold)):
        for inv in lst:
            d = inv.get("_detail")
            if not d:
                continue
            for l in d.get("lines", []):
                n += 1
                det_rows.append([
                    n, loai, fmt_date(inv.get("tdlap")), inv.get("shdon"),
                    f"{inv.get('khmshdon') or ''}{inv.get('khhdon') or ''}",
                    inv.get("nbmst"), inv.get("nbten"), inv.get("nmmst"),
                    l.get("stt"), l.get("ten"), l.get("dvt"), l.get("sluong"), l.get("dgia"),
                    l.get("thtien"), l.get("tsuat"), l.get("tthue"),
                    {"1": "Hàng hóa/DV", "2": "Khuyến mại", "3": "Chiết khấu", "4": "Ghi chú"}.get(
                        str(l.get("tchat")), l.get("tchat")),
                ])
    _write_sheet(ws3, ["STT", "Loại", "Ngày HĐ", "Số HĐ", "Ký hiệu", "MST người bán",
                       "Tên người bán", "MST người mua", "STT dòng", "Tên hàng hóa, dịch vụ",
                       "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "Thuế suất", "Tiền thuế",
                       "Tính chất"], det_rows, {13, 14, 16}, {7: 40, 10: 50})

    # --- tổng hợp
    ws4 = wb.create_sheet("TongHop")
    def sums(lst):
        return (sum(float(i.get("tgtcthue") or 0) for i in lst),
                sum(float(i.get("tgtthue") or 0) for i in lst),
                sum(float(i.get("tgtttbso") or 0) for i in lst))
    p_ok = [i for i in purchase if i.get("tthai") not in (4, 5, 6)]
    s_ok = [i for i in sold if i.get("tthai") not in (4, 5, 6)]
    ps, ss = sums(p_ok), sums(s_ok)
    rows = [
        ["Mua vào (hợp lệ, trừ HĐ bị thay thế/điều chỉnh/hủy)", len(p_ok), *ps],
        ["Bán ra (hợp lệ)", len(s_ok), *ss],
        ["Tổng số hóa đơn mua vào tra được", len(purchase), *sums(purchase)],
        ["Tổng số hóa đơn bán ra tra được", len(sold), *sums(sold)],
        ["Chênh lệch VAT (đầu ra − đầu vào) - ƯỚC TÍNH", "", "", ss[1] - ps[1], ""],
    ]
    _write_sheet(ws4, ["Chỉ tiêu", "Số HĐ", "Tiền hàng", "Thuế GTGT", "Tổng tiền"], rows,
                 {3, 4, 5}, {1: 55})
    ws4.append([])
    ws4.append(["Lưu ý: số liệu chỉ để đối chiếu vận hành; tờ khai chính thức do kế toán xác nhận."])

    # --- theo thuế suất
    ws5 = wb.create_sheet("TheoThueSuat")
    rows5 = []
    for loai, lst in (("Mua vào", purchase), ("Bán ra", sold)):
        for r in analysis.by_vat_rate(lst):
            rows5.append([loai, r["tsuat"], r["so_hd"], r["tien_hang"], r["tien_thue"], r["tien_hang"] + r["tien_thue"]])
    _write_sheet(ws5, ["Loại", "Thuế suất", "Số HĐ", "Tiền hàng", "Tiền thuế", "Tổng"], rows5, {4, 5, 6}, {2: 16})
    ws5.append([]); ws5.append(["(ước) = hóa đơn chưa tải XML, thuế suất suy từ tổng tiền; tải XML để chính xác từng dòng."])

    # --- cảnh báo
    ws6 = wb.create_sheet("CanhBao")
    warns = analysis.check_invoices(purchase, sold)
    _write_sheet(ws6, ["Mức", "Loại", "Ký hiệu", "Số HĐ", "Ngày", "Đối tác", "Nội dung cảnh báo"],
                 [[w["muc"], w["loai"], w["khhdon"], w["so"], fmt_date(w["ngay"]), w["doi_tac"], w["noi_dung"]] for w in warns],
                 set(), {6: 40, 7: 90})

    # --- mẫu nhập MISA (bảng kê từng dòng hàng)
    for name, lst, loai in (("MISA_MuaVao", purchase, "purchase"), ("MISA_BanRa", sold, "sold")):
        ws7 = wb.create_sheet(name)
        _write_sheet(ws7, analysis.MISA_HEADERS, analysis.misa_rows(lst, loai), {14, 15, 16, 18, 19}, {4: 50, 10: 40, 12: 40})
    wb.save(path)
    return path


# --------------------------------------------------------------------- PDF
def find_browser() -> Optional[str]:
    """Tìm Edge / Chrome để in HTML -> PDF (headless)."""
    # Server installs live in MinMin's persistent tool directory, outside PATH.
    # Standalone desktop usage does not have the optional server module.
    try:
        import optional_tools
        managed = optional_tools.duong_dan_chrome()
        if managed and os.path.isfile(managed):
            return managed
    except (ImportError, OSError):
        pass
    cands = []
    if sys.platform.startswith("win"):
        pf = [os.environ.get("ProgramFiles", r"C:\Program Files"),
              os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
              os.environ.get("LOCALAPPDATA", "")]
        for base in pf:
            cands += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"),
                      os.path.join(base, r"Google\Chrome\Application\chrome.exe")]
    else:
        for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser", "chrome"):
            p = shutil.which(name)
            if p:
                cands.append(p)
        cands.append("/opt/pw-browsers/chromium")
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def html_to_pdf(html_path: str, pdf_path: str, browser: Optional[str] = None,
                timeout: int = 60) -> str:
    browser = browser or find_browser()
    if not browser:
        raise RuntimeError("Không tìm thấy Microsoft Edge hoặc Google Chrome để in PDF.")
    os.makedirs(os.path.dirname(pdf_path) or ".", exist_ok=True)
    src = Path(html_path).resolve().as_uri()
    profile = tempfile.mkdtemp(prefix="tct_pdf_")
    # In vào file mới để lần chạy lỗi không nhận nhầm PDF cũ là thành công.
    fd, pending = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(os.path.abspath(pdf_path)))
    os.close(fd)
    cmd = [browser, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
           "--no-sandbox", "--no-pdf-header-footer",
           f"--user-data-dir={profile}", f"--print-to-pdf={pending}", src]
    kw = {}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=timeout, **kw)
        except subprocess.TimeoutExpired:
            # Một số bản Chrome đã in xong nhưng chưa tự thoát.
            pass
        with open(pending, "rb") as f:
            valid = f.read(5) == b"%PDF-"
        if not valid:
            raise RuntimeError("Trình duyệt không tạo được PDF hợp lệ. Kiểm tra/cài lại Trình duyệt ở Công cụ.")
        os.replace(pending, pdf_path)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        if os.path.exists(pending):
            os.unlink(pending)
    return pdf_path


# ============================================================ In hàng loạt
def merge_pdfs(pdf_paths, out_path: str) -> int:
    """Gộp nhiều file PDF thành 1 file (out_path). Trả về SỐ file đã gộp.
    Ưu tiên pypdf; nếu máy chưa có pypdf -> raise RuntimeError để nơi gọi in từng file."""
    files = [p for p in pdf_paths if p and os.path.isfile(p)]
    if not files:
        raise RuntimeError("Không có file PDF nào để gộp.")
    try:
        from pypdf import PdfWriter, PdfReader          # pypdf >= 3
    except Exception:
        try:
            from PyPDF2 import PdfMerger                 # bản cũ
            m = PdfMerger()
            n = 0
            for p in files:
                try:
                    m.append(p); n += 1
                except Exception:
                    pass
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as f:
                m.write(f)
            m.close()
            if n == 0:
                raise RuntimeError("Không đọc được file PDF nào.")
            return n
        except ImportError:
            raise RuntimeError("Chưa cài thư viện gộp PDF (pypdf).")
    w = PdfWriter()
    n = 0
    for p in files:
        try:
            r = PdfReader(p)
            for pg in r.pages:
                w.add_page(pg)
            n += 1
        except Exception:
            pass          # bỏ qua file hỏng, gộp tiếp
    if n == 0:
        raise RuntimeError("Không đọc được file PDF nào.")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        w.write(f)
    return n


def print_file(path: str):
    """Gửi 1 file tới máy in mặc định (Windows dùng 'print'; nếu lỗi thì mở file để in tay)."""
    if sys.platform.startswith("win"):
        try:
            os.startfile(path, "print")  # type: ignore[attr-defined]
            return True
        except Exception:
            try:
                os.startfile(path)       # type: ignore[attr-defined]
                return True
            except Exception:
                return False
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path]); return True
    else:
        try:
            subprocess.Popen(["lp", path]); return True
        except Exception:
            subprocess.Popen(["xdg-open", path]); return True


# ============================================ Bảng kê & Tờ khai thuế GTGT
def export_tax_declaration(path: str, purchase, sold, mst_cty: str = "",
                           ky: str = "") -> str:
    """Xuất 1 file Excel gồm 3 sheet:
       - 'Doi chieu thue GTGT' : tổng hợp đầu ra/đầu vào -> thuế phải nộp / còn khấu trừ
       - 'BK Mua vao (01-2)'   : bảng kê hóa đơn mua vào
       - 'BK Ban ra (01-1)'    : bảng kê hóa đơn bán ra
    """
    from . import analysis
    wb = Workbook()

    # ---------- Sheet 1: Đối chiếu / tờ khai ----------
    ws = wb.active; ws.title = "Doi chieu thue GTGT"
    dec = analysis.vat_declaration(purchase, sold)
    title_font = Font(bold=True, size=14, color="1F4E78")
    sub_font = Font(bold=True, color="FFFFFF")
    sub_fill = PatternFill("solid", fgColor="1F4E78")

    ws["A1"] = "ĐỐI CHIẾU THUẾ GTGT - HỖ TRỢ LẬP TỜ KHAI 01/GTGT"; ws["A1"].font = title_font
    ws["A2"] = f"Mã số thuế: {mst_cty}"
    ws["A3"] = f"Kỳ: {ky}" if ky else "Kỳ: (theo dữ liệu đã tải)"
    r = 5

    def block(title, data_map, val_label):
        nonlocal r
        ws.cell(r, 1, title).font = Font(bold=True, size=12); r += 1
        heads = ["Thuế suất", "Số HĐ", val_label, "Thuế GTGT"]
        for j, h in enumerate(heads, 1):
            c = ws.cell(r, j, h); c.fill = sub_fill; c.font = sub_font
            c.alignment = Alignment(horizontal="center"); c.border = BORDER
        r += 1
        tds = tth = 0.0; nhd = 0
        for b in sorted(data_map, key=analysis._rate_sort_key):
            v = data_map[b]
            ws.cell(r, 1, b).border = BORDER
            ws.cell(r, 2, v["so_hd"]).border = BORDER
            c3 = ws.cell(r, 3, round(v["doanh_so"])); c3.number_format = MONEY; c3.border = BORDER
            c4 = ws.cell(r, 4, round(v["thue"])); c4.number_format = MONEY; c4.border = BORDER
            tds += v["doanh_so"]; tth += v["thue"]; nhd += v["so_hd"]; r += 1
        cc = ws.cell(r, 1, "CỘNG"); cc.font = Font(bold=True); cc.border = BORDER
        ws.cell(r, 2, nhd).font = Font(bold=True); ws.cell(r, 2).border = BORDER
        c3 = ws.cell(r, 3, round(tds)); c3.font = Font(bold=True); c3.number_format = MONEY; c3.border = BORDER
        c4 = ws.cell(r, 4, round(tth)); c4.font = Font(bold=True); c4.number_format = MONEY; c4.border = BORDER
        r += 2
        return tds, tth

    block("A. HÀNG HÓA, DỊCH VỤ BÁN RA (đầu ra)", dec["ban_ra"], "Doanh thu chưa thuế")
    block("B. HÀNG HÓA, DỊCH VỤ MUA VÀO (đầu vào)", dec["mua_vao"], "Giá trị chưa thuế")

    ws.cell(r, 1, "C. KẾT QUẢ").font = Font(bold=True, size=12); r += 1
    def line(lbl, val, bold=False, note=""):
        nonlocal r
        ws.cell(r, 1, lbl).font = Font(bold=bold)
        c = ws.cell(r, 3, round(val)); c.number_format = MONEY; c.font = Font(bold=bold)
        if note:
            ws.cell(r, 4, note)
        r += 1
    line("Thuế GTGT đầu ra", dec["thue_dau_ra"])
    line("Thuế GTGT đầu vào được khấu trừ (ước)", dec["thue_dau_vao"])
    if dec["phai_nop"] > 0:
        line("=> Thuế GTGT PHẢI NỘP trong kỳ", dec["phai_nop"], bold=True,
             note="Đầu ra − Đầu vào")
    else:
        line("=> Thuế GTGT CÒN ĐƯỢC KHẤU TRỪ chuyển kỳ sau", dec["con_khau_tru"], bold=True,
             note="Đầu vào − Đầu ra")
    r += 1
    for txt in ("Ghi chú: Số liệu ước tính từ hóa đơn ĐÃ TẢI để đối chiếu vận hành, không thay tờ khai chính thức.",
                "Thuế đầu vào 'được khấu trừ' tính gộp; loại trừ HĐ >20 triệu thanh toán tiền mặt, HĐ không phục vụ SXKD do kế toán rà.",
                "HĐ trạng thái Hủy/Thay thế/Điều chỉnh đã được loại khỏi tổng hợp."):
        ws.cell(r, 1, txt).font = Font(italic=True, color="888888"); r += 1
    ws.column_dimensions["A"].width = 52
    for col in ("B", "C", "D"):
        ws.column_dimensions[col].width = 22

    # ---------- Sheet 2 + 3: bảng kê ----------
    for title, invs, loai in (("BK Mua vao (01-2)", purchase, "purchase"),
                              ("BK Ban ra (01-1)", sold, "sold")):
        ws2 = wb.create_sheet(title)
        heads = analysis.BANGKE_HEADERS
        rows = analysis.bang_ke_rows(invs, loai)
        money_cols = {8, 10, 11}
        _write_sheet(ws2, heads, rows, money_cols,
                     widths={1: 6, 2: 12, 3: 12, 4: 12, 5: 12, 6: 40, 7: 14, 8: 18, 9: 14, 10: 16, 11: 16, 12: 20, 13: 28})
        # dòng cộng
        last = ws2.max_row + 1
        ws2.cell(last, 1, "CỘNG").font = Font(bold=True)
        for cc in (8, 10, 11):
            s = sum((r[cc - 1] or 0) for r in rows if isinstance(r[cc - 1], (int, float)))
            c = ws2.cell(last, cc, round(s)); c.number_format = MONEY; c.font = Font(bold=True)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path


# ============================================ Xuất riêng theo menu (như app lớn)
def export_detail(path: str, purchase, sold) -> str:
    """Chỉ xuất SHEET CHI TIẾT MẶT HÀNG (mỗi dòng hàng 1 dòng) ra 1 file riêng."""
    wb = Workbook(); ws = wb.active; ws.title = "ChiTiet"
    rows = []; n = 0
    for loai, lst in (("Mua vào", purchase), ("Bán ra", sold)):
        for inv in lst:
            d = inv.get("_detail")
            if not d:
                continue
            for l in d.get("lines", []):
                n += 1
                rows.append([n, loai, fmt_date(inv.get("tdlap")), inv.get("shdon"),
                             f"{inv.get('khmshdon') or ''}{inv.get('khhdon') or ''}",
                             inv.get("nbmst"), inv.get("nbten"),
                             l.get("stt"), l.get("ten"), l.get("dvt"), l.get("sluong"),
                             l.get("dgia"), l.get("thtien"), l.get("tsuat"), l.get("tthue"),
                             inv.get("_cost_type") or ""])
    _write_sheet(ws, ["STT", "Loại", "Ngày HĐ", "Số HĐ", "Ký hiệu", "MST người bán",
                      "Tên người bán", "Dòng", "Tên hàng hóa, dịch vụ", "ĐVT", "Số lượng",
                      "Đơn giá", "Thành tiền", "Thuế suất", "Tiền thuế", "Loại chi phí"],
                 rows, {12, 13, 15}, {7: 40, 9: 50})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path


def zip_files(file_paths, out_path: str) -> int:
    """Gộp nhiều file (HTML/PDF...) vào 1 file .zip. Trả về số file đã thêm."""
    import zipfile
    files = [p for p in file_paths if p and os.path.isfile(p)]
    if not files:
        raise RuntimeError("Không có file nào để nén.")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    n = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            try:
                z.write(p, os.path.basename(p)); n += 1
            except Exception:
                pass
    return n
