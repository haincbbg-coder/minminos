"""Khoá API và kết nối nền tảng của Xưởng video. Mã hoá bằng secrets_store, không bao giờ trả
giá trị thật ra giao diện (chỉ trả "đã đặt hay chưa" và 4 ký tự cuối)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict

import secrets_store

try:
    from config import STATE_DIR
except Exception:  # pragma: no cover
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

_lock = threading.RLock()

# Trường được lưu theo từng dịch vụ. Trường trong BI_MAT được mã hoá và bị che khi trả ra.
DICH_VU: Dict[str, dict] = {
    "fal": {"truong": ("api_key",), "bi_mat": ("api_key",)},
    "gemini": {"truong": ("api_key",), "bi_mat": ("api_key",)},
    "openai": {"truong": ("api_key",), "bi_mat": ("api_key",)},
    "elevenlabs": {"truong": ("api_key", "voice_id"), "bi_mat": ("api_key",)},
    "youtube": {"truong": ("client_id", "client_secret", "refresh_token", "kenh"),
                "bi_mat": ("client_secret", "refresh_token")},
    "facebook": {"truong": ("page_id", "page_token", "ten_trang"), "bi_mat": ("page_token",)},
}


def _file() -> Path:
    p = Path(STATE_DIR) / "xuong-video"
    p.mkdir(parents=True, exist_ok=True)
    return p / "khoa.json"


def _doc() -> dict:
    try:
        d = json.loads(_file().read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ghi(d: dict) -> None:
    f = _file()
    tam = f.with_suffix(".tmp")
    tam.write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    os.replace(tam, f)
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass


def lay(dv: str) -> Dict[str, str]:
    """Giá trị THẬT (đã giải mã) của một dịch vụ, cho mã nội bộ dùng. KHÔNG trả ra giao diện."""
    spec = DICH_VU.get(dv)
    if not spec:
        return {}
    with _lock:
        raw = _doc().get(dv) or {}
    out = {}
    for k in spec["truong"]:
        v = raw.get(k, "")
        out[k] = secrets_store.decrypt(v) if k in spec["bi_mat"] else str(v or "")
    return out


def dat(dv: str, gia_tri: dict) -> bool:
    """Ghi các trường được gửi lên (trường rỗng = giữ nguyên, để form không phải gửi lại bí mật)."""
    spec = DICH_VU.get(dv)
    if not spec:
        return False
    with _lock:
        d = _doc()
        cur = dict(d.get(dv) or {})
        for k in spec["truong"]:
            v = (gia_tri or {}).get(k)
            if v is None or str(v).strip() == "":
                continue
            v = str(v).strip()
            cur[k] = secrets_store.encrypt(v) if k in spec["bi_mat"] else v
        d[dv] = cur
        _ghi(d)
    return True


def xoa(dv: str) -> None:
    with _lock:
        d = _doc()
        d.pop(dv, None)
        _ghi(d)


def che(v: str) -> str:
    v = str(v or "")
    return ("…" + v[-4:]) if len(v) >= 8 else ("đã đặt" if v else "")


def tinh_trang() -> Dict[str, dict]:
    """Cho giao diện: mỗi dịch vụ đã đặt những trường nào (bí mật chỉ hiện 4 ký tự cuối)."""
    out = {}
    for dv, spec in DICH_VU.items():
        val = lay(dv)
        out[dv] = {k: (che(val.get(k, "")) if k in spec["bi_mat"] else val.get(k, "")) for k in spec["truong"]}
        out[dv]["da_dat"] = any(val.get(k) for k in spec["truong"] if k in spec["bi_mat"]) or \
            any(val.get(k) for k in spec["truong"])
    return out


# ---- cài đặt chung (không bí mật) -------------------------------------------------------
MAC_DINH_CAI_DAT = {
    "anh": {"ncc": "gemini", "model": "gemini-2.5-flash-image"},
    "video": {"ncc": "fal", "model": "fal-ai/veo3.1/image-to-video"},
    "giong": {"ncc": "elevenlabs", "model": "eleven_multilingual_v2"},
    "toi_da_video_moi_ngay": 20,
    "toi_da_bai_dang_moi_ngay": 6,
    "ghep_phu_de": True,
}


def cai_dat() -> dict:
    try:
        d = json.loads((_file().with_name("cai-dat.json")).read_text("utf-8"))
    except Exception:
        d = {}
    out = json.loads(json.dumps(MAC_DINH_CAI_DAT))
    for k, v in (d or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update({a: b for a, b in v.items() if isinstance(b, (str, int, float, bool))})
        elif k in out and not isinstance(out[k], dict):
            out[k] = v
    return out


def luu_cai_dat(patch: dict) -> dict:
    cur = cai_dat()
    for k, v in (patch or {}).items():
        if k in ("anh", "video", "giong") and isinstance(v, dict):
            cur[k].update({a: str(b)[:120] for a, b in v.items() if a in ("ncc", "model")})
        elif k in ("toi_da_video_moi_ngay", "toi_da_bai_dang_moi_ngay"):
            try:
                cur[k] = max(0, min(int(v), 500))
            except (TypeError, ValueError):
                pass
        elif k == "ghep_phu_de":
            cur[k] = bool(v)
    f = _file().with_name("cai-dat.json")
    f.write_text(json.dumps(cur, ensure_ascii=False), "utf-8")
    return cur
