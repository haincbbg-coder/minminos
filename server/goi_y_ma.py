"""goi_y_ma.py - kho và bộ tra mã hàng cho tiện ích gợi ý của nhân viên bán hàng (26.10.220).

Khách nhắn tới Pancake thì tiện ích hỏi MinMin "đây là mã nào". Tra theo thứ tự rẻ và chắc nhất:
    1. mã nằm ngay trong tin nhắn ("giá mã V33")          -> tra bảng mã, chắc nhất
    2. ID quảng cáo của tin nhắn đi ra từ quảng cáo        -> ad_id -> mã
    3. ID bài viết / comment khách bấm vào                 -> post_id -> mã
    4. (bước ảnh nằm ở module khác, chỉ cắm vào đây)
Mỗi ứng viên có `bang_chung` (vì sao) và `do_chac`; nhân viên là người chốt. Tồn kho lấy từ bảng sku.

Quy ước tên chiến dịch: "CÔNG TY TNHH MTV HALIMI - TÊN PAGE - P720" -> mã nằm sau dấu " - " cuối cùng.

Ghép máy giống Concat: dashboard tạo mã 6 số, tiện ích đổi lấy token (lưu dạng băm), mọi gọi sau mang
header x-minmin-may. Thuần stdlib; `mo(thu_muc)` một lần lúc khởi động, test gọi với thư mục tạm.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

MA_SONG = 15 * 60
TIEN_TO_TOKEN = "mmg_"
NGUON_TRONG_SO = {"anh": 0.6, "tin_nhan": 1.0, "quang_cao": 0.95, "chien_dich": 0.9, "noi_dung": 0.85, "ma_ro": 0.95, "ma_qc": 0.97, "bai_viet": 0.8, "bi_danh": 0.7}

_goc: Optional[Path] = None
_khoa = threading.RLock()


def mo(thu_muc) -> None:
    global _goc
    _goc = Path(thu_muc)
    _goc.mkdir(parents=True, exist_ok=True)
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS ma_ghep(ma_bam TEXT PRIMARY KEY, het_han REAL);
        CREATE TABLE IF NOT EXISTS may(id TEXT PRIMARY KEY, ten TEXT, token_bam TEXT, tao_luc REAL,
            nhip_luc REAL, phien_ban TEXT);
        CREATE TABLE IF NOT EXISTS sku(ma TEXT PRIMARY KEY, ten TEXT DEFAULT '', ton REAL DEFAULT 0,
            anh TEXT DEFAULT '[]', sua_luc REAL);
        CREATE TABLE IF NOT EXISTS ad_sku(ad_id TEXT PRIMARY KEY, ma TEXT, nguon TEXT DEFAULT 'quang_cao',
            ten TEXT DEFAULT '', tai_khoan TEXT DEFAULT '', sua_luc REAL);
        CREATE TABLE IF NOT EXISTS post_sku(post_id TEXT PRIMARY KEY, ma TEXT, page_id TEXT DEFAULT '',
            nguon TEXT DEFAULT 'bai_viet', sua_luc REAL);
        CREATE TABLE IF NOT EXISTS bi_danh(chuoi TEXT PRIMARY KEY, ma TEXT);
        CREATE TABLE IF NOT EXISTS xac_nhan(id INTEGER PRIMARY KEY AUTOINCREMENT, ma TEXT, nguon TEXT,
            khoa TEXT, luc REAL);
        """)


def thu_muc() -> Path:
    if _goc is None:
        raise RuntimeError("goi_y_ma chưa mo()")
    return _goc


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(str(thu_muc() / "goi_y_ma.db"), timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    return c


def _bam(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


def _now() -> float:
    return time.time()


def chuan_ma(s) -> str:
    """V 33 / v-33 / V33 -> V33. Bỏ dấu, chỉ giữ chữ số và chữ cái."""
    t = unicodedata.normalize("NFD", str(s or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^A-Za-z0-9]", "", t).upper()


# ------------------------------------------------------------------ ghép máy

def tao_ma_ghep() -> str:
    ma = f"{secrets.randbelow(1_000_000):06d}"
    with _khoa, _db() as c:
        c.execute("DELETE FROM ma_ghep WHERE het_han < ?", (_now(),))
        c.execute("INSERT OR REPLACE INTO ma_ghep(ma_bam, het_han) VALUES(?, ?)", (_bam(ma), _now() + MA_SONG))
    return ma


def ghep(ma: str, ten: str = "", phien_ban: str = "") -> dict:
    ma = "".join(ch for ch in str(ma or "") if ch.isdigit())
    if len(ma) != 6:
        raise ValueError("mã ghép phải đủ 6 số")
    with _khoa, _db() as c:
        r = c.execute("SELECT het_han FROM ma_ghep WHERE ma_bam=?", (_bam(ma),)).fetchone()
        if not r or r["het_han"] < _now():
            raise ValueError("mã ghép sai hoặc đã hết hạn - tạo mã mới ở trang Gợi ý mã hàng")
        c.execute("DELETE FROM ma_ghep WHERE ma_bam=?", (_bam(ma),))
        may_id = "g" + secrets.token_hex(4)
        token = TIEN_TO_TOKEN + secrets.token_urlsafe(32)
        ten = (str(ten or "").strip() or "Máy nhân viên")[:60]
        c.execute("INSERT INTO may(id, ten, token_bam, tao_luc, nhip_luc, phien_ban) VALUES(?,?,?,?,?,?)",
                  (may_id, ten, _bam(token), _now(), _now(), str(phien_ban or "")[:20]))
    return {"may_id": may_id, "token": token, "ten": ten}


def may_theo_token(token: str) -> Optional[dict]:
    token = str(token or "")
    if not token.startswith(TIEN_TO_TOKEN):
        return None
    b = _bam(token)
    with _db() as c:
        rows = c.execute("SELECT id, ten, token_bam FROM may").fetchall()
        for r in rows:
            if hmac.compare_digest(r["token_bam"], b):
                c.execute("UPDATE may SET nhip_luc=? WHERE id=?", (_now(), r["id"]))
                return {"id": r["id"], "ten": r["ten"]}
    return None


def ds_may() -> list:
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT id, ten, tao_luc, nhip_luc, phien_ban FROM may ORDER BY tao_luc")]


def go_may(may_id: str) -> bool:
    with _khoa, _db() as c:
        return c.execute("DELETE FROM may WHERE id=?", (str(may_id),)).rowcount > 0


# ------------------------------------------------------------------ nạp dữ liệu

def nap_sku(ds: Iterable[dict]) -> int:
    """[{ma, ten, ton, anh:[url...]}] -> số mã ghi. Ghi đè theo mã."""
    n = 0
    with _khoa, _db() as c:
        for d in ds or []:
            if isinstance(d, str):                       # dạng gọn "P664:508"
                ma_, _, ton_ = d.partition(":")
                try:
                    d = {"ma": ma_, "ton": float(ton_ or 0)}
                except ValueError:
                    continue
                cu = c.execute("SELECT ten, anh FROM sku WHERE ma=?", (chuan_ma(ma_),)).fetchone()
                if cu:                                   # nạp tồn không được xoá tên và ảnh đã có
                    d["ten"], d["anh"] = cu["ten"], json.loads(cu["anh"] or "[]")
            ma = chuan_ma((d or {}).get("ma"))
            if not ma:
                continue
            anh = [str(u) for u in (d.get("anh") or []) if u][:8]
            c.execute("INSERT OR REPLACE INTO sku(ma, ten, ton, anh, sua_luc) VALUES(?,?,?,?,?)",
                      (ma, str(d.get("ten") or "")[:200], float(d.get("ton") or 0),
                       json.dumps(anh, ensure_ascii=False), _now()))
            n += 1
    return n


def nap_tu_dict(a: dict) -> dict:
    """Nạp một lần mọi loại dữ liệu từ dict {sku, quang_cao, bai_viet, bi_danh}. Dùng chung cho plugin."""
    kq = {}
    if a.get("sku"):
        kq["sku"] = nap_sku(a["sku"])
    if a.get("quang_cao"):
        kq["quang_cao"] = nap_quang_cao(a["quang_cao"])
    if a.get("bai_viet"):
        kq["bai_viet"] = nap_bai_viet(a["bai_viet"])
    if a.get("bi_danh"):
        kq["bi_danh"] = nap_bi_danh(a["bi_danh"])
    return kq


def ma_tu_ten_chien_dich(ten: str) -> str:
    """'CÔNG TY TNHH MTV HALIMI - TÊN PAGE - P720' -> 'P720'. Rỗng nếu không có mã ở cuối."""
    phan = [p.strip() for p in re.split(r"\s[-–]\s", str(ten or "")) if p.strip()]
    if len(phan) < 2:
        return ""
    ma = chuan_ma(phan[-1])
    return ma if re.fullmatch(r"[A-Z]{0,4}\d{1,6}[A-Z]{0,2}", ma) else ""


def nap_quang_cao(ds: Iterable[dict]) -> dict:
    """[{ad_id, ma?, ten_chien_dich?, tai_khoan?}]. Thiếu `ma` thì tách từ tên chiến dịch."""
    ok = bo = 0
    with _khoa, _db() as c:
        for d in ds or []:
            ad = str((d or {}).get("ad_id") or "").strip()
            ten = str(d.get("ten_chien_dich") or d.get("ten") or "")
            ma = chuan_ma(d.get("ma")) or ma_tu_ten_chien_dich(ten)
            if not ad or not ma:
                bo += 1
                continue
            nguon = "quang_cao" if d.get("ma") else "chien_dich"
            c.execute("INSERT OR REPLACE INTO ad_sku(ad_id, ma, nguon, ten, tai_khoan, sua_luc) VALUES(?,?,?,?,?,?)",
                      (ad, ma, nguon, ten[:200], str(d.get("tai_khoan") or "")[:60], _now()))
            ok += 1
    return {"ghi": ok, "bo_qua": bo}


def nap_bai_viet(ds: Iterable[dict]) -> dict:
    ok = bo = 0
    with _khoa, _db() as c:
        for d in ds or []:
            p = str((d or {}).get("post_id") or "").strip()
            ma = chuan_ma(d.get("ma"))
            if not p or not ma:
                bo += 1
                continue
            c.execute("INSERT OR REPLACE INTO post_sku(post_id, ma, page_id, nguon, sua_luc) VALUES(?,?,?,?,?)",
                      (p, ma, str(d.get("page_id") or ""), "bai_viet", _now()))
            ok += 1
    return {"ghi": ok, "bo_qua": bo}


def nap_bi_danh(ds: Iterable[dict]) -> int:
    n = 0
    with _khoa, _db() as c:
        for d in ds or []:
            ch, ma = chuan_ma((d or {}).get("chuoi")), chuan_ma(d.get("ma"))
            if ch and ma:
                c.execute("INSERT OR REPLACE INTO bi_danh(chuoi, ma) VALUES(?,?)", (ch, ma))
                n += 1
    return n


# ------------------------------------------------------------------ tra cứu

def _ton(c, ma):
    r = c.execute("SELECT ten, ton, anh FROM sku WHERE ma=?", (ma,)).fetchone()
    if not r:
        return {"co_trong_sku": False, "ten": "", "ton": None, "anh": []}
    return {"co_trong_sku": True, "ten": r["ten"], "ton": r["ton"], "anh": json.loads(r["anh"] or "[]")[:1]}


def tim_ma_trong_chu(c, text: str) -> list:
    """Mã nằm trong câu chữ: chỉ nhận chuỗi có trong bảng sku (hoặc bí danh) nên 'V33' khớp mà 'ok33' thì không."""
    ung = []
    thay = set()
    for tk in re.findall(r"[A-Za-zĐđ]{0,4}[\s\-]?\d{1,6}[A-Za-z]{0,2}", unicodedata.normalize("NFC", str(text or ""))):
        m = chuan_ma(tk)
        if m and m not in thay:
            thay.add(m)
    for m in thay:
        if c.execute("SELECT 1 FROM sku WHERE ma=?", (m,)).fetchone():
            ung.append((m, "tin_nhan", f"khách nhắn mã {m}"))
        else:
            b = c.execute("SELECT ma FROM bi_danh WHERE chuoi=?", (m,)).fetchone()
            if b:
                ung.append((b["ma"], "bi_danh", f"'{m}' là tên gọi khác của {b['ma']}"))
    return ung


def phan_giai(text: str = "", ad_id: str = "", post_id: str = "", gioi_han: int = 5, ad_text: str = "", ma_ro=None, ma_qc=None) -> dict:
    """Trả {ung_vien:[{ma, ten, ton, do_chac, bang_chung:[...]}], da_thu:[...]} xếp giảm dần theo độ chắc."""
    gom: dict = {}
    da_thu = []

    def them(ma, nguon, ly_do):
        d = gom.setdefault(ma, {"ma": ma, "bang_chung": [], "_diem": []})
        d["bang_chung"].append({"nguon": nguon, "ly_do": ly_do})
        d["_diem"].append(NGUON_TRONG_SO.get(nguon, 0.5))

    with _db() as c:
        if str(text or "").strip():
            da_thu.append("tin_nhan")
            for ma, ng, ly in tim_ma_trong_chu(c, text):
                them(ma, ng, ly)
        for i, m in enumerate(ma_ro or []):
            m = chuan_ma(m)
            if not m:
                continue
            b = c.execute("SELECT ma FROM bi_danh WHERE chuoi=?", (m,)).fetchone()
            ma = m if c.execute("SELECT 1 FROM sku WHERE ma=?", (m,)).fetchone() else (b["ma"] if b else m)
            them(ma, "ma_ro", f"tin nhắn ghi rõ mã {ma}")
            gom[ma]["_diem"][-1] -= 0.01 * i
        for i, m in enumerate(ma_qc or []):
            m = chuan_ma(m)
            if not m:
                continue
            b = c.execute("SELECT ma FROM bi_danh WHERE chuoi=?", (m,)).fetchone()
            ma = m if c.execute("SELECT 1 FROM sku WHERE ma=?", (m,)).fetchone() else (b["ma"] if b else m)
            them(ma, "ma_qc", f"tên/nội dung quảng cáo ghi mã {ma}")
            gom[ma]["_diem"][-1] -= 0.01 * i
        if str(ad_text or "").strip():
            da_thu.append("noi_dung")
            for ma, _ng, _ly in tim_ma_trong_chu(c, ad_text):
                them(ma, "noi_dung", f"nội dung quảng cáo nhắc mã {ma}")
        if str(ad_id or "").strip():
            da_thu.append("quang_cao")
            r = c.execute("SELECT ma, nguon, ten, tai_khoan FROM ad_sku WHERE ad_id=?", (str(ad_id).strip(),)).fetchone()
            if r:
                them(r["ma"], r["nguon"], f"quảng cáo {ad_id}" + (f" ({r['ten']})" if r["ten"] else ""))
        if str(post_id or "").strip():
            da_thu.append("bai_viet")
            r = c.execute("SELECT ma FROM post_sku WHERE post_id=?", (str(post_id).strip(),)).fetchone()
            if r:
                them(r["ma"], "bai_viet", f"bài viết {post_id}")
        kq = []
        for ma, d in gom.items():
            diem = sorted(d.pop("_diem"), reverse=True)
            chac = diem[0] + 0.05 * sum(diem[1:2])     # hai nguồn cùng chỉ một mã thì chắc hơn một chút
            d["do_chac"] = round(min(chac, 0.99), 2)
            d.update(_ton(c, ma))
            kq.append(d)
    kq.sort(key=lambda x: (-x["do_chac"], x["ma"]))
    return {"ung_vien": kq[:max(1, int(gioi_han))], "da_thu": da_thu}


def xac_nhan(ma: str, nguon: str = "", khoa: str = "") -> None:
    """Nhân viên chốt mã nào cho ngữ cảnh nào. Giữ làm dữ liệu học (ảnh khách, ad/post lạ)."""
    with _khoa, _db() as c:
        c.execute("INSERT INTO xac_nhan(ma, nguon, khoa, luc) VALUES(?,?,?,?)",
                  (chuan_ma(ma), str(nguon)[:20], str(khoa)[:200], _now()))
        khoa = str(khoa or "")
        if nguon == "quang_cao" and khoa:
            c.execute("INSERT OR IGNORE INTO ad_sku(ad_id, ma, nguon, sua_luc) VALUES(?,?,?,?)",
                      (khoa, chuan_ma(ma), "quang_cao", _now()))
        elif nguon == "bai_viet" and khoa:
            c.execute("INSERT OR IGNORE INTO post_sku(post_id, ma, nguon, sua_luc) VALUES(?,?,?,?)",
                      (khoa, chuan_ma(ma), "bai_viet", _now()))


def xuat_bang() -> dict:
    """Ba bảng gọn để tiện ích nạp sẵn và tra trong vài mili giây ngay trên máy nhân viên."""
    with _db() as c:
        return {
            "sku": {r["ma"]: [r["ten"], r["ton"]] for r in c.execute("SELECT ma, ten, ton FROM sku")},
            "ad": {r["ad_id"]: r["ma"] for r in c.execute("SELECT ad_id, ma FROM ad_sku")},
            "post": {r["post_id"]: r["ma"] for r in c.execute("SELECT post_id, ma FROM post_sku")},
            "bi_danh": {r["chuoi"]: r["ma"] for r in c.execute("SELECT chuoi, ma FROM bi_danh")},
            "luc": _now(),
        }


def thong_ke() -> dict:
    with _db() as c:
        g = lambda t: c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"]
        return {"sku": g("sku"), "quang_cao": g("ad_sku"), "bai_viet": g("post_sku"), "bi_danh": g("bi_danh"),
                "xac_nhan": g("xac_nhan"), "may": g("may")}
