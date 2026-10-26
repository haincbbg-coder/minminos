"""meta_ads_duyet.py - Bật/tắt chiến dịch, nhóm quảng cáo, quảng cáo Facebook CÓ BƯỚC DUYỆT (26.10.252).

Luồng:
  1. Model gọi `meta_ads_de_xuat_trang_thai` (plugin meta-ads-graph) -> `tao()`. KHÔNG đổi gì trên
     Facebook. Hàm đọc từng đối tượng bằng token của tài khoản Facebook đọc được nó, lưu một đề xuất
     (tên, tài khoản quảng cáo, tài khoản Facebook sẽ dùng, chi hôm nay, trạng thái trước -> sau).
  2. Chủ thấy thẻ duyệt (dashboard: JAVIS_CARD type "duyet_ads"; Telegram: tin có nút fa:<id>:d|t).
     Nội dung thẻ lấy từ ĐỀ XUẤT ĐÃ LƯU, không từ chữ model.
  3. Chủ bấm Duyệt -> `quyet(id, "duyet")`: chạy đúng một lần (khoá theo id, bấm hai lần không chạy
     lại), đọc lại trạng thái thật, ghi sổ hành động, báo kết quả. Có Hoàn tác trong 30 phút.
Không tool nào của model gọi `quyet`: chỉ route HTTP (đòi header Sec-Fetch-Site: same-origin mà trình duyệt tự
gửi) và nút Telegram. NÓI THẬT (soát độc lập 26.10.252): não CLI chạy ở mức Toàn quyền có shell, về lý thuyết vẫn
giả được request hoặc đọc token trong STATE_DIR rồi gọi thẳng Facebook. Năng lực đó có từ trước tính năng này;
bước duyệt chặn được model ở mọi mức thấp hơn và mọi não API, không thay được việc giới hạn shell.

Tôn trọng Quyền theo loại việc: loại "tien" (tiền & quảng cáo) bị chủ CHẶN thì không chạy.
Không bao giờ trả token ra ngoài (`xem()` bỏ conn_id).
"""
from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import meta_tai_san as mts

HET_HAN_GIAY = 30 * 60        # đề xuất chờ duyệt quá 30 phút thì hết hạn (trạng thái có thể đã khác)
HOAN_TAC_GIAY = 30 * 60
MAX_MUC = 20
_NHAN_CAP = {"campaign": "chiến dịch", "adset": "nhóm quảng cáo", "ad": "quảng cáo"}

_duong: Optional[Path] = None
_post_fn: Optional[Callable] = None
_tg_fn: Optional[Callable] = None
_chinh_sach_fn: Optional[Callable] = None
_KHOA: dict = {}


def dat_duong(p) -> None:
    global _duong
    _duong = Path(p)


def dat_post(fn) -> None:
    """async fn(path, data, token) -> dict."""
    global _post_fn
    _post_fn = fn


def dat_gui_telegram(fn) -> None:
    """async fn(chat_id, text, reply_markup) -> bool. main.py gắn khi có bot."""
    global _tg_fn
    _tg_fn = fn


def dat_chinh_sach(fn) -> None:
    """fn() -> dict chính sách loại việc đã chuẩn hoá (hanh_dong.chuan_hoa_chinh_sach)."""
    global _chinh_sach_fn
    _chinh_sach_fn = fn


# ---------------------------------------------------------------- kho
def _file() -> Path:
    if _duong:
        return _duong
    import config
    return Path(config.STATE_DIR) / "meta-ads-duyet.json"


def _doc_kho() -> dict:
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ghi_kho(d: dict) -> None:
    # Giữ 200 đề xuất mới nhất là đủ để tra lại.
    if len(d) > 200:
        for k in sorted(d, key=lambda k: d[k].get("tao_luc_ts", 0))[:len(d) - 200]:
            d.pop(k, None)
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def _luu(rec: dict) -> None:
    d = _doc_kho()
    d[rec["id"]] = rec
    _ghi_kho(d)


# ---------------------------------------------------------------- mạng
async def _post(path, data, token) -> dict:
    if _post_fn:
        return await _post_fn(path, data, token)
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{mts.GRAPH}/{str(path).lstrip('/')}", data={**(data or {}), "access_token": token})
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": mts.sach(f"{type(e).__name__}: {e}")}}


def _msg(d) -> str:
    e = mts._loi(d) or {}
    return str(e.get("message") or "")


def _so(v) -> Optional[int]:
    try:
        return int(float(v))
    except Exception:
        return None


def _cap(d) -> str:
    t = str(((d or {}).get("metadata") or {}).get("type") or "").lower()
    if t in ("adgroup", "ad"):
        return "ad"
    if t in ("adset", "adcampaign"):
        return "adset"
    if t in ("campaign", "adcampaign_group"):
        return "campaign"
    return ""


async def _ban_do_tk() -> tuple:
    """(conn_id -> (fb_id, tên tài khoản Facebook), account_id -> fb_id nên dùng, account_id -> tên TKQC)."""
    try:
        ts = await mts.tai_san()
    except Exception:
        return {}, {}, {}
    conn = {}
    for t in ts.get("tai_khoan") or []:
        for k in t.get("ket_noi") or []:
            conn[k["id"]] = (t["fb_id"], t["ten"])
    dung = {a["id"]: a.get("dung") for a in ts.get("tkqc") or []}
    ten = {a["id"]: a.get("ten") for a in ts.get("tkqc") or []}
    return conn, dung, ten


async def _doc_doi_tuong(oid: str, conns: list, uu_tien_fb: dict, conn_fb: dict) -> tuple:
    """Đọc một đối tượng quảng cáo bằng token đầu tiên đọc được nó, ưu tiên tài khoản Facebook có quyền
    ghi với tài khoản quảng cáo đó. Trả (dict|None, conn_id, lỗi)."""
    loi = ""
    thu = list(conns)
    for vong in range(2):
        for c in thu:
            tok = await mts._token(c["id"])
            if not tok:
                continue
            d = await mts._http(oid, {"fields": "id,name,status,effective_status,account_id", "metadata": "1"}, tok)
            if mts._loi(d):
                loi = _msg(d)
                continue
            aid = str(d.get("account_id") or "")
            muon = uu_tien_fb.get(aid)
            if vong == 0 and muon and conn_fb.get(c["id"], ("",))[0] != muon:
                # Đọc được nhưng tài khoản này không phải người nên dùng: thử người kia trước.
                continue
            return d, c["id"], ""
    return None, "", loi or "không tài khoản Facebook nào đọc được"


# ---------------------------------------------------------------- tạo đề xuất
def _la_tg(chat) -> bool:
    return bool(re.fullmatch(r"-?\d{4,20}", str(chat or "").strip()))


async def tao(muc, chat: str = "", ly_do: str = "") -> dict:
    ds = [m for m in (muc or []) if isinstance(m, dict) and str(m.get("id") or "").strip()]
    if not ds:
        return {"ok": False, "loi": "Chưa có đối tượng nào để đổi. Dùng meta_ads_tim để tìm mã chiến dịch trước."}
    if len(ds) > MAX_MUC:
        return {"ok": False, "loi": f"Mỗi lần duyệt tối đa {MAX_MUC} đối tượng."}
    chan = _bi_chan()
    if chan:
        return {"ok": False, "loi": "Không tạo đề xuất: " + chan}
    conns = mts._ket_noi()
    if not conns:
        return {"ok": False, "loi": "Chưa nối tài khoản Facebook nào (Meta Ads hoặc Facebook Trang)."}
    conn_fb, dung, ten_tk = await _ban_do_tk()
    out, loi = [], []
    for m in ds:
        oid = str(m.get("id") or "").strip()
        if not re.fullmatch(r"\d{5,25}", oid):
            loi.append(f"{oid[:40]}: mã phải là dãy số của chiến dịch / nhóm / quảng cáo")
            continue
        tt = str(m.get("trang_thai") or "").strip().lower()
        if tt not in ("bat", "tat"):
            loi.append(f"{oid}: trang_thai phải là 'bat' hoặc 'tat'")
            continue
        d, cid, e = await _doc_doi_tuong(oid, conns, dung, conn_fb)
        if not d:
            loi.append(f"{oid}: {e}")
            continue
        tok = await mts._token(cid)
        cap = _cap(d)
        if not cap:
            loi.append(f"{oid}: không phải chiến dịch, nhóm quảng cáo hay quảng cáo")
            continue
        if str(d.get("effective_status") or "") in ("DELETED", "ARCHIVED"):
            loi.append(f"{oid}: đã xoá hoặc lưu trữ, không bật tắt được")
            continue
        aid = str(d.get("account_id") or "")
        ngan_sach = None
        if cap in ("campaign", "adset"):
            b = await mts._http(oid, {"fields": "daily_budget,lifetime_budget"}, tok)
            if not mts._loi(b):
                ngan_sach = _so(b.get("daily_budget"))
        chi = None
        ins = await mts._http(f"{oid}/insights", {"date_preset": "today", "fields": "spend"}, tok)
        if not mts._loi(ins):
            rows = (ins or {}).get("data") or []
            chi = _so(rows[0].get("spend")) if rows else 0
        tk_ten = ten_tk.get(aid) or ""
        if not tk_ten and aid:
            a = await mts._http(f"act_{aid}", {"fields": "name"}, tok)
            tk_ten = "" if mts._loi(a) else str(a.get("name") or "")
        fb_id, fb_ten = conn_fb.get(cid, ("", ""))
        if not fb_ten:
            fb_ten = next((c["label"] for c in conns if c["id"] == cid), "")
        sang = "ACTIVE" if tt == "bat" else "PAUSED"
        tu = str(d.get("status") or "")
        out.append({"id": oid, "cap": cap, "ten": str(d.get("name") or oid), "tk_id": aid,
                    "tk_ten": tk_ten or (f"act_{aid}" if aid else ""), "fb_id": fb_id, "fb_ten": fb_ten,
                    "conn_id": cid, "tu": tu, "hieu_luc": str(d.get("effective_status") or ""), "sang": sang,
                    "khong_doi": tu == sang, "chi_hom_nay": chi, "ngan_sach_ngay": ngan_sach})
    if not out:
        return {"ok": False, "loi": "Không đọc được đối tượng nào: " + "; ".join(loi)}
    now = time.time()
    rec = {"id": secrets.token_hex(6), "tao_luc": datetime.now().isoformat(timespec="seconds"), "tao_luc_ts": now,
           "het_han_ts": now + HET_HAN_GIAY, "trang_thai": "cho", "muc": out, "chat": str(chat or ""),
           "ly_do": str(ly_do or "")[:300], "bo_qua": loi, "ket_qua": [], "lich_su": []}
    _luu(rec)
    da_gui_tg = False
    if _la_tg(chat) and _tg_fn:
        try:
            da_gui_tg = bool(await _tg_fn(str(chat), chu_tg(rec), ban_phim_tg(rec["id"])))
        except Exception:
            da_gui_tg = False
    v = xem(rec["id"])
    v["da_gui_telegram"] = da_gui_tg
    return v


# ---------------------------------------------------------------- xem
KET_GIAY = 600   # "dang_chay" quá 10 phút = máy chủ khởi động lại giữa chừng


def _het_han_neu_can(rec: dict) -> dict:
    if rec.get("trang_thai") == "cho" and time.time() > float(rec.get("het_han_ts") or 0):
        rec["trang_thai"] = "het_han"
    if rec.get("trang_thai") == "dang_chay" and time.time() - float(rec.get("dang_chay_ts") or 0) > KET_GIAY:
        rec["trang_thai"] = "loi"
        rec["xong_ts"] = float(rec.get("dang_chay_ts") or time.time())
        rec["thong_bao"] = ("Máy chủ dừng giữa lúc đang đổi. Mục nào đã ghi kết quả vẫn hoàn tác được; "
                            "kiểm tra lại các mục còn lại trên Trình quản lý quảng cáo.")
    return rec


def _con_hoan_tac(k: dict) -> bool:
    return bool(k.get("ok") and k.get("da_doi") and not k.get("da_hoan_tac"))


def _co_the_hoan_tac(rec: dict) -> bool:
    return (rec.get("trang_thai") in ("xong", "loi")
            and any(_con_hoan_tac(k) for k in rec.get("ket_qua") or [])
            and time.time() - float(rec.get("xong_ts") or 0) < HOAN_TAC_GIAY)


def _gon(rec: dict) -> dict:
    rec = _het_han_neu_can(dict(rec))
    muc = [{k: v for k, v in m.items() if k != "conn_id"} for m in rec.get("muc") or []]
    caps = {m["cap"] for m in muc}
    return {"ok": True, "id": rec["id"], "trang_thai": rec["trang_thai"], "tao_luc": rec.get("tao_luc"),
            "cap": caps.pop() if len(caps) == 1 else "khac", "muc": muc, "ket_qua": rec.get("ket_qua") or [],
            "hoan_tac": rec.get("hoan_tac") or [],
            "bo_qua": rec.get("bo_qua") or [], "ly_do": rec.get("ly_do") or "",
            "co_the_hoan_tac": _co_the_hoan_tac(rec), "da_hoan_tac": bool(rec.get("da_hoan_tac")),
            "da_chay": False,   # True chỉ trên câu trả lời của lần bấm Duyệt đã thật sự chạy
            "nguoi_quyet": rec.get("nguoi_quyet") or "", "nguon_quyet": rec.get("nguon_quyet") or "",
            "thong_bao": rec.get("thong_bao") or ""}


def xem(rid: str) -> Optional[dict]:
    rec = _doc_kho().get(str(rid or ""))
    return _gon(rec) if rec else None


# ---------------------------------------------------------------- quyết
def _bi_chan() -> str:
    try:
        import hanh_dong
        cs = _chinh_sach_fn() if _chinh_sach_fn else _chinh_sach_that()
        ok, why = hanh_dong.cho_phep(cs or {}, "tien")
        return "" if ok else why
    except Exception as e:
        # Fail-closed: không đọc được chính sách thì KHÔNG chạy (đúng lúc sự cố là lúc dễ sai nhất).
        return f"không đọc được chính sách Quyền theo loại việc ({type(e).__name__}), không chạy"


def _chinh_sach_that() -> dict:
    import config
    import hanh_dong
    return hanh_dong.chuan_hoa_chinh_sach((config.read_settings().get("quyen") or {}).get("loai_viec") or {})


def _ghi_so(m: dict, ok: bool, err: str, ai: str, nguon: str, hanh: str) -> None:
    try:
        import hanh_dong
        hanh_dong.ghi(hanh_dong.dong_so(
            ai=ai or "chủ", tool="meta_ads_doi_trang_thai", connector="meta-ads-graph", label=m.get("fb_ten") or "",
            loai="tien", cls="write", mode="full", ok=ok, ms=0,
            args={"id": m["id"], "ten": m.get("ten"), "trang_thai": hanh, "duyet_qua": nguon}, err=err))
    except Exception:
        pass


async def _doi(m: dict, dich: str, phai_dang=None) -> dict:
    """Đổi một đối tượng. Trước khi ghi, ĐỌC LẠI và so với đề xuất đã lưu (tên, tài khoản quảng cáo, kiểu):
    lệch thì không đổi - phòng trường hợp file đề xuất bị sửa sau khi chủ đã xem thẻ (soát độc lập N3).
    `phai_dang`: trạng thái hiện tại bắt buộc (hoàn tác chỉ khi vẫn đúng trạng thái MinMin đã đặt)."""
    tok = await mts._token(m["conn_id"])
    if not tok:
        return {"id": m["id"], "ten": m["ten"], "ok": False, "loi": "tài khoản Facebook mất token, đăng nhập lại"}
    if not re.fullmatch(r"\d{5,25}", str(m.get("id") or "")):
        return {"id": m.get("id"), "ten": m.get("ten"), "ok": False, "loi": "mã đối tượng không hợp lệ"}
    hien = await mts._http(m["id"], {"fields": "id,name,status,account_id", "metadata": "1"}, tok)
    if mts._loi(hien):
        return {"id": m["id"], "ten": m["ten"], "ok": False, "loi": "không đọc lại được trước khi đổi: " + _msg(hien)[:150]}
    if (str(hien.get("name") or "") != m["ten"] or str(hien.get("account_id") or "") != m["tk_id"]
            or _cap(hien) != m["cap"]):
        return {"id": m["id"], "ten": m["ten"], "ok": False,
                "loi": "đối tượng trên Facebook không khớp đề xuất (tên, tài khoản hoặc loại đã khác), không đổi"}
    if phai_dang and str(hien.get("status") or "") != phai_dang:
        return {"id": m["id"], "ten": m["ten"], "ok": False,
                "loi": f"trạng thái đã bị đổi tay thành {hien.get('status')}, không hoàn tác để khỏi đè"}
    d = await _post(m["id"], {"status": dich}, tok)
    if mts._loi(d):
        msg = _msg(d)
        goi_y = (" Tài khoản Facebook này chưa có quyền quản lý quảng cáo: Kết nối > Facebook > Soi quyền."
                 if ("permission" in msg.lower() or "(#200)" in msg or "(#10)" in msg) else "")
        return {"id": m["id"], "ten": m["ten"], "ok": False, "loi": msg[:200] + goi_y}
    if isinstance(d, dict) and d.get("success") is False:
        return {"id": m["id"], "ten": m["ten"], "ok": False, "loi": "Facebook trả success=false"}
    lai = await mts._http(m["id"], {"fields": "status,effective_status"}, tok)
    st = "" if mts._loi(lai) else str(lai.get("status") or "")
    hl = "" if mts._loi(lai) else str(lai.get("effective_status") or "")
    if not st:
        return {"id": m["id"], "ten": m["ten"], "ok": True, "da_doi": True, "chua_xac_minh": True,
                "trang_thai_moi": dich, "hieu_luc": "", "ghi_chu": "Facebook nhận lệnh nhưng chưa đọc lại được để xác minh"}
    if st != dich:
        return {"id": m["id"], "ten": m["ten"], "ok": False, "trang_thai_moi": st, "hieu_luc": hl,
                "loi": f"Facebook báo đã nhận nhưng đọc lại vẫn là {st}"}
    return {"id": m["id"], "ten": m["ten"], "ok": True, "da_doi": True, "trang_thai_moi": st or dich, "hieu_luc": hl}


def _tra(rec: dict, tb: str) -> dict:
    """Lưu rec (lịch sử bấm) nhưng KHÔNG ghi đè thông báo kết quả đã có; câu tb chỉ đi về người vừa bấm."""
    _luu(rec)
    v = _gon(rec)
    v["thong_bao"] = tb
    v["da_chay"] = False
    return v


async def quyet(rid: str, hanh_dong: str, ai: str = "", nguon: str = "dashboard") -> dict:
    rid = str(rid or "")
    hd = str(hanh_dong or "").strip().lower()
    if len(_KHOA) > 500:
        for k in [k for k, v in _KHOA.items() if not v.locked()]:
            _KHOA.pop(k, None)
    khoa = _KHOA.setdefault(rid, asyncio.Lock())
    async with khoa:
        kho = _doc_kho()
        rec = kho.get(rid)
        if not rec:
            return {"ok": False, "loi": "Không có đề xuất này (có thể đã quá cũ)."}
        rec = _het_han_neu_can(rec)
        tt = rec.get("trang_thai")
        rec.setdefault("lich_su", []).append({"luc": datetime.now().isoformat(timespec="seconds"), "hanh_dong": hd,
                                              "nguon": nguon, "ai": ai})
        if hd in ("tu_choi", "sua"):
            if tt != "cho":
                return _tra(rec, "Đề xuất này đã được xử lý rồi.")
            if tt == "cho":
                rec["trang_thai"] = "tu_choi"
                rec["sua"] = hd == "sua"
                rec["nguoi_quyet"], rec["nguon_quyet"] = ai, nguon
                rec["thong_bao"] = "Đã từ chối, không đổi gì." if hd == "tu_choi" else "Chưa đổi gì, chờ bạn sửa lại."
            _luu(rec)
            return _gon(rec)
        if hd == "duyet":
            if tt != "cho":
                return _tra(rec, {"het_han": "Đề xuất đã hết hạn (quá 30 phút). Nhờ MinMin tạo lại để đọc trạng thái mới.",
                                  "tu_choi": "Đề xuất này đã bị từ chối."}.get(tt, "Đề xuất này đã được xử lý rồi."))
            chan = _bi_chan()
            if chan:
                return _tra(rec, "Không chạy: " + chan)
            rec["trang_thai"] = "dang_chay"
            rec["dang_chay_ts"] = time.time()
            rec["nguoi_quyet"], rec["nguon_quyet"] = ai, nguon
            rec["ket_qua"] = []
            _luu(rec)
            kq = rec["ket_qua"]
            for m in rec["muc"]:
                if m.get("khong_doi"):
                    kq.append({"id": m["id"], "ten": m["ten"], "ok": True, "da_doi": False,
                               "trang_thai_moi": m["sang"], "ghi_chu": "đã ở trạng thái này, không cần đổi"})
                    continue
                r = await _doi(m, m["sang"])
                _ghi_so(m, r["ok"], r.get("loi", ""), ai, nguon, m["sang"])
                kq.append(r)
                _luu(rec)          # lưu sau từng mục: máy chủ dừng giữa chừng vẫn biết mục nào đã đổi
            so_ok = sum(1 for k in kq if k["ok"])
            rec["trang_thai"] = "xong" if so_ok else "loi"
            rec["xong_ts"] = time.time()
            rec["thong_bao"] = f"Đã đổi {so_ok}/{len(kq)}."
            if any(k.get("chua_xac_minh") for k in kq):
                rec["thong_bao"] += " Có mục chưa xác minh được, xem lại trên Trình quản lý quảng cáo."
            _luu(rec)
            v = _gon(rec)
            v["da_chay"] = True
            return v
        if hd == "hoan_tac":
            if not _co_the_hoan_tac(rec):
                return _tra(rec, "Không hoàn tác được nữa (quá 30 phút hoặc chưa đổi gì).")
            chan = _bi_chan()
            if chan:
                return _tra(rec, "Không chạy: " + chan)
            theo_id = {m["id"]: m for m in rec["muc"]}
            ht = []
            for k in rec["ket_qua"]:
                if not _con_hoan_tac(k):
                    continue
                m = theo_id[k["id"]]
                r = await _doi(m, m["tu"], phai_dang=m["sang"])
                _ghi_so(m, r["ok"], r.get("loi", ""), ai, nguon, m["tu"] + " (hoàn tác)")
                if r["ok"]:
                    k["da_hoan_tac"] = True       # chỉ đánh dấu mục hoàn tác được; mục lỗi còn thử lại được
                ht.append(r)
                _luu(rec)
            rec["hoan_tac"] = ht
            rec["da_hoan_tac"] = not any(_con_hoan_tac(k) for k in rec["ket_qua"])
            rec["thong_bao"] = f"Đã hoàn tác {sum(1 for x in ht if x['ok'])}/{len(ht)}."
            _luu(rec)
            return _gon(rec)
        return {"ok": False, "loi": "hanh_dong phải là duyet, tu_choi, sua hoặc hoan_tac."}


# ---------------------------------------------------------------- Telegram
def _tien(v) -> str:
    return "" if v is None else f"{int(v):,}".replace(",", ".") + " đ"


def _nhan_tt(st: str) -> str:
    return {"ACTIVE": "Đang chạy", "PAUSED": "Đang tắt"}.get(st, st or "?")


def chu_tg(rec: dict) -> str:
    v = _gon(rec)
    cap = _NHAN_CAP.get(v["cap"], "đối tượng")
    dong = [f"Chờ duyệt: đổi {len(v['muc'])} {cap}", ""]
    for i, m in enumerate(v["muc"], 1):
        phu = " · ".join(x for x in (m.get("tk_ten"), m.get("fb_ten"),
                                     ("chi hôm nay " + _tien(m["chi_hom_nay"])) if m.get("chi_hom_nay") is not None else "",
                                     (_tien(m["ngan_sach_ngay"]) + "/ngày") if m.get("ngan_sach_ngay") else "") if x)
        dich = "Bật" if m["sang"] == "ACTIVE" else "Tắt"
        dong += [f"{i}. {m['ten']}", phu, f"{_nhan_tt(m['tu'])} -> {dich}" + (" (đã đúng, không đổi)" if m.get("khong_doi") else ""), ""]
    dong.append("Chưa đổi gì cho tới khi bạn bấm Duyệt.")
    return "\n".join(dong)


def chu_ket_qua(v: dict) -> str:
    if v["trang_thai"] in ("xong", "loi"):
        dong = [v.get("thong_bao") or "Đã xử lý."]
        for k in v.get("ket_qua") or []:
            dong.append(("Xong: " if k["ok"] else "Lỗi: ") + k["ten"]
                        + (f" -> {_nhan_tt(k.get('trang_thai_moi', ''))}" if k["ok"] else f" ({k.get('loi', '')})"))
        return "\n".join(dong)
    return v.get("thong_bao") or {"tu_choi": "Đã từ chối, không đổi gì.", "het_han": "Đề xuất đã hết hạn."}.get(v["trang_thai"], "")


def ban_phim_tg(rid: str) -> dict:
    return {"inline_keyboard": [[{"text": "Duyệt", "callback_data": f"fa:{rid}:d"},
                                 {"text": "Từ chối", "callback_data": f"fa:{rid}:t"}]]}


async def tg_callback(data: str, ai: str = "") -> Optional[dict]:
    """Nhánh "fa:<id>:<d|t>" của _tg_callback. Trả {'text','alert'} hoặc None nếu không phải nhánh này."""
    m = re.fullmatch(r"fa:([a-f0-9]{8,32}):([dt])", str(data or ""))
    if not m:
        return None
    v = await quyet(m.group(1), "duyet" if m.group(2) == "d" else "tu_choi", ai=ai, nguon="telegram")
    if not v.get("ok", True) and v.get("loi"):
        return {"text": v["loi"], "alert": True}
    return {"text": chu_ket_qua(v), "alert": False}
