"""Viral Studio: no external calls or publication; temporary state only."""
from _paths import ROOT, SERVER
import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import viral_studio as v


class StudioTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.p=patch.object(v,'STATE_DIR',Path(self.tmp.name));self.p.start()
        self.c={'id':'channel','name':'Test','platform':'tiktok','url':'https://www.tiktok.com/@test','active':True,'task':'task','mapping':{}}
        v.put('channels',self.c)
        self.app=FastAPI();v.register(self.app);self.client=TestClient(self.app)

    def tearDown(self):
        self.p.stop();self.tmp.cleanup()

    def test_url_and_unknown_metrics(self):
        for u in ['http://tiktok.com/a','https://tiktok.com.evil.example/a','https://user@tiktok.com/a','https://127.0.0.1/a']:
            with self.assertRaises(ValueError):v.safe_url(u,'tiktok')
        p=v.normalize({'url':'https://www.tiktok.com/@test/video/1','likes':10},self.c,'test')
        self.assertIsNone(p['views']);self.assertIsNone(v.score(p))
        p.update(published=time.time()-3600,comments=3,shares=2)
        self.assertAlmostEqual(v.score(p),22,delta=.1)

    def test_import_dedup_preserves_saved_and_reports_bad_rows(self):
        raw={'url':'https://www.tiktok.com/@test/video/1','views':100}
        result=v.ingest(self.c,[raw,{'url':'https://evil.example'}],'test')
        self.assertEqual((result['imported'],len(result['errors'])),(1,1))
        p=v.rows('posts')[0];p.update(saved=True,note='note');v.put('posts',p)
        v.ingest(self.c,[dict(raw,views=200)],'test')
        p=v.rows('posts')[0];self.assertEqual(len(v.rows('posts')),1)
        self.assertTrue(p['saved']);self.assertEqual(p['note'],'note');self.assertEqual(p['views'],200)

    def test_licence_and_redaction(self):
        with patch.object(v.giay_phep,'da_mo',return_value=False):
            self.assertEqual(self.client.get(v.BASE+'/api/state').status_code,403)
            self.assertEqual(self.client.get(v.BASE+'/api/export/posts').status_code,403)
        with v.db() as c:c.execute('INSERT INTO settings VALUES(1,?)',(json.dumps({'apify_token':'private','page_token':'private','ai_key':'private','brand':'MinMin'}),))
        with patch.object(v,'gate'):
            body=self.client.get(v.BASE+'/api/state').json()
        self.assertNotIn('private',json.dumps(body));self.assertTrue(body['settings']['page_token_set'])

    def test_repeated_dataset_does_not_refresh_metrics(self):
        self.c['last_dataset']='same';v.put('channels',self.c)
        remote=AsyncMock(return_value={'data':{'defaultDatasetId':'same'}})
        with patch.object(v,'secret',return_value='test'),patch.object(v,'remote_json',remote):
            result=asyncio.run(v.sync_channel(self.c))
        self.assertTrue(result['unchanged']);self.assertEqual(remote.await_count,1)
        self.assertEqual(v.rows('posts'),[])

    def test_approved_target_and_no_duplicate_publication(self):
        v.put('drafts',{'id':'draft','platform':'facebook','status':'approved','page_id':'12345','body':'Test only'})
        s={'page_id':'12345','graph_version':'v24.0'};remote=AsyncMock(return_value={'id':'12345_678'})
        with patch.object(v,'settings',return_value=s),patch.object(v,'secret',return_value='test'),patch.object(v,'remote_json',remote):
            result=asyncio.run(v.publish('draft'))
            self.assertEqual(result['status'],'published')
            with self.assertRaises(ValueError):asyncio.run(v.publish('draft'))
        self.assertEqual(remote.await_count,1)

    def test_ambiguous_publication_is_never_retried(self):
        v.put('drafts',{'id':'draft','platform':'facebook','status':'approved','page_id':'12345','body':'Test only'})
        remote=AsyncMock(side_effect=TimeoutError())
        with patch.object(v,'settings',return_value={'page_id':'12345','graph_version':'v24.0'}),patch.object(v,'secret',return_value='test'),patch.object(v,'remote_json',remote):
            self.assertEqual(asyncio.run(v.publish('draft'))['status'],'needs_check')
            with self.assertRaises(ValueError):asyncio.run(v.publish('draft'))
        self.assertEqual(remote.await_count,1)

    def test_drafts_require_future_schedule_and_supported_platform(self):
        with patch.object(v,'gate'):
            def save(**kw):return self.client.post(v.BASE+'/api/action/draft',json={'body':'test','platform':'facebook',**kw})
            self.assertEqual(save(status='scheduled',scheduled=time.time()-10).status_code,400)
            self.assertEqual(save(status='approved',platform='douyin').status_code,400)
            self.assertEqual(save(status='scheduled',scheduled=time.time()+86400*10).status_code,200)

    def test_changed_page_revokes_publication(self):
        v.put('drafts',{'id':'draft','platform':'facebook','status':'approved','page_id':'12345','body':'Test'})
        remote=AsyncMock()
        with patch.object(v,'settings',return_value={'page_id':'67890','graph_version':'v24.0'}),patch.object(v,'secret',return_value='test'),patch.object(v,'remote_json',remote):
            with self.assertRaises(ValueError):asyncio.run(v.publish('draft'))
        remote.assert_not_called()

    def test_ai_stream_creates_draft_with_source(self):
        import engine
        p=v.normalize({'url':'https://www.tiktok.com/@test/video/1','text':'Nguồn tham khảo'},self.c,'test');v.put('posts',p)
        async def stream(key,model,messages,reasoning):
            self.assertEqual(key,'test');self.assertIn('Nguồn tham khảo',messages[1]['content'])
            yield {'type':'text','content':'Nội dung mới'}
        with patch.object(v,'gate'),patch.object(v,'settings',return_value={'ai_model':'test-model'}),patch.object(v,'secret',return_value='test'),patch.object(engine,'gemini_stream',stream):
            r=self.client.post(v.BASE+'/api/action/generate',json={'id':p['id'],'brief':'Góc nhìn riêng'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['status'],'draft');self.assertEqual(r.json()['source_url'],p['url'])
        self.assertEqual(v.rows('drafts')[0]['body'],'Nội dung mới')


if __name__=='__main__':unittest.main()
