"""Zalo cá nhân: gom tin chat riêng, giữ tin khi chủ đang nhắn tay (26.10.161).

    python tests/run.py zalo_gom_tin
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-gom-")
import zalo_personal_channel as zc  # noqa: E402
import channels.zalo_personal as zp  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


zp.GOM_GIAY = 0.2
GOI, GUI = [], []


async def answer_fn(text, meta, progress):
    GOI.append((text, dict(meta)))
    return {"text": "ok"}


def tao():
    t = zp.Transport("zalo-1", [], answer_fn)

    async def gui(thread, cau, meta=None):
        GUI.append((thread, cau))
    t._gui = gui
    zc._BOTS["zalo-1"] = t
    return t


def ev(text, loai="text", ago=0, **md):
    return {"chat_type": "private", "message_type": loai, "text": text, "external_chat_id": "u1",
            "sender_id": "u1", "sender_name": "Quý", "created_at": time.time() - ago,
            "external_message_id": f"m{time.time()}", "metadata": md}


async def chay():
    t = tao()
    # 1) ba tin liền nhau, một lần trả lời
    for x in ("Chị ơi", "cho em hỏi", "áo này còn size M không"):
        await t.xu_ly(ev(x))
        await asyncio.sleep(0.05)
    check("chưa đáp khi khách còn đang nhắn", not GOI, GOI)
    await asyncio.sleep(0.6)
    check("khách im thì đáp MỘT lần đủ ý", len(GOI) == 1 and GOI[0][0] == "Chị ơi\ncho em hỏi\náo này còn size M không", GOI)
    check("gửi đúng một câu", len(GUI) == 1)

    # 2) ảnh rồi nhắn "xem giúp em": một câu hỏi kèm ảnh
    GOI.clear(); GUI.clear()
    await t.xu_ly(ev("", "image", image_url="https://f9.zdn.vn/a.jpg"))
    await t.xu_ly(ev("xem giúp em"))
    await asyncio.sleep(0.6)
    check("ảnh + chữ thành một lượt có ảnh", len(GOI) == 1 and GOI[0][1].get("co_anh") and GOI[0][1].get("image_url") and "xem giúp em" in GOI[0][0], GOI)

    # 3) file không chữ: bot được báo khách gửi file gì
    GOI.clear()
    await t.xu_ly(ev("", "file", fileName="bang-gia.xlsx"))
    await asyncio.sleep(0.6)
    check("khách gửi file: bot biết tên file", len(GOI) == 1 and "bang-gia.xlsx" in GOI[0][0], GOI)

    # 4) chủ tự trả lời sau tin khách: bỏ phần giữ
    GOI.clear()
    await t.xu_ly(ev("giá sao chị"))
    zc._TAY[("zalo-1", "u1")] = time.time() + 1
    await asyncio.sleep(0.6)
    check("chủ đã tự trả lời thì bot im", not GOI, GOI)

    # 5) chủ vừa nhắn tay TRƯỚC khi khách hỏi: giữ, hết hạn mà chủ im thì đáp một lần
    GOI.clear(); GUI.clear()
    zc._TAY.clear()
    old = zc.TAY_IM
    zc.TAY_IM = 1.0
    zc._TAY[("zalo-1", "u1")] = time.time() - 0.5
    await t.xu_ly(ev("Vậy còn màu đen không"))
    await asyncio.sleep(0.5)
    check("chủ đang nói chuyện thì bot chưa đáp", not GOI, GOI)
    await asyncio.sleep(1.6)
    check("quá hạn chủ vẫn im thì bot đáp một lần", len(GOI) == 1, GOI)
    zc.TAY_IM = old

    # 6) bot tắt giữa chừng thì không gửi gì
    GOI.clear(); zc._TAY.clear()
    await t.xu_ly(ev("alo"))
    zc._BOTS.pop("zalo-1", None)
    await asyncio.sleep(0.6)
    check("bot đã tắt thì không đáp", not GOI, GOI)

    # 7) nhóm vẫn đi đường cũ: không gom, chữ không tên bot thì bỏ
    tao()
    GOI.clear()
    g = {"chat_type": "group", "message_type": "text", "text": "cả nhà ơi", "external_chat_id": "g1",
         "sender_id": "u9", "created_at": time.time(), "metadata": {}}
    await t.xu_ly(g)
    check("nhóm không bị gom chung với chat riêng", "g1" not in t._dem)


asyncio.run(chay())
if fails:
    print("\nĐỎ:", fails)
    raise SystemExit(1)
print("\nxanh")
