"""Driver GPM Login (Global v5.x) qua Local API trên máy này (mặc định http://127.0.0.1:9495).

Đường đã kiểm trên GPMLogin Global v5.1.2:
    GET /api/v1/profiles?page=&per_page=   danh sách profile (phân trang)
    GET /api/v1/groups                     danh sách nhóm
    GET /api/v1/profiles/start/{id}        mở profile -> remote_debugging_port, websocket_debugging_url
    GET /api/v1/profiles/stop/{id}         đóng profile

Không cần bật "Cho phép remote từ internet" trong GPM: worker chạy trên cùng máy nên gọi
localhost. Muốn đổi sang MultiProfile sau này chỉ cần viết một driver khác cùng ba hàm.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request


class LoiGPM(RuntimeError):
    pass


class GPM:
    ten = "gpm"

    def __init__(self, goc: str = "http://127.0.0.1:9495", timeout: float = 60):
        self.goc = goc.rstrip("/")
        self.timeout = timeout

    def _get(self, duong: str, **q) -> dict:
        url = self.goc + duong + ("?" + urllib.parse.urlencode(q) if q else "")
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as r:
                d = json.loads(r.read().decode("utf-8") or "{}")
        except Exception as e:
            raise LoiGPM(f"không gọi được GPM Login ở {self.goc} ({type(e).__name__}). "
                         "GPM Login đã mở chưa? API Gateway có đúng cổng không?") from e
        if not d.get("success"):
            raise LoiGPM(f"GPM báo lỗi: {d.get('message') or 'không rõ'}")
        return d.get("data")

    def kiem_tra(self) -> str:
        """Trả tên/phiên bản GPM, raise LoiGPM nếu không gọi được."""
        url = self.goc + "/api/v1/groups"
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8") or "{}")
        return str(d.get("sender") or "GPM Login")

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

    def mo(self, profile_id: str) -> str:
        """Mở profile, trả địa chỉ CDP cho Playwright connect_over_cdp."""
        d = self._get(f"/api/v1/profiles/start/{urllib.parse.quote(profile_id)}") or {}
        cong = int(d.get("remote_debugging_port") or 0)
        if not cong:
            raise LoiGPM("GPM mở profile nhưng không trả cổng điều khiển (profile Firefox không điều khiển được)")
        return f"http://127.0.0.1:{cong}"

    def dong(self, profile_id: str) -> None:
        try:
            self._get(f"/api/v1/profiles/stop/{urllib.parse.quote(profile_id)}")
        except LoiGPM:
            pass
