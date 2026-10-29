"""Managed Chromium transport, durable sessions and job ownership. No real social accounts."""
import os
import tempfile
from pathlib import Path
os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='minmin-chrome-test-')
from _paths import ROOT, SERVER
import asyncio
import json
import socket
import sys
from unittest.mock import patch
import httpx
from fastapi import FastAPI, Request
import uvicorn
import doi_social as ds
import doi_social_v2 as v2
import social_browser as sb

sys.path.insert(0, str(ROOT / 'apps/doi-social/worker'))
import minmin_worker as mw
from may_chrome import ChromeMinMin


async def run():
    ds.mo(Path(tempfile.mkdtemp()))
    host = sb.BrowserHost(Path(tempfile.mkdtemp()))
    sb.HOST = host
    a = await host.create('Facebook profile')
    b = await host.create('YouTube profile')
    assert a['id'] != b['id']
    assert sb.BrowserHost(host.root).profiles() == [a, b]
    assert 'token' not in json.dumps(host.status())
    for bad in ('../profiles', 'c'+'../'*8):
        try:
            host.profile(bad)
            raise AssertionError('path accepted')
        except ValueError:
            pass
    for url in ('file:///etc/passwd', 'javascript:alert(1)', 'https://name:pass@example.com'):
        try:
            sb.web_url(url)
            raise AssertionError('non-web url accepted')
        except ValueError:
            pass
    app = FastAPI()
    async def auth(request):
        m = ds.may_theo_token(request.headers.get('x-minmin-may', ''))
        if not m:
            from fastapi.responses import JSONResponse
            return None, JSONResponse({'error': 'unauthorized'}, status_code=401)
        return m, None
    sb.register(app, lambda: None, auth)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(.05)
    url = f'http://127.0.0.1:{port}'
    from secrets_store import decrypt
    token = decrypt(host.read()['token'])
    outsider = ds.ghep(ds.tao_ma_ghep(), 'other machine')['token']
    try:
        async with httpx.AsyncClient(base_url=url, trust_env=False) as client:
            assert (await client.get('/doi-social/may/chrome/profiles')).status_code == 401
            assert (await client.get('/doi-social/may/chrome/profiles', headers={'x-minmin-may': outsider})).status_code == 403
            headers = {'x-minmin-may': token}
            assert len((await client.get('/doi-social/may/chrome/profiles', headers=headers)).json()['muc']) == 2
            assert (await client.post('/doi-social/may/chrome/open', headers=headers,
                                      json={'profile': a['id'], 'job': 9999})).status_code == 400
            assert (await client.get('/doi-social/chrome/profile/../frame')).status_code != 200
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                exe = pw.chromium.executable_path
            if not Path(exe).is_file():
                if os.environ.get('MINMIN_REQUIRE_CHROMIUM') == '1':
                    raise RuntimeError('required Chromium missing')
                print('SKIP real browser: binary not installed; metadata and ownership tests PASS')
                return
            host.executable = lambda: exe
            item = await host.open(a['id'])
            assert item['headless'] == (not sb.desktop_available())
            page = host.page(a['id'])
            await page.context.add_cookies([{'name': 'login_fixture', 'value': 'persisted',
                                              'url': 'https://example.com', 'expires': 2000000000}])
            await page.set_content('<input id="field"><button>Login</button>')
            await page.locator('#field').focus()
            await host.action(a['id'], {'action': 'text', 'text': 'local-input'})
            assert await page.locator('#field').input_value() == 'local-input'
            assert (await client.get(f"/doi-social/chrome/profile/{a['id']}/frame")).headers['content-type'] == 'image/jpeg'
            await host.close(a['id'])
            await host.open(a['id'])
            assert any(c['name'] == 'login_fixture' and c['value'] == 'persisted'
                       for c in await host.page(a['id']).context.cookies())
            await host.open(b['id'])
            assert not any(c['name'] == 'login_fixture' for c in await host.page(b['id']).context.cookies())
            await host.close(b['id'])
            machine = host.read()['machine']
            ds.nhip(machine, host.nick_list(), driver_ok=True, kich_ban=['fb_dang_tuong_kho'], song_song=3)
            dot = v2.tao_dot(kich_ban='fb_dang_tuong_kho', nick=[a['id']], tham_so={'kho': 'chung'}, chay_an=True)
            job = ds.nhan_viec(machine)
            assert job and job['id'] == dot['viec'][0]['id']
            assert (await client.post(f"/doi-social/chrome/profile/{a['id']}/action",
                                      json={'action': 'text', 'text': 'should-not-type'})).status_code == 400
            assert (await client.post('/doi-social/may/chrome/open', headers=headers,
                                      json={'profile': b['id'], 'job': job['id']})).status_code == 400
            endpoint = (await client.post('/doi-social/may/chrome/open', headers=headers,
                                         json={'profile': a['id'], 'job': job['id']})).json()['endpoint']
            assert endpoint.startswith('http://127.0.0.1:') and host.live[a['id']]['headless'] is True
            # Worker sync Playwright uses exactly the production Native driver and CDP transport.
            class Server(mw.MayChu):
                def ket_qua(self, vid, ok, msg, steps, image, dem):
                    assert ok, msg
                    ds.ghi_ket_qua(vid, machine, ok, msg, steps, image, dem)
            def probe(nc):
                assert any(c['name'] == 'login_fixture' for c in nc.ctx.cookies())
                nc.page.set_content('<h1>Native Worker result</h1>')
                return 'native worker complete'
            srv = Server(url, token)
            with patch.object(mw, 'NGHI_TRUOC_DONG', 0), patch.object(mw, 'log', lambda *a: None):
                result = await asyncio.to_thread(mw.lam_viec, srv, lambda log: ChromeMinMin(srv), job,
                                                {'fb_dang_tuong_kho': probe})
            assert result['ok'] and ds.lay_viec(job['id'])['trang_thai'] == 'xong'
            assert a['id'] not in host.live
            print('PASS real Chromium: profile isolation, cookie persistence, manual input, screenshot, job locking, native Worker CDP, headless mode, cleanup')
    finally:
        await host.stop()
        server.should_exit = True
        await serving


if __name__ == '__main__':
    asyncio.run(run())
