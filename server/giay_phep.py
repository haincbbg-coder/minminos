"""Giấy phép các ứng dụng KẾT NỐI NGOÀI của MinMin (26.10.3).

Kết nối ngoài là mục chứa các app nhà phát hành tự làm (Zalo Forwarder, Tải Hoá Đơn, Quét hoá
đơn Gmail, Điều khiển máy tính...). Mỗi app phải MỞ KHOÁ bằng một mã kích hoạt mới chạy.

Mã kích hoạt là một gói dữ liệu KÝ SỐ Ed25519:

    MM1.<payload base64url>.<chữ ký base64url>

payload (JSON) gồm:
    v          1
    kh         tên khách (hiện ra trên trang, để khách biết mã của ai)
    ung_dung   danh sách id app được mở, hoặc ["*"] = mọi app
    may        mã máy của bản MinMin được phép dùng, hoặc "*" = máy nào cũng được
    het_han    "YYYY-MM-DD" (hết ngày đó thì khoá lại) hoặc null = vĩnh viễn
    tao        ngày tạo mã
    ghi_chu    tuỳ chọn (gói, số MST...)

Vì sao ký số chứ không hỏi máy chủ: MinMin chạy trên máy của khách (VPS, máy Windows), có khi
không ra được mạng. Mã tự chứng minh được mình thật bằng KHOÁ CÔNG KHAI nằm sẵn trong mã nguồn,
không cần gọi về đâu. Chỉ người giữ KHOÁ RIÊNG mới tạo được mã.

KHOÁ RIÊNG chỉ nằm trên máy của nhà phát hành:
    python server/giay_phep.py tao-khoa
sinh cặp khoá, cất khoá riêng vào `<STATE_DIR>/giay-phep/khoa-rieng.pem` (quyền 600) và in khoá
công khai ra để dán vào `KHOA_CONG_KHAI` dưới đây. Máy có khoá riêng là MÁY NHÀ PHÁT HÀNH: mọi app
tự mở và trang Kết nối ngoài có thêm khung tạo mã cho khách.

Giới hạn phải nói thật: MinMin phân phối dạng mã nguồn Python, người rành code vẫn sửa được để bỏ
qua bước kiểm. Giấy phép ở đây là hàng rào cho người dùng bình thường và căn cứ pháp lý (điều
khoản sử dụng), không phải chống bẻ khoá tuyệt đối.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Optional

try:
    from config import STATE_DIR
except Exception:   # chạy rời làm công cụ dòng lệnh
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

# Khoá công khai của nhà phát hành (base64 của 32 byte Ed25519). Nhiều khoá được phép để đổi
# khoá mà không làm hỏng mã đã bán. Rỗng = chưa phát hành: chỉ máy nhà phát hành dùng được app.
KHOA_CONG_KHAI: tuple = (
    # Khoá nhà phát hành TrungKienHa, sinh trên VPS minmin.elaria.cloud ngày 2026-10-01.
    "sM24Bejp9GZqvy08mFa2xb6tgfxW1TzJK/PXvfIW5zk=",
)

TIEN_TO = "MM1."
_KHOA = threading.Lock()

# Các app trong Kết nối ngoài. `san_sang=False`: app đang được chuyển lên web, thẻ hiện "Sắp ra
# mắt" và chưa mở được kể cả khi đã có mã (mã vẫn kích hoạt trước được).
UNG_DUNG = (
    {"id": "zalo_forwarder", "icon": "send", "san_sang": True, "dieu_khoan_rieng": "zalo",
     "duong_dan": "/apps/zalo-forwarder/"},
    {"id": "tai_hoa_don", "icon": "file-text", "san_sang": True, "dieu_khoan_rieng": "",
     "duong_dan": "/apps/tai-hoa-don/"},
    {"id": "quet_hoa_don_gmail", "icon": "mail", "san_sang": True, "dieu_khoan_rieng": "",
     "duong_dan": "/apps/tai-hoa-don/?tab=gmail"},
    {"id": "dieu_khien_may", "icon": "hand", "san_sang": False, "dieu_khoan_rieng": "dieu_khien"},
)
ID_UNG_DUNG = tuple(u["id"] for u in UNG_DUNG)


def _thu_muc() -> Path:
    p = Path(STATE_DIR) / "giay-phep"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    s = str(s or "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------------------------------------------------------- mã máy

def ma_may() -> str:
    """Mã của BẢN CÀI MinMin này (không phải phần cứng): sinh ngẫu nhiên một lần, cất trong
    STATE_DIR. Khách gửi mã này cho nhà phát hành để nhận mã kích hoạt khoá theo máy."""
    f = _thu_muc() / "ma-may.txt"
    with _KHOA:
        try:
            v = f.read_text(encoding="utf-8").strip()
            if len(v) >= 12:
                return v
        except OSError:
            pass
        v = "MM-" + hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:16].upper()
        f.write_text(v, encoding="utf-8")
        return v


# ---------------------------------------------------------------- khoá

def _khoa_rieng_path() -> Path:
    return _thu_muc() / "khoa-rieng.pem"


def _doc_khoa_rieng():
    from cryptography.hazmat.primitives import serialization
    p = _khoa_rieng_path()
    if not p.is_file():
        return None
    try:
        return serialization.load_pem_private_key(p.read_bytes(), password=None)
    except Exception as e:
        print(f"[giay-phep] khoá riêng hỏng: {e}", file=sys.stderr)
        return None


def la_nha_phat_hanh() -> bool:
    """Máy này giữ khoá riêng (máy của nhà phát hành)."""
    return _doc_khoa_rieng() is not None


def _khoa_cong_khai_tin_cay() -> list:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization
    ds = []
    for k in KHOA_CONG_KHAI:
        try:
            ds.append(Ed25519PublicKey.from_public_bytes(base64.b64decode(k)))
        except Exception:
            pass
    # Máy nhà phát hành tin chính khoá của mình (để thử mã vừa tạo trước khi gửi khách).
    kr = _doc_khoa_rieng()
    if kr is not None:
        ds.append(kr.public_key())
    return ds


def tao_cap_khoa(ghi_de: bool = False) -> str:
    """Sinh cặp khoá Ed25519, cất khoá riêng, trả khoá công khai base64. Không ghi đè khoá cũ
    (mất khoá cũ là mọi mã đã bán thành vô hiệu) trừ khi `ghi_de`."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    p = _khoa_rieng_path()
    if p.exists() and not ghi_de:
        kr = _doc_khoa_rieng()
    else:
        kr = Ed25519PrivateKey.generate()
        p.write_bytes(kr.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    pub = kr.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(pub).decode("ascii")


# ---------------------------------------------------------------- tạo / kiểm mã

def tao_ma(khach: str, ung_dung, may: str = "*", het_han: Optional[str] = None,
           ghi_chu: str = "") -> str:
    """Tạo mã kích hoạt. Chỉ chạy được trên máy giữ khoá riêng."""
    kr = _doc_khoa_rieng()
    if kr is None:
        raise ValueError("máy này không có khoá riêng của nhà phát hành")
    ds = [u for u in (ung_dung or []) if u == "*" or u in ID_UNG_DUNG]
    if not ds:
        raise ValueError("chưa chọn ứng dụng nào")
    if het_han:
        datetime.strptime(str(het_han), "%Y-%m-%d")      # ném ValueError nếu sai định dạng
    payload = {"v": 1, "kh": str(khach or "").strip()[:80] or "Khách", "ung_dung": ds,
               "may": str(may or "*").strip()[:40] or "*", "het_han": het_han or None,
               "tao": date.today().isoformat(), "ghi_chu": str(ghi_chu or "").strip()[:200]}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return TIEN_TO + _b64e(raw) + "." + _b64e(kr.sign(raw))


def doc_ma(ma: str) -> dict:
    """Kiểm chữ ký và trả payload. Ném ValueError với lý do đọc được nếu mã hỏng."""
    ma = "".join(str(ma or "").split())
    if not ma.startswith(TIEN_TO) or ma.count(".") != 2:
        raise ValueError("mã không đúng định dạng (phải bắt đầu bằng MM1.)")
    _, p, s = ma.split(".")
    try:
        raw, sig = _b64d(p), _b64d(s)
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("mã bị cắt hoặc chép thiếu")
    ok = False
    for k in _khoa_cong_khai_tin_cay():
        try:
            k.verify(sig, raw)
            ok = True
            break
        except Exception:
            continue
    if not ok:
        raise ValueError("chữ ký không hợp lệ: mã không phải do nhà phát hành cấp")
    if payload.get("v") != 1:
        raise ValueError("phiên bản mã không hỗ trợ")
    may = payload.get("may") or "*"
    if may != "*" and may != ma_may():
        raise ValueError(f"mã này cấp cho máy {may}, không phải máy này ({ma_may()})")
    return payload


def _con_han(payload: dict, hom_nay: Optional[date] = None) -> bool:
    hh = payload.get("het_han")
    if not hh:
        return True
    try:
        return (hom_nay or date.today()) <= datetime.strptime(hh, "%Y-%m-%d").date()
    except ValueError:
        return False


# ---------------------------------------------------------------- kho mã đã kích hoạt

def _kho_path() -> Path:
    return _thu_muc() / "ma-da-kich-hoat.json"


def _doc_kho() -> list:
    try:
        d = json.loads(_kho_path().read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def kich_hoat(ma: str) -> dict:
    """Kiểm và lưu một mã. Trả payload. Mã đã có thì không lưu trùng."""
    payload = doc_ma(ma)
    if not _con_han(payload):
        raise ValueError(f"mã đã hết hạn ngày {payload.get('het_han')}")
    ma = "".join(str(ma).split())
    with _KHOA:
        ds = _doc_kho()
        if ma not in ds:
            ds.append(ma)
            _kho_path().write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload


def go_ma(ma: str) -> bool:
    ma = "".join(str(ma or "").split())
    with _KHOA:
        ds = _doc_kho()
        if ma not in ds:
            return False
        ds.remove(ma)
        _kho_path().write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def quyen(hom_nay: Optional[date] = None) -> dict:
    """{id_app: {"mo": bool, "het_han": str|None, "kh": str, "ma_cuoi": "...xxxx"}}.

    Nhiều mã cùng mở một app thì lấy mã còn hạn xa nhất (vĩnh viễn thắng mọi mốc)."""
    ra = {u: {"mo": False, "het_han": None, "kh": "", "ma_cuoi": "", "het_han_roi": False} for u in ID_UNG_DUNG}
    if la_nha_phat_hanh():
        for u in ra.values():
            u.update(mo=True, kh="Nhà phát hành")
        return ra
    for ma in _doc_kho():
        try:
            p = doc_ma(ma)
        except ValueError:
            continue
        ds = ID_UNG_DUNG if "*" in (p.get("ung_dung") or []) else p.get("ung_dung") or []
        con = _con_han(p, hom_nay)
        for u in ds:
            if u not in ra:
                continue
            cu = ra[u]
            if not con:
                if not cu["mo"]:
                    cu.update(het_han=p.get("het_han"), kh=p.get("kh") or "", het_han_roi=True)
                continue
            moi = p.get("het_han")
            hon = (not cu["mo"]) or (cu["het_han"] and (moi is None or moi > cu["het_han"]))
            if hon:
                cu.update(mo=True, het_han=moi, kh=p.get("kh") or "", ma_cuoi="..." + ma[-6:],
                          het_han_roi=False)
    return ra


def da_mo(app_id: str) -> bool:
    return bool(quyen().get(app_id, {}).get("mo"))


# ---------------------------------------------------------------- dòng lệnh (máy nhà phát hành)

def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Giấy phép Kết nối ngoài của MinMin")
    sub = ap.add_subparsers(dest="lenh")
    sub.add_parser("tao-khoa", help="sinh cặp khoá nhà phát hành (chỉ làm một lần)")
    t = sub.add_parser("tao-ma", help="tạo mã kích hoạt cho khách")
    t.add_argument("--khach", required=True)
    t.add_argument("--app", default="*", help="id app, cách nhau dấu phẩy, hoặc *")
    t.add_argument("--may", default="*")
    t.add_argument("--het-han", default=None, help="YYYY-MM-DD, bỏ trống = vĩnh viễn")
    t.add_argument("--ghi-chu", default="")
    sub.add_parser("ma-may", help="in mã máy của bản cài này")
    a = ap.parse_args(argv)
    if a.lenh == "tao-khoa":
        print("Khoá công khai (dán vào KHOA_CONG_KHAI trong server/giay_phep.py):")
        print(tao_cap_khoa())
        print(f"Khoá riêng cất ở: {_khoa_rieng_path()}  - GIỮ KÍN, mất là mã đã bán vô hiệu.")
        return 0
    if a.lenh == "tao-ma":
        print(tao_ma(a.khach, [x.strip() for x in a.app.split(",") if x.strip()], a.may, a.het_han, a.ghi_chu))
        return 0
    if a.lenh == "ma-may":
        print(ma_may())
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_main())
