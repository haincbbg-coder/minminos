# -*- coding: utf-8 -*-
"""Đăng nhập gói Google (Antigravity CLI) NGAY TRÊN TRANG MODELS, không cần Terminal.

    python tests/run.py agy_dang_nhap_tren_trang     (KHÔNG mạng)

Chủ MinMin ẩn trang Code (Terminal), nên đường "gõ `agy` trong Terminal" là đường cụt. Từ
26.10.205 thẻ Models có Cài đặt + Đăng nhập Google khuôn Claude: máy chủ chạy `agy` trong pty,
bóc link Google đưa lên trang, nhận lại địa chỉ localhost người dùng dán.

Test chạy một `agy` GIẢ (script Python) đóng đúng hai vai đã biết của bản thật: in link rồi chờ
dán (luồng phiên từ xa), hoặc chỉ mở cổng loopback và không hỏi gì (luồng cũ). Cả hai phải đăng
nhập được - đường thứ hai nhờ máy chủ tự gọi cổng callback.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
import textwrap
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


import antigravity_cli as ag  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="agy-gia-"))
DAU = TMP / "da_dang_nhap"

GIA = textwrap.dedent(f'''\
    #!{sys.executable}
    import os, sys, socket, threading, http.server, time
    DAU = {str(DAU)!r}
    a = sys.argv[1:]
    if a[:1] == ["--help"]:
        print("Usage: agy [--model M] [-p PROMPT]"); sys.exit(0)
    if a[:1] == ["models"]:
        if os.path.exists(DAU):
            print("Fetching available models...")
            print("gemini-3-pro-high\\tGemini 3 Pro (High)"); sys.exit(0)
        print("not logged in", file=sys.stderr); sys.exit(1)
    che_do = os.environ.get("AGY_GIA_CHE_DO", "dan")
    # Mở cổng loopback như bản thật (cả hai luồng đều mở).
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if "code=ma-dung" in self.path:
                open(DAU, "w").write("x")
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        def log_message(self, *x): pass
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    cong = s.server_address[1]
    open(DAU + ".cong", "w").write(str(cong))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    print("Welcome to Antigravity CLI")
    print("Sign in with Google: https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&redirect_uri=http%3A%2F%2Flocalhost%3A" + str(cong), flush=True)
    if che_do == "dan" and os.environ.get("SSH_CONNECTION"):
        print("Paste the callback URL here:", flush=True)
        dong = sys.stdin.readline()
        if "code=ma-dung" in dong:
            open(DAU, "w").write("x")
            print("Signed in.", flush=True)
    while True:
        time.sleep(1)
''')
bin_gia = TMP / "agy"
bin_gia.write_text(GIA, encoding="utf-8")
bin_gia.chmod(0o755)
os.environ["JAVIS_AGY_BIN"] = str(bin_gia)

if os.name == "nt":
    print("bỏ qua: test dùng pty, chỉ chạy trên POSIX")
    sys.exit(0)

# 1. Che bí mật: mã OAuth trong địa chỉ callback không bao giờ vào nhật ký.
ag._LOGIN["log"] = __import__("collections").deque(maxlen=10)
ag._ghi(ag._LOGIN, "http://localhost:4567/oauth-callback?code=4/0AbcSECRET&state=x")
check("nhật ký che code= trong URL", "SECRET" not in " ".join(ag._nhat_ky(ag._LOGIN)))

# 2. Ô dán không biến thành công cụ gọi địa chỉ tuỳ ý từ máy chủ.
check("không gọi địa chỉ ngoài localhost",
      ag._goi_callback_noi_bo("http://169.254.169.254/latest/meta-data").startswith("bỏ qua"))
check("không gọi host giả localhost", ag._goi_callback_noi_bo(
    "http://localhost.evil.com/x").startswith("bỏ qua"))
check("link localhost không bị coi là link đăng nhập",
      not ag._la_link_dang_nhap("http://localhost:1234/oauth-callback"))


def chay(che_do: str):
    for p in (DAU, Path(str(DAU) + ".cong")):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    os.environ["AGY_GIA_CHE_DO"] = che_do
    ag._xoa_cache_auth()
    r = ag.login_start(cho_giay=15)
    check(f"[{che_do}] login_start trả link Google", r.get("ok") and "accounts.google.com" in r.get("url", ""))
    cong = Path(str(DAU) + ".cong").read_text()
    d = ag.login_code(f"http://localhost:{cong}/oauth-callback?code=ma-dung&state=s", cho_giay=12)
    check(f"[{che_do}] login_code báo đã kết nối", d.get("ok") and d.get("connected"))
    check(f"[{che_do}] tiến trình agy đã được tắt sau khi xong", ag._LOGIN.get("proc") is None)


chay("dan")        # bản có ô dán (phiên từ xa)
chay("loopback")   # bản chỉ mở cổng, không hỏi - máy chủ tự gọi callback

# 3. Dán khi phiên đã đóng thì nói rõ, không treo.
d = ag.login_code("http://localhost:1/x?code=a", cho_giay=1)
check("dán khi phiên đã đóng báo het_phien", d.get("het_phien") is True)

# 4. Thẻ Models có nút thật, không còn chỉ đưa lệnh terminal.
js = (ROOT / "dashboard" / "console.js").read_text(encoding="utf-8")
check("thẻ có nút Đăng nhập Google", "data-agylogin" in js and "/antigravity/login-code" in js)
check("thẻ có nút Cài đặt", "data-agyinstall" in js and "/antigravity/install" in js)
src = (SERVER / "main.py").read_text(encoding="utf-8")
for duong in ("/antigravity/install", "/antigravity/login-start", "/antigravity/login-code"):
    check(f"có endpoint {duong}", f'"{duong}"' in src)

if _fails:
    print(f"\n{len(_fails)} FAIL")
    sys.exit(1)
print("\nTất cả OK")
