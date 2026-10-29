"""Remote profile commands, isolation, and existing-profile consent requirements."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='control-test-')
from _paths import ROOT
sys.path.insert(0, str(ROOT / 'apps/doi-social/worker'))
import doi_social as ds
import social_local_control as control
import chrome_existing as existing
from chrome_local import ChromeLocal
from chrome_control import Control
from may_gpm import LoiGPM


def check_error(fn):
    try:
        fn()
    except (ValueError, LoiGPM):
        return
    raise AssertionError('expected rejection')


def run():
    ds.mo(Path(tempfile.mkdtemp()))
    a = ds.ghep(ds.tao_ma_ghep(), 'PC A', 'chrome-local')
    b = ds.ghep(ds.tao_ma_ghep(), 'PC B', 'chrome-local')
    gpm = ds.ghep(ds.tao_ma_ghep(), 'GPM', 'gpm')
    mid, other = a['may_id'], b['may_id']
    check_error(lambda: control.enqueue(gpm['may_id'], 'create', {'name': 'bad'}))
    check_error(lambda: control.enqueue(mid, 'shell', {'name': 'bad'}))
    for url in ('file:///tmp/private', 'https://evil.example', 'https://chromewebstore.google.com@evil.example', 'https://chromewebstore.google.com:8443/'):
        check_error(lambda: control.enqueue(mid, 'extensions', {'url': url}))
    cid = control.enqueue(mid, 'create', {'name': 'My profile', 'exe': '/secret/path'})
    assert control.state(mid)['commands'][0]['state'] == 'pending'
    assert control.claim(other) is None
    command = control.claim(mid)
    assert command['id'] == cid and 'exe' not in command['params']
    assert control.claim(mid) is None
    inv = {'profiles': [{'id': 'test', 'name': 'Safe', 'token': 'SECRET', 'folder': '/private', 'endpoint': 'ws://localhost:1'}], 'existing': []}
    check_error(lambda: control.finish(other, cid, True, 'wrong machine', inv))
    control.finish(mid, cid, True, 'done', inv)
    assert 'SECRET' not in json.dumps(control.state(mid))
    assert '/private' not in json.dumps(control.state(mid))
    assert control.state(mid)['commands'][0]['state'] == 'done'
    check_error(lambda: control.finish(mid, cid, True, 'replayed', inv))
    cid = control.enqueue(mid, 'refresh', {})
    with ds._db() as c:
        c.execute('UPDATE chrome_control SET created=0 WHERE id=?', (cid,))
    assert control.claim(mid) is None
    assert control.state(mid)['commands'][0]['state'] == 'error'

    folder = Path(tempfile.mkdtemp())
    (folder / 'Default').mkdir()
    (folder / 'Profile 1').mkdir()
    (folder / 'Local State').write_text(json.dumps({'profile': {'last_used': 'Default', 'info_cache': {'Default': {'name': 'Existing Facebook'}, 'Profile 1': {'name': 'Existing YouTube'}}}}))
    exe = folder / 'chrome.exe'
    exe.write_text('fixture only')
    (folder / 'Default' / 'Cookies').write_text('PRIVATE-NOT-TOUCH')
    local = ChromeLocal(Path(tempfile.mkdtemp()))
    manager = Control(None, local)
    with patch.object(existing, 'roots', return_value=[('Chrome', folder, exe)]):
        found = existing.public()
        assert len(found) == 2 and found[0]['active'] and not found[1]['active']
        assert 'PRIVATE' not in json.dumps(found) and str(folder) not in json.dumps(found)
        check_error(lambda: existing.connect(found[0]['id']))  # user has not enabled debugging
        manager.execute({'action': 'use-existing', 'params': {'source': found[0]['id']}})
        manager.execute({'action': 'use-existing', 'params': {'source': found[0]['id']}})
        assert len(local.profiles()) == 1
        p = local.profiles()[0]
        assert local.ds_profile()[0]['trinh_duyet'] == 'chrome-existing'
        assert not (local.root / p['id'] / 'Cookies').exists()
        check_error(lambda: local.mo(p['id']))
        # Fixture of a browser explicitly made debuggable by its user; no cookie access needed.
        (folder / 'DevToolsActivePort').write_text('43210\n/devtools/browser/consented-fixture\n')
        assert local.mo(p['id']) == 'ws://127.0.0.1:43210/devtools/browser/consented-fixture'
        with patch('subprocess.Popen') as spawn:
            local.dong(p['id'])
            spawn.assert_not_called()  # never terminate/relaunch a personal browser
        local.for_job({'tham_so': {'chay_an': True}})
        check_error(lambda: local.mo(p['id']))
        local.for_job({})
        check_error(lambda: existing.connect(found[1]['id']))  # wrong active profile
        with patch('subprocess.Popen') as spawn:
            manager.execute({'action': 'open', 'params': {'profile': p['id']}})
            args = spawn.call_args.args[0]
            assert '--profile-directory=Default' in args
            assert not any('--remote-debugging' in arg for arg in args)
        manager.execute({'action': 'rename', 'params': {'profile': p['id'], 'name': 'My Facebook'}})
        assert local.profiles()[0]['ten'] == 'My Facebook'
        assert 'source' not in json.dumps(manager.snapshot())
        assert 'PRIVATE-NOT-TOUCH' == (folder / 'Default' / 'Cookies').read_text()
        check_error(lambda: manager.execute({'action': 'extensions', 'params': {'profile': p['id'], 'url': 'https://evil.example'}}))
        with patch('subprocess.Popen') as spawn:
            manager.execute({'action': 'extensions', 'params': {'profile': p['id']}})
            assert spawn.call_args.args[0][-1] == 'https://chromewebstore.google.com/'
    print('PASS durable commands, machine ownership, allowlist, expiry, privacy, existing sessions without cookie copying')


if __name__ == '__main__':
    run()
