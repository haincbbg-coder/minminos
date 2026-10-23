"""Plugin bundled: đọc văn bản thành giọng nói bằng VieNeu cho MỌI engine.

Tool `javis_vieneu_speak` gọi API đám mây của VieNeu bằng khoá của kết nối "VieNeu" (trang Kết nối,
mục Chợ MinMin) rồi lưu file âm thanh vào `attachments/` của brain. Phần nói chuyện với VieNeu nằm ở
server/vieneu_mcp.py; plugin chỉ lo tìm khoá, đặt tên và lưu file.

min_mode=safe: tạo file và TRỪ token của tài khoản VieNeu, nên chế độ chỉ-đề-xuất không được chạy.
"""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

import mcp_store
import vieneu_mcp


def _ket_noi_vieneu(ten_ket_noi: str = ""):
    """Kết nối VieNeu đang bật: theo nhãn người gọi nêu, rồi mặc định, rồi cái đầu tiên."""
    ds = [c for c in mcp_store.list_connections()
          if c.get("connector_id") == "vieneu" and c.get("enabled")]
    ten = (ten_ket_noi or "").strip().lower()
    if ten:
        ds = [c for c in ds if ten in str(c.get("label") or "").lower() or ten == str(c.get("id") or "").lower()]
    ds.sort(key=lambda c: not c.get("is_default"))
    return ds[0] if ds else None


def _bo_dau_slug(s: str, toi_da: int = 40) -> str:
    s = unicodedata.normalize("NFD", str(s or "")).replace("đ", "d").replace("Đ", "D")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:toi_da] or "giong-doc"


def _thu_muc_luu(vault_root: str) -> Path:
    d = Path(vault_root).resolve() / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def register(ctx):
    def _check():
        if _ket_noi_vieneu() is None:
            return ("Chưa nối VieNeu. Vào Chợ MinMin, chọn VieNeu, dán khoá API (vn_sk_..., tạo ở "
                    "vieneu.io > Nhà phát triển) rồi gọi lại tool này.")
        return None

    async def _speak(args, cctx):
        args = args or {}
        text = str(args.get("text") or "").strip()
        if not text:
            return "ERROR: thiếu 'text' (văn bản cần đọc)."
        if not getattr(cctx, "vault_root", None):
            return "ERROR: chưa biết brain đang dùng nên không có chỗ lưu file âm thanh."
        c = _ket_noi_vieneu(str(args.get("ket_noi") or ""))
        if c is None:
            return _check()
        sec = mcp_store.connection_secrets(c["id"])
        fmt = str(args.get("dinh_dang") or "mp3").lower()
        ok, du_lieu, so_doan, so_ky_tu = await vieneu_mcp.doc_thanh_tieng(
            sec, text, voice=args.get("voice") or "", speed=args.get("toc_do"), fmt=fmt)
        if not ok:
            return du_lieu
        ten = _bo_dau_slug(args.get("ten_file") or text[:30])
        tep = _thu_muc_luu(cctx.vault_root) / f"vieneu-{time.strftime('%y%m%d-%H%M%S')}-{ten}.{fmt}"
        tep.write_bytes(du_lieu)
        rel = f"attachments/{tep.name}"
        phut = f", {so_doan} đoạn ghép lại" if so_doan > 1 else ""
        return (f"Đã đọc {so_ky_tu:,} ký tự bằng VieNeu{phut}, lưu tại {rel} ({len(du_lieu) // 1024} KB). "
                f"HÃY đưa cho người dùng bằng markdown: [{tep.name}]({rel})")

    ctx.register_tool(
        name="javis_vieneu_speak",
        description=("Đọc văn bản thành file âm thanh bằng giọng AI tiếng Việt VieNeu (cần nối VieNeu ở Chợ "
                     "MinMin). Tham số: text (bắt buộc, tối thiểu 50 ký tự), voice (id giọng, lấy từ "
                     "vieneu_danh_sach_giong; bỏ trống = giọng mặc định), toc_do (0.5 đến 2.0), dinh_dang "
                     "(mp3 mặc định, hoặc wav), ten_file (gợi ý tên), ket_noi (nhãn kết nối nếu có nhiều "
                     "tài khoản VieNeu). Mỗi ký tự đọc là một ký tự bị trừ khỏi gói token của VieNeu. Văn bản "
                     "dài tự chia đoạn rồi ghép. Sau khi gọi, đưa link file trả về cho người dùng."),
        handler=_speak, min_mode="safe", check_fn=_check,
        schema={"type": "object", "properties": {
            "text": {"type": "string", "description": "Văn bản cần đọc (từ 50 đến 20.000 ký tự)"},
            "voice": {"type": "string", "description": "Id giọng VieNeu, ví dụ 'Ngọc Lan'"},
            "toc_do": {"type": "number", "description": "Tốc độ đọc 0.5 đến 2.0, mặc định 1.0"},
            "dinh_dang": {"type": "string", "enum": ["mp3", "wav"], "description": "Mặc định mp3"},
            "ten_file": {"type": "string", "description": "Gợi ý tên file, không cần đuôi"},
            "ket_noi": {"type": "string", "description": "Nhãn kết nối VieNeu, khi có nhiều tài khoản"}},
            "required": ["text"]},
    )
