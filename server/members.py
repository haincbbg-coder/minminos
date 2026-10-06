"""Thành viên được mời: đăng nhập bằng email + mật khẩu riêng, 2FA BẮT BUỘC.

Thiết kế fail-closed:
- Phiên thành viên nằm ở kho RIÊNG (không phải config.SESSIONS) nên `valid_session` luôn False
  với họ: mọi cổng quản trị cũ (middleware, WebSocket, token...) tự từ chối, không cần sửa từng chỗ.
- Phiên có cờ `full`: chỉ true sau khi qua 2FA. Chưa full thì chỉ vào được /m/2fa/*.
- Quyền theo từng brain: "view" hoặc "edit". Không có trong danh sách = không thấy.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time

import config as cfgmod
import secrets_store
import totp

_LOCK = threading.RLock()
_PATH = cfgmod.STATE_DIR / "users.json"
_SESS_PATH = cfgmod.STATE_DIR / ".member_sessions.json"
_TTL = 7 * 24 * 3600
MAT_KHAU_TOI_THIEU = 8
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = ("view", "edit")


def _doc() -> dict:
    try:
        d = json.loads(_PATH.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("users"), dict):
            return d
    except Exception:
        pass
    return {"users": {}}


def _ghi(d: dict) -> None:
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except Exception:
        pass
    tmp.replace(_PATH)


def chuan_email(email: str) -> str:
    return str(email or "").strip().lower()


def _sach_grants(grants) -> dict:
    out = {}
    if isinstance(grants, dict):
        for k, v in grants.items():
            k = str(k or "").strip()
            if k and v in ROLES and "/" not in k and "\\" not in k and not k.startswith("."):
                out[k] = v
    return out


def _bam(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


def _cong_khai(u: dict) -> dict:
    return {"email": u["email"], "name": u.get("name", ""), "grants": u.get("grants", {}),
            "disabled": bool(u.get("disabled")), "tfa": bool(u.get("tfa_enabled")),
            "created": u.get("created", 0), "last_login": u.get("last_login", 0)}


def danh_sach() -> list:
    with _LOCK:
        return [_cong_khai(u) for u in _doc()["users"].values()]


def lay(email: str):
    with _LOCK:
        return _doc()["users"].get(chuan_email(email))


def tao(email: str, name: str, password: str, grants=None) -> dict:
    email = chuan_email(email)
    if not _EMAIL_RE.match(email):
        raise ValueError("Email không hợp lệ")
    if len(password or "") < MAT_KHAU_TOI_THIEU:
        raise ValueError(f"Mật khẩu tối thiểu {MAT_KHAU_TOI_THIEU} ký tự")
    with _LOCK:
        d = _doc()
        if email in d["users"]:
            raise ValueError("Email này đã có")
        h, salt = cfgmod.hash_password(password)
        d["users"][email] = {"email": email, "name": str(name or "").strip()[:80],
                             "hash": h, "salt": salt, "grants": _sach_grants(grants),
                             "disabled": False, "tfa_enabled": False, "tfa_secret": "",
                             "recovery": [], "tfa_step": 0, "created": time.time(),
                             "last_login": 0}
        _ghi(d)
        return _cong_khai(d["users"][email])


def sua(email: str, *, name=None, grants=None, disabled=None, password=None, reset_2fa=False) -> dict:
    email = chuan_email(email)
    with _LOCK:
        d = _doc()
        u = d["users"].get(email)
        if not u:
            raise KeyError("Không có thành viên này")
        if name is not None:
            u["name"] = str(name).strip()[:80]
        if grants is not None:
            u["grants"] = _sach_grants(grants)
        if disabled is not None:
            u["disabled"] = bool(disabled)
        if password:
            if len(password) < MAT_KHAU_TOI_THIEU:
                raise ValueError(f"Mật khẩu tối thiểu {MAT_KHAU_TOI_THIEU} ký tự")
            u["hash"], u["salt"] = cfgmod.hash_password(password)
        if reset_2fa:
            u.update({"tfa_enabled": False, "tfa_secret": "", "recovery": [], "tfa_step": 0})
        _ghi(d)
        if disabled or password or reset_2fa:
            dong_phien(email)
        return _cong_khai(u)


def xoa(email: str) -> bool:
    email = chuan_email(email)
    with _LOCK:
        d = _doc()
        if email not in d["users"]:
            return False
        del d["users"][email]
        _ghi(d)
    dong_phien(email)
    return True


def kiem_mat_khau(email: str, password: str):
    """Trả bản ghi user nếu đúng mật khẩu và chưa bị khóa. Luôn tốn thời gian băm như nhau."""
    u = lay(email)
    h, _ = cfgmod.hash_password(password or "", (u or {}).get("salt") or "0" * 32)
    if not u or u.get("disabled") or not hmac.compare_digest(h, u.get("hash", "")):
        return None
    return u


# ---- 2FA ----
_CHO: dict = {}      # email -> (secret, ts), chờ xác nhận, chỉ trong RAM
_CHO_TTL = 15 * 60


def tfa_bat_dau(email: str, ten_workspace: str = "MinMin OS") -> dict:
    email = chuan_email(email)
    secret = totp.sinh_secret()
    _CHO[email] = (secret, time.time())
    uri = totp.otpauth_uri(secret, email, ten_workspace)
    return {"secret": secret, "uri": uri, "qr_svg": totp.qr_svg(uri)}


def tfa_bat(email: str, code: str):
    """Xác nhận mã đầu tiên để BẬT 2FA. Trả danh sách mã khôi phục, hoặc None nếu mã sai."""
    email = chuan_email(email)
    cho = _CHO.get(email)
    if not cho or time.time() - cho[1] > _CHO_TTL:
        return None
    buoc = totp.kiem(cho[0], code)
    if buoc is None:
        return None
    ma = totp.sinh_ma_khoi_phuc()
    with _LOCK:
        d = _doc()
        u = d["users"].get(email)
        if not u:
            return None
        u.update({"tfa_enabled": True, "tfa_secret": secrets_store.encrypt(cho[0]),
                  "recovery": [_bam(totp.chuan_hoa_ma_khoi_phuc(m)) for m in ma],
                  "tfa_step": buoc})
        _ghi(d)
    _CHO.pop(email, None)
    return ma


def tfa_kiem(email: str, code: str) -> bool:
    """Mã 6 số (mỗi bước dùng một lần) hoặc mã khôi phục (dùng một lần)."""
    email = chuan_email(email)
    with _LOCK:
        d = _doc()
        u = d["users"].get(email)
        if not u or not u.get("tfa_enabled"):
            return False
        secret = secrets_store.decrypt(u.get("tfa_secret", ""))
        buoc = totp.kiem(secret, code, buoc_da_dung=int(u.get("tfa_step") or 0))
        if buoc is not None:
            u["tfa_step"] = buoc
            _ghi(d)
            return True
        h = _bam(totp.chuan_hoa_ma_khoi_phuc(code))
        if h in (u.get("recovery") or []):
            u["recovery"].remove(h)
            _ghi(d)
            return True
    return False


# ---- Phiên (kho riêng) ----
def _doc_phien() -> dict:
    try:
        d = json.loads(_SESS_PATH.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ghi_phien(d: dict) -> None:
    try:
        _SESS_PATH.write_text(json.dumps(d), encoding="utf-8")
        _SESS_PATH.chmod(0o600)
    except Exception:
        pass


def tao_phien(email: str, full: bool) -> str:
    t = secrets.token_urlsafe(32)
    with _LOCK:
        d = _doc_phien()
        now = time.time()
        d = {k: v for k, v in d.items() if now - v.get("ts", 0) < _TTL}
        d[_bam(t)] = {"email": chuan_email(email), "ts": now, "full": bool(full)}
        _ghi_phien(d)
        dd = _doc()
        if chuan_email(email) in dd["users"]:
            dd["users"][chuan_email(email)]["last_login"] = now
            _ghi(dd)
    return t


def phien(token: str):
    """Trả {'email', 'full', 'user'} nếu phiên còn hạn và user còn hoạt động, ngược lại None."""
    if not token:
        return None
    with _LOCK:
        d = _doc_phien()
        p = d.get(_bam(token))
        if not p or time.time() - p.get("ts", 0) > _TTL:
            return None
        u = lay(p["email"])
        if not u or u.get("disabled"):
            return None
        return {"email": p["email"], "full": bool(p.get("full")) and bool(u.get("tfa_enabled")), "user": u}


def nang_phien(token: str) -> None:
    with _LOCK:
        d = _doc_phien()
        p = d.get(_bam(token))
        if p:
            p["full"] = True
            _ghi_phien(d)


def dong_phien(email: str = "", token: str = "") -> None:
    with _LOCK:
        d = _doc_phien()
        if token:
            d.pop(_bam(token), None)
        if email:
            e = chuan_email(email)
            d = {k: v for k, v in d.items() if v.get("email") != e}
        _ghi_phien(d)
