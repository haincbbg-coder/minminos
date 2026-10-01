# -*- coding: utf-8 -*-
"""
gdt_client.py - Kết nối cổng hoadondientu.gdt.gov.vn (Tổng cục Thuế).

Tổng cục Thuế KHÔNG công bố API chính thức; các endpoint dưới đây là endpoint
nội bộ mà chính trang web tra cứu đang dùng (quan sát qua DevTools):

  GET  /api/captcha                                   -> {"key", "content"(SVG)}
  POST /api/security-taxpayer/authenticate            -> {"token"}
  GET  /api/query/invoices/purchase|sold              (hóa đơn điện tử)
  GET  /api/sco-query/invoices/purchase|sold          (hóa đơn máy tính tiền)
       ?sort=tdlap:desc&size=50
       &search=tdlap=ge=dd/mm/yyyyT00:00:00;tdlap=le=dd/mm/yyyyT23:59:59[;ttxly==5]
       [&state=<con trỏ trang tiếp>]
  GET  /api/{query|sco-query}/invoices/detail?nbmst&khhdon&khmshdon&shdon
  GET  /api/{query|sco-query}/invoices/export-xml?nbmst&khhdon&khmshdon&shdon
       -> file .zip chứa <xml> + invoice.html

Nếu cổng thuế đổi endpoint, chỉ cần sửa trong file này.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import random
import threading
import time
import uuid
from typing import Callable, Iterable, Optional
from urllib.parse import quote

try:  # curl_cffi giả lập vân tay TLS Chrome -> ít bị WAF F5 của cổng thuế chặn
    from curl_cffi import requests as _cffi_requests  # type: ignore
    _HAS_CFFI = True
except Exception:  # pragma: no cover
    _cffi_requests = None
    _HAS_CFFI = False

import requests


def _safe_ca_bundle():
    """curl (trong curl_cffi) không đọc được đường dẫn có dấu tiếng Việt / ký tự Unicode
    (lỗi 'charmap' codec) -> nếu file chứng chỉ SSL nằm ở đường dẫn như vậy thì chép ra
    thư mục tạm có đường dẫn ASCII và dùng bản chép. Trả về đường dẫn hoặc True (mặc định)."""
    try:
        import certifi
        src = certifi.where()
    except Exception:
        return True
    try:
        src.encode("ascii")
        return src  # đường dẫn sạch, dùng luôn
    except UnicodeEncodeError:
        pass
    import shutil
    import tempfile
    for base in (tempfile.gettempdir(), os.environ.get("LOCALAPPDATA", ""), os.environ.get("SystemDrive", "C:") + os.sep):
        if not base:
            continue
        try:
            base.encode("ascii")
        except UnicodeEncodeError:
            continue
        try:
            dst = os.path.join(base, "tct_cacert.pem")
            if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
                shutil.copyfile(src, dst)
            return dst
        except Exception:
            continue
    return True


class GDTError(Exception):
    """Lỗi chung khi gọi cổng thuế."""


class TokenExpired(GDTError):
    """Phiên đăng nhập hết hạn (HTTP 401)."""


class Cancelled(GDTError):
    """Người dùng bấm Hủy."""


# --- Mã trạng thái hóa đơn (tthai) và kết quả kiểm tra (ttxly) ---------------
TTHAI = {
    1: "Hóa đơn mới",
    2: "Hóa đơn thay thế",
    3: "Hóa đơn điều chỉnh",
    4: "Hóa đơn bị thay thế",
    5: "Hóa đơn bị điều chỉnh",
    6: "Hóa đơn đã bị hủy",
}
TTXLY = {
    0: "Tổng cục Thuế đã nhận",
    1: "Đang kiểm tra điều kiện cấp mã",
    2: "CQT từ chối hóa đơn theo từng lần phát sinh",
    3: "Hóa đơn đủ điều kiện cấp mã",
    4: "Hóa đơn không đủ điều kiện cấp mã",
    5: "Đã cấp mã hóa đơn",
    6: "Tổng cục Thuế đã nhận không mã",
    7: "Đã kiểm tra định kỳ HĐĐT không có mã",
    8: "Tổng cục Thuế đã nhận hóa đơn có mã khởi tạo từ máy tính tiền",
}
# Mua vào phải tra riêng từng trạng thái xử lý rồi gộp (giống trang web)
PURCHASE_TTXLY = (5, 6, 8)


def month_ranges(d_from: dt.date, d_to: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Cổng thuế giới hạn mỗi lần tra cứu ~1 tháng -> chia khoảng ngày theo tháng."""
    out = []
    cur = d_from
    while cur <= d_to:
        last = dt.date(cur.year, cur.month, calendar.monthrange(cur.year, cur.month)[1])
        end = min(last, d_to)
        out.append((cur, end))
        cur = end + dt.timedelta(days=1)
    return out


def _fmt(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")


class GDTClient:
    BASE = "https://hoadondientu.gdt.gov.vn/api"
    ORIGIN = "https://hoadondientu.gdt.gov.vn"
    REFERER = "https://hoadondientu.gdt.gov.vn/tra-cuu/tra-cuu-hoa-don"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

    def __init__(self, base: Optional[str] = None, use_cffi: bool = True,
                 log: Optional[Callable[[str], None]] = None):
        if base:
            self.BASE = base.rstrip("/")
            self.ORIGIN = self.BASE.rsplit("/api", 1)[0]
            self.REFERER = self.ORIGIN + "/tra-cuu/tra-cuu-hoa-don"
        self.log = log or (lambda s: None)
        self.impersonate = False
        if use_cffi and _HAS_CFFI:
            # Cổng thuế đứng sau tường lửa F5 kiểm tra vân tay TLS: Python thường bị
            # 403 "Hệ thống phát hiện hành vi không hợp lệ". curl_cffi giả lập Chrome.
            self.session = _cffi_requests.Session(impersonate="chrome", verify=_safe_ca_bundle())
            self.impersonate = True
        else:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": self.UA,
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
            })
        self.session.headers.update({"Accept": "application/json, text/plain, */*",
                                     "Referer": self.ORIGIN + "/"})
        self._warmed = False
        self.token: Optional[str] = None
        self.token_dead = False
        self.cancel_check: Callable[[], bool] = lambda: False
        # nhịp nghỉ giữa các request (giây) - chống 429
        self.delay_page = 0.4
        self.delay_download = 0.6
        self.max_retry = 6
        # Chống bị nhận diện quét: nghỉ ngẫu nhiên (jitter) và khi bị 429 thì
        # TẤT CẢ luồng cùng dừng theo mốc chung (global backoff).
        self.jitter = 0.5
        self._backoff_until = 0.0
        self._lock = threading.Lock()

    def clone(self) -> "GDTClient":
        """Bản sao cho luồng khác: cùng token + cookie tường lửa, session riêng."""
        c = GDTClient(base=self.BASE if self.BASE != GDTClient.BASE else None,
                      use_cffi=self.impersonate, log=self.log)
        c.cancel_check = self.cancel_check
        c.delay_page, c.delay_download, c.jitter = self.delay_page, self.delay_download, self.jitter
        c.max_retry = self.max_retry
        c._lock = self._lock            # dùng chung mốc backoff
        c._shared = self
        try:
            for ck in self.session.cookies.jar if hasattr(self.session.cookies, "jar") else self.session.cookies:
                c.session.cookies.set(ck.name, ck.value, domain=ck.domain)
        except Exception:
            pass
        c._warmed = True
        if self.token:
            c.set_token(self.token)
        return c

    def _wait_backoff(self):
        src = getattr(self, "_shared", self)
        while True:
            until = src._backoff_until
            if until <= time.time():
                return
            self._sleep(min(until - time.time(), 1.0))

    def _set_backoff(self, sec: float):
        src = getattr(self, "_shared", self)
        with self._lock:
            src._backoff_until = max(src._backoff_until, time.time() + sec)

    def pause(self, base: float):
        """Nghỉ base giây ± jitter ngẫu nhiên (giống người dùng thật)."""
        self._sleep(max(0.0, base + random.uniform(-self.jitter, self.jitter) * base))

    # ------------------------------------------------------------------ utils
    def _check_cancel(self):
        if self.cancel_check():
            raise Cancelled("Đã hủy")

    def _sleep(self, sec: float):
        end = time.time() + sec
        while time.time() < end:
            self._check_cancel()
            time.sleep(min(0.3, end - time.time()) if end > time.time() else 0)

    def _headers(self, action: str) -> dict:
        # Giống hệt axios interceptor của trang web: request-id (UUID v4) là BẮT BUỘC,
        # thiếu nó cổng thuế trả 403 "Hệ thống phát hiện hành vi không hợp lệ".
        return {
            "request-id": str(uuid.uuid4()),
            "Action": quote(action, safe="()"),
            "End-Point": "/tra-cuu/tra-cuu-hoa-don",
            "Accept-Language": "vi",
            "Referer": self.REFERER,
        }

    def _public_headers(self) -> dict:
        """Header cho captcha / đăng nhập (chưa có token) - đúng như trình duyệt gửi."""
        return {"request-id": str(uuid.uuid4()), "Action": "", "End-Point": "/",
                "Referer": self.ORIGIN + "/"}

    def _get(self, url: str, action: str, params: Optional[dict] = None,
             timeout: int = 60, want_json: bool = True):
        """GET có thử lại khi 429 / lỗi mạng / 5xx. 401 -> TokenExpired."""
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retry):
            self._check_cancel()
            self._wait_backoff()
            try:
                r = self.session.get(url, params=params, headers=self._headers(action),
                                     timeout=timeout)
            except Exception as e:  # lỗi mạng
                last_err = e
                self.log(f"Lỗi mạng ({attempt + 1}/{self.max_retry}): {e}")
                self._sleep(min(2 * (attempt + 1), 15))
                continue
            if r.status_code == 401:
                self.token_dead = True
                raise TokenExpired("Phiên đăng nhập hết hạn, vui lòng đăng nhập lại.")
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                try:
                    wait = int(ra) if ra else 3 * (attempt + 1)
                except ValueError:
                    wait = 3 * (attempt + 1)
                self.log(f"Cổng thuế giới hạn tốc độ (429), tất cả luồng chờ {wait}s...")
                self._set_backoff(min(wait, 60))
                self._wait_backoff()
                continue
            if r.status_code == 403:
                # tường lửa nghi ngờ quét -> dừng dài hơn rồi thử lại
                wait = min(30 * (attempt + 1), 120)
                self.log(f"Cổng thuế chặn tạm (403), tất cả luồng chờ {wait}s...")
                self._set_backoff(wait)
                self._wait_backoff()
                continue
            if r.status_code >= 500:
                last_err = GDTError(f"Cổng thuế lỗi {r.status_code}")
                self._sleep(min(2 * (attempt + 1), 15))
                continue
            if r.status_code != 200:
                raise GDTError(f"HTTP {r.status_code}: {r.text[:200]}")
            if want_json:
                try:
                    return r.json()
                except Exception as e:
                    raise GDTError(f"Phản hồi không phải JSON: {e}")
            return r.content
        raise GDTError(f"Thử lại {self.max_retry} lần vẫn lỗi: {last_err}")

    def connection_mode(self) -> str:
        return ("Chrome giả lập (curl_cffi) - OK" if self.impersonate
                else "Python thường - DỄ BỊ CỔNG THUẾ CHẶN 403, hãy cài curl_cffi")

    def warm_up(self):
        """Mở trang chủ 1 lần như trình duyệt để nhận cookie tường lửa (TS...)."""
        if self._warmed:
            return
        try:
            self.session.get(self.ORIGIN + "/", timeout=30,
                             headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
        except Exception as e:  # không chặn luồng chính
            self.log(f"Không mở được trang chủ cổng thuế: {e}")
        self._warmed = True

    # -------------------------------------------------------------- captcha
    def get_captcha(self) -> dict:
        """-> {"key": str, "content": str(SVG hoặc data-URI)}"""
        self.warm_up()
        r = self.session.get(f"{self.BASE}/captcha", timeout=30, headers=self._public_headers())
        if r.status_code != 200:
            raise GDTError(f"Không lấy được captcha (HTTP {r.status_code})")
        try:
            return r.json()
        except Exception:
            return {"key": "", "content": r.text}

    # ---------------------------------------------------------------- login
    def login(self, username: str, password: str, cvalue: str, ckey: str) -> str:
        payload = {"username": username, "password": password,
                   "cvalue": cvalue, "ckey": ckey}
        self.warm_up()
        r = self.session.post(f"{self.BASE}/security-taxpayer/authenticate",
                              json=payload, timeout=30,
                              headers={**self._public_headers(), "Origin": self.ORIGIN,
                                       "Content-Type": "application/json"})
        if r.status_code != 200:
            msg = r.text[:300]
            try:
                msg = r.json().get("message") or msg
            except Exception:
                pass
            hint = ""
            if r.status_code == 403:
                hint = " → Bị tường lửa chặn. Đợi 5-10 phút rồi thử lại; nếu vẫn bị, gửi log cho người hỗ trợ."
            elif r.status_code == 401:
                hint = " → Bấm ⟳ lấy captcha mới, gõ đúng chữ hoa/thường rồi đăng nhập lại."
            raise GDTError(f"Đăng nhập thất bại ({r.status_code}): {msg}{hint}")
        data = r.json()
        token = data.get("token")
        if not token:
            raise GDTError(f"Không nhận được token: {json.dumps(data, ensure_ascii=False)[:200]}")
        self.set_token(token)
        return token

    def set_token(self, token: str):
        self.token = token
        self.token_dead = False
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def token_exp(self) -> int:
        """Thời điểm hết hạn token (epoch), 0 nếu không đọc được."""
        try:
            return int(self.token_info().get("exp") or 0)
        except Exception:
            return 0

    def token_valid(self, margin: int = 600) -> bool:
        return bool(self.token) and not self.token_dead and self.token_exp() > time.time() + margin

    def token_info(self) -> dict:
        """Giải mã payload JWT (không kiểm chữ ký) để lấy tên/MST hiển thị."""
        if not self.token or self.token.count(".") < 2:
            return {}
        try:
            import base64
            part = self.token.split(".")[1]
            part += "=" * (-len(part) % 4)
            return json.loads(base64.urlsafe_b64decode(part).decode("utf-8", "ignore"))
        except Exception:
            return {}

    # ----------------------------------------------------------- tra cứu
    def _fetch_paginated(self, url: str, search: str, action: str, page_size: int = 50,
                         progress: Optional[Callable[[str], None]] = None) -> tuple[list, int]:
        results: list = []
        state = None
        total = 0
        for page in range(1000):
            qs = (f"sort=tdlap:desc&size={page_size}"
                  f"&search={quote(search, safe='=;,:/')}")
            if state:
                qs += f"&state={quote(str(state), safe='')}"
            data = self._get(f"{url}?{qs}", action)
            datas = data.get("datas") or []
            total = int(data.get("total") or total or 0)
            results.extend(datas)
            if progress:
                progress(f"Trang {page + 1}: {len(datas)} bản ghi, cộng dồn {len(results)}/{total}")
            state = data.get("state")
            if not state or not datas or len(results) >= total:
                break
            self.pause(self.delay_page)
        return results, total

    def query_invoices(self, d_from: dt.date, d_to: dt.date, loai: str = "purchase",
                       system: str = "query", page_size: int = 50,
                       progress: Optional[Callable[[str], None]] = None,
                       extra_search: str = "") -> list[dict]:
        """
        loai: "purchase" (mua vào) | "sold" (bán ra)
        system: "query" (HĐ điện tử) | "sco-query" (HĐ máy tính tiền)
        extra_search: điều kiện thêm, vd "shdon==123;khhdon==C26TBB"
        Tự chia theo tháng, mua vào tra từng trạng thái ttxly rồi gộp.
        """
        is_mtt = system == "sco-query"
        url = f"{self.BASE}/{system}/invoices/{loai}"
        kind = "mua vào" if loai == "purchase" else "bán ra"
        action = f"Tìm kiếm (hóa đơn {'máy tính tiền ' if is_mtt else ''}{kind})"
        out: list[dict] = []
        seen: set = set()
        for (a, b) in month_ranges(d_from, d_to):
            self._check_cancel()
            base_search = f"tdlap=ge={_fmt(a)}T00:00:00;tdlap=le={_fmt(b)}T23:59:59"
            if extra_search:
                base_search += ";" + extra_search
            if progress:
                progress(f"Kỳ {_fmt(a)} - {_fmt(b)} ({kind}{', máy tính tiền' if is_mtt else ''})...")
            searches: Iterable[str]
            if loai == "purchase":
                searches = [f"{base_search};ttxly=={t}" for t in PURCHASE_TTXLY]
            else:
                searches = [base_search]
            for s in searches:
                part, _ = self._fetch_paginated(url, s, action, page_size, progress)
                for inv in part:
                    inv["_system"] = system
                    inv["_loai"] = loai
                    key = (inv.get("nbmst"), inv.get("khmshdon"), inv.get("khhdon"), inv.get("shdon"))
                    if key not in seen:
                        seen.add(key)
                        out.append(inv)
                self.pause(self.delay_page)
        return out

    # -------------------------------------------------------------- detail
    def get_detail(self, inv: dict) -> dict:
        system = inv.get("_system", "query")
        loai = inv.get("_loai", "purchase")
        act = "Xem hóa đơn (hóa đơn %s)" % ("mua vào" if loai == "purchase" else "bán ra")
        params = {"nbmst": inv.get("nbmst"), "khhdon": inv.get("khhdon"),
                  "khmshdon": inv.get("khmshdon"), "shdon": inv.get("shdon")}
        return self._get(f"{self.BASE}/{system}/invoices/detail", act, params=params)

    # ---------------------------------------------------------- export xml
    def download_xml_zip(self, inv: dict) -> bytes:
        """Tải file zip (XML + invoice.html) của 1 hóa đơn."""
        system = inv.get("_system", "query")
        params = {"nbmst": inv.get("nbmst"), "khhdon": inv.get("khhdon"),
                  "khmshdon": inv.get("khmshdon"), "shdon": inv.get("shdon")}
        content = self._get(f"{self.BASE}/{system}/invoices/export-xml", "Xuat xml",
                            params=params, timeout=90, want_json=False)
        if content[:1] == b"{":  # JSON báo lỗi thay vì file
            try:
                msg = json.loads(content).get("message")
            except Exception:
                msg = content[:200]
            raise GDTError(f"Cổng thuế không trả file: {msg}")
        return content


def invoice_key(inv: dict) -> str:
    """Khóa duy nhất của hóa đơn -> dùng làm tên file."""
    return f"{inv.get('nbmst')}_{inv.get('khmshdon')}{inv.get('khhdon')}_{inv.get('shdon')}"


def _san_name(s: str, limit: int = 45) -> str:
    """Bỏ ký tự Windows cấm trong tên file, gộp khoảng trắng, cắt ngắn (GIỮ dấu tiếng Việt)."""
    s = str(s or "")
    for ch in '\\/:*?"<>|\r\n\t':
        s = s.replace(ch, " ")
    s = " ".join(s.split()).strip(" .")
    return s[:limit].strip()


def partner_name(inv: dict) -> str:
    """Tên đối tác: mua vào -> người bán (NCC); bán ra -> người mua (khách)."""
    if inv.get("_loai") == "sold":
        return inv.get("nmten") or inv.get("mua_ten") or inv.get("nbten") or inv.get("ban_ten") or ""
    return inv.get("nbten") or inv.get("ban_ten") or inv.get("nmten") or inv.get("mua_ten") or ""


# ---- MẪU ĐẶT TÊN FILE TÙY CHỈNH (người dùng tự ghép các thành phần) ----
# Danh sách token có thể chọn + nhãn hiển thị.
NAME_TOKENS = [
    ("ngay_tai", "Ngày tải"),
    ("ngay_lap", "Ngày lập"),
    ("so_hd", "Số hóa đơn"),
    ("ky_hieu", "Ký hiệu"),
    ("mst", "Mã số thuế"),
    ("ten_doitac", "Tên đối tác"),
]
_DEFAULT_NAME = ["ngay_tai", "ten_doitac", "so_hd", "ngay_lap"]   # tương thích bản cũ
_NAME_TOKENS_CUR = list(_DEFAULT_NAME)
_NAME_KEEPVIET = True


def set_name_template(tokens=None, keep_viet: bool = True):
    """App gọi lúc khởi động để nạp mẫu đặt tên từ cấu hình người dùng."""
    global _NAME_TOKENS_CUR, _NAME_KEEPVIET
    valid = {k for k, _ in NAME_TOKENS}
    toks = [t for t in (tokens or []) if t in valid]
    _NAME_TOKENS_CUR = toks or list(_DEFAULT_NAME)
    _NAME_KEEPVIET = bool(keep_viet)


def _strip_viet(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def _token_value(inv: dict, tok: str) -> str:
    if tok == "ngay_tai":
        return dt.date.today().strftime("%Y-%m-%d")
    if tok == "ngay_lap":
        return str(inv.get("tdlap") or inv.get("ngay") or "")[:10] or "khong-ngay"
    if tok == "so_hd":
        so = str(inv.get("shdon") or "")
        try:
            return f"{int(so):07d}"
        except ValueError:
            return so or "0"
    if tok == "ky_hieu":
        return f"{inv.get('khmshdon') or ''}{inv.get('khhdon') or ''}" or "KH"
    if tok == "mst":
        m = inv.get("nbmst") or inv.get("ban_mst") if inv.get("_loai") != "sold" \
            else (inv.get("nmmst") or inv.get("mua_mst"))
        return str(m or "").strip() or "MST"
    if tok == "ten_doitac":
        return _san_name(partner_name(inv), 40) or "DoiTac"
    return ""


def build_filename(inv: dict, tokens=None, keep_viet=None) -> str:
    """Ghép tên file theo mẫu token (mặc định lấy mẫu người dùng đã cấu hình)."""
    toks = tokens if tokens is not None else _NAME_TOKENS_CUR
    kv = _NAME_KEEPVIET if keep_viet is None else keep_viet
    parts = [_token_value(inv, t) for t in toks]
    parts = [p for p in parts if p]
    base = "_".join(parts)
    if not kv:
        base = _strip_viet(base)
    base = _san_name(base, 150)
    return base or invoice_key(inv)


def invoice_filename(inv: dict) -> str:
    """Tên file hóa đơn tải về theo MẪU người dùng đã cấu hình (PDF/XML/HTML dùng chung base,
    chỉ khác đuôi). Mặc định: <ngày tải>_<tên đối tác>_<số HĐ>_<ngày lập>."""
    return build_filename(inv)
