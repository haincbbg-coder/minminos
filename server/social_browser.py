"""Managed Chromium profiles on the MinMin host; admin UI and local Social Worker.

DevTools stays on loopback. Only the built-in machine can obtain its endpoint,
for a running job assigned to that exact profile. User browser data stays in STATE_DIR.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
from urllib.parse import urlsplit

from fastapi import Request

import config
import doi_social as ds
import secrets_store

ROOT = Path(__file__).resolve().parents[1]


def desktop_available():
    return sys.platform in ('win32', 'darwin') or bool(os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY'))


def web_url(value):
    value = str(value or '').strip()
    u = urlsplit(value)
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
        raise ValueError('Chỉ mở địa chỉ http/https, không kèm mật khẩu trong link')
    return value


class BrowserHost:
    def __init__(self, root=None):
        self.root = Path(root or config.STATE_DIR / 'social-chrome')
        self.live = {}
        self.lock = asyncio.Lock()
        self.worker_lock = asyncio.Lock()
        self.pw = None
        self.worker = None
        self.worker_log = None
        self.install_task = None
        self.install_error = ''
        self.supervisor = None

    def read(self):
        p = self.root / 'profiles.json'
        return json.loads(p.read_text()) if p.exists() else {'enabled': False, 'profiles': []}

    def write(self, data):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        p = self.root / 'profiles.json'
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)

    def profiles(self):
        return self.read().get('profiles', [])

    def profile(self, pid):
        if not re.fullmatch(r'c[a-f0-9]{24}', pid):
            raise ValueError('Profile không hợp lệ')
        p = next((p for p in self.profiles() if p['id'] == pid), None)
        if not p:
            raise ValueError('Không có profile này')
        return p

    def executable(self):
        import optional_tools
        # Prefer the managed full browser; headless-shell is not a desktop Chromium.
        pats = ['chromium-*/chrome-linux*/chrome', 'chromium-*/chrome-win*/chrome.exe',
                'chromium-*/chrome-mac*/*.app/Contents/MacOS/*']
        for pattern in pats:
            matches = sorted((self.root / 'browsers').glob(pattern))
            if matches:
                return str(matches[-1])
        full = optional_tools.duong_dan_chrome()
        if full and 'headless_shell' not in full and 'headless-shell' not in full:
            return full
        return optional_tools._chrome_he_thong()

    def nick_list(self):
        return [{**p, 'nhom': 'Chrome MinMin', 'trinh_duyet': 'chromium', 'co_proxy': False} for p in self.profiles()]

    def busy(self, pid):
        with ds._db() as db:
            return db.execute("SELECT id FROM viec WHERE nick_id=? AND trang_thai='dang_chay'", (pid,)).fetchone()

    def register_machine(self):
        data = self.read()
        if not data.get('machine') or not ds.may_theo_token(secrets_store.decrypt(data.get('token', ''))):
            paired = ds.ghep(ds.tao_ma_ghep(), 'Chrome trên máy MinMin', 'chromium', (ROOT / 'VERSION').read_text().strip())
            data.update(machine=paired['may_id'], token=secrets_store.encrypt_required(paired['token']))
            self.write(data)
        return self.read()

    def sync_profiles(self):
        data = self.read()
        if data.get('machine'):
            ds.nhip(data['machine'], self.nick_list())

    async def enable(self, enabled=True):
        async with self.lock:
            data = self.register_machine() if enabled else self.read()
            data['enabled'] = bool(enabled)
            self.write(data)
        if enabled:
            await self.ensure_worker()
        elif self.worker and self.worker.returncode is None:
            if any(self.busy(p['id']) for p in self.profiles()):
                data['enabled'] = True
                self.write(data)
                raise ValueError('Còn tác vụ đang chạy; dừng tác vụ trước khi tắt')
            self.worker.terminate()
            await self.worker.wait()
        return self.status()

    async def ensure_worker(self):
        async with self.worker_lock:
            await self._ensure_worker()

    async def _ensure_worker(self):
        if not self.read().get('enabled') or not self.executable():
            return
        if self.worker and self.worker.returncode is None:
            return
        data = self.register_machine()
        if self.worker_log:
            self.worker_log.close()
        self.worker_log = open(self.root / 'worker.log', 'ab', buffering=0)
        env = dict(os.environ)
        env.update(MINMIN_NATIVE_TOKEN=secrets_store.decrypt(data['token']),
                   MINMIN_NATIVE_URL='http://127.0.0.1:' + str(os.getenv('JAVIS_PORT', '7777')),
                   MINMIN_NATIVE_MACHINE=data['machine'], PYTHONIOENCODING='utf-8')
        self.worker = await asyncio.create_subprocess_exec(
            sys.executable, str(ROOT / 'apps/doi-social/worker/minmin_worker.py'), 'chay',
            env=env, cwd=str(self.root), stdout=self.worker_log, stderr=self.worker_log)

    async def watch(self):
        while True:
            try:
                await self.ensure_worker()
            except Exception as exc:
                print('[social chrome worker]', type(exc).__name__, file=sys.stderr)
            await asyncio.sleep(10)

    def status(self):
        data = self.read()
        return {'enabled': bool(data.get('enabled')), 'installed': bool(self.executable()),
                'desktop': desktop_available(), 'running': bool(self.worker and self.worker.returncode is None),
                'installing': bool(self.install_task and not self.install_task.done()),
                'install_error': self.install_error,
                'profiles': [{**p, 'open': p['id'] in self.live, 'busy': bool(self.busy(p['id']))}
                             for p in self.profiles()]}

    async def install(self):
        if self.install_task and not self.install_task.done():
            return
        async def run():
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.install_error = ''
            env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(self.root / 'browsers'))
            try:
                proc = await asyncio.create_subprocess_exec(sys.executable, '-m', 'playwright', 'install', 'chromium',
                                                          env=env, stdout=asyncio.subprocess.DEVNULL,
                                                          stderr=asyncio.subprocess.DEVNULL)
                try:
                    code = await asyncio.wait_for(proc.wait(), 1800)
                except BaseException:
                    if proc.returncode is None:
                        proc.terminate()
                        await proc.wait()
                    raise
                if code or not self.executable():
                    raise RuntimeError('download_failed')
                await self.ensure_worker()
            except Exception:
                self.install_error = 'Không tải được Chromium. Kiểm tra kết nối và thử tải lại.'
        self.install_task = asyncio.create_task(run())

    async def create(self, name):
        name = str(name or '').strip()[:80]
        if not name:
            raise ValueError('Nhập tên profile')
        async with self.lock:
            data = self.register_machine()
            if len(data['profiles']) >= 100:
                raise ValueError('Tối đa 100 profile trên máy này')
            p = {'id': 'c' + secrets.token_hex(12), 'ten': name}
            data['profiles'].append(p)
            self.write(data)
            self.sync_profiles()
            return p

    async def close(self, pid, manual=True):
        self.profile(pid)
        if manual and self.busy(pid):
            raise ValueError('Profile đang chạy tác vụ; dừng tác vụ trước')
        item = self.live.pop(pid, None)
        if item:
            await item['context'].close()

    async def open(self, pid, hidden=False, manual=True):
        self.profile(pid)
        if manual and self.busy(pid):
            raise ValueError('Profile đang chạy tác vụ; chỉ xem màn hình hoặc dừng tác vụ trước')
        async with self.lock:
            headless = bool(hidden) or not desktop_available()
            item = self.live.get(pid)
            if item:
                try:
                    if item['context'].pages and item['headless'] == headless:
                        return item
                except Exception:
                    pass
                await self.close(pid, manual=False)
            if len(self.live) >= 3 and not manual:
                idle = next((key for key in self.live if not self.busy(key)), None)
                if idle:
                    await self.close(idle, manual=False)
            if len(self.live) >= 3:
                raise ValueError('Đã mở 3 profile; đóng một profile trước')
            exe = self.executable()
            if not exe:
                raise ValueError('Cần tải lõi Chromium trước')
            from playwright.async_api import async_playwright
            if not self.pw:
                self.pw = await async_playwright().start()
            directory = self.root / 'profiles' / pid
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            (directory / 'DevToolsActivePort').unlink(missing_ok=True)
            ctx = await self.pw.chromium.launch_persistent_context(
                str(directory), executable_path=exe, headless=headless,
                viewport={'width': 1280, 'height': 800}, accept_downloads=False,
                args=['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0'])
            # Closing the native window must release its slot too.
            item = {'context': ctx, 'headless': headless, 'tab': 0, 'directory': directory}
            self.live[pid] = item
            ctx.on('close', lambda: self.live.pop(pid, None) if self.live.get(pid) is item else None)
            if not ctx.pages:
                await ctx.new_page()
            return item

    async def endpoint(self, pid, hidden):
        item = await self.open(pid, hidden, manual=False)
        for _ in range(50):
            try:
                port = int((item['directory'] / 'DevToolsActivePort').read_text().splitlines()[0])
                if 0 < port < 65536:
                    return f'http://127.0.0.1:{port}'
            except (OSError, ValueError, IndexError):
                pass
            await asyncio.sleep(.1)
        await self.close(pid, manual=False)
        raise ValueError('Chromium không mở được cổng điều khiển')

    def page(self, pid):
        self.profile(pid)
        item = self.live.get(pid)
        if not item or not item['context'].pages:
            raise ValueError('Profile chưa mở')
        pages = item['context'].pages
        return pages[min(item['tab'], len(pages) - 1)]

    async def action(self, pid, data):
        if self.busy(pid) and data.get('action') != 'tab':
            raise ValueError('Đang chạy tác vụ; dừng tác vụ trước khi điều khiển tay')
        page = self.page(pid)
        action = data.get('action')
        if action == 'goto':
            await page.goto(web_url(data.get('url')), wait_until='domcontentloaded', timeout=30000)
        elif action == 'click':
            await page.mouse.click(max(0, min(1280, float(data['x']))), max(0, min(800, float(data['y']))))
        elif action == 'drag':
            x, y = [max(0, min(1280 if i == 0 else 800, float(v))) for i, v in enumerate(data['from'])]
            x2, y2 = [max(0, min(1280 if i == 0 else 800, float(v))) for i, v in enumerate(data['to'])]
            await page.mouse.move(x, y)
            await page.mouse.down()
            await page.mouse.move(x2, y2, steps=12)
            await page.mouse.up()
        elif action == 'text':
            await page.keyboard.insert_text(str(data.get('text') or '')[:10000])
        elif action == 'key':
            key = data.get('key')
            if key not in ('Enter', 'Tab', 'Backspace', 'Escape', 'ArrowDown', 'ArrowUp', 'Control+A'):
                raise ValueError('Phím không được hỗ trợ')
            await page.keyboard.press(key)
        elif action == 'scroll':
            await page.mouse.wheel(0, max(-1500, min(1500, int(data.get('dy', 500)))))
        elif action == 'tab':
            self.live[pid]['tab'] = max(0, min(len(self.live[pid]['context'].pages) - 1, int(data.get('tab', 0))))
        else:
            raise ValueError('Thao tác không hợp lệ')

    async def stop(self):
        if self.supervisor:
            self.supervisor.cancel()
            await asyncio.gather(self.supervisor, return_exceptions=True)
        if self.install_task and not self.install_task.done():
            self.install_task.cancel()
            await asyncio.gather(self.install_task, return_exceptions=True)
        if self.worker and self.worker.returncode is None:
            self.worker.terminate()
            try:
                await asyncio.wait_for(self.worker.wait(), 10)
            except asyncio.TimeoutError:
                self.worker.kill()
                await self.worker.wait()
        for pid in list(self.live):
            await self.close(pid, manual=False)
        if self.pw:
            await self.pw.stop()
            self.pw = None
        if self.worker_log:
            self.worker_log.close()


HOST = BrowserHost()


def register(app, blocked, worker_auth):
    from fastapi import Request
    from fastapi.responses import JSONResponse, Response

    def failure(exc):
        # Browser/HTTP exceptions may include page text and secret form values.
        text = str(exc) if isinstance(exc, ValueError) else 'Trình duyệt gặp lỗi; thử mở lại profile'
        return JSONResponse({'ok': False, 'error': text}, status_code=400)

    @app.on_event('startup')
    async def start():
        HOST.supervisor = asyncio.create_task(HOST.watch())

    @app.on_event('shutdown')
    async def stop():
        await HOST.stop()

    @app.get('/doi-social/chrome/status')
    async def status():
        if blocked():
            return JSONResponse({'ok': False, 'error': blocked()}, status_code=403)
        return {'ok': True, **HOST.status()}

    @app.post('/doi-social/chrome/{operation}')
    async def control(operation: str, request: Request):
        if blocked():
            return JSONResponse({'ok': False, 'error': blocked()}, status_code=403)
        try:
            data = await request.json()
            if operation == 'install':
                await HOST.install()
            elif operation == 'enable':
                await HOST.enable(bool(data.get('enabled', True)))
            elif operation == 'profiles':
                return {'ok': True, 'profile': await HOST.create(data.get('name'))}
            else:
                raise ValueError('Lệnh không hợp lệ')
            return {'ok': True, **HOST.status()}
        except Exception as exc:
            return failure(exc)

    @app.post('/doi-social/chrome/profile/{pid}/{operation}')
    async def profile_action(pid: str, operation: str, request: Request):
        if blocked():
            return JSONResponse({'ok': False, 'error': blocked()}, status_code=403)
        try:
            data = await request.json()
            if operation == 'open':
                await HOST.open(pid, bool(data.get('hidden')))
            elif operation == 'close':
                await HOST.close(pid)
            elif operation == 'action':
                await HOST.action(pid, data)
            else:
                raise ValueError('Lệnh không hợp lệ')
            return {'ok': True}
        except Exception as exc:
            return failure(exc)

    @app.get('/doi-social/chrome/profile/{pid}/frame')
    async def frame(pid: str):
        if blocked():
            return JSONResponse({'ok': False, 'error': blocked()}, status_code=403)
        try:
            page = HOST.page(pid)
            return Response(await page.screenshot(type='jpeg', quality=65, timeout=15000, animations='disabled'), media_type='image/jpeg',
                            headers={'Cache-Control': 'no-store'})
        except Exception as exc:
            return failure(exc)

    @app.get('/doi-social/chrome/profile/{pid}/tabs')
    async def tabs(pid: str):
        if blocked():
            return JSONResponse({'ok': False, 'error': blocked()}, status_code=403)
        try:
            HOST.page(pid)
            return {'ok': True, 'tabs': [{'index': i, 'title': await p.title()}
                                        for i, p in enumerate(HOST.live[pid]['context'].pages)]}
        except Exception as exc:
            return failure(exc)

    async def native(request):
        machine, error = await worker_auth(request)
        if error:
            return None, error
        # Remote GPM machine credentials cannot control local Chromium.
        if machine['id'] != HOST.read().get('machine') or request.client.host not in ('127.0.0.1', '::1'):
            return None, JSONResponse({'error': 'forbidden'}, status_code=403)
        return machine, None

    @app.get('/doi-social/may/chrome/profiles')
    async def worker_profiles(request: Request):
        machine, error = await native(request)
        if error:
            return error
        return {'ok': True, 'muc': HOST.nick_list()}

    @app.post('/doi-social/may/chrome/{operation}')
    async def worker_control(operation: str, request: Request):
        machine, error = await native(request)
        if error:
            return error
        try:
            data = await request.json()
            job = ds.lay_viec(int(data.get('job', 0))) or {}
            pid = str(data.get('profile') or '')
            if job.get('may_id') != machine['id'] or job.get('nick_id') != pid or job.get('trang_thai') != 'dang_chay':
                raise ValueError('Profile không thuộc tác vụ đang chạy của máy này')
            if operation == 'open':
                endpoint = await HOST.endpoint(pid, bool((job.get('tham_so') or {}).get('chay_an')))
                return {'ok': True, 'endpoint': endpoint}
            if operation == 'close':
                await HOST.close(pid, manual=False)
                return {'ok': True}
            raise ValueError('Lệnh không hợp lệ')
        except Exception as exc:
            return failure(exc)
