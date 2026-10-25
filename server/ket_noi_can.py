"""ket_noi_can.py - KẾT NỐI một gói chia sẻ cần, so với kết nối máy nhận đang có (26.10.100).

Vì sao: skill "Lên camp sáng" nhập về một máy chưa nối Facebook Ads thì cài xong vẫn vô dụng,
và người nhận chỉ phát hiện khi chạy lần đầu thấy lỗi. Màn xem trước nói trước: gói cần Pancake
(bạn đã có), Facebook Ads (bạn chưa nối).

Hai nguồn, theo thứ tự tin cậy:
  1. KHAI BÁO: frontmatter `ket_noi: [pancake, facebook-ads]` (hoặc `requires_connections`) trong
     agent/workflow/SKILL.md. Người viết biết rõ nhất.
  2. PHÁT HIỆN: chữ trong gói (đã bỏ dấu) nhắc tới dịch vụ hoặc tên tool của nó. Đây là đoán,
     nên giao diện nói "có vẻ cần", không nói chắc.

So khớp với máy nhận dựa trên tên/mã/nhãn của kết nối MCP, gói mở rộng và plugin đã cài. Kết quả
chỉ để BÁO, không chặn cài: thiếu kết nối không nguy hiểm, chỉ là chưa dùng được.
"""
from __future__ import annotations

import io
import re
import zipfile

import fastyaml
from soi_rui_ro import bo_dau

# id -> (tên hiện, mẫu tìm trong GÓI, mẫu tìm trong tên KẾT NỐI của máy nhận)
DICH_VU = {
    "pancake": ("Pancake POS", r"pancake|poscake|pos\.pancake|mcp__pos",
                r"^(?!.*thong.?ke|.*pancake_chat).*(pancake|poscake|\bpos\b)"),
    "pancake-thong-ke": ("Thống kê Pancake", r"pancake_tk|thong ke pancake|pancake thong ke|thong ke hoi thoai",
                         r"thong ke pancake|pancake.?thong.?ke|pancake_chat"),
    "facebook-ads": ("Facebook Ads", r"facebook ads|\bfb ads\b|ads ?manager|meta ads|quang cao facebook|camp(aign)? facebook|mcp__(fb|facebook|meta)[a-z_]*ads",
                     r"facebook.?ads|fb.?ads|meta.?ads|ads.?manager|facebook|\bmeta\b"),
    "facebook-page": ("Fanpage Facebook", r"fanpage|dang bai (len )?(facebook|fb|page)|page facebook", r"facebook|fanpage|\bpage\b|\bmeta\b"),
    "zalo": ("Zalo", r"\bzalo\b|zalo_send|zalo_get|zalo_list", r"zalo"),
    "botcake": ("Botcake", r"botcake", r"botcake"),
    "gmail": ("Gmail", r"\bgmail\b", r"gmail|google.?workspace"),
    "google-calendar": ("Google Calendar", r"google calendar|lich google|google lich", r"calendar|google.?workspace"),
    "google-sheets": ("Google Sheets", r"google sheets?|\bgsheets?\b|bang tinh google", r"sheets?|google.?workspace"),
    "google-drive": ("Google Drive", r"google drive", r"drive|google.?workspace"),
    "google-ads": ("Google Ads", r"google ads", r"google.?ads"),
    "tiktok": ("TikTok", r"tiktok", r"tiktok"),
    "shopee": ("Shopee", r"shopee", r"shopee"),
    "higgsfield": ("Higgsfield", r"higgsfield", r"higgsfield"),
    "elevenlabs": ("ElevenLabs", r"elevenlabs|eleven labs", r"elevenlabs"),
    "notion": ("Notion", r"\bnotion\b", r"notion"),
    "telegram": ("Telegram", r"\btelegram\b", r"telegram"),
    "youtube": ("YouTube", r"youtube", r"youtube"),
    "substack": ("Substack", r"substack", r"substack"),
    "composio": ("Composio", r"composio", r"composio"),
}
_MAU_GOI = {k: re.compile(v[1], re.I) for k, v in DICH_VU.items()}
_MAU_MAY = {k: re.compile(v[2], re.I) for k, v in DICH_VU.items()}
_TOP = ("agents/", "workflows/", "skills/")
_KHOA_KHAI = ("ket_noi", "requires_connections", "connections")


def _ten_muc(arc: str) -> str:
    rel = arc.split("/", 1)[1] if "/" in arc else arc
    if arc.startswith("skills/"):
        return "skill " + rel.split("/")[0]
    return ("agent " if arc.startswith("agents/") else "workflow ") + (rel[:-3] if rel.endswith(".md") else rel)


def _chuan_id(v: str) -> str:
    """Tên người viết khai ('Facebook Ads', 'fb-ads', 'POS Pancake') -> id trong DICH_VU, hoặc
    chính chuỗi đã làm gọn nếu không nhận ra (vẫn hiện ra cho người nhận đọc)."""
    s = bo_dau(v).strip()
    for k, rx in _MAU_MAY.items():
        if s == k or rx.search(s):
            return k
    return re.sub(r"[^a-z0-9.-]+", "-", s).strip("-")[:40]


def phat_hien(data: bytes) -> list:
    """[{id, ten, khai_bao: bool, o: [mục nhắc tới]}], khai báo xếp trước."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return []
    ra: dict = {}

    def them(k, muc, khai):
        it = ra.setdefault(k, {"id": k, "ten": DICH_VU.get(k, (k,))[0], "khai_bao": False, "o": []})
        it["khai_bao"] = it["khai_bao"] or khai
        if muc not in it["o"] and len(it["o"]) < 6:
            it["o"].append(muc)

    for i in z.infolist():
        arc = i.filename.replace("\\", "/")
        if i.is_dir() or not arc.startswith(_TOP) or i.file_size > 512 * 1024 or ".." in arc.split("/"):
            continue
        if not arc.lower().endswith((".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".py", ".js", ".sh")):
            continue
        text = z.read(i).decode("utf-8", "replace")
        muc = _ten_muc(arc)
        if arc.endswith(".md") and text.startswith("---"):
            parts = text.split("---", 2)
            try:
                meta = fastyaml.safe_load(parts[1]) if len(parts) >= 3 else {}
            except Exception:
                meta = {}
            for khoa in _KHOA_KHAI:
                v = (meta or {}).get(khoa) if isinstance(meta, dict) else None
                for x in (v if isinstance(v, list) else [v] if isinstance(v, str) else []):
                    if str(x).strip():
                        them(_chuan_id(str(x)), muc, True)
        bd = bo_dau(text)
        for k, rx in _MAU_GOI.items():
            if rx.search(bd):
                them(k, muc, False)
    # Fanpage và Facebook Ads hay cùng xuất hiện; giữ cả hai vì là hai quyền khác nhau.
    return sorted(ra.values(), key=lambda x: (not x["khai_bao"], x["ten"]))


def doi_chieu(can: list, hien_co: list) -> list:
    """Gắn `trang_thai` cho từng kết nối cần: 'da_co' | 'dang_tat' | 'chua_co'.
    hien_co: [{ten, bat}] - mọi kết nối/gói/plugin của máy nhận, `ten` là chuỗi gộp mã+nhãn."""
    ra = []
    for it in can or []:
        rx = _MAU_MAY.get(it["id"]) or re.compile(re.escape(it["id"]), re.I)
        trung = [h for h in hien_co or [] if rx.search(bo_dau(h.get("ten", "")))]
        tt = "da_co" if any(h.get("bat", True) for h in trung) else ("dang_tat" if trung else "chua_co")
        ra.append(dict(it, trang_thai=tt))
    return ra
