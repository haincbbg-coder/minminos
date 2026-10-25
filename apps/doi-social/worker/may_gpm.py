"""Driver GPM Login (Global v5.x) qua Local API trên máy này (mặc định http://127.0.0.1:9495).

Đường đã kiểm trên GPMLogin Global v5.1.2:
    GET /api/v1/profiles?page=&per_page=   danh sách profile (phân trang)
    GET /api/v1/groups                     danh sách nhóm
    GET /api/v1/profiles/start/{id}        mở profile -> remote_debugging_port, addition_info.process_id
    GET /api/v1/profiles/stop/{id}         đóng profile

Bài học từ máy thật (2026-10-20): cổng `remote_debugging_port` GPM trả về KHÔNG phải lúc nào cũng
là cổng trình duyệt đang nghe (Playwright báo ECONNREFUSED dù cửa sổ đã mở). Vì vậy `mo()` không
tin mù cổng đó: nó hỏi /json/version trên cổng được báo, và nếu không ai trả lời thì tìm mọi cổng
đang LISTEN của tiến trình trình duyệt (process_id GPM trả về và các tiến trình con của nó) rồi
chọn cổng nào trả lời đúng giao thức DevTools. Profile đang mở sẵn (ProfileInUse) thì đóng rồi
mở lại.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request


class LoiGPM(RuntimeError):
    pass


def _devtools(cong: int, timeout: float = 2.0):
    """Trả JSON /json/version nếu cổng là DevTools của Chrome, không thì None."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{cong}/json/version", timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8") or "{}")
        return d if d.get("webSocketDebuggerUrl") else None
    except Exception:
        return None


def _chay(lenh: list, timeout: float = 20) -> str:
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = 0x08000000      # CREATE_NO_WINDOW: không nháy cửa sổ đen
    try:
        return subprocess.run(lenh, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace", **kw).stdout or ""
    except Exception:
        return ""


def cay_tien_trinh(pid: int) -> set:
    """pid và mọi tiến trình con cháu của nó (Windows, qua PowerShell CIM)."""
    if sys.platform != "win32" or not pid:
        return {pid} if pid else set()
    ra = _chay(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId) $($_.Name)\" }"])
    con: dict = {}
    for dong in ra.splitlines():
        p = dong.split(None, 2)
        if len(p) >= 2 and p[0].isdigit() and p[1].isdigit():
            con.setdefault(int(p[1]), []).append(int(p[0]))
    tap, hang = {pid}, [pid]
    while hang:
        for c in con.get(hang.pop(), []):
            if c not in tap:
                tap.add(c)
                hang.append(c)
    return tap


def cong_dang_nghe(pids: set) -> list:
    """Các cổng TCP đang nghe thuộc các pid đã cho. Không dựa vào chữ "LISTENING" vì Windows
    tiếng Việt dịch cột trạng thái; cổng nghe là dòng có địa chỉ xa 0.0.0.0:0 hoặc [::]:0."""
    out = []
    for dong in _chay(["netstat", "-ano", "-p", "TCP"]).splitlines():
        p = dong.split()
        if len(p) >= 5 and p[-1].isdigit() and int(p[-1]) in pids and p[2] in ("0.0.0.0:0", "[::]:0", "*:*"):
            m = re.search(r":(\d+)$", p[1])
            if m:
                out.append(int(m.group(1)))
    return sorted(set(out))


def thu_muc_profile(dong_lenh: str) -> str:
    m = re.search(r'--user-data-dir=(?:"([^"]+)"|(\S+))', dong_lenh or "")
    return (m.group(1) or m.group(2)) if m else ""


def cong_tu_tep(thu_muc: str):
    """Chrome mở bằng --remote-debugging-port=0 ghi cổng thật vào <user-data-dir>/DevToolsActivePort."""
    import os
    try:
        with open(os.path.join(thu_muc, "DevToolsActivePort"), encoding="utf-8") as f:
            dong = f.read().split()
        return int(dong[0]) if dong and dong[0].isdigit() else None
    except Exception:
        return None


def mo_lai_co_cong(dong_lenh: str, pid_chinh: int, nhat_ky) -> int:
    """Tắt trình duyệt GPM vừa mở rồi chạy LẠI đúng dòng lệnh đó, thêm --remote-debugging-port=0.

    Mọi cờ GPM dùng để giả vân tay (extension nạp vào, ngôn ngữ, thư mục profile, proxy) giữ
    nguyên, vì ta chạy lại đúng dòng lệnh của nó. Trả pid tiến trình mới."""
    import os
    tm = thu_muc_profile(dong_lenh)
    _chay(["taskkill", "/PID", str(pid_chinh), "/T", "/F"])
    han = time.monotonic() + 15
    while time.monotonic() < han and any(p == pid_chinh for p, _ in tien_trinh_profile(os.path.basename(tm) or "x")):
        time.sleep(0.5)
    time.sleep(1.5)
    try:
        os.remove(os.path.join(tm, "DevToolsActivePort"))
    except Exception:
        pass
    lenh = re.sub(r"\s--remote-debugging-(?:port|pipe)(?:=\S+)?", "", dong_lenh).strip() + " --remote-debugging-port=0"
    kw = {"creationflags": 0x00000008 | 0x00000200} if sys.platform == "win32" else {}   # DETACHED | NEW_GROUP
    p = subprocess.Popen(lenh, close_fds=True, **kw)
    nhat_ky(f"Đã mở lại trình duyệt của profile với cổng điều khiển (tiến trình {p.pid})")
    return p.pid


def tien_trinh_profile(profile_id: str) -> list:
    """[(pid, dòng lệnh)] của mọi chrome.exe đang chạy mà dòng lệnh có id profile này."""
    if sys.platform != "win32":
        return []
    ra = _chay(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"], timeout=30)
    out = []
    for dong in ra.splitlines():
        pid, _, cmd = dong.partition("\t")
        if pid.strip().isdigit() and profile_id.lower() in cmd.lower():
            out.append((int(pid), cmd.strip()))
    return out


class GPM:
    ten = "gpm"

    def __init__(self, goc: str = "http://127.0.0.1:9495", timeout: float = 60, nhat_ky=None):
        self.goc = goc.rstrip("/")
        self.timeout = timeout
        self.nhat_ky = nhat_ky or (lambda s: None)
        self._tu_mo: dict = {}

    def _get_tho(self, duong: str, **q) -> dict:
        url = self.goc + duong + ("?" + urllib.parse.urlencode(q) if q else "")
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except Exception as e:
            raise LoiGPM(f"không gọi được GPM Login ở {self.goc} ({type(e).__name__}). "
                         "GPM Login đã mở chưa? API Gateway có đúng cổng không?") from e

    def _get(self, duong: str, **q):
        d = self._get_tho(duong, **q)
        if not d.get("success"):
            raise LoiGPM(f"GPM báo lỗi: {d.get('message') or 'không rõ'}")
        return d.get("data")

    def kiem_tra(self) -> str:
        return str(self._get_tho("/api/v1/groups").get("sender") or "GPM Login")

    def nhom(self) -> dict:
        try:
            d = self._get("/api/v1/groups", page=1, per_page=200)
            return {g["id"]: g.get("name", "") for g in (d or {}).get("data", [])}
        except LoiGPM:
            return {}

    def ds_profile(self) -> list:
        nhom = self.nhom()
        out, trang = [], 1
        while trang <= 50:
            d = self._get("/api/v1/profiles", page=trang, per_page=100) or {}
            for p in d.get("data", []):
                out.append({"id": p["id"], "ten": p.get("name", ""),
                            "nhom": nhom.get(p.get("group_id"), ""),
                            "trinh_duyet": (p.get("browser") or {}).get("name", ""),
                            "co_proxy": bool(p.get("raw_proxy"))})
            if trang >= int(d.get("last_page") or 1):
                break
            trang += 1
        return out

    THAM_SO_MO = {"addination_args": "--remote-debugging-port=0",
                  "addition_args": "--remote-debugging-port=0",
                  "args": "--remote-debugging-port=0"}

    def _start(self, profile_id: str) -> dict:
        # GPM Global v5.1.2 báo `remote_debugging_port` nhưng KHÔNG bật nó trên trình duyệt (đã soi
        # dòng lệnh chrome.exe trên máy thật 2026-10-20). Xin GPM thêm cờ cổng ngẫu nhiên; cổng
        # thật đọc từ tệp DevToolsActivePort trong thư mục profile.
        d = self._get_tho(f"/api/v1/profiles/start/{urllib.parse.quote(profile_id)}", **self.THAM_SO_MO)
        def _dang_dung(x):
            return not x.get("success") and "inuse" in str(x.get("message") or "").lower().replace("_", "")
        if _dang_dung(d):
            # 26.10.225: GPM đóng profile mất 5-20 giây (Chrome lưu cookie), có khi chrome là do Worker
            # lần trước tự mở lại nên GPM không quản. Thử lại tới ~40 giây; quá 12 giây thì đóng hẳn
            # các tiến trình chrome của đúng profile này (đóng êm trước, rồi mới buộc).
            self.nhat_ky("Profile đang mở sẵn: đóng lại rồi mở bằng Worker")
            self.dong(profile_id)
            bat_dau, da_dong_han = time.monotonic(), False
            while _dang_dung(d) and time.monotonic() - bat_dau < 40:
                time.sleep(3)
                if not da_dong_han and time.monotonic() - bat_dau > 12:
                    da_dong_han = True
                    pids = sorted({pp for pp, _ in tien_trinh_profile(profile_id)})
                    if pids:
                        self.nhat_ky(f"Profile vẫn bận: đóng {len(pids)} tiến trình chrome của profile này")
                        for pp in pids:
                            _chay(["taskkill", "/PID", str(pp), "/T"])
                        time.sleep(3)
                        for pp in pids:
                            _chay(["taskkill", "/PID", str(pp), "/T", "/F"])
                    try:
                        self._get_tho(f"/api/v1/profiles/stop/{urllib.parse.quote(profile_id)}")
                    except LoiGPM:
                        pass
                d = self._get_tho(f"/api/v1/profiles/start/{urllib.parse.quote(profile_id)}", **self.THAM_SO_MO)
            if _dang_dung(d):
                raise LoiGPM("profile đang được mở ở nơi khác (có thể bạn đang dùng nick này trong GPM). "
                             "Đóng cửa sổ profile đó rồi chạy lại")
        if not d.get("success"):
            raise LoiGPM(f"GPM không mở được profile: {d.get('message') or 'không rõ'}")
        return d.get("data") or {}

    def mo(self, profile_id: str, cho_toi_da: float = 60) -> str:
        """Mở profile, trả địa chỉ CDP (http://127.0.0.1:<cổng>) đã KIỂM là DevTools thật."""
        self._da_ghi_cmd = False
        self._da_mo_lai = False
        d = self._start(profile_id)
        cong = int(d.get("remote_debugging_port") or 0)
        pid = int((d.get("addition_info") or {}).get("process_id") or 0)
        ws = str(d.get("websocket_debugging_url") or "")
        self.nhat_ky(f"GPM mở profile: cổng báo {cong or '-'}, tiến trình {pid or '-'}")
        han = time.monotonic() + cho_toi_da
        da_quet = set()
        while time.monotonic() < han:
            if cong and _devtools(cong):
                return f"http://127.0.0.1:{cong}"
            if ws.startswith("ws"):
                return ws
            pids = cay_tien_trinh(pid) if pid else set()
            ds_tt = tien_trinh_profile(profile_id)
            pids |= {p for p, _ in ds_tt}
            chinh_cmd = next((c for _, c in ds_tt if "--type=" not in c), "")
            tm = thu_muc_profile(chinh_cmd)
            c_tep = cong_tu_tep(tm) if tm and "--remote-debugging-port" in chinh_cmd else None
            if c_tep and _devtools(c_tep):
                self.nhat_ky(f"Cổng điều khiển thật: {c_tep} (từ DevToolsActivePort)")
                return f"http://127.0.0.1:{c_tep}"
            if ds_tt and not getattr(self, "_da_ghi_cmd", False):
                self._da_ghi_cmd = True
                chinh = min(ds_tt, key=lambda x: len(x[1]) if "--type=" in x[1] else -1)
                co = [a for a in re.findall(r"--[\w-]+(?:=\S+)?", chinh[1])
                      if "debug" in a or "user-data" in a or "automation" in a or "pipe" in a]
                self.nhat_ky(f"Tiến trình chrome của profile: {len(ds_tt)}; cờ liên quan: {co or 'không có'}")
                self.nhat_ky("Các cờ khởi động: " + " ".join(sorted({a.split("=")[0] for a in re.findall(r"--[\w-]+", chinh[1])})))
            if (chinh_cmd and "--remote-debugging-port" not in chinh_cmd
                    and not getattr(self, "_da_mo_lai", False)):
                self._da_mo_lai = True
                chinh_pid = next((p for p, c in ds_tt if c == chinh_cmd), 0)
                self.nhat_ky("GPM không bật cổng điều khiển: mở lại profile bằng đúng dòng lệnh của GPM, thêm cổng")
                self._tu_mo[profile_id] = mo_lai_co_cong(chinh_cmd, chinh_pid, self.nhat_ky)
                time.sleep(2)
                continue
            if pids:
                for c in cong_dang_nghe(pids):
                    if c != cong and _devtools(c):
                        self.nhat_ky(f"Trình duyệt nghe ở cổng {c} (khác cổng GPM báo {cong})")
                        return f"http://127.0.0.1:{c}"
                    da_quet.add(c)
            time.sleep(2)
        raise LoiGPM(f"profile đã mở nhưng không có cổng điều khiển nào trả lời sau {int(cho_toi_da)}s "
                     f"(cổng GPM báo {cong}, các cổng tiến trình đang nghe: {sorted(da_quet) or 'không có'}). "
                     "Cách sửa: GPM Login > Cài đặt > Trình duyệt > Chrome start parameters, thêm dòng "
                     "--remote-debugging-port=0 rồi Lưu.")

    def dong(self, profile_id: str) -> None:
        pid = self._tu_mo.pop(profile_id, None)
        if pid:
            _chay(["taskkill", "/PID", str(pid), "/T"])     # đóng êm để Chrome kịp lưu cookie
            time.sleep(3)
            _chay(["taskkill", "/PID", str(pid), "/T", "/F"])
        try:
            self._get_tho(f"/api/v1/profiles/stop/{urllib.parse.quote(profile_id)}")
        except LoiGPM:
            pass
