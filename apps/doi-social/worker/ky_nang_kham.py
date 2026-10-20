"""Kỹ năng nội bộ: khám trang (chẩn đoán). Mở một link trong profile, cuộn vài lần, ghi DÀN Ý phần tử
(vai trò, nhãn trợ năng, chữ, link) thành tệp .txt gửi về MinMin. KHÔNG bấm, KHÔNG gõ gì.

Dùng khi Facebook/TikTok... đổi giao diện: người sửa đọc dàn ý thật để chỉnh bộ chọn phần tử, thay vì
đoán. Không gửi mật khẩu hay ô nhập mật khẩu: giá trị của mọi ô nhập đều bị bỏ.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

_JS_DAN_Y = r"""
(toiDa) => {
  const out = [];
  const nhin = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const sel = 'a,button,input,textarea,select,[role],[contenteditable="true"],[aria-label],h1,h2,h3,h4';
  for (const e of document.querySelectorAll(sel)) {
    if (out.length >= toiDa) break;
    if (!nhin(e)) continue;
    const role = e.getAttribute('role') || '';
    const tag = e.tagName.toLowerCase();
    const al = (e.getAttribute('aria-label') || '').slice(0, 120);
    let chu = '';
    if (!['input', 'textarea', 'select'].includes(tag)) chu = (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 140);
    const href = tag === 'a' ? (e.getAttribute('href') || '').slice(0, 160) : '';
    const them = [];
    for (const k of ['aria-pressed', 'aria-checked', 'aria-expanded', 'aria-disabled', 'data-testid', 'data-e2e', 'name', 'type', 'placeholder', 'aria-posinset']) {
      const v = e.getAttribute(k); if (v) them.push(k + '=' + v.slice(0, 60));
    }
    const r = e.getBoundingClientRect();
    out.push([tag, role, al, chu, href, them.join(' '), Math.round(r.x) + ',' + Math.round(r.y) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)].join(' | '));
  }
  return out;
}
"""


def kham_trang(nc) -> str:
    url = str(nc.ts.get("url") or "")
    if not url.startswith("https://"):
        from ngu_canh import LoiKyNang
        raise LoiKyNang("thiếu link cần khám")
    nc.nhat_ky(f"Khám trang {url} (không bấm gì)")
    nc.mo(url)
    time.sleep(6)
    dong = [f"# URL cuối: {nc.page.url}", f"# Tiêu đề: {nc.page.title()}", f"# Lúc: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for i in range(int(nc.ts.get("cuon") or 0) + 1):
        if i:
            nc.page.mouse.wheel(0, 900)
            time.sleep(2.5)
        try:
            ds = nc.page.evaluate(_JS_DAN_Y, 1500)
        except Exception as e:
            ds = [f"(không đọc được dàn ý: {e})"]
        dong.append(f"## Màn {i + 1} (tag | role | aria-label | chữ | href | thuộc tính | vị trí)")
        dong.extend(ds)
        dong.append("")
    try:
        snap = nc.page.locator("body").aria_snapshot(timeout=15000)
        dong.append("## Cây trợ năng (aria snapshot)")
        dong.append(snap[:300000])
    except Exception as e:
        dong.append(f"(không có aria snapshot: {type(e).__name__})")
    td = Path(tempfile.mkdtemp(prefix="minmin-kham-"))
    p = td / "kham-trang.txt"
    p.write_text("\n".join(dong)[:9_500_000], encoding="utf-8")
    nc.gui_tep_ket_qua(p)
    nc.nhat_ky(f"Đã gửi dàn ý {len(dong)} dòng")
    return f"Đã khám {nc.page.url}: {len(dong)} dòng dàn ý (tệp kham-trang.txt)."


KICH_BAN = {"kham_trang": kham_trang}
