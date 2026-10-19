"""26.10.176: kiểm báo cáo kinh doanh bằng LUẬT, không cần model.

Hai lỗi thật đã gặp ở báo cáo quý 3 (19/10/2026):
  1. Báo cáo tháng có lãi tạm tính, báo cáo quý lại từ chối vì "thiếu giá vốn".
  2. Tổng các nhóm 319,52 triệu nhưng dòng tổng ghi 319,88 triệu, không ai giải thích.

Module này bắt cả hai trên văn bản câu trả lời. Dùng được ở bộ chấm điểm (kiểu "bao_cao" trong
danh_gia.py) và ở test. Không gọi mạng, không đọc file.

    kiem_bao_cao(tra_loi, can_lai=True) -> [chuỗi lỗi]
"""
import re
import unicodedata

# Hàng/cột KHÔNG cộng được: tỷ lệ, bình quân, đơn giá. Cộng ra số vô nghĩa nên bỏ qua.
_NHAN_KHONG_CONG = re.compile(
    r"%|tỷ lệ|ty le|\bcpo\b|\broas\b|\bcpm\b|\bctr\b|\bcpc\b|trung bình|trung binh|bình quân|"
    r"binh quan|/\s*đơn|/\s*don|/\s*ngày|/\s*ngay|\bvs\b|so với|so voi|tăng|giảm|chênh|"
    r"thay đổi|thay doi", re.I)
_TIEU_DE_TONG = re.compile(r"^\s*(tổng|tong|cộng|cong|cả kỳ|ca ky|q[1-4]|quý\s*[1-4]|quy\s*[1-4]|"
                           r"cả năm|ca nam)\b", re.I)
_DONG_TONG = re.compile(r"^\s*\**\s*(tổng|tong|cộng|cong)\b", re.I)

_RE_LAI = re.compile(r"\b(lãi|lời|lợi nhuận|loi nhuan|lai)\b", re.I)
_RE_UOC = re.compile(r"tạm tính|tam tinh|ước tính|uoc tinh|ước lượng|uoc luong|giả định|gia dinh", re.I)
_RE_TU_CHOI_LAI = re.compile(
    r"(không|chưa|khong|chua)\s+(thể\s+|the\s+|có\s+|co\s+)?(tính|tinh|biết|biet|đủ|du)[^.\n]{0,60}"
    r"(lãi|lời|lợi nhuận|lai|loi nhuan)|"
    r"(lãi|lời|lợi nhuận|lai|loi nhuan)[^.\n]{0,60}(không|chưa|khong|chua)\s+(thể|the|tính|tinh)"
    r"[^.\n]{0,40}(được|duoc)?|"
    r"(thiếu|thieu|chưa có|chua co|không có|khong co)[^.\n]{0,20}giá vốn", re.I)
# Có ghi tỷ lệ hoặc mức giá vốn giả định: "giá vốn ước tính 45%", "giá vốn 80k/sét".
_RE_GIA_VON = re.compile(r"giá vốn|gia von|vốn hàng|von hang|\bcogs\b", re.I)


def doc_so_vn(s: str):
    """'6.457,5' -> 6457.5 ; '20.294' -> 20294 ; '12,64%' -> 12.64 ; không phải số -> None."""
    t = re.sub(r"[^\d.,\-]", "", str(s or ""))
    t = t.strip(".,")
    if not t or not re.search(r"\d", t):
        return None
    if "." in t and "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _so_le(s: str) -> int:
    m = re.search(r"[.,](\d+)\s*$", re.sub(r"[^\d.,]", "", str(s or "")).strip(".,"))
    if not m:
        return 0
    # '20.294' là nghìn, không phải 3 số lẻ.
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", re.sub(r"[^\d.]", "", str(s or ""))):
        return 0
    return len(m.group(1))


def _bang(text: str) -> list:
    """Tách mọi bảng markdown trong văn bản: mỗi bảng = {'dau': [...], 'dong': [[...], ...]}."""
    bang, hien = [], []
    for dong in (text or "").splitlines() + [""]:
        d = dong.strip()
        if d.startswith("|") and d.count("|") >= 2:
            hien.append([c.strip() for c in d.strip("|").split("|")])
        else:
            if len(hien) >= 3:
                dau, rest = hien[0], hien[1:]
                if rest and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) or c == "" for c in rest[0]):
                    rest = rest[1:]
                bang.append({"dau": dau, "dong": rest})
            hien = []
    return bang


def _dung_sai(tong: float, phan: list, chu: list) -> float:
    """Chỉ cho phép sai số LÀM TRÒN: mỗi số hiển thị lệch tối đa nửa đơn vị chữ số cuối của nó.
    Cố ý chặt: chênh 0,36 trên 319,5 (0,1%) là lỗi thật đã gặp, một ngưỡng phần trăm sẽ nuốt mất."""
    le = min([_so_le(c) for c in chu] or [0])
    return 0.5 * (10 ** -le) * (len(phan) + 1) + 1e-9


def kiem_tong_bang(text: str) -> list:
    """Bảng có cột 'Tổng/Q3/Cộng' hoặc dòng 'Tổng' thì phần phải cộng ra tổng (sai số làm tròn)."""
    loi = []
    for b in _bang(text):
        dau, dong = b["dau"], b["dong"]
        # (a) cột tổng: cộng các cột đứng trước nó trên mỗi dòng cộng được.
        ct = next((i for i, c in enumerate(dau) if i > 1 and _TIEU_DE_TONG.search(c)), None)
        if ct is not None:
            for r in dong:
                if len(r) <= ct or _NHAN_KHONG_CONG.search(r[0]) or "%" in "".join(r[1:ct + 1]):
                    continue
                phan_raw = r[1:ct]
                phan = [doc_so_vn(c) for c in phan_raw]
                tong = doc_so_vn(r[ct])
                if tong is None or len(phan) < 2 or any(p is None for p in phan):
                    continue
                if abs(sum(phan) - tong) > _dung_sai(tong, phan, phan_raw + [r[ct]]):
                    loi.append(f"dòng '{r[0]}': các phần cộng ra {round(sum(phan), 3)} nhưng cột "
                               f"'{dau[ct]}' ghi {r[ct]}")
        # (b) dòng tổng: cộng các dòng phía trên trong mỗi cột.
        for k, r in enumerate(dong):
            if not _DONG_TONG.search(r[0] if r else ""):
                continue
            for j in range(1, len(r)):
                if j < len(dau) and _NHAN_KHONG_CONG.search(dau[j]):
                    continue
                phan_raw = [x[j] for x in dong[:k] if len(x) > j]
                phan = [doc_so_vn(c) for c in phan_raw]
                tong = doc_so_vn(r[j])
                if tong is None or len(phan) < 2 or any(p is None for p in phan) or "%" in r[j]:
                    continue
                if abs(sum(phan) - tong) > _dung_sai(tong, phan, phan_raw + [r[j]]):
                    nhan = dau[j] if j < len(dau) else f"cột {j}"
                    loi.append(f"cột '{nhan}': các dòng trên cộng ra {round(sum(phan), 3)} nhưng dòng "
                               f"'{r[0]}' ghi {r[j]}")
    return loi


def kiem_lai(text: str) -> list:
    """Báo cáo kỳ (tháng, quý, năm) phải có lãi TẠM TÍNH và nói rõ giả định giá vốn."""
    t = text or ""
    loi = []
    co_so_lai = re.search(r"(lãi|lời|lợi nhuận)[^.\n]{0,60}\d[\d.,]*\s*(tỷ|ty|triệu|trieu|tr\b|k\b|đ|đồng|%)", t, re.I)
    if _RE_TU_CHOI_LAI.search(t) and not co_so_lai:
        loi.append("từ chối tính lãi vì thiếu giá vốn: phải ra lãi tạm tính theo tỷ lệ ước tính")
        return loi
    if not _RE_LAI.search(t):
        loi.append("báo cáo kỳ không có phần lãi")
        return loi
    if not _RE_UOC.search(t):
        loi.append("có lãi nhưng không nói đó là tạm tính hoặc ước tính")
    if not _RE_GIA_VON.search(t):
        loi.append("không nói giả định giá vốn (tỷ lệ hoặc giá vốn dùng để tính lãi)")
    return loi


def kiem_bao_cao(tra_loi: str, can_lai: bool = True) -> list:
    """Danh sách lỗi của báo cáo; rỗng là đạt."""
    loi = list(kiem_tong_bang(tra_loi))
    if can_lai:
        loi += kiem_lai(tra_loi)
    return loi
