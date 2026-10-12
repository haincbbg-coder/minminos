"""tong_hop_tuan.py - Bản tổng hợp 7 ngày qua của một brain: MinMin đã nhớ, học và dùng gì.

Chỉ ĐỌC đĩa (ký ức, nhật ký hội thoại, wiki, bộ đếm dùng skill, skill bị khoá), không gọi mô
hình, không tốn token. Mọi con số là đếm file thật, nên đọc xong có thể mở đúng chỗ kiểm.
Không bao giờ raise: phần nào đọc hỏng thì bỏ phần đó, các phần còn lại vẫn ra.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List

_NGAY = 7


def _moi(p: Path, tu: float) -> bool:
    try:
        return p.stat().st_mtime >= tu
    except OSError:
        return False


def _dong_dau(p: Path) -> str:
    """Dòng nội dung đầu tiên sau frontmatter, cắt ngắn."""
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if txt.startswith("---"):
        parts = txt.split("---", 2)
        txt = parts[2] if len(parts) == 3 else txt
    for ln in txt.splitlines():
        ln = ln.strip().lstrip("#-* ").strip()
        if ln:
            return ln[:120]
    return ""


def thu_thap(brain_root, mem_dir=None, now: float | None = None) -> Dict:
    now = now or time.time()
    tu = now - _NGAY * 86400
    root = Path(brain_root)
    mem = Path(mem_dir) if mem_dir else root / "memory"
    out: Dict = {"facts": [], "hoi_thoai_ngay": 0, "wiki": [], "skill_dung": [], "skill_khoa": []}
    try:
        for p in sorted((mem / "facts").glob("*.md"), key=lambda x: -x.stat().st_mtime):
            if _moi(p, tu):
                out["facts"].append({"ten": p.stem, "y": _dong_dau(p)})
    except Exception:
        pass
    try:
        out["hoi_thoai_ngay"] = sum(1 for p in (mem / "conversations").glob("*.md") if _moi(p, tu))
    except Exception:
        pass
    try:
        for d in root.iterdir():
            if d.is_dir() and d.name.lower() == "wiki":
                for p in d.rglob("*.md"):
                    if _moi(p, tu):
                        out["wiki"].append(str(p.relative_to(d)))
                break
    except Exception:
        pass
    try:
        dung = json.loads((root / "Javis" / "skill-usage.json").read_text(encoding="utf-8"))
        for slug, rec in (dung.items() if isinstance(dung, dict) else []):
            if isinstance(rec, dict) and float(rec.get("last_used_at") or 0) >= tu:
                out["skill_dung"].append((slug, int(rec.get("use_count") or 0)))
        out["skill_dung"].sort(key=lambda x: -x[1])
    except Exception:
        pass
    try:
        dd = root / "skills" / ".disabled"
        if dd.is_dir():
            out["skill_khoa"] = sorted(p.name for p in dd.iterdir() if p.is_dir() and _moi(p, tu))
    except Exception:
        pass
    return out


def xay(brain_root, mem_dir=None, now: float | None = None) -> str:
    """Văn nói tiếng Việt, không bảng, đọc được cả trên Telegram/Zalo."""
    d = thu_thap(brain_root, mem_dir, now)
    dong: List[str] = ["TUẦN QUA MINMIN ĐÃ HỌC GÌ"]
    n = len(d["facts"])
    if n:
        dong.append(f"Ghi nhớ thêm hoặc sửa {n} điều:")
        dong += [f"- {f['y'] or f['ten']}" for f in d["facts"][:5]]
        if n > 5:
            dong.append(f"- và {n - 5} điều nữa (xem ở trang Học, mục Điều MinMin đang nhớ)")
    else:
        dong.append("Không có ký ức nào mới.")
    if d["wiki"]:
        dong.append(f"Kho tri thức có {len(d['wiki'])} trang mới hoặc vừa sửa.")
    if d["hoi_thoai_ngay"]:
        dong.append(f"Có trò chuyện trong {d['hoi_thoai_ngay']} ngày của tuần.")
    if d["skill_dung"]:
        top = ", ".join(f"{s} ({c} lần)" for s, c in d["skill_dung"][:3])
        dong.append(f"Kỹ năng được dùng: {top}.")
    if d["skill_khoa"]:
        dong.append("Cần bố xem: kỹ năng nhập từ ngoài bị khoá vì nghi nguy hiểm: "
                    + ", ".join(d["skill_khoa"]) + ". Đọc rồi mới bật.")
    dong.append("Điều nào sai thì vào trang Học bấm Sửa hoặc Xoá.")
    return "\n".join(dong)
