"""Zalo cá nhân: chia câu trả lời dài, báo tin khách bị bỏ lỡ lúc mất kết nối (26.10.167).

    python tests/run.py zalo_chia_tin_bo_lo
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-chia-")
import zalo_personal_channel as zc  # noqa: E402
import channels.zalo_personal as zp  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


# --- chia_tin ---
check("câu ngắn giữ nguyên", zp.chia_tin("xin chào") == ["xin chào"])
check("rỗng không ra tin nào", zp.chia_tin("  ") == [])
dai = " ".join(f"Câu số {i} nói về sản phẩm." for i in range(300))
m = zp.chia_tin(dai, 500)
check("câu dài cắt nhiều mảnh", len(m) > 5, len(m))
check("mỗi mảnh không quá giới hạn", all(len(x) <= 500 for x in m), max(len(x) for x in m))
check("không rơi chữ", " ".join(m).split() == dai.split())
check("cắt ở hết câu", all(x.endswith(".") for x in m), [x[-5:] for x in m if not x.endswith(".")][:3])
lien = "a" * 1200
check("chuỗi liền vẫn cắt được", [len(x) for x in zp.chia_tin(lien, 500)] == [500, 500, 200])
dd = "đoạn một\n\n" + "b " * 400 + "\n\nđoạn ba"
check("ưu tiên cắt ở ngắt đoạn", zp.chia_tin(dd, 600)[0].startswith("đoạn một"))

# --- _gui gửi nhiều tin, tag chỉ ở tin đầu ---
GUI = []


async def gui_gia(tk, chat_id, text, chat_type="private"):
    GUI.append(("rieng", text))
    return True, ""


async def gui_tag_gia(conn_id, thread, cau, specs):
    GUI.append(("nhom", cau, bool(specs)))
    return True, ""


zp.gui, zp.gui_co_tag = gui_gia, gui_tag_gia
zc.ghi_da_gui = lambda *a, **k: None
t = zp.Transport("zalo-1", [], None)
orig = zp.asyncio.sleep


async def nhanh(_):
    return None


zp.asyncio.sleep = nhanh
zp.GIOI_HAN_TIN = 500
asyncio.run(t._gui("th1", dai))
check("chat riêng gửi nhiều tin", len(GUI) == len(zp.chia_tin(dai)) and len(GUI) > 1, len(GUI))
check("nhiều tin đúng thứ tự", " ".join(g[1] for g in GUI).split() == dai.split())
zp.asyncio.sleep = orig

# --- báo tin bỏ lỡ ---
BAO = []
zc.bao_tin_bo_lo = lambda conn, ten: BAO.append(ten)


async def goi_gia(conn, tool, args):
    now = time.time()
    return {"messages": [
        {"id": "1", "threadId": "k1", "senderName": "Lan", "text": "shop ơi", "ts": now - 3600, "threadType": 0},
        {"id": "2", "threadId": "k2", "senderName": "Mai", "text": "mới đây", "ts": now - 5, "threadType": 0},
    ], "nextCursor": "c2"}


zc._goi = goi_gia
zc._ket_noi = lambda: []
conn = {"id": "zalo-1", "label": "Shop"}
import conversations  # noqa: E402
conversations.ghi_trang_thai(f"{zc.KENH}:zalo-1:cursor", "c1")
zc._BOTS["zalo-1"] = type("B", (), {"xu_ly": staticmethod(lambda ev: asyncio.sleep(0))})()


async def chay():
    return await zc.doc_mot_lan(conn)


asyncio.run(chay())
check("tin cũ 1 giờ được báo là bỏ lỡ", BAO and BAO[0] == ["Lan"], BAO)

print("PASS" if not fails else f"FAILED: {fails}")
raise SystemExit(1 if fails else 0)
