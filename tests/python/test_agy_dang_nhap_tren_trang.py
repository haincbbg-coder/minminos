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
    print("Welcome to the Antigravity CLI. You are currently not signed in.")
    if os.environ.get("AGY_GIA_MENU") == "1":
        # Đúng như bản thật (ảnh 2026-10-23): in menu rồi CHỜ một phím.
        print("Select login method:")
        print("> 1. Google OAuth")
        print("  2. Use a Google Cloud project", flush=True)
        phim = sys.stdin.readline()
        if phim.strip() not in ("", "1"):
            print("Google Cloud project flow", flush=True); time.sleep(60)
    link = ("https://accounts.google.com/o/oauth2/auth?access_type=offline&client_id=1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
            "&code_challenge=Ab12Cd34Ef56Gh78Ij90Kl12Mn34Op56Qr78St90Uv1&code_challenge_method=S256"
            "&redirect_uri=http%3A%2F%2Flocalhost%3A" + str(cong) + "%2Foauth-callback&response_type=code"
            "&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&state=xyz123")
    open(DAU + ".link", "w").write(link)
    print("Sign in with Google:", flush=True)
    if os.environ.get("AGY_GIA_BE") == "1":
        # Bản bẻ link xuống dòng theo 78 cột, bất kể màn hình rộng bao nhiêu (ảnh 2026-10-23:
        # MinMin 26.10.209 chỉ lấy dòng đầu, Google báo thiếu response_type).
        for i in range(0, len(link), 78):
            print("  " + link[i:i + 78], flush=True)
        print("", flush=True)
    else:
        print(link, flush=True)
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
    for p in (DAU, Path(str(DAU) + ".cong"), Path(str(DAU) + ".link")):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    os.environ["AGY_GIA_CHE_DO"] = che_do
    ag._xoa_cache_auth()
    r = ag.login_start(cho_giay=15)
    if not r.get("url"): print("   ->", r.get("error", "")[:400], r.get("xong"))
    check(f"[{che_do}] login_start trả link Google", r.get("ok") and "accounts.google.com" in r.get("url", ""))
    link_that = Path(str(DAU) + ".link").read_text()
    if r.get("url") and r.get("url") != link_that:
        print("   -> link nhận:", r.get("url")[:200], "...", len(r.get("url")), "vs", len(link_that))
    check(f"[{che_do}{' bẻ dòng' if os.environ.get('AGY_GIA_BE') else ''}] link đủ, không cụt (có response_type)",
          r.get("url") == link_that)
    cong = Path(str(DAU) + ".cong").read_text()
    d = ag.login_code(f"http://localhost:{cong}/oauth-callback?code=ma-dung&state=s", cho_giay=12)
    if not d.get("ok"):
        print("   ->", (d.get("error") or "")[:300], ag._nhat_ky(ag._LOGIN)[-6:])
    check(f"[{che_do}] login_code báo đã kết nối", d.get("ok") and d.get("connected"))
    check(f"[{che_do}] tiến trình agy đã được tắt sau khi xong", ag._LOGIN.get("proc") is None)


chay("dan")        # bản có ô dán (phiên từ xa)
os.environ["AGY_GIA_MENU"] = "1"
chay("dan")        # bản thật 2026-10-23: menu "Select login method" trước, phải tự chọn mục 1
os.environ["AGY_GIA_BE"] = "1"
chay("dan")        # link bị bẻ thành nhiều dòng 78 cột - phải nối lại đủ
os.environ.pop("AGY_GIA_BE", None)
os.environ.pop("AGY_GIA_MENU", None)
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
    if f'"{duong}"' not in src:
        print("   -> main.py đọc được", len(src), "ký tự")
    check(f"có endpoint {duong}", f'"{duong}"' in src)

if _fails:
    print(f"\n{len(_fails)} FAIL")
    sys.exit(1)
print("\nTất cả OK")
