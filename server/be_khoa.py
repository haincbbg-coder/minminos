"""be_khoa.py - BỂ KHOÁ XOAY VÒNG cho các nhà cung cấp API (26.10.161, mượn ý credential pool
của Hermes Agent).

Vì sao: một khoá OpenRouter/OpenAI/Anthropic API/Gemini/Groq có hạn mức riêng (TPM, RPM, hạn
ngày). Chủ có nhiều khoá CHÍNH CHỦ (nhiều tài khoản API, nhiều dự án Google) thì một lượt vấp
429 nên chuyển sang khoá khác ngay, thay vì ngồi chờ cửa sổ hạn mức trôi qua.

CHỈ cho nhà cung cấp dùng API KEY. KHÔNG áp cho gói thuê bao (Claude Code, ChatGPT qua Codex,
Grok Build, Antigravity): xoay nhiều tài khoản thuê bao để lách hạn mức là vi phạm điều khoản
của Anthropic/OpenAI/xAI và có thể bị khoá tài khoản; MinMin không làm việc đó.

Cách dùng:
  - settings `model.be_khoa = {"openrouter": ["sk-..", "sk-.."], "gemini": [...]}`; khoá chính
    (`model.openrouter_key`...) luôn đứng đầu danh sách, không cần ghi lại.
  - `Xoay(prov, keys)`: `.khoa()` trả khoá đang dùng; `.loi(ev)` nhận sự kiện lỗi của engine
    (có `ma` = HTTP status) để đưa khoá đó vào thời gian nghỉ và chuyển sang khoá kế.
  - Trạng thái nghỉ nằm trong process (dict có khoá), kèm thống kê để trang Models hiện.

Thuần stdlib. Không bao giờ in khoá ra log: mọi nơi chỉ dùng `nhan()` = 4 ký tự cuối.
"""
from __future__ import annotations

import threading
import time
from typing import Iterable, Optional

API_CO_BE = ("openrouter", "openai", "anthropic-api", "gemini", "groq", "xai", "meta", "ollama", "openai-compat")

# Nghỉ bao lâu theo loại lỗi (giây). 429: ít nhất một cửa sổ hạn mức ngắn; sai khoá thì nghỉ
# lâu để không đập mãi vào tường, nhưng không vĩnh viễn (chủ có thể vừa nạp tiền).
NGHI_429 = 60
NGHI_SAI_KHOA = 3600
NGHI_QUOTA_HET = 900
NGHI_TOI_DA = 6 * 3600

_LOCK = threading.Lock()
# (prov, key) -> {"nghi_den": ts, "loi": n, "dung": n, "ly_do": str}
_TRANG_THAI: dict = {}
_LUOT: dict = {}     # prov -> con trỏ xoay vòng


def nhan(key: str) -> str:
    """Nhãn an toàn của một khoá: 4 ký tự cuối."""
    k = str(key or "")
    return ("…" + k[-4:]) if len(k) >= 4 else "…"


def danh_sach(prov: str, mcfg: dict, khoa_chinh: str = "") -> list:
    """Khoá chính + khoá dự phòng trong settings, bỏ trùng và rỗng, giữ thứ tự."""
    ra = []
    for k in [khoa_chinh] + list(((mcfg or {}).get("be_khoa") or {}).get(prov) or []):
        k = str(k or "").strip()
        if k and k not in ra and k not in ("local", "none"):
            ra.append(k)
    return ra


def _tt(prov: str, key: str) -> dict:
    return _TRANG_THAI.setdefault((prov, key), {"nghi_den": 0.0, "loi": 0, "dung": 0, "ly_do": ""})


def dang_nghi(prov: str, key: str, now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    with _LOCK:
        return _tt(prov, key)["nghi_den"] > now


def chon(prov: str, keys: Iterable[str], tranh: Iterable[str] = (), now: Optional[float] = None) -> str:
    """Khoá nên dùng lúc này: đang không nghỉ, xoay vòng cho đều; tất cả đều nghỉ thì lấy khoá
    hết nghỉ sớm nhất (vẫn còn hơn không gọi)."""
    keys = [k for k in keys if k]
    if not keys:
        return ""
    if len(keys) == 1:
        return keys[0]
    now = time.time() if now is None else now
    tranh = set(tranh or ())
    with _LOCK:
        bat_dau = _LUOT.get(prov, 0) % len(keys)
        thu_tu = keys[bat_dau:] + keys[:bat_dau]
        for k in thu_tu:
            if k in tranh:
                continue
            if _tt(prov, k)["nghi_den"] <= now:
                _LUOT[prov] = (keys.index(k) + 1) % len(keys)
                _tt(prov, k)["dung"] += 1
                return k
        # tất cả đang nghỉ (hoặc bị tránh): chọn khoá hết nghỉ sớm nhất
        k = min(keys, key=lambda x: _tt(prov, x)["nghi_den"])
        _tt(prov, k)["dung"] += 1
        return k


def bao_loi(prov: str, key: str, ma: Optional[int] = None, cho: Optional[float] = None,
            ly_do: str = "", now: Optional[float] = None) -> float:
    """Ghi nhận khoá vừa lỗi; trả số giây khoá đó phải nghỉ (0 = lỗi không thuộc về khoá)."""
    now = time.time() if now is None else now
    try:
        ma = int(ma) if ma is not None else None
    except (TypeError, ValueError):
        ma = None
    if ma == 429:
        nghi = max(float(cho or 0), NGHI_429)
    elif ma in (401, 403):
        nghi = NGHI_SAI_KHOA
    elif ma == 402 or "quota" in (ly_do or "").lower() or "insufficient" in (ly_do or "").lower():
        nghi = NGHI_QUOTA_HET
    else:
        return 0.0
    with _LOCK:
        t = _tt(prov, key)
        t["loi"] += 1
        # lỗi lặp lại thì nghỉ dài dần, có trần
        nghi = min(NGHI_TOI_DA, nghi * (2 ** min(4, max(0, t["loi"] - 1))))
        t["nghi_den"] = max(t["nghi_den"], now + nghi)
        t["ly_do"] = (ly_do or f"HTTP {ma}")[:120]
    return nghi


def bao_ok(prov: str, key: str) -> None:
    """Gọi thành công: xoá đếm lỗi để lần vấp sau không bị nghỉ dài oan."""
    with _LOCK:
        _tt(prov, key)["loi"] = 0


class Xoay:
    """Bộ xoay cho MỘT lượt gọi: giữ danh sách khoá, khoá đang dùng, các khoá đã vấp."""

    def __init__(self, prov: str, keys: Iterable[str]):
        self.prov = prov
        self.keys = [k for k in keys if k]
        self.da_vap: list = []
        self.hien = chon(prov, self.keys) if self.keys else ""

    def khoa(self) -> str:
        return self.hien

    def con_khoa_khac(self) -> bool:
        return len(self.keys) > 1 and any(k not in self.da_vap for k in self.keys if k != self.hien)

    def loi(self, ev: dict) -> bool:
        """Nhận sự kiện lỗi. Trả True nếu đã CHUYỂN sang khoá khác (lượt sau nên gọi lại ngay)."""
        if not self.hien:
            return False
        ma = (ev or {}).get("ma")
        nghi = bao_loi(self.prov, self.hien, ma, (ev or {}).get("cho"), str((ev or {}).get("content") or ""))
        if nghi <= 0:
            return False
        self.da_vap.append(self.hien)
        if not self.con_khoa_khac():
            return False
        self.hien = chon(self.prov, self.keys, tranh=self.da_vap)
        return bool(self.hien) and self.hien not in self.da_vap

    def ok(self) -> None:
        if self.hien:
            bao_ok(self.prov, self.hien)


def thong_ke(mcfg: dict, khoa_chinh_cua=None) -> dict:
    """Cho trang Models: mỗi nhà có bao nhiêu khoá, khoá nào đang nghỉ (nhãn 4 ký tự cuối)."""
    now = time.time()
    ra = {}
    for prov in API_CO_BE:
        chinh = ""
        try:
            chinh = khoa_chinh_cua(prov) if khoa_chinh_cua else ""
        except Exception:
            chinh = ""
        keys = danh_sach(prov, mcfg, chinh)
        if len(keys) <= 1 and not ((mcfg or {}).get("be_khoa") or {}).get(prov):
            continue
        with _LOCK:
            dong = []
            for k in keys:
                t = _tt(prov, k)
                dong.append({"nhan": nhan(k), "nghi_con_giay": max(0, int(t["nghi_den"] - now)),
                             "loi": t["loi"], "dung": t["dung"], "ly_do": t["ly_do"]})
        ra[prov] = {"so_khoa": len(keys), "khoa": dong}
    return ra


def xoa_trang_thai() -> None:
    with _LOCK:
        _TRANG_THAI.clear()
        _LUOT.clear()
