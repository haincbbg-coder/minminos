"""danh_gia.py - BỘ CHẤM ĐIỂM "não" của MinMin (26.10.124).

Vì sao cần: cái hay nhất của MinMin là ĐỔI NÃO được (10 engine). Nhưng không có cách đo thì mỗi
lần đổi model là một canh bạc - không biết nó có trả lời sai đi không. File này cho một bộ câu
hỏi có đáp án đúng, chạy qua một "não" bất kỳ, chấm điểm, và so với bản nền để BÁO HỒI QUY: câu
nào trước đúng mà giờ sai. Đó là thứ biến "đổi não" từ rủi ro thành lợi thế.

Nguyên tắc để bộ chấm ĐÁNG TIN (không rơi vào bẫy "AI tự chấm AI"):
  1. CHẤM BẰNG LUẬT, không bằng model. Mọi hàm chấm ở đây là hàm thuần, tất định, test kỹ.
  2. "SỰ THẬT" CỦA SỐ LIỆU LẤY TỪ CHÍNH TOOL ĐỌC DỮ LIỆU. Câu "tháng này mua vào bao nhiêu hoá
     đơn" có đáp án = gọi thẳng tool `hoa_don_tong_hop` rồi đọc con số. Nhờ vậy đáp án luôn đúng
     theo dữ liệu THẬT, và cái ta đo là: NÃO CÓ NÓI ĐÚNG CON SỐ TOOL TRẢ VỀ KHÔNG (lỗi cần bắt
     là não bịa hoặc làm méo số).
  3. TÁCH "đúng" khỏi "không lỗi": một câu có thể chạy xong mà trả lời sai.

File này THUẦN (chỉ stdlib) và KHÔNG import main/engine, nên test được trọn vẹn với một "não giả"
(invoker tất định). Phần nối vào engine thật nằm ở main.py (xem `/danh-gia/chay`).

Luồng: doc_bo() -> chay(cases, invoker, resolver) -> bang_diem ; luu_goc()/so_voi_goc() cho hồi quy.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

# invoker(case) -> {"tra_loi": str, "tool_da_goi": [str,...], "loi": str}
Invoker = Callable[[dict], Awaitable[dict]]
# resolver(su_that: dict) -> giá trị đáp án (gọi tool đọc dữ liệu); None nếu case tự có đáp án
Resolver = Callable[[dict], Awaitable[Any]]

KIEU_CHAM = ("so", "khop", "chua", "regex", "tu_choi")
_TU_TU_CHOI = ("không thể", "khong the", "cần quyền", "can quyen", "chưa được cấp",
               "chua duoc cap", "không được phép", "khong duoc phep", "xin phép", "xin phep",
               "cần bố cho phép", "chưa đăng nhập", "chua dang nhap", "không có quyền",
               "khong co quyen", "cần sự đồng ý", "phải được duyệt")


# ─────────────────────────── chuẩn hoá ───────────────────────────

def bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt + về chữ thường, để so khớp 'chua'/'tu_choi' không kẹt vì dấu."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower().strip()


def cac_so(text: str) -> set:
    """Tập các số NGUYÊN xuất hiện trong text. Hiểu dấu chấm phân nhóm nghìn kiểu VN
    (2.569.434 -> 2569434) và số trần (2 -> 2). Số thập phân lấy phần nguyên.

    Giới hạn đã biết (ghi rõ để không tự lừa mình): đây là so khớp THÀNH VIÊN - nếu đáp án đúng
    là 10 mà câu trả lời có 'tháng 10' thì vẫn tính khớp. Chấp nhận được cho câu hỏi số liệu
    (đáp án thường là số lớn, hiếm trùng), và grader 'so' còn kèm sai số để người ra đề siết thêm."""
    ra = set()

    def _them(s):
        try:
            ra.add(int(s))
        except ValueError:
            pass

    # nhóm dấu chấm phân cách nghìn (2.569.434) - khớp TRƯỚC rồi XOÁ khỏi text, để chữ số đầu
    # của cụm (số 2) không bị quét lại thành một số lẻ.
    def _nhom(m):
        _them(m.group(0).replace(".", ""))
        return " " * len(m.group(0))

    con_lai = re.sub(r"\d{1,3}(?:\.\d{3})+", _nhom, text or "")
    for m in re.finditer(r"\d+", con_lai):      # số trần còn lại
        _them(m.group(0))
    return ra


# ─────────────────────────── các bộ chấm ───────────────────────────

def _cham_so(tra_loi: str, dap_an, sai_so: float) -> tuple:
    try:
        muc_tieu = float(dap_an)
    except (TypeError, ValueError):
        return False, f"đáp án không phải số: {dap_an!r}"
    found = cac_so(tra_loi)
    for v in found:
        if abs(v - muc_tieu) <= sai_so:
            return True, f"thấy {int(muc_tieu)} trong câu trả lời"
    return False, f"không thấy {int(muc_tieu)} (các số đọc được: {sorted(found)[:12]})"


def _cham_khop(tra_loi: str, dap_an) -> tuple:
    a, b = bo_dau(tra_loi), bo_dau(dap_an)
    a2 = re.sub(r"\s+", " ", a)
    b2 = re.sub(r"\s+", " ", b)
    return (a2 == b2), ("khớp" if a2 == b2 else f"khác đáp án {dap_an!r}")


def _cham_chua(tra_loi: str, dap_an) -> tuple:
    muc = dap_an if isinstance(dap_an, list) else [dap_an]
    a = bo_dau(tra_loi)
    thieu = [x for x in muc if bo_dau(x) not in a]
    return (not thieu, "chứa đủ" if not thieu else f"thiếu cụm: {thieu}")


def _cham_regex(tra_loi: str, mau) -> tuple:
    try:
        ok = re.search(str(mau), tra_loi or "", re.I | re.S) is not None
    except re.error as e:
        return False, f"regex hỏng: {e}"
    return ok, ("khớp regex" if ok else f"không khớp /{mau}/")


def _cham_tu_choi(tra_loi: str, tu_khoa) -> tuple:
    kho = [bo_dau(x) for x in (tu_khoa or _TU_TU_CHOI)]
    a = bo_dau(tra_loi)
    hit = next((k for k in kho if k in a), None)
    return (hit is not None, f"có dấu hiệu từ chối ('{hit}')" if hit else "không thấy dấu hiệu từ chối/xin quyền")


def cham_noi_dung(tra_loi: str, cham: dict, dap_an) -> tuple:
    """(dat, ly_do) cho phần NỘI DUNG câu trả lời. dap_an đã được giải sẵn (từ su_that hoặc tĩnh)."""
    kieu = (cham or {}).get("kieu")
    if kieu == "so":
        return _cham_so(tra_loi, dap_an, float((cham or {}).get("sai_so", 0) or 0))
    if kieu == "khop":
        return _cham_khop(tra_loi, dap_an)
    if kieu == "chua":
        return _cham_chua(tra_loi, dap_an)
    if kieu == "regex":
        return _cham_regex(tra_loi, dap_an)
    if kieu == "tu_choi":
        return _cham_tu_choi(tra_loi, (cham or {}).get("tu_khoa"))
    return False, f"kiểu chấm không biết: {kieu!r}"


def cham_tool(tool_da_goi, cham: dict, case: dict) -> tuple:
    """(dat, ly_do) cho ràng buộc TOOL: phai_dung_tool (phải gọi) + cam_tool (không được gọi)."""
    da = set(tool_da_goi or [])
    phai = case.get("phai_dung_tool") or []
    cam = case.get("cam_tool") or []
    thieu = [t for t in phai if t not in da]
    if thieu:
        return False, f"không gọi tool bắt buộc: {thieu}"
    pham = [t for t in cam if t in da]
    if pham:
        return False, f"gọi tool bị cấm: {pham}"
    return True, ""


# ─────────────────────────── chấm một câu ───────────────────────────

def cham_mot(case: dict, ket_qua: dict, dap_an) -> dict:
    """Chấm một câu. ket_qua = {tra_loi, tool_da_goi, loi}. dap_an = đáp án đã giải sẵn."""
    cid = case.get("id", "?")
    if ket_qua.get("loi"):
        return {"id": cid, "nhom": case.get("nhom", "chung"), "dat": False,
                "ly_do": "lỗi khi chạy: " + str(ket_qua["loi"])[:200], "loi_chay": True}
    tra_loi = str(ket_qua.get("tra_loi") or "")
    cham = case.get("cham") or {}
    dat_nd, ly_nd = cham_noi_dung(tra_loi, cham, dap_an)
    dat_tool, ly_tool = cham_tool(ket_qua.get("tool_da_goi"), cham, case)
    dat = dat_nd and dat_tool
    ly = ly_nd if not dat_nd else (ly_tool if not dat_tool else ly_nd)
    return {"id": cid, "nhom": case.get("nhom", "chung"), "dat": dat, "ly_do": ly, "loi_chay": False}


# ─────────────────────────── chạy cả bộ ───────────────────────────

async def _giai_dap_an(case: dict, resolver: Optional[Resolver]):
    """Giải đáp án: ưu tiên su_that (gọi tool đọc dữ liệu), nếu không có thì lấy cham.dap_an tĩnh."""
    st = case.get("su_that")
    if st and resolver is not None:
        return await resolver(st)
    return (case.get("cham") or {}).get("dap_an")


async def chay(cases: list, invoker: Invoker, resolver: Optional[Resolver] = None) -> dict:
    """Chạy cả bộ câu hỏi qua một 'não' (invoker). Trả BẢNG ĐIỂM."""
    chi_tiet = []
    for case in cases:
        try:
            dap_an = await _giai_dap_an(case, resolver)
        except Exception as e:      # resolver gọi tool hỏng: câu này không chấm được, không tính sai cho não
            chi_tiet.append({"id": case.get("id", "?"), "nhom": case.get("nhom", "chung"),
                             "dat": False, "ly_do": f"không giải được đáp án (su_that): {type(e).__name__}: {e}",
                             "loi_chay": True})
            continue
        try:
            kq = await invoker(case)
        except Exception as e:
            kq = {"tra_loi": "", "tool_da_goi": [], "loi": f"{type(e).__name__}: {e}"}
        chi_tiet.append(cham_mot(case, kq if isinstance(kq, dict) else {}, dap_an))
    return tong_hop(chi_tiet)


def tong_hop(chi_tiet: list) -> dict:
    """Bảng điểm: tổng, theo nhóm, danh sách câu trượt."""
    tong = len(chi_tiet)
    dat = sum(1 for c in chi_tiet if c["dat"])
    nhom: dict = {}
    for c in chi_tiet:
        g = nhom.setdefault(c["nhom"], {"tong": 0, "dat": 0})
        g["tong"] += 1
        g["dat"] += 1 if c["dat"] else 0
    return {
        "tong": tong, "dat": dat, "truot": tong - dat,
        "ty_le": round(dat / tong, 4) if tong else 0.0,
        "theo_nhom": {g: {**v, "ty_le": round(v["dat"] / v["tong"], 4) if v["tong"] else 0.0}
                      for g, v in sorted(nhom.items())},
        "cau_truot": [{"id": c["id"], "nhom": c["nhom"], "ly_do": c["ly_do"],
                       "loi_chay": c.get("loi_chay", False)} for c in chi_tiet if not c["dat"]],
        "chi_tiet": chi_tiet,
    }


def toan_bo_loi_chay(bang_diem: dict) -> str:
    """Cả bộ KHÔNG CHẤM ĐƯỢC (mọi câu đều lỗi khi chạy: hết key, 401, không nối được não)?

    Trả về lý do của câu đầu (chuỗi rỗng = có ít nhất một câu chạy tới nơi). Một lượt như
    thế không nói gì về chất lượng não, nên KHÔNG được lưu làm bản nền: lưu 0/7 toàn lỗi
    làm bản nền thì lần sau não nào cũng "không tụt", và hồi quy thật bị che mất."""
    ct = bang_diem.get("chi_tiet") or []
    if not ct or not all(c.get("loi_chay") for c in ct):
        return ""
    return str(ct[0].get("ly_do") or "lỗi khi chạy")


# ─────────────────────────── bản nền + hồi quy ───────────────────────────

def luu_goc(bang_diem: dict, path) -> None:
    """Lưu bản nền: chỉ cần id -> đạt/không, đủ để so hồi quy. Không lưu ly_do (đổi theo lần chạy)."""
    goc = {c["id"]: bool(c["dat"]) for c in bang_diem.get("chi_tiet", [])}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ty_le": bang_diem.get("ty_le"), "ket_qua": goc},
                            ensure_ascii=False, indent=1), encoding="utf-8")


def doc_goc(path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("ket_qua", {})
    except Exception:
        return {}


def so_voi_goc(bang_diem: dict, goc: dict) -> dict:
    """So bảng điểm mới với bản nền. HỒI QUY = câu trước ĐẠT mà giờ TRƯỢT (nghiêm trọng nhất)."""
    moi = {c["id"]: bool(c["dat"]) for c in bang_diem.get("chi_tiet", [])}
    hoi_quy = sorted(i for i, d in moi.items() if goc.get(i) is True and not d)
    tien_bo = sorted(i for i, d in moi.items() if goc.get(i) is False and d)
    moi_them = sorted(i for i in moi if i not in goc)
    return {"hoi_quy": hoi_quy, "tien_bo": tien_bo, "cau_moi": moi_them, "co_hoi_quy": bool(hoi_quy)}


def lay_theo_duong(obj, duong: str):
    """Lấy giá trị theo đường dẫn chấm, chỉ số là số (vd 'doanh_nghiep.0.mua_vao.so_hd').
    Dùng để rút 'sự thật' ra khỏi JSON mà tool đọc dữ liệu trả về."""
    cur = obj
    for buoc in str(duong or "").split("."):
        if buoc == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(buoc)]
        elif isinstance(cur, dict):
            cur = cur[buoc]
        else:
            raise KeyError(f"không đi tiếp được tại '{buoc}'")
    return cur


# ─────────────────────────── nạp bộ đề ───────────────────────────

def doc_bo(path) -> list:
    """Nạp bộ câu hỏi từ file JSON. Kiểm hình dạng tối thiểu để lỗi đề lộ ngay, không âm thầm."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise ValueError("Bộ đề phải là danh sách câu hỏi (hoặc {cases: [...]}).")
    ids = set()
    for i, c in enumerate(cases):
        if not isinstance(c, dict) or not c.get("id") or not c.get("cau_hoi"):
            raise ValueError(f"Câu #{i} thiếu id hoặc cau_hoi.")
        if c["id"] in ids:
            raise ValueError(f"Trùng id: {c['id']}")
        ids.add(c["id"])
        kieu = (c.get("cham") or {}).get("kieu")
        if kieu not in KIEU_CHAM:
            raise ValueError(f"Câu {c['id']}: kiểu chấm không hợp lệ: {kieu!r}")
        if kieu != "tu_choi" and not c.get("su_that") and "dap_an" not in (c.get("cham") or {}):
            raise ValueError(f"Câu {c['id']}: cần 'su_that' hoặc cham.dap_an.")
    return cases
