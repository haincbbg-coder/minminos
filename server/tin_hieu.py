"""Tín hiệu dùng (26.10.69): ghi lại NGƯỜI DÙNG ĐANG DÙNG MINMIN RA SAO, để sau này MinMin hiểu thói quen.

Chỉ GHI NHẬN, chưa đổi hành vi nào của agent (tránh bẫy Goodhart: chưa nên tối ưu theo con số
khi chưa biết con số nào phản ánh đúng ích lợi thật). Hiện duy nhất một chỗ dùng tới: ngăn kéo
điều hướng đưa vài trang bố hay mở lên đầu ("Hay dùng").

Quyền riêng tư: CHỈ lưu loại tín hiệu + tên trang/nút + giờ. KHÔNG lưu nội dung tin nhắn, tên
file hay bất cứ chữ nào bố gõ. Danh sách loại tín hiệu là whitelist; ngoài danh sách thì bỏ.

Tệp: JAVIS_STATE_DIR/tin-hieu.jsonl, mỗi dòng một tín hiệu, tự cắt còn ~MAX_DONG dòng mới nhất.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter
from pathlib import Path

import config

# loại -> mô tả. Thêm loại mới là thêm ở ĐÂY (và thêm test), không nhận chuỗi tuỳ ý từ client.
LOAI = {
    "mo_trang": "mở một trang trong điều hướng (đối tượng = id trang)",
    "mo_menu": "bấm nút Menu để gọi thanh điều hướng",
    "gui_chat": "gửi một tin trong chat (KHÔNG kèm nội dung)",
    "doi_che_do": "đổi giữa chế độ gọn và đầy đủ (đối tượng = gon | day_du)",
}
MAX_DONG = 5000
_DOI_TUONG_OK = re.compile(r"^[a-z0-9_.\-]{1,48}$")
_KHOA = threading.Lock()


def _duong_dan() -> Path:
    return config.STATE_DIR / "tin-hieu.jsonl"


def ghi(loai: str, doi_tuong: str = "") -> bool:
    """Ghi một tín hiệu. Trả False nếu bị từ chối (loại lạ / đối tượng không sạch)."""
    loai = str(loai or "")
    if loai not in LOAI:
        return False
    doi_tuong = str(doi_tuong or "")
    if doi_tuong and not _DOI_TUONG_OK.match(doi_tuong):
        return False
    dong = json.dumps({"t": int(time.time()), "loai": loai, "dt": doi_tuong}, ensure_ascii=False)
    p = _duong_dan()
    with _KHOA:
        try:
            with p.open("a", encoding="utf-8") as f:
                f.write(dong + "\n")
            if p.stat().st_size > MAX_DONG * 80:
                dong_cu = p.read_text(encoding="utf-8").splitlines()[-MAX_DONG:]
                p.write_text("\n".join(dong_cu) + "\n", encoding="utf-8")
        except OSError:
            return False
    return True


def _doc(n_ngay: int):
    moc = time.time() - n_ngay * 86400
    try:
        dong = _duong_dan().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for d in dong:
        try:
            x = json.loads(d)
        except ValueError:
            continue
        if isinstance(x, dict) and x.get("loai") in LOAI and x.get("t", 0) >= moc:
            out.append(x)
    return out


def tom_tat(n_ngay: int = 30, top: int = 4) -> dict:
    """Tóm tắt: trang hay mở nhất, số lần gửi chat."""
    xs = _doc(max(1, min(int(n_ngay), 365)))
    trang = Counter(x["dt"] for x in xs if x["loai"] == "mo_trang" and x.get("dt"))
    return {
        "hay_dung": [{"id": k, "so_lan": v} for k, v in trang.most_common(max(1, min(int(top), 12)))],
        "so_tin_chat": sum(1 for x in xs if x["loai"] == "gui_chat"),
        "tong_tin_hieu": len(xs),
    }
