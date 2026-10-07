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

Thêm ở 26.10.92 (Chợ chia sẻ):
  5. MÃ NGẮN `K7Q2X-9XPA3` (10 ký tự, bảng 31 chữ bỏ 0/O/1/I/L dễ đọc nhầm, khoảng 49 bit) để đọc
     qua điện thoại hay gõ tay. Mã chỉ là một tên khác của token, cùng hạn, cùng thu hồi. Đoán mã
     bị chặn ở tầng route bằng giới hạn số lần sai theo IP.
  6. MÃ PIN tuỳ chọn: lưu PBKDF2 (không bao giờ lưu PIN gốc), sai 5 lần trong 15 phút là khoá link
     đó 15 phút. PIN đi bằng header, không bao giờ nằm trong URL.
  7. GIỚI HẠN LƯỢT: `toi_da` = 1 là link dùng một lần. Hết lượt thì `doc()` trả None như hết hạn.
"""
import hashlib
import hmac
import json
import os
import re
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
# Kênh THEO DÕI bản mới (26.10.102): token riêng, sống lâu hơn link (link 7-90 ngày hay dùng một
# lần là để PHÁT; người đã nhận vẫn cần hỏi được bản mới sau đó). Thu hồi link là chết cả hai.
TD_NGAY = 365
BANG_MA = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"   # 31 ký tự, không có 0 O 1 I L
DO_DAI_MA = 10
TOI_DA_LUOT = 1000
_PIN_SAI_TOI_DA = 5
_PIN_KHOA_GIAY = 15 * 60
_PIN_SAI: dict = {}   # token -> [mốc thời gian sai]


def _sinh_ma() -> str:
    return "".join(secrets.choice(BANG_MA) for _ in range(DO_DAI_MA))


def chuan_ma(s: str) -> str:
    """'k7q2x-9xpa3 ' -> 'K7Q2X9XPA3'. Chuỗi không đúng dạng trả ''."""
    t = re.sub(r"[\s-]+", "", str(s or "")).upper()
    return t if len(t) == DO_DAI_MA and all(c in BANG_MA for c in t) else ""


def hien_ma(ma: str) -> str:
    return f"{ma[:5]}-{ma[5:]}" if ma else ""


def _bam_pin(pin: str, muoi: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(muoi), 120_000).hex()


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


def tao(brain: str, items: dict, ngay: int = NGAY_MAC_DINH, nhan: str = "", tat_ca: bool = False,
        pin: str = "", toi_da: int = 0) -> dict:
    """items: {"agent": [slug...], "skill": [...], "workflow": [...]}. tat_ca = mọi mục lúc tải.
    pin: 4-12 ký tự (rỗng = không PIN). toi_da: số lượt tải tối đa (0 = không giới hạn, 1 = một lần)."""
    pin = str(pin or "").strip()
    if pin and not re.fullmatch(r"[A-Za-z0-9]{4,12}", pin):
        raise ValueError("Mã PIN phải gồm 4 đến 12 chữ hoặc số")
    try:
        toi_da = max(0, min(TOI_DA_LUOT, int(toi_da or 0)))
    except (TypeError, ValueError):
        toi_da = 0
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
        dang_dung = {v.get("ma") for v in d.values() if isinstance(v, dict)}
        ma = _sinh_ma()
        while ma in dang_dung:
            ma = _sinh_ma()
        now = time.time()
        d[tok] = {"brain": str(brain or "brain"), "items": sach, "tat_ca": bool(tat_ca),
                  "nhan": " ".join(str(nhan or "").split())[:120],
                  "tao_luc": now, "het_han": now + ngay * 86400, "tai": 0,
                  "ma": ma, "toi_da": toi_da,
                  "td": secrets.token_urlsafe(24), "td_het_han": now + TD_NGAY * 86400}
        if pin:
            muoi = secrets.token_hex(16)
            d[tok]["pin"] = {"muoi": muoi, "bam": _bam_pin(pin, muoi)}
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
    if int(ban.get("toi_da") or 0) and int(ban.get("tai") or 0) >= int(ban.get("toi_da") or 0):
        return None   # link dùng một lần (hoặc N lần) đã hết lượt
    return dict(ban, token=tok)


def tim_ma(ma: str):
    """Bản ghi CÒN DÙNG ĐƯỢC của mã ngắn, hoặc None."""
    m = chuan_ma(ma)
    if not m:
        return None
    for tok, v in _doc_tho().items():
        if isinstance(v, dict) and v.get("ma") == m:
            return doc(tok)
    return None


def co_pin(ban: dict) -> bool:
    return isinstance((ban or {}).get("pin"), dict)


def kiem_pin(ban: dict, pin: str) -> str:
    """'' = cho qua; 'can_pin' = thiếu PIN; 'sai' = sai PIN; 'khoa' = sai quá nhiều, đang khoá."""
    if not co_pin(ban):
        return ""
    tok = ban.get("token", "")
    now = time.time()
    with _LOCK:
        ds = [t for t in _PIN_SAI.get(tok, []) if now - t < _PIN_KHOA_GIAY]
        _PIN_SAI[tok] = ds
        if len(ds) >= _PIN_SAI_TOI_DA:
            return "khoa"
    pin = str(pin or "").strip()
    if not pin:
        return "can_pin"
    p = ban["pin"]
    try:
        dung = hmac.compare_digest(_bam_pin(pin, p["muoi"]), p["bam"])
    except Exception:
        dung = False
    if dung:
        return ""
    with _LOCK:
        _PIN_SAI.setdefault(tok, []).append(now)
    return "sai"


def dam_bao_td(token: str) -> str:
    """Token theo dõi của một link (link tạo trước 26.10.102 chưa có thì sinh lúc tải lần đầu)."""
    with _LOCK:
        d = _doc_tho()
        v = d.get(token)
        if not isinstance(v, dict):
            return ""
        if not v.get("td"):
            v["td"] = secrets.token_urlsafe(24)
            v["td_het_han"] = time.time() + TD_NGAY * 86400
            _ghi_tho(d)
        return v["td"]


def doc_theo_doi(td: str):
    """Bản ghi của token theo dõi, chỉ xét hạn của CHÍNH nó (không xét hạn link hay số lượt)."""
    t = str(td or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", t):
        return None
    for tok, v in _doc_tho().items():
        if isinstance(v, dict) and v.get("td") and hmac.compare_digest(str(v["td"]), t):
            if float(v.get("td_het_han") or 0) < time.time():
                return None
            return dict(v, token=tok)
    return None


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
