"""Zalo Forwarder trên trình duyệt (26.10.4): cửa mã kích hoạt + điều khoản, danh sách hàm
cố định, tiến trình Node nền, chặn lấy file ngoài thư mục ảnh.

    python tests/python/test_zalo_forwarder.py      (KHÔNG mạng, không đăng nhập Zalo thật)

Phần chạy tiến trình Node thật cần `apps/zalo-forwarder/node_modules` (CI cài bằng `npm ci`).
Thiếu thì phần đó tự bỏ qua và in rõ là bỏ qua.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-zf-")
os.environ["JAVIS_STATE_DIR"] = _STATE
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import giay_phep  # noqa: E402
import routes.ket_noi_ngoai as knn  # noqa: E402
import routes.zalo_forwarder as zf  # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


giay_phep.STATE_DIR = Path(_STATE)
APP = Path(ROOT) / "apps" / "zalo-forwarder"

# ---- mã nguồn: hàm của giao diện, cổng Python và tiến trình Node phải khớp nhau
shim = (APP / "web" / "web-api.js").read_text(encoding="utf-8")
server_js = (APP / "server.js").read_text(encoding="utf-8")
ham_shim = set(re.findall(r'goi\("([A-Za-z]+)"\)', shim)) | {"loginQR", "loadConfig", "saveConfig"}
rpc_block = server_js.split("const RPC = {", 1)[1].split("\n};", 1)[0]
ham_node = set(re.findall(r"^  ([A-Za-z]+):", rpc_block, re.M))
check("mọi hàm giao diện gọi đều nằm trong danh sách cho phép", ham_shim <= zf.HAM, ham_shim - zf.HAM)
check("danh sách cho phép khớp đúng các hàm tiến trình Node có", zf.HAM == ham_node, zf.HAM ^ ham_node)
html = (APP / "web" / "index.html").read_text(encoding="utf-8")
scripts = set(re.findall(r'<(?:script src|link rel="stylesheet" href)="([^"]+)"', html))
check("index.html chỉ nạp file có trong danh sách phục vụ", scripts <= zf.WEB_FILES, scripts - zf.WEB_FILES)
check("web-api.js nạp TRƯỚC renderer.js (renderer đọc window.api lúc nạp)",
      html.index("web-api.js") < html.index("renderer.js"))
check("bản web không còn bootstrap.js của Electron", "bootstrap.js" not in html)
check("ô proxy riêng có trong hộp đăng nhập", 'id="login-proxy"' in html and "login-proxy" in shim)
em = [str(p.relative_to(APP)) for p in list((APP / "web").glob("*")) + list((APP / "core").glob("*.js"))
      + [APP / "server.js"] if "—" in p.read_text(encoding="utf-8")]
check("không có ký tự em dash trong mã app", not em, em)
svc = (APP / "core" / "zalo-service.js").read_text(encoding="utf-8")
check("lõi không còn tham chiếu bundle Electron", not re.search(r"require_\w+\(\)|init_dist|__commonJS", svc))
check("đăng nhập QR truyền user agent riêng của tài khoản", "userAgent: env.userAgent" in svc)

# ---- cửa: chưa mở khoá
app = FastAPI()
zf.register(app)
B = zf.GOC

with TestClient(app) as c:
    r = c.get(B + "/")
    check("chưa mở khoá: trang trả 403 kèm lời chỉ đường", r.status_code == 403 and "mã kích hoạt" in r.text)
    r = c.post(B + "/api/rpc/listAccounts", json={"args": []})
    check("chưa mở khoá: gọi hàm bị chặn 403", r.status_code == 403 and r.json()["ok"] is False)
    check("chưa mở khoá: file giao diện cũng khoá", c.get(B + "/renderer.js").status_code == 403)
    check("file lạ không phục vụ", c.get(B + "/server.js").status_code == 404
          and c.get(B + "/..%2Fserver.js").status_code == 404)
    check("trang-thai báo chưa được phép", c.get(B + "/api/trang-thai").json()["cho_phep"] is False)
    check("chưa mở khoá thì không bật tiến trình nền", not zf.TT.song())

    # ---- mở khoá (máy nhà phát hành) nhưng chưa đồng ý điều khoản
    giay_phep.tao_cap_khoa()
    r = c.post(B + "/api/rpc/listAccounts", json={"args": []})
    check("có mã mà chưa đồng ý điều khoản chung: vẫn chặn", r.status_code == 403 and "Điều khoản" in r.json()["error"])
    knn.ghi_dong_y("chung")
    r = c.post(B + "/api/rpc/listAccounts", json={"args": []})
    check("chưa đồng ý Phụ lục A (Zalo): vẫn chặn", r.status_code == 403 and "Phụ lục A" in r.json()["error"])
    knn.ghi_dong_y("zalo")
    r = c.get(B + "/")
    check("đủ điều kiện: trang mở", r.status_code == 200 and "web-api.js" in r.text)
    check("đủ điều kiện: file giao diện mở", c.get(B + "/web-api.js").status_code == 200)
    check("đường không có / cuối chuyển hướng", c.get(B, follow_redirects=False).status_code == 307)
    r = c.post(B + "/api/rpc/eval", json={"args": ["1"]})
    check("hàm ngoài danh sách bị chặn ở cổng Python", r.status_code == 404)

    co_node = (APP / "node_modules" / "zca-js").is_dir()
    if not co_node:
        print("skip phần chạy tiến trình Node thật (thiếu apps/zalo-forwarder/node_modules)")
    else:
        r = c.post(B + "/api/rpc/loadConfig", json={"args": []}).json()
        check("tiến trình nền bật khi cần, đọc cấu hình mặc định",
              r.get("ok") and isinstance(r["result"].get("routes"), list), r)
        check("tiến trình nền đang chạy", zf.TT.song())
        dl = Path(_STATE) / "zalo-forwarder"
        check("dữ liệu app nằm trong STATE, không nằm trong mã nguồn",
              (dl / "sessions").is_dir() and not (APP / ".data").exists())
        r = c.post(B + "/api/rpc/listAccounts", json={"args": []}).json()
        check("chưa có tài khoản nào", r.get("ok") and r["result"] == [], r)
        r = c.post(B + "/api/rpc/previewRules", json={"args": ["Giá 400k nhé", {
            "price": {"enabled": True, "mode": "add_amount", "amount": 50000}}]}).json()
        check("biên tập giá chạy qua cổng", r.get("result") == "Giá 450k nhé", r)
        cfg = {"account": "", "routes": [], "ruleSets": {}, "sending": {"minDelayMs": 1}}
        c.post(B + "/api/rpc/saveConfig", json={"args": [cfg]})
        r = c.post(B + "/api/rpc/loadConfig", json={"args": []}).json()
        check("lưu rồi đọc lại cấu hình", r.get("result", {}).get("sending") == {"minDelayMs": 1}, r)
        r = c.post(B + "/api/rpc/saveConfig", json={"args": [[1, 2]]}).json()
        check("cấu hình sai kiểu bị từ chối", r.get("ok") is False)
        r = c.post(B + "/api/upload?ten=a.png", content=b"\x89PNG\r\n\x1a\nxx").json()
        check("tải ảnh lên trả về tên file trong thư mục ảnh", r.get("ok") and re.fullmatch(r"[0-9a-f]{20}\.png", r["path"]), r)
        check("ảnh nằm trong STATE/zalo-forwarder/uploads", (dl / "uploads" / r["path"]).is_file())
        r = c.post(B + "/api/upload?ten=x.exe", content=b"x").json()
        check("đuôi lạ bị đổi về ảnh", r.get("path", "").endswith(".jpg"), r)
        # Không cho trình duyệt chỉ một file bất kỳ trên máy chủ rồi gửi nó lên Zalo
        r = c.post(B + "/api/rpc/broadcastSend", json={"args": ["acc", {
            "targets": [{"id": "1"}], "images": ["../../giay-phep/khoa-rieng.pem"]}]}).json()
        check("đăng nhóm: ảnh ngoài thư mục ảnh bị chặn", r.get("ok") is False and "khoa-rieng" not in str(r.get("result")), r)
        r = c.post(B + "/api/rpc/setProxy", json={"args": ["khong-co", "http://1.2.3.4:80"]}).json()
        check("đặt proxy cho tài khoản chưa có: báo lỗi", r.get("ok") is False)
        r = c.post(B + "/api/rpc/connect", json={"args": ["khong-co"]}).json()
        check("kết nối tài khoản chưa đăng nhập: báo cần QR", r.get("ok") is False and "QR" in r.get("error", ""), r)

        async def _su_kien():
            async with httpx.AsyncClient(timeout=10) as h:
                async with h.stream("GET", zf.TT.base + "/events", headers=zf.TT._hdr()) as s:
                    async for khuc in s.aiter_text():
                        return khuc
        dau = asyncio.run(_su_kien())
        check("luồng sự kiện mở bằng gói hello", "event: hello" in (dau or ""), dau)

        async def _khong_token():
            async with httpx.AsyncClient(timeout=5) as h:
                return (await h.post(zf.TT.base + "/rpc/listAccounts", json={"args": []})).status_code
        check("tiến trình Node từ chối gọi thiếu token", asyncio.run(_khong_token()) == 401)

    # ---- user agent riêng từng tài khoản (chạy bằng node, không cần mạng)
    if co_node:
        import subprocess
        out = subprocess.run(["node", "-e", (
            "const {pickUserAgent,cleanProxy}=require('./core/zalo-service.js');"
            "const a=new Set(['shop1','shop2','shop3','shop4','shop5'].map(pickUserAgent));"
            "let bad='';try{cleanProxy('socks5://x')}catch(e){bad='chan'}"
            "console.log(JSON.stringify({khac:a.size,on:pickUserAgent('shop1')===pickUserAgent('shop1'),bad}))")],
            cwd=str(APP), capture_output=True, text=True, timeout=30)
        import json
        d = json.loads(out.stdout.strip() or "{}")
        check("các tài khoản được gán trình duyệt khác nhau, cố định theo tên", d.get("khac", 0) >= 3 and d.get("on"), out.stderr)
        check("proxy sai dạng bị từ chối", d.get("bad") == "chan")

check("tắt server thì tiến trình nền tắt theo", not zf.TT.song())

print()
if _fails:
    print(f"FAILED {len(_fails)}: {_fails}")
    sys.exit(1)
print("ALL OK")
