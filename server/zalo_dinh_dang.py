"""Đổi Markdown trong câu bot viết thành định dạng chữ của Zalo (26.10.314).

Zalo không hiện Markdown: khách đọc thấy nguyên `**85.000đ**` với bốn dấu sao. Nhưng Zalo có định
dạng riêng (đậm, nghiêng, gạch ngang, gạch chân, bốn màu, hai cỡ chữ) gửi kèm tin dưới dạng danh
sách khoảng `(vị trí, độ dài, kiểu)`. Module này đọc câu bot viết và trả về:

  - `sang_zalo(text)` -> (chữ trơn, [(bắt đầu, độ dài, tên kiểu), ...]) cho Zalo cá nhân, gửi qua
    `zalo-agent-cli msg send --style bắt_đầu:độ_dài:tên` (có từ bản 1.6.2 đang ghim);
  - `bo_dinh_dang(text)` -> chữ trơn, cho nơi không gửi được kiểu (Zalo OA, tin nhóm có tag).

Vị trí và độ dài tính theo ĐƠN VỊ UTF-16 vì zca-js cắt chuỗi theo chỉ số của JavaScript: một
emoji chiếm hai đơn vị, tính theo ký tự Python là lệch kiểu sang chữ bên cạnh.

Cú pháp nhận: `**đậm**`, `__đậm__`, `*nghiêng*`, `~~gạch~~`, `{red:chữ}` (red, orange, yellow,
green, big, small), `` `mã` `` (bỏ dấu), tiêu đề `# ...` (thành dòng đậm), gạch đầu dòng `- `
(thành `• `), liên kết `[chữ](url)` (thành `chữ (url)`), rào khối mã ``` (bỏ dòng rào).
"""
from __future__ import annotations

import re

KIEU = ("bold", "italic", "underline", "strikethrough", "red", "orange", "yellow", "green", "big", "small")

_MAU = re.compile(r"\{(red|orange|yellow|green|big|small):([^{}\n]+?)\}")
_DAM = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__")
_GACH = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_NGHIENG = re.compile(r"(?<![\*\w])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\*\w])")
_MA = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_TIEU_DE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_GACH_DAU = re.compile(r"^(\s*)[-*+]\s+")
_RAO = re.compile(r"^\s*```")


def _dong(text: str) -> str:
    """Bước theo dòng: rào khối mã, tiêu đề, gạch đầu dòng, liên kết."""
    out = []
    for d in str(text or "").replace("\r\n", "\n").split("\n"):
        if _RAO.match(d):
            continue
        m = _TIEU_DE.match(d)
        if m:
            noi = m.group(1).strip().strip("*").strip()
            d = f"**{noi}**" if noi else ""
        else:
            d = _GACH_DAU.sub(lambda mm: mm.group(1) + "• ", d, count=1)
        d = _LINK.sub(lambda mm: f"{mm.group(1)} ({mm.group(2)})", d)
        out.append(d)
    return "\n".join(out)


def _doi_vi_tri(pos: int, dau: int, trai: int, giua: int, phai: int) -> int:
    """Vị trí `pos` của chuỗi CŨ sau khi cặp dấu quanh [dau, dau+trai+giua+phai) bị bỏ."""
    if pos <= dau:
        return pos
    if pos <= dau + trai:
        return dau
    if pos <= dau + trai + giua:
        return pos - trai
    if pos <= dau + trai + giua + phai:
        return dau + giua
    return pos - trai - phai


def _boc(chu: str, styles: list, mau: re.Pattern, ten_kieu) -> str:
    """Bỏ một loại dấu khỏi `chu`, ghi lại khoảng chữ của nó vào `styles` và dời các khoảng đã có."""
    pos = 0
    while True:
        m = mau.search(chu, pos)
        if not m:
            return chu
        nhom = next(i for i in range(1, (m.lastindex or 0) + 1) if m.group(i) is not None
                    and not (mau is _MAU and i == 1))
        noi = m.group(nhom)
        trai = m.start(nhom) - m.start()
        phai = m.end() - m.end(nhom)
        kieu = ten_kieu(m) if callable(ten_kieu) else ten_kieu
        dau = m.start()
        for i, (a, n, k) in enumerate(styles):
            a2 = _doi_vi_tri(a, dau, trai, len(noi), phai)
            b2 = _doi_vi_tri(a + n, dau, trai, len(noi), phai)
            styles[i] = (a2, max(0, b2 - a2), k)
        chu = chu[:dau] + noi + chu[m.end():]
        if kieu:
            styles.append((dau, len(noi), kieu))
        pos = dau + len(noi)


def _utf16(chu: str, styles: list) -> list:
    """Đổi khoảng (chỉ số ký tự Python) sang đơn vị UTF-16 như zca-js đếm."""
    moc = [0]
    for ch in chu:
        moc.append(moc[-1] + (2 if ord(ch) > 0xFFFF else 1))
    out = []
    for a, n, k in styles:
        if n <= 0 or a < 0 or a + n > len(chu) or k not in KIEU:
            continue
        out.append((moc[a], moc[a + n] - moc[a], k))
    out.sort()
    return out


def sang_zalo(text: str):
    """(chữ trơn, danh sách kiểu theo UTF-16). Không có dấu nào thì danh sách rỗng."""
    chu = _dong(text)
    styles: list = []
    chu = _boc(chu, styles, _MA, None)
    chu = _boc(chu, styles, _MAU, lambda m: m.group(1))
    chu = _boc(chu, styles, _DAM, "bold")
    chu = _boc(chu, styles, _GACH, "strikethrough")
    chu = _boc(chu, styles, _NGHIENG, "italic")
    return chu, _utf16(chu, styles)


def bo_dinh_dang(text: str) -> str:
    """Chỉ lấy chữ trơn: khách không thấy dấu sao, dấu ngoặc nhọn hay dấu thăng nào."""
    return sang_zalo(text)[0]


def tham_so_style(styles) -> list:
    """Tham số `--style` cho `zalo-agent-cli msg send` (rỗng khi không có kiểu nào)."""
    specs = [f"{int(a)}:{int(n)}:{k}" for a, n, k in (styles or ()) if int(n) > 0 and k in KIEU]
    return ["--style", *specs] if specs else []
