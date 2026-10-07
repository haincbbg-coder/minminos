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


def pancake_office(raw) -> dict:
    """Nhân viên theo phòng ban + xếp hạng, từ file do kết nối Pancake POS (và Facebook Ads) ghi vào brain.

    Mỗi người: {name, dept, orders, revenue, target?, spend?, roas?}. Xếp hạng theo doanh thu (marketing: theo
    doanh thu quy cho chiến dịch, hoặc ROAS nếu không có). Số liệu để nguyên dạng số; client tự định dạng."""
    rows = (raw.get("staff") or raw.get("nhan_vien") or []) if isinstance(raw, dict) else []
    out = {"sale": [], "kho": [], "marketing": []}
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
        out[r["dept"]].append(r)
    for k, lst in out.items():
        lst.sort(key=lambda r: (-(r["roas"] if k == "marketing" and not r["revenue"] else r["revenue"]), -r["orders"], r["name"]))
        for i, r in enumerate(lst[:24]):
            r["rank"] = i + 1
        out[k] = lst[:24]
    ads = raw.get("ads") if isinstance(raw, dict) and isinstance(raw.get("ads"), dict) else {}
    return {"sale": out["sale"], "kho": out["kho"], "marketing": out["marketing"],
            "ads": {k: _num(v) for k, v in list(ads.items())[:8]}}


def register(app: FastAPI, deps: HudDeps) -> None:
    index = deps.dashboard_dir / "hud" / "index.html"

    @app.get("/hud")
    def hud_page():
        return FileResponse(str(index), media_type="text/html",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/office/pancake")
    def office_pancake(brain: str = Query("brain")):
        root = Path(deps.brain_root(brain))
        for rel in PANCAKE_FILES:
            f = root / rel
            if not f.is_file():
                continue
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return JSONResponse({"error": f"File {rel} không đọc được (JSON hỏng).", "source": rel})
            d = pancake_office(raw)
            upd = (raw.get("updated_at") or raw.get("updated") or raw.get("cap_nhat")) if isinstance(raw, dict) else None
            d.update({"source": rel, "updated": upd or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))})
            return d
        return {"sale": [], "kho": [], "marketing": [], "ads": {}, "source": None}

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
