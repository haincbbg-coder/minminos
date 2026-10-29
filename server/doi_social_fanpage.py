"""doi_social_fanpage.py - kho của Fanpage qua Graph API (26.10.194).

Hợp đồng: docs/doi-social/FANPAGE.md. Dùng CHUNG tệp SQLite và khoá với `doi_social`
(`ds._db()`, `ds._khoa`, bảng `cai_dat`). Ở đây thuần đồng bộ, thuần stdlib, KHÔNG gọi mạng:
bảng, CRUD, spin, lịch, chọn nội dung từ kho, quy tắc bình luận, cảnh báo, số liệu tổng quan.
Phần gọi Graph ở `doi_social_fanpage_graph.py`.

Luật an toàn (mục 1 hợp đồng) giữ ngay ở kho:
- bài tạo hàng loạt mặc định `cho_duyet` (chủ tắt `duyet_truoc` mới vào thẳng `cho_dang`);
- quy tắc bình luận mặc định `tu_gui = 0` -> câu trả lời ở `cho_duyet`;
- `dung_tu_dong` chặn áp quy tắc (vòng nền ở lớp Graph kiểm thêm phần đăng/quét);
- token thật KHÔNG BAO GIỜ ra khỏi hàm nội bộ `_token_tho()`; mọi hàm trả ra ngoài đều che.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Iterable, Optional

import doi_social as ds

LOAI_TOKEN = ("ket_noi", "nguoi_dung", "trang")
TT_TOKEN = ("tot", "loi", "het_han", "chua_kiem")
LOAI_BAI = ("chu", "anh", "album", "video", "reel", "story")
TT_BAI = ("cho_duyet", "cho_dang", "da_hen_fb", "dang_dang", "da_dang", "loi", "bo")
TT_CHO = ("cho_duyet", "cho_dang", "da_hen_fb")          # bài còn chờ (chiếm khung giờ, tính hàng chờ)
NGUON_BAI = ("tay", "kho", "kenh", "ai", "thu_muc")
TT_BL = ("moi", "cho_duyet", "cho_gui", "dang_gui", "da_tra_loi", "da_an", "bo_qua", "loi")
HANH_DONG_QT = ("tra_loi", "tra_loi_ai", "an", "an_va_tra_loi")
LOAI_KHO = ("noi_dung", "binh_luan", "link", "tieu_su")
CHE_DO_KHO = ("ngau_nhien", "stt", "lan_luot")
CHIA_KENH = ("xoay", "tat_ca")
DUOI_ANH = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DUOI_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
ANH_TOI_DA = 15 * 1024 * 1024
VIDEO_TOI_DA = 300 * 1024 * 1024
CHU_TOI_DA = 8000
BAI_MOT_LAN_TOI_DA = 1000
MUC_KHO_TOI_DA = 5000
LICH_GAN_PHUT = 20                # hai bài của một Trang cách nhau < 20 phút thì coi như trùng khung
FB_HEN_TU = 11 * 60               # Facebook nhận hẹn giờ từ 10 phút tới 30 ngày; chừa biên an toàn
FB_HEN_DEN = 29 * 86400
CONG_KHAI_SONG = 2 * 3600
QUYEN_DANG = ("CREATE_CONTENT", "MANAGE")
BIEN_SPIN = ("ten_trang", "ngay", "ten_tep")

LICH_MAC_DINH = {"che_do": "gio", "gio": ["09:00", "12:00", "18:00"], "moi_gio": 4, "tu": "08:00",
                 "den": "22:00", "lech_phut": 30, "trai_phut": 0, "cach": "tool"}
CAU_HINH_MAC_DINH = {
    "lich": LICH_MAC_DINH,
    "kho_noi_dung": None, "kho_binh_luan": None, "kho_tieu_su": None,
    "binh_luan_sau_dang": False, "story": False, "ig_dong_bo": False,
    "tu_an": False, "tu_tra_loi": False, "chia_video": "mot_trang",
    "duyet_truoc": True,
}
CAI_DAT_MAC_DINH = {"dung_tu_dong": False, "xoa_tep_sau_ngay": 7, "bao_moi_bai": False,
                    "cho_dang_trung": False, "luong": 3, "ig_toi_da_24h": 50}

# Lỗi Graph -> cách sửa người đọc được (dùng cho cảnh báo gộp theo mã).
CACH_SUA_LOI = {
    "200": "Nối lại kết nối Facebook Trang và tick quyền pages_manage_posts (cùng pages_read_engagement).",
    "10": "Tài khoản không đủ quyền trên Trang: vào Cài đặt Trang > Quyền truy cập, cấp quyền quản lý nội dung.",
    "190": "Token đã hết hạn hoặc bị thu hồi: nối lại kết nối hoặc dán token mới ở tab Token.",
    "368": "Facebook tạm chặn hành động này vì nghi spam: giảm số bài mỗi ngày, đợi vài giờ rồi thử lại.",
    "100": "Tham số không hợp lệ (thường là tệp hỏng hoặc sai định dạng): kiểm tra tệp media của bài.",
    "tep": "Tệp media của bài không còn: tải lại tệp rồi tạo lại bài.",
}

_KHONG_DOI = object()


# ------------------------------------------------------------------ hạ tầng

def tao_bang(c) -> None:
    """Gọi từ doi_social_v2.tao_bang (trong doi_social.mo). Idempotent."""
    c.executescript("""
    CREATE TABLE IF NOT EXISTS fp_token(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nhan TEXT, loai TEXT, ket_noi_id TEXT DEFAULT '',
        token TEXT DEFAULT '', trang_thai TEXT DEFAULT 'chua_kiem', het_han REAL, kiem_luc REAL,
        loi TEXT DEFAULT '', so_trang INTEGER DEFAULT 0, so_bai_dang INTEGER DEFAULT 0, tao_luc REAL);
    CREATE TABLE IF NOT EXISTS fp_trang(
        id TEXT PRIMARY KEY, ten TEXT, anh TEXT, danh_muc TEXT, link TEXT, ig_id TEXT DEFAULT '',
        ig_ten TEXT DEFAULT '', nhom_id INTEGER, cau_hinh TEXT DEFAULT '{}', nguon TEXT DEFAULT '[]',
        quyen TEXT DEFAULT '[]', nguoi_theo_doi INTEGER DEFAULT 0, bat INTEGER DEFAULT 1,
        cap_nhat REAL, loi TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS fp_nhom(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, mo_ta TEXT DEFAULT '', cau_hinh TEXT DEFAULT '{}',
        tao_luc REAL);
    CREATE TABLE IF NOT EXISTS fp_kho(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, loai TEXT, che_do TEXT DEFAULT 'ngau_nhien',
        muc TEXT DEFAULT '[]', gan TEXT DEFAULT '{}', mau_link TEXT DEFAULT '', con_tro INTEGER DEFAULT 0,
        tao_luc REAL);
    CREATE TABLE IF NOT EXISTS fp_bai(
        id INTEGER PRIMARY KEY AUTOINCREMENT, trang_id TEXT, nhom_id INTEGER, loai TEXT,
        noi_dung TEXT DEFAULT '', media TEXT DEFAULT '[]', link TEXT DEFAULT '', binh_luan TEXT DEFAULT '',
        story INTEGER DEFAULT 0, ig INTEGER DEFAULT 0, hen_luc REAL, cach_hen TEXT DEFAULT 'tool',
        trang_thai TEXT, post_id TEXT DEFAULT '', url TEXT DEFAULT '', loi TEXT DEFAULT '',
        so_lan_thu INTEGER DEFAULT 0, bl_tt TEXT DEFAULT '', story_tt TEXT DEFAULT '', ig_tt TEXT DEFAULT '',
        ig_media_id TEXT DEFAULT '', nguon TEXT DEFAULT 'tay', khoa_trung TEXT DEFAULT '',
        so_lieu TEXT DEFAULT '{}', tao_luc REAL, dang_luc REAL);
    CREATE INDEX IF NOT EXISTS fp_bai_tt ON fp_bai(trang_thai, hen_luc);
    CREATE INDEX IF NOT EXISTS fp_bai_trang ON fp_bai(trang_id, trang_thai);
    CREATE INDEX IF NOT EXISTS fp_bai_khoa ON fp_bai(khoa_trung);
    CREATE TABLE IF NOT EXISTS fp_binh_luan(
        id TEXT PRIMARY KEY, trang_id TEXT, post_id TEXT, cha_id TEXT DEFAULT '', tu_id TEXT, tu_ten TEXT,
        noi_dung TEXT, luc REAL, la_cua_trang INTEGER DEFAULT 0, an INTEGER DEFAULT 0,
        trang_thai TEXT DEFAULT 'moi', tra_loi TEXT DEFAULT '', quy_tac_id INTEGER, loi TEXT DEFAULT '',
        cap_nhat REAL);
    CREATE INDEX IF NOT EXISTS fp_bl_tt ON fp_binh_luan(trang_thai, trang_id);
    CREATE TABLE IF NOT EXISTS fp_quy_tac(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, pham_vi TEXT DEFAULT '{}', tu_khoa TEXT DEFAULT '[]',
        hanh_dong TEXT DEFAULT 'tra_loi', mau TEXT DEFAULT '[]', tu_gui INTEGER DEFAULT 0, bat INTEGER DEFAULT 1,
        uu_tien INTEGER DEFAULT 0, tao_luc REAL);
    CREATE TABLE IF NOT EXISTS fp_kenh(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nen_tang TEXT, link TEXT, ten TEXT DEFAULT '',
        trang_ids TEXT DEFAULT '[]', nhom_id INTEGER, chia TEXT DEFAULT 'xoay', loai_bai TEXT DEFAULT 'reel',
        theo_doi INTEGER DEFAULT 1, chu_ky_gio INTEGER DEFAULT 6, toi_da_moi_lan INTEGER DEFAULT 5,
        lan_quet REAL, so_video INTEGER DEFAULT 0, trang_thai TEXT DEFAULT 'cho', loi TEXT DEFAULT '',
        tao_luc REAL);
    CREATE TABLE IF NOT EXISTS fp_kenh_video(
        kenh_id INTEGER, ma TEXT, tieu_de TEXT, tep TEXT DEFAULT '', luc REAL, trang_thai TEXT DEFAULT 'da_tai',
        PRIMARY KEY(kenh_id, ma));
    CREATE TABLE IF NOT EXISTS fp_so_lieu(
        trang_id TEXT, ngay TEXT, nguoi_theo_doi INTEGER, tiep_can INTEGER, tuong_tac INTEGER, luot_xem INTEGER,
        PRIMARY KEY(trang_id, ngay));
    CREATE TABLE IF NOT EXISTS fp_canh_bao(
        id INTEGER PRIMARY KEY AUTOINCREMENT, luc REAL, muc TEXT, ma TEXT, doi_tuong TEXT, tieu_de TEXT,
        chi_tiet TEXT, cach_sua TEXT, toi TEXT, het_luc REAL);
    CREATE INDEX IF NOT EXISTS fp_cb_mo ON fp_canh_bao(het_luc);
    CREATE TABLE IF NOT EXISTS fp_nhat_ky(
        id INTEGER PRIMARY KEY AUTOINCREMENT, luc REAL, loai TEXT, trang_id TEXT, bai_id INTEGER,
        ket_qua TEXT, chi_tiet TEXT);
    CREATE INDEX IF NOT EXISTS fp_nk_luc ON fp_nhat_ky(luc);
    """)
    import sqlite3
    # Cột THÊM so với hợp đồng (chỉ thêm, không đổi tên): đề xuất hành động của quy tắc cho bình luận
    # đang chờ duyệt ('tra_loi' | 'an' | 'an_va_tra_loi' | 'tra_loi_ai').
    for bang, cot in (("fp_binh_luan", "de_xuat TEXT DEFAULT ''"), ("fp_bai", "campaign_key TEXT DEFAULT ''")):
        try:
            c.execute(f"ALTER TABLE {bang} ADD COLUMN {cot}")
        except sqlite3.OperationalError:
            pass

    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS fp_campaign_key ON fp_bai(campaign_key) WHERE campaign_key!=''")

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


def _ngay_str(luc: float) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(luc, _tz()).strftime("%Y-%m-%d")


def _chu(v, toi_da: int = 2000) -> str:
    return str(v if v is not None else "").strip()[:toi_da]


def _int(v, ten: str, lo: int, hi: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"'{ten}' phải là số nguyên")
    if n < lo or n > hi:
        raise ValueError(f"'{ten}' phải trong khoảng {lo}-{hi}")
    return n


def _trang_so(trang_so, moi_trang, mac: int = 50) -> tuple:
    try:
        t = max(1, int(trang_so or 1))
    except (TypeError, ValueError):
        t = 1
    try:
        m = max(1, min(500, int(moi_trang or mac)))
    except (TypeError, ValueError):
        m = mac
    return t, m, (t - 1) * m


def thu_muc() -> Path:
    p = ds._goc / "fanpage"
    (p / "media").mkdir(parents=True, exist_ok=True)
    return p


def che(token: str) -> str:
    """Che token: 6 ký tự đầu + '…' + 4 cuối. Token ngắn chỉ hiện dấu che."""
    t = str(token or "")
    if not t:
        return ""
    if len(t) < 16:
        return "…"
    return t[:6] + "…" + t[-4:]


# ------------------------------------------------------------------ cài đặt

def _cd_doc(k: str, mac=None):
    with ds._db() as c:
        r = c.execute("SELECT v FROM cai_dat WHERE k=?", (k,)).fetchone()
    return _j(r["v"], mac) if r else mac


def _cd_ghi(k: str, v) -> None:
    with ds._khoa, ds._db() as c:
        c.execute("INSERT OR REPLACE INTO cai_dat(k, v) VALUES(?, ?)", (k, _dj(v)))


def cai_dat() -> dict:
    d = dict(CAI_DAT_MAC_DINH)
    luu = _cd_doc("fp_cai_dat", {}) or {}
    for k in d:
        if k in luu:
            d[k] = luu[k]
    return d


def dat_cai_dat(moi: dict) -> dict:
    if not isinstance(moi, dict):
        raise ValueError("cài đặt phải là object")
    d = cai_dat()
    for k, v in moi.items():
        if k not in CAI_DAT_MAC_DINH:
            continue
        if k in ("dung_tu_dong", "bao_moi_bai", "cho_dang_trung"):
            d[k] = bool(v)
        elif k == "xoa_tep_sau_ngay":
            d[k] = _int(v, k, 0, 365)
        elif k == "luong":
            d[k] = _int(v, k, 1, 20)
        elif k == "ig_toi_da_24h":
            d[k] = _int(v, k, 1, 100)
    _cd_ghi("fp_cai_dat", d)
    return d


def dung_tu_dong() -> bool:
    return bool(cai_dat()["dung_tu_dong"])


def goc_cong_khai() -> str:
    return str(_cd_doc("fp_goc_cong_khai", "") or "")


def dat_goc_cong_khai(goc: str) -> str:
    goc = _chu(goc, 300).rstrip("/")
    if goc and not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?", goc):
        raise ValueError("gốc công khai phải dạng https://ten-mien (không kèm đường dẫn)")
    if goc != goc_cong_khai():
        _cd_ghi("fp_goc_cong_khai", goc)
    return goc


def _bi_mat() -> bytes:
    s = _cd_doc("fp_bi_mat", "")
    if not s:
        s = secrets.token_hex(32)
        _cd_ghi("fp_bi_mat", s)
    return str(s).encode()


# ------------------------------------------------------------------ nhật ký

def ghi_nk(loai: str, trang_id: str = "", bai_id=None, ket_qua: str = "thong_tin", chi_tiet: str = "") -> None:
    with ds._khoa, ds._db() as c:
        c.execute("INSERT INTO fp_nhat_ky(luc, loai, trang_id, bai_id, ket_qua, chi_tiet) VALUES(?,?,?,?,?,?)",
                  (_now(), _chu(loai, 40), _chu(trang_id, 40), bai_id, _chu(ket_qua, 20), _loc_token(_chu(chi_tiet, 1000))))
        if secrets.randbelow(200) == 0:
            c.execute("DELETE FROM fp_nhat_ky WHERE luc < ?", (_now() - 60 * 86400,))


def ds_nhat_ky(gioi: int = 20, trang_id: str = "") -> list:
    q, a = "SELECT n.*, t.ten AS trang_ten FROM fp_nhat_ky n LEFT JOIN fp_trang t ON t.id=n.trang_id", []
    if trang_id:
        q += " WHERE n.trang_id=?"
        a.append(trang_id)
    q += " ORDER BY n.id DESC LIMIT ?"
    a.append(max(1, min(500, int(gioi))))
    with ds._db() as c:
        return [dict(r) for r in c.execute(q, a).fetchall()]


# ------------------------------------------------------------------ token

def _dong_token(r) -> dict:
    d = dict(r)
    tho = d.pop("token", "") or ""
    d["che"] = che(tho)
    if d.get("loai") == "ket_noi":
        d["id"] = "kn:" + str(d.get("ket_noi_id") or "")
    return d


def _kiem_chuoi_token(token: str) -> str:
    t = str(token or "").strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    if not re.fullmatch(r"[A-Za-z0-9_|.\-]{20,1200}", t):
        raise ValueError("token không hợp lệ (dán đúng chuỗi access token, không có khoảng trắng)")
    return t


def them_token(nhan: str, token: str, loai: str = "nguoi_dung") -> dict:
    t = _kiem_chuoi_token(token)
    if loai not in ("nguoi_dung", "trang"):
        raise ValueError("loại token phải là nguoi_dung hoặc trang")
    nhan = _chu(nhan, 80) or ("Token " + che(t))
    with ds._khoa, ds._db() as c:
        for r in c.execute("SELECT id, token FROM fp_token WHERE loai!='ket_noi'").fetchall():
            if hmac.compare_digest(str(r["token"] or ""), t):
                raise ValueError("token này đã có trong danh sách")
        tid = c.execute("INSERT INTO fp_token(nhan, loai, token, trang_thai, tao_luc) VALUES(?,?,?,?,?)",
                        (nhan, loai, t, "chua_kiem", _now())).lastrowid
    return lay_token(tid)


def dam_bao_ket_noi(cid: str, nhan: str = "") -> int:
    """Hàng đại diện một kết nối OAuth (không lưu token). Trả id nội bộ."""
    cid = _chu(cid, 120)
    with ds._khoa, ds._db() as c:
        r = c.execute("SELECT id, nhan FROM fp_token WHERE loai='ket_noi' AND ket_noi_id=?", (cid,)).fetchone()
        if r:
            if nhan and nhan != r["nhan"]:
                c.execute("UPDATE fp_token SET nhan=? WHERE id=?", (_chu(nhan, 80), r["id"]))
            return int(r["id"])
        return int(c.execute("INSERT INTO fp_token(nhan, loai, ket_noi_id, trang_thai, tao_luc) VALUES(?,?,?,?,?)",
                             (_chu(nhan, 80) or "Kết nối Facebook Trang", "ket_noi", cid, "chua_kiem", _now())).lastrowid)


def bo_ket_noi_vang(con_ids: Iterable) -> None:
    """Xoá hàng kết nối OAuth đã bị gỡ ở trang Kết nối."""
    con = {str(x) for x in con_ids}
    with ds._khoa, ds._db() as c:
        for r in c.execute("SELECT id, ket_noi_id FROM fp_token WHERE loai='ket_noi'").fetchall():
            if r["ket_noi_id"] not in con:
                _xoa_token_c(c, int(r["id"]))


def tim_token_id(tid) -> Optional[int]:
    """'kn:<cid>' hoặc số -> id nội bộ."""
    s = str(tid or "")
    with ds._db() as c:
        if s.startswith("kn:"):
            r = c.execute("SELECT id FROM fp_token WHERE loai='ket_noi' AND ket_noi_id=?", (s[3:],)).fetchone()
        else:
            try:
                r = c.execute("SELECT id FROM fp_token WHERE id=?", (int(s),)).fetchone()
            except ValueError:
                r = None
    return int(r["id"]) if r else None


def lay_token(tid) -> Optional[dict]:
    i = tim_token_id(tid)
    if i is None:
        return None
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_token WHERE id=?", (i,)).fetchone()
    return _dong_token(r) if r else None


def hang_token(tid: int) -> Optional[dict]:
    """Hàng thô KHÔNG có token (cho lớp Graph biết loai, ket_noi_id)."""
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_token WHERE id=?", (int(tid),)).fetchone()
    if not r:
        return None
    d = dict(r)
    d.pop("token", None)
    return d


def _token_tho(tid: int) -> str:
    """CHỈ cho lớp Graph. Không bao giờ đưa giá trị này ra API/log."""
    with ds._db() as c:
        r = c.execute("SELECT token FROM fp_token WHERE id=?", (int(tid),)).fetchone()
    return str(r["token"] or "") if r else ""


def ds_token() -> list:
    with ds._db() as c:
        return [_dong_token(r) for r in c.execute(
            "SELECT * FROM fp_token ORDER BY loai='ket_noi' DESC, id").fetchall()]


def ds_token_noi_bo() -> list:
    """[hàng token không có chuỗi token] cho lớp Graph."""
    with ds._db() as c:
        rows = c.execute("SELECT * FROM fp_token ORDER BY loai='ket_noi' DESC, id").fetchall()
    ra = []
    for r in rows:
        d = dict(r)
        d.pop("token", None)
        ra.append(d)
    return ra


def cap_nhat_token(tid: int, **kw) -> None:
    cot = {k: v for k, v in kw.items() if k in ("nhan", "loai", "trang_thai", "het_han", "kiem_luc", "loi",
                                                 "so_trang")}
    if "loi" in cot:
        cot["loi"] = _loc_token(_chu(cot["loi"], 500))
    if not cot:
        return
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE fp_token SET " + ", ".join(f"{k}=?" for k in cot) + " WHERE id=?",
                  (*cot.values(), int(tid)))


def tang_bai_dang(tid: int) -> None:
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE fp_token SET so_bai_dang=so_bai_dang+1 WHERE id=?", (int(tid),))


def _xoa_token_c(c, tid: int) -> None:
    c.execute("DELETE FROM fp_token WHERE id=?", (tid,))
    for r in c.execute("SELECT id, nguon FROM fp_trang").fetchall():
        ng = [x for x in _j(r["nguon"], []) if x != tid]
        c.execute("UPDATE fp_trang SET nguon=? WHERE id=?", (_dj(ng), r["id"]))


def xoa_token(tid) -> bool:
    i = tim_token_id(tid)
    if i is None:
        return False
    h = hang_token(i)
    if h and h["loai"] == "ket_noi":
        raise ValueError("đây là kết nối OAuth: gỡ ở trang Kết nối, không xoá ở đây")
    with ds._khoa, ds._db() as c:
        _xoa_token_c(c, i)
    return True


def _loc_token(s: str) -> str:
    """Xoá mọi chuỗi trông như access token (EAA...) khỏi chữ trước khi lưu/trả ra."""
    return re.sub(r"EAA[A-Za-z0-9]{12,}", lambda m: che(m.group(0)), str(s or ""))


# ------------------------------------------------------------------ cấu hình nhóm / Trang

def _gio(v, ten: str) -> str:
    s = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(f"'{ten}' phải dạng HH:MM")
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _kiem_lich(d) -> dict:
    if d is None:
        return None
    if not isinstance(d, dict):
        raise ValueError("lịch phải là object")
    ra = {}
    for k, v in d.items():
        if v is None:
            continue
        if k == "che_do":
            if v not in ("gio", "chu_ky", "tat"):
                raise ValueError("chế độ lịch phải là gio, chu_ky hoặc tat")
            ra[k] = v
        elif k == "gio":
            if not isinstance(v, list) or len(v) > 48:
                raise ValueError("'gio' phải là danh sách tối đa 48 khung HH:MM")
            ra[k] = sorted({_gio(x, "gio") for x in v})
        elif k == "moi_gio":
            ra[k] = _int(v, k, 1, 168)
        elif k in ("tu", "den"):
            ra[k] = _gio(v, k)
        elif k in ("lech_phut", "trai_phut"):
            ra[k] = _int(v, k, 0, 240)
        elif k == "cach":
            if v not in ("tool", "fb"):
                raise ValueError("'cach' phải là tool hoặc fb")
            ra[k] = v
    return ra


def _kiem_cau_hinh(d) -> dict:
    """Kiểm một cấu hình nhóm/Trang (có thể thiếu khoá; `null` = theo cấp trên). Khoá lạ bị bỏ."""
    if d is None:
        return {}
    if not isinstance(d, dict):
        raise ValueError("cấu hình phải là object")
    ra = {}
    for k, v in d.items():
        if k not in CAU_HINH_MAC_DINH:
            continue
        if v is None:
            ra[k] = None
        elif k == "lich":
            ra[k] = _kiem_lich(v)
        elif k.startswith("kho_"):
            kid = _int(v, k, 1, 10 ** 9)
            loai = {"kho_noi_dung": "noi_dung", "kho_binh_luan": "binh_luan", "kho_tieu_su": "tieu_su"}[k]
            kh = _hang_kho(kid)
            if not kh:
                raise ValueError(f"không có kho #{kid}")
            if kh["loai"] != loai:
                raise ValueError(f"kho #{kid} không phải kho loại {loai}")
            ra[k] = kid
        elif k == "chia_video":
            if v not in ("mot_trang", "tat_ca"):
                raise ValueError("'chia_video' phải là mot_trang hoặc tat_ca")
            ra[k] = v
        else:
            ra[k] = bool(v)
    return ra


def _gop(goc: dict, moi: dict) -> dict:
    ra = json.loads(json.dumps(goc))
    for k, v in (moi or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(ra.get(k), dict):
            ra[k] = _gop(ra[k], v)
        else:
            ra[k] = v
    return ra


def _hieu_luc_tho(ch_trang: dict, ch_nhom: dict) -> tuple:
    hl = _gop(_gop(CAU_HINH_MAC_DINH, ch_nhom or {}), ch_trang or {})
    if (ch_trang or {}).get("lich"):
        nguon = "trang"
    elif (ch_nhom or {}).get("lich"):
        nguon = "nhom"
    else:
        nguon = "mac_dinh"
    return hl, nguon


def hieu_luc(trang_id: str) -> dict:
    """Cấu hình hiệu lực của Trang: mặc định <- nhóm <- Trang."""
    with ds._db() as c:
        t = c.execute("SELECT cau_hinh, nhom_id FROM fp_trang WHERE id=?", (str(trang_id),)).fetchone()
        n = c.execute("SELECT cau_hinh FROM fp_nhom WHERE id=?", (t["nhom_id"],)).fetchone() if t and t["nhom_id"] else None
    if not t:
        return json.loads(json.dumps(CAU_HINH_MAC_DINH))
    return _hieu_luc_tho(_j(t["cau_hinh"], {}), _j(n["cau_hinh"], {}) if n else {})[0]


# ------------------------------------------------------------------ Trang

def ghi_trang(d: dict, token_id: Optional[int] = None) -> bool:
    """Ghi/cập nhật Trang từ Graph (giữ nhom_id, cau_hinh, bat). Trả True nếu Trang mới."""
    pid = _chu(d.get("id"), 40)
    if not re.fullmatch(r"\d{3,40}", pid):
        return False
    anh = d.get("anh")
    if anh is None:
        pic = d.get("picture") or {}
        anh = ((pic.get("data") or {}).get("url") if isinstance(pic, dict) else "") or ""
    ig = d.get("instagram_business_account") or {}
    ig_id = _chu(d.get("ig_id") if "ig_id" in d else (ig.get("id") if isinstance(ig, dict) else ""), 40)
    ig_ten = _chu(d.get("ig_ten") if "ig_ten" in d else (ig.get("username") if isinstance(ig, dict) else ""), 120)
    theo = d.get("followers_count")
    if theo is None:
        theo = d.get("fan_count")
    tasks = d.get("tasks")
    with ds._khoa, ds._db() as c:
        cu = c.execute("SELECT * FROM fp_trang WHERE id=?", (pid,)).fetchone()
        nguon = _j(cu["nguon"], []) if cu else []
        if token_id is not None and token_id not in nguon:
            nguon.append(int(token_id))
        quyen = list(tasks) if isinstance(tasks, list) else (_j(cu["quyen"], []) if cu else [])
        gia_tri = (_chu(d.get("name") or d.get("ten") or (cu["ten"] if cu else ""), 200), _chu(anh, 1000),
                   _chu(d.get("category") or (cu["danh_muc"] if cu else ""), 120),
                   _chu(d.get("link") or (cu["link"] if cu else "") or f"https://www.facebook.com/{pid}", 500),
                   ig_id, ig_ten, _dj(nguon), _dj(quyen),
                   int(theo) if isinstance(theo, (int, float)) else (cu["nguoi_theo_doi"] if cu else 0), _now())
        if cu:
            c.execute("UPDATE fp_trang SET ten=?, anh=?, danh_muc=?, link=?, ig_id=?, ig_ten=?, nguon=?, quyen=?, "
                      "nguoi_theo_doi=?, cap_nhat=?, loi='' WHERE id=?", (*gia_tri, pid))
            return False
        c.execute("INSERT INTO fp_trang(ten, anh, danh_muc, link, ig_id, ig_ten, nguon, quyen, nguoi_theo_doi, "
                  "cap_nhat, id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (*gia_tri, pid))
        return True


def bo_nguon_trang(token_id: int, giu_ids: Iterable) -> None:
    """Token `token_id` không còn thấy các Trang ngoài `giu_ids` -> gỡ token khỏi nguồn của chúng."""
    giu = {str(x) for x in giu_ids}
    with ds._khoa, ds._db() as c:
        for r in c.execute("SELECT id, nguon FROM fp_trang").fetchall():
            ng = _j(r["nguon"], [])
            if token_id in ng and r["id"] not in giu:
                ng.remove(token_id)
                c.execute("UPDATE fp_trang SET nguon=? WHERE id=?", (_dj(ng), r["id"]))


def dat_loi_trang(trang_id: str, loi: str) -> None:
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE fp_trang SET loi=? WHERE id=?", (_loc_token(_chu(loi, 500)), str(trang_id)))


def _dem_bai_trang(c) -> dict:
    ra = {}
    for r in c.execute("SELECT trang_id, trang_thai, COUNT(*) n FROM fp_bai GROUP BY trang_id, trang_thai").fetchall():
        d = ra.setdefault(r["trang_id"], {"da_dang": 0, "cho": 0, "loi": 0})
        if r["trang_thai"] == "da_dang":
            d["da_dang"] += r["n"]
        elif r["trang_thai"] in TT_CHO:
            d["cho"] += r["n"]
        elif r["trang_thai"] == "loi":
            d["loi"] += r["n"]
    return ra


def _dong_trang(r, nhom: dict, dem: dict, bai_ke: dict) -> dict:
    d = dict(r)
    d["cau_hinh"] = _j(d.get("cau_hinh"), {})
    d["nguon"] = _j(d.get("nguon"), [])
    d["quyen"] = _j(d.get("quyen"), [])
    n = nhom.get(d.get("nhom_id")) or {}
    d["nhom_ten"] = n.get("ten") or ""
    hl, nguon = _hieu_luc_tho(d["cau_hinh"], n.get("cau_hinh") or {})
    d["cau_hinh_hieu_luc"] = hl
    d["nguon_cau_hinh"] = nguon
    d["so_token"] = len(d["nguon"])
    d.pop("nguon", None)
    d["bat"] = bool(d.get("bat"))
    d["co_quyen_dang"] = (not d["quyen"]) or any(x in d["quyen"] for x in QUYEN_DANG)
    d["dem"] = dem.get(d["id"], {"da_dang": 0, "cho": 0, "loi": 0})
    d["bai_ke"] = bai_ke.get(d["id"])
    return d


def _bang_nhom(c) -> dict:
    return {r["id"]: {"ten": r["ten"], "cau_hinh": _j(r["cau_hinh"], {})}
            for r in c.execute("SELECT id, ten, cau_hinh FROM fp_nhom").fetchall()}


def _bai_ke(c) -> dict:
    return {r["trang_id"]: r["h"] for r in c.execute(
        "SELECT trang_id, MIN(hen_luc) h FROM fp_bai WHERE trang_thai IN ('cho_dang','da_hen_fb') "
        "AND hen_luc IS NOT NULL GROUP BY trang_id").fetchall()}


def ds_trang(nhom=None, q: str = "", sap_xep: str = "ten") -> dict:
    with ds._db() as c:
        nhom_bang = _bang_nhom(c)
        dem = _dem_bai_trang(c)
        ke = _bai_ke(c)
        rows = c.execute("SELECT * FROM fp_trang").fetchall()
        so_nhom = {r["nhom_id"]: r["n"] for r in c.execute(
            "SELECT nhom_id, COUNT(*) n FROM fp_trang GROUP BY nhom_id").fetchall()}
    muc = [_dong_trang(r, nhom_bang, dem, ke) for r in rows]
    if nhom not in (None, ""):
        if str(nhom) in ("0", "chua", "none"):
            muc = [t for t in muc if not t["nhom_id"]]
        else:
            try:
                nid = int(nhom)
            except (TypeError, ValueError):
                nid = -1
            muc = [t for t in muc if t["nhom_id"] == nid]
    if q:
        g = ds._bo_dau(q)
        muc = [t for t in muc if g in ds._bo_dau(t["ten"]) or g in t["id"]]
    if sap_xep == "da_dang":
        muc.sort(key=lambda t: (-t["dem"]["da_dang"], ds._bo_dau(t["ten"])))
    else:
        muc.sort(key=lambda t: ds._bo_dau(t["ten"]))
    return {"muc": muc, "nhom": [{"id": k, "ten": v["ten"], "so": so_nhom.get(k, 0)} for k, v in
                                 sorted(nhom_bang.items(), key=lambda kv: ds._bo_dau(kv[1]["ten"]))],
            "chua_nhom": so_nhom.get(None, 0)}


def lay_trang(trang_id: str) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_trang WHERE id=?", (str(trang_id),)).fetchone()
        if not r:
            return None
        return _dong_trang(r, _bang_nhom(c), _dem_bai_trang(c), _bai_ke(c))


def hang_trang(trang_id: str) -> Optional[dict]:
    """Hàng Trang thô cho lớp Graph (nguon là list id token, không có token)."""
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_trang WHERE id=?", (str(trang_id),)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["nguon"] = _j(d.get("nguon"), [])
    d["quyen"] = _j(d.get("quyen"), [])
    d["cau_hinh"] = _j(d.get("cau_hinh"), {})
    return d


def ids_trang(bat_only: bool = True) -> list:
    with ds._db() as c:
        return [r[0] for r in c.execute("SELECT id FROM fp_trang" + (" WHERE bat=1" if bat_only else "")
                                        + " ORDER BY id").fetchall()]


def sua_trang(trang_id: str, nhom_id=_KHONG_DOI, cau_hinh=None, bat=None) -> dict:
    t = hang_trang(trang_id)
    if not t:
        raise ValueError(f"không có Trang {trang_id}")
    with ds._khoa, ds._db() as c:
        if nhom_id is not _KHONG_DOI:
            if nhom_id in (None, "", 0):
                nhom_id = None
            else:
                nhom_id = int(nhom_id)
                if not c.execute("SELECT 1 FROM fp_nhom WHERE id=?", (nhom_id,)).fetchone():
                    raise ValueError(f"không có nhóm #{nhom_id}")
            c.execute("UPDATE fp_trang SET nhom_id=? WHERE id=?", (nhom_id, t["id"]))
    if cau_hinh is not None:
        ch = _kiem_cau_hinh(cau_hinh)
        moi = dict(t["cau_hinh"])
        moi.update(ch)
        moi = {k: v for k, v in moi.items() if v is not None}
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_trang SET cau_hinh=? WHERE id=?", (_dj(moi), t["id"]))
    if bat is not None:
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_trang SET bat=? WHERE id=?", (int(bool(bat)), t["id"]))
    return lay_trang(t["id"])


def hanh_dong_trang(ids, hanh_dong: str, d: dict) -> dict:
    """Phần hành động thuần kho: gan_nhom, gan_cau_hinh, bat, tat. Còn lại ở lớp Graph."""
    ids = [str(x) for x in (ids or [])][:2000]
    if not ids:
        raise ValueError("chưa chọn Trang nào")
    so, loi = 0, []
    if hanh_dong == "gan_cau_hinh":
        _kiem_cau_hinh(d.get("cau_hinh"))       # kiểm trước một lần, khỏi lỗi giữa chừng
    for tid in ids:
        try:
            if hanh_dong == "gan_nhom":
                sua_trang(tid, nhom_id=d.get("nhom_id"))
            elif hanh_dong == "gan_cau_hinh":
                sua_trang(tid, cau_hinh=d.get("cau_hinh") or {})
            elif hanh_dong in ("bat", "tat"):
                sua_trang(tid, bat=hanh_dong == "bat")
            else:
                raise ValueError(f"hành động lạ: {hanh_dong}")
            so += 1
        except ValueError as e:
            if "hành động lạ" in str(e):
                raise
            loi.append({"id": tid, "loi": str(e)})
    return {"so": so, "loi": loi}


# ------------------------------------------------------------------ nhóm

def _dong_nhom(c, r) -> dict:
    d = dict(r)
    d["cau_hinh"] = _j(d.get("cau_hinh"), {})
    tr = [dict(x) for x in c.execute("SELECT id, ten, anh FROM fp_trang WHERE nhom_id=? ORDER BY ten",
                                     (d["id"],)).fetchall()]
    d["so_trang"] = len(tr)
    d["trang"] = tr
    d["cau_hinh_hieu_luc"] = _gop(CAU_HINH_MAC_DINH, d["cau_hinh"])
    return d


def ds_nhom() -> list:
    with ds._db() as c:
        return [_dong_nhom(c, r) for r in c.execute("SELECT * FROM fp_nhom ORDER BY ten").fetchall()]


def lay_nhom(nid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_nhom WHERE id=?", (int(nid),)).fetchone()
        return _dong_nhom(c, r) if r else None


def tao_nhom(ten: str, mo_ta: str = "", cau_hinh=None) -> dict:
    ten = _chu(ten, 120)
    if not ten:
        raise ValueError("nhóm cần có tên")
    ch = {k: v for k, v in _kiem_cau_hinh(cau_hinh).items() if v is not None}
    with ds._khoa, ds._db() as c:
        nid = c.execute("INSERT INTO fp_nhom(ten, mo_ta, cau_hinh, tao_luc) VALUES(?,?,?,?)",
                        (ten, _chu(mo_ta, 1000), _dj(ch), _now())).lastrowid
    return lay_nhom(nid)


def sua_nhom(nid, ten=None, mo_ta=None, cau_hinh=None) -> dict:
    n = lay_nhom(nid)
    if not n:
        raise ValueError(f"không có nhóm #{nid}")
    with ds._khoa, ds._db() as c:
        if ten is not None:
            if not _chu(ten, 120):
                raise ValueError("nhóm cần có tên")
            c.execute("UPDATE fp_nhom SET ten=? WHERE id=?", (_chu(ten, 120), n["id"]))
        if mo_ta is not None:
            c.execute("UPDATE fp_nhom SET mo_ta=? WHERE id=?", (_chu(mo_ta, 1000), n["id"]))
    if cau_hinh is not None:
        ch = dict(n["cau_hinh"])
        ch.update(_kiem_cau_hinh(cau_hinh))
        ch = {k: v for k, v in ch.items() if v is not None}
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_nhom SET cau_hinh=? WHERE id=?", (_dj(ch), n["id"]))
    return lay_nhom(n["id"])


def xoa_nhom(nid) -> bool:
    with ds._khoa, ds._db() as c:
        n = c.execute("DELETE FROM fp_nhom WHERE id=?", (int(nid),)).rowcount
        c.execute("UPDATE fp_trang SET nhom_id=NULL WHERE nhom_id=?", (int(nid),))
    return n > 0


# ------------------------------------------------------------------ kho

def _hang_kho(kid) -> Optional[dict]:
    try:
        kid = int(kid)
    except (TypeError, ValueError):
        return None
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_kho WHERE id=?", (kid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["muc"] = _j(d.get("muc"), [])
    d["gan"] = _j(d.get("gan"), {})
    return d


def _kiem_muc(loai: str, muc) -> list:
    if not isinstance(muc, list):
        raise ValueError("'muc' phải là danh sách")
    ra = []
    for x in muc:
        s = str(x if x is not None else "").replace("\r\n", "\n").strip()
        if not s:
            continue
        if len(s) > CHU_TOI_DA:
            raise ValueError(f"một mục quá dài (tối đa {CHU_TOI_DA} ký tự)")
        if loai == "link" and not re.match(r"https?://\S+$", s):
            raise ValueError(f"kho link chỉ nhận link http(s): {s[:60]}")
        ra.append(s)
    if len(ra) > MUC_KHO_TOI_DA:
        raise ValueError(f"kho tối đa {MUC_KHO_TOI_DA} mục")
    return ra


def _kiem_gan(gan) -> dict:
    if not gan:
        return {}
    if not isinstance(gan, dict):
        raise ValueError("'gan' phải là object {noi_dung:[id], binh_luan:[id]}")
    ra = {}
    for k in ("noi_dung", "binh_luan"):
        v = gan.get(k) or []
        if not isinstance(v, list):
            raise ValueError(f"'gan.{k}' phải là danh sách id kho")
        ids = []
        for x in v:
            kh = _hang_kho(x)
            if not kh or kh["loai"] != k:
                raise ValueError(f"kho #{x} không phải kho {k}")
            ids.append(int(x))
        if ids:
            ra[k] = ids
    return ra


def _kiem_mau_link(m: str) -> str:
    m = _chu(m, 500)
    if m and not re.match(r"https?://\S+$", m):
        raise ValueError("mẫu link phải bắt đầu bằng http(s):// và không có khoảng trắng")
    return m


def _dong_kho(d: dict, day_du: bool) -> dict:
    ra = {"id": d["id"], "ten": d["ten"], "loai": d["loai"], "che_do": d["che_do"], "so": len(d["muc"]),
          "gan": d["gan"], "mau_link": d.get("mau_link") or "", "con_tro": d.get("con_tro") or 0,
          "tao_luc": d.get("tao_luc")}
    if day_du:
        ra["muc"] = d["muc"]
    else:
        ra["vi_du"] = [str(x)[:120] for x in d["muc"][:3]]
    return ra


def ds_kho(loai: str = "") -> list:
    with ds._db() as c:
        q, a = "SELECT id FROM fp_kho", []
        if loai:
            q += " WHERE loai=?"
            a.append(loai)
        ids = [r[0] for r in c.execute(q + " ORDER BY loai, ten", a).fetchall()]
    return [_dong_kho(_hang_kho(i), False) for i in ids]


def lay_kho(kid) -> Optional[dict]:
    d = _hang_kho(kid)
    return _dong_kho(d, True) if d else None


def tao_kho(ten: str, loai: str, che_do: str = "ngau_nhien", muc=None, gan=None, mau_link: str = "") -> dict:
    ten = _chu(ten, 120)
    if not ten:
        raise ValueError("kho cần có tên")
    if loai not in LOAI_KHO:
        raise ValueError("loại kho phải là noi_dung, binh_luan, link hoặc tieu_su")
    if che_do not in CHE_DO_KHO:
        raise ValueError("chế độ phải là ngau_nhien, stt hoặc lan_luot")
    muc = _kiem_muc(loai, muc or [])
    gan = _kiem_gan(gan) if loai == "link" else {}
    mau = _kiem_mau_link(mau_link) if loai == "link" else ""
    with ds._khoa, ds._db() as c:
        kid = c.execute("INSERT INTO fp_kho(ten, loai, che_do, muc, gan, mau_link, tao_luc) VALUES(?,?,?,?,?,?,?)",
                        (ten, loai, che_do, _dj(muc), _dj(gan), mau, _now())).lastrowid
    return lay_kho(kid)


def sua_kho(kid, ten=None, che_do=None, muc=None, gan=None, mau_link=None) -> dict:
    k = _hang_kho(kid)
    if not k:
        raise ValueError(f"không có kho #{kid}")
    cot = {}
    if ten is not None:
        if not _chu(ten, 120):
            raise ValueError("kho cần có tên")
        cot["ten"] = _chu(ten, 120)
    if che_do is not None:
        if che_do not in CHE_DO_KHO:
            raise ValueError("chế độ phải là ngau_nhien, stt hoặc lan_luot")
        cot["che_do"] = che_do
    if muc is not None:
        cot["muc"] = _dj(_kiem_muc(k["loai"], muc))
    if gan is not None and k["loai"] == "link":
        cot["gan"] = _dj(_kiem_gan(gan))
    if mau_link is not None and k["loai"] == "link":
        cot["mau_link"] = _kiem_mau_link(mau_link)
    if cot:
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_kho SET " + ", ".join(f"{x}=?" for x in cot) + " WHERE id=?",
                      (*cot.values(), k["id"]))
    return lay_kho(k["id"])


def xoa_kho(kid) -> bool:
    with ds._khoa, ds._db() as c:
        return c.execute("DELETE FROM fp_kho WHERE id=?", (int(kid),)).rowcount > 0


def tach_muc(chu: str) -> list:
    """Có dòng '---' thì tách theo nó (mỗi phần nhiều dòng), không thì mỗi dòng một mục."""
    dong = str(chu or "").replace("\r\n", "\n").split("\n")
    if any(x.strip() == "---" for x in dong):
        phan, cur = [], []
        for x in dong:
            if x.strip() == "---":
                phan.append("\n".join(cur).strip())
                cur = []
            else:
                cur.append(x)
        phan.append("\n".join(cur).strip())
        return [p for p in phan if p]
    return [x.strip() for x in dong if x.strip()]


def nhap_kho(kid, chu: str) -> dict:
    k = _hang_kho(kid)
    if not k:
        raise ValueError(f"không có kho #{kid}")
    moi = _kiem_muc(k["loai"], tach_muc(chu))
    if not moi:
        raise ValueError("không có mục nào để nhập")
    sua_kho(k["id"], muc=k["muc"] + moi)
    return {"so": len(moi), "kho": lay_kho(k["id"])}


def so_tu_ten_tep(ten: str) -> Optional[int]:
    """'12.mp4', 'phim_12.jpg', 'tap-012.mp4' -> 12. Không có số -> None."""
    so = re.findall(r"\d+", Path(ten_goc(ten)).stem)
    return int(so[-1]) if so else None


def chon_tu_kho(kid, ten_tep: str = "", rnd=None, con_tro: Optional[dict] = None) -> Optional[str]:
    """Lấy một mục theo chế độ của kho. `con_tro` (dict kid -> số) cho phép chọn nhiều lần không ghi
    DB (xem trước, tạo hàng loạt); None = tăng con trỏ trong DB ngay."""
    import random
    rnd = rnd or random
    k = _hang_kho(kid)
    if not k or not k["muc"]:
        return None
    muc = k["muc"]

    def lan_luot():
        if con_tro is not None:
            i = con_tro.get(k["id"], k["con_tro"] or 0)
            con_tro[k["id"]] = i + 1
        else:
            with ds._khoa, ds._db() as c:
                i = c.execute("SELECT con_tro FROM fp_kho WHERE id=?", (k["id"],)).fetchone()[0] or 0
                c.execute("UPDATE fp_kho SET con_tro=? WHERE id=?", (i + 1, k["id"]))
        return muc[i % len(muc)]

    if k["che_do"] == "ngau_nhien":
        return rnd.choice(muc)
    if k["che_do"] == "stt":
        n = so_tu_ten_tep(ten_tep) if ten_tep else None
        if n is not None and 1 <= n <= len(muc):
            return muc[n - 1]
    return lan_luot()


def ghi_con_tro(con_tro: dict) -> None:
    with ds._khoa, ds._db() as c:
        for kid, i in (con_tro or {}).items():
            c.execute("UPDATE fp_kho SET con_tro=? WHERE id=?", (int(i), int(kid)))


def slug_tep(ten: str) -> str:
    s = ds._bo_dau(Path(ten_goc(ten)).stem if "." in ten_goc(ten) else ten_goc(ten))
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9_-]", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def dung_link(mau_link: str, ten_tep: str) -> str:
    mau = _kiem_mau_link(mau_link)
    if not mau:
        raise ValueError("chưa có mẫu link")
    return mau.replace("{ten_tep}", slug_tep(ten_tep or ""))


def link_cho(kho_id, gan_loai: str, ten_tep: str = "", rnd=None, con_tro: Optional[dict] = None) -> str:
    """Link nối vào caption (gan_loai='noi_dung') hoặc bình luận ('binh_luan') của kho `kho_id`."""
    if not kho_id:
        return ""
    with ds._db() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM fp_kho WHERE loai='link' ORDER BY id").fetchall()]
    for i in ids:
        k = _hang_kho(i)
        if int(kho_id) not in (k["gan"].get(gan_loai) or []):
            continue
        if k["mau_link"] and ten_tep:
            return dung_link(k["mau_link"], ten_tep)
        return chon_tu_kho(i, ten_tep, rnd, con_tro) or ""
    return ""


# ------------------------------------------------------------------ spin

def _ngay_vn(luc: Optional[float] = None) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(luc if luc is not None else _now(), _tz()).strftime("%d/%m/%Y")


def spin(mau: str, rnd=None, bien: Optional[dict] = None) -> str:
    """`{a|b|{c|d}}` lồng nhau, chọn ngẫu nhiên. Ở cấp ngoài cùng `{{` và `}}` là ngoặc chữ thật
    (bên trong một nhóm thì `}}` là hai lần đóng, để `{a|{b|c}}` chạy đúng). Biến `{ten_trang}`,
    `{ngay}`, `{ten_tep}` thay từ `bien`; biến không có giá trị thì giữ nguyên chữ."""
    import random
    rnd = rnd or random
    bien = dict(bien or {})
    bien.setdefault("ngay", _ngay_vn())
    s = str(mau or "")
    n = len(s)

    def nhom(i):
        """s[i] == '{'. Trả (chữ đã chọn, vị trí sau '}') hoặc None nếu không đóng."""
        m = re.match(r"\{(" + "|".join(BIEN_SPIN) + r")\}", s[i:])
        if m:
            ten = m.group(1)
            return (str(bien[ten]) if bien.get(ten) is not None else m.group(0)), i + len(m.group(0))
        lua, cur = [], []
        j = i + 1
        while j < n:
            ch = s[j]
            if ch == "{":
                kq = nhom(j)
                if kq is None:
                    cur.append(ch)
                    j += 1
                    continue
                cur.append(kq[0])
                j = kq[1]
            elif ch == "|":
                lua.append("".join(cur))
                cur = []
                j += 1
            elif ch == "}":
                lua.append("".join(cur))
                return rnd.choice(lua), j + 1
            else:
                cur.append(ch)
                j += 1
        return None

    out, i = [], 0
    while i < n:
        if s.startswith("{{", i):
            out.append("{")
            i += 2
        elif s.startswith("}}", i):
            out.append("}")
            i += 2
        elif s[i] == "{":
            kq = nhom(i)
            if kq is None:
                out.append(s[i])
                i += 1
            else:
                out.append(kq[0])
                i = kq[1]
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


# ------------------------------------------------------------------ lịch

def _phut(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def tinh_lich(cau_hinh_lich: Optional[dict], so: int, bat_dau: float, da_co: Iterable = (),
              chi_so_trang: int = 0, rnd=None) -> list:
    """Danh sách `so` mốc giờ (ts) cho một Trang. `tat` -> [] (không tự xếp)."""
    import random
    from datetime import datetime, timedelta
    rnd = rnd or random
    lich = _gop(LICH_MAC_DINH, _kiem_lich(cau_hinh_lich or {}) or {})
    so = max(0, min(BAI_MOT_LAN_TOI_DA, int(so or 0)))
    if lich["che_do"] == "tat" or so == 0:
        return []
    tz = _tz()
    tu, den = _phut(lich["tu"]), _phut(lich["den"])
    kep = tu < den
    lech = int(lich["lech_phut"])
    trai = int(chi_so_trang) * int(lich["trai_phut"])
    chiem = [float(x) for x in da_co if x]
    ra: list = []
    som_nhat = bat_dau + 120

    def ngay0(dt):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    def kep_khung(t: float) -> float:
        if not kep:
            return t
        dt = datetime.fromtimestamp(t, tz)
        p = dt.hour * 60 + dt.minute
        if p < tu:
            return (ngay0(dt) + timedelta(minutes=tu)).timestamp()
        if p > den:
            return (ngay0(dt) + timedelta(minutes=den)).timestamp()
        return t

    def them(goc_ts: float) -> None:
        t = goc_ts + (rnd.uniform(-lech, lech) if lech else 0) * 60 + trai * 60
        t = kep_khung(max(t, som_nhat))
        if any(abs(t - x) < LICH_GAN_PHUT * 60 for x in chiem + ra):
            return
        ra.append(t)

    d0 = ngay0(datetime.fromtimestamp(bat_dau, tz))
    if lich["che_do"] == "gio":
        gio = lich["gio"] or LICH_MAC_DINH["gio"]
        for ngay in range(0, 800):
            dn = d0 + timedelta(days=ngay)
            for g in gio:
                if len(ra) >= so:
                    break
                goc_ts = (dn + timedelta(minutes=_phut(g))).timestamp()
                if goc_ts + trai * 60 < som_nhat:
                    continue                      # khung đã qua
                # khung đã có bài của Trang (cách < 20 phút) thì bỏ khung, không dồn sang khung khác
                if any(abs(goc_ts + trai * 60 - x) < LICH_GAN_PHUT * 60 for x in chiem):
                    continue
                them(goc_ts)
            if len(ra) >= so:
                break
    else:                                          # chu_ky
        buoc = int(lich["moi_gio"]) * 3600
        dt = datetime.fromtimestamp(som_nhat, tz)
        moc = dt.replace(minute=0, second=0, microsecond=0)
        if moc.timestamp() < som_nhat:
            moc = moc + timedelta(hours=1)
        t = moc.timestamp()
        for _ in range(20000):
            if len(ra) >= so:
                break
            if kep:
                dtt = datetime.fromtimestamp(t, tz)
                p = dtt.hour * 60 + dtt.minute
                if p < tu:
                    t = (ngay0(dtt) + timedelta(minutes=tu)).timestamp()
                elif p > den:
                    t = (ngay0(dtt) + timedelta(days=1, minutes=tu)).timestamp()
                    continue
            them(t)
            t += buoc
    return sorted(ra[:so])


def cach_hen_cho(loai: str, cach: str, hen_luc: Optional[float], now: Optional[float] = None) -> str:
    now = _now() if now is None else now
    if (cach == "fb" and loai not in ("story", "reel", "album") and hen_luc
            and now + FB_HEN_TU < hen_luc < now + FB_HEN_DEN):
        return "fb"
    return "tool"


def gio_da_co(trang_id: str, tru_id=None) -> list:
    with ds._db() as c:
        q = ("SELECT hen_luc FROM fp_bai WHERE trang_id=? AND trang_thai IN ('cho_duyet','cho_dang','da_hen_fb') "
             "AND hen_luc IS NOT NULL")
        a = [str(trang_id)]
        if tru_id:
            q += " AND id!=?"
            a.append(int(tru_id))
        return [r[0] for r in c.execute(q, a).fetchall()]


def xem_truoc_lich(cau_hinh_lich=None, trang_id: str = "", so: int = 10, bat_dau: Optional[float] = None,
                   rnd=None) -> list:
    bat_dau = _now() if bat_dau is None else bat_dau
    so = max(1, min(100, int(so or 10)))
    if trang_id:
        t = hang_trang(trang_id)
        if not t:
            raise ValueError(f"không có Trang {trang_id}")
        lich = hieu_luc(trang_id)["lich"] if cau_hinh_lich is None else cau_hinh_lich
        return tinh_lich(lich, so, bat_dau, gio_da_co(trang_id), 0, rnd)
    return tinh_lich(cau_hinh_lich or {}, so, bat_dau, (), 0, rnd)


# ------------------------------------------------------------------ media

def ten_goc(tep: str) -> str:
    """Tên tệp trước khi máy chủ gắn đuôi ngẫu nhiên `__abcdef` (để đếm STT, dựng link)."""
    ten = str(tep or "").split("/")[-1]
    p = Path(ten)
    return re.sub(r"__[a-z]{6}$", "", p.stem) + p.suffix


def loai_media(tep: str) -> str:
    d = Path(str(tep)).suffix.lower()
    if d in DUOI_ANH:
        return "anh"
    if d in DUOI_VIDEO:
        return "video"
    return ""


def kiem_duoi_media(ten: str) -> str:
    loai = loai_media(ten)
    if not loai:
        raise ValueError(f"chỉ nhận ảnh ({', '.join(sorted(DUOI_ANH))}) hoặc video ({', '.join(sorted(DUOI_VIDEO))}): "
                         f"{Path(str(ten)).name[:80]}")
    return loai


def _ten_an_toan(ten: str) -> str:
    ten = str(ten or "").replace("\\", "/").split("/")[-1].replace("\x00", "")
    ten = re.sub(r'[\x00-\x1f<>:"|?*#%&{}$!`\']', "", ten).strip().lstrip(".")
    return ten[:150] or "tep"


def luu_media(ten: str, tam) -> dict:
    """Chuyển tệp tạm vào kho media với tên an toàn + đuôi ngẫu nhiên. Trả {tep, ten, loai, dai}."""
    loai = kiem_duoi_media(ten)
    goc = _ten_an_toan(ten)
    p = Path(goc)
    duoi = p.suffix.lower()
    than = p.stem[:120] or "tep"
    import random as _r
    hau = "".join(_r.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))
    dich = thu_muc() / "media" / f"{than}__{hau}{duoi}"
    shutil.move(str(tam), str(dich))
    return {"tep": dich.name, "ten": goc, "loai": loai, "dai": dich.stat().st_size}


def duong_media(tep: str) -> Optional[Path]:
    """Tệp media theo tên lưu. Nhận `ten` (trong media/) hoặc `kenh/<id>/<ten>`. Chặn thoát thư mục."""
    s = str(tep or "")
    if not s or "\x00" in s or "\\" in s or len(s) > 400:
        return None
    m = re.fullmatch(r"kenh/(\d{1,10})/([^/]+)", s)
    if m:
        ten = m.group(2)
        goc = thu_muc() / "kenh" / m.group(1)
    elif "/" in s:
        return None
    else:
        ten = s
        goc = thu_muc() / "media"
    if ten.startswith(".") or ten in ("", ".", ".."):
        return None
    p = goc / ten
    try:
        p.resolve().relative_to(thu_muc().resolve())
    except (ValueError, OSError):
        return None
    return p if p.is_file() else None


def ds_media(gioi: int = 300) -> list:
    goc = thu_muc() / "media"
    ra = []
    for p in sorted(goc.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:gioi]:
        if p.is_file() and loai_media(p.name):
            ra.append({"tep": p.name, "ten": ten_goc(p.name), "loai": loai_media(p.name), "dai": p.stat().st_size,
                       "luc": p.stat().st_mtime})
    return ra


def don_tep(sau_ngay: int, now: Optional[float] = None) -> int:
    """Xoá tệp chỉ thuộc bài đã đăng/bỏ quá `sau_ngay` ngày (không đụng tệp bài còn chờ)."""
    now = _now() if now is None else now
    if sau_ngay <= 0:
        return 0
    han = now - sau_ngay * 86400
    with ds._db() as c:
        giu = set()
        xoa = set()
        for r in c.execute("SELECT media, trang_thai, dang_luc, tao_luc FROM fp_bai").fetchall():
            ms = _j(r["media"], [])
            if r["trang_thai"] in ("da_dang", "bo") and (r["dang_luc"] or r["tao_luc"] or now) < han:
                xoa.update(ms)
            else:
                giu.update(ms)
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='social_campaign'").fetchone():
            for row in c.execute("SELECT settings FROM social_campaign WHERE state IN ('planning','active','paused','error')"):
                giu.update((_j(row[0], {}).get('image') or {}).get('media') or [])
            for row in c.execute("SELECT data FROM social_campaign_run WHERE state IN ('new','writing','generating','waiting_media')"):
                giu.update(_j(row[0], {}).get('media') or [])
    so = 0
    for t in xoa - giu:
        p = duong_media(t)
        if p:
            try:
                p.unlink()
                so += 1
            except OSError:
                pass
    return so


# ------------------------------------------------------------------ mã công khai (IG cần URL công khai)

def _b64(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def ma_cong_khai(tep: str, song: int = CONG_KHAI_SONG, now: Optional[float] = None) -> str:
    if not duong_media(tep):
        raise ValueError(f"không có tệp {tep}")
    het = int((_now() if now is None else now) + song)
    than = f"{het}:{tep}".encode()
    ky = hmac.new(_bi_mat(), than, hashlib.sha256).digest()[:18]
    return _b64(than) + "." + _b64(ky)


def doc_ma_cong_khai(ma: str, now: Optional[float] = None) -> Optional[Path]:
    try:
        a, b = str(ma or "").split(".", 1)
        than = _unb64(a)
        ky = _unb64(b)
    except Exception:
        return None
    dung = hmac.new(_bi_mat(), than, hashlib.sha256).digest()[:18]
    if not hmac.compare_digest(dung, ky):
        return None
    try:
        het_s, tep = than.decode().split(":", 1)
        het = int(het_s)
    except Exception:
        return None
    if (_now() if now is None else now) > het:
        return None
    return duong_media(tep)


def url_cong_khai(tep: str) -> str:
    goc = goc_cong_khai()
    if not goc:
        return ""
    return f"{goc}/doi-social/fp/cong-khai/{ma_cong_khai(tep)}"


# ------------------------------------------------------------------ bài

def _khoa_trung(trang_id: str, loai: str, noi_dung: str, media: list) -> str:
    s = "|".join([str(trang_id), loai, ds._bo_dau(noi_dung), ",".join(ten_goc(m) for m in media)])
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _dong_bai(r, trang: Optional[dict] = None) -> dict:
    d = dict(r)
    d["media"] = _j(d.get("media"), [])
    d["so_lieu"] = _j(d.get("so_lieu"), {})
    d["story"] = bool(d.get("story"))
    d["ig"] = bool(d.get("ig"))
    if trang is not None:
        d["trang_ten"] = trang.get("ten") or ""
        d["trang_anh"] = trang.get("anh") or ""
    return d


def lay_bai(bid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT b.*, t.ten AS trang_ten, t.anh AS trang_anh FROM fp_bai b LEFT JOIN fp_trang t "
                      "ON t.id=b.trang_id WHERE b.id=?", (int(bid),)).fetchone()
    return _dong_bai(r) if r else None


def _loc_bai(trang_thai="", trang="", nhom="", loai="", tu=None, den=None, q="") -> tuple:
    w, a = [], []
    if trang_thai:
        tts = [x for x in str(trang_thai).split(",") if x in TT_BAI]
        if tts:
            w.append("b.trang_thai IN (" + ",".join("?" * len(tts)) + ")")
            a += tts
    if trang:
        w.append("b.trang_id=?")
        a.append(str(trang))
    if nhom not in (None, ""):
        if str(nhom) in ("0", "chua"):
            w.append("t.nhom_id IS NULL")
        else:
            w.append("t.nhom_id=?")
            a.append(int(nhom))
    if loai:
        w.append("b.loai=?")
        a.append(loai)
    if tu:
        w.append("COALESCE(b.dang_luc, b.hen_luc, b.tao_luc) >= ?")
        a.append(float(tu))
    if den:
        w.append("COALESCE(b.dang_luc, b.hen_luc, b.tao_luc) <= ?")
        a.append(float(den))
    if q:
        w.append("(b.noi_dung LIKE ? OR b.post_id LIKE ?)")
        a += [f"%{q}%", f"%{q}%"]
    return (" WHERE " + " AND ".join(w)) if w else "", a


def ds_bai(trang_thai="", trang="", nhom="", loai="", tu=None, den=None, q="", sap_xep="moi",
           trang_so=1, moi_trang=50) -> dict:
    t, m, off = _trang_so(trang_so, moi_trang)
    wh, a = _loc_bai(trang_thai, trang, nhom, loai, tu, den, q)
    wh0, a0 = _loc_bai("", trang, nhom, loai, tu, den, q)
    thu_tu = {"hen": "b.hen_luc IS NULL, b.hen_luc ASC, b.id",
              "tuong_tac": "CAST(COALESCE(json_extract(b.so_lieu, '$.tuong_tac'), 0) AS INTEGER) DESC, b.id DESC"
              }.get(sap_xep, "b.id DESC")
    tu_bang = "FROM fp_bai b LEFT JOIN fp_trang t ON t.id=b.trang_id"
    with ds._db() as c:
        tong = c.execute(f"SELECT COUNT(*) {tu_bang}{wh}", a).fetchone()[0]
        rows = c.execute(f"SELECT b.*, t.ten AS trang_ten, t.anh AS trang_anh {tu_bang}{wh} ORDER BY {thu_tu} "
                         "LIMIT ? OFFSET ?", (*a, m, off)).fetchall()
        dem = {r[0]: r[1] for r in c.execute(f"SELECT b.trang_thai, COUNT(*) {tu_bang}{wh0} GROUP BY b.trang_thai",
                                            a0).fetchall()}
    return {"muc": [_dong_bai(r) for r in rows], "tong": tong, "trang": t, "dem": {**{x: 0 for x in TT_BAI}, **dem}}


def bai_csv(**loc) -> str:
    import csv
    import io
    from datetime import datetime
    loc.pop("trang_so", None)
    loc.pop("moi_trang", None)
    tz = _tz()

    def gio(x):
        return datetime.fromtimestamp(x, tz).strftime("%Y-%m-%d %H:%M") if x else ""

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "trang", "loai", "trang_thai", "hen_luc", "dang_luc", "noi_dung", "media", "post_id", "url",
                "loi", "tiep_can", "tuong_tac", "nguon"])
    trang_so = 1
    while True:
        kq = ds_bai(**loc, trang_so=trang_so, moi_trang=500)
        for b in kq["muc"]:
            sl = b["so_lieu"] or {}
            w.writerow([b["id"], b.get("trang_ten") or b["trang_id"], b["loai"], b["trang_thai"], gio(b["hen_luc"]),
                        gio(b["dang_luc"]), b["noi_dung"], " ".join(b["media"]), b["post_id"], b["url"], b["loi"],
                        sl.get("tiep_can", ""), sl.get("tuong_tac", ""), b["nguon"]])
        if trang_so * 500 >= kq["tong"]:
            break
        trang_so += 1
    return "﻿" + buf.getvalue()


def _don_vi(loai: str, noi_dung, media, so_bai: int) -> list:
    """Các 'đơn vị' nội dung: [(media_list, noi_dung_hoac_None)]."""
    if isinstance(media, list) and media and all(isinstance(x, list) for x in media):
        nhom_media = [[str(y) for y in x if y] for x in media]
        nhom_media = [x for x in nhom_media if x]
    elif isinstance(media, list) and media:
        phang = [str(x) for x in media if x]
        nhom_media = [phang] if loai == "album" else [[x] for x in phang]
    else:
        nhom_media = []
    nd = [str(x) for x in (noi_dung or []) if str(x or "").strip()] if isinstance(noi_dung, list) else (
        [str(noi_dung)] if isinstance(noi_dung, str) and noi_dung.strip() else [])
    if nhom_media:
        if len(nd) > 1 and len(nd) != len(nhom_media):
            raise ValueError(f"số nội dung ({len(nd)}) phải bằng số đơn vị media ({len(nhom_media)}) hoặc chỉ 1")
        return [(m, (nd[i] if len(nd) > 1 else (nd[0] if nd else None))) for i, m in enumerate(nhom_media)]
    if nd:
        return [([], x) for x in nd]
    return [([], None) for _ in range(max(1, min(BAI_MOT_LAN_TOI_DA, int(so_bai or 1))))]


def _kiem_media_loai(loai: str, media: list) -> None:
    for t in media:
        if not duong_media(t):
            raise ValueError(f"không thấy tệp media '{t}' (tải lên lại)")
    ls = [loai_media(t) for t in media]
    if loai == "chu" and media:
        raise ValueError("bài chữ không kèm media (chọn loại ảnh/video)")
    if loai in ("anh", "album") and (not media or any(x != "anh" for x in ls)):
        raise ValueError(f"bài {loai} cần tệp ảnh")
    if loai == "anh" and len(media) > 1:
        raise ValueError("bài ảnh đơn chỉ một ảnh mỗi bài (dùng album cho nhiều ảnh)")
    if loai == "album" and not 2 <= len(media) <= 30:
        raise ValueError("album cần từ 2 đến 30 ảnh")
    if loai in ("video", "reel") and (len(media) != 1 or ls[0] != "video"):
        raise ValueError(f"bài {loai} cần đúng một tệp video")
    if loai == "story" and len(media) != 1:
        raise ValueError("story cần đúng một ảnh hoặc video")


def tao_bai(*, trang_ids=None, nhom_id=None, loai: str = "chu", noi_dung=None, kho_id=None, media=None,
            chia: str = "", binh_luan=None, kho_binh_luan_id=None, story=None, ig=None, hen="tu_dong",
            chay_thu: bool = False, nguon: str = "tay", link: str = "", so_bai: int = 1, rnd=None,
            now: Optional[float] = None, ep_duyet: bool = False, idempotency_key: str = "") -> dict:
    """Tạo bài hàng loạt (mục 8 hợp đồng). Raise ValueError tiếng Việt.

    `hen`: 'tu_dong' (lịch nhóm/Trang) | 'ngay' | mốc epoch | {"bat_dau": epoch, "cach_phut": n}
    (26.10.200: bài thứ k, đếm qua mọi Trang theo thứ tự tạo, đăng lúc bat_dau + k*cach_phut).
    `ep_duyet`: luôn vào chờ duyệt dù nhóm tắt duyet_truoc (bài AI viết)."""
    import random
    if idempotency_key and not chay_thu:
        with ds._db() as db:
            old = db.execute("SELECT id FROM fp_bai WHERE campaign_key=?", (idempotency_key,)).fetchone()
        if old:
            return {"so": 1, "muc": [lay_bai(old[0])], "bo_trung": 0, "xem_truoc": None}
    rnd = rnd or random
    now = _now() if now is None else now
    if loai not in LOAI_BAI:
        raise ValueError("loại bài phải là chu, anh, album, video, reel hoặc story")
    if nguon not in NGUON_BAI:
        nguon = "tay"
    if isinstance(binh_luan, int) and not isinstance(binh_luan, bool):
        kho_binh_luan_id, binh_luan = binh_luan, None
    # ---- Trang
    if trang_ids:
        ids = [str(x) for x in trang_ids]
    elif nhom_id:
        with ds._db() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM fp_trang WHERE nhom_id=? AND bat=1 ORDER BY ten",
                                           (int(nhom_id),)).fetchall()]
        if not ids:
            raise ValueError("nhóm chưa có Trang nào đang bật")
    else:
        raise ValueError("chọn Trang hoặc nhóm để đăng")
    trang = []
    for tid in dict.fromkeys(ids):
        t = hang_trang(tid)
        if not t:
            raise ValueError(f"không có Trang {tid}")
        trang.append(t)
    if kho_id and not (_hang_kho(kho_id) or {}).get("loai") == "noi_dung":
        raise ValueError(f"kho #{kho_id} không phải kho nội dung")
    if kho_binh_luan_id and not (_hang_kho(kho_binh_luan_id) or {}).get("loai") == "binh_luan":
        raise ValueError(f"kho #{kho_binh_luan_id} không phải kho bình luận")
    link = _chu(link, 1000)
    if link and not re.match(r"https?://\S+$", link):
        raise ValueError("link phải bắt đầu bằng http(s)://")
    don_vi = _don_vi(loai, noi_dung, media, so_bai)
    for m, _ in don_vi:
        _kiem_media_loai(loai, m)
    hl0 = hieu_luc(trang[0]["id"])
    chia = chia or (hl0.get("chia_video") if loai in ("video", "reel") else "") or "mot_trang"
    if chia not in ("mot_trang", "tat_ca"):
        raise ValueError("chia phải là mot_trang hoặc tat_ca")
    # ---- ghép đơn vị -> Trang
    cap: list = []
    if chia == "tat_ca":
        for t in trang:
            for dv in don_vi:
                cap.append((t, dv))
    else:
        for i, dv in enumerate(don_vi):
            cap.append((trang[i % len(trang)], dv))
    if len(cap) > BAI_MOT_LAN_TOI_DA:
        raise ValueError(f"tối đa {BAI_MOT_LAN_TOI_DA} bài mỗi lần (đang là {len(cap)})")
    cd = cai_dat()
    con_tro: dict = {}
    with ds._db() as c:
        khoa_cu = {r[0] for r in c.execute("SELECT khoa_trung FROM fp_bai WHERE trang_thai!='bo' AND khoa_trung!=''")}
    khoa_moi = set()
    bai_moi, bo_trung = [], 0
    dem_trang: dict = {}
    for t, (m, nd) in cap:
        hl = hieu_luc(t["id"])
        ten_tep = ten_goc(m[0]) if m else ""
        bien = {"ten_trang": t["ten"], "ten_tep": Path(ten_tep).stem if ten_tep else ""}
        kho_nd = kho_id or (None if nd is not None else hl.get("kho_noi_dung"))
        goc_nd = nd if nd is not None else (chon_tu_kho(kho_nd, ten_tep, rnd, con_tro) if kho_nd else "")
        if goc_nd is None:
            goc_nd = ""
        cap_chu = spin(goc_nd, rnd, bien).strip()
        lk = link_cho(kho_nd, "noi_dung", ten_tep, rnd, con_tro) if kho_nd else ""
        if lk:
            cap_chu = (cap_chu + "\n" + lk).strip()
        if loai == "chu" and not cap_chu and not link:
            raise ValueError("bài chữ cần nội dung (nhập chữ hoặc chọn kho nội dung có mục)")
        if len(cap_chu) > CHU_TOI_DA:
            raise ValueError(f"nội dung quá dài (tối đa {CHU_TOI_DA} ký tự)")
        # bình luận sau đăng
        bl = ""
        if isinstance(binh_luan, str) and binh_luan.strip():
            bl = spin(binh_luan, rnd, bien).strip()
        else:
            kbl = kho_binh_luan_id or (hl.get("kho_binh_luan") if hl.get("binh_luan_sau_dang") else None)
            if kbl:
                bl = spin(chon_tu_kho(kbl, ten_tep, rnd, con_tro) or "", rnd, bien).strip()
                lkb = link_cho(kbl, "binh_luan", ten_tep, rnd, con_tro)
                if lkb:
                    bl = (bl + "\n" + lkb).strip()
        st = bool(hl.get("story") if story is None else story) and loai != "story"
        g = bool(hl.get("ig_dong_bo") if ig is None else ig) and bool(t.get("ig_id"))
        khoa = _khoa_trung(t["id"], loai, cap_chu if nguon != "kenh" else (nd or ""), m)
        if not cd["cho_dang_trung"] and (khoa in khoa_cu or khoa in khoa_moi):
            bo_trung += 1
            continue
        khoa_moi.add(khoa)
        dem_trang.setdefault(t["id"], []).append(len(bai_moi))
        bai_moi.append({"trang_id": t["id"], "nhom_id": t.get("nhom_id"), "loai": loai, "noi_dung": cap_chu,
                        "media": m, "link": link if loai == "chu" else "", "binh_luan": bl, "story": int(st),
                        "ig": int(g), "hen_luc": None, "cach_hen": "tool",
                        "trang_thai": "cho_duyet" if (ep_duyet or hl.get("duyet_truoc", True)) else "cho_dang",
                        "nguon": nguon, "khoa_trung": khoa, "trang_ten": t["ten"], "trang_anh": t.get("anh") or ""})
    # ---- giờ đăng
    if isinstance(hen, dict):
        try:
            bd = float(hen.get("bat_dau") or now)
            cach = max(0, min(7 * 24 * 60, int(hen.get("cach_phut") or 0)))
        except (TypeError, ValueError):
            raise ValueError("giờ bắt đầu / khoảng cách không hợp lệ")
        if bd < now - 60:
            raise ValueError("giờ bắt đầu đã qua")
        if bd > now + 60 * 86400:
            raise ValueError("giờ bắt đầu tối đa 60 ngày tới")
        for k, b in enumerate(bai_moi):
            b["hen_luc"] = bd + k * cach * 60
            lich = hieu_luc(b["trang_id"])["lich"]
            b["cach_hen"] = cach_hen_cho(loai, lich.get("cach", "tool"), b["hen_luc"], now)
        dem_trang = {}
    for chi_so, t in enumerate(trang):
        vt = dem_trang.get(t["id"]) or []
        if not vt:
            continue
        lich = hieu_luc(t["id"])["lich"]
        if hen == "ngay":
            gio = [now] * len(vt)
        elif isinstance(hen, (int, float)) and not isinstance(hen, bool):
            if hen < now - 60:
                raise ValueError("giờ hẹn đã qua")
            gio = [float(hen)] * len(vt)
        elif hen in (None, "", "tu_dong"):
            gio = tinh_lich(lich, len(vt), now, gio_da_co(t["id"]), chi_so, rnd)
            gio = gio + [None] * (len(vt) - len(gio))
        else:
            raise ValueError("hen phải là 'tu_dong', 'ngay' hoặc một mốc thời gian")
        for i, vi in enumerate(vt):
            b = bai_moi[vi]
            b["hen_luc"] = gio[i]
            b["cach_hen"] = cach_hen_cho(loai, lich.get("cach", "tool"), gio[i], now)
    if chay_thu:
        return {"so": len(bai_moi), "muc": [], "bo_trung": bo_trung, "xem_truoc": bai_moi}
    ra = []
    if idempotency_key and len(bai_moi) > 1:
        raise ValueError('Mỗi khóa chiến dịch chỉ tạo một bài')
    with ds._khoa, ds._db() as c:
        if idempotency_key:
            old = c.execute("SELECT id FROM fp_bai WHERE campaign_key=?", (idempotency_key,)).fetchone()
            if old:
                return {"so": 1, "muc": [lay_bai(old[0])], "bo_trung": 0, "xem_truoc": None}
        for b in bai_moi:
            bid = c.execute(
                "INSERT INTO fp_bai(trang_id, nhom_id, loai, noi_dung, media, link, binh_luan, story, ig, hen_luc, "
                "cach_hen, trang_thai, nguon, khoa_trung, tao_luc,campaign_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (b["trang_id"], b["nhom_id"], b["loai"], b["noi_dung"], _dj(b["media"]), b["link"], b["binh_luan"],
                 b["story"], b["ig"], b["hen_luc"], b["cach_hen"], b["trang_thai"], b["nguon"], b["khoa_trung"],
                 now, idempotency_key)).lastrowid
            ra.append(bid)
    ghi_con_tro(con_tro)
    if ra:
        ghi_nk("tao_bai", "", None, "thong_tin", f"tạo {len(ra)} bài ({loai}, nguồn {nguon})"
               + (f", bỏ {bo_trung} bài trùng" if bo_trung else ""))
    return {"so": len(ra), "muc": [lay_bai(i) for i in ra], "bo_trung": bo_trung, "xem_truoc": None}


def sua_bai(bid, noi_dung=None, hen_luc=_KHONG_DOI, binh_luan=None, link=None) -> dict:
    b = lay_bai(bid)
    if not b:
        raise ValueError(f"không có bài #{bid}")
    if b["trang_thai"] not in ("cho_duyet", "cho_dang", "loi"):
        raise ValueError(f"bài #{bid} đang '{b['trang_thai']}', không sửa được")
    cot = {}
    if noi_dung is not None:
        nd = _chu(noi_dung, CHU_TOI_DA + 1)
        if len(nd) > CHU_TOI_DA:
            raise ValueError(f"nội dung quá dài (tối đa {CHU_TOI_DA} ký tự)")
        if b["loai"] == "chu" and not nd and not b["link"]:
            raise ValueError("bài chữ cần nội dung")
        cot["noi_dung"] = nd
        cot["khoa_trung"] = _khoa_trung(b["trang_id"], b["loai"], nd, b["media"])
    if binh_luan is not None:
        cot["binh_luan"] = _chu(binh_luan, CHU_TOI_DA)
    if link is not None:
        lk = _chu(link, 1000)
        if lk and not re.match(r"https?://\S+$", lk):
            raise ValueError("link phải bắt đầu bằng http(s)://")
        cot["link"] = lk
    if hen_luc is not _KHONG_DOI:
        if hen_luc in (None, ""):
            cot["hen_luc"] = None
            cot["cach_hen"] = "tool"
        else:
            h = float(hen_luc)
            if h < _now() - 60:
                raise ValueError("giờ hẹn đã qua")
            cot["hen_luc"] = h
            cot["cach_hen"] = cach_hen_cho(b["loai"], hieu_luc(b["trang_id"])["lich"].get("cach", "tool"), h)
    if cot:
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_bai SET " + ", ".join(f"{k}=?" for k in cot) + " WHERE id=?",
                      (*cot.values(), int(bid)))
    return lay_bai(bid)


def hanh_dong_bai(ids, hanh_dong: str, now: Optional[float] = None) -> dict:
    now = _now() if now is None else now
    if hanh_dong not in ("duyet", "bo", "dang_ngay", "thu_lai", "xoa", "xep_lai_lich"):
        raise ValueError(f"hành động lạ: {hanh_dong}")
    ids = [int(x) for x in (ids or [])][:2000]
    if not ids:
        raise ValueError("chưa chọn bài nào")
    so, loi = 0, []
    with ds._khoa, ds._db() as c:
        rows = {r["id"]: dict(r) for r in c.execute(
            f"SELECT * FROM fp_bai WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()}
    xep = []
    for i in ids:
        b = rows.get(i)
        if not b:
            loi.append({"id": i, "loi": "không có bài"})
            continue
        tt = b["trang_thai"]
        moi = None
        if hanh_dong == "duyet" and tt == "cho_duyet":
            moi = {"trang_thai": "cho_dang"}
        elif hanh_dong == "bo" and tt in ("cho_duyet", "cho_dang", "loi"):
            moi = {"trang_thai": "bo"}
        elif hanh_dong == "dang_ngay" and tt in ("cho_duyet", "cho_dang", "loi"):
            moi = {"trang_thai": "cho_dang", "hen_luc": now, "cach_hen": "tool", "so_lan_thu": 0, "loi": ""}
        elif hanh_dong == "thu_lai" and tt == "loi":
            moi = {"trang_thai": "cho_dang", "so_lan_thu": 0, "loi": "",
                   "hen_luc": b["hen_luc"] if b["hen_luc"] and b["hen_luc"] > now else now, "cach_hen": "tool"}
        elif hanh_dong == "thu_lai" and tt in ("da_dang", "da_hen_fb") and "loi" in (b["bl_tt"], b["story_tt"], b["ig_tt"]):
            moi = {k: "cho" for k in ("bl_tt", "story_tt", "ig_tt") if b[k] == "loi"}
        elif hanh_dong == "xoa" and tt != "dang_dang":
            moi = "xoa"
        elif hanh_dong == "xep_lai_lich" and tt in ("cho_duyet", "cho_dang"):
            xep.append(b)
            continue
        if moi is None:
            loi.append({"id": i, "loi": f"bài đang '{tt}', không {hanh_dong} được"})
            continue
        with ds._khoa, ds._db() as c:
            if moi == "xoa":
                c.execute("DELETE FROM fp_bai WHERE id=?", (i,))
            else:
                c.execute("UPDATE fp_bai SET " + ", ".join(f"{k}=?" for k in moi) + " WHERE id=?", (*moi.values(), i))
        so += 1
    if xep:
        theo_trang: dict = {}
        for b in xep:
            theo_trang.setdefault(b["trang_id"], []).append(b)
        for chi_so, (tid, ds_b) in enumerate(theo_trang.items()):
            with ds._db() as c:
                bo_id = [b["id"] for b in ds_b]
                da = [r[0] for r in c.execute(
                    f"SELECT hen_luc FROM fp_bai WHERE trang_id=? AND trang_thai IN ('cho_duyet','cho_dang','da_hen_fb') "
                    f"AND hen_luc IS NOT NULL AND id NOT IN ({','.join('?' * len(bo_id))})", (tid, *bo_id)).fetchall()]
            lich = hieu_luc(tid)["lich"]
            gio = tinh_lich(lich, len(ds_b), now, da, 0)
            gio = gio + [None] * (len(ds_b) - len(gio))
            for b, h in zip(sorted(ds_b, key=lambda x: x["id"]), gio):
                with ds._khoa, ds._db() as c:
                    c.execute("UPDATE fp_bai SET hen_luc=?, cach_hen=? WHERE id=?",
                              (h, cach_hen_cho(b["loai"], lich.get("cach", "tool"), h, now), b["id"]))
                so += 1
    return {"so": so, "loi": loi}


def nhan_bai_toi_han(now: float, gioi: int) -> list:
    """Giành các bài `cho_dang` tới giờ đăng (đổi sang `dang_dang`). Bài hẹn kiểu fb còn xa giờ thì
    gửi ngay để Facebook giữ; sát giờ (< 10 phút) thì đăng thường khi tới giờ."""
    with ds._khoa, ds._db() as c:
        rows = c.execute(
            "SELECT b.id, b.cach_hen, b.hen_luc FROM fp_bai b JOIN fp_trang t ON t.id=b.trang_id "
            "WHERE b.trang_thai='cho_dang' AND b.hen_luc IS NOT NULL AND t.bat=1 AND "
            "((b.cach_hen='fb' AND b.hen_luc > ?) OR b.hen_luc <= ?) ORDER BY b.hen_luc, b.id LIMIT ?",
            (now + 10 * 60, now, int(gioi))).fetchall()
        ra = []
        for r in rows:
            if r["cach_hen"] == "fb" and r["hen_luc"] <= now + 10 * 60:
                c.execute("UPDATE fp_bai SET cach_hen='tool' WHERE id=?", (r["id"],))
            n = c.execute("UPDATE fp_bai SET trang_thai='dang_dang' WHERE id=? AND trang_thai='cho_dang'",
                          (r["id"],)).rowcount
            if n:
                ra.append(r["id"])
    return ra


def giu_bai_dang(bid) -> bool:
    """Giành một bài để đăng ngay (nút Đăng ngay / kiểm thử)."""
    with ds._khoa, ds._db() as c:
        return c.execute("UPDATE fp_bai SET trang_thai='dang_dang' WHERE id=? AND trang_thai='cho_dang'",
                         (int(bid),)).rowcount > 0


def ket_qua_dang(bid, *, ok: bool, post_id: str = "", url: str = "", loi: str = "", hen_fb: bool = False,
                 thu_lai_sau: Optional[float] = None, now: Optional[float] = None) -> dict:
    now = _now() if now is None else now
    b = lay_bai(bid)
    if not b:
        raise ValueError(f"không có bài #{bid}")
    with ds._khoa, ds._db() as c:
        if ok:
            t = hang_trang(b["trang_id"]) or {}
            c.execute("UPDATE fp_bai SET trang_thai=?, post_id=?, url=?, loi='', dang_luc=?, bl_tt=?, story_tt=?, "
                      "ig_tt=? WHERE id=?",
                      ("da_hen_fb" if hen_fb else "da_dang", _chu(post_id, 120), _chu(url, 500),
                       b["hen_luc"] if hen_fb else now, "cho" if b["binh_luan"] else "",
                       "cho" if b["story"] and b["loai"] != "story" else "",
                       "cho" if b["ig"] and t.get("ig_id") else "", int(bid)))
        elif thu_lai_sau is not None:
            c.execute("UPDATE fp_bai SET trang_thai='cho_dang', loi=?, so_lan_thu=so_lan_thu+1, hen_luc=?, "
                      "cach_hen='tool' WHERE id=?", (_loc_token(_chu(loi, 500)), now + thu_lai_sau, int(bid)))
        else:
            c.execute("UPDATE fp_bai SET trang_thai='loi', loi=?, so_lan_thu=so_lan_thu+1, dang_luc=? WHERE id=?",
                      (_loc_token(_chu(loi, 500)), now, int(bid)))
    if ok:
        ghi_nk("dang_bai", b["trang_id"], int(bid), "thanh_cong",
               ("đã hẹn trên Facebook" if hen_fb else "đã đăng") + f" {b['loai']}" + (f": {url}" if url else ""))
    elif thu_lai_sau is None:
        ghi_nk("dang_bai", b["trang_id"], int(bid), "loi", loi)
    return lay_bai(bid)


def dat_phu(bid, **kw) -> None:
    """Cập nhật trạng thái các bước phụ (bl_tt, story_tt, ig_tt, ig_media_id, so_lieu, trang_thai...)."""
    cot = {k: v for k, v in kw.items() if k in ("bl_tt", "story_tt", "ig_tt", "ig_media_id", "trang_thai", "loi",
                                                 "so_lieu", "url")}
    if "so_lieu" in cot and not isinstance(cot["so_lieu"], str):
        cot["so_lieu"] = _dj(cot["so_lieu"])
    if "loi" in cot:
        cot["loi"] = _loc_token(_chu(cot["loi"], 500))
    if cot:
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_bai SET " + ", ".join(f"{k}=?" for k in cot) + " WHERE id=?",
                      (*cot.values(), int(bid)))


def bai_cho_phu(now: float, gioi: int = 20) -> list:
    """Bài đã đăng/đã hẹn còn bước phụ (bình luận sau 60s, story, IG) tới lượt."""
    with ds._db() as c:
        rows = c.execute(
            "SELECT * FROM fp_bai WHERE trang_thai IN ('da_dang','da_hen_fb') AND dang_luc IS NOT NULL AND "
            "dang_luc <= ? AND (bl_tt='cho' OR story_tt='cho' OR ig_tt IN ('cho','xu_ly')) ORDER BY dang_luc LIMIT ?",
            (now, int(gioi))).fetchall()
    return [_dong_bai(r) for r in rows]


def chot_hen_fb(now: float) -> int:
    """Bài đã hẹn trên Facebook qua giờ 2 phút -> coi như đã đăng."""
    with ds._khoa, ds._db() as c:
        return c.execute("UPDATE fp_bai SET trang_thai='da_dang' WHERE trang_thai='da_hen_fb' AND hen_luc < ?",
                         (now - 120,)).rowcount


def ig_24h(trang_id: str = "", now: Optional[float] = None) -> int:
    now = _now() if now is None else now
    with ds._db() as c:
        q, a = "SELECT COUNT(*) FROM fp_bai WHERE ig_tt='xong' AND dang_luc > ?", [now - 86400]
        if trang_id:
            q += " AND trang_id=?"
            a.append(trang_id)
        return c.execute(q, a).fetchone()[0]


def ds_instagram(now: Optional[float] = None) -> list:
    cd = cai_dat()
    with ds._db() as c:
        rows = c.execute("SELECT id, ten, ig_id, ig_ten FROM fp_trang WHERE ig_id!='' ORDER BY ten").fetchall()
    return [{"trang_id": r["id"], "trang_ten": r["ten"], "ig_id": r["ig_id"], "ig_ten": r["ig_ten"],
             "da_dang_24h": ig_24h(r["id"], now), "toi_da": cd["ig_toi_da_24h"]} for r in rows]


def ghi_so_lieu_bai(bid, so_lieu: dict) -> None:
    b = lay_bai(bid)
    if not b:
        return
    sl = dict(b["so_lieu"] or {})
    sl.update({k: v for k, v in so_lieu.items() if isinstance(v, (int, float))})
    sl["tuong_tac"] = int(sl.get("cam_xuc", 0)) + int(sl.get("binh_luan", 0)) + int(sl.get("chia_se", 0))
    sl["cap_nhat"] = _now()
    dat_phu(bid, so_lieu=sl)


def ghi_so_lieu_trang(trang_id: str, ngay: str, **kw) -> None:
    with ds._khoa, ds._db() as c:
        cu = c.execute("SELECT * FROM fp_so_lieu WHERE trang_id=? AND ngay=?", (trang_id, ngay)).fetchone()
        d = dict(cu) if cu else {"nguoi_theo_doi": None, "tiep_can": None, "tuong_tac": None, "luot_xem": None}
        for k in ("nguoi_theo_doi", "tiep_can", "tuong_tac", "luot_xem"):
            if kw.get(k) is not None:
                d[k] = int(kw[k])
        c.execute("INSERT OR REPLACE INTO fp_so_lieu(trang_id, ngay, nguoi_theo_doi, tiep_can, tuong_tac, luot_xem) "
                  "VALUES(?,?,?,?,?,?)", (trang_id, ngay, d["nguoi_theo_doi"], d["tiep_can"], d["tuong_tac"],
                                          d["luot_xem"]))
        if kw.get("nguoi_theo_doi") is not None:
            c.execute("UPDATE fp_trang SET nguoi_theo_doi=? WHERE id=?", (int(kw["nguoi_theo_doi"]), trang_id))


def bai_can_so_lieu(now: float, gioi: int = 50) -> list:
    with ds._db() as c:
        rows = c.execute("SELECT * FROM fp_bai WHERE trang_thai='da_dang' AND post_id!='' AND dang_luc > ? "
                         "ORDER BY dang_luc DESC LIMIT ?", (now - 30 * 86400, int(gioi))).fetchall()
    return [_dong_bai(r) for r in rows]


# ------------------------------------------------------------------ bình luận

def ghi_binh_luan(trang_id: str, post_id: str, d: dict) -> bool:
    """Ghi một bình luận từ Graph. Trả True nếu mới."""
    cid = _chu(d.get("id"), 80)
    if not cid:
        return False
    tu = d.get("from") or {}
    tu_id = _chu(tu.get("id") if isinstance(tu, dict) else "", 40)
    from datetime import datetime
    luc = _now()
    ct = d.get("created_time")
    if ct:
        try:
            luc = datetime.strptime(str(ct).replace("+0000", "+00:00"), "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except ValueError:
            pass
    cha = d.get("parent") or {}
    with ds._khoa, ds._db() as c:
        cu = c.execute("SELECT id FROM fp_binh_luan WHERE id=?", (cid,)).fetchone()
        if cu:
            c.execute("UPDATE fp_binh_luan SET noi_dung=?, an=? WHERE id=?",
                      (_chu(d.get("message"), 8000), int(bool(d.get("is_hidden"))), cid))
            return False
        c.execute("INSERT INTO fp_binh_luan(id, trang_id, post_id, cha_id, tu_id, tu_ten, noi_dung, luc, la_cua_trang, "
                  "an, trang_thai, cap_nhat) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, str(trang_id), _chu(post_id, 120), _chu(cha.get("id") if isinstance(cha, dict) else "", 80),
                   tu_id, _chu(tu.get("name") if isinstance(tu, dict) else "", 200), _chu(d.get("message"), 8000), luc,
                   int(tu_id == str(trang_id)), int(bool(d.get("is_hidden"))),
                   "bo_qua" if tu_id == str(trang_id) else "moi", _now()))
    return True


def _dong_bl(r) -> dict:
    d = dict(r)
    d["an"] = bool(d.get("an"))
    d["la_cua_trang"] = bool(d.get("la_cua_trang"))
    return d


def lay_binh_luan(cid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT b.*, t.ten AS trang_ten FROM fp_binh_luan b LEFT JOIN fp_trang t ON t.id=b.trang_id "
                      "WHERE b.id=?", (str(cid),)).fetchone()
    return _dong_bl(r) if r else None


def ds_binh_luan(trang="", trang_thai="", chi_khach=False, q="", tu=None, trang_so=1, moi_trang=50) -> dict:
    t, m, off = _trang_so(trang_so, moi_trang)
    w, a = [], []
    if trang:
        w.append("b.trang_id=?")
        a.append(str(trang))
    if trang_thai:
        tts = [x for x in str(trang_thai).split(",") if x in TT_BL]
        if tts:
            w.append("b.trang_thai IN (" + ",".join("?" * len(tts)) + ")")
            a += tts
    if chi_khach:
        w.append("b.la_cua_trang=0")
    if q:
        w.append("(b.noi_dung LIKE ? OR b.tu_ten LIKE ?)")
        a += [f"%{q}%", f"%{q}%"]
    if tu:
        w.append("b.luc >= ?")
        a.append(float(tu))
    wh = (" WHERE " + " AND ".join(w)) if w else ""
    import doi_social_v2 as v2
    dau = v2._dau_ngay()
    with ds._db() as c:
        tong = c.execute(f"SELECT COUNT(*) FROM fp_binh_luan b{wh}", a).fetchone()[0]
        rows = c.execute(f"SELECT b.*, t.ten AS trang_ten FROM fp_binh_luan b LEFT JOIN fp_trang t ON t.id=b.trang_id"
                         f"{wh} ORDER BY b.luc DESC LIMIT ? OFFSET ?", (*a, m, off)).fetchall()
        hn = {r[0]: r[1] for r in c.execute("SELECT trang_thai, COUNT(*) FROM fp_binh_luan WHERE cap_nhat >= ? "
                                            "GROUP BY trang_thai", (dau,)).fetchall()}
        cho = {r[0]: r[1] for r in c.execute("SELECT trang_thai, COUNT(*) FROM fp_binh_luan WHERE trang_thai IN "
                                             "('cho_gui','cho_duyet') GROUP BY trang_thai").fetchall()}
    return {"muc": [_dong_bl(r) for r in rows], "tong": tong, "trang": t,
            "hom_nay": {"da_tra_loi": hn.get("da_tra_loi", 0), "cho_gui": cho.get("cho_gui", 0),
                        "cho_duyet": cho.get("cho_duyet", 0), "loi": hn.get("loi", 0)},
            "quet_luc": _cd_doc("fp_quet_luc", None)}


def dat_binh_luan(cid, **kw) -> None:
    cot = {k: v for k, v in kw.items() if k in ("trang_thai", "tra_loi", "quy_tac_id", "loi", "an", "de_xuat")}
    if "loi" in cot:
        cot["loi"] = _loc_token(_chu(cot["loi"], 500))
    if "tra_loi" in cot:
        cot["tra_loi"] = _chu(cot["tra_loi"], 8000)
    cot["cap_nhat"] = _now()
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE fp_binh_luan SET " + ", ".join(f"{k}=?" for k in cot) + " WHERE id=?",
                  (*cot.values(), str(cid)))


def binh_luan_cho_gui(gioi: int = 20) -> list:
    with ds._db() as c:
        return [_dong_bl(r) for r in c.execute(
            "SELECT * FROM fp_binh_luan WHERE trang_thai='cho_gui' ORDER BY cap_nhat LIMIT ?", (int(gioi),)).fetchall()]


def ghi_quet_luc(now: Optional[float] = None) -> None:
    _cd_ghi("fp_quet_luc", _now() if now is None else now)


# ---- quy tắc

def _dong_qt(r) -> dict:
    d = dict(r)
    d["pham_vi"] = _j(d.get("pham_vi"), {})
    d["tu_khoa"] = _j(d.get("tu_khoa"), [])
    d["mau"] = _j(d.get("mau"), [])
    d["tu_gui"] = bool(d.get("tu_gui"))
    d["bat"] = bool(d.get("bat"))
    return d


def _kiem_qt(d: dict, cu: Optional[dict] = None) -> dict:
    cu = cu or {}
    ra = {}
    ten = _chu(d.get("ten", cu.get("ten")), 120)
    if not ten:
        raise ValueError("quy tắc cần có tên")
    ra["ten"] = ten
    pv = d.get("pham_vi", cu.get("pham_vi")) or {}
    if not isinstance(pv, dict):
        raise ValueError("'pham_vi' phải là object {nhom:[id], trang:[id]}")
    ra["pham_vi"] = {"nhom": [int(x) for x in (pv.get("nhom") or [])][:500],
                     "trang": [str(x) for x in (pv.get("trang") or [])][:2000]}
    tk = d.get("tu_khoa", cu.get("tu_khoa")) or []
    if isinstance(tk, str):
        tk = [x for x in re.split(r"[,\n]", tk)]
    ra["tu_khoa"] = [_chu(x, 100) for x in tk if _chu(x, 100)][:200]
    hd = d.get("hanh_dong", cu.get("hanh_dong") or "tra_loi")
    if hd not in HANH_DONG_QT:
        raise ValueError("hành động phải là tra_loi, tra_loi_ai, an hoặc an_va_tra_loi")
    ra["hanh_dong"] = hd
    mau = d.get("mau", cu.get("mau")) or []
    if isinstance(mau, str):
        mau = tach_muc(mau)
    ra["mau"] = [_chu(x, 2000) for x in mau if _chu(x, 2000)][:200]
    if hd in ("tra_loi", "an_va_tra_loi") and not ra["mau"]:
        raise ValueError("quy tắc trả lời cần ít nhất một câu mẫu")
    ra["tu_gui"] = int(bool(d.get("tu_gui", cu.get("tu_gui", False))))
    ra["bat"] = int(bool(d.get("bat", cu.get("bat", True))))
    ra["uu_tien"] = _int(d.get("uu_tien", cu.get("uu_tien", 0)) or 0, "uu_tien", -1000, 1000)
    return ra


def ds_quy_tac() -> list:
    with ds._db() as c:
        return [_dong_qt(r) for r in c.execute("SELECT * FROM fp_quy_tac ORDER BY uu_tien DESC, id").fetchall()]


def lay_quy_tac(qid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_quy_tac WHERE id=?", (int(qid),)).fetchone()
    return _dong_qt(r) if r else None


def tao_quy_tac(d: dict) -> dict:
    q = _kiem_qt(d or {})
    with ds._khoa, ds._db() as c:
        qid = c.execute("INSERT INTO fp_quy_tac(ten, pham_vi, tu_khoa, hanh_dong, mau, tu_gui, bat, uu_tien, tao_luc) "
                        "VALUES(?,?,?,?,?,?,?,?,?)", (q["ten"], _dj(q["pham_vi"]), _dj(q["tu_khoa"]), q["hanh_dong"],
                                                      _dj(q["mau"]), q["tu_gui"], q["bat"], q["uu_tien"], _now())).lastrowid
    return lay_quy_tac(qid)


def sua_quy_tac(qid, d: dict) -> dict:
    cu = lay_quy_tac(qid)
    if not cu:
        raise ValueError(f"không có quy tắc #{qid}")
    q = _kiem_qt(d or {}, cu)
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE fp_quy_tac SET ten=?, pham_vi=?, tu_khoa=?, hanh_dong=?, mau=?, tu_gui=?, bat=?, uu_tien=? "
                  "WHERE id=?", (q["ten"], _dj(q["pham_vi"]), _dj(q["tu_khoa"]), q["hanh_dong"], _dj(q["mau"]),
                                 q["tu_gui"], q["bat"], q["uu_tien"], int(qid)))
    return lay_quy_tac(qid)


def xoa_quy_tac(qid) -> bool:
    with ds._khoa, ds._db() as c:
        return c.execute("DELETE FROM fp_quy_tac WHERE id=?", (int(qid),)).rowcount > 0


def khop_tu_khoa(tu_khoa: list, noi_dung: str) -> bool:
    """Không phân biệt dấu/hoa thường, khớp theo ranh giới từ ('ib' không khớp 'vibe')."""
    if not tu_khoa:
        return True
    s = ds._bo_dau(noi_dung)
    for k in tu_khoa:
        g = ds._bo_dau(k)
        if g and re.search(r"(?<!\w)" + re.escape(g) + r"(?!\w)", s):
            return True
    return False


def _trong_pham_vi(q: dict, trang: dict) -> bool:
    pv = q.get("pham_vi") or {}
    nh, tr = pv.get("nhom") or [], pv.get("trang") or []
    if not nh and not tr:
        return True
    return str(trang.get("id")) in tr or (trang.get("nhom_id") in nh)


def ap_quy_tac(cid, rnd=None) -> Optional[dict]:
    """Áp quy tắc cho một bình luận 'moi' của khách. Trả {quy_tac, hanh_dong, tu_gui} hoặc None.
    An toàn: dung_tu_dong -> không áp; tu_gui=0 -> 'cho_duyet' (chủ bấm gửi/ẩn)."""
    import random
    rnd = rnd or random
    if dung_tu_dong():
        return None
    bl = lay_binh_luan(cid)
    if not bl or bl["la_cua_trang"] or bl["trang_thai"] != "moi":
        return None
    t = hang_trang(bl["trang_id"])
    if not t:
        return None
    hl = hieu_luc(t["id"])
    for q in ds_quy_tac():
        if not q["bat"] or not _trong_pham_vi(q, t) or not khop_tu_khoa(q["tu_khoa"], bl["noi_dung"]):
            continue
        hd = q["hanh_dong"]
        co_an = hd in ("an", "an_va_tra_loi")
        co_tl = hd in ("tra_loi", "an_va_tra_loi", "tra_loi_ai")
        if co_an and not hl.get("tu_an"):
            co_an = False
        if co_tl and not hl.get("tu_tra_loi"):
            co_tl = False
        if not co_an and not co_tl:
            continue
        de_xuat = "an_va_tra_loi" if co_an and co_tl else ("an" if co_an else "tra_loi")
        if hd == "tra_loi_ai" and co_tl:
            de_xuat = "tra_loi_ai"
        tra = ""
        if co_tl and hd != "tra_loi_ai" and q["mau"]:
            tra = spin(rnd.choice(q["mau"]), rnd, {"ten_trang": t["ten"]}).strip()
        tt = "cho_gui" if q["tu_gui"] and hd != "tra_loi_ai" else "cho_duyet"
        dat_binh_luan(cid, trang_thai=tt, tra_loi=tra, quy_tac_id=q["id"], de_xuat=de_xuat, loi="")
        return {"quy_tac": q["id"], "hanh_dong": de_xuat, "tu_gui": q["tu_gui"]}
    return None


# ------------------------------------------------------------------ kênh nguồn

def _nen_tang_link(link: str) -> str:
    s = link.lower()
    for k, v in (("youtube.com", "youtube"), ("youtu.be", "youtube"), ("tiktok.com", "tiktok"),
                 ("facebook.com", "facebook"), ("fb.watch", "facebook"), ("instagram.com", "instagram"),
                 ("douyin.com", "douyin"), ("bilibili.com", "bilibili")):
        if k in s:
            return v
    return "khac"


def _kiem_kenh(d: dict, cu: Optional[dict] = None) -> dict:
    cu = cu or {}
    ra = {}
    link = _chu(d.get("link", cu.get("link")), 500)
    if not re.match(r"https://\S+$", link):
        raise ValueError("link kênh phải bắt đầu bằng https:// và không có khoảng trắng")
    ra["link"] = link
    ra["nen_tang"] = _chu(d.get("nen_tang") or cu.get("nen_tang") or _nen_tang_link(link), 30)
    ra["ten"] = _chu(d.get("ten", cu.get("ten")), 200)
    tids = d.get("trang_ids", cu.get("trang_ids")) or []
    if not isinstance(tids, list):
        raise ValueError("'trang_ids' phải là danh sách")
    for x in tids:
        if not hang_trang(str(x)):
            raise ValueError(f"không có Trang {x}")
    ra["trang_ids"] = [str(x) for x in tids]
    nid = d.get("nhom_id", cu.get("nhom_id"))
    if nid:
        if not lay_nhom(nid):
            raise ValueError(f"không có nhóm #{nid}")
        nid = int(nid)
    ra["nhom_id"] = nid or None
    if not ra["trang_ids"] and not ra["nhom_id"]:
        raise ValueError("chọn Trang hoặc nhóm nhận video của kênh")
    chia = d.get("chia", cu.get("chia") or "xoay")
    if chia not in CHIA_KENH:
        raise ValueError("chia phải là xoay hoặc tat_ca")
    ra["chia"] = chia
    lb = d.get("loai_bai", cu.get("loai_bai") or "reel")
    if lb not in ("reel", "video"):
        raise ValueError("loại bài của kênh phải là reel hoặc video")
    ra["loai_bai"] = lb
    ra["theo_doi"] = int(bool(d.get("theo_doi", cu.get("theo_doi", True))))
    ra["chu_ky_gio"] = _int(d.get("chu_ky_gio", cu.get("chu_ky_gio", 6)), "chu_ky_gio", 1, 168)
    ra["toi_da_moi_lan"] = _int(d.get("toi_da_moi_lan", cu.get("toi_da_moi_lan", 5)), "toi_da_moi_lan", 1, 50)
    return ra


def _dong_kenh(r) -> dict:
    d = dict(r)
    d["trang_ids"] = _j(d.get("trang_ids"), [])
    d["theo_doi"] = bool(d.get("theo_doi"))
    with ds._db() as c:
        ten = {x["id"]: x["ten"] for x in c.execute("SELECT id, ten FROM fp_trang").fetchall()}
        nh = c.execute("SELECT ten FROM fp_nhom WHERE id=?", (d.get("nhom_id"),)).fetchone() if d.get("nhom_id") else None
    d["trang_ten"] = [ten.get(x, x) for x in d["trang_ids"]]
    d["nhom_ten"] = nh["ten"] if nh else ""
    return d


def ds_kenh() -> list:
    with ds._db() as c:
        return [_dong_kenh(r) for r in c.execute("SELECT * FROM fp_kenh ORDER BY id").fetchall()]


def lay_kenh(kid) -> Optional[dict]:
    with ds._db() as c:
        r = c.execute("SELECT * FROM fp_kenh WHERE id=?", (int(kid),)).fetchone()
    return _dong_kenh(r) if r else None


def tao_kenh(d: dict) -> dict:
    k = _kiem_kenh(d or {})
    with ds._khoa, ds._db() as c:
        kid = c.execute("INSERT INTO fp_kenh(nen_tang, link, ten, trang_ids, nhom_id, chia, loai_bai, theo_doi, "
                        "chu_ky_gio, toi_da_moi_lan, tao_luc) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (k["nen_tang"], k["link"], k["ten"], _dj(k["trang_ids"]), k["nhom_id"], k["chia"],
                         k["loai_bai"], k["theo_doi"], k["chu_ky_gio"], k["toi_da_moi_lan"], _now())).lastrowid
    return lay_kenh(kid)


def sua_kenh(kid, d: dict) -> dict:
    cu = lay_kenh(kid)
    if not cu:
        raise ValueError(f"không có kênh #{kid}")
    k = _kiem_kenh(d or {}, cu)
    with ds._khoa, ds._db() as c:
        c.execute("UPDATE fp_kenh SET nen_tang=?, link=?, ten=?, trang_ids=?, nhom_id=?, chia=?, loai_bai=?, theo_doi=?, "
                  "chu_ky_gio=?, toi_da_moi_lan=? WHERE id=?",
                  (k["nen_tang"], k["link"], k["ten"], _dj(k["trang_ids"]), k["nhom_id"], k["chia"], k["loai_bai"],
                   k["theo_doi"], k["chu_ky_gio"], k["toi_da_moi_lan"], int(kid)))
    return lay_kenh(kid)


def dat_kenh(kid, **kw) -> None:
    cot = {k: v for k, v in kw.items() if k in ("trang_thai", "loi", "lan_quet", "so_video", "ten")}
    if "loi" in cot:
        cot["loi"] = _loc_token(_chu(cot["loi"], 500))
    if cot:
        with ds._khoa, ds._db() as c:
            c.execute("UPDATE fp_kenh SET " + ", ".join(f"{k}=?" for k in cot) + " WHERE id=?",
                      (*cot.values(), int(kid)))


def xoa_kenh(kid) -> bool:
    with ds._khoa, ds._db() as c:
        n = c.execute("DELETE FROM fp_kenh WHERE id=?", (int(kid),)).rowcount
        c.execute("DELETE FROM fp_kenh_video WHERE kenh_id=?", (int(kid),))
    shutil.rmtree(str(thu_muc() / "kenh" / str(int(kid))), ignore_errors=True)
    return n > 0


def kenh_toi_han(now: float) -> list:
    return [k for k in ds_kenh() if k["theo_doi"] and (not k["lan_quet"] or now - k["lan_quet"] >= k["chu_ky_gio"] * 3600)]


def video_da_co(kid) -> set:
    with ds._db() as c:
        return {r[0] for r in c.execute("SELECT ma FROM fp_kenh_video WHERE kenh_id=?", (int(kid),)).fetchall()}


def ghi_video_kenh(kid, ma: str, tieu_de: str, tep: str, trang_thai: str = "da_tai") -> None:
    with ds._khoa, ds._db() as c:
        c.execute("INSERT OR REPLACE INTO fp_kenh_video(kenh_id, ma, tieu_de, tep, luc, trang_thai) VALUES(?,?,?,?,?,?)",
                  (int(kid), _chu(ma, 120), _chu(tieu_de, 500), _chu(tep, 400), _now(), _chu(trang_thai, 20)))
        c.execute("UPDATE fp_kenh SET so_video=(SELECT COUNT(*) FROM fp_kenh_video WHERE kenh_id=? AND "
                  "trang_thai!='loi') WHERE id=?", (int(kid), int(kid)))


def trang_cua_kenh(k: dict) -> list:
    ids = list(k.get("trang_ids") or [])
    if not ids and k.get("nhom_id"):
        with ds._db() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM fp_trang WHERE nhom_id=? AND bat=1 ORDER BY ten",
                                           (int(k["nhom_id"]),)).fetchall()]
    return ids


# ------------------------------------------------------------------ cảnh báo

def _cb(muc, ma, doi_tuong, tieu_de, chi_tiet, cach_sua, toi) -> dict:
    return {"muc": muc, "ma": ma, "doi_tuong": str(doi_tuong or ""), "tieu_de": tieu_de, "chi_tiet": chi_tiet,
            "cach_sua": cach_sua, "toi": toi}


def _ma_loi(loi: str) -> str:
    m = re.match(r"#(\d+)", str(loi or ""))
    if m:
        return m.group(1)
    if "tệp" in str(loi or ""):
        return "tep"
    return "khac"


def kiem_loi(co_ket_noi: int = 0, co_yt_dlp: bool = True, now: Optional[float] = None, luu: bool = True) -> list:
    """Danh sách cảnh báo hiện tại (mục 7). `luu` = ghi lịch sử xuất hiện / hết."""
    now = _now() if now is None else now
    ra = []
    tok = ds_token_noi_bo()
    with ds._db() as c:
        trang = [dict(r) for r in c.execute("SELECT * FROM fp_trang").fetchall()]
        nhom = _bang_nhom(c)
        loi_bai = c.execute("SELECT loi, COUNT(*) n, MAX(trang_id) t FROM fp_bai WHERE trang_thai='loi' AND "
                            "COALESCE(dang_luc, tao_luc) > ? GROUP BY loi", (now - 86400,)).fetchall()
        cho_trang = {r[0]: (r[1], r[2]) for r in c.execute(
            "SELECT trang_id, COUNT(*), MAX(hen_luc) FROM fp_bai WHERE trang_thai IN ('cho_duyet','cho_dang','da_hen_fb') "
            "GROUP BY trang_id").fetchall()}
        kenh = c.execute("SELECT id, ten, link, trang_thai, loi FROM fp_kenh").fetchall()
        kho = {r["id"]: dict(r) for r in c.execute("SELECT id, ten, loai, muc FROM fp_kho").fetchall()}
    cd = cai_dat()
    if not tok and not co_ket_noi:
        ra.append(_cb("chan", "chua_token", "", "Chưa có nguồn token nào",
                      "Fanpage cần token của Trang để đăng bằng Graph API.",
                      "Nối 'Facebook Trang (tự tạo app)' ở trang Kết nối, hoặc dán token ở tab Token.",
                      "#/fp-trang?tab=token"))
    elif tok and all(t["trang_thai"] in ("loi", "het_han") for t in tok):
        ra.append(_cb("chan", "moi_token_loi", "", "Mọi token đều lỗi",
                      f"{len(tok)} nguồn token, không nguồn nào dùng được.",
                      CACH_SUA_LOI["190"], "#/fp-trang?tab=token"))
    for t in tok:
        tid = ("kn:" + t["ket_noi_id"]) if t["loai"] == "ket_noi" else str(t["id"])
        if t.get("het_han") and t["het_han"] > now and t["het_han"] - now < 7 * 86400:
            ngay = max(0, int((t["het_han"] - now) // 86400))
            ra.append(_cb("nang", "token_sap_het", tid, f"Token '{t['nhan']}' sắp hết hạn",
                          f"Còn khoảng {ngay} ngày.", "Nối lại kết nối hoặc dán token mới trước khi hết hạn.",
                          "#/fp-trang?tab=token"))
    for t in trang:
        if not t["bat"]:
            continue
        quyen = _j(t["quyen"], [])
        if quyen and not any(x in quyen for x in QUYEN_DANG):
            ra.append(_cb("chan", "mat_quyen_dang", t["id"], f"Trang '{t['ten']}' không có quyền đăng",
                          "Tài khoản nối không có quyền tạo nội dung (CREATE_CONTENT) trên Trang này.",
                          CACH_SUA_LOI["10"], f"#/fp-trang?trang={t['id']}"))
        ch_t = _j(t["cau_hinh"], {})
        ch_n = (nhom.get(t["nhom_id"]) or {}).get("cau_hinh") or {}
        hl, nguon = _hieu_luc_tho(ch_t, ch_n)
        co_lich = hl["lich"]["che_do"] != "tat"
        so_cho, cuoi = cho_trang.get(t["id"], (0, None))
        if co_lich and nguon != "mac_dinh":
            kid = hl.get("kho_noi_dung")
            kho_rong = not kid or not _j((kho.get(kid) or {}).get("muc"), [])
            if so_cho == 0 and kho_rong:
                ra.append(_cb("nang", "het_bai", t["id"], f"Trang '{t['ten']}' hết bài",
                              "Trang có lịch đăng nhưng không còn bài chờ và kho nội dung rỗng.",
                              "Tạo bài hàng loạt hoặc thêm mục vào kho nội dung của nhóm/Trang.", "#/fp-bai"))
            elif so_cho and cuoi and cuoi < now + 86400:
                ra.append(_cb("nhac", "hang_cho_het", t["id"], f"Hàng chờ của '{t['ten']}' sắp hết",
                              "Bài chờ cuối cùng đăng trong 24 giờ tới.", "Tạo thêm bài cho Trang này.", "#/fp-bai"))
        if t["ig_id"] and ig_24h(t["id"], now) >= cd["ig_toi_da_24h"]:
            ra.append(_cb("nang", "ig_han", t["id"], f"Instagram của '{t['ten']}' chạm hạn 24 giờ",
                          f"Đã đăng {cd['ig_toi_da_24h']} bài trong 24 giờ qua.",
                          "Đợi qua 24 giờ; bài IG mới sẽ tự đăng khi còn hạn.", "#/fp-bai"))
    chua = [t for t in trang if t["bat"] and not t["nhom_id"] and not (_j(t["cau_hinh"], {}) or {}).get("lich")]
    if chua:
        ra.append(_cb("nhac", "chua_nhom", "", f"{len(chua)} Trang chưa thuộc nhóm và chưa có lịch",
                      ", ".join(t["ten"] for t in chua[:8]) + (" ..." if len(chua) > 8 else ""),
                      "Gán nhóm (nhóm có lịch đăng) hoặc đặt lịch riêng cho Trang.", "#/fp-trang"))
    for r in loi_bai:
        ma = _ma_loi(r["loi"])
        ra.append(_cb("nang", "bai_loi", ma, f"{r['n']} bài lỗi trong 24 giờ" + (f" (#{ma})" if ma.isdigit() else ""),
                      str(r["loi"] or "")[:300],
                      CACH_SUA_LOI.get(ma, "Xem chi tiết lỗi ở trang Bài đăng rồi bấm Thử lại."),
                      "#/fp-bai?trang_thai=loi"))
    for k in kenh:
        if k["trang_thai"] == "loi":
            ra.append(_cb("nang", "kenh_loi", k["id"], f"Kênh nguồn '{k['ten'] or k['link']}' lỗi",
                          str(k["loi"] or "")[:300], "Kiểm tra link kênh còn công khai rồi bấm Quét lại.", "#/fp-kenh"))
    if kenh and not co_yt_dlp:
        ra.append(_cb("nang", "thieu_yt_dlp", "", "Máy chủ thiếu yt-dlp",
                      "Kênh nguồn cần yt-dlp để tải video.", "Cập nhật MinMin bản mới (image có sẵn yt-dlp) hoặc "
                      "chạy 'pip install yt-dlp' trên máy chủ.", "#/fp-kenh"))
    dang_gan = set()
    for ch in [(_j(t["cau_hinh"], {})) for t in trang] + [v["cau_hinh"] for v in nhom.values()]:
        for kk in ("kho_noi_dung", "kho_binh_luan", "kho_tieu_su"):
            if ch.get(kk):
                dang_gan.add(ch[kk])
    for kid in sorted(dang_gan):
        k = kho.get(kid)
        if k and not _j(k["muc"], []):
            ra.append(_cb("nhac", "kho_trong", kid, f"Kho '{k['ten']}' đang được gắn nhưng trống",
                          "Nhóm/Trang dùng kho này sẽ không có nội dung.", "Nhập thêm mục vào kho.", "#/fp-kho"))
    if cd["dung_tu_dong"]:
        ra.append(_cb("nhac", "dung_tu_dong", "", "Đang bật Dừng mọi tự động",
                      "Không tự đăng, không tự trả lời, không quét kênh. Bài đã hẹn trên Facebook vẫn lên.",
                      "Tắt Dừng mọi tự động ở trang Bình luận khi muốn chạy lại.", "#/fp-binh-luan"))
    if luu:
        _luu_canh_bao(ra, now)
    return ra


def _luu_canh_bao(ds_cb: list, now: float) -> None:
    with ds._khoa, ds._db() as c:
        mo = {(r["ma"], r["doi_tuong"]): r["id"] for r in c.execute(
            "SELECT id, ma, doi_tuong FROM fp_canh_bao WHERE het_luc IS NULL").fetchall()}
        hien = set()
        for x in ds_cb:
            k = (x["ma"], x["doi_tuong"])
            hien.add(k)
            if k in mo:
                c.execute("UPDATE fp_canh_bao SET tieu_de=?, chi_tiet=?, muc=? WHERE id=?",
                          (x["tieu_de"], x["chi_tiet"], x["muc"], mo[k]))
            else:
                c.execute("INSERT INTO fp_canh_bao(luc, muc, ma, doi_tuong, tieu_de, chi_tiet, cach_sua, toi) "
                          "VALUES(?,?,?,?,?,?,?,?)", (now, x["muc"], x["ma"], x["doi_tuong"], x["tieu_de"],
                                                      x["chi_tiet"], x["cach_sua"], x["toi"]))
        for k, i in mo.items():
            if k not in hien:
                c.execute("UPDATE fp_canh_bao SET het_luc=? WHERE id=?", (now, i))
    _cd_ghi("fp_kiem_luc", now)


def canh_bao_mo() -> list:
    with ds._db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM fp_canh_bao WHERE het_luc IS NULL ORDER BY "
                                           "CASE muc WHEN 'chan' THEN 0 WHEN 'nang' THEN 1 ELSE 2 END, id").fetchall()]


def dem_canh_bao(ds_cb: Optional[list] = None) -> dict:
    ds_cb = canh_bao_mo() if ds_cb is None else ds_cb
    d = {"chan": 0, "nang": 0, "nhac": 0}
    for x in ds_cb:
        d[x["muc"]] = d.get(x["muc"], 0) + 1
    return d


def kiem_luc() -> Optional[float]:
    return _cd_doc("fp_kiem_luc", None)


def lich_su_canh_bao(gioi: int = 200) -> list:
    with ds._db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM fp_canh_bao ORDER BY id DESC LIMIT ?",
                                           (max(1, min(1000, int(gioi))),)).fetchall()]


def xuat_chan_doan(co_ket_noi: int = 0, co_yt_dlp: bool = True) -> str:
    """Bản chẩn đoán dạng chữ để chủ gửi hỗ trợ. KHÔNG chứa token (đã che + lọc lần cuối)."""
    from datetime import datetime
    tz = _tz()

    def gio(x):
        return datetime.fromtimestamp(x, tz).strftime("%Y-%m-%d %H:%M") if x else "-"

    dong = ["MinMin - Đội Social - Fanpage (API): chẩn đoán", f"Lúc: {gio(_now())}", ""]
    dong.append(f"Cài đặt: {_dj(cai_dat())}")
    dong.append(f"Gốc URL công khai (IG): {goc_cong_khai() or '(chưa có)'}")
    dong.append(f"Kết nối OAuth facebook-pages: {co_ket_noi} ; yt-dlp: {'có' if co_yt_dlp else 'thiếu'}")
    dong.append("")
    dong.append("== Token")
    for t in ds_token():
        dong.append(f"- {t['id']} [{t['loai']}] {t['nhan']} {t['che']} trạng thái={t['trang_thai']} "
                    f"hết hạn={gio(t['het_han'])} trang={t['so_trang']} lỗi={t['loi'] or '-'}")
    dong.append("")
    dong.append("== Trang")
    for t in ds_trang()["muc"]:
        dong.append(f"- {t['id']} {t['ten']} nhóm={t['nhom_ten'] or '-'} bật={t['bat']} token={t['so_token']} "
                    f"quyền={','.join(t['quyen']) or '-'} lịch={t['cau_hinh_hieu_luc']['lich']['che_do']} "
                    f"đếm={t['dem']} lỗi={t['loi'] or '-'}")
    dong.append("")
    dong.append("== Cảnh báo đang mở")
    for x in kiem_loi(co_ket_noi, co_yt_dlp, luu=False):
        dong.append(f"- [{x['muc']}] {x['tieu_de']}: {x['chi_tiet']}")
    dong.append("")
    dong.append("== Nhật ký gần nhất")
    for n in ds_nhat_ky(50):
        dong.append(f"- {gio(n['luc'])} {n['loai']} {n['trang_ten'] or n['trang_id'] or ''} #{n['bai_id'] or ''} "
                    f"{n['ket_qua']}: {n['chi_tiet']}")
    chu = "\n".join(dong) + "\n"
    with ds._db() as c:
        for r in c.execute("SELECT token FROM fp_token WHERE token!=''").fetchall():
            if r["token"]:
                chu = chu.replace(r["token"], che(r["token"]))
    return _loc_token(chu)


# ------------------------------------------------------------------ tổng quan / báo cáo

def tong_quan(now: Optional[float] = None) -> dict:
    import doi_social_v2 as v2
    now = _now() if now is None else now
    cd = cai_dat()
    with ds._db() as c:
        tr = c.execute("SELECT COUNT(*) tong, SUM(CASE WHEN loi!='' THEN 1 ELSE 0 END) loi, "
                       "COALESCE(SUM(nguoi_theo_doi),0) theo FROM fp_trang").fetchone()
        bai = {r[0]: r[1] for r in c.execute("SELECT trang_thai, COUNT(*) FROM fp_bai GROUP BY trang_thai").fetchall()}
        tu7 = _ngay_str(now - 6 * 86400)
        sl = c.execute("SELECT COALESCE(SUM(tiep_can),0), COALESCE(SUM(tuong_tac),0) FROM fp_so_lieu WHERE ngay>=?",
                       (tu7,)).fetchone()
        dau = v2._dau_ngay(now)
        xu = []
        for i in range(13, -1, -1):
            a, b = dau - i * 86400, dau - (i - 1) * 86400
            ng = _ngay_str(a + 3600)
            n = c.execute("SELECT COUNT(*) FROM fp_bai WHERE trang_thai='da_dang' AND dang_luc>=? AND dang_luc<?",
                          (a, b)).fetchone()[0]
            tc = c.execute("SELECT COALESCE(SUM(tiep_can),0) FROM fp_so_lieu WHERE ngay=?", (ng,)).fetchone()[0]
            xu.append({"ngay": ng, "da_dang": n, "tiep_can": tc})
        top = [dict(r) for r in c.execute(
            "SELECT t.id, t.ten, t.anh, COUNT(b.id) da_dang, "
            "COALESCE(SUM(CAST(COALESCE(json_extract(b.so_lieu,'$.tuong_tac'),0) AS INTEGER)),0) tuong_tac "
            "FROM fp_trang t JOIN fp_bai b ON b.trang_id=t.id AND b.trang_thai='da_dang' AND b.dang_luc>=? "
            "GROUP BY t.id ORDER BY tuong_tac DESC, da_dang DESC LIMIT 5", (now - 7 * 86400,)).fetchall()]
        ig_tk = c.execute("SELECT COUNT(*) FROM fp_trang WHERE ig_id!=''").fetchone()[0]
        so_tok = c.execute("SELECT COUNT(*) FROM fp_token").fetchone()[0]
    co_lich = sum(1 for t in ds_trang()["muc"] if t["cau_hinh_hieu_luc"]["lich"]["che_do"] != "tat"
                  and t["nguon_cau_hinh"] != "mac_dinh")
    return {"trang": {"tong": tr["tong"] or 0, "co_lich": co_lich, "loi": tr["loi"] or 0},
            "bai": {"tong": sum(bai.values()), "da_dang": bai.get("da_dang", 0), "cho_duyet": bai.get("cho_duyet", 0),
                    "cho_dang": bai.get("cho_dang", 0), "da_hen_fb": bai.get("da_hen_fb", 0), "loi": bai.get("loi", 0)},
            "nguoi_theo_doi": tr["theo"] or 0, "tiep_can_7": sl[0], "tuong_tac_7": sl[1], "xu_huong": xu,
            "top_trang": top, "hoat_dong": ds_nhat_ky(20), "canh_bao": dem_canh_bao(),
            "ig": {"tai_khoan": ig_tk, "da_dang_24h": ig_24h("", now)}, "nguon_token": so_tok,
            "dung_tu_dong": cd["dung_tu_dong"]}


def bao_cao(trang: str = "", ngay: int = 7, now: Optional[float] = None) -> dict:
    now = _now() if now is None else now
    ngay = max(1, min(90, int(ngay or 7)))
    tu = _ngay_str(now - (ngay - 1) * 86400)
    hom_nay, hom_qua = _ngay_str(now), _ngay_str(now - 86400)
    with ds._db() as c:
        q, a = "SELECT id, ten, anh, nguoi_theo_doi FROM fp_trang", []
        if trang:
            q += " WHERE id=?"
            a.append(trang)
        trs = [dict(r) for r in c.execute(q + " ORDER BY ten", a).fetchall()]
        for t in trs:
            s = c.execute("SELECT COALESCE(SUM(tiep_can),0), COALESCE(SUM(tuong_tac),0), COALESCE(SUM(luot_xem),0) "
                          "FROM fp_so_lieu WHERE trang_id=? AND ngay>=?", (t["id"], tu)).fetchone()
            t["tiep_can"], t["tuong_tac"], t["luot_xem"] = s[0], s[1], s[2]
            a1 = c.execute("SELECT nguoi_theo_doi FROM fp_so_lieu WHERE trang_id=? AND ngay=?", (t["id"], hom_nay)).fetchone()
            a0 = c.execute("SELECT nguoi_theo_doi FROM fp_so_lieu WHERE trang_id=? AND ngay=?", (t["id"], hom_qua)).fetchone()
            t["tang_24h"] = (a1[0] - a0[0]) if a1 and a0 and a1[0] is not None and a0[0] is not None else 0
        qb, ab = ("SELECT b.id, b.trang_id, t.ten AS trang_ten, b.noi_dung, b.url, b.dang_luc, b.so_lieu, b.loai FROM fp_bai b "
                  "LEFT JOIN fp_trang t ON t.id=b.trang_id WHERE b.trang_thai='da_dang' AND b.dang_luc>=?",
                  [now - ngay * 86400])
        if trang:
            qb += " AND b.trang_id=?"
            ab.append(trang)
        bai = [dict(r) for r in c.execute(
            qb + " ORDER BY CAST(COALESCE(json_extract(b.so_lieu,'$.tuong_tac'),0) AS INTEGER) DESC, b.dang_luc DESC "
            "LIMIT 100", ab).fetchall()]
        for b in bai:
            b["so_lieu"] = _j(b["so_lieu"], {})
            b["noi_dung"] = (b["noi_dung"] or "")[:300]
        qc, ac = ("SELECT ngay, COALESCE(SUM(nguoi_theo_doi),0) nguoi_theo_doi, COALESCE(SUM(tiep_can),0) tiep_can, "
                  "COALESCE(SUM(tuong_tac),0) tuong_tac FROM fp_so_lieu WHERE ngay>=?", [tu])
        if trang:
            qc += " AND trang_id=?"
            ac.append(trang)
        chuoi = [dict(r) for r in c.execute(qc + " GROUP BY ngay ORDER BY ngay", ac).fetchall()]
    return {"trang": trs, "bai": bai, "chuoi": chuoi}
