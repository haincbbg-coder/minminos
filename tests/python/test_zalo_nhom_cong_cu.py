"""Plugin zalo-nhom: ghi chú, nhắc việc, bình chọn, tìm thành viên trong nhóm Zalo.

    python tests/python/test_zalo_nhom_cong_cu.py      (KHÔNG mạng, không npx thật)
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import sys

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        fails.append(name)


spec = importlib.util.spec_from_file_location("zalo_nhom_plugin", ROOT / "system" / "plugins" / "zalo-nhom" / "plugin.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

CHAY = []
TRA = {"v": (0, "{}", "")}
MOT = [{"id": "c1", "label": "Zalo chính", "home": "/state/zalo-a"}]
HAI = MOT + [{"id": "c2", "label": "Zalo phụ", "home": "/state/zalo-b"}]


def gia(conns):
    P._ket_noi_zalo = lambda: list(conns)
    P.shutil.which = lambda n: "/usr/bin/npx" if n == "npx" else None

    async def _cli(home, *lenh):
        CHAY.append((home, list(lenh)))
        v = TRA["v"]
        return v(lenh) if callable(v) else v
    P._cli = _cli


def run(f, args):
    return asyncio.run(f(args, None))


gia(MOT)
r = run(P._note, {"group_id": "7001", "title": "Chốt giá sỉ tháng 10", "pin": True})
check("ghi chú: đúng lệnh, đúng home, có --pin",
      CHAY[-1] == ("/state/zalo-a", ["group", "note-create", "7001", "Chốt giá sỉ tháng 10", "--pin"]), CHAY[-1])
check("ghi chú trả ok", json.loads(r)["ok"])
check("ghi chú thiếu tiêu đề thì từ chối", run(P._note, {"group_id": "7001"}).startswith("ERROR"))

r = run(P._remind, {"thread_id": "7001", "title": "Chốt đơn", "time": "2026-10-05 09:00", "repeat": "weekly"})
lenh = CHAY[-1][1]
check("nhắc việc: đúng lệnh, loại nhóm, lặp tuần", lenh[:3] == ["reminder", "create", "7001"] and "-t" in lenh
      and lenh[lenh.index("-t") + 1] == "1" and lenh[lenh.index("--repeat") + 1] == "weekly", lenh)
check("giờ Việt Nam được đổi sang giờ máy chủ (cùng một thời điểm)",
      P.gio_cho_cli("2026-10-05 09:00") is not None)
import datetime as _d
from zoneinfo import ZoneInfo
_vn = _d.datetime(2026, 10, 5, 9, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
_chuoi = P.gio_cho_cli("2026-10-05 09:00")
_lai = _d.datetime.strptime(_chuoi, "%Y-%m-%d %H:%M").astimezone()
check("đổi giờ đúng: quy về máy chủ rồi đọc lại vẫn là 9h sáng Việt Nam", _lai == _vn, (_chuoi, _lai, _vn))
check("giờ sai định dạng bị từ chối", run(P._remind, {"thread_id": "1", "title": "x", "time": "mai 9h"}).startswith("ERROR"))
check("repeat lạ bị từ chối", run(P._remind, {"thread_id": "1", "title": "x", "repeat": "hourly"}).startswith("ERROR"))

r = run(P._poll, {"group_id": "7001", "question": "Họp lúc nào?", "options": ["9h", "14h"], "multi": True})
check("bình chọn: đúng lệnh", CHAY[-1][1][:3] == ["poll", "create", "7001"] and "--multi" in CHAY[-1][1]
      and CHAY[-1][1][4:6] == ["9h", "14h"], CHAY[-1])
check("bình chọn một lựa chọn bị từ chối", run(P._poll, {"group_id": "7001", "question": "q", "options": ["a"]}).startswith("ERROR"))
check("id nhóm có chữ lạ bị lọc về số (không tiêm cờ CLI)",
      run(P._note, {"group_id": "--help 7001", "title": "x"}) and CHAY[-1][1][2] == "7001")

run(P._note, {"group_id": "7001", "title": "--pin hack"})
check("tiêu đề bắt đầu bằng gạch không thành cờ CLI", CHAY[-1][1][3] == "pin hack", CHAY[-1])

# tìm thành viên
def _gia_cli(lenh):
    if lenh[1] == "members":
        return 0, json.dumps({"111": 1, "222": 1, "333": 1}), ""
    return 0, json.dumps([{"userId": "111", "displayName": "Lan Anh"}, {"userId": "222", "displayName": "Lan Hương"},
                          {"userId": "333", "displayName": "Minh Đức"}]), ""
TRA["v"] = _gia_cli
r = json.loads(run(P._find, {"group_id": "7001", "name": "lan"}))
check("tìm 'lan' ra hai người và báo mơ hồ", len(r["matches"]) == 2 and r["luu_y"], r)
r = json.loads(run(P._find, {"group_id": "7001", "name": "duc"}))
check("tìm không dấu ra đúng một người", r["matches"] == [{"user_id": "333", "name": "Minh Đức"}], r)

# nhiều tài khoản thì hỏi lại
gia(HAI)
check("nhiều tài khoản Zalo mà không nêu connection_id thì hỏi lại, không đoán",
      run(P._note, {"group_id": "7001", "title": "x"}).startswith("ERROR"))
gia([])
check("chưa đấu Zalo thì báo rõ", "Chưa đấu" in run(P._poll, {"group_id": "1", "question": "q", "options": ["a", "b"]}))

check("không có em dash", "—" not in (ROOT / "system" / "plugins" / "zalo-nhom" / "plugin.py").read_text(encoding="utf-8"))
if fails:
    print(f"\nFAIL: {fails}"); sys.exit(1)
print("\nOK - test_zalo_nhom_cong_cu: tất cả pass")
