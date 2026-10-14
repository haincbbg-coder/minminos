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


# ─────────────────────────── đo ngữ cảnh cố định (26.10.155) ───────────────────────────

_RE_KHOI = re.compile(r"^# === (.+?) ===.*$", re.MULTILINE)

# Tên ngắn cho thẻ Tiết kiệm. Khối không có trong bảng thì hiện nguyên tiêu đề.
_TEN_KHOI = {
    "BỘ NHỚ DÀI HẠN (nạp sẵn)": "bộ nhớ",
    "LỚP AGENTIC (vault đang làm việc)": "đường dẫn vault",
    "BÂY GIỜ": "đồng hồ",
    "NGÔN NGỮ": "ngôn ngữ",
    "KÊNH HỘI THOẠI HIỆN TẠI": "kênh",
}


def chia_khoi(prompt: str, ratio: float = 3.5) -> list:
    """Cắt system prompt THẬT thành các khối theo tiêu đề `# === X ===`, đo ký tự và token ước
    lượng của từng khối. Phần trước tiêu đề đầu tiên là CLAUDE.md.

    Vì sao: thẻ Tiết kiệm chỉ đo phần KẾT QUẢ TOOL (nén + đệm), mà báo cáo 311k token của chủ
    repo (13/10) chỉ bớt được 488 token ở đó. Phần nặng là ngữ cảnh cố định nạp lại MỖI BƯỚC;
    không nhìn thấy nó chia ra sao thì không biết cắt chỗ nào đáng."""
    s = prompt or ""
    ratio = max(1.0, float(ratio or 3.5))
    moc = [(m.start(), m.group(1).strip()) for m in _RE_KHOI.finditer(s)]
    ra = []

    def _them(ten, doan):
        n = len(doan)
        if n <= 0:
            return
        ra.append({"ten": ten, "ky_tu": n, "token_uoc": int(round(n / ratio))})

    dau = moc[0][0] if moc else len(s)
    _them("CLAUDE.md", s[:dau])
    for i, (vi, ten) in enumerate(moc):
        cuoi = moc[i + 1][0] if i + 1 < len(moc) else len(s)
        ten_ngan = _TEN_KHOI.get(ten)
        if ten_ngan is None:
            t = ten.lower()
            ten_ngan = ("skill" if "skill" in t else "năng lực" if "năng lực" in t
                        else "project" if "project" in t else ten)
        _them(ten_ngan, s[vi:cuoi])
    return ra


def cache_cua(usage: Any) -> int:
    """Số token ĐỌC LẠI TỪ CACHE trong một bản usage, bất kể nhà cung cấp:
    Anthropic `cache_read_input_tokens`; OpenAI/OpenRouter `prompt_tokens_details.cached_tokens`;
    Responses API `input_tokens_details.cached_tokens`. Không có thì 0."""
    if not isinstance(usage, dict):
        return 0
    v = usage.get("cache_read_input_tokens")
    if v is None:
        for k in ("prompt_tokens_details", "input_tokens_details"):
            d = usage.get(k)
            if isinstance(d, dict) and d.get("cached_tokens") is not None:
                v = d.get("cached_tokens")
                break
    try:
        return max(0, int(v or 0))
    except (TypeError, ValueError):
        return 0


# ─────────────────────────── tràn kết quả tool ra file (26.10.160) ───────────────────────────

import hashlib
import os
from pathlib import Path

# Kho file tràn: NGOÀI vault (không lẫn vào Second Brain, không bị git/đồng bộ kéo theo), trong
# STATE_DIR để mọi brain dùng chung một chỗ dọn. Chỉ javis_read_file của đường chat CHỦ đọc được.
def _state_dir() -> Path:
    try:
        from config import STATE_DIR
        return Path(STATE_DIR)
    except Exception:
        return Path(os.environ.get("JAVIS_STATE_DIR") or Path(__file__).parent)


KHO_TRAN = _state_dir() / "tool-cache"
TRAN_GIU_GIO = 24          # file quá tuổi này bị dọn ở lần ghi kế tiếp
TRAN_TOI_DA_FILE = 400


def _don_kho_tran(now: Optional[float] = None) -> None:
    now = time.time() if now is None else now
    try:
        fs = sorted(KHO_TRAN.glob("*.txt"), key=lambda f: f.stat().st_mtime)
    except OSError:
        return
    for f in fs:
        try:
            if now - f.stat().st_mtime > TRAN_GIU_GIO * 3600:
                f.unlink()
        except OSError:
            pass
    try:
        fs = sorted(KHO_TRAN.glob("*.txt"), key=lambda f: f.stat().st_mtime)
        for f in fs[: max(0, len(fs) - TRAN_TOI_DA_FILE)]:
            f.unlink()
    except OSError:
        pass


def ghi_tran(text: str, ten_tool: str = "tool") -> Path:
    """Ghi TOÀN BỘ kết quả tool ra file trong KHO_TRAN. Tên = giờ + tool + băm nội dung, nên
    cùng kết quả thì cùng file (không nhân đôi khi đệm trả lại)."""
    KHO_TRAN.mkdir(parents=True, exist_ok=True)
    _don_kho_tran()
    ten = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(ten_tool or "tool"))[:40].strip("-") or "tool"
    bam = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:10]
    f = KHO_TRAN / f"{time.strftime('%Y%m%d-%H%M%S')}-{ten}-{bam}.txt"
    if not f.exists():
        tmp = f.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, f)
    return f


def xem_truoc_tran(text: str, duong_dan, max_chars: int = 8000, head_ratio: float = 0.6) -> str:
    """Bản xem trước đầu/đuôi kèm chỉ dẫn đọc tiếp. Vì sao: trước đây não API chỉ thấy 8.000
    ký tự đầu đuôi và PHẦN GIỮA MẤT HẲN (60 trang đơn hàng -> sai số âm thầm). Giờ phần giữa
    nằm trong file, não đọc tiếp bằng javis_read_file(path, offset, limit) khi cần."""
    n = len(text)
    head_n = int(max_chars * head_ratio)
    tail_n = max_chars - head_n
    return (text[:head_n]
            + f"\n\n… [KẾT QUẢ DÀI {n:,} KÝ TỰ, ĐÃ LƯU TRỌN tại {duong_dan}. Ở đây chỉ là "
            f"{head_n:,} ký tự đầu và {tail_n:,} ký tự cuối. Cần phần giữa thì gọi "
            f"javis_read_file(path=\"{duong_dan}\", offset=<ký tự bắt đầu>, limit=<số ký tự, tối đa "
            f"30000>) theo từng đoạn; đếm hay cộng toàn bộ thì đọc đủ các đoạn, đừng đoán từ "
            f"phần đã thấy.] …\n\n"
            + text[-tail_n:])


def la_file_tran(p) -> bool:
    """Đường dẫn nằm trong kho file tràn? (để javis_read_file cho phép đọc)."""
    try:
        t = Path(p).resolve()
        k = KHO_TRAN.resolve()
        return t.is_file() and (k in t.parents)
    except (OSError, ValueError):
        return False


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
