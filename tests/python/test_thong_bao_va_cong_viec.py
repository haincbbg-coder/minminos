"""26.10.312: bộ chỉ huy thông báo và trang Công việc yên hơn.

    python tests/python/test_thong_bao_va_cong_viec.py

- Mỗi tin có nhóm và mức; mặc định chỉ tin khẩn mới kêu, còn lại vào ngăn Đã lọc (đã đọc).
- "Không cần báo" được nhớ cho loại tin đó; "Nên báo" trên tin đã lọc thì luôn kêu; hoàn tác được.
- [SILENT] tính khi mở đầu HOẶC kết thúc câu trả lời.
- "Cần bố xử lý" chỉ giữ câu hỏi / xin quyền / chờ duyệt; việc dừng kỹ thuật vào khu riêng.
- Nhắn thêm, Kiểm lại, gợi ý việc lặp.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="minmin-thongbao-")

import channel_context  # noqa: E402
import inbox  # noqa: E402
import muc_thong_bao as M  # noqa: E402
from task_store import TaskStore  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  [{them}]" if not cond and them else ""))
    if not cond:
        _fails.append(name)


# ── phân loại ─────────────────────────────────────────────────────────────────────────────
check("nhắc hẹn là nhóm Nhắc lịch, mức khẩn",
      M.level_of(group=M.group_of(source="reminder")) == "urgent" and M.group_of(source="reminder") == "reminder")
check("việc đang hỏi bố là Câu hỏi chờ bố", M.group_of(viec={"kind": "task", "status": "hoi"}) == "question")
check("kết quả chờ duyệt cũng là Câu hỏi chờ bố", M.group_of(viec={"kind": "task", "status": "review"}) == "question")
check("tin lặng là bình thường", M.level_of(quiet=True, group="job") == "info")
check("chatbot mặc định khẩn", M.level_of(group="chatbot") == "urgent")
check("kết quả việc mặc định đáng chú ý", M.level_of(group="job") == "important")
check("dáng tiêu đề bỏ số", M.signature("Việc 'A' lỗi lần 3") == M.signature("Việc 'A' lỗi lần 4"))
check("hai việc khác tên là hai dáng", M.signature("Việc 'A' lỗi") != M.signature("Việc 'B' lỗi"))

# ── quyết định mặc định: chỉ tin khẩn ─────────────────────────────────────────────────────
d = M.decide("job", "important", "Việc 'X' đã hoàn thành")
check("mặc định: tin đáng chú ý bị lọc", d["verdict"] == "quiet" and d["why"] == "mode", d)
d = M.decide("reminder", "urgent", "Nhắc bố: gọi khách")
check("mặc định: tin khẩn kêu", d["verdict"] == "loud", d)

# luật lặp: tin không khẩn kêu quá 3 lần trong cửa sổ thì vào Đã lọc
M.set_mode("connection", "all")
now = time.time()
v = [M.decide("connection", "important", "Kết nối Pancake lỗi lần %d" % i, now=now + i)["verdict"] for i in range(5)]
check("luật lặp: 3 lần đầu kêu, sau đó lọc", v == ["loud", "loud", "loud", "quiet", "quiet"], v)
v = [M.decide("reminder", "urgent", "Nhắc lần %d" % i, now=now + i)["verdict"] for i in range(5)]
check("tin khẩn không bao giờ bị luật lặp lọc", all(x == "loud" for x in v), v)

# tắt nhóm: bỏ hẳn
c = M.set_mode("update", "off")
check("tắt nhóm Cập nhật: bỏ hẳn", M.decide("update", "info", "Có bản mới")["verdict"] == "drop")
check("hoàn tác chế độ nhóm", M.undo(c["id"]) and M.decide("update", "info", "Có bản mới")["verdict"] == "quiet")

# ── hòm thư ──────────────────────────────────────────────────────────────────────────────
it = inbox.add("Việc 'Báo cáo' đã hoàn thành.\n\nchi tiết", kind="answer", source="job", tu_phan_loai=True)
check("thư không khẩn bỏ thẳng: có nhóm, bị lọc, đã đọc",
      it.get("group") == "job" and it.get("filtered") and it.get("read"), it)
it2 = inbox.add("Khách bức xúc ở nhóm A", kind="system", source="chatbot", tu_phan_loai=True)
check("thư chatbot: khẩn, chưa đọc", it2.get("level") == "urgent" and not it2.get("read"), it2)
check("số chưa đọc chỉ đếm tin kêu", inbox.so_chua_doc() == 1, inbox.so_chua_doc())

# Không cần báo: thư thành đã đọc, loại đó bị lọc lần sau (kể cả khẩn, vì bố đã nói)
after = inbox.phan_hoi(it2["id"], "not_needed")
ch = M.react(after, "not_needed")
check("Không cần báo: thư thành đã đọc", after.get("read") is True)
check("Không cần báo: có thay đổi và nói ra được", ch and "lọc" in M.describe(ch), ch)
it3 = inbox.add("Khách bức xúc ở nhóm A", kind="system", source="chatbot", tu_phan_loai=True)
check("lần sau loại tin đó vào Đã lọc", it3.get("filtered") and it3.get("why") == "muted", it3)
check("hoàn tác Không cần báo", M.undo(ch["id"]) is not None
      and not inbox.add("Khách bức xúc ở nhóm A", kind="system", source="chatbot", tu_phan_loai=True).get("filtered"))

# Nên báo trên một tin đã lọc: loại đó luôn kêu
ch = M.react(it, "needed")
check("Nên báo: loại tin luôn kêu", M.decide("job", "important", it["title"])["verdict"] == "loud", ch)
st = M.status()
check("status liệt kê đủ nhóm và luật", len(st["groups"]) == len(M.GROUPS) and st["rules"], st["rules"])

# ── [SILENT] ─────────────────────────────────────────────────────────────────────────────
check("[SILENT] mở đầu", channel_context.is_silent_report("[SILENT] không có gì mới"))
check("[SILENT] kết thúc", channel_context.is_silent_report("Đã kiểm, không có đơn mới.\n[SILENT]"))
check("[SILENT] cuối câu, có nhấn markdown", channel_context.is_silent_report("Không có gì. **[SILENT]**"))
check("[SILENT] giữa đoạn không tính",
      not channel_context.is_silent_report("Khi không có gì, mình trả [SILENT] cho hệ thống.\nCòn đây là báo cáo."))
check("rỗng không phải im lặng", not channel_context.is_silent_report(""))

# ── trang Công việc ──────────────────────────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="minmin-cv-"))
store = TaskStore(tmp / "q.sqlite3")
root = str(tmp / "brain")
Path(root).mkdir()


def _viec(title, kind=None, status="blocked"):
    tid = store.enqueue(root, title, title, capability="files", status="ready")
    assert store.claim(tid, "w")
    if status == "done":
        return store.complete(tid, "w", "Kết quả: đã viết 3 bài.")
    if kind == "needs_input":
        return store.ask(tid, "w", "Giá bán bao nhiêu?")
    return store.block(tid, "w", kind, "lỗi kỹ thuật " + kind)


hoi = _viec("Hỏi giá", "needs_input")
quyen = _viec("Đăng bài", "capability")
tam = _viec("Báo cáo", "transient")
check("câu hỏi chờ bố", TaskStore.waits_for_owner(hoi))
check("xin quyền chờ bố", TaskStore.waits_for_owner(quyen))
check("lỗi kỹ thuật KHÔNG chờ bố", not TaskStore.waits_for_owner(tam))

xong = _viec("Viết bài", status="done")
t, err = store.followup(xong["id"], "Viết ngắn lại đoạn 2")
check("Nhắn thêm cho việc đã xong: về hàng đợi", t and t["status"] == "ready" and t["attempts"] == 0, (t, err))
qa = (t["metadata"] or {}).get("qa") or []
check("Nhắn thêm vào sổ hỏi đáp kèm kết quả cũ",
      qa and qa[-1].get("kind") == "followup" and "3 bài" in qa[-1].get("progress", ""), qa)
t, err = store.followup(hoi["id"], "abc")
check("việc đang chờ câu trả lời thì không Nhắn thêm", t is None and err == "waiting", err)
check("lời nhắn rỗng bị từ chối", store.followup(tam["id"], "  ")[1] == "empty")

import tasks as tasks_mod  # noqa: E402
hd = tasks_mod.TasksFeature._hoi_dap(t if t else store.get_task(xong["id"]))
check("lần chạy sau đọc lời nhắn thêm như yêu cầu mới", "Chủ nhắn thêm" in hd and "đoạn 2" in hd, hd[:200])

xong2 = _viec("Viết bài 2", status="done")
check("Kiểm: đạt", (store.set_check(xong2["id"], "dat", "ok")["metadata"]["kiem"]["state"]) == "dat")
t = store.set_check(xong2["id"], "chua_dat", "thiếu bài thứ ba")
check("Kiểm: chưa đạt thì sang Cần bố xử lý với câu hỏi",
      t["status"] == "blocked" and t["block_kind"] == "needs_input" and "thiếu bài" in t["block_reason"], t)

calm = tasks_mod.TasksFeature._calm(store.get_task(tam["id"]))
check("việc dừng kỹ thuật có câu dễ hiểu, nói bố không cần làm gì", "không cần làm gì" in calm, calm)
check("câu dễ hiểu không có gạch dài", "—" not in calm)

# Gợi ý việc lặp: 3 lần giao tay trong 60 ngày, tên khác nhau ở con số
for ngay in ("28/10", "29/10", "30/10"):
    store.enqueue(root, f"Báo cáo doanh thu ngày {ngay}", "báo cáo", created_by="user")
store.enqueue(root, "Báo cáo doanh thu ngày 31/10", "báo cáo", created_by="loop")
h = store.repeat_hints(root)
check("gợi ý việc lặp sau 3 lần giao tay", h and h[0]["count"] == 3, h)
store.dismiss_hint(root, h[0]["key"])
check("bỏ qua gợi ý thì không hiện nữa", not store.repeat_hints(root))

check("Xoá tất cả khu tự xử lý chỉ dọn việc kỹ thuật",
      store.archive_stopped(root, owner=False) >= 1 and store.get_task(hoi["id"])["status"] == "blocked")
store.close()

print()
if _fails:
    print(f"FAIL {len(_fails)}: " + "; ".join(_fails))
    sys.exit(1)
print("TẤT CẢ PASS")
