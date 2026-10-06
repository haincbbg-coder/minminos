"""Tên hiển thị của brain (26.10.71): đổi tên "Brain Default" hay brain nào cũng được.

Chỉ đổi NHÃN hiển thị, KHÔNG đổi tên thư mục. Tên thư mục là khoá nối tới hội thoại, project,
bản sao lưu git và đường dẫn đã lưu ở các máy khác; đổi thư mục là đứt hết những chỗ đó. Nhãn
nằm trong STATE_DIR/brain-labels.json: {tên_thư_mục: nhãn}. Nhãn rỗng = về tên thư mục.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import config

_KHOA = threading.Lock()
MAX_DAI = 60


def _path() -> Path:
    return config.STATE_DIR / "brain-labels.json"


def doc() -> dict:
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in d.items() if isinstance(d, dict) and str(v).strip()}
    except Exception:
        return {}


def dat(ten_thu_muc: str, nhan: str) -> str:
    """Đặt nhãn, trả nhãn đã làm sạch ('' nếu xoá). Ném ValueError nếu tên thư mục rỗng."""
    k = (ten_thu_muc or "").strip()
    if not k:
        raise ValueError("thiếu tên brain")
    nhan = " ".join((nhan or "").split())[:MAX_DAI]
    with _KHOA:
        d = doc()
        if nhan and nhan != k:
            d[k] = nhan
        else:
            d.pop(k, None)
            nhan = ""
        try:
            _path().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            raise ValueError(str(e))
    return nhan
