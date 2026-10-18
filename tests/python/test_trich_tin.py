"""Nhặt thông tin từ tin khách, cờ tin gấp chat riêng (26.10.169).

    python tests/run.py trich_tin
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-trich-")
import trich_tin as t  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


check("bắt số điện thoại", t.phan_tich("chị 0912345678 nhé").get("sdt") == ["0912345678"])
check("bắt +84", t.phan_tich("+84912345678").get("sdt") == ["+84912345678"])
check("không nhặt dãy số dài làm SĐT", "sdt" not in t.phan_tich("mã đơn 09123456789012"))
r = t.phan_tich("STK 1234567890 Vietcombank")
check("bắt STK và ngân hàng", r.get("tk") == [{"so": "1234567890", "nh": "VIETCOMBANK"}], r)
check("số đơn không kèm chữ tài khoản thì bỏ", "tk" not in t.phan_tich("đơn 1234567890 chưa tới"))
r = t.phan_tich("tk: 0123 4567 8901 MB")
check("STK có dấu cách", r.get("tk") and r["tk"][0]["so"] == "012345678901", r)
check("SĐT không bị nhặt thành STK", "tk" not in t.phan_tich("tk em là 0912345678"))
check("bắt link, bỏ dấu chấm cuối", t.phan_tich("xem https://x.vn/a.").get("link") == ["https://x.vn/a"])
check("cờ gấp", "gấp" in t.phan_tich("em cần gấp").get("gap", []))
check("khiếu nại", "khiếu nại" in t.phan_tich("tôi muốn khiếu nại").get("gap", []))
check("'gấp đôi'? vẫn là từ gấp - chấp nhận, nhưng 'ngấp nghé' không dính",
      "gap" not in t.phan_tich("ngấp nghé"))
check("'hẹn sáng mai' không là gì", t.phan_tich("hẹn sáng mai nhé") == {})
check("rỗng", t.phan_tich("  ") == {})

# gắn vào sự kiện
e = {"sender_type": "customer", "message_type": "text", "text": "gấp, 0912345678", "metadata": {}}
tr = t.gan_vao_tin(e)
check("gắn vào metadata.trich", e["metadata"].get("trich") == tr and tr.get("sdt"))
e2 = {"sender_type": "owner", "message_type": "text", "text": "gấp 0912345678", "metadata": {}}
check("tin của chủ không phân tích", t.gan_vao_tin(e2) == {} and "trich" not in e2["metadata"])

# báo chuông
BAO = []
import inbox  # noqa: E402
inbox.add = lambda *a, **k: BAO.append((a, k))
ev = {"chat_type": "private", "sender_type": "customer", "sender_name": "Lan", "text": "gấp", "channel": "zalo_personal"}
check("chat riêng tin gấp báo chuông", t.bao_gap(ev, {"gap": ["gấp"]}, 7, now=1e6) and len(BAO) == 1)
check("báo lại trong 30 phút bị nén", not t.bao_gap(ev, {"gap": ["gấp"]}, 7, now=1e6 + 500) and len(BAO) == 1)
check("quá 30 phút báo lại", t.bao_gap(ev, {"gap": ["gấp"]}, 7, now=1e6 + t._BAO_NGHI + 1))
check("nhóm không báo", not t.bao_gap(dict(ev, chat_type="group"), {"gap": ["gấp"]}, 8))
check("khách khác báo riêng", t.bao_gap(ev, {"gap": ["gấp"]}, 9, now=1e6))

# đi qua ghi_su_kien thật
import conversations as cv  # noqa: E402
kq = cv.ghi_su_kien({"channel": "zalo_personal", "account_id": "a1", "external_chat_id": "k1",
                     "chat_type": "private", "sender_type": "customer", "sender_name": "Mai",
                     "message_type": "text", "text": "Khiếu nại đơn, gọi 0987654321", "external_message_id": "m1"})
tin = cv.tin_nhan(kq["conversation_id"])
check("tin lưu mang metadata.trich", tin and tin[-1]["metadata"].get("trich", {}).get("sdt") == ["0987654321"], tin)
check("ghi sự kiện đã báo chuông", len(BAO) >= 4, len(BAO))

print("PASS" if not fails else f"FAILED: {fails}")
raise SystemExit(1 if fails else 0)
