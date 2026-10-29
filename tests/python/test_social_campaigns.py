"""Campaign lifecycle with real SQLite/HTTP/draft queues; no social publication or paid image calls."""
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp()
os.environ['JAVIS_DOI_SOCIAL_VONG'] = '0'
from _paths import ROOT
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
import doi_social as ds
import doi_social_fanpage as fp
import social_campaigns as cp
import social_campaign_media as media

ds.mo(Path(tempfile.mkdtemp()))
fp.ghi_trang({'id': '111111', 'name': 'Fixture Page', 'tasks': ['CREATE_CONTENT']})
fp.dat_cai_dat({'dung_tu_dong': False})
calls = []
async def planner(prompt, images):
    calls.append(prompt)
    return json.dumps({'title': 'Mẹo chăm cây', 'schedule': {'kind': 'once'}, 'angles': ['Chăm cây ban công']})
async def writer(*args, **kwargs):
    return ['Chăm cây ban công bằng cách quan sát lá và giữ đất thoáng. Mỗi buổi sáng là một cơ hội vun trồng.']

def request(**kw):
    return {'prompt': 'Chia sẻ mẹo chăm cây, giọng nhẹ nhàng, một lượt ngay.', 'targets': [{'id': 'api:111111', 'style': 'story'}], **kw}

def runs(cid):
    return next(c for c in cp.list_all() if c['id'] == cid)['runs']

async def run():
    engine = cp.Engine(lambda: planner, lambda *a: None)
    cid = cp.create(request(client_key='same-click'))
    assert cp.create(request(client_key='same-click')) == cid
    with patch.object(cp.ai, 'viet_bai', writer):
        await engine.tick()
        assert len(runs(cid)) == 1 and runs(cid)[0]['state'] == 'queued'
        post = runs(cid)[0]['outputs'][0]
        assert post['status'] == 'cho_duyet', post
        assert fp.lay_bai(post['id'])['noi_dung'].startswith('Chăm cây')
        # Restart must never recreate a draft for a completed slot.
        await cp.Engine(lambda: planner, lambda *a: None).tick()
        assert len(runs(cid)) == 1
        assert len(fp.ds_bai()['muc']) == 1
    # Public idempotency returns the same post even if the text changes on retry.
    key = 'fixture-idempotency'
    one = fp.tao_bai(trang_ids=['111111'], noi_dung=['Bài kiểm tra độc lập đủ dài.'], hen='ngay', ep_duyet=True, idempotency_key=key)
    two = fp.tao_bai(trang_ids=['111111'], noi_dung=['Nội dung khác sau mất kết nối.'], hen='ngay', ep_duyet=True, idempotency_key=key)
    assert one['muc'][0]['id'] == two['muc'][0]['id']

    paused = cp.create(request(client_key='pause-during-ai', prompt='Một bài hoàn toàn mới về chăm cây khi trời mưa.'))
    async def pause_writer(*args, **kwargs):
        cp.command(paused, 'pause')
        return ['Trời mưa là lúc kiểm tra chậu cây thoát nước, đừng để rễ úng và giữ nơi trồng thông thoáng.']
    before = len(fp.ds_bai()['muc'])
    with patch.object(cp.ai, 'viet_bai', pause_writer):
        await engine.tick()
    assert cp.read(paused)['state'] == 'paused'
    assert len(fp.ds_bai()['muc']) == before, 'pause during awaited AI must prevent new queue writes'
    cp.command(paused, 'resume')
    assert cp.read(paused)['next_at'] is None
    await engine.tick()
    await engine.tick()
    assert len(runs(paused)) == 1 and runs(paused)[0]['state'] == 'queued', 'resume once must not create another paid generation slot'
    pending = cp.create(request(client_key='pause-planning'))
    cp.command(pending, 'pause'); cp.command(pending, 'resume')
    assert cp.read(pending)['state'] == 'planning'
    cp.command(pending, 'pause')

    # A disabled/deleted target is caught before expensive media generation.
    disabled = cp.create(request(client_key='disabled', image={'mode': 'mcp', 'generate_tool': 'fake'}))
    fp.sua_trang('111111', bat=False)
    with patch.object(media, 'call', side_effect=AssertionError('paid call on disabled target')):
        await engine.tick()
    assert runs(disabled)[0]['state'] == 'error'
    fp.sua_trang('111111', bat=True)
    cp.command(disabled, 'pause')

    # Async provider: generation once, restart polls original job, image validated before drafting.
    image = io.BytesIO(); Image.new('RGB', (2, 2), 'green').save(image, format='PNG')
    encoded = base64.b64encode(image.getvalue()).decode()
    image_calls = []
    async def image_tool(tool, args):
        image_calls.append((tool, args))
        if tool == 'generate':
            return {'job_id': 'job-fixture', 'status': 'processing'}
        assert args['job_id'] == 'job-fixture'
        return {'job_id': 'job-fixture', 'status': 'completed', 'content': [{'type': 'image', 'data': encoded}]}
    images = cp.create(request(client_key='async-image', prompt='Ảnh cây xanh ban công và một lời nhắc tưới nước.', image={
        'mode': 'mcp', 'generate_tool': 'generate', 'poll_tool': 'poll', 'args': {'prompt': '{{image_prompt}}'}, 'poll_args': {'job_id': '{{job_id}}'}}))
    async def different_writer(*a, **kw):
        return ['Cây xanh bên ban công giúp buổi sáng thêm bình yên. Hãy kiểm tra độ ẩm trước khi tưới nước nhé.']
    with patch.object(media, 'call', image_tool), patch.object(cp.ai, 'viet_bai', different_writer):
        await engine.tick()
        assert runs(images)[0]['state'] == 'waiting_media'
        await cp.Engine(lambda: planner, lambda *a: None).tick()
        assert runs(images)[0]['state'] == 'queued'
    assert [x[0] for x in image_calls] == ['generate', 'poll']
    imgpost = fp.lay_bai(runs(images)[0]['outputs'][0]['id'])
    assert imgpost['media'] and fp.duong_media(imgpost['media'][0]).is_file()
    retained = cp.create(request(client_key='retain-library-image', image={'mode': 'media', 'media': imgpost['media']}))
    cp.command(retained, 'pause')
    with ds._db() as db:
        db.execute("UPDATE fp_bai SET trang_thai='bo',tao_luc=? WHERE id=?", (time.time()-30*86400, imgpost['id']))
    fp.don_tep(1)
    assert fp.duong_media(imgpost['media'][0]).is_file(), 'active/paused campaign must retain its media'
    # Unknown result is stopped after restart; no silent duplicate paid generation.
    row = cp.read(images)
    with patch.object(media, 'call', side_effect=AssertionError('must not regenerate')):
        try:
            await engine.image(row, {'id': 'missing', 'slot': time.time()}, {'generation_started': True})
            raise AssertionError('uncertain image retried')
        except ValueError as exc:
            assert 'không tự tạo lại' in str(exc)

    now = time.time()
    conf = cp.read(cid)['settings']
    plan = cp.validate_plan({'schedule': {'kind': 'daily', 'times': ['20:00', '09:00'], 'weekdays': [0, 2, 4]}}, conf, now)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monday = datetime(2026, 11, 2, 8, 0, tzinfo=ZoneInfo(conf['timezone'])).timestamp()
    assert cp.schedule(plan, monday) == monday+3600
    assert cp.schedule(plan, monday+13*3600) == monday+49*3600
    assert cp.validate_plan({'schedule': {'kind': 'interval', 'minutes': 30}}, conf, now)['minutes'] == 30
    try:
        cp.validate_plan({'schedule': {'kind': 'interval', 'minutes': 1}}, conf, now)
        raise AssertionError('minute flood accepted')
    except ValueError:
        pass
    # Cap uses the day of the scheduled slot, not the earlier image generation time.
    capped = cp.create(request(client_key='cap', max_runs_day=1))
    await engine.plan(cp.read(capped))
    with ds._db() as db:
        db.execute("INSERT INTO social_campaign_run(id,campaign,slot,state,created,updated) VALUES('cap-used',?,?,'queued',?,?)", (capped, now-10, now-10, now-10))
    with patch.object(cp.ai, 'viet_bai', side_effect=AssertionError('daily limit exceeded')):
        await engine.tick()
    assert len(runs(capped)) == 1 and cp.read(capped)['next_at'] is None
    paired = ds.ghep(ds.tao_ma_ghep(), 'Fixture Chrome PC', 'chrome-local')
    ds.nhip(paired['may_id'], [{'id': 'fixture-nick', 'ten': 'Fixture Nick', 'trinh_duyet': 'chrome'}],
            kich_ban=['dang_ban_nhap'], song_song=1)
    variant_requests = []
    async def per_platform(kt, platform, number, prompt, **kwargs):
        variant_requests.append((platform, prompt))
        return ['Facebook kể câu chuyện trồng cây ban công với ánh sáng dịu và đất thoáng.' if platform == 'fb_trang' else
                'Threads hỏi vui: hôm nay bạn đã ngắm lá mới chưa? Ban công nhỏ cũng có niềm vui xanh.']
    multi = cp.create(request(client_key='multiple-platforms', targets=[{'id': 'api:111111', 'style': 'story'},
        {'id': 'nick:fixture-nick:threads', 'style': 'fun'}], auto_publish=True))
    with patch.object(cp.ai, 'viet_bai', per_platform):
        await engine.tick()
    posts = runs(multi)[0]['outputs']
    assert len(posts) == 2 and {p['kind'] for p in posts} == {'api', 'nick'}
    assert all(p['status'] != 'cho_duyet' for p in posts), posts
    assert {p[0] for p in variant_requests} == {'fb_trang', 'threads'}
    assert any('kể chuyện gần gũi' in p for _, p in variant_requests) and any('hóm hỉnh' in p for _, p in variant_requests)
    missed = cp.create(request(client_key='missed-slots'))
    await engine.plan(cp.read(missed))
    with ds._db() as db:
        db.execute('UPDATE social_campaign SET plan=?,next_at=? WHERE id=?',
                   (json.dumps({'kind': 'interval', 'minutes': 60, 'timezone': conf['timezone']}), now-2*86400, missed))
    with patch.object(cp.ai, 'viet_bai', side_effect=AssertionError('must not backfill old slots')):
        await engine.tick()
    assert not runs(missed) and cp.read(missed)['next_at'] > time.time()
    blocked_campaign = cp.create(request(client_key='app-disabled'))
    await cp.Engine(lambda: planner, lambda *a: None, allowed=lambda: False).tick()
    assert cp.read(blocked_campaign)['state'] == 'planning'
    cp.command(blocked_campaign, 'pause')

    # MIME/HTML is rejected rather than handed to the publisher.
    try:
        media.save_image(b'<html>not an image</html>')
        raise AssertionError('HTML accepted')
    except ValueError:
        pass
    assert media.inspect({'job_id': 'job', 'status': 'processing', 'image_url': 'https://example.com/wait.png'})['urls'] == []
    assert media.render({'p': '{{image_prompt}}', 'id': '{{job_id}}'}, {'image_prompt': 'cây xanh', 'job_id': 'abc'}) == {'p': 'cây xanh', 'id': 'abc'}
    print('PASS durable campaigns, approval, pause, idempotency, disabled targets, async MCP restart, caps, timezone and image validation')

asyncio.run(run())
app = FastAPI()
cp.register(app, lambda: 'Ứng dụng chưa bật', lambda: planner, lambda *a: None, enabled=False)
client = TestClient(app)
assert client.get('/doi-social/campaigns/catalog').status_code == 403
assert client.post('/doi-social/campaigns', json=request()).status_code == 403
print('PASS campaign access gate')
