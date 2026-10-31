"""Nhặt thông tin từ tin khách và gắn cờ tin gấp (26.10.167+, học Zalo.Net).

Chạy trong `conversations.ghi_su_kien` cho tin do KHÁCH gửi: số điện thoại, số tài khoản
ngân hàng, link được ghi vào `metadata.trich` của chính tin đó (không thêm bảng), và tin có
dấu hiệu gấp / khiếu nại ở chat riêng thì báo chuông một lần mỗi khách trong một khoảng.

Mẫu cố ý hẹp: thà sót còn hơn nhặt rác. Khác Zalo.Net, chữ "sáng", "tối" KHÔNG bị coi là lời hẹn.
"""
from __future__ import annotations

import re
import sys
import time
from typing import Dict

_SDT = re.compile(r"(?<![\d.])(?:\+?84|0)(?:3|5|7|8|9)\d{8}(?!\d)")
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_CHU_TK = r"(?:stk|s\.t\.k|số tài khoản|so tai khoan|tài khoản|tai khoan|tk|account|bank|ngân hàng|ngan hang)"
_TK = re.compile(r"(?i)\b" + _CHU_TK + r"\b[^\d\n]{0,40}?(\d(?:[ .]?\d){5,17})(?!\d)")
_NH = re.compile(r"(?i)\b(vcb|vietcombank|mb|mbbank|tcb|techcombank|vpb|vpbank|tpb|tpbank|bidv|"
                 r"agribank|acb|sacombank|vib|shb|hdbank|ocb|msb|momo)\b")
_GAP = re.compile(r"(?i)(?<!\w)(gấp|khẩn cấp|khẩn|khiếu nại|khieu nai|hỗ trợ ngay|sos|lừa đảo|lua dao|"
                  r"báo công an|bao cong an|đòi tiền|hoàn tiền ngay|trả lại tiền)(?!\w)")
_BAO_NGHI = 1800            # giây: một khách chat riêng báo chuông nhiều nhất một lần mỗi chừng này
_DA_BAO: Dict[tuple, float] = {}


def phan_tich(text: str) -> dict:
    """{"sdt": [...], "tk": [{"so","nh"}], "link": [...], "gap": [...]}; khoá rỗng thì bỏ."""
    t = str(text or "")
    if not t.strip():
        return {}
    out: dict = {}
    sdt = list(dict.fromkeys(_SDT.findall(t)))
    if sdt:
        out["sdt"] = sdt[:5]
    tk = []
    for m in _TK.finditer(t):
        so = re.sub(r"[ .]", "", m.group(1))
        if so in sdt or len(so) < 6:
            continue
        gan = t[max(0, m.start() - 30): m.end() + 30]
        nh = _NH.search(gan)
        tk.append({"so": so, "nh": nh.group(1).upper() if nh else ""})
    if tk:
        seen, uniq = set(), []
        for x in tk:
            if x["so"] not in seen:
                seen.add(x["so"])
                uniq.append(x)
        out["tk"] = uniq[:3]
    link = [u.rstrip(".,;)") for u in _URL.findall(t)]
    if link:
        out["link"] = list(dict.fromkeys(link))[:5]
    gap = list(dict.fromkeys(g.lower() for g in _GAP.findall(t)))
    if gap:
        out["gap"] = gap[:5]
    return out


def gan_vao_tin(e: dict) -> dict:
    """Thêm `metadata.trich` vào sự kiện chuẩn (đã qua chuan_hoa) nếu là tin chữ của khách."""
    if e.get("sender_type") != "customer" or e.get("message_type") not in ("text", "image", "file", "other"):
        return {}
    tr = phan_tich(e.get("text") or "")
    if tr:
        meta = e.get("metadata")
        if isinstance(meta, dict):
            meta["trich"] = tr
    return tr


def bao_gap(e: dict, tr: dict, conv_id: int, now: float = None) -> bool:
    """Tin gấp ở chat riêng: báo chuông. Trả True nếu đã báo."""
    if not tr.get("gap") or e.get("chat_type") != "private" or e.get("sender_type") != "customer":
        return False
    now = now or time.time()
    khoa = (int(conv_id),)
    if now - _DA_BAO.get(khoa, 0) < _BAO_NGHI:
        return False
    if len(_DA_BAO) > 500:
        _DA_BAO.clear()
    _DA_BAO[khoa] = now
    try:
        import inbox
        ten = str(e.get("sender_name") or e.get("chat_title") or "Một khách")
        inbox.add(f"{ten} vừa nhắn có vẻ gấp ({', '.join(tr['gap'])}):\n\n\"{str(e.get('text') or '')[:400]}\"\n\n"
                  f"Mở Hộp thư hội thoại để xem và trả lời.",
                  kind="system", title=f"Tin gấp từ {ten}", source="trich-tin", tu_phan_loai=True,
                  channel=str(e.get("channel") or ""))
        return True
    except Exception as ex:
        print(f"[trich-tin] báo tin gấp lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
        return False
