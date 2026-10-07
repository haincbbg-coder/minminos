"""ke_hang.py - KỆ HÀNG CÔNG KHAI của một máy chủ MinMin (26.10.103).

Link chia sẻ là gửi TỪNG người. Kệ hàng là bày sẵn: chủ máy chọn những agent, skill, workflow
muốn cho người khác lấy, và ai gõ tên miền của máy này vào Chợ chia sẻ (hoặc mở /bs/ke) là thấy
cả kệ, xem trước và nhận về như nhận một link.

Ranh giới an toàn:
  - Kệ TẮT mặc định. Tắt kệ là /bs/ke và mọi món trên kệ trả 404 ngay, không cần gỡ từng món.
  - CHỈ món chủ chủ động đưa lên. Không có chế độ "đưa cả brain lên kệ".
  - Gói của món trên kệ dựng bằng đúng bộ dựng của link chia sẻ (share_bundle), nên bộ nhớ, wiki,
    ghi chú, khoá API không bao giờ vào được; skill hệ thống tự bị loại.
  - Mỗi món có một mã ngẫu nhiên bền (`id`) làm luôn kênh theo dõi bản mới: người đã nhận hỏi
    /bs/td/<id> như với link, gỡ món khỏi kệ là kênh đó chết.

Kho: `<STATE_DIR>/ke-hang.json`, đọc/ghi nguyên khối, có trần số món.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

try:
    from config import STATE_DIR
except Exception:
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

_LOCK = threading.RLock()
TRAN_MON = 200
KINDS = ("agent", "skill", "workflow")
_ID_RE = re.compile(r"[A-Za-z0-9_-]{16,80}")
_SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def _file() -> Path:
    return Path(STATE_DIR) / "ke-hang.json"


def _doc() -> dict:
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("bat", False)
    d.setdefault("ten_ke", "")
    d.setdefault("gioi_thieu", "")
    if not isinstance(d.get("mon"), list):
        d["mon"] = []
    return d


def _ghi(d: dict) -> None:
    p = _file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _gon(s, n) -> str:
    return " ".join(str(s or "").split())[:n]


def doc() -> dict:
    """Toàn bộ kệ (cho chủ máy, trang quản lý)."""
    return _doc()


def cai_dat(bat=None, ten_ke=None, gioi_thieu=None) -> dict:
    with _LOCK:
        d = _doc()
        if bat is not None:
            d["bat"] = bool(bat)
        if ten_ke is not None:
            d["ten_ke"] = _gon(ten_ke, 80)
        if gioi_thieu is not None:
            d["gioi_thieu"] = _gon(gioi_thieu, 400)
        _ghi(d)
        return d


def them_mon(brain: str, typ: str, slug: str, mo_ta: str = "") -> dict:
    """Đưa một món lên kệ. Đã có (cùng brain + loại + slug) thì trả lại món cũ, giữ nguyên id để
    người đã nhận vẫn theo dõi được."""
    if typ not in KINDS or not _SLUG_RE.fullmatch(str(slug or "")) or ".." in str(slug):
        raise ValueError("Món không hợp lệ")
    with _LOCK:
        d = _doc()
        for m in d["mon"]:
            if m.get("brain") == str(brain) and m.get("type") == typ and m.get("slug") == slug:
                if mo_ta:
                    m["mo_ta"] = _gon(mo_ta, 300)
                    _ghi(d)
                return dict(m)
        if len(d["mon"]) >= TRAN_MON:
            raise ValueError(f"Kệ đã đủ {TRAN_MON} món, gỡ bớt trước")
        m = {"id": secrets.token_urlsafe(18), "brain": str(brain or "brain"), "type": typ, "slug": slug,
             "mo_ta": _gon(mo_ta, 300), "luc": int(time.time())}
        d["mon"].append(m)
        _ghi(d)
        return dict(m)


def bo_mon(id_: str) -> bool:
    with _LOCK:
        d = _doc()
        truoc = len(d["mon"])
        d["mon"] = [m for m in d["mon"] if m.get("id") != id_]
        if len(d["mon"]) == truoc:
            return False
        _ghi(d)
        return True


def sua_mon(id_: str, **truong) -> dict:
    """Sửa thuộc tính của một món (mô tả; phần gói có phí dùng thêm khoá riêng)."""
    with _LOCK:
        d = _doc()
        for m in d["mon"]:
            if m.get("id") == id_:
                for k, v in truong.items():
                    m[k] = v
                _ghi(d)
                return dict(m)
    return {}


def tim(id_: str):
    """Món CÒN trên một kệ ĐANG BẬT, hoặc None. Cửa duy nhất của mọi đường công khai."""
    if not _ID_RE.fullmatch(str(id_ or "")):
        return None
    d = _doc()
    if not d.get("bat"):
        return None
    for m in d["mon"]:
        if m.get("id") == id_:
            return dict(m)
    return None


def cong_khai() -> list:
    """Các món cho người ngoài xem (kệ tắt -> rỗng). Không lộ brain path nào."""
    d = _doc()
    if not d.get("bat"):
        return []
    return [dict(m) for m in d["mon"]]
