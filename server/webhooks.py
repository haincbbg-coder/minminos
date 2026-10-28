"""Webhook: hệ thống bên ngoài (form landing page, cổng thanh toán, app khác) gọi một đường dẫn
bí mật để MinMin chạy một việc, rồi báo kết quả như nhắc hẹn (26.10.167, học Javis 0.198).

Thiết kế an toàn, theo thứ tự:
  - Mã bí mật nằm trong đường (`/hook/<mã>`), chỉ hiện ĐÚNG MỘT LẦN lúc tạo hoặc đổi mã; sau đó
    kho chỉ giữ băm SHA-256, nên lộ file cũng không dùng lại được.
  - Dữ liệu sự kiện là DỮ LIỆU của người lạ: được bọc và dán nhãn "không phải lệnh" trước khi
    đưa cho AI. Mức quyền mặc định `suggest` (chỉ đọc rồi báo); chủ tự nâng tay.
  - 26.10.273: mỗi lần giao được LƯU bền vào hòm sự kiện (webhook_su_kien) trước khi trả lời,
    chống trùng 24 giờ, bộ lọc, hành động không cần AI (chuyển tiếp), thử lại tự động, kiểm chữ
    ký theo nhà gửi (webhook_ky). Bộ chạy nền ở webhook_chay. Trần 120 lần/giờ: quá trần thì sự
    kiện vẫn được lưu nhưng bị chặn, chủ bấm chạy lại.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

TRAN_MOI_GIO = 120           # quá trần thì sự kiện vẫn được LƯU, chỉ không tự chạy (bị chặn)
TRUNG_GIO_MAC_DINH = 24
THAN_TOI_DA = 64 * 1024
MUC_HOP_LE = ("suggest", "auto", "full")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
_KHOA = threading.RLock()


def _state_dir() -> Path:
    import bien_dong
    return bien_dong._state_dir()


def file_kho() -> Path:
    return _state_dir() / "webhooks.json"


def _doc() -> list:
    try:
        d = json.loads(file_kho().read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _ghi(ds: list) -> None:
    p = file_kho()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    tmp.replace(p)


def _bam(tok: str) -> str:
    return hashlib.sha256(str(tok).encode("utf-8")).hexdigest()


def _dem_gio(wid: str) -> int:
    try:
        import webhook_su_kien
        return webhook_su_kien.dem_gio(wid)
    except Exception:
        return 0


def _cong_khai(w: dict) -> dict:
    """Bản cho giao diện: không bao giờ có băm mã, khoá ký hay đường đầy đủ của nơi chuyển tiếp."""
    import webhook_chay
    xt = dict(w.get("xac_thuc") or {"kieu": "none"})
    xt.pop("khoa", None)
    xt["co_khoa"] = bool((w.get("xac_thuc") or {}).get("khoa"))
    hd = []
    for a in webhook_chay.chuan_hanh_dong(w.get("hanh_dong")):
        a = dict(a)
        if a.get("url"):
            a["url"] = webhook_chay.an_url(a["url"])
        hd.append(a)
    return {"id": w["id"], "ten": w.get("ten", ""), "viec": w.get("viec", ""),
            "muc_quyen": w.get("muc_quyen", "suggest"), "bat": bool(w.get("bat", True)),
            "tam_dung": bool(w.get("tam_dung")), "brain": w.get("brain", "brain"),
            "so_lan": int(w.get("so_lan") or 0), "lan_cuoi": float(w.get("lan_cuoi") or 0),
            "lan_gio": _dem_gio(w["id"]),
            "tran_gio": TRAN_MOI_GIO, "tao_luc": float(w.get("tao_luc") or 0),
            "loc": w.get("loc") or [], "hanh_dong": hd, "xac_thuc": xt,
            "trung_gio": float(w.get("trung_gio") or TRUNG_GIO_MAC_DINH),
            "trung_theo_don": bool(w.get("trung_theo_don"))}


def danh_sach() -> list:
    with _KHOA:
        return [_cong_khai(w) for w in _doc()]


def tao(ten: str, viec: str, muc_quyen: str = "suggest", brain: str = "brain") -> dict:
    """Trả {"webhook": {...}, "token": "<hiện một lần>"}."""
    ten = str(ten or "").strip()[:80]
    viec = str(viec or "").strip()[:1200]
    if not ten:
        raise ValueError("Thiếu tên webhook")
    if not viec:
        raise ValueError("Thiếu việc cần làm khi webhook được gọi")
    mq = str(muc_quyen or "suggest").strip().lower()
    if mq not in MUC_HOP_LE:
        mq = "suggest"
    tok = secrets.token_urlsafe(24)
    w = {"id": "wh_" + uuid.uuid4().hex[:8], "ten": ten, "viec": viec, "muc_quyen": mq,
         "brain": str(brain or "brain"), "bat": True, "bam": _bam(tok), "so_lan": 0,
         "lan_cuoi": 0.0, "tao_luc": time.time(), "hanh_dong": [{"id": "ai", "loai": "ai"}],
         "loc": [], "xac_thuc": {"kieu": "none"}, "trung_gio": TRUNG_GIO_MAC_DINH}
    with _KHOA:
        ds = _doc()
        if len(ds) >= 50:
            raise ValueError("Tối đa 50 webhook")
        ds.append(w)
        _ghi(ds)
    return {"webhook": _cong_khai(w), "token": tok}


def _tim(ds: list, wid: str) -> Optional[dict]:
    return next((w for w in ds if w.get("id") == wid), None)


def doi_token(wid: str) -> Optional[str]:
    with _KHOA:
        ds = _doc()
        w = _tim(ds, wid)
        if not w:
            return None
        tok = secrets.token_urlsafe(24)
        w["bam"] = _bam(tok)
        _ghi(ds)
        return tok


def dat(wid: str, **kw) -> bool:
    """Sửa một webhook. Cấu hình sai ném ValueError (kiểm hết TRƯỚC khi ghi)."""
    import webhook_chay
    import webhook_ky
    import webhook_su_kien as sk
    loc = sk.chuan_loc(kw["loc"]) if kw.get("loc") is not None else None
    hd = webhook_chay.chuan_hanh_dong(kw["hanh_dong"]) if kw.get("hanh_dong") is not None else None
    xt = webhook_ky.chuan_cau_hinh(kw["xac_thuc"]) if kw.get("xac_thuc") is not None else None
    with _KHOA:
        ds = _doc()
        w = _tim(ds, wid)
        if not w:
            return False
        if hd is not None:
            # Giữ nguyên địa chỉ chuyển tiếp cũ khi giao diện gửi lại bản đã che ("https://máy/…").
            cu = {a.get("id"): a for a in (w.get("hanh_dong") or [])}
            for a in hd:
                if a.get("url", "").endswith("/…") and cu.get(a["id"], {}).get("url"):
                    a["url"] = cu[a["id"]]["url"]
            w["hanh_dong"] = hd
        if "bat" in kw and kw["bat"] is not None:
            w["bat"] = bool(kw["bat"])
        if "tam_dung" in kw and kw["tam_dung"] is not None:
            w["tam_dung"] = bool(kw["tam_dung"])
        if kw.get("trung_theo_don") is not None:
            if not isinstance(kw["trung_theo_don"], bool):
                raise ValueError("trung_theo_don phải là true/false")
            w["trung_theo_don"] = kw["trung_theo_don"]
        if kw.get("muc_quyen") in MUC_HOP_LE:
            w["muc_quyen"] = kw["muc_quyen"]
        if kw.get("viec"):
            w["viec"] = str(kw["viec"]).strip()[:1200]
        if kw.get("ten"):
            w["ten"] = str(kw["ten"]).strip()[:80]
        if loc is not None:
            w["loc"] = loc
        if kw.get("trung_gio") is not None:
            try:
                w["trung_gio"] = max(0.0, min(float(kw["trung_gio"]), 168.0))
            except (TypeError, ValueError):
                raise ValueError("trung_gio là số giờ (0 đến 168)")
        if xt is not None:
            cu_khoa = (w.get("xac_thuc") or {}).get("khoa", "")
            moi = str(kw.get("khoa") or "").strip()
            if moi and not 8 <= len(moi) <= 500:
                raise ValueError("khoá ký dài 8 đến 500 ký tự")
            if xt["kieu"] != "none":
                import secrets_store
                xt["khoa"] = secrets_store.encrypt(moi) if moi else cu_khoa
                if not xt["khoa"]:
                    raise ValueError("kiểu xác thực này cần khoá ký của nhà gửi")
            w["xac_thuc"] = xt
        _ghi(ds)
        return True


def lay_day_du(wid: str) -> Optional[dict]:
    """Bản ĐẦY ĐỦ cho bộ chạy nền (không bao giờ đưa ra giao diện)."""
    with _KHOA:
        w = _tim(_doc(), wid)
        return dict(w) if w else None


def khoa_ky(w: dict) -> str:
    """Khoá ký đã giải mã. Chỉ dùng để kiểm chữ ký, không log, không trả ra ngoài."""
    enc = (w.get("xac_thuc") or {}).get("khoa") or ""
    if not enc:
        return ""
    import secrets_store
    return secrets_store.decrypt(enc)


def ghi_nhan_goi(wid: str, now: Optional[float] = None) -> None:
    """Đếm số lần gọi và lần cuối cho dòng tóm tắt."""
    now = now or time.time()
    with _KHOA:
        ds = _doc()
        w = _tim(ds, wid)
        if w:
            w["so_lan"] = int(w.get("so_lan") or 0) + 1
            w["lan_cuoi"] = now
            w.pop("gio", None)
            w.pop("da_thay", None)
            _ghi(ds)


def xoa(wid: str) -> bool:
    with _KHOA:
        ds = _doc()
        moi = [w for w in ds if w.get("id") != wid]
        if len(moi) == len(ds):
            return False
        _ghi(moi)
    try:
        import webhook_su_kien
        webhook_su_kien.xoa_hook(wid)
    except Exception:
        pass
    return True


def tim_theo_token(tok: str) -> Optional[dict]:
    """Webhook ứng với mã trong đường (so thời gian hằng), hoặc None. Không xét bật/tắt."""
    tok = str(tok or "")
    if not TOKEN_RE.match(tok):
        return None
    b = _bam(tok)
    with _KHOA:
        hit = None
        for w in _doc():     # duyệt hết, không dừng sớm: thời gian không lộ vị trí
            if hmac.compare_digest(str(w.get("bam") or "").encode(), b.encode()):
                hit = w
        return dict(hit) if hit else None

