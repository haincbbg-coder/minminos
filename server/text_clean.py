"""Gỡ ký tự vô hình khỏi tin nhắn người ngoài gửi tới (Telegram, Zalo, bot khách, CLI).

Vì sao cần: người lạ nhắn tin có thể chèn chữ KHÔNG hiện ra trên màn hình (ký tự rộng bằng
không, ký tự đảo chiều chữ, khối "tag" U+E0000) để lén ra lệnh cho bộ não, trong khi chủ đọc
hộp thư thì không thấy gì. Gỡ sạch trước khi tin tới bộ não và trước khi lưu lại.

Giữ nguyên: xuống dòng, tab, và ký tự nối U+200D khi nó nằm giữa hai biểu tượng (emoji ghép
như 👨‍👩‍👧) hoặc giữa hai ký tự ngoài bảng chữ cái.
"""
import unicodedata

_GIU_CC = {"\n", "\r", "\t"}


def _la_bieu_tuong(ch):
    return ord(ch) >= 0x2190 if ch else False


def strip_hidden(text):
    """Trả bản sao không còn ký tự điều khiển/định dạng ẩn. Không phải chuỗi thì trả nguyên."""
    if not isinstance(text, str) or not text:
        return text
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        o = ord(ch)
        cat = unicodedata.category(ch)
        if cat == "Cc":
            if ch in _GIU_CC:
                out.append(ch)
            continue
        if ch == "️" or ch == "︎":      # chọn kiểu hiển thị emoji: vô hại, giữ
            out.append(ch)
            continue
        if ch == "‍":
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < n else ""
            if _la_bieu_tuong(prev) and _la_bieu_tuong(nxt):
                out.append(ch)
            continue
        if cat == "Cf" or 0xE0100 <= o <= 0xE01EF or cat in ("Zl", "Zp"):
            continue
        out.append(ch)
    return "".join(out)
