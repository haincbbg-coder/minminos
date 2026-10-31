"""Nén gọn JS/CSS của dashboard lúc phục vụ (26.10.313). Không có bước build: mã nguồn giữ nguyên.

VÌ SAO
Dashboard là JS thuần, chú thích tiếng Việt viết rất dày (đó là cách repo này giữ lý do của từng
quyết định). Đo ngày 30/10/2026 trên máy chủ thử: lần mở đầu tải 2.013 KB (đã gzip), phần lớn là JS.
Điện thoại trên 4G phải tải và đọc qua toàn bộ chú thích đó đúng lúc người dùng chờ nhất: lần mở
đầu và ngay sau mỗi bản cập nhật.

CÁCH LÀM (cố ý dè dặt)
- Không bao giờ đụng vào BÊN TRONG chuỗi, template, regex.
- Chỉ bỏ chú thích và khoảng trắng GIỮA các token.
- Khoảng trắng hay chú thích có xuống dòng thì giữ ĐÚNG SỐ dấu xuống dòng đó: luật tự chèn dấu chấm
  phẩy (ASI) không đổi nghĩa, và số dòng của bản nén trùng mã nguồn, nên báo lỗi trên trình duyệt
  vẫn chỉ đúng dòng cần sửa (mỗi dòng trống tốn một byte, gzip nén gần hết).
- Bỏ hẳn một khoảng trắng chỉ khi một bên là dấu chắc chắn không dính được vào bên kia.
`tests/js/test_nen_gon.js` chạy bộ này trên MỌI file JS của dashboard rồi so từng token với bản gốc
bằng acorn: một chỗ đoán sai "/" là regex hay phép chia là test đỏ ngay.

An toàn khi hỏng: mọi lỗi (file lạ, chuỗi không đóng, ngoại lệ) đều trả lại nguyên bản gốc.
Tắt hẳn bằng MINMIN_MINIFY=0.
"""
from __future__ import annotations

import os
import threading
import zlib
from pathlib import Path

# Sau các từ khoá này, "/" mở một regex chứ không phải phép chia.
_TU_TRUOC_REGEX = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
                   "case", "do", "else", "yield", "await"}
# Bỏ hẳn khoảng trắng khi một bên là một trong các dấu này. Cố ý vắng mặt: + - . / (dính thành ++,
# --, số thập phân, chú thích), < > ! (dính thành chú thích kiểu HTML `<!--`, `-->`), dấu nháy.
_DAU_AN_TOAN = set("{}()[];,:=?&|*%^~")
_KHOANG = " \t\r\n\f\v ﻿  "
_XUONG = "\n\r  "


def _la_chu(c: str) -> bool:
    return c.isalnum() or c in "_$\\#" or ord(c) > 127


def _so_xuong_dong(doan: str) -> int:
    return doan.replace("\r\n", "\n").count("\n") + doan.count("\r") - doan.count("\r\n") \
        + doan.count(" ") + doan.count(" ")


def nen_js(src: str) -> str:
    """Bỏ chú thích và khoảng trắng thừa. Ném ValueError khi gặp thứ không chắc."""
    out: list = []
    n = len(src)
    i = 0
    truoc = ""            # token có nghĩa ngay trước (đoán "/" là regex hay phép chia)
    loai_truoc = ""       # "chu" | "dau" | "chuoi" | "regex" | "tpl"
    cho = ""              # khoảng trắng/chú thích vừa bỏ: "" | " " | "\n" * k
    ngoac: list = []      # mỗi `${` đang mở: số ngoặc nhọn đã mở bên trong nó

    def ghi(tok: str, loai: str) -> None:
        nonlocal cho, truoc, loai_truoc
        if cho:
            if cho[0] == "\n":
                out.append(cho)
            elif out:
                a, b = out[-1][-1], tok[0]
                if a == "/" or b == "/":
                    out.append(" ")
                elif a in _DAU_AN_TOAN or b in _DAU_AN_TOAN:
                    pass
                else:
                    out.append(" ")
        cho = ""
        out.append(tok)
        truoc, loai_truoc = tok, loai

    def them_cho(doan: str) -> None:
        nonlocal cho
        k = _so_xuong_dong(doan)
        if k:
            cho = "\n" * (k + (len(cho) if cho[:1] == "\n" else 0))
        elif not cho:
            cho = " "

    def doc_template(k: int) -> tuple:
        """Từ dấu ` mở (hoặc `}` đóng một `${`) ở vị trí k: lấy trọn đoạn chữ tới ` đóng hoặc `${`.
        Trả (đoạn, vị trí kế, đoạn có mở `${` không)."""
        m = k + 1
        while m < n:
            c = src[m]
            if c == "\\":
                m += 2
                continue
            if c == "`":
                return src[k:m + 1], m + 1, False
            if c == "$" and m + 1 < n and src[m + 1] == "{":
                return src[k:m + 2], m + 2, True
            m += 1
        raise ValueError("template không đóng")

    def ghi_template(k: int) -> int:
        doan, j, mo = doc_template(k)
        if mo:
            ngoac.append(0)
            ghi(doan, "dau")        # ngay sau `${` là đầu một biểu thức: "/" ở đó là regex
        else:
            ghi(doan, "tpl")
        return j

    while i < n:
        c = src[i]
        if c in _KHOANG:
            j = i
            while j < n and src[j] in _KHOANG:
                j += 1
            them_cho(src[i:j])
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = i + 2
            while j < n and src[j] not in _XUONG:
                j += 1
            if not cho:
                cho = " "
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                raise ValueError("chú thích không đóng")
            them_cho(src[i:j + 2] if _so_xuong_dong(src[i:j + 2]) else " ")
            i = j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] in "\n\r":
                    raise ValueError("chuỗi không đóng")
                j += 1
            if j >= n:
                raise ValueError("chuỗi không đóng")
            ghi(src[i:j + 1], "chuoi")
            i = j + 1
            continue
        if c == "`":
            i = ghi_template(i)
            continue
        if c == "/":
            la_regex = (loai_truoc in ("", "dau") and truoc not in (")", "]", "++", "--")) \
                or (loai_truoc == "chu" and truoc in _TU_TRUOC_REGEX)
            if la_regex:
                j = i + 1
                trong_lop = False
                while j < n:
                    d = src[j]
                    if d == "\\":
                        j += 2
                        continue
                    if d in _XUONG:
                        raise ValueError("regex không đóng")
                    if d == "[":
                        trong_lop = True
                    elif d == "]":
                        trong_lop = False
                    elif d == "/" and not trong_lop:
                        break
                    j += 1
                if j >= n:
                    raise ValueError("regex không đóng")
                j += 1
                while j < n and _la_chu(src[j]):
                    j += 1
                ghi(src[i:j], "regex")
                i = j
                continue
            ghi("/", "dau")
            i += 1
            continue
        if _la_chu(c):
            j = i + 1
            while j < n and _la_chu(src[j]):
                j += 1
            ghi(src[i:j], "chu")
            i = j
            continue
        if c in "+-" and i + 1 < n and src[i + 1] == c:
            ghi(c + c, "dau")
            i += 2
            continue
        if c == "{":
            if ngoac:
                ngoac[-1] += 1
            ghi("{", "dau")
            i += 1
            continue
        if c == "}":
            if ngoac and ngoac[-1] == 0:
                ngoac.pop()
                i = ghi_template(i)
                continue
            if ngoac:
                ngoac[-1] -= 1
            ghi("}", "dau")
            i += 1
            continue
        ghi(c, "dau")
        i += 1

    if ngoac:
        raise ValueError("template không đóng")
    if cho[:1] == "\n":
        out.append(cho)
    return "".join(out)


def nen_css(src: str) -> str:
    """Bỏ chú thích, thụt đầu dòng và khoảng trắng cuối dòng; gộp chuỗi khoảng trắng thành một.
    Không bao giờ bỏ HẲN khoảng trắng giữa hai thứ (trong CSS nó có thể là bộ chọn con cháu)."""
    out: list = []
    n = len(src)
    i = 0
    cho = ""
    while i < n:
        c = src[i]
        if c in " \t\r\n\f":
            j = i
            while j < n and src[j] in " \t\r\n\f":
                j += 1
            k = src[i:j].replace("\r\n", "\n").count("\n")
            cho = "\n" * (k + (len(cho) if cho[:1] == "\n" else 0)) if k else (cho or " ")
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                raise ValueError("chú thích không đóng")
            k = src[i:j].count("\n")
            cho = "\n" * (k + (len(cho) if cho[:1] == "\n" else 0)) if k else (cho or " ")
            i = j + 2
            continue
        if cho:
            if cho[0] == "\n" or out:
                out.append(cho)
            cho = ""
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    raise ValueError("chuỗi không đóng")
                j += 1
            if j >= n:
                raise ValueError("chuỗi không đóng")
            out.append(src[i:j + 1])
            i = j + 1
            continue
        out.append(c)
        i += 1
    if cho[:1] == "\n":
        out.append(cho)
    return "".join(out)


def bat() -> bool:
    return os.getenv("MINMIN_MINIFY", "1").strip().lower() not in ("0", "false", "no", "off")


def nen_duoc(ten: str) -> bool:
    """File nào đáng nén: .js/.css của MinMin. Thư viện ngoài (.min.js, vendor/) đã gọn sẵn."""
    t = ten.replace("\\", "/").lower()
    if not t.endswith((".js", ".mjs", ".css")) or ".min." in t or "/vendor/" in t or t.startswith("vendor/"):
        return False
    return True


_NHO: dict = {}          # đường dẫn -> (khoá (mtime, size, bật), bytes, crc)
_KHOA = threading.Lock()


def ban_phuc_vu(f: Path, ten: str = "") -> tuple:
    """(nội dung sẽ gửi cho trình duyệt, crc32 hex của chính nội dung đó). Nhớ theo (mtime, size)
    nên gọi lại rẻ. Lỗi nén thì gửi nguyên bản gốc. Ném OSError khi không đọc được file."""
    st = f.stat()
    nen = bat() and nen_duoc(ten or f.name)
    khoa = (st.st_mtime_ns, st.st_size, nen)
    k = str(f)
    with _KHOA:
        ent = _NHO.get(k)
    if ent and ent[0] == khoa:
        return ent[1], ent[2]
    raw = f.read_bytes()
    data = raw
    if nen:
        try:
            src = raw.decode("utf-8")
            gon = nen_css(src) if f.suffix.lower() == ".css" else nen_js(src)
            data = gon.encode("utf-8")
        except Exception:  # noqa: BLE001 - không chắc thì gửi nguyên văn, không bao giờ gửi bản hỏng
            data = raw
    crc = format(zlib.crc32(data) & 0xFFFFFFFF, "08x")
    with _KHOA:
        _NHO[k] = (khoa, data, crc)
    return data, crc
