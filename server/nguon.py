"""nguon.py - DẪN NGUỒN và TỰ KIỂM SỐ LIỆU cho câu trả lời của MinMin (Trụ 3, 26.10.137).

Vì sao cần: MinMin báo cáo số liệu kinh doanh (doanh thu, hoá đơn, chi phí ads). Một con số
nói ra mà không chỉ được lấy từ đâu thì người chủ không kiểm được, và một con số bịa nghe y hệt
một con số thật. File này làm hai việc, BẰNG LUẬT, không nhờ model nào tự chấm:

  1. CHÂN NGUỒN: dưới câu trả lời ghi rõ lượt này đã đọc dữ liệu từ tool nào, tham số gì, lúc
     mấy giờ. Đó là "chứng từ" của câu trả lời.
  2. NEO SỐ: rút mọi con số đáng kể trong câu trả lời, đối chiếu từng số với nội dung tool
     trả về. Số nào KHÔNG thấy trong bất kỳ kết quả tool nào thì cảnh báo: có thể model tự
     cộng trừ (chấp nhận được) hoặc bịa (không chấp nhận được), người đọc phải kiểm lại.
     Câu hỏi về dữ liệu mà không gọi tool nào vẫn có số liệu -> cảnh báo mạnh nhất.

Thuần stdlib, không import main/engine. Phần nối vào lượt chat ở main.py (nhánh não API của
dashboard): gom sự kiện tool_call/tool_result rồi gọi `chan_nguon`.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Iterable

# Số "đáng kể": từ 1.000 trở lên (tiền, số đơn, số hoá đơn) hoặc có dấu nhóm nghìn. Bỏ năm.
NGUONG_SO = 1000
_NAM_MIN, _NAM_MAX = 1900, 2100
# Câu hỏi "về dữ liệu": không gọi tool mà vẫn có số là đáng ngờ nhất.
# Chỉ từ chuyên NGÀNH, không lấy "bao nhiêu"/"tổng": câu tính nhẩm nào cũng có mấy chữ đó.
_TU_DU_LIEU = ("doanh thu", "hoa don", "chi phi", "don hang", "ton kho", "bao cao", "thong ke",
               "loi nhuan", "quang cao", "ads", "pancake", "revenue", "invoice", "orders",
               "report", "inventory", "profit")


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "d").lower()


# ─────────────────────────── rút số ───────────────────────────

_RE_NHOM = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})+(?![\d.,])")   # 1.550.000 / 1,550,000
_RE_TRAN = re.compile(r"(?<![\d.,])\d+(?![\d.,])")


def cac_so(text: str) -> set:
    """Các số nguyên trong văn bản, hiểu cả kiểu nhóm nghìn VN (1.550.000) và Anh (1,550,000).
    Nhóm nghìn bắt trước rồi xoá khỏi văn bản, để "2.569.434" không bị đọc thành 2 và 569."""
    text = str(text or "")
    ra = set()
    for m in _RE_NHOM.finditer(text):
        try:
            ra.add(int(re.sub(r"[.,]", "", m.group(0))))
        except ValueError:
            pass
    con_lai = _RE_NHOM.sub(" ", text)
    for m in _RE_TRAN.finditer(con_lai):
        try:
            ra.add(int(m.group(0)))
        except ValueError:
            pass
    return ra


def so_dang_ke(text: str, *, tru: Iterable[int] = ()) -> set:
    """Số đáng kiểm: >= NGUONG_SO, không phải năm, không nằm trong `tru` (vd số đã có trong
    câu hỏi - người dùng tự đưa thì không cần nguồn)."""
    tru = set(tru or ())
    return {n for n in cac_so(text)
            if n >= NGUONG_SO and not (_NAM_MIN <= n <= _NAM_MAX) and n not in tru}


def _chuoi_so_trong(ket_qua: str) -> set:
    """Tập số xuất hiện trong một kết quả tool (JSON hay văn bản). Đọc cả số thập phân kiểu
    "1550000.0" (JSON) bằng cách bỏ phần ".0"."""
    kq = str(ket_qua or "")
    kq = re.sub(r"(\d)\.0+(?!\d)", r"\1", kq)   # 1550000.0 -> 1550000
    return cac_so(kq)


def neo_so(tra_loi: str, cau_hoi: str, ket_qua_tool: Iterable[str]) -> dict:
    """Đối chiếu số trong câu trả lời với dữ liệu tool.

    Trả {"co_nguon": [..], "khong_nguon": [..]} (số nguyên, đã sắp). Số có mặt trong BẤT KỲ
    kết quả tool nào là có nguồn. Số nằm sẵn trong câu hỏi thì không xét."""
    trong_hoi = cac_so(cau_hoi)
    can = so_dang_ke(tra_loi, tru=trong_hoi)
    kho = set()
    for kq in ket_qua_tool or ():
        kho |= _chuoi_so_trong(kq)
    co = sorted(n for n in can if n in kho)
    khong = sorted(n for n in can if n not in kho)
    return {"co_nguon": co, "khong_nguon": khong}


# ─────────────────────────── chân nguồn ───────────────────────────

def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _tom_tat_args(args) -> str:
    """Tham số tool rút gọn cho người đọc: loai=mua, tu=2026-01-01. Tối đa 60 ký tự."""
    if not isinstance(args, dict) or not args:
        return ""
    phan = []
    for k, v in list(args.items())[:4]:
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        v = str(v)
        if len(v) > 18:
            v = v[:15] + "..."
        phan.append(f"{k}={v}")
    s = ", ".join(phan)
    return s if len(s) <= 60 else s[:57] + "..."


def chan_nguon(tra_loi: str, cau_hoi: str, tool_calls: list, ket_qua_tool: list, *,
               luc: str = "", bat: bool = True) -> str:
    """Dựng chân nguồn (chuỗi, có thể rỗng) để nối dưới câu trả lời.

    tool_calls: [{"name": str, "input": dict}], ket_qua_tool: [str]. `luc` = giờ phút đọc dữ liệu.
    Rỗng khi: tắt, hoặc lượt không có tool lẫn không có số đáng kể (chat thường)."""
    if not bat:
        return ""
    goi = [tc for tc in (tool_calls or []) if (tc or {}).get("name")]
    # tool nội bộ của hub (tìm tool, chạy tool) không phải NGUỒN dữ liệu; tên thật đã được
    # chuyển qua javis_run_tool(name=...) nên đọc từ input.
    ten_nguon = []
    for tc in goi:
        n = str(tc.get("name") or "")
        n = n.rsplit("__", 1)[-1]
        if n == "javis_run_tool":
            n = str((tc.get("input") or {}).get("name") or n).rsplit("__", 1)[-1]
            args = (tc.get("input") or {}).get("args") or {}
        else:
            args = tc.get("input") or {}
        if n in ("javis_search_tools", "javis_no_tools", "javis_wait_quota"):
            continue
        tt = _tom_tat_args(args)
        ten_nguon.append(f"{n}({tt})" if tt else n)
    neo = neo_so(tra_loi, cau_hoi, ket_qua_tool)
    co_so = bool(neo["co_nguon"] or neo["khong_nguon"])
    if not ten_nguon and not co_so:
        return ""
    dong = []
    if ten_nguon:
        # gộp trùng, giữ thứ tự
        seen, uniq = set(), []
        for t in ten_nguon:
            if t not in seen:
                seen.add(t); uniq.append(t)
        dong.append("Nguồn: " + " · ".join(uniq[:6]) + (f" · lúc {luc}" if luc else ""))
    if neo["khong_nguon"]:
        ds = ", ".join(_fmt(n) for n in neo["khong_nguon"][:6])
        if ten_nguon:
            dong.append(f"⚠ Số chưa thấy trong dữ liệu tool: {ds}. Có thể model tự cộng trừ, "
                        f"hoặc bịa; bố kiểm lại trước khi dùng.")
        elif any(k in bo_dau(cau_hoi) for k in _TU_DU_LIEU):
            dong.append(f"⚠ Câu trả lời có số liệu ({ds}) nhưng lượt này KHÔNG đọc dữ liệu nào. "
                        f"Đừng dùng con số này.")
        else:
            return ""   # chat thường, model tự tính (vd 3 áo x 250k): không cằn nhằn
    return "\n".join(dong)
