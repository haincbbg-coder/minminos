"""Kho tạm, không mạng: hồ sơ đồng thời, SLA theo đợt, lọc thẻ và API."""
from _paths import ROOT, SERVER  # noqa: F401
import os
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='minmin-ops-')
import conversations as cs
import conversation_ops as ops
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import conversation_ops as routes


class OpsTests(unittest.TestCase):
    def setUp(self):
        cs.close()
        from pathlib import Path
        cs.DB_PATH = Path(tempfile.mkdtemp()) / 'test.sqlite3'
        self.now = time.time()

    def event(self, seconds=0, kind='customer', channel='zalo_personal', chat='customer-1', text='xin chào'):
        return cs.ghi_su_kien({'channel': channel, 'account_id': 'account-1', 'external_chat_id': chat,
                              'sender_type': kind, 'sender_id': chat, 'sender_name': 'Người trực' if kind == 'human' else 'Lan',
                              'text': text, 'created_at': self.now + seconds})

    def test_profile_and_conflict(self):
        cid = self.event()['conversation_id']
        a = ops.profile(cid)
        saved = ops.save_profile(cid, revision=a['revision'], owner='Mai', tags=['VIP', 'VIP'], note='Thích màu be')
        self.assertEqual(saved['customer_tags'], ['VIP'])
        self.assertEqual(saved['customer_note'], 'Thích màu be')
        self.assertEqual(saved['owner'], 'Mai')
        with self.assertRaises(ValueError):
            ops.save_profile(cid, revision=a['revision'], owner='Nam', tags=[], note='ghi đè')
        self.assertEqual(ops.profile(cid)['owner'], 'Mai')
        self.assertEqual(len(ops.audit()), 1)

    def test_exact_tag_and_unread_pagination(self):
        a = self.event(chat='a')['conversation_id']
        b = self.event(chat='b')['conversation_id']
        cs.dat_tag_khach(cs.chi_tiet(a)['customer_id'], ['VIP'])
        cs.dat_tag_khach(cs.chi_tiet(b)['customer_id'], ['VIP2'])
        self.assertEqual([x['id'] for x in cs.danh_sach(tag='VIP')], [a])
        cs.danh_dau_da_doc(a)
        self.assertEqual(cs.danh_sach(tag='VIP', unread=True), [])
        self.assertEqual([x['id'] for x in cs.danh_sach(unread=True, limit=1)], [b])

    def test_response_burst_sla_and_channel_isolation(self):
        self.event(-600)
        self.event(-400)
        self.event(-200, kind='human')
        self.event(-100)
        self.event(-50, kind='ai')
        self.event(-800, channel='telegram', chat='elsewhere')
        r = ops.report(sla=300)
        self.assertEqual(r['response_count'], 2)
        self.assertEqual(r['avg_seconds'], 225)  # 400s và 50s; không reset theo tin khách thứ hai.
        self.assertEqual(r['sla_met'], 1)
        self.assertEqual(r['messages'], {'customer': 3, 'human': 1, 'ai': 1})
        self.assertEqual(r['pending_count'], 0)
        self.assertEqual(sum(r['hourly']), 3)

    def test_backlog_uses_first_unanswered_message_and_closed_excluded(self):
        cid = self.event(-600)['conversation_id']
        self.event(-10)
        r = ops.report(sla=300)
        self.assertGreaterEqual(r['pending'][0]['waiting_seconds'], 600)
        self.assertEqual(r['overdue_count'], 1)
        cs.dat_che_do(cid, 'closed')
        self.assertEqual(ops.report()['pending_count'], 0)

    def test_templates_validation_and_audit_append_only(self):
        ops.save_template('/chao', 'Chào {tenKhach}')
        ops.save_template('chao', 'Xin chào {tenKhach}')
        self.assertEqual(len(ops.templates()), 1)
        with self.assertRaises(ValueError):
            ops.save_template('../x', 'x')
        with self.assertRaises(Exception):
            ops._db().execute('DELETE FROM conversation_audit')
        ops._db().rollback()
        self.assertEqual(len(ops.audit()), 2)

    def test_customer_after_reply_same_timestamp_still_waits(self):
        self.event(-600, kind='human')
        self.event(-600, kind='customer')
        self.assertEqual(ops.report()['pending_count'], 1)

    def test_shared_customer_profile_conflicts_across_conversations(self):
        a = self.event(chat='a')['conversation_id']
        b = self.event(chat='b')['conversation_id']
        with cs._lock:
            db = cs._conn()
            db.execute('UPDATE conversations SET customer_id=? WHERE id=?', (cs.chi_tiet(a)['customer_id'], b))
            db.commit()
        ops.profile(b)  # B mở trước khi A sửa, giữ revision 0.
        ops.save_profile(a, revision=0, owner='Mai', tags=['VIP'], note='giữ lại')
        with self.assertRaises(ValueError):
            ops.save_profile(b, revision=0, owner='Nam', tags=[], note='không được ghi đè')

    def test_api_profile_validation_and_summary_is_preview(self):
        app = FastAPI(); routes.register(app); client = TestClient(app)
        cid = self.event()['conversation_id']
        self.assertEqual(client.get('/conversation-ops/profile/999').status_code, 404)
        self.assertEqual(client.put('/conversation-ops/profile/' + str(cid), json={'revision': -1}).status_code, 422)
        self.assertEqual(client.post('/conversation-ops/summary/' + str(cid)).status_code, 400)
        with cs._lock:
            db = cs._conn(); db.execute('UPDATE conversations SET bot_id=? WHERE id=?', ('bot', cid)); db.commit()
        async def preview(bot_id, prompt, **kwargs):
            self.assertEqual(bot_id, 'bot')
            self.assertEqual(kwargs['max_chars'], 16000)
            return {'ok': True, 'text': 'Khách cần tư vấn.'}
        before = cs.chi_tiet(cid)['message_count']
        with patch('chatbot_runtime.thu_bot', preview):
            response = client.post('/conversation-ops/summary/' + str(cid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cs.chi_tiet(cid)['message_count'], before)
        self.assertEqual(client.get('/conversation-ops/report?channel=telegram').json()['report']['conversations'], 0)

    def test_new_routes_inherit_authentication(self):
        import main
        client = TestClient(main.app, base_url='http://localhost')
        with patch.object(main.cfgmod, 'gate_active', return_value=True), \
             patch.object(main.cfgmod, 'valid_session', return_value=False), \
             patch.object(main, '_token_ok', return_value=False):
            for method, url in [('get', '/conversation-ops/report'), ('get', '/conversation-ops/audit.csv'),
                                ('put', '/conversation-ops/templates'), ('post', '/conversation-ops/summary/1')]:
                self.assertEqual(getattr(client, method)(url).status_code, 401, url)


if __name__ == '__main__':
    unittest.main()
