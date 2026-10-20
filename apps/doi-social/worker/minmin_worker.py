"""MinMin Worker - chạy trên máy Windows có GPM Login, nhận việc từ MinMin và làm bằng trình duyệt.

Cách dùng (xem HUONG-DAN.txt):
    python minmin_worker.py ghep https://minmin.cua-ban.com 123456   # lần đầu, mã lấy ở trang Đội Social
    python minmin_worker.py chay                                     # chạy mãi, nhận và làm việc
    python minmin_worker.py thu "Tên profile"                        # chỉ mở profile rồi đóng, để kiểm tra

Worker tự kết nối RA ngoài tới MinMin (long-poll), nên không phải mở cổng router hay bật
"Cho phép remote từ internet" trong GPM. Token máy lưu trong worker.json cạnh file này.
"""
from __future__ import annotations

import base64
import json
import platform
import socket
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PHIEN_BAN = "26.10.186"
THU_MUC = Path(__file__).resolve().parent
CAU_HINH = THU_MUC / "worker.json"
NHAT_KY = THU_MUC / "worker.log"
NHIP_GIAY = 30

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(*a) -> None:
    dong = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(dong, flush=True)
    try:
        with open(NHAT_KY, "a", encoding="utf-8") as f:
            f.write(dong + "\n")
    except Exception:
        pass


def doc_cau_hinh() -> dict:
    if CAU_HINH.is_file():
        return json.loads(CAU_HINH.read_text(encoding="utf-8"))
    return {}


def ghi_cau_hinh(d: dict) -> None:
    CAU_HINH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


class MayChu:
    def __init__(self, goc: str, token: str = ""):
        self.goc = goc.rstrip("/")
        self.token = token

    def _req(self, method: str, duong: str, body=None, timeout: float = 60, tho: bool = False):
        data = None if body is None else json.dumps(body).encode("utf-8")
        rq = urllib.request.Request(self.goc + duong, data=data, method=method)
        rq.add_header("content-type", "application/json")
        rq.add_header("user-agent", f"MinMinWorker/{PHIEN_BAN}")
        if self.token:
            rq.add_header("x-minmin-may", self.token)
        try:
            with urllib.request.urlopen(rq, timeout=timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error")
            except Exception:
                msg = str(e)
            raise RuntimeError(f"MinMin trả {e.code}: {msg}") from None
        return raw if tho else json.loads(raw.decode("utf-8") or "{}")

    def ghep(self, ma: str, ten: str) -> dict:
        return self._req("POST", "/doi-social/may/ghep",
                         {"ma": ma, "ten": ten, "driver": "gpm", "phien_ban": PHIEN_BAN})

    def nhip(self, **kw) -> dict:
        return self._req("POST", "/doi-social/may/nhip", {"phien_ban": PHIEN_BAN, **kw})

    def lay_viec(self, cho: int = 25):
        return self._req("GET", f"/doi-social/may/viec?cho={cho}", timeout=cho + 20).get("viec")

    def tai_tep(self, vid: int, luu: str, dich: Path) -> None:
        dich.write_bytes(self._req("GET", f"/doi-social/may/tep/{vid}/{urllib.parse.quote(luu)}",
                                   timeout=600, tho=True))

    def ket_qua(self, vid: int, ok: bool, thong_diep: str, buoc: list, anh: bytes = b"") -> None:
        self._req("POST", f"/doi-social/may/ket-qua/{vid}",
                  {"ok": ok, "thong_diep": thong_diep, "buoc": buoc,
                   "anh": base64.b64encode(anh).decode("ascii") if anh else ""}, timeout=120)


def lam_viec(may_chu: MayChu, gpm, viec: dict) -> None:
    from playwright.sync_api import sync_playwright
    import ky_nang_fb

    vid = viec["id"]
    buoc: list = []

    def nhat_ky(s: str) -> None:
        buoc.append(time.strftime("%H:%M:%S ") + s)
        log(f"[#{vid}] {s}")

    log(f"Nhận việc #{vid}: {viec.get('nhan_ky_nang')} · nick {viec.get('nick_ten')}")
    anh = b""
    with tempfile.TemporaryDirectory(prefix="minmin-") as td:
        tep_cuc_bo = []
        try:
            for t in (viec.get("tham_so") or {}).get("tep") or []:
                d = Path(td) / t["luu"]
                may_chu.tai_tep(vid, t["luu"], d)
                tep_cuc_bo.append(str(d))
            if tep_cuc_bo:
                nhat_ky(f"Đã tải {len(tep_cuc_bo)} tệp từ MinMin")
            nhat_ky("Mở profile trong GPM Login")
            gpm.nhat_ky = nhat_ky
            cdp = gpm.mo(viec["nick_id"])
            nhat_ky(f"Đã kết nối được trình duyệt ({cdp.split('/')[-1] if cdp.startswith('ws') else cdp})")
        except Exception as e:
            may_chu.ket_qua(vid, False, f"không chuẩn bị được: {e}", buoc)
            return
        try:
            with sync_playwright() as pw:
                trinh = pw.chromium.connect_over_cdp(cdp, timeout=60000)
                ctx = trinh.contexts[0] if trinh.contexts else trinh.new_context()
                page = ctx.new_page()
                try:
                    if viec.get("ky_nang") != "fb_dang_bai":
                        raise RuntimeError(f"Worker này chưa biết kỹ năng {viec.get('ky_nang')} - cập nhật Worker")
                    msg = ky_nang_fb.dang_bai(page, viec, tep_cuc_bo, nhat_ky)
                    ok = True
                except Exception as e:
                    ok, msg = False, str(e)
                    if not isinstance(e, ky_nang_fb.LoiKyNang):
                        log(traceback.format_exc())
                try:
                    anh = page.screenshot(full_page=False, timeout=20000)
                except Exception:
                    anh = b""
                try:
                    page.close()
                except Exception:
                    pass
        except Exception as e:
            ok, msg = False, f"không điều khiển được trình duyệt: {e}"
            log(traceback.format_exc())
        finally:
            time.sleep(2)
            gpm.dong(viec["nick_id"])
    try:
        may_chu.ket_qua(vid, ok, msg, buoc, anh)
        log(f"[#{vid}] {'XONG' if ok else 'LỖI'}: {msg}")
    except Exception as e:
        log(f"[#{vid}] gửi kết quả lỗi: {e}")


def _dau_van_ma() -> tuple:
    out = []
    for p in sorted(THU_MUC.glob("*.py")):
        try:
            out.append((p.name, p.stat().st_mtime))
        except OSError:
            pass
    return tuple(out)


def chay() -> int:
    from may_gpm import GPM, LoiGPM
    ch = doc_cau_hinh()
    if not ch.get("token"):
        log("Chưa ghép máy. Chạy: python minmin_worker.py ghep <địa chỉ MinMin> <mã 6 số>")
        return 2
    may_chu = MayChu(ch["may_chu"], ch["token"])
    gpm = GPM(ch.get("gpm") or "http://127.0.0.1:9495")
    log(f"MinMin Worker {PHIEN_BAN} - máy '{ch.get('ten')}' - MinMin {may_chu.goc}")
    nhip_cuoi = 0.0
    loi_lien = 0
    ban_dau = _dau_van_ma()
    while True:
        if _dau_van_ma() != ban_dau:
            # Có bản Worker mới chép đè (cập nhật từ MinMin hoặc tay): thoát để chay.bat mở lại bằng
            # code mới. Chỉ kiểm giữa hai việc, không bao giờ cắt ngang một lượt đăng.
            log("Phát hiện bản Worker mới, khởi động lại...")
            return 3
        try:
            if time.time() - nhip_cuoi > NHIP_GIAY:
                try:
                    ds = gpm.ds_profile()
                    may_chu.nhip(nick=ds, driver_ok=True, loi_driver="")
                except LoiGPM as e:
                    may_chu.nhip(driver_ok=False, loi_driver=str(e))
                    log(f"GPM chưa sẵn sàng: {e}")
                nhip_cuoi = time.time()
            viec = may_chu.lay_viec(25)
            loi_lien = 0
            if viec:
                lam_viec(may_chu, gpm, viec)
                nhip_cuoi = 0
        except KeyboardInterrupt:
            log("Dừng Worker.")
            return 0
        except Exception as e:
            loi_lien += 1
            cho = min(60, 5 * loi_lien)
            log(f"Mất kết nối MinMin ({e}). Thử lại sau {cho}s.")
            if "401" in str(e):
                log("Token máy không còn hợp lệ (máy đã bị gỡ?). Ghép lại bằng mã mới.")
            time.sleep(cho)


def ghep(goc: str, ma: str, ten: str = "") -> int:
    ten = ten or f"{socket.gethostname()} ({platform.system()})"
    kq = MayChu(goc).ghep(ma, ten)
    ch = doc_cau_hinh()
    ch.update({"may_chu": goc.rstrip("/"), "token": kq["token"], "may_id": kq["may_id"], "ten": kq["ten"]})
    ch.setdefault("gpm", "http://127.0.0.1:9495")
    ghi_cau_hinh(ch)
    log(f"Đã ghép máy '{kq['ten']}' với MinMin. Giờ chạy: python minmin_worker.py chay")
    return 0


def thu(goi: str) -> int:
    """Mở một profile (theo id hoặc tên), vào Facebook, chụp màn hình, đóng. Ghi mọi bước vào worker.log."""
    from may_gpm import GPM
    from playwright.sync_api import sync_playwright
    ch = doc_cau_hinh()
    gpm = GPM(ch.get("gpm") or "http://127.0.0.1:9495", nhat_ky=lambda s: log("[thu] " + s))
    ds = [p for p in gpm.ds_profile() if p["id"] == goi.strip() or p["ten"].strip().lower() == goi.strip().lower()]
    if not ds:
        log(f"[thu] Không thấy profile '{goi}' trong GPM")
        return 1
    log(f"[thu] Thử profile '{ds[0]['ten']}'")
    try:
        cdp = gpm.mo(ds[0]["id"])
        log(f"[thu] Địa chỉ điều khiển: {cdp}")
        with sync_playwright() as pw:
            trinh = pw.chromium.connect_over_cdp(cdp, timeout=60000)
            ctx = trinh.contexts[0] if trinh.contexts else trinh.new_context()
            page = ctx.new_page()
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            log(f"[thu] Trang hiện tại: {page.url} - tiêu đề: {page.title()}")
            page.screenshot(path=str(THU_MUC / "thu-ket-noi.png"))
            log("[thu] Đã chụp thu-ket-noi.png")
            page.close()
    except Exception as e:
        log(f"[thu] LỖI: {type(e).__name__}: {e}")
        log(traceback.format_exc())
        return 1
    finally:
        time.sleep(2)
        gpm.dong(ds[0]["id"])
    log("[thu] XONG: Worker điều khiển được GPM trên máy này.")
    return 0


def main(argv) -> int:
    if len(argv) >= 3 and argv[0] == "ghep":
        return ghep(argv[1], argv[2], " ".join(argv[3:]))
    if argv and argv[0] == "chay":
        return chay()
    if len(argv) >= 2 and argv[0] == "thu":
        return thu(" ".join(argv[1:]))
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
