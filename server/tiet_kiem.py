"""tiet_kiem.py - TIẾT KIỆM TOKEN không mất dữ liệu (Lớp 6, 26.10.154).

Vì sao: một báo cáo HALIMI/MeiMei tốn 467.000 token (ảnh chủ repo 11/10): não gọi cùng một
tool Pancake nhiều lần cho cùng khoảng giờ, JSON trả về thụt dòng và đầy trường rỗng, và phải
mò qua lớp "tìm tool" trước khi gọi. Ba việc ở đây đều TẤT ĐỊNH và KHÔNG BAO GIỜ BỎ SỐ:

  1. nen_json(): nén kết quả tool. JSON thì dump lại dạng đặc, bỏ trường null/""/[]/{} (giữ 0,
     false); văn bản thường thì gom khoảng trắng thừa. Mọi giá trị số và chữ giữ nguyên.
     (Khác Headroom: nó bỏ bớt phần tử giữa danh sách theo thống kê; với tiền thì không được.)
  2. BoDem: bộ đệm kết quả tool CHỈ ĐỌC theo (kết nối, tool, tham số) trong vài phút. Việc ghi
     lên kết nối đó xoá đệm của kết nối đó, nên không bao giờ đọc được số cũ sau khi vừa sửa.
  3. tool_nong(): các tool được gọi nhiều nhất (theo nhật ký hub) luôn hiện trực tiếp cho não,
     không giấu sau lớp tìm tool.

Thuần stdlib. Hook ở mcp_hub (_guard, _apply_lazy).
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter
from typing import Any, Iterable, Optional

# ─────────────────────────── nén không mất dữ liệu ───────────────────────────

_RE_KHOANG = re.compile(r"[ \t]{2,}")
_RE_DONG_TRONG = re.compile(r"\n{3,}")


def _bo_rong(v: Any) -> Any:
    """Bỏ trường rỗng đệ quy. GIỮ 0, False, "0". Danh sách giữ nguyên số phần tử (chỉ làm sạch
    từng phần tử), vì số phần tử của một danh sách đơn hàng CHÍNH LÀ một con số."""
    if isinstance(v, dict):
        ra = {}
        for k, x in v.items():
            x2 = _bo_rong(x)
            if x2 is None or x2 == "" or x2 == [] or x2 == {}:
                continue
            ra[k] = x2
        return ra
    if isinstance(v, list):
        return [_bo_rong(x) for x in v]
    return v


def nen_json(text: Any) -> str:
    """Kết quả tool -> bản gọn hơn, cùng nội dung. Không phải JSON thì chỉ gom khoảng trắng."""
    s = text if isinstance(text, str) else str(text)
    t = s.strip()
    if t[:1] in ("{", "[") and t[-1:] in ("}", "]"):
        try:
            obj = json.loads(t)
        except ValueError:
            obj = None
        if obj is not None and isinstance(obj, (dict, list)):
            try:
                return json.dumps(_bo_rong(obj), ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                pass
    s = _RE_KHOANG.sub(" ", s)
    s = _RE_DONG_TRONG.sub("\n\n", s)
    return s


# ─────────────────────────── bộ đệm tool đọc ───────────────────────────

def khoa_dem(conn_id: str, tool: str, args: Any) -> str:
    """Khoá tất định: tham số dump sắp khoá, nên {a:1,b:2} và {b:2,a:1} là một."""
    try:
        a = json.dumps(args if args is not None else {}, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        a = str(args)
    return f"{conn_id}|{tool}|{a}"


class BoDem:
    """TTL cache nhỏ, an toàn luồng. `tru` cho mục chưa hết hạn; `xoa_ket_noi` khi có việc ghi."""

    def __init__(self, ttl_giay: int = 180, toi_da: int = 400):
        self.ttl = max(0, int(ttl_giay))
        self.toi_da = max(10, int(toi_da))
        self._kho: dict = {}
        self._lock = threading.Lock()
        self.hit = 0
        self.miss = 0
        self.ky_tu_tiet_kiem = 0   # nen_json tiết kiệm được bao nhiêu ký tự (đếm ở hook)

    def lay(self, khoa: str, now: Optional[float] = None) -> Optional[str]:
        if self.ttl <= 0:
            return None
        now = time.time() if now is None else now
        with self._lock:
            ent = self._kho.get(khoa)
            if not ent:
                self.miss += 1
                return None
            ts, conn_id, gia_tri = ent
            if now - ts > self.ttl:
                self._kho.pop(khoa, None)
                self.miss += 1
                return None
            self.hit += 1
            return gia_tri

    def cat(self, khoa: str, conn_id: str, gia_tri: str, now: Optional[float] = None) -> None:
        if self.ttl <= 0:
            return
        now = time.time() if now is None else now
        with self._lock:
            if len(self._kho) >= self.toi_da:
                # bỏ 1/4 mục cũ nhất
                cu = sorted(self._kho.items(), key=lambda kv: kv[1][0])[: max(1, self.toi_da // 4)]
                for k, _ in cu:
                    self._kho.pop(k, None)
            self._kho[khoa] = (now, conn_id, gia_tri)

    def xoa_ket_noi(self, conn_id: str) -> int:
        """Việc GHI lên một kết nối -> mọi mục đọc của kết nối đó hết hiệu lực ngay."""
        with self._lock:
            ks = [k for k, (_, c, _) in self._kho.items() if c == conn_id]
            for k in ks:
                self._kho.pop(k, None)
            return len(ks)

    def xoa_het(self) -> None:
        with self._lock:
            self._kho.clear()

    def thong_ke(self) -> dict:
        with self._lock:
            n = len(self._kho)
        tong = self.hit + self.miss
        return {"muc": n, "hit": self.hit, "miss": self.miss,
                "ty_le_hit": round(self.hit / tong, 3) if tong else 0.0,
                "ky_tu_tiet_kiem": self.ky_tu_tiet_kiem, "ttl_giay": self.ttl}


# ─────────────────────────── tool nóng ───────────────────────────

def tool_nong(audit: Iterable[dict], route: dict, k: int = 12, chi_ok: bool = True) -> list:
    """Tên fn của các tool được gọi nhiều nhất trong nhật ký hub, có mặt trong `route`.

    audit: bản ghi {conn_id, tool, ok}; route: {fn: {"conn": {"id":..}, "tool":..}}. Tool
    không còn trong route (kết nối đã gỡ) bị bỏ. Trả tối đa k tên, nhiều nhất trước."""
    dem: Counter = Counter()
    for r in audit or ():
        if chi_ok and not r.get("ok", True):
            continue
        dem[(str(r.get("conn_id") or ""), str(r.get("tool") or ""))] += 1
    if not dem:
        return []
    theo_khoa = {}
    for fn, ent in (route or {}).items():
        conn = (ent or {}).get("conn") or {}
        t = (ent or {}).get("tool")
        if conn.get("id") and t:
            theo_khoa[(str(conn["id"]), str(t))] = fn
    ra = []
    for (cid, t), _ in dem.most_common():
        fn = theo_khoa.get((cid, t))
        if fn and fn not in ra:
            ra.append(fn)
        if len(ra) >= max(0, int(k)):
            break
    return ra
