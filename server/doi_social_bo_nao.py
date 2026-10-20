"""doi_social_bo_nao.py - nối Đội Social với bộ não MinMin (wiki, ghi chú, trí nhớ) (26.10.187).

Vì sao: Kiến thức cho Agent không nên là một kho tách rời. Chủ đã viết sẵn mô tả sản phẩm, bảng giá,
chính sách, giọng văn trong brain (wiki, sources, memory). Agent social phải đọc được ngay chỗ đó,
không bắt chủ nhập lại.

Ba đường vào prompt AI:
  1. Tệp gắn tay vào một sản phẩm (`nguon_bo_nao`) - luôn đưa vào, đọc nguyên văn (cắt ngắn).
  2. Tự tra bộ não theo ngữ cảnh (`tu_tra_bo_nao`, mặc định bật) - dùng chính bộ tìm của chatbot
     (`chatbot_grounding.thu_thap`: đối chiếu từ khoá có trọng số, có ngưỡng "coi như không thấy",
     bỏ qua inbox/attachments/memory/skills để không tự đầu độc).
  3. Trí nhớ doanh nghiệp (`memory/MEMORY.md`, chỉ mục các fact về chủ và doanh nghiệp) - đưa một
     đoạn ngắn làm bối cảnh cho Trợ lý AI và các câu trả lời khách.

Gốc brain do main.py tiêm (`dat_goc`), test tiêm thư mục tạm. Mọi đường dẫn tệp gắn tay đều là
đường TƯƠNG ĐỐI trong brain, kiểm chặt không thoát ra ngoài.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, List, Optional

DUOI = (".md", ".txt", ".markdown")
TEP_TOI_DA = 6000          # chữ mỗi tệp gắn tay đưa vào prompt
KY_UC_TOI_DA = 2500        # chữ trích từ MEMORY.md
_goc: Optional[Callable[[], str]] = None


def dat_goc(ham: Optional[Callable[[], str]]) -> None:
    global _goc
    _goc = ham


def goc() -> Optional[Path]:
    if not _goc:
        return None
    try:
        p = Path(str(_goc())).resolve()
    except Exception:
        return None
    return p if p.is_dir() else None


def _an_toan(duong: str) -> Optional[Path]:
    r = goc()
    if not r or not duong:
        return None
    d = str(duong).replace("\\", "/").lstrip("/")
    if ".." in d.split("/"):
        return None
    p = (r / d).resolve()
    try:
        p.relative_to(r)
    except ValueError:
        return None
    if p.suffix.lower() not in DUOI or not p.is_file():
        return None
    return p


def doc_tep(duong: str, toi_da: int = TEP_TOI_DA) -> Optional[dict]:
    p = _an_toan(duong)
    if not p:
        return None
    try:
        chu = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    ten = p.stem
    for dong in chu.splitlines()[:40]:
        if dong.startswith("# "):
            ten = dong[2:].strip() or ten
            break
    return {"path": str(p.relative_to(goc())).replace("\\", "/"), "ten": ten, "noi_dung": chu[:toi_da],
            "dai": len(chu)}


def tim(cau_hoi: str, k: int = 6) -> List[dict]:
    """Mảnh tài liệu trong brain khớp câu hỏi (cho ô tìm ở trang Kiến thức). Không lọc ngưỡng."""
    r = goc()
    if not r or not str(cau_hoi or "").strip():
        return []
    try:
        import chatbot_grounding as cg
        hit = cg.tim(r, str(cau_hoi)[:500], k)
    except Exception as e:
        print(f"[doi-social] tìm bộ não lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return []
    ra, da = [], set()
    for h in hit:
        if h["path"] in da:
            continue
        da.add(h["path"])
        ra.append({"path": h["path"], "ten": h["ten"], "diem": h["diem"], "trich": (h["text"] or "")[:400]})
    return ra


def thu_thap(cau_hoi: str, k: int = 4) -> dict:
    """Khối tài liệu ĐỦ liên quan cho prompt (có ngưỡng). {co, khoi, nguon}."""
    r = goc()
    if not r or not str(cau_hoi or "").strip():
        return {"co": False, "khoi": "", "nguon": []}
    try:
        import chatbot_grounding as cg
        return cg.thu_thap(r, str(cau_hoi)[:800], k)
    except Exception as e:
        print(f"[doi-social] thu thập bộ não lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return {"co": False, "khoi": "", "nguon": []}


def ky_uc() -> str:
    """Đoạn đầu chỉ mục trí nhớ (facts về chủ và doanh nghiệp) - bối cảnh chung."""
    r = goc()
    if not r:
        return ""
    for ten in ("memory/MEMORY.md", "memory/memory.md"):
        p = r / ten
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")[:KY_UC_TOI_DA]
            except Exception:
                return ""
    return ""


def bo_sung(kt: Optional[dict], cau_hoi: str = "") -> Optional[dict]:
    """Thêm tri thức từ bộ não vào kiến thức sản phẩm đưa cho AI (dạng `tai_lieu` mà prompt đã đọc).

    Tệp gắn tay đứng trước (chủ đã chọn), rồi tới mảnh tự tra theo tên sản phẩm + từ khoá + ngữ cảnh."""
    if not kt:
        return kt
    kt = dict(kt)
    tl = list(kt.get("tai_lieu") or [])
    them = []
    for d in (kt.get("nguon_bo_nao") or [])[:10]:
        t = doc_tep(d)
        if t:
            them.append({"ten": f"Bộ não MinMin: {t['ten']}", "noi_dung": t["noi_dung"]})
    if kt.get("tu_tra_bo_nao", True):
        q = " ".join(x for x in (str(kt.get("ten") or ""), str(kt.get("tu_khoa") or ""), str(cau_hoi or "")[:300]) if x)
        tt = thu_thap(q, 3)
        da = set(kt.get("nguon_bo_nao") or [])
        if tt.get("co") and not all(n in da for n in tt.get("nguon") or []):
            them.append({"ten": "Bộ não MinMin (tự tra theo ngữ cảnh)", "noi_dung": tt["khoi"]})
    kt["tai_lieu"] = them + tl
    kt["nguon_tri_thuc"] = [t["ten"] for t in them]
    return kt


def boi_canh_tro_ly(tin: str) -> dict:
    """Tri thức bộ não cho Trợ lý AI: trí nhớ doanh nghiệp + mảnh khớp câu hỏi."""
    tt = thu_thap(tin, 4)
    return {"ky_uc": ky_uc(), "tai_lieu": tt.get("khoi", "") if tt.get("co") else "", "nguon": tt.get("nguon", [])}


# ------------------------------------------------------------------ agent MinMin làm vai trò cho Đội Social
# Việc AI của Đội Social mượn "vai" của agent sẵn có trong bộ não (agents/<slug>.md): chăm sóc khách
# trả lời tin nhắn/bình luận, content creator viết bài/bình luận. Chủ đổi được trong trang Kiến thức.
VIEC_AI = {
    "tra_loi_tin_nhan": "Trả lời tin nhắn khách",
    "tra_loi_binh_luan": "Trả lời bình luận",
    "viet_binh_luan": "Viết bình luận nhóm / seeding",
    "viet_bai": "Viết bài đăng",
    "tro_ly": "Trợ lý AI lập kế hoạch",
}
VAI_MAC_DINH = {"tra_loi_tin_nhan": "cham-soc-khach-hang", "tra_loi_binh_luan": "cham-soc-khach-hang",
                "viet_binh_luan": "content-creator", "viet_bai": "content-creator", "tro_ly": ""}
VAI_TOI_DA = 3000


def ds_agent() -> list:
    """Agent có trong bộ não: [{slug, ten, mo_ta}] (đọc frontmatter name/description nếu có)."""
    r = goc()
    if not r:
        return []
    ra = []
    for thu_muc in ("agents", "Javis/agents"):
        d = r / thu_muc
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md"))[:200]:
            ten, mo_ta = p.stem, ""
            try:
                dau = p.read_text(encoding="utf-8", errors="replace")[:3000]
            except Exception:
                continue
            if dau.startswith("---"):
                for dong in dau.split("\n---", 1)[0].splitlines():
                    if dong.startswith("name:"):
                        ten = dong[5:].strip().strip('"\'') or ten
                    elif dong.startswith("description:"):
                        mo_ta = dong[12:].strip().strip('"\'')[:200]
            if not any(a["slug"] == p.stem for a in ra):
                ra.append({"slug": p.stem, "ten": ten, "mo_ta": mo_ta})
        if ra:
            break
    return ra


def doc_agent(slug: str) -> str:
    """Thân agent (bỏ frontmatter), cắt ngắn. Rỗng nếu không có."""
    import re as _re
    if not slug or not _re.fullmatch(r"[A-Za-z0-9._-]{1,120}", slug):
        return ""
    for thu_muc in ("agents", "Javis/agents"):
        t = doc_tep(f"{thu_muc}/{slug}.md", 20000)
        if t:
            than = t["noi_dung"]
            if than.startswith("---"):
                ket = than.find("\n---", 3)
                if ket > 0:
                    than = than[ket + 4:]
            return than.strip()[:VAI_TOI_DA]
    return ""


def phu_luc_vai(viec: str, cau_hinh: dict) -> str:
    """Đoạn mở đầu prompt: vai trò lấy từ agent MinMin được gán cho loại việc này."""
    slug = (cau_hinh or {}).get(viec, VAI_MAC_DINH.get(viec, ""))
    than = doc_agent(slug)
    if not than:
        return ""
    return (f"VAI TRÒ CỦA BẠN (lấy từ agent MinMin '{slug}' trong bộ não của chủ; theo đúng giọng văn, cách xưng hô, "
            "cách chăm sóc khách ở đây, nhưng LUẬT và định dạng trả lời phía dưới luôn được ưu tiên):\n"
            + than + "\n\n=====\n\n")
