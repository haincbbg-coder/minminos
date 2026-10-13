"""Việc hẹn giờ một lần gặp lỗi tạm thời thì tự thử lại, hết lượt mới báo (26.10.152).

    python tests/run.py reminder_thu_lai
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-thulai-state-")
import reminders  # noqa: E402
import tong_hop_tuan  # noqa: E402

fails = []
sent = []
brain = Path(tempfile.mkdtemp(prefix="javis-thulai-brain-"))


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


def atomic_write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


async def fake_send(chat_id, text):
    sent.append(text)
    return True, ""


deps = reminders.RemindersDeps(brain_root=lambda _b: str(brain), atomic_write_text=atomic_write,
                               send_telegram=fake_send, build_system_prompt=lambda _b: "",
                               aux_model=lambda: None, safe_tools=[], readonly_tools=[],
                               scheduler_brains=lambda: [])
f = reminders.RemindersFeature(deps)


def luu(rem):
    atomic_write(f._path(str(brain)), json.dumps({"reminders": [rem], "updated": 0}))


def doc():
    return json.loads(f._path(str(brain)).read_text(encoding="utf-8"))["reminders"][0]


async def task_hong(_b, _t, _m=""):
    return "", "engine timeout"


async def main():
    f._run_task = task_hong
    rem = {"id": "r1", "mode": "task", "text": "x", "label": "Việc", "chat_id": "1", "status": "pending", "due_at": 0}
    luu(rem)
    await f._fire(str(brain), rem)
    r = doc()
    check("lần 1 lỗi: hẹn lại, im lặng", r["status"] == "pending" and r["attempts"] == 1 and not sent, (r, sent))
    check("hẹn lại sau vài phút", r["due_at"] > reminders._now() + 200, r["due_at"])
    await f._fire(str(brain), r)
    r = doc()
    check("lần 2 lỗi: vẫn hẹn lại", r["status"] == "pending" and r["attempts"] == 2 and not sent, r)
    await f._fire(str(brain), r)
    r = doc()
    check("hết lượt: failed và báo ra ngoài", r["status"] == "failed" and len(sent) == 1 and "engine timeout" in sent[0], (r, sent))
    check("đếm chuỗi hỏng", r["fail_streak"] == 3, r.get("fail_streak"))

    # việc lặp theo lịch không thử lại: lần tới tự đến
    sent.clear()
    cr = {"id": "r2", "mode": "task", "text": "x", "label": "Cron", "chat_id": "1", "status": "pending",
          "due_at": 0, "cron": "0 7 * * *"}
    luu(cr)
    await f._fire(str(brain), cr)
    r = doc()
    check("cron lỗi: báo ngay, không thử lại", len(sent) == 1 and r.get("attempts") in (None, 0) and r["status"] == "pending", (r, sent))

    # task thành công sau lỗi: xoá chuỗi hỏng
    async def task_ok(_b, _t, _m=""):
        return "xong", ""
    f._run_task = task_ok
    sent.clear()
    cr2 = dict(doc(), fail_streak=3)
    luu(cr2)
    await f._fire(str(brain), cr2)
    check("chạy ổn thì về 0", doc()["fail_streak"] == 0)

    # tổng quan
    luu({"id": "r3", "mode": "task", "text": "Việc A", "status": "failed", "error": "lỗi gì đó", "fail_streak": 3, "fired_at": reminders._now()})
    tq = f.tong_quan(str(brain))
    check("tổng quan đếm việc hỏng", tq["hong"] == 1 and tq["hong_ds"][0]["ten"] == "Việc A", tq)

    # bản tổng hợp tuần nhắc việc hỏng
    (brain / "memory").mkdir(exist_ok=True)
    v = tong_hop_tuan.xay(brain)
    check("tổng hợp tuần có việc hẹn giờ hỏng", "Việc A" in v, v)

    # nhắc notify gửi hỏng thì gửi lại
    async def send_fail(_c, _t):
        return False, "mạng"
    deps.send_telegram = send_fail
    n = {"id": "r4", "mode": "notify", "text": "uống nước", "chat_id": "1", "status": "pending", "due_at": 0}
    luu(n)
    await f._fire(str(brain), n)
    check("notify gửi hỏng: hẹn gửi lại", doc()["status"] == "pending" and doc()["attempts"] == 1, doc())


asyncio.run(main())
if fails:
    print("\nĐỎ:", fails)
    raise SystemExit(1)
print("\nxanh")
