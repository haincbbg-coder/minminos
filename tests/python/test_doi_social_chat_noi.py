"""26.10.323: khung chat Messenger nổi còn sót trên Facebook làm Worker đọc nhầm tên nhóm ('Đoạn chat')
và tìm nút Thích/Chia sẻ trong khung chat (lỗi thật khi chạy thử 31/10 trên nick HÁN NGỌC NHI).

    python tests/run.py doi_social_chat_noi

Chromium headless, trang Facebook giả: tên lấy đúng h1 của vùng chính, phạm vi bài bỏ qua dialog chat,
don_chat_noi đóng khung chat."""
import os
import sys
import types

from _paths import ROOT  # noqa: F401

sys.path.insert(0, str(ROOT / "apps" / "doi-social" / "worker"))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
import fb_chung as f  # noqa: E402

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


HTML = """<html><body>
<div role="dialog" aria-label="Đoạn chat"><h1>Đoạn chat</h1>
  <div role="dialog" aria-label="Chat với Lan"><div contenteditable="true" role="textbox" aria-label="Tin nhắn"></div>
  <div role="button" aria-label="Đóng đoạn chat" onclick="this.closest('[aria-label=\\'Đoạn chat\\']').remove()">x</div></div>
</div>
<div role="main"><h1>Hội Váy Đẹp Hà Nội</h1>
  <div role="article" aria-posinset="1"><div data-ad-preview="message">Cần tìm chân váy đen</div>
    <div role="button" aria-label="Thích">Thích</div><div role="button" aria-label="Gửi bài viết này cho bạn bè hoặc đăng lên trang cá nhân của bạn.">Chia sẻ</div>
    <div contenteditable="true" role="textbox" aria-label="Viết bình luận..."></div></div>
</div></body></html>"""

try:
    from playwright.sync_api import sync_playwright
except Exception as e:      # noqa: BLE001
    print("SKIP không có playwright", e)
    raise SystemExit(0)

from pathlib import Path  # noqa: E402


def _mo_trinh(pw):
    try:
        return pw.chromium.launch(headless=True)
    except Exception:
        goc = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
        exe = sorted(goc.glob("chromium-*/chrome-linux*/chrome"))
        return pw.chromium.launch(headless=True, executable_path=str(exe[-1])) if exe else None


with sync_playwright() as p:
    b = _mo_trinh(p)
    if b is None:
        print("SKIP không có Chromium trên máy này")
        raise SystemExit(0)
    page = b.new_page()
    page.set_content(HTML)
    check("ten_trang bỏ 'Đoạn chat', lấy h1 vùng chính", f.ten_trang(page) == "Hội Váy Đẹp Hà Nội", f.ten_trang(page))
    pv = f.pham_vi_bai(page)
    check("pham_vi_bai không nhận dialog chat", "Cần tìm chân váy" in pv.inner_text(), pv.inner_text()[:80])
    check("thấy nút Thích trong phạm vi bài", f.tim_nut(pv, f._THICH_CHUA, 1500) is not None)
    nc = types.SimpleNamespace(page=page, nhat_ky=lambda *a, **k: None)
    check("don_chat_noi đóng khung chat", f.don_chat_noi(nc) == 1 and page.locator("text=Đoạn chat").count() == 0)
    check("không có chat thì không làm gì", f.don_chat_noi(nc) == 0)
    # Bài mở dạng popup thật vẫn được nhận
    page.set_content("<div role='main'><h1>Trang</h1></div><div role='dialog'><div role='article'>Bài popup"
                     "<div role='button' aria-label='Thích'>Thích</div></div></div>")
    check("dialog bài popup vẫn được nhận", "Bài popup" in f.pham_vi_bai(page).inner_text())
    b.close()

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
