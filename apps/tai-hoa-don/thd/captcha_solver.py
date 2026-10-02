# -*- coding: utf-8 -*-
"""
captcha_solver.py - Tự giải captcha qua API dịch vụ (OmoCaptcha, 2Captcha, Anti-Captcha).

Khách đăng ký tài khoản ở một trong các dịch vụ, nạp tiền, lấy API key, điền vào phần mềm
(Cài đặt → Giải captcha). Khi cần giải captcha (tra cứu MST, hóa đơn BKAV...), phần mềm gửi
ảnh/khoá site cho dịch vụ và nhận kết quả - không phải gõ tay.

Cả 3 dịch vụ đều dùng chuẩn Anti-Captcha (createTask + getTaskResult), chỉ khác base URL và
tên "task type". Thêm dịch vụ mới: thêm vào PROVIDERS.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Callable, Optional

PROVIDERS = {
    "2captcha": {
        "label": "2Captcha (2captcha.com)",
        "base": "https://api.2captcha.com",
        "image_type": "ImageToTextTask", "image_field": "body",
        "recaptcha_type": "RecaptchaV2TaskProxyless",
    },
    "omocaptcha": {
        "label": "OmoCaptcha (omocaptcha.com)",
        "base": "https://api.omocaptcha.com/v2",
        "image_type": "ImageToTextTask", "image_field": "imageBase64",
        "recaptcha_type": "RecaptchaV2TokenTask",
    },
    "anticaptcha": {
        "label": "Anti-Captcha (anti-captcha.com)",
        "base": "https://api.anti-captcha.com",
        "image_type": "ImageToTextTask", "image_field": "body",
        "recaptcha_type": "RecaptchaV2TaskProxyless",
    },
}


class CaptchaError(Exception):
    pass


def provider_labels() -> list[tuple[str, str]]:
    return [(k, v["label"]) for k, v in PROVIDERS.items()]


def get_balance(provider: str, api_key: str, timeout: int = 25) -> float:
    """Số dư tài khoản dịch vụ giải captcha (USD). Raise CaptchaError nếu lỗi/không key."""
    if provider not in PROVIDERS:
        raise CaptchaError(f"Chưa hỗ trợ dịch vụ '{provider}'")
    if not api_key:
        raise CaptchaError("Chưa nhập API key")
    s = _session()
    res = _post(s, PROVIDERS[provider]["base"] + "/getBalance", {"clientKey": api_key})
    if res.get("errorId"):
        raise CaptchaError(res.get("errorCode") or res.get("errorDescription") or "lỗi lấy số dư")
    bal = res.get("balance")
    if bal is None:
        raise CaptchaError("Không đọc được số dư")
    return float(bal)


def _session():
    try:
        import requests
        return requests.Session()
    except Exception:
        from .gdt_client import _safe_ca_bundle
        from curl_cffi import requests as cr
        s = cr.Session(impersonate="chrome"); s.verify = _safe_ca_bundle(); return s


def _post(s, url: str, payload: dict) -> dict:
    r = s.post(url, data=json.dumps(payload), timeout=40,
               headers={"Content-Type": "application/json", "Accept": "application/json"})
    if r.status_code != 200:
        raise CaptchaError(f"Dịch vụ captcha trả về HTTP {r.status_code}")
    try:
        return json.loads(r.text)
    except ValueError:
        raise CaptchaError("Dịch vụ captcha trả về dữ liệu không hợp lệ")


def _solve(provider: str, api_key: str, task: dict, want_key: str,
           timeout: int, log: Callable[[str], None]) -> str:
    if provider not in PROVIDERS:
        raise CaptchaError(f"Chưa hỗ trợ dịch vụ '{provider}'")
    if not api_key:
        raise CaptchaError("Chưa nhập API key dịch vụ giải captcha")
    cfg = PROVIDERS[provider]
    s = _session()
    created = _post(s, cfg["base"] + "/createTask", {"clientKey": api_key, "task": task})
    if created.get("errorId"):
        raise CaptchaError(f"{provider}: {created.get('errorCode') or created.get('errorDescription') or 'lỗi tạo task'}")
    task_id = created.get("taskId")
    if not task_id:
        raise CaptchaError(f"{provider}: không nhận được taskId")
    log(f"Đã gửi captcha cho {provider}, chờ giải...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        res = _post(s, cfg["base"] + "/getTaskResult", {"clientKey": api_key, "taskId": task_id})
        if res.get("errorId"):
            raise CaptchaError(f"{provider}: {res.get('errorCode') or 'lỗi lấy kết quả'}")
        if res.get("status") == "fail":
            raise CaptchaError(f"{provider}: không giải được captcha")
        if res.get("status") == "ready":
            sol = res.get("solution") or {}
            if want_key is None:
                return sol
            val = sol.get(want_key) or sol.get("text") or sol.get("gRecaptchaResponse")
            if not val:
                raise CaptchaError(f"{provider}: kết quả rỗng")
            return str(val)
    raise CaptchaError(f"{provider}: quá thời gian chờ ({timeout}s)")


def solve_image(provider: str, api_key: str, image_bytes: bytes,
                log: Optional[Callable[[str], None]] = None, timeout: int = 120) -> str:
    """Giải captcha ảnh -> chuỗi ký tự."""
    log = log or (lambda s: None)
    if provider not in PROVIDERS:
        raise CaptchaError(f"Chưa hỗ trợ dịch vụ '{provider}'")
    cfg = PROVIDERS[provider]
    b64 = base64.b64encode(image_bytes).decode()
    task = {"type": cfg["image_type"], cfg.get("image_field", "body"): b64}
    return _solve(provider, api_key, task, "text", timeout, log).strip()


def solve_recaptcha_v2(provider: str, api_key: str, site_key: str, page_url: str,
                       log: Optional[Callable[[str], None]] = None, timeout: int = 180) -> str:
    """Giải reCAPTCHA v2 (checkbox 'Tôi không phải robot') -> token g-recaptcha-response."""
    log = log or (lambda s: None)
    if provider not in PROVIDERS:
        raise CaptchaError(f"Chưa hỗ trợ dịch vụ '{provider}'")
    # Cả 3 dịch vụ (2Captcha, OmoCaptcha, Anti-Captcha) đều dùng websiteURL + websiteKey.
    task = {"type": PROVIDERS[provider]["recaptcha_type"],
            "websiteURL": page_url, "websiteKey": site_key}
    return _solve(provider, api_key, task, "gRecaptchaResponse", timeout, log).strip()


class Solver:
    """Bọc DANH SÁCH (dịch vụ + API key) để provider giải captcha ảnh / reCAPTCHA v2.
    Tự động CHUYỂN sang dịch vụ kế tiếp nếu dịch vụ đang dùng hết tiền / giải lỗi (failover).

    LỚP OCR CỤC BỘ: nếu bật (local_first=True) và máy có engine OCR (ddddocr...), captcha ẢNH
    được thử ĐỌC MIỄN PHÍ tại chỗ trước. Mỗi phiên giải, local được thử tối đa local_max_tries
    lần; hết mới chuyển sang dịch vụ trả phí. reCAPTCHA v2 luôn dùng dịch vụ (không đọc cục bộ)."""
    def __init__(self, provider=None, api_key: str = "", services=None,
                 log: Optional[Callable[[str], None]] = None,
                 local_first: bool = True, local_max_tries: int = 2,
                 local_digits_only: bool = False):
        # services: list [{"provider":..,"api_key":..}] ; hoặc truyền provider+api_key đơn lẻ
        self.log = log or (lambda s: None)
        self.services = []
        if services:
            for s in services:
                if s.get("provider") and s.get("api_key"):
                    self.services.append((s["provider"], s["api_key"]))
        if provider and api_key and not self.services:
            self.services.append((provider, api_key))
        self.local_first = local_first
        self.local_max_tries = max(0, int(local_max_tries))
        self.local_digits_only = local_digits_only
        self._img_try = 0        # đếm số lần image() đã gọi (để biết khi nào hết lượt local)

    def _run(self, fn, what: str):
        last = None
        for i, (prov, key) in enumerate(self.services):
            try:
                val = fn(prov, key)
                if val:
                    if i > 0:
                        self.log(f"Đã chuyển sang dịch vụ {prov} để giải {what}.")
                    return val
                last = f"{prov}: trả rỗng"
            except Exception as e:  # noqa
                last = f"{prov}: {str(e)[:80]}"
                self.log(f"Dịch vụ {prov} giải {what} lỗi ({str(e)[:60]}), thử dịch vụ khác...")
        raise CaptchaError(last or "Không có dịch vụ giải captcha")

    def _try_local(self, image_bytes: bytes) -> str:
        """Thử OCR cục bộ. Trả "" nếu không bật / không có engine / đọc không chắc."""
        if not self.local_first or self.local_max_tries <= 0:
            return ""
        try:
            from . import captcha_local
        except Exception:
            return ""
        if not captcha_local.available():
            return ""
        if self._img_try >= self.local_max_tries:
            return ""
        self._img_try += 1
        val = captcha_local.recognize(image_bytes, digits_only=self.local_digits_only)
        if val:
            self.log(f"OCR cục bộ ({captcha_local.engine_name()}) đọc: {val} "
                     f"(lần {self._img_try}/{self.local_max_tries}, miễn phí).")
        return val

    def image(self, image_bytes: bytes) -> str:
        # 1) thử đọc miễn phí tại chỗ trước
        local = self._try_local(image_bytes)
        if local:
            return local
        # 2) hết lượt local (hoặc không có) -> dùng dịch vụ trả phí
        if not self.services:
            raise CaptchaError("OCR cục bộ đọc không được và chưa cấu hình dịch vụ giải captcha")
        return self._run(lambda p, k: solve_image(p, k, image_bytes, log=self.log), "captcha ảnh")

    def reset_local(self):
        """Về đầu lượt OCR cục bộ (gọi khi bắt đầu một captcha mới)."""
        self._img_try = 0

    def recaptcha_v2(self, site_key: str, page_url: str) -> str:
        return self._run(lambda p, k: solve_recaptcha_v2(p, k, site_key, page_url, log=self.log),
                         "reCAPTCHA")

    def slider(self, background: bytes, puzzle: bytes, domain: str, width: int, height: int, puzzle_width: int) -> float:
        """Return horizontal displacement, not a token; caller verifies with the issuer."""
        def solve(provider, key):
            bg = base64.b64encode(background).decode()
            piece = base64.b64encode(puzzle).decode()
            if provider == "omocaptcha":
                task = {"type": "SliderAllWebTask", "domain": domain, "imageBase64": bg,
                        "puzzle": piece, "widthView": width, "heightView": height}
            elif provider == "2captcha":
                task = {"type": "CoordinatesTask", "body": bg, "imgInstructions": piece,
                        "comment": "Click the center of the missing puzzle piece in the background. One point only.",
                        "minClicks": 1, "maxClicks": 1}
            else:
                raise CaptchaError("Dịch vụ chưa hỗ trợ captcha trượt trong MinMin")
            solution = _solve(provider, key, task, None, 180, self.log)
            point = solution.get("end") if provider == "omocaptcha" else (solution.get("coordinates") or [None])[0]
            if not isinstance(point, dict) or "x" not in point:
                raise CaptchaError("Dịch vụ không trả tọa độ trượt hợp lệ")
            offset = float(point["x"]) - puzzle_width / 2
            if not 0 <= offset <= width - puzzle_width:
                raise CaptchaError("Tọa độ trượt nằm ngoài ảnh")
            return offset
        return self._run(solve, "captcha trượt")

    # tương thích code cũ gọi solver(img)
    def __call__(self, image_bytes: bytes) -> str:
        return self.image(image_bytes)
