"""Cấp "bản riêng" cho học viên: một container MinMin riêng, tách hẳn khỏi bản của chủ.

Cần socket Docker (/var/run/docker.sock) gắn vào container MinMin của chủ. Không có socket thì
`co_docker()` trả False và giao diện chỉ hiện lệnh để chủ tự chạy trên VPS.

Container học viên: cùng ảnh với bản đang chạy, volume RIÊNG (data, brains, claude, codex), KHÔNG
publish cổng nào, nối cùng mạng Docker với cổng để cổng gọi tới được. Giới hạn RAM/CPU.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import secrets
import socket
import time

SOCK = os.getenv("JAVIS_DOCKER_SOCK", "/var/run/docker.sock")
RAM_MB = int(os.getenv("JAVIS_TENANT_RAM_MB", "1024"))
CPUS = float(os.getenv("JAVIS_TENANT_CPUS", "1.0"))


class _UnixConn(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=60)
        self._p = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(60)
        s.connect(self._p)
        self.sock = s


def _docker(method: str, path: str, body=None):
    """Gọi Docker Engine API. Trả (status, json|text). Ghi đè được trong test."""
    c = _UnixConn(SOCK)
    try:
        data = json.dumps(body).encode() if body is not None else None
        c.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
        r = c.getresponse()
        raw = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(raw) if raw else {}
        except ValueError:
            return r.status, raw
    finally:
        c.close()


def co_docker() -> bool:
    try:
        return os.path.exists(SOCK) and _docker("GET", "/_ping")[0] == 200
    except Exception:
        return False


def ten(email: str) -> str:
    h = hashlib.sha256(str(email).strip().lower().encode()).hexdigest()[:10]
    return "minmin-m-" + h


def _ban_goc():
    """(ảnh, danh sách mạng) của chính container MinMin đang chạy."""
    cid = os.getenv("HOSTNAME", "")
    st, j = _docker("GET", "/containers/%s/json" % cid)
    if st != 200 or not isinstance(j, dict):
        raise RuntimeError("Không đọc được container MinMin hiện tại qua Docker")
    img = (j.get("Config") or {}).get("Image") or j.get("Image")
    nets = list(((j.get("NetworkSettings") or {}).get("Networks") or {}).keys())
    return img, nets


def tao(email: str, domain: str) -> dict:
    """Tạo + chạy container. Trả {url, user, password} để cổng đăng nhập hộ."""
    name = ten(email)
    img, nets = _ban_goc()
    user, pw = "tenant", secrets.token_urlsafe(24)
    host = re.sub(r"^https?://", "", (domain or "").strip()).split("/")[0]
    env = ["JAVIS_ADMIN_USER=" + user, "JAVIS_ADMIN_PASSWORD=" + pw,
           "JAVIS_REQUIRE_LOGIN=1", "JAVIS_TENANT=1",
           "JAVIS_ALLOWED_HOSTS=" + ",".join(x for x in (host, name) if x),
           "DOMAIN_NAME=" + (host or "localhost")]
    cfg = {
        "Image": img, "Env": env,
        "Cmd": ["sh", "-c", "exec python -m uvicorn main:app --app-dir server --host 0.0.0.0 --port 7777"],
        "Labels": {"minmin.tenant": "1", "minmin.tenant.email_hash": name},
        "HostConfig": {
            "Binds": ["%s-data:/data" % name, "%s-brains:/brains" % name,
                      "%s-claude:/home/javis/.claude" % name, "%s-codex:/home/javis/.codex" % name],
            "RestartPolicy": {"Name": "unless-stopped"},
            "Memory": RAM_MB * 1024 * 1024, "NanoCpus": int(CPUS * 1e9),
            "NetworkMode": nets[0] if nets else "bridge",
            "PublishAllPorts": False, "Privileged": False,
            "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"],
        },
    }
    st, j = _docker("POST", "/containers/create?name=" + name, cfg)
    if st == 409:
        raise RuntimeError("Bản riêng của người này đã có")
    if st not in (200, 201):
        raise RuntimeError("Docker từ chối tạo container: %s" % (j,))
    st, j = _docker("POST", "/containers/%s/start" % name)
    if st not in (200, 204, 304):
        raise RuntimeError("Không chạy được container: %s" % (j,))
    return {"url": "http://%s:7777" % name, "user": user, "password": pw}


def trang_thai(email: str) -> str:
    st, j = _docker("GET", "/containers/%s/json" % ten(email))
    if st != 200:
        return "none"
    return "running" if (j.get("State") or {}).get("Running") else "stopped"


def dung(email: str) -> bool:
    return _docker("POST", "/containers/%s/stop" % ten(email))[0] in (204, 304)


def chay(email: str) -> bool:
    return _docker("POST", "/containers/%s/start" % ten(email))[0] in (204, 304)


def go(email: str, xoa_du_lieu: bool = False) -> bool:
    name = ten(email)
    _docker("POST", "/containers/%s/stop" % name)
    st, _ = _docker("DELETE", "/containers/%s?force=true" % name)
    if xoa_du_lieu:
        for v in ("data", "brains", "claude", "codex"):
            _docker("DELETE", "/volumes/%s-%s" % (name, v))
    return st in (204, 404)


def cho_san_sang(url: str, giay: int = 60) -> bool:
    import urllib.request
    t = time.time() + giay
    while time.time() < t:
        try:
            if urllib.request.urlopen(url + "/health", timeout=3).status == 200:
                return True
        except Exception:
            time.sleep(2)
    return False


def lenh_thu_cong(email: str, domain: str, image: str = "ghcr.io/blogminhquy/javis-os:latest") -> str:
    """Lệnh để chủ tự chạy trên VPS khi chưa gắn socket Docker."""
    name = ten(email)
    host = re.sub(r"^https?://", "", (domain or "").strip()).split("/")[0] or "ten-mien-cua-ban"
    return ("docker run -d --name %s --restart unless-stopped --memory %dm --cap-drop ALL "
            "--security-opt no-new-privileges:true --network <mang-cua-minmin> "
            "-e JAVIS_ADMIN_USER=tenant -e JAVIS_ADMIN_PASSWORD=<mat-khau-noi-bo> "
            "-e JAVIS_REQUIRE_LOGIN=1 -e JAVIS_ALLOWED_HOSTS=%s,%s "
            "-v %s-data:/data -v %s-brains:/brains -v %s-claude:/home/javis/.claude "
            "-v %s-codex:/home/javis/.codex %s sh -c \"exec python -m uvicorn main:app "
            "--app-dir server --host 0.0.0.0 --port 7777\"" % (
                name, RAM_MB, host, name, name, name, name, name, image))
