"""Bot Zalo cá nhân trong NHÓM (26.10.52): gọi tên, tag đúng người, ảnh có caption, nhóm lạ im.

    python tests/python/test_zalo_nhom.py      (KHÔNG mạng, MCP giả)
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-zalonhom-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import chatbot_runtime  # noqa: E402
import chatbot_store  # noqa: E402
import zalo_nhom as zn  # noqa: E402
import zalo_personal_channel as zc  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


# ---- hàm thuần ------------------------------------------------------------------------
tv = {"1": "Lan Anh", "2": "Lan Hương", "3": "Minh"}
c, sp = zn.gan_tag("Dạ còn size M ạ", "3", "Minh", tv)
check("không tag ai thì tag người vừa hỏi ở đầu câu", c.startswith("@Minh ") and sp == ["0:3:5"], (c, sp))
c, sp = zn.gan_tag("Chị @Minh xem giúp em nhé", "1", "Lan Anh", tv)
check("@Tên khớp đúng một người thì thành tag thật, đúng vị trí và độ dài",
      sp == ["4:3:5"] and c[4:9] == "@Minh", (c, sp))
c, sp = zn.gan_tag("Chị @Lan xem nhé", "3", "Minh", tv)
check("@Lan khớp hai người thì KHÔNG đoán, quay về tag người hỏi", sp == ["0:3:5"], (c, sp))
c, sp = zn.gan_tag("@Lan Anh ơi còn hàng", "3", "Minh", tv)
check("cụm dài nhất thắng: @Lan Anh không bị hiểu thành @Lan", sp == ["0:1:8"], (c, sp))
check("gọi tên bằng tag đúng vị trí", zn.co_goi_ten("@Lan cho hỏi", [{"pos": 0, "len": 4}], ["Lan"]))
check("gọi tên bằng chữ @ gõ tay", zn.co_goi_ten("ê @Lan ơi", [], ["Lan"]))
check("tin không nhắc bot thì không", not zn.co_goi_ten("mai đi chơi nha", [], ["Lan"]))
check("ảnh không kèm lời không tính là tin", not zn.la_chu_thich("image", "[Zalo: khách gửi image]"))
check("ảnh có caption tính là tin", zn.la_chu_thich("image", "@Lan giá cái này?"))

from channels import zalo_personal as zp  # noqa: E402
av = zp.lenh_cli({"command": "npx", "args": ["-y", "zalo-agent-cli@1.6.2", "mcp", "start"]},
                 "msg", "send", "70011", "@Minh hi", "-t", "1", "--mention", "0:3:5")
check("lệnh CLI dùng đúng gói đã ghim, bỏ 'mcp start'",
      av == ["npx", "-y", "zalo-agent-cli@1.6.2", "msg", "send", "70011", "@Minh hi", "-t", "1",
             "--mention", "0:3:5"], av)
check("kết nối không phải npx thì không dựng lệnh", zp.lenh_cli({"command": "node", "args": []}, "x") is None)

# ---- luồng thật qua Transport ------------------------------------------------------------
CONN = {"id": "zalo-1", "label": "Shop Zalo", "connector_id": "zalo"}
GUI, KHO = [], []
LUOT = []


def _ms(s=0):
    return int((time.time() - s) * 1000)


async def _goi_gia(conn, tool, args):
    if tool == "zalo_send_message":
        GUI.append(dict(args))
        return {"success": True}
    if tool == "zalo_list_threads":
        return {"threads": [{"threadId": "70011", "name": "Nhóm sỉ", "type": "group"},
                            {"threadId": "70022", "name": "Nhóm lạ", "type": "group"}]}
    if tool == "zalo_get_messages":
        t = list(KHO); KHO.clear()
        return {"messages": t, "nextCursor": "c" + str(time.time())}
    return {}


zc._ket_noi = lambda: [dict(CONN)]
zc._goi = _goi_gia


async def _engine(text, meta, progress, *, channel="", bot=None):
    LUOT.append(text)
    return {"text": "Dạ còn ạ", "files": []}


chatbot_runtime.wire(answer=_engine, brain_root=lambda b: tempfile.mkdtemp(prefix="brain-"),
                     read_agent=lambda br, slug: ({"name": "Lan", "role": "Bán hàng"}, "Tư vấn."))
bid, loi = chatbot_store.create_bot({"name": "Lan", "agent_slug": "lan", "brain": "b",
                                     "account_ids": ["zalo-1"]})
chatbot_store.update_bot(bid, {"groups": ["70011"], "reply_when": "mention"})


def msg(thread, mid, text, loai="text", tu="u9", ten="Khách Minh", **them):
    d = {"threadId": thread, "from": tu, "senderName": ten, "type": loai, "text": text,
         "id": mid, "ts": _ms(3), "threadType": 1}
    d.update(them)
    return d


async def chay():
    ok, err = chatbot_runtime.start_bot(bid)
    check("bật được bot", ok, err)
    KHO.append(msg("70011", "a1", "mai ship sớm nhé cả nhà"))
    await zc.doc_mot_lan(dict(CONN)); await asyncio.sleep(0.3)
    check("nhóm đã bật, không ai gọi tên: im, không tốn model", not GUI and not LUOT, (GUI, LUOT))

    KHO.append(msg("70011", "a2", "@Lan cho hỏi áo này còn không?", mentions=[{"pos": 0, "len": 4}]))
    await zc.doc_mot_lan(dict(CONN)); await asyncio.sleep(0.4)
    check("gọi tên bằng tag thì bot trả lời trong nhóm", len(GUI) == 1, GUI)
    check("gửi đúng nhóm với loại tin NHÓM (cả threadType lẫn type)",
          GUI and GUI[0]["threadId"] == "70011" and GUI[0]["threadType"] == 1 and GUI[0]["type"] == 1, GUI)
    check("câu trả lời tag người vừa hỏi", GUI and GUI[0]["text"].startswith("@Khách Minh "), GUI)

    GUI.clear()
    KHO.append(msg("70011", "a3", "@Lan giá cái này?", loai="image", mentions=[{"pos": 0, "len": 4}]))
    await zc.doc_mot_lan(dict(CONN)); await asyncio.sleep(0.4)
    check("ảnh có caption gọi tên thì bot trả lời", len(GUI) == 1, GUI)

    GUI.clear(); n = len(LUOT)
    KHO.append(msg("70011", "a4", "", loai="image"))
    await zc.doc_mot_lan(dict(CONN)); await asyncio.sleep(0.3)
    check("ảnh không caption thì bỏ qua", not GUI and len(LUOT) == n)

    KHO.append(msg("70022", "b1", "@Lan ơi giúp mình", mentions=[{"pos": 0, "len": 4}]))
    await zc.doc_mot_lan(dict(CONN)); await asyncio.sleep(0.4)
    check("nhóm LẠ (chưa bật) gọi tên: bot IM, không nhân danh chủ xin được bật",
          not GUI and len(LUOT) == n, GUI)
    check("nhưng nhóm đó lên hàng chờ để chủ duyệt",
          any(x.get("chat_id") == "70022" for x in (chatbot_runtime.nhom_cho(bid) or [])),
          chatbot_runtime.nhom_cho(bid))
    chatbot_runtime.stop_bot(bid)


asyncio.run(chay())
for f in (ROOT / "server" / "zalo_nhom.py", ROOT / "server" / "channels" / "zalo_personal.py"):
    check(f"không có em dash trong {f.name}", "—" not in f.read_text(encoding="utf-8"))
if _fails:
    print(f"\nFAIL: {_fails}"); sys.exit(1)
print("\nOK - test_zalo_nhom: tất cả pass")
