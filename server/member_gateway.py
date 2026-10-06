"""Cổng chuyển học viên vào BẢN MINMIN RIÊNG của họ (reverse proxy HTTP + WebSocket).

Mô hình: mỗi học viên có một container MinMin riêng (state, brain, đăng nhập AI, kết nối POS/Ads
đều riêng). Họ vào CHUNG tên miền; cổng này nhận ra phiên thành viên (đã qua 2FA) rồi chuyển
toàn bộ request sang container của họ. Trình duyệt KHÔNG BAO GIỜ nhận cookie của bản riêng:
cổng tự đăng nhập hộ bằng mật khẩu nội bộ rồi tự gắn cookie đó vào request đi.

Fail-closed:
- Thành viên có bản riêng mà bản đó không chạy: trả 502, TUYỆT ĐỐI không rơi về bản của chủ.
- Cookie của trình duyệt bị bỏ khỏi request đi; Set-Cookie của bản riêng bị bỏ khỏi phản hồi.
- /auth/* của bản riêng bị chặn (trừ /auth/status): học viên không đổi được mật khẩu nội bộ.
- Admin (phiên thật) và khách chưa đăng nhập đi thẳng vào app như cũ, không qua cổng.
"""
from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urlsplit

import httpx

import config as cfgmod
import members

COOKIE = "javis_session"
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
        "transfer-encoding", "upgrade", "content-length", "host"}
_AUTH_CHO_QUA = ("/auth/status",)
_LOGIN_LOCKS: dict = {}


def _cookie_cua(headers) -> str:
    for k, v in headers:
        if k == b"cookie":
            for part in v.decode("latin-1").split(";"):
                n, _, val = part.strip().partition("=")
                if n == COOKIE:
                    return val
    return ""


def _chan_auth(path: str) -> bool:
    return path.startswith("/auth/") and path not in _AUTH_CHO_QUA


async def _dang_nhap_ho(email: str, t: dict, host: str, client: httpx.AsyncClient) -> str:
    lock = _LOGIN_LOCKS.setdefault(email, asyncio.Lock())
    async with lock:
        r = await client.post(t["url"] + "/auth/login", data={"username": t["user"], "password": t["password"]},
                              headers={"host": host}, timeout=15)
        ck = r.cookies.get(COOKIE) or ""
        if r.status_code != 200 or not ck:
            return ""
        members._TENANT_COOKIE[email] = ck
        return ck


class MemberGateway:
    def __init__(self, app):
        self.app = app
        self._clients = {}

    def _http(self):
        # Một client cho mỗi event loop: httpx gắn kết nối vào loop đã tạo ra nó. Trên server chỉ có
        # một loop; nhiều loop chỉ xảy ra khi chạy test.
        loop = asyncio.get_running_loop()
        c = self._clients.get(id(loop))
        if c is None or c[0] is not loop:
            c = (loop, httpx.AsyncClient(timeout=httpx.Timeout(60, read=None), follow_redirects=False))
            self._clients = {id(loop): c}
        return c[1]

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        token = _cookie_cua(scope.get("headers") or [])
        if not token or cfgmod.valid_session(token):
            return await self.app(scope, receive, send)
        p = members.phien(token)
        if not p or not p["full"]:
            return await self.app(scope, receive, send)
        t = members.tenant_cua(p["user"])
        if not t:
            return await self.app(scope, receive, send)      # thành viên không có bản riêng
        path = scope.get("path", "")
        if scope["type"] == "http" and path in ("/auth/logout", "/m/logout"):
            scope = dict(scope, path="/m/logout", raw_path=b"/m/logout")
            return await self.app(scope, receive, send)
        if path.startswith("/m/") or _chan_auth(path):
            if scope["type"] == "http":
                return await self._loi(send, 403, "Không dùng được chức năng này trong bản riêng.")
            return await send({"type": "websocket.close", "code": 1008})
        if scope["type"] == "http":
            return await self._http_proxy(scope, receive, send, p, t)
        return await self._ws_proxy(scope, receive, send, p, t)

    # ---------- HTTP ----------
    async def _loi(self, send, code, msg):
        body = json.dumps({"ok": False, "error": msg}, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": code,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    def _header_di(self, scope, cookie: str):
        out = []
        host = ""
        for k, v in scope.get("headers") or []:
            kk = k.decode("latin-1").lower()
            if kk == "host":
                host = v.decode("latin-1")
            if kk in _HOP or kk == "cookie":
                continue
            out.append((kk, v.decode("latin-1")))
        out.append(("host", host))
        out.append(("cookie", COOKIE + "=" + cookie))
        return out, host

    async def _http_proxy(self, scope, receive, send, p, t):
        email = p["email"]
        c = self._http()
        host = ""
        for k, v in scope.get("headers") or []:
            if k == b"host":
                host = v.decode("latin-1")
        cookie = members._TENANT_COOKIE.get(email) or ""
        try:
            if not cookie:
                cookie = await _dang_nhap_ho(email, t, host, c)
            if not cookie:
                return await self._loi(send, 502, "Bản riêng của bạn chưa sẵn sàng. Thử lại sau ít phút.")
            body = b""
            while True:
                m = await receive()
                body += m.get("body", b"")
                if not m.get("more_body"):
                    break
            url = t["url"] + scope["path"] + (("?" + scope["query_string"].decode("latin-1")) if scope.get("query_string") else "")
            for lan in (0, 1):
                headers, _ = self._header_di(scope, cookie)
                req = c.build_request(scope["method"], url, headers=headers, content=body)
                r = await c.send(req, stream=True)
                if r.status_code == 401 and lan == 0:
                    await r.aclose()
                    cookie = await _dang_nhap_ho(email, t, host, c)
                    if not cookie:
                        return await self._loi(send, 502, "Bản riêng của bạn chưa sẵn sàng.")
                    continue
                break
        except (httpx.HTTPError, OSError):
            return await self._loi(send, 502, "Bản riêng của bạn chưa sẵn sàng. Thử lại sau ít phút.")
        hs = [(k.encode("latin-1"), v.encode("latin-1")) for k, v in r.headers.multi_items()
              if k.lower() not in _HOP and k.lower() != "set-cookie"]
        await send({"type": "http.response.start", "status": r.status_code, "headers": hs})
        try:
            async for chunk in r.aiter_raw():
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
        finally:
            await r.aclose()
        await send({"type": "http.response.body", "body": b""})

    # ---------- WebSocket ----------
    async def _ws_proxy(self, scope, receive, send, p, t):
        import websockets
        email = p["email"]
        host = ""
        origin = ""
        for k, v in scope.get("headers") or []:
            if k == b"host":
                host = v.decode("latin-1")
            elif k == b"origin":
                origin = v.decode("latin-1")
        cookie = members._TENANT_COOKIE.get(email) or await _dang_nhap_ho(email, t, host, self._http())
        if not cookie:
            await receive()
            return await send({"type": "websocket.close", "code": 1013})
        u = urlsplit(t["url"])
        url = ("wss" if u.scheme == "https" else "ws") + "://" + u.netloc + scope["path"]
        if scope.get("query_string"):
            url += "?" + scope["query_string"].decode("latin-1")
        hdr = {"Cookie": COOKIE + "=" + cookie, "Host": host}
        if origin:
            hdr["Origin"] = origin
        subs = scope.get("subprotocols") or None
        await receive()          # websocket.connect
        try:
            try:
                from websockets.asyncio.client import connect as _conn      # websockets >= 13
                up = await _conn(url, additional_headers=hdr, subprotocols=subs, max_size=None,
                                 open_timeout=15)
            except ImportError:
                up = await websockets.connect(url, extra_headers=hdr, subprotocols=subs, max_size=None,
                                              open_timeout=15)
        except Exception as ex:
            print("[gateway] ws upstream lỗi:", repr(ex), file=__import__("sys").stderr)
            return await send({"type": "websocket.close", "code": 1013})
        await send({"type": "websocket.accept", "subprotocol": up.subprotocol})

        async def den_up():
            while True:
                m = await receive()
                if m["type"] == "websocket.disconnect":
                    return
                if m.get("text") is not None:
                    await up.send(m["text"])
                elif m.get("bytes") is not None:
                    await up.send(m["bytes"])

        async def den_khach():
            async for msg in up:
                if isinstance(msg, bytes):
                    await send({"type": "websocket.send", "bytes": msg})
                else:
                    await send({"type": "websocket.send", "text": msg})

        tasks = [asyncio.ensure_future(den_up()), asyncio.ensure_future(den_khach())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for x in tasks:
                x.cancel()
            try:
                await up.close()
            except Exception:
                pass
            try:
                await send({"type": "websocket.close", "code": 1000})
            except Exception:
                pass
