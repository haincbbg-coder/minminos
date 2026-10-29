"""Bulk profile metadata and real authenticated proxy socket exchanges (no external network)."""
import base64
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import tempfile
import threading
os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp()
from _paths import ROOT
sys.path.insert(0, str(ROOT / 'apps/doi-social/worker'))
import profile_config as pc
from chrome_local import ChromeLocal, FileLock
from may_gpm import LoiGPM
from proxy_bridge import ProxyBridge, exact, headers

local = ChromeLocal(Path(tempfile.mkdtemp()))
base = str(Path(tempfile.mkdtemp()) / 'profiles')
batch = local.create_many({'name': 'Shop {n}', 'count': 3, 'start': 8, 'digits': 3, 'group': 'Shop', 'storage_root': base,
                           'proxy_lines': '127.0.0.1:8080:fixture-user:fixture-password'})
assert [p['ten'] for p in batch] == ['Shop 008', 'Shop 009', 'Shop 010']
assert all(Path(p['data_dir']).parent == Path(base) for p in batch)
assert 'fixture-password' not in pc.public_proxy(batch[0]['proxy'])
assert 'fixture-password' not in pc.public_proxy({'server': 'http://fixture-user:fixture-password@localhost:8080'})
old = local.create('Old folder')
local.storage(str(Path(tempfile.mkdtemp()) / 'new-storage'))
new = local.create('New folder')
assert Path(old['data_dir']).parent != Path(new['data_dir']).parent
assert local.profile(old['id'])['data_dir'] == old['data_dir']
with FileLock(local.root / (batch[1]['id'] + '.lock')):
    try:
        local.update_many([batch[0]['id'], batch[1]['id']], {'group': 'Must not partially update'})
        raise AssertionError('changed open profile')
    except LoiGPM:
        pass
assert local.profile(batch[0]['id'])['group'] == 'Shop'
local.update_many([p['id'] for p in batch], {'group': 'Group B', 'proxy': ''})
assert all(local.profile(p['id'])['group'] == 'Group B' and not local.profile(p['id'])['proxy'] for p in batch)
before = len(local.profiles())
for bad in ({'names': 'A\nA'}, {'name': 'A', 'count': 3, 'proxy_lines': 'localhost:8\nlocalhost:9'}):
    try:
        local.create_many(bad)
        raise AssertionError('invalid batch accepted')
    except ValueError:
        pass
assert len(local.profiles()) == before

def exchange(scheme):
    seen = []
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(3)
            if scheme == 'http':
                data = headers(self.request)
                assert b'CONNECT example.test:443' in data
                expected = base64.b64encode(b'user:password')
                assert b'Proxy-Authorization: Basic ' + expected in data
                self.request.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
            else:
                assert exact(self.request, 3) == b'\x05\x01\x02'
                self.request.sendall(b'\x05\x02')
                assert exact(self.request, 2) == b'\x01\x04'
                assert exact(self.request, 4) == b'user'
                assert exact(self.request, 1) == b'\x08'
                assert exact(self.request, 8) == b'password'
                self.request.sendall(b'\x01\x00')
                assert exact(self.request, 5) == b'\x05\x01\x00\x03\x0c'
                assert exact(self.request, 14) == b'example.test\x01\xbb'
                self.request.sendall(b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00')
            seen.append(exact(self.request, 8))
            self.request.sendall(b'echo-ok!')
    server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    bridge = ProxyBridge(pc.proxy(f'{scheme}://user:password@127.0.0.1:{server.server_address[1]}'))
    try:
        with socket.create_connection(bridge.server.server_address, timeout=3) as sock:
            sock.sendall(b'CONNECT example.test:443 HTTP/1.1\r\nHost: example.test:443\r\n\r\n')
            assert b'200' in headers(sock)
            sock.sendall(b'payload!')
            assert exact(sock, 8) == b'echo-ok!'
        assert seen == [b'payload!']
    finally:
        bridge.close(); server.shutdown(); server.server_close(); thread.join()
exchange('http'); exchange('socks5')
bridge = ProxyBridge(pc.proxy('http://127.0.0.1:1'))
try:
    with socket.create_connection(bridge.server.server_address, timeout=3) as sock:
        sock.sendall(b'CONNECT example.test:443 HTTP/1.1\r\n\r\n')
        assert b'502' in headers(sock)
finally:
    bridge.close()
print('PASS bulk names, groups, proxy redaction, custom folders, atomic busy locks, authenticated HTTP/SOCKS5 and no direct fallback')
