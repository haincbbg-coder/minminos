"""Separate scenarios within one owner installation; preserve legacy revisions."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import giay_phep


def connect():
    folder = Path(giay_phep.STATE_DIR) / 'financial-planning'
    folder.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(folder / 'plans.sqlite3', timeout=15)
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('CREATE TABLE IF NOT EXISTS versions (revision INTEGER PRIMARY KEY, saved_at TEXT NOT NULL, plan TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, settings TEXT NOT NULL, config_revision INTEGER NOT NULL DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS workspace_versions (workspace TEXT NOT NULL REFERENCES workspaces(id), revision INTEGER NOT NULL, saved_at TEXT NOT NULL, plan TEXT NOT NULL, PRIMARY KEY(workspace,revision))')
    settings = dict(name='Kế hoạch mặc định', company='', store='', mode='manual', connectionId='', shopId='')
    fresh = c.execute('INSERT OR IGNORE INTO workspaces VALUES (?,?,0)', ('default', json.dumps(settings))).rowcount
    if fresh:
        c.execute("INSERT INTO workspace_versions SELECT 'default', revision,saved_at,plan FROM versions")
    c.commit()
    return c


def workspace(c, key):
    r = c.execute('SELECT settings,config_revision FROM workspaces WHERE id=?', (key,)).fetchone()
    if not r:
        raise KeyError('Không có phương án này.')
    return dict(json.loads(r[0]), id=key, configRevision=r[1])


def settings(data):
    result = {}
    for key in ('name', 'company', 'store', 'connectionId', 'shopId'):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > 160:
            raise ValueError('Tên hoặc mã nguồn không hợp lệ.')
        result[key] = value.strip()
    if not result['name']:
        raise ValueError('Cần tên phương án.')
    result['mode'] = data.get('mode', 'manual')
    if result['mode'] not in ('manual', 'pos'):
        raise ValueError('Chọn nhập tay hoặc POS.')
    return result


def latest(c, key):
    workspace(c, key)
    r = c.execute('SELECT revision,saved_at,plan FROM workspace_versions WHERE workspace=? ORDER BY revision DESC LIMIT 1', (key,)).fetchone()
    return dict(revision=r[0], savedAt=r[1], plan=json.loads(r[2])) if r else dict(revision=0, plan=None)


def create(c, data, plan=None):
    s = settings(data)
    key = uuid.uuid4().hex
    if c.execute('SELECT count(*) FROM workspaces').fetchone()[0] >= 200:
        raise ValueError('Tối đa 200 phương án trong một cài đặt.')
    c.execute('INSERT INTO workspaces VALUES (?,?,0)', (key, json.dumps(s, ensure_ascii=False)))
    if plan is not None:
        c.execute('INSERT INTO workspace_versions VALUES (?,?,?,?)', (key, 1, now(), json.dumps(plan, ensure_ascii=False, allow_nan=False)))
    c.commit()
    return workspace(c, key)


def now():
    return datetime.now(timezone.utc).isoformat()
