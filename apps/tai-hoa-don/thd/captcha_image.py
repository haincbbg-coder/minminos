# -*- coding: utf-8 -*-
"""
captcha_image.py - Chuyển captcha SVG của cổng thuế thành PNG để hiện trong Tkinter.
Thử lần lượt: resvg_py -> cairosvg -> svglib+reportlab. Không có thư viện nào
thì trả None (giao diện sẽ mở captcha bằng trình duyệt).
"""
from __future__ import annotations

import base64
import re
from typing import Optional


def normalize_svg(content: str) -> str:
    """content có thể là SVG thô hoặc data:image/svg+xml;base64,..."""
    c = (content or "").strip()
    m = re.match(r"data:image/svg\+xml;base64,(.*)", c, re.S)
    if m:
        c = base64.b64decode(m.group(1)).decode("utf-8", "ignore")
    elif c.startswith("data:image/svg+xml,"):
        from urllib.parse import unquote
        c = unquote(c[len("data:image/svg+xml,"):])
    return c


def svg_to_png(svg: str, width: int = 240) -> Optional[bytes]:
    svg = normalize_svg(svg)
    # 1) resvg (Rust, có wheel Windows) - khuyến nghị
    try:
        import resvg_py  # type: ignore
        try:
            data = resvg_py.svg_to_bytes(svg_string=svg, width=width)
        except TypeError:
            data = resvg_py.svg_to_bytes(svg, width=width)
        return bytes(data) if data else None
    except Exception:
        pass
    # 2) cairosvg
    try:
        import cairosvg  # type: ignore
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)
    except Exception:
        pass
    # 3) svglib + reportlab
    try:
        import io
        from svglib.svglib import svg2rlg  # type: ignore
        from reportlab.graphics import renderPM  # type: ignore
        drawing = svg2rlg(io.StringIO(svg))
        if drawing is None:
            return None
        scale = width / max(drawing.width, 1)
        drawing.scale(scale, scale)
        drawing.width, drawing.height = drawing.width * scale, drawing.height * scale
        buf = io.BytesIO()
        renderPM.drawToFile(drawing, buf, fmt="PNG")
        return buf.getvalue()
    except Exception:
        pass
    return None
