"""MinMin installation examples must use the published image and working aliases."""
from _paths import ROOT
import json
import os
import re
import shutil
import subprocess
import unittest
import yaml

GUIDES = ('README.md', 'README.en.md', 'QUICKSTART.md', 'QUICKSTART.en.md',
          'DEPLOY.md', 'DEPLOY.en.md', 'docs/README.md', 'docs/en/README.md')
COMPOSES = ('docker-compose.minmin.yml', 'docker-compose.minmin.hostinger.yml')


class MinMinPublicGuidesTests(unittest.TestCase):
    def test_public_entry_guides_use_minmin(self):
        for path in GUIDES:
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding='utf-8')
                self.assertNotRegex(text.lower(), r'javis|blogminhquy|minh qu[ýy]')
        for filename in ('start-minmin.bat', 'start-minmin.vbs', 'stop-minmin.bat'):
            self.assertTrue((ROOT / filename).is_file(), filename)
        vbs = (ROOT / 'start-minmin.vbs').read_text(encoding='utf-8')
        self.assertIn('stop-minmin.bat', vbs)
        self.assertIn('server\\minmin.log', vbs)
        self.assertIn('.venv\\Scripts\\python.exe server\\main.py', vbs)

    def test_compose_wires_brand_inputs_to_runtime(self):
        for filename in COMPOSES:
            with self.subTest(filename=filename):
                src = (ROOT / filename).read_text(encoding='utf-8')
                cfg = yaml.safe_load(src)
                app = cfg['services']['minmin']
                self.assertEqual(app['image'], 'ghcr.io/haincbbg-coder/minminos:latest')
                env = app['environment']
                self.assertIn('MINMIN_ADMIN_USER', env['JAVIS_ADMIN_USER'])
                self.assertIn('MINMIN_ADMIN_PASSWORD:?', env['JAVIS_ADMIN_PASSWORD'])
                self.assertEqual(app['pull_policy'], 'always')
                updater = cfg['services']['watchtower']
                self.assertEqual(updater['command'], app['container_name'])
                self.assertEqual(updater['environment']['WATCHTOWER_HTTP_API_TOKEN'], env['WATCHTOWER_TOKEN'])
                self.assertNotIn('blogminhquy', src)
                for volume in app['volumes']:
                    self.assertIn(volume.split(':')[0], cfg['volumes'])

    @unittest.skipUnless(shutil.which('docker'), 'Docker Compose not installed')
    def test_real_compose_interpolation_and_required_password(self):
        if subprocess.run(['docker', 'compose', 'version'], capture_output=True).returncode:
            self.skipTest('Docker Compose unavailable')
        env = {k:v for k,v in os.environ.items() if not k.startswith('MINMIN_')}
        env.update(MINMIN_ADMIN_USER='shop-admin', MINMIN_ADMIN_PASSWORD='Test$Password!123',
                   MINMIN_NAME='minmin-test', MINMIN_HOST_PORT='7788', DOMAIN_NAME='minmin.example.com')
        for filename in COMPOSES:
            with self.subTest(filename=filename):
                cmd = ['docker', 'compose', '--env-file', os.devnull, '-f', str(ROOT / filename), 'config', '--format', 'json']
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                cfg = json.loads(result.stdout)
                app = cfg['services']['minmin']
                self.assertEqual(app['environment']['JAVIS_ADMIN_USER'], env['MINMIN_ADMIN_USER'])
                self.assertEqual(app['environment']['JAVIS_ADMIN_PASSWORD'], env['MINMIN_ADMIN_PASSWORD'])
                self.assertEqual(str(app['ports'][0]['published']), '7788')
                self.assertEqual(app['container_name'], 'minmin-test')
                missing = dict(env); missing.pop('MINMIN_ADMIN_PASSWORD')
                self.assertNotEqual(subprocess.run(cmd, env=missing, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()

