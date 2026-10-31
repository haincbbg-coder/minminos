"""Cầu nối Concat - chạy trên máy Windows có Concat, cho MinMin (VPS) điều khiển trình dựng video.

Cách dùng (xem HUONG-DAN.txt):
    python concat_cau.py ghep https://minmin.cua-ban.com 123456   # lần đầu, mã lấy ở trang Concat
    python concat_cau.py chay                                     # chạy mãi, nhận và làm việc
    python concat_cau.py thu                                      # chỉ mở Concat MCP, in phiên bản và số công cụ

Cầu nối tự kết nối RA ngoài tới MinMin (long-poll), không phải mở cổng router. Nó khởi động
`concat.exe --mcp` (MCP qua stdio, có sẵn trong Concat) và chuyển nguyên lời gọi công cụ của
MinMin vào đó. Khi cửa sổ Concat đang mở với Cài đặt > Tự động hoá > Script và ứng dụng BẬT, MCP
tự đi qua cửa sổ (chế độ `window`); không thì tự chạy bộ máy dựng không cửa sổ (`headless`).

Chỉ dùng thư viện chuẩn Python 3.8+, không cần cài thêm gì. Token máy lưu trong cau-noi.json.

Tệp vào/ra:
  - Tham số MinMin gửi có thể chứa chuỗi "minmin-tep:<số>": cầu nối tải tệp đó về
    THU_MUC_NHAP rồi thay bằng đường dẫn thật trên máy này trước khi gọi Concat.
  - Việc loại "lay_tep" đọc một tệp dưới thư mục người dùng (thường là video vừa xuất) và đẩy lên
    MinMin để lưu vào bộ não.
  - Ảnh trong kết quả (preview_frame) gửi nguyên base64; MinMin lưu thành tệp ảnh.
"""
from __future__ import annotations

import base64
import json
import os
import platform
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PHIEN_BAN = "26.10.326"
THU_MUC = Path(__file__).resolve().parent
CAU_HINH = THU_MUC / "cau-noi.json"
NHAT_KY = THU_MUC / "cau-noi.log"
NHIP_GIAY = 30
TEP_TOI_DA = 1536 * 1024 * 1024          # 1,5 GB: video xuất 4K dài vẫn lọt, chặn nhầm cả ổ
TIEN_TO_TEP = "minmin-tep:"
GIAO_THUC_MCP = "2025-06-18"

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
        try:
            return json.loads(CAU_HINH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def ghi_cau_hinh(d: dict) -> None:
    CAU_HINH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def thu_muc_nha() -> Path:
    return Path(os.path.expanduser("~"))


def thu_muc_lam_viec(cfg: dict = None) -> Path:
    """Nơi để dự án và video xuất. Concat chỉ ghi dưới thư mục người dùng, nên mặc định ở Videos."""
    cfg = cfg or {}
    if cfg.get("thu_muc_lam_viec"):
        return Path(cfg["thu_muc_lam_viec"])
    return thu_muc_nha() / "Videos" / "MinMin Concat"


def tim_concat(cfg: dict = None) -> str:
    """Đường dẫn concat.exe: cấu hình > biến môi trường > các nơi bộ cài hay đặt."""
    cfg = cfg or {}
    ung_vien = [cfg.get("concat_exe"), os.environ.get("CONCAT_EXE")]
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA") or str(thu_muc_nha() / "AppData" / "Local")
        ung_vien += [os.path.join(la, "Programs", "Concat", "concat.exe"),
                     os.path.join(la, "Programs", "concat", "concat.exe"),
                     os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Concat", "concat.exe")]
    elif sys.platform == "darwin":
        ung_vien.append("/Applications/Concat.app/Contents/MacOS/concat")
    else:
        ung_vien.append("/usr/bin/concat")
    for p in ung_vien:
        if p and Path(p).is_file():
            return str(p)
    raise RuntimeError("Không tìm thấy concat.exe. Cài Concat, hoặc ghi \"concat_exe\" vào cau-noi.json.")


# ============================================================
# Phiên MCP với concat --mcp (stdio, JSON-RPC 2.0 theo dòng)
# ============================================================
class LoiMCP(RuntimeError):
    pass


class PhienMCP:
    def __init__(self, exe: str, che_do: str = "auto"):
        self.exe = exe
        self.che_do = che_do
        self.proc = None
        self._id = 0
        self._cho = {}
        self._khoa = threading.Lock()
        self.thong_tin = {}
        self.cong_cu = []

    def song(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def mo(self) -> None:
        self.dong()
        co = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.proc = subprocess.Popen([self.exe, "--mcp", self.che_do], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     creationflags=co, cwd=str(thu_muc_nha()))
        threading.Thread(target=self._doc, daemon=True, name="mcp-doc").start()
        threading.Thread(target=self._doc_loi, daemon=True, name="mcp-loi").start()
        kq = self.goi("initialize", {"protocolVersion": GIAO_THUC_MCP, "capabilities": {},
                                     "clientInfo": {"name": "minmin-concat-cau", "version": PHIEN_BAN}},
                      timeout=60)
        self.thong_tin = kq.get("serverInfo") or {}
        self._gui({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.cong_cu = self.goi("tools/list", {}, timeout=60).get("tools") or []
        log(f"Concat MCP sẵn sàng: {self.thong_tin.get('name', 'concat')} "
            f"{self.thong_tin.get('version', '')}, {len(self.cong_cu)} công cụ")

    def dong(self) -> None:
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.stdin.close()
            except Exception:
                pass
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        with self._khoa:
            cho, self._cho = self._cho, {}
        for q in cho.values():
            q.put({"error": {"message": "Concat MCP đã đóng"}})

    def _gui(self, msg: dict) -> None:
        if not self.song():
            raise LoiMCP("Concat MCP chưa chạy")
        dong = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self._khoa:
            self.proc.stdin.write(dong)
            self.proc.stdin.flush()

    def _doc(self) -> None:
        p = self.proc
        try:
            for raw in p.stdout:
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue
                mid = msg.get("id")
                if mid is None or "method" in msg:
                    continue             # thông báo tiến độ hoặc yêu cầu từ server: bỏ qua
                with self._khoa:
                    q = self._cho.pop(mid, None)
                if q is not None:
                    q.put(msg)
        except Exception:
            pass

    def _doc_loi(self) -> None:
        p = self.proc
        try:
            for raw in p.stderr:
                s = raw.decode("utf-8", "replace").strip()
                if s:
                    log("[concat]", s[:400])
        except Exception:
            pass

    def goi(self, method: str, params: dict, timeout: float = 600) -> dict:
        with self._khoa:
            self._id += 1
            mid = self._id
            q = queue.Queue(1)
            self._cho[mid] = q
        self._gui({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty:
            with self._khoa:
                self._cho.pop(mid, None)
            raise LoiMCP(f"Concat không trả lời {method} sau {int(timeout)} giây")
        if msg.get("error"):
            raise LoiMCP(str(msg["error"].get("message") or msg["error"]))
        return msg.get("result") or {}

    def goi_cong_cu(self, ten: str, tham_so: dict, timeout: float = 600) -> dict:
        return self.goi("tools/call", {"name": ten, "arguments": tham_so or {}}, timeout=timeout)


# ============================================================
# Máy chủ MinMin
# ============================================================
class LoiHTTP(RuntimeError):
    def __init__(self, code: int, thong_diep: str):
        super().__init__(f"MinMin trả {code}: {thong_diep}")
        self.code = code


class MayChu:
    def __init__(self, goc: str, token: str = ""):
        self.goc = goc.rstrip("/")
        self.token = token

    def _req(self, method: str, duong: str, body=None, timeout: float = 60, tho: bool = False,
             du_lieu: bytes = None, loai: str = "application/json"):
        data = du_lieu if du_lieu is not None else (None if body is None else json.dumps(body).encode("utf-8"))
        rq = urllib.request.Request(self.goc + duong, data=data, method=method)
        rq.add_header("content-type", loai)
        rq.add_header("user-agent", f"MinMinConcat/{PHIEN_BAN}")
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

    def ghep(self, ma: str, ten: str) -> dict:
        return self._req("POST", "/concat/may/ghep", {"ma": ma, "ten": ten, "phien_ban": PHIEN_BAN})

    def nhip(self, **kw) -> dict:
        return self._req("POST", "/concat/may/nhip", {"phien_ban": PHIEN_BAN, **kw})

    def lay_viec(self, cho: int = 25):
        return self._req("GET", f"/concat/may/viec?cho={cho}", timeout=cho + 20).get("viec")

    def tai_tep(self, vid: int, so: int, dich: Path) -> None:
        dich.write_bytes(self._req("GET", f"/concat/may/tep/{vid}/{so}", timeout=900, tho=True))

    def day_tep(self, vid: int, ten: str, du_lieu: bytes) -> dict:
        return self._req("POST", f"/concat/may/tai-len/{vid}?ten={urllib.parse.quote(ten)}",
                         du_lieu=du_lieu, loai="application/octet-stream", timeout=1800)

    def ket_qua(self, vid: int, ok: bool, ket_qua=None, loi: str = "") -> None:
        self._req("POST", f"/concat/may/ket-qua/{vid}", {"ok": ok, "ket_qua": ket_qua, "loi": loi},
                  timeout=180)


# ============================================================
# Làm một việc
# ============================================================
def _ten_an_toan(ten: str) -> str:
    ten = os.path.basename(str(ten or "").replace("\\", "/")) or "tep"
    return "".join(c for c in ten if c not in '<>:"/\\|?*' and ord(c) >= 32)[:120] or "tep"


def thay_tep(gia_tri, tep: list, tai) -> object:
    """Thay mọi chuỗi 'minmin-tep:<số>' trong tham số bằng đường dẫn thật (tải về khi gặp lần đầu)."""
    if isinstance(gia_tri, str) and gia_tri.startswith(TIEN_TO_TEP):
        try:
            so = int(gia_tri[len(TIEN_TO_TEP):])
        except ValueError:
            return gia_tri
        if not 0 <= so < len(tep):
            raise RuntimeError(f"Tham số trỏ tới tệp số {so} không có trong việc")
        return tai(so)
    if isinstance(gia_tri, list):
        return [thay_tep(x, tep, tai) for x in gia_tri]
    if isinstance(gia_tri, dict):
        return {k: thay_tep(v, tep, tai) for k, v in gia_tri.items()}
    return gia_tri


def duong_cho_phep(p: str) -> Path:
    """Chỉ cho đọc tệp dưới thư mục người dùng (giống luật ghi của Concat)."""
    that = Path(os.path.expanduser(str(p or ""))).resolve()
    nha = thu_muc_nha().resolve()
    try:
        that.relative_to(nha)
    except ValueError:
        raise RuntimeError("Chỉ lấy được tệp nằm trong thư mục người dùng của máy này")
    if not that.is_file():
        raise RuntimeError(f"Không thấy tệp {that}")
    if that.stat().st_size > TEP_TOI_DA:
        raise RuntimeError("Tệp quá lớn (trên 1,5 GB)")
    return that


def lam_viec(may_chu: MayChu, mcp: PhienMCP, viec: dict, cfg: dict) -> None:
    vid = viec["id"]
    loai = viec.get("loai") or "goi"
    try:
        if loai == "lay_tep":
            p = duong_cho_phep(viec.get("duong_dan"))
            log(f"Việc #{vid}: gửi tệp {p.name} ({p.stat().st_size // 1024} KB) lên MinMin")
            kq = may_chu.day_tep(vid, p.name, p.read_bytes())
            may_chu.ket_qua(vid, True, {"tep": kq.get("duong_dan"), "ten": p.name})
            return
        if not mcp.song():
            mcp.mo()
        tep = viec.get("tep") or []
        nhap = thu_muc_lam_viec(cfg) / "nhap"
        da_tai = {}

        def tai(so: int) -> str:
            if so not in da_tai:
                nhap.mkdir(parents=True, exist_ok=True)
                dich = nhap / f"{vid}-{so}-{_ten_an_toan(tep[so].get('ten'))}"
                may_chu.tai_tep(vid, so, dich)
                da_tai[so] = str(dich)
            return da_tai[so]

        tham_so = thay_tep(viec.get("tham_so") or {}, tep, tai)
        cong_cu = viec.get("cong_cu")
        log(f"Việc #{vid}: {cong_cu}")
        cho = float(viec.get("cho_giay") or 600)
        kq = mcp.goi_cong_cu(cong_cu, tham_so, timeout=max(30.0, cho))
        may_chu.ket_qua(vid, not kq.get("isError"), kq,
                        "" if not kq.get("isError") else _chu(kq)[:500])
    except Exception as e:
        log(f"Việc #{vid} lỗi: {e}")
        if not isinstance(e, (LoiMCP, RuntimeError, LoiHTTP, OSError)):
            log(traceback.format_exc())
        if isinstance(e, LoiMCP) and not mcp.song():
            mcp.dong()
        try:
            may_chu.ket_qua(vid, False, None, str(e)[:500])
        except Exception as e2:
            log(f"Không gửi được kết quả việc #{vid}: {e2}")


def _chu(kq: dict) -> str:
    return " ".join(c.get("text", "") for c in (kq.get("content") or []) if c.get("type") == "text")


# ============================================================
# Vòng chạy
# ============================================================
def gui_nhip(may_chu: MayChu, mcp: PhienMCP, cfg: dict, loi: str = "") -> dict:
    return may_chu.nhip(
        concat_ok=mcp.song(), loi_concat=loi, concat=mcp.thong_tin,
        cong_cu=[{"name": t.get("name"), "description": t.get("description", ""),
                  "inputSchema": t.get("inputSchema") or {}} for t in mcp.cong_cu],
        thu_muc_lam_viec=str(thu_muc_lam_viec(cfg)), may=platform.node(),
    )


def chay() -> int:
    cfg = doc_cau_hinh()
    if not cfg.get("goc") or not cfg.get("token"):
        log("Chưa ghép máy. Chạy ghep-may.bat trước.")
        return 2
    may_chu = MayChu(cfg["goc"], cfg["token"])
    thu_muc_lam_viec(cfg).mkdir(parents=True, exist_ok=True)
    mcp = PhienMCP(tim_concat(cfg), cfg.get("che_do") or "auto")
    loi = ""
    try:
        mcp.mo()
    except Exception as e:
        loi = str(e)
        log("Chưa mở được Concat MCP:", loi)
    dung = threading.Event()

    def nhip_lap():
        nonlocal loi
        while not dung.is_set():
            try:
                if not mcp.song():
                    try:
                        mcp.mo()
                        loi = ""
                    except Exception as e:
                        loi = str(e)
                gui_nhip(may_chu, mcp, cfg, loi)
            except LoiHTTP as e:
                log("Nhịp lỗi:", e)
                if e.code in (401, 403):
                    log("Máy đã bị gỡ khỏi MinMin. Ghép lại bằng ghep-may.bat.")
                    dung.set()
            except Exception as e:
                log("Nhịp lỗi:", e)
            dung.wait(NHIP_GIAY)

    threading.Thread(target=nhip_lap, daemon=True, name="nhip").start()
    log(f"Cầu nối Concat {PHIEN_BAN} đang chạy, nối tới {cfg['goc']}. Để cửa sổ này mở.")
    while not dung.is_set():
        try:
            viec = may_chu.lay_viec(25)
        except LoiHTTP as e:
            if e.code in (401, 403):
                log("Token máy không còn hợp lệ. Ghép lại bằng ghep-may.bat.")
                return 2
            log("Lấy việc lỗi:", e)
            time.sleep(10)
            continue
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            log("Mất kết nối tới MinMin:", e)
            time.sleep(10)
            continue
        if viec:
            lam_viec(may_chu, mcp, viec, cfg)
    mcp.dong()
    return 2


def ghep(goc: str, ma: str) -> int:
    goc = goc.strip().rstrip("/")
    if not goc.startswith("http"):
        goc = "https://" + goc
    kq = MayChu(goc).ghep(ma.strip(), platform.node())
    cfg = doc_cau_hinh()
    cfg.update({"goc": goc, "token": kq["token"], "may_id": kq.get("may_id")})
    ghi_cau_hinh(cfg)
    log(f"Đã ghép với {goc}. Giờ bấm đúp chay.bat.")
    return 0


def thu() -> int:
    cfg = doc_cau_hinh()
    mcp = PhienMCP(tim_concat(cfg), cfg.get("che_do") or "auto")
    mcp.mo()
    kq = mcp.goi_cong_cu("concat_version", {}, timeout=60)
    print(_chu(kq)[:2000])
    mcp.dong()
    return 0


def main(argv) -> int:
    if len(argv) >= 4 and argv[1] == "ghep":
        return ghep(argv[2], argv[3])
    if len(argv) >= 2 and argv[1] == "chay":
        return chay()
    if len(argv) >= 2 and argv[1] == "thu":
        return thu()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
