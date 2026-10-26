"""Facebook Trang (26.10.252): danh sách Trang lật trang (không dừng ở 200), và đưa ID Trang không có
trong danh sách thì MinMin hỏi thẳng Facebook trên từng tài khoản đã nối. Không mạng.

    python tests/run.py meta_pages_lat_trang
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-metalat-"))
_fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        _fails.append(n)


spec = importlib.util.spec_from_file_location("t_meta_pages_lat", str(ROOT / "system" / "plugins" / "meta-pages-graph" / "plugin.py"))
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)

CONNS = [{"id": "c_a", "label": "Trung - Tố Khuyên", "is_default": True},
         {"id": "c_b", "label": "Khang - HB Vũ", "is_default": False}]
TOK = {"c_a": "U_A", "c_b": "U_B"}
calls = []


async def tok_of(cid):
    return TOK[cid]


async def fget(path, params, token):
    calls.append((path, dict(params or {}), token))
    if path == "me/accounts":
        if token == "U_A":
            if not params.get("after"):
                return {"data": [{"id": str(i), "name": f"Trang {i}", "access_token": f"PT{i}", "tasks": ["MANAGE"]}
                                 for i in range(200)],
                        "paging": {"cursors": {"after": "CUR2"}, "next": "https://graph.facebook.com/x"}}
            return {"data": [{"id": "9001", "name": "Trang thứ 201", "access_token": "PT9001", "tasks": ["MANAGE"]}],
                    "paging": {"cursors": {"after": "CUR3"}}}
        return {"data": []}
    if path == "55555555":   # Trang chủ cầm (biên tập) mà danh sách không có; chỉ tài khoản B nhận token
        if token == "U_B":
            return {"id": "55555555", "name": "Hoa Trà Boutique", "access_token": "PT_HT", "tasks": ["CREATE_CONTENT"]}
        return {"id": "55555555", "name": "Hoa Trà Boutique"}
    if path == "66666666":
        return {"error": {"message": "Unsupported get request.", "code": 100}}
    return {"data": []}


posted = []


async def fpost(path, data, token):
    posted.append((path, token))
    return {"id": "x_1"}


async def chay():
    pg._conns = lambda: list(CONNS)
    pg._token_of = tok_of
    pg._get = fget
    pg._post = fpost
    r = json.loads(await pg._list({}, None))
    ids = {p["id"] for p in r}
    check("lật trang: lấy đủ 201 Trang (trang thứ hai qua con trỏ after)", len(ids) == 201 and "9001" in ids, len(ids))
    check("gửi đúng con trỏ after ở lần gọi thứ hai",
          any(c[0] == "me/accounts" and c[1].get("after") == "CUR2" for c in calls))

    pid, ptok, name, err = await pg._resolve_page({"page_id": "55555555"})
    check("ID không có trong danh sách: hỏi thẳng, dùng tài khoản nhận được token Trang",
          pid == "55555555" and ptok == "PT_HT" and not err, (pid, err))
    check("ghi nhận tài khoản đã dùng", pg._PAGE_OWNER.get("55555555") == "Khang - HB Vũ")
    out = json.loads(await pg._publish({"page_id": "55555555", "message": "chào"}, None))
    check("đăng lên Trang lấy theo ID dùng token Trang đó", posted[-1] == ("55555555/feed", "PT_HT"), posted[-1:])
    check("kết quả đăng báo tài khoản Facebook đã dùng", out.get("tai_khoan") == "Khang - HB Vũ", out)

    _, _, _, err = await pg._resolve_page({"page_id": "66666666"})
    check("ID không ai được giao: báo lỗi trỏ sang Soi quyền, không đoán",
          err and err.startswith("ERROR") and "Soi quyền" in err, err)
    _, _, _, err = await pg._resolve_page({"page": "không có trang này"})
    check("tên lạ vẫn báo như cũ", err and "Không khớp" in err, err)


asyncio.run(chay())
print("\n" + ("TẤT CẢ OK" if not _fails else f"{len(_fails)} LỖI: {_fails}"))
sys.exit(1 if _fails else 0)
