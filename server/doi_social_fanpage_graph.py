"""doi_social_fanpage_graph.py - gọi Graph API cho Fanpage (26.10.194).

Hợp đồng: docs/doi-social/FANPAGE.md mục 6. Kho ở `doi_social_fanpage` (đồng bộ, không mạng);
ở đây là phần async: nguồn token, đồng bộ Trang, đăng bài các loại (chữ/ảnh/album/video/reel/story,
bình luận sau đăng, story kèm, Instagram), bình luận (quét/trả lời/ẩn), insights, đổi info, kênh
nguồn (yt-dlp) và `nhip()` cho vòng nền 30 giây của Đội Social.

Không gọi mạng trong test: mọi lời gọi đi qua `_goi()`, thay được bằng `dat_http(fn)` với
`async fn(method, url, params=None, data=None, files=None, headers=None, content=None) -> dict`.
`files` là {tên_trường: (tên_tệp, Path)}, `content` là Path (rupload). Kết nối OAuth, yt-dlp và AI
cũng tiêm được (`dat_ket_noi`, `dat_ytdlp`, `dat_ai`).

Token: page token của kết nối OAuth chỉ nằm TRONG BỘ NHỚ (`_CACHE`, 50 phút), không ghi đĩa; token
dán tay vốn đã lưu ở kho. Không bao giờ ghi token ra log/nhật ký (lỗi đi qua `fp._loc_token`).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

import doi_social_fanpage as fp

GRAPH = "https://graph.facebook.com/v26.0"
GRAPH_VIDEO = "https://graph-video.facebook.com/v26.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v26.0"
CONNECTOR_ID = "facebook-pages"
TTL_TOKEN_TRANG = 50 * 60
LOI_TAM = {1, 2, 4, 17, 32, 613, 341, 368}
LOI_QUYEN = {10, 190, 200}
THU_TOI_DA = 3
THU_LAI_SAU = 600
TRUONG_TRANG = ("id,name,category,link,tasks,access_token,picture{url},followers_count,fan_count,"
                "instagram_business_account{id,username}")
TRUONG_TRANG_TOKEN = "id,name,category,link,picture{url},followers_count,fan_count,instagram_business_account{id,username}"
CONG = {"binh_luan": 600, "kiem_loi": 600, "kenh": 3600, "so_lieu": 6 * 3600, "don_tep": 86400}

_HTTP: Optional[Callable[..., Awaitable[dict]]] = None
_KET_NOI: Optional[Callable[[], list]] = None
_TOKEN_KN: Optional[Callable[[str], Awaitable[str]]] = None
_YTDLP: Optional[tuple] = None
_AI: Optional[Callable[[dict, dict], Awaitable[str]]] = None
_CACHE: dict = {}                 # (trang_id, token_id) -> (page_token, het_luc)
_MOC: dict = {}                   # cổng thời gian của nhip()
_DANG = {"chay": False}


async def _ngu(giay: float) -> None:
    await asyncio.sleep(giay)


# ------------------------------------------------------------------ tiêm phụ thuộc

def dat_http(fn) -> None:
    global _HTTP
    _HTTP = fn


def dat_ket_noi(liet_ke=None, lay_token=None) -> None:
    """Test: thay danh sách kết nối OAuth ([{id, label}]) và hàm async lấy user token."""
    global _KET_NOI, _TOKEN_KN
    _KET_NOI, _TOKEN_KN = liet_ke, lay_token


def dat_ytdlp(liet_ke=None, tai=None) -> None:
    """liet_ke(link, n) -> [{ma, tieu_de, url}] ; tai(url, thu_muc: Path, ma) -> Path. Đồng bộ."""
    global _YTDLP
    _YTDLP = (liet_ke, tai) if liet_ke and tai else None


def dat_ai(fn) -> None:
    """async fn(binh_luan: dict, trang: dict) -> câu trả lời (routes nối vào bộ não MinMin)."""
    global _AI
    _AI = fn


async def _http_that(method, url, params=None, data=None, files=None, headers=None, content=None) -> dict:
    import httpx
    mo = []
    try:
        f = None
        if files:
            f = {}
            for k, (ten, p) in files.items():
                fh = open(p, "rb")
                mo.append(fh)
                f[k] = (ten, fh)
        than = Path(content).read_bytes() if isinstance(content, (str, Path)) else content
        cho = 900 if (files or content is not None) else 60
        async with httpx.AsyncClient(timeout=cho) as c:
            r = await c.request(method, url, params=params, data=data, files=f, headers=headers, content=than)
        try:
            d = r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}", "code": "http"},
                    "_http": r.status_code}
        if not isinstance(d, dict):
            d = {"data": d}
        if r.status_code >= 400:
            d["_http"] = r.status_code
        return d
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {str(e)[:200]}", "code": "mang"}}
    finally:
        for fh in mo:
            try:
                fh.close()
            except Exception:
                pass


async def _goi(method, url, params=None, data=None, files=None, headers=None, content=None) -> dict:
    fn = _HTTP or _http_that
    try:
        kq = await fn(method, url, params=params, data=data, files=files, headers=headers, content=content)
    except Exception as e:
        kq = {"error": {"message": f"{type(e).__name__}: {str(e)[:200]}", "code": "mang"}}
    return kq if isinstance(kq, dict) else {"data": kq}


async def _get(path, params, token) -> dict:
    return await _goi("GET", f"{GRAPH}/{str(path).lstrip('/')}", params={**(params or {}), "access_token": token})


async def _post(path, data, token, files=None, goc=GRAPH) -> dict:
    return await _goi("POST", f"{goc}/{str(path).lstrip('/')}", data={**(data or {}), "access_token": token},
                      files=files)


# ------------------------------------------------------------------ lỗi

def _loi(kq) -> Optional[dict]:
    if not isinstance(kq, dict):
        return {"message": "phản hồi lạ", "code": "khac"}
    e = kq.get("error")
    if e:
        return e if isinstance(e, dict) else {"message": str(e), "code": "khac"}
    if kq.get("success") is False:
        return {"message": "Facebook báo không thành công", "code": "khac"}
    return None


def _ma(e: dict):
    c = (e or {}).get("code")
    try:
        return int(c)
    except (TypeError, ValueError):
        return c


def chu_loi(e: dict) -> str:
    ma = _ma(e)
    msg = str((e or {}).get("error_user_msg") or (e or {}).get("message") or "lỗi không rõ")
    tien = f"#{ma}" if isinstance(ma, int) else ("mạng" if ma == "mang" else str(ma or "lỗi"))
    return fp._loc_token(f"{tien}: {msg}")[:500]


def phan_loai(e: dict, kq: Optional[dict] = None) -> str:
    """'tam' (thử lại), 'quyen' (lỗi ngay + cảnh báo) hoặc 'khac'."""
    ma = _ma(e)
    if ma == "mang":
        return "tam"
    if isinstance(ma, int):
        if ma in LOI_QUYEN or 200 <= ma <= 299:
            return "quyen"
        if ma in LOI_TAM or e.get("is_transient"):
            return "tam"
    if (kq or {}).get("_http", 0) >= 500:
        return "tam"
    return "khac"


# ------------------------------------------------------------------ nguồn token

def _ds_ket_noi() -> Optional[list]:
    """[{id, label}] kết nối facebook-pages đã đăng nhập; None nếu không đọc được kho kết nối."""
    if _KET_NOI is not None:
        try:
            return list(_KET_NOI() or [])
        except Exception:
            return None
    try:
        import mcp_store
        import oauth_mcp
    except Exception:
        return None
    try:
        ra = []
        for c in mcp_store.list_connections():
            if c.get("connector_id") == CONNECTOR_ID and oauth_mcp.status(c["id"]).get("connected"):
                ra.append({"id": c["id"], "label": c.get("label") or c.get("name") or c["id"],
                           "is_default": bool(c.get("is_default"))})
        ra.sort(key=lambda x: not x.get("is_default"))
        return ra
    except Exception:
        return None


def so_ket_noi() -> int:
    return len(_ds_ket_noi() or [])


async def _token_ket_noi(cid: str) -> str:
    if _TOKEN_KN is not None:
        return str(await _TOKEN_KN(cid) or "")
    try:
        import oauth_mcp
        hdr = await oauth_mcp.auth_headers(cid)
    except Exception:
        return ""
    return (hdr.get("Authorization", "") or "").replace("Bearer ", "").strip()


async def _tho(row: dict) -> str:
    if row.get("loai") == "ket_noi":
        return await _token_ket_noi(row.get("ket_noi_id") or "")
    return fp._token_tho(row["id"])


def nguon_token() -> list:
    """Đồng bộ hàng kết nối OAuth vào fp_token rồi trả mọi nguồn (không có chuỗi token)."""
    kn = _ds_ket_noi()
    if kn is not None:
        for c in kn:
            fp.dam_bao_ket_noi(c["id"], c.get("label") or "")
        fp.bo_ket_noi_vang([c["id"] for c in kn])
    return fp.ds_token_noi_bo()


def _danh_dau_token_loi(tid: int, e: dict) -> None:
    msg = str((e or {}).get("message") or "")
    het = _ma(e) == 190 and ((e or {}).get("error_subcode") == 463 or "expired" in msg.lower())
    fp.cap_nhat_token(tid, trang_thai="het_han" if het else "loi", loi=chu_loi(e), kiem_luc=time.time())
    for k in [k for k in _CACHE if k[1] == tid]:
        _CACHE.pop(k, None)


async def _dong_bo_mot(row: dict, tok: str) -> dict:
    """Đồng bộ Trang của một nguồn token. Trả {so, moi} hoặc {loi}."""
    tid = int(row["id"])
    trang_ids, moi = [], 0
    la_trang = row.get("loai") == "trang"
    if not la_trang:
        d = await _get("me/accounts", {"fields": TRUONG_TRANG, "limit": 100}, tok)
        e = _loi(d)
        if e and row.get("loai") == "nguoi_dung" and _ma(e) == 100 and "page" in str(e.get("message", "")).lower():
            la_trang = True               # dán nhầm page token vào ô user token: tự nhận ra
        elif e:
            _danh_dau_token_loi(tid, e)
            return {"loi": chu_loi(e)}
        else:
            trang = list(d.get("data") or [])
            tiep = (d.get("paging") or {}).get("next")
            for _ in range(20):
                if not tiep:
                    break
                d2 = await _goi("GET", tiep)
                if _loi(d2):
                    break
                trang += list(d2.get("data") or [])
                tiep = (d2.get("paging") or {}).get("next")
            for p in trang:
                if fp.ghi_trang(p, tid):
                    moi += 1
                trang_ids.append(str(p.get("id")))
                if p.get("access_token"):
                    _CACHE[(str(p.get("id")), tid)] = (p["access_token"], time.time() + TTL_TOKEN_TRANG)
    if la_trang:
        d = await _get("me", {"fields": TRUONG_TRANG_TOKEN}, tok)
        e = _loi(d)
        if e:
            _danh_dau_token_loi(tid, e)
            return {"loi": chu_loi(e)}
        if row.get("loai") != "trang":
            fp.cap_nhat_token(tid, loai="trang")
        if fp.ghi_trang(d, tid):
            moi += 1
        trang_ids.append(str(d.get("id")))
    fp.bo_nguon_trang(tid, trang_ids)
    fp.cap_nhat_token(tid, trang_thai="tot", loi="", so_trang=len(trang_ids), kiem_luc=time.time())
    return {"so": len(trang_ids), "moi": moi}


async def dong_bo_trang() -> dict:
    so, moi, loi = 0, 0, []
    for r in nguon_token():
        tok = await _tho(r)
        if not tok:
            fp.cap_nhat_token(r["id"], trang_thai="loi", loi="kết nối chưa đăng nhập hoặc không lấy được token",
                              kiem_luc=time.time())
            loi.append({"token": r["nhan"], "loi": "không lấy được token"})
            continue
        kq = await _dong_bo_mot(r, tok)
        if kq.get("loi"):
            loi.append({"token": r["nhan"], "loi": kq["loi"]})
            continue
        so += kq["so"]
        moi += kq["moi"]
    if so or moi:
        fp.ghi_nk("dong_bo", "", None, "thanh_cong", f"đồng bộ {so} lượt Trang, {moi} Trang mới")
    return {"so": so, "moi": moi, "loi": loi}


async def kiem_token(tid) -> dict:
    i = fp.tim_token_id(tid)
    if i is None:
        raise ValueError("không có token này")
    if str(tid).startswith("kn:") or (fp.hang_token(i) or {}).get("loai") == "ket_noi":
        nguon_token()
    row = fp.hang_token(i)
    tok = await _tho(row)
    if not tok:
        fp.cap_nhat_token(i, trang_thai="loi", loi="kết nối chưa đăng nhập hoặc không lấy được token",
                          kiem_luc=time.time())
        return fp.lay_token(i)
    d = await _get("me", {"fields": "id,name"}, tok)
    e = _loi(d)
    if e:
        _danh_dau_token_loi(i, e)
        return fp.lay_token(i)
    kw = {"trang_thai": "tot", "loi": "", "kiem_luc": time.time()}
    app = ""
    if os.environ.get("FB_APP_ID") and os.environ.get("FB_APP_SECRET"):
        app = f"{os.environ['FB_APP_ID']}|{os.environ['FB_APP_SECRET']}"
    dbg = await _get("debug_token", {"input_token": tok}, app or tok)
    dd = (dbg or {}).get("data") if not _loi(dbg) else None
    if isinstance(dd, dict):
        if dd.get("expires_at"):
            kw["het_han"] = float(dd["expires_at"])
        if row.get("loai") != "ket_noi" and dd.get("type") in ("PAGE", "USER"):
            kw["loai"] = "trang" if dd["type"] == "PAGE" else "nguoi_dung"
    fp.cap_nhat_token(i, **kw)
    return fp.lay_token(i)


async def token_trang(trang_id: str) -> list:
    """[(token_id, page_token)] cho Trang, token tốt trước."""
    t = fp.hang_trang(trang_id)
    if not t:
        return []
    hang = {r["id"]: r for r in fp.ds_token_noi_bo()}
    ids = sorted([i for i in t["nguon"] if i in hang], key=lambda i: hang[i]["trang_thai"] != "tot")
    ra = []
    for i in ids:
        r = hang[i]
        if r["loai"] == "trang":
            tok = fp._token_tho(i)
            if tok:
                ra.append((i, tok))
            continue
        c = _CACHE.get((str(trang_id), i))
        if c and c[1] > time.time():
            ra.append((i, c[0]))
            continue
        utok = await _tho(r)
        if not utok:
            continue
        d = await _get(str(trang_id), {"fields": "access_token"}, utok)
        e = _loi(d)
        if e:
            if _ma(e) == 190:
                _danh_dau_token_loi(i, e)
            continue
        if d.get("access_token"):
            _CACHE[(str(trang_id), i)] = (d["access_token"], time.time() + TTL_TOKEN_TRANG)
            ra.append((i, d["access_token"]))
    return ra


async def _voi_token(trang_id: str, ham) -> tuple:
    """Chạy `ham(page_token)` với lần lượt từng token của Trang (pool). Token chết (#190) thì đánh
    dấu lỗi và thử token kế; lỗi quyền thì thử token kế (admin khác có thể đủ quyền)."""
    ds_tok = await token_trang(trang_id)
    if not ds_tok:
        return {"error": {"message": "Trang chưa có token nào dùng được (bấm Đồng bộ Trang hoặc nối lại kết nối)",
                          "code": 190}}, None
    cuoi = None
    for tid, tok in ds_tok:
        kq = await ham(tok)
        e = _loi(kq)
        if e and phan_loai(e, kq) == "quyen":
            if _ma(e) == 190:
                _danh_dau_token_loi(tid, e)
            cuoi = kq
            continue
        return kq, tid
    return cuoi, None


# ------------------------------------------------------------------ đăng bài

def _tep(t: str) -> Path:
    p = fp.duong_media(t)
    if not p:
        raise FileNotFoundError(t)
    return p


def _url_bai(post_id: str, loai: str) -> str:
    if not post_id:
        return ""
    if loai == "reel":
        return f"https://www.facebook.com/reel/{post_id}"
    return f"https://www.facebook.com/{post_id}"


async def _rupload(upload_url: str, video_id: str, tok: str, p: Path) -> dict:
    url = upload_url or f"{RUPLOAD}/{video_id}"
    return await _goi("POST", url, headers={"Authorization": f"OAuth {tok}", "offset": "0",
                                            "file_size": str(p.stat().st_size)}, content=p)


async def _dang_story(page: str, tep: str, tok: str) -> dict:
    p = _tep(tep)
    if fp.loai_media(tep) == "anh":
        d = await _post(f"{page}/photos", {"published": "false"}, tok, files={"source": (p.name, p)})
        if _loi(d):
            return d
        return await _post(f"{page}/photo_stories", {"photo_id": d.get("id")}, tok)
    d = await _post(f"{page}/video_stories", {"upload_phase": "start"}, tok)
    if _loi(d):
        return d
    vid = str(d.get("video_id") or "")
    u = await _rupload(d.get("upload_url") or "", vid, tok, p)
    if _loi(u):
        return u
    kq = await _post(f"{page}/video_stories", {"upload_phase": "finish", "video_id": vid}, tok)
    if not _loi(kq) and not kq.get("post_id"):
        kq["post_id"] = vid
    return kq


async def _dang_chinh(b: dict, page: str, tok: str, hen_fb: bool) -> dict:
    loai = b["loai"]
    hen = {"published": "false", "scheduled_publish_time": str(int(b["hen_luc"]))} if hen_fb else {}
    try:
        if loai == "chu":
            data = {"message": b["noi_dung"], **hen}
            if b.get("link"):
                data["link"] = b["link"]
            return await _post(f"{page}/feed", data, tok)
        if loai == "anh":
            p = _tep(b["media"][0])
            return await _post(f"{page}/photos", {"message": b["noi_dung"], **hen}, tok, files={"source": (p.name, p)})
        if loai == "album":
            ids = []
            for t in b["media"]:
                p = _tep(t)
                d = await _post(f"{page}/photos", {"published": "false"}, tok, files={"source": (p.name, p)})
                if _loi(d):
                    return d
                ids.append(str(d.get("id")))
            data = {"message": b["noi_dung"]}
            for i, x in enumerate(ids):
                data[f"attached_media[{i}]"] = json.dumps({"media_fbid": x})
            return await _post(f"{page}/feed", data, tok)
        if loai == "video":
            p = _tep(b["media"][0])
            return await _post(f"{page}/videos", {"description": b["noi_dung"], **hen}, tok,
                               files={"source": (p.name, p)}, goc=GRAPH_VIDEO)
        if loai == "reel":
            p = _tep(b["media"][0])
            d = await _post(f"{page}/video_reels", {"upload_phase": "start"}, tok)
            if _loi(d):
                return d
            vid = str(d.get("video_id") or "")
            if not vid:
                return {"error": {"message": "Meta không trả video_id khi bắt đầu Reels", "code": "khac"}}
            u = await _rupload(d.get("upload_url") or "", vid, tok, p)
            if _loi(u):
                return u
            kq = await _post(f"{page}/video_reels", {"upload_phase": "finish", "video_id": vid,
                                                      "video_state": "PUBLISHED", "description": b["noi_dung"]}, tok)
            if not _loi(kq):
                kq.setdefault("post_id", vid)
            return kq
        if loai == "story":
            return await _dang_story(page, b["media"][0], tok)
    except FileNotFoundError as ex:
        return {"error": {"message": f"không thấy tệp media '{ex}' (tệp đã bị xoá?)", "code": "tep"}}
    return {"error": {"message": f"loại bài lạ: {loai}", "code": "khac"}}


async def dang_bai(bid, now: Optional[float] = None) -> dict:
    """Đăng một bài đã được giành (`dang_dang`). Trả bài sau khi ghi kết quả."""
    import doi_social_v2 as v2
    now = time.time() if now is None else now
    b = fp.lay_bai(bid)
    if not b:
        raise ValueError(f"không có bài #{bid}")
    t = fp.hang_trang(b["trang_id"])
    if not t:
        return fp.ket_qua_dang(bid, ok=False, loi="Trang không còn trong danh sách", now=now)
    hen_fb = b["cach_hen"] == "fb" and bool(b["hen_luc"]) and b["hen_luc"] > now + 600
    kq, tid = await _voi_token(t["id"], lambda tok: _dang_chinh(b, t["id"], tok, hen_fb))
    e = _loi(kq)
    if e:
        loai_loi = phan_loai(e, kq)
        chu = chu_loi(e)
        if loai_loi == "tam" and (b["so_lan_thu"] or 0) < THU_TOI_DA:
            return fp.ket_qua_dang(bid, ok=False, loi=chu, thu_lai_sau=THU_LAI_SAU, now=now)
        r = fp.ket_qua_dang(bid, ok=False, loi=chu, now=now)
        if loai_loi == "quyen":
            fp.dat_loi_trang(t["id"], chu)
            v2.bao("Fanpage: lỗi quyền khi đăng", f"Trang '{t['ten']}' không đăng được bài #{bid}: {chu}\n"
                   + fp.CACH_SUA_LOI.get(fp._ma_loi(chu), ""))
        return r
    post_id = str(kq.get("post_id") or kq.get("id") or "")
    r = fp.ket_qua_dang(bid, ok=True, post_id=post_id, url=_url_bai(post_id, b["loai"]), hen_fb=hen_fb, now=now)
    if tid is not None:
        fp.tang_bai_dang(tid)
    if t.get("loi"):
        fp.dat_loi_trang(t["id"], "")
    if fp.cai_dat()["bao_moi_bai"]:
        v2.bao("Fanpage: " + ("đã hẹn bài" if hen_fb else "đã đăng bài"),
               f"Trang '{t['ten']}': {(b['noi_dung'] or b['loai'])[:200]}\n{r.get('url') or ''}")
    return r


async def _dang_ig(b: dict, t: dict, now: float) -> None:
    ig = t.get("ig_id") or ""
    if not ig:
        fp.dat_phu(b["id"], ig_tt="loi", loi="Trang chưa nối tài khoản Instagram doanh nghiệp")
        return

    async def lam(tok):
        if b["ig_tt"] == "xu_ly" and b["ig_media_id"]:
            cid = b["ig_media_id"]
        else:
            if fp.ig_24h(t["id"], now) >= fp.cai_dat()["ig_toi_da_24h"]:
                return {"_cho": True}
            if b["loai"] == "chu" or not b["media"]:
                return {"error": {"message": "Instagram không nhận bài chỉ có chữ", "code": "khac"}}
            if not fp.goc_cong_khai():
                return {"error": {"message": "chưa biết địa chỉ công khai của MinMin (mở MinMin một lần bằng tên "
                                             "miền https để Instagram tải được tệp)", "code": "khac"}}
            try:
                urls = [fp.url_cong_khai(x) for x in b["media"]]
            except ValueError as ex:
                return {"error": {"message": str(ex), "code": "tep"}}
            cap = b["noi_dung"] or ""
            if b["loai"] == "album":
                con = []
                for u in urls[:10]:
                    d = await _post(f"{ig}/media", {"image_url": u, "is_carousel_item": "true"}, tok)
                    if _loi(d):
                        return d
                    con.append(str(d.get("id")))
                d = await _post(f"{ig}/media", {"media_type": "CAROUSEL", "children": ",".join(con), "caption": cap},
                                tok)
            else:
                video = fp.loai_media(b["media"][0]) == "video"
                data = {"video_url": urls[0]} if video else {"image_url": urls[0]}
                if b["loai"] == "story":
                    data["media_type"] = "STORIES"
                elif video:
                    data["media_type"] = "REELS"
                if b["loai"] != "story":
                    data["caption"] = cap
                d = await _post(f"{ig}/media", data, tok)
            if _loi(d):
                return d
            cid = str(d.get("id") or "")
            fp.dat_phu(b["id"], ig_tt="xu_ly", ig_media_id=cid)
        st = await _get(cid, {"fields": "status_code"}, tok)
        if _loi(st):
            return st
        sc = str(st.get("status_code") or "")
        if sc in ("ERROR", "EXPIRED"):
            return {"error": {"message": f"Instagram xử lý tệp lỗi ({sc})", "code": "khac"}}
        if sc != "FINISHED":
            return {"_cho": True}
        return await _post(f"{ig}/media_publish", {"creation_id": cid}, tok)

    kq, _ = await _voi_token(t["id"], lam)
    if kq and kq.get("_cho"):
        return
    e = _loi(kq)
    if e:
        if phan_loai(e, kq) == "tam":
            return
        fp.dat_phu(b["id"], ig_tt="loi", loi="Instagram: " + chu_loi(e))
        fp.ghi_nk("instagram", t["id"], b["id"], "loi", chu_loi(e))
        return
    fp.dat_phu(b["id"], ig_tt="xong", ig_media_id=str(kq.get("id") or ""))
    fp.ghi_nk("instagram", t["id"], b["id"], "thanh_cong", "đã đăng lên Instagram")


async def xu_ly_phu(b: dict, now: Optional[float] = None) -> None:
    """Story kèm, Instagram, bình luận sau đăng (đợi 60 giây sau khi bài lên)."""
    now = time.time() if now is None else now
    t = fp.hang_trang(b["trang_id"])
    if not t:
        return
    if b["story_tt"] == "cho":
        if not b["media"]:
            fp.dat_phu(b["id"], story_tt="loi", loi="story cần ảnh hoặc video")
        else:
            kq, _ = await _voi_token(t["id"], lambda tok: _dang_story_an_toan(t["id"], b["media"][0], tok))
            e = _loi(kq)
            if not e:
                fp.dat_phu(b["id"], story_tt="xong")
            elif phan_loai(e, kq) != "tam":
                fp.dat_phu(b["id"], story_tt="loi", loi="Story: " + chu_loi(e))
    if b["ig_tt"] in ("cho", "xu_ly"):
        await _dang_ig(fp.lay_bai(b["id"]), t, now)
    if b["bl_tt"] == "cho" and b["post_id"] and (b["dang_luc"] or now) <= now - 60:
        kq, _ = await _voi_token(t["id"], lambda tok: _post(f"{b['post_id']}/comments", {"message": b["binh_luan"]}, tok))
        e = _loi(kq)
        if not e:
            fp.dat_phu(b["id"], bl_tt="xong")
            fp.ghi_nk("binh_luan_sau_dang", t["id"], b["id"], "thanh_cong", "đã bình luận dưới bài")
        elif phan_loai(e, kq) != "tam":
            fp.dat_phu(b["id"], bl_tt="loi", loi="Bình luận sau đăng: " + chu_loi(e))


async def _dang_story_an_toan(page, tep, tok) -> dict:
    try:
        return await _dang_story(page, tep, tok)
    except FileNotFoundError as ex:
        return {"error": {"message": f"không thấy tệp media '{ex}'", "code": "tep"}}


async def kiem_tra_bai(bid, now: Optional[float] = None) -> dict:
    """Kiểm thử không đăng: Trang, token, quyền, tệp, giờ, IG."""
    now = time.time() if now is None else now
    b = fp.lay_bai(bid)
    if not b:
        raise ValueError(f"không có bài #{bid}")
    buoc = []
    t = fp.hang_trang(b["trang_id"])
    buoc.append({"ten": "Trang", "ok": bool(t and t["bat"]),
                 "chi_tiet": (t["ten"] + ("" if t["bat"] else " (đang tắt)")) if t else "Trang không còn"})
    if t:
        ds_tok = await token_trang(t["id"])
        ok_tok, chi = False, "chưa có token nào dùng được"
        if ds_tok:
            d = await _get(t["id"], {"fields": "id,name"}, ds_tok[0][1])
            e = _loi(d)
            ok_tok, chi = (not e), (f"{len(ds_tok)} token, gọi thử được" if not e else chu_loi(e))
        buoc.append({"ten": "Token", "ok": ok_tok, "chi_tiet": chi})
        q = t["quyen"]
        co = (not q) or any(x in q for x in fp.QUYEN_DANG)
        buoc.append({"ten": "Quyền", "ok": co, "chi_tiet": ",".join(q) if q else "chưa rõ (token Trang)"})
    try:
        fp._kiem_media_loai(b["loai"], b["media"])
        buoc.append({"ten": "Tệp", "ok": True, "chi_tiet": f"{len(b['media'])} tệp" if b["media"] else "không có tệp"})
    except ValueError as ex:
        buoc.append({"ten": "Tệp", "ok": False, "chi_tiet": str(ex)})
    if b["trang_thai"] not in ("cho_duyet", "cho_dang", "loi"):
        buoc.append({"ten": "Giờ", "ok": True, "chi_tiet": f"bài đang '{b['trang_thai']}'"})
    elif not b["hen_luc"]:
        buoc.append({"ten": "Giờ", "ok": True, "chi_tiet": "chưa hẹn giờ (đăng tay bằng Đăng ngay)"})
    elif b["cach_hen"] == "fb" and not (now + 600 < b["hen_luc"] < now + fp.FB_HEN_DEN + 86400):
        buoc.append({"ten": "Giờ", "ok": False, "chi_tiet": "giờ hẹn ngoài khoảng Facebook nhận (10 phút - 30 ngày)"})
    else:
        buoc.append({"ten": "Giờ", "ok": True, "chi_tiet": "hẹn kiểu " + b["cach_hen"]})
    if b["ig"]:
        ok_ig = bool(t and t.get("ig_id")) and bool(fp.goc_cong_khai()) and b["loai"] != "chu"
        buoc.append({"ten": "Instagram", "ok": ok_ig,
                     "chi_tiet": "sẵn sàng" if ok_ig else "cần tài khoản IG gắn Trang, bài có media và địa chỉ "
                                                          "công khai https của MinMin"})
    return {"ok": all(x["ok"] for x in buoc), "buoc": buoc}


# ------------------------------------------------------------------ bình luận

TRUONG_FEED = ("id,created_time,comments.limit(50).order(reverse_chronological)"
               "{id,from,message,created_time,parent{id},is_hidden}")


async def quet_binh_luan(trang_id: str, ap_dung: bool = True) -> int:
    t = fp.hang_trang(trang_id)
    if not t:
        raise ValueError(f"không có Trang {trang_id}")
    kq, _ = await _voi_token(t["id"], lambda tok: _get(f"{t['id']}/feed", {"fields": TRUONG_FEED, "limit": 15}, tok))
    e = _loi(kq)
    if e:
        fp.ghi_nk("quet_binh_luan", t["id"], None, "loi", chu_loi(e))
        raise ValueError("quét bình luận lỗi: " + chu_loi(e))
    moi = []
    for bai in kq.get("data") or []:
        for c in ((bai.get("comments") or {}).get("data") or []):
            if fp.ghi_binh_luan(t["id"], bai.get("id") or "", c):
                moi.append(str(c.get("id")))
    if ap_dung and not fp.dung_tu_dong():
        for cid in moi:
            r = fp.ap_quy_tac(cid)
            if r and r["hanh_dong"] == "tra_loi_ai":
                try:
                    await soan_ai(cid, tu_gui=r["tu_gui"])
                except ValueError as ex:
                    fp.dat_binh_luan(cid, loi=str(ex))
    fp.ghi_quet_luc()
    return len(moi)


async def soan_ai(cid: str, tu_gui: bool = False) -> str:
    bl = fp.lay_binh_luan(cid)
    if not bl:
        raise ValueError("không có bình luận này")
    if not _AI:
        raise ValueError("chưa nối bộ não AI của MinMin")
    t = fp.hang_trang(bl["trang_id"]) or {}
    chu = str(await _AI(bl, t) or "").strip()
    if not chu:
        raise ValueError("AI không trả câu trả lời")
    fp.dat_binh_luan(cid, tra_loi=chu[:2000], trang_thai="cho_gui" if tu_gui else "cho_duyet", loi="")
    return chu


async def an_binh_luan(cid: str, an: bool = True) -> dict:
    bl = fp.lay_binh_luan(cid)
    if not bl:
        raise ValueError("không có bình luận này")
    kq, _ = await _voi_token(bl["trang_id"], lambda tok: _post(str(cid), {"is_hidden": "true" if an else "false"}, tok))
    e = _loi(kq)
    if e:
        fp.dat_binh_luan(cid, loi=chu_loi(e))
        raise ValueError(("ẩn" if an else "hiện") + " bình luận lỗi: " + chu_loi(e))
    tt = bl["trang_thai"]
    if an and tt not in ("da_tra_loi",):
        tt = "da_an"
    elif not an and tt == "da_an":
        tt = "moi"
    fp.dat_binh_luan(cid, an=int(an), trang_thai=tt, loi="")
    fp.ghi_nk("an_binh_luan" if an else "hien_binh_luan", bl["trang_id"], None, "thanh_cong", str(cid))
    return fp.lay_binh_luan(cid)


async def tra_loi_binh_luan(cid: str, chu: str) -> dict:
    bl = fp.lay_binh_luan(cid)
    if not bl:
        raise ValueError("không có bình luận này")
    chu = str(chu or "").strip()
    if not chu:
        raise ValueError("câu trả lời trống")
    fp.dat_binh_luan(cid, trang_thai="dang_gui", tra_loi=chu)
    kq, _ = await _voi_token(bl["trang_id"], lambda tok: _post(f"{cid}/comments", {"message": chu}, tok))
    e = _loi(kq)
    if e:
        fp.dat_binh_luan(cid, trang_thai="loi", loi=chu_loi(e))
        raise ValueError("gửi trả lời lỗi: " + chu_loi(e))
    fp.dat_binh_luan(cid, trang_thai="da_tra_loi", loi="")
    fp.ghi_nk("tra_loi", bl["trang_id"], None, "thanh_cong", chu[:200])
    return fp.lay_binh_luan(cid)


async def gui_binh_luan(cid: str) -> dict:
    """Thực hiện đề xuất đang chờ: ẩn (nếu có) rồi gửi câu trả lời (nếu có)."""
    bl = fp.lay_binh_luan(cid)
    if not bl:
        raise ValueError("không có bình luận này")
    if bl["de_xuat"] in ("an", "an_va_tra_loi") and not bl["an"]:
        await an_binh_luan(cid, True)
    if bl["tra_loi"]:
        return await tra_loi_binh_luan(cid, bl["tra_loi"])
    if bl["de_xuat"] not in ("an", "an_va_tra_loi"):
        raise ValueError("bình luận chưa có câu trả lời để gửi")
    return fp.lay_binh_luan(cid)


# ------------------------------------------------------------------ insights

def _gia_tri_cuoi(m: dict):
    v = m.get("values") or []
    if not v:
        return None
    x = v[-1].get("value")
    return x if isinstance(x, (int, float)) else None


async def cap_nhat_so_lieu(trang_id: str = "", now: Optional[float] = None) -> dict:
    now = time.time() if now is None else now
    ngay = fp._ngay_str(now)
    ids = [trang_id] if trang_id else fp.ids_trang()
    so_trang, so_bai = 0, 0
    for tid in ids:
        ds_tok = await token_trang(tid)
        if not ds_tok:
            continue
        tok = ds_tok[0][1]
        kw = {}
        d = await _get(tid, {"fields": "followers_count,fan_count"}, tok)
        if not _loi(d):
            kw["nguoi_theo_doi"] = d.get("followers_count", d.get("fan_count"))
        metric = {"page_impressions_unique": "tiep_can", "page_post_engagements": "tuong_tac",
                  "page_views_total": "luot_xem"}
        d = await _get(f"{tid}/insights", {"metric": ",".join(metric), "period": "day"}, tok)
        ds_m = [] if _loi(d) else (d.get("data") or [])
        if _loi(d):
            for m in metric:
                d1 = await _get(f"{tid}/insights", {"metric": m, "period": "day"}, tok)
                if not _loi(d1):
                    ds_m += d1.get("data") or []
        for m in ds_m:
            if m.get("name") in metric and _gia_tri_cuoi(m) is not None:
                kw[metric[m["name"]]] = _gia_tri_cuoi(m)
        if kw:
            fp.ghi_so_lieu_trang(tid, ngay, **kw)
            so_trang += 1
    for b in fp.bai_can_so_lieu(now):
        if trang_id and b["trang_id"] != trang_id:
            continue
        ds_tok = await token_trang(b["trang_id"])
        if not ds_tok:
            continue
        tok = ds_tok[0][1]
        sl = {}
        d = await _get(b["post_id"], {"fields": "reactions.summary(true),comments.summary(true),shares"}, tok)
        if not _loi(d):
            sl["cam_xuc"] = int(((d.get("reactions") or {}).get("summary") or {}).get("total_count") or 0)
            sl["binh_luan"] = int(((d.get("comments") or {}).get("summary") or {}).get("total_count") or 0)
            sl["chia_se"] = int((d.get("shares") or {}).get("count") or 0)
        d = await _get(f"{b['post_id']}/insights", {"metric": "post_impressions_unique,post_clicks"}, tok)
        if not _loi(d):
            for m in d.get("data") or []:
                v = _gia_tri_cuoi(m)
                if v is None:
                    continue
                if m.get("name") == "post_impressions_unique":
                    sl["tiep_can"] = v
                elif m.get("name") == "post_clicks":
                    sl["click"] = v
        if sl:
            fp.ghi_so_lieu_bai(b["id"], sl)
            so_bai += 1
    return {"trang": so_trang, "bai": so_bai}


# ------------------------------------------------------------------ đổi info Trang

async def doi_info(trang_id: str, hanh_dong: str, d: dict, rnd=None) -> None:
    t = fp.hang_trang(trang_id)
    if not t:
        raise ValueError(f"không có Trang {trang_id}")
    if hanh_dong == "doi_tieu_su":
        chu = str(d.get("chu") or "")
        if d.get("kho_id"):
            chu = fp.chon_tu_kho(d["kho_id"], "", rnd) or ""
        chu = fp.spin(chu, rnd, {"ten_trang": t["ten"]}).strip()
        if not chu:
            raise ValueError("tiểu sử trống (nhập chữ hoặc chọn kho tiểu sử có mục)")
        ham = lambda tok: _post(t["id"], {"about": chu[:255]}, tok)       # noqa: E731
    elif hanh_dong in ("doi_anh", "doi_bia"):
        p = fp.duong_media(str(d.get("tep") or ""))
        if not p or fp.loai_media(p.name) != "anh":
            raise ValueError("chọn một tệp ảnh đã tải lên")
        if hanh_dong == "doi_anh":
            ham = lambda tok: _post(f"{t['id']}/picture", {}, tok, files={"source": (p.name, p)})   # noqa: E731
        else:
            async def ham(tok):
                x = await _post(f"{t['id']}/photos", {"published": "false"}, tok, files={"source": (p.name, p)})
                if _loi(x):
                    return x
                return await _post(t["id"], {"cover": str(x.get("id"))}, tok)
    else:
        raise ValueError(f"hành động lạ: {hanh_dong}")
    kq, _ = await _voi_token(t["id"], ham)
    e = _loi(kq)
    if e:
        fp.ghi_nk(hanh_dong, t["id"], None, "loi", chu_loi(e))
        raise ValueError(chu_loi(e))
    fp.ghi_nk(hanh_dong, t["id"], None, "thanh_cong", {"doi_tieu_su": "đã đổi tiểu sử", "doi_anh": "đã đổi ảnh đại diện",
                                                       "doi_bia": "đã đổi ảnh bìa"}[hanh_dong])


async def hanh_dong_trang(ids, hanh_dong: str, d: dict) -> dict:
    if hanh_dong in ("doi_tieu_su", "doi_anh", "doi_bia"):
        ids = [str(x) for x in (ids or [])][:500]
        if not ids:
            raise ValueError("chưa chọn Trang nào")
        so, loi = 0, []
        for tid in ids:
            try:
                await doi_info(tid, hanh_dong, d)
                so += 1
            except ValueError as e:
                loi.append({"id": tid, "loi": str(e)})
        return {"so": so, "loi": loi}
    return fp.hanh_dong_trang(ids, hanh_dong, d)


# ------------------------------------------------------------------ kênh nguồn (yt-dlp)

def co_yt_dlp() -> bool:
    if _YTDLP:
        return True
    import importlib.util
    try:
        return importlib.util.find_spec("yt_dlp") is not None
    except Exception:
        return False


def _liet_ke_that(link: str, n: int) -> list:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "playlistend": int(n),
            "socket_timeout": 30}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(link, download=False) or {}
    ra = []
    for e in (info.get("entries") or [])[:n]:
        if not isinstance(e, dict) or not e.get("id"):
            continue
        u = e.get("url") or e.get("webpage_url") or ""
        if u and not u.startswith("http"):
            u = e.get("webpage_url") or ""
        ra.append({"ma": str(e["id"]), "tieu_de": str(e.get("title") or ""), "url": u})
    return ra


def _tai_that(url: str, thu_muc: Path, ma: str) -> Path:
    import yt_dlp
    thu_muc.mkdir(parents=True, exist_ok=True)
    opts = {"outtmpl": str(thu_muc / f"{ma}.%(ext)s"), "quiet": True, "no_warnings": True, "noplaylist": True,
            "format": "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "merge_output_format": "mp4",
            "socket_timeout": 30, "retries": 3, "max_filesize": fp.VIDEO_TOI_DA}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        p = Path(ydl.prepare_filename(info))
    if not p.exists():
        cands = sorted(thu_muc.glob(f"{ma}.*"), key=lambda x: x.stat().st_size, reverse=True)
        if not cands:
            raise RuntimeError("tải xong nhưng không thấy tệp video")
        p = cands[0]
    if p.suffix.lower() != ".mp4" and fp.loai_media(p.name) != "video":
        raise RuntimeError(f"tệp tải về không phải video ({p.suffix})")
    return p


async def quet_kenh(kid, now: Optional[float] = None) -> dict:
    now = time.time() if now is None else now
    k = fp.lay_kenh(kid)
    if not k:
        raise ValueError(f"không có kênh #{kid}")
    if not co_yt_dlp():
        fp.dat_kenh(kid, trang_thai="loi", loi="máy chủ thiếu yt-dlp", lan_quet=now)
        return {"so": 0, "loi": "máy chủ thiếu yt-dlp"}
    liet_ke, tai = _YTDLP if _YTDLP else (_liet_ke_that, _tai_that)
    trang_ids = fp.trang_cua_kenh(k)
    if not trang_ids:
        fp.dat_kenh(kid, trang_thai="loi", loi="kênh chưa có Trang nhận video", lan_quet=now)
        return {"so": 0, "loi": "kênh chưa có Trang nhận video"}
    fp.dat_kenh(kid, trang_thai="dang_quet")
    try:
        ds_v = await asyncio.to_thread(liet_ke, k["link"], max(30, k["toi_da_moi_lan"] * 3))
    except Exception as ex:
        loi = f"không đọc được kênh ({str(ex).splitlines()[0][:200] if str(ex) else type(ex).__name__})"
        fp.dat_kenh(kid, trang_thai="loi", loi=loi, lan_quet=now)
        return {"so": 0, "loi": loi}
    co = fp.video_da_co(kid)
    moi = [v for v in ds_v if v.get("ma") and str(v["ma"]) not in co][:k["toi_da_moi_lan"]]
    hl = fp.hieu_luc(trang_ids[0])
    kho_nd = hl.get("kho_noi_dung")
    so_bai, loi_v = 0, []
    dem_truoc = k["so_video"] or 0
    for i, v in enumerate(moi):
        ma = re.sub(r"[^A-Za-z0-9_-]", "", str(v["ma"]))[:80] or f"v{i}"
        tieu = str(v.get("tieu_de") or "")
        try:
            p = await asyncio.to_thread(tai, v.get("url") or k["link"], fp.thu_muc() / "kenh" / str(int(kid)), ma)
        except Exception as ex:
            fp.ghi_video_kenh(kid, str(v["ma"]), tieu, "", "loi")
            loi_v.append(f"{ma}: {str(ex)[:120]}")
            continue
        ref = f"kenh/{int(kid)}/{Path(p).name}"
        if not fp.duong_media(ref) or fp.loai_media(Path(p).name) != "video":
            fp.ghi_video_kenh(kid, str(v["ma"]), tieu, "", "loi")
            loi_v.append(f"{ma}: tệp không phải video")
            continue
        fp.ghi_video_kenh(kid, str(v["ma"]), tieu, ref)
        an_toan = tieu.replace("{", "{{").replace("}", "}}")
        nd = an_toan
        if kho_nd:
            mau = fp.chon_tu_kho(kho_nd, Path(p).name)
            if mau:
                nd = mau.replace("{ten_tep}", an_toan)
        chon = trang_ids if k["chia"] == "tat_ca" else [trang_ids[(dem_truoc + i) % len(trang_ids)]]
        try:
            kq = fp.tao_bai(trang_ids=chon, loai=k["loai_bai"], noi_dung=[nd], media=[ref], chia="tat_ca",
                            nguon="kenh", hen="tu_dong", now=now)
            so_bai += kq["so"]
        except ValueError as ex:
            loi_v.append(f"{ma}: {ex}")
    fp.dat_kenh(kid, trang_thai="loi" if loi_v and not so_bai else "tot",
                loi="; ".join(loi_v)[:500], lan_quet=now)
    fp.ghi_nk("quet_kenh", "", None, "thanh_cong" if so_bai else ("loi" if loi_v else "thong_tin"),
              f"kênh #{kid}: {len(moi)} video mới, tạo {so_bai} bài" + (f", lỗi {len(loi_v)}" if loi_v else ""))
    return {"so": so_bai, "video": len(moi), "loi": loi_v}


# ------------------------------------------------------------------ vòng nền

def _toi(k: str, now: float) -> bool:
    if now - _MOC.get(k, 0) >= CONG[k]:
        _MOC[k] = now
        return True
    return False


def _ghi_loi(viec: str, ex: Exception) -> None:
    print(f"[doi-social/fanpage] {viec} lỗi: {type(ex).__name__}: {fp._loc_token(str(ex))[:300]}", file=sys.stderr)


async def nhip(deps=None, now: Optional[float] = None) -> dict:
    """Một nhịp vòng nền. Không chạy chồng (lượt trước chưa xong thì bỏ lượt này)."""
    if _DANG["chay"]:
        return {"bo_qua": True}
    _DANG["chay"] = True
    try:
        now = time.time() if now is None else now
        kq = {"dang": 0, "phu": 0, "gui": 0}
        cd = fp.cai_dat()
        dung = bool(cd["dung_tu_dong"])
        if not dung:
            for bid in fp.nhan_bai_toi_han(now, cd["luong"]):
                try:
                    await dang_bai(bid, now)
                    kq["dang"] += 1
                except Exception as ex:
                    _ghi_loi(f"đăng bài #{bid}", ex)
                    try:
                        fp.ket_qua_dang(bid, ok=False, loi=f"lỗi nội bộ: {type(ex).__name__}", now=now)
                    except Exception:
                        pass
            fp.chot_hen_fb(now)
            for b in fp.bai_cho_phu(now):
                try:
                    await xu_ly_phu(b, now)
                    kq["phu"] += 1
                except Exception as ex:
                    _ghi_loi(f"bước phụ bài #{b['id']}", ex)
            for bl in fp.binh_luan_cho_gui():
                try:
                    await gui_binh_luan(bl["id"])
                    kq["gui"] += 1
                except Exception as ex:
                    _ghi_loi(f"gửi bình luận {bl['id']}", ex)
        if _toi("binh_luan", now) and not dung:
            for tid in fp.ids_trang():
                hl = fp.hieu_luc(tid)
                if hl.get("tu_an") or hl.get("tu_tra_loi"):
                    try:
                        await quet_binh_luan(tid)
                    except Exception as ex:
                        _ghi_loi(f"quét bình luận {tid}", ex)
        if _toi("kiem_loi", now):
            try:
                fp.kiem_loi(so_ket_noi(), co_yt_dlp(), now)
            except Exception as ex:
                _ghi_loi("kiểm lỗi", ex)
        if _toi("kenh", now) and not dung:
            for k in fp.kenh_toi_han(now):
                try:
                    await quet_kenh(k["id"], now)
                except Exception as ex:
                    _ghi_loi(f"quét kênh #{k['id']}", ex)
        if _toi("so_lieu", now):
            try:
                await cap_nhat_so_lieu(now=now)
            except Exception as ex:
                _ghi_loi("insights", ex)
        if _toi("don_tep", now):
            try:
                fp.don_tep(int(cd["xoa_tep_sau_ngay"]), now)
            except Exception as ex:
                _ghi_loi("dọn tệp", ex)
        return kq
    finally:
        _DANG["chay"] = False
