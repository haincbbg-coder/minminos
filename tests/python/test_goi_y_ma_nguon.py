"""Tiện ích Gợi ý mã hàng gọi từ nguồn chrome-extension:// không bị luật CSRF chặn, nhưng đường quản lý vẫn bị.

    python3 tests/python/test_goi_y_ma_nguon.py
"""
from _paths import ROOT, SERVER  # noqa: F401
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-gym-nguon-"))
from fastapi.testclient import TestClient

import main

cl = TestClient(main.app, base_url="http://127.0.0.1:7777")
NGUON = {"origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop"}
ok = loi = 0


def kt(ten, dk):
    global ok, loi
    if dk:
        ok += 1
    else:
        loi += 1
        print("FAIL:", ten)


r = cl.post("/goi-y-ma/may/ghep", headers=NGUON, json={"ma": "000000"})
kt("ghép từ tiện ích không bị chặn nguồn (400 mã sai, không phải 403)", r.status_code == 400 and "web_security" not in r.text)
kt("lấy bảng không token = 401, không phải 403", cl.get("/goi-y-ma/may/bang", headers=NGUON).status_code == 401)
r = cl.post("/goi-y-ma/api/ma-ghep", headers=NGUON)
kt("đường quản lý vẫn chặn nguồn lạ", r.status_code == 403 and "web_security" in r.text)
r = cl.post("/goi-y-ma/api/ma-ghep", headers={"origin": "http://127.0.0.1:7777"})
kt("đường quản lý cùng nguồn không bị chặn bởi CSRF", "web_security" not in r.text)
print(f"goi_y_ma_nguon: {ok} đạt, {loi} lỗi")
sys.exit(1 if loi else 0)
