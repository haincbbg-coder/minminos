#!/usr/bin/env python3
"""MinMin Tay - cho HUD MinMin dieu khien chuot va ban phim cua may Windows bang cu chi tay.

Chay tren MAY CUA BO (khong phai VPS). HUD tren trinh duyet nhan dien tay, gui lenh toi day qua
http://localhost:47700; chuong trinh nay bam chuot / phim that bang Windows API (SendInput).

An toan:
  - Chi nghe o localhost (127.0.0.1), may khac trong mang khong goi duoc.
  - Moi lenh phai kem MA GHEP NOI (sinh ngau nhien lan dau, luu o %APPDATA%\\MinMinTay\\ma.txt).
    Trang web khac khong co ma thi khong dieu khien duoc may bo.
  - Chi nhan mot so lenh co dinh: di chuot, bam, cuon, phong to (Ctrl + lan), mot so phim dieu
    huong. KHONG go chu, KHONG chay lenh, KHONG doc man hinh.
  - Tat cua so nay (hoac Ctrl+C) la dung ngay.

Chay:  py minmin-tay.py            (tu in ma ghep noi va chep san vao clipboard)
       py minmin-tay.py --man 2    (dieu khien man hinh so 2 thay vi man chinh)
       py minmin-tay.py --thu      (chay thu, chi in lenh ra man hinh, khong bam that)
Chi dung thu vien co san cua Python 3.8+, khong can cai them gi.
"""
import argparse
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONG = 47700
PHIEN_BAN = "1.0"
PHIM = {  # ten phim -> (ma phim Windows, co phai phim mo rong)
    "left": (0x25, True), "up": (0x26, True), "right": (0x27, True), "down": (0x28, True),
    "pageup": (0x21, True), "pagedown": (0x22, True), "home": (0x24, True), "end": (0x23, True),
    "space": (0x20, False), "enter": (0x0D, False), "esc": (0x1B, False), "tab": (0x09, False),
    "browserback": (0xA6, True), "browserforward": (0xA7, True),
}
LENH = {"move", "click", "rclick", "dblclick", "scroll", "hscroll", "zoom", "key"}


def thu_muc():
    goc = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(goc, "MinMinTay")
    os.makedirs(d, exist_ok=True)
    return d


def lay_ma(tao_moi=False):
    """Ma ghep noi: doc tu tep, chua co (hoac tao_moi) thi sinh ngau nhien."""
    p = os.path.join(thu_muc(), "ma.txt")
    if not tao_moi and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            ma = f.read().strip()
        if len(ma) >= 16:
            return ma
    ma = secrets.token_urlsafe(18)
    with open(p, "w", encoding="utf-8") as f:
        f.write(ma)
    return ma


def kiem_lenh(d):
    """Kiem va chuan hoa mot lenh tu HUD. Tra dict sach hoac nem ValueError."""
    if not isinstance(d, dict):
        raise ValueError("lenh phai la object")
    t = d.get("t")
    if t not in LENH:
        raise ValueError("lenh khong ho tro")
    out = {"t": t}
    if t == "move":
        x, y = float(d.get("x")), float(d.get("y"))
        out["x"], out["y"] = min(1.0, max(0.0, x)), min(1.0, max(0.0, y))
    elif t in ("scroll", "hscroll", "zoom"):
        k = "d" if t == "zoom" else "n"
        n = int(d.get(k, 0))
        out[k] = max(-10, min(10, n))
    elif t == "key":
        k = str(d.get("k", "")).lower()
        if k not in PHIM:
            raise ValueError("phim khong ho tro")
        out["k"] = k
    return out


# ---------------- Bam that tren Windows ----------------
class MayWindows:
    def __init__(self, man=0):
        import ctypes
        from ctypes import wintypes
        self.c = ctypes
        self.u = ctypes.windll.user32
        try:   # toa do dung pixel that tren man hinh co phong chu 125-150%
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                self.u.SetProcessDPIAware()
            except Exception:
                pass
        self.mans = self._liet_ke(wintypes)
        chinh = [m for m in self.mans if m["chinh"]] or self.mans
        self.man = self.mans[man - 1] if 0 < man <= len(self.mans) else chinh[0]

    def _liet_ke(self, wintypes):
        c = self.c
        mans = []

        class MONITORINFO(c.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        CB = c.WINFUNCTYPE(c.c_int, wintypes.HMONITOR, wintypes.HDC, c.POINTER(wintypes.RECT), wintypes.LPARAM)

        def cb(hm, hdc, rc, lp):
            mi = MONITORINFO()
            mi.cbSize = c.sizeof(MONITORINFO)
            self.u.GetMonitorInfoW(hm, c.byref(mi))
            r = mi.rcMonitor
            mans.append({"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top,
                         "chinh": bool(mi.dwFlags & 1)})
            return 1
        self.u.EnumDisplayMonitors(0, 0, CB(cb), 0)
        return mans or [{"x": 0, "y": 0, "w": self.u.GetSystemMetrics(0), "h": self.u.GetSystemMetrics(1), "chinh": True}]

    def mo_ta(self):
        m = self.man
        return f"{m['w']}x{m['h']}" + (" (màn chính)" if m["chinh"] else "")

    def _chuot(self, co, du=0):
        self.u.mouse_event(co, 0, 0, du & 0xFFFFFFFF, 0)

    def _phim(self, vk, mo_rong=False, len_=False):
        co = (0x1 if mo_rong else 0) | (0x2 if len_ else 0)
        self.u.keybd_event(vk, 0, co, 0)

    def lam(self, l):
        t = l["t"]
        if t == "move":
            m = self.man
            self.u.SetCursorPos(int(m["x"] + l["x"] * (m["w"] - 1)), int(m["y"] + l["y"] * (m["h"] - 1)))
        elif t == "click":
            self._chuot(0x2); self._chuot(0x4)
        elif t == "rclick":
            self._chuot(0x8); self._chuot(0x10)
        elif t == "dblclick":
            for _ in range(2):
                self._chuot(0x2); self._chuot(0x4)
        elif t == "scroll":
            self._chuot(0x800, 120 * l["n"])
        elif t == "hscroll":
            self._chuot(0x1000, 120 * l["n"])
        elif t == "zoom":   # Ctrl + lan chuot: phong to / thu nho trong trinh duyet, Word, PDF, anh
            self._phim(0x11)
            try:
                for _ in range(abs(l["d"])):
                    self._chuot(0x800, 120 if l["d"] > 0 else -120)
            finally:
                self._phim(0x11, len_=True)
        elif t == "key":
            vk, mr = PHIM[l["k"]]
            self._phim(vk, mr); self._phim(vk, mr, True)


class MayThu:
    """--thu hoac khong phai Windows: chi ghi lai lenh (de kiem tra, khong bam that)."""
    def __init__(self):
        self.da_lam = []

    def mo_ta(self):
        return "chạy thử (không bấm thật)"

    def lam(self, l):
        self.da_lam.append(l)
        print("  ->", json.dumps(l, ensure_ascii=False), flush=True)


# ---------------- May chu HTTP ----------------
def tao_may_chu(ma, may, nguon=None, cong=CONG, host="127.0.0.1"):
    """nguon: danh sach Origin duoc phep (None = moi trang, nhung van phai co ma)."""
    khoa = threading.Lock()

    class XuLy(BaseHTTPRequestHandler):
        server_version = "MinMinTay/" + PHIEN_BAN

        def log_message(self, *a):
            pass

        def _nguon_ok(self):
            o = self.headers.get("Origin")
            return not nguon or not o or o in nguon

        def _dau(self, code, body=None):
            o = self.headers.get("Origin")
            self.send_response(code)
            if o and self._nguon_ok():
                self.send_header("Access-Control-Allow-Origin", o)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "content-type, x-minmin-token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                # Chrome: trang https goi vao localhost phai duoc cho phep "mang noi bo"
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Cache-Control", "no-store")
            data = json.dumps(body if body is not None else {}, ensure_ascii=False).encode()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _ma_ok(self):
            return secrets.compare_digest(self.headers.get("x-minmin-token", ""), ma)

        def do_OPTIONS(self):
            o = self.headers.get("Origin")
            self.send_response(204 if self._nguon_ok() else 403)
            if o and self._nguon_ok():
                self.send_header("Access-Control-Allow-Origin", o)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "content-type, x-minmin-token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if self.path.split("?")[0] != "/ping":
                return self._dau(404, {"ok": False})
            if not self._nguon_ok():
                return self._dau(403, {"ok": False, "ly_do": "sai_nguon"})
            if not self._ma_ok():
                return self._dau(401, {"ok": False, "ly_do": "sai_ma"})
            self._dau(200, {"ok": True, "ten": "MinMin Tay", "phien_ban": PHIEN_BAN, "man": may.mo_ta()})

        def do_POST(self):
            if self.path.split("?")[0] != "/act":
                return self._dau(404, {"ok": False})
            if not self._nguon_ok():
                return self._dau(403, {"ok": False, "ly_do": "sai_nguon"})
            if not self._ma_ok():
                return self._dau(401, {"ok": False, "ly_do": "sai_ma"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 2048:
                    raise ValueError("lenh qua dai")
                lenh = kiem_lenh(json.loads(self.rfile.read(n) or b"{}"))
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                return self._dau(400, {"ok": False, "ly_do": str(e)})
            with khoa:
                may.lam(lenh)
            self._dau(200, {"ok": True})

    return ThreadingHTTPServer((host, cong), XuLy)


def chep_clipboard(chu):
    if os.name != "nt":
        return False
    try:
        import subprocess
        subprocess.run("clip", input=chu.encode("utf-16-le"), check=True, shell=True)
        return True
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="MinMin Tay: điều khiển chuột, bàn phím bằng cử chỉ tay qua HUD MinMin")
    ap.add_argument("--man", type=int, default=0, help="số thứ tự màn hình cần điều khiển (mặc định: màn chính)")
    ap.add_argument("--nguon", default="", help="chỉ nhận lệnh từ các trang này, cách nhau dấu phẩy (vd https://minmin.elaria.cloud)")
    ap.add_argument("--thu", action="store_true", help="chạy thử: in lệnh ra màn hình, không bấm thật")
    ap.add_argument("--ma-moi", action="store_true", help="tạo mã ghép nối mới (mã cũ hết hiệu lực)")
    ap.add_argument("--cong", type=int, default=CONG)
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    may = MayThu() if (a.thu or os.name != "nt") else MayWindows(a.man)
    ma = lay_ma(a.ma_moi)
    nguon = [x.strip().rstrip("/") for x in a.nguon.split(",") if x.strip()] or None
    try:
        sv = tao_may_chu(ma, may, nguon, a.cong)
    except OSError:
        print(f"Cổng {a.cong} đang bận: có thể MinMin Tay đã chạy ở một cửa sổ khác.")
        input("Nhấn Enter để đóng...")
        return 1
    print("=" * 60)
    print(" MINMIN TAY đang chạy - HUD MinMin điều khiển được chuột, bàn phím")
    print("=" * 60)
    print(f" Màn hình điều khiển : {may.mo_ta()}")
    print(f" Mã ghép nối         : {ma}")
    if chep_clipboard(ma):
        print("                       (đã chép sẵn, vào HUD bấm Máy tính rồi dán Ctrl+V)")
    print(" Tắt cửa sổ này hoặc nhấn Ctrl+C để dừng.")
    print("=" * 60, flush=True)
    try:
        sv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
