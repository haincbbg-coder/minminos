"""Bộ phán xử: chấm điểm, nhớ quyết định, học theo phản hồi.   python tests/run.py chatbot_phan_xu"""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
import _paths  # noqa
import chatbot_phan_xu as px
px.THU_MUC = __import__("pathlib").Path(tempfile.mkdtemp())

ok = True
def check(ten, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + ten)
    ok = ok and bool(cond)

now = time.time()
k = lambda t, s="u1": {"sender_type": "customer", "sender_id": s, "text": t, "created_at": now - 300}
check("hỏi giá thì nói", px.cham_diem("Áo này giá bao nhiêu vậy shop?", [])[0])
check("xã giao thì im", not px.cham_diem("ok cảm ơn nha", [])[0])
check("nhắc người khác bằng @ thì im", not px.cham_diem("@Lan bạn ơi mai đi đâu", [])[0])
check("khách đối đáp nhau thì im",
      not px.cham_diem("mai mình đi sớm nhé", [k("ừ", "a"), k("ok", "b"), k("chiều về", "a")])[0])
bot = {"sender_type": "ai", "text": "Dạ size M còn ạ", "created_at": now - 3}
check("bot vừa nói xong thì nén giọng", not px.cham_diem("còn màu đen không?", [bot], bay_gio=now)[0])
bot2 = dict(bot, created_at=now - 120)
check("nói tiếp sau câu của bot thì nói", px.cham_diem("còn màu đen không", [bot2], bay_gio=now)[0])

q = px.quyet_dinh("b1", "g1", "giá áo thun bao nhiêu shop ơi?", [], khoa_tin="m1", ten_nhom="Nhóm A")
q2 = px.quyet_dinh("b1", "g1", "giá áo thun bao nhiêu shop ơi?", [], khoa_tin="m1")
check("cùng một tin chỉ ghi một lần", q["id"] == q2["id"] and len(px.nhat_ky("b1")) == 1)
check("nhật ký có lý do", px.nhat_ky("b1")[0]["ly_do"])

r = px.phan_hoi("b1", q["id"], False)
check("Sai khi bot nói -> nhóm kín hơn", r["ok"] and r["lech"] == 1)
check("chấm hai lần không đẩy thêm", not px.phan_hoi("b1", q["id"], False)["ok"])
for i in range(6):
    qq = px.quyet_dinh("b1", "g1", f"cho em hỏi giá mẫu số {i} nhé shop?", [], khoa_tin=f"x{i}")
    px.phan_hoi("b1", qq["id"], False)
check("ngưỡng bị chặn trên", px._doc("b1")["lech"]["g1"] <= px.LECH_TOI_DA)
px.quen_het("b1", "g1")
check("quên hết xoá ngưỡng đã học", "g1" not in px._doc("b1")["lech"])
check("nhận ra khách bức xúc", px.la_khieu_nai("Giao sai size, tôi muốn hoàn tiền") and not px.la_khieu_nai("áo này giá bao nhiêu"))
kn = px.quyet_dinh("b2", "g9", "hàng lỗi quá, shop lừa đảo à?", [], khoa_tin="k1")
check("tin khiếu nại: bot không nói và đánh dấu để báo chủ", kn["noi"] is False and kn["khieu_nai"])
sys.exit(0 if ok else 1)
