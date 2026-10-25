"""Regression: design system 26.10.238 (phương án A "Nổi mềm tinh gọn") - chặn số lạ quay lại.

Bối cảnh: trước đợt này kho CSS có 28 cỡ chữ px và 21 mức bo góc px khác nhau, mỗi trang tự
chọn số. Phase 01 dựng thang token chung trong `dashboard/surface-tokens.css`, Phase 04 quy đổi
các file CSS sang token. Test này giữ cho thang không bị phá lại:

1. surface-tokens.css khai ĐỦ token và ĐÚNG giá trị như bảng trong plans/design-system/PLAN.md.
2. Trong các file CSS đã chuẩn hoá (bỏ chú thích trước khi soi):
   - không còn `font-size: Npx` với 10 <= N < 30 (phải dùng var(--mm-fs-*));
     cỡ < 10 (nhãn đồ thị) và >= 30 (số trang trí) là ngoại lệ được phép;
   - không còn bo góc px >= 5 trong mọi biến thể `*-radius` (kể cả dạng nhiều giá trị
     `10px 10px 0 0`); 0 và 2-4px (thanh mảnh, thanh cuộn) được phép; 99px/999px phải là
     var(--mm-r-pill);
   - mọi var(--mm-fs-*) và var(--mm-r-*) phải là token CÓ THẬT. Trình duyệt gặp var() không
     giải được thì bỏ cả dòng khai báo, hỏng trong im lặng (xem lỗi --warn ở test_theme_tokens).
3. Vòng quét THẬT SỰ thấy dữ liệu, để regex hỏng thì test đỏ chứ không xanh giả.

Logic soi tách thành hàm nhận chuỗi CSS để thử được trên CSS mẫu.

Chạy:
    .venv/Scripts/python.exe tests/python/test_design_tokens.py
"""
import re

from _paths import ROOT  # noqa: E402

DASH = ROOT / "dashboard"
TOKENS_FILE = DASH / "surface-tokens.css"

# Giá trị chuẩn, chép từ bảng quy đổi trong plans/design-system/PLAN.md.
EXPECTED = {
    "--mm-fs-badge": "10px", "--mm-fs-12": "12px", "--mm-fs-13": "13px", "--mm-fs-14": "14px",
    "--mm-fs-16": "16px", "--mm-fs-20": "20px", "--mm-fs-24": "24px", "--mm-fs-32": "32px",
    "--mm-r-chip": "8px", "--mm-r-btn": "12px", "--mm-r-field": "16px", "--mm-r-card": "22px",
    "--mm-r-pill": "999px",
    "--mm-sp-1": "4px", "--mm-sp-2": "8px", "--mm-sp-3": "12px", "--mm-sp-4": "16px",
    "--mm-sp-6": "24px", "--mm-sp-8": "32px", "--mm-sp-12": "48px",
}

# Các file đã chuẩn hoá ở Phase 04. Thêm file mới vào đây khi nó được quy đổi.
NORMALIZED = [
    "style.css", "console.css", "noi-mem.css", "minmin-galaxy.css", "minmin-workspace.css",
    "file-shelf.css", "cua-chinh.css", "conversation-ops.css", "office3d.css", "app-theme.css",
]

MAX_LIST = 15

_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
# Khai báo token: `--ten: giá trị;` (giá trị dừng ở ; hoặc }).
_DECL = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}]*)")
# Thuộc tính font-size thật (không bắt đuôi của custom property kiểu --chip-font-size).
_FONT_SIZE = re.compile(r"(?<![\w-])font-size\s*:\s*([^;}]*)", re.I)
# Mọi biến thể bo góc: border-radius, border-top-left-radius, border-start-end-radius...
_RADIUS = re.compile(r"(?<![\w-])(border(?:-[a-z]+)*-radius)\s*:\s*([^;}]*)", re.I)
_PX = re.compile(r"(?<![\w.#-])(\d*\.?\d+)px\b", re.I)
_TOKEN_REF = re.compile(r"var\(\s*(--mm-(?:fs|r)-[A-Za-z0-9_-]*)")


def strip_comments(css: str) -> str:
    """Chú thích được phép nhắc số cũ để giải thích, đó không phải giá trị đang chạy."""
    return _COMMENT.sub("", css)


def declared_tokens(css: str) -> dict:
    """{tên token: giá trị} khai trong một chuỗi CSS (khai sau đè khai trước)."""
    return {k: v.strip() for k, v in _DECL.findall(strip_comments(css))}


def font_size_violations(css: str) -> list:
    """Các giá trị font-size còn số px trong khoảng 10 <= N < 30."""
    out = []
    for value in _FONT_SIZE.findall(strip_comments(css)):
        for num in _PX.findall(value):
            if 10 <= float(num) < 30:
                out.append(f"font-size: {value.strip()}")
                break
    return out


def radius_violations(css: str) -> list:
    """Các giá trị *-radius còn số px >= 5 (0 và 2-4px được phép)."""
    out = []
    for prop, value in _RADIUS.findall(strip_comments(css)):
        for num in _PX.findall(value):
            if float(num) >= 5:
                out.append(f"{prop}: {value.strip()}")
                break
    return out


def token_refs(css: str) -> list:
    """Mọi tên token --mm-fs-* / --mm-r-* được tham chiếu qua var()."""
    return _TOKEN_REF.findall(strip_comments(css))


def _fmt(items: list) -> str:
    if not items:
        return "không có"
    shown = items[:MAX_LIST]
    more = f" ... và {len(items) - MAX_LIST} chỗ nữa" if len(items) > MAX_LIST else ""
    return "\n    " + "\n    ".join(shown) + more


def main() -> None:
    fails = []

    def check(name: str, condition: bool) -> None:
        print(("PASS: " if condition else "FAIL: ") + name)
        if not condition:
            fails.append(name.split("\n")[0])

    # --- 1. Token khai đủ và đúng giá trị -----------------------------------------
    check("có file dashboard/surface-tokens.css", TOKENS_FILE.is_file())
    tokens = declared_tokens(TOKENS_FILE.read_text(encoding="utf-8")) if TOKENS_FILE.is_file() else {}
    missing = sorted(k for k in EXPECTED if k not in tokens)
    check(f"surface-tokens.css khai đủ {len(EXPECTED)} token cỡ chữ/bo góc/khoảng cách (thiếu: {missing})",
          not missing)
    wrong = sorted(f"{k}={tokens[k]} (cần {v})" for k, v in EXPECTED.items()
                   if k in tokens and tokens[k] != v)
    check(f"giá trị token khớp bảng trong PLAN.md (sai: {wrong})", not wrong)

    # --- 2. Các file CSS đã chuẩn hoá -----------------------------------------------
    fs_bad, r_bad, unknown, refs_total = [], [], [], 0
    known = set(tokens)
    for name in NORMALIZED:
        path = DASH / name
        check(f"có file dashboard/{name}", path.is_file())
        if not path.is_file():
            continue
        css = path.read_text(encoding="utf-8")
        fs_bad += [f"{name}: {v}" for v in font_size_violations(css)]
        r_bad += [f"{name}: {v}" for v in radius_violations(css)]
        refs = token_refs(css)
        refs_total += len(refs)
        unknown += sorted({f"{name}: {r}" for r in refs if r not in known})

    check(f"không còn font-size px trong khoảng 10-29 ({len(fs_bad)} chỗ):{_fmt(fs_bad)}", not fs_bad)
    check(f"không còn bo góc px >= 5 ({len(r_bad)} chỗ):{_fmt(r_bad)}", not r_bad)
    check(f"mọi var(--mm-fs-*)/var(--mm-r-*) là token có thật (gõ nhầm):{_fmt(unknown)}", not unknown)

    # --- 3. Vòng quét thật sự thấy dữ liệu ------------------------------------------
    check(f"vòng quét THẬT SỰ thấy token (đếm được {refs_total} lần dùng, cần > 100)", refs_total > 100)

    if fails:
        raise SystemExit(f"\nFAIL - test_design_tokens: {len(fails)} lỗi")
    print("\nOK - test_design_tokens: tất cả pass")


if __name__ == "__main__":
    main()
