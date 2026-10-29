"""VPS profile manager commands, executed on the paired PC over outbound HTTPS."""
import threading
from urllib.parse import urlsplit

from chrome_local import ChromeLocal, FileLock
from may_gpm import LoiGPM
import chrome_existing


class Control:
    def __init__(self, server, chrome=None):
        self.server = server
        self.chrome = chrome or ChromeLocal()
        self.stop_event = threading.Event()
        self.thread = None

    def reap(self):
        for pid, item in list(self.chrome.live.items()):
            if item[0] is not None and item[0].poll() is not None:
                self.chrome.dong(pid)

    def snapshot(self):
        self.reap()
        profiles = []
        for p in self.chrome.profiles():
            opened = p['id'] in self.chrome.live
            if not opened:
                try:
                    with FileLock(self.chrome.root / (p['id'] + '.lock')):
                        pass
                except LoiGPM:
                    opened = True
            profiles.append({'id': p['id'], 'name': p['ten'], 'browser': p.get('browser', 'Chromium'),
                             'kind': p.get('kind', 'managed'), 'open': opened, 'group': p.get('group', ''),
                             'note': p.get('note', ''), 'data_dir': p.get('data_dir') or ('' if p.get('kind') == 'existing' else str(self.chrome.root / p['id'])),
                             'proxy_label': __import__('profile_config').public_proxy(p.get('proxy'))})
        return {'profiles': profiles, 'existing': chrome_existing.public(),
                'storage_root': self.chrome.settings().get('storage_root') or str(self.chrome.root)}

    def execute(self, command):
        action, p = command['action'], command.get('params') or {}
        pid = p.get('profile', '')
        self.reap()
        if action == 'refresh':
            return 'Đã đọc danh sách trên máy tính'
        if action == 'install':
            self.chrome.install()
            return 'Đã tải Chromium trên máy tính'
        if action == 'storage':
            self.chrome.storage(p.get('storage_root'))
            return 'Đã đặt thư mục cho profile tạo mới. Profile cũ giữ nguyên vị trí.'
        if action == 'create-batch':
            result = self.chrome.create_many(p)
            return f'Đã tạo {len(result)} profile trên máy tính'
        if action == 'update-batch':
            self.chrome.update_many(p.get('profiles'), p)
            return 'Đã cập nhật các profile đã chọn'
        if action == 'update':
            self.chrome.update(pid, p)
            return 'Đã lưu nhóm, proxy và ghi chú'
        if action == 'create':
            self.chrome.create_many(p)
            return 'Đã tạo profile trên máy tính'
        if action == 'rename':
            self.chrome.rename(pid, p.get('name'))
            return 'Đã đổi tên profile trong MinMin'
        if action == 'use-existing':
            self.chrome.use_existing(p.get('source'))
            return 'Đã thêm profile có sẵn. Mở profile và bật kết nối trong Chrome; chấp nhận hộp thoại tại máy tính khi chạy việc.'
        profile = self.chrome.profile(pid)
        if action == 'close':
            if profile.get('kind') == 'existing':
                return 'MinMin không đóng trình duyệt cá nhân. Đóng cửa sổ trực tiếp trên máy nếu cần.'
            if pid not in self.chrome.live:
                # Refuse to interfere with another Worker job or manager process.
                with FileLock(self.chrome.root / (pid + '.lock')):
                    return 'Profile đã đóng'
            self.chrome.dong(pid)
            return 'Đã lưu và đóng profile'
        if action not in ('open', 'extensions'):
            raise ValueError('Lệnh profile không hợp lệ')
        url = str(p.get('url') or 'https://chromewebstore.google.com/')
        if action == 'extensions':
            u = urlsplit(url)
            if u.scheme != 'https' or u.hostname != 'chromewebstore.google.com' or u.username or u.password or u.port not in (None, 443):
                raise ValueError('Chỉ mở Chrome Web Store chính thức')
        if profile.get('kind') == 'existing':
            chrome_existing.open_window(profile['source'], url if action == 'extensions' else 'chrome://inspect/#remote-debugging')
            return 'Đã yêu cầu mở đúng profile trên máy tính. Cài extension hoặc duyệt kết nối trực tiếp tại đó.'
        if pid not in self.chrome.live:
            self.chrome.mo(pid)
        if action == 'extensions':
            from playwright.sync_api import sync_playwright
            from chrome_existing import endpoint
            with sync_playwright() as pw:
                browser = pw.chromium.connect_over_cdp(endpoint(self.chrome.profile(pid).get('data_dir') or self.chrome.root / pid))
                page = browser.contexts[0].new_page()
                page.goto(url, wait_until='domcontentloaded')
            return 'Đã mở Chrome Web Store trên máy tính; người dùng chọn extension và duyệt quyền cài đặt.'
        return 'Đã mở Chrome trên máy tính để đăng nhập. Đóng bằng nút Đóng profile trước khi chạy Automation.'

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True, name='chrome-profile-manager')
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=20)

    def run(self):
        pending = None
        try:
            while not self.stop_event.is_set():
                try:
                    self.reap()
                    if pending is None:
                        command = self.server.goi('GET', '/doi-social/may/chrome-local/control', timeout=10).get('command')
                        if command:
                            try:
                                message = self.execute(command)
                                ok = True
                            except Exception as exc:
                                ok = False
                                message = 'Không thao tác được trên máy tính; kiểm tra cửa sổ Worker.' if not isinstance(exc, (ValueError, LoiGPM)) else str(exc)
                            pending = {'id': command['id'], 'ok': ok, 'message': message, 'inventory': self.snapshot()}
                    if pending:
                        self.server.goi('POST', '/doi-social/may/chrome-local/result', pending, timeout=10)
                        pending = None
                        try:
                            self.server.nhip(nick=self.chrome.ds_profile(), driver_ok=True)
                        except Exception:
                            pass
                except Exception as exc:
                    if getattr(exc, 'code', 0) in (400, 403, 404):
                        pending = None
                self.stop_event.wait(3)
        finally:
            for pid in list(self.chrome.live):
                self.chrome.dong(pid)
