"""Cầu nối Thống kê Pancake (transport "internal"). Một kết nối gom NHIỀU page Facebook/Pancake.

Pancake (pancake.vn, hộp thư hội thoại) có Public API v1 riêng cho số liệu chat, khác Pancake POS:
  base   https://pages.fm/api/public_api/v1
  auth   query `page_access_token` (mỗi page một token, tạo ở Cài đặt page > Công cụ > Public API
         access token; token không hết hạn trừ khi bị xoá hoặc tạo lại)
  GET /pages/{page_id}/statistics/pages   since, until (unix giây)
        -> {"data": [{"hour": "2026-10-19T00:00:00" (giờ VN), new_customer_count, new_inbox_count,
           customer_inbox_count, customer_comment_count, phone_number_count, uniq_phone_number_count,
           page_inbox_count, ...}]} - mỗi dòng một giờ, giờ không có gì thì vắng.
        (page_customers trong đặc tả KHÔNG dùng được: chạy thật 26/10/2026 trả trang HTML, mã 200.)
  GET /pages/{page_id}/statistics/customer_engagements   date_range, by_hour
        -> data.categories[] + data.series[{name, data[]}] (inbox, comment, total,
           new_customer_replied, customer_engagement_new_inbox, order_count, old_order_count)
           + users_engagements[{user_id, name, inbox_count, order_count, old_order_count, total_engagement}]
  GET /pages/{page_id}/statistics/users   date_range
        -> data.users{uuid: {user_name, unique_inbox_count, inbox_count, comment_count,
           phone_number_count, average_response_time, ...}}
  date_range = "DD/MM/YYYY HH:MM:SS - DD/MM/YYYY HH:MM:SS" theo giờ CỦA PAGE (UTC+7 với page VN).
Nguồn: https://developer.pancake.biz/openapi/openapi.yaml (đọc 2026-10-25). Màn Thống kê trên web
pancake.vn đã đối chiếu với tài khoản thật cùng ngày. Chạy thật bằng token 34 page ngày 26/10/2026:
customer_engagements, users, statistics/pages trả JSON đúng dạng ở trên.

Ô đăng nhập `pages`: mỗi dòng một page, dạng `page_id | page_access_token | tên hiển thị` (tên tuỳ
chọn). Dấu phân cách nhận `|`, `,`, `;`, tab hoặc dấu cách.

TỶ LỆ CHỐT do MinMin tính (Pancake không trả sẵn):
  ty_le_chot          = don_chot / khach_nhan_tin   (khách tương tác qua inbox trong kỳ)
  ty_le_chot_tren_sdt = don_chot / so_dien_thoai
  nhân viên: don_chot / khach_da_tra_loi (unique_inbox_count)

Có bộ nhớ đệm 60 giây cho từng (page, kỳ, loại số): hỏi dồn dập hay nhiều báo cáo cùng lúc không
dội Pancake, mà số vẫn gần như trực tiếp.

Bản này CHỈ ĐỌC.
"""
from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from datetime import datetime, timedelta

import ket_noi_api as k

HOST = "https://pages.fm/api/public_api/v1"
TEN = "Pancake"
TTL = 60                 # giây giữ kết quả trong bộ nhớ đệm
SONG_SONG = 4            # số page gọi cùng lúc
TOI_DA_NGAY = 92         # khoảng ngày dài nhất một lần hỏi
CUA_SO_GIO = 31          # statistics/pages trả theo giờ: hỏi từng khúc tối đa 31 ngày cho nhẹ
_DEM: dict = {}          # (page_id, loại, date_range) -> (thời điểm, dữ liệu)

_PAGE_PROP = {"page": {"type": "string",
                       "description": "page_id hoặc một phần tên page; bỏ trống = tất cả page của kết nối"}}

TOOLS = [
    k.tool("pancake_tk_ds_page",
           "Danh sách page đã gắn vào kết nối Thống kê Pancake (page_id, tên). Không trả token."),
    k.tool("pancake_tk_tong_quan",
           "Số liệu hội thoại theo kỳ (mặc định HÔM NAY): khách mới, khách nhắn tin, bình luận, số điện "
           "thoại, đơn chốt, đơn khách cũ, tỷ lệ chốt. Trả TỔNG mọi page và TỪNG page; theo_ngay=true "
           "thêm bảng từng ngày.",
           {"tu_ngay": {"type": "string", "description": "từ ngày YYYY-MM-DD (giờ VN), mặc định hôm nay"},
            "den_ngay": {"type": "string", "description": "đến ngày YYYY-MM-DD, mặc định hôm nay"},
            "theo_ngay": {"type": "boolean", "description": "kèm số từng ngày của tổng các page"},
            **_PAGE_PROP}),
    k.tool("pancake_tk_nhan_vien",
           "Xếp hạng nhân viên sale theo kỳ (mặc định HÔM NAY): khách đã trả lời, số điện thoại lấy "
           "được, đơn chốt, tỷ lệ chốt, thời gian phản hồi trung bình. Cộng dồn mọi page, kèm chi tiết "
           "từng page của mỗi người.",
           {"tu_ngay": {"type": "string", "description": "từ ngày YYYY-MM-DD (giờ VN), mặc định hôm nay"},
            "den_ngay": {"type": "string", "description": "đến ngày YYYY-MM-DD, mặc định hôm nay"},
            **_PAGE_PROP}),
]


async def list_tools(spec):
    return TOOLS


# ---------------------------------------------------------------- đọc cấu hình page

def _bo_dau(s):
    s = unicodedata.normalize("NFD", str(s or "")).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def doc_pages(raw):
    """Chuỗi nhiều dòng -> [{"id", "token", "ten"}]. Bỏ dòng trống và dòng chú thích (#)."""
    out, thay = [], set()
    for dong in str(raw or "").splitlines():
        dong = dong.strip()
        if not dong or dong.startswith("#"):
            continue
        phan = [p.strip() for p in re.split(r"\s*[|,;\t]\s*|\s+", dong, maxsplit=2) if p.strip()]
        if len(phan) < 2 or not re.fullmatch(r"\d{5,25}", phan[0]):
            continue
        if phan[0] in thay:
            continue
        thay.add(phan[0])
        out.append({"id": phan[0], "token": phan[1], "ten": phan[2] if len(phan) > 2 else phan[0]})
    return out


def _chon(pages, loc):
    loc = str(loc or "").strip()
    if not loc:
        return pages
    if loc.isdigit():
        return [p for p in pages if p["id"] == loc]
    q = _bo_dau(loc)
    return [p for p in pages if q in _bo_dau(p["ten"])]


# ---------------------------------------------------------------- thời gian

def _ky(a):
    """(ngày đầu, ngày cuối) dạng date theo giờ người dùng. Mặc định hôm nay."""
    hom_nay = datetime.now(k.mui_gio()).date()

    def doc(v):
        try:
            return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None
    den = doc(a.get("den_ngay")) or hom_nay
    tu = doc(a.get("tu_ngay")) or (den if a.get("den_ngay") else hom_nay)
    if tu > den:
        tu, den = den, tu
    if (den - tu).days >= TOI_DA_NGAY:
        tu = den - timedelta(days=TOI_DA_NGAY - 1)
    return tu, den


def date_range(tu, den):
    return f"{tu:%d/%m/%Y} 00:00:00 - {den:%d/%m/%Y} 23:59:59"


# ---------------------------------------------------------------- gọi API

async def _get(page, path, params):
    key = (page["id"], path, tuple(sorted(params.items())))
    now = time.time()
    if key in _DEM and now - _DEM[key][0] < TTL:
        return True, _DEM[key][1]
    sec = {"token": page["token"]}
    ok, d = await k.goi(TEN, "GET", f"{HOST}/pages/{page['id']}{path}", secrets=sec,
                        params={**params, "page_access_token": page["token"]})
    if ok and not isinstance(d, dict):
        ok, d = False, f"ERROR: Pancake trả về không phải dữ liệu ({path}) - API này không dùng được với token page"
    if ok and isinstance(d, dict) and d.get("success") is False:
        ok, d = False, k.giau(f"ERROR: Pancake từ chối: {d.get('message') or d.get('error') or d}", sec)
    if ok:
        _DEM[key] = (now, d)
    return ok, d


def _n(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def _ty_le(tu_so, mau):
    return round(tu_so * 100.0 / mau, 1) if mau else None


_GIO = {"khach_moi": "new_customer_count", "hoi_thoai_inbox_moi": "new_inbox_count",
        "so_dien_thoai": "phone_number_count", "so_dien_thoai_khong_trung": "uniq_phone_number_count",
        "tin_nhan_khach": "customer_inbox_count", "binh_luan_khach": "customer_comment_count"}


def doc_gio(ds_d, tu=None, den=None):
    """statistics/pages (theo giờ) -> (tổng, {ngày 'YYYY-MM-DD': {...}}). Bỏ giờ nằm ngoài kỳ:
    Pancake trả lấn sang 00:00 của ngày sau kỳ."""
    tong, ngay = dict.fromkeys(_GIO, 0), {}
    for d in (ds_d if isinstance(ds_d, list) else [ds_d]):
        rows = d.get("data") if isinstance(d, dict) else None
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            nk = _ngay_iso(str(r.get("hour") or r.get("date") or "")[:10])
            if nk and tu and den and not (f"{tu:%Y-%m-%d}" <= nk <= f"{den:%Y-%m-%d}"):
                continue
            x = {kk: _n(r.get(goc)) for kk, goc in _GIO.items()}
            for kk, v in x.items():
                tong[kk] += v
            if nk:
                cu = ngay.setdefault(nk, dict.fromkeys(_GIO, 0))
                for kk, v in x.items():
                    cu[kk] += v
    return tong, ngay


def khuc_gio(tu, den):
    """Chia kỳ thành các khúc <= CUA_SO_GIO ngày -> [(since, until)] unix giây theo giờ người dùng."""
    out, d = [], tu
    while d <= den:
        cuoi = min(den, d + timedelta(days=CUA_SO_GIO - 1))
        a = datetime(d.year, d.month, d.day, tzinfo=k.mui_gio())
        b = datetime(cuoi.year, cuoi.month, cuoi.day, 23, 59, 59, tzinfo=k.mui_gio())
        out.append((int(a.timestamp()), int(b.timestamp())))
        d = cuoi + timedelta(days=1)
    return out


_SERIES = {"inbox": "khach_nhan_tin", "comment": "khach_binh_luan", "total": "tong_tuong_tac",
           "new_customer_replied": "khach_moi_da_tra_loi",
           "customer_engagement_new_inbox": "khach_mo_hoi_thoai_moi",
           "order_count": "don_chot", "old_order_count": "don_khach_cu"}


def _ngay_iso(s):
    s = str(s or "").strip()
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.split(" ")[0], f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def doc_tuong_tac(d):
    """customer_engagements -> (tổng, theo ngày, nhân viên[]). Nhận cả dạng bảng
    `engagement_statistics` (màn web) lẫn dạng categories/series (Public API)."""
    if not isinstance(d, dict):
        return dict.fromkeys(_SERIES.values(), 0), {}, []
    data = d.get("data") if isinstance(d.get("data"), dict) else d
    tong, ngay = dict.fromkeys(_SERIES.values(), 0), {}
    cats = data.get("categories") or []
    for s in data.get("series") or []:
        ten = _SERIES.get(str((s or {}).get("name")))
        if not ten:
            continue
        for i, v in enumerate(s.get("data") or []):
            tong[ten] += _n(v)
            nk = _ngay_iso(cats[i]) if i < len(cats) else None
            if nk:
                ngay.setdefault(nk, dict.fromkeys(_SERIES.values(), 0))[ten] += _n(v)
    for r in d.get("engagement_statistics") or data.get("engagement_statistics") or []:
        nk = _ngay_iso((r or {}).get("time"))
        for goc, ten in _SERIES.items():
            v = _n((r or {}).get(goc))
            tong[ten] += v
            if nk:
                ngay.setdefault(nk, dict.fromkeys(_SERIES.values(), 0))[ten] += v
    nv = data.get("users_engagements") or d.get("users_engagements") or []
    if isinstance(nv, dict):
        nv = [{"user_id": kk, **(v or {})} for kk, v in nv.items()]
    return tong, ngay, [x for x in nv if isinstance(x, dict)]


def doc_nhan_vien(d):
    """statistics/users -> {khoá: {...}}; khoá là user id (uuid)."""
    data = d.get("data") if isinstance(d, dict) else None
    users = (data or {}).get("users") if isinstance(data, dict) else None
    out = {}
    for uid, u in (users or {}).items():
        if not isinstance(u, dict):
            continue
        out[str(uid)] = {"ten": str(u.get("user_name") or uid).strip(),
                         "khach_da_tra_loi": _n(u.get("unique_inbox_count")),
                         "tin_inbox": _n(u.get("inbox_count")),
                         "binh_luan_da_tra_loi": _n(u.get("unique_comment_count")),
                         "so_dien_thoai": _n(u.get("phone_number_count")),
                         "phan_hoi_tb_giay": _giay(u.get("average_response_time"))}
    return out


def _giay(v):
    """Đặc tả ghi mili giây; màn web hiện số nhỏ như 17 (giây). Lớn hơn 10 phút coi là mili giây."""
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return 0
    return round(x / 1000.0 if x > 600 else x, 1)


async def _moi_page(pages, viec):
    sem = asyncio.Semaphore(SONG_SONG)

    async def mot(p):
        async with sem:
            return p, await viec(p)
    return await asyncio.gather(*(mot(p) for p in pages))


# ---------------------------------------------------------------- các tool

async def tong_quan(pages, a):
    tu, den = _ky(a)
    dr = date_range(tu, den)

    khuc = khuc_gio(tu, den)

    async def gio(p):
        kq = []
        for since, until in khuc:
            ok, d = await _get(p, "/statistics/pages", {"since": since, "until": until})
            if not ok:
                return False, d
            kq.append(d)
        return True, kq

    async def viec(p):
        (ok1, d1), (ok2, d2) = await asyncio.gather(
            gio(p), _get(p, "/statistics/customer_engagements", {"date_range": dr}))
        return ok1, d1, ok2, d2

    ket = await _moi_page(pages, viec)
    tong = dict.fromkeys(tuple(_GIO) + tuple(_SERIES.values()), 0)
    tung_page, loi, theo_ngay = [], [], {}
    for p, (ok1, d1, ok2, d2) in ket:
        if not ok1 and not ok2:
            loi.append(f"{p['ten']}: {d1}")
            continue
        kh, ngay_kh = doc_gio(d1, tu, den) if ok1 else (dict.fromkeys(_GIO, 0), {})
        tt, ngay_tt, _nv = doc_tuong_tac(d2) if ok2 else (dict.fromkeys(_SERIES.values(), 0), {}, [])
        if not ok1 or not ok2:
            loi.append(f"{p['ten']}: thiếu một phần số ({d1 if not ok1 else d2})")
        dong = {"page_id": p["id"], "page": p["ten"], **kh, **tt}
        dong["ty_le_chot"] = _ty_le(dong["don_chot"], dong["khach_nhan_tin"])
        dong["ty_le_chot_tren_sdt"] = _ty_le(dong["don_chot"], dong["so_dien_thoai"])
        tung_page.append(dong)
        for kk in tong:
            tong[kk] += dong.get(kk, 0)
        for nguon in (ngay_kh, ngay_tt):
            for nk, x in nguon.items():
                cu = theo_ngay.setdefault(nk, dict.fromkeys(tong, 0))
                for kk, v in x.items():
                    cu[kk] = cu.get(kk, 0) + v
    tong["ty_le_chot"] = _ty_le(tong["don_chot"], tong["khach_nhan_tin"])
    tong["ty_le_chot_tren_sdt"] = _ty_le(tong["don_chot"], tong["so_dien_thoai"])
    tung_page.sort(key=lambda r: (r["don_chot"], r["khach_nhan_tin"]), reverse=True)
    kq = {"ky": {"tu_ngay": f"{tu:%Y-%m-%d}", "den_ngay": f"{den:%Y-%m-%d}"},
          "cap_nhat_luc": datetime.now(k.mui_gio()).strftime("%Y-%m-%d %H:%M"),
          "so_page": len(pages), "tong_tat_ca_page": tong, "tung_page": tung_page,
          "dinh_nghia": "khach_nhan_tin = khách tương tác qua inbox; hoi_thoai_inbox_moi = hội thoại mới; "
                        "so_dien_thoai = số điện thoại thu được (so_dien_thoai_khong_trung đã bỏ trùng); "
                        "ty_le_chot = don_chot / khach_nhan_tin (%); ty_le_chot_tren_sdt = don_chot / so_dien_thoai (%). "
                        "Số đơn là đơn tạo từ hội thoại Pancake, chưa trừ đơn huỷ (đối chiếu POS nếu cần)."}
    if a.get("theo_ngay"):
        kq["theo_ngay"] = [{"ngay": nk, **v} for nk, v in sorted(theo_ngay.items())]
    if loi:
        kq["loi"] = loi
    return kq


def _khoa_ten(ten):
    return re.sub(r"\s+", " ", _bo_dau(ten))


async def nhan_vien(pages, a):
    tu, den = _ky(a)
    dr = date_range(tu, den)

    async def viec(p):
        (ok1, d1), (ok2, d2) = await asyncio.gather(
            _get(p, "/statistics/users", {"date_range": dr}),
            _get(p, "/statistics/customer_engagements", {"date_range": dr}))
        return ok1, d1, ok2, d2

    ket = await _moi_page(pages, viec)
    gop, loi = {}, []
    for p, (ok1, d1, ok2, d2) in ket:
        if not ok1 and not ok2:
            loi.append(f"{p['ten']}: {d1}")
            continue
        theo_id = doc_nhan_vien(d1) if ok1 else {}
        _t, _n2, eng = doc_tuong_tac(d2) if ok2 else ({}, {}, [])
        don = {}
        for e in eng:
            uid = str(e.get("user_id") or "")
            ten = str(e.get("name") or e.get("user_name") or theo_id.get(uid, {}).get("ten") or uid).strip()
            don[uid or ten] = (ten, _n(e.get("order_count")), _n(e.get("old_order_count")))
        for uid in set(theo_id) | set(don):
            u = theo_id.get(uid, {})
            ten = u.get("ten") or (don.get(uid) or ("",))[0] or uid
            if not ten or _khoa_ten(ten) in ("", "pos", "botcake", "bot"):
                continue
            x = gop.setdefault(_khoa_ten(ten), {"ten": ten, "khach_da_tra_loi": 0, "tin_inbox": 0,
                                               "binh_luan_da_tra_loi": 0, "so_dien_thoai": 0, "don_chot": 0,
                                               "don_khach_cu": 0, "_tg": [], "tung_page": []})
            dc = (don.get(uid) or ("", 0, 0))
            dong = {"page": p["ten"], "khach_da_tra_loi": u.get("khach_da_tra_loi", 0),
                    "so_dien_thoai": u.get("so_dien_thoai", 0), "don_chot": dc[1]}
            for kk in ("khach_da_tra_loi", "tin_inbox", "binh_luan_da_tra_loi", "so_dien_thoai"):
                x[kk] += u.get(kk, 0)
            x["don_chot"] += dc[1]
            x["don_khach_cu"] += dc[2]
            if u.get("phan_hoi_tb_giay"):
                x["_tg"].append((u["phan_hoi_tb_giay"], max(1, u.get("khach_da_tra_loi", 0))))
            if any(dong[kk] for kk in ("khach_da_tra_loi", "so_dien_thoai", "don_chot")):
                x["tung_page"].append(dong)
    ds = []
    for x in gop.values():
        tg = x.pop("_tg")
        tong_w = sum(w for _, w in tg)
        x["phan_hoi_tb_giay"] = round(sum(v * w for v, w in tg) / tong_w, 1) if tong_w else None
        x["ty_le_chot"] = _ty_le(x["don_chot"], x["khach_da_tra_loi"])
        if any(x[kk] for kk in ("khach_da_tra_loi", "so_dien_thoai", "don_chot", "tin_inbox")):
            ds.append(x)
    ds.sort(key=lambda r: (r["don_chot"], r["so_dien_thoai"], r["khach_da_tra_loi"]), reverse=True)
    kq = {"ky": {"tu_ngay": f"{tu:%Y-%m-%d}", "den_ngay": f"{den:%Y-%m-%d}"},
          "cap_nhat_luc": datetime.now(k.mui_gio()).strftime("%Y-%m-%d %H:%M"),
          "so_page": len(pages), "nhan_vien": ds,
          "tong": {kk: sum(x[kk] for x in ds) for kk in ("khach_da_tra_loi", "so_dien_thoai", "don_chot")},
          "dinh_nghia": "ty_le_chot = don_chot / khach_da_tra_loi (%). Một người làm nhiều page được cộng dồn theo tên."}
    kq["tong"]["ty_le_chot"] = _ty_le(kq["tong"]["don_chot"], kq["tong"]["khach_da_tra_loi"])
    if loi:
        kq["loi"] = loi
    return kq


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    pages = doc_pages(sec.get("pages"))
    if not pages:
        return ("ERROR: kết nối Thống kê Pancake chưa có page nào. Mở trang Kết nối, dán mỗi dòng "
                "`page_id | page_access_token | tên page` rồi lưu.")
    # Giấu MỌI bí mật của kết nối trong mọi câu trả về: một page lỗi có thể nhại lại cả chuỗi cấu hình.
    tat_ca_token = {**{kk: v for kk, v in sec.items() if kk != "pages"},
                    **{f"t{i}": p["token"] for i, p in enumerate(pages)}}
    a = arguments or {}
    if tool == "pancake_tk_ds_page":
        return k.json_ra({"so_page": len(pages), "pages": [{"page_id": p["id"], "ten": p["ten"]} for p in pages]})
    chon = _chon(pages, a.get("page"))
    if not chon:
        return f"ERROR: không có page nào khớp '{a.get('page')}'. Gọi pancake_tk_ds_page để xem danh sách."
    if tool in ("pancake_tk_tong_quan", "pancake_tk_nhan_vien"):
        kq = await (tong_quan if tool == "pancake_tk_tong_quan" else nhan_vien)(chon, a)
        if kq.get("loi") and len(kq["loi"]) >= len(chon) and not (kq.get("tung_page") or kq.get("nhan_vien")):
            return k.giau("ERROR: không page nào đọc được số. " + " | ".join(kq["loi"])[:800], tat_ca_token)
        return k.giau(k.json_ra(kq, 12000), tat_ca_token)
    return f"ERROR: tool '{tool}' không có trong cầu nối Thống kê Pancake"
