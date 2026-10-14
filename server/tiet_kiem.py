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


# ─────────────────────────── dọn kết quả tool cũ trong lượt (26.10.162) ───────────────────────────

DAU_DA_DON = "[Kết quả tool cũ đã dọn"
_RE_FILE_TRAN = re.compile(r"ĐÃ LƯU TRỌN tại (\S+?\.txt)")


def nguong_don_ky_tu(default: int = 240_000) -> int:
    """settings mcp.don_ngu_canh_ky_tu: tổng ký tự của hội thoại mà vượt qua thì bắt đầu dọn
    kết quả tool cũ. 0 = tắt. Mặc định 240.000 ký tự (~60-70k token), đủ xa trần 128k-200k
    của phần đông model để còn chỗ cho câu trả lời."""
    try:
        from config import read_settings
        v = (read_settings().get("mcp") or {}).get("don_ngu_canh_ky_tu")
        return max(0, int(v)) if v is not None else default
    except Exception:
        return default


def _dau_don(ten_tool: str, n: int, cu: str) -> str:
    m = _RE_FILE_TRAN.search(cu or "")
    duong = f", bản đầy đủ còn ở file {m.group(1)} (đọc bằng javis_read_file)" if m else ", gọi lại tool nếu cần"
    return f"{DAU_DA_DON}: {ten_tool or 'tool'}, {n:,} ký tự{duong}]"


def don_ket_qua_cu(muc: list, lay, dat, ten=None, *, giu_cuoi: int = 4,
                   nguong: Optional[int] = None, muc_tieu: float = 0.6) -> int:
    """Dọn kết quả tool CŨ trong một hội thoại đang chạy vòng tool, mượn cách ContextCompressor
    của Hermes: khi tổng ký tự vượt `nguong`, thay nội dung các kết quả tool cũ nhất (trừ
    `giu_cuoi` kết quả gần nhất) bằng một dòng đánh dấu, cho tới khi tổng xuống dưới
    nguong*muc_tieu. KHÔNG đụng lời người dùng và lời model; dữ liệu lớn đã có bản đầy đủ ở kho
    file tràn nên dòng đánh dấu dẫn thẳng tới đó.

    Vì sao: mỗi vòng tool gửi lại TOÀN BỘ hội thoại. Báo cáo 60 trang đơn hàng thì trang 1 vẫn
    đi theo tới vòng 60, trong khi model đã dùng xong nó từ vòng 2. Đây là phần nặng nhất của
    một lượt nhiều bước, nặng hơn cả ngữ cảnh cố định.

    `muc`: danh sách message/item; `lay(x)` -> nội dung kết quả tool (str) hoặc None nếu x không
    phải kết quả tool; `dat(x, s)` ghi nội dung mới; `ten(x)` -> tên tool (tuỳ chọn).
    Trả số kết quả đã dọn."""
    nguong = nguong_don_ky_tu() if nguong is None else int(nguong)
    if nguong <= 0 or not muc:
        return 0

    def _tong():
        t = 0
        for x in muc:
            try:
                t += len(json.dumps(x, ensure_ascii=False, default=str))
            except (TypeError, ValueError):
                t += len(str(x))
        return t

    tong = _tong()
    if tong <= nguong:
        return 0
    vi_tri = [i for i, x in enumerate(muc) if isinstance(lay(x), str)]
    ung_vien = vi_tri[: max(0, len(vi_tri) - max(0, int(giu_cuoi)))]
    dich = nguong * max(0.1, min(0.95, float(muc_tieu)))
    da = 0
    for i in ung_vien:
        x = muc[i]
        cu = lay(x) or ""
        if cu.startswith(DAU_DA_DON) or len(cu) < 200:
            continue
        moi = _dau_don(ten(x) if ten else "", len(cu), cu)
        dat(x, moi)
        tong -= (len(cu) - len(moi))
        da += 1
        if tong <= dich:
            break
    return da


# Ba bộ lay/dat cho ba định dạng hội thoại của engine API.
def don_openai(msgs: list, **kw) -> int:
    return don_ket_qua_cu(
        msgs, lambda m: m.get("content") if isinstance(m, dict) and m.get("role") == "tool" else None,
        lambda m, s: m.__setitem__("content", s),
        lambda m: str(m.get("name") or m.get("tool_call_id") or ""), **kw)


def don_responses(items: list, **kw) -> int:
    return don_ket_qua_cu(
        items, lambda m: m.get("output") if isinstance(m, dict) and m.get("type") == "function_call_output" else None,
        lambda m, s: m.__setitem__("output", s),
        lambda m: str(m.get("name") or m.get("call_id") or ""), **kw)


def don_anthropic(conv: list, **kw) -> int:
    """Anthropic gói nhiều tool_result trong MỘT message user; dọn từng block."""
    blocks = []
    for m in conv:
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result" and isinstance(b.get("content"), str):
                    blocks.append(b)
    if not blocks:
        return 0
    # tổng ký tự tính trên CẢ hội thoại, nhưng ứng viên là từng block
    nguong = kw.pop("nguong", None)
    nguong = nguong_don_ky_tu() if nguong is None else int(nguong)
    if nguong <= 0:
        return 0
    try:
        tong = len(json.dumps(conv, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        tong = sum(len(str(m)) for m in conv)
    if tong <= nguong:
        return 0
    giu_cuoi = int(kw.get("giu_cuoi", 4))
    dich = nguong * float(kw.get("muc_tieu", 0.6))
    da = 0
    for b in blocks[: max(0, len(blocks) - giu_cuoi)]:
        cu = b.get("content") or ""
        if cu.startswith(DAU_DA_DON) or len(cu) < 200:
            continue
        moi = _dau_don(str(b.get("tool_use_id") or ""), len(cu), cu)
        b["content"] = moi
        tong -= (len(cu) - len(moi))
        da += 1
        if tong <= dich:
            break
    return da


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
