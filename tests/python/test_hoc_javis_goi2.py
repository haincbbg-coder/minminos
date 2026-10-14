"""Gói học Javis 2: kiểm nguồn gốc WebSocket, cắt dấu cách mật khẩu, giờ trực chatbot (26.10.160).

    python tests/run.py hoc_javis_goi2
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile
from datetime import datetime

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-goi2-")
import chatbot_store  # noqa: E402
import config as cfgmod  # noqa: E402
import web_security  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


# 1) WebSocket
d = web_security.ws_decision
check("cùng host qua", d("localhost:8000", "http://localhost:8000", False) is None)
check("không Origin (CLI, curl) qua", d("localhost:8000", None, False) is None)
r = d("localhost:8000", "https://trang-la.example", False)
check("Origin trang lạ bị chặn khi chưa có mật khẩu", r and r[0] == 403, r)
r = d("localhost:8000", "https://trang-la.example", True)
check("Origin trang lạ bị chặn cả khi đã có cổng đăng nhập", r and r[0] == 403, r)
r = d("minmin.example.com", "https://minmin.example.com", True)
check("tên miền thật cùng nguồn gốc qua", r is None, r)
check("Host méo bị từ chối", (d("a/b", None, False) or (0,))[0] == 400)
src = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
check("cả 4 endpoint WebSocket đều gọi _ws_chan_nguon", src.count("if _ws_chan_nguon(ws)") == 4, src.count("if _ws_chan_nguon(ws)"))

# 2) Mật khẩu có dấu cách thừa
h, salt = cfgmod.hash_password("matkhau123")
cfg = {"auth": {"password_hash": h, "salt": salt}}
check("đúng mật khẩu", cfgmod.verify_password("matkhau123", cfg))
check("mật khẩu dính dấu cách thừa vẫn vào được", cfgmod.verify_password("  matkhau123 \n", cfg))
check("sai mật khẩu vẫn bị từ chối", not cfgmod.verify_password("matkhau124", cfg))
h2, s2 = cfgmod.hash_password("co dau cach ")
check("mật khẩu cũ lỡ có dấu cách ở rìa vẫn khớp đúng như gõ", cfgmod.verify_password("co dau cach ", {"auth": {"password_hash": h2, "salt": s2}}))

# Tài khoản đã băm từ bản CÓ dấu cách thừa (trước khi có luật cắt): cập nhật xong KHÔNG bị đặt lại.
cfgmod.write_settings({"auth": {}})
os.environ["JAVIS_ADMIN_PASSWORD"] = "envpass999 "
os.environ.pop("JAVIS_ADMIN_USER", None)
check("env tạo tài khoản lần đầu", cfgmod.provision_admin_from_env() == "created")
c = cfgmod.read_settings()
check("mật khẩu env được cắt dấu cách rồi mới băm", cfgmod.verify_password("envpass999", c))
check("gõ lại đúng như trong env (có dấu cách) vẫn vào", cfgmod.verify_password("envpass999 ", c))
check("khởi động lại với cùng giá trị thì KHÔNG đặt lại", cfgmod.provision_admin_from_env() == "")
# dấu đã ghi từ bản cũ băm trên chuỗi thô
import secrets as _s
c = cfgmod.read_settings()
a = dict(c["auth"])
ms = _s.token_hex(16)
a["env_applied"] = {"username": "admin", "hash": cfgmod.hash_password("envpass999 ", ms)[0], "salt": ms}
c["auth"] = a
cfgmod.write_settings(c)
check("dấu cũ băm từ chuỗi có dấu cách vẫn coi là cùng giá trị", cfgmod.provision_admin_from_env() == "")
os.environ["JAVIS_ADMIN_PASSWORD"] = "doi-hanBan2"
check("đổi giá trị thật thì vẫn đặt lại", cfgmod.provision_admin_from_env() == "reset")

# 3) Giờ trực
def luc(h, m):
    return datetime(2026, 10, 14, h, m)

b = {"gio_truc_tu": "08:00", "gio_truc_den": "17:30"}
check("trong giờ", chatbot_store.trong_gio_truc(b, luc(9, 0)))
check("đúng giờ bắt đầu thì trực", chatbot_store.trong_gio_truc(b, luc(8, 0)))
check("đúng giờ kết thúc thì hết trực", not chatbot_store.trong_gio_truc(b, luc(17, 30)))
check("ngoài giờ", not chatbot_store.trong_gio_truc(b, luc(3, 0)))
n = {"gio_truc_tu": "22:00", "gio_truc_den": "02:00"}
check("qua nửa đêm: 23:00 trực", chatbot_store.trong_gio_truc(n, luc(23, 0)))
check("qua nửa đêm: 01:00 trực", chatbot_store.trong_gio_truc(n, luc(1, 0)))
check("qua nửa đêm: 12:00 không trực", not chatbot_store.trong_gio_truc(n, luc(12, 0)))
check("để trống thì trực cả ngày", chatbot_store.trong_gio_truc({}, luc(3, 0)) and chatbot_store.trong_gio_truc({"gio_truc_tu": "08:00"}, luc(3, 0)))
check("giờ sai dạng bị bỏ qua, trực cả ngày", chatbot_store.trong_gio_truc({"gio_truc_tu": "abc", "gio_truc_den": "17:00"}, luc(3, 0)))
check("chuẩn hoá 8:05 thành 08:05", chatbot_store._clean_gio("8:05") == "08:05" and chatbot_store._clean_gio("25:00") == "")
rt = (ROOT / "server" / "chatbot_runtime.py").read_text(encoding="utf-8")
check("runtime chặn ngoài giờ trực nhưng vẫn ghi Hộp thư", "trong_gio_truc(cfg)" in rt and "ghi_tin_khach(cfg, meta or {}, text)\n            return {\"text\": \"\", \"files\": [], \"im_lang\": True}" in rt)

if fails:
    print("\nĐỎ:", fails)
    raise SystemExit(1)
print("\nxanh")
