"""Trang Tổng quan: gom số liệu trong tiến trình cho `GET /tong-quan?brain=<brain>`.

Hợp đồng dữ liệu nằm ở plans/tong-quan/PLAN.md (giữ đúng tên khoá). Mỗi khối mang `trang_thai`:
"ok" | "chua_noi" | "loi" (kèm `loi`: câu ngắn đã giấu bí mật). Nguyên tắc:

- Mỗi nguồn là MỘT hàm riêng bọc try/except. Nguồn lỗi chỉ làm khối của nó thành "loi", không
  bao giờ làm hỏng cả response.
- Nguồn chưa nối thì "chua_noi", tuyệt đối không trả số 0 giả cho thứ chưa đo được.
- Không import `main` ở đầu module (main import ngược module này để đăng ký route). Mọi thứ cần
  từ main đi qua `TongQuanDeps`, nhờ vậy test giả lập được từng phụ thuộc.
- Chỉ đọc. Tác dụng phụ duy nhất là đồng bộ Pancake POS theo TTL, y như GET /office/pancake.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

TOI_DA_MUC = 12               # khối "Cần xử lý" hiện tối đa ngần này mục
HAN_PANCAKE_CHAT = 15.0       # giây chờ Thống kê Pancake (nhiều page gọi song song)
HAN_DONG_BO_POS = 20.0        # giây chờ đồng bộ Pancake POS; quá thì trả số cũ nếu có
_THU_TU_MUC = {"bad": 0, "warn": 1, "info": 2}

_RE_THAM_SO = re.compile(r"((?:api_key|access_token|page_access_token|token|key|secret)=)[^&\s'\"]+", re.I)
_RE_CHUOI_DAI = re.compile(r"[A-Za-z0-9_\-\.]{24,}")


@dataclass
class TongQuanDeps:
    """Phụ thuộc lấy từ main. Mặc định là bản rỗng an toàn để test chỉ cần điền cái mình cần."""
    brain_root: Callable[[str], str]
    brain_key: Callable[[str], str] = lambda b: b
    nhac_hen: Callable[[], Any] = lambda: None          # reminders_feature (tạo sau trong main)
    loop: Callable[[], Any] = lambda: None              # loop_feature
    ket_noi_hien_co: Callable[[], list] = lambda: []    # main._ket_noi_hien_co
    providers_view: Callable[[], list] = lambda: []     # main._providers_view(cfgmod.read_settings())
    read_settings: Callable[[], dict] = lambda: {}
    bi_mat_them: list = field(default_factory=list)     # chuỗi bí mật thêm để giấu (test)


# ---------------------------------------------------------------- tiện ích

def giau_loi(e, bi_mat=()) -> str:
    """Câu lỗi ngắn, đã giấu bí mật: giá trị đã biết, tham số kiểu token=..., và mọi chuỗi dài
    giống token (>= 24 ký tự liền). Thà che nhầm một đoạn vô hại còn hơn lọt một token."""
    s = f"{type(e).__name__}: {e}" if isinstance(e, BaseException) else str(e or "")
    for v in sorted({str(x) for x in bi_mat if x}, key=len, reverse=True):
        if len(v) >= 6:
            s = s.replace(v, "***")
    s = _RE_THAM_SO.sub(r"\1***", s)
    s = _RE_CHUOI_DAI.sub("***", s)
    s = " ".join(s.split())
    return s[:160]


def _so(v) -> int:
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _bay_gio_iso() -> str:
    try:
        import localefmt
        return datetime.now(localefmt.tz()).isoformat(timespec="seconds")
    except Exception:
        return datetime.now().astimezone().isoformat(timespec="seconds")


def _muc(id_, nguon, muc_do, tieu_de, mo_ta, nut) -> dict:
    return {"id": str(id_), "nguon": nguon, "muc_do": muc_do,
            "tieu_de": str(tieu_de or "")[:120], "mo_ta": str(mo_ta or "")[:200], "nut": nut}


def _nut_trang(trang, **kw) -> dict:
    return {"nhan": "Mở", "loai": "trang", "trang": trang, **kw}


# ---------------------------------------------------------------- Cần xử lý: từng nguồn

def nguon_kanban(deps: TongQuanDeps, brain: str) -> list:
    import tasks
    feat = tasks.current()
    if feat is None:            # hàng đợi chưa khởi tạo (test nạp lẻ, hoặc app đang dựng): bỏ êm
        return []
    view = feat.board_view(brain)
    ra = []
    for t in (view.get("operations") or {}).get("attention") or []:
        tid = str(t.get("id") or "")
        ten = str(t.get("title") or "Việc nền")
        if t.get("status") == "review":
            ra.append(_muc(f"kanban:{tid}", "kanban", "warn", ten, "Việc nền đã xong, chờ bạn duyệt kết quả.",
                           [{"nhan": "Duyệt", "loai": "duyet_kanban", "task_id": tid},
                            _nut_trang("kanban", task_id=tid)]))
            continue
        kind = str(t.get("block_kind") or "")
        if kind == "needs_input":
            qa = (t.get("metadata") or {}).get("qa") or []
            cuoi = qa[-1] if qa and isinstance(qa[-1], dict) else {}
            hoi = str(cuoi.get("q") or t.get("block_reason") or "").strip()
            mo_ta = "Đang hỏi bạn: " + " ".join(hoi.split())[:150]
        elif kind == "capability":
            mo_ta = "Chờ cấp quyền thao tác ra ngoài"
        else:
            mo_ta = giau_loi(t.get("block_reason") or kind or "Việc đang kẹt", deps.bi_mat_them)[:150]
        ra.append(_muc(f"kanban:{tid}", "kanban", "warn", ten, mo_ta, [_nut_trang("kanban", task_id=tid)]))
    return ra


def nguon_doi_social(deps: TongQuanDeps, brain: str) -> list:
    import routes.doi_social as rds
    if rds.ly_do_chan() is not None:        # chưa mở khoá hoặc chưa đồng ý điều khoản: không có gì để báo
        return []
    import doi_social_v2
    ra = []
    for i, m in enumerate(doi_social_v2.tong_quan(ngay=14).get("can_xu_ly") or []):
        loai = str(m.get("loai") or "")
        muc_do = "bad" if loai in ("nick", "dot_loi", "may") else "warn"
        phu = m.get("nick_id") or m.get("dot_id") or i
        ra.append(_muc(f"doi_social:{loai}:{phu}", "doi_social", muc_do, m.get("tieu_de"), m.get("chi_tiet"),
                       [{"nhan": "Mở", "loai": "link", "url": "/apps/doi-social/" + str(m.get("den") or "")}]))
    try:
        import doi_social_fanpage as fp
        ds_cb = fp.canh_bao_mo()
    except Exception:
        ds_cb = []      # kho Fanpage chưa dựng bảng (chưa dùng Fanpage): phần Đội Social chính vẫn hiện
    for cb in ds_cb:
        muc = str(cb.get("muc") or "")
        if muc not in ("chan", "nang"):
            continue
        ra.append(_muc(f"doi_social:fp:{cb.get('id')}", "doi_social", "bad" if muc == "chan" else "warn",
                       cb.get("tieu_de") or "Cảnh báo Fanpage", cb.get("cach_sua") or cb.get("chi_tiet"),
                       [{"nhan": "Mở", "loai": "link", "url": "/apps/doi-social/#/fp-canh-bao"}]))
    return ra


def nguon_ket_noi(deps: TongQuanDeps, brain: str) -> list:
    import connect_health
    import mcp_store
    snap = connect_health.snapshot()
    ra = []
    for c in mcp_store.list_connections():
        if not c.get("enabled"):
            continue
        rec = snap.get(c.get("id"))
        if not rec or rec.get("ok") is not False:     # chưa kiểm hoặc đang ổn
            continue
        ten = c.get("label") or c.get("name") or c.get("connector_id") or "Kết nối"
        if rec.get("kind") == "auth":
            ra.append(_muc(f"ket_noi:{c['id']}", "ket_noi", "bad", f"Kết nối {ten} hỏng", "Cần đăng nhập lại",
                           [_nut_trang("mcp")]))
        else:
            ra.append(_muc(f"ket_noi:{c['id']}", "ket_noi", "warn", f"Kết nối {ten} hỏng",
                           giau_loi(rec.get("message") or "Không phản hồi", deps.bi_mat_them),
                           [_nut_trang("mcp")]))
    for ten, rec in (connect_health.engines_snapshot() or {}).items():
        if rec.get("ok") is False:
            ra.append(_muc(f"ket_noi:nao:{ten}", "ket_noi", "bad", "Bộ não AI chưa dùng được",
                           giau_loi(rec.get("message") or ten, deps.bi_mat_them), [_nut_trang("models")]))
    return ra


def nguon_nhac_hen(deps: TongQuanDeps, brain: str) -> list:
    feat = deps.nhac_hen()
    if feat is None:
        return []
    tq = feat.tong_quan(brain) or {}
    ra = []
    for r in tq.get("hong_ds") or []:
        ra.append(_muc(f"nhac_hen:{r.get('id')}", "nhac_hen", "warn", f"Nhắc hẹn hỏng: {r.get('ten') or ''}",
                       giau_loi(r.get("loi") or "Lần chạy gần nhất lỗi", deps.bi_mat_them),
                       [_nut_trang("selfimprove")]))
    return ra


def nguon_loop(deps: TongQuanDeps, brain: str) -> list:
    feat = deps.loop()
    if feat is None:
        return []
    st = feat.read_state(brain) or {}
    ra = []
    for lp in feat.list_loops(brain):
        ly_do = (st.get(lp.get("slug")) or {}).get("auto_paused_reason")
        if ly_do:
            ra.append(_muc(f"loop:{lp.get('slug')}", "loop", "warn", f"Loop tự dừng: {lp.get('name') or lp.get('slug')}",
                           giau_loi(ly_do, deps.bi_mat_them), [_nut_trang("selfimprove")]))
    return ra


def nguon_workflow(deps: TongQuanDeps, brain: str) -> list:
    import workflow_runs
    ra = []
    for r in workflow_runs.get_store().gan_nhat(deps.brain_key(brain), status="waiting", limit=10):
        ra.append(_muc(f"workflow:{r.get('id')}", "workflow", "warn",
                       f"Quy trình '{r.get('name') or r.get('slug')}' chờ bạn duyệt",
                       "Quy trình dừng ở một bước cần duyệt trước khi chạy tiếp.",
                       [_nut_trang("workspace", slug=str(r.get("slug") or ""))]))
    return ra


NGUON_CAN_XU_LY = (
    ("kanban", "Bảng việc", nguon_kanban),
    ("doi_social", "Đội Social", nguon_doi_social),
    ("ket_noi", "Kết nối", nguon_ket_noi),
    ("nhac_hen", "Nhắc hẹn", nguon_nhac_hen),
    ("loop", "Loop", nguon_loop),
    ("workflow", "Quy trình", nguon_workflow),
)


async def khoi_can_xu_ly(deps: TongQuanDeps, brain: str) -> dict:
    async def mot(ten, ham):
        try:
            return ten, await asyncio.to_thread(ham, deps, brain), None
        except Exception as e:
            return ten, [], giau_loi(e, deps.bi_mat_them)

    # Gọi qua globals() để test thay được từng hàm nguồn bằng monkeypatch tên trong module.
    g = globals()
    kq = await asyncio.gather(*(mot(nhan, g.get(ham.__name__, ham)) for _, nhan, ham in NGUON_CAN_XU_LY))
    muc, loi_nguon = [], []
    for nhan, ds, loi in kq:
        muc.extend(ds)
        if loi:
            loi_nguon.append(f"{nhan}: {loi}")
    muc.sort(key=lambda m: _THU_TU_MUC.get(m.get("muc_do"), 3))     # sort ổn định: giữ thứ tự trong nguồn
    out = {"trang_thai": "ok", "muc": muc[:TOI_DA_MUC], "loi_nguon": loi_nguon}
    if len(loi_nguon) == len(NGUON_CAN_XU_LY):
        out["trang_thai"] = "loi"
        out["loi"] = "Không đọc được nguồn nào."
    return out


# ---------------------------------------------------------------- Hoàn tất cài đặt

def _da_co(ket_noi: list, id_can: str) -> bool:
    import ket_noi_can
    return ket_noi_can.doi_chieu([{"id": id_can}], ket_noi)[0].get("trang_thai") == "da_co"


def _buoc_pos(deps, root: Path) -> bool:
    import routes.hud as hud
    return (root / hud.PANCAKE_CFG).is_file() or _da_co(deps.ket_noi_hien_co(), "pancake")


def _buoc_ads(deps, root: Path) -> bool:
    import mcp_store
    import oauth_mcp
    for c in mcp_store.list_connections():
        if c.get("connector_id") == "meta-ads-graph" and c.get("enabled") and oauth_mcp.status(c["id"]).get("connected"):
            return True
    # Mẫu "facebook-ads" của ket_noi_can khớp cả chữ "facebook" trần (Fanpage cũng dính), nên chỉ
    # đưa vào những kết nối có chữ "ads" trong tên. meta-ads-graph đã soi đăng nhập thật ở trên.
    hien_co = [h for h in deps.ket_noi_hien_co()
               if "ads" in str(h.get("ten", "")).lower() and "meta-ads-graph" not in str(h.get("ten", ""))]
    return _da_co(hien_co, "facebook-ads")


def _buoc_zalo(deps, root: Path) -> bool:
    import mcp_store
    if any(c.get("connector_id") == "zalo" and c.get("enabled") for c in mcp_store.list_connections()):
        return True
    z = (deps.read_settings() or {}).get("zalo_bot") or {}
    return bool(z.get("enabled") and z.get("token"))


def _buoc_telegram(deps, root: Path) -> bool:
    t = (deps.read_settings() or {}).get("telegram") or {}
    return bool(t.get("enabled") and t.get("token") and t.get("chat_id"))


def _bien_dong_da_cai() -> bool:
    import bien_dong
    # KHÔNG gọi cai_dat_cong_khai(): nó tự tạo mã webhook (ghi file) khi chưa có.
    return bien_dong.file_cai_dat().exists() and bool(bien_dong._cai_dat().get("khoa"))


def _buoc_biendong(deps, root: Path) -> bool:
    return _bien_dong_da_cai()


def _buoc_nao(deps, root: Path) -> bool:
    # Đã chọn bộ não chính VÀ không engine nào đang báo hỏng. Thiếu vế sau thì thanh cài đặt báo
    # "xong" trong khi khối Cần xử lý ngay dưới lại báo "Bộ não AI chưa dùng được" (thấy khi chụp màn).
    if not any(p.get("is_main") and p.get("configured") for p in deps.providers_view() or []):
        return False
    import connect_health
    return not any(rec.get("ok") is False for rec in (connect_health.engines_snapshot() or {}).values())


BUOC_CAI_DAT = (
    ("pos", "Pancake POS", "mcp", _buoc_pos),
    ("ads", "Facebook Ads", "mcp", _buoc_ads),
    ("zalo", "Zalo", "mcp", _buoc_zalo),
    ("telegram", "Telegram", "channels", _buoc_telegram),
    ("biendong", "Biến động số dư", "biendong", _buoc_biendong),
    ("nao", "Bộ não AI", "models", _buoc_nao),
)


def khoi_cai_dat(deps: TongQuanDeps, brain: str) -> dict:
    root = Path(deps.brain_root(brain))
    buoc = []
    for id_, ten, trang, ham in BUOC_CAI_DAT:
        try:
            xong = bool(ham(deps, root))
        except Exception:
            xong = False         # không xác định được thì coi như chưa xong, nút đi nối vẫn đúng
        buoc.append({"id": id_, "ten": ten, "xong": xong, "trang": trang})
    return {"buoc": buoc, "xong": sum(1 for b in buoc if b["xong"]), "tong": len(buoc)}


# ---------------------------------------------------------------- Tiền vào hôm nay

def khoi_tien_vao(deps: TongQuanDeps, brain: str) -> dict:
    try:
        import bien_dong
        if not _bien_dong_da_cai():
            return {"trang_thai": "chua_noi"}
        ds = bien_dong.danh_sach(limit=500, chi_vao=True, tu_ngay=bien_dong.dau_hom_nay(), co_thu_nghiem=False)
        t = bien_dong.tong(ds)
        return {"trang_thai": "ok", "tong": int(t.get("tong_vao") or 0), "so_gd": int(t.get("so_gd_vao") or 0),
                "gan_nhat": [{"mo_ta": str(g.get("mo_ta") or "")[:60], "so_tien": int(g.get("so_tien") or 0),
                              "luc": int(g.get("luc") or 0)} for g in ds[:3]]}
    except Exception as e:
        return {"trang_thai": "loi", "loi": giau_loi(e, deps.bi_mat_them)}


# ---------------------------------------------------------------- Chi phí AI hôm nay

def khoi_chi_phi_ai(deps: TongQuanDeps, brain: str) -> dict:
    try:
        import usage_index
        s = usage_index.summary(period="today")
        theo = {x.get("key"): x for x in (s.get("by_provider") or [])}
        that = float((theo.get("api") or {}).get("cost") or 0)
        kpi = s.get("kpi") or {}
        quy_doi = max(0.0, float(kpi.get("cost_est") or 0) - that)
        return {"trang_thai": "ok", "usd_that": round(that, 4), "usd_quy_doi": round(quy_doi, 2),
                "luot": int(kpi.get("turns") or 0)}
    except Exception as e:
        return {"trang_thai": "loi", "loi": giau_loi(e, deps.bi_mat_them)}


# ---------------------------------------------------------------- Số chính từ Pancake POS

def _cong_staff(raw) -> tuple:
    """(đơn hôm nay, doanh thu hôm nay, đơn hôm qua | None, doanh thu hôm qua | None)."""
    rows = (raw.get("staff") or raw.get("nhan_vien") or []) if isinstance(raw, dict) else []
    don = dt = 0
    don_q = dt_q = 0
    co_qua = False
    for it in rows if isinstance(rows, list) else []:
        if not isinstance(it, dict):
            continue
        don += _so(it.get("orders") if it.get("orders") is not None else it.get("don"))
        dt += _so(it.get("revenue") if it.get("revenue") is not None else it.get("doanh_thu"))
        y = it.get("yesterday") if isinstance(it.get("yesterday"), dict) else it.get("hom_qua")
        if isinstance(y, dict):
            co_qua = True
            don_q += _so(y.get("orders") if y.get("orders") is not None else y.get("don"))
            dt_q += _so(y.get("revenue") if y.get("revenue") is not None else y.get("doanh_thu"))
    return don, dt, (don_q if co_qua else None), (dt_q if co_qua else None)


def _chi_ads(raw) -> Optional[int]:
    ads = raw.get("ads") if isinstance(raw, dict) and isinstance(raw.get("ads"), dict) else {}
    for k in ("spend", "chi_phi", "chi_tieu"):
        v = ads.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v)
    return None


async def khoi_pos(deps: TongQuanDeps, brain: str) -> dict:
    """{doanh_thu, don_chot, chi_ads}: cùng nguồn file pancake-office.json như GET /office/pancake."""
    import routes.hud as hud
    root = Path(deps.brain_root(brain))
    cfg = root / hud.PANCAKE_CFG
    bi_mat = list(deps.bi_mat_them)
    loi_dong_bo = ""
    try:
        if cfg.is_file():
            try:
                c = json.loads(cfg.read_text(encoding="utf-8"))
                bi_mat.append(str(c.get("api_key") or ""))
            except Exception:
                pass
            f0 = root / hud.PANCAKE_FILES[0]
            if not f0.is_file() or time.time() - f0.stat().st_mtime > hud.PANCAKE_TTL:
                try:
                    loi_dong_bo = await asyncio.wait_for(asyncio.to_thread(hud.dong_bo_pancake, root), HAN_DONG_BO_POS)
                except asyncio.TimeoutError:
                    loi_dong_bo = "Pancake POS phản hồi chậm, đang dùng số lần đồng bộ trước."
        raw = None
        for rel in hud.PANCAKE_FILES:
            f = root / rel
            if f.is_file():
                raw = json.loads(f.read_text(encoding="utf-8"))
                break
        if raw is None:
            if not cfg.is_file():
                cn = {"trang_thai": "chua_noi"}
                return {"doanh_thu": dict(cn), "don_chot": dict(cn), "chi_ads": dict(cn)}
            loi = {"trang_thai": "loi", "loi": giau_loi(loi_dong_bo or "Chưa đồng bộ được Pancake POS.", bi_mat)}
            return {"doanh_thu": dict(loi), "don_chot": dict(loi), "chi_ads": {"trang_thai": "chua_noi"}}
        don, dt, don_q, dt_q = _cong_staff(raw)
        dthu = {"trang_thai": "ok", "hom_nay": dt, "hom_qua": dt_q}
        dchot = {"trang_thai": "ok", "hom_nay": don, "hom_qua": don_q}
        if loi_dong_bo:          # số cũ vẫn đúng là số thật của lần trước; kèm lời nhắn để trang biết
            ghi = giau_loi(loi_dong_bo, bi_mat)
            dthu["ghi_chu"] = dchot["ghi_chu"] = ghi
        spend = _chi_ads(raw)
        ads = {"trang_thai": "ok", "hom_nay": spend} if spend is not None else {"trang_thai": "chua_noi"}
        return {"doanh_thu": dthu, "don_chot": dchot, "chi_ads": ads}
    except Exception as e:
        loi = {"trang_thai": "loi", "loi": giau_loi(e, bi_mat)}
        return {"doanh_thu": dict(loi), "don_chot": dict(loi), "chi_ads": {"trang_thai": "chua_noi"}}


# ---------------------------------------------------------------- Thống kê hội thoại Pancake

async def khoi_pancake_chat(deps: TongQuanDeps, brain: str) -> dict:
    """{chot_hoi_thoai, theo_page} từ kết nối "pancake-thong-ke" (mọi kết nối bật, gộp page)."""
    bi_mat = list(deps.bi_mat_them)
    try:
        import mcp_store
        import pancake_chat_mcp as pk
        conns = await asyncio.to_thread(mcp_store.resolved, True)
        pages, thay = [], set()
        for c in conns:
            if c.get("connector_id") != "pancake-thong-ke":
                continue
            sec = c.get("secrets") or {}
            bi_mat.extend(str(v) for v in sec.values() if v)
            for p in pk.doc_pages(sec.get("pages")):
                bi_mat.append(p["token"])
                if p["id"] not in thay:
                    thay.add(p["id"])
                    pages.append(p)
        if not pages:
            cn = {"trang_thai": "chua_noi"}
            return {"chot_hoi_thoai": dict(cn), "theo_page": dict(cn)}
        kq = await asyncio.wait_for(pk.tong_quan(pages, {}), HAN_PANCAKE_CHAT)
        if kq.get("loi") and not kq.get("tung_page"):
            loi = {"trang_thai": "loi", "loi": giau_loi("Không page nào đọc được số. " + " | ".join(kq["loi"]), bi_mat)}
            return {"chot_hoi_thoai": dict(loi), "theo_page": dict(loi)}
        t = kq.get("tong_tat_ca_page") or {}
        chot = {"trang_thai": "ok", "ty_le": t.get("ty_le_chot"), "khach": _so(t.get("khach_nhan_tin")),
                "sdt": _so(t.get("so_dien_thoai_moi"))}
        dong = [{"page": str(r.get("page") or r.get("page_id") or ""), "khach": _so(r.get("khach_nhan_tin")),
                 "sdt": _so(r.get("so_dien_thoai_moi")), "don": _so(r.get("don_chot")), "ty_le": r.get("ty_le_chot")}
                for r in kq.get("tung_page") or []]
        theo = {"trang_thai": "ok", "dong": dong}
        if kq.get("loi"):        # vài page lỗi, page khác vẫn có số
            theo["ghi_chu"] = chot["ghi_chu"] = giau_loi(" | ".join(kq["loi"]), bi_mat)
        return {"chot_hoi_thoai": chot, "theo_page": theo}
    except asyncio.TimeoutError:
        loi = {"trang_thai": "loi", "loi": "Pancake phản hồi quá chậm, thử lại sau."}
        return {"chot_hoi_thoai": dict(loi), "theo_page": dict(loi)}
    except Exception as e:
        loi = {"trang_thai": "loi", "loi": giau_loi(e, bi_mat)}
        return {"chot_hoi_thoai": dict(loi), "theo_page": dict(loi)}


# ---------------------------------------------------------------- ráp

def _loi_khoi(e, deps) -> dict:
    return {"trang_thai": "loi", "loi": giau_loi(e, deps.bi_mat_them)}


async def gom(brain: str, deps: TongQuanDeps) -> dict:
    """Ráp toàn bộ trang. Các nguồn chạy song song; nguồn chặn luồng chạy trong to_thread."""
    g = globals()     # tra tên lúc chạy để test monkeypatch được từng khối

    async def an_toan(coro_fn, mac_dinh):
        try:
            return await coro_fn()
        except Exception as e:
            return mac_dinh(e)

    cai_dat, can, tien, ai, pos, chat = await asyncio.gather(
        an_toan(lambda: asyncio.to_thread(g["khoi_cai_dat"], deps, brain),
                lambda e: {"buoc": [], "xong": 0, "tong": len(BUOC_CAI_DAT), "loi": giau_loi(e, deps.bi_mat_them)}),
        an_toan(lambda: g["khoi_can_xu_ly"](deps, brain),
                lambda e: {**_loi_khoi(e, deps), "muc": [], "loi_nguon": []}),
        an_toan(lambda: asyncio.to_thread(g["khoi_tien_vao"], deps, brain), lambda e: _loi_khoi(e, deps)),
        an_toan(lambda: asyncio.to_thread(g["khoi_chi_phi_ai"], deps, brain), lambda e: _loi_khoi(e, deps)),
        an_toan(lambda: g["khoi_pos"](deps, brain),
                lambda e: {"doanh_thu": _loi_khoi(e, deps), "don_chot": _loi_khoi(e, deps),
                           "chi_ads": {"trang_thai": "chua_noi"}}),
        an_toan(lambda: g["khoi_pancake_chat"](deps, brain),
                lambda e: {"chot_hoi_thoai": _loi_khoi(e, deps), "theo_page": _loi_khoi(e, deps)}),
    )
    return {
        "luc": _bay_gio_iso(),
        "cai_dat": cai_dat,
        "can_xu_ly": can,
        "tien_vao": tien,
        "chi_phi_ai": ai,
        "so_chinh": {"doanh_thu": pos["doanh_thu"], "don_chot": pos["don_chot"],
                     "chot_hoi_thoai": chat["chot_hoi_thoai"], "chi_ads": pos["chi_ads"]},
        "theo_page": chat["theo_page"],
    }


def register(app, deps: TongQuanDeps) -> None:
    """Đăng ký ở ĐUÔI main.py (route_table.json khoá thứ tự route)."""
    from fastapi import Query

    @app.get("/tong-quan")
    async def tong_quan_trang(brain: str = Query("brain")):
        """Số liệu trang Tổng quan. Chỉ đọc; nguồn lỗi chỉ làm khối của nó thành "loi"."""
        return await gom(brain, deps)
