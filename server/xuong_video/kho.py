"""Kho dự án của Xưởng video: mỗi dự án một thư mục, trạng thái trong project.json.

Ghi nguyên tử và có khoá: dây chuyền chạy nhiều việc song song nên hai chỗ cùng cập nhật một
dự án là chuyện thường. Không có DB: một dự án vài chục KB, vài trăm dự án là dư.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from config import STATE_DIR
except Exception:  # pragma: no cover
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

TRANG_THAI = ("nhap", "dang_lap_kich_ban", "kich_ban_xong", "dang_tao_anh", "dang_tao_video",
              "dang_tao_giong", "dang_ghep", "san_sang", "dang_dang", "da_dang", "loi", "da_huy")
NEN_TANG = ("youtube", "youtube_short", "facebook_reel", "tiktok", "zalo", "instagram", "x", "threads")
TI_LE = ("9:16", "16:9", "1:1")
MAX_NHAT_KY = 200
_lock = threading.RLock()


def goc() -> Path:
    p = Path(STATE_DIR) / "xuong-video" / "du-an"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _id_ok(i: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(i or "").lower())[:20]


def thu_muc(pid: str) -> Path:
    return goc() / _id_ok(pid)


def _file(pid: str) -> Path:
    return thu_muc(pid) / "project.json"


def _sach_chu(v: Any, n: int) -> str:
    return re.sub(r"\r", "", str(v or "")).strip()[:n]


def tao(data: dict) -> str:
    """Tạo dự án mới từ biểu mẫu. Trả id. Không chạy gì: chạy là việc của `chay`."""
    pid = uuid.uuid4().hex[:12]
    nt = [x for x in (data.get("nen_tang") or []) if x in NEN_TANG]
    ti_le = data.get("ti_le") if data.get("ti_le") in TI_LE else "9:16"
    try:
        gs = max(8, min(int(data.get("thoi_luong_giay") or 30), 180))
    except (TypeError, ValueError):
        gs = 30
    p: Dict[str, Any] = {
        "id": pid, "ten": _sach_chu(data.get("ten"), 120) or "Dự án mới",
        "y_tuong": _sach_chu(data.get("y_tuong"), 8000),
        "tai_lieu": [], "nen_tang": nt, "ti_le": ti_le, "thoi_luong_giay": gs,
        "phong_cach": _sach_chu(data.get("phong_cach"), 400),
        "ngon_ngu": _sach_chu(data.get("ngon_ngu"), 20) or "vi",
        "che_do_dang": "tu_dong" if data.get("che_do_dang") == "tu_dong" else "duyet",
        "dang_luc": float(data.get("dang_luc") or 0),
        "lo_id": _sach_chu(data.get("lo_id"), 20),
        "brain": _sach_chu(data.get("brain"), 80) or "brain",
        "trang_thai": "nhap", "loi": "", "tao_luc": time.time(), "sua_luc": time.time(),
        "kich_ban": {}, "canh": [], "nhan_vat": [], "ket_qua": {}, "dang": {}, "nhat_ky": [],
        "so_video_da_tao": 0,
        "nguon": "tu_lieu" if data.get("nguon") == "tu_lieu" else "ai",
        "ban_dung": {},
    }
    thu_muc(pid).mkdir(parents=True, exist_ok=True)
    _ghi(p)
    return pid


def _ghi(p: dict) -> None:
    f = _file(p["id"])
    f.parent.mkdir(parents=True, exist_ok=True)
    p["sua_luc"] = time.time()
    p["nhat_ky"] = (p.get("nhat_ky") or [])[-MAX_NHAT_KY:]
    tam = f.with_suffix(".tmp")
    tam.write_text(json.dumps(p, ensure_ascii=False), "utf-8")
    os.replace(tam, f)


def doc(pid: str) -> Optional[dict]:
    try:
        d = json.loads(_file(pid).read_text("utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def cap_nhat(pid: str, **kw) -> Optional[dict]:
    """Đọc, sửa các trường, ghi lại trong một khoá. Giá trị callable nhận giá trị cũ."""
    with _lock:
        p = doc(pid)
        if not p:
            return None
        for k, v in kw.items():
            p[k] = v(p.get(k)) if callable(v) else v
        _ghi(p)
        return p


def nhat_ky(pid: str, dong: str, muc: str = "info") -> None:
    cap_nhat(pid, nhat_ky=lambda ds: list(ds or []) + [{"t": time.time(), "m": str(dong)[:400], "k": muc}])


def cap_nhat_canh(pid: str, stt: int, **kw) -> Optional[dict]:
    with _lock:
        p = doc(pid)
        if not p:
            return None
        for c in p.get("canh") or []:
            if int(c.get("stt") or 0) == int(stt):
                c.update(kw)
                break
        _ghi(p)
        return p


def dat_trang_thai(pid: str, tt: str, loi: str = "") -> None:
    if tt in TRANG_THAI:
        cap_nhat(pid, trang_thai=tt, loi=str(loi or "")[:500])


def liet_ke() -> List[dict]:
    out = []
    try:
        for d in sorted(goc().iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            p = doc(d.name)
            if p:
                out.append(tom_tat(p))
    except OSError:
        pass
    return out


def tom_tat(p: dict) -> dict:
    canh = p.get("canh") or []
    return {"id": p["id"], "ten": p.get("ten"), "trang_thai": p.get("trang_thai"), "loi": p.get("loi") or "",
            "tao_luc": p.get("tao_luc"), "sua_luc": p.get("sua_luc"), "nen_tang": p.get("nen_tang") or [],
            "che_do_dang": p.get("che_do_dang"), "dang_luc": p.get("dang_luc") or 0,
            "so_canh": len(canh), "canh_xong": sum(1 for c in canh if c.get("video")),
            "co_video": bool((p.get("ket_qua") or {}).get("video")), "lo_id": p.get("lo_id") or "",
            "dang": {k: (v or {}).get("trang_thai") for k, v in (p.get("dang") or {}).items()}}


def xoa(pid: str) -> bool:
    d = thu_muc(pid)
    if not _id_ok(pid) or not d.is_dir():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True


def duong_dan_file(pid: str, rel: str) -> Optional[Path]:
    """File của dự án theo đường dẫn tương đối, chặn thoát khỏi thư mục dự án."""
    base = thu_muc(pid).resolve()
    try:
        p = (base / rel).resolve()
        p.relative_to(base)
    except (ValueError, OSError):
        return None
    return p if p.is_file() else None


DUOI_ANH = {".png", ".jpg", ".jpeg", ".webp"}
DUOI_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
DUOI_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}


def them_tai_lieu(pid: str, ten_goc: str, noi_dung: bytes) -> tuple:
    """Lưu một tài liệu tham khảo (ảnh/video). Trả (rel, loi)."""
    ten = re.sub(r"[^\w.\-]", "_", Path(str(ten_goc or "")).name)[:80] or "tep"
    duoi = Path(ten).suffix.lower()
    if duoi not in DUOI_ANH | DUOI_VIDEO | DUOI_AUDIO:
        return "", "Chỉ nhận ảnh, video hoặc âm thanh (mp3, wav, m4a, aac, ogg, flac)."
    if not noi_dung or len(noi_dung) > 200 * 1024 * 1024:
        return "", "File rỗng hoặc quá 200MB."
    p = doc(pid)
    if not p:
        return "", "Không có dự án này."
    d = thu_muc(pid) / "tai-lieu"
    d.mkdir(parents=True, exist_ok=True)
    dich, i = d / ten, 2
    while dich.exists():
        dich = d / f"{Path(ten).stem}-{i}{duoi}"
        i += 1
    dich.write_bytes(noi_dung)
    rel = "tai-lieu/" + dich.name
    cap_nhat(pid, tai_lieu=lambda ds: list(ds or []) + [
        {"rel": rel, "loai": "anh" if duoi in DUOI_ANH else "video" if duoi in DUOI_VIDEO else "audio", "ten": ten_goc[:80]}])
    return rel, ""
