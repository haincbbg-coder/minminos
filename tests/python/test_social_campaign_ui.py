"""Real browser → production campaign routes → planner → durable approval draft. No live posting."""
import asyncio
import json
import os
from pathlib import Path
import socket
import tempfile
os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp()
os.environ['JAVIS_DOI_SOCIAL_VONG'] = '0'
from _paths import ROOT
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
import uvicorn
import doi_social as ds
import doi_social_fanpage as fp
import routes.doi_social as routes
import social_campaigns as cp

async def run():
    async with async_playwright() as pw:
        if not Path(pw.chromium.executable_path).is_file():
            if os.getenv('MINMIN_REQUIRE_CHROMIUM') == '1':
                raise RuntimeError('required Chromium missing')
            print('SKIP campaign browser fixture: Chromium unavailable; mandatory in dedicated CI')
            return
        ds.mo(Path(tempfile.mkdtemp()))
        fp.ghi_trang({'id': '111111', 'name': 'Fixture garden', 'tasks': ['CREATE_CONTENT']})
        fp.dat_cai_dat({'dung_tu_dong': False})
        paired = ds.ghep(ds.tao_ma_ghep(), 'Fixture PC', 'chrome-local')
        ds.nhip(paired['may_id'], [{'id': 'nick-' + str(i), 'ten': 'Fixture Nick ' + str(i), 'trinh_duyet': 'chrome'} for i in range(50)],
                kich_ban=['dang_ban_nhap'], song_song=1)
        async def model(prompt, images):
            if 'Lập kế hoạch nội dung' in prompt:
                return json.dumps({'title': 'Ban công xanh', 'schedule': {'kind': 'once'}, 'angles': ['Tưới nước']})
            return json.dumps({'ban': ['Ban công xanh cho ngày bình yên. Quan sát lá, giữ đất thoáng và tưới nước vừa đủ mỗi sáng.']})
        routes.ly_do_chan = lambda: None
        routes.VONG_NEN_BAT = False
        app = FastAPI()
        routes.register(app, routes.DoiSocialDeps(goi_ai=model))
        @app.get('/up-bai/trang-thai')
        def fixture_sheet():
            return {'ok': True, 'cau_hinh': {'sheet_id': '', 'bat': False, 'tu_duyet': False}, 'nhat_ky': []}
        app.mount('/apps/doi-social', StaticFiles(directory=str(ROOT / 'apps/doi-social/web'), html=True))
        sock = socket.socket(); sock.bind(('127.0.0.1', 0))
        url = 'http://127.0.0.1:' + str(sock.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
        serving = asyncio.create_task(server.serve(sockets=[sock]))
        while not server.started:
            await asyncio.sleep(.05)
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        try:
            page = await browser.new_page(viewport={'width': 390, 'height': 850})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(url + '/apps/doi-social/#/chien-dich', wait_until='networkidle')
            await page.locator('#cp-chooser summary').click()
            await page.locator('[data-target="api:111111"]').wait_for()
            assert await page.locator('[data-target]').count() == 20
            await page.locator('[data-target="api:111111"]').check()
            await page.locator('[data-style="api:111111"]').select_option('story')
            await page.locator('#cp-more').click()
            assert await page.locator('[data-target]').count() == 40
            await page.locator('#cp-platform').select_option('threads')
            await page.locator('#cp-search').fill('fixture nick 49')
            assert await page.locator('[data-target]').count() == 1
            assert 'Đã chọn 1/12' in await page.locator('#cp-picked').inner_text()
            await page.locator('#cp-platform').select_option('')
            await page.locator('#cp-search').fill('')
            assert await page.locator('[data-target="api:111111"]').is_checked()
            assert await page.locator('[data-style="api:111111"]').input_value() == 'story'
            # Chosen target may be hidden by filtering at submission time.
            await page.locator('#cp-platform').select_option('threads')
            await page.locator('#cp-chooser summary').click()
            await page.locator('#cp-prompt').fill('Chia sẻ mẹo trồng cây ban công, phong cách kể chuyện, một lượt ngay.')
            await page.locator('#cp-schedule').select_option('once')
            assert not await page.locator('#cp-auto').is_checked()
            await page.locator('#cp-start').click()
            await page.locator('#cp-message').get_by_text('Đã lưu.', exact=False).wait_for()
            saved = cp.list_all()
            assert len(saved) == 1 and not saved[0]['settings']['auto_publish']
            assert saved[0]['settings']['targets'][0]['style'] == 'story'
            await cp.Engine(lambda: model, lambda *a: None).tick()
            await page.reload(wait_until='networkidle')
            await page.locator('#cp-list').get_by_text('Ban công xanh', exact=True).wait_for()
            assert fp.ds_bai()['muc'][0]['trang_thai'] == 'cho_duyet'
            await page.locator('#cp-list [data-cmd="pause"]').click()
            await page.locator('#cp-list').get_by_text('Tạm dừng · Chờ duyệt', exact=False).wait_for()
            assert cp.list_all()[0]['state'] == 'paused'
            for theme in ('light', 'dark'):
                await page.locator('html').evaluate('(el, value) => el.setAttribute("data-theme", value)', theme)
                for width in (390, 1280):
                    await page.set_viewport_size({'width': width, 'height': 850})
                    assert await page.locator('#cp-start').is_visible()
            assert not errors, errors
            await page.goto(url + '/apps/doi-social/#/may', wait_until='networkidle')
            await page.locator('#ub-sheet').fill('FIXTURE_SHEET_UNSAVED')
            await page.locator('#ub-bat').check()
            await page.locator('#ub-tu').check()
            await page.locator('#g-bai').fill('8')
            async with page.expect_response(lambda r: '/up-bai/trang-thai' in r.url, timeout=25000) as next_refresh:
                await page.locator('h1').click()  # leave edit focus before periodic refresh
            await next_refresh.value
            await page.wait_for_load_state('networkidle')
            assert await page.locator('#ub-sheet').input_value() == 'FIXTURE_SHEET_UNSAVED'
            assert await page.locator('#ub-bat').is_checked() and await page.locator('#ub-tu').is_checked()
            assert await page.locator('#g-bai').input_value() == '8'
            assert not errors, errors
            print('PASS real Chromium campaign form with 351 targets, filters/retained style, one-click draft, pause, themes and unsaved Machine form after refresh')
        finally:
            await browser.close()
            server.should_exit = True
            await serving

asyncio.run(run())
