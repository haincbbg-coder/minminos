"""test_the_bieu_do.py - thẻ biểu đồ JAVIS_CARD trong khung chat (26.10.175, cổng từ Javis 0.201.0)."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import ROOT, SERVER  # noqa: E402,F401
import channel_context  # noqa: E402
import chat_cards  # noqa: E402
import nguon  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


chart = {"type": "chart", "title": "Doanh thu", "labels": ["T2", "T3"],
         "series": [{"name": "Tuần này", "data": [1200000, 900000]}, {"name": "Tuần trước", "data": [1000000, 950000]}]}
t = chat_cards.card_to_text(json.dumps(chart))
check("biểu đồ hạ thành một dòng mỗi nhãn", "- T2: Tuần này 1.200.000 / Tuần trước 1.000.000" in t and t.startswith("**Doanh thu**"))
t = chat_cards.card_to_text(json.dumps({"type": "stats", "items": [{"label": "Đơn", "value": "128", "delta": "+12%"}]}))
check("ô số hạ thành nhãn: giá trị (delta)", "- Đơn: **128** (+12%)" in t)
t = chat_cards.card_to_text(json.dumps({"type": "buttons", "title": "Duyệt?", "buttons": [{"label": "Duyệt"}, {"label": "Sửa"}]}))
check("nút hạ thành danh sách đánh số", "1. Duyệt" in t and "2. Sửa" in t)
check("thẻ hỏng hoặc lạ ra rỗng", chat_cards.card_to_text("{bad") == "" and
      chat_cards.card_to_text(json.dumps({"type": "html", "x": 1})) == "")

msg = "Quý này ổn.\n<!-- JAVIS_CARD: " + json.dumps(chart, ensure_ascii=False) + " -->\nHết."
out = channel_context.strip_control_blocks(msg)
check("kênh chữ: thẻ thành chữ, không lộ khối", "JAVIS_CARD" not in out and "- T3:" in out and "Hết." in out)
check("prompt khung chat web nói về thẻ", "JAVIS_CARD" in channel_context.build_channel_block("dashboard", {}))
check("prompt Telegram không nói về thẻ", "JAVIS_CARD" not in channel_context.build_channel_block("telegram", {"chat_id": "1"}))

# Số trong JSON của thẻ không được tính là số cần nguồn (đơn vị khác bảng, sẽ cảnh báo oan)
r = nguon.neo_so('Doanh thu 11,84 tỷ <!-- JAVIS_CARD: {"type":"chart","labels":["T7"],"series":[{"name":"a","data":[3760,4320,9999]}]} -->',
                 "", ["11840000000"])
check("chân nguồn bỏ qua JSON của thẻ", r["khong_nguon"] == [] and 9999 not in r["co_nguon"])

html = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
check("index.html nạp chat-card.js", "/static/chat-card.js?v=" in html)
render = (ROOT / "dashboard" / "chat-render.js").read_text(encoding="utf-8")
i_card = render.find("window.JavisCard.replaceIn(raw, put)")
i_vis = render.find("raw = visibleMarkdown(raw);", i_card)
check("chat-render vẽ thẻ trước khi bỏ comment ẩn", 0 < i_card < i_vis)

print()
print("FAIL" if fails else "PASS", f"({len(fails)} failed)")
raise SystemExit(1 if fails else 0)
