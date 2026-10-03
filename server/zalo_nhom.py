"""Việc riêng của bot trong NHÓM Zalo: nhận ra bị gọi tên, tag người đúng ID, ảnh có caption.

Thuần hàm, không đụng mạng/đĩa, để test được từng luật:

  - `co_goi_ten`: tin trong nhóm có nhắc bot không. Zalo không cho biết "tin này tag ai" theo
    cách chắc chắn cho tài khoản cá nhân, nên đối chiếu theo TÊN: các đoạn @tag trong tin
    (theo vị trí `mentions`) và cả chữ "@Tên" gõ tay, so với tên của bot / tên tài khoản.
  - `gan_tag`: câu trả lời của bot trong nhóm được gắn tag NGƯỜI VỪA HỎI ở đầu câu, và mọi
    "@Tên" khác trong câu được đổi thành tag thật nếu tên đó khớp ĐÚNG MỘT thành viên đã nói
    trong nhóm. Tên khớp nhiều người thì để nguyên chữ, không đoán: tag nhầm người trong nhóm
    đông là lỗi khách nhìn thấy ngay.
  - `la_chu_thich`: ảnh/file chỉ tính là tin để bot trả lời khi có chữ thật đi kèm.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple


def chuan(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def la_chu_thich(loai: str, text: str, nhan_kenh: str = "") -> bool:
    """Tin có chữ thật để trả lời không. Tin chữ: có chữ là đủ. Ảnh/file/tiếng: chỉ khi chữ
    đó KHÔNG phải câu giữ chỗ do kênh tự chèn khi tin không kèm lời."""
    t = str(text or "").strip()
    if not t:
        return False
    if loai == "text":
        return True
    return not (t.startswith("[") and "khách gửi" in t)


def _doan_tag(text: str, mentions) -> List[str]:
    out = []
    for m in (mentions or []):
        if not isinstance(m, dict):
            continue
        try:
            pos, ln = int(m.get("pos")), int(m.get("len"))
        except (TypeError, ValueError):
            continue
        if 0 <= pos < len(text) and ln > 0:
            out.append(text[pos:pos + ln])
    return out


def co_goi_ten(text: str, mentions, ten_bot: List[str]) -> bool:
    """`ten_bot`: các tên bot có thể bị gọi (tên bot, tên tài khoản Zalo...)."""
    ten = [chuan(x) for x in (ten_bot or []) if chuan(x)]
    if not ten:
        return False
    for d in _doan_tag(text, mentions):
        c = chuan(d)
        if c and any(c == t or c.endswith(t) or t.endswith(c) for t in ten):
            return True
    for m in re.finditer(r"@([^\n@,.!?;:]{1,40})", str(text or "")):
        c = chuan(m.group(1))
        if not c:
            continue
        if any(c == t or c.startswith(t + " ") or t.startswith(c + " ") for t in ten):
            return True
    return False


def thanh_vien(tin: List[dict]) -> Dict[str, str]:
    """Từ các tin gần đây: {sender_id: tên}, chỉ khách có ID."""
    out: Dict[str, str] = {}
    for m in tin or []:
        sid, ten = str(m.get("sender_id") or ""), str(m.get("sender_name") or "").strip()
        if m.get("sender_type") == "customer" and sid and ten:
            out[sid] = ten
    return out


def _tim_nguoi(ten_go: str, tv: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """Tên gõ sau @ -> (id, tên đầy đủ) nếu khớp đúng MỘT người; mơ hồ thì None."""
    c = chuan(ten_go)
    if not c:
        return None
    chinh = [(i, n) for i, n in tv.items() if chuan(n) == c]
    if len(chinh) == 1:
        return chinh[0]
    if chinh:
        return None
    gan = [(i, n) for i, n in tv.items() if chuan(n).startswith(c + " ")]
    return gan[0] if len(gan) == 1 else None


def gan_tag(cau: str, nguoi_hoi_id: str, nguoi_hoi_ten: str,
            tv: Dict[str, str]) -> Tuple[str, List[str]]:
    """(câu mới, danh sách spec "pos:uid:len" cho `zalo-agent msg send --mention`)."""
    cau = str(cau or "")
    specs: List[str] = []
    # 1. @Tên đã có trong câu: đổi thành tag thật nếu khớp đúng một người. Thử cụm dài nhất
    # trước (tối đa 4 chữ) để "@Lan Anh" không bị hiểu thành "@Lan".
    for m in re.finditer(r"@", cau):
        sau = re.findall(r"[^\s@,.!?;:]+", cau[m.end():m.end() + 60])
        for k in range(min(4, len(sau)), 0, -1):
            cum = " ".join(sau[:k])
            kq = _tim_nguoi(cum, tv)
            if kq:
                dai = 1 + len(re.match(r"\s*".join(map(re.escape, sau[:k])), cau[m.end():]).group(0))
                specs.append(f"{m.start()}:{kq[0]}:{dai}")
                break
    # 2. Chưa tag ai thì tag người vừa hỏi ở đầu câu.
    if not specs and nguoi_hoi_id and nguoi_hoi_ten:
        dau = f"@{nguoi_hoi_ten.strip()}"
        cau = f"{dau} {cau}"
        specs = [f"0:{nguoi_hoi_id}:{len(dau)}"]
    return cau, specs[:5]
