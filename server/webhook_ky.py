"""Kiểm chữ ký webhook theo từng nhà gửi (26.10.273, học nền tảng sự kiện của Javis 0.274).

Hai lớp khoá, theo thứ tự, TRƯỚC khi lưu bất cứ thứ gì:
  1. Mã bí mật trong đường `/hook/<mã>` (webhooks.py, chỉ giữ băm).
  2. Chữ ký của nhà gửi trên THÂN GỐC (cấu hình `xac_thuc` của từng webhook):

    {"kieu": "none"}                                    chỉ mã trong đường (mặc định)
    {"kieu": "hmac_sha256", "header": "X-Signature", "ma_hoa": "hex"|"base64", "tien_to": ""}
    {"kieu": "stripe"}      Stripe-Signature t=..,v1=..  (nhận nhiều v1, cửa sổ 5 phút)
    {"kieu": "github"}      X-Hub-Signature-256: sha256=<hex>; mã lần giao X-GitHub-Delivery
    {"kieu": "shopify"}     X-Shopify-Hmac-Sha256: <base64>; mã lần giao X-Shopify-Event-Id
    {"kieu": "systeme_io"}  X-Webhook-Signature hex (CHƯA kiểm với lần giao thật)

  Thuật toán, tên header và khoá là của webhook, KHÔNG BAO GIỜ do thân yêu cầu chọn.

POSCake/Pancake: lần giao thật Javis bắt được (2026-10-22) chỉ có `content-type` và
`user-agent: mint/1.9.3`, không chữ ký, không header riêng. Nên POSCake dùng mã trong đường
(`none`); MinMin KHÔNG tự bịa thuật toán ký cho nó (`kieu: poscake` bị từ chối khi lưu).

Khoá ký lưu mã hoá (secrets_store, tiền tố `enc:`), không bao giờ trả ra giao diện hay ghi log.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Optional

KIEU = ("none", "hmac_sha256", "stripe", "github", "shopify", "systeme_io")
# `spec`: dựng theo tài liệu công khai của nhà gửi. `chua_kiem`: chưa đối chiếu được với lần giao thật.
TINH_TRANG = {"none": "spec", "hmac_sha256": "spec", "stripe": "spec", "github": "spec",
              "shopify": "spec", "systeme_io": "chua_kiem"}
CUA_SO_S = 300
# Header được LƯU cùng sự kiện: không bao giờ là khoá hay chữ ký.
HEADER_LUU = ("content-type", "user-agent", "x-github-event", "x-github-delivery",
              "x-shopify-topic", "x-shopify-event-id", "x-shopify-webhook-id",
              "x-shopify-shop-domain", "x-webhook-event", "x-webhook-message-id",
              "x-request-id", "idempotency-key", "x-event-id", "x-delivery-id")


class LoiCauHinh(ValueError):
    """Cấu hình xác thực sai (báo lúc lưu)."""


def chuan_cau_hinh(cfg: Any) -> dict:
    """Cấu hình đã chuẩn hoá (chưa gồm khoá) hoặc LoiCauHinh."""
    if cfg in (None, "", {}):
        return {"kieu": "none"}
    if not isinstance(cfg, dict):
        raise LoiCauHinh("xac_thuc phải là object")
    kieu = str(cfg.get("kieu") or "none").strip().lower()
    if kieu in ("poscake", "pancake"):
        raise LoiCauHinh("POSCake chưa công bố cách ký webhook. Dùng mã bí mật trong đường (none).")
    if kieu not in KIEU:
        raise LoiCauHinh("kiểu xác thực là một trong: " + ", ".join(KIEU))
    out = {"kieu": kieu}
    if kieu == "hmac_sha256":
        hdr = str(cfg.get("header") or "").strip()
        if not hdr or len(hdr) > 64 or not all(c.isalnum() or c == "-" for c in hdr):
            raise LoiCauHinh("hmac_sha256 cần tên header chữ ký (chữ, số, dấu -)")
        if hdr.lower() in HEADER_LUU or hdr.lower() in ("authorization", "cookie", "host"):
            raise LoiCauHinh("header chữ ký không được trùng header MinMin lưu lại")
        mh = str(cfg.get("ma_hoa") or "hex").strip().lower()
        if mh not in ("hex", "base64"):
            raise LoiCauHinh("ma_hoa là hex hoặc base64")
        out.update(header=hdr.lower(), ma_hoa=mh, tien_to=str(cfg.get("tien_to") or "")[:20])
    return out


def _h(headers: Any, ten: str) -> str:
    try:
        return str(headers.get(ten) or headers.get(ten.lower()) or "")
    except Exception:
        return ""


def _bang(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8", "replace"), b.encode("utf-8", "replace"))


def _dang_systeme(than: bytes) -> list:
    """Các dạng thân Systeme.io có thể đã ký: thân gốc và hai kiểu json_encode của PHP."""
    out = [bytes(than or b"")]
    try:
        doc = json.loads(bytes(than).decode("utf-8"))
    except Exception:
        return out
    try:
        mac_dinh = json.dumps(doc, ensure_ascii=True, separators=(",", ":")).replace("/", "\\/")
        khong_thoat = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        out += [mac_dinh.encode("utf-8"), khong_thoat.encode("utf-8")]
    except Exception:
        pass
    return out


def _kiem_mot(cfg: dict, khoa: bytes, headers: Any, than: bytes, now: float) -> tuple:
    kieu = cfg.get("kieu")
    if kieu == "stripe":
        phan: dict = {}
        for muc in _h(headers, "stripe-signature").split(","):
            k, _, v = muc.strip().partition("=")
            phan.setdefault(k, []).append(v)
        ts = (phan.get("t") or [""])[0]
        if not ts.isdigit():
            return False, "thiếu hoặc sai Stripe-Signature"
        if abs(now - int(ts)) > CUA_SO_S:
            return False, "chữ ký Stripe quá cũ"
        muon = hmac.new(khoa, ts.encode() + b"." + than, hashlib.sha256).hexdigest()
        return any(_bang(muon, v) for v in phan.get("v1", [])), "chữ ký Stripe không khớp"
    if kieu == "github":
        co = _h(headers, "x-hub-signature-256")
        muon = "sha256=" + hmac.new(khoa, than, hashlib.sha256).hexdigest()
        return bool(co) and _bang(muon, co), "chữ ký GitHub không khớp"
    if kieu == "shopify":
        co = _h(headers, "x-shopify-hmac-sha256")
        muon = base64.b64encode(hmac.new(khoa, than, hashlib.sha256).digest()).decode()
        return bool(co) and _bang(muon, co), "chữ ký Shopify không khớp"
    if kieu == "systeme_io":
        co = _h(headers, "x-webhook-signature").strip().lower()
        if not co:
            return False, "thiếu chữ ký Systeme.io"
        for dang in _dang_systeme(than):
            if _bang(hmac.new(khoa, dang, hashlib.sha256).hexdigest(), co):
                return True, ""
        return False, "chữ ký Systeme.io không khớp"
    if kieu == "hmac_sha256":
        so = hmac.new(khoa, than, hashlib.sha256).digest()
        ma_hex = cfg.get("ma_hoa", "hex") == "hex"
        muon = cfg.get("tien_to", "") + (so.hex() if ma_hex else base64.b64encode(so).decode())
        co = _h(headers, cfg.get("header", "")).strip()
        if ma_hex:
            muon, co = muon.lower(), co.lower()
        return bool(co) and _bang(muon, co), "chữ ký không khớp"
    return False, "kiểu xác thực lạ"


def kiem(cfg: Optional[dict], khoa: str, headers: Any, than: bytes,
         now: Optional[float] = None) -> tuple:
    """(đúng, lý do). Không bao giờ ném lỗi; lý do không bao giờ chứa khoá."""
    cfg = cfg or {}
    if (cfg.get("kieu") or "none") == "none":
        return True, ""
    if not khoa:
        return False, "chưa có khoá ký"
    try:
        return _kiem_mot(cfg, str(khoa).encode("utf-8"), headers, bytes(than or b""),
                         time.time() if now is None else now)
    except Exception as e:
        return False, f"kiểm chữ ký lỗi: {type(e).__name__}"


def ma_lan_giao(kieu: str, headers: Any, doc: Any) -> str:
    """Mã lần giao của chính nhà gửi (ổn định qua các lần họ gửi lại), hoặc ''."""
    d = doc if isinstance(doc, dict) else {}
    if kieu == "stripe":
        v = str(d.get("id") or "")
    elif kieu == "github":
        v = _h(headers, "x-github-delivery")
    elif kieu == "shopify":
        v = _h(headers, "x-shopify-event-id") or _h(headers, "x-shopify-webhook-id")
    elif kieu == "systeme_io":
        v = _h(headers, "x-webhook-message-id")
    else:
        v = ""
    return f"{kieu}:{v}"[:200] if v else ""


def header_luu(headers: Any) -> dict:
    out = {}
    for k in HEADER_LUU:
        v = _h(headers, k)
        if v:
            out[k] = v[:300]
    return out

