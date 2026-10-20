"""doi_social.py - kho của Đội Social (26.10.185): máy ở nhà, nick, hàng đợi việc, kết quả.

Vì sao có: MinMin chạy trên VPS, còn trình duyệt có nick thật (GPM Login, MultiProfile) nằm trên
máy Windows ở nhà. VPS không vào được mạng nhà, nên máy nhà chạy MinMin Worker, tự kết nối RA
ngoài để hỏi việc (long-poll), làm xong gửi kết quả + ảnh chụp lên. Không mở cổng router.

Vòng đời một việc:
    cho_duyet  -> (chủ bấm Duyệt) -> cho_chay -> (worker nhận) -> dang_chay -> xong | loi
    cho_duyet  -> (chủ bấm Bỏ)    -> bo
    dang_chay quá HET_GIO_CHAY giây không báo kết quả -> loi ("worker im lặng")

Ghép máy: dashboard tạo mã 6 số (sống 15 phút, lưu dạng băm). Worker gửi mã -> nhận token máy
(chỉ trả MỘT lần, lưu dạng băm). Mọi gọi sau của worker mang token trong header x-minmin-may.

Giới hạn nick (bản đầu, cứng ở kho, không phụ thuộc prompt): mỗi nick tối đa N bài/ngày theo
từng kỹ năng và nghỉ ít nhất M phút giữa hai lượt. Mặc định 5 bài/ngày, 20 phút.

Thuần stdlib. Gọi `mo(thu_muc)` một lần lúc khởi động (main.py), test gọi với thư mục tạm.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

KY_NANG = {
    # id kỹ năng -> nhãn người đọc. Worker cũng giữ bảng tương ứng; kỹ năng lạ bị từ chối.
    "fb_dang_bai": "Đăng bài Facebook",
}
TRANG_THAI = ("cho_duyet", "cho_chay", "dang_chay", "xong", "loi", "bo")
DUOI_TEP = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".m4v", ".webm"}
TEP_TOI_DA = 200 * 1024 * 1024          # 200MB mỗi tệp
SO_TEP_TOI_DA = 10                       # Facebook nhận tối đa ~10 ảnh/video một bài đơn giản
CHU_TOI_DA = 8000
MA_SONG = 15 * 60
HET_GIO_CHAY = 20 * 60                   # một lượt đăng bài thật hiếm khi quá 20 phút
MAY_ONLINE = 90                          # worker nhịp mỗi ~30s; 90s không thấy = ngoại tuyến
GIOI_HAN_MAC_DINH = {"bai_moi_ngay": 5, "nghi_phut": 20}

_khoa = threading.RLock()
_goc: Optional[Path] = None
_goc_tep_cho_phep: list = []


# ------------------------------------------------------------------ khởi tạo

def mo(thu_muc) -> None:
    """Mở (tạo nếu chưa có) kho trong `thu_muc`. Gọi lại với thư mục khác = đổi kho (test)."""
    global _goc
    with _khoa:
        _goc = Path(thu_muc)
        (_goc / "anh").mkdir(parents=True, exist_ok=True)
        (_goc / "tep").mkdir(parents=True, exist_ok=True)
        with _db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS ma_ghep(ma_bam TEXT PRIMARY KEY, het_han REAL);
            CREATE TABLE IF NOT EXISTS may(
                id TEXT PRIMARY KEY, ten TEXT, token_bam TEXT UNIQUE, driver TEXT,
                tao_luc REAL, nhip_luc REAL, phien_ban TEXT, driver_ok INTEGER DEFAULT 0,
                loi_driver TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS nick(
                may_id TEXT, id TEXT, ten TEXT, nhom TEXT, trinh_duyet TEXT, co_proxy INTEGER,
                cap_nhat REAL, PRIMARY KEY(may_id, id));
            CREATE TABLE IF NOT EXISTS viec(
                id INTEGER PRIMARY KEY AUTOINCREMENT, ky_nang TEXT, may_id TEXT, nick_id TEXT,
                nick_ten TEXT, tham_so TEXT, trang_thai TEXT, tao_luc REAL, duyet_luc REAL,
                bat_dau REAL, xong_luc REAL, thong_diep TEXT DEFAULT '', buoc TEXT DEFAULT '[]',
                co_anh INTEGER DEFAULT 0, chat_id TEXT DEFAULT '', nguon TEXT DEFAULT '',
                ai_tao TEXT DEFAULT '');
            CREATE INDEX IF NOT EXISTS viec_tt ON viec(trang_thai, may_id);
            CREATE TABLE IF NOT EXISTS cai_dat(k TEXT PRIMARY KEY, v TEXT);
            """)


def dat_goc_tep(ds: Iterable) -> None:
    """Thư mục mà tệp đính kèm được phép lấy từ đó (thư mục tải về của Telegram, các brain).
    Đường dẫn ngoài các gốc này bị từ chối, để một lệnh chat không lôi được tệp tuỳ ý trên VPS."""
    global _goc_tep_cho_phep
    _goc_tep_cho_phep = [Path(p).resolve() for p in ds if p]


def _db() -> sqlite3.Connection:
    if _goc is None:
        raise RuntimeError("doi_social chưa mo()")
    c = sqlite3.connect(str(_goc / "doi-social.db"), timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    return c


def _bam(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


def _bay_gio() -> float:
    return time.time()


# ------------------------------------------------------------------ cài đặt / giới hạn

def gioi_han() -> dict:
    with _db() as c:
        r = c.execute("SELECT v FROM cai_dat WHERE k='gioi_han'").fetchone()
    d = dict(GIOI_HAN_MAC_DINH)
    if r:
        try:
            d.update({k: int(v) for k, v in json.loads(r["v"]).items() if k in d})
        except Exception:
            pass
    return d


def dat_gioi_han(bai_moi_ngay=None, nghi_phut=None) -> dict:
    d = gioi_han()
    if bai_moi_ngay is not None:
        d["bai_moi_ngay"] = max(1, min(50, int(bai_moi_ngay)))
    if nghi_phut is not None:
        d["nghi_phut"] = max(0, min(24 * 60, int(nghi_phut)))
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO cai_dat(k, v) VALUES('gioi_han', ?)", (json.dumps(d),))
    return d


# ------------------------------------------------------------------ ghép máy

def tao_ma_ghep() -> str:
    ma = f"{secrets.randbelow(1_000_000):06d}"
    with _khoa, _db() as c:
        c.execute("DELETE FROM ma_ghep WHERE het_han < ?", (_bay_gio(),))
        c.execute("INSERT OR REPLACE INTO ma_ghep(ma_bam, het_han) VALUES(?, ?)",
                  (_bam(ma), _bay_gio() + MA_SONG))
    return ma


def ghep(ma: str, ten: str = "", driver: str = "gpm", phien_ban: str = "") -> dict:
    """Đổi mã 6 số lấy token máy. Mã dùng một lần. Raise ValueError nếu sai/hết hạn."""
    ma = "".join(ch for ch in str(ma or "") if ch.isdigit())
    if len(ma) != 6:
        raise ValueError("mã ghép phải đủ 6 số")
    with _khoa, _db() as c:
        r = c.execute("SELECT het_han FROM ma_ghep WHERE ma_bam=?", (_bam(ma),)).fetchone()
        if not r or r["het_han"] < _bay_gio():
            raise ValueError("mã ghép sai hoặc đã hết hạn - tạo mã mới ở trang Đội Social")
        c.execute("DELETE FROM ma_ghep WHERE ma_bam=?", (_bam(ma),))
        may_id = "m" + secrets.token_hex(4)
        token = "mmw_" + secrets.token_urlsafe(32)
        ten = (str(ten or "").strip() or "Máy ở nhà")[:60]
        c.execute("INSERT INTO may(id, ten, token_bam, driver, tao_luc, nhip_luc, phien_ban) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (may_id, ten, _bam(token), (driver or "gpm")[:20], _bay_gio(), _bay_gio(),
                   str(phien_ban or "")[:20]))
    return {"may_id": may_id, "token": token, "ten": ten}


def may_theo_token(token: str) -> Optional[dict]:
    token = str(token or "")
    if not token.startswith("mmw_"):
        return None
    with _db() as c:
        rows = c.execute("SELECT * FROM may").fetchall()
    b = _bam(token)
    for r in rows:      # so thời gian hằng, không dùng WHERE token_bam=? để khỏi lộ qua thời gian
        if hmac.compare_digest(r["token_bam"], b):
            return dict(r)
    return None


def go_may(may_id: str) -> bool:
    with _khoa, _db() as c:
        n = c.execute("DELETE FROM may WHERE id=?", (may_id,)).rowcount
        c.execute("DELETE FROM nick WHERE may_id=?", (may_id,))
        c.execute("UPDATE viec SET trang_thai='loi', thong_diep='máy đã bị gỡ', xong_luc=? "
                  "WHERE may_id=? AND trang_thai IN ('cho_duyet','cho_chay','dang_chay')",
                  (_bay_gio(), may_id))
    return n > 0


def nhip(may_id: str, nick_ds=None, driver_ok=None, loi_driver: str = "", phien_ban: str = "") -> None:
    """Worker báo còn sống, kèm danh sách profile đọc từ GPM (nếu có)."""
    now = _bay_gio()
    with _khoa, _db() as c:
        c.execute("UPDATE may SET nhip_luc=?, driver_ok=COALESCE(?, driver_ok), loi_driver=?, "
                  "phien_ban=COALESCE(NULLIF(?, ''), phien_ban) WHERE id=?",
                  (now, None if driver_ok is None else int(bool(driver_ok)), str(loi_driver or "")[:300],
                   str(phien_ban or "")[:20], may_id))
        if nick_ds is not None:
            c.execute("DELETE FROM nick WHERE may_id=?", (may_id,))
            for n in list(nick_ds)[:2000]:
                if not isinstance(n, dict) or not n.get("id"):
                    continue
                c.execute("INSERT OR REPLACE INTO nick VALUES(?,?,?,?,?,?,?)",
                          (may_id, str(n["id"])[:80], str(n.get("ten") or n.get("name") or "")[:200],
                           str(n.get("nhom") or "")[:120], str(n.get("trinh_duyet") or "")[:20],
                           int(bool(n.get("co_proxy"))), now))
        _don_viec_treo(c)


def ds_may() -> list:
    now = _bay_gio()
    with _db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM may ORDER BY tao_luc").fetchall()]
        for r in rows:
            r.pop("token_bam", None)
            r["online"] = (now - (r.get("nhip_luc") or 0)) < MAY_ONLINE
            r["so_nick"] = c.execute("SELECT COUNT(*) FROM nick WHERE may_id=?", (r["id"],)).fetchone()[0]
    return rows


def ds_nick(may_id: str = "") -> list:
    with _db() as c:
        q = "SELECT n.*, m.ten AS may_ten FROM nick n JOIN may m ON m.id=n.may_id"
        args = ()
        if may_id:
            q += " WHERE n.may_id=?"
            args = (may_id,)
        return [dict(r) for r in c.execute(q + " ORDER BY n.ten", args).fetchall()]


def _bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").replace("đ", "d")
    return " ".join(s.split())


def tim_nick(goi: str) -> list:
    """Tìm nick theo tên người gõ (không dấu, không phân biệt hoa thường). Khớp đúng tên trước,
    rồi tới chứa chuỗi. Trả danh sách để bên gọi hỏi lại khi có nhiều kết quả."""
    g = _bo_dau(goi)
    if not g:
        return []
    ds = ds_nick()
    dung = [n for n in ds if _bo_dau(n["ten"]) == g or n["id"] == goi]
    if dung:
        return dung
    return [n for n in ds if g in _bo_dau(n["ten"])]


# ------------------------------------------------------------------ việc

def _chep_tep(viec_id: int, tep: Iterable) -> list:
    """Chép tệp đính kèm vào kho của việc. Chỉ nhận tệp ảnh/video nằm trong các gốc cho phép."""
    ra = []
    dich = _goc / "tep" / str(viec_id)
    for i, p in enumerate(list(tep or [])[:SO_TEP_TOI_DA]):
        src = Path(str(p)).expanduser()
        try:
            src = src.resolve(strict=True)
        except Exception:
            raise ValueError(f"không thấy tệp: {p}")
        if src.suffix.lower() not in DUOI_TEP:
            raise ValueError(f"chỉ nhận ảnh/video, không nhận {src.suffix or 'tệp không đuôi'}: {src.name}")
        if not any(src == g or g in src.parents for g in _goc_tep_cho_phep):
            raise ValueError(f"tệp nằm ngoài thư mục được phép: {src.name}")
        if src.stat().st_size > TEP_TOI_DA:
            raise ValueError(f"tệp quá lớn (tối đa 200MB): {src.name}")
        dich.mkdir(parents=True, exist_ok=True)
        d = dich / f"{i:02d}{src.suffix.lower()}"
        shutil.copyfile(str(src), str(d))
        ra.append({"ten": src.name, "luu": d.name, "co": d.stat().st_size})
    return ra


def _dem_hom_nay(c, nick_id: str, ky_nang: str) -> int:
    t = time.localtime()
    dau_ngay = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    return c.execute("SELECT COUNT(*) FROM viec WHERE nick_id=? AND ky_nang=? AND tao_luc>=? "
                     "AND trang_thai NOT IN ('bo','loi')", (nick_id, ky_nang, dau_ngay)).fetchone()[0]


def tao_viec(*, ky_nang: str, nick: str, noi_dung: str = "", tep=None, noi_dang: str = "",
             can_duyet: bool = True, chat_id: str = "", nguon: str = "", ai_tao: str = "") -> dict:
    """Tạo việc. `nick` là id profile hoặc tên (khớp duy nhất). Raise ValueError với câu tiếng
    Việt người đọc được nếu thiếu/sai/vượt giới hạn."""
    if ky_nang not in KY_NANG:
        raise ValueError(f"kỹ năng chưa có: {ky_nang}")
    noi_dung = str(noi_dung or "").strip()
    if len(noi_dung) > CHU_TOI_DA:
        raise ValueError(f"nội dung quá dài (tối đa {CHU_TOI_DA} ký tự)")
    tep = list(tep or [])
    if not noi_dung and not tep:
        raise ValueError("bài cần có chữ hoặc ít nhất một ảnh/video")
    noi_dang = str(noi_dang or "").strip()
    if noi_dang and not (noi_dang.startswith("https://") and "facebook.com" in noi_dang):
        raise ValueError("nơi đăng phải là link https://...facebook.com/... (để trống = tường của nick)")
    kq = tim_nick(nick)
    if not kq:
        raise ValueError(f"không thấy nick '{nick}'. Kiểm tra máy ở nhà đang chạy và tên profile trong GPM.")
    if len(kq) > 1:
        raise ValueError("có nhiều nick khớp: " + "; ".join(n["ten"] for n in kq[:8])
                         + ". Ghi rõ tên đầy đủ hơn.")
    n = kq[0]
    if (n.get("trinh_duyet") or "").lower() == "firefox":
        raise ValueError(f"nick '{n['ten']}' dùng Firefox; Đội Social hiện chỉ điều khiển profile Chrome.")
    gh = gioi_han()
    with _khoa, _db() as c:
        if _dem_hom_nay(c, n["id"], ky_nang) >= gh["bai_moi_ngay"]:
            raise ValueError(f"nick '{n['ten']}' đã đủ {gh['bai_moi_ngay']} bài hôm nay "
                             "(giới hạn chống checkpoint). Đổi giới hạn ở trang Đội Social nếu thật cần.")
        now = _bay_gio()
        cur = c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, "
                        "tao_luc, chat_id, nguon, ai_tao) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (ky_nang, n["may_id"], n["id"], n["ten"], "{}",
                         "cho_duyet" if can_duyet else "cho_chay", now, str(chat_id or "")[:60],
                         str(nguon or "")[:30], str(ai_tao or "")[:60]))
        vid = cur.lastrowid
        if not can_duyet:
            c.execute("UPDATE viec SET duyet_luc=? WHERE id=?", (now, vid))
    try:
        ds_tep = _chep_tep(vid, tep)
    except Exception:
        with _db() as c:
            c.execute("DELETE FROM viec WHERE id=?", (vid,))
        shutil.rmtree(str(_goc / "tep" / str(vid)), ignore_errors=True)
        raise
    ts = {"noi_dung": noi_dung, "tep": ds_tep, "noi_dang": noi_dang}
    with _db() as c:
        c.execute("UPDATE viec SET tham_so=? WHERE id=?", (json.dumps(ts, ensure_ascii=False), vid))
    return lay_viec(vid)


def _dong(r) -> dict:
    d = dict(r)
    for k, mac in (("tham_so", {}), ("buoc", [])):
        try:
            d[k] = json.loads(d.get(k) or "")
        except Exception:
            d[k] = mac
    d["nhan_ky_nang"] = KY_NANG.get(d.get("ky_nang"), d.get("ky_nang"))
    return d


def lay_viec(vid) -> Optional[dict]:
    with _db() as c:
        r = c.execute("SELECT * FROM viec WHERE id=?", (int(vid),)).fetchone()
    return _dong(r) if r else None


def ds_viec(limit: int = 50, trang_thai: str = "") -> list:
    with _db() as c:
        q, a = "SELECT * FROM viec", []
        if trang_thai:
            q += " WHERE trang_thai=?"
            a.append(trang_thai)
        q += " ORDER BY id DESC LIMIT ?"
        a.append(max(1, min(500, int(limit))))
        return [_dong(r) for r in c.execute(q, a).fetchall()]


def duyet(vid, dong_y: bool) -> dict:
    with _khoa, _db() as c:
        r = c.execute("SELECT trang_thai FROM viec WHERE id=?", (int(vid),)).fetchone()
        if not r:
            raise ValueError(f"không có việc #{vid}")
        if r["trang_thai"] != "cho_duyet":
            raise ValueError(f"việc #{vid} đã ở trạng thái '{r['trang_thai']}', không duyệt lại được")
        c.execute("UPDATE viec SET trang_thai=?, duyet_luc=? WHERE id=?",
                  ("cho_chay" if dong_y else "bo", _bay_gio(), int(vid)))
    if not dong_y:
        shutil.rmtree(str(_goc / "tep" / str(int(vid))), ignore_errors=True)
    return lay_viec(vid)


def _don_viec_treo(c) -> None:
    c.execute("UPDATE viec SET trang_thai='loi', thong_diep='máy ở nhà không báo kết quả (quá giờ)', "
              "xong_luc=? WHERE trang_thai='dang_chay' AND bat_dau < ?",
              (_bay_gio(), _bay_gio() - HET_GIO_CHAY))


def nhan_viec(may_id: str) -> Optional[dict]:
    """Việc kế tiếp cho máy này, tôn trọng khoảng nghỉ giữa hai lượt của cùng một nick.
    Mỗi máy chạy MỘT việc một lúc (máy nhà không phải trại máy chủ)."""
    gh = gioi_han()
    with _khoa, _db() as c:
        _don_viec_treo(c)
        if c.execute("SELECT 1 FROM viec WHERE may_id=? AND trang_thai='dang_chay'", (may_id,)).fetchone():
            return None
        for r in c.execute("SELECT * FROM viec WHERE may_id=? AND trang_thai='cho_chay' ORDER BY id",
                           (may_id,)).fetchall():
            cuoi = c.execute("SELECT MAX(xong_luc) FROM viec WHERE nick_id=? AND trang_thai='xong'",
                             (r["nick_id"],)).fetchone()[0]
            if cuoi and _bay_gio() - cuoi < gh["nghi_phut"] * 60:
                continue
            c.execute("UPDATE viec SET trang_thai='dang_chay', bat_dau=? WHERE id=?", (_bay_gio(), r["id"]))
            return lay_viec(r["id"])
    return None


def duong_tep(vid, luu: str) -> Optional[Path]:
    """Tệp đính kèm của việc (worker tải về). `luu` chỉ là tên trong kho, không nhận '/'."""
    if not luu or "/" in luu or "\\" in luu or luu.startswith("."):
        return None
    p = _goc / "tep" / str(int(vid)) / luu
    return p if p.is_file() else None


def ghi_ket_qua(vid, may_id: str, ok: bool, thong_diep: str = "", buoc=None, anh: bytes = b"") -> dict:
    with _khoa, _db() as c:
        r = c.execute("SELECT may_id, trang_thai FROM viec WHERE id=?", (int(vid),)).fetchone()
        if not r or r["may_id"] != may_id:
            raise ValueError("việc không thuộc máy này")
        if r["trang_thai"] != "dang_chay":
            raise ValueError(f"việc #{vid} không ở trạng thái đang chạy")
        co_anh = 0
        if anh:
            (_goc / "anh" / f"{int(vid)}.png").write_bytes(anh[:8 * 1024 * 1024])
            co_anh = 1
        c.execute("UPDATE viec SET trang_thai=?, xong_luc=?, thong_diep=?, buoc=?, co_anh=? WHERE id=?",
                  ("xong" if ok else "loi", _bay_gio(), str(thong_diep or "")[:1000],
                   json.dumps(list(buoc or [])[:50], ensure_ascii=False), co_anh, int(vid)))
    shutil.rmtree(str(_goc / "tep" / str(int(vid))), ignore_errors=True)
    return lay_viec(vid)


def duong_anh(vid) -> Optional[Path]:
    p = _goc / "anh" / f"{int(vid)}.png"
    return p if p.is_file() else None


def tom_tat(v: dict) -> str:
    """Một đoạn chữ thuần mô tả việc, dùng cho Telegram/hòm thư."""
    ts = v.get("tham_so") or {}
    nd = ts.get("noi_dung") or ""
    tep = ts.get("tep") or []
    dong = [f"#{v['id']} · {v.get('nhan_ky_nang')} · nick: {v.get('nick_ten')}"]
    if ts.get("noi_dang"):
        dong.append(f"Nơi đăng: {ts['noi_dang']}")
    else:
        dong.append("Nơi đăng: tường của nick")
    if tep:
        dong.append("Tệp: " + ", ".join(t.get("ten", "") for t in tep))
    if nd:
        dong.append("")
        dong.append(nd if len(nd) <= 1500 else nd[:1500] + "…")
    return "\n".join(dong)
