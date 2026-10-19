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

# Đuôi: không được nối tiếp bằng chữ số, hoặc dấu+chữ số (số thập phân/nhóm nghìn dở). Dấu
# phẩy/chấm đứng một mình phía sau (JSON "12500000, " hay cuối câu) thì vẫn là số nguyên.
_RE_NHOM = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)")   # 1.550.000 / 1,550,000
_RE_TRAN = re.compile(r"(?<![\d.,])\d+(?![.,]?\d)")


_RE_THE = re.compile(r"<!--\s*JAVIS_CARD:[\s\S]*?-->")


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
    ra = cac_so(kq)
    # Số thập phân lẻ kiểu API ("spend":"553483.1"): cac_so bỏ qua cả số vì đuôi .1, nên chi
    # tiêu Meta không bao giờ "có nguồn" (chủ repo 13/10). Lấy phần nguyên và bản làm tròn.
    for m in re.finditer(r"(?<![\d.,])(\d{4,})\.(\d+)(?![\d.,])", kq):
        try:
            nguyen = int(m.group(1))
            ra.add(nguyen)
            ra.add(int(round(float(m.group(0)))))
        except ValueError:
            pass
    return ra


# Số kèm ĐƠN VỊ trong câu trả lời: "4,306 tỷ", "42,3 triệu", "7.225 tỷ đồng". Dấu phẩy hay chấm
# ở đây là dấu THẬP PHÂN (người Việt viết tiền tỷ như vậy), không phải nhóm nghìn.
_DON_VI = {"ty": 1e9, "tỷ": 1e9, "trieu": 1e6, "triệu": 1e6, "tr": 1e6, "nghin": 1e3,
           "nghìn": 1e3, "ngan": 1e3, "ngàn": 1e3, "k": 1e3}
_RE_DON_VI = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,3})?)\s*(tỷ|ty|triệu|trieu|tr|nghìn|nghin|ngàn|ngan|k)\b",
                        re.IGNORECASE)


def so_co_don_vi(text: str) -> dict:
    """{số-như-cac_so-đọc: giá trị thật}. "4,306 tỷ" -> {4306: 4.306e9}; "42,3 triệu" -> {423: 4.23e7}.

    Vì sao (26.10.157): model viết "doanh thu 4,306 tỷ đồng", cac_so đọc thành 4306 rồi không
    thấy 4306 trong JSON Pancake (ở đó là 4306251000) -> báo oan "số chưa thấy". Số đó là số
    THẬT, chỉ viết theo đơn vị người đọc."""
    ra = {}
    for m in _RE_DON_VI.finditer(str(text or "")):
        chu, dv = m.group(1), m.group(2).lower()
        he = _DON_VI.get(dv) or _DON_VI.get(bo_dau(dv))
        if not he:
            continue
        try:
            gia_tri = float(chu.replace(",", ".")) * he
            khoa = int(re.sub(r"[.,]", "", chu))
        except ValueError:
            continue
        ra[khoa] = gia_tri
    return ra


def _la_ban_lam_tron(n: int, kho: set) -> bool:
    """n là bản LÀM TRÒN của một số trong kho? 7225 ~ 7224638000 (viết "7,225 tỷ"), 42300 ~ 42312000.
    Đòi ít nhất 4 chữ số có nghĩa để không khớp bừa với mọi số bắt đầu bằng cùng 3 chữ số."""
    m = int(str(n).rstrip("0") or "0")
    if m < 1000:
        return False
    for k in kho:
        if k <= n:
            continue
        for p in range(1, 13):
            q = round(k / 10 ** p)
            if q == m:
                return True
            if q < m:
                break
    return False


def _khop_xap_xi(n: int, don_vi: dict, kho: set) -> bool:
    """n viết kèm đơn vị (4,306 tỷ) có khớp số nào trong kho trong sai số nửa chữ số cuối?"""
    v = don_vi.get(n)
    if not v:
        return False
    for k in kho:
        if k and abs(k - v) / v <= 5e-4:
            return True
    return False


def _la_tong(n: int, kho_lon: list) -> bool:
    """n là tổng của 2 hoặc 3 số đáng kể trong kho? (model tự cộng 3 tài khoản ads: chấp nhận
    được, không phải bịa). kho_lon: danh sách số >= NGUONG_SO, đã sắp, đã bỏ trùng."""
    tap = set(kho_lon)
    for i, a in enumerate(kho_lon):
        if a >= n:
            break
        if (n - a) in tap and (n - a) != a:
            return True
        for b in kho_lon[i + 1:]:
            if a + b >= n:
                break
            c = n - a - b
            if c in tap and c not in (a, b):
                return True
    return False


def neo_so(tra_loi: str, cau_hoi: str, ket_qua_tool: Iterable[str]) -> dict:
    """Đối chiếu số trong câu trả lời với dữ liệu tool.

    Trả {"co_nguon": [..], "khong_nguon": [..], "xap_xi": [..]} (số nguyên, đã sắp). Số có
    mặt trong BẤT KỲ kết quả tool nào là có nguồn. Số viết theo đơn vị (4,306 tỷ) hay làm tròn
    (7.225 của 7.224.638.000) mà khớp một số trong kho thì là "xấp xỉ": cũng có nguồn, không
    cảnh báo. Số nằm sẵn trong câu hỏi thì không xét."""
    trong_hoi = cac_so(cau_hoi)
    tra_loi = _RE_THE.sub(" ", str(tra_loi or ""))   # JSON của thẻ biểu đồ không phải câu chữ để đối chiếu
    can = so_dang_ke(tra_loi, tru=trong_hoi)
    kho = set()
    for kq in ket_qua_tool or ():
        kho |= _chuoi_so_trong(kq)
    don_vi = so_co_don_vi(tra_loi)
    kho_lon = sorted(k for k in kho if k >= NGUONG_SO)[:600]   # chặn trên cho vòng tổng O(k²)
    co, xap_xi, tong, khong = [], [], [], []
    for n in sorted(can):
        if n in kho:
            co.append(n)
        elif _khop_xap_xi(n, don_vi, kho) or _la_ban_lam_tron(n, kho):
            xap_xi.append(n)
        elif _la_tong(n, kho_lon):
            tong.append(n)
        else:
            khong.append(n)
    return {"co_nguon": co, "khong_nguon": khong, "xap_xi": xap_xi, "tong": tong}


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


def gom_nguon(ten_nguon: list, toi_da: int = 6) -> list:
    """Gộp các lần gọi CÙNG TOOL thành một mục: `pos_order ×4`, giữ thứ tự xuất hiện đầu.
    Gọi một lần thì kèm tham số rút gọn `pos_order(action=list, shop_id=...)`.

    Vì sao (26.10.156): báo cáo 2 shop gọi pos_order bốn lần, chân nguồn liệt kê đủ bốn dòng
    tham số dài gần bằng chính câu trả lời, chữ nhiều mà thông tin ít; và chân nguồn quay lại
    ngữ cảnh ở lượt sau, nên dài là tốn token mỗi lượt về sau."""
    thu_tu, dem, args_dau = [], {}, {}
    for n, tt in ten_nguon:
        if n not in dem:
            thu_tu.append(n); args_dau[n] = tt
        dem[n] = dem.get(n, 0) + 1
    ra = []
    for n in thu_tu[:toi_da]:
        if dem[n] > 1:
            ra.append(f"{n} ×{dem[n]}")
        else:
            ra.append(f"{n}({args_dau[n]})" if args_dau[n] else n)
    if len(thu_tu) > toi_da:
        ra.append(f"+{len(thu_tu) - toi_da} tool khác")
    return ra


# Dòng chân nguồn GIẢ do model viết: sau vài lượt thấy "Nguồn: pos_order ×4 · lúc 10:44" dưới
# câu trả lời, model bắt chước và tự in một dòng y hệt (kể cả "⚠ Số chưa thấy..."), có khi
# hai lần (chủ repo 13/10 13:04: hai dòng Nguồn, hai giờ khác nhau). Chân nguồn là CHỨNG TỪ do
# code dựng từ nhật ký tool; model in ra thì vừa sai vừa làm người đọc hết tin dòng thật.
_RE_CHAN_GIA = re.compile(
    r"^[ \t]*(?:Nguồn:[^\n]*(?:· lúc \d{1,2}:\d{2}|×\d+)[^\n]*"
    r"|⚠[ \t]*Số chưa thấy trong dữ liệu tool:[^\n]*"
    r"|⚠[ \t]*Câu trả lời có số liệu[^\n]*"
    r"|Tự cộng từ dữ liệu:[^\n]*)[ \t]*$",
    re.MULTILINE)


def bo_chan_gia(tra_loi: str) -> str:
    """Xoá các dòng model tự in giả chân nguồn, để chân nguồn THẬT (dựng từ nhật ký) đứng một
    mình. Không đụng vào câu chữ khác."""
    s = str(tra_loi or "")
    if "Nguồn:" not in s and "⚠" not in s and "Tự cộng" not in s:
        return s
    s = _RE_CHAN_GIA.sub("", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.rstrip()


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
        # Tool nội bộ của hub (tìm tool, đọc/ghi file brain, skill) không phải NGUỒN dữ liệu
        # kinh doanh; kể vào chỉ làm chân nguồn dài ra mà không nói thêm gì.
        if n in ("javis_search_tools", "javis_no_tools", "javis_wait_quota", "javis_read_file",
                 "javis_list_files", "javis_write_file", "javis_use_skill", "javis_connections",
                 "javis_now", "javis_date_add"):
            continue
        ten_nguon.append((n, _tom_tat_args(args)))
    neo = neo_so(tra_loi, cau_hoi, ket_qua_tool)
    co_so = bool(neo["co_nguon"] or neo["khong_nguon"])
    if not ten_nguon and not co_so:
        return ""
    dong = []
    if ten_nguon:
        dong.append("Nguồn: " + " · ".join(gom_nguon(ten_nguon)) + (f" · lúc {luc}" if luc else ""))
    if neo.get("tong") and ten_nguon:
        # Tổng model tự cộng từ các số có trong dữ liệu: nói ra để người đọc biết đó là phép
        # cộng chứ không phải số tool trả, nhưng không phải cảnh báo.
        dong.append("Tự cộng từ dữ liệu: " + ", ".join(_fmt(n) for n in neo["tong"][:6]))
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
