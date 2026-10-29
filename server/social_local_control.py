"""Durable, allowlisted profile commands for paired local Chrome Workers.

No executable paths, shell commands, cookies or CDP endpoints cross this API.
User endpoints retain main's login/CSRF guard; Worker endpoints bind to its token.
"""
import json
import time
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
import doi_social as ds

ACTIONS = {'install', 'refresh', 'create', 'rename', 'open', 'close', 'extensions', 'use-existing'}


def init(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS chrome_control(
      id INTEGER PRIMARY KEY AUTOINCREMENT, machine TEXT NOT NULL, action TEXT NOT NULL,
      params TEXT NOT NULL, state TEXT NOT NULL, created REAL, started REAL, message TEXT DEFAULT '');
      CREATE TABLE IF NOT EXISTS chrome_inventory(machine TEXT PRIMARY KEY, updated REAL, data TEXT);''')


def machine(c, mid):
    row = c.execute('SELECT driver FROM may WHERE id=?', (mid,)).fetchone()
    if not row or row['driver'] != 'chrome-local':
        raise ValueError('Chọn máy đã ghép chế độ Chrome trên máy tính')


def enqueue(mid, action, params):
    if action not in ACTIONS or not isinstance(params, dict):
        raise ValueError('Lệnh profile không hợp lệ')
    p = {k: str(params.get(k) or '').strip()[:200] for k in ('name', 'profile', 'source')}
    if action in ('create', 'rename') and not p['name']:
        raise ValueError('Nhập tên profile')
    if action == 'extensions':
        url = str(params.get('url') or 'https://chromewebstore.google.com/').strip()
        u = urlsplit(url)
        if u.scheme != 'https' or u.hostname != 'chromewebstore.google.com' or u.username or u.password or u.port not in (None, 443):
            raise ValueError('Chỉ nhận link Chrome Web Store chính thức')
        p['url'] = url[:2000]
    with ds._khoa, ds._db() as c:
        init(c)
        machine(c, mid)
        expire(c)
        count = c.execute("SELECT count(*) FROM chrome_control WHERE machine=? AND state IN ('pending','running')", (mid,)).fetchone()[0]
        if count >= 20:
            raise ValueError('Máy còn nhiều lệnh chưa xử lý; chờ Worker kết nối')
        cur = c.execute('INSERT INTO chrome_control(machine,action,params,state,created) VALUES(?,?,?,?,?)',
                        (mid, action, json.dumps(p), 'pending', time.time()))
        return cur.lastrowid


def expire(c):
    c.execute("UPDATE chrome_control SET state='error',message='Worker chưa hoàn tất; kiểm tra máy rồi gửi lệnh mới' WHERE (state='pending' AND created<?) OR (state='running' AND started<? AND action!='install') OR (state='running' AND action='install' AND started<?)",
              (time.time() - 600, time.time() - 300, time.time() - 1800))


def claim(mid):
    with ds._khoa, ds._db() as c:
        init(c)
        machine(c, mid)
        expire(c)
        c.execute('BEGIN IMMEDIATE')
        try:
            if c.execute("SELECT 1 FROM chrome_control WHERE machine=? AND state='running'", (mid,)).fetchone():
                c.commit()
                return None
            row = c.execute("SELECT * FROM chrome_control WHERE machine=? AND state='pending' ORDER BY id LIMIT 1", (mid,)).fetchone()
            if row:
                c.execute("UPDATE chrome_control SET state='running',started=? WHERE id=?", (time.time(), row['id']))
            c.commit()
        except BaseException:
            c.rollback()
            raise
        return {'id': row['id'], 'action': row['action'], 'params': json.loads(row['params'])} if row else None


def inventory(data):
    if not isinstance(data, dict):
        raise ValueError('Danh sách profile không hợp lệ')
    out = {}
    for key in ('profiles', 'existing'):
        out[key] = [{k: (bool(p.get(k)) if k in ('open', 'active', 'ready') else str(p.get(k) or '')[:200])
                     for k in ('id', 'name', 'browser', 'kind', 'open', 'active', 'ready')}
                    for p in (data.get(key) or [])[:100] if isinstance(p, dict)]
    return out


def finish(mid, cid, ok, message, data):
    safe = inventory(data)
    with ds._khoa, ds._db() as c:
        init(c)
        machine(c, mid)
        cur = c.execute("UPDATE chrome_control SET state=?,message=? WHERE id=? AND machine=? AND state='running'",
                        ('done' if ok else 'error', str(message or '')[:500], int(cid), mid))
        if not cur.rowcount:
            raise ValueError('Lệnh không thuộc máy hoặc đã kết thúc')
        c.execute('INSERT OR REPLACE INTO chrome_inventory VALUES(?,?,?)', (mid, time.time(), json.dumps(safe)))


def state(mid):
    with ds._khoa, ds._db() as c:
        init(c)
        machine(c, mid)
        expire(c)
        row = c.execute('SELECT * FROM chrome_inventory WHERE machine=?', (mid,)).fetchone()
        commands = [dict(r) for r in c.execute('SELECT id,action,state,message FROM chrome_control WHERE machine=? ORDER BY id DESC LIMIT 10', (mid,))]
    return {'updated': row['updated'] if row else None, **(json.loads(row['data']) if row else {'profiles': [], 'existing': []}), 'commands': commands}


def register(app, blocked, worker_auth):
    def error(exc, status=400):
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=status)

    @app.get('/doi-social/chrome-local/{mid}')
    def local_state(mid: str):
        if blocked():
            return error(blocked(), 403)
        try:
            return {'ok': True, **state(mid)}
        except ValueError as exc:
            return error(exc)

    @app.post('/doi-social/chrome-local/{mid}')
    async def local_command(mid: str, request: Request):
        if blocked():
            return error(blocked(), 403)
        try:
            d = await request.json()
            return {'ok': True, 'id': enqueue(mid, d.get('action'), d.get('params') or {})}
        except (ValueError, AttributeError) as exc:
            return error(exc)

    @app.get('/doi-social/may/chrome-local/control')
    async def worker_command(request: Request):
        m, err = await worker_auth(request)
        if err:
            return err
        try:
            return {'ok': True, 'command': claim(m['id'])}
        except ValueError as exc:
            return error(exc, 403)

    @app.post('/doi-social/may/chrome-local/result')
    async def worker_result(request: Request):
        m, err = await worker_auth(request)
        if err:
            return err
        try:
            d = await request.json()
            finish(m['id'], d.get('id'), d.get('ok') is True, d.get('message'), d.get('inventory'))
            return {'ok': True}
        except (ValueError, TypeError, AttributeError) as exc:
            return error(exc)
