"""goi_y_anh.py - gợi ý mã hàng từ ẢNH khách gửi (26.10.225).

Hai bước để vừa nhanh vừa rẻ:
  1. Rút gọn bằng màu, chạy trên máy chủ, không tốn token: so biểu đồ màu của ảnh khách với ảnh mẫu trên POS
     và với ảnh khách mà nhân viên ĐÃ xác nhận trước đó. Giữ K mã giống nhất (mặc định 36).
  2. Nhờ ChatGPT (gói đã đăng nhập, xem image_vision) nhìn ảnh khách cạnh một bảng ảnh mẫu của K mã đó, mỗi ô ghi
     mã ở góc, chọn tối đa 5 mã cùng kiểu. Một lần gọi, hai ảnh.
Kết quả lưu theo mã băm của ảnh nên cùng một ảnh hỏi lại không tốn gì. Có trần số lần gọi AI mỗi ngày.
Nhân viên bấm "Đúng mã này" thì đặc trưng màu của ảnh khách đó được cộng vào kho của mã, lần sau bước 1 chính xác hơn.

Kho dùng chung file goi_y_ma.db (bảng sku_dt, anh_cache, anh_dem) và thư mục `mau/` cạnh nó để giữ ảnh thu nhỏ.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import time
from typing import Callable, Optional

import goi_y_ma as gm

K_RUT_GON = 36
TRAN_MOI_NGAY = int(os.getenv("JAVIS_GOI_Y_ANH_TRAN_NGAY", "500"))
ANH_TOI_DA = 6 * 1024 * 1024
TOI_DA_ANH_MAU = 3                       # ảnh mẫu mỗi mã
HE_SO_KHACH = 1.15                       # ảnh khách đã xác nhận được ưu tiên hơn ảnh mẫu một chút
_NGAY_KHAC = 24 * 3600


def _pil():
    from PIL import Image
    return Image


def _db():
    c = gm._db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS sku_dt(id INTEGER PRIMARY KEY AUTOINCREMENT, ma TEXT, loai TEXT, khoa TEXT,
        dt TEXT, UNIQUE(ma, loai, khoa));
    CREATE INDEX IF NOT EXISTS sku_dt_ma ON sku_dt(ma);
    CREATE TABLE IF NOT EXISTS anh_cache(hash TEXT PRIMARY KEY, luc REAL, dt TEXT, kq TEXT);
    CREATE TABLE IF NOT EXISTS anh_dem(ngay TEXT PRIMARY KEY, n INTEGER);
    """)
    return c


def thu_muc_mau():
    d = gm.thu_muc() / "mau"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ đặc trưng màu

_NHOM = 28           # 4 mức xám + 12 sắc x 2 độ sáng


def dac_trung(raw: bytes) -> list:
    """Biểu đồ màu 28 ô của vùng giữa ảnh (bỏ viền để bớt nền), chuẩn hoá tổng 1."""
    Image = _pil()
    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGB")
    im.thumbnail((128, 128))
    w, h = im.size
    c = im.crop((int(w * .12), int(h * .08), max(int(w * .88), int(w * .12) + 1), max(int(h * .92), int(h * .08) + 1)))
    c = c.resize((28, 28)).convert("HSV")
    hist = [0.0] * _NHOM
    for hh, ss, vv in c.getdata():
        if ss < 45 or vv < 40:
            hist[min(3, vv // 64)] += 0.35 if vv > 200 else 1.0      # nền trắng/xám nhạt đếm nhẹ
        else:
            # Dịch sắc độ nửa ô để màu đỏ (nằm sát biên 0/255) rơi giữa một ô, rồi chia nhẹ sang hai ô bên
            # cạnh: hai ảnh cùng một màu chụp lệch sáng một chút vẫn giống nhau.
            b = ((hh + 11) % 256) * 12 // 256
            sang = 1 if vv > 150 else 0
            hist[4 + b * 2 + sang] += 0.7
            hist[4 + ((b + 1) % 12) * 2 + sang] += 0.15
            hist[4 + ((b - 1) % 12) * 2 + sang] += 0.15
    tong = sum(hist) or 1.0
    return [round(x / tong, 5) for x in hist]


def giong(a: list, b: list) -> float:
    """Giao hai biểu đồ, 0 đến 1."""
    return sum(min(x, y) for x, y in zip(a, b))


# ------------------------------------------------------------------ ảnh mẫu từ POS

async def _tai(url: str, cl) -> Optional[bytes]:
    import web_watch
    if not str(url).startswith("https://"):
        return None
    try:
        await asyncio.to_thread(web_watch.check_url, url)
        r = await cl.get(url)
    except Exception:
        return None
    if r.status_code != 200 or not r.content or len(r.content) > ANH_TOI_DA:
        return None
    return r.content


def _luu_mau(ma: str, i: int, raw: bytes) -> list:
    Image = _pil()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((360, 360))
    p = thu_muc_mau() / f"{ma}_{i}.jpg"
    im.save(p, "JPEG", quality=82)
    return dac_trung(p.read_bytes())


async def hoc_anh_mau(ma_ds: Optional[list] = None, tai: Optional[Callable] = None, toi_da: int = 400) -> dict:
    """Tải ảnh mẫu của các mã chưa có đặc trưng 'pos', thu nhỏ, lưu và tính đặc trưng. Chạy lại an toàn."""
    import httpx
    with _db() as c:
        rows = c.execute("SELECT ma, anh FROM sku").fetchall()
        co = {r["ma"] for r in c.execute("SELECT DISTINCT ma FROM sku_dt WHERE loai='pos'")}
    can = [(r["ma"], json.loads(r["anh"] or "[]")) for r in rows
           if r["ma"] not in co and json.loads(r["anh"] or "[]") and (not ma_ds or r["ma"] in ma_ds)][:toi_da]
    ok = loi = 0
    sem = asyncio.Semaphore(6)

    async def lam(ma, urls, cl):
        nonlocal ok, loi
        async with sem:
            xong = 0
            for i, u in enumerate(urls[:TOI_DA_ANH_MAU]):
                raw = await (tai(u) if tai else _tai(u, cl))
                if not raw:
                    continue
                try:
                    dt = await asyncio.to_thread(_luu_mau, ma, i, raw)
                except Exception:
                    continue
                with _db() as c:
                    c.execute("INSERT OR REPLACE INTO sku_dt(ma, loai, khoa, dt) VALUES(?,?,?,?)", (ma, "pos", str(i), json.dumps(dt)))
                xong += 1
            if xong:
                ok += 1
            else:
                loi += 1

    async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=10), follow_redirects=False,
                                 headers={"User-Agent": "MinMin/goi-y-anh"}) as cl:
        await asyncio.gather(*[lam(m, u, cl) for m, u in can])
    with _db() as c:
        tong = c.execute("SELECT COUNT(DISTINCT ma) n FROM sku_dt WHERE loai='pos'").fetchone()["n"]
    return {"hoc_xong": ok, "khong_tai_duoc": loi, "tong_ma_co_dac_trung": tong}


# ------------------------------------------------------------------ rút gọn và vẽ bảng ảnh mẫu

def rut_gon(dt: list, k: int = K_RUT_GON) -> list:
    """[(ma, diem)] giảm dần theo độ giống màu, mỗi mã lấy ảnh giống nhất (ảnh khách đã xác nhận nhân hệ số)."""
    tot: dict = {}
    with _db() as c:
        for r in c.execute("SELECT ma, loai, dt FROM sku_dt"):
            s = giong(dt, json.loads(r["dt"])) * (HE_SO_KHACH if r["loai"] == "khach" else 1.0)
            if s > tot.get(r["ma"], -1):
                tot[r["ma"]] = s
    return sorted(tot.items(), key=lambda x: -x[1])[:k]


def ve_bang(ma_ds: list, cot: int = 6, o: int = 220) -> bytes:
    """Bảng ảnh mẫu, mỗi ô ghi mã ở góc trên trái. Trả byte JPEG."""
    from PIL import Image, ImageDraw, ImageFont
    n = len(ma_ds)
    hang = max(1, (n + cot - 1) // cot)
    bg = Image.new("RGB", (cot * o, hang * o), "white")
    try:
        font = ImageFont.load_default(size=30)
    except TypeError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(bg)
    for i, ma in enumerate(ma_ds):
        x, y = (i % cot) * o, (i // cot) * o
        p = thu_muc_mau() / f"{ma}_0.jpg"
        if p.exists():
            im = Image.open(p).convert("RGB")
            im.thumbnail((o - 6, o - 6))
            bg.paste(im, (x + 3 + (o - 6 - im.size[0]) // 2, y + 3 + (o - 6 - im.size[1]) // 2))
        d.rectangle([x, y, x + o - 1, y + o - 1], outline=(200, 200, 200))
        tw = d.textlength(ma, font=font)
        d.rectangle([x, y, x + tw + 12, y + 38], fill=(0, 0, 0))
        d.text((x + 6, y + 3), ma, fill=(255, 255, 0), font=font)
    out = io.BytesIO()
    bg.save(out, "JPEG", quality=85)
    return out.getvalue()


def _data_url(raw: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


CAU_HOI = (
    "Ảnh 1 là ảnh KHÁCH gửi cho shop thời trang. Ảnh 2 là bảng ảnh mẫu của shop, mỗi ô có MÃ viết ở góc trên trái. "
    "Chọn tối đa 5 mã trong bảng có CÙNG kiểu sản phẩm với ảnh khách (kiểu dáng, màu, hoa văn, chi tiết), xếp từ giống nhất. "
    "Chỉ dùng mã có trong bảng, không bịa. Nếu không ô nào giống thì đặt khong_co là true. "
    'Trả lời DUY NHẤT một đối tượng JSON: {"ung_vien":[{"ma":"V33","do_giong":85,"ly_do":"cùng áo thun cổ tròn màu đỏ"}],"khong_co":false}'
)


def doc_tra_loi(text: str, hop_le: set) -> list:
    """Lấy JSON trong câu trả lời của AI (có thể kèm chữ thừa), chỉ giữ mã có thật. [(ma, do_giong 0-100, ly_do)]"""
    t = str(text or "")
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return []
    try:
        j = json.loads(t[a:b + 1])
    except ValueError:
        return []
    if not isinstance(j, dict) or j.get("khong_co"):
        return []
    kq, thay = [], set()
    for u in (j.get("ung_vien") or [])[:5]:
        if not isinstance(u, dict):
            continue
        ma = gm.chuan_ma(u.get("ma"))
        if ma in hop_le and ma not in thay:
            thay.add(ma)
            try:
                dg = max(0.0, min(100.0, float(u.get("do_giong") or 50)))
            except (TypeError, ValueError):
                dg = 50.0
            kq.append((ma, dg, str(u.get("ly_do") or "")[:140]))
    return kq


# ------------------------------------------------------------------ đếm trần mỗi ngày

def _ngay() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def da_dung_hom_nay() -> int:
    with _db() as c:
        r = c.execute("SELECT n FROM anh_dem WHERE ngay=?", (_ngay(),)).fetchone()
        return int(r["n"]) if r else 0


def _cong_dem() -> None:
    with _db() as c:
        c.execute("INSERT INTO anh_dem(ngay, n) VALUES(?,1) ON CONFLICT(ngay) DO UPDATE SET n=n+1", (_ngay(),))


# ------------------------------------------------------------------ tra ảnh

def _ung_vien(ma_ds: list) -> list:
    """Dựng ứng viên cùng định dạng với goi_y_ma.phan_giai, từ [(ma, do_giong, ly_do)]."""
    kq = []
    with gm._db() as c:
        for ma, dg, ly in ma_ds:
            d = {"ma": ma, "bang_chung": [{"nguon": "anh", "ly_do": ("ảnh giống mẫu " + ma + (": " + ly if ly else ""))}],
                 "do_chac": round(min(0.85, 0.35 + 0.5 * dg / 100.0), 2)}
            d.update(gm._ton(c, ma))
            kq.append(d)
    return kq


async def tra_anh(raw: bytes, mime: str = "image/jpeg", mo_ta: Optional[Callable] = None) -> dict:
    """Ảnh khách -> {ok, ung_vien, hash, cache, ...}. `mo_ta` thay được hàm gọi AI (dùng cho test)."""
    if not raw or len(raw) > ANH_TOI_DA:
        return {"ok": False, "error": "ảnh rỗng hoặc quá lớn (trên 6 MB)"}
    h = hashlib.sha1(raw).hexdigest()
    with _db() as c:
        r = c.execute("SELECT kq FROM anh_cache WHERE hash=?", (h,)).fetchone()
    if r:
        return {"ok": True, "hash": h, "cache": True, **json.loads(r["kq"])}
    try:
        dt = await asyncio.to_thread(dac_trung, raw)
    except Exception as e:
        return {"ok": False, "error": f"không đọc được ảnh: {type(e).__name__}"}
    ds = await asyncio.to_thread(rut_gon, dt)
    if not ds:
        return {"ok": False, "hash": h, "error": "chưa học ảnh mẫu nào. Nhờ MinMin chạy javis_goi_y_ma_hoc_anh trước."}
    if da_dung_hom_nay() >= TRAN_MOI_NGAY:
        return {"ok": False, "hash": h, "error": f"đã đủ {TRAN_MOI_NGAY} lần so ảnh bằng AI hôm nay"}
    ma_ds = [m for m, _ in ds]
    bang = await asyncio.to_thread(ve_bang, ma_ds)
    if mo_ta is None:
        import image_vision
        mo_ta = image_vision.describe_data_urls
    kq_ai = await mo_ta([_data_url(raw, mime), _data_url(bang)], CAU_HOI, ["ảnh khách", "bảng ảnh mẫu"])
    _cong_dem()
    if not kq_ai.get("ok"):
        return {"ok": False, "hash": h, "error": kq_ai.get("error") or "AI không trả lời"}
    chon = doc_tra_loi(kq_ai.get("text"), set(ma_ds))
    kq = {"ung_vien": _ung_vien(chon), "khong_co": not chon, "so_mau_xet": len(ma_ds)}
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO anh_cache(hash, luc, dt, kq) VALUES(?,?,?,?)",
                  (h, time.time(), json.dumps(dt), json.dumps(kq, ensure_ascii=False)))
    return {"ok": True, "hash": h, "cache": False, **kq}


def hoc_tu_xac_nhan(ma: str, hash_anh: str) -> bool:
    """Nhân viên chốt ảnh này là mã `ma`: cộng đặc trưng ảnh khách vào kho của mã đó."""
    ma = gm.chuan_ma(ma)
    with _db() as c:
        r = c.execute("SELECT dt FROM anh_cache WHERE hash=?", (str(hash_anh),)).fetchone()
        if not r or not ma:
            return False
        c.execute("INSERT OR REPLACE INTO sku_dt(ma, loai, khoa, dt) VALUES(?,?,?,?)", (ma, "khach", str(hash_anh), r["dt"]))
    return True


def thong_ke() -> dict:
    with _db() as c:
        return {"ma_co_anh_mau": c.execute("SELECT COUNT(DISTINCT ma) n FROM sku_dt WHERE loai='pos'").fetchone()["n"],
                "anh_khach_da_hoc": c.execute("SELECT COUNT(*) n FROM sku_dt WHERE loai='khach'").fetchone()["n"],
                "da_so_hom_nay": da_dung_hom_nay(), "tran_moi_ngay": TRAN_MOI_NGAY}
