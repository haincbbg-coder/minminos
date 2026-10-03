"""Danh bạ Zalo để tích chọn và phạm vi trả lời của bot.   python tests/run.py bot_danh_ba_pham_vi"""
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
import _paths  # noqa
import chatbot_store, chatbot_runtime
import zalo_personal_channel as zc

ok = True
def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)

# ---- danh bạ -------------------------------------------------------------------------
CONN = {"id": "zalo-1", "label": "Zalo"}
zc.ket_noi_theo_id = lambda cid: CONN if cid == "zalo-1" else None
async def goi(conn, tool, args):
    if tool == "zalo_list_threads":
        return {"threads": [{"threadId": "u1", "name": "Nguyễn Văn Ánh", "type": "user"},
                            {"threadId": "g1", "name": "Nhóm Khách VIP", "type": "group"},
                            {"threadId": "u2", "name": "Lan Hương", "type": "user"}]}
    if tool == "zalo_search_threads":
        return {"threads": [{"threadId": "u3", "name": "Anh Tuấn", "type": "user"}]}
    return {}
zc._goi = goi
r = asyncio.run(zc.danh_ba("zalo-1"))
check("liệt kê đủ bạn bè và nhóm, nhóm lên trước", r["ok"] and [x["id"] for x in r["items"]][0] == "g1" and len(r["items"]) == 3, r)
r = asyncio.run(zc.danh_ba("zalo-1", "anh"))
check("tìm theo tên không phân biệt dấu, gồm kết quả tìm của Zalo",
      {x["id"] for x in r["items"]} == {"u1", "u3"}, r)
r = asyncio.run(zc.danh_ba("zalo-1", "", "group"))
check("lọc riêng nhóm", [x["id"] for x in r["items"]] == ["g1"], r)
check("tài khoản lạ báo lỗi rõ", not asyncio.run(zc.danh_ba("khong-co"))["ok"])

# ---- phạm vi trả lời -----------------------------------------------------------------
check("làm sạch từ khoá cấm", chatbot_store._clean_tu_khoa("giá sỉ, Đại lý;giá sỉ\nx") == ["giá sỉ", "Đại lý"])
bot = {"channel": "telegram", "cam_tu_khoa": ["giá sỉ"]}
check("tin có từ khoá cấm thì bot im (chat riêng)",
      chatbot_runtime._ly_do_im(bot, {"chat_type": "private", "chat_id": "x"}, "cho em hỏi GIÁ SỈ ạ") == "tu_khoa_cam")
check("tin bình thường vẫn trả lời",
      chatbot_runtime._ly_do_im(bot, {"chat_type": "private", "chat_id": "x"}, "áo này giá bao nhiêu") == "")
kh = chatbot_runtime.khoi_pham_vi_noi({"noi_duoc": "giá, size", "noi_cam": "chính trị"})
check("khối phạm vi có cả được và cấm, mặc định từ chối lịch sự",
      "giá, size" in kh and "chính trị" in kh and "từ chối lịch sự" in kh)
check("chọn im thì dặn [IM_LANG]", "[IM_LANG]" in chatbot_runtime.khoi_pham_vi_noi({"noi_cam": "x", "ngoai_pham_vi": "im"}))
check("không khai gì thì không thêm gì", chatbot_runtime.khoi_pham_vi_noi({}) == "")
sys.exit(0 if ok else 1)
