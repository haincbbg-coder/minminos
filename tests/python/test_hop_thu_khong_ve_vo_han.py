"""Thanh bot ở Hộp thư không được vẽ lại vô tận (đã treo cứng tab ở 26.10.50-26.10.60).
python tests/run.py hop_thu_khong_ve_vo_han"""
import pathlib, sys
src = (pathlib.Path(__file__).resolve().parents[2] / "dashboard" / "conversations.js").read_text("utf-8")
ok = True
def check(ten, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + ten); ok = ok and cond
check("không còn so JSON.stringify(undefined) với 'null' để quyết định vẽ lại",
      "JSON.stringify((_px.items[0] || {}).id)" not in src)
check("vẽ lại chỉ khi chữ ký đổi", "chuKyBot() !== chuKyTruoc" in src)
check("chữ ký luôn là chuỗi, không bao giờ undefined", '.join("|")' in src)
sys.exit(0 if ok else 1)
