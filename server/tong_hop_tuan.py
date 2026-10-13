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


def thu_thap(brain_root, mem_dir=None, now: float | None = None, bo_qua=()) -> Dict:
    now = now or time.time()
    tu = now - _NGAY * 86400
    root = Path(brain_root)
    mem = Path(mem_dir) if mem_dir else root / "memory"
    out: Dict = {"facts": [], "hoi_thoai_ngay": 0, "wiki": [], "skill_dung": [], "skill_khoa": [], "skill_chua_thay": [], "viec_hong": []}
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
    # Skill chưa thấy dùng: CHỈ để bố cân nhắc. Bộ đếm chỉ thấy lần gọi qua javis_use_skill (Claude
    # nạp skill native thì không đếm), nên "chưa thấy" khác "vô dụng" - không bao giờ tự tắt.
    try:
        import skill_usage
        dung = skill_usage.read_usage(root)
        sk = root / "skills"
        for d in sorted(sk.iterdir()) if sk.is_dir() else []:
            md = d / "SKILL.md"
            if not d.is_dir() or d.name.startswith(".") or d.name in bo_qua or not md.is_file():
                continue
            if skill_usage.is_stale(dung.get(d.name, {}), md.stat().st_mtime, now):
                out["skill_chua_thay"].append(d.name)
    except Exception:
        pass
    try:
        rems = json.loads((root / "Javis" / "reminders.json").read_text(encoding="utf-8")).get("reminders", [])
        for r in rems:
            if not isinstance(r, dict):
                continue
            hong_gan_day = r.get("status") == "failed" and float(r.get("fired_at") or 0) >= tu
            lien_tiep = int(r.get("fail_streak") or 0) >= 2
            if hong_gan_day or lien_tiep:
                out["viec_hong"].append({"ten": str(r.get("label") or r.get("text") or "")[:60],
                                         "loi": str(r.get("error") or "")[:100]})
    except Exception:
        pass
    return out


def xay(brain_root, mem_dir=None, now: float | None = None, bo_qua=()) -> str:
    """Văn nói tiếng Việt, không bảng, đọc được cả trên Telegram/Zalo."""
    d = thu_thap(brain_root, mem_dir, now, bo_qua)
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
    if d["viec_hong"]:
        dong.append(f"Việc hẹn giờ đang hỏng ({len(d['viec_hong'])}):")
        dong += [f"- {v['ten']}: {v['loi'] or 'không rõ lỗi'}" for v in d["viec_hong"][:5]]
    if d["skill_chua_thay"]:
        n2 = len(d["skill_chua_thay"])
        dong.append(f"{n2} kỹ năng chưa thấy dùng quá 30 ngày: " + ", ".join(d["skill_chua_thay"][:6])
                    + (" và còn nữa" if n2 > 6 else "")
                    + ". Chưa thấy dùng chưa chắc là vô dụng, bố xem cái nào không cần thì tắt.")
    dong.append("Điều nào sai thì vào trang Học bấm Sửa hoặc Xoá.")
    return "\n".join(dong)
