"""google-link-doc - đọc link Google Docs / Sheets / Slides chia sẻ công khai (26.10.144).

Vì sao cần: khách hoặc chủ dán link Google Sheet ("danh sách bài cần đăng", "bảng giá") vào chat mà
não không mở được link. Tool này tải bản xuất văn bản của chính tài liệu đó.

Chỉ đọc, KHÔNG cần đăng nhập Google: dùng đường xuất công khai (export) nên tài liệu phải ở chế độ
"Bất kỳ ai có đường liên kết đều xem được". Tài liệu riêng tư thì báo rõ để chủ đổi quyền chia sẻ
hoặc nối kết nối Google Sheets riêng.

An toàn: chỉ nhận host docs.google.com / drive.google.com, theo chuyển hướng tối đa 3 lần và CHỈ
trong các host Google, nên không bị lợi dụng làm cầu gọi vào mạng nội bộ.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

TOI_DA_KY_TU = 30_000
HOST_OK = {"docs.google.com", "drive.google.com", "doc-0s-0-docs.googleusercontent.com"}
_ID = r"/d/([A-Za-z0-9_-]{15,})"


def phan_tich(url: str):
    """-> (loai, id, gid) hoặc (None, lỗi, None). loai: document|spreadsheets|presentation."""
    u = urlparse(str(url or "").strip())
    if u.scheme not in ("http", "https") or (u.hostname or "").lower() not in HOST_OK:
        return None, "Chỉ đọc được link docs.google.com (Docs, Sheets, Slides).", None
    m = re.search(r"/(document|spreadsheets|presentation)" + _ID, u.path)
    if not m:
        return None, "Link này không phải Google Docs, Sheets hay Slides.", None
    gid = (parse_qs(u.query).get("gid") or [""])[0]
    if not gid:
        g = re.search(r"gid=(\d+)", u.fragment or "")
        gid = g.group(1) if g else ""
    return m.group(1), m.group(2), gid


def url_xuat(loai, did, gid):
    if loai == "document":
        return f"https://docs.google.com/document/d/{did}/export?format=txt"
    if loai == "spreadsheets":
        return (f"https://docs.google.com/spreadsheets/d/{did}/export?format=csv"
                + (f"&gid={gid}" if gid else ""))
    return f"https://docs.google.com/presentation/d/{did}/export/txt"


async def _tai(url):
    """-> (status, content_type, text). Theo chuyển hướng thủ công, chỉ trong host Google."""
    import httpx
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as c:
        for _ in range(4):
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0 MinMin"})
            if r.status_code in (301, 302, 303, 307, 308):
                nxt = r.headers.get("location") or ""
                host = (urlparse(nxt).hostname or "").lower()
                if not nxt.startswith("https://") or not (host in HOST_OK or host.endswith(".google.com")
                                                          or host.endswith(".googleusercontent.com")):
                    return 0, "", ""
                if host.endswith("accounts.google.com"):
                    return 401, "", ""
                url = nxt
                continue
            return r.status_code, r.headers.get("content-type", ""), r.text
    return 0, "", ""


async def _doc(args):
    url = str((args or {}).get("url") or "").strip()
    loai, did, gid = phan_tich(url)
    if not loai:
        return "ERROR: " + did
    gid = str((args or {}).get("gid") or gid or "")
    st, ct, text = await _tai(url_xuat(loai, did, gid))
    if st in (401, 403, 404) or (st == 200 and "text/html" in ct.lower()):
        return ("ERROR: Không mở được tài liệu. Vào Google bấm Chia sẻ > Bất kỳ ai có đường liên kết, "
                "quyền Người xem, rồi gửi lại link. Tài liệu riêng tư thì cần nối kết nối Google riêng.")
    if st != 200:
        return f"ERROR: Google trả mã {st or 'không rõ'}, thử lại sau."
    text = (text or "").lstrip("﻿").strip()
    if not text:
        return "Tài liệu trống."
    cat = len(text) > TOI_DA_KY_TU
    ten = {"document": "Google Docs", "spreadsheets": "Google Sheets", "presentation": "Google Slides"}[loai]
    kq = f"[{ten}{' tab gid=' + gid if gid else ''}]\n" + text[:TOI_DA_KY_TU]
    if cat:
        kq += f"\n\n(đã cắt, tài liệu dài {len(text)} ký tự, chỉ lấy {TOI_DA_KY_TU} ký tự đầu)"
    return kq


def register(ctx):
    ctx.register_tool(
        name="google_link_doc",
        description=("Đọc nội dung một link Google Docs, Google Sheets (xuất CSV, mỗi dòng một hàng) hoặc "
                     "Google Slides đang chia sẻ 'Bất kỳ ai có đường liên kết'. Tham số: url (bắt buộc), "
                     "gid (tuỳ chọn, số của tab trong Sheets, mặc định lấy từ link hoặc tab đầu). "
                     "Dùng khi người dùng dán link Google và muốn bạn đọc, tóm tắt hay làm theo bảng."),
        handler=_doc, min_mode="readonly",
        schema={"type": "object", "properties": {
            "url": {"type": "string", "description": "Link docs.google.com"},
            "gid": {"type": "string", "description": "Số tab trong Google Sheets (tuỳ chọn)"}},
            "required": ["url"]},
    )
