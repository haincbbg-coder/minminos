"""Thống kê hộp thư chatbot khách hàng (tính năng "Thống kê chatbot", Phase 01).

Đọc DỮ LIỆU THẬT từ kho hội thoại khách (`conversations.py` -> customer_conversations.sqlite3).
Mỗi tin trong bảng `messages` có: `created_at` (epoch giây), `sender_type`
(customer | ai | human | system), thuộc một `conversation`, và hội thoại gắn với một tài khoản
kênh (`channel_accounts`, khoá `<kênh>:<nick>`). Từ đó tính được các chỉ số dưới đây cho MỘT kỳ
và KỲ LIỀN TRƯỚC (cùng độ dài) để so sánh.

Các chỉ số (giống Javis 0.399):
  - Tỉ lệ % câu trả lời do AI lo = ai / (ai + human). `human` là tin chủ trả tay (trả từ hòm thư,
    hoặc tin của chính chủ trên Zalo cá nhân - xem `zalo_personal_channel`).
  - Số tin AI trả thay chủ = số tin `sender_type='ai'` đã GỬI (nháp chưa gửi nằm ở
    `metadata.draft`, không phải một dòng `messages`, nên không tính vào đây).
  - Ước tính GIỜ RẢNH = số tin AI trả x số phút mỗi tin (mặc định 2 phút). KHÔNG quy ra tiền.
  - Số tin AI trả lúc 21h-7h (giờ chủ nghỉ), theo giờ Việt Nam.
  - Số khách được phục vụ (có ít nhất một tin khách trong kỳ) + số khách MỚI (tạo trong kỳ).
  - Tốc độ trả lời đầu tiên: TRUNG VỊ thời gian từ tin khách mở một đợt tới câu đáp đầu, tách
    AI và tay. "Mở một đợt" = tin khách đầu tiên khi chưa có tin khách nào đang chờ (không reset
    khi khách nhắn thêm), đúng cách `conversation_ops.report` đang dùng.
  - Biểu đồ giờ khách nhắn nhiều nhất: 24 ô theo giờ trong ngày (giờ Việt Nam).

Múi giờ: Asia/Ho_Chi_Minh (ghim cứng, không theo cấu hình - Việt Nam không có giờ mùa hè nên
+07:00 luôn đúng). Chỉ ĐỌC kho, dùng chung kết nối + khoá của `conversations` để không mở thêm
handle tới cùng file WAL.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import conversations

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:                       # pragma: no cover - thiếu tzdata thì về +07:00 cố định
    TZ = timezone(timedelta(hours=7))

PERIODS = ("today", "7d", "30d", "90d", "last_month", "custom")
GIO_NGHI = range(0, 7)                  # 00:00-06:59
GIO_NGHI_TOI = 21                       # 21:00-23:59
DEFAULT_MINS_PER_REPLY = 2.0
MAX_MINS_PER_REPLY = 24 * 60            # trần phòng số vô lý (1 ngày / tin)

# Số chỉ số vô hướng được so kỳ trước (field -> cách lấy từ khối kỳ).
_DELTA_KEYS = (
    "ai_reply_count", "owner_reply_count", "ai_reply_pct", "ai_free_minutes", "ai_free_hours",
    "ai_night_reply_count", "customer_msg_count", "customers_served", "new_customers",
)


# ============================================================
# Thời gian / kỳ
# ============================================================
def _la_dem(dt: datetime) -> bool:
    """Mốc này (đã ở giờ VN) có nằm trong giờ chủ nghỉ 21h-7h không."""
    h = dt.hour
    return h >= GIO_NGHI_TOI or h in GIO_NGHI


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), TZ).isoformat()


def _parse_ngay(s: str) -> datetime:
    """"YYYY-MM-DD" -> nửa đêm hôm đó theo giờ VN. Ném ValueError nếu sai khuôn."""
    d = datetime.strptime(str(s).strip(), "%Y-%m-%d")
    return datetime(d.year, d.month, d.day, tzinfo=TZ)


def resolve_period(period: str, frm: str = "", to: str = "",
                   now: Optional[float] = None) -> Tuple[float, float, float, float]:
    """(start, end, prev_start, prev_end) dạng epoch giây cho `period`.

    Kỳ là [start, end). Kỳ liền trước cùng độ dài, nối ngay trước start (riêng last_month là
    tháng trước nữa). `today` so với CÙNG GIỜ hôm qua, không phải cả ngày hôm qua.
    """
    now = float(now) if now is not None else datetime.now(TZ).timestamp()
    ndt = datetime.fromtimestamp(now, TZ)
    today0 = ndt.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        start, end = today0, ndt
        prev_start, prev_end = start - timedelta(days=1), end - timedelta(days=1)
    elif period in ("7d", "30d", "90d"):
        days = {"7d": 7, "30d": 30, "90d": 90}[period]
        start, end = ndt - timedelta(days=days), ndt
        prev_start, prev_end = start - timedelta(days=days), start
    elif period == "last_month":
        first_this = today0.replace(day=1)
        start = (first_this - timedelta(days=1)).replace(day=1)   # mùng 1 tháng trước
        end = first_this                                          # mùng 1 tháng này
        prev_start = (start - timedelta(days=1)).replace(day=1)   # mùng 1 tháng trước nữa
        prev_end = start
    elif period == "custom":
        start = _parse_ngay(frm)
        end = _parse_ngay(to) + timedelta(days=1)                 # `to` tính TRỌN ngày
        if end <= start:
            raise ValueError("'to' phải không nhỏ hơn 'from'")
        dur = end - start
        prev_start, prev_end = start - dur, start
    else:
        raise ValueError(f"period '{period}' không hợp lệ (nhận: {', '.join(PERIODS)})")

    return (start.timestamp(), end.timestamp(), prev_start.timestamp(), prev_end.timestamp())


# ============================================================
# Lọc theo 1 nick (tài khoản kênh)
# ============================================================
def _acc_clause(account: str, alias: str = "a") -> Tuple[str, list]:
    """Mệnh đề WHERE lọc đúng một tài khoản kênh. Khớp khoá kho (`<kênh>:<nick>`), id ngoài của
    nick, hoặc tên hiển thị - để gọi bằng giá trị nào cũng ra. Rỗng -> không lọc."""
    a = str(account or "").strip()
    if not a:
        return "", []
    return (f" AND ({alias}.id=? OR {alias}.external_account_id=? OR {alias}.display_name=?)",
            [a, a, a])


def danh_sach_nick() -> List[dict]:
    """Các nick (tài khoản kênh) đang có trong kho, để UI đổ vào ô lọc. Không ném."""
    try:
        with conversations._lock:
            rows = conversations._conn().execute(
                "SELECT a.id, a.channel, a.external_account_id, a.display_name,"
                " COUNT(c.id) AS conversations"
                " FROM channel_accounts a LEFT JOIN conversations c ON c.channel_account_id=a.id"
                " GROUP BY a.id ORDER BY a.channel, a.display_name").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ============================================================
# Tính cho MỘT cửa sổ [start, end)
# ============================================================
def _window(start: float, end: float, account: str, mins_per_reply: float) -> dict:
    """Mọi chỉ số cho một cửa sổ thời gian. Đọc kho một lần cho phần đếm/histogram, một lần cho
    bắt cặp tốc độ trả lời, một lần đếm khách mới."""
    acc_sql, acc_args = _acc_clause(account)

    with conversations._lock:
        db = conversations._conn()
        # 1) Đếm, histogram, khách được phục vụ - một lượt quét tin trong cửa sổ.
        rows = db.execute(
            "SELECT m.sender_type AS st, m.created_at AS ts, c.customer_id AS cid"
            " FROM messages m JOIN conversations c ON c.id=m.conversation_id"
            " JOIN channel_accounts a ON a.id=c.channel_account_id"
            " WHERE m.created_at>=? AND m.created_at<?" + acc_sql,
            [start, end] + acc_args).fetchall()
        # 2) Bắt cặp tốc độ trả lời đầu - tin theo thứ tự trong từng hội thoại.
        pair_rows = db.execute(
            "SELECT m.conversation_id AS conv, m.sender_type AS st, m.created_at AS ts"
            " FROM messages m JOIN conversations c ON c.id=m.conversation_id"
            " JOIN channel_accounts a ON a.id=c.channel_account_id"
            " WHERE m.created_at>=? AND m.created_at<?" + acc_sql +
            " ORDER BY m.conversation_id, m.created_at, m.id",
            [start, end] + acc_args).fetchall()
        # 3) Khách MỚI: tạo trong cửa sổ.
        acc_sql_k, acc_args_k = _acc_clause(account)
        new_customers = db.execute(
            "SELECT COUNT(*) FROM customers k JOIN channel_accounts a ON a.id=k.channel_account_id"
            " WHERE k.created_at>=? AND k.created_at<?" + acc_sql_k,
            [start, end] + acc_args_k).fetchone()[0]

    ai = owner = ai_night = 0
    hours = [0] * 24
    served = set()
    for r in rows:
        st, ts = r["st"], r["ts"]
        if st == "ai":
            ai += 1
            if _la_dem(datetime.fromtimestamp(ts, TZ)):
                ai_night += 1
        elif st == "human":
            owner += 1
        elif st == "customer":
            hours[datetime.fromtimestamp(ts, TZ).hour] += 1
            if r["cid"] is not None:
                served.add(int(r["cid"]))
    customer_msgs = sum(hours)

    # Tốc độ trả lời đầu: mở đợt bằng tin khách đầu khi chưa có đợt đang chờ, chốt ở câu đáp đầu.
    starts: Dict[int, float] = {}
    ai_delays: List[float] = []
    owner_delays: List[float] = []
    for r in pair_rows:
        conv, st, ts = r["conv"], r["st"], r["ts"]
        if st == "customer":
            starts.setdefault(conv, ts)
        elif st in ("ai", "human") and conv in starts:
            delay = max(0.0, ts - starts.pop(conv))
            (ai_delays if st == "ai" else owner_delays).append(delay)

    def _med(xs: List[float]) -> Optional[float]:
        return round(statistics.median(xs), 1) if xs else None

    denom = ai + owner
    ai_pct = round(ai / denom * 100, 1) if denom else None
    free_min = round(ai * mins_per_reply, 1)

    return {
        "ai_reply_count": ai,
        "owner_reply_count": owner,
        "ai_reply_pct": ai_pct,
        "ai_free_minutes": free_min,
        "ai_free_hours": round(free_min / 60, 2),
        "ai_night_reply_count": ai_night,
        "customer_msg_count": customer_msgs,
        "customers_served": len(served),
        "new_customers": int(new_customers or 0),
        "first_response_sec": {
            "ai_median": _med(ai_delays), "ai_n": len(ai_delays),
            "owner_median": _med(owner_delays), "owner_n": len(owner_delays),
            "overall_median": _med(ai_delays + owner_delays), "overall_n": len(ai_delays) + len(owner_delays),
        },
        "customer_msgs_by_hour": hours,
        "range": {"from": _iso(start), "to": _iso(end)},
    }


def _delta(cur: dict, prev: dict) -> dict:
    """Chênh lệch tuyệt đối từng chỉ số vô hướng giữa kỳ này và kỳ trước. None nếu một bên None."""
    out = {}
    for k in _DELTA_KEYS:
        a, b = cur.get(k), prev.get(k)
        out[k] = round(a - b, 2) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
    return out


# ============================================================
# Điểm vào công khai
# ============================================================
def tinh(period: str = "7d", frm: str = "", to: str = "", account: str = "",
         mins_per_reply: Any = DEFAULT_MINS_PER_REPLY, now: Optional[float] = None) -> dict:
    """Thống kê hộp thư chatbot cho `period` kèm kỳ liền trước và chênh lệch.

    Ném ValueError khi `period` hoặc ngày custom sai khuôn (route biến thành 400).
    """
    period = str(period or "7d").strip().lower()
    if period not in PERIODS:
        raise ValueError(f"period '{period}' không hợp lệ (nhận: {', '.join(PERIODS)})")
    try:
        mpr = float(mins_per_reply)
    except (TypeError, ValueError):
        mpr = DEFAULT_MINS_PER_REPLY
    if not (0 < mpr <= MAX_MINS_PER_REPLY):
        mpr = DEFAULT_MINS_PER_REPLY

    start, end, prev_start, prev_end = resolve_period(period, frm, to, now)
    cur = _window(start, end, account, mpr)
    prev = _window(prev_start, prev_end, account, mpr)

    return {
        "period": period,
        "account": str(account or "") or None,
        "mins_per_reply": mpr,
        "timezone": "Asia/Ho_Chi_Minh",
        "generated_at": _iso(datetime.now(TZ).timestamp()),
        "current": cur,
        "previous": prev,
        "delta": _delta(cur, prev),
        # Mọi chỉ số đều tính được từ schema hiện có. Ô này còn trống; thêm vào khi gặp chỉ số
        # không dựng nổi từ dữ liệu (trả null kèm lý do), theo đúng ràng buộc "không bịa".
        "_missing": {},
        "_notes": {
            "first_response": "Chỉ bắt cặp tin khách VÀ câu đáp đều nằm trong kỳ; câu đáp rơi sang"
                              " sau mốc kết thúc kỳ không được tính.",
            "owner_replies": "Tin 'human' = chủ trả tay (từ hòm thư hoặc Zalo cá nhân của chủ).",
            "free_hours": "Chỉ là ước tính thời gian, KHÔNG quy ra tiền.",
            "new_customers": "Đếm theo lúc khách LẦN ĐẦU vào kho (customers.created_at), không phải"
                             " theo giờ từng tin. Kỳ trước khi kho bắt đầu ghi sẽ ra 0.",
        },
    }
