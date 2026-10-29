"""Profile metadata validation shared by the native host and the PC Worker."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote


def proxy(value):
    if not value:
        return None
    if isinstance(value, dict):
        server = str(value.get('server') or '')
        user, password = str(value.get('username') or ''), str(value.get('password') or '')
    else:
        text = str(value).strip()
        if '://' not in text:
            bits = text.split(':', 3)
            if len(bits) == 4 and bits[1].isdigit():
                text, user, password = 'http://' + bits[0] + ':' + bits[1], bits[2], bits[3]
            else:
                text, user, password = 'http://' + text, '', ''
        else:
            user = password = ''
        u = urlsplit(text)
        user, password = unquote(u.username or user), unquote(u.password or password)
        host = '[' + u.hostname + ']' if u.hostname and ':' in u.hostname else u.hostname
        server = u.scheme + '://' + str(host) + ':' + str(u.port or '')
    u = urlsplit(server)
    if u.scheme not in ('http', 'https', 'socks5') or not u.hostname or not u.port or u.path not in ('', '/') or u.query or u.fragment:
        raise ValueError('Proxy cần dạng http://IP:PORT, socks5://IP:PORT hoặc IP:PORT:USER:PASS')
    if u.username is not None or u.password is not None:
        user, password = unquote(u.username or user), unquote(u.password or password)
        host = '[' + u.hostname + ']' if ':' in u.hostname else u.hostname
        server = u.scheme + '://' + host + ':' + str(u.port)
    if any(c in user + password for c in '\r\n\x00'):
        raise ValueError('Thông tin proxy không hợp lệ')
    return {'server': server.rstrip('/'), 'username': user, 'password': password}


def public_proxy(value):
    p = proxy(value)
    return p['server'] + (' (có xác thực)' if p.get('username') else '') if p else ''


def names(data):
    supplied = data.get('names')
    if isinstance(supplied, str):
        supplied = [x.strip() for x in supplied.splitlines() if x.strip()]
    if supplied:
        if not isinstance(supplied, list) or len(supplied) > 100:
            raise ValueError('Tối đa 100 tên mỗi lần')
        result = [str(x).strip()[:80] for x in supplied]
    else:
        count = int(data.get('count') or 1)
        start = int(data.get('start') if data.get('start') not in (None, '') else 1)
        digits = int(data.get('digits') if data.get('digits') not in (None, '') else 2)
        pattern = str(data.get('name') or '').strip()
        if not 1 <= count <= 100 or not 1 <= digits <= 6 or not 0 <= start <= 999999:
            raise ValueError('Số lượng từ 1 đến 100, số bắt đầu và số chữ số phải hợp lệ')
        if count > 1 and '{n}' not in pattern:
            pattern += ' {n}'
        result = [pattern.replace('{n}', str(start+i).zfill(digits))[:80] for i in range(count)]
    if not all(result) or len(set(result)) != len(result):
        raise ValueError('Tên profile không được trống hoặc trùng trong cùng lô')
    return result


def fields(data):
    out = {}
    for key in ('group', 'note'):
        if key in data:
            out[key] = str(data.get(key) or '').strip()[:(80 if key == 'group' else 500)]
    if 'proxy' in data:
        out['proxy'] = proxy(data['proxy'])
    return out


def storage(root, requested=''):
    base = Path(requested).expanduser() if requested else Path(root)
    if not base.is_absolute():
        raise ValueError('Nhập đường dẫn tuyệt đối trên máy chạy Chrome')
    base = base.resolve()
    forbidden = [Path('/'), Path('/etc'), Path('/usr'), Path('/bin'), Path('/proc'), Path('/sys')]
    if base in forbidden or (base.drive and str(base).rstrip('/\\') == base.drive):
        raise ValueError('Chọn thư mục riêng để lưu profile')
    if (base / 'Local State').exists() or (base / 'Cookies').exists():
        raise ValueError('Đây là thư mục trình duyệt đang có; dùng Quét profile có sẵn')
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    return str(base)


def batch(data):
    result = names(data)
    proxies = data.get('proxy_lines') or []
    if isinstance(proxies, str):
        proxies = [x.strip() for x in proxies.splitlines() if x.strip()]
    if proxies and len(proxies) not in (1, len(result)):
        raise ValueError('Nhập một proxy dùng chung hoặc đúng một proxy cho mỗi profile')
    common = fields(data)
    return [(name, {**common, **({'proxy': proxy(proxies[0 if len(proxies) == 1 else i])} if proxies else {})})
            for i, name in enumerate(result)]
