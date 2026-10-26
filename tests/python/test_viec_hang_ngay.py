"""Hộp tin Việc Hàng Ngày (26.10.259).

    python tests/run.py viec_hang_ngay      (KHÔNG mạng, không spawn engine)

Chủ repo báo 2026-10-26: kết quả Bảng việc và Lịch tự chạy cứ chèn vào hội thoại đang dùng.
Yêu cầu: dồn mặc định vào mục "Việc Hàng Ngày" (mục chủ repo đã tự tạo), Bảng việc chỉ MỘT hội
thoại, Lịch tự chạy chỉ MỘT hội thoại, đầy thì mở phiên mới nhưng vẫn nằm trong mục đó.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import tempfile
from pathlib import Path

import sessions  # noqa: E402
import viec_hang_ngay as vhn  # noqa: E402

fails = []


def check(ten, ok, chi_tiet=""):
    print(("ok   " if ok else "FAIL ") + ten + ("" if ok else f"  ({chi_tiet})"))
    if not ok:
        fails.append(ten)


tmp = Path(tempfile.mkdtemp(prefix="javis-vhn-"))
store = sessions.SessionStore(tmp / "sessions.db")
hop = vhn.HopViec(lambda: store, tmp / "viec-hang-ngay.json")

# Mục người dùng TỰ TẠO (viết hoa, có dấu) phải được dùng luôn, không đẻ mục thứ hai.
pid_tay = store.create_project("Việc Hàng Ngày", brain="brain")
dang_chat = store.create_session(brain="brain", title="Quét danh sách các page")

d1 = hop.doi_dich("web:" + dang_chat, {"kind": "loop", "status": "done"})
check("loop không còn về hội thoại đang chat", d1 != "web:" + dang_chat, d1)
s_lich = d1[len("web:"):]
check("dùng đúng mục người dùng đã tạo", store.get_session(s_lich)["project_id"] == pid_tay)
check("chỉ có MỘT mục Việc Hàng Ngày",
      sum(1 for p in store.list_projects("brain") if vhn.chuan_ten(p["name"]) == "viec hang ngay") == 1)
check("tên hội thoại 'Lịch Tự Chạy'", store.get_session(s_lich)["title"] == "Lịch Tự Chạy")

# Nhắc hẹn, theo dõi web: cùng hộp Lịch. Từ một hội thoại khác cũng vậy.
khac = store.create_session(brain="brain", title="Hội thoại khác")
check("nhắc hẹn chung hội thoại Lịch",
      hop.doi_dich("web:" + khac, {"kind": "reminder"}) == "web:" + s_lich)
check("theo dõi web chung hội thoại Lịch",
      hop.doi_dich("web:" + dang_chat, {"kind": "watch"}) == "web:" + s_lich)

# Bảng việc: hội thoại RIÊNG, chỉ một.
d_bang = hop.doi_dich("web:" + dang_chat, {"kind": "task", "status": "done"})
s_bang = d_bang[len("web:"):]
check("Bảng việc có hội thoại riêng", s_bang and s_bang != s_lich)
check("Bảng việc chỉ một hội thoại", hop.doi_dich("web:" + khac, {"kind": "task"}) == d_bang)
check("GATE đi Bảng Việc", hop.doi_dich("web:" + khac, None, "bang") == d_bang)
check("tên 'Bảng Việc'", store.get_session(s_bang)["title"] == "Bảng Việc")

# Không thuộc diện: giữ nguyên đích.
check("Telegram giữ nguyên", hop.doi_dich("12345", {"kind": "loop"}) == "12345")
check("Zalo giữ nguyên", hop.doi_dich("zalo:9", {"kind": "task"}) == "zalo:9")
check("việc chạy nền của lượt chat (job) về đúng khung đã hỏi",
      hop.doi_dich("web:" + dang_chat, {"kind": "job"}) == "web:" + dang_chat)
check("tin không có khối việc giữ nguyên", hop.doi_dich("web:" + dang_chat, None) == "web:" + dang_chat)
check("phiên không tồn tại giữ nguyên", hop.doi_dich("web:khongco", {"kind": "loop"}) == "web:khongco")

# Đầy thì mở phần 2, vẫn trong mục.
vhn.TRAN_TIN = 3
for i in range(3):
    store.append_message(s_lich, "assistant", f"tin {i}")
d2 = hop.doi_dich("web:" + dang_chat, {"kind": "loop"})
s2 = d2[len("web:"):]
check("đầy thì mở hội thoại mới", s2 != s_lich)
check("hội thoại mới vẫn trong mục", store.get_session(s2)["project_id"] == pid_tay)
check("tên 'phần 2'", store.get_session(s2)["title"] == "Lịch Tự Chạy · phần 2",
      store.get_session(s2)["title"])
check("chưa đầy thì dùng tiếp", hop.doi_dich("web:" + khac, {"kind": "loop"}) == d2)
vhn.TRAN_TIN = 1000

# Người dùng kéo hội thoại ra khỏi mục hoặc lưu trữ: không kéo ngược về, mở cái mới.
store.set_project(s_bang, None)
d_bang2 = hop.doi_dich("web:" + dang_chat, {"kind": "task"})
check("kéo ra khỏi mục thì mở hội thoại mới", d_bang2 != d_bang)
check("hội thoại đã kéo ra vẫn nằm ngoài mục", not store.get_session(s_bang)["project_id"])
store.archive(d_bang2[len("web:"):])
check("lưu trữ thì mở hội thoại mới", hop.doi_dich("web:" + dang_chat, {"kind": "task"}) != d_bang2)

# Mục bị xoá: lần sau tự tạo lại.
store.delete_project(pid_tay)
d3 = hop.doi_dich("web:" + dang_chat, {"kind": "loop"})
pid_moi = store.get_session(d3[len("web:"):])["project_id"]
check("mục bị xoá thì tạo lại", pid_moi and pid_moi != pid_tay
      and store.get_project(pid_moi)["name"] == vhn.TEN_MUC)

# Mỗi bộ não một mục riêng.
o_nao2 = store.create_session(brain="nao2", title="x")
d4 = hop.doi_dich("web:" + o_nao2, {"kind": "loop"})
check("bộ não khác có hội thoại riêng", store.get_session(d4[len("web:"):])["brain"] == "nao2")

# Công tắc tắt: giữ hành vi cũ.
tat = vhn.HopViec(lambda: store, tmp / "x.json", bat=lambda: False)
check("tắt thì về hội thoại cũ", tat.doi_dich("web:" + dang_chat, {"kind": "loop"}) == "web:" + dang_chat)

# 26.10.260: mục mang khoá "brain", hội thoại mang khoá đường dẫn của CÙNG bộ não.
BIET_DANH = {"/brains/Brain Default": ["/brains/Brain Default", "brain"]}
hop2 = vhn.HopViec(lambda: store, tmp / "y.json", brain_keys=lambda b: BIET_DANH.get(b, [b]))
for p in store.list_projects("brain"):
    store.delete_project(p["id"])
pid_bo = store.create_project("Việc Hàng Ngày", brain="brain")
pid_tu_tao = store.create_project("Việc Hàng Ngày", brain="/brains/Brain Default")  # mục lỡ tạo
o_dai = store.create_session(brain="/brains/Brain Default", title="Quét Sheet")
d5 = hop2.doi_dich("web:" + o_dai, {"kind": "loop"})
check("khoá khác tên vẫn dùng đúng mục người dùng tạo (mục cũ nhất)",
      store.get_session(d5[len("web:"):])["project_id"] == pid_bo)
check("hội thoại mới mang khoá bộ não của hội thoại gốc",
      store.get_session(d5[len("web:"):])["brain"] == "/brains/Brain Default")
check("lần sau dùng lại, không đẻ thêm", hop2.doi_dich("web:" + o_dai, {"kind": "loop"}) == d5)
store.delete_project(pid_bo); store.delete_project(pid_tu_tao)
d6 = hop2.doi_dich("web:" + o_dai, {"kind": "task"})
check("chưa có mục thì tạo bằng khoá 'brain'",
      store.get_project(store.get_session(d6[len("web:"):])["project_id"])["brain"] == "brain")

# Nối dây ở main.py và tasks.py.
MAIN = (SERVER / "main.py").read_text(encoding="utf-8")
TASKS = (SERVER / "tasks.py").read_text(encoding="utf-8")
check("_notify_owner đổi đích trước khi bỏ hòm thư",
      MAIN.index("owner_chat = await asyncio.to_thread(_HOP_VIEC.doi_dich")
      < MAIN.index("vao_hom = await _bo_vao_hom_thu("))
check("main.py truyền _brain_keys", "brain_keys=lambda b: _brain_keys(b)" in MAIN)
check("GATE đổi đích về Bảng Việc", '_HOP_VIEC.doi_dich, chat, None, "bang"' in MAIN)
check("báo gộp việc kẹt mang khối việc", 'viec={"kind": "task", "status": "blocked"' in TASKS)
check("không có gạch dài", not any(c in (SERVER / "viec_hang_ngay.py").read_text(encoding="utf-8")
                                   for c in "–—"))

store._conn.close()
if fails:
    print(f"\n{len(fails)} FAIL")
    raise SystemExit(1)
print("\nTất cả ok")
