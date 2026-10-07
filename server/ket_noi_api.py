"""Bộ khung dùng chung cho các cầu nối API tự bọc (transport "internal" trong catalog).

Mỗi nền tảng (Shopee, TikTok Shop, Lazada, GHN, GHTK, SePay, Casso, payOS, TikTok Ads, Zalo OA)
là một module `<ten>_mcp.py` có hai hàm `list_tools(spec)` và `call(tool, arguments, spec)`,
giống `botcake_mcp`. File này gom phần lặp lại để từng module chỉ còn lo đúng việc của nó:

- `tool()`        dựng khai báo tool theo chuẩn MCP.
- `goi()`         gọi HTTP có hạn giờ, không bao giờ ném lỗi ra ngoài, và GIẤU mọi bí mật khỏi
                  câu lỗi. Lý do: câu lỗi đi thẳng vào hội thoại, vào nhật ký và vào Telegram;
                  một token lọt vào đó là lọt cho mọi nơi câu chat được chép tới.
- `luu_bi_mat()`  ghi token MỚI (sau khi đổi mã ủy quyền hoặc làm mới token) vào kết nối, đã mã
                  hoá như mọi ô đăng nhập khác. Có khoá theo từng kết nối vì refresh token của
                  Shopee, Lazada, Zalo là loại DÙNG MỘT LẦN: hai lượt gọi cùng làm mới song song
                  thì lượt thứ hai cầm token đã chết và kết nối hỏng tới khi ủy quyền lại.

Đa tài khoản: mỗi KẾT NỐI là một tài khoản (một shop, một tài khoản vận chuyển, một tài khoản
ngân hàng...). Hub tự đặt namespace riêng khi một connector có nhiều kết nối, nên module ở đây
không cần biết mình là tài khoản thứ mấy, chỉ cần đọc `spec["secrets"]` của chính nó.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone  # noqa: F401

import httpx



def mui_gio():
    """Múi giờ người dùng chọn ở Cài đặt (mặc định Asia/Ho_Chi_Minh). Không ghim cứng UTC+7:
    xem chốt chặn trong tests/python/test_locale.py."""
    try:
        import localefmt
        return localefmt.tz()
    except Exception:
        return timezone.utc
_KHOA = {}          # khoá làm mới token theo từng kết nối


def tool(name, description, props=None, required=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props or {}, "required": required or []}}


def clip(text, max_chars=8000):
    text = str(text)
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    return (text[:head] + f"\n… [KẾT QUẢ BỊ CẮT - bỏ {len(text) - head - tail:,} ký tự giữa] …\n"
            + text[-tail:])


def json_ra(d, max_chars=8000):
    return clip(json.dumps(d, ensure_ascii=False, default=str), max_chars)


def giau(text, secrets):
    """Thay mọi giá trị bí mật xuất hiện trong `text` bằng ***. Chỉ giấu chuỗi đủ dài (>= 6)
    để không biến một mã shop 3 chữ số thành *** khắp nơi."""
    s = str(text)
    for v in sorted({str(x) for x in (secrets or {}).values() if x}, key=len, reverse=True):
        if len(v) >= 6:
            s = s.replace(v, "***")
    return s


def bi_mat(spec):
    return dict((spec or {}).get("secrets") or {})


def thieu(secrets, *keys):
    """Tên các ô bắt buộc còn trống."""
    return [k for k in keys if not str(secrets.get(k, "") or "").strip()]


async def goi(ten, method, url, *, secrets=None, params=None, json_body=None, data=None,
              headers=None, content=None, timeout=30):
    """Gọi HTTP. Trả (ok, kết_quả). ok=False thì kết_quả là câu lỗi đã giấu bí mật.
    Kết quả thành công là JSON đã parse (hoặc chuỗi nếu server trả không phải JSON)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.request(method, url, params=params, json=json_body, data=data,
                                headers=headers, content=content)
    except Exception as e:
        return False, giau(f"ERROR: {ten} không phản hồi: {type(e).__name__}: {e}", secrets)
    try:
        body = r.json()
    except ValueError:
        body = r.text or ""
    if r.status_code >= 400:
        tom = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        return False, giau(f"ERROR: {ten} {r.status_code}: {str(tom)[:400]}", secrets)
    return True, body


def khoa(spec):
    key = str((spec or {}).get("key") or id(spec))
    if key not in _KHOA:
        _KHOA[key] = asyncio.Lock()
    return _KHOA[key]


def luu_bi_mat(spec, patch):
    """Ghi các ô bí mật mới vào kết nối (mã hoá tại mcp_store) và cập nhật spec đang dùng.
    Không có id kết nối (ví dụ đang Test trước khi lưu) thì chỉ cập nhật bộ nhớ."""
    patch = {k: str(v) for k, v in (patch or {}).items() if v not in (None, "")}
    if not patch:
        return
    sec = (spec or {}).setdefault("secrets", {})
    sec.update(patch)
    cid = (spec or {}).get("key")
    if not cid or not isinstance(cid, str):
        return
    try:
        import mcp_store   # import trễ: mcp_store kéo theo cả catalog
        mcp_store.update_connection(cid, {"fields": patch})
    except Exception as e:
        import sys
        print(f"[ket_noi_api] không lưu được token mới cho {cid}: {type(e).__name__}", file=sys.stderr)


def con_han(secrets, key_het_han, du_phong=300):
    """True nếu token còn hạn ít nhất `du_phong` giây. Không có mốc hết hạn thì coi là còn."""
    raw = str(secrets.get(key_het_han, "") or "").strip()
    if not raw:
        return True
    try:
        return float(raw) - time.time() > du_phong
    except ValueError:
        return True


def ngay_sang_ts(ngay, cuoi_ngay=False):
    """'YYYY-MM-DD' (giờ Việt Nam) -> unix giây. Rỗng hoặc sai dạng -> None."""
    try:
        d = datetime.strptime(str(ngay).strip(), "%Y-%m-%d").replace(tzinfo=mui_gio())
    except (TypeError, ValueError):
        return None
    if cuoi_ngay:
        d = d + timedelta(days=1) - timedelta(seconds=1)
    return int(d.timestamp())


def khoang(args, mac_dinh_ngay=7, toi_da_ngay=None):
    """(từ, đến) unix giây từ args `tu_ngay`/`den_ngay`. Mặc định N ngày gần nhất.
    `toi_da_ngay` cắt bớt khoảng cho API giới hạn (Shopee chỉ cho 15 ngày mỗi lần)."""
    args = args or {}
    den = ngay_sang_ts(args.get("den_ngay"), cuoi_ngay=True) or int(time.time())
    tu = ngay_sang_ts(args.get("tu_ngay")) or (den - mac_dinh_ngay * 86400)
    if tu > den:
        tu, den = den, tu
    if toi_da_ngay and den - tu > toi_da_ngay * 86400:
        tu = den - toi_da_ngay * 86400
    return tu, den


def so(v, mac_dinh, nho=1, lon=100):
    try:
        return max(nho, min(lon, int(v)))
    except (TypeError, ValueError):
        return mac_dinh


def ds(v):
    """Nhận list hoặc chuỗi 'a,b,c' -> list chuỗi đã bỏ trống."""
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


NGAY_PROPS = {
    "tu_ngay": {"type": "string", "description": "từ ngày YYYY-MM-DD (giờ VN), mặc định 7 ngày trước"},
    "den_ngay": {"type": "string", "description": "đến ngày YYYY-MM-DD, mặc định hôm nay"},
}
