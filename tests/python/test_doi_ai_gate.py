# -*- coding: utf-8 -*-
"""Đội AI: job = chuỗi bước trên Kanban, bước GATE chờ chủ duyệt (plans/doi-ai-gate, phase 01).

    python tests/run.py doi_ai_gate

Phủ: dựng job đúng deps/capability/mức quyền; GATE không bao giờ được giao cho worker; tới lượt
thì GATE chờ duyệt và notify_gate được gọi đúng một lần dù housekeep chạy bao nhiêu vòng;
duyet / sua / tu_choi; jobs_view đúng hình dạng và trạng thái; kiểm đầu vào; việc lẻ không job
chạy như cũ; route /kanban/job* qua TestClient. KHÔNG chạy engine thật: `_execute` bị thay.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-doiai-"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI                 # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402

from tasks import TasksDeps, TasksFeature   # noqa: E402

FAILS = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        FAILS.append(name)


def _atomic(path, text):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


async def _workflow(*_a, **_k):
    if False:
        yield {}


def _feature(notify=True):
    tmp = Path(tempfile.mkdtemp(prefix="javis-doiai-t-"))
    brain = tmp / "Brain"
    brain.mkdir()
    bao, reports = [], []

    async def report(chat_id, text, **kw):
        reports.append({"chat_id": chat_id, "text": text, **kw})
        return True

    def notify_gate(view, gate):
        bao.append((view, gate))

    deps = TasksDeps(
        brain_root=lambda value: str(brain),
        atomic_write_text=_atomic,
        execute_workflow=_workflow,
        workflows_dir=lambda b: brain / "workflows",
        build_system_prompt=lambda b: "system",
        aux_model=lambda: None,
        safe_tools=["Read", "Write"],
        state_dir=tmp / "state",
        scheduler_brains=lambda: [str(brain)],
        report=report,
    )
    if notify:
        deps.notify_gate = notify_gate
    f = TasksFeature(deps)
    return f, str(brain), bao, reports


STEPS = [
    {"title": "Soạn bài", "intent": "soạn 3 bài nháp", "capability": "files"},
    {"title": "Chọn ảnh", "intent": "chọn ảnh cho bài", "capability": "files"},
    {"title": "Duyệt mẫu", "gate": True, "gate_mo_ta": "Duyệt mẫu trước khi đăng"},
    {"title": "Đăng bài", "intent": "đăng bài đã duyệt"},
]


def _run(f, tid, result="Đã làm xong.", seen=None):
    """Nhận và chạy một lượt worker với kết quả cho sẵn (không engine thật)."""
    async def execute(task):
        if seen is not None:
            seen.append(task)
        return result, "", False, {"provider": "test"}

    f._execute = execute
    claimed = f.store.claim(tid, "w-test")
    if not claimed:
        return None
    asyncio.run(f._run_worker(claimed, "w-test"))
    return f.store.get_task(tid)


def _buoc(f, job_id):
    return f._cac_buoc(job_id)


def _view(f, brain, job_id):
    return next(j for j in f.jobs_view(brain)["jobs"] if j["id"] == job_id)


# ----------------------------------------------------------------------
def test_tao_job():
    f, brain, _, _ = _feature()
    jid = f.create_job(brain, "Bài fanpage tuần này", "social", STEPS, chat_id="web:s1")
    b = _buoc(f, jid)
    check("tạo đủ 4 bước", len(b) == 4, len(b))
    check("deps nối tiếp", all(b[i]["deps"] == [b[i - 1]["id"]] for i in range(1, 4))
          and b[0]["deps"] == [], [x["deps"] for x in b])
    check("job_id + job_step trên mọi bước",
          all(x["job_id"] == jid and x["metadata"]["job_step"] == i + 1 for i, x in enumerate(b)))
    check("bước thường giữ capability, mode auto",
          b[0]["capability"] == "files" and b[1]["capability"] == "files"
          and b[0]["execution_mode"] == "auto")
    g = b[2]
    check("GATE: capability gate + metadata gate",
          g["capability"] == "gate" and g["metadata"]["gate"]["mo_ta"] == "Duyệt mẫu trước khi đăng"
          and g["metadata"]["gate"]["mo_khoa"] == [b[3]["id"]], g["metadata"])
    check("bước sau GATE: external-write ở mức auto",
          b[3]["capability"] == "external-write" and b[3]["execution_mode"] == "auto")
    check("chat_id đi xuống từng bước", all(x["chat_id"] == "web:s1" for x in b))
    check("bước đầu ready, còn lại todo",
          b[0]["status"] == "ready" and all(x["status"] == "todo" for x in b[1:]),
          [x["status"] for x in b])
    v = _view(f, brain, jid)
    check("jobs_view: hình dạng job_view",
          set(v) == {"id", "title", "doi", "status", "created_at", "chat_id", "buoc", "gate_cho"}
          and v["status"] == "dang_chay" and v["gate_cho"] is None and v["doi"] == "social", v)
    check("jobs_view: hình dạng bước",
          set(v["buoc"][0]) == {"task_id", "title", "loai", "status", "ket_qua_ngan", "block_reason"}
          and [x["loai"] for x in v["buoc"]] == ["buoc", "buoc", "gate", "buoc"])
    # Tiêu đề bước trùng việc lẻ đang mở không được gộp vào việc lẻ đó.
    le = f.enqueue(brain, "Soạn bài", "việc lẻ", capability="files")
    jid2 = f.create_job(brain, "Job 2", "khac", STEPS[:2])
    check("bước job không gộp vào việc lẻ trùng tên", _buoc(f, jid2)[0]["id"] != le)
    f.store.close()


def test_kiem_dau_vao():
    f, brain, _, _ = _feature()
    cases = {
        "gate đầu": [{"title": "G", "gate": True}, {"title": "A"}],
        "gate cuối": [{"title": "A"}, {"title": "G", "gate": True}],
        "hai gate liền": [{"title": "A"}, {"title": "G", "gate": True},
                          {"title": "G2", "gate": True}, {"title": "B"}],
        "rỗng": [],
        "quá 12 bước": [{"title": f"B{i}"} for i in range(13)],
        "tiêu đề bước trống": [{"title": "  - "}],
        "JSON hỏng": "[{",
    }
    for ten, steps in cases.items():
        try:
            f.create_job(brain, "Job", "khac", steps)
            check(f"từ chối {ten}", False)
        except ValueError:
            check(f"từ chối {ten}", True)
    try:
        f.create_job(brain, "   ", "khac", [{"title": "A"}])
        check("từ chối tiêu đề job trống", False)
    except ValueError:
        check("từ chối tiêu đề job trống", True)
    check("không đẻ job rác khi từ chối", f.jobs_view(brain)["jobs"] == [])
    jid = f.create_job(brain, "Job", "xyz", json.dumps([{"title": "A"}]))
    check("steps dạng JSON + đội lạ -> khac", _view(f, brain, jid)["doi"] == "khac")
    f.store.close()


def test_gate_va_duyet():
    f, brain, bao, reports = _feature()
    f.store.set_orchestration(brain, "auto")
    jid = f.create_job(brain, "Bài fanpage", "social", STEPS)
    b = _buoc(f, jid)
    g, sau = b[2]["id"], b[3]["id"]

    check("GATE không claim được khi còn chờ deps", f.store.claim(g, "w") is None)
    _run(f, b[0]["id"], "Bản nháp 1, 2, 3")
    f._housekeep(brain)
    seen = []
    _run(f, b[1]["id"], "Ảnh: a.jpg, b.jpg", seen=seen)
    check("bước job nhận bối cảnh bước trước", "Bản nháp 1, 2, 3" in f._ngu_canh_job(seen[0]))
    check("metadata job_step sống qua lần chạy",
          f.store.get_task(b[1]["id"])["metadata"].get("job_step") == 2)
    for _ in range(4):
        f._housekeep(brain)
        asyncio.run(f.tick([brain]))
    gt = f.store.get_task(g)
    check("GATE -> blocked/gate", gt["status"] == "blocked" and gt["block_kind"] == "gate"
          and gt["block_reason"] == "Duyệt mẫu trước khi đăng", (gt["status"], gt["block_kind"]))
    check("notify_gate đúng 1 lần dù housekeep/tick nhiều vòng", len(bao) == 1, len(bao))
    f.jobs_view(brain)
    check("đọc jobs_view không báo thêm", len(bao) == 1, len(bao))
    check("notify_gate nhận job_view + gate_task",
          bao and bao[0][0]["id"] == jid and bao[0][0]["status"] == "cho_duyet"
          and bao[0][1]["id"] == g)
    check("_report không báo GATE lần hai",
          not any("Duyệt mẫu" in r["text"] for r in reports), [r["text"][:60] for r in reports])
    check("GATE không bao giờ claim được", f.store.claim(g, "w") is None)
    check("GATE không phải ứng viên dispatcher",
          (f.store.next_candidate(brain) or {}).get("id") != g)
    v = _view(f, brain, jid)
    check("job cho_duyet + gate_cho đủ khoá",
          v["status"] == "cho_duyet" and v["gate_cho"]
          and v["gate_cho"]["task_id"] == g and v["gate_cho"]["mo_khoa"] == [sau]
          and v["gate_cho"]["xem_truoc"] == "Ảnh: a.jpg, b.jpg", v)
    check("bước sau GATE vẫn chờ", f.store.get_task(sau)["status"] == "todo")

    r = f.gate_action(brain, jid, "duyet")
    st = f.store.get_task(sau)
    check("duyet -> ok + dang_chay", r == {"ok": True, "status": "dang_chay"}, r)
    check("duyet -> GATE done", f.store.get_task(g)["status"] == "done")
    check("duyet -> bước sau full + ready", st["execution_mode"] == "full" and st["status"] == "ready",
          (st["execution_mode"], st["status"]))
    ev = [e["event_type"] for e in f.store.list_events(g)]
    check("event gate_duyet có source",
          "gate_duyet" in ev and any(e["event_type"] == "gate_duyet"
                                     and e["metadata"].get("source") == "dashboard"
                                     for e in f.store.list_events(g)))
    n_grant = sum(1 for e in f.store.list_events(sau) if e["event_type"] == "operator_grant")
    r2 = f.gate_action(brain, jid, "duyet", source="telegram")
    n_grant2 = sum(1 for e in f.store.list_events(sau) if e["event_type"] == "operator_grant")
    check("duyet lần 2: ok, không cấp quyền thêm", r2["ok"] and n_grant == n_grant2 == 1,
          (r2, n_grant, n_grant2))
    check("không ai bị báo lại sau duyệt", len(bao) == 1)

    _run(f, sau, "Đã đăng 3 bài")
    check("bước sau chạy thật (không bị chặn quyền)", f.store.get_task(sau)["status"] == "done")
    check("job xong", _view(f, brain, jid)["status"] == "xong")
    f.store.close()


def test_sua():
    f, brain, bao, _ = _feature()
    jid = f.create_job(brain, "Job sửa", "social", STEPS)
    b = _buoc(f, jid)
    g, truoc = b[2]["id"], b[1]["id"]
    _run(f, b[0]["id"])
    f._housekeep(brain)
    _run(f, truoc, "Ảnh bản 1")
    f._housekeep(brain)
    check("chờ duyệt lần 1 báo 1 lần", len(bao) == 1)
    check("sua thiếu ghi chú bị từ chối", f.gate_action(brain, jid, "sua")["ok"] is False)
    r = f.gate_action(brain, jid, "sua", note="Đổi ảnh sáng hơn")
    pt = f.store.get_task(truoc)
    check("sua -> ok + dang_chay", r == {"ok": True, "status": "dang_chay"}, r)
    check("bước trước về ready, intent có ghi chú",
          pt["status"] == "ready" and "Chủ yêu cầu sửa: Đổi ảnh sáng hơn" in pt["intent"]
          and pt["metadata"]["sua"][-1]["note"] == "Đổi ảnh sáng hơn", (pt["status"], pt["intent"]))
    gt = f.store.get_task(g)
    check("GATE về todo, xoá cờ đã báo",
          gt["status"] == "todo" and not gt["metadata"]["gate"].get("da_bao"))
    check("event gate_sua", any(e["event_type"] == "gate_sua" for e in f.store.list_events(g)))
    f._housekeep(brain)
    check("GATE chưa mở lại khi bước trước chưa chạy lại", f.store.get_task(g)["status"] == "todo")
    _run(f, truoc, "Ảnh bản 2")
    check("ghi chú sửa sống qua lần chạy lại",
          f.store.get_task(truoc)["metadata"].get("sua"))
    f._housekeep(brain)
    f._housekeep(brain)
    check("chờ duyệt lần 2 báo lại đúng 1 lần", len(bao) == 2, len(bao))
    check("xem_truoc là bản mới", _view(f, brain, jid)["gate_cho"]["xem_truoc"] == "Ảnh bản 2")
    f.store.close()


def test_tu_choi_va_trang_thai():
    f, brain, bao, _ = _feature()
    jid = f.create_job(brain, "Job từ chối", "ads", STEPS)
    b = _buoc(f, jid)
    _run(f, b[0]["id"])
    f._housekeep(brain)
    _run(f, b[1]["id"])
    f._housekeep(brain)
    r = f.gate_action(brain, jid, "tu_choi", source="telegram")
    check("tu_choi -> ok + dung", r == {"ok": True, "status": "dung"}, r)
    st = [f.store.get_task(x["id"])["status"] for x in b]
    check("GATE và bước còn lại cancelled, bước xong giữ nguyên",
          st == ["done", "done", "cancelled", "cancelled"], st)
    check("event gate_tu_choi source telegram",
          any(e["event_type"] == "gate_tu_choi" and e["metadata"].get("source") == "telegram"
              for e in f.store.list_events(b[2]["id"])))
    check("duyet sau tu_choi bị từ chối", f.gate_action(brain, jid, "duyet")["ok"] is False)
    check("jobs_view: dung", _view(f, brain, jid)["status"] == "dung")

    # ket: một bước thường bị chặn
    jid2 = f.create_job(brain, "Job kẹt", "khac", STEPS)
    b2 = _buoc(f, jid2)
    claimed = f.store.claim(b2[0]["id"], "w")
    f.store.block(b2[0]["id"], "w", "transient", "lỗi engine")
    check("bước lỗi -> job ket", _view(f, brain, jid2)["status"] == "ket")
    # GATE bị dọn khỏi bảng mà chưa ai duyệt: không được mở khoá bước sau.
    jid3 = f.create_job(brain, "Job dọn", "khac", STEPS)
    b3 = _buoc(f, jid3)
    _run(f, b3[0]["id"])
    f._housekeep(brain)
    _run(f, b3[1]["id"])
    f._housekeep(brain)
    f.store.archive_by_status(brain, ("blocked",))
    f._housekeep(brain)
    check("GATE archive tay không mở khoá bước sau",
          f.store.get_task(b3[3]["id"])["status"] == "todo")
    check("GATE archive tay -> job ket", _view(f, brain, jid3)["status"] == "ket")
    check("job không tồn tại -> ok false + loi",
          f.gate_action(brain, "j_khong_co", "duyet") == {"ok": False, "status": "",
                                                        "loi": "Không tìm thấy job"})
    check("action lạ -> ok false", f.gate_action(brain, jid2, "xoa")["ok"] is False)
    _ = claimed
    f.store.close()


def test_khong_notify_van_cho_duyet_khi_off():
    f, brain, _, _ = _feature(notify=False)
    check("bảng mặc định off", f.store.board_mode(brain) == "off")
    jid = f.create_job(brain, "Job off", "khac", [
        {"title": "A", "capability": "files"}, {"title": "G", "gate": True}, {"title": "B"}])
    b = _buoc(f, jid)
    _run(f, b[0]["id"])                      # chủ bấm chạy tay
    v = _view(f, brain, jid)                 # dispatcher chưa quét vòng nào
    check("off + chưa nối notify: GATE vẫn sang chờ duyệt khi đọc jobs_view",
          v["status"] == "cho_duyet" and v["gate_cho"] is not None, v["status"])
    check("chưa nối notify thì không bật cờ đã báo",
          not f.store.get_task(b[1]["id"])["metadata"]["gate"].get("da_bao"))
    f.store.close()


def test_viec_le_nhu_cu():
    f, brain, bao, _ = _feature()
    a = f.enqueue(brain, "Việc lẻ A", "làm A", capability="files")
    c = f.enqueue(brain, "Việc lẻ C", "làm C", deps=[a], capability="files")
    check("việc lẻ không có job_id", f.store.get_task(a)["job_id"] is None)
    _run(f, a)
    check("việc lẻ phụ thuộc vẫn được thăng ready", f.store.get_task(c)["status"] == "ready")
    _run(f, c)
    check("việc lẻ xong", f.store.get_task(c)["status"] == "done")
    x = f.enqueue(brain, "Việc ngoài", "gửi tin cho khách", capability="external-write")
    f.store.move(x, "ready")
    _run(f, x)
    t = f.store.get_task(x)
    check("external-write lẻ vẫn bị chặn quyền như cũ",
          t["status"] == "blocked" and t["block_kind"] == "capability")
    check("không có job nào", f.jobs_view(brain)["jobs"] == [] and not bao)
    f.store.close()


def test_route():
    f, brain, bao, _ = _feature()
    app = FastAPI()
    app.include_router(f.router)
    c = TestClient(app)
    tm = c.get("/kanban/job-templates").json()
    ids = {m["id"] for m in tm["mau"]}
    check("job-templates có đủ 3 mẫu", {"social-bai-fanpage", "ads-len-camp", "tu-ke-buoc"} <= ids, ids)
    for m in tm["mau"]:
        if m["buoc"]:
            try:
                f._kiem_buoc(m["buoc"])
                ok = True
            except ValueError as e:
                ok = str(e)
            check(f"mẫu {m['id']} hợp lệ", ok is True, ok)
    r = c.post("/kanban/job", data={"brain": "brain", "mau": "ads-len-camp",
                                    "muc_tieu": "Váy lụa {mới}", "chat_id": "web:x"}).json()
    check("POST /kanban/job theo mẫu", r.get("ok") and r.get("job_id"), r)
    v = c.get("/kanban/jobs", params={"brain": "brain"}).json()
    j = next(x for x in v["jobs"] if x["id"] == r["job_id"])
    t0 = f.store.get_task(j["buoc"][0]["task_id"])
    check("mẫu: đội ads, 5 bước, mục tiêu được chèn",
          j["doi"] == "ads" and len(j["buoc"]) == 5 and "Váy lụa {mới}" in t0["intent"]
          and j["chat_id"] == "web:x", j)
    check("mẫu: bước bật camp là external-write auto",
          f.store.get_task(j["buoc"][4]["task_id"])["capability"] == "external-write")
    check("POST mẫu trống bị từ chối",
          c.post("/kanban/job", data={"mau": "tu-ke-buoc", "muc_tieu": "x"}).json()["ok"] is False)
    check("POST gate đầu bị từ chối",
          c.post("/kanban/job", data={"title": "x", "steps": json.dumps(
              [{"title": "G", "gate": True}, {"title": "A"}])}).json()["ok"] is False)
    r = c.post("/kanban/job", data={"title": "Tự kê", "doi": "khac", "steps": json.dumps(
        [{"title": "A", "capability": "files"}, {"title": "G", "gate": True}, {"title": "B"}])}).json()
    jid = r["job_id"]
    b = _buoc(f, jid)
    _run(f, b[0]["id"], "nháp")
    r = c.post("/kanban/job/gate", data={"brain": "brain", "job_id": jid, "action": "duyet"}).json()
    check("POST /kanban/job/gate duyet", r == {"ok": True, "status": "dang_chay"}, r)
    check("route: bước sau được full", f.store.get_task(b[2]["id"])["execution_mode"] == "full")
    r = c.post("/kanban/job/gate", data={"job_id": "j_x", "action": "duyet"}).json()
    check("route: job lạ -> ok false", r["ok"] is False and r["loi"])
    f.store.close()


if __name__ == "__main__":
    for fn in (test_tao_job, test_kiem_dau_vao, test_gate_va_duyet, test_sua,
               test_tu_choi_va_trang_thai, test_khong_notify_van_cho_duyet_khi_off,
               test_viec_le_nhu_cu, test_route):
        print(f"--- {fn.__name__}")
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{fn.__name__} không ném lỗi", False, f"{type(e).__name__}: {e}")
    print(f"\n{'FAIL ' + str(len(FAILS)) if FAILS else 'ok   tất cả'}")
    raise SystemExit(1 if FAILS else 0)
