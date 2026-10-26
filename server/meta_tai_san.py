"""meta_tai_san.py - Facebook nhiều tài khoản: ai cầm Trang / tài khoản quảng cáo nào, Facebook
giao cho MinMin những gì, cái gì chưa giao và vì sao (26.10.252).

Vì sao có file này. Chủ nối nhiều tài khoản Facebook qua app tự tạo (kết nối `facebook-pages` và
`meta-ads-graph`). Các plugin chỉ hỏi `me/accounts` và `me/adaccounts`, tức là chỉ thấy cái Facebook
đã GIAO cho token. Trang chủ cầm quyền cá nhân mà không tick lúc đăng nhập thì biến mất không một
lời báo, và chủ tưởng MinMin chỉ đọc theo BM. File này gom mọi nguồn có thể hỏi được:
  - `me/accounts`            Trang đã giao (kèm tasks = vai trò);
  - `me/businesses` -> owned/client pages, owned/client ad accounts: tài sản trong BM chủ thấy;
  - `me/adaccounts`          tài khoản quảng cáo đã giao (kèm business, user_tasks);
  - `me/permissions` + `debug_token`: quyền token, hạn token, tên app.
rồi so ra "có quyền nhưng chưa giao". Trang cá nhân CHƯA tick không lộ qua API nào: chỉ thấy khi
tài khoản khác hoặc BM thấy nó, hoặc chủ hỏi bằng ID/link (`hoi_trang`). Màn Soi quyền nói đúng thế.

Không bao giờ trả access token ra ngoài. Mọi chỗ gọi mạng đi qua `_http`, kết nối qua `_ket_noi`,
token qua `_token` - test chèn bản giả bằng `dat_*`.
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import Callable, Optional

GRAPH = "https://graph.facebook.com/v26.0"
CONNECTORS = ("facebook-pages", "meta-ads-graph")
DEM_GIAY = 120

QUYEN = [  # (mã, tên, cần để làm gì) - thứ tự hiện trên màn Soi quyền
    ("pages_show_list", "Danh sách Trang", "cần để thấy Trang"),
    ("pages_manage_posts", "Đăng bài Trang", "cần để đăng bài"),
    ("pages_read_engagement", "Đọc bài, bình luận", "cần để đọc bài và bình luận"),
    ("pages_manage_engagement", "Trả lời bình luận", "cần để trả lời bình luận"),
    ("ads_read", "Đọc quảng cáo", "cần để xem số liệu quảng cáo"),
    ("ads_management", "Quản lý quảng cáo", "cần để bật tắt camp"),
    ("business_management", "Tài sản Business", "cần để thấy Trang, tài khoản quảng cáo trong BM"),
]
_TEN_QUYEN = {m: t for m, t, _ in QUYEN}

_ket_noi_fn: Optional[Callable] = None
_token_fn: Optional[Callable] = None
_http_fn: Optional[Callable] = None
_DEM: dict = {}


def dat_ket_noi(fn) -> None:
    """fn() -> [{id, connector_id, label, is_default}] các kết nối ĐÃ đăng nhập."""
    global _ket_noi_fn
    _ket_noi_fn = fn


def dat_token(fn) -> None:
    """async fn(conn_id) -> user token | None."""
    global _token_fn
    _token_fn = fn


def dat_http(fn) -> None:
    """async fn(path_or_url, params, token) -> dict (JSON Graph, lỗi dạng {"error": {...}})."""
    global _http_fn
    _http_fn = fn


def xoa_dem() -> None:
    _DEM.clear()


# ---------------------------------------------------------------- nguồn thật
def _ket_noi() -> list:
    if _ket_noi_fn:
        return list(_ket_noi_fn() or [])
    try:
        import mcp_store
        import oauth_mcp
    except Exception:
        return []
    out = []
    for c in mcp_store.list_connections():
        if c.get("connector_id") in CONNECTORS and oauth_mcp.status(c["id"]).get("connected"):
            out.append({"id": c["id"], "connector_id": c.get("connector_id"),
                        "label": c.get("label") or c.get("name") or c["id"],
                        "is_default": bool(c.get("is_default"))})
    out.sort(key=lambda x: not x["is_default"])
    return out


async def _token(cid) -> Optional[str]:
    if _token_fn:
        return await _token_fn(cid)
    try:
        import oauth_mcp
        hdr = await oauth_mcp.auth_headers(cid)
    except Exception:
        return None
    return (hdr.get("Authorization", "") or "").replace("Bearer ", "").strip() or None


async def _http(path, params, token) -> dict:
    if _http_fn:
        return await _http_fn(path, params, token)
    import httpx
    url = path if str(path).startswith("http") else f"{GRAPH}/{str(path).lstrip('/')}"
    q = dict(params or {})
    if not str(path).startswith("http"):
        q["access_token"] = token
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(url, params=q)
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


_RE_TOKEN = re.compile(r"(access_token|input_token)=[^&\s'\"]+")


def sach(s) -> str:
    """Bỏ token khỏi câu lỗi (lỗi của httpx có thể kèm URL mang access_token)."""
    return _RE_TOKEN.sub(r"\1=***", str(s or ""))


def _loi(d) -> Optional[dict]:
    if isinstance(d, dict) and d.get("error"):
        e = d["error"]
        return e if isinstance(e, dict) else {"message": str(e)}
    return None


async def _het_trang(path, params, token, tran=20) -> tuple:
    """Lật hết trang một cạnh Graph. Trả (rows, lỗi|None)."""
    rows, d = [], await _http(path, params, token)
    e = _loi(d)
    if e:
        return [], e
    for _ in range(tran):
        rows += list((d or {}).get("data") or [])
        nxt = ((d or {}).get("paging") or {}).get("next")
        if not nxt:
            break
        d = await _http(nxt, None, token)
        if _loi(d):
            break
    return rows, None


# ---------------------------------------------------------------- vai trò
def vai_tro(tasks) -> str:
    t = set(tasks or [])
    if "MANAGE" in t:
        return "quan_tri"
    if "CREATE_CONTENT" in t:
        return "bien_tap"
    if "MODERATE" in t:
        return "kiem_duyet"
    if "ADVERTISE" in t:
        return "quang_cao"
    if "ANALYZE" in t:
        return "phan_tich"
    return "khac" if t else "quan_tri"   # Trang cũ không trả tasks = quyền đầy đủ


def dang_duoc(tasks) -> bool:
    t = tasks or []
    return (not t) or any(x in t for x in ("CREATE_CONTENT", "MANAGE"))


_NHAN_VAI = {"quan_tri": "Quản trị viên", "bien_tap": "Biên tập viên", "kiem_duyet": "Kiểm duyệt viên",
             "quang_cao": "Quảng cáo", "phan_tich": "Phân tích", "khac": "Khác"}


def ten_bm(b) -> str:
    """'BM Halimi' giữ nguyên, 'Halimi' thành 'BM Halimi' - tránh 'BM BM Halimi'."""
    s = str(b or "").strip()
    return s if re.match(r"(?i)(bm|business)\b", s) else ("BM " + s if s else "BM")


def _nguon_chu(vt, qua, bm):
    s = _NHAN_VAI.get(vt, "")
    return (s + " · " if s else "") + ("qua " + ten_bm(bm) if qua == "bm" and bm else "cá nhân")


# ---------------------------------------------------------------- một tài khoản
async def _quet_mot(conns: list) -> dict:
    """Quét một tài khoản Facebook (có thể nhiều kết nối cùng một người). Dùng token của từng kết nối,
    gộp lại: Trang/TKQC giao qua kết nối nào cũng tính là đã giao cho MinMin."""
    tk = {"conns": conns, "fb_id": "", "ten_fb": "", "loi": [], "quyen": set(), "co_quyen_tin": False,
          "trang": {}, "tkqc": {}, "bm_trang": {}, "bm_tkqc": {}, "het_han": None, "hop_le": True,
          "ung_dung": "", "token_ok": False}
    for c in conns:
        tok = await _token(c["id"])
        if not tok:
            tk["loi"].append(f"{c['label']}: chưa có token (đăng nhập lại)")
            continue
        me = await _http("me", {"fields": "id,name"}, tok)
        e = _loi(me)
        if e:
            tk["loi"].append(f"{c['label']}: {e.get('message', '')}")
            if e.get("code") == 190:
                tk["hop_le"] = False
            continue
        tk["token_ok"] = True
        tk["fb_id"] = tk["fb_id"] or str(me.get("id") or "")
        tk["ten_fb"] = tk["ten_fb"] or str(me.get("name") or "")
        dbg = await _http("debug_token", {"input_token": tok}, tok)
        dd = (dbg or {}).get("data") or {}
        if dd:
            tk["ung_dung"] = tk["ung_dung"] or str(dd.get("application") or "")
            ea = int(dd.get("expires_at") or 0)
            if ea and (tk["het_han"] is None or ea < tk["het_han"]):
                tk["het_han"] = ea
            if dd.get("is_valid") is False:
                tk["hop_le"] = False
        perms, e = await _het_trang("me/permissions", {}, tok, tran=2)
        if not e:
            tk["co_quyen_tin"] = True
            tk["quyen"] |= {p.get("permission") for p in perms if p.get("status") == "granted"}
        pages, e = await _het_trang("me/accounts", {"fields": "id,name,tasks", "limit": 100}, tok)
        if e:
            tk["loi"].append(f"{c['label']} (Trang): {e.get('message', '')}")
        for p in pages:
            pid = str(p.get("id"))
            cu = tk["trang"].get(pid)
            if not cu or (not dang_duoc(cu.get("tasks")) and dang_duoc(p.get("tasks"))):
                tk["trang"][pid] = {"id": pid, "ten": p.get("name") or pid, "tasks": p.get("tasks"), "conn_id": c["id"]}
        ads, e = await _het_trang("me/adaccounts", {"fields": "account_id,name,business{name},user_tasks",
                                                    "limit": 200}, tok)
        # Kết nối chỉ xin quyền Trang thì đọc quảng cáo lỗi là bình thường, không báo.
        if e and c.get("connector_id") == "meta-ads-graph":
            tk["loi"].append(f"{c['label']} (quảng cáo): {e.get('message', '')}")
        for a in ads:
            aid = str(a.get("account_id") or str(a.get("id", "")).replace("act_", ""))
            if aid and aid not in tk["tkqc"]:
                tk["tkqc"][aid] = {"id": aid, "ten": a.get("name") or aid,
                                   "bm": ((a.get("business") or {}).get("name") or ""),
                                   "user_tasks": a.get("user_tasks") or [], "conn_id": c["id"]}
        bizs, e = await _het_trang("me/businesses", {"fields": "id,name", "limit": 100}, tok, tran=3)
        for b in bizs[:30]:
            bten = b.get("name") or ""
            for canh in ("owned_pages", "client_pages"):
                rows, _ = await _het_trang(f"{b.get('id')}/{canh}", {"fields": "id,name", "limit": 200}, tok, tran=5)
                for p in rows:
                    tk["bm_trang"].setdefault(str(p.get("id")), {"ten": p.get("name") or "", "bm": bten})
            for canh in ("owned_ad_accounts", "client_ad_accounts"):
                rows, _ = await _het_trang(f"{b.get('id')}/{canh}", {"fields": "account_id,name", "limit": 200},
                                           tok, tran=5)
                for a in rows:
                    aid = str(a.get("account_id") or str(a.get("id", "")).replace("act_", ""))
                    if aid:
                        tk["bm_tkqc"].setdefault(aid, {"ten": a.get("name") or "", "bm": bten})
    return tk


def _token_tt(tk) -> dict:
    if not tk["token_ok"]:
        return {"trang_thai": "loi", "con_ngay": None, "loi": "; ".join(tk["loi"])[:300]}
    if not tk["hop_le"]:
        return {"trang_thai": "het_han", "con_ngay": 0, "loi": "Token hết hạn hoặc bị thu hồi"}
    if tk["het_han"]:
        ngay = max(0, int((tk["het_han"] - time.time()) // 86400))
        return {"trang_thai": "sap_het" if ngay < 7 else "tot", "con_ngay": ngay, "loi": ""}
    return {"trang_thai": "tot", "con_ngay": None, "loi": ""}


def _thieu_quyen(tk) -> list:
    if not tk["co_quyen_tin"]:
        return []
    return [{"ma": m, "ten": t} for m, t, _ in QUYEN if m not in tk["quyen"]]


async def _quet_tat_ca() -> list:
    conns = _ket_noi()
    # Chưa biết fb_id trước khi gọi `me`, nên quét theo từng kết nối rồi gộp những kết nối cùng fb_id.
    ket = await asyncio.gather(*[_quet_mot([c]) for c in conns])
    gop, thu_tu = {}, []
    for c, tk in zip(conns, ket):
        khoa = tk["fb_id"] or ("conn:" + c["id"])
        if khoa not in gop:
            gop[khoa] = tk
            thu_tu.append(khoa)
            continue
        g = gop[khoa]
        g["conns"] += tk["conns"]
        g["loi"] += tk["loi"]
        g["quyen"] |= tk["quyen"]
        g["co_quyen_tin"] = g["co_quyen_tin"] or tk["co_quyen_tin"]
        g["token_ok"] = g["token_ok"] or tk["token_ok"]
        for k in ("trang", "tkqc", "bm_trang", "bm_tkqc"):
            for kk, vv in tk[k].items():
                g[k].setdefault(kk, vv)
        if tk["het_han"] and (not g["het_han"] or tk["het_han"] < g["het_han"]):
            g["het_han"] = tk["het_han"]
    return [gop[k] for k in thu_tu]


# ---------------------------------------------------------------- tài sản gộp
async def _du_lieu(lam_moi=False) -> tuple:
    if not lam_moi and _DEM.get("ts") and time.time() - _DEM["ts"] < DEM_GIAY:
        return _DEM["tks"], _DEM["kiem_luc"]
    tks = await _quet_tat_ca()
    _DEM.update(ts=time.time(), tks=tks, kiem_luc=datetime.now().isoformat(timespec="seconds"))
    return tks, _DEM["kiem_luc"]


def _fb(tk) -> str:
    return tk["fb_id"] or ("conn:" + tk["conns"][0]["id"])


def _gom(tks) -> dict:
    trang, tkqc, loi = {}, {}, []
    for tk in tks:
        fb = _fb(tk)
        loi += tk["loi"]
        co_ghi_ads = "ads_management" in tk["quyen"] or not tk["co_quyen_tin"]
        for pid, p in tk["trang"].items():
            bm = tk["bm_trang"].get(pid)
            e = trang.setdefault(pid, {"id": pid, "ten": p["ten"], "nguon": {}, "_dang": []})
            e["nguon"][fb] = {"vai_tro": vai_tro(p.get("tasks")), "qua": "bm" if bm else "ca_nhan",
                              "bm_ten": (bm or {}).get("bm", ""), "giao": True}
            if dang_duoc(p.get("tasks")):
                e["_dang"].append(fb)
        for pid, b in tk["bm_trang"].items():
            if pid in tk["trang"]:
                continue
            e = trang.setdefault(pid, {"id": pid, "ten": b["ten"] or pid, "nguon": {}, "_dang": []})
            e["nguon"].setdefault(fb, {"vai_tro": "", "qua": "bm", "bm_ten": b["bm"], "giao": False})
        for aid, a in tk["tkqc"].items():
            e = tkqc.setdefault(aid, {"id": aid, "ten": a["ten"], "nguon": {}, "_ghi": [], "_doc": []})
            e["nguon"][fb] = {"qua": "bm" if a["bm"] else "ca_nhan", "bm_ten": a["bm"], "giao": True}
            ut = a.get("user_tasks") or []
            e["_doc"].append(fb)
            if co_ghi_ads and (not ut or any(x in ut for x in ("MANAGE", "ADVERTISE"))):
                e["_ghi"].append(fb)
        for aid, b in tk["bm_tkqc"].items():
            if aid in tk["tkqc"]:
                continue
            e = tkqc.setdefault(aid, {"id": aid, "ten": b["ten"] or aid, "nguon": {}, "_ghi": [], "_doc": []})
            e["nguon"].setdefault(fb, {"qua": "bm", "bm_ten": b["bm"], "giao": False})
    ds_trang = []
    for e in trang.values():
        dang = e.pop("_dang")
        e["dang_bang"] = dang[0] if dang else ""
        e["van_de"] = "" if dang else "chua_giao"
        ds_trang.append(e)
    ds_tkqc = []
    for e in tkqc.values():
        ghi, doc = e.pop("_ghi"), e.pop("_doc")
        e["dung"] = ghi[0] if ghi else (doc[0] if doc else "")
        e["van_de"] = "" if ghi else ("thieu_quyen_ghi" if doc else "chua_giao")
        ds_tkqc.append(e)
    ds_trang.sort(key=lambda x: (x["van_de"] == "", x["ten"].lower()))
    ds_tkqc.sort(key=lambda x: (x["van_de"] == "", x["ten"].lower()))
    return {"trang": ds_trang, "tkqc": ds_tkqc, "loi": loi}


def _the_tk(tk, gom) -> dict:
    fb = _fb(tk)
    can = sum(1 for p in gom["trang"] if fb in p["nguon"] and not p["nguon"][fb]["giao"])
    can += sum(1 for a in gom["tkqc"] if fb in a["nguon"] and not a["nguon"][fb]["giao"])
    thieu = _thieu_quyen(tk)
    if any(q["ma"] == "ads_management" for q in thieu) and tk["tkqc"]:
        can += 1
    c0 = tk["conns"][0]
    return {"fb_id": fb, "ten": c0["label"], "ten_fb": tk["ten_fb"],
            "mac_dinh": any(c.get("is_default") for c in tk["conns"]),
            "ket_noi": [{"id": c["id"], "connector_id": c.get("connector_id"), "label": c["label"]} for c in tk["conns"]],
            "token": _token_tt(tk), "so_trang": len(tk["trang"]), "so_tkqc": len(tk["tkqc"]),
            "can_xu_ly": can, "thieu_quyen": thieu}


async def tai_san(lam_moi: bool = False) -> dict:
    tks, luc = await _du_lieu(lam_moi)
    gom = _gom(tks)
    return {"ok": True, "kiem_luc": luc, "loi": gom["loi"],
            "tai_khoan": [_the_tk(tk, gom) for tk in tks], "trang": gom["trang"], "tkqc": gom["tkqc"]}


# ---------------------------------------------------------------- soi quyền một tài khoản
async def soi_quyen(fb_id: str, lam_moi: bool = True) -> dict:
    tks, luc = await _du_lieu(lam_moi)
    tk = next((x for x in tks if _fb(x) == str(fb_id or "")), None)
    if not tk:
        return {"ok": False, "loi": "Không có tài khoản Facebook này trong các kết nối đang nối."}
    gom = _gom(tks)
    fb = _fb(tk)
    chua = []
    for p in gom["trang"]:
        n = p["nguon"].get(fb)
        if n and not n["giao"]:
            chua.append({"loai": "trang", "id": p["id"], "ten": p["ten"], "vai_tro": "", "qua": "bm",
                         "bm_ten": n["bm_ten"], "ly_do_ma": "chua_giao_bm",
                         "ly_do": f"Trang thuộc {ten_bm(n['bm_ten'])} nhưng Facebook chưa giao cho MinMin.",
                         "cach_sua": "Nếu bạn được gán Trang này trong BM: Đăng nhập lại và tick Trang này. "
                                     "Nếu chưa được gán: vào BM gán quyền Trang cho tài khoản này trước.",
                         "nut": "dang_nhap_lai"})
        elif n and n["giao"] and p["dang_bang"] != fb and not dang_duoc_vai(n["vai_tro"]):
            chua.append({"loai": "trang", "id": p["id"], "ten": p["ten"], "vai_tro": n["vai_tro"], "qua": n["qua"],
                         "bm_ten": n["bm_ten"], "ly_do_ma": "khong_dang",
                         "ly_do": f"Vai trò {_NHAN_VAI.get(n['vai_tro'], '')} không được đăng bài.",
                         "cach_sua": "Nhờ quản trị viên Trang nâng lên Biên tập viên trở lên.", "nut": "huong_dan"})
    thieu = {q["ma"] for q in _thieu_quyen(tk)}
    for a in gom["tkqc"]:
        n = a["nguon"].get(fb)
        if not n:
            continue
        if not n["giao"]:
            chua.append({"loai": "tkqc", "id": a["id"], "ten": a["ten"], "vai_tro": "", "qua": "bm",
                         "bm_ten": n["bm_ten"], "ly_do_ma": "chua_giao_bm",
                         "ly_do": f"Tài khoản quảng cáo thuộc {ten_bm(n['bm_ten'])} nhưng Facebook chưa giao cho MinMin.",
                         "cach_sua": "Đăng nhập lại và chọn tài khoản này ở màn chọn tài khoản quảng cáo.",
                         "nut": "dang_nhap_lai"})
        elif "ads_management" in thieu:
            chua.append({"loai": "tkqc", "id": a["id"], "ten": a["ten"], "vai_tro": "", "qua": n["qua"],
                         "bm_ten": n["bm_ten"], "ly_do_ma": "thieu_quyen",
                         "ly_do": "Token chưa có quyền quản lý quảng cáo nên chưa bật tắt camp được.",
                         "cach_sua": "Đăng nhập lại và cho phép Quản lý quảng cáo. Nếu màn Facebook không hỏi "
                                     "quyền này, app chưa bật quyền ads_management: xem hướng dẫn.",
                         "nut": "cap_quyen"})
    return {"ok": True, "kiem_luc": luc, "tai_khoan": _the_tk(tk, gom), "ung_dung": tk["ung_dung"],
            "quyen": [{"ma": m, "ten": t, "co": (m in tk["quyen"]) if tk["co_quyen_tin"] else None, "de_lam": d}
                      for m, t, d in QUYEN],
            "trang_giao": len(tk["trang"]), "tkqc_giao": len(tk["tkqc"]),
            "trang_chua_giao": sum(1 for x in chua if x["loai"] == "trang" and x["ly_do_ma"] == "chua_giao_bm"),
            "tkqc_chua_giao": sum(1 for x in chua if x["loai"] == "tkqc" and x["ly_do_ma"] == "chua_giao_bm"),
            "chua_giao": chua, "loi": tk["loi"]}


def dang_duoc_vai(vt) -> bool:
    return vt in ("quan_tri", "bien_tap")


# ---------------------------------------------------------------- hỏi Facebook về một Trang
_RE_FB = re.compile(r"(?:https?://)?(?:www\.|m\.|web\.)?(?:facebook|fb)\.com/(.+)", re.I)


def tach_q(q: str) -> tuple:
    """-> ("id"|"slug"|"ten"|"", giá trị)."""
    s = str(q or "").strip()
    if not s:
        return "", ""
    m = _RE_FB.match(s)
    if m:
        duoi = m.group(1)
        mid = re.search(r"[?&]id=(\d+)", duoi)
        if mid:
            return "id", mid.group(1)
        seg = re.split(r"[/?#]", duoi)[0]
        if seg.lower() in ("pages", "pg") :
            parts = [x for x in re.split(r"[/?#]", duoi) if x]
            num = next((x for x in parts if x.isdigit()), "")
            return ("id", num) if num else ("", "")
        if seg.isdigit():
            return "id", seg
        return ("slug", seg) if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", seg or "") else ("", "")
    if re.fullmatch(r"\d{5,25}", s):
        return "id", s
    return "ten", s


async def hoi_trang(fb_id: str, q: str) -> dict:
    tks, _ = await _du_lieu(False)
    tk = next((x for x in tks if _fb(x) == str(fb_id or "")), None)
    if not tk:
        return {"ok": False, "ket_qua": "loi_token", "ly_do": "Không có tài khoản Facebook này.", "cach_sua": "",
                "nguyen_van": ""}
    loai, gt = tach_q(q)
    if not loai:
        return {"ok": True, "ket_qua": "can_id", "id": "", "ten": "",
                "ly_do": "Chưa đọc được Trang nào từ ô nhập.", "cach_sua": "Dán ID Trang hoặc link facebook.com của Trang.",
                "nguyen_van": ""}
    pid = gt
    if loai == "ten":
        gom = _gom(tks)
        tl = gt.lower()
        hit = [p for p in gom["trang"] if p["id"] == gt] or [p for p in gom["trang"] if p["ten"].lower() == tl] or [p for p in gom["trang"] if tl in p["ten"].lower()]
        if len(hit) != 1:
            return {"ok": True, "ket_qua": "can_id", "id": "", "ten": gt,
                    "ly_do": ("Tên này khớp nhiều Trang." if hit else
                              "MinMin không biết Trang nào tên như vậy, vì Facebook chưa cho tài khoản nào thấy nó."),
                    "cach_sua": "Dán ID Trang hoặc link facebook.com của Trang để hỏi thẳng Facebook.",
                    "nguyen_van": ""}
        pid = hit[0]["id"]
    tok = None
    for c in tk["conns"]:
        tok = await _token(c["id"])
        if tok:
            break
    if not tok:
        return {"ok": True, "ket_qua": "loi_token", "id": pid, "ten": "", "ly_do": "Tài khoản này chưa có token.",
                "cach_sua": "Đăng nhập lại Facebook cho tài khoản này.", "nguyen_van": ""}
    d = await _http(pid, {"fields": "id,name,access_token,tasks"}, tok)
    e = _loi(d)
    if e:
        msg = str(e.get("message") or "")
        code = e.get("code")
        nv = f"({code}) {msg}" if code is not None else msg
        if code == 190:
            return {"ok": True, "ket_qua": "loi_token", "id": pid, "ten": "", "nguyen_van": nv,
                    "ly_do": "Token của tài khoản này đã hết hạn hoặc bị thu hồi.",
                    "cach_sua": "Đăng nhập lại Facebook cho tài khoản này."}
        if code in (10, 200) or "permission" in msg.lower():
            return {"ok": True, "ket_qua": "thieu_quyen", "id": pid, "ten": "", "nguyen_van": nv,
                    "ly_do": "Facebook từ chối vì app chưa đủ quyền với Trang này.",
                    "cach_sua": "Đăng nhập lại và tick Trang này. Nếu Trang thuộc BM khác BM sở hữu app, app tự tạo "
                                "ở mức thường có thể bị chặn: cần nâng quyền app với Meta."}
        return {"ok": True, "ket_qua": "khong_tim_thay", "id": pid, "ten": "", "nguyen_van": nv,
                "ly_do": "Facebook không cho token này đọc Trang này, hoặc ID/link sai.",
                "cach_sua": "Kiểm tra lại ID/link. Nếu đúng, tài khoản này chưa có vai trò trên Trang, hoặc chưa tick "
                            "Trang lúc đăng nhập."}
    ten = str(d.get("name") or pid)
    pid = str(d.get("id") or pid)
    if d.get("access_token"):
        if dang_duoc(d.get("tasks")):
            return {"ok": True, "ket_qua": "giao", "id": pid, "ten": ten, "nguyen_van": "",
                    "ly_do": f"Đã giao cho MinMin. Vai trò: {_NHAN_VAI.get(vai_tro(d.get('tasks')), '')}.",
                    "cach_sua": "Không cần làm gì. Nếu bảng chưa hiện, bấm Quét lại."}
        return {"ok": True, "ket_qua": "giao_khong_dang", "id": pid, "ten": ten, "nguyen_van": "",
                "ly_do": f"Đã giao, nhưng vai trò {_NHAN_VAI.get(vai_tro(d.get('tasks')), '')} không được đăng bài.",
                "cach_sua": "Nhờ quản trị viên Trang nâng lên Biên tập viên trở lên."}
    bm = tk["bm_trang"].get(pid)
    if bm:
        return {"ok": True, "ket_qua": "chua_giao_bm", "id": pid, "ten": ten, "nguyen_van": "",
                "ly_do": f"Trang thuộc {ten_bm(bm['bm'])} nhưng chưa giao cho MinMin.",
                "cach_sua": "Nếu bạn được gán Trang trong BM: Đăng nhập lại và tick Trang này. Nếu chưa: gán quyền "
                            "Trang cho tài khoản này trong BM trước."}
    return {"ok": True, "ket_qua": "khong_thay_quyen", "id": pid, "ten": ten, "nguyen_van": "",
            "ly_do": "Facebook thấy Trang nhưng không cho MinMin biết tài khoản này có vai trò trên nó.",
            "cach_sua": f"Nếu bạn là quản trị viên hoặc biên tập viên của {ten}: Đăng nhập lại Facebook, ở màn chọn "
                        "Trang tick Trang này, giữ nguyên các Trang cũ."}
