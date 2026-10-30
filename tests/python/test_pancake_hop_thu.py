"""Pancake trong Hộp thư (26.10.315): mỗi Page một tài khoản, đồng bộ tăng dần chống trùng, nhân viên Pancake nhắn
thì A.I. nhường, mặc định chỉ soạn nháp, tự trả lời phải bật riêng từng Page, gửi nháp đúng một lần, khung 24 giờ.
Dữ liệu Pancake là bản giả; không token thật, không gọi mạng."""
from _paths import ROOT, SERVER
import asyncio
import os
import tempfile
import time
from pathlib import Path

state = Path(tempfile.mkdtemp(prefix='minmin-pancake-'))
os.environ['JAVIS_STATE_DIR'] = str(state)
os.environ['JAVIS_ALLOWED_HOSTS'] = 'testserver'

import channels
import channel_accounts
import chatbot_store as bots
import chatbot_runtime as runtime
import conversations as inbox
import inbox_state
import pancake_hoi_thoai as ph
import pancake_inbox as pi
from channels import pancake as kenh_pk
from fastapi import FastAPI
from fastapi.testclient import TestClient
import routes.conversations as conv_routes
import routes.channels as ch_routes

PID, PID2 = '111222333', '444555666'
TOKEN = 'tok-secret-pancake'
CONN = {'id': 'pc-1', 'connector_id': 'pancake-thong-ke', 'perm': 'full', 'enabled': True,
        'secrets': {'pages': f'{PID} | {TOKEN} | Shop Halimi\n{PID2} | tok-2 | Shop Mei'}}
pi._ket_noi = lambda: [CONN]
pi._quyen_gui = lambda p: '' if p.get('perm') == 'full' else 'chỉ đọc'


def iso(ts):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ts))


# ---- Pancake giả ------------------------------------------------------------------------------------------------
FAKE = {'convs': [], 'msgs': {}, 'sent': [], 'calls': []}


async def fake_request(page, method, version, path, params=None, body=None, file=None):
    FAKE['calls'].append((page['id'], method, version, path, dict(params or {}), body))
    assert page['token'] in (TOKEN, 'tok-2')
    if method == 'GET' and path == '/conversations':
        return {'success': True, 'conversations': [c for c in FAKE['convs'] if c['page_id'] == page['id']]}
    if method == 'GET' and path.endswith('/messages'):
        cid = path.split('/')[2]
        return {'success': True, 'messages': list(FAKE['msgs'].get(cid, []))}
    if path == '/tags':
        return {'success': True, 'tags': [{'id': 7, 'text': 'Khách VIP'}]}
    if path == '/users':
        return {'success': True, 'users': [{'id': 'u-lan', 'name': 'Lan Sale'}]}
    if method == 'POST' and path.endswith('/messages'):
        cid = path.split('/')[2]
        mid = f'm-out-{len(FAKE["sent"]) + 1}'
        FAKE['sent'].append((page['id'], cid, body['message']))
        return {'success': True, 'id': mid}
    raise AssertionError(path)

ph.request = fake_request


def conv(cid, updated, page_id=PID, **kw):
    c = {'id': cid, 'page_id': page_id, 'type': 'INBOX', 'updated_at': updated,
         'customers': [{'id': 'cus-1', 'fb_id': 'psid-1', 'name': 'Chị Hoa'}]}
    c.update(kw)
    for i, x in enumerate(FAKE['convs']):
        if x['id'] == cid:
            FAKE['convs'][i] = c
            return c
    FAKE['convs'].append(c)
    return c


def msg(cid, mid, text, ts, page_side=False, admin=''):
    f = {'id': PID, 'name': 'Shop Halimi'} if page_side else {'id': 'psid-1', 'name': 'Chị Hoa'}
    if admin:
        f['admin_name'] = admin
    FAKE['msgs'].setdefault(cid, []).append({'id': mid, 'from': f, 'message': text, 'inserted_at': iso(ts)})


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


asyncio.set_event_loop(asyncio.new_event_loop())

# ---- 1. Sổ kênh: Pancake là kênh kind=account, trả lời được từ MinMin, gắn được bot -----------------------------
channels.reset_cho_test()
s = channels.spec('pancake')
assert s and s.kind == 'account' and s.logo == 'pancake'
assert s.nl('tra_loi_tu_javis') and s.nl('bot') and s.nl('ghi_theo_cong_tac')
assert 'pancake' in inbox.KENH or 'pancake' in channels.ids()
inbox.KENH = channels.ids()

# ---- 2. Page lấy từ kết nối Thống kê Pancake có sẵn, mỗi Page một tài khoản ảo chọn được cho bot --------------
tk = {a['id']: a for a in pi.tai_khoan()}
assert set(tk) == {PID, PID2} and tk[PID]['label'] == 'Shop Halimi' and not tk[PID]['theo_doi']
assert TOKEN not in repr(tk)
a = channel_accounts.get_account(PID)
assert a and a['channel'] == 'pancake' and a['kind'] == 'account'
assert channel_accounts.get_token(PID) == PID, 'virtual account key is the page id, never the Pancake token'
assert not pi.bao_co_su_kien(PID), 'a webhook poke for a Page that is off does nothing'

# ---- 3. Bật Page: lần đầu chỉ ghi mốc, không kéo lịch sử ----------------------------------------------------------
now = time.time()
msg('c1', 'old-1', 'Tin từ tuần trước', now - 7 * 86400)
conv('c1', iso(now - 7 * 86400))
assert pi.bat(PID, True)['ok'] and pi.dang_theo_doi(PID) and pi.bao_co_su_kien(PID)
r = run(pi.doc_mot_lan(pi.page(PID)))
assert r['moi'] == 0 and not inbox.danh_sach(channel='pancake'), 'first poll only records a baseline'
q = FAKE['calls'][0]
assert q[2:4] == ('v2', '/conversations') and q[4]['order_by'] == 'updated_at' and q[4]['type'] == 'INBOX'

# ---- 4. Khách nhắn mới: vào Hộp thư, mặc định "A.I. soạn, tôi duyệt"; đọc lại không trùng --------------------
msg('c1', 'm-1', 'Váy này còn size M không shop?', now - 30)
conv('c1', iso(now - 30), tags=[7], recent_phone_numbers=[{'phone_number': '0912345678'}],
     current_assign_users=[{'id': 'u-lan', 'name': 'Lan Sale'}])
r = run(pi.doc_mot_lan(pi.page(PID)))
assert r['moi'] == 2, r      # the old message comes in as context, the new one as the customer's question
rows = inbox.danh_sach(channel='pancake')
assert len(rows) == 1
c1 = inbox.chi_tiet(rows[0]['id'])
assert c1['mode'] == 'draft', 'a Pancake chat never defaults to A.I. replies'
assert c1['unread_count'] == 1, 'history before the Page was switched on is not unread'
ms = inbox.tin_nhan(c1['id'])
assert [m['external_message_id'] for m in ms] == ['old-1', 'm-1'] and ms[-1]['sender_type'] == 'customer'
assert c1['metadata']['pancake'] == {'the': ['Khách VIP'], 'nhan_vien': ['Lan Sale'], 'sdt': '0912345678'}
conv('c1', iso(now - 29))   # touched again, same messages
r = run(pi.doc_mot_lan(pi.page(PID)))
assert r['moi'] == 0 and len(inbox.tin_nhan(c1['id'])) == 2, 'Pancake message ids stop duplicates'

# ---- 5. "A.I. tự trả lời" bị chặn tới khi bật riêng Page, bật phải xác nhận cảnh báo ----------------------------
app = FastAPI()
conv_routes.register(app, conv_routes.ConversationsDeps(bot_status=lambda _: {'running': True}))
ch_routes.register(app, ch_routes.ChannelsDeps(bot_status=lambda _: {}, main_bot_token=lambda: ''))
app.include_router(conv_routes.router)
app.include_router(ch_routes.router)
cl = TestClient(app)
r = cl.post(f'/conversations/{c1["id"]}/mode', data={'mode': 'ai'})
assert r.status_code == 409 and r.json()['code'] == 'mode_blocked'
assert inbox.chi_tiet(c1['id'])['mode'] == 'draft'
row = next(x for x in cl.get('/conversations?channel=pancake').json()['items'] if x['id'] == c1['id'])
assert row['auto_ok'] is False
acc = next(x for x in cl.get('/channels/accounts').json()['accounts'] if x['account_key'] == f'pancake:{PID}')
assert acc['auto_reply'] is False and acc['watch'] is True and acc['kind'] == 'account'
r = cl.post(f'/channels/accounts/{PID}/auto-reply', data={'on': '1'})
assert r.status_code == 409 and 'nhân viên' in r.json()['error'].lower(), 'switching on needs the warning confirmed'
assert not pi.tu_tra_loi(PID)
assert cl.post(f'/channels/accounts/{PID}/auto-reply', data={'on': '1', 'xac_nhan': '1'}).json()['tu_tra_loi']
assert cl.post(f'/conversations/{c1["id"]}/mode', data={'mode': 'ai'}).status_code == 200
assert not pi.tu_tra_loi(PID2), 'the switch is per Page'
r = cl.post(f'/channels/accounts/{PID}/auto-reply', data={'on': '0'}).json()
assert r['doi_ve_nhap'] == 1 and inbox.chi_tiet(c1['id'])['mode'] == 'draft', 'switching off returns chats to drafts'

# ---- 6. Gửi nháp từ Hộp thư: đúng một lần, qua API gửi Pancake đang có; tiếng vọng không bị tính là nhân viên ---
inbox.save_draft(c1['id'], 'Dạ còn size M ạ', inbox.last_customer_message_id(c1['id']))
d = inbox.draft_of(inbox.chi_tiet(c1['id']))
r = cl.post(f'/conversations/{c1["id"]}/draft', data={'action': 'send', 'text': 'Dạ còn size M ạ', 'draft_ts': d['ts']})
assert r.status_code == 200, r.text
assert FAKE['sent'] == [(PID, 'c1', 'Dạ còn size M ạ')]
post = [x for x in FAKE['calls'] if x[1] == 'POST'][-1]
assert post[2:4] == ('v1', '/conversations/c1/messages') and post[5] == {'action': 'reply_inbox', 'message': 'Dạ còn size M ạ'}
assert cl.post(f'/conversations/{c1["id"]}/draft', data={'action': 'send', 'text': 'Dạ còn size M ạ'}).status_code == 409
assert len(FAKE['sent']) == 1
msg('c1', 'm-out-1', 'Dạ còn size M ạ', time.time(), page_side=True)
conv('c1', iso(time.time()))
run(pi.doc_mot_lan(pi.page(PID)))
c1 = inbox.chi_tiet(c1['id'])
assert c1['mode'] == 'draft', 'the echo of MinMin own reply is not a staff takeover'
assert sum(1 for m in inbox.tin_nhan(c1['id']) if m['text'] == 'Dạ còn size M ạ') == 1
assert any(m['external_message_id'] == 'm-out-1' for m in inbox.tin_nhan(c1['id'])), 'echo id attached to our row'
run(pi.doc_mot_lan(pi.page(PID)))
assert sum(1 for m in inbox.tin_nhan(c1['id']) if m['text'] == 'Dạ còn size M ạ') == 1

# ---- 7. Nhân viên trả lời trong Pancake: "Bạn đang xử lý", nháp chờ bị bỏ; tin Botcake không tính -------------
msg('c1', 'm-2', 'Ship về Bắc Giang mấy ngày ạ?', time.time())
conv('c1', iso(time.time()))
run(pi.doc_mot_lan(pi.page(PID)))
inbox.save_draft(c1['id'], 'Nháp A.I.', inbox.last_customer_message_id(c1['id']))
msg('c1', 'm-3', 'Cảm ơn chị đã nhắn tin!', time.time(), page_side=True, admin='Botcake')
conv('c1', iso(time.time() + 1))
run(pi.doc_mot_lan(pi.page(PID)))
c1 = inbox.chi_tiet(c1['id'])
assert c1['mode'] == 'draft' and inbox.draft_of(c1), 'an automated greeting does not take the chat over'
assert next(m for m in inbox.tin_nhan(c1['id']) if m['external_message_id'] == 'm-3')['sender_type'] == 'system'
msg('c1', 'm-4', 'Dạ 2 ngày chị nhé', time.time(), page_side=True, admin='Lan Sale')
conv('c1', iso(time.time() + 2))
run(pi.doc_mot_lan(pi.page(PID)))
c1 = inbox.chi_tiet(c1['id'])
m4 = next(m for m in inbox.tin_nhan(c1['id']) if m['external_message_id'] == 'm-4')
assert m4['sender_type'] == 'human' and 'Lan Sale' in m4['sender_name']
assert c1['mode'] == 'human' and not inbox.draft_of(c1)
b, err = bots.create_bot({'name': 'Halimi A.I.', 'agent_slug': 'shop', 'brain': 'shop', 'channel': 'pancake',
                          'account_ids': [PID]})
assert b, err
inbox.set_account_bot(f'pancake:{PID}', b)
st = inbox_state.state(inbox.chi_tiet(c1['id']), bots.get_bot(b), True)
assert st['who'] == 'owner' and st['who_code'] == 'you', st

# ---- 8. Bot: chưa bật tự trả lời thì KHÔNG gửi gì, câu A.I. thành nháp; bật rồi mới gửi -------------------------
inbox.dat_che_do(c1['id'], 'draft')
asked = []


async def answer(text, meta, progress):
    asked.append((text, meta['chat_id'], meta['account_id']))
    return {'text': 'Dạ shop gửi chị bảng size ạ', 'files': []}

tb = kenh_pk.Transport(PID, '', answer)
n = len(FAKE['sent'])
run(tb.tra_loi('c1', [{'text': 'Cho xem bảng size', 'id': 'm-5', 'sender_id': 'psid-1', 'sender_name': 'Chị Hoa'}]))
assert asked[-1] == ('Cho xem bảng size', 'c1', PID)
assert len(FAKE['sent']) == n and inbox.draft_of(inbox.chi_tiet(c1['id']))['text'] == 'Dạ shop gửi chị bảng size ạ'
inbox.dat_che_do(c1['id'], 'ai')          # forced to ai without the Page switch: still never sends
run(tb.tra_loi('c1', [{'text': 'Còn không', 'id': 'm-6'}]))
assert len(FAKE['sent']) == n and inbox.chi_tiet(c1['id'])['mode'] == 'draft'
inbox.dat_che_do(c1['id'], 'human')
run(tb.tra_loi('c1', [{'text': 'Alo', 'id': 'm-7'}]))
assert len(asked) == 2, 'staff handling: the A.I. is not even asked'
pi.dat_tu_tra_loi(PID, True, True)
inbox.dat_che_do(c1['id'], 'ai')
run(tb.tra_loi('c1', [{'text': 'Size L còn không', 'id': 'm-8'}]))
assert FAKE['sent'][-1] == (PID, 'c1', 'Dạ shop gửi chị bảng size ạ') and len(FAKE['sent']) == n + 1
pi.dat_tu_tra_loi(PID, False)

# ---- 9. Khung 24 giờ của Facebook và quyền chỉ đọc: chặn trước khi gọi mạng -----------------------------------
old = time.time() - 3 * 86400
msg('c9', 'x-1', 'Hôm kia hỏi', old)
conv('c9', iso(old))
pi._TT.pop(PID, None)
run(pi.doc_mot_lan(pi.page(PID)))
assert pi.qua_24h(PID, 'c9')
n = len(FAKE['sent'])
ok, why = run(pi.gui(PID, 'c9', 'Chào chị'))
assert not ok and '24 giờ' in why and len(FAKE['sent']) == n
CONN['perm'] = 'read'
pi._DS['ts'] = 0
ok, why = run(pi.gui(PID, 'c1', 'Chào chị'))
assert not ok and len(FAKE['sent']) == n
CONN['perm'] = 'full'
pi._DS['ts'] = 0


async def rejected(page, method, version, path, params=None, body=None, file=None):
    raise RuntimeError('(#10) This message is sent outside of allowed window.')
ph.request = rejected
ok, why = run(pi.gui(PID, 'c1', 'Chào chị'))
assert not ok and why.startswith('Đã quá 24 giờ')
ph.request = fake_request

# ---- 10. Thống kê đếm Pancake như mọi kênh; tin nhân viên là tin người trực -----------------------------------
ins = inbox.insights(time.time() - 30 * 86400, time.time() + 10)
assert ins['by_channel']['pancake']['customer'] >= 3 and ins['by_channel']['pancake']['human'] >= 1
assert TOKEN not in repr(inbox.danh_sach(channel='pancake'))
print('PASS: Pancake Pages as inbox accounts, incremental dedup sync, staff takeover, draft-only default, '
      'per-Page auto-reply opt-in, single send, echo, 24-hour window and stats')
