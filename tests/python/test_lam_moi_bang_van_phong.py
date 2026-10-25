"""Gộp tài khoản trùng người (khác dấu) trên bảng văn phòng + nút Làm mới bảng chạy ngay việc định kỳ."""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.hud as hud

# --- gộp tên trùng ---
r = hud.pancake_office({"staff": [
    {"name": "Khánh Vy", "dept": "sale", "orders": 25, "revenue": 7260000, "yesterday": {"orders": 82, "revenue": 27960000}},
    {"name": "Khanh Vy", "dept": "sale", "orders": 0, "revenue": 0, "yesterday": {"orders": 63, "revenue": 20680000}},
    {"name": "Hồng Cẩm", "dept": "sale", "orders": 39, "revenue": 12810000},
]})
ten = [x["name"] for x in r["sale"]]
assert ten.count("Khánh Vy") == 1 and "Khanh Vy" not in ten and len(ten) == 2, ten
kv = [x for x in r["sale"] if x["name"] == "Khánh Vy"][0]
assert kv["orders"] == 25 and kv["revenue"] == 7260000, kv
assert kv["y"]["orders"] == 145 and kv["y"]["revenue"] == 48640000, kv
assert hud._khoa_ten("  ĐẶNG  Thị  Hà ") == "dang thi ha"
# cùng tên nhưng khác phòng ban thì KHÔNG gộp
r2 = hud.pancake_office({"staff": [{"name": "An", "dept": "sale"}, {"name": "An", "dept": "kho"}]})
assert len(r2["sale"]) == 1 and len(r2["kho"]) == 1


# --- nút làm mới ---
class FakeIO:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class FakeRem:
    def __init__(self, ds): self.ds, self.created, self._io = ds, [], FakeIO()
    def _load(self, brain): return {"reminders": self.ds}
    def _create(self, brain, text, **kw):
        self.created.append((text, kw)); return {"id": "r_new"}


viec = {"id": "r_851", "status": "pending", "cron": "0 8-22 * * *", "text": "Làm mới 3 file ...",
        "label": "Làm mới bảng số liệu văn phòng mỗi giờ", "mode": "task", "chat_id": "web:abc", "muc_quyen": "full"}
khac = {"id": "r_2", "status": "pending", "cron": "0 7 * * *", "text": "nhắc uống nước", "label": "uong nuoc"}
assert hud.tim_viec_lam_moi([khac, viec])["id"] == "r_851"
assert hud.tim_viec_lam_moi([khac]) is None
assert hud.tim_viec_lam_moi([dict(viec, status="done")]) is None

feat = FakeRem([khac, viec])
app = FastAPI()
hud.register_lam_moi(app, hud.HudDeps(dashboard_dir=Path(tempfile.mkdtemp()), brain_root=lambda b: tempfile.mkdtemp(),
                              nhac_hen=lambda: feat))
c = TestClient(app)
j = c.post("/office/lam-moi?brain=brain").json()
assert j["ok"] is True and j["dung_viec_dinh_ky"] is True, j
text, kw = feat.created[0]
assert text == "Làm mới 3 file ..." and kw["mode"] == "task" and kw["delay_min"] == 0 and kw["muc_quyen"] == "full", (text, kw)
assert kw["chat_id"] == "web:abc" and kw["allow_no_channel"] is True
j2 = c.post("/office/lam-moi?brain=brain").json()          # bấm lại ngay: bị chặn, không tạo thêm
assert j2["ok"] is False and j2["cho"] > 0 and len(feat.created) == 1, j2
# không có việc định kỳ: dùng lệnh mặc định
hud._lam_moi_cuoi.clear()
feat2 = FakeRem([khac])
app2 = FastAPI()
hud.register_lam_moi(app2, hud.HudDeps(dashboard_dir=Path(tempfile.mkdtemp()), brain_root=lambda b: "x", nhac_hen=lambda: feat2))
j3 = TestClient(app2).post("/office/lam-moi").json()
assert j3["ok"] and j3["dung_viec_dinh_ky"] is False and "không bịa" in feat2.created[0][0]
print("OK")
