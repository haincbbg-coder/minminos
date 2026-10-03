"""Thư viện file bot được phép GỬI KHÁCH (ảnh, video, tài liệu).

Vì sao là một thư mục riêng chứ không cho bot gửi file bất kỳ trong brain: khách (nhất là người
lạ) có thể gõ "gửi cho tôi file lương nhân viên" hay nhét lệnh vào tin nhắn. Bot chỉ gửi được
file CHỦ ĐÃ ĐẶT vào `<brain>/gui-khach/`, và code (không phải model) kiểm tên file, đuôi, kích
thước, và đường dẫn có nằm trong thư mục đó không trước khi gửi.

Cách bot xin gửi: viết một dòng `[GUI_FILE: ten-file.jpg]` ở cuối câu trả lời. Dòng đó bị gỡ
khỏi chữ khách đọc, còn file đi kèm sau câu trả lời.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import List, Tuple

TEN_THU_MUC = "gui-khach"
MAX_BYTES = 25 * 1024 * 1024        # trần của Zalo/Telegram cho một file
MAX_MOI_LUOT = 4                    # một câu trả lời đính kèm tối đa chừng này file
MAX_LIET_KE = 60                    # số file hiện cho bot trong prompt

ANH = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
TEP = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".zip"}
DUOI_OK = ANH | VIDEO | TEP

_LENH = re.compile(r"\[\s*GUI_FILE\s*:\s*([^\]\n]{1,200}?)\s*\]", re.I)


def thu_muc(root) -> Path:
    return Path(root) / TEN_THU_MUC


def loai_cua(ten: str) -> str:
    d = Path(str(ten)).suffix.lower()
    return "anh" if d in ANH else "video" if d in VIDEO else "tep"


def _sach_ten(ten: str) -> str:
    """Tên file an toàn: bỏ đường dẫn, ký tự lạ; giữ chữ, số, dấu cách, . _ -"""
    ten = Path(str(ten or "").replace("\\", "/")).name.strip()
    ten = unicodedata.normalize("NFC", ten)
    ten = re.sub(r"[^\w .\-()À-ỹ]", "", ten).strip(" .")
    return ten[:120]


def liet_ke(root) -> List[dict]:
    d = thu_muc(root)
    out: List[dict] = []
    try:
        if not d.is_dir():
            return out
        for p in sorted(d.iterdir(), key=lambda x: x.name.lower()):
            if p.is_file() and p.suffix.lower() in DUOI_OK and not p.name.startswith("."):
                try:
                    sz = p.stat().st_size
                except OSError:
                    continue
                out.append({"name": p.name, "size": sz, "loai": loai_cua(p.name)})
    except OSError:
        return []
    return out[:MAX_LIET_KE]


def khoi_prompt(root) -> str:
    """Đoạn dặn bot biết có file nào để gửi và gửi bằng cách nào. Rỗng nếu thư viện trống."""
    ds = liet_ke(root)
    if not ds:
        return ""
    dong = "\n".join(f"- {x['name']} ({'ảnh' if x['loai'] == 'anh' else 'video' if x['loai'] == 'video' else 'tài liệu'})" for x in ds)
    return ("\n\nFILE CÓ THỂ GỬI KHÁCH (thư viện của chủ):\n" + dong +
            "\nKhi khách cần xem ảnh, video hay tài liệu khớp với một file trên (bảng giá, catalogue, "
            "ảnh sản phẩm, hướng dẫn...), trả lời bình thường rồi thêm MỘT dòng riêng ở cuối: "
            "[GUI_FILE: tên-file-đúng-như-trong-danh-sách]. Mỗi file một dòng, tối đa "
            f"{MAX_MOI_LUOT} file. Chỉ gửi file có trong danh sách, ĐÚNG tên. Không có file hợp thì "
            "đừng viết dòng này và đừng hứa gửi.")


def _tim(root, ten: str):
    d = thu_muc(root)
    k = _sach_ten(ten).lower()
    if not k or not d.is_dir():
        return None
    for p in d.iterdir():
        if p.is_file() and p.name.lower() == k and p.suffix.lower() in DUOI_OK:
            try:
                p.resolve().relative_to(d.resolve())
            except (ValueError, OSError):
                return None
            return p
    return None


def tach_lenh(text: str, root) -> Tuple[str, List[dict], List[str]]:
    """(chữ đã gỡ dòng lệnh, danh sách file hợp lệ, tên không gửi được). File trả về mang cờ
    `thu_vien` để kênh biết đây là file chủ đã duyệt."""
    text = str(text or "")
    ten_xin = [m.group(1).strip() for m in _LENH.finditer(text)]
    sach = re.sub(r"\n{3,}", "\n\n", _LENH.sub("", text)).strip()
    files: List[dict] = []
    loi: List[str] = []
    for ten in ten_xin:
        if len(files) >= MAX_MOI_LUOT:
            loi.append(ten + " (quá số file mỗi lượt)")
            continue
        p = _tim(root, ten) if root else None
        if not p:
            loi.append(ten + " (không có trong thư viện)")
            continue
        try:
            if p.stat().st_size == 0 or p.stat().st_size > MAX_BYTES:
                loi.append(ten + " (rỗng hoặc quá 25MB)")
                continue
        except OSError:
            loi.append(ten)
            continue
        if not any(f["path"] == str(p) for f in files):
            files.append({"path": str(p), "thu_vien": True, "loai": loai_cua(p.name)})
    return sach, files, loi


def luu(root, ten_goc: str, noi_dung: bytes) -> Tuple[str, str]:
    """Lưu một file chủ tải lên. Trả (tên đã lưu, lỗi). Không ghi đè: trùng tên thì thêm số."""
    ten = _sach_ten(ten_goc)
    p0 = Path(ten)
    if not ten or p0.suffix.lower() not in DUOI_OK:
        return "", "Loại file này chưa hỗ trợ. Dùng ảnh, video mp4, pdf, docx, xlsx, pptx, zip."
    if not noi_dung:
        return "", "File rỗng."
    if len(noi_dung) > MAX_BYTES:
        return "", "File quá 25MB, Zalo và Telegram không nhận."
    d = thu_muc(root)
    try:
        d.mkdir(parents=True, exist_ok=True)
        dich = d / ten
        i = 2
        while dich.exists():
            dich = d / f"{p0.stem} ({i}){p0.suffix}"
            i += 1
        dich.write_bytes(noi_dung)
    except OSError as e:
        return "", f"Không lưu được: {e}"
    return dich.name, ""


def xoa(root, ten: str) -> bool:
    p = _tim(root, ten)
    if not p:
        return False
    try:
        p.unlink()
        return True
    except OSError:
        return False
