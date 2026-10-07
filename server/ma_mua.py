"""ma_mua.py - MÃ MUA cho món CÓ PHÍ trên kệ hàng (26.10.104).

MinMin không thu tiền. Người bán thu tiền theo cách của mình (chuyển khoản...), rồi cấp cho khách
một MÃ MUA. Mã chỉ mở đúng món đó, cho đúng MÁY của khách, tới đúng hạn.

Hình dạng mã:   MMB1.<payload base64url>.<chữ ký base64url>
payload (JSON): v=1, mon (id món trên kệ, hoặc "*" = mọi món có phí), mua (vân tay máy người mua),
                kh (tên khách, để người bán nhận ra), het_han ("YYYY-MM-DD" hoặc null), so (số sê-ri).
Chữ ký: khoá RIÊNG của máy người bán (danh_tinh), nên chỉ máy bán mới cấp được, và máy bán tự
kiểm được mà không cần hỏi ai.

Vì sao gắn VÂN TAY MÁY MUA chứ không phát mã trơn: mã trơn là mã dán lên nhóm Zalo là ai cũng tải.
Ở đây mỗi lần tải, máy mua phải KÝ yêu cầu bằng khoá riêng của chính nó (header X-MinMin-Khoa /
X-MinMin-Luc / X-MinMin-Ky phủ đường dẫn + thời điểm). Máy bán kiểm: chữ ký đúng, vân tay khoá đó
khớp `mua` trong mã, thời điểm lệch không quá 10 phút. Lộ mã mà không có khoá riêng của máy mua
thì mã vô dụng.

Thu hồi: người bán bấm thu hồi theo số sê-ri; máy bán từ chối mã đó từ lượt sau, kể cả cập nhật.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import threading
import time
from datetime import date, datetime
from pathlib import Path

import danh_tinh

try:
    from config import STATE_DIR
except Exception:
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

TIEN_TO = "MMB1."
LECH_GIAY = 600
_LOCK = threading.RLock()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def chuan_van_tay(s: str) -> str:
    t = re.sub(r"[^0-9A-Fa-f]", "", str(s or "")).upper()
    return "-".join(t[i:i + 4] for i in range(0, 16, 4)) if len(t) == 16 else ""


# ─────────────────────────── BÊN BÁN ───────────────────────────

def _so_ban() -> Path:
    return Path(STATE_DIR) / "ma-mua-da-cap.json"


def _doc_json(p: Path, mac_dinh):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, type(mac_dinh)) else mac_dinh
    except Exception:
        return mac_dinh


def _ghi_json(p: Path, d, mode=0o644) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(tmp, mode)
    except OSError:
        pass
    os.replace(tmp, p)


def cap_ma(mon: str, mua_van_tay: str, kh: str = "", het_han: str = "") -> dict:
    """Cấp mã mua. het_han: 'YYYY-MM-DD' hoặc '' (vĩnh viễn). Trả {ma, so, ...}."""
    vt = chuan_van_tay(mua_van_tay)
    if not vt:
        raise ValueError("Vân tay máy người mua phải có dạng XXXX-XXXX-XXXX-XXXX")
    if mon != "*" and not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", str(mon or "")):
        raise ValueError("Món không hợp lệ")
    hh = None
    if str(het_han or "").strip():
        try:
            hh = date.fromisoformat(str(het_han).strip()).isoformat()
        except ValueError:
            raise ValueError("Hạn phải có dạng YYYY-MM-DD")
    payload = {"v": 1, "mon": mon, "mua": vt, "kh": " ".join(str(kh or "").split())[:60], "het_han": hh,
               "so": secrets.token_hex(6), "tao": int(time.time())}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sig = base64.b64decode(danh_tinh.ky(raw))
    ma = TIEN_TO + _b64(raw) + "." + _b64(sig)
    with _LOCK:
        ds = _doc_json(_so_ban(), [])
        ds.append(dict(payload, thu_hoi=False, ma=ma))   # giữ mã để người bán chép lại khi khách lỡ mất
        _ghi_json(_so_ban(), ds[-2000:], 0o600)
    return dict(payload, ma=ma)


def danh_sach_da_cap() -> list:
    return list(reversed(_doc_json(_so_ban(), [])))


def thu_hoi(so: str) -> bool:
    with _LOCK:
        ds = _doc_json(_so_ban(), [])
        for x in ds:
            if x.get("so") == so:
                x["thu_hoi"] = True
                _ghi_json(_so_ban(), ds, 0o600)
                return True
    return False


def doc_ma(ma: str):
    """Payload của một mã DO CHÍNH MÁY NÀY cấp (kiểm chữ ký bằng khoá công khai của mình), hoặc None."""
    s = str(ma or "").strip()
    if not s.startswith(TIEN_TO) or len(s) > 2000:
        return None
    try:
        p64, s64 = s[len(TIEN_TO):].split(".", 1)
        raw, sig = _unb64(p64), _unb64(s64)
    except Exception:
        return None
    if not danh_tinh.xac_minh(danh_tinh.cong_khai(), raw, base64.b64encode(sig).decode()):
        return None
    try:
        p = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return p if isinstance(p, dict) and p.get("v") == 1 else None


def thong_diep(duong: str, luc: str) -> bytes:
    return f"minmin-mua|{duong}|{luc}".encode("utf-8")


def kiem_yeu_cau(mon_id: str, duong: str, ma: str, khoa_mua: str, luc: str, ky: str) -> str:
    """'' = cho tải. Ngược lại là mã lỗi: can_ma | ma_sai | sai_mon | het_han | thu_hoi | sai_may | sai_gio."""
    if not ma:
        return "can_ma"
    p = doc_ma(ma)
    if not p:
        return "ma_sai"
    if p.get("mon") not in ("*", mon_id):
        return "sai_mon"
    if p.get("het_han"):
        try:
            if date.today() > date.fromisoformat(p["het_han"]):
                return "het_han"
        except ValueError:
            return "ma_sai"
    if any(x.get("so") == p.get("so") and x.get("thu_hoi") for x in _doc_json(_so_ban(), [])):
        return "thu_hoi"
    try:
        if abs(time.time() - int(luc)) > LECH_GIAY:
            return "sai_gio"
    except (TypeError, ValueError):
        return "sai_gio"
    if danh_tinh.van_tay(khoa_mua) != p.get("mua"):
        return "sai_may"
    if not danh_tinh.xac_minh(khoa_mua, thong_diep(duong, luc), ky):
        return "sai_may"
    return ""


# ─────────────────────────── BÊN MUA ───────────────────────────

def _so_mua() -> Path:
    return Path(STATE_DIR) / "ma-mua-cua-toi.json"


def luu_ma_cua_toi(host: str, mon_id: str, ma: str) -> None:
    """Máy mua nhớ mã để những lần tải sau (cập nhật) tự gửi kèm. Quyền 600: mã là thứ đã trả tiền."""
    with _LOCK:
        d = _doc_json(_so_mua(), {})
        d[f"{str(host).lower()}|{mon_id}"] = str(ma).strip()
        _ghi_json(_so_mua(), d, 0o600)


def ma_cua_toi(host: str, mon_id: str) -> str:
    return str(_doc_json(_so_mua(), {}).get(f"{str(host).lower()}|{mon_id}") or "")


def dau_yeu_cau(duong: str, ma: str) -> dict:
    """Header máy mua gửi kèm một lượt tải món có phí: mã + khoá công khai + chữ ký thời điểm."""
    luc = str(int(time.time()))
    return {"X-MinMin-Ma-Mua": ma, "X-MinMin-Khoa": danh_tinh.cong_khai(), "X-MinMin-Luc": luc,
            "X-MinMin-Ky": danh_tinh.ky(thong_diep(duong, luc))}


def han_hien(p: dict) -> str:
    return p.get("het_han") or ""


def nhan_ngay(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y")
    except Exception:
        return ""
