"""Chăm khách trên kho hội thoại hiện có, không tạo bản sao dữ liệu khách.

Người phụ trách là nhãn điều phối trong phiên quản trị chung, không phải danh tính
đăng nhập hay hàng rào phân quyền. Nhật ký chỉ thêm qua API; chủ SQLite vẫn có thể sửa.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime

import conversations as cs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_ops(
 conversation_id INTEGER PRIMARY KEY, owner TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS conversation_templates(
 code TEXT PRIMARY KEY, text TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS conversation_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
 target TEXT NOT NULL, detail TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS conversation_audit_no_update BEFORE UPDATE ON conversation_audit
 BEGIN SELECT RAISE(ABORT, 'append only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_audit_no_delete BEFORE DELETE ON conversation_audit
 BEGIN SELECT RAISE(ABORT, 'append only'); END;
"""


def _db():
    db = cs._conn()
    # Không executescript ở đây: nó commit giao dịch đang chạy của kho hội thoại.
    for stmt in _SCHEMA.split(';\n'):
        if stmt.strip():
            db.execute(stmt)
    return db


def _audit(db, action, target, detail):
    db.execute('INSERT INTO conversation_audit(action,target,detail,created_at) VALUES(?,?,?,?)',
               (action, str(target), json.dumps(detail, ensure_ascii=False), time.time()))


def profile(cid):
    with cs._lock:
        c = cs.chi_tiet(cid)
        if not c:
            raise LookupError('Không có hội thoại này.')
        r = _db().execute('SELECT owner,revision FROM conversation_ops WHERE conversation_id=?', (cid,)).fetchone()
    return dict(c, owner=r['owner'] if r else '', revision=r['revision'] if r else 0)


def save_profile(cid, *, revision, owner, tags, note):
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValueError('Thẻ phải là danh sách tên thẻ.')
    if len(owner) > 120 or len(note) > 4000:
        raise ValueError('Tên phụ trách tối đa 120 ký tự, ghi chú tối đa 4.000 ký tự.')
    with cs._lock:
        db = _db()
        try:
            db.execute('BEGIN IMMEDIATE')
            c = profile(cid)
            if c['revision'] != revision:
                raise ValueError('Hồ sơ vừa được sửa ở cửa sổ khác. Mở lại hồ sơ rồi lưu.')
            if not c.get('customer_id') and (tags or note):
                raise ValueError('Hội thoại chưa liên kết khách. Hiện chỉ lưu được người phụ trách.')
            db.execute('INSERT INTO conversation_ops VALUES(?,?,?) ON CONFLICT(conversation_id) '
                       'DO UPDATE SET owner=excluded.owner,revision=excluded.revision',
                       (cid, owner.strip(), revision + 1))
            if c.get('customer_id'):
                db.execute('INSERT OR IGNORE INTO conversation_ops(conversation_id) '
                           'SELECT id FROM conversations WHERE customer_id=?', (c['customer_id'],))
                db.execute('UPDATE customers SET tags_json=?,note=? WHERE id=?',
                           (json.dumps(cs.chuan_hoa_tag(tags), ensure_ascii=False), note, c['customer_id']))
                # Cùng một khách có thể được mở từ hai hội thoại: làm cũ mọi bản sửa khác.
                db.execute('UPDATE conversation_ops SET revision=revision+1 WHERE conversation_id!=? '
                           'AND conversation_id IN (SELECT id FROM conversations WHERE customer_id=?)',
                           (cid, c['customer_id']))
            _audit(db, 'profile', cid, {'owner': owner.strip(), 'tags': cs.chuan_hoa_tag(tags)})
            db.commit()
        except Exception:
            db.rollback()
            raise
    return profile(cid)


def templates():
    with cs._lock:
        return [dict(r) for r in _db().execute('SELECT * FROM conversation_templates ORDER BY code')]


def save_template(code, text):
    code = code.strip().lstrip('/')
    if not re.fullmatch(r'[a-zA-Z0-9_\-]{1,40}', code):
        raise ValueError('Mã lệnh dùng 1–40 chữ, số, dấu _ hoặc -.')
    if not text.strip() or len(text) > cs.MAX_CHU:
        raise ValueError('Nội dung cần có từ 1 đến 8.000 ký tự.')
    with cs._lock:
        db = _db()
        db.execute('INSERT INTO conversation_templates VALUES(?,?,?) ON CONFLICT(code) '
                   'DO UPDATE SET text=excluded.text,updated_at=excluded.updated_at',
                   (code, text.strip(), time.time()))
        _audit(db, 'template', code, {})
        db.commit()
    return code


def audit(limit=100):
    with cs._lock:
        return [dict(r) for r in _db().execute('SELECT * FROM conversation_audit ORDER BY id DESC LIMIT ?',
                                              (max(1, min(limit, 500)),))]


def record(action, target, detail=None):
    with cs._lock:
        db = _db()
        _audit(db, action, target, detail or {})
        db.commit()


def record_safely(action, target, detail=None):
    # Sau khi gửi thành công tuyệt đối không trả lỗi làm người dùng gửi lần hai.
    try:
        record(action, target, detail)
    except Exception as e:
        import sys
        print(f'[conversation-ops] audit: {e}', file=sys.stderr)


def report(days=7, channel='zalo_personal', account_id='', sla=300):
    """SLA = từ tin khách đầu một đợt đến lần đáp đầu, không reset khi khách nhắn tiếp.

    Báo cáo các đợt bắt đầu trong cửa sổ trượt N ngày. Backlog đọc toàn bộ lịch sử còn
    lưu. Nhóm bị cắt lịch sử thì chỉ tính được trên phần còn giữ, không dựng số giả.
    """
    days = max(1, min(int(days), 90))
    sla = max(10, min(int(sla), 86400))
    now = time.time()
    since = now - days * 86400
    wh, args = [], []
    if channel:
        wh.append('a.channel=?'); args.append(channel)
    if account_id:
        wh.append('a.id=?'); args.append(account_id)
    where = ' AND '.join(wh) if wh else '1=1'
    with cs._lock:
        db = _db()
        convs = [dict(r) for r in db.execute(
            'SELECT c.id,c.title,c.chat_type,c.mode,c.last_sender_type,c.unread_count,'
            'a.display_name AS account_name,COALESCE(o.owner,\'\') AS owner '
            'FROM conversations c JOIN channel_accounts a ON a.id=c.channel_account_id '
            'LEFT JOIN conversation_ops o ON o.conversation_id=c.id WHERE ' + where, args)]
        rows = db.execute('SELECT m.conversation_id,m.sender_type,m.sender_name,m.created_at,m.text '
                          'FROM messages m JOIN conversations c ON c.id=m.conversation_id '
                          'JOIN channel_accounts a ON a.id=c.channel_account_id WHERE ' + where +
                          ' AND m.created_at>=? AND m.created_at<=? '
                          'ORDER BY m.conversation_id,m.created_at,m.id', args + [since, now]).fetchall()
        pending = db.execute(
            'SELECT c.id,MIN(m.created_at) AS since FROM conversations c '
            'JOIN channel_accounts a ON a.id=c.channel_account_id '
            'JOIN messages m ON m.conversation_id=c.id '
            'WHERE ' + where + " AND c.mode!='closed' "
            "AND m.sender_type='customer' AND NOT EXISTS (SELECT 1 FROM messages r "
            "WHERE r.conversation_id=c.id AND r.sender_type IN ('human','ai') "
            "AND (r.created_at>m.created_at OR (r.created_at=m.created_at AND r.id>m.id))) "
            'GROUP BY c.id', args).fetchall()
        customers = db.execute('SELECT COUNT(*) FROM customers k JOIN channel_accounts a '
                               'ON a.id=k.channel_account_id WHERE ' + where + ' AND k.created_at>=?',
                               args + [since]).fetchone()[0]
    try:
        import localefmt
        tz = localefmt.tz()
    except Exception:
        tz = None
    counts = {'customer': 0, 'human': 0, 'ai': 0}
    hours = [0] * 24
    starts, samples, people = {}, [], {}
    phones = set()
    for m in rows:
        kind, cid, ts = m['sender_type'], m['conversation_id'], m['created_at']
        if kind in counts:
            counts[kind] += 1
        if kind == 'customer':
            hours[datetime.fromtimestamp(ts, tz).hour] += 1
            starts.setdefault(cid, ts)
            phones.update(re.findall(r'(?<!\d)(?:0|\+84)[\d .-]{8,14}\d(?!\d)', m['text'] or ''))
        elif kind in ('human', 'ai') and cid in starts:
            delay = max(0, ts - starts.pop(cid))
            samples.append(delay)
            # Tên người gửi lấy từ dữ liệu đã lưu, không coi nhãn phân công là danh tính gửi.
            name = ('AI' if kind == 'ai' else (m['sender_name'] or 'Người trực'))
            people.setdefault(name, []).append(delay)
    by_id = {c['id']: c for c in convs}
    backlog = [dict(by_id[r['id']], waiting_seconds=round(max(0, now-r['since'])),
                    overdue=now-r['since'] > sla) for r in pending if r['id'] in by_id]
    backlog.sort(key=lambda x: -x['waiting_seconds'])
    return {'days': days, 'since': since, 'generated_at': now, 'sla_seconds': sla,
            'conversations': len(convs), 'new_customers': customers,
            'unread': sum(c['unread_count'] > 0 for c in convs), 'messages': counts,
            'response_count': len(samples), 'avg_seconds': round(sum(samples)/len(samples)) if samples else None,
            'sla_met': sum(s <= sla for s in samples), 'hourly': hours,
            'phone_mentions': len(phones), 'pending_count': len(backlog),
            'overdue_count': sum(c['overdue'] for c in backlog), 'pending': backlog[:100],
            'responders': [{'name': n, 'responses': len(v), 'avg_seconds': round(sum(v)/len(v)),
                            'max_seconds': round(max(v))} for n, v in people.items()],
            'limitations': 'Cửa sổ trượt; tính thời gian liên tục, gồm AI. Chỉ tính lịch sử còn lưu. '
                            'Tên gửi chung không phân biệt được từng nhân viên. SĐT là phát hiện mẫu, chưa xác minh lead.'}
