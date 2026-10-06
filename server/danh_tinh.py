"""danh_tinh.py - DANH TÍNH của một máy chủ MinMin, để gói chia sẻ biết chắc là của ai (26.10.91).

Vì sao cần
----------
Link chia sẻ 26.10.73 chỉ là một token: người nhận tải được gói, nhưng không có cách nào biết gói
đó đúng là của máy chủ ghi trên link, và không biết nó có bị ai sửa dọc đường (máy chủ trung gian,
file .zip chuyển tay qua Zalo, mail) hay không. Một skill hay agent là CHỈ DẪN cho AI chạy thật trên
máy người nhận, nên "ai viết ra nó" là câu hỏi an toàn chứ không phải trang trí.

Cách làm
--------
Mỗi bản MinMin tự sinh MỘT cặp khoá Ed25519 lần đầu cần tới, cất khoá riêng ở
`<STATE_DIR>/danh-tinh/khoa-rieng.pem` (quyền 600). Khoá này KHÁC khoá nhà phát hành ở
giay_phep.py: khoá kia chỉ máy nhà phát hành có và dùng để bán mã kích hoạt; khoá này máy nào cũng
có và chỉ dùng để ký gói mình chia sẻ đi.

Khoá công khai được công bố ở `GET /bs/danh-tinh` (công khai, không cần đăng nhập). Người nhận:
  1. kiểm chữ ký trong gói bằng khoá kèm trong gói (gói không bị sửa sau khi ký),
  2. hỏi lại tên miền đã cho tải gói xem khoá công bố có đúng là khoá đó không (gói đúng là của
     tên miền ấy, không phải ai đó tự ký rồi nói là của minmin.elaria.cloud),
  3. nhớ cặp (tên miền, khoá) lần đầu gặp. Lần sau khoá ĐỔI thì cảnh báo to: hoặc chủ máy đó cài
     lại máy, hoặc có người đang mạo danh. Người dùng tự quyết, nhưng không bao giờ im lặng.

Vân tay (fingerprint) là 16 ký tự hex đầu của sha256(khoá công khai), chia 4 nhóm, để hai người
đọc cho nhau qua điện thoại mà so được bằng mắt.

Module chỉ dùng stdlib + cryptography + config, không import main (tránh vòng import).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from pathlib import Path

try:
    from config import STATE_DIR
except Exception:   # chạy rời (test công cụ)
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

_KHOA = threading.RLock()
_CACHE: dict = {}


def _thu_muc() -> Path:
    return Path(STATE_DIR) / "danh-tinh"


def _file_khoa() -> Path:
    return _thu_muc() / "khoa-rieng.pem"


def _file_thong_tin() -> Path:
    return _thu_muc() / "thong-tin.json"


def _file_da_biet() -> Path:
    return _thu_muc() / "da-biet.json"


def _ghi_nguyen_tu(p: Path, data: bytes, mode: int = 0o644) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(data)
    try:
        os.chmod(tmp, mode)
    except OSError:
        pass
    os.replace(tmp, p)


def _khoa_rieng():
    """Khoá riêng Ed25519 của máy này, tự sinh lần đầu. Không bao giờ rời khỏi máy."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    with _KHOA:
        k = _CACHE.get("khoa")
        if k is not None and _CACHE.get("file") == str(_file_khoa()):
            return k
        p = _file_khoa()
        if p.is_file():
            k = serialization.load_pem_private_key(p.read_bytes(), password=None)
        else:
            k = Ed25519PrivateKey.generate()
            pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
            _ghi_nguyen_tu(p, pem, 0o600)
        _CACHE.update(khoa=k, file=str(p))
        return k


def cong_khai() -> str:
    """Khoá công khai base64 (32 byte)."""
    from cryptography.hazmat.primitives import serialization
    raw = _khoa_rieng().public_key().public_bytes(serialization.Encoding.Raw,
                                                  serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def van_tay(khoa_b64: str = "") -> str:
    """'A1B2-C3D4-E5F6-0718' từ khoá công khai (mặc định: của máy này)."""
    try:
        raw = base64.b64decode(khoa_b64 or cong_khai(), validate=True)
    except Exception:
        return ""
    h = hashlib.sha256(raw).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def ky(data: bytes) -> str:
    return base64.b64encode(_khoa_rieng().sign(bytes(data))).decode()


def xac_minh(khoa_b64: str, data: bytes, chu_ky_b64: str) -> bool:
    """True khi chữ ký đúng. Mọi lỗi định dạng đều là False, không ném."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        raw = base64.b64decode(khoa_b64, validate=True)
        sig = base64.b64decode(chu_ky_b64, validate=True)
        if len(raw) != 32 or len(sig) != 64:
            return False
        Ed25519PublicKey.from_public_bytes(raw).verify(sig, bytes(data))
        return True
    except Exception:
        return False


# ───────────── tên hiển thị (người chia sẻ tự đặt) ─────────────

def _doc_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def ten() -> str:
    return str(_doc_json(_file_thong_tin()).get("ten") or "").strip()


def dat_ten(gia_tri: str) -> str:
    """Tên người/shop chia sẻ hiện trên trang nhận ('Shop HALIMI'). Rỗng = chỉ hiện tên miền."""
    s = " ".join(str(gia_tri or "").split())[:60]
    with _KHOA:
        d = _doc_json(_file_thong_tin())
        d["ten"] = s
        _ghi_nguyen_tu(_file_thong_tin(), json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))
    return s


def cong_bo(app_version: str = "") -> dict:
    """Thứ /bs/danh-tinh trả ra. CHỈ thông tin công khai."""
    k = cong_khai()
    return {"app": "minmin", "v": 1, "khoa": k, "van_tay": van_tay(k), "ten": ten(),
            "phien_ban": app_version}


# ───────────── nhớ tên miền đã gặp (TOFU) ─────────────

def doi_chieu_da_biet(host: str, khoa_b64: str) -> str:
    """'moi' (lần đầu gặp host), 'khop' (đúng khoá đã nhớ), 'doi' (host này từng dùng khoá KHÁC).
    Chỉ ĐỌC, không ghi: ghi chỉ xảy ra khi người dùng thật sự cài (nho_host)."""
    h = str(host or "").strip().lower()
    cu = _doc_json(_file_da_biet()).get(h)
    if not isinstance(cu, dict) or not cu.get("khoa"):
        return "moi"
    return "khop" if cu.get("khoa") == khoa_b64 else "doi"


def nho_host(host: str, khoa_b64: str, ten_hien: str = "") -> None:
    h = str(host or "").strip().lower()
    if not h or not khoa_b64:
        return
    with _KHOA:
        d = _doc_json(_file_da_biet())
        cu = d.get(h) if isinstance(d.get(h), dict) else {}
        now = time.time()
        d[h] = {"khoa": khoa_b64, "van_tay": van_tay(khoa_b64), "ten": str(ten_hien or "")[:60],
                "lan_dau": cu.get("lan_dau") if cu.get("khoa") == khoa_b64 and cu.get("lan_dau") else now,
                "lan_cuoi": now}
        if len(d) > 2000:   # trần cứng: file đọc nguyên khối mỗi lần nhập
            for k in sorted(d, key=lambda x: (d[x] or {}).get("lan_cuoi") or 0)[:len(d) - 2000]:
                d.pop(k, None)
        _ghi_nguyen_tu(_file_da_biet(), json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))


def danh_sach_da_biet() -> list:
    d = _doc_json(_file_da_biet())
    ra = [dict(v, host=k) for k, v in d.items() if isinstance(v, dict)]
    ra.sort(key=lambda x: x.get("lan_cuoi") or 0, reverse=True)
    return ra
