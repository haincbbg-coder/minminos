"""doi_social_v2.py - kho của Đội Social bản đầy đủ (26.10.187).

Hợp đồng: docs/doi-social/KIEN-TRUC.md mục 1, 2, 7. Dùng CHUNG tệp SQLite và khoá với
`doi_social` (bảng cũ ma_ghep, may, nick, viec, cai_dat giữ nguyên ở đó). Ở đây có:

- đợt chạy (một mẫu x nhiều nick = nhiều việc), lịch hẹn cron, kế hoạch AI chờ duyệt;
- hạn mức theo nick (tuổi nick, tăng theo tuần, tổng việc/ngày) tính lúc giao việc;
- sự kiện từng thao tác (dòng thời gian, cảnh báo đăng xuất/checkpoint), trí nhớ chống lặp;
- kho bài, bản nháp chờ duyệt, kiến thức sản phẩm (tài liệu, hỏi đáp), nhóm FB, hội thoại;
- số liệu cho trang Tổng quan và mục "Cần bạn xử lý".

Thuần stdlib, đồng bộ. Không gọi AI, không gọi mạng: phần đó ở routes/doi_social.py.
Thư viện nặng (csv, zipfile, random...) nạp trong hàm để import main vẫn nhẹ.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
from collections import deque
from pathlib import Path
from typing import Iterable, Optional

import doi_social as ds
import doi_social_kich_ban as kb

LOAI_NHAP = ("binh_luan", "bai_dang", "tra_loi")
NOI_DANG = ("fb_nhom", "fb_tuong", "fb_trang", "threads", "instagram", "reddit", "x", "tiktok")
TT_NHAP = ("cho_duyet", "da_duyet", "da_dang", "da_bo", "loi", "het_han")
KET_QUA_SK = ("thanh_cong", "bo_qua", "loi", "thong_tin")
MA_CANH_BAO = {"dang_xuat": "bị đăng xuất", "checkpoint": "bị checkpoint", "captcha": "gặp captcha",
               "qua_nhanh": "bị báo thao tác quá nhanh"}
TT_HOI_THOAI = ("bot_dang_lo", "can_tra_loi_tay", "da_xu_ly", "spam")
TT_NHOM = ("cho_duyet", "da_duyet", "den")
TT_VAO = ("da_vao", "cho_duyet", "bi_tu_choi")
NGUON_DOT = ("web", "lich", "tro_ly", "telegram")
KHO_DUOI = set(ds.DUOI_TEP)
KHO_TOI_DA = 200 * 1024 * 1024
TL_DUOI = {".txt", ".md", ".pdf", ".docx"}
TL_TOI_DA = 5 * 1024 * 1024
TL_CHU_TOI_DA = 200_000
NHUONG_GIO = 12
KQ_DUOI = {".csv", ".txt"}
KQ_TOI_DA = 10 * 1024 * 1024
X_CACH_PHUT = 10                 # X: hai bài của cùng nick cách nhau ít nhất 10 phút (xuyên đợt)
TEN_NEN_TANG = dict(kb.NEN_TANG)

_BUOC: dict = {}                 # viec_id -> deque 30 dòng nhật ký trực tiếp (mục "Đang chạy")
_BAO_CHO: deque = deque(maxlen=200)   # (tieu_de, noi_dung) chờ routes gửi hòm thư/Telegram
_khoa_bao = threading.Lock()


# ------------------------------------------------------------------ hạ tầng

def tao_bang(c) -> None:
    """Gọi từ doi_social.mo() trong cùng kết nối. Idempotent."""
    c.executescript("""
    CREATE TABLE IF NOT EXISTS nick_meta(
        nick_id TEXT PRIMARY KEY, nhan TEXT DEFAULT '[]', tao_tu TEXT DEFAULT '', ghi_chu TEXT DEFAULT '',
        canh_bao TEXT DEFAULT '{}', lan_chay REAL);
    CREATE TABLE IF NOT EXISTS dot_chay(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, kich_ban TEXT, nick TEXT DEFAULT '[]',
        tham_so TEXT DEFAULT '{}', song_song INTEGER DEFAULT 1, chay_an INTEGER DEFAULT 0,
        chay_thu INTEGER DEFAULT 0, trang_thai TEXT DEFAULT 'cho', tao_luc REAL, xong_luc REAL,
        lich_id INTEGER, nguon TEXT DEFAULT 'web');
    CREATE INDEX IF NOT EXISTS dot_tt ON dot_chay(trang_thai, tao_luc);
    CREATE TABLE IF NOT EXISTS lich_hen(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, kich_ban TEXT, nick TEXT DEFAULT '[]',
        tham_so TEXT DEFAULT '{}', song_song INTEGER DEFAULT 1, cron TEXT, bat INTEGER DEFAULT 1,
        lan_ke REAL, lan_truoc REAL, so_lan INTEGER DEFAULT 0, so_loi INTEGER DEFAULT 0, tao_luc REAL,
        chay_an INTEGER DEFAULT 0, loi_cuoi TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS su_kien(
        id INTEGER PRIMARY KEY AUTOINCREMENT, luc REAL, viec_id INTEGER, dot_id INTEGER, nick_id TEXT,
        nick_ten TEXT, nen_tang TEXT, kich_ban TEXT, tinh_nang TEXT, hanh_dong TEXT, ket_qua TEXT,
        chi_tiet TEXT DEFAULT '', link TEXT DEFAULT '', nhom TEXT DEFAULT '', san_pham TEXT DEFAULT '',
        ma TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS su_kien_luc ON su_kien(luc);
    CREATE INDEX IF NOT EXISTS su_kien_nick ON su_kien(nick_id, luc);
    CREATE TABLE IF NOT EXISTS kho_bai(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nen_tang TEXT, nick_id TEXT DEFAULT '', tieu_de TEXT DEFAULT '',
        noi_dung TEXT DEFAULT '', tep TEXT DEFAULT '[]', trang_thai TEXT DEFAULT 'cho', giu_boi_viec INTEGER,
        luc_tao REAL, luc_dang REAL, link TEXT DEFAULT '', loi TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS kho_tt ON kho_bai(nen_tang, nick_id, trang_thai);
    CREATE TABLE IF NOT EXISTS ban_nhap(
        id INTEGER PRIMARY KEY AUTOINCREMENT, loai TEXT, noi_dang TEXT, nick_id TEXT DEFAULT '',
        nick_ten TEXT DEFAULT '', nhom TEXT DEFAULT '', link_goc TEXT DEFAULT '', bai_goc TEXT DEFAULT '',
        ly_do TEXT DEFAULT '', noi_dung TEXT DEFAULT '', san_pham_id TEXT DEFAULT '',
        trang_thai TEXT DEFAULT 'cho_duyet', tao_luc REAL, het_han REAL, viec_tao TEXT DEFAULT '',
        ket_qua TEXT DEFAULT '{}', tep TEXT DEFAULT '[]', giu_boi_viec INTEGER, chay_thu INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS nhap_tt ON ban_nhap(trang_thai, noi_dang);
    CREATE TABLE IF NOT EXISTS kien_thuc(
        id INTEGER PRIMARY KEY AUTOINCREMENT, loai TEXT DEFAULT 'san_pham', ten TEXT, mo_ta TEXT DEFAULT '',
        gia TEXT DEFAULT '', link TEXT DEFAULT '', tu_khoa TEXT DEFAULT '', giong_van TEXT DEFAULT '',
        dan_rieng TEXT DEFAULT '', trang_thai TEXT DEFAULT 'dang_dung', tao_luc REAL);
    CREATE TABLE IF NOT EXISTS tai_lieu(id INTEGER PRIMARY KEY AUTOINCREMENT, kt_id INTEGER, ten TEXT,
        noi_dung TEXT);
    CREATE TABLE IF NOT EXISTS hoi_dap(id INTEGER PRIMARY KEY AUTOINCREMENT, kt_id INTEGER, hoi TEXT,
        dap TEXT DEFAULT '', trang_thai TEXT DEFAULT 'da_tra_loi', nguon TEXT DEFAULT '', luc REAL);
    CREATE TABLE IF NOT EXISTS nhom_fb(
        id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id TEXT, link TEXT, ten TEXT DEFAULT '',
        trang_thai TEXT DEFAULT 'cho_duyet', nick_chinh TEXT DEFAULT '', nick_tuong_tac TEXT DEFAULT '[]',
        tinh_trang_vao TEXT DEFAULT '{}', lan_quet REAL, quet_lai_gio INTEGER DEFAULT 24,
        ghi_chu TEXT DEFAULT '', UNIQUE(san_pham_id, link));
    CREATE TABLE IF NOT EXISTS hoi_thoai(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nick_id TEXT, nick_ten TEXT DEFAULT '', khach_ten TEXT DEFAULT '',
        khach_link TEXT, san_pham_id TEXT DEFAULT '', trang_thai TEXT DEFAULT 'bot_dang_lo',
        tiem_nang INTEGER DEFAULT 0, sdt TEXT DEFAULT '', nhuong_den REAL DEFAULT 0, cap_nhat REAL,
        UNIQUE(nick_id, khach_link));
    CREATE TABLE IF NOT EXISTS tin_nhan(id INTEGER PRIMARY KEY AUTOINCREMENT, ht_id INTEGER, tu TEXT,
        noi_dung TEXT, luc REAL);
    CREATE INDEX IF NOT EXISTS tin_ht ON tin_nhan(ht_id, id);
    CREATE TABLE IF NOT EXISTS ke_hoach(
        id INTEGER PRIMARY KEY AUTOINCREMENT, mo_ta TEXT, buoc TEXT DEFAULT '[]',
        trang_thai TEXT DEFAULT 'cho_duyet', nguon TEXT DEFAULT 'web', chat_id TEXT DEFAULT '',
        tao_luc REAL, dot_ids TEXT DEFAULT '[]');
    CREATE TABLE IF NOT EXISTS tro_ly(id INTEGER PRIMARY KEY AUTOINCREMENT, phien TEXT, vai TEXT,
        noi_dung TEXT, ke_hoach_id INTEGER, luc REAL);
    CREATE INDEX IF NOT EXISTS tro_ly_phien ON tro_ly(phien, id);
    CREATE TABLE IF NOT EXISTS dich_den(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nick_id TEXT, nen_tang TEXT, loai TEXT, ten TEXT, link TEXT,
        ma TEXT DEFAULT '', anh TEXT DEFAULT '', cap_nhat REAL, UNIQUE(nick_id, nen_tang, link));
    CREATE INDEX IF NOT EXISTS dich_den_nick ON dich_den(nick_id);
    CREATE TABLE IF NOT EXISTS da_lam(nick_id TEXT, khoa TEXT, luc REAL, PRIMARY KEY(nick_id, khoa));
    CREATE INDEX IF NOT EXISTS da_lam_khoa ON da_lam(khoa);
    """)
    import sqlite3
    for bang, cot in (("ban_nhap", "muc_tieu TEXT DEFAULT '{}'"),
                      ("kien_thuc", "nguon_bo_nao TEXT DEFAULT '[]'"),
                      ("kien_thuc", "tu_tra_bo_nao INTEGER DEFAULT 1"),
                      ("viec", "lenh TEXT DEFAULT ''")):
        try:
            c.execute(f"ALTER TABLE {bang} ADD COLUMN {cot}")
        except sqlite3.OperationalError:
            pass


def _now() -> float:
    return ds._bay_gio()


def _j(s, mac):
    try:
        v = json.loads(s) if isinstance(s, str) and s else None
    except Exception:
        v = None
    return mac if v is None else v


def _dj(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _tz():
    import localefmt
    return localefmt.tz()


def _dau_ngay(luc: Optional[float] = None) -> float:
    from datetime import datetime
    dt = datetime.fromtimestamp(luc if luc is not None else _now(), _tz())
    return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _ngay_str(luc: float) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(luc, _tz()).strftime("%Y-%m-%d")


def _trang(trang, moi_trang, mac: int = 50) -> tuple:
    try:
        t = max(1, int(trang or 1))
    except (TypeError, ValueError):
        t = 1
    try:
        m = max(1, min(200, int(moi_trang or mac)))
    except (TypeError, ValueError):
        m = mac
    return t, m, (t - 1) * m


def _chu(v, toi_da: int = 2000) -> str:
    return str(v if v is not None else "").strip()[:toi_da]


def bao(tieu_de: str, noi_dung: str) -> None:
    """Đẩy một thông báo cho chủ vào hàng chờ; routes gửi đi (hòm thư + Telegram)."""
    with _khoa_bao:
        _BAO_CHO.append((str(tieu_de)[:200], str(noi_dung)[:3000]))


def lay_bao() -> list:
    with _khoa_bao:
        ra = list(_BAO_CHO)
        _BAO_CHO.clear()
    return ra


def _nen_tang_noi_dang(noi_dang: str) -> str:
    return "facebook" if str(noi_dang).startswith("fb_") else str(noi_dang)


def _ten_mau(ky: str) -> str:
    m = kb.THEO_ID.get(ky)
    return m["ten"] if m else ds.KY_NANG.get(ky, ky)


# ------------------------------------------------------------------ giới hạn v2

def _ghep_sau(goc: dict, moi: dict) -> dict:
    ra = json.loads(json.dumps(goc))
    for k, v in (moi or {}).items():
        if isinstance(v, dict) and isinstance(ra.get(k), dict):
            ra[k] = _ghep_sau(ra[k], v)
        else:
            ra[k] = v
    return ra


def gioi_han_v2() -> dict:
    with ds._db() as c:
        r = c.execute("SELECT v FROM cai_dat WHERE k='gioi_han_v2'").fetchone()
    return _ghep_sau(kb.GIOI_HAN_MAC_DINH, _j(r["v"], {}) if r else {})


def vai_agent() -> dict:
    """Loại việc AI -> slug agent MinMin làm vai trò (ghép với mặc định trong doi_social_bo_nao)."""
    import doi_social_bo_nao as bn
    with ds._db() as c:
        r = c.execute("SELECT v FROM cai_dat WHERE k='agent_vai'").fetchone()
    luu = _j(r["v"], {}) if r else {}
    return {k: str(luu.get(k, bn.VAI_MAC_DINH.get(k, "")) or "") for k in bn.VIEC_AI}


def dat_vai_agent(moi: dict) -> dict:
    import re
    import doi_social_bo_nao as bn
    cu = vai_agent()
    for k, v in (moi or {}).items():
        if k not in bn.VIEC_AI:
            raise ValueError(f"loại việc lạ: {k}")
        v = str(v or "").strip()
        if v and not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", v):
            raise ValueError("tên agent không hợp lệ")
        cu[k] = v
    with ds._khoa, ds._db() as c:
        c.execute("INSERT OR REPLACE INTO cai_dat(k, v) VALUES('agent_vai', ?)", (_dj(cu),))
    return cu


def _so_nguyen(v, ten: str, lo: int = 0, hi: int = 100000) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"'{ten}' phải là số nguyên")
    if n < lo or n > hi:
        raise ValueError(f"'{ten}' phải trong khoảng {lo}-{hi}")
    return n


def _cap(v, ten: str, hi: int = 100000) -> list:
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise ValueError(f"'{ten}' phải là cặp [nhỏ, lớn]")
    a, b = _so_nguyen(v[0], ten, 0, hi), _so_nguyen(v[1], ten, 0, hi)
    if a > b:
        raise ValueError(f"'{ten}': số đầu không được lớn hơn số sau")
    return [a, b]


def dat_gioi_han_v2(moi: dict) -> dict:
    """Ghép sâu `moi` vào giới hạn hiện có, kiểm từng ô, lưu. Raise ValueError tiếng Việt."""
    if not isinstance(moi, dict):
        raise ValueError("giới hạn phải là object")
    g = _ghep_sau(gioi_han_v2(), moi)
    ch = g.get("chung") or {}
    sach = {"chung": {}, "nen_tang": {}}
    for k in ("viec_ngay_moi", "viec_ngay_lau"):
        sach["chung"][k] = _so_nguyen(ch.get(k), k, 0, 1000)
    sach["chung"]["lau_nam_sau_ngay"] = _so_nguyen(ch.get("lau_nam_sau_ngay"), "lau_nam_sau_ngay", 0, 3650)
    sach["chung"]["tang_tuan_pt"] = _so_nguyen(ch.get("tang_tuan_pt"), "tang_tuan_pt", 0, 500)
    sach["chung"]["nghi_phut"] = _cap(ch.get("nghi_phut"), "nghi_phut", 24 * 60)
    sach["chung"]["nghi_giay"] = _cap(ch.get("nghi_giay"), "nghi_giay", 3600)
    for nt, bang in (g.get("nen_tang") or {}).items():
        if nt not in TEN_NEN_TANG or not isinstance(bang, dict):
            continue
        sb = {}
        for hd, v in bang.items():
            if isinstance(v, (list, tuple)):
                sb[hd] = _cap(v, f"{nt}.{hd}", 10000)
            else:
                sb[hd] = _so_nguyen(v, f"{nt}.{hd}", 0, 10000)
        sach["nen_tang"][nt] = sb
    with ds._khoa, ds._db() as c:
        c.execute("INSERT OR REPLACE INTO cai_dat(k, v) VALUES('gioi_han_v2', ?)", (json.dumps(sach),))
    return gioi_han_v2()


# ------------------------------------------------------------------ nick + hạn mức

def _meta(c, nick_id: str) -> dict:
    r = c.execute("SELECT * FROM nick_meta WHERE nick_id=?", (nick_id,)).fetchone()
    d = dict(r) if r else {"nick_id": nick_id, "nhan": "[]", "tao_tu": "", "ghi_chu": "", "canh_bao": "{}",
                           "lan_chay": None}
    d["nhan"] = _j(d.get("nhan"), [])
    d["canh_bao"] = _j(d.get("canh_bao"), {})
    return d


def _luu_meta(c, m: dict) -> None:
    c.execute("INSERT OR REPLACE INTO nick_meta(nick_id, nhan, tao_tu, ghi_chu, canh_bao, lan_chay) "
              "VALUES(?,?,?,?,?,?)", (m["nick_id"], _dj(m.get("nhan") or []), m.get("tao_tu") or "",
                                     m.get("ghi_chu") or "", _dj(m.get("canh_bao") or {}), m.get("lan_chay")))


def _tuoi_ngay(tao_tu: str, now: float) -> Optional[int]:
    from datetime import datetime
    try:
        y, m = str(tao_tu).split("-")[:2]
        dt = datetime(int(y), int(m), 1, tzinfo=_tz())
    except Exception:
        return None
    return max(0, int((now - dt.timestamp()) // 86400))


def _muc(meta: dict, g: dict, now: float) -> str:
    t = _tuoi_ngay(meta.get("tao_tu") or "", now)
    return "lau" if t is not None and t >= int(g["chung"].get("lau_nam_sau_ngay", 90)) else "moi"


def _tran(c, nick_id: str, nen_tang: str, hd: str, g: dict, muc: str, now: float) -> Optional[int]:
    lim = ((g.get("nen_tang") or {}).get(nen_tang) or {}).get(hd)
    if not isinstance(lim, (list, tuple)) or len(lim) != 2:
        return None
    if muc == "lau":
        return int(lim[1])
    dau = c.execute("SELECT MIN(bat_dau) FROM viec WHERE nick_id=? AND bat_dau IS NOT NULL",
                    (nick_id,)).fetchone()[0]
    tuan = int(max(0, now - dau) // (7 * 86400)) if dau else 0
    pt = float(g["chung"].get("tang_tuan_pt", 0)) / 100.0
    return int(min(int(lim[1]), int(int(lim[0]) * (1 + pt) ** min(tuan, 104))))


def _han_muc(c, nick_id: str, nen_tang: str, hanh_dong: Iterable, g: Optional[dict] = None,
             now: Optional[float] = None) -> dict:
    g = g or gioi_han_v2()
    now = now if now is not None else _now()
    muc = _muc(_meta(c, nick_id), g, now)
    dau = _dau_ngay(now)
    ra = {}
    for hd in hanh_dong or []:
        tr = _tran(c, nick_id, nen_tang, hd, g, muc, now)
        if tr is None:
            ra[hd] = 999
            continue
        da = c.execute("SELECT COUNT(*) FROM su_kien WHERE nick_id=? AND nen_tang=? AND hanh_dong=? "
                       "AND ket_qua='thanh_cong' AND luc>=?", (nick_id, nen_tang, hd, dau)).fetchone()[0]
        ra[hd] = max(0, tr - da)
    return ra


def han_muc(nick_id: str, nen_tang: str, hanh_dong: Iterable) -> dict:
    """Số thao tác còn được làm hôm nay cho nick, theo từng hành động (999 = không giới hạn)."""
    with ds._db() as c:
        return _han_muc(c, nick_id, nen_tang, list(hanh_dong))


def ds_nick() -> list:
    """Nick (profile GPM) kèm nhãn nền tảng, tuổi, mức giới hạn, cảnh báo."""
    now = _now()
    g = gioi_han_v2()
    may = {m["id"]: m for m in ds.ds_may()}
    ra = []
    with ds._db() as c:
        dich = {}
        for r in c.execute("SELECT * FROM dich_den ORDER BY nen_tang, loai, ten"):
            dich.setdefault(r["nick_id"], []).append({k: r[k] for k in ("id", "nen_tang", "loai", "ten", "link", "anh",
                                                                        "cap_nhat")})
        for n in ds.ds_nick():
            m = _meta(c, n["id"])
            tuoi = _tuoi_ngay(m["tao_tu"], now)
            ra.append({"id": n["id"], "ten": n["ten"], "may_id": n["may_id"], "may_ten": n.get("may_ten"),
                       "nhom": n.get("nhom") or "", "trinh_duyet": n.get("trinh_duyet") or "",
                       "co_proxy": bool(n.get("co_proxy")), "nhan": m["nhan"], "tao_tu": m["tao_tu"],
                       "ghi_chu": m["ghi_chu"], "tuoi_ngay": tuoi, "muc": _muc(m, g, now),
                       "canh_bao": m["canh_bao"], "lan_chay": m["lan_chay"],
                       "online": bool((may.get(n["may_id"]) or {}).get("online")),
                       "dich_den": dich.get(n["id"], [])})
    return ra


def dat_nick_meta(ids, nhan=None, tao_tu=None, ghi_chu=None) -> int:
    ids = [str(x)[:80] for x in (ids or []) if str(x).strip()]
    if not ids:
        raise ValueError("chưa chọn nick nào")
    if nhan is not None:
        if not isinstance(nhan, list):
            raise ValueError("nhãn phải là danh sách nền tảng")
        sai = [x for x in nhan if x not in TEN_NEN_TANG]
        if sai:
            raise ValueError(f"nền tảng lạ: {sai[0]}")
    if tao_tu is not None:
        tao_tu = str(tao_tu).strip()
        if tao_tu and _tuoi_ngay(tao_tu, _now()) is None:
            raise ValueError("'Tạo từ' phải dạng YYYY-MM, ví dụ 2023-05")
    with ds._khoa, ds._db() as c:
        for i in ids:
            m = _meta(c, i)
            if nhan is not None:
                m["nhan"] = list(dict.fromkeys(nhan))
            if tao_tu is not None:
                m["tao_tu"] = tao_tu
            if ghi_chu is not None:
                m["ghi_chu"] = _chu(ghi_chu, 500)
            _luu_meta(c, m)
    return len(ids)


# ------------------------------------------------------------------ giao việc (gọi từ doi_social.nhan_viec)

def may_lam_duoc(ky: str, ho_tro: set, r) -> bool:
    """Máy có báo làm được việc này không. `fb_dang_bai` cũ được xử lý ở doi_social."""
    if ky == "dang_ban_nhap":
        nt = (_j(r["tham_so"], {}) or {}).get("nen_tang") or ""
        return ("dang_ban_nhap" in ho_tro or f"dang_ban_nhap:{nt}" in ho_tro
                or (nt == "facebook" and any(str(x).startswith("fb_") for x in ho_tro)))
    if ky in ("kham_trang", "quet_tai_khoan"):
        return ky in ho_tro
    if ky == "fb_gui_tin":
        return "fb_gui_tin" in ho_tro or any(str(x).startswith("fb_") for x in ho_tro)
    return ky in ho_tro


def _ghi_sk(c, *, viec: dict, hanh_dong: str, ket_qua: str, chi_tiet: str = "", link: str = "",
            nhom: str = "", san_pham: str = "", ma: str = "", luc: Optional[float] = None) -> None:
    ts = viec.get("tham_so") or {}
    ky = viec.get("ky_nang") or ""
    m = kb.THEO_ID.get(ky)
    tinh_nang = m["tinh_nang"] if m else ("Nhắn tin Messenger" if ky == "fb_gui_tin" else "Đăng nội dung đã duyệt")
    c.execute("INSERT INTO su_kien(luc, viec_id, dot_id, nick_id, nick_ten, nen_tang, kich_ban, tinh_nang, "
              "hanh_dong, ket_qua, chi_tiet, link, nhom, san_pham, ma) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (luc if luc is not None else _now(), viec.get("id"), viec.get("dot_id"), viec.get("nick_id"),
               viec.get("nick_ten"), ts.get("nen_tang") or (m or {}).get("nen_tang") or "", ky, tinh_nang,
               _chu(hanh_dong, 40), ket_qua, _chu(chi_tiet, 1000), _chu(link, 500), _chu(nhom, 300),
               _chu(san_pham, 200), _chu(ma, 30)))


def chuan_bi_giao(c, r, g: dict) -> str:
    """Quyết định cho một việc `cho_chay`: 'cho' (chưa tới lượt), 'bo_qua' (hết hạn mức, đã kết
    thúc ở máy chủ) hoặc 'giao' (đã chuyển dang_chay, tham_so mang han_muc mới)."""
    import random
    now = _now()
    ts = _j(r["tham_so"], {})
    ky = r["ky_nang"]
    mau = kb.THEO_ID.get(ky)
    noi_bo = ky in ds.KY_NANG_NOI_BO
    nen = ts.get("nen_tang") or (mau or {}).get("nen_tang") or ""
    hd = list((mau or {}).get("hanh_dong") or [])
    if noi_bo:
        hd = list(ts.get("hanh_dong") or [])
    meta = _meta(c, r["nick_id"])
    muc = _muc(meta, g, now)
    ly_do = ""
    if not noi_bo and not r["chay_thu"]:
        a, b = (g["chung"].get("nghi_phut") or [0, 0])[:2]
        cuoi = c.execute("SELECT MAX(xong_luc) FROM viec WHERE nick_id=? AND trang_thai IN ('xong','loi') "
                         "AND bat_dau IS NOT NULL AND chay_thu=0 AND ky_nang NOT IN ('dang_ban_nhap','fb_gui_tin')",
                         (r["nick_id"],)).fetchone()[0]
        nghi = random.Random(int(r["id"])).uniform(float(a), float(b)) * 60
        if cuoi and now - cuoi < nghi:
            return "cho"
    if nen == "x" and "dang_tuong" in hd and not r["chay_thu"]:
        cuoi_x = c.execute("SELECT MAX(luc) FROM su_kien WHERE nick_id=? AND nen_tang='x' AND hanh_dong='dang_tuong' "
                           "AND ket_qua='thanh_cong'", (r["nick_id"],)).fetchone()[0]
        if cuoi_x and now - cuoi_x < X_CACH_PHUT * 60:
            return "cho"
    if not noi_bo and not r["chay_thu"]:
        tran_ngay = int(g["chung"].get("viec_ngay_lau" if muc == "lau" else "viec_ngay_moi", 0))
        da = c.execute("SELECT COUNT(*) FROM viec WHERE nick_id=? AND bat_dau>=? AND chay_thu=0 "
                       "AND ky_nang NOT IN ('fb_dang_bai','dang_ban_nhap','fb_gui_tin')",
                       (r["nick_id"], _dau_ngay(now))).fetchone()[0]
        if da >= tran_ngay:
            ly_do = f"Bỏ qua: nick đã đủ {tran_ngay} việc hôm nay (giới hạn nick)"
    con = _han_muc(c, r["nick_id"], nen, hd, g, now)
    if not ly_do and not noi_bo and not r["chay_thu"] and hd and all(v <= 0 for v in con.values()):
        ly_do = "Bỏ qua: nick đã đủ giới hạn hôm nay"
    v = ds._dong(r)
    if ly_do:
        c.execute("UPDATE viec SET trang_thai='bo', thong_diep=?, xong_luc=?, ket_qua=? WHERE id=?",
                  (ly_do, now, json.dumps({"thanh_cong": 0, "bo_qua": 1, "loi": 0}), r["id"]))
        _ghi_sk(c, viec=v, hanh_dong="", ket_qua="bo_qua", chi_tiet=ly_do, ma="het_han_muc")
        sau_viec(c, int(r["id"]))
        return "bo_qua"
    ts["han_muc"] = con
    ts["nghi_giay"] = list(g["chung"].get("nghi_giay") or [6, 25])
    ts["nen_tang"] = nen
    c.execute("UPDATE viec SET trang_thai='dang_chay', bat_dau=?, tham_so=? WHERE id=?",
              (now, _dj(ts), r["id"]))
    meta["lan_chay"] = now
    _luu_meta(c, meta)
    if r["dot_id"]:
        c.execute("UPDATE dot_chay SET trang_thai='dang_chay' WHERE id=? AND trang_thai='cho'", (r["dot_id"],))
    return "giao"


def sau_viec(c, vid: int) -> None:
    """Dọn sau khi một việc kết thúc (xong/loi/bo): nhả bài kho, nháp đang giữ; cập nhật đợt."""
    r = c.execute("SELECT id, ky_nang, trang_thai, dot_id, tham_so FROM viec WHERE id=?", (int(vid),)).fetchone()
    if not r:
        return
    tt = r["trang_thai"]
    now = _now()
    if tt == "bo":
        c.execute("UPDATE kho_bai SET trang_thai='cho', giu_boi_viec=NULL WHERE giu_boi_viec=? AND trang_thai='dang_giu'",
                  (vid,))
    else:
        c.execute("UPDATE kho_bai SET trang_thai='loi', giu_boi_viec=NULL, loi=? WHERE giu_boi_viec=? "
                  "AND trang_thai='dang_giu'",
                  ("Việc kết thúc khi bài còn đang giữ: không rõ đã đăng chưa, kiểm tra tay rồi bấm Trả lại", vid))
    if r["ky_nang"] == "dang_ban_nhap":
        moi = {"xong": "da_dang", "loi": "loi"}.get(tt)
        if moi:
            c.execute("UPDATE ban_nhap SET trang_thai=?, giu_boi_viec=NULL WHERE giu_boi_viec=? AND trang_thai='da_duyet'",
                      (moi, vid))
        else:
            c.execute("UPDATE ban_nhap SET giu_boi_viec=NULL WHERE giu_boi_viec=? AND trang_thai='da_duyet'", (vid,))
    elif tt == "bo":
        c.execute("UPDATE ban_nhap SET giu_boi_viec=NULL WHERE giu_boi_viec=? AND trang_thai='da_duyet'", (vid,))
    else:
        c.execute("UPDATE ban_nhap SET trang_thai='loi', giu_boi_viec=NULL, ket_qua=? WHERE giu_boi_viec=? "
                  "AND trang_thai='da_duyet'",
                  (_dj({"loi": "việc kết thúc khi nháp còn đang giữ, không rõ đã đăng chưa"}), vid))
    _BUOC.pop(int(vid), None)
    if r["dot_id"]:
        _cap_nhat_dot(c, int(r["dot_id"]), now)


# ------------------------------------------------------------------ đợt chạy

def _tim_nick_ds(c, nick) -> list:
    """Danh sách id/tên -> danh sách dòng nick có thật (giữ thứ tự, bỏ trùng). Raise nếu thiếu."""
    if isinstance(nick, str):
        nick = [x.strip() for x in nick.replace(",", "\n").splitlines() if x.strip()]
    if not isinstance(nick, list) or not nick:
        raise ValueError("chưa chọn nick nào")
    tat_ca = {}
    for r in c.execute("SELECT * FROM nick ORDER BY cap_nhat DESC").fetchall():
        tat_ca.setdefault(r["id"], dict(r))
    ra, thieu = [], []
    for x in nick[:500]:
        x = str(x).strip()
        n = tat_ca.get(x)
        if not n:
            kq = ds.tim_nick(x)
            n = kq[0] if len(kq) == 1 else None
        if not n:
            thieu.append(x)
            continue
        if n["id"] not in [y["id"] for y in ra]:
            ra.append(n)
    if thieu:
        raise ValueError("không thấy nick: " + ", ".join(thieu[:5]) + ". Kiểm tra máy ở nhà đã gửi danh sách profile.")
    ff = [n["ten"] for n in ra if (n.get("trinh_duyet") or "").lower() == "firefox"]
    if ff:
        raise ValueError(f"nick dùng Firefox chưa điều khiển được: {', '.join(ff[:5])}")
    return ra


def _kiem_mau(c, kich_ban: str, tham_so: dict) -> tuple:
    m = kb.THEO_ID.get(str(kich_ban or ""))
    if not m:
        raise ValueError(f"không có mẫu '{kich_ban}'")
    ts = kb.kiem_tham_so(m["id"], tham_so or {})
    sp = ts.get("san_pham")
    if sp:
        if not c.execute("SELECT 1 FROM kien_thuc WHERE id=?", (_int(sp),)).fetchone():
            raise ValueError(f"không có sản phẩm/chủ đề #{sp} trong Kiến thức cho Agent")
    return m, ts


def _int(v, mac: int = -1) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return mac


def _chia_deu(dong: list, n: int) -> list:
    ra = [[] for _ in range(n)]
    for i, x in enumerate(dong):
        ra[i % n].append(x)
    return ra


def tao_dot(*, kich_ban, nick, tham_so, ten="", song_song=1, chay_an=False, nguon="web", lich_id=None,
            chay_thu=None) -> dict:
    """Tạo đợt chạy: một việc `cho_chay` cho mỗi nick. Raise ValueError câu tiếng Việt."""
    nguon = nguon if nguon in NGUON_DOT else "web"
    ss = max(1, min(ds.SONG_SONG_TRAN, _int(song_song, 1)))
    now = _now()
    with ds._khoa, ds._db() as c:
        m, ts = _kiem_mau(c, kich_ban, tham_so)
        nicks = _tim_nick_ds(c, nick)
        if chay_thu is None:
            chay_thu = ts.get("che_do") == "chay_thu"
        chay_thu = bool(chay_thu)
        ten = _chu(ten, 120) or f"{m['ten']} · {len(nicks)} nick"
        cur = c.execute("INSERT INTO dot_chay(ten, kich_ban, nick, tham_so, song_song, chay_an, chay_thu, "
                        "trang_thai, tao_luc, lich_id, nguon) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (ten, m["id"], _dj([n["id"] for n in nicks]), _dj(ts), ss, int(bool(chay_an)),
                         int(chay_thu), "cho", now, lich_id, nguon))
        dot_id = cur.lastrowid
        phan = None
        if m["id"] == "fb_nhan_tin_ds":     # chia đều người nhận cho các nick
            dong = [x.strip() for x in str(ts.get("nguoi_nhan") or "").splitlines() if x.strip()]
            phan = _chia_deu(dong, len(nicks))
        for i, n in enumerate(nicks):
            tsn = dict(ts)
            for f in m["tham_so"]:          # nơi đăng chọn riêng cho từng nick: {nick_id: link}
                if f["kieu"] == "dich_den":
                    gt = ts.get(f["key"])
                    tsn[f["key"]] = str((gt.get(n["id"]) if isinstance(gt, dict) else gt) or "")
            if phan is not None:
                if not phan[i]:
                    continue
                tsn["nguoi_nhan"] = "\n".join(phan[i])
            vts = {"kich_ban": m["id"], "tham_so": tsn, "chay_thu": chay_thu, "dot_id": dot_id,
                   "han_muc": {}, "nghi_giay": [], "nen_tang": m["nen_tang"], "chay_an": bool(chay_an)}
            c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc, "
                      "duyet_luc, nguon, dot_id, chay_thu) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (m["id"], n["may_id"], n["id"], n["ten"], _dj(vts), "cho_chay", now, now, nguon,
                       dot_id, int(chay_thu)))
    return lay_dot(dot_id, kem_viec=True)


def _tien_trinh(c, dot_id: int) -> dict:
    d = {"tong": 0, "xong": 0, "loi": 0, "dang": 0, "cho": 0, "bo": 0, "tam": 0}
    for r in c.execute("SELECT trang_thai, COUNT(*) n FROM viec WHERE dot_id=? GROUP BY trang_thai", (dot_id,)):
        d["tong"] += r["n"]
        k = {"xong": "xong", "loi": "loi", "dang_chay": "dang", "cho_chay": "cho", "bo": "bo",
             "tam_dung": "tam"}.get(r["trang_thai"])
        if k:
            d[k] += r["n"]
    return d


def _dong_dot(c, r) -> dict:
    d = dict(r)
    d["nick"] = _j(d.get("nick"), [])
    d["tham_so"] = _j(d.get("tham_so"), {})
    d["ten_mau"] = _ten_mau(d.get("kich_ban") or "")
    d["tien_trinh"] = _tien_trinh(c, d["id"])
    return d


def _cap_nhat_dot(c, dot_id: int, now: float) -> None:
    r = c.execute("SELECT * FROM dot_chay WHERE id=?", (dot_id,)).fetchone()
    if not r or r["trang_thai"] in ("hoan_tat",):
        return
    tt = _tien_trinh(c, dot_id)
    con = tt["cho"] + tt["dang"] + tt["tam"]
    if con == 0 and r["trang_thai"] in ("cho", "dang_chay"):
        c.execute("UPDATE dot_chay SET trang_thai='hoan_tat', xong_luc=? WHERE id=?", (now, dot_id))
        bao("Đợt chạy xong", f"{r['ten']}: thành công {tt['xong']}, lỗi {tt['loi']}, bỏ qua {tt['bo']}"
                             f" / {tt['tong']} việc.")
        _cap_nhat_ke_hoach(c, dot_id)
    elif con == 0 and r["trang_thai"] == "huy" and not r["xong_luc"]:
        c.execute("UPDATE dot_chay SET xong_luc=? WHERE id=?", (now, dot_id))
        _cap_nhat_ke_hoach(c, dot_id)


def lay_dot(dot_id, kem_viec: bool = True) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM dot_chay WHERE id=?", (_int(dot_id),)).fetchone()
        if not r:
            return None
        d = _dong_dot(c, r)
        if kem_viec:
            d["viec"] = [ds._dong(x) for x in c.execute("SELECT * FROM viec WHERE dot_id=? ORDER BY id",
                                                        (d["id"],)).fetchall()]
            for x in d["viec"]:
                x["tep_ket_qua"] = ds_tep_ket_qua(x["id"])
            d["su_kien"] = [dict(x) for x in c.execute("SELECT * FROM su_kien WHERE dot_id=? ORDER BY id DESC LIMIT 50",
                                                       (d["id"],)).fetchall()]
    return d


def ds_dot(trang_thai: str = "", tu: float = 0, trang=1, moi_trang=50) -> dict:
    t, m, off = _trang(trang, moi_trang)
    q, a = " FROM dot_chay WHERE 1=1", []
    if trang_thai:
        q += " AND trang_thai=?"
        a.append(trang_thai)
    if tu:
        q += " AND tao_luc>=?"
        a.append(float(tu))
    with ds._db() as c:
        tong = c.execute("SELECT COUNT(*)" + q, a).fetchone()[0]
        muc = [_dong_dot(c, r) for r in c.execute("SELECT *" + q + " ORDER BY id DESC LIMIT ? OFFSET ?",
                                                  a + [m, off]).fetchall()]
    return {"tong": tong, "trang": t, "muc": muc}


def huy_dot(dot_id) -> dict:
    now = _now()
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT trang_thai FROM dot_chay WHERE id=?", (_int(dot_id),)).fetchone()
        if not r:
            raise ValueError(f"không có đợt chạy #{dot_id}")
        if r["trang_thai"] in ("hoan_tat", "huy"):
            raise ValueError("đợt này đã kết thúc, không huỷ được nữa")
        c.execute("UPDATE dot_chay SET trang_thai='huy' WHERE id=?", (_int(dot_id),))
        ids = [x[0] for x in c.execute("SELECT id FROM viec WHERE dot_id=? AND trang_thai IN ('cho_chay','tam_dung')",
                                       (_int(dot_id),))]
        c.execute("UPDATE viec SET lenh='huy' WHERE dot_id=? AND trang_thai='dang_chay'", (_int(dot_id),))
        for vid in ids:
            c.execute("UPDATE viec SET trang_thai='bo', thong_diep='đợt chạy bị huỷ', xong_luc=? WHERE id=?", (now, vid))
            sau_viec(c, vid)
        _cap_nhat_dot(c, _int(dot_id), now)
    return lay_dot(dot_id, kem_viec=False)


def lenh_viec(vid) -> dict:
    """Worker hỏi giữa các thao tác: {dung, tam_dung}. dung = huỷ (việc/đợt) hoặc việc không còn chạy."""
    with ds._db() as c:
        r = c.execute("SELECT v.trang_thai, v.lenh, d.trang_thai AS dtt FROM viec v LEFT JOIN dot_chay d ON d.id=v.dot_id "
                      "WHERE v.id=?", (_int(vid),)).fetchone()
    if not r:
        return {"dung": True, "tam_dung": False}
    lenh = r["lenh"] or ""
    dung = r["trang_thai"] != "dang_chay" or r["dtt"] == "huy" or lenh == "huy"
    return {"dung": dung, "tam_dung": (not dung) and lenh == "tam_dung"}


def can_dung(vid) -> bool:
    return lenh_viec(vid)["dung"]


DIEU_KHIEN = ("tam_dung", "tiep_tuc", "huy")


def dieu_khien_viec(vid, hanh_dong: str) -> dict:
    """Nút trên từng dòng tài khoản: tạm dừng / tiếp tục / huỷ MỘT việc (không đụng cả đợt).

    - Việc chưa chạy: tạm dừng = giữ lại không giao cho máy; tiếp tục = trả về hàng chờ; huỷ = bỏ.
    - Việc đang chạy: ghi lệnh, máy nhà đọc ở lần hỏi kế tiếp (vài giây) rồi đứng chờ / chạy tiếp / dừng.
    Trả việc sau khi đổi. Raise ValueError câu tiếng Việt."""
    if hanh_dong not in DIEU_KHIEN:
        raise ValueError("hành động phải là tam_dung, tiep_tuc hoặc huy")
    now = _now()
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT id, trang_thai, lenh, dot_id FROM viec WHERE id=?", (_int(vid),)).fetchone()
        if not r:
            raise ValueError(f"không có việc #{vid}")
        tt, lenh = r["trang_thai"], r["lenh"] or ""
        if tt in ("xong", "loi", "bo"):
            raise ValueError("việc này đã kết thúc")
        if hanh_dong == "tam_dung":
            if tt in ("cho_chay", "cho_duyet"):
                c.execute("UPDATE viec SET trang_thai='tam_dung', lenh='' WHERE id=?", (r["id"],))
            elif tt == "dang_chay":
                c.execute("UPDATE viec SET lenh='tam_dung' WHERE id=?", (r["id"],))
        elif hanh_dong == "tiep_tuc":
            if tt == "tam_dung":
                c.execute("UPDATE viec SET trang_thai='cho_chay', lenh='' WHERE id=?", (r["id"],))
            elif tt == "dang_chay" and lenh == "tam_dung":
                c.execute("UPDATE viec SET lenh='' WHERE id=?", (r["id"],))
        else:
            if tt in ("cho_chay", "tam_dung", "cho_duyet"):
                c.execute("UPDATE viec SET trang_thai='bo', lenh='', thong_diep='Bạn đã huỷ việc này', xong_luc=? "
                          "WHERE id=?", (now, r["id"]))
                sau_viec(c, r["id"])
            else:
                c.execute("UPDATE viec SET lenh='huy' WHERE id=?", (r["id"],))
        if r["dot_id"]:
            _cap_nhat_dot(c, r["dot_id"], now)
    return ds.lay_viec(vid)


def dieu_khien_dot(dot_id, hanh_dong: str) -> dict:
    """Tạm dừng / tiếp tục cả đợt = áp cho mọi việc chưa kết thúc của đợt."""
    if hanh_dong not in ("tam_dung", "tiep_tuc"):
        raise ValueError("hành động phải là tam_dung hoặc tiep_tuc")
    with ds._db() as c:
        ids = [x[0] for x in c.execute("SELECT id FROM viec WHERE dot_id=? AND trang_thai IN "
                                       "('cho_chay','tam_dung','dang_chay')", (_int(dot_id),))]
    for vid in ids:
        try:
            dieu_khien_viec(vid, hanh_dong)
        except ValueError:
            pass
    return lay_dot(dot_id, kem_viec=False)


# ------------------------------------------------------------------ lịch hẹn

def _cron(expr: str) -> str:
    import cron_util
    expr = str(expr or "").strip()
    if not expr:
        raise ValueError("thiếu lịch (cron), ví dụ '15 8 * * *' = 8:15 mỗi ngày")
    try:
        return cron_util.validate_cron(expr)
    except Exception as e:
        raise ValueError(f"lịch cron không hợp lệ: {e}")


def _lan_ke(expr: str, sau: float) -> float:
    import cron_util
    return cron_util.cron_next(expr, sau, _tz())


def tao_lich(*, kich_ban, nick, tham_so, cron, ten="", song_song=1, chay_an=False) -> dict:
    expr = _cron(cron)
    now = _now()
    with ds._khoa, ds._db() as c:
        m, ts = _kiem_mau(c, kich_ban, tham_so)
        nicks = _tim_nick_ds(c, nick)
        ten = _chu(ten, 120) or f"{m['ten']} · {len(nicks)} nick"
        cur = c.execute("INSERT INTO lich_hen(ten, kich_ban, nick, tham_so, song_song, cron, bat, lan_ke, so_lan, "
                        "so_loi, tao_luc, chay_an) VALUES(?,?,?,?,?,?,1,?,0,0,?,?)",
                        (ten, m["id"], _dj([n["id"] for n in nicks]), _dj(ts),
                         max(1, min(ds.SONG_SONG_TRAN, _int(song_song, 1))), expr, _lan_ke(expr, now), now,
                         int(bool(chay_an))))
        lid = cur.lastrowid
    return lay_lich(lid)


def _dong_lich(r) -> dict:
    import cron_util
    d = dict(r)
    d["nick"] = _j(d.get("nick"), [])
    d["tham_so"] = _j(d.get("tham_so"), {})
    d["bat"] = bool(d.get("bat"))
    d["so_nick"] = len(d["nick"])
    d["ten_mau"] = _ten_mau(d.get("kich_ban") or "")
    d["mo_ta_lich"] = cron_util.describe_cron(d.get("cron") or "", "vi")
    return d


def lay_lich(lid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM lich_hen WHERE id=?", (_int(lid),)).fetchone()
    return _dong_lich(r) if r else None


def ds_lich() -> list:
    with ds._db() as c:
        return [_dong_lich(r) for r in c.execute("SELECT * FROM lich_hen ORDER BY id DESC").fetchall()]


def sua_lich(lid, *, bat=None, ten=None, cron=None, nick=None, tham_so=None, song_song=None, chay_an=None) -> dict:
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT * FROM lich_hen WHERE id=?", (_int(lid),)).fetchone()
        if not r:
            raise ValueError(f"không có lịch hẹn #{lid}")
        now = _now()
        expr = r["cron"]
        if cron is not None:
            expr = _cron(cron)
            c.execute("UPDATE lich_hen SET cron=?, lan_ke=? WHERE id=?", (expr, _lan_ke(expr, now), r["id"]))
        if ten is not None:
            c.execute("UPDATE lich_hen SET ten=? WHERE id=?", (_chu(ten, 120) or r["ten"], r["id"]))
        if nick is not None:
            nicks = _tim_nick_ds(c, nick)
            c.execute("UPDATE lich_hen SET nick=? WHERE id=?", (_dj([n["id"] for n in nicks]), r["id"]))
        if tham_so is not None:
            _, ts = _kiem_mau(c, r["kich_ban"], tham_so)
            c.execute("UPDATE lich_hen SET tham_so=? WHERE id=?", (_dj(ts), r["id"]))
        if song_song is not None:
            c.execute("UPDATE lich_hen SET song_song=? WHERE id=?",
                      (max(1, min(ds.SONG_SONG_TRAN, _int(song_song, 1))), r["id"]))
        if chay_an is not None:
            c.execute("UPDATE lich_hen SET chay_an=? WHERE id=?", (int(bool(chay_an)), r["id"]))
        if bat is not None:
            c.execute("UPDATE lich_hen SET bat=? WHERE id=?", (int(bool(bat)), r["id"]))
            if bat and not r["bat"]:     # bật lại: tính lần kế từ bây giờ, không chạy bù
                c.execute("UPDATE lich_hen SET lan_ke=? WHERE id=?", (_lan_ke(expr, now), r["id"]))
    return lay_lich(lid)


def xoa_lich(lid) -> bool:
    with ds._khoa, ds._db() as c:
        return c.execute("DELETE FROM lich_hen WHERE id=?", (_int(lid),)).rowcount > 0


def chay_lich(lid, tinh_lan_ke: bool = False) -> dict:
    """Tạo một đợt từ lịch. `tinh_lan_ke` = do vòng nền gọi lúc tới giờ (tính lần kế tiếp)."""
    l = lay_lich(lid)
    if not l:
        raise ValueError(f"không có lịch hẹn #{lid}")
    now = _now()
    try:
        dot = tao_dot(kich_ban=l["kich_ban"], nick=l["nick"], tham_so=l["tham_so"], ten=l["ten"],
                      song_song=l["song_song"], chay_an=bool(l.get("chay_an")), nguon="lich", lich_id=l["id"])
        loi = ""
    except ValueError as e:
        dot, loi = None, str(e)
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE lich_hen SET lan_truoc=?, so_lan=so_lan+1, so_loi=so_loi+?, loi_cuoi=? WHERE id=?",
                  (now, 1 if loi else 0, loi[:300], l["id"]))
        if tinh_lan_ke:
            c.execute("UPDATE lich_hen SET lan_ke=? WHERE id=?", (_lan_ke(l["cron"], now), l["id"]))
    if loi:
        bao("Lịch hẹn không chạy được", f"{l['ten']}: {loi}")
        raise ValueError(loi)
    return dot


def vong_nen(now: Optional[float] = None) -> list:
    """Một nhịp của vòng nền 30 giây: lịch tới giờ -> đợt; nháp quá hạn -> het_han.
    Trả danh sách đợt vừa tạo (để routes đánh thức máy)."""
    now = now if now is not None else _now()
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE ban_nhap SET trang_thai='het_han' WHERE trang_thai='cho_duyet' AND het_han IS NOT NULL "
                  "AND het_han < ?", (now,))
        den = [r["id"] for r in c.execute("SELECT id FROM lich_hen WHERE bat=1 AND lan_ke IS NOT NULL AND lan_ke<=?",
                                          (now,)).fetchall()]
    ra = []
    for lid in den:
        try:
            ra.append(chay_lich(lid, tinh_lan_ke=True))
        except ValueError:
            pass
        except Exception as e:     # một lịch hỏng không được giết cả vòng
            import sys
            print(f"[doi-social] lịch #{lid} lỗi: {type(e).__name__}: {e}", file=sys.stderr)
    return ra


# ------------------------------------------------------------------ sự kiện + nhật ký trực tiếp

def _viec_cua_may(c, vid, may_id: str) -> dict:
    r = c.execute("SELECT * FROM viec WHERE id=?", (_int(vid),)).fetchone()
    if not r or r["may_id"] != may_id:
        raise ValueError("việc không thuộc máy này")
    return ds._dong(r)


def viec_cua_may(vid, may_id: str) -> dict:
    with ds._db() as c:
        return _viec_cua_may(c, vid, may_id)


def ghi_su_kien(vid, may_id: str, d: dict) -> dict:
    """Worker báo một thao tác. Trả {con_lai, dung}. Raise ValueError nếu sai."""
    kq = str(d.get("ket_qua") or "")
    if kq not in KET_QUA_SK:
        raise ValueError("ket_qua phải là thanh_cong | bo_qua | loi | thong_tin")
    hd = _chu(d.get("hanh_dong"), 40)
    ma = _chu(d.get("ma"), 30)
    now = _now()
    with ds._khoa, ds._db() as c:
        v = _viec_cua_may(c, vid, may_id)
        ts = v.get("tham_so") or {}
        nen = ts.get("nen_tang") or (kb.THEO_ID.get(v["ky_nang"]) or {}).get("nen_tang") or ""
        _ghi_sk(c, viec=v, hanh_dong=hd, ket_qua=kq, chi_tiet=d.get("chi_tiet") or "", link=d.get("link") or "",
                nhom=d.get("nhom") or "", san_pham=d.get("san_pham") or "", ma=ma, luc=now)
        meta = _meta(c, v["nick_id"])
        meta["lan_chay"] = now
        if ma in MA_CANH_BAO and nen:
            moi = meta["canh_bao"].get(nen) != ma
            meta["canh_bao"][nen] = ma
            if moi:
                bao("Nick cần bạn xử lý", f"Nick {v['nick_ten']} {MA_CANH_BAO[ma]} trên {TEN_NEN_TANG.get(nen, nen)}. "
                                          "Mở profile trong GPM để xử lý.")
        elif kq == "thanh_cong" and nen in meta["canh_bao"]:
            meta["canh_bao"].pop(nen, None)
        _luu_meta(c, meta)
        hds = list((kb.THEO_ID.get(v["ky_nang"]) or {}).get("hanh_dong") or ts.get("hanh_dong") or [])
        if hd and hd in kb.HANH_DONG and hd not in hds:     # hành động lạ (vd dang_nhap): ghi, không đếm
            hds.append(hd)
        con = _han_muc(c, v["nick_id"], nen, hds, None, now)
        dung = v["trang_thai"] != "dang_chay"
        if v.get("dot_id"):
            r = c.execute("SELECT trang_thai FROM dot_chay WHERE id=?", (v["dot_id"],)).fetchone()
            dung = dung or bool(r and r["trang_thai"] == "huy")
    return {"con_lai": con, "dung": dung}


def ghi_buoc(vid, dong: str) -> None:
    q = _BUOC.setdefault(int(vid), deque(maxlen=30))
    q.append({"luc": _now(), "dong": _chu(dong, 500)})
    if len(_BUOC) > 500:
        for k in list(_BUOC)[:100]:
            _BUOC.pop(k, None)


def dang_chay() -> list:
    with ds._db() as c:
        ds_v = [ds._dong(r) for r in c.execute("SELECT * FROM viec WHERE trang_thai='dang_chay' ORDER BY bat_dau").fetchall()]
    for v in ds_v:
        b = list(_BUOC.get(int(v["id"])) or [])
        v["nhat_ky"] = b
        v["buoc_cuoi"] = b[-1]["dong"] if b else ""
        v["ten_mau"] = _ten_mau(v["ky_nang"])
    return ds_v


def hom_nay_theo_nick() -> list:
    dau = _dau_ngay()
    ra = {}
    with ds._db() as c:
        for r in c.execute("SELECT nick_id, nick_ten, hanh_dong, ket_qua, COUNT(*) n FROM su_kien WHERE luc>=? "
                           "GROUP BY nick_id, hanh_dong, ket_qua", (dau,)):
            d = ra.setdefault(r["nick_id"], {"nick_id": r["nick_id"], "nick_ten": r["nick_ten"], "thanh_cong": 0,
                                             "bo_qua": 0, "loi": 0, "_hd": {}})
            if r["ket_qua"] in ("thanh_cong", "bo_qua", "loi"):
                d[r["ket_qua"]] += r["n"]
            if r["ket_qua"] == "thanh_cong" and r["hanh_dong"]:
                d["_hd"][r["hanh_dong"]] = d["_hd"].get(r["hanh_dong"], 0) + r["n"]
    out = []
    for d in ra.values():
        hd = d.pop("_hd")
        d["chi_tiet"] = " · ".join(f"{kb.HANH_DONG.get(k, k)} {n}" for k, n in sorted(hd.items(), key=lambda x: -x[1]))
        out.append(d)
    return sorted(out, key=lambda x: -(x["thanh_cong"] + x["bo_qua"] + x["loi"]))


def _loc_su_kien(tu=None, den=None, nick="", tinh_nang="", ket_qua="", kich_ban="", dot=None) -> tuple:
    q, a = " FROM su_kien WHERE 1=1", []
    if tu:
        q += " AND luc>=?"
        a.append(float(tu))
    if den:
        q += " AND luc<=?"
        a.append(float(den))
    for cot, v in (("nick_id", nick), ("tinh_nang", tinh_nang), ("ket_qua", ket_qua), ("kich_ban", kich_ban)):
        if v:
            q += f" AND {cot}=?"
            a.append(str(v))
    if dot:
        q += " AND dot_id=?"
        a.append(_int(dot))
    return q, a


def ds_su_kien(tu=None, den=None, nick="", tinh_nang="", ket_qua="", kich_ban="", dot=None, trang=1,
               moi_trang=50) -> dict:
    t, m, off = _trang(trang, moi_trang)
    q, a = _loc_su_kien(tu, den, nick, tinh_nang, ket_qua, kich_ban, dot)
    with ds._db() as c:
        tong = c.execute("SELECT COUNT(*)" + q, a).fetchone()[0]
        muc = [dict(r) for r in c.execute("SELECT *" + q + " ORDER BY luc DESC, id DESC LIMIT ? OFFSET ?",
                                          a + [m, off]).fetchall()]
    for x in muc:
        x["nhan_hanh_dong"] = kb.HANH_DONG.get(x.get("hanh_dong") or "", x.get("hanh_dong") or "")
    return {"tong": tong, "trang": t, "muc": muc}


def su_kien_csv(tu=None, den=None, nick="", tinh_nang="", ket_qua="", kich_ban="", dot=None) -> str:
    """Dòng thời gian ra CSV (UTF-8 có BOM để Excel đọc đúng tiếng Việt)."""
    import csv
    import io
    from datetime import datetime
    q, a = _loc_su_kien(tu, den, nick, tinh_nang, ket_qua, kich_ban, dot)
    nhan_kq = {"thanh_cong": "Thành công", "bo_qua": "Bỏ qua", "loi": "Lỗi", "thong_tin": "Thông tin"}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Thời gian", "Nick", "Nền tảng", "Mẫu", "Tính năng", "Hành động", "Kết quả", "Chi tiết",
                "Nhóm", "Sản phẩm", "Link"])
    tz = _tz()
    with ds._db() as c:
        for r in c.execute("SELECT *" + q + " ORDER BY luc DESC LIMIT 50000", a):
            w.writerow([datetime.fromtimestamp(r["luc"] or 0, tz).strftime("%Y-%m-%d %H:%M:%S"), r["nick_ten"],
                        TEN_NEN_TANG.get(r["nen_tang"], r["nen_tang"]), _ten_mau(r["kich_ban"] or ""), r["tinh_nang"],
                        kb.HANH_DONG.get(r["hanh_dong"] or "", r["hanh_dong"] or ""),
                        nhan_kq.get(r["ket_qua"], r["ket_qua"]), r["chi_tiet"], r["nhom"], r["san_pham"], r["link"]])
    return "﻿" + buf.getvalue()


def _thu_muc_kq(vid) -> Path:
    return ds._goc / "ket-qua" / str(int(vid))


def luu_tep_ket_qua(vid, may_id: str, ten: str, du_lieu) -> dict:
    """Worker gửi tệp kết quả (CSV ≤ 10MB). `du_lieu` = bytes hoặc đường dẫn tạm."""
    viec_cua_may(vid, may_id)
    ten = _ten_an_toan(ten)
    if Path(ten).suffix.lower() not in KQ_DUOI:
        raise ValueError("tệp kết quả chỉ nhận .csv hoặc .txt")
    import re
    ten = re.sub(r"[^A-Za-z0-9._-]", "_", ten)[:100]
    d = _thu_muc_kq(vid)
    d.mkdir(parents=True, exist_ok=True)
    p = d / ten
    if isinstance(du_lieu, (bytes, bytearray)):
        if len(du_lieu) > KQ_TOI_DA:
            raise ValueError("tệp kết quả quá lớn (tối đa 10MB)")
        p.write_bytes(bytes(du_lieu))
    else:
        if Path(du_lieu).stat().st_size > KQ_TOI_DA:
            raise ValueError("tệp kết quả quá lớn (tối đa 10MB)")
        shutil.move(str(du_lieu), str(p))
    return {"ten": ten, "co": p.stat().st_size}


def ds_tep_ket_qua(vid) -> list:
    d = _thu_muc_kq(vid)
    if not d.is_dir():
        return []
    return [{"ten": p.name, "co": p.stat().st_size} for p in sorted(d.iterdir()) if p.is_file()]


def duong_tep_ket_qua(vid, ten: str) -> Optional[Path]:
    ten = str(ten or "")
    if not ten or "/" in ten or "\\" in ten or ".." in ten or ten.startswith("."):
        return None
    p = _thu_muc_kq(_int(vid, 0)) / ten
    return p if p.is_file() else None


def lich_su(trang_thai: str = "", kich_ban: str = "", trang=1, moi_trang=50) -> dict:
    t, m, off = _trang(trang, moi_trang)
    q, a = " FROM viec v LEFT JOIN dot_chay d ON d.id=v.dot_id WHERE 1=1", []
    if trang_thai:
        q += " AND v.trang_thai=?"
        a.append(trang_thai)
    if kich_ban:
        q += " AND v.ky_nang=?"
        a.append(kich_ban)
    with ds._db() as c:
        tong = c.execute("SELECT COUNT(*)" + q, a).fetchone()[0]
        rows = c.execute("SELECT v.*, d.ten AS ten_dot" + q + " ORDER BY v.id DESC LIMIT ? OFFSET ?",
                         a + [m, off]).fetchall()
    muc = []
    for r in rows:
        v = ds._dong(r)
        v["ten_mau"] = _ten_mau(v["ky_nang"])
        v["tep_ket_qua"] = ds_tep_ket_qua(v["id"])
        muc.append(v)
    return {"tong": tong, "trang": t, "muc": muc}


# ------------------------------------------------------------------ trí nhớ chống lặp

def da_lam(nick_id: str, khoa: str, ca_doi: bool = False) -> bool:
    khoa = _chu(khoa, 500)
    with ds._db() as c:
        if ca_doi:
            return c.execute("SELECT 1 FROM da_lam WHERE khoa=? LIMIT 1", (khoa,)).fetchone() is not None
        return c.execute("SELECT 1 FROM da_lam WHERE nick_id=? AND khoa=?", (nick_id, khoa)).fetchone() is not None


def ghi_da_lam(nick_id: str, khoa: str) -> None:
    khoa = _chu(khoa, 500)
    if not khoa:
        raise ValueError("thiếu khoá")
    with ds._khoa, ds._db() as c:
        c.execute("INSERT OR REPLACE INTO da_lam(nick_id, khoa, luc) VALUES(?,?,?)", (nick_id, khoa, _now()))


def nick_thuoc_may(nick_id: str, may_id: str) -> bool:
    with ds._db() as c:
        return c.execute("SELECT 1 FROM nick WHERE id=? AND may_id=?", (nick_id, may_id)).fetchone() is not None


def bai_doi_da_dang(vid, may_id: str) -> list:
    """Bài đội đã đăng 2-48 giờ qua (trừ bài của chính nick), mỗi bài chưa quá 3 nick tương tác."""
    now = _now()
    with ds._db() as c:
        v = _viec_cua_may(c, vid, may_id)
        nen = (v.get("tham_so") or {}).get("nen_tang") or ""
        q = ("SELECT link, nick_id, nick_ten, nhom, san_pham, MAX(luc) luc FROM su_kien WHERE ket_qua='thanh_cong' "
             "AND hanh_dong IN ('dang_nhom','dang_tuong') AND link<>'' AND luc BETWEEN ? AND ? AND nick_id<>?")
        a = [now - 48 * 3600, now - 2 * 3600, v["nick_id"]]
        if nen:
            q += " AND nen_tang=?"
            a.append(nen)
        ra = []
        for r in c.execute(q + " GROUP BY link ORDER BY luc DESC LIMIT 100", a).fetchall():
            n = c.execute("SELECT COUNT(DISTINCT nick_id) FROM su_kien WHERE link=? AND ket_qua='thanh_cong' "
                          "AND hanh_dong IN ('thich','binh_luan')", (r["link"],)).fetchone()[0]
            if n < 3:
                d = dict(r)
                d["so_nick_tuong_tac"] = n
                ra.append(d)
    return ra


# ------------------------------------------------------------------ kho bài

def _ten_an_toan(ten: str) -> str:
    ten = str(ten or "").replace("\\", "/").split("/")[-1].replace("\x00", "").strip()
    return (ten.lstrip(".") or "tep")[:120]


def kiem_duoi_kho(ten: str) -> str:
    duoi = Path(_ten_an_toan(ten)).suffix.lower()
    if duoi not in KHO_DUOI:
        raise ValueError(f"kho chỉ nhận ảnh/video ({', '.join(sorted(KHO_DUOI))}), không nhận '{duoi or 'tệp không đuôi'}'")
    return duoi


def _thu_muc_kho(bid) -> Path:
    return ds._goc / "kho" / str(int(bid))


def them_kho(*, nen_tang: str, nick_id: str = "", tieu_de: str = "", noi_dung: str = "", tep=None) -> list:
    """Thêm bài vào kho. `tep` = [(ten_goc, đường_dẫn_tạm)] (tệp tạm bị chuyển đi).
    `noi_dung` có dòng '===' tách nhiều bài. Trả danh sách id bài mới."""
    if nen_tang not in TEN_NEN_TANG:
        raise ValueError("nền tảng không hợp lệ")
    nick_id = _chu(nick_id, 80)
    tep = list(tep or [])
    for ten, _ in tep:
        kiem_duoi_kho(ten)
    phan, cur = [], []
    for dong in str(noi_dung or "").replace("\r\n", "\n").split("\n"):
        if dong.strip() == "===":
            phan.append("\n".join(cur).strip())
            cur = []
        else:
            cur.append(dong)
    phan.append("\n".join(cur).strip())
    phan = [p for p in phan if p]
    if any(len(p) > ds.CHU_TOI_DA for p in phan):
        raise ValueError(f"một bài quá dài (tối đa {ds.CHU_TOI_DA} ký tự)")
    if not phan and not tep:
        raise ValueError("bài cần có chữ hoặc ít nhất một ảnh/video")
    if len(phan) > 1 and tep and len(tep) != len(phan):
        raise ValueError(f"nhiều bài kèm tệp: số tệp ({len(tep)}) phải bằng số bài ({len(phan)}) để ghép mỗi bài một tệp")
    if len(phan) > 1:
        bai = [(p, [tep[i]] if tep else []) for i, p in enumerate(phan)]
    elif not phan and len(tep) > 1 and nen_tang in ("tiktok", "youtube"):
        bai = [("", [t]) for t in tep]              # video không chữ: mỗi tệp một bài
    else:
        bai = [(phan[0] if phan else "", tep)]
    if len(bai) > 500:
        raise ValueError("tối đa 500 bài mỗi lần thêm")
    with ds._db() as c:
        if nick_id and not c.execute("SELECT 1 FROM nick WHERE id=?", (nick_id,)).fetchone():
            raise ValueError(f"không thấy nick '{nick_id}'")
    ids = []
    for nd, ds_tep in bai:
        with ds._khoa, ds._db() as c:
            bid = c.execute("INSERT INTO kho_bai(nen_tang, nick_id, tieu_de, noi_dung, tep, trang_thai, luc_tao) "
                            "VALUES(?,?,?,?,?,?,?)", (nen_tang, nick_id, _chu(tieu_de, 300), nd, "[]", "cho",
                                                      _now())).lastrowid
        luu = []
        thu_muc = _thu_muc_kho(bid)
        for i, (ten, tam) in enumerate(ds_tep):
            thu_muc.mkdir(parents=True, exist_ok=True)
            d = thu_muc / f"{i:02d}{kiem_duoi_kho(ten)}"
            shutil.move(str(tam), str(d))
            luu.append({"ten": _ten_an_toan(ten), "luu": d.name, "co": d.stat().st_size})
        with ds._db() as c:
            c.execute("UPDATE kho_bai SET tep=? WHERE id=?", (_dj(luu), bid))
        ids.append(bid)
    return ids


def _dong_kho(r) -> dict:
    d = dict(r)
    d["tep"] = _j(d.get("tep"), [])
    return d


def kho_tong(nen_tang: str = "") -> dict:
    q, a = "SELECT nick_id, trang_thai, COUNT(*) n FROM kho_bai", []
    if nen_tang:
        q += " WHERE nen_tang=?"
        a.append(nen_tang)
    chung = {"con": 0, "dang_giu": 0, "da_dang": 0, "loi": 0}
    theo = {}
    ten = {n["id"]: n["ten"] for n in ds.ds_nick()}
    with ds._db() as c:
        for r in c.execute(q + " GROUP BY nick_id, trang_thai", a):
            dich = chung if not r["nick_id"] else theo.setdefault(
                r["nick_id"], {"nick_id": r["nick_id"], "nick_ten": ten.get(r["nick_id"], r["nick_id"]),
                               "con": 0, "dang_giu": 0, "da_dang": 0, "loi": 0})
            k = {"cho": "con"}.get(r["trang_thai"], r["trang_thai"])
            if k in dich:
                dich[k] += r["n"]
    return {"chung": chung, "theo_nick": sorted(theo.values(), key=lambda x: x["nick_ten"] or "")}


def ds_kho(nen_tang: str = "", nick=None, trang_thai: str = "", trang=1, moi_trang=50) -> dict:
    t, m, off = _trang(trang, moi_trang)
    q, a = " FROM kho_bai WHERE 1=1", []
    if nen_tang:
        q += " AND nen_tang=?"
        a.append(nen_tang)
    if nick is not None:
        q += " AND nick_id=?"
        a.append(str(nick))
    if trang_thai:
        q += " AND trang_thai=?"
        a.append(trang_thai)
    with ds._db() as c:
        tong = c.execute("SELECT COUNT(*)" + q, a).fetchone()[0]
        muc = [_dong_kho(r) for r in c.execute("SELECT *" + q + " ORDER BY id LIMIT ? OFFSET ?", a + [m, off])]
    return {"tong": tong, "trang": t, "muc": muc}


def lay_bai_kho(bid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM kho_bai WHERE id=?", (_int(bid),)).fetchone()
    return _dong_kho(r) if r else None


def xoa_kho(bid) -> bool:
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT trang_thai FROM kho_bai WHERE id=?", (_int(bid),)).fetchone()
        if not r:
            return False
        if r["trang_thai"] == "dang_giu":
            raise ValueError("bài đang được máy ở nhà đăng, đợi xong rồi xoá")
        c.execute("DELETE FROM kho_bai WHERE id=?", (_int(bid),))
    shutil.rmtree(str(_thu_muc_kho(_int(bid))), ignore_errors=True)
    return True


def tra_lai_kho(bid) -> dict:
    with ds._khoa, ds._db() as c:
        n = c.execute("UPDATE kho_bai SET trang_thai='cho', giu_boi_viec=NULL, loi='' WHERE id=? "
                      "AND trang_thai IN ('loi','dang_giu')", (_int(bid),)).rowcount
    if not n:
        raise ValueError("chỉ trả lại được bài đang lỗi hoặc đang giữ")
    return lay_bai_kho(bid)


def duong_tep_kho(bid, luu: str) -> Optional[Path]:
    luu = str(luu or "")
    if not luu or "/" in luu or "\\" in luu or ".." in luu or luu.startswith("."):
        return None
    p = _thu_muc_kho(_int(bid, 0)) / luu
    return p if p.is_file() else None


def lay_kho_cho_viec(vid, may_id: str) -> Optional[dict]:
    """Giữ một bài kho cho việc (theo nền tảng + kho chung/theo nick). Đã giữ thì trả lại bài đó."""
    with ds._khoa, ds._db() as c:
        v = _viec_cua_may(c, vid, may_id)
        if v["trang_thai"] != "dang_chay":
            raise ValueError("việc không còn đang chạy")
        r = c.execute("SELECT * FROM kho_bai WHERE giu_boi_viec=? AND trang_thai='dang_giu'", (v["id"],)).fetchone()
        if r:
            return _dong_kho(r)
        ts = v.get("tham_so") or {}
        nen = ts.get("nen_tang") or ""
        theo_nick = (ts.get("tham_so") or {}).get("kho") == "theo_nick"
        r = c.execute("SELECT * FROM kho_bai WHERE nen_tang=? AND nick_id=? AND trang_thai='cho' ORDER BY id LIMIT 1",
                      (nen, v["nick_id"] if theo_nick else "")).fetchone()
        if not r:
            return None
        c.execute("UPDATE kho_bai SET trang_thai='dang_giu', giu_boi_viec=? WHERE id=?", (v["id"], r["id"]))
        r = c.execute("SELECT * FROM kho_bai WHERE id=?", (r["id"],)).fetchone()
    return _dong_kho(r)


def bai_kho_cua_may(bid, may_id: str) -> Optional[dict]:
    """Bài kho đang được một việc của máy này giữ (để Worker tải tệp)."""
    with ds._db() as c:
        r = c.execute("SELECT k.* FROM kho_bai k JOIN viec v ON v.id=k.giu_boi_viec WHERE k.id=? AND v.may_id=?",
                      (_int(bid), may_id)).fetchone()
    return _dong_kho(r) if r else None


def ket_qua_kho(bid, may_id: str, ok: bool, da_bam_dang: bool, link: str = "", loi: str = "",
                hong: bool = False) -> dict:
    """ok -> da_dang; lỗi trước khi bấm Đăng -> về hàng chờ; lỗi SAU khi bấm -> loi (không tự đăng lại);
    `hong` (bài hỏng: tệp lỗi, quá dài...) -> loi ngay, không quay lại hàng chờ."""
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT k.* FROM kho_bai k JOIN viec v ON v.id=k.giu_boi_viec WHERE k.id=? AND v.may_id=? "
                      "AND k.trang_thai='dang_giu'", (_int(bid), may_id)).fetchone()
        if not r:
            raise ValueError("bài này không do việc của máy này giữ")
        if ok:
            c.execute("UPDATE kho_bai SET trang_thai='da_dang', giu_boi_viec=NULL, luc_dang=?, link=?, loi='' WHERE id=?",
                      (_now(), _chu(link, 500), r["id"]))
        elif hong:
            c.execute("UPDATE kho_bai SET trang_thai='loi', giu_boi_viec=NULL, loi=? WHERE id=?",
                      ("bài hỏng: " + (_chu(loi, 480) or "không rõ lý do"), r["id"]))
        elif not da_bam_dang:
            c.execute("UPDATE kho_bai SET trang_thai='cho', giu_boi_viec=NULL, loi=? WHERE id=?", (_chu(loi, 500), r["id"]))
        else:
            c.execute("UPDATE kho_bai SET trang_thai='loi', giu_boi_viec=NULL, loi=? WHERE id=?",
                      (_chu(loi, 500) or "lỗi sau khi đã bấm Đăng", r["id"]))
    return lay_bai_kho(bid)


# ------------------------------------------------------------------ bản nháp

def _dong_nhap(r) -> dict:
    d = dict(r)
    d["tep"] = _j(d.get("tep"), [])
    d["ket_qua"] = _j(d.get("ket_qua"), {})
    d["chay_thu"] = bool(d.get("chay_thu"))
    d["muc_tieu"] = _j(d.get("muc_tieu"), {})
    return d


def _thu_muc_nhap(nid) -> Path:
    return ds._goc / "nhap" / str(int(nid))


def _muc_tieu(v) -> dict:
    if v in (None, ""):
        return {}
    if not isinstance(v, dict):
        raise ValueError("muc_tieu phải là object")
    s = _dj(v)
    if len(s) > 20000:
        raise ValueError("muc_tieu quá lớn")
    return v


def them_tep_nhap(nid, tep) -> list:
    """Gắn tệp ảnh/video cho nháp. `tep` = [(ten, bytes | đường_dẫn_tạm)]. Trả danh sách tệp của nháp."""
    tep = list(tep or [])
    for ten, _ in tep:
        kiem_duoi_kho(ten)
    n = lay_ban_nhap(nid)
    if not n:
        raise ValueError(f"không có nháp #{nid}")
    ds_tep = list(n["tep"])
    if len(ds_tep) + len(tep) > 20:
        raise ValueError("nháp tối đa 20 tệp")
    thu_muc = _thu_muc_nhap(nid)
    for ten, nguon in tep:
        thu_muc.mkdir(parents=True, exist_ok=True)
        d = thu_muc / f"{len(ds_tep):02d}{kiem_duoi_kho(ten)}"
        if isinstance(nguon, (bytes, bytearray)):
            if len(nguon) > KHO_TOI_DA:
                raise ValueError(f"tệp '{_ten_an_toan(ten)}' quá lớn")
            d.write_bytes(bytes(nguon))
        else:
            shutil.move(str(nguon), str(d))
        ds_tep.append({"ten": _ten_an_toan(ten), "luu": d.name, "co": d.stat().st_size})
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE ban_nhap SET tep=? WHERE id=?", (_dj(ds_tep), _int(nid)))
    return ds_tep


def duong_tep_nhap(nid, luu: str) -> Optional[Path]:
    luu = str(luu or "")
    if not luu or "/" in luu or "\\" in luu or ".." in luu or luu.startswith("."):
        return None
    p = _thu_muc_nhap(_int(nid, 0)) / luu
    return p if p.is_file() else None


def nhap_cua_may(nid, may_id: str) -> Optional[dict]:
    """Nháp đang được một việc của máy này giữ (để Worker tải tệp)."""
    with ds._db() as c:
        r = c.execute("SELECT b.* FROM ban_nhap b JOIN viec v ON v.id=b.giu_boi_viec WHERE b.id=? AND v.may_id=?",
                      (_int(nid), may_id)).fetchone()
    return _dong_nhap(r) if r else None


def tao_ban_nhap(*, loai: str, noi_dang: str, noi_dung: str, nick_id: str = "", nick_ten: str = "", nhom: str = "",
                 link_goc: str = "", bai_goc: str = "", ly_do: str = "", san_pham_id="", het_han_gio=None,
                 viec_tao: str = "", chay_thu: bool = False, tep=None, muc_tieu=None) -> dict:
    """`tep` = [(ten, bytes | đường_dẫn_tạm)] ảnh/video kèm nháp."""
    if loai not in LOAI_NHAP:
        raise ValueError("loại nháp phải là binh_luan | bai_dang | tra_loi")
    if noi_dang not in NOI_DANG:
        raise ValueError("nơi đăng không hợp lệ")
    noi_dung = str(noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("nháp rỗng")
    if len(noi_dung) > ds.CHU_TOI_DA:
        raise ValueError(f"nháp quá dài (tối đa {ds.CHU_TOI_DA} ký tự)")
    mt = _muc_tieu(muc_tieu)
    tep = list(tep or [])
    for ten, _ in tep:
        kiem_duoi_kho(ten)
    gio = 72 if loai == "bai_dang" else 18
    if het_han_gio not in (None, ""):
        gio = max(1, min(24 * 30, _int(het_han_gio, gio)))
    now = _now()
    with ds._khoa, ds._db() as c:
        nid = c.execute("INSERT INTO ban_nhap(loai, noi_dang, nick_id, nick_ten, nhom, link_goc, bai_goc, ly_do, "
                        "noi_dung, san_pham_id, trang_thai, tao_luc, het_han, viec_tao, ket_qua, tep, chay_thu, muc_tieu) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,'cho_duyet',?,?,?,'{}','[]',?,?)",
                        (loai, noi_dang, _chu(nick_id, 80), _chu(nick_ten, 200), _chu(nhom, 300), _chu(link_goc, 500),
                         _chu(bai_goc, 4000), _chu(ly_do, 1000), noi_dung, _chu(san_pham_id, 40), now,
                         now + gio * 3600, _chu(viec_tao, 40), int(bool(chay_thu)), _dj(mt))).lastrowid
    if tep:
        try:
            them_tep_nhap(nid, tep)
        except Exception:
            with ds._db() as c:
                c.execute("DELETE FROM ban_nhap WHERE id=?", (nid,))
            shutil.rmtree(str(_thu_muc_nhap(nid)), ignore_errors=True)
            raise
    return lay_ban_nhap(nid)


def tao_ban_nhap_tu_may(vid, may_id: str, d: dict) -> dict:
    v = viec_cua_may(vid, may_id)
    ts = v.get("tham_so") or {}
    sp = d.get("san_pham_id") or (ts.get("tham_so") or {}).get("san_pham") or ""
    import base64
    tep = []
    raw = d.get("tep") or []
    if not isinstance(raw, list):
        raise ValueError("tep phải là danh sách {ten, b64}")
    for t in raw[:20]:
        if not isinstance(t, dict) or not t.get("ten") or not t.get("b64"):
            raise ValueError("mỗi tệp cần {ten, b64}")
        kiem_duoi_kho(t["ten"])
        try:
            tep.append((str(t["ten"]), base64.b64decode(str(t["b64"]).split(",")[-1])))
        except Exception:
            raise ValueError(f"tệp '{_ten_an_toan(t['ten'])}' base64 hỏng")
    return tao_ban_nhap(loai=str(d.get("loai") or ""), noi_dang=str(d.get("noi_dang") or ""),
                        noi_dung=d.get("noi_dung") or "", nick_id=v["nick_id"], nick_ten=v["nick_ten"],
                        nhom=d.get("nhom") or "", link_goc=d.get("link_goc") or "", bai_goc=d.get("bai_goc") or "",
                        ly_do=d.get("ly_do") or "", san_pham_id=sp, het_han_gio=d.get("het_han_gio"),
                        viec_tao=str(v["id"]), chay_thu=bool(v.get("chay_thu")), tep=tep, muc_tieu=d.get("muc_tieu"))


def lay_ban_nhap(nid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM ban_nhap WHERE id=?", (_int(nid),)).fetchone()
    return _dong_nhap(r) if r else None


def ds_ban_nhap(trang_thai: str = "cho_duyet", noi_dang: str = "", san_pham: str = "", trang=1, moi_trang=50) -> dict:
    t, m, off = _trang(trang, moi_trang)
    q, a = " FROM ban_nhap WHERE 1=1", []
    if trang_thai:
        q += " AND trang_thai=?"
        a.append(trang_thai)
    q_nd, a_nd = q, list(a)
    if san_pham:
        q += " AND san_pham_id=?"
        a.append(str(san_pham))
        q_nd, a_nd = q, list(a)
    if noi_dang:
        q += " AND noi_dang=?"
        a.append(noi_dang)
    with ds._db() as c:
        tong = c.execute("SELECT COUNT(*)" + q, a).fetchone()[0]
        muc = [_dong_nhap(r) for r in c.execute("SELECT *" + q + " ORDER BY id DESC LIMIT ? OFFSET ?", a + [m, off])]
        dem = {k: 0 for k in TT_NHAP}
        for r in c.execute("SELECT trang_thai, COUNT(*) n FROM ban_nhap GROUP BY trang_thai"):
            dem[r["trang_thai"]] = r["n"]
        dem_nd = {}
        for r in c.execute("SELECT noi_dang, COUNT(*) n" + q_nd + " GROUP BY noi_dang", a_nd):
            dem_nd[r["noi_dang"]] = r["n"]
    return {"tong": tong, "trang": t, "muc": muc, "dem": dem, "dem_noi_dang": dem_nd}


def _hd_nhap(n: dict) -> list:
    if n["loai"] == "tra_loi":
        return ["tra_loi_binh_luan"]
    if n["loai"] == "binh_luan":
        return ["binh_luan_nhom" if n["noi_dang"] == "fb_nhom" else "binh_luan"]
    return [{"fb_nhom": "dang_nhom", "fb_trang": "dang_trang"}.get(n["noi_dang"], "dang_tuong")]


def duyet_ban_nhap(nid, dong_y: bool) -> dict:
    """Đồng ý: nháp có nick -> tạo việc `dang_ban_nhap` cho đúng nick (cho_chay, nháp được giữ cho
    việc đó); nháp chưa gán nick -> nằm ở da_duyet chờ mẫu đăng bài AI lấy. Từ chối: da_bo."""
    now = _now()
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT * FROM ban_nhap WHERE id=?", (_int(nid),)).fetchone()
        if not r:
            raise ValueError(f"không có nháp #{nid}")
        if r["trang_thai"] != "cho_duyet":
            raise ValueError(f"nháp #{nid} đang ở trạng thái '{r['trang_thai']}', không duyệt lại được")
        n = _dong_nhap(r)
        if not dong_y:
            c.execute("UPDATE ban_nhap SET trang_thai='da_bo' WHERE id=?", (n["id"],))
            return lay_ban_nhap(nid) | {"viec_id": None}
        vid = None
        if n["nick_id"]:
            nk = c.execute("SELECT * FROM nick WHERE id=? ORDER BY cap_nhat DESC", (n["nick_id"],)).fetchone()
            if not nk:
                raise ValueError(f"nick của nháp không còn trên máy ở nhà ({n['nick_ten'] or n['nick_id']})")
            nen = _nen_tang_noi_dang(n["noi_dang"])
            vts = {"kich_ban": "dang_ban_nhap", "nen_tang": nen, "chay_thu": False, "dot_id": None, "han_muc": {},
                   "nghi_giay": [], "hanh_dong": _hd_nhap(n),
                   "tham_so": {"ban_nhap_id": n["id"], "loai": n["loai"], "noi_dang": n["noi_dang"],
                               "link_goc": n["link_goc"], "nhom": n["nhom"], "noi_dung": n["noi_dung"],
                               "tep": [{"ten": t.get("ten"), "luu": t.get("luu")} for t in n["tep"]],
                               "muc_tieu": n["muc_tieu"]}}
            vid = c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc, "
                            "duyet_luc, nguon, chay_thu) VALUES(?,?,?,?,?,'cho_chay',?,?,'duyet',0)",
                            ("dang_ban_nhap", nk["may_id"], nk["id"], nk["ten"], _dj(vts), now, now)).lastrowid
        c.execute("UPDATE ban_nhap SET trang_thai='da_duyet', giu_boi_viec=? WHERE id=?", (vid, n["id"]))
    return lay_ban_nhap(nid) | {"viec_id": vid}


def sua_ban_nhap(nid, noi_dung: str) -> dict:
    noi_dung = str(noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("nội dung trống")
    if len(noi_dung) > ds.CHU_TOI_DA:
        raise ValueError(f"nội dung quá dài (tối đa {ds.CHU_TOI_DA} ký tự)")
    with ds._khoa, ds._db() as c:
        n = c.execute("UPDATE ban_nhap SET noi_dung=? WHERE id=? AND trang_thai IN ('cho_duyet','het_han','loi')",
                      (noi_dung, _int(nid))).rowcount
        if n:   # sửa một nháp hết hạn/lỗi = đưa lại vào hàng chờ duyệt
            c.execute("UPDATE ban_nhap SET trang_thai='cho_duyet', het_han=MAX(COALESCE(het_han,0), ?) WHERE id=?",
                      (_now() + 18 * 3600, _int(nid)))
    if not n:
        raise ValueError("chỉ sửa được nháp đang chờ duyệt, hết hạn hoặc lỗi")
    return lay_ban_nhap(nid)


def lay_ban_nhap_cho_viec(vid, may_id: str, noi_dang: str = "", san_pham: str = "") -> Optional[dict]:
    with ds._khoa, ds._db() as c:
        v = _viec_cua_may(c, vid, may_id)
        if v["trang_thai"] != "dang_chay":
            raise ValueError("việc không còn đang chạy")
        q = ("SELECT * FROM ban_nhap WHERE trang_thai='da_duyet' AND giu_boi_viec IS NULL "
             "AND (nick_id='' OR nick_id=?)")
        a = [v["nick_id"]]
        if noi_dang:
            q += " AND noi_dang=?"
            a.append(noi_dang)
        if san_pham:
            q += " AND san_pham_id=?"
            a.append(str(san_pham))
        r = c.execute(q + " ORDER BY (nick_id='') ASC, id LIMIT 1", a).fetchone()
        if not r:
            return None
        c.execute("UPDATE ban_nhap SET giu_boi_viec=? WHERE id=?", (v["id"], r["id"]))
    return lay_ban_nhap(r["id"])


def ket_qua_ban_nhap(nid, may_id: str, ok: bool, link: str = "", loi: str = "") -> dict:
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT b.* FROM ban_nhap b JOIN viec v ON v.id=b.giu_boi_viec WHERE b.id=? AND v.may_id=? "
                      "AND b.trang_thai='da_duyet'", (_int(nid), may_id)).fetchone()
        if not r:
            raise ValueError("nháp này không do việc của máy này giữ")
        kq = {"link": _chu(link, 500), "loi": _chu(loi, 500), "luc": _now()}
        c.execute("UPDATE ban_nhap SET trang_thai=?, giu_boi_viec=NULL, ket_qua=? WHERE id=?",
                  ("da_dang" if ok else "loi", _dj(kq), r["id"]))
    return lay_ban_nhap(nid)


def dem_nhap_cho_duyet() -> int:
    with ds._db() as c:
        return c.execute("SELECT COUNT(*) FROM ban_nhap WHERE trang_thai='cho_duyet'").fetchone()[0]


# ------------------------------------------------------------------ kiến thức

_KT_COT = ("loai", "ten", "mo_ta", "gia", "link", "tu_khoa", "giong_van", "dan_rieng", "trang_thai")


def _kiem_kt(d: dict, cu: Optional[dict] = None) -> dict:
    ra = dict(cu or {"loai": "san_pham", "trang_thai": "dang_dung"})
    for k in _KT_COT:
        if k in d and d[k] is not None:
            ra[k] = _chu(d[k], 20000 if k in ("mo_ta", "dan_rieng") else 2000)
    if ra.get("loai") not in ("san_pham", "chu_de"):
        raise ValueError("loại phải là san_pham hoặc chu_de")
    if ra.get("trang_thai") not in ("dang_dung", "cho_duyet"):
        raise ValueError("trạng thái phải là dang_dung hoặc cho_duyet")
    if not ra.get("ten"):
        raise ValueError("thiếu tên sản phẩm/chủ đề")
    # Nối với bộ não MinMin (26.10.187): tệp wiki/ghi chú gắn tay + cờ tự tra bộ não theo ngữ cảnh.
    if d.get("nguon_bo_nao") is not None:
        ds_tep = d["nguon_bo_nao"]
        if isinstance(ds_tep, str):
            ds_tep = [x.strip() for x in ds_tep.splitlines() if x.strip()]
        ra["nguon_bo_nao"] = [str(x)[:500] for x in (ds_tep or []) if str(x).strip()][:20]
    if d.get("tu_tra_bo_nao") is not None:
        ra["tu_tra_bo_nao"] = 1 if (d["tu_tra_bo_nao"] and str(d["tu_tra_bo_nao"]).lower() not in ("0", "false")) else 0
    return ra


def _ghi_bo_nao(c, kid, k: dict) -> None:
    if "nguon_bo_nao" in k:
        nb = k["nguon_bo_nao"]
        c.execute("UPDATE kien_thuc SET nguon_bo_nao=? WHERE id=?",
                  (_dj(nb if isinstance(nb, list) else []), _int(kid)))
    if "tu_tra_bo_nao" in k:
        c.execute("UPDATE kien_thuc SET tu_tra_bo_nao=? WHERE id=?", (int(bool(k["tu_tra_bo_nao"])), _int(kid)))


def tao_kien_thuc(d: dict) -> dict:
    k = _kiem_kt(d or {})
    with ds._khoa, ds._db() as c:
        kid = c.execute("INSERT INTO kien_thuc(" + ",".join(_KT_COT) + ", tao_luc) VALUES(" + ",".join("?" * len(_KT_COT))
                        + ",?)", [k.get(x, "") for x in _KT_COT] + [_now()]).lastrowid
        _ghi_bo_nao(c, kid, k)
    return lay_kien_thuc(kid)


def sua_kien_thuc(kid, d: dict) -> dict:
    cu = lay_kien_thuc(kid, day_du=False)
    if not cu:
        raise ValueError(f"không có kiến thức #{kid}")
    k = _kiem_kt(d or {}, cu)
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE kien_thuc SET " + ",".join(f"{x}=?" for x in _KT_COT) + " WHERE id=?",
                  [k.get(x, "") for x in _KT_COT] + [_int(kid)])
        _ghi_bo_nao(c, kid, k)
    return lay_kien_thuc(kid)


def xoa_kien_thuc(kid) -> bool:
    with ds._khoa, ds._db() as c:
        n = c.execute("DELETE FROM kien_thuc WHERE id=?", (_int(kid),)).rowcount
        c.execute("DELETE FROM tai_lieu WHERE kt_id=?", (_int(kid),))
        c.execute("DELETE FROM hoi_dap WHERE kt_id=?", (_int(kid),))
    return n > 0


def ds_kien_thuc() -> list:
    with ds._db() as c:
        ra = []
        for r in c.execute("SELECT * FROM kien_thuc ORDER BY loai, ten").fetchall():
            d = dict(r)
            try:
                d["nguon_bo_nao"] = json.loads(d.get("nguon_bo_nao") or "[]")
            except Exception:
                d["nguon_bo_nao"] = []
            d["tu_tra_bo_nao"] = bool(d.get("tu_tra_bo_nao", 1))
            d["so_tai_lieu"] = c.execute("SELECT COUNT(*) FROM tai_lieu WHERE kt_id=?", (d["id"],)).fetchone()[0]
            d["so_hoi_dap"] = c.execute("SELECT COUNT(*) FROM hoi_dap WHERE kt_id=?", (d["id"],)).fetchone()[0]
            d["cho_ban"] = c.execute("SELECT COUNT(*) FROM hoi_dap WHERE kt_id=? AND trang_thai='cho_ban'",
                                     (d["id"],)).fetchone()[0]
            d["so_nhom"] = c.execute("SELECT COUNT(*) FROM nhom_fb WHERE san_pham_id=? AND trang_thai='da_duyet'",
                                     (str(d["id"]),)).fetchone()[0]
            d["so_nhom_co_nick"] = c.execute("SELECT COUNT(*) FROM nhom_fb WHERE san_pham_id=? AND trang_thai='da_duyet' "
                                             "AND tinh_trang_vao LIKE '%da_vao%'", (str(d["id"]),)).fetchone()[0]
            ra.append(d)
    return ra


def lay_kien_thuc(kid, day_du: bool = True) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM kien_thuc WHERE id=?", (_int(kid),)).fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            d["nguon_bo_nao"] = json.loads(d.get("nguon_bo_nao") or "[]")
        except Exception:
            d["nguon_bo_nao"] = []
        d["tu_tra_bo_nao"] = bool(d.get("tu_tra_bo_nao", 1))
        if day_du:
            d["tai_lieu"] = [dict(x) for x in c.execute("SELECT id, ten, noi_dung FROM tai_lieu WHERE kt_id=? ORDER BY id",
                                                        (d["id"],))]
            d["hoi_dap"] = [dict(x) for x in c.execute("SELECT * FROM hoi_dap WHERE kt_id=? ORDER BY trang_thai DESC, id",
                                                       (d["id"],))]
            d["nhom"] = [_dong_nhom(x) for x in c.execute("SELECT * FROM nhom_fb WHERE san_pham_id=? ORDER BY id",
                                                           (str(d["id"]),))]
    return d


def kien_thuc_cho_ai(kid) -> Optional[dict]:
    """Dạng gọn đưa vào prompt: chỉ hỏi đáp đã trả lời, tài liệu cắt ngắn."""
    if kid in (None, ""):
        return None
    k = lay_kien_thuc(kid, day_du=True)
    if not k:
        return None
    k["tai_lieu"] = [{"ten": t["ten"], "noi_dung": (t["noi_dung"] or "")[:20000]} for t in k["tai_lieu"][:10]]
    k["hoi_dap"] = [{"hoi": h["hoi"], "dap": h["dap"]} for h in k["hoi_dap"] if h["trang_thai"] == "da_tra_loi"][:100]
    k.pop("nhom", None)
    return k


def trich_chu_tai_lieu(ten: str, du_lieu: bytes) -> str:
    """Chữ từ tệp tài liệu (.txt/.md, .docx bằng stdlib, .pdf nếu có pypdf). Raise ValueError."""
    duoi = Path(_ten_an_toan(ten)).suffix.lower()
    if duoi not in TL_DUOI:
        raise ValueError(f"tài liệu chỉ nhận {', '.join(sorted(TL_DUOI))}")
    if len(du_lieu) > TL_TOI_DA:
        raise ValueError("tài liệu quá lớn (tối đa 5MB)")
    if duoi in (".txt", ".md"):
        for ma in ("utf-8-sig", "utf-16", "cp1258", "latin-1"):
            try:
                return du_lieu.decode(ma)[:TL_CHU_TOI_DA]
            except UnicodeDecodeError:
                continue
    if duoi == ".docx":
        import io
        import re
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(du_lieu)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
        except Exception:
            raise ValueError("không đọc được tệp .docx (tệp hỏng?)")
        xml = re.sub(r"</w:p>", "\n", xml)
        chu = re.sub(r"<[^>]+>", "", xml)
        import html
        return html.unescape(chu).strip()[:TL_CHU_TOI_DA]
    try:
        import io
        import pypdf
    except Exception:
        raise ValueError("máy chủ chưa có thư viện đọc PDF: chép chữ trong PDF rồi dán vào ô nội dung")
    try:
        rd = pypdf.PdfReader(io.BytesIO(du_lieu))
        chu = "\n".join((p.extract_text() or "") for p in rd.pages[:200])
    except Exception:
        raise ValueError("không đọc được tệp PDF")
    if not chu.strip():
        raise ValueError("PDF không có lớp chữ (ảnh scan): chép chữ rồi dán vào ô nội dung")
    return chu[:TL_CHU_TOI_DA]


def them_tai_lieu(kid, ten: str, noi_dung: str) -> dict:
    noi_dung = str(noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("tài liệu rỗng")
    with ds._khoa, ds._db() as c:
        if not c.execute("SELECT 1 FROM kien_thuc WHERE id=?", (_int(kid),)).fetchone():
            raise ValueError(f"không có kiến thức #{kid}")
        tid = c.execute("INSERT INTO tai_lieu(kt_id, ten, noi_dung) VALUES(?,?,?)",
                        (_int(kid), _chu(ten, 200) or "Tài liệu", noi_dung[:TL_CHU_TOI_DA])).lastrowid
    return {"id": tid, "kt_id": _int(kid), "ten": _chu(ten, 200) or "Tài liệu"}


def xoa_tai_lieu(tid) -> bool:
    with ds._khoa, ds._db() as c:
        return c.execute("DELETE FROM tai_lieu WHERE id=?", (_int(tid),)).rowcount > 0


def them_hoi_dap(kid, hoi: str, dap: str = "", nguon: str = "chu") -> dict:
    hoi = _chu(hoi, 2000)
    if not hoi:
        raise ValueError("thiếu câu hỏi")
    dap = _chu(dap, 5000)
    with ds._khoa, ds._db() as c:
        if not c.execute("SELECT 1 FROM kien_thuc WHERE id=?", (_int(kid),)).fetchone():
            raise ValueError(f"không có kiến thức #{kid}")
        hid = c.execute("INSERT INTO hoi_dap(kt_id, hoi, dap, trang_thai, nguon, luc) VALUES(?,?,?,?,?,?)",
                        (_int(kid), hoi, dap, "da_tra_loi" if dap else "cho_ban", _chu(nguon, 60), _now())).lastrowid
        return dict(c.execute("SELECT * FROM hoi_dap WHERE id=?", (hid,)).fetchone())


def ghi_hoi_cho_ban(kid, hoi: str, nguon: str = "") -> Optional[dict]:
    """AI gặp câu chưa có thông tin: ghi Hỏi đáp chờ chủ trả lời (không trùng câu đang chờ)."""
    hoi = _chu(hoi, 2000)
    if not hoi or _int(kid) < 0:
        return None
    with ds._db() as c:
        if not c.execute("SELECT 1 FROM kien_thuc WHERE id=?", (_int(kid),)).fetchone():
            return None
        if c.execute("SELECT 1 FROM hoi_dap WHERE kt_id=? AND hoi=? AND trang_thai='cho_ban'", (_int(kid), hoi)).fetchone():
            return None
    return them_hoi_dap(kid, hoi, "", nguon or "ai")


def tra_loi_hoi_dap(hid, dap: str) -> dict:
    dap = _chu(dap, 5000)
    if not dap:
        raise ValueError("thiếu câu trả lời")
    with ds._khoa, ds._db() as c:
        if not c.execute("UPDATE hoi_dap SET dap=?, trang_thai='da_tra_loi' WHERE id=?", (dap, _int(hid))).rowcount:
            raise ValueError(f"không có hỏi đáp #{hid}")
        return dict(c.execute("SELECT * FROM hoi_dap WHERE id=?", (_int(hid),)).fetchone())


def xoa_hoi_dap(hid) -> bool:
    with ds._khoa, ds._db() as c:
        return c.execute("DELETE FROM hoi_dap WHERE id=?", (_int(hid),)).rowcount > 0


# ------------------------------------------------------------------ nhóm FB

def _dong_nhom(r) -> dict:
    d = dict(r)
    d["nick_tuong_tac"] = _j(d.get("nick_tuong_tac"), [])
    d["tinh_trang_vao"] = _j(d.get("tinh_trang_vao"), {})
    d["can_quet"] = not d.get("lan_quet") or (_now() - d["lan_quet"]) > (d.get("quet_lai_gio") or 24) * 3600
    return d


def _chuan_link_nhom(link: str) -> str:
    link = str(link or "").strip()
    if not link.startswith("https://") or "facebook.com" not in link:
        raise ValueError(f"link nhóm phải dạng https://...facebook.com/groups/... ({link[:60]})")
    return link.split("?")[0].split("#")[0].rstrip("/")[:300]


def ds_nhom(san_pham: str = "") -> list:
    q, a = "SELECT * FROM nhom_fb", []
    if san_pham:
        q += " WHERE san_pham_id=?"
        a.append(str(san_pham))
    with ds._db() as c:
        return [_dong_nhom(r) for r in c.execute(q + " ORDER BY id", a).fetchall()]


def them_nhom(san_pham_id, links, ten: str = "", trang_thai: str = "da_duyet") -> list:
    if isinstance(links, str):
        links = [x for x in links.replace(",", "\n").splitlines() if x.strip()]
    links = [_chuan_link_nhom(x) for x in (links or [])][:500]
    if not links:
        raise ValueError("chưa có link nhóm")
    if trang_thai not in TT_NHOM:
        trang_thai = "da_duyet"
    sp = str(san_pham_id or "")
    with ds._khoa, ds._db() as c:
        if not c.execute("SELECT 1 FROM kien_thuc WHERE id=?", (_int(sp),)).fetchone():
            raise ValueError("chọn sản phẩm/chủ đề trong Kiến thức cho Agent trước")
        ids = []
        for l in links:
            cur = c.execute("INSERT OR IGNORE INTO nhom_fb(san_pham_id, link, ten, trang_thai) VALUES(?,?,?,?)",
                            (sp, l, _chu(ten, 300) if len(links) == 1 else "", trang_thai))
            if cur.rowcount:
                ids.append(cur.lastrowid)
    return ids


def sua_nhom(gid, *, trang_thai=None, nick_chinh=None, nick_tuong_tac=None, quet_lai_gio=None, ten=None,
             ghi_chu=None) -> dict:
    with ds._khoa, ds._db() as c:
        if not c.execute("SELECT 1 FROM nhom_fb WHERE id=?", (_int(gid),)).fetchone():
            raise ValueError(f"không có nhóm #{gid}")
        if trang_thai is not None:
            if trang_thai not in TT_NHOM:
                raise ValueError("trạng thái nhóm phải là cho_duyet | da_duyet | den")
            c.execute("UPDATE nhom_fb SET trang_thai=? WHERE id=?", (trang_thai, _int(gid)))
        if nick_chinh is not None:
            c.execute("UPDATE nhom_fb SET nick_chinh=? WHERE id=?", (_chu(nick_chinh, 80), _int(gid)))
        if nick_tuong_tac is not None:
            if not isinstance(nick_tuong_tac, list):
                raise ValueError("nick tương tác phải là danh sách")
            c.execute("UPDATE nhom_fb SET nick_tuong_tac=? WHERE id=?",
                      (_dj([_chu(x, 80) for x in nick_tuong_tac][:3]), _int(gid)))
        if quet_lai_gio is not None:
            c.execute("UPDATE nhom_fb SET quet_lai_gio=? WHERE id=?", (max(1, min(24 * 30, _int(quet_lai_gio, 24))), _int(gid)))
        if ten is not None:
            c.execute("UPDATE nhom_fb SET ten=? WHERE id=?", (_chu(ten, 300), _int(gid)))
        if ghi_chu is not None:
            c.execute("UPDATE nhom_fb SET ghi_chu=? WHERE id=?", (_chu(ghi_chu, 1000), _int(gid)))
        return _dong_nhom(c.execute("SELECT * FROM nhom_fb WHERE id=?", (_int(gid),)).fetchone())


def xoa_nhom(gid) -> bool:
    with ds._khoa, ds._db() as c:
        return c.execute("DELETE FROM nhom_fb WHERE id=?", (_int(gid),)).rowcount > 0


def _vai(n: dict, nick_id: str) -> str:
    if n.get("nick_chinh") == nick_id:
        return "chinh"
    if nick_id in (n.get("nick_tuong_tac") or []):
        return "tuong_tac"
    return "chua_gan"


def nhom_cho_viec(vid, may_id: str) -> list:
    v = viec_cua_may(vid, may_id)
    sp = str(((v.get("tham_so") or {}).get("tham_so") or {}).get("san_pham") or "")
    if not sp:
        return []
    ra = []
    for n in ds_nhom(sp):
        if n["trang_thai"] == "den":
            continue
        n["vai"] = _vai(n, v["nick_id"])
        ra.append(n)
    return ra


def bao_nhom(vid, may_id: str, d: dict) -> Optional[dict]:
    v = viec_cua_may(vid, may_id)
    sp = str(((v.get("tham_so") or {}).get("tham_so") or {}).get("san_pham") or d.get("san_pham_id") or "")
    if not sp:
        raise ValueError("việc này không gắn sản phẩm nên không ghi được nhóm")
    link = _chuan_link_nhom(d.get("link"))
    tt = d.get("tinh_trang")
    if tt is not None and tt not in TT_VAO:
        raise ValueError("tinh_trang phải là da_vao | cho_duyet | bi_tu_choi")
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT * FROM nhom_fb WHERE san_pham_id=? AND link=?", (sp, link)).fetchone()
        if not r:
            if not d.get("them_moi"):
                raise ValueError("nhóm chưa có trong Kho group FB (gửi them_moi=true để thêm)")
            c.execute("INSERT INTO nhom_fb(san_pham_id, link, ten, trang_thai) VALUES(?,?,?,'cho_duyet')",
                      (sp, link, _chu(d.get("ten"), 300)))
            r = c.execute("SELECT * FROM nhom_fb WHERE san_pham_id=? AND link=?", (sp, link)).fetchone()
        n = _dong_nhom(r)
        if d.get("ten") and not n["ten"]:
            c.execute("UPDATE nhom_fb SET ten=? WHERE id=?", (_chu(d.get("ten"), 300), n["id"]))
        if tt:
            n["tinh_trang_vao"][v["nick_id"]] = tt
            c.execute("UPDATE nhom_fb SET tinh_trang_vao=? WHERE id=?", (_dj(n["tinh_trang_vao"]), n["id"]))
            if tt == "da_vao":
                if not n["nick_chinh"]:
                    c.execute("UPDATE nhom_fb SET nick_chinh=? WHERE id=?", (v["nick_id"], n["id"]))
                elif n["nick_chinh"] != v["nick_id"] and v["nick_id"] not in n["nick_tuong_tac"] \
                        and len(n["nick_tuong_tac"]) < 3:
                    c.execute("UPDATE nhom_fb SET nick_tuong_tac=? WHERE id=?",
                              (_dj(n["nick_tuong_tac"] + [v["nick_id"]]), n["id"]))
        if d.get("lan_quet"):
            c.execute("UPDATE nhom_fb SET lan_quet=? WHERE id=?", (_now(), n["id"]))
        return _dong_nhom(c.execute("SELECT * FROM nhom_fb WHERE id=?", (n["id"],)).fetchone())


# ------------------------------------------------------------------ hội thoại

def _dong_ht(r) -> dict:
    d = dict(r)
    d["tiem_nang"] = bool(d.get("tiem_nang"))
    return d


def ghi_hoi_thoai(vid, may_id: str, d: dict) -> dict:
    """Worker gửi hội thoại đọc được. Trả {id, bot_duoc_tra_loi}."""
    v = viec_cua_may(vid, may_id)
    link = _chu(d.get("khach_link"), 500)
    if not link:
        raise ValueError("thiếu khach_link")
    tt = d.get("trang_thai")
    if tt is not None and tt not in TT_HOI_THOAI:
        raise ValueError("trang_thai hội thoại không hợp lệ")
    now = _now()
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT * FROM hoi_thoai WHERE nick_id=? AND khach_link=?", (v["nick_id"], link)).fetchone()
        if not r:
            hid = c.execute("INSERT INTO hoi_thoai(nick_id, nick_ten, khach_ten, khach_link, san_pham_id, trang_thai, "
                            "cap_nhat) VALUES(?,?,?,?,?,'bot_dang_lo',?)",
                            (v["nick_id"], v["nick_ten"], _chu(d.get("khach_ten"), 200), link,
                             _chu(d.get("san_pham_id"), 40), now)).lastrowid
            r = c.execute("SELECT * FROM hoi_thoai WHERE id=?", (hid,)).fetchone()
        ht = dict(r)
        cu = {(x["tu"], x["noi_dung"]) for x in c.execute("SELECT tu, noi_dung FROM tin_nhan WHERE ht_id=? "
                                                         "ORDER BY id DESC LIMIT 200", (ht["id"],))}
        co_khach_moi = False
        for t in (d.get("tin") or [])[:200]:
            if not isinstance(t, dict):
                continue
            tu = t.get("tu") if t.get("tu") in ("khach", "bot", "chu") else "khach"
            nd = _chu(t.get("noi_dung"), 4000)
            if not nd or (tu, nd) in cu:
                continue
            cu.add((tu, nd))
            luc = t.get("luc")
            c.execute("INSERT INTO tin_nhan(ht_id, tu, noi_dung, luc) VALUES(?,?,?,?)",
                      (ht["id"], tu, nd, float(luc) if isinstance(luc, (int, float)) else now))
            co_khach_moi = co_khach_moi or tu == "khach"
        moi_tt = ht["trang_thai"]
        if tt:
            moi_tt = tt
        elif co_khach_moi and ht["trang_thai"] == "da_xu_ly":
            moi_tt = "bot_dang_lo"
        sdt = _chu(d.get("sdt"), 30)
        c.execute("UPDATE hoi_thoai SET trang_thai=?, cap_nhat=?, khach_ten=COALESCE(NULLIF(?, ''), khach_ten), "
                  "san_pham_id=COALESCE(NULLIF(?, ''), san_pham_id), sdt=COALESCE(NULLIF(?, ''), sdt), "
                  "tiem_nang=MAX(tiem_nang, ?) WHERE id=?",
                  (moi_tt, now, _chu(d.get("khach_ten"), 200), _chu(d.get("san_pham_id"), 40), sdt,
                   1 if sdt else 0, ht["id"]))
        if moi_tt == "can_tra_loi_tay" and ht["trang_thai"] != "can_tra_loi_tay":
            bao("Khách cần bạn trả lời tay", f"{_chu(d.get('khach_ten'), 200) or ht['khach_ten']} nhắn nick {v['nick_ten']}.")
        duoc = moi_tt not in ("can_tra_loi_tay", "spam", "da_xu_ly") and (ht.get("nhuong_den") or 0) < now
    return {"id": ht["id"], "bot_duoc_tra_loi": bool(duoc)}


def danh_dau_hoi_thoai(nick_id: str, khach_link: str, *, sdt: str = "", can_tay: bool = False) -> None:
    """Sau khi AI trả lời tin nhắn: có SĐT -> khách tiềm năng; câu khó -> cần trả lời tay."""
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT * FROM hoi_thoai WHERE nick_id=? AND khach_link=?", (nick_id, _chu(khach_link, 500))).fetchone()
        if not r:
            return
        if sdt:
            c.execute("UPDATE hoi_thoai SET sdt=?, tiem_nang=1 WHERE id=?", (_chu(sdt, 30), r["id"]))
        if can_tay and r["trang_thai"] != "can_tra_loi_tay":
            c.execute("UPDATE hoi_thoai SET trang_thai='can_tra_loi_tay' WHERE id=?", (r["id"],))
            bao("Khách cần bạn trả lời tay", f"{r['khach_ten']} nhắn nick {r['nick_ten']}.")


def ds_hoi_thoai(tab: str = "tat_ca") -> dict:
    q = "SELECT h.*, (SELECT noi_dung FROM tin_nhan t WHERE t.ht_id=h.id ORDER BY id DESC LIMIT 1) tin_cuoi FROM hoi_thoai h"
    if tab == "can_tay":
        q += " WHERE h.trang_thai='can_tra_loi_tay'"
    elif tab == "tiem_nang":
        q += " WHERE h.tiem_nang=1"
    with ds._db() as c:
        muc = [_dong_ht(r) for r in c.execute(q + " ORDER BY h.cap_nhat DESC LIMIT 500").fetchall()]
        dem = {"can_tay": c.execute("SELECT COUNT(*) FROM hoi_thoai WHERE trang_thai='can_tra_loi_tay'").fetchone()[0],
               "tat_ca": c.execute("SELECT COUNT(*) FROM hoi_thoai").fetchone()[0],
               "tiem_nang": c.execute("SELECT COUNT(*) FROM hoi_thoai WHERE tiem_nang=1").fetchone()[0]}
    return {"muc": muc, "dem": dem}


def lay_hoi_thoai(hid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM hoi_thoai WHERE id=?", (_int(hid),)).fetchone()
        if not r:
            return None
        d = _dong_ht(r)
        d["tin"] = [dict(x) for x in c.execute("SELECT tu, noi_dung, luc FROM tin_nhan WHERE ht_id=? ORDER BY id", (d["id"],))]
    return d


def doi_hoi_thoai(hid, hanh_dong: str) -> dict:
    moi = {"cho_ai_tiep": "bot_dang_lo", "spam": "spam", "da_xu_ly": "da_xu_ly"}.get(hanh_dong)
    if not moi:
        raise ValueError("hành động phải là cho_ai_tiep | spam | da_xu_ly")
    with ds._khoa, ds._db() as c:
        n = c.execute("UPDATE hoi_thoai SET trang_thai=?, nhuong_den=CASE WHEN ?='bot_dang_lo' THEN 0 ELSE nhuong_den END "
                      "WHERE id=?", (moi, moi, _int(hid))).rowcount
    if not n:
        raise ValueError(f"không có hội thoại #{hid}")
    return lay_hoi_thoai(hid)


def tra_loi_tay(hid, noi_dung: str) -> dict:
    """Chủ tự gõ: tạo việc `fb_gui_tin` (cho_chay), ghi tin 'chu', bot nhường 12 giờ."""
    noi_dung = str(noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("tin nhắn trống")
    if len(noi_dung) > 4000:
        raise ValueError("tin nhắn quá dài (tối đa 4000 ký tự)")
    now = _now()
    with ds._khoa, ds._db() as c:
        h = c.execute("SELECT * FROM hoi_thoai WHERE id=?", (_int(hid),)).fetchone()
        if not h:
            raise ValueError(f"không có hội thoại #{hid}")
        nk = c.execute("SELECT * FROM nick WHERE id=? ORDER BY cap_nhat DESC", (h["nick_id"],)).fetchone()
        if not nk:
            raise ValueError("nick của hội thoại không còn trên máy ở nhà")
        vts = {"kich_ban": "fb_gui_tin", "nen_tang": "facebook", "chay_thu": False, "dot_id": None, "han_muc": {},
               "nghi_giay": [], "hanh_dong": ["nhan_tin"],
               "tham_so": {"khach_link": h["khach_link"], "noi_dung": noi_dung, "hoi_thoai_id": h["id"]}}
        vid = c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc, duyet_luc, "
                        "nguon, chay_thu) VALUES('fb_gui_tin',?,?,?,?,'cho_chay',?,?,'web',0)",
                        (nk["may_id"], nk["id"], nk["ten"], _dj(vts), now, now)).lastrowid
        c.execute("INSERT INTO tin_nhan(ht_id, tu, noi_dung, luc) VALUES(?,?,?,?)", (h["id"], "chu", noi_dung, now))
        c.execute("UPDATE hoi_thoai SET trang_thai='bot_dang_lo', nhuong_den=?, cap_nhat=? WHERE id=?",
                  (now + NHUONG_GIO * 3600, now, h["id"]))
    return {"hoi_thoai": lay_hoi_thoai(hid), "viec": ds.lay_viec(vid)}


def tao_kham_trang(nick: str, url: str, cuon: int = 2, trong: str = "", chon: str = "") -> dict:
    """Việc chẩn đoán: máy nhà mở `url` trong profile, cuộn, ghi dàn ý phần tử (vai trò, nhãn, chữ)
    thành tệp .txt gửi về. KHÔNG bấm gì. Dùng để sửa bộ chọn phần tử khi Facebook/TikTok đổi giao diện."""
    url = str(url or "").strip()
    if not url.startswith("https://"):
        raise ValueError("link phải bắt đầu bằng https://")
    now = _now()
    with ds._khoa, ds._db() as c:
        nicks = _tim_nick_ds(c, [nick])
        nk = nicks[0]
        vts = {"kich_ban": "kham_trang", "nen_tang": "", "chay_thu": True, "dot_id": None, "han_muc": {},
               "nghi_giay": [], "hanh_dong": [], "tham_so": {"url": url[:2000], "cuon": max(0, min(10, _int(cuon, 2))),
                                                          "trong": str(trong or "")[:300], "chon": str(chon or "")[:300]}}
        vid = c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc, duyet_luc, "
                        "nguon, chay_thu) VALUES('kham_trang',?,?,?,?,'cho_chay',?,?,'web',1)",
                        (nk["may_id"], nk["id"], nk["ten"], _dj(vts), now, now)).lastrowid
    return ds.lay_viec(vid)


# ------------------------------------------------------------------ kế hoạch + trợ lý

def _kiem_buoc(c, buoc) -> tuple:
    hop, bo = [], []
    for i, b in enumerate(buoc if isinstance(buoc, list) else []):
        if not isinstance(b, dict):
            bo.append(f"bước {i + 1}: sai dạng")
            continue
        try:
            m, ts = _kiem_mau(c, b.get("kich_ban"), b.get("tham_so") or {})
            nicks = _tim_nick_ds(c, b.get("nick") or [])
        except ValueError as e:
            bo.append(f"bước {i + 1} ({b.get('kich_ban')}): {e}")
            continue
        hop.append({"kich_ban": m["id"], "nick": [n["id"] for n in nicks], "tham_so": ts,
                    "ghi_chu": _chu(b.get("ghi_chu"), 500), "ten_mau": m["ten"]})
    return hop, bo


def tao_ke_hoach(*, mo_ta, buoc, nguon="web", chat_id="") -> dict:
    """Lưu kế hoạch chờ duyệt. Bước sai (mẫu lạ, tham số sai, nick không có) bị bỏ, ghi chú vào mô tả."""
    with ds._khoa, ds._db() as c:
        hop, bo = _kiem_buoc(c, buoc)
        if not hop:
            raise ValueError("kế hoạch không có bước nào hợp lệ" + (": " + "; ".join(bo[:3]) if bo else ""))
        mt = _chu(mo_ta, 2000) or "Kế hoạch của Trợ lý AI"
        if bo:
            mt += "\n(Đã bỏ " + str(len(bo)) + " bước sai: " + "; ".join(bo[:5]) + ")"
        kid = c.execute("INSERT INTO ke_hoach(mo_ta, buoc, trang_thai, nguon, chat_id, tao_luc, dot_ids) "
                        "VALUES(?,?,'cho_duyet',?,?,?,'[]')", (mt, _dj(hop), _chu(nguon, 20) or "web",
                                                                 _chu(chat_id, 60), _now())).lastrowid
    return lay_ke_hoach(kid)


def _dong_kh(c, r) -> dict:
    d = dict(r)
    d["buoc"] = _j(d.get("buoc"), [])
    d["dot_ids"] = _j(d.get("dot_ids"), [])
    for i, b in enumerate(d["buoc"]):
        did = d["dot_ids"][i] if i < len(d["dot_ids"]) else None
        b["dot_id"] = did
        if did:
            dr = c.execute("SELECT trang_thai FROM dot_chay WHERE id=?", (did,)).fetchone()
            b["trang_thai"] = dr["trang_thai"] if dr else "?"
            b["tien_trinh"] = _tien_trinh(c, did)
        else:
            b["trang_thai"] = "chuan_bi" if d["trang_thai"] in ("cho_duyet", "dang_chay") else d["trang_thai"]
    return d


def lay_ke_hoach(kid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM ke_hoach WHERE id=?", (_int(kid),)).fetchone()
        return _dong_kh(c, r) if r else None


def ds_ke_hoach(gioi: int = 50) -> list:
    with ds._db() as c:
        return [_dong_kh(c, r) for r in c.execute("SELECT * FROM ke_hoach ORDER BY id DESC LIMIT ?",
                                                  (max(1, min(200, int(gioi))),)).fetchall()]


def duyet_ke_hoach(kid, dong_y: bool) -> dict:
    """Đồng ý -> tạo một đợt (nguon=tro_ly) cho từng bước. Kế hoạch KHÔNG tự chạy khi chưa duyệt."""
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT * FROM ke_hoach WHERE id=?", (_int(kid),)).fetchone()
        if not r:
            raise ValueError(f"không có kế hoạch #{kid}")
        if r["trang_thai"] != "cho_duyet":
            raise ValueError(f"kế hoạch #{kid} đã ở trạng thái '{r['trang_thai']}'")
        if not dong_y:
            c.execute("UPDATE ke_hoach SET trang_thai='tu_choi' WHERE id=?", (r["id"],))
            return _dong_kh(c, c.execute("SELECT * FROM ke_hoach WHERE id=?", (r["id"],)).fetchone())
        c.execute("UPDATE ke_hoach SET trang_thai='dang_chay' WHERE id=?", (r["id"],))
        buoc = _j(r["buoc"], [])
    dot_ids, loi = [], []
    for i, b in enumerate(buoc):
        try:
            dot = tao_dot(kich_ban=b["kich_ban"], nick=b["nick"], tham_so=b.get("tham_so") or {},
                          ten=f"Kế hoạch #{kid} · bước {i + 1}", nguon="tro_ly")
            dot_ids.append(dot["id"])
        except ValueError as e:
            dot_ids.append(None)
            loi.append(f"bước {i + 1}: {e}")
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE ke_hoach SET dot_ids=? WHERE id=?", (_dj(dot_ids), _int(kid)))
        if not any(dot_ids):
            c.execute("UPDATE ke_hoach SET trang_thai='hoan_tat' WHERE id=?", (_int(kid),))
    kh = lay_ke_hoach(kid)
    kh["loi"] = loi
    return kh


def _cap_nhat_ke_hoach(c, dot_id: int) -> None:
    for r in c.execute("SELECT id, dot_ids FROM ke_hoach WHERE trang_thai='dang_chay'").fetchall():
        ids = [x for x in _j(r["dot_ids"], []) if x]
        if dot_id not in ids:
            continue
        xong = c.execute(f"SELECT COUNT(*) FROM dot_chay WHERE id IN ({','.join('?' * len(ids))}) "
                         "AND trang_thai IN ('hoan_tat','huy')", ids).fetchone()[0]
        if xong == len(ids):
            c.execute("UPDATE ke_hoach SET trang_thai='hoan_tat' WHERE id=?", (r["id"],))


def ghi_tro_ly(phien: str, vai: str, noi_dung: str, ke_hoach_id=None) -> None:
    with ds._khoa, ds._db() as c:
        c.execute("INSERT INTO tro_ly(phien, vai, noi_dung, ke_hoach_id, luc) VALUES(?,?,?,?,?)",
                  (_chu(phien, 60), "ai" if vai == "ai" else "nguoi", _chu(noi_dung, 20000), ke_hoach_id, _now()))


def lich_su_tro_ly(phien: str, gioi: int = 100) -> list:
    with ds._db() as c:
        rows = c.execute("SELECT * FROM tro_ly WHERE phien=? ORDER BY id DESC LIMIT ?",
                         (_chu(phien, 60), max(1, min(500, int(gioi))))).fetchall()
    return [dict(r) for r in reversed(rows)]


def ds_phien_tro_ly(gioi: int = 30) -> list:
    with ds._db() as c:
        rows = c.execute("SELECT phien, MIN(luc) bat_dau, MAX(luc) cuoi, COUNT(*) so_tin, "
                         "(SELECT noi_dung FROM tro_ly t2 WHERE t2.phien=t.phien AND vai='nguoi' ORDER BY id LIMIT 1) dau "
                         "FROM tro_ly t GROUP BY phien ORDER BY cuoi DESC LIMIT ?", (max(1, min(200, int(gioi))),)).fetchall()
    return [dict(r) | {"tieu_de": (r["dau"] or "")[:80]} for r in rows]


# ------------------------------------------------------------------ tổng quan

def san_sang_theo_mau() -> dict:
    """id mẫu -> có máy đã ghép nào báo làm được."""
    co = set()
    for m in ds.ds_may():
        co.update(m.get("kich_ban") or [])
    return {x["id"]: x["id"] in co for x in kb.MAU}


def danh_muc_kem_san_sang() -> dict:
    dm = kb.danh_muc()
    ss = san_sang_theo_mau()
    dm = dict(dm)
    dm["mau"] = [dict(m) | {"san_sang": ss.get(m["id"], False)} for m in kb.MAU]
    return dm


def tong_quan(ngay: int = 14) -> dict:
    ngay = max(1, min(90, _int(ngay, 14)))
    now = _now()
    dau_nay = _dau_ngay(now)
    may = ds.ds_may()
    nicks = ds_nick()
    nen = set()
    for n in nicks:
        nen.update(n["nhan"])
    with ds._db() as c:
        tu7 = now - 7 * 86400
        dem7 = {r["trang_thai"]: r["n"] for r in c.execute(
            "SELECT trang_thai, COUNT(*) n FROM viec WHERE bat_dau>=? GROUP BY trang_thai", (tu7,))}
        dang = c.execute("SELECT COUNT(*) FROM viec WHERE trang_thai='dang_chay'").fetchone()[0]
        tc, loi = dem7.get("xong", 0), dem7.get("loi", 0)
        so7 = {"luot": tc + loi + dem7.get("dang_chay", 0), "thanh_cong": tc, "dang_chay": dang, "loi": loi,
               "ty_le": round(100.0 * tc / (tc + loi)) if (tc + loi) else 0}
        bd = {}
        bat = _dau_ngay(now - (ngay - 1) * 86400)
        for r in c.execute("SELECT xong_luc, trang_thai FROM viec WHERE xong_luc>=? AND trang_thai IN ('xong','loi')",
                           (bat,)):
            k = _ngay_str(r["xong_luc"])
            d = bd.setdefault(k, {"thanh_cong": 0, "loi": 0})
            d["thanh_cong" if r["trang_thai"] == "xong" else "loi"] += 1
        bieu_do = []
        for i in range(ngay):
            k = _ngay_str(bat + i * 86400 + 3600 * 12)
            bieu_do.append({"ngay": k, **bd.get(k, {"thanh_cong": 0, "loi": 0})})
        hom_nay = c.execute("SELECT COUNT(*) FROM viec WHERE bat_dau>=?", (dau_nay,)).fetchone()[0]
        can = []
        for n in nicks:
            for nt, ma in (n["canh_bao"] or {}).items():
                can.append({"loai": "nick", "tieu_de": f"{n['ten']}: {MA_CANH_BAO.get(ma, ma)} · {TEN_NEN_TANG.get(nt, nt)}",
                            "chi_tiet": "Mở profile trong GPM để đăng nhập lại / xác minh, rồi chạy lại.",
                            "nut": "Xem", "den": "#/tai-khoan", "nick_id": n["id"]})
        so = c.execute("SELECT COUNT(*) FROM ban_nhap WHERE trang_thai='cho_duyet'").fetchone()[0]
        if so:
            can.append({"loai": "ban_nhap", "tieu_de": f"{so} nội dung chờ bạn duyệt",
                        "chi_tiet": "AI đã viết nháp, bấm Duyệt thì máy ở nhà mới đăng.", "nut": "Duyệt", "den": "#/duyet"})
        so = c.execute("SELECT COUNT(*) FROM hoi_dap WHERE trang_thai='cho_ban'").fetchone()[0]
        if so:
            can.append({"loai": "hoi_dap", "tieu_de": f"{so} câu khách hỏi chờ bạn trả lời",
                        "chi_tiet": "AI chưa có thông tin để trả lời; trả lời một lần, lần sau AI tự dùng.",
                        "nut": "Trả lời", "den": "#/kien-thuc"})
        so = c.execute("SELECT COUNT(*) FROM hoi_thoai WHERE trang_thai='can_tra_loi_tay'").fetchone()[0]
        if so:
            can.append({"loai": "hoi_thoai", "tieu_de": f"{so} khách cần bạn trả lời tay",
                        "chi_tiet": "Câu khó, khiếu nại hoặc đặt hàng: bot đã giữ khách, chờ bạn.", "nut": "Xem",
                        "den": "#/tin-nhan"})
        so = c.execute("SELECT COUNT(*) FROM nhom_fb WHERE trang_thai='cho_duyet'").fetchone()[0]
        if so:
            can.append({"loai": "nhom_fb", "tieu_de": f"{so} nhóm Facebook chờ bạn duyệt",
                        "chi_tiet": "Nhóm AI tìm được, duyệt thì đội mới vào và bình luận.", "nut": "Duyệt",
                        "den": "#/nhom-fb"})
        so = c.execute("SELECT COUNT(*) FROM ke_hoach WHERE trang_thai='cho_duyet'").fetchone()[0]
        if so:
            can.append({"loai": "ke_hoach", "tieu_de": f"{so} kế hoạch của Trợ lý AI chờ duyệt",
                        "chi_tiet": "Kế hoạch không tự chạy khi chưa duyệt.", "nut": "Duyệt", "den": "#/tro-ly"})
        for r in c.execute("SELECT * FROM dot_chay WHERE tao_luc>=? ORDER BY id DESC LIMIT 100", (tu7,)).fetchall():
            tt = _tien_trinh(c, r["id"])
            if tt["loi"] >= 2 and tt["loi"] * 2 >= max(1, tt["tong"]):
                can.append({"loai": "dot_loi", "tieu_de": f"Đợt '{r['ten']}' lỗi {tt['loi']}/{tt['tong']} việc",
                            "chi_tiet": "Xem nhật ký để biết lý do.", "nut": "Xem", "den": "#/nhat-ky", "dot_id": r["id"]})
    for m in may:
        if not m["online"]:
            can.append({"loai": "may", "tieu_de": f"Máy '{m['ten']}' đang ngoại tuyến",
                        "chi_tiet": "Bật máy ở nhà và chạy MinMin Worker.", "nut": "Xem", "den": "#/may"})
    return {"nick_tong": len(nicks), "nen_tang_dung": sorted(nen),
            "ai": {"engine": "", "mo_hinh": "", "nhin_anh": False, "san_sang": False},
            "may": [{"id": m["id"], "ten": m["ten"], "online": m["online"], "phien_ban": m.get("phien_ban") or "",
                     "so_nick": m.get("so_nick", 0), "kich_ban": m.get("kich_ban") or []} for m in may],
            "so7": so7, "bieu_do": bieu_do, "hom_nay": hom_nay, "can_xu_ly": can}


def boi_canh_tro_ly() -> dict:
    ss = san_sang_theo_mau()
    tq = tong_quan(7)
    tq.pop("bieu_do", None)
    return {"mau": [{"id": m["id"], "ten": m["ten"], "nen_tang": m["nen_tang"], "mo_ta": m["mo_ta"],
                     "tham_so": [f["key"] for f in m["tham_so"]], "san_sang": ss.get(m["id"], False)} for m in kb.MAU],
            "nick": [{"id": n["id"], "ten": n["ten"], "nhan": n["nhan"],
                      "noi_dang": [{"nen_tang": d["nen_tang"], "loai": d["loai"], "ten": d["ten"], "link": d["link"]}
                                   for d in (n.get("dich_den") or [])][:15]} for n in ds_nick()],
            "kien_thuc": [{"id": k["id"], "ten": k["ten"], "loai": k["loai"]} for k in ds_kien_thuc()],
            "tong_quan": tq | {"hom_nay_theo_nick": hom_nay_theo_nick()}}


# ------------------------------------------------------------------ nơi đăng đã quét (Trang, tài khoản)
NEN_TANG_QUET = ("facebook", "instagram", "tiktok", "threads")
LOAI_DICH = ("ca_nhan", "trang", "tai_khoan")


def tao_quet_tai_khoan(nick, nen_tang=None) -> list:
    """Một việc `quet_tai_khoan` cho mỗi nick: máy nhà mở profile, đọc Trang Facebook nick quản lý và tài
    khoản Instagram / TikTok / Threads đang đăng nhập. Chỉ đọc, không bấm gì."""
    nt = [x for x in (nen_tang or NEN_TANG_QUET) if x in NEN_TANG_QUET] or list(NEN_TANG_QUET)
    now = _now()
    ra = []
    with ds._khoa, ds._db() as c:
        for n in _tim_nick_ds(c, nick):
            if c.execute("SELECT 1 FROM viec WHERE nick_id=? AND ky_nang='quet_tai_khoan' AND trang_thai IN "
                         "('cho_chay','dang_chay')", (n["id"],)).fetchone():
                continue
            vts = {"kich_ban": "quet_tai_khoan", "nen_tang": "", "chay_thu": True, "dot_id": None, "han_muc": {},
                   "nghi_giay": [], "hanh_dong": [], "tham_so": {"nen_tang": nt}}
            ra.append(c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc, "
                                "duyet_luc, nguon, chay_thu) VALUES('quet_tai_khoan',?,?,?,?,'cho_chay',?,?,'web',1)",
                                (n["may_id"], n["id"], n["ten"], _dj(vts), now, now)).lastrowid)
    return [ds.lay_viec(v) for v in ra]


def ghi_dich_den(vid, may_id: str, nen_tang_da_quet, muc) -> dict:
    """Worker gửi kết quả quét. Nền tảng đã quét được thay toàn bộ danh sách cũ của nick (Trang bị gỡ
    quyền thì biến mất); nền tảng không quét được giữ nguyên. Gắn nhãn nền tảng cho nick theo kết quả."""
    v = viec_cua_may(vid, may_id)
    nick_id = v["nick_id"]
    da_quet = [x for x in (nen_tang_da_quet or []) if x in NEN_TANG_QUET]
    sach = []
    for m in (muc or [])[:200]:
        if not isinstance(m, dict):
            continue
        nt, link = str(m.get("nen_tang") or ""), str(m.get("link") or "").strip()
        if nt not in NEN_TANG_QUET or not link.startswith("https://"):
            continue
        sach.append({"nen_tang": nt, "loai": m.get("loai") if m.get("loai") in LOAI_DICH else "tai_khoan",
                     "ten": _chu(m.get("ten"), 200) or link, "link": link[:500], "ma": _chu(m.get("ma"), 100),
                     "anh": str(m.get("anh") or "")[:500] if str(m.get("anh") or "").startswith("https://") else ""})
    now = _now()
    with ds._khoa, ds._db() as c:
        for nt in da_quet:
            c.execute("DELETE FROM dich_den WHERE nick_id=? AND nen_tang=?", (nick_id, nt))
        for m in sach:
            if m["nen_tang"] not in da_quet:
                continue
            c.execute("INSERT OR REPLACE INTO dich_den(nick_id, nen_tang, loai, ten, link, ma, anh, cap_nhat) "
                      "VALUES(?,?,?,?,?,?,?,?)", (nick_id, m["nen_tang"], m["loai"], m["ten"], m["link"], m["ma"],
                                                 m["anh"], now))
        co = {r[0] for r in c.execute("SELECT DISTINCT nen_tang FROM dich_den WHERE nick_id=?", (nick_id,))}
        meta = _meta(c, nick_id)
        nhan = [x for x in (meta.get("nhan") or []) if x not in da_quet or x in co]
        nhan += [x for x in sorted(co) if x not in nhan]
        meta["nhan"] = nhan
        _luu_meta(c, meta)
    return {"so": len([m for m in sach if m["nen_tang"] in da_quet]), "nhan": nhan}


def ds_dich_den(nick_id: str = "", nen_tang: str = "") -> list:
    q, a = "SELECT * FROM dich_den WHERE 1=1", []
    if nick_id:
        q += " AND nick_id=?"
        a.append(nick_id)
    if nen_tang:
        q += " AND nen_tang=?"
        a.append(nen_tang)
    with ds._db() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY nick_id, nen_tang, loai, ten", a).fetchall()]
