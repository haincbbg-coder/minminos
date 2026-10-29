"""Standalone local Chrome Worker against production VPS routes. No social accounts."""
import asyncio
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch
import zipfile

os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='minmin-local-test-')
from _paths import ROOT
sys.path.insert(0, str(ROOT / 'apps/doi-social/worker'))
import chrome_local as cl
import minmin_worker as mw
mw.NHAT_KY = Path(tempfile.mkdtemp()) / "worker.log"
from chrome_control import Control
from may_gpm import GPM, LoiGPM
from playwright.sync_api import sync_playwright


def metadata():
    local = cl.ChromeLocal(Path(tempfile.mkdtemp()))
    a, b = local.create('Local Facebook'), local.create('Local YouTube')
    assert a['id'] != b['id']
    assert cl.ChromeLocal(local.root).profiles() == [a, b]
    for bad in ('../bad', 'l' + '../' * 8, 'l' + 'a' * 24):
        try:
            local.profile(bad)
            raise AssertionError('accepted invalid profile')
        except ValueError:
            pass
    lockpath = local.root / 'test.lock'
    with cl.FileLock(lockpath):
        cmd = ('import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
               'from chrome_local import FileLock; FileLock(Path(sys.argv[2])).acquire()')
        r = subprocess.run([sys.executable, '-c', cmd, str(ROOT / 'apps/doi-social/worker'), str(lockpath)],
                           capture_output=True)
        assert r.returncode != 0 and b'LoiGPM' in r.stderr, r.stderr.decode('utf-8', errors='replace')
    with cl.FileLock(lockpath):
        pass
    # Capacity and failed launch both release profile locks cleanly.
    local.executable = lambda: '/missing/chrome'
    slots = [cl.FileLock(local.root / ('slot-' + str(i) + '.lock')).acquire() for i in range(3)]
    try:
        try:
            local.mo(a['id'])
            raise AssertionError('capacity exceeded')
        except LoiGPM as exc:
            assert '3 profile' in str(exc)
    finally:
        for slot in slots:
            slot.release()
    try:
        local.mo(a['id'])
        raise AssertionError('missing executable accepted')
    except FileNotFoundError:
        pass
    with cl.FileLock(local.root / (a['id'] + '.lock')):
        pass
    assert isinstance(mw.tao_trinh_duyet({'driver': 'chrome-local'}), cl.ChromeLocal)
    assert isinstance(mw.tao_trinh_duyet({}), GPM)
    with patch.object(mw, 'CAU_HINH', local.root / 'worker.json'):
        with patch.object(mw.MayChu, 'ghep', return_value={'token': 'test', 'may_id': 'mtest', 'ten': 'Local'}) as pair:
            mw.main(['ghep-chrome', 'https://minmin.example', '123456'])
            pair.assert_called_once_with('123456', socket.gethostname() + ' (' + __import__('platform').system() + ')', 'chrome-local')
            assert mw.doc_cau_hinh()['driver'] == 'chrome-local'
    # Download/update packages must never contain local browser data, even on a local MinMin host.
    import routes.doi_social as routes
    worker = Path(tempfile.mkdtemp())
    (worker / 'chrome-data').mkdir()
    (worker / 'chrome-data' / 'cookies.txt').write_text('private')
    (worker / 'worker.json').write_text('private token')
    (worker / 'minmin_worker.py').write_text('worker')
    with patch.object(routes, 'WORKER_DIR', worker):
        with zipfile.ZipFile(io.BytesIO(routes._goi_worker_zip())) as z:
            assert z.namelist() == ['MinMinWorker/minmin_worker.py']
    print('PASS local metadata, process locks, pairing driver, download privacy')


async def integration():
    # GitHub's unprivileged Linux runner denies Chrome's namespace sandbox.
    # Windows/desktop users retain the browser's default sandbox.
    if os.getenv('CI') and sys.platform == 'linux':
        os.environ['MINMIN_CHROME_NO_SANDBOX'] = '1'
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    import httpx
    import doi_social as ds
    import doi_social_v2 as v2
    import routes.doi_social as routes
    from playwright.async_api import async_playwright
    ds.mo(Path(tempfile.mkdtemp()))
    routes.ly_do_chan = lambda: None
    routes.VONG_NEN_BAT = False
    app = FastAPI()
    routes.register(app, routes.DoiSocialDeps())
    @app.get('/fixture')
    def fixture():
        return HTMLResponse('<h1>Local worker fixture</h1><input id="draft">')
    app.mount('/apps/doi-social', StaticFiles(directory=str(ROOT / 'apps/doi-social/web'), html=True))
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    url = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(.05)
    try:
        local = cl.ChromeLocal(Path(tempfile.mkdtemp()))
        a, b = local.create('Test local Facebook'), local.create('Test local YouTube')
        async with httpx.AsyncClient(base_url=url, trust_env=False) as http:
            code = (await http.post('/doi-social/ma-ghep', json={})).json()['ma']
        remote = mw.MayChu(url)
        paired = await asyncio.to_thread(remote.ghep, code, 'Local fixture PC', 'chrome-local')
        remote.token = paired['token']
        assert ds.may_theo_token(remote.token)['driver'] == 'chrome-local'
        with patch.object(cl.ChromeLocal, 'executable', return_value='/fake/chrome'):
            await asyncio.to_thread(remote.nhip, nick=local.ds_profile(), driver_ok=True,
                                    kich_ban=['fb_dang_tuong_kho'], song_song=1)
        dot = v2.tao_dot(kich_ban='fb_dang_tuong_kho', nick=[a['id']], tham_so={'kho': 'chung'}, chay_an=True)
        job = await asyncio.to_thread(remote.lay_viec, 0)
        assert job['id'] == dot['viec'][0]['id'] and job['nick_id'] == a['id']
        # An ordinary paired PC can never use the VPS's loopback-only browser APIs.
        async with httpx.AsyncClient(base_url=url, trust_env=False) as http:
            denied = await http.get('/doi-social/may/chrome/profiles', headers={'x-minmin-may': remote.token})
            assert denied.status_code == 403
        async with httpx.AsyncClient(base_url=url, trust_env=False) as http:
            assert (await http.get('/doi-social/may/chrome-local/control')).status_code == 401
            gpm = ds.ghep(ds.tao_ma_ghep(), 'Other GPM')
            assert (await http.get('/doi-social/may/chrome-local/control', headers={'x-minmin-may': gpm['token']})).status_code == 403
            owner_url = '/doi-social/chrome-local/' + paired['may_id']
            cid = (await http.post(owner_url, json={'action': 'refresh', 'params': {}})).json()['id']
            claimed = (await http.get('/doi-social/may/chrome-local/control', headers={'x-minmin-may': remote.token})).json()['command']
            assert claimed['id'] == cid
            result = {'id': cid, 'ok': True, 'message': 'fixture refresh', 'inventory': {'profiles': [], 'existing': []}}
            other = ds.ghep(ds.tao_ma_ghep(), 'Other Chrome', 'chrome-local')
            assert (await http.post('/doi-social/may/chrome-local/result', headers={'x-minmin-may': other['token']}, json=result)).status_code == 400
            assert (await http.post('/doi-social/may/chrome-local/result', headers={'x-minmin-may': remote.token}, json=result)).status_code == 200
            assert (await http.get(owner_url)).json()['commands'][0]['state'] == 'done'
        async with async_playwright() as pw:
            exe = pw.chromium.executable_path
        if not Path(exe).is_file():
            if os.getenv('MINMIN_REQUIRE_CHROMIUM') == '1':
                raise RuntimeError('required Chromium missing')
            print('PASS real VPS pairing, heartbeat, dispatch and isolation; SKIP real browser: binary unavailable')
            return

        manager_chrome = cl.ChromeLocal(local.root)
        manager_chrome.executable = lambda: exe
        manager = Control(remote, manager_chrome)
        manager.start()

        def on_computer():
            local.executable = lambda: exe
            local.for_job({'tham_so': {'chay_an': not bool(os.getenv('DISPLAY')) and sys.platform != 'win32'}})
            try:
                endpoint = local.mo(a['id'])
            except LoiGPM:
                print((local.root / a['id'] / 'startup.log').read_text(errors='replace'))
                raise
            try:
                # A separate manager/worker cannot take over an open profile.
                duplicate = cl.ChromeLocal(local.root)
                duplicate.executable = lambda: exe
                try:
                    duplicate.mo(a['id'])
                    raise AssertionError('manual profile not locked')
                except LoiGPM:
                    pass
                with sync_playwright() as pw:
                    browser = pw.chromium.connect_over_cdp(endpoint)
                    context = browser.contexts[0]
                    context.add_cookies([{'name': 'login_fixture', 'value': 'persisted', 'url': url, 'expires': 2000000000}])
                    page = context.new_page()
                    page.goto(url + '/apps/doi-social/#/chrome', wait_until='networkidle')
                    page.locator('#chrome-location').select_option('local')
                    page.locator('#chrome-local-machines').get_by_text('Local fixture PC', exact=True).wait_for()
                    page.locator('#chrome-local-machine').select_option(paired['may_id'])
                    assert page.locator('#chrome-host').is_hidden()
                    page.locator('[data-act=local-refresh]').click()
                    page.locator('#chrome-local-inventory').get_by_text('Test local Facebook', exact=False).wait_for()
                    page.locator('#chrome-local-name').fill('Created from VPS')
                    page.locator('[data-act=local-create]').click()
                    page.locator('#chrome-local-inventory').get_by_text('Created from VPS', exact=False).wait_for()
                    created = next(p for p in local.profiles() if p['ten'] == 'Created from VPS')
                    pid = created['id']
                    page.locator('[data-name="' + pid + '"]').fill('Renamed from VPS')
                    page.locator('[data-act=local-rename][data-id="' + pid + '"]').click()
                    page.locator('#chrome-local-inventory').get_by_text('Renamed from VPS', exact=False).wait_for()
                    bulk_ui = page.locator('#chrome-local-profile-manager')
                    bulk_ui.locator('summary').click()
                    bulk_ui.locator('[data-pm=name]').fill('Bulk {n}')
                    bulk_ui.locator('[data-pm=count]').fill('2')
                    bulk_ui.locator('[data-pm=group]').fill('Fixture group')
                    bulk_ui.locator('[data-pm=storage_root]').fill(str(local.root / 'custom-storage'))
                    bulk_ui.locator('[data-pm=proxy_lines]').fill('127.0.0.1:1:fixture-user:fixture-password')
                    bulk_ui.locator('[data-act=pm-create]').click()
                    bulk_ui.locator('[data-pm=table]').get_by_text('Bulk 01', exact=True).wait_for()
                    made = [p for p in local.profiles() if p['ten'].startswith('Bulk ')]
                    assert len(made) == 2 and all(p['group'] == 'Fixture group' and Path(p['data_dir']).parent == (local.root / 'custom-storage').resolve() for p in made)
                    assert 'fixture-password' not in bulk_ui.locator('[data-pm=table]').inner_text()
                    bulk_ui.locator('summary').click()
                    page.locator('[data-act=local-open][data-id="' + pid + '"]').click()
                    page.wait_for_function('(id) => Array.from(document.querySelectorAll("#chrome-local-inventory .row")).some(el => el.querySelector("[data-id=" + id + "]") && el.textContent.includes("Đang mở"))', arg=pid)
                    assert pid in manager_chrome.live
                    page.locator('[data-act=local-close][data-id="' + pid + '"]').click()
                    page.wait_for_function('(id) => Array.from(document.querySelectorAll("#chrome-local-inventory .row")).some(el => el.querySelector("[data-id=" + id + "]") && !el.textContent.includes("Đang mở"))', arg=pid)
                    assert pid not in manager_chrome.live
                    page.locator('[data-act=pair-local]').click()
                    page.wait_for_function("document.querySelector('#chrome-pair').textContent.includes('Mã ghép:')")
                    for dark in ('light', 'dark'):
                        page.locator('html').evaluate('(el, theme) => el.setAttribute("data-theme", theme)', dark)
                        for width in (390, 1280):
                            page.set_viewport_size({'width': width, 'height': 850})
                            assert page.locator('#chrome-location').is_visible()
                            assert page.locator('[data-act=pair-local]').is_visible()
                    page.close()
            finally:
                local.dong(a['id'])
            assert not local.live
            # Attach to a separately running, consented fixture browser without copying
            # its session or closing it. Personal Chrome's consent UI stays user-owned.
            import chrome_existing
            folder = local.root / a['id']
            state_file = folder / 'Local State'
            state = json.loads(state_file.read_text())
            state.setdefault('profile', {}).update(last_used='Default', info_cache={'Default': {'name': 'Existing fixture'}})
            state_file.write_text(json.dumps(state))
            local.mo(a['id'])
            try:
                with patch.object(chrome_existing, 'roots', return_value=[('Chrome', folder, Path(exe))]):
                    source = chrome_existing.public()[0]
                    borrowed = cl.ChromeLocal(Path(tempfile.mkdtemp()))
                    borrowed.use_existing(source['id'])
                    bp = borrowed.profiles()[0]
                    ep = borrowed.mo(bp['id'])
                    try:
                        with sync_playwright() as pw:
                            browser = pw.chromium.connect_over_cdp(ep)
                            assert any(c['name'] == 'login_fixture' for c in browser.contexts[0].cookies())
                    finally:
                        borrowed.dong(bp['id'])
                    assert local.live[a['id']][0].poll() is None
            finally:
                local.dong(a['id'])
            def handler(nc):
                assert any(c['name'] == 'login_fixture' and c['value'] == 'persisted' for c in nc.ctx.cookies())
                nc.page.goto(url + '/fixture')
                nc.page.locator('#draft').fill('Automated on local computer')
                assert nc.page.locator('#draft').input_value() == 'Automated on local computer'
                return 'Local Chrome completed'
            # Production dispatcher, transport, browser launch and result upload, no social APIs.
            mw.NGHI_TRUOC_DONG = 0
            result = mw.lam_viec(remote, lambda nk: local, job, {'fb_dang_tuong_kho': handler}, toc_do=0)
            assert result['ok'], result
            assert not local.live
            local.mo(b['id'])
            try:
                with sync_playwright() as pw:
                    port = int((local.root / b['id'] / 'DevToolsActivePort').read_text().splitlines()[0])
                    browser = pw.chromium.connect_over_cdp('http://127.0.0.1:' + str(port))
                    assert not any(c['name'] == 'login_fixture' for c in browser.contexts[0].cookies())
            finally:
                local.dong(b['id'])
        try:
            await asyncio.to_thread(on_computer)
        finally:
            await asyncio.to_thread(manager.stop)
        assert ds.lay_viec(job['id'])['trang_thai'] == 'xong'
        print('PASS real local Chromium, session persistence/isolation, VPS result, UI place selection')
    finally:
        server.should_exit = True
        await serving


if __name__ == '__main__':
    metadata()
    asyncio.run(integration())
