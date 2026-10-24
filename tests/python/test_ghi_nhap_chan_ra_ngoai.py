# -*- coding: utf-8 -*-
"""Mức Ghi nháp (auto) chặn ĐÚNG mọi hành động ra ngoài, như lời dặn hệ thống nói (26.10.219).

    python tests/run.py ghi_nhap_chan_ra_ngoai     (KHÔNG mạng)

Trước bản này, connector không khai `tool_meta.danger` (16 cái trong danh mục: gmail,
google-ads, shopee, tiktok-shop, lazada, haravan, sapo, kiotviet, nhanh-vn...) chỉ được đoán
bằng WRITE_HINTS so chuỗi con:
- `send_email` thành "write" -> CHẠY ở mức Ghi nháp.
- `mutate` (Google Ads) không khớp chữ nào -> "read" -> chạy cả ở mức Chỉ đọc.
- `list_posts`, `get_post_insights` dính "post" -> bị coi là ghi, ẩn oan ở mức Chỉ đọc.
Chủ chốt sửa CODE cho đúng lời dặn (mức Ghi nháp chặn hành động ra ngoài).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        _fails.append(name)


import mcp_catalog as m  # noqa: E402

KHONG_KHAI = {}   # connector không khai tool_meta: đúng cảnh 16 connector trong danh mục

# 1. Hành động ra ngoài bị chặn ở Ghi nháp và Chỉ đọc, vẫn chạy ở Toàn quyền.
for tool in ("send_email", "gmail_send", "sendMessage", "zalo_send_message", "forward",
             "share_file", "trash_thread", "mutate", "pause_campaign", "ads_activate_entity",
             "create_order", "refund_payment", "post_comment", "reply_review", "delete_note",
             "fetch_and_send", "get_then_delete", "publish_post", "transfer_funds"):
    ok_auto, _ = m.allowed(KHONG_KHAI, "full", "auto", tool, {})
    ok_sug, _ = m.allowed(KHONG_KHAI, "full", "suggest", tool, {})
    ok_full, _ = m.allowed(KHONG_KHAI, "full", "full", tool, {})
    check(f"{tool}: chặn ở Ghi nháp", not ok_auto)
    check(f"{tool}: chặn ở Chỉ đọc", not ok_sug)
    check(f"{tool}: Toàn quyền vẫn chạy", ok_full)

# 2. Ghi nháp vẫn được ghi trong phạm vi (tạo/sửa thường) - chatbot "Được ghi" và phiên Coding
#    dựa vào nghĩa này.
for tool in ("create_event", "update_sheet", "add_row", "upload_file", "edit_note"):
    ok_auto, _ = m.allowed(KHONG_KHAI, "full", "auto", tool, {})
    ok_sug, _ = m.allowed(KHONG_KHAI, "full", "suggest", tool, {})
    check(f"{tool}: Ghi nháp được ghi", ok_auto)
    check(f"{tool}: Chỉ đọc thì không", not ok_sug)

# 3. Tool đọc không bị chặn oan nữa (lỗi cũ so chuỗi con).
for tool in ("list_posts", "get_post_insights", "list_orders", "get_messages",
             "search_campaigns", "get_ad_accounts", "fetch_inbox", "run_report"):
    ok_sug, _ = m.allowed(KHONG_KHAI, "full", "suggest", tool, {})
    check(f"{tool}: đọc được ở Chỉ đọc", ok_sug, m.classify(KHONG_KHAI, tool))

# 4. Khai báo tường minh của connector vẫn thắng mọi đoán.
khai = {"tool_meta": {"read": ["send_report_preview"], "write": ["pause_note"]}}
check("tool_meta.read thắng đoán ra-ngoài", m.classify(khai, "send_report_preview") == "read")
check("tool_meta.write thắng đoán ra-ngoài", m.classify(khai, "pause_note") == "write")

# 5. Kết nối đặt mức 'Ghi được' (safe) trong lượt Toàn quyền: gửi mail giờ cũng bị chặn, đúng
#    nghĩa safe = không làm việc nguy hiểm.
ok, _ = m.allowed(KHONG_KHAI, "safe", "full", "send_email", {})
check("kết nối mức safe không gửi mail được", not ok)

if _fails:
    print(f"\n{len(_fails)} FAIL")
    sys.exit(1)
print("\nTất cả OK")
