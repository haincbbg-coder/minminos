"""Kỹ năng nội bộ: quét Trang / tài khoản của một nick (26.10.192). CHỈ ĐỌC, không bấm gì công khai.

- Facebook: danh sách Trang nick quản lý (facebook.com/pages/?category=your_pages). Bố cục quan sát thật
  21/10/2026: mỗi Trang có link `aria-label="Ảnh đại diện của <tên>"` trỏ tới trang, danh sách nạp dần khi cuộn.
- Instagram / TikTok / Threads: tài khoản đang đăng nhập, đọc từ link "Trang cá nhân"/"Profile" trên thanh điều
  hướng. Chưa đăng nhập thì ghi nhật ký và bỏ qua nền tảng đó (không xoá danh sách cũ của nền tảng đó).

Gửi về MinMin qua POST /doi-social/may/dich-den {viec_id, nen_tang: [đã quét được], muc: [...]}.
"""
from __future__ import annotations

import re
import time
import urllib.parse

_JS_TRANG_FB = r"""() => {
  const goc = document.querySelector('[role="main"]') || document.body;
  const out = {};
  goc.querySelectorAll('a[aria-label]').forEach(a => {
    const al = a.getAttribute('aria-label') || '';
    const m = al.match(/^(Ảnh đại diện của|Profile picture of|Ảnh đại diện)\s+(.+)$/i);
    if (!m) return;
    const href = a.href || '';
    if (!/facebook\.com\//.test(href)) return;
    const img = a.querySelector('image, img');
    const anh = img ? (img.getAttribute('xlink:href') || img.getAttribute('href') || img.src || '') : '';
    out[href] = {ten: m[2].trim(), link: href, anh: anh};
  });
  return Object.values(out);
}"""


def _chuan_fb(link: str) -> str:
    """https://www.facebook.com/profile.php?id=123 hoặc /123 hoặc /ten-trang (bỏ tham số rác)."""
    try:
        u = urllib.parse.urlsplit(link)
    except Exception:
        return link
    q = urllib.parse.parse_qs(u.query)
    if u.path.rstrip("/") == "/profile.php" and q.get("id"):
        return f"https://www.facebook.com/profile.php?id={q['id'][0]}"
    duong = u.path.rstrip("/")
    return "https://www.facebook.com" + duong if duong else link


def _ma_fb(link: str) -> str:
    m = re.search(r"[?&]id=(\d+)", link) or re.search(r"facebook\.com/(\d{6,})", link)
    return m.group(1) if m else ""


def quet_facebook(nc) -> list:
    nc.nhat_ky("Facebook: mở danh sách Trang nick quản lý")
    nc.mo("https://www.facebook.com/pages/?category=your_pages")
    time.sleep(5)
    nc.kiem_dang_nhap()
    trang = {}
    dung_yen = 0
    for _ in range(25):                 # cuộn tới khi không nạp thêm Trang nào
        try:
            ds = nc.page.evaluate(_JS_TRANG_FB) or []
        except Exception:
            ds = []
        truoc = len(trang)
        for t in ds:
            link = _chuan_fb(str(t.get("link") or ""))
            if link and link not in trang:
                trang[link] = {"nen_tang": "facebook", "loai": "trang", "ten": str(t.get("ten") or "")[:200],
                               "link": link, "ma": _ma_fb(link),
                               "anh": str(t.get("anh") or "") if str(t.get("anh") or "").startswith("https://") else ""}
        dung_yen = dung_yen + 1 if len(trang) == truoc else 0
        if dung_yen >= 2:
            break
        nc.page.mouse.wheel(0, 1800)
        time.sleep(2.0)
    nc.nhat_ky(f"Facebook: thấy {len(trang)} Trang")
    return list(trang.values())


def _ho_so(nc, url: str, mau_link: str, nhan: str):
    """Link hồ sơ của tài khoản đang đăng nhập (từ thanh điều hướng). None nếu chưa đăng nhập."""
    nc.mo(url)
    time.sleep(6)
    try:
        nc.kiem_dang_nhap()
    except Exception as e:      # chưa đăng nhập nền tảng này: bỏ qua, không phải lỗi của việc quét
        nc.nhat_ky(f"{nhan}: {e}")
        return None
    try:
        href = nc.page.evaluate(r"""([mau]) => {
          const re = new RegExp(mau);
          const ung = [...document.querySelectorAll('a[href]')].filter(a => re.test(a.getAttribute('href') || ''));
          const uu = ung.find(a => /(Trang cá nhân|Profile|Hồ sơ)/i.test((a.getAttribute('aria-label') || '') + ' ' + (a.innerText || '')));
          const a = uu || null;
          return a ? a.href : '';
        }""", [mau_link]) or ""
    except Exception:
        href = ""
    return href or None


def quet_instagram(nc):
    href = _ho_so(nc, "https://www.instagram.com/", r"^/[A-Za-z0-9._]{1,30}/?$", "Instagram")
    if not href:
        return None
    ten = urllib.parse.urlsplit(href).path.strip("/")
    if ten in ("explore", "reels", "direct", "accounts"):
        return None
    return [{"nen_tang": "instagram", "loai": "tai_khoan", "ten": "@" + ten, "link": f"https://www.instagram.com/{ten}/",
             "ma": ten}]


def quet_tiktok(nc):
    href = _ho_so(nc, "https://www.tiktok.com/foryou", r"^/@[^/?#]+", "TikTok")
    if not href:
        return None
    m = re.search(r"/@([^/?#]+)", href)
    if not m:
        return None
    return [{"nen_tang": "tiktok", "loai": "tai_khoan", "ten": "@" + m.group(1),
             "link": f"https://www.tiktok.com/@{m.group(1)}", "ma": m.group(1)}]


def quet_threads(nc):
    href = _ho_so(nc, "https://www.threads.com/", r"^/@[^/?#]+", "Threads")
    if not href:
        return None
    m = re.search(r"/@([^/?#]+)", href)
    if not m:
        return None
    return [{"nen_tang": "threads", "loai": "tai_khoan", "ten": "@" + m.group(1),
             "link": f"https://www.threads.com/@{m.group(1)}", "ma": m.group(1)}]


_QUET = {"facebook": quet_facebook, "instagram": quet_instagram, "tiktok": quet_tiktok, "threads": quet_threads}


def quet_tai_khoan(nc) -> str:
    can = [x for x in (nc.ts.get("nen_tang") or list(_QUET)) if x in _QUET]
    da_quet, muc, tom = [], [], []
    for nt in can:
        if nc.nen_dung():
            break
        cu = nc.nen_tang
        nc.nen_tang = nt              # kiem_dang_nhap() dùng bảng nhận biết của đúng nền tảng
        try:
            kq = _QUET[nt](nc)
        except Exception as e:
            nc.nhat_ky(f"{nt}: quét lỗi {type(e).__name__}: {str(e)[:150]}")
            kq = None
        finally:
            nc.nen_tang = cu
        if kq is None:
            tom.append(f"{nt}: chưa đăng nhập / không đọc được")
            continue
        da_quet.append(nt)
        muc.extend(kq)
        tom.append(f"{nt}: {len(kq)}" + (" Trang" if nt == "facebook" else " tài khoản"))
    d = nc.may_chu.goi("POST", "/doi-social/may/dich-den", {"viec_id": nc.vid, "nen_tang": da_quet, "muc": muc}) or {}
    nc.nhat_ky(f"Đã gửi {d.get('so', len(muc))} nơi đăng về MinMin")
    return "Quét xong. " + "; ".join(tom)


KICH_BAN = {"quet_tai_khoan": quet_tai_khoan}
