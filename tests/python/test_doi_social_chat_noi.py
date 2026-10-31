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
    ghi0 = []
    f.chan_doan_nut(types.SimpleNamespace(nhat_ky=ghi0.append), page.locator("[role='main']"), "Thích")
    check("chan_doan_nut liệt kê nhãn nút", ghi0 and "Thích" in ghi0[0] and "nút" in ghi0[0], ghi0)
    # Trình xem reel (DOM thật 31/10): nhãn kèm số, 2 reel xếp chồng, reel kế tiếp ở ngoài khung nhìn
    page.set_content("<div role='main'><div style='height:300px'></div>"
                     "<div role='button' aria-label='Thích, 116 reactions' id='a'>x</div>"
                     "<div role='button' aria-label='Chia sẻ, 0 lượt chia sẻ' id='c'>s</div>"
                     "<div style='height:3000px'></div><div role='button' aria-label='Thích, 540 reactions' id='b'>y</div></div>")
    m = page.locator("[role='main']")
    n1 = f.nut_kem_so(m, f._THICH_CHUA, 1500)
    check("reel: chọn nút Thích của reel đang phát", n1 is not None and n1.get_attribute("id") == "a",
          n1 and n1.get_attribute("id"))
    n2 = f.nut_kem_so(m, ["Chia sẻ", "Share"], 1500)
    check("reel: thấy nút Chia sẻ kèm số", n2 is not None and n2.get_attribute("id") == "c")
    check("nhãn 'Thích' trần không bị nut_kem_so bắt nhầm 'Bày tỏ cảm xúc'",
          f.nut_kem_so(page.locator("body"), ["Bày"], 500) is None)
    # Bài mở dạng popup thật vẫn được nhận
    page.set_content("<div role='main'><h1>Trang</h1></div><div role='dialog'><div role='article'>Bài popup"
                     "<div role='button' aria-label='Thích'>Thích</div></div></div>")
    check("dialog bài popup vẫn được nhận", "Bài popup" in f.pham_vi_bai(page).inner_text())
    # Hộp đòi mã PIN Messenger: bỏ qua (Đóng), không nhập mã, không bấm "Không khôi phục", không báo lỗi
    import fb_tin  # noqa: E402
    page.set_content("<div role='main'><div role='textbox' contenteditable='true' aria-label='Tin nhắn'></div></div>"
                     "<div role='dialog'>Nhập mã PIN để khôi phục tin nhắn<input type='password' id='pin'>"
                     "<div role='button' aria-label='Không khôi phục tin nhắn' onclick=\"window.huy=1\">Không khôi phục</div>"
                     "<div role='button' aria-label='Đóng' onclick='this.parentNode.remove()'>x</div></div>")
    ghi = []
    tay = types.SimpleNamespace(bam=lambda l: l.click(), phim=lambda k: page.keyboard.press(k), nghi=lambda *a: None)
    nc2 = types.SimpleNamespace(page=page, tay=tay, nhat_ky=lambda m: ghi.append(m))
    loi = None
    try:
        fb_tin._kiem_pin(nc2)
    except Exception as e:      # noqa: BLE001
        loi = e
    check("hộp PIN được đóng, không lỗi", loi is None and not fb_tin._co_pin(nc2), loi)
    check("không bấm 'Không khôi phục', không gõ PIN", page.evaluate("window.huy") is None and any("bỏ qua" in m for m in ghi))
    b.close()

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
