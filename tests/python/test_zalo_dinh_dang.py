"""Bot Zalo cá nhân: chữ đậm/màu và "đang soạn tin" (26.10.314, server/zalo_dinh_dang.py + channels/zalo_personal.py).

    python tests/run.py zalo_dinh_dang

Phủ: Markdown thành kiểu Zalo (vị trí UTF-16, lồng nhau, không đụng snake_case hay phép nhân), tham số --style của
zalo-agent-cli; chat riêng gửi qua lệnh CLI có định dạng và nhớ bản chữ trơn để nhận tiếng vọng; CLI hỏng thì
gửi chữ trơn qua MCP; hết giờ không gửi lại; nhóm bỏ dấu trước khi gắn tag; "đang soạn tin" chỉ chat riêng,
MCP thiếu tool thì nghỉ một giờ và câu trả lời không phải chờ.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="minmin-zalo-dd-")
import zalo_dinh_dang as zd  # noqa: E402
import zalo_personal_channel as zc  # noqa: E402
import channels.zalo_personal as zp  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


# ---- 1. Markdown -> kiểu Zalo ----
p, st = zd.sang_zalo("Giá **85.000đ** nhé")
check("đậm", (p, st) == ("Giá 85.000đ nhé", [(4, 7, "bold")]), (p, st))
p, st = zd.sang_zalo("😀 **x**")
check("emoji tính hai đơn vị UTF-16", (p, st) == ("😀 x", [(3, 1, "bold")]), (p, st))
p, st = zd.sang_zalo("**đậm *nghiêng* đậm** ~~cũ~~ {red:Giảm 50%}")
check("lồng nhau và màu", p == "đậm nghiêng đậm cũ Giảm 50%"
      and st == [(0, 15, "bold"), (4, 7, "italic"), (16, 2, "strikethrough"), (19, 8, "red")], (p, st))
p, st = zd.sang_zalo("# Ưu đãi\n- một\n* hai\n[web](https://a.vn) `mã`\n```\nx\n```")
check("tiêu đề đậm, gạch đầu dòng, liên kết, mã", p == "Ưu đãi\n• một\n• hai\nweb (https://a.vn) mã\nx"
      and st == [(0, 6, "bold")], (p, st))
check("không đụng snake_case và phép nhân", zd.sang_zalo("ten_bien_moi va 2*3*4") == ("ten_bien_moi va 2*3*4", []))
check("tham số --style đúng khuôn CLI", zd.tham_so_style([(0, 3, "bold"), (4, 2, "red"), (0, 0, "bold"), (1, 1, "la")])
      == ["--style", "0:3:bold", "4:2:red"])
check("không kiểu thì không tham số", zd.tham_so_style([]) == [])
check("tiếng vọng chữ trơn khớp câu Markdown đã gửi", zc._chuan("Giá **85.000đ**  nhé") == zc._chuan("Giá 85.000đ nhé"))

# ---- 2. chat riêng: gửi qua CLI có định dạng, nhớ bản trơn ----
DA_NHO, GUI_MCP, CLI = [], [], []


async def mcp_gia(conn, tool, args):
    GUI_MCP.append((tool, args))
    if tool == zp.GO_TOOL:
        raise RuntimeError("Tool zalo_send_typing not found")
    return {"success": True}


class Proc:
    def __init__(self, rc=0, treo=False):
        self.returncode, self.treo = rc, treo

    async def communicate(self):
        if self.treo:
            await asyncio.sleep(60)
        return b"", b""

    def kill(self):
        pass


KQ = {"proc": Proc(0)}


async def exec_gia(*argv, **kw):
    CLI.append(list(argv))
    return KQ["proc"]


zc._goi = mcp_gia
zc.ket_noi_theo_id = lambda cid: {"id": cid, "command": "npx", "args": ["-y", "zalo-agent-cli@1.6.2", "mcp", "start"]}
zc.ghi_da_gui = lambda conn, thread, text: DA_NHO.append(text)
zp.asyncio.create_subprocess_exec = exec_gia
t = zp.Transport("zalo-1", [], None)
asyncio.run(t._gui("th1", "Dạ **85.000đ** ạ"))
check("chat riêng: gọi msg send --style", CLI and CLI[-1][-6:] == ["th1", "Dạ 85.000đ ạ", "-t", "0", "--style", "3:7:bold"],
      CLI and CLI[-1])
check("đúng gói đã ghim", CLI and "zalo-agent-cli@1.6.2" in CLI[-1])
check("nhớ bản chữ trơn cho tiếng vọng", DA_NHO == ["Dạ 85.000đ ạ"], DA_NHO)
check("không gửi lần hai qua MCP", not [g for g in GUI_MCP if g[0] == "zalo_send_message"])

CLI.clear()
asyncio.run(t._gui("th1", "chào chị"))
check("không Markdown thì đi MCP như cũ", not CLI and GUI_MCP[-1][1]["text"] == "chào chị", GUI_MCP[-1:])

KQ["proc"] = Proc(1)
GUI_MCP.clear()
asyncio.run(t._gui("th1", "Dạ **85.000đ** ạ"))
check("CLI hỏng: gửi chữ trơn qua MCP", GUI_MCP and GUI_MCP[-1][1]["text"] == "Dạ 85.000đ ạ", GUI_MCP)
CLI.clear()
asyncio.run(t._gui("th1", "**lần hai**"))
check("CLI vừa hỏng thì nghỉ đường CLI một lúc", not CLI and GUI_MCP[-1][1]["text"] == "lần hai")
zp._CLI_NGHI.clear()

KQ["proc"] = Proc(0, treo=True)
GUI_MCP.clear()
goc_wait = zp.asyncio.wait_for


async def wait_nhanh(aw, timeout):
    return await goc_wait(aw, 0.05)


zp.asyncio.wait_for = wait_nhanh
ok, loi = asyncio.run(zp.gui({"id": "zalo-1"}, "th1", "**x**", "private"))
zp.asyncio.wait_for = goc_wait
check("hết giờ: kết cục không rõ, KHÔNG gửi lại", not ok and "không rõ" in loi and not GUI_MCP, (ok, loi, GUI_MCP))
KQ["proc"] = Proc(0)

# ---- 3. nhóm: bỏ dấu trước khi gắn tag ----
TAG = []


async def tag_gia(conn_id, thread, cau, specs):
    TAG.append((cau, specs))
    return True, ""


goc_tag = zp.gui_co_tag
zp.gui_co_tag = tag_gia
asyncio.run(t._gui("g1", "Giá **85k** nha", {"chat_type": "group", "user_id": "", "user_name": ""}))
zp.gui_co_tag = goc_tag
check("nhóm gửi chữ trơn", TAG and "**" not in TAG[0][0] and "85k" in TAG[0][0], TAG)

# ---- 4. "đang soạn tin" ----
GUI_MCP.clear()


async def tra_loi(text, meta, progress):
    await asyncio.sleep(0.05)
    return "Dạ có ạ"


zp.GO_TRE, zp.GO_NHIP = 0.0, 0.01
t2 = zp.Transport("zalo-2", [], tra_loi)
t2._gui = lambda *a, **k: asyncio.sleep(0)
asyncio.run(t2._tra_loi("th9", "còn hàng không", {"chat_type": "private"}, False))
go = [g for g in GUI_MCP if g[0] == zp.GO_TOOL]
check("chat riêng: thử bật đang soạn tin", len(go) == 1 and go[0][1]["threadId"] == "th9", go)
check("MCP thiếu tool: nghỉ một giờ", zp._GO_NGHI.get("zalo-2", 0) > time.time() + 3000)
GUI_MCP.clear()
asyncio.run(t2._tra_loi("th9", "nữa", {"chat_type": "private"}, False))
check("đang nghỉ thì không gọi lại", not [g for g in GUI_MCP if g[0] == zp.GO_TOOL])
zp._GO_NGHI.clear()
asyncio.run(t2._tra_loi("g9", "nhóm", {"chat_type": "group"}, True))
check("nhóm không hiện đang soạn tin", not [g for g in GUI_MCP if g[0] == zp.GO_TOOL])


async def mcp_co_tool(conn, tool, args):
    GUI_MCP.append((tool, args))
    return {"success": True}


zc._goi = mcp_co_tool
GUI_MCP.clear()
zp._GO_NGHI.clear()


async def tra_loi_lau(text, meta, progress):
    await asyncio.sleep(0.05)
    return "ok"


t3 = zp.Transport("zalo-3", [], tra_loi_lau)
t3._gui = lambda *a, **k: asyncio.sleep(0)
asyncio.run(t3._tra_loi("th3", "hỏi", {"chat_type": "private"}, False))
n = len([g for g in GUI_MCP if g[0] == zp.GO_TOOL])
check("MCP có tool: giữ đang soạn tin suốt lượt", n >= 2, n)

print("\nXANH" if not fails else f"\nFAILED: {fails}")
raise SystemExit(1 if fails else 0)
