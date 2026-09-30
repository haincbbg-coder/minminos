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


def _fmt(v):
    if isinstance(v, bool) or v is None:
        return str(v or "")
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.0f}".replace(",", ".")
        return f"{v:g}"
    return str(v)


def normalize(raw) -> list:
    """Nhận nhiều kiểu file khác nhau, trả danh sách {label, value, unit, delta, tone}."""
    items = []
    src = None
    if isinstance(raw, dict):
        src = raw.get("kpis") or raw.get("metrics") or raw.get("chi_so")
        if src is None:
            # dict phẳng: {"Doanh thu hôm nay": 12500000, ...}
            src = [{"label": k, "value": v} for k, v in raw.items()
                   if isinstance(v, (int, float, str)) and not str(k).startswith("_")
                   and k not in ("updated", "updated_at", "cap_nhat", "title")]
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
        items.append({
            "label": str(label)[:40],
            "value": _fmt(it.get("value", it.get("gia_tri", ""))),
            "unit": str(it.get("unit") or it.get("don_vi") or "")[:8],
            "delta": str(it.get("delta") or it.get("so_voi") or "")[:24],
            "tone": it.get("tone") if it.get("tone") in ("up", "down", "warn") else "",
        })
    return items


def register(app: FastAPI, deps: HudDeps) -> None:
    index = deps.dashboard_dir / "hud" / "index.html"

    @app.get("/hud")
    def hud_page():
        return FileResponse(str(index), media_type="text/html",
                            headers={"Cache-Control": "no-cache"})

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
            upd = raw.get("updated") or raw.get("updated_at") or raw.get("cap_nhat") if isinstance(raw, dict) else None
            return {"kpis": normalize(raw), "source": rel,
                    "updated": upd or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))}
        return {"kpis": [], "source": None}
