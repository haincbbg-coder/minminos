"""Nguồn MCP vừa hỏng thì các lần gọi sau báo lỗi ngay, Kiểm tra thành công thì dùng lại."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
import mcp_client  # noqa: E402

ok = True


def check(ten, dk):
    global ok
    print(("  ok   " if dk else "  FAIL ") + ten)
    ok = ok and bool(dk)


class Pool(mcp_client.SessionPool):
    def __init__(self):
        super().__init__()
        self.lan = 0
        self.hong = True

    async def _retry(self, spec, op, idempotent=True, ban=False):
        self.lan += 1
        if self.hong:
            raise RuntimeError("không khởi động được")
        return []


p = Pool()
spec = {"key": "k1", "label": "Nguồn thử"}
r1 = asyncio.run(p.call_tool(spec, "t", {}))
r2 = asyncio.run(p.call_tool(spec, "t", {}))
check("lần đầu hỏng thật", r1.startswith("ERROR: gọi tool lỗi"))
check("lần sau báo ngay, không chạm nguồn nữa", r2.startswith("ERROR: nguồn") and p.lan == 1)
p.hong = False
asyncio.run(p.list_tools(spec))
r3 = asyncio.run(p.call_tool(spec, "t", {}))
check("Kiểm tra thành công thì dùng lại ngay", not str(r3).startswith("ERROR") and p.lan == 3)

if not ok:
    sys.exit(1)
print("\nđạt")
