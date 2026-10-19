"""Shelf image route: restricted fetch, byte cap, verified bytes, temp cleanup."""
from _paths import ROOT, SERVER
import io
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import routes.conversations as route
import image_vision


class ShelfImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        route.register(app, route.ConversationsDeps(bot_status=lambda _: {}))
        cls.client = TestClient(app)

    def test_reject_host_before_fetch(self):
        with patch.object(image_vision, 'fetch_image') as fetch:
            r = self.client.post('/conversations/file-shelf/image', data={'url':'https://evil.example/a.png'})
            self.assertEqual(r.status_code, 400)
            fetch.assert_not_called()

    def test_verified_image_and_cleanup(self):
        paths = []
        data = io.BytesIO()
        Image.new('RGB', (2, 2)).save(data, format='PNG')
        async def fetch(url, folder, stem, max_bytes):
            self.assertEqual(max_bytes, 20*1024*1024)
            p = Path(folder) / 'image.jpg'  # extension must not decide MIME
            p.write_bytes(data.getvalue()); paths.append(p)
            return p, ''
        with patch.object(image_vision, 'fetch_image', side_effect=fetch):
            r = self.client.post('/conversations/file-shelf/image', data={'url':'https://photo-stal-17.zdn.vn/a.jpg'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['content-type'], 'image/png')
        self.assertEqual(r.headers['cache-control'], 'no-store')
        self.assertEqual(r.content, data.getvalue())
        self.assertFalse(paths[0].parent.exists())

    def test_html_disguised_as_image(self):
        async def fetch(url, folder, stem, max_bytes):
            p = Path(folder) / 'image.png'; p.write_bytes(b'<html>not image</html>'); return p, ''
        with patch.object(image_vision, 'fetch_image', side_effect=fetch):
            r = self.client.post('/conversations/file-shelf/image', data={'url':'https://zdn.vn/a.png'})
        self.assertEqual(r.status_code, 422)


if __name__ == '__main__':
    unittest.main()
