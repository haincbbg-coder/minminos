"""MinMin Worker - chạy trên máy Windows có GPM Login, nhận việc từ MinMin và làm bằng trình duyệt.

Cách dùng (xem HUONG-DAN.txt):
    python minmin_worker.py ghep https://minmin.cua-ban.com 123456   # lần đầu, mã lấy ở trang Đội Social
    python minmin_worker.py chay                                     # chạy mãi, nhận và làm việc
    python minmin_worker.py thu "Tên profile"                        # chỉ mở profile rồi đóng, để kiểm tra
    python minmin_worker.py thu-mau <id mẫu> "Tên profile" [tham số JSON]
                                     # chạy THỬ một mẫu trên profile thật, không cần MinMin, không đăng gì

Worker tự kết nối RA ngoài tới MinMin (long-poll), nên không phải mở cổng router hay bật
"Cho phép remote từ internet" trong GPM. Token máy lưu trong worker.json cạnh file này.

Kỹ năng: mọi tệp `ky_nang_*.py` cạnh tệp này được nạp động, mỗi tệp khai `KICH_BAN = {id mẫu: ham}`
(hợp đồng ở docs/doi-social/KIEN-TRUC.md mục 4). Tệp hỏng bị bỏ qua và ghi vào worker.log.
Chạy song song tối đa `song_song` việc (worker.json, mặc định 1, trần 3), một nick một việc.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import platform
import queue
import re
import socket
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PHIEN_BAN = "26.10.263"
THU_MUC = Path(__file__).resolve().parent
CAU_HINH = THU_MUC / "worker.json"
NHAT_KY = THU_MUC / "worker.log"
NHIP_GIAY = 30
SONG_SONG_TRAN = 3
NGHI_TRUOC_DONG = 2.0

if str(THU_MUC) not in sys.path:
    sys.path.insert(0, str(THU_MUC))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_KHOA_LOG = threading.Lock()


def log(*a) -> None:
    dong = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    with _KHOA_LOG:
        try:
            print(dong, flush=True)
        except Exception:
            pass
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


class LoiHTTP(RuntimeError):
    """MinMin trả mã lỗi HTTP. `code` để NguCanh biết lỗi 4xx (không thử lại) hay 5xx (thử lại)."""

    def __init__(self, code: int, thong_diep: str):
        super().__init__(f"MinMin trả {code}: {thong_diep}")
        self.code = code


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
            raise LoiHTTP(e.code, msg) from None
        return raw if tho else json.loads(raw.decode("utf-8") or "{}")

    def goi(self, method: str, duong: str, body=None, timeout: float = 60):
        """Gọi chung một đường /doi-social/may/* (dùng bởi NguCanh). Trả JSON đã giải mã."""
        return self._req(method, duong, body, timeout=timeout)

    def tai_ve(self, duong: str, dich: Path) -> None:
        Path(dich).write_bytes(self._req("GET", duong, timeout=600, tho=True))

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

    def ket_qua(self, vid: int, ok: bool, thong_diep: str, buoc: list, anh: bytes = b"", dem: dict = None) -> None:
        body = {"ok": ok, "thong_diep": thong_diep, "buoc": buoc,
                "anh": base64.b64encode(anh).decode("ascii") if anh else ""}
        if dem is not None:
            body["dem"] = dem
        self._req("POST", f"/doi-social/may/ket-qua/{vid}", body, timeout=120)

    def ban_cap_nhat(self) -> bytes:
        return self._req("GET", "/doi-social/may/ban-cap-nhat", timeout=300, tho=True)


class DayBuoc:
    """Đẩy từng dòng nhật ký lên /may/buoc/{vid} ở luồng nền: không chặn việc, lỗi thì bỏ."""

    def __init__(self, may_chu):
        self.may_chu = may_chu
        self.q: "queue.Queue" = queue.Queue(maxsize=500)
        threading.Thread(target=self._chay, daemon=True, name="day-buoc").start()

    def __call__(self, vid, dong: str) -> None:
        try:
            self.q.put_nowait((vid, dong))
        except queue.Full:
            pass

    def _chay(self) -> None:
        while True:
            vid, dong = self.q.get()
            try:
                self.may_chu.goi("POST", f"/doi-social/may/buoc/{vid}", {"dong": dong}, timeout=10)
            except Exception:
                pass


# ---------------------------------------------------------------------------- nạp kỹ năng
def nap_ky_nang(thu_muc: Path = THU_MUC):
    """Nạp mọi `ky_nang_*.py` trong thư mục. Trả (KICH_BAN gộp, [(tên tệp, lỗi)])."""
    thu_muc = Path(thu_muc)
    if str(thu_muc) not in sys.path:
        sys.path.insert(0, str(thu_muc))
    kb: dict = {}
    loi: list = []
    for p in sorted(thu_muc.glob("ky_nang_*.py")):
        ten = p.stem
        try:
            spec = importlib.util.spec_from_file_location(ten, str(p))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[ten] = mod
            spec.loader.exec_module(mod)
        except BaseException as e:      # noqa: BLE001 - kể cả SystemExit trong tệp hỏng
            sys.modules.pop(ten, None)
            loi.append((p.name, f"{type(e).__name__}: {e}"))
            log(f"Bỏ qua {p.name}: không nạp được ({type(e).__name__}: {e})")
            continue
        k = getattr(mod, "KICH_BAN", None)
        if not isinstance(k, dict):
            if ten != "ky_nang_fb":
                loi.append((p.name, "không có KICH_BAN"))
            continue
        for id_mau, ham in k.items():
            if callable(ham):
                if id_mau in kb:
                    log(f"Mẫu {id_mau} khai ở nhiều tệp, dùng bản trong {p.name}")
                kb[str(id_mau)] = ham
    return kb, loi


def ds_kich_ban_gui(kb: dict) -> list:
    """Danh sách id gửi trong nhịp: bỏ khoá nội bộ có ':' nhưng báo `dang_ban_nhap` nếu có ít nhất
    một nền tảng làm được."""
    ra = {k for k in kb if ":" not in k}
    if any(k.startswith("dang_ban_nhap:") for k in kb):
        ra.add("dang_ban_nhap")
    return sorted(ra)


def chon_ham(kb: dict, viec: dict):
    """(hàm, '') hoặc (None, lý do). `fb_dang_bai` là việc cũ, lõi xử lý riêng."""
    from ngu_canh import NOI_DANG_NEN_TANG
    kn = str(viec.get("ky_nang") or "")
    if kn == "fb_dang_bai":
        return "fb_dang_bai", ""
    if kn == "dang_ban_nhap":
        tsv = viec.get("tham_so") or {}
        ts = tsv.get("tham_so") if isinstance(tsv.get("tham_so"), dict) else tsv
        nd = str(ts.get("noi_dang") or tsv.get("noi_dang") or "")
        nt = NOI_DANG_NEN_TANG.get(nd, nd)
        ham = kb.get(f"dang_ban_nhap:{nt}")
        return (ham, "") if ham else (None, f"Worker này chưa biết đăng nháp lên '{nd or '?'}' - cập nhật Worker")
    ham = kb.get(kn)
    return (ham, "") if ham else (None, f"Worker này chưa biết kỹ năng {kn} - cập nhật Worker")


# ---------------------------------------------------------------------------- điều phối song song
class DieuPhoi:
    """Sổ việc của máy: tối đa `song_song` việc (đang chạy + chờ nick rảnh), một nick một việc."""

    def __init__(self, song_song: int = 1):
        self.song_song = max(1, min(SONG_SONG_TRAN, int(song_song or 1)))
        self.dang: dict = {}        # vid -> nick_id
        self.cho: list = []         # việc đã nhận nhưng nick đang bận

    def con_cho(self) -> bool:
        return len(self.dang) + len(self.cho) < self.song_song

    def ranh(self) -> bool:
        return not self.dang and not self.cho

    def nick_ban(self, nick_id) -> bool:
        return str(nick_id) in {str(n) for n in self.dang.values()}

    def nhan(self, viec: dict) -> None:
        self.cho.append(viec)

    def lay_de_chay(self) -> list:
        ra, con = [], []
        for v in self.cho:
            if len(self.dang) < self.song_song and not self.nick_ban(v.get("nick_id")):
                self.dang[v["id"]] = v.get("nick_id")
                ra.append(v)
            else:
                con.append(v)
        self.cho = con
        return ra

    def xong(self, vid) -> None:
        self.dang.pop(vid, None)

    def ds_dang(self) -> list:
        return list(self.dang.keys())


# ---------------------------------------------------------------------------- làm một việc
def _tai_tep_viec(may_chu, viec: dict, td: Path) -> list:
    tsv = viec.get("tham_so") or {}
    ds = list(tsv.get("tep") or [])
    # Tệp của việc dang_ban_nhap thuộc về nháp: NguCanh.chuan_bi_ban_nhap() tải qua /may/ban-nhap/tep/.
    if isinstance(tsv.get("tham_so"), dict) and viec.get("ky_nang") != "dang_ban_nhap":
        ds += list(tsv["tham_so"].get("tep") or [])
    out, thay = [], set()
    for t in ds:
        luu = str((t or {}).get("luu") or "")
        if not luu or luu in thay or "/" in luu or "\\" in luu or luu.startswith("."):
            continue
        thay.add(luu)
        d = td / luu
        may_chu.tai_tep(viec["id"], luu, d)
        out.append(str(d))
    return out


def tom_tat_dem(dem: dict) -> str:
    return f"thành công {dem.get('thanh_cong', 0)}, bỏ qua {dem.get('bo_qua', 0)}, lỗi {dem.get('loi', 0)}"


def lam_viec(may_chu, tao_gpm, viec: dict, kb: dict = None, day_buoc=None, toc_do: float = 1.0,
             connect=None) -> dict:
    """Làm một việc từ đầu tới cuối và gửi kết quả. `tao_gpm(nhat_ky)` trả đối tượng có mo()/dong().
    `connect(pw, cdp)` (test) thay cho pw.chromium.connect_over_cdp."""
    from playwright.sync_api import sync_playwright
    from ngu_canh import LoiKyNang, NguCanh

    if kb is None:
        kb, _ = nap_ky_nang()
    vid = viec["id"]
    buoc: list = []

    def nhat_ky(s: str) -> None:
        buoc.append(time.strftime("%H:%M:%S ") + s)
        log(f"[#{vid}] {s}")
        if day_buoc:
            day_buoc(vid, s)

    log(f"Nhận việc #{vid}: {viec.get('nhan_ky_nang') or viec.get('ky_nang')} · nick {viec.get('nick_ten')}")
    ham, ly_do = chon_ham(kb, viec)
    dem0 = {"thanh_cong": 0, "bo_qua": 0, "loi": 0}

    def gui(ok, msg, anh=b"", dem=None):
        for lan in range(4):
            try:
                may_chu.ket_qua(vid, ok, msg, buoc, anh, dem)
                log(f"[#{vid}] {'XONG' if ok else 'LỖI'}: {msg}")
                return
            except Exception as e:      # noqa: BLE001
                if getattr(e, "code", 500) < 500 or lan == 3:
                    log(f"[#{vid}] gửi kết quả lỗi: {e}")
                    return
                time.sleep(3 * (lan + 1))

    if ham is None:
        gui(False, ly_do, dem=dem0)
        return {"ok": False, "thong_diep": ly_do, "dem": dem0}
    co_cu = ham == "fb_dang_bai"
    nc = None
    ok, msg, anh = False, "", b""
    with tempfile.TemporaryDirectory(prefix="minmin-") as td:
        try:
            tep_cuc_bo = _tai_tep_viec(may_chu, viec, Path(td))
            if tep_cuc_bo:
                nhat_ky(f"Đã tải {len(tep_cuc_bo)} tệp từ MinMin")
            nhat_ky("Mở profile trong GPM Login")
            gpm = tao_gpm(nhat_ky)
            cdp = gpm.mo(viec["nick_id"])
            nhat_ky(f"Đã kết nối được trình duyệt ({cdp.split('/')[-1] if cdp.startswith('ws') else cdp})")
        except Exception as e:
            gui(False, f"không chuẩn bị được: {e}", dem=dem0)
            return {"ok": False, "thong_diep": str(e), "dem": dem0}
        try:
            with sync_playwright() as pw:
                try:
                    trinh = connect(pw, cdp) if connect else pw.chromium.connect_over_cdp(cdp, timeout=60000)
                except Exception as e1:
                    # 26.10.229: trình duyệt còn sót từ lượt trước (đang tắt dần) trả lời /json rồi chết ngay
                    # -> ECONNREFUSED. Đóng hẳn profile, mở lại một lần.
                    nhat_ky(f"Kết nối trình duyệt lỗi ({str(e1)[:80]}): đóng profile rồi mở lại")
                    try:
                        gpm.dong(viec["nick_id"])
                    except Exception:
                        pass
                    time.sleep(5)
                    cdp = gpm.mo(viec["nick_id"])
                    nhat_ky(f"Mở lại xong ({cdp})")
                    trinh = connect(pw, cdp) if connect else pw.chromium.connect_over_cdp(cdp, timeout=60000)
                ctx = trinh.contexts[0] if trinh.contexts else trinh.new_context()
                page = ctx.new_page()
                nc = NguCanh(may_chu, viec, page, ctx, nhat_ky, thu_muc_tam=td, toc_do=toc_do)
                nc.tep_cuc_bo = list(tep_cuc_bo)
                if nc.chay_thu:
                    nhat_ky("CHẠY THỬ: không bấm bất kỳ nút công khai nào")
                try:
                    if co_cu:
                        import ky_nang_fb
                        msg = ky_nang_fb.dang_bai(page, viec, tep_cuc_bo, nhat_ky)
                        ok = True
                    else:
                        if viec.get("ky_nang") == "dang_ban_nhap":
                            nc.chuan_bi_ban_nhap()
                        msg = str(ham(nc) or "").strip()
                        ok = not (nc.dem["thanh_cong"] == 0 and nc.dem["loi"] > 0)
                        if not msg:
                            msg = "Xong: " + tom_tat_dem(nc.dem)
                        elif not ok:
                            msg = f"{msg} (không thao tác nào thành công: {tom_tat_dem(nc.dem)})"
                except Exception as e:      # noqa: BLE001
                    ok, msg = False, str(e) or type(e).__name__
                    if isinstance(e, LoiKyNang):
                        if e.ma and not co_cu:
                            try:
                                nc.su_kien(nc.hanh_dong_cuoi or "khac", "loi", msg, ma=e.ma)
                            except Exception as e2:      # noqa: BLE001
                                log(f"[#{vid}] không báo được sự kiện lỗi: {e2}")
                    else:
                        log(traceback.format_exc())
                    if nc.dem["thanh_cong"]:
                        msg += f" (trước đó đã làm được {nc.dem['thanh_cong']} thao tác)"
                anh = nc.chup()
                try:
                    page.close()
                except Exception:
                    pass
        except Exception as e:      # noqa: BLE001
            ok, msg = False, f"không điều khiển được trình duyệt: {e}"
            log(traceback.format_exc())
        finally:
            time.sleep(NGHI_TRUOC_DONG)
            try:
                gpm.dong(viec["nick_id"])
            except Exception as e:      # noqa: BLE001
                log(f"[#{vid}] đóng profile lỗi: {e}")
    dem = dict(nc.dem) if nc else dem0
    gui(ok, msg, anh, dem)
    return {"ok": ok, "thong_diep": msg, "dem": dem, "bi_chan": list(getattr(getattr(nc, "tay", None), "bi_chan", []) or [])}


def _chay_luong(may_chu, tao_gpm, viec, kb, day_buoc) -> None:
    try:
        lam_viec(may_chu, tao_gpm, viec, kb, day_buoc)
    except Exception as e:      # noqa: BLE001
        log(f"[#{viec.get('id')}] lỗi không lường trước: {e}\n{traceback.format_exc()}")
        try:
            may_chu.ket_qua(viec["id"], False, f"Worker lỗi: {e}", [], b"", {"thanh_cong": 0, "bo_qua": 0, "loi": 1})
        except Exception:
            pass


# ---------------------------------------------------------------------------- tự cập nhật
DUOI_CAP_NHAT = (".py", ".txt", ".bat")
KHONG_DE = ("worker.json", "worker.log")


def so_phien_ban(s: str) -> tuple:
    """'26.10.187' -> (26, 10, 187). Phần không phải số lấy chữ số đầu (vd '187b' -> 187), không có -> 0."""
    ra = []
    for x in str(s or "").strip().split("."):
        m = re.match(r"\d+", x.strip())
        ra.append(int(m.group(0)) if m else 0)
    return tuple(ra)


def ap_dung_cap_nhat(du_lieu: bytes, thu_muc: Path = THU_MUC) -> list:
    """Giải nén gói Worker đè các tệp .py/.txt/.bat. Kiểm TOÀN BỘ gói trước khi ghi tệp nào: có đường
    dẫn thoát thư mục (../, đường tuyệt đối, ổ đĩa) thì từ chối cả gói. Không đụng worker.json,
    worker.log. Tệp giống hệt bản đang có thì không ghi (tránh đụng chay.bat đang chạy)."""
    import io
    import zipfile
    goc = Path(thu_muc).resolve()
    with zipfile.ZipFile(io.BytesIO(du_lieu)) as z:
        muc = [i for i in z.infolist() if not i.is_dir()]
        phan = [i.filename.replace("\\", "/").split("/") for i in muc]
        chung = phan[0][0] if phan and all(len(p) > 1 and p[0] == phan[0][0] for p in phan) else None
        se_ghi = []
        for i, p in zip(muc, phan):
            ten = i.filename.replace("\\", "/")
            if ten.startswith("/") or re.match(r"^[A-Za-z]:", ten):
                raise ValueError(f"gói cập nhật có đường dẫn không an toàn: {i.filename}")
            if chung:
                p = p[1:]
            if not p or any(x in ("", ".", "..") or ":" in x for x in p):
                raise ValueError(f"gói cập nhật có đường dẫn không an toàn: {i.filename}")
            dich = (goc / Path(*p)).resolve()
            if goc != dich.parent and goc not in dich.parents:
                raise ValueError(f"gói cập nhật có đường dẫn không an toàn: {i.filename}")
            if p[-1].lower() in KHONG_DE or "__pycache__" in p or dich.suffix.lower() not in DUOI_CAP_NHAT:
                continue
            se_ghi.append((i, dich))
        if not any(d.name == "minmin_worker.py" and d.parent == goc for _, d in se_ghi):
            raise ValueError("gói cập nhật thiếu minmin_worker.py")
        da_ghi = []
        for i, dich in se_ghi:
            noi = z.read(i)
            try:
                if dich.is_file() and dich.read_bytes() == noi:
                    continue
            except OSError:
                pass
            dich.parent.mkdir(parents=True, exist_ok=True)
            tam = dich.with_name(dich.name + ".moi")
            tam.write_bytes(noi)
            os.replace(str(tam), str(dich))
            da_ghi.append(str(dich.relative_to(goc)))
    return da_ghi


def cap_nhat(may_chu, ban_moi: str) -> int:
    log(f"Cập nhật Worker {PHIEN_BAN} -> {ban_moi}")
    da_ghi = ap_dung_cap_nhat(may_chu.ban_cap_nhat(), THU_MUC)
    log(f"Đã cập nhật {len(da_ghi)} tệp: {', '.join(da_ghi[:12])}. Khởi động lại...")
    return 3


def _dau_van_ma() -> tuple:
    out = []
    for p in sorted(THU_MUC.glob("*.py")):
        try:
            out.append((p.name, p.stat().st_mtime))
        except OSError:
            pass
    return tuple(out)


# ---------------------------------------------------------------------------- vòng chính
def chay() -> int:
    from may_gpm import GPM, LoiGPM
    ch = doc_cau_hinh()
    if not ch.get("token"):
        log("Chưa ghép máy. Chạy: python minmin_worker.py ghep <địa chỉ MinMin> <mã 6 số>")
        return 2
    may_chu = MayChu(ch["may_chu"], ch["token"])
    goc_gpm = ch.get("gpm") or "http://127.0.0.1:9495"
    try:
        song_song = max(1, min(SONG_SONG_TRAN, int(ch.get("song_song") or 1)))
    except (TypeError, ValueError):
        song_song = 1
    kb, loi_nap = nap_ky_nang()
    ds_kb = ds_kich_ban_gui(kb)
    log(f"MinMin Worker {PHIEN_BAN} - máy '{ch.get('ten')}' - MinMin {may_chu.goc} - "
        f"{len(ds_kb)} mẫu, song song {song_song}")
    if loi_nap:
        log("Tệp kỹ năng lỗi: " + "; ".join(f"{t} ({l})" for t, l in loi_nap))

    def tao_gpm(nk):
        return GPM(goc_gpm, nhat_ky=nk)

    gpm_nhip = GPM(goc_gpm)
    dp = DieuPhoi(song_song)
    luong: dict = {}
    day_buoc = DayBuoc(may_chu)
    nhip_cuoi = 0.0
    loi_lien = 0
    ban_dau = _dau_van_ma()
    ban_moi = ""
    tranh_cap_nhat_toi = 0.0
    while True:
        try:
            for vid, t in list(luong.items()):
                if not t.is_alive():
                    luong.pop(vid, None)
                    dp.xong(vid)
                    nhip_cuoi = 0
            for v in dp.lay_de_chay():
                t = threading.Thread(target=_chay_luong, args=(may_chu, tao_gpm, v, kb, day_buoc),
                                     daemon=True, name=f"viec-{v['id']}")
                luong[v["id"]] = t
                t.start()
            if dp.ranh():
                # Chỉ đổi mã khi không có việc nào đang chạy: không bao giờ cắt ngang một lượt đăng.
                if _dau_van_ma() != ban_dau:
                    log("Phát hiện bản Worker mới, khởi động lại...")
                    return 3
                if ban_moi and time.time() >= tranh_cap_nhat_toi:
                    try:
                        return cap_nhat(may_chu, ban_moi)
                    except Exception as e:      # noqa: BLE001
                        log(f"Cập nhật Worker lỗi ({e}); làm việc tiếp, thử lại sau 10 phút")
                        ban_moi, tranh_cap_nhat_toi = "", time.time() + 600
            if time.time() - nhip_cuoi > NHIP_GIAY:
                chung = {"kich_ban": ds_kb, "song_song": song_song, "dang_chay": dp.ds_dang()}
                try:
                    ds = gpm_nhip.ds_profile()
                    kq = may_chu.nhip(nick=ds, driver_ok=True, loi_driver="", **chung)
                except LoiGPM as e:
                    kq = may_chu.nhip(driver_ok=False, loi_driver=str(e), **chung)
                    log(f"GPM chưa sẵn sàng: {e}")
                nhip_cuoi = time.time()
                pb = str((kq or {}).get("phien_ban_worker") or "")
                if (pb and so_phien_ban(pb) > so_phien_ban(PHIEN_BAN) and pb != ban_moi
                        and time.time() >= tranh_cap_nhat_toi):
                    ban_moi = pb
                    log(f"MinMin có Worker {pb}: ngừng nhận việc mới, cập nhật khi các việc đang chạy xong")
            if dp.con_cho() and not ban_moi:
                viec = may_chu.lay_viec(25 if dp.ranh() else 8)
                loi_lien = 0
                if viec:
                    if dp.nick_ban(viec.get("nick_id")):
                        log(f"Việc #{viec['id']} chờ: nick {viec.get('nick_ten')} đang chạy việc khác")
                    dp.nhan(viec)
            else:
                time.sleep(1.5)
        except KeyboardInterrupt:
            log("Dừng Worker.")
            return 0
        except Exception as e:      # noqa: BLE001
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


def _tim_profile(gpm, goi: str):
    import unicodedata

    def bo_dau(x: str) -> str:
        x = unicodedata.normalize("NFD", str(x or "").replace("đ", "d").replace("Đ", "D"))
        return "".join(c for c in x if unicodedata.category(c) != "Mn").lower().strip()
    tat_ca = gpm.ds_profile()
    ds = [p for p in tat_ca if p["id"] == goi.strip() or p["ten"].strip().lower() == goi.strip().lower()]
    if not ds:   # gõ không dấu / một phần tên, miễn khớp duy nhất
        ds = [p for p in tat_ca if bo_dau(goi) and bo_dau(goi) in bo_dau(p["ten"])]
        if len(ds) > 1:
            log("[thu] Nhiều profile khớp: " + "; ".join(p["ten"] for p in ds[:8]))
            return None
    return ds[0] if ds else None


def thu(goi: str) -> int:
    """Mở một profile (theo id hoặc tên), vào Facebook, chụp màn hình, đóng. Ghi mọi bước vào worker.log."""
    from may_gpm import GPM
    from playwright.sync_api import sync_playwright
    ch = doc_cau_hinh()
    gpm = GPM(ch.get("gpm") or "http://127.0.0.1:9495", nhat_ky=lambda s: log("[thu] " + s))
    pf = _tim_profile(gpm, goi)
    if not pf:
        log(f"[thu] Không thấy profile '{goi}' trong GPM")
        return 1
    log(f"[thu] Thử profile '{pf['ten']}'")
    try:
        cdp = gpm.mo(pf["id"])
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
        gpm.dong(pf["id"])
    log("[thu] XONG: Worker điều khiển được GPM trên máy này.")
    return 0


# ---------------------------------------------------------------------------- chạy thử một mẫu
AI_MAU = {
    "cham_bai": {"diem": 80, "chon": True, "ly_do": "(chạy thử) bài có người đang hỏi đúng nhu cầu", "la_doi_thu": False},
    "viet_binh_luan": {"noi_dung": "(chạy thử) Mình cũng từng tìm hiểu cái này, bạn tham khảo thêm nhé.",
                       "tra_loi_con": ""},
    "tra_loi_binh_luan": {"noi_dung": "(chạy thử) Cảm ơn bạn đã quan tâm, mình nhắn riêng bạn nhé.", "can_hoi_chu": False},
    "tra_loi_tin_nhan": {"noi_dung": "(chạy thử) Dạ shop chào bạn, bạn cần tư vấn mẫu nào ạ?", "can_tra_loi_tay": False},
    "viet_bai": {"noi_dung": "(chạy thử) Bài viết mẫu của MinMin."},
}


class MayChuGia:
    """MinMin giả cho lệnh thu-mau: in mọi lời gọi ra màn hình, AI trả câu mẫu cố định, kho trả một
    bài mẫu không tệp, nhóm lấy từ `links` của tham số. Không gọi mạng."""

    def __init__(self, ts: dict = None, in_ra=print):
        self.ts = ts or {}
        self.in_ra = in_ra
        self.goi_ds: list = []
        self._id = 0

    def goi(self, method: str, duong: str, body=None, timeout: float = 60):
        self.goi_ds.append((method, duong, body))
        d = duong.split("?")[0].replace("/doi-social/may/", "")
        if not d.startswith("buoc/"):
            self.in_ra(f"[MinMin giả] {method} {duong} {json.dumps(body, ensure_ascii=False)[:300] if body else ''}")
        links = [l for l in (self.ts.get("links") or []) if l]
        if d.startswith("su-kien/"):
            return {"con_lai": {}, "dung": False}
        if d.startswith("dung/"):
            return {"dung": False}
        if d == "ai":
            md = (body or {}).get("muc_dich")
            if md == "tra_loi_cau_hoi_nhom":
                n = len(((body or {}).get("du_lieu") or {}).get("cau_hoi") or [])
                return {"ok": True, "ket_qua": {"tra_loi": ["(chạy thử) Mình quan tâm chủ đề của nhóm."] * n, "bo_nhom": False}}
            if md == "chon_nhom":
                kq = ((body or {}).get("du_lieu") or {}).get("ket_qua_tim") or []
                return {"ok": True, "ket_qua": {"chon": [r.get("link") for r in kq[:2]]}}
            return {"ok": True, "ket_qua": dict(AI_MAU.get(md, {"noi_dung": "(chạy thử)"}))}
        if d == "ban-nhap":
            self._id += 1
            return {"id": self._id}
        if d == "ban-nhap/lay":
            return {"ban_nhap": {"id": 0, "noi_dung": "(chạy thử) Bài AI mẫu đã duyệt.", "nhom": links[0] if links else ""}}
        if d == "kho/lay":
            return {"bai": {"id": 0, "noi_dung": "(chạy thử) Bài mẫu từ kho của MinMin.", "tep": []}}
        if d == "nhom-fb" and method == "GET":
            return {"nhom": [{"link": l, "ten": l, "vai": "chinh", "tinh_trang_vao": "da_vao", "trang_thai": "da_duyet"}
                             for l in links], "tu_khoa": self.ts.get("tu_khoa", "")}
        if d == "da-tuong-tac" and method == "GET":
            return {"da_lam": False}
        if d == "hoi-thoai":
            return {"id": 0, "bot_duoc_tra_loi": True}
        if d == "bai-doi-da-dang":
            return {"bai": [{"link": l, "nhom": ""} for l in links]}
        return {"ok": True}

    def tai_ve(self, duong: str, dich: Path) -> None:
        Path(dich).write_bytes(b"")

    def tai_tep(self, vid, luu, dich: Path) -> None:
        Path(dich).write_bytes(b"")

    def ket_qua(self, vid, ok, thong_diep, buoc, anh=b"", dem=None) -> None:
        self.in_ra(f"[MinMin giả] KẾT QUẢ: {'OK' if ok else 'LỖI'} - {thong_diep} - {dem}")
        if anh:
            try:
                (THU_MUC / "thu-mau.png").write_bytes(anh)
                self.in_ra(f"[MinMin giả] Ảnh màn hình cuối: {THU_MUC / 'thu-mau.png'}")
            except Exception:
                pass


def thu_mau(mau_id: str, goi: str, ts_json: str = "") -> int:
    from may_gpm import GPM
    from ngu_canh import doan_nen_tang
    try:
        ts = json.loads(ts_json) if ts_json.strip() else {}
        if not isinstance(ts, dict):
            raise ValueError("tham số phải là một object JSON")
    except ValueError as e:
        log(f"[thu-mau] Tham số JSON sai: {e}")
        return 1
    ch = doc_cau_hinh()
    goc_gpm = ch.get("gpm") or "http://127.0.0.1:9495"
    pf = _tim_profile(GPM(goc_gpm), goi)
    if not pf:
        log(f"[thu-mau] Không thấy profile '{goi}' trong GPM")
        return 1
    kb, loi = nap_ky_nang()
    for t, l in loi:
        log(f"[thu-mau] tệp kỹ năng lỗi: {t}: {l}")
    han_muc = ts.pop("han_muc", {})
    nghi = ts.pop("nghi_giay", [2, 5])
    viec = {"id": 0, "ky_nang": mau_id, "nhan_ky_nang": f"{mau_id} (chạy thử)", "nick_id": pf["id"], "nick_ten": pf["ten"],
            "tham_so": {"kich_ban": mau_id, "tham_so": ts, "chay_thu": True, "han_muc": han_muc, "nghi_giay": nghi,
                        "nen_tang": doan_nen_tang(mau_id, ts)}}
    if mau_id == "fb_dang_bai":
        log("[thu-mau] fb_dang_bai là việc đăng thật, không có chế độ chạy thử - dùng 'thu' để kiểm kết nối")
        return 1
    log(f"[thu-mau] Chạy thử mẫu {mau_id} trên profile '{pf['ten']}' (không đăng gì)")
    kq = lam_viec(MayChuGia(ts, lambda s: log(s)), lambda nk: GPM(goc_gpm, nhat_ky=nk), viec, kb)
    if kq.get("bi_chan"):
        log(f"[thu-mau] Đã chặn {len(kq['bi_chan'])} cú bấm công khai: {', '.join(kq['bi_chan'][:10])}")
    return 0 if kq.get("ok") else 1


def main(argv) -> int:
    if len(argv) >= 3 and argv[0] == "ghep":
        return ghep(argv[1], argv[2], " ".join(argv[3:]))
    if argv and argv[0] == "chay":
        return chay()
    if len(argv) >= 3 and argv[0] == "thu-mau":
        return thu_mau(argv[1], argv[2], " ".join(argv[3:]))
    if len(argv) >= 2 and argv[0] == "thu":
        return thu(" ".join(argv[1:]))
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
