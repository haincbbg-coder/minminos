"""Offline regressions for follow-up evidence and owner bot branding."""
from _paths import ROOT, SERVER
import asyncio
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from cryptography.fernet import Fernet
import secrets_store
from turn_continuity import ReceiptStore, prepare, track, TTL
from telegram_bot import TelegramBot


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'receipts.db'
        self.store = ReceiptStore(self.path)
        self.scope = self.store.scope(self.tmp.name, 'chat-1')
        p = patch.object(secrets_store, '_fernet', Fernet(Fernet.generate_key()))
        p.start()
        self.addCleanup(p.stop)

    def test_restart_isolation_redaction_and_encryption(self):
        self.store.save(self.scope, 'higgsfield.generateimage', 'returned',
                        json.dumps({'job_id': 'job-123', 'status': 'processing', 'api_key': 'private-secret'}))
        recovered = ReceiptStore(self.path).recent(self.scope)
        self.assertIn('job-123', str(recovered))
        self.assertIn('processing', str(recovered))
        self.assertNotIn('private-secret', str(recovered))
        self.assertEqual(self.store.recent(self.store.scope(self.tmp.name, 'chat-2')), [])
        self.assertEqual(self.store.recent(self.store.scope('/other-brain', 'chat-1')), [])
        self.assertNotIn(b'job-123', self.path.read_bytes())

    def test_bounds_and_expiry(self):
        for i in range(40):
            self.store.save(self.scope, 'tool', 'returned', str(i))
        self.assertEqual(len(self.store.recent(self.scope)), 8)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM receipts').fetchone()[0], 32)
            db.execute('UPDATE receipts SET created=0')
        self.assertEqual(self.store.recent(self.scope), [])

    def test_copy_and_discovery_contract(self):
        original = [{'role': 'system', 'content': 'identity'}, {'role': 'user', 'content': '4 files'}]
        receipts = [{'tool': 'image', 'state': 'returned', 'result_excerpt': 'processing job-123'}]
        result = prepare(original, [{'fn': 'javis_search_tools'}], receipts)
        self.assertEqual(len(original), 2)
        self.assertEqual(result[-1], original[-1])
        self.assertIn('PHẢI gọi javis_search_tools', result[1]['content'])
        self.assertIn('job-123', result[1]['content'])
        self.assertIn('không tự coi là thành công', result[1]['content'])

    def test_tracking_does_not_persist_arguments_or_replay_on_failure(self):
        events = [{'type': 'tool_call', 'name': 'javis_run_tool',
                   'input': {'name': 'higgsfield.generateimage', 'arguments': {'prompt': 'private-prompt'}}},
                  {'type': 'tool_result', 'name': 'javis_run_tool', 'content': '{"job_id":"job-321"}'}]
        async def source():
            for event in events:
                yield event
        async def collect():
            return [event async for event in track(source(), self.store, self.scope)]
        self.assertEqual(asyncio.run(collect()), events)
        data = str(self.store.recent(self.scope))
        self.assertIn('higgsfield.generateimage', data)
        self.assertIn('job-321', data)
        self.assertNotIn('private-prompt', data)
        with patch.object(self.store, 'save', side_effect=RuntimeError('disk unavailable')):
            self.assertEqual(asyncio.run(collect()), events)

    def test_api_followup_receives_previous_job(self):
        import main
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from contextlib import ExitStack
        seen = []
        async def engine(key, model, messages, *args):
            seen.append(messages)
            yield {'type': 'tool_call', 'name': 'higgsfield.generateimage', 'input': {}}
            yield {'type': 'tool_result', 'name': 'higgsfield.generateimage',
                   'content': '{"job_id":"followup-job","status":"processing"}'}
        original = [{'role': 'user', 'content': '4 separate images'}]
        async def turns():
            for _ in range(2):
                stream = await main._api_stream_mcp('openai', 'fake', 'fake', original, brain='brain')
                async for _ in stream:
                    pass
        with ExitStack() as stack:
            for obj, name, value in [
                (main, '_hub_enabled', lambda: True),
                (main, '_brain_root', lambda brain: self.tmp.name),
                (main.mcp_hub, 'discover_all', AsyncMock(return_value=([{'fn': 'javis_search_tools'}], {}))),
                (main.mcp_hub, 'registry_inventory', lambda *a, **kw: ([], {})),
                (main.context_runtime, 'current_trace', lambda: SimpleNamespace(session_id='chat-1')),
                (main, '_CONTEXT_RUNTIME', MagicMock()),
                (main, '_schedule_registry_shadow', MagicMock()),
                (main, '_be_khoa_cua', lambda *a: None),
                (main.turn_continuity, 'ReceiptStore', lambda: self.store),
                (main.engine, 'openai_chat_with_mcp', engine),
                (main.engine, 'thu_lai_khi_tam_thoi', lambda fn, **kw: fn()),
            ]:
                stack.enter_context(patch.object(obj, name, value))
            asyncio.run(turns())
        self.assertNotIn('followup-job', str(seen[0]))
        self.assertIn('followup-job', str(seen[1]))
        self.assertEqual(len(original), 1)

    def test_owner_name_only_and_failure_visible(self):
        bot = TelegramBot.__new__(TelegramBot)
        bot.token = 'test'
        bot.display_name = 'MinMin OS'
        client = AsyncMock()
        class Response:
            def json(self):
                return {'ok': True}
        client.post.return_value = Response()
        asyncio.run(bot._dong_bo_ten(client))
        self.assertEqual(client.post.await_count, 3)
        self.assertEqual([call.kwargs['json']['language_code'] for call in client.post.call_args_list], ['', 'vi', 'en'])
        self.assertTrue(all(c.kwargs['json']['name'] == 'MinMin OS' for c in client.post.call_args_list))
        client.post.reset_mock()
        bot.display_name = ''
        asyncio.run(bot._dong_bo_ten(client))
        client.post.assert_not_called()
        bot.display_name = 'MinMin OS'
        client.post.side_effect = RuntimeError('offline')
        asyncio.run(bot._dong_bo_ten(client))
        self.assertIn('RuntimeError', bot.loi_ten_hien_thi)


if __name__ == '__main__':
    unittest.main()
