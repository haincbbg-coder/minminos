"""HUD màn phụ: trang /hud và /hud/kpi đọc đúng file số liệu, chịu được nhiều kiểu file."""
from _paths import ROOT, SERVER  # noqa: F401
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.hud as hud

brain = Path(tempfile.mkdtemp(prefix="minmin-hud-test-"))
app = FastAPI()
hud.register(app, hud.HudDeps(dashboard_dir=Path(ROOT) / "dashboard", brain_root=lambda b: str(brain)))
client = TestClient(app)

# Trang HUD có thật và trỏ tới script của nó
r = client.get("/hud")
assert r.status_code == 200 and "/static/hud/hud.js" in r.text

# Chưa có file số liệu: bảng rỗng, không lỗi
assert client.get("/hud/kpi").json()["kpis"] == []

# Kiểu 1: danh sách chuẩn
f = brain / "00 - Dashboard" / "minmin-dashboard.json"
f.parent.mkdir(parents=True)
f.write_text(json.dumps({"updated": "2026-09-30T09:00:00", "kpis": [
    {"label": "Đơn mới hôm nay", "value": 414, "delta": "+12%", "tone": "up"},
    {"label": "Chi phí mỗi đơn", "value": 44500, "unit": "đ", "tone": "lạ"},
]}), encoding="utf-8")
j = client.get("/hud/kpi").json()
assert j["updated"] == "2026-09-30T09:00:00"
assert j["kpis"][0] == {"label": "Đơn mới hôm nay", "value": "414", "unit": "", "delta": "+12%", "tone": "up"}
assert j["kpis"][1]["value"] == "44.500" and j["kpis"][1]["tone"] == ""   # tone lạ bị bỏ

# Kiểu 2: dict phẳng
f.write_text(json.dumps({"Doanh thu": 86400000, "cap_nhat": "hôm nay", "_ghi_chu": "x"}), encoding="utf-8")
j = client.get("/hud/kpi").json()
assert [k["label"] for k in j["kpis"]] == ["Doanh thu"] and j["kpis"][0]["value"] == "86.400.000"

# JSON hỏng: báo rõ, không 500
f.write_text("{hỏng", encoding="utf-8")
j = client.get("/hud/kpi").json()
assert j["kpis"] == [] and "JSON" in j["error"]

# Tối đa 8 ô
f.write_text(json.dumps({"kpis": [{"label": f"k{i}", "value": i} for i in range(20)]}), encoding="utf-8")
assert len(client.get("/hud/kpi").json()["kpis"]) == 8

print("ok")
