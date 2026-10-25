"""HUD màn phụ của MinMin: trang `/hud` và số liệu kinh doanh `/hud/kpi`.

Trang HUD là file tĩnh trong dashboard/hud/; nó tự nối vào WebSocket `/ws` sẵn có để thấy
MinMin đang nghe, nghĩ, gọi công cụ nào và trả lời gì. Module này chỉ thêm hai đường:

- `GET /hud`      trả trang HUD (đi qua `_auth_guard` của main như mọi request HTTP khác).
- `GET /hud/kpi`  đọc file số liệu dashboard trong brain và chuẩn hoá về dạng HUD hiểu.

Không ghi gì, không gọi dịch vụ ngoài. Thiếu file số liệu thì trả `{"kpis": []}` để HUD ẩn
bảng đi, không báo lỗi.
"""
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse

# Các chỗ MinMin hay đặt file số liệu (theo thứ tự ưu tiên).
KPI_FILES = (
    "00 - Dashboard/minmin-dashboard.json",
    "00 - Dashboard/hud-kpi.json",
    "Dashboard/minmin-dashboard.json",
)
MAX_KPI = 8


@dataclass
class HudDeps:
    dashboard_dir: Path                 # thư mục dashboard/ (chứa hud/index.html)
    brain_root: Callable[[str], str]    # tên/đường dẫn brain -> thư mục gốc
    nhac_hen: Callable[[], object] = lambda: None   # reminders_feature, lấy trễ (tạo sau ở main)


def _so_vn(x: float, le: int = 1) -> str:
    """12500.5 -> '12.500,5' (dấu chấm nghìn, dấu phẩy thập phân kiểu Việt)."""
    s = f"{x:,.{le}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return s.rstrip("0").rstrip(",") if "," in s else s


def _fmt(v, unit: str = ""):
    """Cùng cách viết số với bảng điều hành MinMin (minmin-dashboard.js)."""
    if isinstance(v, bool) or v is None:
        return str(v or ""), unit
    if not isinstance(v, (int, float)):
        return str(v), unit
    if unit in ("đ", "VND"):
        a = abs(v)
        if a >= 1e9:
            return _so_vn(v / 1e9, 2), "tỷ"
        if a >= 1e6:
            return _so_vn(v / 1e6, 1), "tr"
        if a >= 1e3:
            return _so_vn(v / 1e3, 1), "k"
        return _so_vn(v, 0), "đ"
    if unit == "%":
        return _so_vn(v, 1), "%"
    if unit == "x":
        return _so_vn(v, 2), "x"
    return _so_vn(v, 2 if abs(v) < 100 and v != int(v) else 0), unit


def normalize(raw) -> list:
    """Nhận nhiều kiểu file khác nhau, trả danh sách {label, value, unit, delta, tone}.

    Kiểu chuẩn của MinMin (minmin-dashboard.example): kpis = [{label, value, unit, delta_pct,
    compare, lower_is_better}]. Cũng nhận delta/tone viết sẵn, hoặc một dict phẳng tên -> số.
    """
    items = []
    src = None
    if isinstance(raw, dict):
        src = raw.get("kpis") or raw.get("metrics") or raw.get("chi_so")
        if src is None:
            # dict phẳng: {"Doanh thu hôm nay": 12500000, ...}
            src = [{"label": k, "value": v} for k, v in raw.items()
                   if isinstance(v, (int, float, str)) and not str(k).startswith("_")
                   and k not in ("updated", "updated_at", "cap_nhat", "title", "source", "period_label")]
        elif isinstance(src, dict):
            src = [{"label": k, "value": v} for k, v in src.items()]
    elif isinstance(raw, list):
        src = raw
    for it in (src or [])[:MAX_KPI]:
        if not isinstance(it, dict):
            continue
        label = it.get("label") or it.get("name") or it.get("ten") or ""
        if not label:
            continue
        value, unit = _fmt(it.get("value", it.get("gia_tri", "")), str(it.get("unit") or it.get("don_vi") or ""))
        delta = str(it.get("delta") or it.get("so_voi") or "")
        tone = it.get("tone") if it.get("tone") in ("up", "down", "warn") else ""
        dp = it.get("delta_pct")
        if not delta and isinstance(dp, (int, float)):
            delta = ("+" if dp >= 0 else "-") + _so_vn(abs(dp), 1) + "%" + (" " + str(it.get("compare")) if it.get("compare") else "")
            tot = dp >= 0 if not it.get("lower_is_better") else dp < 0
            tone = tone or ("up" if tot else "down")
        items.append({"label": str(label)[:40], "value": value, "unit": unit[:8], "delta": delta[:32], "tone": tone})
    return items


def alerts_of(raw) -> list:
    """Khối "Cần chú ý" của bảng điều hành: [{level, text}] -> tối đa 5 dòng."""
    out = []
    if isinstance(raw, dict):
        for a in (raw.get("alerts") or [])[:5]:
            if isinstance(a, dict) and a.get("text"):
                lv = a.get("level") if a.get("level") in ("good", "warning", "serious", "critical", "info") else "info"
                out.append({"level": lv, "text": str(a["text"])[:140]})
    return out


def _lines(v, n=4, w=120) -> list:
    """Danh sách dòng chữ ngắn (kế hoạch, đề xuất): nhận list chuỗi, list dict {text}, hoặc một chuỗi nhiều dòng."""
    if isinstance(v, str):
        v = [x for x in v.splitlines() if x.strip()]
    out = []
    for it in (v or [])[:n] if isinstance(v, list) else []:
        t = it.get("text") or it.get("title") or it.get("ten") if isinstance(it, dict) else it
        if t:
            out.append(str(t).strip()[:w])
    return out


def targets_of(raw) -> list:
    """Chỉ tiêu: [{label, target, current, unit}] -> thêm pct (0..100+) để vẽ thanh tiến độ."""
    out = []
    src = (raw.get("targets") or raw.get("chi_tieu") or raw.get("goals")) if isinstance(raw, dict) else None
    for it in (src or [])[:5] if isinstance(src, list) else []:
        if not isinstance(it, dict):
            continue
        label = it.get("label") or it.get("name") or it.get("ten")
        tg, cur = it.get("target", it.get("muc_tieu")), it.get("current", it.get("hien_tai", it.get("value")))
        if not label or not isinstance(tg, (int, float)) or isinstance(tg, bool) or not tg:
            continue
        cur = cur if isinstance(cur, (int, float)) and not isinstance(cur, bool) else 0
        unit = str(it.get("unit") or it.get("don_vi") or "")
        tv, tu = _fmt(tg, unit)
        cv, cu = _fmt(cur, unit)
        out.append({"label": str(label)[:36], "target": tv + (" " + tu if tu else ""), "current": cv + (" " + cu if cu else ""),
                    "pct": round(cur / tg * 100)})
    return out


PANCAKE_FILES = ("00 - Dashboard/pancake-office.json", "Dashboard/pancake-office.json")
_DEPT = (("marketing", ("marketing", "mkt", "ads", "quang cao", "quảng cáo")),
         ("kho", ("kho", "warehouse", "stock")),
         ("sale", ("sale", "sales", "ban hang", "bán hàng", "cskh", "chot don", "chốt đơn")))


def _dept(v) -> str:
    t = str(v or "").strip().lower()
    for key, hints in _DEPT:
        if any(h in t for h in hints):
            return key
    return "sale"


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def _khoa_ten(name: str) -> str:
    """'Khánh Vy' và 'Khanh  vy' ra cùng một khoá: bỏ dấu tiếng Việt, đ -> d, hạ chữ, gộp khoảng trắng."""
    t = unicodedata.normalize("NFD", str(name or "").replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def _gop_trung(r: dict, cu: dict) -> None:
    """Gộp dòng `r` (cùng người, khác cách viết tên) vào dòng `cu`: cộng đơn, doanh thu, chi phí; giữ tên có dấu."""
    if any(ord(c) > 127 for c in r["name"]) and not any(ord(c) > 127 for c in cu["name"]):
        cu["name"] = r["name"]
    for k in ("orders", "revenue", "spend", "packed"):
        cu[k] = cu.get(k, 0) + r.get(k, 0)
    for k in ("target", "roas"):
        cu[k] = cu.get(k) or r.get(k, 0)
    if r.get("month_orders") is not None:
        cu["month_orders"] = (cu.get("month_orders") or 0) + r["month_orders"]
    if isinstance(r.get("y"), dict):
        y = cu.setdefault("y", {})
        for k, v in r["y"].items():
            y[k] = (y.get(k) or 0) + v if k != "roas" else (y.get(k) or v)


def pancake_office(raw) -> dict:
    """Nhân viên theo phòng ban + xếp hạng, từ file do kết nối Pancake POS (và Facebook Ads) ghi vào brain.

    Mỗi người: {name, dept, orders, revenue, target?, spend?, roas?}. Xếp hạng theo doanh thu (marketing: theo
    doanh thu quy cho chiến dịch, hoặc ROAS nếu không có). Số liệu để nguyên dạng số; client tự định dạng."""
    rows = (raw.get("staff") or raw.get("nhan_vien") or []) if isinstance(raw, dict) else []
    out = {"sale": [], "kho": [], "marketing": []}
    gop: dict = {}
    for it in rows[:80] if isinstance(rows, list) else []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("ten") or "").strip()[:40]
        if not name:
            continue
        r = {"name": name, "dept": _dept(it.get("dept") or it.get("phong") or it.get("role")), "role": str(it.get("role") or "")[:30],
             "orders": _num(it.get("orders") or it.get("don")), "revenue": _num(it.get("revenue") or it.get("doanh_thu")),
             "target": _num(it.get("target") or it.get("chi_tieu")), "spend": _num(it.get("spend") or it.get("chi_phi")),
             "roas": _num(it.get("roas")), "packed": _num(it.get("packed") or it.get("dong_goi"))}
        mo = it.get("month_orders", it.get("don_thang"))
        if mo is not None:
            r["month_orders"] = _num(mo)      # marketing: đơn tính lương trong tháng của các mã người đó phụ trách
        y = it.get("yesterday") or it.get("hom_qua")
        if isinstance(y, dict):
            r["y"] = {"orders": _num(y.get("orders") or y.get("don")), "revenue": _num(y.get("revenue") or y.get("doanh_thu")),
                      "spend": _num(y.get("spend") or y.get("chi_phi")), "roas": _num(y.get("roas")), "packed": _num(y.get("packed") or y.get("dong_goi"))}
            if y.get("month_orders") is not None:
                r["y"]["month_orders"] = _num(y.get("month_orders"))
        cu = gop.get((r["dept"], _khoa_ten(name)))
        if cu is not None:
            _gop_trung(r, cu)          # cùng một người nhưng Pancake có hai tài khoản khác dấu
            continue
        gop[(r["dept"], _khoa_ten(name))] = r
        out[r["dept"]].append(r)
    for k, lst in out.items():
        if k == "marketing":
            lst.sort(key=lambda r: (-r.get("month_orders", -1), -(r["roas"] if not r["revenue"] else r["revenue"]), -r["orders"], r["name"]))
        else:
            lst.sort(key=lambda r: (-r["revenue"], -r["orders"], r["name"]))
        for i, r in enumerate(lst[:24]):
            r["rank"] = i + 1
        out[k] = lst[:24]
    ads = raw.get("ads") if isinstance(raw, dict) and isinstance(raw.get("ads"), dict) else {}
    ay = raw.get("ads_yesterday") if isinstance(raw, dict) and isinstance(raw.get("ads_yesterday"), dict) else None
    res = {"sale": out["sale"], "kho": out["kho"], "marketing": out["marketing"],
           "ads": {k: _num(v) for k, v in list(ads.items())[:8]}}
    if ay is not None:
        res["ads_yesterday"] = {k: _num(v) for k, v in list(ay.items())[:8]}
    return res


PANCAKE_CFG = "00 - Dashboard/pancake-config.json"
# Bảng Marketing đọc từ file riêng để đơn tính lương (MinMin tính cho từng người) không bị đồng bộ Pancake ghi đè
MKT_FILES = ("00 - Dashboard/marketing-office.json", "Dashboard/marketing-office.json")
MKT_MAC_DINH = ("Tiến", "Phúc")
PANCAKE_API = "https://pos.pages.fm/api/v1"
PANCAKE_TTL = 120   # giây: lâu hơn mức này mới gọi Pancake lại


def _pc_get(path: str, params: dict):
    url = PANCAKE_API + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as r:   # noqa: S310 - URL cố định của Pancake
        return json.loads(r.read().decode("utf-8", "replace"))


def _pc_list(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in ("data", "users", "orders", "items"):
            if isinstance(raw.get(k), list):
                return raw[k]
    return []


def dong_bo_pancake(root: Path) -> str:
    """Kéo nhân viên và doanh thu hôm nay từ Pancake POS rồi ghi pancake-office.json. Trả lỗi (rỗng nếu ổn).

    Cần file 00 - Dashboard/pancake-config.json: {"api_key": "...", "shop_id": 123,
    "marketing": ["Tên người"], "kho": ["Tên người"]} (người không nằm trong hai danh sách là Sale).
    Chưa kiểm chứng với tài khoản thật: parse theo tài liệu Open API v1 của Pancake POS, thiếu trường thì bỏ qua."""
    cfgf = root / PANCAKE_CFG
    try:
        cfg = json.loads(cfgf.read_text(encoding="utf-8"))
        key, shop = str(cfg["api_key"]), str(cfg["shop_id"])
    except Exception:
        return "Thiếu hoặc sai file pancake-config.json (cần api_key và shop_id)."
    now = time.time()
    tm = time.localtime(now)
    day0 = int(time.mktime((tm.tm_year, tm.tm_mon, tm.tm_mday, 0, 0, 0, 0, 0, -1)))
    def gom(t0, t1):
        agg = {}
        for page in range(1, 21):
            batch = _pc_list(_pc_get(f"/shops/{shop}/orders", {"api_key": key, "startDateTime": t0, "endDateTime": t1,
                                                              "page_size": 100, "page_number": page}))
            for o in batch:
                if not isinstance(o, dict) or o.get("status") in (6, 7):
                    continue
                who = o.get("assigning_seller") or o.get("creator") or {}
                n = str((who.get("name") if isinstance(who, dict) else who) or "").strip()
                if not n:
                    continue
                a = agg.setdefault(n, {"orders": 0, "revenue": 0})
                a["orders"] += 1
                a["revenue"] += _num(o.get("total_price") or o.get("cod") or 0)
            if len(batch) < 100:
                break
        return agg
    try:
        users = _pc_list(_pc_get(f"/shops/{shop}/users", {"api_key": key}))
        names = set()
        for u in users:
            if isinstance(u, dict):
                n = str(u.get("name") or (u.get("user") or {}).get("name") or "").strip()
                if n:
                    names.add(n)
        hom_nay = gom(day0, int(now))
        hom_qua = gom(day0 - 86400, day0 - 1)       # hôm qua: số đã chốt, bảng "HÔM QUA" đọc từ đây
        agg = {n: hom_nay.get(n, {"orders": 0, "revenue": 0}) for n in names | set(hom_nay) | set(hom_qua)}
    except Exception as e:  # mạng, khoá sai, API đổi
        return f"Pancake: {type(e).__name__}: {str(e)[:120]}"
    mk, kho = {str(x).strip().lower() for x in cfg.get("marketing") or []}, {str(x).strip().lower() for x in cfg.get("kho") or []}
    staff = [{"name": n, "dept": "marketing" if n.lower() in mk else "kho" if n.lower() in kho else "sale",
              "orders": a["orders"], "revenue": a["revenue"], "packed": a["orders"] if n.lower() in kho else 0,
              "yesterday": {"orders": hom_qua.get(n, {}).get("orders", 0), "revenue": hom_qua.get(n, {}).get("revenue", 0),
                            "packed": hom_qua.get(n, {}).get("orders", 0) if n.lower() in kho else 0}} for n, a in agg.items()]
    out = {"updated": time.strftime("%Y-%m-%d %H:%M", tm), "staff": staff}
    (root / PANCAKE_FILES[0]).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return ""


def _marketing_rows(root: Path) -> list:
    """Hàng bảng Marketing: từ marketing-office.json nếu có; chưa có thì hiện sẵn Tiến và Phúc (chưa có số)."""
    for rel in MKT_FILES:
        f = root / rel
        if f.is_file():
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    raw = {"staff": raw}
                rows = raw.get("staff") or raw.get("nhan_vien") or []
                for it in rows:
                    if isinstance(it, dict):
                        it["dept"] = "marketing"
                return pancake_office({"staff": rows})["marketing"]
            except Exception:
                break
    return pancake_office({"staff": [{"name": n, "dept": "marketing"} for n in MKT_MAC_DINH]})["marketing"]


LAM_MOI_CHO = 180          # giây: bấm "Làm mới bảng" liên tiếp trong khoảng này bị chặn, tránh chạy chồng
LAM_MOI_TU_KHOA = "bang so lieu van phong"   # tên việc định kỳ làm mới bảng (so sánh đã bỏ dấu)
LAM_MOI_MAC_DINH = (
    "Làm mới ngay các bảng số liệu văn phòng 3D. Ghi đè 3 file trong '00 - Dashboard', mục nào thiếu nguồn thì "
    "để trống, không bịa số: (1) minmin-dashboard.json từ Pancake POS và Meta Ads; (2) pancake-office.json: "
    "nhân viên, đơn và doanh thu hôm nay và hôm qua, bỏ đơn huỷ; (3) marketing-office.json: Phúc và Tiến, chi phí ads "
    "và đơn tính lương tháng này từ báo cáo tính lương marketing (không có thì để null). Xong báo lại số đã ghi.")
_lam_moi_cuoi: dict = {}


def tim_viec_lam_moi(rems: list) -> dict | None:
    """Việc định kỳ đang chờ có tên chứa 'bảng số liệu văn phòng' (người dùng đã dặn MinMin tạo)."""
    for r in rems:
        if r.get("status") != "pending" or not (r.get("cron") or r.get("repeat_min")):
            continue
        if LAM_MOI_TU_KHOA in _khoa_ten(f"{r.get('label') or ''} {r.get('text') or ''}"):
            return r
    return None


def register(app: FastAPI, deps: HudDeps) -> None:
    index = deps.dashboard_dir / "hud" / "index.html"

    @app.get("/hud")
    def hud_page():
        return FileResponse(str(index), media_type="text/html",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/office/pancake")
    def office_pancake(brain: str = Query("brain")):
        root = Path(deps.brain_root(brain))
        loi = ""
        f0 = root / PANCAKE_FILES[0]
        if (root / PANCAKE_CFG).is_file() and (not f0.is_file() or time.time() - f0.stat().st_mtime > PANCAKE_TTL):
            loi = dong_bo_pancake(root)
        for rel in PANCAKE_FILES:
            f = root / rel
            if not f.is_file():
                continue
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return JSONResponse({"error": f"File {rel} không đọc được (JSON hỏng).", "source": rel})
            d = pancake_office(raw)
            d["marketing"] = _marketing_rows(root)
            upd = (raw.get("updated_at") or raw.get("updated") or raw.get("cap_nhat")) if isinstance(raw, dict) else None
            if loi:
                d["error"] = loi
            d.update({"source": rel, "updated": upd or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))})
            return d
        return {"sale": [], "kho": [], "marketing": _marketing_rows(root), "ads": {}, "source": None, "error": loi}

    @app.get("/hud/kpi")
    def hud_kpi(brain: str = Query("brain")):
        root = Path(deps.brain_root(brain))
        for rel in KPI_FILES:
            f = root / rel
            if not f.is_file():
                continue
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return JSONResponse({"kpis": [], "error": f"File {rel} không đọc được (JSON hỏng)."})
            upd = (raw.get("updated_at") or raw.get("updated") or raw.get("cap_nhat")) if isinstance(raw, dict) else None
            info = raw if isinstance(raw, dict) else {}
            return {"kpis": normalize(raw), "alerts": alerts_of(raw), "source": rel,
                    "company": str(info.get("company") or info.get("cong_ty") or info.get("name") or "")[:60],
                    "plan": _lines(info.get("plan") or info.get("ke_hoach")), "targets": targets_of(raw),
                    "proposals": _lines(info.get("proposals") or info.get("de_xuat") or info.get("suggestions")),
                    "updated": upd or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))}
        return {"kpis": [], "source": None}


def register_lam_moi(app: FastAPI, deps: HudDeps) -> None:
    """Đăng ký riêng ở ĐUÔI main.py để không đẩy thứ tự các route có sẵn (route_table.json khoá thứ tự)."""
    @app.post("/office/lam-moi")
    async def office_lam_moi(brain: str = Query("brain")):
        """Nút "Làm mới bảng": chạy NGAY một bản của việc định kỳ làm mới số liệu (cùng nội dung, cùng mức quyền)."""
        feat = deps.nhac_hen()
        if feat is None:
            return {"ok": False, "error": "Chưa có bộ hẹn giờ để chạy việc làm mới."}
        now = time.time()
        con_lai = int(LAM_MOI_CHO - (now - _lam_moi_cuoi.get(brain, 0)))
        if con_lai > 0:
            return {"ok": False, "cho": con_lai, "error": f"Vừa làm mới xong, chờ {con_lai} giây rồi bấm lại."}
        try:
            from reminders import muc_quyen_cua
            nguon = tim_viec_lam_moi(feat._load(brain).get("reminders", []))
            text = (nguon or {}).get("text") or LAM_MOI_MAC_DINH
            async with feat._io:
                rem = feat._create(brain, text, delay_min=0, mode="task",
                                   muc_quyen=muc_quyen_cua(nguon) if nguon else None,
                                   chat_id=(nguon or {}).get("chat_id", ""), allow_no_channel=True,
                                   label="Làm mới bảng văn phòng (bấm tay)", created_by="office")
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        _lam_moi_cuoi[brain] = now
        return {"ok": True, "id": rem["id"], "dung_viec_dinh_ky": bool(nguon)}
