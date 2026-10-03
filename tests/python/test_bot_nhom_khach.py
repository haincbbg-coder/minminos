"""Nhóm khách và người lạ của bot.   python tests/run.py bot_nhom_khach"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
import _paths  # noqa
import json
import chatbot_store as cs, chatbot_runtime as rt

ok = True
def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)

nk = cs._clean_nhom_khach(json.dumps([
    {"ten": "Khách mua hàng", "thanh_vien": "111\n222", "noi_duoc": "size, tồn kho, giao hàng", "cam_tu_khoa": "lương"},
    {"ten": "Nội bộ", "thanh_vien": ["333"], "agent_slug": "tro-ly", "bat": False},
]))
check("làm sạch nhóm khách: có id, thành viên, phạm vi riêng", len(nk) == 2 and nk[0]["id"] and nk[0]["thanh_vien"] == ["111", "222"] and nk[0]["cam_tu_khoa"] == ["lương"], nk)
check("cờ bật/tắt giữ đúng", nk[0]["bat"] is True and nk[1]["bat"] is False)
check("nhóm khách rỗng/hỏng thì là danh sách rỗng", cs._clean_nhom_khach("hu hong") == [] and cs._clean_nhom_khach("") == [])
nl = cs._clean_nguoi_la('{"bat": true, "noi_duoc": "chỉ tuyển dụng"}')
check("người lạ bật kèm phạm vi", nl["bat"] is True and nl["noi_duoc"] == "chỉ tuyển dụng", nl)
check("người lạ chưa khai thì rỗng", cs._clean_nguoi_la("") == {})

bot = {"id": "b1", "channel": "zalo_personal", "agent": {"slug": "chinh", "brain": "b"},
       "noi_cam": "chuyện nội bộ", "nhom_khach": nk, "nguoi_la": nl}
cfg, nhan, duoc = cs.hieu_luc(bot, "111")
check("thành viên nhóm khách theo phạm vi nhóm, THAY phạm vi chung", nhan == "Khách mua hàng" and duoc and cfg["noi_duoc"].startswith("size") and cfg["noi_cam"] == "")
cfg, nhan, duoc = cs.hieu_luc(bot, "333")
check("nhóm đang tắt thì bot im", nhan == "Nội bộ" and not duoc)
check("nhóm có Agent riêng thì đổi Agent", cfg["agent"]["slug"] == "tro-ly" and cfg["agent"]["brain"] == "b")
cfg, nhan, duoc = cs.hieu_luc(bot, "ai-do-la")
check("người lạ bật thì trả lời theo phạm vi người lạ", nhan == "Người lạ" and duoc and cfg["noi_duoc"] == "chỉ tuyển dụng")
bot2 = dict(bot, nguoi_la={})
check("Zalo cá nhân không khai người lạ: mặc định im", not cs.hieu_luc(bot2, "ai-do-la")[2])
check("bot Telegram không khai gì: trả lời như cũ", cs.hieu_luc({"channel": "telegram"}, "x")[2])

p = lambda c, t="hi": rt._ly_do_im(bot, {"chat_type": "private", "chat_id": c}, t)
check("khách mua hàng được trả lời", p("111") == "")
check("nhóm nội bộ đang tắt: im, đúng lý do", p("333") == "nhom_khach_tat")
check("người lạ được bật: trả lời", p("zz") == "")
check("từ khoá cấm của RIÊNG nhóm có tác dụng", p("111", "hỏi về lương đi") == "tu_khoa_cam")
check("từ khoá cấm của nhóm khác không lây sang", p("zz", "hỏi về lương đi") == "")
check("người lạ bị tắt thì im", rt._ly_do_im(dict(bot, nguoi_la={"bat": False}), {"chat_type": "private", "chat_id": "zz"}, "hi") == "rieng_chua_cho")
g = lambda c: rt._ly_do_im(dict(bot, groups=[]), {"chat_type": "group", "chat_id": c, "mentioned": True}, "hi")
bot["nhom_khach"][1]["bat"] = True
bot["nhom_khach"][1]["thanh_vien"].append("-100777")
check("nhóm Zalo nằm trong nhóm khách đang bật thì bot nhận việc", rt._ly_do_im(bot, {"chat_type": "group", "chat_id": "-100777", "mentioned": True}, "hi") == "")
check("nhóm lạ vẫn im", rt._ly_do_im(bot, {"chat_type": "group", "chat_id": "-100888", "mentioned": True}, "hi") == "nhom_chua_bat")
sys.exit(0 if ok else 1)
