"""brain_share.py - LINK CHIA SẺ agent / skill / workflow của một brain cho người khác (26.10.73).

Khác share_store (link xem MỘT file): ở đây link dẫn tới một GÓI .zip của share_bundle, để người
nhận dán link vào MinMin của họ và nhập vào brain của họ.

Ranh giới an toàn, canh bằng tests/python/test_brain_share.py:
  1. CHỈ agent, skill, workflow đi vào gói. Bộ nhớ (memory/), wiki, ghi chú, cài đặt, API key,
     lịch sử chat KHÔNG BAO GIỜ nằm trong gói: build_bundle không có đường nào lấy chúng.
  2. Token 144 bit ngẫu nhiên, có HẠN (mặc định 7 ngày, tối đa 90) và THU HỒI được (xoá là 404).
  3. Skill hệ thống không vào gói (build_bundle đã loại); người nhận tự có bản của họ.
  4. Lúc tải, gói được dựng LẠI từ brain hiện tại theo danh sách slug đã chọn lúc tạo link, nên
     không lưu bản chụp nào ngoài danh sách tên.
"""
import json
import os
import secrets
import threading
import time

from config import STATE_DIR

_LOCK = threading.RLock()
STORE = STATE_DIR / "brain_shares.json"
TRAN = 200
NGAY_MAC_DINH = 7
NGAY_TOI_DA = 90
KINDS = ("agent", "skill", "workflow")


def _doc_tho() -> dict:
    try:
        d = json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def _ghi_tho(d: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STORE)


def tao(brain: str, items: dict, ngay: int = NGAY_MAC_DINH, nhan: str = "", tat_ca: bool = False) -> dict:
    """items: {"agent": [slug...], "skill": [...], "workflow": [...]}. tat_ca = mọi mục lúc tải."""
    sach = {k: [str(s) for s in (items or {}).get(k, []) if str(s).strip()][:200] for k in KINDS}
    if not tat_ca and not any(sach.values()):
        raise ValueError("Chưa chọn mục nào để chia sẻ")
    try:
        ngay = int(ngay)
    except (TypeError, ValueError):
        ngay = NGAY_MAC_DINH
    ngay = max(1, min(NGAY_TOI_DA, ngay))
    with _LOCK:
        d = _doc_tho()
        if len(d) >= TRAN:
            raise ValueError(f"Đã đạt trần {TRAN} link chia sẻ, thu hồi bớt link cũ trước")
        tok = secrets.token_urlsafe(24)
        now = time.time()
        d[tok] = {"brain": str(brain or "brain"), "items": sach, "tat_ca": bool(tat_ca),
                  "nhan": " ".join(str(nhan or "").split())[:120],
                  "tao_luc": now, "het_han": now + ngay * 86400, "tai": 0}
        _ghi_tho(d)
        return dict(d[tok], token=tok)


def doc(token: str):
    """Bản ghi còn HẠN của token, hoặc None (không có / hết hạn / đã thu hồi). Cửa DUY NHẤT của
    đường công khai, nên hết hạn là chết ở đây."""
    tok = str(token or "").strip()
    if not tok or len(tok) > 80:
        return None
    ban = _doc_tho().get(tok)
    if not isinstance(ban, dict) or float(ban.get("het_han") or 0) < time.time():
        return None
    return dict(ban, token=tok)


def ghi_tai(token: str) -> None:
    with _LOCK:
        d = _doc_tho()
        if isinstance(d.get(token), dict):
            d[token]["tai"] = int(d[token].get("tai") or 0) + 1
            _ghi_tho(d)


def xoa(token: str) -> bool:
    tok = str(token or "").strip()
    with _LOCK:
        d = _doc_tho()
        if tok not in d:
            return False
        d.pop(tok, None)
        _ghi_tho(d)
        return True


def danh_sach(brain: str = "") -> list:
    now = time.time()
    ra = [dict(v, token=k, con_han=float(v.get("het_han") or 0) >= now) for k, v in _doc_tho().items()
          if isinstance(v, dict) and (not brain or v.get("brain") == brain)]
    ra.sort(key=lambda x: x.get("tao_luc") or 0, reverse=True)
    return ra
