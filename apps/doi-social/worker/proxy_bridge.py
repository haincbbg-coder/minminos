"""Loopback proxy adapter: keep upstream credentials off Chrome command lines.

HTTP/HTTPS proxies support Basic auth; SOCKS5 supports username/password and remote
DNS. There is no direct-network fallback when an upstream proxy fails.
"""
import base64
import selectors
import socket
import socketserver
import ssl
import threading
from urllib.parse import urlsplit


def exact(sock, size):
    data = b''
    while len(data) < size:
        chunk = sock.recv(size-len(data))
        if not chunk:
            raise OSError('proxy closed')
        data += chunk
    return data


def headers(sock):
    data = b''
    while not data.endswith(b'\r\n\r\n'):
        data += exact(sock, 1)
        if len(data) > 65536:
            raise OSError('proxy headers too large')
    return data


class ProxyBridge:
    def __init__(self, config):
        self.config = config
        self.stopped = threading.Event()
        self.capacity = threading.BoundedSemaphore(64)
        bridge = self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                if not bridge.capacity.acquire(blocking=False):
                    return
                try:
                    bridge.handle(self.request)
                finally:
                    bridge.capacity.release()
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True
        self.server = Server(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_address[1])

    def dial(self, host, port):
        p = urlsplit(self.config['server'])
        upstream = socket.create_connection((p.hostname, p.port), timeout=15)
        try:
            if p.scheme == 'https':
                upstream = ssl.create_default_context().wrap_socket(upstream, server_hostname=p.hostname)
            if p.scheme == 'socks5':
                user = self.config.get('username', '').encode()
                password = self.config.get('password', '').encode()
                upstream.sendall(b'\x05\x01' + (b'\x02' if user else b'\x00'))
                method = exact(upstream, 2)
                if method != b'\x05' + (b'\x02' if user else b'\x00'):
                    raise OSError('proxy auth unavailable')
                if user:
                    if len(user) > 255 or len(password) > 255:
                        raise OSError('proxy credentials too long')
                    upstream.sendall(b'\x01' + bytes([len(user)]) + user + bytes([len(password)]) + password)
                    if exact(upstream, 2) != b'\x01\x00':
                        raise OSError('proxy auth rejected')
                domain = host.encode('idna')
                if len(domain) > 255:
                    raise OSError('hostname too long')
                upstream.sendall(b'\x05\x01\x00\x03' + bytes([len(domain)]) + domain + port.to_bytes(2, 'big'))
                reply = exact(upstream, 4)
                if reply[:2] != b'\x05\x00':
                    raise OSError('proxy connect rejected')
                length = {1: 4, 4: 16}.get(reply[3])
                if reply[3] == 3:
                    length = exact(upstream, 1)[0]
                if length is None:
                    raise OSError('proxy response invalid')
                exact(upstream, length+2)
            else:
                authority = ('[' + host + ']' if ':' in host else host) + ':' + str(port)
                auth = ''
                if self.config.get('username'):
                    credential = (self.config['username'] + ':' + self.config.get('password', '')).encode()
                    auth = 'Proxy-Authorization: Basic ' + base64.b64encode(credential).decode() + '\r\n'
                upstream.sendall(('CONNECT ' + authority + ' HTTP/1.1\r\nHost: ' + authority + '\r\n' + auth + '\r\n').encode())
                response = headers(upstream)
                if response.split(b' ', 2)[1] != b'200':
                    raise OSError('proxy connect rejected')
            return upstream
        except BaseException:
            upstream.close()
            raise

    def handle(self, client):
        upstream = None
        try:
            client.settimeout(20)
            request = headers(client)
            first, *lines = request.decode('iso-8859-1').split('\r\n')
            method, target, version = first.split(' ', 2)
            if method == 'CONNECT':
                dest = urlsplit('https://' + target)
                host, port = dest.hostname, dest.port or 443
            else:
                dest = urlsplit(target)
                if dest.scheme != 'http' or not dest.hostname:
                    raise OSError('invalid proxy target')
                host, port = dest.hostname, dest.port or 80
            upstream = self.dial(host, port)
            if method == 'CONNECT':
                client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            else:
                path = (dest.path or '/') + ('?' + dest.query if dest.query else '')
                clean = [line for line in lines if line and not line.lower().startswith(('proxy-authorization:', 'proxy-connection:'))]
                upstream.sendall((method + ' ' + path + ' ' + version + '\r\n' + '\r\n'.join(clean) + '\r\n\r\n').encode('iso-8859-1'))
            client.settimeout(None)
            upstream.settimeout(None)
            with selectors.DefaultSelector() as select:
                select.register(client, selectors.EVENT_READ, upstream)
                select.register(upstream, selectors.EVENT_READ, client)
                idle = 0
                while not self.stopped.is_set() and idle < 120:
                    events = select.select(1)
                    idle = 0 if events else idle+1
                    for key, _ in events:
                        data = key.fileobj.recv(65536)
                        if not data:
                            return
                        key.data.sendall(data)
        except (OSError, ValueError, IndexError):
            try:
                client.sendall(b'HTTP/1.1 502 Proxy unavailable\r\nContent-Length: 0\r\n\r\n')
            except OSError:
                pass
        finally:
            if upstream:
                upstream.close()

    def close(self):
        self.stopped.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
