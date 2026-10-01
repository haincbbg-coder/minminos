# -*- coding: utf-8 -*-
"""
invoice_xml.py - Giải nén file zip cổng thuế trả về, bóc dữ liệu XML hóa đơn
(chuẩn TĐ 78/2021/NĐ-CP và các biến thể T-VAN), tạo HTML để in PDF khi cần.
"""
from __future__ import annotations

import html
import base64
import re
import io
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(el: Optional[ET.Element], names, default: str = "") -> str:
    if el is None:
        return default
    names = [names] if isinstance(names, str) else names
    for child in el.iter():
        if _local(child.tag) in names and child.text and child.text.strip():
            return child.text.strip()
    return default


def _find(el: ET.Element, names) -> Optional[ET.Element]:
    names = [names] if isinstance(names, str) else names
    for child in el.iter():
        if _local(child.tag) in names:
            return child
    return None


def _num(s: str) -> float:
    s = (s or "").strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _looks_xml(data: bytes) -> bool:
    head = data.lstrip(b"\xef\xbb\xbf \r\n\t")[:200].lower()
    return head.startswith(b"<?xml") or b"<hdon" in head or b"<tdiep" in head or head.startswith(b"<")


def _looks_html(data: bytes) -> bool:
    head = data.lstrip()[:300].lower()
    return b"<html" in head or b"<!doctype html" in head


def extract_zip(zip_bytes: bytes, _depth: int = 0) -> dict:
    """-> {"xml": bytes|None, "html": bytes|None, "others": {name: bytes}, "names": [..]}
    Nhận diện theo NỘI DUNG (không tin tên file): cổng thuế có lúc trả file XML không đuôi,
    hoặc zip lồng trong zip."""
    out = {"xml": None, "html": None, "others": {}, "names": []}
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        if _looks_xml(zip_bytes) and not _looks_html(zip_bytes):
            out["xml"] = zip_bytes
        elif _looks_html(zip_bytes):
            out["html"] = zip_bytes
        return out
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        data = zf.read(name)
        out["names"].append(name)
        low = name.lower()
        if (low.endswith(".zip") or data[:2] == b"PK") and _depth < 3:
            inner = extract_zip(data, _depth + 1)
            out["xml"] = out["xml"] or inner["xml"]; out["html"] = out["html"] or inner["html"]
            out["others"].update(inner["others"]); out["names"] += [name + "/" + n for n in inner["names"]]
        elif (low.endswith(".xml") or _looks_xml(data)) and not _looks_html(data) and out["xml"] is None:
            out["xml"] = data
        elif (low.endswith((".html", ".htm")) or _looks_html(data)) and out["html"] is None:
            out["html"] = data
        else:
            out["others"][name] = data
    return out


def parse_invoice(xml_bytes: bytes) -> dict:
    """Bóc thông tin chung + danh sách dòng hàng từ XML hóa đơn."""
    root = ET.fromstring(xml_bytes)
    tt_chung = _find(root, "TTChung")
    nban = _find(root, ["NBan", "SellerInfo"])
    nmua = _find(root, ["NMua", "BuyerInfo"])
    ttoan = _find(root, ["TToan", "Payment"])
    hdr = {
        "khmshdon": _text(tt_chung, "KHMSHDon"),
        "khhdon": _text(tt_chung, "KHHDon"),
        "shdon": _text(tt_chung, ["SHDon", "SoHD"]),
        "ngay": _text(tt_chung, ["NLap", "NgayLap"]),
        "dvtte": _text(tt_chung, "DVTTe", "VND"),
        "tgia": _text(tt_chung, "TGia", "1"),
        "httt": _text(tt_chung, "HTTToan"),
        "mccqt": _text(root, "MCCQT"),
        "ban_mst": _text(nban, ["MST", "sellerTaxCode"]),
        "ban_ten": _text(nban, ["Ten", "sellerLegalName"]),
        "ban_dchi": _text(nban, ["DChi", "sellerAddressLine"]),
        "mua_mst": _text(nmua, ["MST", "buyerTaxCode"]),
        "mua_ten": _text(nmua, ["Ten", "buyerLegalName"]),
        "mua_dchi": _text(nmua, ["DChi", "buyerAddressLine"]),
        "mua_hvt": _text(nmua, ["HVTNMHang"]),
        "tien_chua_thue": _num(_text(ttoan, ["TgTCThue", "TotalAmountWithoutVAT"])),
        "tien_thue": _num(_text(ttoan, ["TgTThue", "TotalVATAmount"])),
        "tien_ck": _num(_text(ttoan, ["TTCKTMai"])),
        "tong_tien": _num(_text(ttoan, ["TgTTTBSo", "TotalAmountWithVAT"])),
        "tong_bang_chu": _text(ttoan, ["TgTTTBChu", "TotalAmountInWords"]),
    }
    lines = []
    for el in root.iter():
        if _local(el.tag) in ("HHDVu", "ItemInfo"):
            # chỉ lấy tag con trực tiếp để không lẫn tag của dòng khác
            d = {_local(c.tag): (c.text or "").strip() for c in el}
            tchat = d.get("TChat", "1")
            lines.append({
                "stt": d.get("STT", str(len(lines) + 1)),
                "tchat": tchat,  # 1 hàng hóa, 2 khuyến mại, 3 chiết khấu, 4 ghi chú
                "ten": d.get("THHDVu") or d.get("ItemName", ""),
                "dvt": d.get("DVTinh") or d.get("UnitName", ""),
                "sluong": _num(d.get("SLuong") or d.get("Quantity", "")),
                "dgia": _num(d.get("DGia") or d.get("UnitPrice", "")),
                "thtien": _num(d.get("ThTien") or d.get("Amount", "")),
                "tsuat": d.get("TSuat") or d.get("VATRate", ""),
                "tthue": _num(d.get("TThue") or d.get("VATAmount", "")),
                "ck": _num(d.get("STCKhau", "")),
            })
    # nếu XML có bảng LTSuat (tổng thuế theo thuế suất) mà dòng hàng không có TThue,
    # phân bổ tiền thuế theo thuế suất của dòng.
    if lines and all(l["tthue"] == 0 for l in lines):
        for l in lines:
            r = _rate(l["tsuat"])
            if r is not None:
                l["tthue"] = round(l["thtien"] * r / 100)
    hdr["lines"] = lines
    # MST tổ chức cung cấp giải pháp (để biết NHÀ PHÁT HÀNH) + ngày ký số
    try:
        import re as _re
        raw = xml_bytes.decode("utf-8", "ignore")
        m = _re.search(r"<MSTTCGP>\s*([0-9\-]+)", raw, _re.I)
        hdr["msttcgp"] = (m.group(1).replace("-", "") if m else "")
        sk = _re.findall(r"(?:SigningTime|NgayKy|SignDate)>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", raw, _re.I)
        hdr["ngay_ky"] = sk[-1] if sk else ""
    except Exception:  # noqa
        hdr["msttcgp"] = ""; hdr["ngay_ky"] = ""
    return hdr


def _rate(s: str) -> Optional[float]:
    s = (s or "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None  # KCT, KKKNT...


def render_html(inv: dict) -> str:
    """Tạo HTML hóa đơn (dùng khi zip không có invoice.html) để in ra PDF."""
    def fmt(n):
        try:
            return f"{float(n):,.0f}".replace(",", ".")
        except (TypeError, ValueError):
            return html.escape(str(n or ""))
    rows = "".join(
        f"<tr><td>{html.escape(l['stt'])}</td><td>{html.escape(l['ten'])}</td>"
        f"<td>{html.escape(l['dvt'])}</td><td class='r'>{fmt(l['sluong'])}</td>"
        f"<td class='r'>{fmt(l['dgia'])}</td><td class='r'>{fmt(l['thtien'])}</td>"
        f"<td class='r'>{html.escape(str(l['tsuat']))}</td><td class='r'>{fmt(l['tthue'])}</td></tr>"
        for l in inv.get("lines", []))
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>Hóa đơn {html.escape(inv.get('khhdon',''))}-{html.escape(inv.get('shdon',''))}</title>
<style>body{{font-family:Arial,Helvetica,sans-serif;font-size:12px;margin:24px;color:#111}}
h1{{text-align:center;font-size:18px;margin:4px 0}} .c{{text-align:center}} .r{{text-align:right}}
table{{border-collapse:collapse;width:100%;margin-top:10px}} th,td{{border:1px solid #444;padding:4px 6px}}
th{{background:#eef}} .meta td{{border:none;padding:2px 4px}} .tot td{{font-weight:bold}}</style></head><body>
<h1>HÓA ĐƠN GIÁ TRỊ GIA TĂNG</h1>
<p class="c">Ký hiệu: <b>{html.escape(inv.get('khmshdon',''))}{html.escape(inv.get('khhdon',''))}</b>
&nbsp;&nbsp; Số: <b>{html.escape(inv.get('shdon',''))}</b> &nbsp;&nbsp; Ngày: {html.escape(inv.get('ngay',''))}</p>
<p class="c">Mã CQT: {html.escape(inv.get('mccqt',''))}</p>
<table class="meta">
<tr><td><b>Đơn vị bán:</b> {html.escape(inv.get('ban_ten',''))}</td></tr>
<tr><td>MST: {html.escape(inv.get('ban_mst',''))} - Địa chỉ: {html.escape(inv.get('ban_dchi',''))}</td></tr>
<tr><td><b>Đơn vị mua:</b> {html.escape(inv.get('mua_ten',''))} {('- ' + html.escape(inv.get('mua_hvt',''))) if inv.get('mua_hvt') else ''}</td></tr>
<tr><td>MST: {html.escape(inv.get('mua_mst',''))} - Địa chỉ: {html.escape(inv.get('mua_dchi',''))}</td></tr>
<tr><td>Hình thức thanh toán: {html.escape(inv.get('httt',''))} - Đơn vị tiền tệ: {html.escape(inv.get('dvtte','VND'))}</td></tr>
</table>
<table><thead><tr><th>STT</th><th>Tên hàng hóa, dịch vụ</th><th>ĐVT</th><th>Số lượng</th>
<th>Đơn giá</th><th>Thành tiền</th><th>Thuế suất</th><th>Tiền thuế</th></tr></thead>
<tbody>{rows}</tbody>
<tfoot class="tot"><tr><td colspan="5" class="r">Cộng tiền hàng</td><td class="r">{fmt(inv.get('tien_chua_thue'))}</td><td></td><td class="r">{fmt(inv.get('tien_thue'))}</td></tr>
<tr><td colspan="5" class="r">Tổng tiền thanh toán</td><td class="r" colspan="3">{fmt(inv.get('tong_tien'))}</td></tr>
<tr><td colspan="8">Số tiền viết bằng chữ: {html.escape(inv.get('tong_bang_chu',''))}</td></tr></tfoot></table>
<p class="c" style="margin-top:20px;color:#666">Bản thể hiện hóa đơn điện tử - tạo từ dữ liệu XML tải về từ hoadondientu.gdt.gov.vn</p>
</body></html>"""


def prepare_invoice_html(content: bytes, assets: dict) -> bytes:
    """Bản thể hiện tự chứa ảnh từ ZIP, không chạy script của file tải về."""
    text = content.decode("utf-8-sig", errors="replace")
    images = {}
    for name, data in assets.items():
        if len(data) > 2 * 1024 * 1024:
            continue
        mime = "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if data.startswith(b"\xff\xd8\xff") else ""
        if mime:
            images[name.replace("\\", "/")] = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")

    def image_url(value):
        key = value.strip().removeprefix("./")
        return images.get(key, value)

    text = re.sub(r'url\(\s*([\"\x27]?)([^)\"\x27]+)\1\s*\)',
                  lambda m: 'url("' + image_url(m[2]) + '")', text, flags=re.I)
    text = re.sub(r'(<img\b[^>]*\bsrc\s*=\s*)([\"\x27])([^\"\x27]+)\2',
                  lambda m: m[1] + m[2] + image_url(m[3]) + m[2], text, flags=re.I)
    text = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', text, flags=re.I | re.S)
    bg = images.get("viewinvoice-bg.jpg", "")
    css = """<style data-minmin-print="2">
    @media print {
      .print-page, .main-page { max-width: 100% !important; min-height: 0 !important; box-shadow: none !important; }
      .main-page { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .sign-box, .sign-box * { overflow-wrap: anywhere !important; word-break: break-word !important; white-space: normal !important; }
      .sign-box { max-width: 100% !important; padding-bottom: 70px !important; background-position: right 10px bottom 5px !important; }
    """ + ('.main-page { background-image: url("' + bg + '") !important; }' if bg else '') + "\n}</style>"
    return (text.replace("</head>", css + "</head>", 1) if "</head>" in text else css + text).encode("utf-8")


def save_invoice_files(folder: str, base: str, zip_bytes: bytes,
                       keep_zip: bool = False) -> dict:
    """Lưu XML (+ invoice.html) vào thư mục. -> {"xml": path, "html": path|None, "zip": path|None, "names": [...]}
    Không tìm thấy XML thì LUÔN giữ lại zip gốc để không mất dữ liệu."""
    os.makedirs(folder, exist_ok=True)
    parts = extract_zip(zip_bytes)
    out = {"xml": None, "html": None, "zip": None, "names": parts.get("names", [])}
    if keep_zip or parts["xml"] is None:
        zp = os.path.join(folder, base + ".zip")
        with open(zp, "wb") as f:
            f.write(zip_bytes)
        out["zip"] = zp
    if parts["xml"]:
        p = os.path.join(folder, base + ".xml")
        with open(p, "wb") as f:
            f.write(parts["xml"])
        out["xml"] = p
    if parts["html"]:
        p = os.path.join(folder, base + ".html")
        with open(p, "wb") as f:
            f.write(prepare_invoice_html(parts["html"], parts["others"]))
        out["html"] = p
    return out
