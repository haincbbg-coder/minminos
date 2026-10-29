"""Chrome profiles on the Worker's computer. No inbound server, no GPM required.

Only a loopback DevTools endpoint is opened while a profile is in use. OS file
locks exclude manual login vs jobs, across processes, and bound open profiles.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time

from may_gpm import LoiGPM

ROOT = Path(__file__).resolve().parent / 'chrome-data'


class FileLock:
    def __init__(self, path):
        self.path, self.file = Path(path), None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = open(self.path, 'a+b')
        self.file.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.fstat(self.file.fileno()).st_size == 0:
                self.file.write(b'0')
                self.file.flush()
        except OSError:
            self.release()
            raise LoiGPM('Profile đang mở hoặc đang được sửa; đóng cửa sổ đăng nhập rồi thử lại') from None
        return self

    def release(self):
        if self.file:
            # Closing the handle releases the kernel lock, including after a crash.
            self.file.close()
            self.file = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.release()


class ChromeLocal:
    ten = 'chrome-local'

    def __init__(self, root=None, nhat_ky=None):
        self.root = Path(root or ROOT)
        self.live = {}
        self.job = {}

    def profiles(self):
        p = self.root / 'profiles.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []

    def ds_profile(self):
        if not self.executable() and not any(p.get('kind') == 'existing' for p in self.profiles()):
            raise LoiGPM('Chưa có Chrome. Chạy chrome-may-tinh.bat và chọn Tải Chromium')
        return [{'id': p['id'], 'ten': p['ten'], 'nhom': 'Chrome trên máy tính',
                 'trinh_duyet': 'chrome-existing' if p.get('kind') == 'existing' else 'chromium', 'co_proxy': False}
                for p in self.profiles()]

    def create(self, name):
        name = str(name or '').strip()[:80]
        if not name:
            raise ValueError('Nhập tên profile')
        with FileLock(self.root / 'metadata.lock'):
            profiles = self.profiles()
            if len(profiles) >= 100:
                raise ValueError('Tối đa 100 profile trên máy này')
            p = {'id': 'l' + secrets.token_hex(12), 'ten': name}
            profiles.append(p)
            tmp = self.root / 'profiles.tmp'
            tmp.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.root / 'profiles.json')
            return p

    def rename(self, pid, name):
        self.profile(pid)
        name = str(name or '').strip()[:80]
        if not name:
            raise ValueError('Nhập tên profile')
        with FileLock(self.root / 'metadata.lock'):
            profiles = self.profiles()
            for p in profiles:
                if p['id'] == pid:
                    p['ten'] = name
            self.save(profiles)

    def save(self, profiles):
        tmp = self.root / 'profiles.tmp'
        tmp.write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.root / 'profiles.json')

    def use_existing(self, source):
        import chrome_existing
        item = chrome_existing.find(source)
        with FileLock(self.root / 'metadata.lock'):
            profiles = self.profiles()
            if any(p.get('source') == source for p in profiles):
                return
            if len(profiles) >= 100:
                raise ValueError('Tối đa 100 profile trên máy này')
            profiles.append({'id': 'l' + secrets.token_hex(12), 'ten': item['name'],
                             'kind': 'existing', 'source': source, 'browser': item['browser']})
            self.save(profiles)

    def profile(self, pid):
        if not re.fullmatch(r'l[a-f0-9]{24}', str(pid)):
            raise ValueError('Profile không hợp lệ')
        p = next((p for p in self.profiles() if p['id'] == pid), None)
        if not p:
            raise ValueError('Không có profile này trên máy tính')
        return p

    def executable(self):
        for pattern in ('chromium-*/chrome-win*/chrome.exe', 'chromium-*/chrome-linux*/chrome',
                        'chromium-*/chrome-mac*/*.app/Contents/MacOS/*'):
            matches = sorted((self.root / 'browsers').glob(pattern))
            if matches:
                return str(matches[-1])
        candidates = [shutil.which('google-chrome'), shutil.which('chromium'), shutil.which('chromium-browser')]
        if sys.platform == 'win32':
            for env in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
                if os.getenv(env):
                    candidates.append(str(Path(os.environ[env]) / 'Google/Chrome/Application/chrome.exe'))
        if sys.platform == 'darwin':
            candidates.append('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        return next((p for p in candidates if p and Path(p).is_file()), '')

    def install(self):
        with FileLock(self.root / 'install.lock'):
            env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str((self.root / 'browsers').resolve()))
            subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], env=env, check=True)
            if not self.executable():
                raise LoiGPM('Tải Chromium chưa thành công')

    def for_job(self, job):
        self.job = job

    def mo(self, pid):
        profile = self.profile(pid)
        if pid in self.live:
            raise LoiGPM('Profile đã mở')
        exe = self.executable()
        if not exe and profile.get('kind') != 'existing':
            raise LoiGPM('Chưa có Chrome trên máy này')
        profile_lock = FileLock(self.root / (pid + '.lock')).acquire()
        slot = None
        try:
            for i in range(3):
                try:
                    slot = FileLock(self.root / ('slot-' + str(i) + '.lock')).acquire()
                    break
                except LoiGPM:
                    pass
            if slot is None:
                raise LoiGPM('Đang mở tối đa 3 profile; đóng một profile rồi thử lại')
            if profile.get('kind') == 'existing':
                import chrome_existing
                if (self.job.get('tham_so') or {}).get('chay_an'):
                    raise LoiGPM('Phiên Chrome có sẵn không hỗ trợ chạy ẩn; tắt Chạy ẩn')
                endpoint = chrome_existing.connect(profile['source'])
                self.live[pid] = (None, profile_lock, slot)
                return endpoint
            folder = (self.root / pid).resolve()
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            port_file = folder / 'DevToolsActivePort'
            port_file.unlink(missing_ok=True)
            params = self.job.get('tham_so') or {}
            hidden = bool(params.get('chay_an'))
            if sys.platform not in ('win32', 'darwin') and not os.getenv('DISPLAY'):
                hidden = True
            args = [exe, '--user-data-dir=' + str(folder), '--remote-debugging-port=0',
                    '--remote-debugging-address=127.0.0.1', '--no-first-run', '--no-default-browser-check', '--disable-dev-shm-usage']
            if hidden:
                args.append('--headless=new')
            if (hasattr(os, 'geteuid') and os.geteuid() == 0) or os.getenv('MINMIN_CHROME_NO_SANDBOX') == '1':
                args.append('--no-sandbox')
            args.append('about:blank')
            # Keep startup diagnostics locally; never upload browser stderr to the VPS.
            with open(folder / 'startup.log', 'wb') as startup_log:
                child = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=startup_log)
            self.live[pid] = (child, profile_lock, slot)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise LoiGPM('Chrome không mở được; đóng cửa sổ cũ và xem chrome-data/profile/startup.log trên máy')
                try:
                    port = int(port_file.read_text().splitlines()[0])
                    if 0 < port < 65536:
                        return 'http://127.0.0.1:' + str(port)
                except (OSError, ValueError, IndexError):
                    pass
                time.sleep(.1)
            raise LoiGPM('Chrome mở quá lâu; thử lại')
        except BaseException:
            if pid in self.live:
                self.dong(pid)
            else:
                profile_lock.release()
                if slot:
                    slot.release()
            raise

    def dong(self, pid):
        item = self.live.pop(pid, None)
        if not item:
            return
        child, lock, slot = item
        try:
            if child is not None and child.poll() is None:
                # Graceful Browser.close flushes cookies before any fallback termination.
                try:
                    from playwright.sync_api import sync_playwright
                    port = int((self.root / pid / 'DevToolsActivePort').read_text().splitlines()[0])
                    with sync_playwright() as pw:
                        browser = pw.chromium.connect_over_cdp('http://127.0.0.1:' + str(port), timeout=5000)
                        browser.new_browser_cdp_session().send('Browser.close')
                except Exception:
                    pass
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
        finally:
            lock.release()
            slot.release()


def menu():
    chrome = ChromeLocal()
    while True:
        print('\nChrome trên máy tính - dữ liệu đăng nhập chỉ nằm trên máy này.')
        profiles = chrome.profiles()
        for i, p in enumerate(profiles, 1):
            print(f"  {i}. {p['ten']}")
        print('T: Tạo profile | C: Tải Chromium | Số profile: Mở / Đăng nhập | Q: Thoát')
        choice = input('Chọn: ').strip().lower()
        try:
            if choice == 'q':
                return 0
            if choice == 't':
                chrome.create(input('Tên profile: '))
            elif choice == 'c':
                chrome.install()
            elif choice.isdigit() and 1 <= int(choice) <= len(profiles):
                p = profiles[int(choice) - 1]
                chrome.mo(p['id'])
                try:
                    print('Nhập facebook.com, youtube.com, tiktok.com... trực tiếp trong cửa sổ Chrome để đăng nhập.')
                    input('Đăng nhập xong, nhấn Enter ở đây để lưu và đóng trước khi chạy Automation: ')
                finally:
                    chrome.dong(p['id'])
        except (Exception, KeyboardInterrupt) as exc:
            print('Chưa thực hiện được:', str(exc))

