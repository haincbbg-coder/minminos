"""Biến động số dư: nhận giao dịch ngân hàng từ Casso (Webhook V2), lưu lại và soạn câu báo.

Chủ shop nối tài khoản Techcombank (hay ngân hàng bất kỳ) vào Casso Flow. Mỗi giao dịch Casso
đẩy một POST tới `/bien-dong/casso/<token>` (xem routes/bien_dong.py). Module này chỉ lo lưu,
đọc và soạn câu, không biết gì về HTTP:

- Giao dịch: `<STATE>/bien_dong.json`, giữ 1000 giao dịch gần nhất cùng tập id đã thấy (để
  Casso gửi lại một giao dịch thì không báo lần hai: Casso thử lại tới 17 lần trong 24 giờ).
- Cài đặt: `<STATE>/bien_dong_cai_dat.json`, tách khỏi settings.json để GET /settings (trả gần
  như nguyên cấu hình ra trình duyệt) không bao giờ chạm tới khoá Casso. Khoá còn được mã hoá
  bằng secrets_store, và KHÔNG BAO GIỜ trả ra ngoài: chỉ có cờ `da_co_khoa`.

Chữ ký Casso V2: header `X-Casso-Signature: t=<ms>,v1=<hex>`,
v1 = HMAC-SHA512(khoá, f"{t}.{json thân đã sắp khoá, không khoảng trắng}"). Mẫu Python chính
thức dùng json.dumps mặc định (ensure_ascii=True) còn mẫu JS dùng JSON.stringify (giữ nguyên
chữ có dấu), nên với nội dung tiếng Việt hai bản khác nhau: nhận khi khớp MỘT trong hai.
"""
from __future__ import annotations

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

GIU_TOI_DA = 1000              # số giao dịch giữ lại
ID_DA_THAY_TOI_DA = 5000       # số id đã thấy giữ lại để chống báo trùng
TRA_TOI_DA = 500               # một lần đọc trả tối đa 500 giao dịch
NOI_NHAN_TOI_DA = 10
NHAN_TK_TOI_DA = 20
TUOI_CHU_KY_TOI_DA = 3 * 86400   # chữ ký cũ hơn 3 ngày thì từ chối (Casso chỉ thử lại trong 24 giờ)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
_ZALO_RE = re.compile(r"^zalo:[A-Za-z0-9_-]{1,64}$")
_TG_RE = re.compile(r"^-?\d{1,20}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]{128}$")
_KHOA = threading.RLock()


def _state_dir() -> Path:
    try:
        import config as cfgmod
        return Path(cfgmod.STATE_DIR)
    except Exception:
        return Path(os.getenv("JAVIS_STATE_DIR", str(Path(__file__).parent)))


def file_kho() -> Path:
    return _state_dir() / "bien_dong.json"


def file_cai_dat() -> Path:
    return _state_dir() / "bien_dong_cai_dat.json"


def _tz():
    # Múi giờ theo Cài đặt (localefmt), không ghim cứng.
    import localefmt
    return localefmt.tz()


def _doc_json(p: Path, mac_dinh: dict) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else dict(mac_dinh)
    except Exception:
        return dict(mac_dinh)


def _ghi_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    tmp.replace(p)


# ---------------------------------------------------------------- cài đặt

MAC_DINH = {"token": "", "khoa": "", "chi_tien_vao": True, "nguong_toi_thieu": 0,
            "noi_nhan_them": [], "nhan_tk": {}}


def _cai_dat() -> dict:
    d = dict(MAC_DINH)
    d.update(_doc_json(file_cai_dat(), {}))
    return d


def tao_token() -> str:
    """Tạo (hoặc thay) mã trong đường webhook. Đường cũ hết hiệu lực ngay."""
    with _KHOA:
        d = _cai_dat()
        d["token"] = secrets.token_urlsafe(24)
        _ghi_json(file_cai_dat(), d)
        return d["token"]


def lay_token() -> str:
    """Mã hiện tại; chưa có thì tạo."""
    with _KHOA:
        tok = str(_cai_dat().get("token") or "")
        return tok if _TOKEN_RE.match(tok) else tao_token()


def token_dung(tok: str) -> bool:
    """So mã trong đường bằng phép so thời gian hằng. Chưa có mã thì không gì đúng."""
    tok = str(tok or "")
    luu = str(_cai_dat().get("token") or "")
    if not luu or not _TOKEN_RE.match(tok):
        return False
    return hmac.compare_digest(tok.encode("utf-8"), luu.encode("utf-8"))


def lay_khoa() -> str:
    import secrets_store
    return secrets_store.decrypt(str(_cai_dat().get("khoa") or "")) or ""


def duong_dan() -> str:
    return "/bien-dong/casso/" + lay_token()


def cai_dat_cong_khai() -> dict:
    """Thứ trang cài đặt được thấy. Không bao giờ có khoá Casso."""
    d = _cai_dat()
    return {"duong_dan": duong_dan(), "da_co_khoa": bool(d.get("khoa")),
            "chi_tien_vao": bool(d.get("chi_tien_vao", True)),
            "nguong_toi_thieu": int(d.get("nguong_toi_thieu") or 0),
            "noi_nhan_them": list(d.get("noi_nhan_them") or []),
            "nhan_tk": dict(d.get("nhan_tk") or {})}


def noi_nhan_them() -> list:
    return [str(x) for x in (_cai_dat().get("noi_nhan_them") or [])]


def chuan_noi_nhan(raw, ds_telegram, ds_zalo=None) -> list:
    """Kiểm danh sách nơi nhận thêm. Mỗi mục là chat id Telegram ĐÃ CÓ trong danh sách cho phép
    của bot, hoặc `zalo:<id>`. Sai một mục là từ chối cả lô (ValueError), không lặng lẽ bỏ.

    Bot Zalo có danh sách cho phép thì id Zalo cũng phải nằm trong đó: `_zalo_send_to` gặp id
    lạ sẽ gửi sang các id trong danh sách, tức tin tiền vào rơi nhầm người."""
    if raw is None:
        return []
    items = raw if isinstance(raw, (list, tuple)) else re.split(r"[,;\n]+", str(raw))
    cho_phep = {str(x).strip() for x in (ds_telegram or [])}
    zalo_ok = {str(x).strip() for x in (ds_zalo or [])}
    out = []
    for x in items:
        s = str(x).strip()
        if not s:
            continue
        if _ZALO_RE.match(s):
            if zalo_ok and s[len("zalo:"):] not in zalo_ok:
                raise ValueError(f"id Zalo {s[5:]} chưa có trong danh sách cho phép của bot Zalo "
                                 "(Kênh nhắn > Zalo > Chat ID). Thêm vào đó trước.")
        elif _TG_RE.match(s):
            if s not in cho_phep:
                raise ValueError(f"chat id Telegram {s} chưa có trong danh sách cho phép của bot "
                                 "(Kênh nhắn > Telegram > Chat ID). Thêm vào đó trước.")
        else:
            raise ValueError(f"nơi nhận không hợp lệ: {s[:40]!r} (dùng chat id Telegram hoặc zalo:<id>)")
        if s not in out:
            out.append(s)
    if len(out) > NOI_NHAN_TOI_DA:
        raise ValueError(f"tối đa {NOI_NHAN_TOI_DA} nơi nhận thêm")
    return out


def luu_cai_dat(patch: dict, ds_telegram=None, ds_zalo=None) -> dict:
    """Ghi các khoá có trong patch: khoa (chuỗi, rỗng = giữ nguyên), xoa_khoa, chi_tien_vao,
    nguong_toi_thieu, noi_nhan_them, nhan_tk. Lỗi kiểm tra -> ValueError, không ghi gì."""
    if not isinstance(patch, dict):
        raise ValueError("dữ liệu cài đặt phải là object")
    import secrets_store
    with _KHOA:
        d = _cai_dat()
        khoa = patch.get("khoa")
        if isinstance(khoa, str) and khoa.strip():
            k = khoa.strip()
            if len(k) > 512:
                raise ValueError("khoá bảo mật quá dài")
            d["khoa"] = secrets_store.encrypt(k)
        if patch.get("xoa_khoa"):
            d["khoa"] = ""
        if "chi_tien_vao" in patch:
            d["chi_tien_vao"] = bool(patch["chi_tien_vao"])
        if "nguong_toi_thieu" in patch:
            try:
                n = int(float(patch["nguong_toi_thieu"] or 0))
            except (TypeError, ValueError):
                raise ValueError("ngưỡng tối thiểu phải là số")
            if n < 0 or n > 10 ** 13:
                raise ValueError("ngưỡng tối thiểu không hợp lệ")
            d["nguong_toi_thieu"] = n
        if "noi_nhan_them" in patch:
            d["noi_nhan_them"] = chuan_noi_nhan(patch["noi_nhan_them"], ds_telegram, ds_zalo)
        if "nhan_tk" in patch:
            raw = patch["nhan_tk"] or {}
            if not isinstance(raw, dict):
                raise ValueError("nhãn tài khoản phải là object {số tài khoản: tên}")
            nhan = {}
            for k, v in raw.items():
                so = re.sub(r"\D", "", str(k))
                ten = " ".join(str(v or "").split())[:40]
                if so and ten:
                    nhan[so[:30]] = ten
            if len(nhan) > NHAN_TK_TOI_DA:
                raise ValueError(f"tối đa {NHAN_TK_TOI_DA} nhãn tài khoản")
            d["nhan_tk"] = nhan
        if not _TOKEN_RE.match(str(d.get("token") or "")):
            d["token"] = secrets.token_urlsafe(24)
        _ghi_json(file_cai_dat(), d)
    return cai_dat_cong_khai()


# ---------------------------------------------------------------- chữ ký

def _tach_header(header: str) -> tuple:
    t = v1 = ""
    for phan in str(header or "").split(","):
        k, _, v = phan.strip().partition("=")
        if k == "t":
            t = v.strip()
        elif k == "v1":
            v1 = v.strip()
    return t, v1


def xac_thuc_chu_ky(header: str, body: dict, key: str) -> bool:
    """Đúng chữ ký Casso V2 không. Thử cả bản ensure_ascii=True (mẫu Python) lẫn False (mẫu JS)."""
    if not key or not isinstance(body, dict) or len(str(header or "")) > 400:
        return False
    t, v1 = _tach_header(header)
    if not t.isdigit() or not _HEX_RE.match(v1):
        return False
    v1 = v1.lower().encode("ascii")
    k = key.encode("utf-8")
    dung = False
    for ascii_ in (True, False):
        than = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii_)
        sig = hmac.new(k, f"{t}.{than}".encode("utf-8"), hashlib.sha512).hexdigest().encode("ascii")
        # Không thoát sớm: luôn so cả hai bản cho thời gian đều nhau.
        dung = hmac.compare_digest(sig, v1) or dung
    return dung


def chu_ky_con_han(header: str, bay_gio: Optional[float] = None) -> bool:
    """Mốc t trong chữ ký không quá cũ (chống phát lại giao dịch cũ đã rơi khỏi tập id)."""
    t, _ = _tach_header(header)
    if not t.isdigit():
        return False
    bay_gio = time.time() if bay_gio is None else bay_gio
    tuoi = bay_gio - int(t) / 1000.0
    return -86400 < tuoi < TUOI_CHU_KY_TOI_DA


# ---------------------------------------------------------------- lưu giao dịch

def _kho() -> dict:
    d = _doc_json(file_kho(), {})
    if not isinstance(d.get("giao_dich"), list):
        d["giao_dich"] = []
    if not isinstance(d.get("da_thay"), list):
        d["da_thay"] = []
    d.setdefault("version", 1)
    return d


def _so_nguyen(x) -> Optional[int]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or abs(v) > 1e15:
        return None
    return int(round(v))


def _chu(x, toi_da: int = 200) -> str:
    return " ".join(str(x or "").split())[:toi_da]


def cuoi4(so) -> str:
    s = re.sub(r"\s", "", str(so or ""))
    return s[-4:] if s else ""


def _moc_gd(s) -> Optional[float]:
    """'2024-10-03 15:06:37' (giờ ngân hàng = giờ địa phương theo Cài đặt) -> epoch."""
    s = str(s or "").strip()
    if not s:
        return None
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], f).replace(tzinfo=_tz()).timestamp()
        except ValueError:
            continue
    try:
        d = datetime.fromisoformat(s)
        return (d if d.tzinfo else d.replace(tzinfo=_tz())).timestamp()
    except ValueError:
        return None


def chuan_hoa(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("thiếu data")
    so_tien = _so_nguyen(data.get("amount"))
    if so_tien is None:
        raise ValueError("amount không hợp lệ")
    raw_id = data.get("id")
    gid = _chu(raw_id, 64)
    thu = raw_id in (0, "0", None, "")
    bay_gio = time.time()
    tk = re.sub(r"\s", "", str(data.get("accountNumber") or ""))
    nhan = (_cai_dat().get("nhan_tk") or {}).get(re.sub(r"\D", "", tk)) if tk else None
    so_du = _so_nguyen(data.get("runningBalance"))
    return {
        "id": gid or "0", "thu_nghiem": thu, "so_tien": so_tien,
        "mo_ta": _chu(data.get("description"), 300), "ma_gd": _chu(data.get("reference"), 80),
        "so_du": so_du, "luc": _moc_gd(data.get("transactionDateTime")) or bay_gio,
        "luc_nhan": bay_gio, "tk4": cuoi4(tk), "nhan_tk": nhan or "",
        "ngan_hang": _chu(data.get("bankName"), 60), "viet_tat": _chu(data.get("bankAbbreviation"), 20),
        "tk_ao4": cuoi4(data.get("virtualAccountNumber")),
        "nguoi_chuyen": _chu(data.get("counterAccountName"), 80),
        "tk_chuyen4": cuoi4(data.get("counterAccountNumber")),
        "ngan_hang_chuyen": _chu(data.get("counterAccountBankName"), 60),
    }


def nen_bao(gd: dict) -> bool:
    if gd.get("thu_nghiem"):
        return True       # "Gọi thử" của Casso luôn phải thấy được, để biết đã nối đúng
    d = _cai_dat()
    if bool(d.get("chi_tien_vao", True)) and gd["so_tien"] <= 0:
        return False
    return abs(gd["so_tien"]) >= int(d.get("nguong_toi_thieu") or 0)


def nhan(body: dict) -> tuple:
    """Nhận thân webhook Casso (đã qua kiểm chữ ký). Trả (trang_thai, cau_bao):
    trang_thai là "luu" hoặc "trung"; cau_bao là None khi không cần báo."""
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise ValueError("thân webhook không có data")
    gd = chuan_hoa(body["data"])
    with _KHOA:
        kho = _kho()
        if not gd["thu_nghiem"] and gd["id"] in set(kho["da_thay"]):
            return "trung", None
        kho["giao_dich"].append(gd)
        kho["giao_dich"] = kho["giao_dich"][-GIU_TOI_DA:]
        if not gd["thu_nghiem"]:
            kho["da_thay"].append(gd["id"])
            kho["da_thay"] = kho["da_thay"][-ID_DA_THAY_TOI_DA:]
        _ghi_json(file_kho(), kho)
    return "luu", (cau_bao(gd) if nen_bao(gd) else None)


# ---------------------------------------------------------------- đọc

def _moc(x, cuoi_ngay: bool = False) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        pass
    s = str(x).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            d = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=_tz())
            return (d + timedelta(days=1)).timestamp() - 0.001 if cuoi_ngay else d.timestamp()
        d = datetime.fromisoformat(s)
        return (d if d.tzinfo else d.replace(tzinfo=_tz())).timestamp()
    except ValueError:
        raise ValueError(f"mốc thời gian không hiểu được: {s!r} (dùng YYYY-MM-DD hoặc ISO)")


def dau_hom_nay() -> float:
    n = datetime.now(_tz())
    return n.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def danh_sach(limit: int = 100, chi_vao: bool = False, tu_ngay=None, den_ngay=None,
              tim: str = "", co_thu_nghiem: bool = True) -> list:
    """Giao dịch mới nhất trước. tu_ngay/den_ngay: YYYY-MM-DD, ISO hoặc epoch."""
    tu, den = _moc(tu_ngay), _moc(den_ngay, cuoi_ngay=True)
    try:
        limit = max(1, min(int(limit or 100), TRA_TOI_DA))
    except (TypeError, ValueError):
        limit = 100
    tim = str(tim or "").strip().lower()
    out = []
    with _KHOA:
        ds = list(_kho()["giao_dich"])
    for g in sorted(ds, key=lambda x: x.get("luc") or 0, reverse=True):
        if chi_vao and (g.get("so_tien") or 0) <= 0:
            continue
        if not co_thu_nghiem and g.get("thu_nghiem"):
            continue
        if tu is not None and (g.get("luc") or 0) < tu:
            continue
        if den is not None and (g.get("luc") or 0) > den:
            continue
        if tim and tim not in (" ".join(str(g.get(k) or "") for k in
                                        ("mo_ta", "nguoi_chuyen", "ma_gd"))).lower():
            continue
        out.append(dict(g))
        if len(out) >= limit:
            break
    return out


def tong(ds: list) -> dict:
    that = [g for g in ds if not g.get("thu_nghiem")]
    vao = [g["so_tien"] for g in that if g.get("so_tien", 0) > 0]
    ra = [-g["so_tien"] for g in that if g.get("so_tien", 0) < 0]
    return {"tong_vao": sum(vao), "so_gd_vao": len(vao), "tong_ra": sum(ra), "so_gd_ra": len(ra),
            "so_gd": len(that)}


def tong_hom_nay() -> dict:
    return tong(danh_sach(limit=TRA_TOI_DA, tu_ngay=dau_hom_nay(), co_thu_nghiem=False))


# ---------------------------------------------------------------- soạn câu

def tien(n) -> str:
    """599000 -> '599.000đ'."""
    n = int(n or 0)
    return f"{abs(n):,}".replace(",", ".") + "đ"


def gio(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), _tz()).strftime("%H:%M %d/%m")
    except Exception:
        return "?"


def _ten_tk(gd: dict) -> str:
    ngan_hang = gd.get("ngan_hang") or gd.get("viet_tat") or ""
    so = (" " + gd["tk4"]) if gd.get("tk4") else ""
    if gd.get("nhan_tk"):
        return f"{gd['nhan_tk']} ({(ngan_hang + so).strip()})" if (ngan_hang or so) else gd["nhan_tk"]
    return f"TK {ngan_hang}{so}".strip() if (ngan_hang or so) else "tài khoản"


def cau_bao(gd: dict) -> str:
    vao = gd["so_tien"] > 0
    dau = ("💰 +" if vao else "💸 -") + tien(gd["so_tien"]) + (" vào " if vao else " ra khỏi ") + _ten_tk(gd)
    if gd.get("thu_nghiem"):
        dau += " (thử nghiệm)"
    dong = [dau]
    if gd.get("mo_ta"):
        dong.append("Nội dung: " + gd["mo_ta"][:200])
    if gd.get("nguoi_chuyen"):
        nh = f" ({gd['ngan_hang_chuyen']})" if gd.get("ngan_hang_chuyen") else ""
        dong.append(("Người chuyển: " if vao else "Người nhận: ") + gd["nguoi_chuyen"] + nh)
    if gd.get("so_du") is not None:
        dong.append("Số dư: " + ("-" if gd["so_du"] < 0 else "") + tien(gd["so_du"]))
    dong.append("Lúc " + gio(gd.get("luc")))
    return "\n".join(dong)


def mau_thu() -> dict:
    """Thân giả dùng cho nút "Gửi thử" (không qua Casso)."""
    return {"error": 0, "data": {
        "id": 0, "reference": "MINMIN_GUI_THU", "description": "MinMin gui thu bao bien dong",
        "amount": 599000, "runningBalance": 25000000,
        "transactionDateTime": datetime.now(_tz()).strftime("%Y-%m-%d %H:%M:%S"),
        "accountNumber": "0000", "bankName": "Ngân hàng thử", "bankAbbreviation": "TEST",
        "counterAccountName": "NGUYEN VAN A", "counterAccountBankName": "VietinBank"}}
