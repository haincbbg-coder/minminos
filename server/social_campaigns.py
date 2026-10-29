"""Durable prompt-to-content campaigns; generation and publishing are separate states.

An explicit auto_publish setting authorizes only selected catalog targets. Images
are ingested before posts enter existing approval/publishing queues. Paid MCP
generation is never silently retried after an uncertain response or a restart.
"""
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import secrets
import time
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.responses import JSONResponse
import doi_social as ds
import doi_social_ai as ai
import doi_social_v2 as v2
import doi_social_fanpage as fp
import social_campaign_media as media

STYLES = {'auto': 'phù hợp nền tảng', 'story': 'kể chuyện gần gũi', 'sales': 'bán hàng rõ lợi ích',
          'professional': 'chuyên nghiệp', 'fun': 'hóm hỉnh', 'poetic': 'giàu cảm xúc', 'education': 'chia sẻ kiến thức'}
PLATFORMS = {'fb_tuong': 'Facebook cá nhân', 'threads': 'Threads', 'instagram': 'Instagram',
             'tiktok': 'TikTok', 'youtube': 'YouTube', 'x': 'X', 'reddit': 'Reddit'}


def init():
    with ds._db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS social_campaign(
          id TEXT PRIMARY KEY, client_key TEXT UNIQUE, title TEXT, prompt TEXT, settings TEXT,
          plan TEXT DEFAULT '{}', state TEXT, next_at REAL, errors INTEGER DEFAULT 0,
          message TEXT DEFAULT '', created REAL, updated REAL);
          CREATE TABLE IF NOT EXISTS social_campaign_run(
          id TEXT PRIMARY KEY, campaign TEXT, slot REAL, state TEXT, data TEXT DEFAULT '{}',
          message TEXT DEFAULT '', created REAL, updated REAL, UNIQUE(campaign,slot));
          CREATE UNIQUE INDEX IF NOT EXISTS campaign_draft_once ON ban_nhap(viec_tao)
          WHERE substr(viec_tao,1,4)='cmp:';''')


def catalog():
    result = []
    for page in fp.ds_trang().get('muc', []):
        if page.get('bat'):
            result.append({'id': 'api:' + page['id'], 'name': 'Facebook · ' + page['ten'],
                           'kind': 'api', 'platform': 'fb_trang', 'page': page['id']})
    for nick in v2.ds_nick():
        if nick.get('trinh_duyet') == 'firefox':
            continue
        for platform, label in PLATFORMS.items():
            result.append({'id': 'nick:' + nick['id'] + ':' + platform, 'name': label + ' · ' + nick['ten'],
                           'kind': 'nick', 'platform': platform, 'nick': nick['id'], 'nick_name': nick['ten']})
        for page in nick.get('dich_den') or []:
            if page.get('nen_tang') == 'facebook' and page.get('loai') != 'ca_nhan':
                result.append({'id': 'nick:' + nick['id'] + ':page:' + str(page.get('ma') or page.get('link')),
                               'name': 'Facebook Trang · ' + page['ten'] + ' · ' + nick['ten'], 'kind': 'nick',
                               'platform': 'fb_trang', 'nick': nick['id'], 'nick_name': nick['ten'], 'destination': page.get('link', '')})
    return result[:1000]


def text_key(text):
    return hashlib.sha256(re.sub(r'\W+', '', str(text).casefold()).encode()).hexdigest()


def settings(data):
    prompt = str(data.get('prompt') or '').strip()
    if not 5 <= len(prompt) <= 10000:
        raise ValueError('Nhập ý tưởng/yêu cầu từ 5 đến 10.000 ký tự')
    available = {t['id']: t for t in catalog()}
    chosen = data.get('targets') or []
    if not isinstance(chosen, list) or len(chosen) > 12:
        raise ValueError('Chọn tối đa 12 đích đăng')
    targets = []
    for raw in chosen:
        key = raw.get('id') if isinstance(raw, dict) else raw
        if not isinstance(key, str) or key not in available:
            raise ValueError('Đích đăng đã thay đổi; tải lại danh sách')
        style = str(raw.get('style') or 'auto') if isinstance(raw, dict) else 'auto'
        if style not in STYLES:
            raise ValueError('Phong cách không hợp lệ')
        if not any(t['id'] == key for t in targets):
            targets.append({**available[key], 'style': style})
    if not targets:
        raise ValueError('Chọn ít nhất một đích đăng để tránh đăng nhầm tài khoản')
    zone = str(data.get('timezone') or 'Asia/Ho_Chi_Minh')
    try:
        ZoneInfo(zone)
    except Exception:
        raise ValueError('Múi giờ không hợp lệ') from None
    image = data.get('image') or {'mode': 'none'}
    if not isinstance(image, dict) or image.get('mode') not in ('none', 'media', 'mcp', 'folder'):
        raise ValueError('Chọn nguồn ảnh: không kèm, kho/tải lên, thư mục hoặc MCP')
    image = dict(image)
    if image['mode'] == 'media':
        ids = image.get('media') or []
        if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or any(not fp.duong_media(str(i)) for i in ids):
            raise ValueError('Chọn từ 1 đến 10 tệp đã có trong kho media')
        image['media'] = [str(i) for i in ids]
    if image['mode'] == 'folder':
        folder = Path(str(image.get('folder') or '')).expanduser()
        if not folder.is_absolute() or not folder.is_dir():
            raise ValueError('Chọn đường dẫn thư mục ảnh có thật trên máy cài MinMin')
        # No recursive traversal or credential/document reading.
        image['folder'] = str(folder.resolve())
        if not any(p.is_file() and p.suffix.lower() in fp.DUOI_ANH for p in folder.iterdir()):
            raise ValueError('Thư mục chưa có ảnh JPEG/PNG/WebP')
    if image['mode'] == 'mcp':
        if not image.get('generate_tool'):
            raise ValueError('Chọn MCP tạo ảnh; kết nối mới ở trang Kết nối')
        for key in ('args', 'poll_args'):
            val = image.get(key) or ({'prompt': '{{image_prompt}}'} if key == 'args' else {'job_id': '{{job_id}}'})
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except ValueError:
                    raise ValueError('Mẫu tham số MCP cần là JSON hợp lệ') from None
            if not isinstance(val, dict):
                raise ValueError('Mẫu tham số MCP cần là JSON object')
            image[key] = val
    # Validate platform format before any paid generation.
    types = [fp.loai_media(i) for i in image.get('media') or []]
    for target in targets:
        if target['platform'] == 'youtube' and types != ['video']:
            raise ValueError('YouTube cần một video có sẵn; tạo ảnh không thay thế video YouTube')
        if target['platform'] in ('instagram', 'tiktok') and image['mode'] == 'none':
            raise ValueError('Instagram/TikTok cần ảnh hoặc video; chọn nguồn media')
    cap = int(data.get('max_runs_day') or 5)
    if not 1 <= cap <= 24:
        raise ValueError('Giới hạn lượt mỗi ngày từ 1 đến 24')
    return prompt, {'targets': targets, 'timezone': zone, 'image': image, 'max_runs_day': cap,
                    'max_images_day': max(1, min(24, int(data.get('max_images_day') or 5))),
                    'auto_publish': data.get('auto_publish') is True, 'product': str(data.get('product') or ''),
                    'schedule': data.get('schedule') or 'prompt'}


def schedule(plan, after):
    tz = ZoneInfo(plan['timezone'])
    now = datetime.fromtimestamp(after, tz)
    if plan['kind'] == 'once':
        value = float(plan.get('at') or after)
        return value if value >= after-1 else None
    if plan['kind'] == 'interval':
        return after + int(plan['minutes']) * 60
    for offset in range(8):
        day = now.date() + timedelta(days=offset)
        if day.weekday() not in plan['weekdays']:
            continue
        for value in plan['times']:
            hour, minute = map(int, value.split(':'))
            slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).timestamp()
            if slot >= after:
                return slot
    return None


def validate_plan(raw, config, now):
    if not isinstance(raw, dict):
        raise ValueError('AI chưa hiểu lịch; ghi rõ giờ, số lần hoặc khoảng cách trong prompt')
    timing = raw.get('schedule') or {}
    kind = timing.get('kind') or 'once'
    if kind not in ('daily', 'interval', 'once'):
        raise ValueError('Lịch cần là một lần, theo giờ trong ngày hoặc cách N phút')
    plan = {'kind': kind, 'timezone': config['timezone']}
    if kind == 'daily':
        times = sorted(set(str(t) for t in timing.get('times') or []))
        if not times or len(times) > config['max_runs_day'] or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in times):
            raise ValueError('Giờ đăng cần dạng HH:MM và không vượt giới hạn lượt/ngày')
        days = timing.get('weekdays') if timing.get('weekdays') is not None else list(range(7))
        if not isinstance(days, list) or not days or any(type(d) is not int or not 0 <= d <= 6 for d in days):
            raise ValueError('Thứ trong tuần không hợp lệ')
        plan.update(times=times, weekdays=sorted(set(days)))
    elif kind == 'interval':
        minutes = int(timing.get('minutes') or 0)
        if not 30 <= minutes <= 43200:
            raise ValueError('Khoảng cách từ 30 phút đến 30 ngày; số lượt vẫn bị chặn theo giới hạn ngày')
        plan['minutes'] = minutes
    else:
        at = timing.get('at')
        if isinstance(at, str) and at:
            value = datetime.fromisoformat(at)
            if not value.tzinfo:
                value = value.replace(tzinfo=ZoneInfo(config['timezone']))
            at = value.timestamp()
        plan['at'] = float(at or now)
        if not now-60 <= plan['at'] <= now+60*86400:
            raise ValueError('Giờ đăng đã qua hoặc xa hơn 60 ngày')
    plan['title'] = str(raw.get('title') or 'Chiến dịch AI')[:120]
    plan['image_prompt'] = str(raw.get('image_prompt') or '')[:6000]
    plan['angles'] = [str(s)[:500] for s in (raw.get('angles') or [])[:20]]
    return plan


def create(data):
    init()
    prompt, config = settings(data)
    client = str(data.get('client_key') or secrets.token_hex(16))[:80]
    now = time.time()
    with ds._khoa, ds._db() as c:
        old = c.execute('SELECT id FROM social_campaign WHERE client_key=?', (client,)).fetchone()
        if old:
            return old['id']
        cid = secrets.token_hex(12)
        c.execute('INSERT INTO social_campaign(id,client_key,title,prompt,settings,state,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                  (cid, client, 'AI đang lập kế hoạch', prompt, json.dumps(config), 'planning', now, now))
    return cid


def read(cid):
    with ds._db() as c:
        r = c.execute('SELECT * FROM social_campaign WHERE id=?', (cid,)).fetchone()
    if not r:
        raise ValueError('Không có chiến dịch này')
    row = dict(r)
    row['settings'], row['plan'] = json.loads(row['settings']), json.loads(row['plan'])
    return row


def list_all():
    init()
    with ds._db() as c:
        ids = [r[0] for r in c.execute('SELECT id FROM social_campaign ORDER BY created DESC LIMIT 100')]
        runs = [dict(r) for r in c.execute('SELECT id,campaign,slot,state,message,data FROM social_campaign_run ORDER BY created DESC LIMIT 100')]
    result = []
    for cid in ids:
        campaign = read(cid)
        campaign['runs'] = []
        for run in runs:
            if run['campaign'] != cid:
                continue
            state = json.loads(run['data'])
            outputs = []
            for output in state.get('outputs', {}).values():
                if not output.get('post'):
                    continue
                post = fp.lay_bai(output['post']) if output['kind'] == 'api' else v2.lay_ban_nhap(output['post'])
                outputs.append({'id': output['post'], 'kind': output['kind'], 'status': (post or {}).get('trang_thai', 'khong_con'), 'name': output['name']})
            campaign['runs'].append({k: v for k, v in run.items() if k != 'data'} | {'outputs': outputs})
        result.append(campaign)
    return result


def command(cid, action):
    row = read(cid)
    now = time.time()
    with ds._khoa, ds._db() as c:
        if action == 'pause':
            c.execute("UPDATE social_campaign SET state='paused',updated=? WHERE id=?", (now, cid))
        elif action == 'resume':
            if not row['plan']:
                raise ValueError('Chiến dịch chưa có kế hoạch hợp lệ')
            c.execute("UPDATE social_campaign SET state='active',errors=0,next_at=?,updated=? WHERE id=?",
                      (now if row['plan']['kind'] == 'once' else schedule(row['plan'], now), now, cid))
        elif action == 'run':
            if row['state'] != 'active':
                raise ValueError('Chỉ chạy ngay khi chiến dịch đang bật')
            c.execute('UPDATE social_campaign SET next_at=?,updated=? WHERE id=?', (now, now, cid))
        else:
            raise ValueError('Lệnh không hợp lệ')


class Engine:
    def __init__(self, get_ai, get_knowledge):
        self.get_ai, self.get_knowledge = get_ai, get_knowledge
        self.lock = asyncio.Lock()
        self.stopped = False

    def save_run(self, rid, state, data, message=''):
        with ds._db() as c:
            c.execute('UPDATE social_campaign_run SET state=?,data=?,message=?,updated=? WHERE id=?',
                      (state, json.dumps(data), message[:500], time.time(), rid))

    async def plan(self, row):
        goi = self.get_ai()
        if not goi:
            raise ValueError('Chưa có mô hình AI; chọn mô hình trong MinMin')
        config = row['settings']
        now = time.time()
        local = datetime.fromtimestamp(now, ZoneInfo(config['timezone'])).isoformat()
        prompt = ('Lập kế hoạch nội dung, KHÔNG đăng hoặc gọi công cụ. Trả JSON thuần: '
                  '{"title":"...","schedule":{"kind":"once|daily|interval","times":["09:00"],"weekdays":[0,1,2,3,4,5,6],"minutes":60,"at":"ISO8601 nếu hẹn một lần"},'
                  '"angles":["góc tiếp cận khác nhau"],"image_prompt":"mô tả ảnh phù hợp yêu cầu"}. '
                  '0=thứ hai,6=chủ nhật. Không tự bịa lịch: yêu cầu không có lịch thì once ngay. '
                  'Giờ hiện tại: ' + local + '. Múi giờ: ' + config['timezone'] + '. '
                  'Giới hạn lượt/ngày: ' + str(config['max_runs_day']) + '. Yêu cầu của chủ:\n' + row['prompt'])
        raw = ai.boc_json(await asyncio.wait_for(goi(prompt, []), 120))
        if config['schedule'] == 'once':
            if not isinstance(raw, dict):
                raw = {}
            raw['schedule'] = {'kind': 'once', 'at': now}
        plan = validate_plan(raw, config, now)
        next_at = schedule(plan, now-1)
        with ds._db() as c:
            c.execute("UPDATE social_campaign SET title=?,plan=?,state='active',next_at=?,message='',updated=? WHERE id=? AND state='planning'",
                      (plan['title'], json.dumps(plan), next_at, time.time(), row['id']))

    async def image(self, row, run, data):
        config = row['settings']['image']
        mode = config['mode']
        if 'media' in data:
            return data['media']
        if mode == 'none':
            data['media'] = []
        elif mode == 'media':
            data['media'] = config['media']
        elif mode == 'folder':
            paths = sorted(p for p in Path(config['folder']).iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in fp.DUOI_ANH)
            if not paths:
                raise ValueError('Thư mục không còn ảnh; chưa đưa bài vào hàng đợi')
            path = paths[int(run['slot']) % len(paths)]
            if path.stat().st_size > 15*1024*1024:
                raise ValueError('Ảnh lớn hơn 15 MB; chưa đọc vào bộ nhớ')
            data['media'] = [await asyncio.to_thread(media.save_image, path.read_bytes())]
        else:
            if data.get('generation_started') and not data.get('job_id'):
                raise ValueError('Chưa xác định kết quả lệnh tạo ảnh trước; kiểm tra lịch sử MCP, không tự tạo lại để tránh tính phí hai lần')
            angle = (row['plan'].get('angles') or [row['prompt']])[int(run['slot']) % max(1, len(row['plan'].get('angles') or []))]
            image_prompt = (row['plan'].get('image_prompt') or row['prompt']) + '\nGóc triển khai: ' + angle + '\nLượt nội dung: ' + datetime.fromtimestamp(run['slot'], ZoneInfo(row['settings']['timezone'])).isoformat()
            values = {'prompt': row['prompt'], 'image_prompt': image_prompt, 'job_id': data.get('job_id', '')}
            if data.get('job_id'):
                if not config.get('poll_tool'):
                    raise ValueError('Ảnh đang tạo; cần chọn công cụ kiểm tra trạng thái và mẫu tham số job_id')
                reply = await media.call(config['poll_tool'], media.render(config['poll_args'], values))
            else:
                local = datetime.fromtimestamp(time.time(), ZoneInfo(row['settings']['timezone']))
                start = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                with ds._db() as c:
                    used = c.execute("SELECT count(*) FROM social_campaign_run WHERE campaign=? AND created>=? AND data LIKE '%\"generation_started\": true%'", (row['id'], start)).fetchone()[0]
                if used >= row['settings']['max_images_day']:
                    raise ValueError('Đã chạm giới hạn tạo ảnh hôm nay; không gọi MCP thêm')
                data['generation_started'] = True
                self.save_run(run['id'], 'generating', data, 'Đang gửi yêu cầu tạo ảnh')
                reply = await media.call(config['generate_tool'], media.render(config['args'], values))
            parsed = media.inspect(reply)
            if parsed['job_id']:
                data['job_id'] = parsed['job_id']
                self.save_run(run['id'], 'waiting_media', data, 'Đang chờ ảnh từ MCP')
            ids, parsed = await media.ingest(reply)
            if not ids:
                if parsed['job_id'] or data.get('job_id'):
                    self.save_run(run['id'], 'waiting_media', data, 'Đang chờ ảnh từ MCP')
                    return None
                raise ValueError('MCP chưa trả ảnh hoặc mã tác vụ; kiểm tra kết quả trước khi tạo lại')
            data['media'] = ids
        if any(not fp.duong_media(i) for i in data['media']):
            raise ValueError('Media không còn trong kho; chưa đăng bài')
        self.save_run(run['id'], 'writing', data)
        return data['media']

    async def execute(self, row, run):
        data = json.loads(run['data'])
        config = row['settings']
        if row['state'] != 'active' or fp.cai_dat()['dung_tu_dong']:
            return
        available = {t['id'] for t in catalog()}
        if any(t['id'] not in available for t in config['targets']):
            raise ValueError('Đích đăng không còn bật hoặc đã bị xoá; chưa tạo ảnh/nội dung')
        ids = await self.image(row, run, data)
        if ids is None:
            if time.time() - run['created'] > 1800:
                raise ValueError('Ảnh chưa xong sau 30 phút; kiểm tra tác vụ MCP, không tự tạo lại')
            return
        goi = self.get_ai()
        if not goi:
            raise ValueError('AI chưa sẵn sàng')
        kt = self.get_knowledge(config['product'], row['prompt']) if config['product'] else None
        if not kt:
            kt = {'id': '', 'loai': 'chu_de', 'ten': row['title'], 'mo_ta': row['prompt'],
                  'gia': '; '.join(str(p)+'đ' for p in ai.gia_trong(row['prompt'])), 'link': '\n'.join(ai.tim_link(row['prompt']))}
        outputs = data.setdefault('outputs', {})
        for index, target in enumerate(config['targets']):
            latest = read(row['id'])
            if latest['state'] != 'active' or fp.cai_dat()['dung_tu_dong']:
                return
            key = target['id']
            out = outputs.setdefault(key, {'kind': target['kind'], 'name': target['name']})
            if out.get('post'):
                continue
            if not out.get('text'):
                with ds._db() as c:
                    recent = [json.loads(r[0]).get('outputs', {}) for r in c.execute('SELECT data FROM social_campaign_run WHERE campaign=? AND id!=? ORDER BY created DESC LIMIT 30', (row['id'], run['id']))]
                old = [v.get('text', '') for group in recent for v in group.values()] + [v.get('text', '') for v in outputs.values()]
                seen = {text_key(t) for t in old if t}
                angle = (row['plan'].get('angles') or [row['prompt']])[index % max(1, len(row['plan'].get('angles') or []))]
                request = 'Phong cách: ' + STYLES[target['style']] + '. Góc triển khai: ' + angle + '\nBài mới, không sao chép các mở đầu: ' + '; '.join(t[:100] for t in old[-10:]) + '\nYêu cầu: ' + row['prompt']
                for attempt in range(3):
                    variants = await asyncio.wait_for(ai.viet_bai(kt, target['platform'], 1, request + f'\nBiến thể {attempt+1}.', goi_ai=goi), 120)
                    unique = next((v for v in variants if text_key(v) not in seen), None)
                    if unique:
                        out['text'] = unique
                        break
                if not out.get('text'):
                    raise ValueError('AI viết trùng nội dung cũ; chưa tạo bài lặp để lấp số lượng')
                self.save_run(run['id'], 'writing', data)
            # Recheck actual media requirements, even after an async provider has finished.
            kinds = [fp.loai_media(i) for i in ids]
            if target['platform'] == 'youtube' and kinds != ['video']:
                raise ValueError('YouTube cần một video có sẵn')
            if target['platform'] in ('instagram', 'tiktok') and not ids:
                raise ValueError('Nền tảng này cần media')
            marker = 'cmp:' + run['id'] + ':' + str(index)
            if read(row['id'])['state'] != 'active' or fp.cai_dat()['dung_tu_dong']:
                return
            hen = max(run['slot'], time.time()+5)
            if target['kind'] == 'api':
                loai = 'chu' if not ids else 'video' if kinds == ['video'] else 'album' if len(ids) > 1 else 'anh'
                result = fp.tao_bai(trang_ids=[target['page']], loai=loai, noi_dung=[out['text']], media=[ids] if ids else None,
                                    hen=hen, nguon='ai', ep_duyet=True, story=False, ig=False, idempotency_key=marker)
                if not result['muc']:
                    raise ValueError('Bài đã trùng với kho; không đăng lại')
                post = result['muc'][0]
                if config['auto_publish'] and post['trang_thai'] == 'cho_duyet':
                    fp.hanh_dong_bai([post['id']], 'duyet')
            else:
                with ds._db() as c:
                    old = c.execute('SELECT id FROM ban_nhap WHERE viec_tao=?', (marker,)).fetchone()
                post = v2.lay_ban_nhap(old['id']) if old else v2.tao_ban_nhap(loai='bai_dang', noi_dang=target['platform'],
                    noi_dung=out['text'], nick_id=target['nick'], nick_ten=target['nick_name'], nhom=target.get('destination', ''),
                    ly_do='Chiến dịch AI: ' + row['title'], viec_tao=marker, hen_luc=hen,
                    tep=[(fp.ten_goc(i), fp.duong_media(i)) for i in ids])
                if len(post.get('tep') or []) != len(ids):
                    raise ValueError('Nháp thiếu media; cần kiểm tra trước khi duyệt')
                if config['auto_publish'] and post['trang_thai'] == 'cho_duyet':
                    v2.duyet_ban_nhap(post['id'], True)
            out['post'] = post['id']
            self.save_run(run['id'], 'writing', data)
        self.save_run(run['id'], 'queued', data, 'Đã tạo nội dung và đưa vào hàng đợi' if config['auto_publish'] else 'Đã tạo nháp, chờ duyệt')
        with ds._db() as c:
            c.execute('UPDATE social_campaign SET errors=0,message=?,updated=? WHERE id=?', ('Lượt gần nhất đã tạo nội dung; xem trạng thái đăng của từng bài', time.time(), row['id']))

    async def tick(self):
        if self.lock.locked():
            return
        async with self.lock:
            init()
            with ds._db() as c:
                ids = [r[0] for r in c.execute("SELECT id FROM social_campaign WHERE state IN ('planning','active') ORDER BY created LIMIT 100")]
            for cid in ids:
                if self.stopped:
                    return
                row = read(cid)
                if fp.cai_dat()['dung_tu_dong']:
                    continue
                try:
                    if row['state'] == 'planning':
                        await self.plan(row)
                        row = read(cid)
                    with ds._db() as c:
                        unfinished = c.execute("SELECT * FROM social_campaign_run WHERE campaign=? AND state IN ('new','writing','generating','waiting_media') ORDER BY created LIMIT 1", (cid,)).fetchone()
                    if unfinished:
                        await self.execute(row, dict(unfinished))
                        continue
                    if row['next_at'] is None or row['next_at'] > time.time()+900:
                        continue
                    now = time.time()
                    local = datetime.fromtimestamp(row['next_at'], ZoneInfo(row['settings']['timezone']))
                    start = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    end = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    with ds._khoa, ds._db() as c:
                        count = c.execute('SELECT count(*) FROM social_campaign_run WHERE campaign=? AND slot>=? AND slot<?', (cid, start, end)).fetchone()[0]
                        if count >= row['settings']['max_runs_day']:
                            following = schedule(row['plan'], end) if row['plan']['kind'] != 'once' else None
                            c.execute('UPDATE social_campaign SET next_at=?,message=? WHERE id=?', (following, 'Đã đủ giới hạn lượt trong ngày hẹn', cid))
                            continue
                        rid = secrets.token_hex(12)
                        slot = row['next_at']
                        inserted = c.execute("INSERT OR IGNORE INTO social_campaign_run(id,campaign,slot,state,created,updated) VALUES(?,?,?,'new',?,?)", (rid, cid, slot, now, now)).rowcount
                        following = (slot + row['plan']['minutes']*60 if row['plan']['kind'] == 'interval' else schedule(row['plan'], slot+1)) if row['plan']['kind'] != 'once' else None
                        c.execute('UPDATE social_campaign SET next_at=? WHERE id=?', (following, cid))
                    if inserted:
                        await self.execute(read(cid), {'id': rid, 'slot': slot, 'data': '{}', 'created': now})
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    message = str(exc)[:500] if isinstance(exc, ValueError) else 'Tác vụ chưa hoàn tất: ' + type(exc).__name__ + '. Kiểm tra kết nối và nhật ký.'
                    with ds._db() as c:
                        c.execute("UPDATE social_campaign_run SET state='error',message=?,updated=? WHERE campaign=? AND state IN ('new','writing','generating','waiting_media')", (message, time.time(), cid))
                        c.execute("UPDATE social_campaign SET errors=errors+1,message=?,state=CASE WHEN state='planning' OR errors>=2 THEN 'error' ELSE state END,updated=? WHERE id=?", (message, time.time(), cid))


def register(app, blocked, get_ai, get_knowledge, enabled=True):
    engine = Engine(get_ai, get_knowledge)
    task = None
    async def loop():
        await asyncio.sleep(5)
        while True:
            try:
                await engine.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(15)
    @app.on_event('startup')
    async def start():
        nonlocal task
        import os
        if enabled and os.getenv('JAVIS_DOI_SOCIAL_VONG', '1') != '0':
            task = asyncio.create_task(loop())
    @app.on_event('shutdown')
    async def stop():
        engine.stopped = True
        if task:
            task.cancel()
    def error(exc, status=400):
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=status)
    @app.get('/doi-social/campaigns/catalog')
    async def catalogs():
        if blocked():
            return error(blocked(), 403)
        return {'ok': True, 'targets': catalog(), 'styles': STYLES, 'media': fp.ds_media()}
    @app.get('/doi-social/campaigns/mcp')
    async def mcp_catalog():
        if blocked():
            return error(blocked(), 403)
        try:
            found, _ = await media.tools()
            return {'ok': True, 'tools': found}
        except Exception:
            return error('Chưa đọc được MCP; kiểm tra kết nối rồi thử lại', 502)
    @app.get('/doi-social/campaigns')
    def listing():
        if blocked():
            return error(blocked(), 403)
        return {'ok': True, 'items': list_all()}
    @app.post('/doi-social/campaigns')
    async def creating(request: Request):
        if blocked():
            return error(blocked(), 403)
        try:
            if not get_ai():
                raise ValueError('Chọn mô hình AI trong MinMin trước')
            data = await request.json()
            return {'ok': True, 'id': create(data)}
        except (ValueError, TypeError) as exc:
            return error(exc)
    @app.post('/doi-social/campaigns/{cid}/{action}')
    async def controlling(cid: str, action: str):
        if blocked():
            return error(blocked(), 403)
        try:
            command(cid, action)
            return {'ok': True}
        except ValueError as exc:
            return error(exc)
    return engine
