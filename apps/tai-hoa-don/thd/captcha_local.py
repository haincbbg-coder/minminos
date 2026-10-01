# -*- coding: utf-8 -*-
"""
captcha_local.py - Lớp OCR CỤC BỘ (miễn phí, chạy ngay trên máy) để giải captcha ẢNH.

Mục đích: giảm phí dịch vụ. Với captcha ảnh đơn giản (tracuunnt, EasyInvoice, Viettel...)
phần mềm thử ĐỌC bằng model offline trước; chỉ khi đọc sai / không chắc mới gọi
2Captcha/OmoCaptcha (mất tiền). reCAPTCHA v2 (BKAV) KHÔNG đọc cục bộ được - vẫn qua dịch vụ.

Ưu tiên engine:
  1) ddddocr  - model ONNX gói sẵn, không cần cài binary ngoài, chạy tốt trên Windows.
  2) pytesseract - nếu máy đã cài Tesseract (dự phòng).

Không có engine nào -> available() = False, phần mềm tự dùng dịch vụ trả phí như cũ.
"""
from __future__ import annotations

import io
import re
from typing import Optional

_ocr = None          # ddddocr.DdddOcr (nạp 1 lần, dùng lại)
_engine = None       # "ddddocr" | "tesseract" | None
_probed = False


def _probe():
    """Nạp engine OCR (lazy). Chỉ chạy 1 lần cho cả phiên."""
    global _ocr, _engine, _probed
    if _probed:
        return
    _probed = True
    # 1) ddddocr
    try:
        import ddddocr  # type: ignore
        _ocr = ddddocr.DdddOcr(show_ad=False, beta=False)
        _engine = "ddddocr"
        return
    except Exception:
        _ocr = None
    # 2) pytesseract
    try:
        import pytesseract  # type: ignore  # noqa
        from PIL import Image  # noqa
        _engine = "tesseract"
        return
    except Exception:
        _engine = None


def available() -> bool:
    """Có engine OCR cục bộ dùng được không."""
    _probe()
    return _engine is not None


def engine_name() -> Optional[str]:
    _probe()
    return _engine


def _clean(text: str, digits_only: bool = False) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", "", t)
    if digits_only:
        t = re.sub(r"\D+", "", t)
    else:
        t = re.sub(r"[^0-9A-Za-z]+", "", t)
    return t


def _preprocess(image_bytes: bytes) -> bytes:
    """Làm sạch nhẹ: xám hoá + nhị phân + phóng to. Giúp model đọc chuẩn hơn.
    Lỗi/không có Pillow -> trả nguyên ảnh gốc."""
    try:
        from PIL import Image, ImageOps, ImageFilter  # type: ignore
        im = Image.open(io.BytesIO(image_bytes)).convert("L")
        # phóng to nếu ảnh nhỏ (captcha cổng thuế thường ~120x40)
        if im.width < 200:
            scale = max(2, 200 // max(im.width, 1))
            im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
        im = ImageOps.autocontrast(im)
        im = im.filter(ImageFilter.MedianFilter(3))
        # nhị phân hoá theo ngưỡng
        im = im.point(lambda p: 255 if p > 140 else 0)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        return image_bytes


def recognize(image_bytes: bytes, expect_len: int = 0,
              digits_only: bool = False, preprocess: bool = True) -> str:
    """Đọc captcha ảnh -> chuỗi ký tự. Trả "" nếu không đọc được / không chắc.

    expect_len: nếu > 0 và kết quả có độ dài khác -> coi như KHÔNG chắc (trả "").
    digits_only: chỉ giữ chữ số (captcha tracuunnt hay là số).
    """
    _probe()
    if _engine is None or not image_bytes:
        return ""
    candidates = []
    if preprocess:
        candidates.append(_preprocess(image_bytes))
    candidates.append(image_bytes)  # thử cả ảnh gốc

    best = ""
    for data in candidates:
        raw = ""
        try:
            if _engine == "ddddocr" and _ocr is not None:
                raw = _ocr.classification(data)
            elif _engine == "tesseract":
                import pytesseract  # type: ignore
                from PIL import Image  # type: ignore
                cfg = "--psm 8 -c tessedit_char_whitelist=0123456789" if digits_only \
                    else "--psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                raw = pytesseract.image_to_string(Image.open(io.BytesIO(data)), config=cfg)
        except Exception:
            raw = ""
        val = _clean(raw, digits_only=digits_only)
        if not val:
            continue
        if expect_len and len(val) != expect_len:
            # sai độ dài -> giữ tạm làm dự phòng, ưu tiên cái đúng độ dài
            if not best:
                best = ""      # không nhận vì sai độ dài
            continue
        return val
    return best
