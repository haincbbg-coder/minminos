"""Văn phòng AI 3D: bộ phát sự kiện trong RAM và GET /office/events."""
from _paths import ROOT, SERVER  # noqa: F401
from fastapi import FastAPI
from fastapi.testclient import TestClient

import office_bus
import routes.office as office_routes

office_bus._reset_for_tests()
app = FastAPI()
office_routes.register(app)
c = TestClient(app)

# Rỗng: mốc 0, không sự kiện
d = c.get("/office/events").json()
assert d == {"seq": 0, "reset": False, "events": []}, d

# Phát vài sự kiện, đọc theo mốc
office_bus.emit("run_start", "b1", run="r1", name="Bán hàng")
office_bus.emit("step", "b1", run="r1", agent="An Sales", prev="", task="Kiểm tra tồn kho")
office_bus.emit("step", "b2", run="r9", agent="Người khác", prev="", task="x")     # brain khác
office_bus.emit("tool", "", run="r1", agent="An Sales", tool="mcp__pos__orders")    # không gắn brain: ai cũng thấy
d = c.get("/office/events?since=0&brain=b1").json()
assert d["seq"] == 4 and [e["k"] for e in d["events"]] == ["run_start", "step", "tool"], d
assert d["events"][1]["agent"] == "An Sales" and d["events"][1]["task"] == "Kiểm tra tồn kho"

# Chỉ lấy phần mới
d = c.get("/office/events?since=3&brain=b1").json()
assert [e["k"] for e in d["events"]] == ["tool"]

# Mốc của client lớn hơn mốc server (server vừa khởi động lại): báo reset để đồng bộ lại
assert c.get("/office/events?since=999").json()["reset"] is True

# Chuỗi dài bị cắt, không ném lỗi dù truyền kiểu lạ
office_bus.emit("step", "b1", agent="x" * 500, task=None, n=3)
last = c.get("/office/events?since=4&brain=b1").json()["events"][-1]
assert len(last["agent"]) == 160 and last["n"] == 3

# Vòng đệm giới hạn: không phình mãi
for i in range(700):
    office_bus.emit("tool", "b1", tool=str(i))
assert len(office_bus._BUF) <= 500
print("ok office_bus")
