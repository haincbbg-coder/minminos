"""Tự soi Node.js của máy: thiếu bản vá bảo mật mới nhất thì nhắc trong chuông Tin tức (26.10.310).

Claude Code, Codex và mọi MCP chạy bằng npx đều chạy trên Node.js của chính máy, nên một lỗ hổng
Node.js chạm tới tất cả. Ảnh Docker ghim sẵn một bản đã vá; cài thẳng trên máy (Windows, Mac, VPS
không Docker) thì dùng Node.js bố tự cài, MinMin không tự nâng được (cần sudo, Homebrew, winget).
Nên module này so `node --version` với bản vá đầu tiên của từng dòng còn hỗ trợ, ghi một dòng vào
nhật ký lúc khởi động, và dựng MỘT tin trong chuông nói rõ cần làm gì.

Đợt vá hiện tại: Node.js 21/10/2026, 10 lỗ hổng, có CVE-2026-111497 (bộ giải nén Brotli ghi tràn,
chạy mã từ xa qua fetch() và zlib). Đợt vá sau: sửa `BAN_VA`, `DOT_VA_*` cùng chỗ ghim trong
Dockerfile và install.sh (tests/python/test_kiem_node.py canh ba chỗ khớp nhau).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time

DOT_VA_ID = "security-nodejs-2026-10"
DOT_VA_NGAY = "2026-10-21"
DOT_VA_URL = "https://nodejs.org/en/blog/vulnerability/october-2026-security-releases"

# Bản vá đầu tiên của mỗi dòng còn hỗ trợ. Dòng cũ hơn (20 trở xuống) và dòng lẻ dưới dòng mới nhất đã
# hết hỗ trợ, không có bản vá nào.
BAN_VA = {22: (22, 23, 4), 24: (24, 22, 1), 26: (26, 12, 1)}
BAN_DOCKER = "22.23.4"

_GIU_GIAY = 600
_nho = {"luc": 0.0, "ban": None}


def doc_phien_ban(text):
    """'v22.12.0' -> (22, 12, 0). None nếu không phải dòng phiên bản Node.js."""
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", str(text or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def xep_loai(ban) -> str:
    """on (đã vá hoặc không có Node) | thieu_va (dòng còn hỗ trợ, chưa vá) | het_ho_tro."""
    if not ban:
        return "on"
    if ban[0] > max(BAN_VA):
        return "on"
    san = BAN_VA.get(ban[0])
    if san is None:
        return "het_ho_tro"
    return "on" if tuple(ban) >= san else "thieu_va"


def phien_ban_node():
    """Phiên bản của `node` trên PATH, nhớ 10 phút. None khi máy không có Node.js.
    Chặn (gọi tiến trình con): từ event loop thì gọi qua asyncio.to_thread."""
    bay_gio = time.monotonic()
    if _nho["luc"] and bay_gio - _nho["luc"] < _GIU_GIAY:
        return _nho["ban"]
    ban = None
    node = shutil.which("node")
    if node:
        try:
            from winproc import kwargs_no_window
            ra = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5,
                                **kwargs_no_window())
            ban = doc_phien_ban(ra.stdout)
        except (OSError, subprocess.SubprocessError, ImportError):
            ban = None
    _nho.update({"luc": bay_gio, "ban": ban})
    return ban


def _cach_sua(che_do: str) -> str:
    if che_do == "docker":
        return (f"Cập nhật MinMin lên bản mới nhất (nút Cập nhật, hoặc ./update.sh trên VPS). "
                f"Ảnh Docker mới đã có Node.js {BAN_DOCKER}.")
    if che_do == "windows":
        return ("Mở PowerShell chạy: winget upgrade OpenJS.NodeJS.LTS (hoặc tải bản LTS ở nodejs.org), "
                "hoặc chạy lại install.ps1. Xong thì khởi động lại MinMin.")
    return ("Cài Node.js 22.23.4, 24.22.1, 26.12.1 hoặc mới hơn, ví dụ: brew upgrade node (Mac), "
            "sudo apt-get install --only-upgrade nodejs (Ubuntu dùng NodeSource), nvm install 22. "
            "Hoặc chạy lại install.sh. Xong thì khởi động lại MinMin.")


def tin_canh_bao(ban, che_do: str):
    """Tin trong chuông cho máy này, hoặc None khi Node.js đã vá hoặc máy không có Node.js."""
    loai = xep_loai(ban)
    if loai == "on":
        return None
    hien = "v" + ".".join(str(x) for x in ban)
    if loai == "het_ho_tro":
        tom = (f"Máy đang chạy Node.js {hien}. Dòng này đã hết hỗ trợ nên không có bản vá cho 10 lỗ hổng "
               "công bố ngày 21/10/2026, trong đó có lỗi Brotli cho phép chạy mã từ xa.")
    else:
        tom = (f"Máy đang chạy Node.js {hien}, chưa có bản vá ngày 21/10/2026 cho 10 lỗ hổng, trong đó có "
               "lỗi Brotli cho phép chạy mã từ xa.")
    return {
        "id": f"{DOT_VA_ID}:{hien}",
        "kind": "security",
        "title": "Node.js trên máy cần cập nhật bản vá bảo mật",
        "summary": tom,
        "body": "Claude Code, Codex và các MCP chạy bằng npx đều dùng Node.js này. " + _cach_sua(che_do),
        "published_at": DOT_VA_NGAY,
        "expires_at": "",
        "priority": "high",
        "cta": {"label": "Xem thông báo của Node.js →", "url": DOT_VA_URL},
    }


def tu_soi_khi_khoi_dong(che_do: str) -> str:
    """Soi một lần lúc server khởi động, in một dòng vào nhật ký khi thiếu vá. Trả loại để test đọc."""
    ban = phien_ban_node()
    loai = xep_loai(ban)
    if loai != "on":
        hien = "v" + ".".join(str(x) for x in ban)
        print(f"[node] Node.js {hien} {'đã hết hỗ trợ' if loai == 'het_ho_tro' else 'thiếu bản vá ' + DOT_VA_NGAY}. "
              + _cach_sua(che_do), file=sys.stderr)
    return loai
