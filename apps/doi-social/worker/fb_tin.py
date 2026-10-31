"""Kỹ năng Facebook về TRẢ LỜI và TIN NHẮN: fb_tra_loi_binh_luan, fb_tra_loi_tin_nhan, fb_nhan_tin_ds, fb_gui_tin."""
from __future__ import annotations

import re
import time
import urllib.parse

from fb_chung import (FB, chuan_link, dau_tien_thay, doc_bai, ds_binh_luan, mo_va_kiem, ms, pham_vi_bai,
                      phai_dung, thay_chu, tim_nut, tra_loi_binh_luan)
from ngu_canh import LoiKyNang
from nguoi import chon_cau

# ---------------------------------------------------------------------------- trả lời bình luận
_TB_BL = re.compile(r"(bình luận|commented|nhắc đến bạn|nhắc bạn|mentioned you|đã trả lời|replied|phản hồi)", re.I)
_TB_BAI_MINH = re.compile(r"(bài viết của bạn|your post|ảnh của bạn|your photo|video của bạn|your video|"
                          r"bình luận của bạn|your comment)", re.I)
_TACH_TAC_GIA = re.compile(r"^(.+?)\s+(đã|và|and|commented|mentioned|replied)\b", re.I)


def _doc_thong_bao(nc, toi_da: int) -> list:
    mo_va_kiem(nc, FB + "/notifications")
    page = nc.page
    nc.tay.luot_doc(nc.rng.uniform(3, 6))
    ra, thay = [], set()
    for _ in range(4):
        for a in page.locator("a[href*='comment_id'], a[href*='/posts/'], a[href*='/permalink/'], "
                              "a[href*='story_fbid'], a[href*='/videos/']").all()[:120]:
            try:
                href = a.get_attribute("href") or ""
                chu = re.sub(r"\s+", " ", a.inner_text(timeout=1500) or "").strip()
            except Exception:
                continue
            if not href or href in thay or not _TB_BL.search(chu):
                continue
            thay.add(href)
            m = _TACH_TAC_GIA.match(chu)
            ra.append({"link": urllib.parse.urljoin(FB, href), "chu": chu[:300],
                       "tac_gia": (m.group(1) if m else "").strip()[:80],
                       "bai_cua_nick": bool(_TB_BAI_MINH.search(chu))})
            if len(ra) >= toi_da:
                return ra
        nc.tay.luot(2)
    return ra


def _khoa_tb(link: str) -> str:
    p = urllib.parse.urlsplit(link)
    q = dict(urllib.parse.parse_qsl(p.query))
    return f"fb_tlbl:{p.path.rstrip('/')}:{q.get('comment_id', '')}:{q.get('reply_comment_id', '')}"


def fb_tra_loi_binh_luan(nc) -> str:
    sp = str(nc.ts.get("san_pham") or "")
    tb = _doc_thong_bao(nc, int(nc.ts.get("so_thong_bao") or 20))
    nc.nhat_ky(f"Đọc được {len(tb)} thông báo bình luận/nhắc tên")
    lam = 0
    for t in tb:
        if phai_dung(nc) or nc.con_lai("tra_loi_binh_luan") <= 0:
            break
        khoa = _khoa_tb(t["link"])
        if nc.da_lam(khoa):
            continue
        try:
            mo_va_kiem(nc, t["link"])
            pv = pham_vi_bai(nc.page)
            bai = doc_bai(pv)
            ds = ds_binh_luan(nc.page)
            if t["tac_gia"]:
                ds_tg = []
                for b in ds:
                    try:
                        nhan = b.get_attribute("aria-label", timeout=1000) or ""
                    except Exception:
                        nhan = ""
                    if t["tac_gia"].lower() in nhan.lower():
                        ds_tg.append(b)
                ds = ds_tg or ds
            if not ds:
                nc.su_kien("tra_loi_binh_luan", "bo_qua", "Không tìm thấy bình luận trong thông báo", link=t["link"])
                continue
            bl = ds[-1]
            chu_bl = re.sub(r"\s+", " ", bl.inner_text(timeout=ms(3000)) or "").strip()[:600]
            kq = nc.ai("tra_loi_binh_luan", {"bai_cua_nick": t["bai_cua_nick"], "bai": bai,
                                             "binh_luan": {"tac_gia": t["tac_gia"], "chu": chu_bl}, "san_pham_id": sp})
            noi_dung = str(kq.get("noi_dung") or "").strip()
            if not noi_dung:
                continue
            if nc.che_do in ("chay_thu", "duyet_truoc"):
                nc.ban_nhap(loai="tra_loi", noi_dang="fb_nhom" if "/groups/" in t["link"] else "fb_tuong",
                            link_goc=t["link"], bai_goc=(bai.get("chu") or "")[:600] + f"\n\n[Bình luận] {chu_bl}",
                            ly_do=t["chu"][:200], noi_dung=noi_dung, san_pham_id=sp)
                nc.su_kien("tra_loi_binh_luan", "thong_tin",
                           ("Chạy thử: " if nc.chay_thu else "") + f"tạo nháp trả lời: {noi_dung[:100]}", link=t["link"])
                if nc.che_do == "duyet_truoc":
                    nc.ghi_da_lam(khoa)
                lam += 1
                continue
            r = tra_loi_binh_luan(nc, bl, noi_dung)
            if r == "thanh_cong":
                nc.ghi_da_lam(khoa)
                nc.su_kien("tra_loi_binh_luan", "thanh_cong", f"Trả lời {t['tac_gia'] or 'bình luận'}: {noi_dung[:100]}",
                           link=t["link"])
                lam += 1
            else:
                nc.su_kien("tra_loi_binh_luan", "loi", "Không thấy nút Phản hồi" if r == "khong_thay"
                           else "Đã gửi nhưng chưa thấy câu trả lời hiện", link=t["link"])
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien("tra_loi_binh_luan", "loi", str(e), link=t["link"])
        nc.nghi_thao_tac()
    return f"Trả lời {lam} bình luận" + (" (nháp)." if nc.che_do != "dang_luon" else ".")


# ---------------------------------------------------------------------------- Messenger
_O_TIN = re.compile(r"(^Tin nhắn$|^Message$|^Aa$|Viết tin nhắn|Write a message|Nhắn tin|Send a message)", re.I)
_PIN = re.compile(r"(mã PIN|Enter your PIN|Nhập mã PIN|PIN của bạn|your PIN|khôi phục tin nhắn|restore your chat history|"
                  r"end-to-end encrypted chats? (are|is) locked)", re.I)
_CHUA_DOC = re.compile(r"(chưa đọc|Unread|tin nhắn mới|new message)", re.I)
_NHOM_CHAT = re.compile(r"(\d+\s*(thành viên|members)|Thêm người|Add people|nhóm chat|group chat)", re.I)


# Chỉ đóng hộp, KHÔNG bấm "Không khôi phục tin nhắn" (Facebook cảnh báo mất lịch sử chat).
_BO_PIN = ["Đóng", "Close", "Bỏ qua", "Skip", "Để sau", "Not now", "Không phải bây giờ", "Lúc khác", "Maybe later"]


def _co_pin(nc) -> bool:
    try:
        loc = nc.page.get_by_text(_PIN)
        return loc.count() > 0 and loc.first.is_visible()
    except Exception:
        return False


def _kiem_pin(nc) -> None:
    """Messenger hiện hộp đòi mã PIN khôi phục tin nhắn mã hoá: Worker KHÔNG nhập PIN, chỉ đóng hộp/bỏ qua
    rồi làm tiếp (tin nhắn mới vẫn gửi, đọc được). Không đóng được thì vẫn làm tiếp, chỉ ghi nhật ký."""
    if not _co_pin(nc):
        return
    page = nc.page
    for _ in range(3):
        hop = page.get_by_role("dialog").filter(has_text=_PIN)
        pham_vi = hop.first if hop.count() else page
        nut = tim_nut(pham_vi, _BO_PIN, 1500) or tim_nut(pham_vi, ["Đóng", "Close"], 800, chinh_xac=False)
        try:
            if nut:
                nc.tay.bam(nut)
            else:
                nc.tay.phim("Escape")
        except Exception:
            pass
        nc.tay.nghi(0.8, 1.6)
        if not _co_pin(nc):
            nc.nhat_ky("Messenger đòi mã PIN: đã bỏ qua hộp PIN (không nhập mã), làm tiếp")
            return
    nc.nhat_ky("Messenger vẫn hiện yêu cầu mã PIN; không nhập mã, thử làm tiếp với tin nhắn mới")


def o_tin_nhan(page, timeout_ms: int = 10000):
    return dau_tien_thay([page.get_by_role("textbox", name=_O_TIN),
                          page.locator("[role='main'] [contenteditable='true'][role='textbox']"),
                          page.locator("[contenteditable='true'][role='textbox'][aria-label]")], timeout_ms)


def _doc_hoi_thoai(nc) -> list:
    """[{tu: khach|bot, noi_dung}] đọc từ khung chat đang mở. Tin bên phải màn hình là của nick."""
    try:
        return nc.page.evaluate("""() => {
          const main = document.querySelector('[role="main"]') || document.body;
          const r = main.getBoundingClientRect(); const giua = r.left + r.width / 2;
          const out = [];
          main.querySelectorAll('[role="row"]').forEach(row => {
            const t = (row.innerText || '').trim();
            if (!t || t.length > 2000) return;
            const nodes = row.querySelectorAll('div[dir="auto"]');
            const el = nodes.length ? nodes[nodes.length - 1] : row;
            const b = el.getBoundingClientRect();
            if (!b.width) return;
            out.push({tu: (b.left + b.width / 2) > giua ? 'bot' : 'khach', noi_dung: (el.innerText || t).trim()});
          });
          return out.slice(-20);
        }""") or []
    except Exception:
        return []


def _gui_tin(nc, noi_dung: str, mo_ta: str, hanh_dong: str) -> str:
    """Gõ và gửi vào khung chat đang mở. 'thanh_cong' | 'chay_thu' | 'khong_thay' | 'khong_hien'."""
    o = o_tin_nhan(nc.page)
    if not o:
        return "khong_thay"
    if not nc.duoc_bam_cong_khai(mo_ta, hanh_dong):
        return "chay_thu"
    nc.tay.bam(o)
    nc.tay.nghi(0.5, 1.2)
    nc.tay.go_binh_luan(noi_dung)
    nc.tay.nghi(0.8, 2.0)
    nc.tay.phim("Enter")
    han = time.monotonic() + ms(12000) / 1000
    while time.monotonic() < han:
        try:
            if not (o.inner_text(timeout=1000) or "").strip():
                break
        except Exception:
            break
        time.sleep(0.5)
    return "thanh_cong" if thay_chu(nc.page.locator("[role='main']"), noi_dung, 10000) else "khong_hien"


def _ds_hoi_thoai(nc, toi_da: int) -> list:
    page = nc.page
    ra, thay = [], set()
    for a in page.locator("a[href*='/messages/t/'], a[href*='/messages/e2ee/t/']").all()[:80]:
        try:
            href = a.get_attribute("href") or ""
            chu = (a.inner_text(timeout=1500) or "").strip()
            nhan = a.get_attribute("aria-label") or ""
        except Exception:
            continue
        if not href or href in thay:
            continue
        thay.add(href)
        dong = [d.strip() for d in chu.splitlines() if d.strip()]
        try:
            dam = a.evaluate("e => [...e.querySelectorAll('span')].some(s => parseInt(getComputedStyle(s).fontWeight) >= 600 "
                             "&& s.innerText.trim().length > 3)")
        except Exception:
            dam = False
        ra.append({"link": urllib.parse.urljoin(FB, href), "ten": dong[0][:80] if dong else "",
                   "chua_doc": bool(_CHUA_DOC.search(chu + " " + nhan)) or bool(dam),
                   "nhom_chat": "," in (dong[0] if dong else "")})
    chua = [h for h in ra if h["chua_doc"] and not h["nhom_chat"]]
    chua.reverse()                       # danh sách mới nhất ở trên: khách chờ lâu nhất là cuối danh sách
    return chua[:toi_da]


# ---------------------------------------------------------------------------- Hộp thư Meta Business Suite
# Nick đang ở danh nghĩa Trang (quản trị fanpage) mở /messages/ thì Facebook chuyển sang Hộp thư của
# Business Suite (business.facebook.com/latest/inbox). Bố cục quan sát 21/10/2026 bằng kỹ năng khám trang:
#  - lọc "Chưa đọc": div[role=button][aria-label="Chưa đọc"];
#  - mỗi hội thoại: div[role=presentation] cao ~92px ở cột trái, chữ "Tên  Bạn: <tin cuối>  ngày" ("Bạn:" =
#    tin cuối do Trang gửi, tức khách KHÔNG chờ), kèm grid nút "Chuyển đến thư mục Xong";
#  - khung tin: div[role=region] "Vùng chứa danh sách tin nhắn...", tin của Trang nằm nửa phải;
#  - ô soạn: div[role=textbox] contenteditable ở chân khung, Enter để gửi.
_BS_LOC_CHUA_DOC = re.compile(r"^(Chưa đọc|Unread)$", re.I)


def _bs_ds_hoi_thoai(nc, toi_da: int) -> list:
    try:
        nut = dau_tien_thay([nc.page.get_by_role("button", name=_BS_LOC_CHUA_DOC)], ms(6000))
        if nut:
            nc.tay.bam(nut)          # chỉ lọc danh sách, không phải thao tác công khai
            nc.tay.nghi(2.0, 3.5)
    except Exception:
        pass
    try:
        ds = nc.page.evaluate(r"""() => {
          const out = [];
          document.querySelectorAll('div[role="presentation"]').forEach((e, i) => {
            const r = e.getBoundingClientRect();
            if (r.height < 50 || r.height > 140 || r.x > 200 || r.width < 250) return;
            const t = (e.innerText || '').trim(); if (!t) return;
            const dong = t.split('\n').map(x => x.trim()).filter(Boolean);
            out.push({i: i, ten: dong[0] || '', tin_cuoi: dong.slice(1, 3).join(' '), y: r.y});
          });
          return out;
        }""") or []
    except Exception:
        ds = []
    ra = [h for h in ds if h.get("ten") and not str(h.get("tin_cuoi") or "").startswith(("Bạn:", "You:"))]
    ra.reverse()                    # danh sách mới nhất ở trên: khách chờ lâu nhất xử lý trước
    return ra[:toi_da]


def _bs_mo(nc, h: dict) -> bool:
    loc = nc.page.locator('div[role="presentation"]').nth(int(h["i"]))
    try:
        loc.scroll_into_view_if_needed(timeout=5000)
        nc.tay.bam(loc)
    except Exception as e:
        nc.nhat_ky(f"Bấm mở hội thoại bằng tay người lỗi ({type(e).__name__}: {str(e)[:120]}), thử bấm thẳng")
        try:
            loc.click(timeout=8000)
        except Exception as e2:
            nc.nhat_ky(f"Không mở được hội thoại: {type(e2).__name__}: {str(e2)[:160]}")
            return False
    nc.tay.nghi(2.5, 4.5)
    return True


def _bs_doc(nc) -> list:
    try:
        return nc.page.evaluate(r"""() => {
          const vung = document.querySelector('div[role="region"]'); if (!vung) return [];
          const r = vung.getBoundingClientRect(); const giua = r.left + r.width / 2;
          const out = []; const da = new Set();
          vung.querySelectorAll('div[dir="auto"], span[dir="auto"]').forEach(el => {
            if (el.querySelector('[dir="auto"]')) return;          // chỉ lấy lá
            const t = (el.innerText || '').trim(); if (!t || t.length > 2000 || da.has(el)) return;
            const b = el.getBoundingClientRect(); if (!b.width) return;
            if (/^\d{1,2}:\d{2}/.test(t) && t.length < 25) return;   // mốc giờ
            da.add(el);
            out.push({tu: (b.left + b.width / 2) > giua ? 'bot' : 'khach', noi_dung: t});
          });
          return out.slice(-20);
        }""") or []
    except Exception:
        return []


def _bs_vung(nc) -> str:
    """Mô tả cấu trúc (không chứa nội dung tin) để chẩn đoán khi đọc khung tin không ra."""
    try:
        return nc.page.evaluate(r"""() => {
          const v = [...document.querySelectorAll('div[role="region"]')];
          return v.map(e => { const r = e.getBoundingClientRect();
            return (e.getAttribute('aria-label') || '').slice(0, 40) + ' @' + Math.round(r.x) + ',' + Math.round(r.y) + ' ' +
              Math.round(r.width) + 'x' + Math.round(r.height) + ' dir=' + e.querySelectorAll('[dir="auto"]').length +
              ' row=' + e.querySelectorAll('[role="row"],[role="gridcell"],[role="listitem"]').length; }).join(' ; ') || 'không có';
        }""")
    except Exception as e:
        return f"lỗi {type(e).__name__}"


def _bs_gui(nc, noi_dung: str, mo_ta: str) -> str:
    o = dau_tien_thay([nc.page.locator('div[role="textbox"][contenteditable="true"]').last,
                       nc.page.get_by_role("textbox").last], ms(8000))
    if not o:
        return "khong_thay"
    if not nc.duoc_bam_cong_khai(mo_ta, "tra_loi_tin_nhan"):
        return "chay_thu"
    nc.tay.bam(o)
    nc.tay.nghi(0.5, 1.2)
    nc.tay.go_binh_luan(noi_dung)
    nc.tay.nghi(0.8, 2.0)
    nc.tay.phim("Enter")
    return "thanh_cong" if thay_chu(nc.page.locator('div[role="region"]').first, noi_dung, 12000) else "khong_hien"


def _bs_tra_loi(nc, sp: str) -> str:
    ds = _bs_ds_hoi_thoai(nc, int(nc.ts.get("so_hoi_thoai") or 10))
    nc.nhat_ky(f"Hộp thư Business Suite: {len(ds)} hội thoại khách đang chờ")
    lam = xem = 0
    for h in ds:
        if phai_dung(nc) or nc.con_lai("tra_loi_tin_nhan") <= 0:
            break
        try:
            if not _bs_mo(nc, h):
                continue
            tin = _bs_doc(nc)
            nc.nhat_ky(f"Đọc khung tin: {len(tin)} dòng ({sum(1 for t in tin if t['tu'] == 'khach')} của khách), "
                       f"vùng tin: {_bs_vung(nc)}")
            if not tin or tin[-1]["tu"] != "khach":
                continue
            xem += 1
            link = nc.page.url
            ht = nc.hoi_thoai(khach_ten=h["ten"], khach_link=link, tin=tin, san_pham_id=sp)
            if not ht.get("bot_duoc_tra_loi", True):
                nc.su_kien("tra_loi_tin_nhan", "bo_qua", f"Bạn đang tự trả lời {h['ten']}, bot nhường", link=link)
                continue
            kq = nc.ai("tra_loi_tin_nhan", {"hoi_thoai": {"khach_ten": h["ten"], "khach_link": link, "tin": tin},
                                            "san_pham_id": sp})
            noi_dung = str(kq.get("noi_dung") or "").strip()
            tay_ = bool(kq.get("can_tra_loi_tay"))
            if tay_ or kq.get("sdt"):
                nc.hoi_thoai(khach_ten=h["ten"], khach_link=link, tin=tin, san_pham_id=sp,
                             trang_thai="can_tra_loi_tay" if tay_ else "bot_dang_lo", sdt=str(kq.get("sdt") or ""))
            if not noi_dung:
                continue
            if nc.che_do != "dang_luon":
                nc.su_kien("tra_loi_tin_nhan", "thong_tin",
                           ("Chạy thử: " if nc.chay_thu else "Duyệt trước (chưa có hàng duyệt tin nhắn): ")
                           + f"sẽ trả lời {h['ten']}: {noi_dung[:100]}" + (" [cần trả lời tay]" if tay_ else ""), link=link)
                continue
            r = _bs_gui(nc, noi_dung, f"gửi tin cho {h['ten']}")
            if r == "thanh_cong":
                lam += 1
                nc.hoi_thoai(khach_ten=h["ten"], khach_link=link, san_pham_id=sp,
                             tin=tin + [{"tu": "bot", "noi_dung": noi_dung}],
                             **({"trang_thai": "can_tra_loi_tay"} if tay_ else {}))
                nc.su_kien("tra_loi_tin_nhan", "thanh_cong",
                           (f"Gửi câu giữ khách, cần bạn trả lời tay ({kq.get('ly_do') or 'câu khó'})" if tay_
                            else f"Trả lời {h['ten']}: {noi_dung[:100]}"), link=link)
            else:
                nc.su_kien("tra_loi_tin_nhan", "loi", "Không thấy ô nhập tin" if r == "khong_thay"
                           else "Đã gửi nhưng chưa thấy tin hiện", link=link)
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien("tra_loi_tin_nhan", "loi", str(e))
        nc.tay.nghi(20.0, 60.0)
    return (f"Trả lời {lam} hội thoại (Hộp thư Trang)." if nc.che_do == "dang_luon"
            else f"Đã xem {xem} hội thoại khách đang chờ trên Hộp thư Trang (không gửi).")


def fb_tra_loi_tin_nhan(nc) -> str:
    sp = str(nc.ts.get("san_pham") or "")
    mo_va_kiem(nc, FB + "/messages/t/")
    nc.tay.nghi(2.0, 4.0)
    if "business.facebook.com" in (nc.page.url or ""):
        return _bs_tra_loi(nc, sp)
    _kiem_pin(nc)
    ds = _ds_hoi_thoai(nc, int(nc.ts.get("so_hoi_thoai") or 10))
    nc.nhat_ky(f"Có {len(ds)} hội thoại chưa đọc cần xem")
    lam = 0
    for h in ds:
        if phai_dung(nc) or nc.con_lai("tra_loi_tin_nhan") <= 0:
            break
        try:
            mo_va_kiem(nc, h["link"])
            _kiem_pin(nc)
            nc.tay.nghi(2.0, 5.0)
            try:
                dau = nc.page.locator("[role='main']").first.inner_text(timeout=3000)[:400]
            except Exception:
                dau = ""
            if _NHOM_CHAT.search(dau):
                nc.nhat_ky(f"Bỏ qua nhóm chat: {h['ten']}")
                continue
            tin = _doc_hoi_thoai(nc)
            if not tin:
                nc.su_kien("tra_loi_tin_nhan", "bo_qua", f"Không đọc được tin trong hội thoại {h['ten']}"
                           + (" (Messenger đang khoá tin mã hoá, cần nhập PIN một lần)" if _co_pin(nc) else ""),
                           link=h["link"])
                continue
            if tin[-1]["tu"] != "khach":
                nc.su_kien("tra_loi_tin_nhan", "bo_qua", f"Tin cuối của {h['ten']} là của nick, không cần trả lời",
                           link=h["link"])
                continue
            ht = nc.hoi_thoai(khach_ten=h["ten"], khach_link=h["link"], tin=tin, san_pham_id=sp)
            if not ht.get("bot_duoc_tra_loi", True):
                nc.su_kien("tra_loi_tin_nhan", "bo_qua", f"Bạn đang tự trả lời {h['ten']}, bot nhường", link=h["link"])
                continue
            kq = nc.ai("tra_loi_tin_nhan", {"hoi_thoai": {"khach_ten": h["ten"], "khach_link": h["link"], "tin": tin},
                                            "san_pham_id": sp})
            noi_dung = str(kq.get("noi_dung") or "").strip()
            tay_ = bool(kq.get("can_tra_loi_tay"))
            if tay_ or kq.get("sdt"):
                nc.hoi_thoai(khach_ten=h["ten"], khach_link=h["link"], tin=tin, san_pham_id=sp,
                             trang_thai="can_tra_loi_tay" if tay_ else "bot_dang_lo", sdt=str(kq.get("sdt") or ""))
            if not noi_dung:
                continue
            if nc.che_do != "dang_luon":
                nc.su_kien("tra_loi_tin_nhan", "thong_tin",
                           ("Chạy thử: " if nc.chay_thu else "Duyệt trước (chưa có hàng duyệt tin nhắn): ")
                           + f"sẽ trả lời {h['ten']}: {noi_dung[:100]}" + (" [cần trả lời tay]" if tay_ else ""),
                           link=h["link"])
                continue
            r = _gui_tin(nc, noi_dung, f"gửi tin cho {h['ten']}", "tra_loi_tin_nhan")
            if r == "thanh_cong":
                lam += 1
                nc.hoi_thoai(khach_ten=h["ten"], khach_link=h["link"], san_pham_id=sp,
                             tin=tin + [{"tu": "bot", "noi_dung": noi_dung}],
                             **({"trang_thai": "can_tra_loi_tay"} if tay_ else {}))
                nc.su_kien("tra_loi_tin_nhan", "thanh_cong",
                           (f"Gửi câu giữ khách, cần bạn trả lời tay ({kq.get('ly_do') or 'câu khó'})" if tay_
                            else f"Trả lời {h['ten']}: {noi_dung[:100]}"), link=h["link"])
            else:
                nc.su_kien("tra_loi_tin_nhan", "loi", "Không thấy ô nhập tin" if r == "khong_thay"
                           else "Đã gửi nhưng chưa thấy tin hiện", link=h["link"])
        except LoiKyNang as e:
            if e.ma:
                raise
            nc.su_kien("tra_loi_tin_nhan", "loi", str(e), link=h["link"])
        nc.tay.nghi(20.0, 60.0)          # nhịp giữa hai khách như người trực page
    return f"Trả lời {lam} hội thoại." if nc.che_do == "dang_luon" else f"Đã xem {len(ds)} hội thoại (không gửi)."


# ---------------------------------------------------------------------------- nhắn tin danh sách
def link_tin_nhan(nguoi: str) -> str:
    """UID / username / link trang cá nhân / m.me → link khung chat facebook.com/messages/t/<id>."""
    s = (nguoi or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"[\w.]+", s):
        return f"{FB}/messages/t/{s}"
    p = urllib.parse.urlsplit(s if "://" in s else "https://" + s)
    q = dict(urllib.parse.parse_qsl(p.query))
    if "/messages/" in p.path:
        return urllib.parse.urlunsplit(("https", "www.facebook.com", p.path, "", ""))
    if p.path.startswith("/profile.php") and q.get("id"):
        return f"{FB}/messages/t/{q['id']}"
    phan = [x for x in p.path.split("/") if x]
    if p.netloc.endswith("m.me") and phan:
        return f"{FB}/messages/t/{phan[0]}"
    if phan and phan[0] not in ("groups", "pages", "people", "watch", "events", "stories"):
        return f"{FB}/messages/t/{phan[0]}"
    if len(phan) >= 3 and phan[0] == "people":
        return f"{FB}/messages/t/{phan[2]}"
    return ""


def _khoa_nguoi(nguoi: str) -> str:
    l = link_tin_nhan(nguoi)
    return "fb_nt:" + (l.rsplit("/", 1)[-1] if l else nguoi.strip().lower())


def fb_nhan_tin_ds(nc) -> str:
    ds = [d.strip() for d in str(nc.ts.get("nguoi_nhan") or "").splitlines() if d.strip()]
    mau = str(nc.ts.get("noi_dung") or "")
    moi_nick = int(nc.ts.get("moi_nick") or 10)
    if not chon_cau(mau):
        raise LoiKyNang("chưa có nội dung tin nhắn")
    # Mỗi nick đi danh sách theo một thứ tự riêng (theo id nick) để các nick chạy song song ít đụng nhau.
    import random as _r
    _r.Random(str(nc.viec.get("nick_id"))).shuffle(ds)
    gui, thu, da_dung = 0, 0, []
    for nguoi in ds:
        if gui >= moi_nick or phai_dung(nc) or nc.con_lai("nhan_tin") <= 0:
            break
        khoa = _khoa_nguoi(nguoi)
        if nc.da_lam(khoa, ca_doi=True):
            continue
        so_loi = sum(1 for k in range(1, 4) if nc.da_lam(f"{khoa}:loi{k}", ca_doi=True))
        if so_loi >= 3:
            continue
        link = link_tin_nhan(nguoi)
        if not link:
            nc.su_kien("nhan_tin", "bo_qua", f"Không hiểu người nhận '{nguoi[:60]}'")
            continue
        cau = chon_cau(mau, nc.rng, da_dung)
        da_dung.append(cau)
        try:
            mo_va_kiem(nc, link)
            _kiem_pin(nc)
            r = _gui_tin(nc, cau, f"nhắn '{cau[:60]}' cho {nguoi[:60]}", "nhan_tin")
        except LoiKyNang as e:
            if e.ma:
                raise
            r = "loi:" + str(e)
        if r == "chay_thu":
            thu += 1
            continue
        if r == "thanh_cong":
            nc.ghi_da_lam(khoa)
            nc.su_kien("nhan_tin", "thanh_cong", f"Nhắn {nguoi[:60]}: {cau[:80]}", link=link)
            gui += 1
        else:
            nc.ghi_da_lam(f"{khoa}:loi{so_loi + 1}")
            nc.su_kien("nhan_tin", "loi", f"Nhắn {nguoi[:60]} lỗi lần {so_loi + 1}/3: "
                       + ("không thấy ô nhập tin" if r == "khong_thay" else "chưa thấy tin hiện" if r == "khong_hien" else r[4:]),
                       link=link)
        nc.nghi_thao_tac()
    if thu and not gui:
        return f"Chạy thử: đã mở hộp tin và soạn sẵn cho {thu} người, không bấm Gửi."
    return f"Đã nhắn {gui} người."


def fb_gui_tin(nc) -> str:
    """Việc nội bộ: gửi một tin Messenger chủ tự gõ trên trang Tin nhắn."""
    link = str(nc.ts.get("khach_link") or "")
    noi_dung = str(nc.ts.get("noi_dung") or "").strip()
    if not link or not noi_dung:
        raise LoiKyNang("thiếu link khách hoặc nội dung tin")
    dich = link if "/messages/" in link else (link_tin_nhan(link) or link)
    mo_va_kiem(nc, dich)
    _kiem_pin(nc)
    r = _gui_tin(nc, noi_dung, "gửi tin bạn vừa gõ", "tra_loi_tin_nhan")
    if r == "chay_thu":
        return "Chạy thử: không gửi tin."
    if r != "thanh_cong":
        nc.su_kien("tra_loi_tin_nhan", "loi", "Không thấy ô nhập tin" if r == "khong_thay" else "Đã gửi nhưng chưa thấy tin hiện",
                   link=link)
        raise LoiKyNang("không gửi được tin cho khách")
    nc.su_kien("tra_loi_tin_nhan", "thanh_cong", f"Gửi tin của bạn: {noi_dung[:100]}", link=link)
    return "Đã gửi tin cho khách."


__all__ = ["fb_tra_loi_binh_luan", "fb_tra_loi_tin_nhan", "fb_nhan_tin_ds", "fb_gui_tin", "link_tin_nhan",
           "chuan_link"]
