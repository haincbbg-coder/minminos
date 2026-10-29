"""Discover browser profile names, and attach only via user-enabled debugging.

Never read/copy/decrypt cookie or credential databases. Default Chrome profiles
require Chrome 144+'s inspect UI permission flow; Cốc Cốc must expose that flow.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from may_gpm import LoiGPM


def roots():
    if sys.platform == 'win32':
        base = Path(os.getenv('LOCALAPPDATA') or Path.home() / 'AppData/Local')
        chrome = base / 'Google/Chrome'
        coc = base / 'CocCoc/Browser'
        exe = next((p for p in [chrome / 'Application/chrome.exe',
                   Path(os.getenv('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe',
                   Path(os.getenv('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Google/Chrome/Application/chrome.exe'] if p.is_file()), None)
        return [('Chrome', chrome / 'User Data', exe), ('Cốc Cốc', coc / 'User Data', coc / 'Application/browser.exe')]
    if sys.platform == 'darwin':
        return [('Chrome', Path.home() / 'Library/Application Support/Google/Chrome', Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))]
    import shutil
    return [('Chrome', Path.home() / '.config/google-chrome', Path(shutil.which('google-chrome') or '/usr/bin/google-chrome'))]


def endpoint(folder):
    try:
        lines = (Path(folder) / 'DevToolsActivePort').read_text().splitlines()
        port, suffix = int(lines[0]), lines[1]
        if not 0 < port < 65536 or not re.fullmatch(r'/devtools/browser/[a-zA-Z0-9-]+', suffix):
            raise ValueError()
        return 'ws://127.0.0.1:' + str(port) + suffix
    except (OSError, ValueError, IndexError):
        raise LoiGPM('Mở đúng profile, vào chrome://inspect/#remote-debugging và bật kết nối. Chrome cần bản 144+; Cốc Cốc chỉ dùng được nếu hỗ trợ cơ chế này. Chấp nhận hộp thoại kết nối tại máy tính.') from None


def scan():
    result = []
    for browser, folder, exe in roots():
        if not exe or not exe.is_file():
            continue
        try:
            state = json.loads((folder / 'Local State').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        profile = state.get('profile') or {}
        for dirname, info in (profile.get('info_cache') or {}).items():
            if not re.fullmatch(r'Default|Profile [0-9]+', dirname) or not (folder / dirname).is_dir():
                continue
            key = hashlib.sha256((browser + str(folder.resolve()) + dirname).encode()).hexdigest()[:24]
            try:
                endpoint(folder)
                ready = True
            except LoiGPM:
                ready = False
            result.append({'id': key, 'name': str(info.get('name') or dirname), 'browser': browser,
                           'active': dirname == profile.get('last_used', 'Default'), 'ready': ready,
                           'folder': folder, 'directory': dirname, 'exe': exe})
    return result


def find(key):
    item = next((p for p in scan() if p['id'] == key), None)
    if not item:
        raise LoiGPM('Không còn thấy profile trên máy này; quét lại danh sách')
    return item


def connect(key):
    item = find(key)
    if not item['active']:
        raise LoiGPM('Mở profile đã chọn làm phiên Chrome hiện tại rồi thử lại. Worker không tự chọn một tài khoản khác.')
    return endpoint(item['folder'])


def open_window(key, url='chrome://inspect/#remote-debugging'):
    item = find(key)
    # Ordinary browser UI only. Never enable debugging or bypass the consent dialog.
    subprocess.Popen([str(item['exe']), '--user-data-dir=' + str(item['folder']),
                      '--profile-directory=' + item['directory'], url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def public():
    return [{k: p[k] for k in ('id', 'name', 'browser', 'active', 'ready')} for p in scan()]
