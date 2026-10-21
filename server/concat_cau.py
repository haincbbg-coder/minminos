"""concat_cau.py - kho của Concat (26.10.196): máy có Concat, hàng đợi lời gọi công cụ, kết quả.

Vì sao có: Concat (trình dựng video, có MCP server sẵn trong app) chạy trên máy Windows ở nhà, còn
MinMin chạy trên VPS và không vào được mạng nhà. Nên máy nhà chạy cầu nối `apps/concat/cau`, tự kết
nối RA ngoài hỏi việc (long-poll), chuyển lời gọi vào `concat --mcp` rồi gửi kết quả lên.

Vòng đời một việc:
    cho -> (cầu nối nhận) -> dang -> xong | loi
    dang quá hạn (cho_giay + HET_GIO_THEM) không báo kết quả -> loi ("cầu nối im lặng")

Hai loại việc:
    goi      gọi một công cụ MCP của Concat: {cong_cu, tham_so, tep}
    lay_tep  đọc một tệp trên máy nhà (thường là video vừa xuất) đẩy lên, lưu vào bộ não

Tệp từ bộ não gửi xuống máy nhà: tham số chứa "minmin-tep:<số>", danh sách `tep` của việc giữ
đường dẫn thật trên VPS. Cầu nối tải về rồi thay bằng đường dẫn trên máy nhà.

Ghép máy giống Đội Social: dashboard tạo mã 6 số (sống 15 phút, lưu dạng băm), cầu nối đổi mã lấy
token (trả MỘT lần, lưu dạng băm), mọi gọi sau mang header x-minmin-may.

Thuần stdlib. Gọi `mo(thu_muc)` một lần lúc khởi động (main.py), test gọi với thư mục tạm.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Iterable, Optional

MA_SONG = 15 * 60
MAY_ONLINE = 120               # giây không nhịp thì coi máy tắt
HET_GIO_THEM = 120             # quá cho_giay + chừng này mà chưa có kết quả -> lỗi
CHO_GIAY_MAC_DINH = 120
CHO_GIAY_TRAN = 1800
GIU_VIEC_NGAY = 7
TIEN_TO_TEP = "minmin-tep:"
TIEN_TO_TOKEN = "mmc_"
KET_QUA_TOI_DA = 12 * 1024 * 1024   # JSON kết quả (kể cả ảnh base64)
TEP_LEN_TOI_DA = 1536 * 1024 * 1024

_goc: Optional[Path] = None
_goc_tep_cho_phep: list = []
_khoa = threading.RLock()
_doi = threading.Condition(_khoa)   # đánh thức long-poll khi có việc mới / có kết quả


def mo(thu_muc) -> None:
    global _goc
    _goc = Path(thu_muc)
    _goc.mkdir(parents=True, exist_ok=True)
    (_goc / "tep").mkdir(exist_ok=True)
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS ma_ghep(ma_bam TEXT PRIMARY KEY, het_han REAL);
        CREATE TABLE IF NOT EXISTS may(id TEXT PRIMARY KEY, ten TEXT, token_bam TEXT, tao_luc REAL,
            nhip_luc REAL, phien_ban TEXT, concat_ok INTEGER DEFAULT 0, loi_concat TEXT DEFAULT '',
            concat TEXT DEFAULT '{}', cong_cu TEXT DEFAULT '[]', thu_muc TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS viec(id INTEGER PRIMARY KEY AUTOINCREMENT, loai TEXT, cong_cu TEXT,
            tham_so TEXT, tep TEXT DEFAULT '[]', duong_dan TEXT DEFAULT '', cho_giay REAL,
            trang_thai TEXT, may_id TEXT DEFAULT '', ket_qua TEXT, loi TEXT DEFAULT '',
            tao_luc REAL, nhan_luc REAL, xong_luc REAL);
        CREATE INDEX IF NOT EXISTS viec_tt ON viec(trang_thai);
        """)


def dat_goc_tep(ds: Iterable) -> None:
    """Thư mục mà tệp gửi xuống máy nhà được phép lấy từ đó (các brain). Ngoài các gốc này bị từ
    chối, để một lệnh chat không lôi được tệp tuỳ ý trên VPS xuống máy khác."""
    global _goc_tep_cho_phep
    _goc_tep_cho_phep = [Path(p).resolve() for p in ds if p]


def thu_muc() -> Path:
    if _goc is None:
        raise RuntimeError("concat_cau chưa mo()")
    return _goc


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(str(thu_muc() / "concat.db"), timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    return c


def _bam(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


def _bay_gio() -> float:
    return time.time()


# ------------------------------------------------------------------ ghép máy

def tao_ma_ghep() -> str:
    ma = f"{secrets.randbelow(1_000_000):06d}"
    with _khoa, _db() as c:
        c.execute("DELETE FROM ma_ghep WHERE het_han < ?", (_bay_gio(),))
        c.execute("INSERT OR REPLACE INTO ma_ghep(ma_bam, het_han) VALUES(?, ?)",
                  (_bam(ma), _bay_gio() + MA_SONG))
    return ma


def ghep(ma: str, ten: str = "", phien_ban: str = "") -> dict:
    """Đổi mã 6 số lấy token máy. Mã dùng một lần. Raise ValueError nếu sai/hết hạn."""
    ma = "".join(ch for ch in str(ma or "") if ch.isdigit())
    if len(ma) != 6:
        raise ValueError("mã ghép phải đủ 6 số")
    with _khoa, _db() as c:
        r = c.execute("SELECT het_han FROM ma_ghep WHERE ma_bam=?", (_bam(ma),)).fetchone()
        if not r or r["het_han"] < _bay_gio():
            raise ValueError("mã ghép sai hoặc đã hết hạn - tạo mã mới ở trang Concat")
        c.execute("DELETE FROM ma_ghep WHERE ma_bam=?", (_bam(ma),))
        may_id = "c" + secrets.token_hex(4)
        token = TIEN_TO_TOKEN + secrets.token_urlsafe(32)
        ten = (str(ten or "").strip() or "Máy ở nhà")[:60]
        c.execute("INSERT INTO may(id, ten, token_bam, tao_luc, nhip_luc, phien_ban) VALUES(?,?,?,?,?,?)",
                  (may_id, ten, _bam(token), _bay_gio(), _bay_gio(), str(phien_ban or "")[:20]))
    return {"may_id": may_id, "token": token, "ten": ten}


def may_theo_token(token: str) -> Optional[dict]:
    token = str(token or "")
    if not token.startswith(TIEN_TO_TOKEN):
        return None
    with _db() as c:
        rows = c.execute("SELECT id, token_bam FROM may").fetchall()
    b = _bam(token)
    for r in rows:      # so thời gian hằng
        if hmac.compare_digest(r["token_bam"], b):
            return lay_may(r["id"])
    return None


def lay_may(may_id: str) -> Optional[dict]:
    with _db() as c:
        r = c.execute("SELECT * FROM may WHERE id=?", (may_id,)).fetchone()
    return _may(r) if r else None


def _may(r) -> dict:
    d = dict(r)
    d.pop("token_bam", None)
    d["online"] = (_bay_gio() - (d.get("nhip_luc") or 0)) < MAY_ONLINE
    d["concat_ok"] = bool(d.get("concat_ok"))
    for k, mac in (("concat", {}), ("cong_cu", [])):
        try:
            d[k] = json.loads(d.get(k) or "null") or mac
        except Exception:
            d[k] = mac
    return d


def go_may(may_id: str) -> bool:
    with _khoa, _db() as c:
        n = c.execute("DELETE FROM may WHERE id=?", (may_id,)).rowcount
        c.execute("UPDATE viec SET trang_thai='loi', loi='máy đã bị gỡ', xong_luc=? "
                  "WHERE may_id=? AND trang_thai='dang'", (_bay_gio(), may_id))
        _doi.notify_all()
    return n > 0


def nhip(may_id: str, concat_ok=None, loi_concat: str = "", concat=None, cong_cu=None,
         thu_muc_lam_viec: str = "", phien_ban: str = "") -> None:
    cc_json = None
    if isinstance(cong_cu, list):
        gon = []
        for t in cong_cu[:200]:
            if isinstance(t, dict) and t.get("name"):
                gon.append({"name": str(t["name"])[:80], "description": str(t.get("description") or "")[:1500],
                            "inputSchema": t.get("inputSchema") if isinstance(t.get("inputSchema"), dict) else {}})
        cc_json = json.dumps(gon, ensure_ascii=False)
        if len(cc_json) > 600_000:
            cc_json = None
    with _khoa, _db() as c:
        c.execute("UPDATE may SET nhip_luc=?, concat_ok=COALESCE(?, concat_ok), loi_concat=?, "
                  "concat=COALESCE(?, concat), cong_cu=COALESCE(?, cong_cu), "
                  "thu_muc=COALESCE(NULLIF(?, ''), thu_muc), phien_ban=COALESCE(NULLIF(?, ''), phien_ban) "
                  "WHERE id=?",
                  (_bay_gio(), None if concat_ok is None else int(bool(concat_ok)), str(loi_concat or "")[:300],
                   json.dumps(concat, ensure_ascii=False)[:2000] if isinstance(concat, dict) else None,
                   cc_json, str(thu_muc_lam_viec or "")[:400], str(phien_ban or "")[:20], may_id))
        _don_viec_treo(c)


def ds_may() -> list:
    with _db() as c:
        return [_may(r) for r in c.execute("SELECT * FROM may ORDER BY tao_luc").fetchall()]


def may_chinh() -> Optional[dict]:
    """Máy sẽ nhận việc: máy online có nhịp gần nhất (thường chỉ có một)."""
    ds = [m for m in ds_may() if m["online"]]
    if not ds:
        return None
    return max(ds, key=lambda m: m.get("nhip_luc") or 0)


def trang_thai() -> dict:
    ds = ds_may()
    m = may_chinh()
    return {"may": ds, "da_ghep": bool(ds), "online": bool(m),
            "concat_ok": bool(m and m["concat_ok"]),
            "may_chinh": m["id"] if m else ""}


# ------------------------------------------------------------------ tệp gửi xuống

def _kiem_tep(duong: str, goc_them=None) -> Path:
    p = Path(str(duong or "")).expanduser()
    try:
        that = p.resolve()
    except Exception:
        raise ValueError(f"đường dẫn tệp không hợp lệ: {duong}")
    if not that.is_file():
        raise ValueError(f"không thấy tệp {duong}")
    goc = list(_goc_tep_cho_phep)
    if goc_them:
        goc.append(Path(goc_them).resolve())
    if not any(_trong(that, g) for g in goc):
        raise ValueError(f"tệp {that.name} nằm ngoài bộ não, không gửi xuống máy nhà")
    return that


def _trong(p: Path, goc: Path) -> bool:
    try:
        p.relative_to(goc)
        return True
    except ValueError:
        return False


def gom_tep(tham_so, giai_duong=None, goc_them=None):
    """Thay mọi chuỗi 'minmin:<đường trong bộ não>' trong tham số bằng 'minmin-tep:<số>'.
    `giai_duong(rel) -> Path` đổi đường tương đối trong brain thành đường thật (plugin truyền vào).
    Trả (tham_so_moi, danh_sach_tep)."""
    tep: list = []
    so_theo_duong: dict = {}

    def doi(v):
        if isinstance(v, str) and v.startswith("minmin:"):
            rel = v[len("minmin:"):].strip()
            that = _kiem_tep(giai_duong(rel) if giai_duong else rel, goc_them)
            k = str(that)
            if k not in so_theo_duong:
                so_theo_duong[k] = len(tep)
                tep.append({"duong": k, "ten": that.name, "co": that.stat().st_size,
                            "goc": str(goc_them or "")})
            return f"{TIEN_TO_TEP}{so_theo_duong[k]}"
        if isinstance(v, list):
            return [doi(x) for x in v]
        if isinstance(v, dict):
            return {k2: doi(x) for k2, x in v.items()}
        return v

    return doi(tham_so if tham_so is not None else {}), tep


def duong_tep(vid: int, so: int, may_id: str) -> Optional[Path]:
    v = lay_viec(vid)
    if not v or v.get("may_id") != may_id or not 0 <= so < len(v["tep"]):
        return None
    try:
        return _kiem_tep(v["tep"][so]["duong"], v["tep"][so].get("goc") or None)
    except ValueError:
        return None


# ------------------------------------------------------------------ hàng đợi việc

def tao_viec(*, loai: str = "goi", cong_cu: str = "", tham_so=None, tep=None, duong_dan: str = "",
             cho_giay=None) -> dict:
    if loai not in ("goi", "lay_tep"):
        raise ValueError("loại việc không hợp lệ")
    if loai == "goi" and not str(cong_cu or "").strip():
        raise ValueError("thiếu tên công cụ Concat")
    try:
        cg = float(cho_giay if cho_giay is not None else CHO_GIAY_MAC_DINH)
    except (TypeError, ValueError):
        cg = CHO_GIAY_MAC_DINH
    cg = max(10.0, min(CHO_GIAY_TRAN, cg))
    with _khoa, _db() as c:
        c.execute("DELETE FROM viec WHERE tao_luc < ? AND trang_thai IN ('xong','loi')",
                  (_bay_gio() - GIU_VIEC_NGAY * 86400,))
        cur = c.execute("INSERT INTO viec(loai, cong_cu, tham_so, tep, duong_dan, cho_giay, trang_thai, tao_luc) "
                        "VALUES(?,?,?,?,?,?, 'cho', ?)",
                        (loai, str(cong_cu or "")[:80], json.dumps(tham_so or {}, ensure_ascii=False),
                         json.dumps(tep or [], ensure_ascii=False), str(duong_dan or "")[:1000], cg, _bay_gio()))
        vid = cur.lastrowid
        _doi.notify_all()
    return lay_viec(vid)


def _dong(r) -> dict:
    d = dict(r)
    for k, mac in (("tham_so", {}), ("tep", []), ("ket_qua", None)):
        try:
            d[k] = json.loads(d.get(k) or "null")
        except Exception:
            d[k] = None
        if d[k] is None:
            d[k] = mac
    return d


def lay_viec(vid) -> Optional[dict]:
    with _db() as c:
        r = c.execute("SELECT * FROM viec WHERE id=?", (int(vid),)).fetchone()
    return _dong(r) if r else None


def ds_viec(limit: int = 30) -> list:
    with _db() as c:
        rows = c.execute("SELECT * FROM viec ORDER BY id DESC LIMIT ?", (max(1, min(200, int(limit))),)).fetchall()
    out = []
    for r in rows:
        d = _dong(r)
        d.pop("ket_qua", None)          # danh sách không kèm kết quả nặng (ảnh base64)
        out.append(d)
    return out


def _don_viec_treo(c) -> None:
    now = _bay_gio()
    c.execute("UPDATE viec SET trang_thai='loi', loi='cầu nối im lặng quá lâu (máy tắt hoặc Concat treo)', "
              "xong_luc=? WHERE trang_thai='dang' AND nhan_luc + cho_giay + ? < ?", (now, HET_GIO_THEM, now))
    c.execute("UPDATE viec SET trang_thai='loi', loi='máy ở nhà không nhận việc (tắt máy hoặc chưa chạy cầu nối)', "
              "xong_luc=? WHERE trang_thai='cho' AND tao_luc + cho_giay + ? < ?", (now, HET_GIO_THEM, now))


def _phat_viec(c, may_id: str) -> Optional[dict]:
    r = c.execute("SELECT * FROM viec WHERE trang_thai='cho' ORDER BY id LIMIT 1").fetchone()
    if not r:
        return None
    c.execute("UPDATE viec SET trang_thai='dang', may_id=?, nhan_luc=? WHERE id=?", (may_id, _bay_gio(), r["id"]))
    d = _dong(r)
    tep = [{"ten": t.get("ten"), "co": t.get("co")} for t in d["tep"]]   # không lộ đường trên VPS
    return {"id": d["id"], "loai": d["loai"], "cong_cu": d["cong_cu"], "tham_so": d["tham_so"],
            "tep": tep, "duong_dan": d["duong_dan"], "cho_giay": d["cho_giay"]}


def nhan_viec(may_id: str, cho: float = 0) -> Optional[dict]:
    """Long-poll: trả việc kế tiếp, hoặc đợi tối đa `cho` giây cho có việc."""
    het = _bay_gio() + max(0.0, min(30.0, float(cho or 0)))
    with _khoa:
        while True:
            with _db() as c:
                _don_viec_treo(c)
                v = _phat_viec(c, may_id)
                c.execute("UPDATE may SET nhip_luc=? WHERE id=?", (_bay_gio(), may_id))
            if v or _bay_gio() >= het:
                return v
            _doi.wait(timeout=max(0.1, het - _bay_gio()))


def ghi_ket_qua(vid, may_id: str, ok: bool, ket_qua=None, loi: str = "") -> bool:
    raw = json.dumps(ket_qua, ensure_ascii=False) if ket_qua is not None else "null"
    if len(raw) > KET_QUA_TOI_DA:
        raw, ok, loi = "null", False, "kết quả quá lớn (trên 12 MB)"
    with _khoa, _db() as c:
        n = c.execute("UPDATE viec SET trang_thai=?, ket_qua=?, loi=?, xong_luc=? "
                      "WHERE id=? AND may_id=? AND trang_thai='dang'",
                      ("xong" if ok else "loi", raw, str(loi or "")[:1000], _bay_gio(), int(vid), may_id)).rowcount
        _doi.notify_all()
    return n > 0


def cho_ket_qua(vid, toi_da: float) -> dict:
    """Đợi việc xong hoặc hết `toi_da` giây. Trả bản ghi việc (trang_thai có thể vẫn cho/dang)."""
    het = _bay_gio() + max(0.0, float(toi_da))
    with _khoa:
        while True:
            v = lay_viec(vid)
            if not v or v["trang_thai"] in ("xong", "loi") or _bay_gio() >= het:
                return v or {}
            _doi.wait(timeout=min(5.0, max(0.1, het - _bay_gio())))
            with _db() as c:
                _don_viec_treo(c)


def luu_tep_len(vid, may_id: str, ten: str, du_lieu: bytes, dich_thu_muc: Path) -> Path:
    """Lưu tệp cầu nối đẩy lên (việc lay_tep) vào `dich_thu_muc` (thư mục trong bộ não)."""
    v = lay_viec(vid)
    if not v or v.get("may_id") != may_id or v["loai"] != "lay_tep" or v["trang_thai"] != "dang":
        raise ValueError("việc không chờ tệp")
    if len(du_lieu) > TEP_LEN_TOI_DA:
        raise ValueError("tệp quá lớn")
    ten = "".join(ch for ch in Path(str(ten or "tep").replace("\\", "/")).name
                  if ch not in '<>:"/\\|?*' and ord(ch) >= 32)[:120] or "tep"
    dich_thu_muc.mkdir(parents=True, exist_ok=True)
    dich = dich_thu_muc / ten
    if dich.exists():
        dich = dich_thu_muc / f"{dich.stem}-{vid}{dich.suffix}"
    dich.write_bytes(du_lieu)
    return dich
