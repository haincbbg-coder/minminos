"""Bản riêng của học viên (26.10.78): cổng chuyển sang container riêng, không rò cookie, fail-closed.

    python tests/run.py member_tenant
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import socket
import tempfile
import threading
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-ten-")
os.environ["BRAINS_DIR"] = tempfile.mkdtemp(prefix="javis-ten-b-")
os.environ["JAVIS_REQUIRE_LOGIN"] = "1"
import uvicorn  # noqa: E402
from fastapi import FastAPI, Form, Request, WebSocket  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import members  # noqa: E402
import tenants  # noqa: E402
import totp  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---- "Container học viên" giả: đòi đăng nhập nội bộ, ghi lại cookie/host/origin nhận được ----
up = FastAPI()
SEEN = {}


@up.get("/health")
async def _h():
    return {"status": "ok"}


@up.post("/auth/login")
async def _login(username: str = Form(...), password: str = Form(...)):
    if (username, password) != ("tenant", "mat-khau-noi-bo"):
        return JSONResponse({"ok": False}, status_code=401)
    r = JSONResponse({"ok": True})
    r.set_cookie("javis_session", "TENANT-SESSION-1", path="/")
    return r


def _auth(req):
    return req.cookies.get("javis_session") == "TENANT-SESSION-1"


@up.get("/auth/status")
async def _st(request: Request):
    return {"authed": _auth(request), "from": "tenant"}


@up.get("/ten")
async def _ten(request: Request):
    if not _auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    SEEN["cookie"] = request.headers.get("cookie")
    SEEN["host"] = request.headers.get("host")
    SEEN["origin"] = request.headers.get("origin")
    return {"who": "tenant", "q": dict(request.query_params)}


@up.post("/echo")
async def _echo(request: Request):
    if not _auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"len": len(await request.body())}


@up.get("/stream")
async def _stream(request: Request):
    async def g():
        for i in range(3):
            yield ("chunk%d\n" % i).encode()
    return StreamingResponse(g(), media_type="text/plain")


@up.websocket("/ws/echo")
async def _ws(ws: WebSocket):
    if ws.cookies.get("javis_session") != "TENANT-SESSION-1":
        await ws.close(code=1008)
        return
    await ws.accept()
    while True:
        try:
            t = await ws.receive_text()
        except Exception:
            return
        await ws.send_text("tenant:" + t)


s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
srv = uvicorn.Server(uvicorn.Config(up, host="127.0.0.1", port=PORT, log_level="error"))
threading.Thread(target=srv.run, daemon=True).start()
for _ in range(50):
    try:
        socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
    except OSError:
        time.sleep(0.1)

adm = TestClient(main.app, base_url="http://localhost")
adm.post("/auth/setup", data={"username": "admin", "password": "matkhau-admin-1"})
adm.post("/members", data={"email": "hv@example.com", "name": "HV", "password": "matkhau-hv-001", "grants": "{}"})
adm.post("/members", data={"email": "khac@example.com", "name": "Khac", "password": "matkhau-khac-01", "grants": "{}"})


def vao(email, pw):
    c = TestClient(main.app, base_url="http://localhost")
    r = c.post("/auth/login", data={"username": email, "password": pw})
    s = c.post("/m/2fa/start").json()
    c.post("/m/2fa/enable", data={"code": totp.ma_cua_buoc(s["secret"], totp.buoc_hien_tai())})
    return c


hv = vao("hv@example.com", "matkhau-hv-001")
khac = vao("khac@example.com", "matkhau-khac-01")

# --- chưa có bản riêng: đi đường cũ, không vào được endpoint admin ---
check("chưa có tenant: /ten bị chặn", hv.get("/ten").status_code in (403, 404))

# --- đặt tenant ---
r = adm.post("/members/tenant/set", data={"email": "hv@example.com", "url": "http://127.0.0.1:%d" % PORT,
                                          "user": "tenant", "password": "mat-khau-noi-bo"})
check("admin đặt tenant", r.status_code == 200, r.text)
check("url sai bị từ chối", adm.post("/members/tenant/set", data={"email": "hv@example.com", "url": "file:///etc", "password": "x"}).status_code == 400)
check("danh sách có tenant, không lộ mật khẩu", "mat-khau-noi-bo" not in adm.get("/members").text and "127.0.0.1" in adm.get("/members").text)
check("mật khẩu nội bộ được mã hóa trên đĩa", "mat-khau-noi-bo" not in (members._PATH.read_text(encoding="utf-8")))
check("học viên không tự đặt tenant", hv.post("/members/tenant/set", data={"email": "hv@example.com", "url": "http://evil:1", "password": "x"}).status_code in (403, 404) and "evil" not in members._PATH.read_text(encoding="utf-8"))

hv.headers.update({"Origin": "https://minmin.example.com"})
r = hv.get("/ten?x=1", headers={"cookie": "javis_session=" + hv.cookies.get("javis_session", "")})
check("học viên có tenant đi qua cổng", r.status_code == 200 and r.json() == {"who": "tenant", "q": {"x": "1"}}, r.text)
check("cookie phiên thành viên KHÔNG rò sang tenant", "TENANT-SESSION-1" in SEEN.get("cookie", "") and hv.cookies.get("javis_session", "x") not in SEEN.get("cookie", ""), SEEN)
check("Origin được chuyển nguyên", SEEN.get("origin") == "https://minmin.example.com")
check("trình duyệt không nhận cookie của tenant", "TENANT-SESSION-1" not in str(r.headers) and "TENANT-SESSION-1" not in str(hv.cookies))
check("POST có body", hv.post("/echo", content=b"x" * 5000).json() == {"len": 5000})
check("stream", hv.get("/stream").text == "chunk0\nchunk1\nchunk2\n")
check("auth/status là của tenant", hv.get("/auth/status").json().get("from") == "tenant")
check("chặn /auth/login của tenant", hv.post("/auth/login", data={"username": "tenant", "password": "x"}).status_code == 403)
check("chặn /auth/setup của tenant", hv.post("/auth/setup", data={"username": "a", "password": "12345678"}).status_code == 403)
check("chặn /m/files của bản gốc", hv.get("/m/brains").status_code == 403)
with hv.websocket_connect("/ws/echo", headers={"cookie": "javis_session=" + hv.cookies.get("javis_session", "")}) as ws:
    ws.send_text("xin chào")
    check("WebSocket qua cổng", ws.receive_text() == "tenant:xin chào")

# --- người khác không có tenant không đi nhầm ---
check("học viên khác không thấy bản này", khac.get("/ten").status_code in (403, 404))
anon = TestClient(main.app, base_url="http://localhost")
check("khách chưa đăng nhập bị 401", anon.get("/ten").status_code == 401)
try:
    with anon.websocket_connect("/ws/echo") as ws:
        ws.receive_text()
    check("khách không vào WebSocket", False)
except Exception:
    check("khách không vào WebSocket", True)
# admin vẫn vào app của mình, không bị chuyển sang tenant
check("admin vẫn dùng bản gốc", adm.get("/members").status_code == 200)

# --- tenant chết: fail-closed, không rơi về bản của chủ ---
srv.should_exit = True
time.sleep(1.5)
members._TENANT_COOKIE.clear()
r = hv.get("/ten")
check("tenant sập thì 502, không rơi về bản gốc", r.status_code == 502, (r.status_code, r.text[:80]))
r = hv.get("/members")
check("tenant sập vẫn không vào được admin", r.status_code == 502)

# --- đăng xuất ---
hv.headers.pop("Origin", None); _lo = hv.post("/auth/logout"); _me = hv.get("/m/me"); check("đăng xuất kết thúc phiên", _lo.status_code == 200 and _me.status_code == 401, (_lo.status_code, _lo.text[:80], _me.status_code, _me.text[:80]))

# --- khóa thì mất quyền ngay ---
adm.post("/members/update", data={"email": "khac@example.com", "disabled": "1"})
check("bị khóa thì mất phiên", khac.get("/m/me").status_code == 401)

# --- provisioner (mock Docker) ---
calls = []


def fake(method, path, body=None):
    calls.append((method, path, body))
    if path.startswith("/containers/") and path.endswith("/json") and method == "GET" and "minmin-m-" not in path:
        return 200, {"Config": {"Image": "ghcr.io/x/minmin:1"}, "NetworkSettings": {"Networks": {"javis-web": {}}}}
    if path.startswith("/containers/create"):
        return 201, {"Id": "abc"}
    return 204, {}


tenants._docker = fake
os.environ["HOSTNAME"] = "gateway123"
t = tenants.tao("hv@example.com", "minmin.example.com")
body = [c for c in calls if c[1].startswith("/containers/create")][0][2]
hc = body["HostConfig"]
check("container: không publish cổng, không đặc quyền", hc["PublishAllPorts"] is False and hc["Privileged"] is False and "PortBindings" not in hc)
check("container: bỏ capability + giới hạn RAM/CPU", hc["CapDrop"] == ["ALL"] and hc["Memory"] > 0 and hc["NanoCpus"] > 0)
check("container: volume riêng theo học viên", all(b.startswith(tenants.ten("hv@example.com")) for b in hc["Binds"]) and len(hc["Binds"]) == 4)
check("container: không gắn socket Docker/thư mục host", not any("docker.sock" in b or b.startswith("/") for b in hc["Binds"]))
check("container: cùng mạng với cổng", hc["NetworkMode"] == "javis-web")
check("container: cho phép tên miền công khai", "minmin.example.com" in str(body["Env"]) and "JAVIS_TENANT=1" in body["Env"])
check("tạo trả url nội bộ + mật khẩu ngẫu nhiên", t["url"].startswith("http://minmin-m-") and len(t["password"]) >= 24)
check("tên container khác nhau theo email", tenants.ten("a@x.com") != tenants.ten("b@x.com"))

print("\n%d lỗi" % len(fails))
raise SystemExit(1 if fails else 0)
