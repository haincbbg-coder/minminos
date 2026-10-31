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

26.10.270 (Thứ tự dùng): bể khoá thành DANH SÁCH ĐÁNH SỐ hiện trên thẻ ở trang Bộ não AI.
  - `model.be_khoa[prov]` = [{"id", "ten", "bat"}] theo thứ tự dùng, gồm cả khoá 1.
  - Chất liệu khoá nằm ở `model.be_khoa_ma[id]` (mã hoá như mọi secret, xem config._SECRET_PATHS).
  - Trường cũ (`openrouter_key`...) luôn bằng khoá BẬT đầu tiên, để giọng nói, team, Lark... vẫn
    đọc trường cũ như trước.
  - Cài đặt cũ (danh sách chuỗi) được `chuyen_doi` đổi một lần, chạy lại không nhân đôi.
  - Chọn khoá theo THỨ TỰ: dùng khoá 1 tới khi hết lượt mới sang khoá 2, khoá 1 hồi thì quay lại.
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Iterable, Optional

import nha_api_rieng   # thuần stdlib như module này

# DeepSeek/Qwen/GLM/MiniMax có bể khoá như mọi nhà API. Lưu ý gói Coding Plan: xoay nhiều tài
# khoản GÓI để lách hạn mức có thể trái điều khoản của hãng y như gói thuê bao - bể khoá dành
# cho nhiều key trả theo lượng chính chủ.
API_CO_BE = ("openrouter", "openai", "anthropic-api", "gemini", "groq", "xai", "meta", "ollama", "openai-compat",
             *nha_api_rieng.IDS)

# Nghỉ bao lâu theo loại lỗi (giây). 429: ít nhất một cửa sổ hạn mức ngắn; sai khoá thì nghỉ
# lâu để không đập mãi vào tường, nhưng không vĩnh viễn (chủ có thể vừa nạp tiền).
NGHI_429 = 60
NGHI_SAI_KHOA = 3600
NGHI_QUOTA_HET = 900
NGHI_TOI_DA = 6 * 3600

_LOCK = threading.Lock()
# (prov, key) -> {"nghi_den": ts, "loi": n, "dung": n, "ly_do": str}
_TRANG_THAI: dict = {}
_LUOT: dict = {}     # (giữ tên cho mã cũ; từ 26.10.270 không còn xoay vòng đều)
_DANG_DUNG: dict = {}   # prov -> khoá vừa được chọn, để thẻ tô "đang dùng"


def nhan(key: str) -> str:
    """Nhãn an toàn của một khoá: 4 ký tự cuối."""
    k = str(key or "")
    return ("…" + k[-4:]) if len(k) >= 4 else "…"


def _ma_id(prov: str, so: int) -> str:
    """Id ổn định cho khoá thứ `so` của một nhà lúc chuyển đổi (chạy lại ra cùng id)."""
    return "k_" + hashlib.sha1(f"{prov}#{so}".encode("utf-8")).hexdigest()[:10]


def id_moi() -> str:
    return "k_" + hashlib.sha1(f"{time.time_ns()}".encode("utf-8")).hexdigest()[:10]


def _la_dang_cu(lst) -> bool:
    return isinstance(lst, list) and any(isinstance(x, str) for x in lst)


def muc(mcfg: dict, prov: str, key_field: str = "") -> list:
    """Danh sách khoá ĐÁNH SỐ của một nhà: [{"id", "ten", "bat", "khoa"}] theo thứ tự dùng.

    Cài đặt chưa chuyển đổi vẫn đọc ra đúng: khoá ở trường cũ là khoá 1, các chuỗi trong bể cũ
    là khoá 2, 3... (cùng id mà `chuyen_doi` sẽ ghi, nên trang không nhảy khi file được đổi)."""
    m = mcfg or {}
    lst = (m.get("be_khoa") or {}).get(prov)
    if isinstance(lst, list) and lst and not _la_dang_cu(lst):
        ma = m.get("be_khoa_ma") or {}
        ra = []
        for a in lst:
            if isinstance(a, dict) and a.get("id"):
                ra.append({"id": str(a["id"]), "ten": str(a.get("ten") or ""),
                           "bat": a.get("bat") is not False, "khoa": str(ma.get(a["id"]) or "")})
        return ra
    ra, thay = [], []
    for k in [m.get(key_field) if key_field else ""] + list(lst or []):
        k = str(k or "").strip()
        if k and k not in thay and k not in ("local", "none"):
            thay.append(k)
            ra.append({"id": _ma_id(prov, len(ra)), "ten": "", "bat": True, "khoa": k})
    return ra


def luu_muc(mcfg: dict, prov: str, ds: list, key_field: str = "") -> None:
    """Ghi danh sách khoá của một nhà (thứ tự, tên, bật/tắt, khoá) và đồng bộ trường cũ = khoá bật
    đầu tiên. Khoá của mục bị gỡ cũng bị xoá khỏi kho mã."""
    ma = mcfg.setdefault("be_khoa_ma", {})
    truoc = {a["id"]: a["khoa"] for a in muc(mcfg, prov, key_field)}
    sach = []
    for a in ds or []:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        aid = str(a["id"])
        k = str(a.get("khoa") or "").strip() or truoc.get(aid, "")
        if not k:
            continue
        sach.append({"id": aid, "ten": str(a.get("ten") or "")[:40], "bat": a.get("bat") is not False})
        ma[aid] = k
    be = mcfg.get("be_khoa")
    if not isinstance(be, dict):
        be = mcfg["be_khoa"] = {}
    be[prov] = sach
    for gone in set(truoc) - {a["id"] for a in sach}:
        ma.pop(gone, None)
        with _LOCK:
            _TRANG_THAI.pop((prov, truoc[gone]), None)
    if key_field:
        dau = next((a for a in sach if a["bat"]), None)
        mcfg[key_field] = ma[dau["id"]] if dau else ""


def chuyen_doi(mcfg: dict, key_fields: dict) -> bool:
    """Đổi bể khoá kiểu cũ (danh sách chuỗi, khoá chính để riêng) sang danh sách đánh số.
    Chạy lại an toàn: nhà đã ở dạng mới thì không đụng. Trả True khi có đổi."""
    doi = False
    for prov, kf in (key_fields or {}).items():
        lst = (mcfg.get("be_khoa") or {}).get(prov)
        if isinstance(lst, list) and lst and not _la_dang_cu(lst):
            continue
        if not lst and not (kf and mcfg.get(kf)):
            continue
        luu_muc(mcfg, prov, muc(mcfg, prov, kf), kf)
        doi = True
    return doi


def danh_sach(prov: str, mcfg: dict, khoa_chinh: str = "") -> list:
    """Các khoá ĐANG BẬT theo thứ tự dùng, bỏ trùng và rỗng. Khoá chính (trường cũ) đứng đầu
    khi danh sách chưa có nó - với cài đặt mới thì nó chính là khoá bật đầu tiên."""
    ra = []
    m = mcfg or {}
    lst = (m.get("be_khoa") or {}).get(prov)
    if isinstance(lst, list) and lst and not _la_dang_cu(lst):
        ma = m.get("be_khoa_ma") or {}
        tat = {str(ma.get(a.get("id")) or "") for a in lst if isinstance(a, dict) and a.get("bat") is False}
        nguon = [khoa_chinh] + [ma.get(a.get("id")) for a in lst
                                if isinstance(a, dict) and a.get("bat") is not False]
    else:
        tat = set()
        nguon = [khoa_chinh] + list(lst or [])
    for k in nguon:
        k = str(k or "").strip()
        if k and k not in ra and k not in tat and k not in ("local", "none"):
            ra.append(k)
    return ra


def _tt(prov: str, key: str) -> dict:
    return _TRANG_THAI.setdefault((prov, key), {"nghi_den": 0.0, "loi": 0, "dung": 0, "ly_do": ""})


def dang_nghi(prov: str, key: str, now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    with _LOCK:
        return _tt(prov, key)["nghi_den"] > now


def chon(prov: str, keys: Iterable[str], tranh: Iterable[str] = (), now: Optional[float] = None) -> str:
    """Khoá nên dùng lúc này: khoá ĐẦU TIÊN theo thứ tự đang không nghỉ (26.10.270: dùng khoá 1 tới
    khi hết lượt mới sang khoá 2, không chia đều từng câu); tất cả đều nghỉ thì lấy khoá hết nghỉ
    sớm nhất (vẫn còn hơn không gọi)."""
    keys = [k for k in keys if k]
    if not keys:
        return ""
    now = time.time() if now is None else now
    tranh = set(tranh or ())
    with _LOCK:
        k = next((x for x in keys if x not in tranh and _tt(prov, x)["nghi_den"] <= now), None)
        if k is None:
            # tất cả đang nghỉ (hoặc bị tránh): chọn khoá hết nghỉ sớm nhất
            k = min(keys, key=lambda x: _tt(prov, x)["nghi_den"])
        _tt(prov, k)["dung"] += 1
        _DANG_DUNG[prov] = k
        return k


def con_khoa_dung_duoc(prov: str, mcfg: dict, khoa_chinh: str = "", now: Optional[float] = None) -> bool:
    """Nhà này còn ít nhất một khoá bật mà không nghỉ không (chat dùng để né nhà hết lượt)."""
    now = time.time() if now is None else now
    keys = danh_sach(prov, mcfg, khoa_chinh)
    with _LOCK:
        return any(_tt(prov, k)["nghi_den"] <= now for k in keys)


def nghi_den(prov: str, key: str) -> float:
    """Epoch khoá này được thử lại (0 = đang không nghỉ)."""
    with _LOCK:
        t = _TRANG_THAI.get((prov, key))
        until = float(t["nghi_den"]) if t else 0.0
    return until if until > time.time() else 0.0


def dang_dung(prov: str, keys: Iterable[str]) -> str:
    """Khoá được chọn gần nhất nếu còn trong danh sách; chưa gọi lần nào thì khoá chat sẽ chọn."""
    keys = [k for k in keys if k]
    with _LOCK:
        k = _DANG_DUNG.get(prov)
    if k in keys and not nghi_den(prov, k):
        return k
    now = time.time()
    with _LOCK:
        return next((x for x in keys if _tt(prov, x)["nghi_den"] <= now), "")


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
        t = _tt(prov, key)
        t["loi"] = 0
        t["nghi_den"] = 0.0    # vừa gọi được thì chắc chắn không còn nghỉ


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
        if len(keys) <= 1 and len(((mcfg or {}).get("be_khoa") or {}).get(prov) or []) <= 1:
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
        _DANG_DUNG.clear()
