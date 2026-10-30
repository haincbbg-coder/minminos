"""Giữ ấm tiến trình engine giữa các tin nhắn của một cuộc chat (26.10.313).

VÌ SAO
Mỗi lượt chat Claude Code trước đây mở một tiến trình `claude` mới, nối lại mọi MCP rồi mới tới
lượt model. Javis đo ngày 28-29/10/2026: tin tiếp theo mất 8-14 giây trên tiến trình mới, chỉ
khoảng 2 giây trên tiến trình được giữ sống. Module này là cái "hồ" giữ các tiến trình đó, CÓ TRẦN:

- mỗi cuộc chat một chỗ (slot), kèm vân tay cấu hình lúc mở. Lượt sau có vân tay khác (đổi model,
  đổi mức quyền, sửa skill, đổi tài khoản...) thì đóng chỗ cũ và chạy lạnh như trước;
- trần RAM: một phần tư RAM trống (lấy giới hạn của container nếu có), tối đa 1.200 MB, hoặc
  MINMIN_WARM_BUDGET_MB (đặt 0 để tắt hẳn). Hồ đầy thì đẩy chỗ RẢNH lâu nhất ra, không bao giờ
  đụng chỗ đang chạy; không còn chỗ rảnh nào thì lượt đó chạy lạnh và đóng tiến trình như cũ;
- chỗ rảnh quá MINMIN_WARM_IDLE_S (mặc định 300 giây, bằng tuổi cache prompt của nhà cung cấp:
  quá mốc đó lượt sau đằng nào cũng nạp lại ngữ cảnh) thì đóng, nhưng giữ lại "công thức" mở lại
  trong 12 tiếng. Bố bắt đầu gõ là `hum_nong` dùng công thức đó mở sẵn tiến trình trước khi tin tới.

Chỉ lượt chat của chủ trên dashboard dùng hồ này. Việc nền và bot khách vẫn một tiến trình mỗi lần
chạy (chúng cần chạy song song, không cần nhanh vài giây). Trượt hồ luôn nghĩa là "chạy y như cũ".
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from typing import Dict, Optional

# MB ước tính cho một tiến trình đang ngủ (Javis đo: `claude` ~228 MB).
CAN_NANG_MB = {"claude": 300}
NGHI_MAC_DINH_S = 300.0
TRAN_RAM_MB = 1200
CONG_THUC_SONG_S = 12 * 3600.0     # công thức hâm nóng giữ 12 tiếng: nghỉ trưa, nghỉ tối vẫn mở ấm
CONG_THUC_TOI_DA = 200
NHIP_DON_S = 30.0


def _so_env(ten: str, mac_dinh: float) -> float:
    try:
        raw = os.getenv(ten)
        return float(raw) if raw not in (None, "") else mac_dinh
    except ValueError:
        return mac_dinh


def thoi_gian_nghi_s() -> float:
    return max(10.0, _so_env("MINMIN_WARM_IDLE_S", NGHI_MAC_DINH_S))


def _ram_trong_cgroup_mb() -> Optional[float]:
    """Phần còn lại dưới trần RAM của container (cgroup v2 rồi v1). None = không có trần."""
    for p_tran, p_dung in (("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
                           ("/sys/fs/cgroup/memory/memory.limit_in_bytes",
                            "/sys/fs/cgroup/memory/memory.usage_in_bytes")):
        try:
            with open(p_tran) as f:
                raw = f.read().strip()
            if raw == "max":
                return None
            tran = int(raw)
            if tran <= 0 or tran >= 1 << 60:   # v1 ghi "không giới hạn" bằng một số khổng lồ
                return None
            with open(p_dung) as f:
                dung = int(f.read().strip())
            return max(0.0, (tran - dung) / 2 ** 20)
        except (OSError, ValueError):
            continue
    return None


def ram_trong_mb() -> float:
    """RAM trống (MB). Không đọc được thì coi là 2048. Không bao giờ ném lỗi."""
    trong = None
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo") as f:
                for dong in f:
                    if dong.startswith("MemAvailable:"):
                        trong = int(dong.split()[1]) / 1024
                        break
            cg = _ram_trong_cgroup_mb()
            if cg is not None:
                trong = cg if trong is None else min(trong, cg)
        elif os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
                trong = ms.ullAvailPhys / 2 ** 20
    except Exception:  # noqa: BLE001 - đoán sai chỉ làm hồ to/nhỏ hơn, không được phá lượt chat
        trong = None
    return float(trong) if trong is not None else 2048.0


def ngan_sach_mb(dang_dung_mb: float = 0.0) -> float:
    """Hồ được giữ bao nhiêu MB. RAM trống đã trừ phần hồ đang giữ, nên cộng lại phần đó."""
    raw = os.getenv("MINMIN_WARM_BUDGET_MB")
    if raw not in (None, ""):
        return max(0.0, _so_env("MINMIN_WARM_BUDGET_MB", 0.0))
    return min(float(TRAN_RAM_MB), (ram_trong_mb() + dang_dung_mb) * 0.25)


class Tay:
    """Thứ engine gửi vào hồ (claude_giu_am.TayClaude). Lớp con trả lời `con_song` và `dong`."""
    loai = ""

    def con_song(self) -> bool:
        return False

    async def dong(self) -> None:
        return None


class Cho:
    __slots__ = ("khoa", "loai", "van_tay", "tay", "ban", "luc_dung", "loop", "cong_thuc", "so_luot")

    def __init__(self, khoa: str, loai: str, van_tay: str, tay: Tay, cong_thuc=None):
        self.khoa = khoa
        self.loai = loai
        self.van_tay = van_tay
        self.tay = tay
        self.ban = True
        self.luc_dung = time.monotonic()
        self.loop = asyncio.get_running_loop()
        self.cong_thuc = cong_thuc      # async () -> Tay: mở lại đúng tiến trình này sau (hâm nóng)
        self.so_luot = 0

    @property
    def can_nang(self) -> int:
        return CAN_NANG_MB.get(self.loai, 300)


class Ho:
    def __init__(self):
        self._cho: Dict[str, Cho] = {}
        self._cong_thuc: Dict[str, tuple] = {}     # khoa -> (loai, van_tay, cong_thuc, luc_luu)
        self._lock = threading.Lock()
        self._don: Optional[asyncio.Task] = None
        self._dang_hum: set = set()
        self._the_he: Dict[str, int] = {}          # mỗi lượt đi tìm chỗ của cuộc chat là tăng 1
        self._viec: set = set()
        self.dem = {"trung": 0, "truot": 0, "nhan": 0, "tu_choi": 0, "day_ra": 0, "het_han": 0,
                    "hum_nong": 0}

    # ---- phía lượt chat ----
    def lay(self, khoa: str, loai: str, van_tay: str) -> Optional[Cho]:
        """Chỗ ấm của cuộc chat nếu còn khớp, đánh dấu bận. None = chạy lạnh. Chỗ không còn khớp
        (cấu hình khác, tiến trình chết, vòng sự kiện khác) thì đóng."""
        if not khoa or ngan_sach_mb() <= 0:
            return None
        cu = None
        with self._lock:
            # Một lần hâm nóng bắt đầu TRƯỚC lượt này thì không được đáp xuống SAU nó.
            self._the_he[khoa] = self._the_he.get(khoa, 0) + 1
            cho = self._cho.get(khoa)
            if cho is not None and not cho.ban:
                try:
                    cung_loop = cho.loop is asyncio.get_running_loop()
                except RuntimeError:
                    cung_loop = False
                if cho.loai == loai and cho.van_tay == van_tay and cung_loop and cho.tay.con_song():
                    cho.ban = True
                    cho.so_luot += 1
                    self.dem["trung"] += 1
                    return cho
                cu = self._cho.pop(khoa)
            self.dem["truot"] += 1
        if cu is not None:
            self._dong_sau(cu)
        return None

    def nhin(self, khoa: str) -> Optional[Cho]:
        """Chỗ của cuộc chat, không đụng gì (để giải thích một lần trượt)."""
        with self._lock:
            return self._cho.get(khoa)

    def nhan(self, khoa: str, loai: str, van_tay: str, tay: Tay, cong_thuc=None, duoc_day: bool = True,
             the_he: Optional[int] = None) -> Optional[Cho]:
        """Một lượt lạnh vừa mở `tay`: giữ lại cho lượt sau nếu ngân sách cho phép (đẩy chỗ rảnh ra
        nếu cần). Trả chỗ (đang bận) hoặc None khi không vừa (bên gọi tự đóng như cũ).
        Hâm nóng truyền duoc_day=False và thế hệ lúc nó bắt đầu: không đẩy ai, không thay chỗ nào,
        và bỏ cuộc nếu trong lúc đó đã có lượt thật đi tìm chỗ của cuộc chat này."""
        if not khoa or not tay.con_song():
            return None
        nang = CAN_NANG_MB.get(loai, 300)
        bo = []
        with self._lock:
            cu = self._cho.get(khoa)
            if the_he is not None and (cu is not None or self._the_he.get(khoa, 0) != the_he):
                self.dem["tu_choi"] += 1
                return None
            if cu is not None and cu.ban:
                self.dem["tu_choi"] += 1
                return None        # cùng cuộc chat đang chạy chỗ khác: không bao giờ hai tiến trình ấm
            if cu is not None:
                bo.append(self._cho.pop(khoa))
            dung = sum(c.can_nang for c in self._cho.values())
            tran = ngan_sach_mb(dung)
            ranh = sorted((c for c in self._cho.values() if not c.ban), key=lambda c: c.luc_dung)
            while duoc_day and dung + nang > tran and ranh:
                c = ranh.pop(0)
                self._cho.pop(c.khoa, None)
                bo.append(c)
                dung -= c.can_nang
                self.dem["day_ra"] += 1
            if dung + nang > tran:
                self.dem["tu_choi"] += 1
                moi = None
            else:
                moi = Cho(khoa, loai, van_tay, tay, cong_thuc)
                self._cho[khoa] = moi
                self.dem["nhan"] += 1
        for c in bo:
            self._nho(c)
            self._dong_sau(c)
        if moi is not None:
            self._bat_don()
        return moi

    def tra(self, cho: Cho, giu: bool = True, van_tay: Optional[str] = None) -> None:
        """Hết lượt. giu=False (lỗi, tiến trình phải thoát) thì đóng. `van_tay` cập nhật chỗ đang
        là gì (mạch Claude đổi id theo từng lượt)."""
        if van_tay:
            cho.van_tay = van_tay
        cho.luc_dung = time.monotonic()
        with self._lock:
            cua_minh = self._cho.get(cho.khoa) is cho
            if giu and cua_minh and cho.tay.con_song():
                cho.ban = False
                return
            if cua_minh:
                self._cho.pop(cho.khoa, None)
        self._nho(cho)
        self._dong_sau(cho)

    # ---- hâm nóng ----
    def nho_cong_thuc(self, khoa: str, loai: str, van_tay: str, cong_thuc) -> None:
        if khoa and cong_thuc is not None:
            with self._lock:
                self._cong_thuc.pop(khoa, None)
                self._cong_thuc[khoa] = (loai, van_tay, cong_thuc, time.monotonic())
                while len(self._cong_thuc) > CONG_THUC_TOI_DA:   # thứ tự chèn = cũ nhất trước
                    self._cong_thuc.pop(next(iter(self._cong_thuc)))

    def _nho(self, cho: Cho) -> None:
        if cho.cong_thuc is not None:
            self.nho_cong_thuc(cho.khoa, cho.loai, cho.van_tay, cho.cong_thuc)

    def hum_nong(self, khoa: str) -> bool:
        """Bố bắt đầu gõ trong cuộc chat này: mở lại tiến trình gần nhất của nó ở nền nếu chưa có.
        True khi đã hẹn mở. Không bao giờ ném lỗi."""
        try:
            if not khoa or ngan_sach_mb() <= 0:
                return False
            with self._lock:
                if khoa in self._cho or khoa in self._dang_hum:
                    return False
                ct = self._cong_thuc.get(khoa)
                if ct is None or time.monotonic() - ct[3] > CONG_THUC_SONG_S:
                    self._cong_thuc.pop(khoa, None)
                    return False
                self._dang_hum.add(khoa)
                the_he = self._the_he.get(khoa, 0)
            self._giu_viec(asyncio.get_running_loop().create_task(self._hum(khoa, ct, the_he)))
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[giữ ấm] hâm nóng lỗi {type(e).__name__}: {e}", file=sys.stderr)
            return False

    async def _hum(self, khoa: str, ct: tuple, the_he: int) -> None:
        loai, van_tay, cong_thuc, _ = ct
        tay = None
        try:
            with self._lock:
                dung = sum(c.can_nang for c in self._cho.values())
            if dung + CAN_NANG_MB.get(loai, 300) > ngan_sach_mb(dung):
                return     # không còn chỗ mà không đẩy ai: một phỏng đoán không đáng giá thế
            tay = await cong_thuc()
            cho = self.nhan(khoa, loai, van_tay, tay, cong_thuc, duoc_day=False, the_he=the_he)
            if cho is None:
                await tay.dong()
                return
            self.dem["hum_nong"] += 1
            print(f"[giữ ấm] đã hâm nóng {loai} {khoa[:12]}", file=sys.stderr)
            self.tra(cho)
        except Exception as e:  # noqa: BLE001 - đoán hụt chỉ mất công thử
            print(f"[giữ ấm] hâm nóng {khoa[:12]} hỏng: {type(e).__name__}: {e}", file=sys.stderr)
            if tay is not None:
                try:
                    await tay.dong()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            with self._lock:
                self._dang_hum.discard(khoa)

    # ---- dọn dẹp ----
    def _giu_viec(self, task) -> None:
        """Giữ tham chiếu tới task cho tới khi xong (asyncio chỉ giữ tham chiếu yếu)."""
        self._viec.add(task)
        task.add_done_callback(self._viec.discard)

    def _dong_sau(self, cho: Cho) -> None:
        async def _dong():
            try:
                await cho.tay.dong()
            except Exception as e:  # noqa: BLE001
                print(f"[giữ ấm] đóng {cho.loai} lỗi {type(e).__name__}: {e}", file=sys.stderr)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop is cho.loop:
            self._giu_viec(loop.create_task(_dong()))
        elif cho.loop is not None and not cho.loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(_dong(), cho.loop)
            except RuntimeError:
                pass

    def _bat_don(self) -> None:
        if self._don is None or self._don.done():
            try:
                self._don = asyncio.get_running_loop().create_task(self._vong_don())
            except RuntimeError:
                self._don = None

    async def _vong_don(self) -> None:
        while True:
            await asyncio.sleep(NHIP_DON_S)
            self.don()
            with self._lock:
                if not self._cho:
                    return

    def don(self, bay_gio: Optional[float] = None) -> int:
        """Đóng chỗ rảnh quá hạn và chỗ đã chết. Trả số chỗ đã đóng."""
        bay_gio = time.monotonic() if bay_gio is None else bay_gio
        han = thoi_gian_nghi_s()
        ra = []
        with self._lock:
            for khoa, c in list(self._cho.items()):
                if c.ban:
                    continue
                if bay_gio - c.luc_dung > han or not c.tay.con_song():
                    ra.append(self._cho.pop(khoa))
                    self.dem["het_han"] += 1
        for c in ra:
            print(f"[giữ ấm] đóng {c.loai} {c.khoa[:12]} nghỉ lâu, sau {c.so_luot + 1} lượt", file=sys.stderr)
            self._nho(c)
            self._dong_sau(c)
        return len(ra)

    def bo_loai(self, loai: str) -> int:
        """Đóng mọi chỗ của một engine và quên công thức của nó (đăng nhập/đăng xuất đổi người
        chạy). Chỗ đang bận thì rút khỏi bảng để `tra()` của lượt đó tự đóng. Gọi từ thread nào cũng được."""
        with self._lock:
            ra = [c for c in self._cho.values() if c.loai == loai]
            for c in ra:
                self._cho.pop(c.khoa, None)
            for khoa in [k for k, r in self._cong_thuc.items() if r[0] == loai]:
                self._cong_thuc.pop(khoa, None)
        for c in ra:
            if not c.ban:
                self._dong_sau(c)
        return len(ra)

    def quen(self, khoa: str) -> None:
        """Cuộc chat bị xoá: đóng chỗ và bỏ công thức của nó."""
        with self._lock:
            c = self._cho.pop(khoa, None)
            self._cong_thuc.pop(khoa, None)
        if c is not None and not c.ban:
            self._dong_sau(c)

    async def dong_het(self) -> None:
        with self._lock:
            ds = list(self._cho.values())
            self._cho.clear()
            self._cong_thuc.clear()
        for c in ds:
            try:
                await c.tay.dong()
            except Exception:  # noqa: BLE001
                pass

    def trang_thai(self) -> dict:
        with self._lock:
            ds = [{"loai": c.loai, "ban": c.ban, "so_luot": c.so_luot,
                   "nghi_s": round(time.monotonic() - c.luc_dung, 1)} for c in self._cho.values()]
            dung = sum(c.can_nang for c in self._cho.values())
            so_cong_thuc = len(self._cong_thuc)
        return {"cho": ds, "dung_mb": dung, "ngan_sach_mb": round(ngan_sach_mb(dung)),
                "nghi_s": thoi_gian_nghi_s(), "cong_thuc": so_cong_thuc, **self.dem}


HO = Ho()
