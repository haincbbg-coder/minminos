"""Kho sự kiện của MinMin Mắt Nhà (camera EZVIZ ở nhà, qua Frigate + cầu nối minmin-cau).

Máy tính ở nhà chạy Frigate, nhận diện người/xe/biển số/giọng nói NGAY TẠI NHÀ, rồi cầu nối
chỉ gửi lên đây một dòng tóm tắt (ai, lúc nào, camera nào) kèm ảnh chụp nhỏ. Video, bộ mặt
đã học và mã camera KHÔNG bao giờ rời máy ở nhà (Luật Bảo vệ dữ liệu cá nhân 91/2025: mẫu
khuôn mặt là dữ liệu nhạy cảm, giữ ở nhà là mặc định an toàn nhất).

Module này chỉ lo lưu và đọc, không biết gì về HTTP:

- Sự kiện: `<STATE>/mat-nha/su-kien/YYYY-MM-DD.jsonl`, một file mỗi ngày (theo giờ địa phương
  của lúc bắt đầu). Chia theo ngày để xoá hạn lưu trữ chỉ là xoá file, không phải viết lại.
- Ảnh: `<STATE>/mat-nha/anh/<id>.jpg`, có trần dung lượng tổng.
- Trạng thái: `<STATE>/mat-nha/trang-thai.json` (nhịp cuối của cầu nối, sự kiện cuối mỗi camera).

Mã ghép nối KHÔNG lưu nguyên văn: settings chỉ giữ bản băm sha256, nên GET /settings (trả gần
như nguyên cấu hình ra trình duyệt) không có gì để lộ. Mã chỉ hiện đúng một lần lúc tạo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

NGAY_GIU = 30                      # giữ sự kiện và ảnh 30 ngày
ANH_TOI_DA_BYTE = 300 * 1024       # một ảnh chụp tối đa 300KB (cầu nối gửi ~640px, thường 30-80KB)
ANH_TONG_TOI_DA = 500 * 1024 * 1024  # cả thư mục ảnh tối đa 500MB, quá thì xoá ảnh cũ nhất
DONG_TOI_DA = 4096                 # một dòng sự kiện tối đa 4KB sau khi cắt chữ
CHU_TOI_DA = 1000                  # lời nói chép lại tối đa 1000 ký tự
GIOI_HAN_TRA = 500                 # một lần đọc trả tối đa 500 sự kiện
LOAI_HOP_LE = ("nguoi", "xe", "con_vat", "vat", "giong", "khac")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_CAM_RE = re.compile(r"[^a-z0-9_-]+")
_KHOA = threading.Lock()
_DON_LUC = {"t": 0.0}              # lần dọn hạn lưu trữ gần nhất (dọn tối đa 1 lần/giờ)


def _state_dir() -> Path:
    try:
        import config as cfgmod
        return Path(cfgmod.STATE_DIR)
    except Exception:
        return Path(os.getenv("JAVIS_STATE_DIR", str(Path(__file__).parent)))


def thu_muc() -> Path:
    return _state_dir() / "mat-nha"


def _tz():
    # Múi giờ theo Cài đặt (localefmt), không ghim cứng - xem test_locale.py.
    import localefmt
    return localefmt.tz()


# ---------------------------------------------------------------- mã ghép nối

def _bam(ma: str) -> str:
    return hashlib.sha256(("mat-nha:" + str(ma)).encode("utf-8")).hexdigest()


def tao_ma() -> str:
    """Tạo (hoặc thay) mã ghép nối. Trả mã NGUYÊN VĂN đúng một lần; settings chỉ giữ bản băm."""
    import config as cfgmod
    ma = "mn_" + secrets.token_urlsafe(24)
    cfg = cfgmod.read_settings()
    mn = cfg.get("mat_nha") if isinstance(cfg.get("mat_nha"), dict) else {}
    mn["token_hash"] = _bam(ma)
    mn["token_tao_luc"] = int(time.time())
    mn["token_cuoi"] = ma[-4:]
    cfg["mat_nha"] = mn
    cfgmod.write_settings(cfg)
    return ma


def thong_tin_ma() -> dict:
    try:
        import config as cfgmod
        mn = cfgmod.read_settings().get("mat_nha") or {}
    except Exception:
        mn = {}
    return {"da_co": bool(mn.get("token_hash")), "tao_luc": mn.get("token_tao_luc"),
            "cuoi": mn.get("token_cuoi") or ""}


def ma_dung(ma: str) -> bool:
    """So mã bằng phép so thời gian hằng (hmac.compare_digest trên bản băm)."""
    if not ma or len(ma) > 200:
        return False
    try:
        import config as cfgmod
        luu = str((cfgmod.read_settings().get("mat_nha") or {}).get("token_hash") or "")
    except Exception:
        luu = ""
    if not luu:
        return False
    return hmac.compare_digest(_bam(ma), luu)


# ---------------------------------------------------------------- chuẩn hoá sự kiện

def _so(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and 0 < v < 1e11 else None


def _chu(x, toi_da: int = 80) -> Optional[str]:
    if x is None:
        return None
    s = " ".join(str(x).split())
    return s[:toi_da] if s else None


def ten_camera(x) -> str:
    s = _CAM_RE.sub("-", str(x or "").strip().lower()).strip("-")
    return s[:40] or "khong-ro"


def bien_so_chuan(x) -> str:
    """'29-B1 123.45' -> '29B112345': bỏ mọi ký tự không phải chữ/số để so khớp dễ."""
    return re.sub(r"[^A-Z0-9]", "", str(x or "").upper())


def chuan_hoa(raw: dict) -> dict:
    """Nhận JSON từ cầu nối, trả dict sạch để lưu. Ném ValueError nếu thiếu thứ bắt buộc."""
    if not isinstance(raw, dict):
        raise ValueError("thân yêu cầu phải là object JSON")
    eid = str(raw.get("id") or "").strip()
    if not _ID_RE.match(eid):
        raise ValueError("id không hợp lệ (chỉ chữ, số, . _ -, tối đa 80 ký tự)")
    loai = str(raw.get("loai") or "khac").strip().lower()
    if loai not in LOAI_HOP_LE:
        loai = "khac"
    bat_dau = _so(raw.get("bat_dau")) or time.time()
    ket_thuc = _so(raw.get("ket_thuc"))
    diem = _so(raw.get("diem"))
    ev = {
        "id": eid,
        "camera": ten_camera(raw.get("camera")),
        "loai": loai,
        "nhan": _chu(raw.get("nhan"), 40),
        "ten": _chu(raw.get("ten"), 60),
        "bien_so": _chu(raw.get("bien_so"), 20),
        "la_nguoi_la": bool(raw.get("la_nguoi_la")) and loai == "nguoi",
        "bat_dau": round(bat_dau, 3),
        "ket_thuc": round(ket_thuc, 3) if ket_thuc else None,
        "diem": round(diem, 3) if diem is not None and diem <= 1.0 else None,
        "chu": _chu(raw.get("chu"), CHU_TOI_DA),
        "nhan_luc": round(time.time(), 3),
    }
    if ev["ten"]:
        ev["la_nguoi_la"] = False
    return ev


def _ngay_cua(ts: float) -> str:
    return datetime.fromtimestamp(ts, _tz()).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- ghi

def _anh_path(eid: str) -> Path:
    return thu_muc() / "anh" / f"{eid}.jpg"


def _giai_anh(b64) -> Optional[bytes]:
    if not b64 or not isinstance(b64, str):
        return None
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[-1]
    if len(b64) > ANH_TOI_DA_BYTE * 4 // 3 + 16:
        raise ValueError("ảnh quá lớn (tối đa 300KB)")
    try:
        data = base64.b64decode(b64, validate=True)
    except Exception:
        raise ValueError("ảnh không phải base64 hợp lệ")
    if len(data) > ANH_TOI_DA_BYTE:
        raise ValueError("ảnh quá lớn (tối đa 300KB)")
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("ảnh phải là JPEG")
    return data


def _da_co(eid: str, ngay: str) -> bool:
    f = thu_muc() / "su-kien" / f"{ngay}.jsonl"
    if not f.is_file():
        return False
    kim = f'"id": "{eid}"'
    try:
        with f.open("r", encoding="utf-8") as fh:
            return any(kim in dong for dong in fh)
    except Exception:
        return False


def luu_su_kien(raw: dict) -> dict:
    """Lưu một sự kiện (và ảnh nếu có). Trùng id thì bỏ qua, trả {"trung": True}."""
    ev = chuan_hoa(raw)
    anh = _giai_anh(raw.get("anh_b64") or raw.get("anh"))
    ngay = _ngay_cua(ev["bat_dau"])
    goc = thu_muc()
    with _KHOA:
        (goc / "su-kien").mkdir(parents=True, exist_ok=True)
        if _da_co(ev["id"], ngay):
            return {"ok": True, "trung": True, "id": ev["id"]}
        if anh:
            (goc / "anh").mkdir(parents=True, exist_ok=True)
            _anh_path(ev["id"]).write_bytes(anh)
            ev["co_anh"] = True
        dong = json.dumps(ev, ensure_ascii=False)
        if len(dong.encode("utf-8")) > DONG_TOI_DA:
            ev["chu"] = (ev.get("chu") or "")[:200]
            dong = json.dumps(ev, ensure_ascii=False)
        with (goc / "su-kien" / f"{ngay}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(dong + "\n")
        _cap_nhat_trang_thai(ev=ev)
    don_dep()
    return {"ok": True, "id": ev["id"]}


def ghi_nhip(raw: dict) -> dict:
    """Cầu nối báo 'còn sống' (mỗi vài phút). Không lưu thành sự kiện."""
    cams = raw.get("cameras") if isinstance(raw, dict) else None
    ds = [ten_camera(c) for c in cams][:32] if isinstance(cams, list) else []
    with _KHOA:
        _cap_nhat_trang_thai(nhip={"luc": round(time.time(), 3), "cameras": ds,
                                   "phien_ban": _chu((raw or {}).get("phien_ban"), 20),
                                   "hang_doi": int(_so((raw or {}).get("hang_doi")) or 0)})
    return {"ok": True}


def _doc_trang_thai() -> dict:
    f = thu_muc() / "trang-thai.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _cap_nhat_trang_thai(ev: Optional[dict] = None, nhip: Optional[dict] = None) -> None:
    d = _doc_trang_thai()
    if nhip:
        d["nhip"] = nhip
    if ev:
        cams = d.setdefault("cameras", {})
        c = cams.setdefault(ev["camera"], {})
        c["su_kien_cuoi"] = max(float(c.get("su_kien_cuoi") or 0), ev["bat_dau"])
        c["nhan_cuoi"] = ev.get("ten") or ev.get("bien_so") or ev.get("nhan") or ev["loai"]
        if len(cams) > 64:
            for k in sorted(cams, key=lambda k: cams[k].get("su_kien_cuoi") or 0)[:len(cams) - 64]:
                cams.pop(k, None)
    f = thu_muc() / "trang-thai.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


def trang_thai(song_trong_giay: int = 600) -> dict:
    d = _doc_trang_thai()
    nhip = d.get("nhip") or {}
    luc = _so(nhip.get("luc"))
    cams = d.get("cameras") or {}
    for c in (nhip.get("cameras") or []):
        cams.setdefault(c, {})
    return {
        "cau_noi_song": bool(luc and time.time() - luc < song_trong_giay),
        "nhip_cuoi": luc,
        "hang_doi": nhip.get("hang_doi") or 0,
        "phien_ban_cau": nhip.get("phien_ban"),
        "cameras": [{"camera": k, "su_kien_cuoi": v.get("su_kien_cuoi"), "nhan_cuoi": v.get("nhan_cuoi")}
                    for k, v in sorted(cams.items())],
        "ma": thong_tin_ma(),
    }


# ---------------------------------------------------------------- dọn hạn lưu trữ

def don_dep(ep: bool = False, bay_gio: Optional[float] = None) -> dict:
    """Xoá file sự kiện quá NGAY_GIU ngày, ảnh quá hạn, và ảnh cũ nhất khi vượt trần dung lượng.
    Chạy tối đa một lần mỗi giờ (trừ khi ep=True) vì được gọi ngay sau mỗi lần ghi."""
    now = bay_gio or time.time()
    if not ep and now - _DON_LUC["t"] < 3600:
        return {"bo_qua": True}
    _DON_LUC["t"] = now
    goc = thu_muc()
    han = datetime.fromtimestamp(now - NGAY_GIU * 86400, _tz()).strftime("%Y-%m-%d")
    xoa_file = xoa_anh = 0
    with _KHOA:
        for f in (goc / "su-kien").glob("*.jsonl") if (goc / "su-kien").is_dir() else []:
            if f.stem < han:
                try:
                    f.unlink()
                    xoa_file += 1
                except OSError:
                    pass
        thu_anh = goc / "anh"
        if thu_anh.is_dir():
            ds = []
            for f in thu_anh.glob("*.jpg"):
                try:
                    st = f.stat()
                except OSError:
                    continue
                if st.st_mtime < now - NGAY_GIU * 86400:
                    try:
                        f.unlink()
                        xoa_anh += 1
                    except OSError:
                        pass
                else:
                    ds.append((st.st_mtime, st.st_size, f))
            tong = sum(s for _, s, _ in ds)
            for _, s, f in sorted(ds, key=lambda x: x[0]):
                if tong <= ANH_TONG_TOI_DA:
                    break
                try:
                    f.unlink()
                    tong -= s
                    xoa_anh += 1
                except OSError:
                    pass
    return {"xoa_file": xoa_file, "xoa_anh": xoa_anh}


# ---------------------------------------------------------------- đọc

def _moc(x, cuoi_ngay: bool = False) -> Optional[float]:
    """'2026-09-30' | '2026-09-30T08:00' | epoch -> epoch. Ngày trần: đầu ngày (hoặc cuối ngày)."""
    if x is None or x == "":
        return None
    v = _so(x)
    if v is not None:
        return v
    s = str(x).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            d = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=_tz())
            return (d + timedelta(days=1)).timestamp() - 0.001 if cuoi_ngay else d.timestamp()
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=_tz())
        return d.timestamp()
    except ValueError:
        raise ValueError(f"mốc thời gian không hiểu được: {s!r} (dùng YYYY-MM-DD hoặc ISO)")


def dau_hom_nay() -> float:
    n = datetime.now(_tz())
    return n.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def tim(tu=None, den=None, camera=None, loai=None, ten=None, bien_so=None,
        chi_nguoi_la: bool = False, limit: int = 100) -> list:
    """Sự kiện khớp bộ lọc, MỚI NHẤT TRƯỚC. `ten`, `bien_so` so khớp một phần, không phân biệt hoa."""
    t0 = _moc(tu)
    t1 = _moc(den, cuoi_ngay=True)
    if t0 is None:
        t0 = time.time() - NGAY_GIU * 86400
    if t1 is None:
        t1 = time.time() + 86400
    try:
        limit = max(1, min(int(limit or 100), GIOI_HAN_TRA))
    except (TypeError, ValueError):
        limit = 100
    cam = ten_camera(camera) if camera else None
    loai = str(loai).strip().lower() if loai else None
    ten_l = str(ten).strip().lower() if ten else None
    bs = bien_so_chuan(bien_so) if bien_so else None
    d0 = datetime.fromtimestamp(t0, _tz()).date()
    d1 = datetime.fromtimestamp(t1, _tz()).date()
    goc = thu_muc() / "su-kien"
    ra = []
    ngay = d1
    while ngay >= d0 and len(ra) < limit:
        f = goc / f"{ngay.isoformat()}.jsonl"
        ngay -= timedelta(days=1)
        if not f.is_file():
            continue
        try:
            dong = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        trong_ngay = []
        for d in dong:
            try:
                ev = json.loads(d)
            except Exception:
                continue
            ts = ev.get("bat_dau") or 0
            if ts < t0 or ts > t1:
                continue
            if cam and ev.get("camera") != cam:
                continue
            if loai and ev.get("loai") != loai:
                continue
            if ten_l and ten_l not in str(ev.get("ten") or "").lower():
                continue
            if bs and bs not in bien_so_chuan(ev.get("bien_so")):
                continue
            if chi_nguoi_la and not ev.get("la_nguoi_la"):
                continue
            trong_ngay.append(ev)
        trong_ngay.sort(key=lambda e: e.get("bat_dau") or 0, reverse=True)
        ra.extend(trong_ngay[: limit - len(ra)])
    return ra


def doc_anh(eid: str) -> Optional[Path]:
    if not _ID_RE.match(str(eid or "")):
        return None
    p = _anh_path(eid)
    return p if p.is_file() else None


# ---------------------------------------------------------------- tóm tắt tiếng Việt (cho plugin)

_TEN_LOAI = {"nguoi": "người", "xe": "xe", "con_vat": "con vật", "vat": "đồ vật",
             "giong": "âm thanh/giọng nói", "khac": "khác"}


def gio(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), _tz()).strftime("%H:%M %d/%m")
    except Exception:
        return "?"


def mo_ta(ev: dict) -> str:
    ai = ev.get("ten") or ("người lạ" if ev.get("la_nguoi_la") else None)
    phan = [gio(ev.get("bat_dau")), ev.get("camera") or "?"]
    if ev.get("loai") == "nguoi":
        phan.append(ai or "người")
    elif ev.get("loai") == "xe":
        phan.append((ev.get("nhan") or "xe") + (f" biển {ev['bien_so']}" if ev.get("bien_so") else ""))
    elif ev.get("loai") == "giong":
        phan.append(("giọng nói: \"" + ev["chu"][:160] + "\"") if ev.get("chu") else (ev.get("nhan") or "âm thanh"))
    else:
        phan.append(ev.get("nhan") or _TEN_LOAI.get(ev.get("loai"), "?"))
    return " - ".join(phan)


def tom_tat(ds: list, toi_da_dong: int = 30) -> str:
    if not ds:
        return "Không có sự kiện nào khớp."
    nguoi = [e for e in ds if e.get("loai") == "nguoi"]
    quen = sorted({e["ten"] for e in nguoi if e.get("ten")})
    la = sum(1 for e in nguoi if e.get("la_nguoi_la"))
    xe = [e for e in ds if e.get("loai") == "xe"]
    bien = sorted({e["bien_so"] for e in xe if e.get("bien_so")})
    dau = [f"{len(ds)} sự kiện" + (" (đã cắt bớt)" if len(ds) >= GIOI_HAN_TRA else "") + "."]
    if nguoi:
        dau.append(f"Người: {len(nguoi)} lần" + (f", nhận ra: {', '.join(quen)}" if quen else "")
                   + (f", người lạ (không nhận ra mặt): {la} lần" if la else "") + ".")
    if xe:
        dau.append(f"Xe: {len(xe)} lần" + (f", biển số đọc được: {', '.join(bien[:10])}" if bien else "") + ".")
    dong = [mo_ta(e) for e in ds[:toi_da_dong]]
    them = f"\n(... còn {len(ds) - toi_da_dong} sự kiện nữa)" if len(ds) > toi_da_dong else ""
    return " ".join(dau) + "\nMới nhất trước:\n- " + "\n- ".join(dong) + them
