"""MinMin's multichannel inbox: preserve scope, drafts, handoff and delivery integrity. No real messages."""
from _paths import ROOT, SERVER
import os,tempfile,asyncio,json
from pathlib import Path
state=Path(tempfile.mkdtemp(prefix='minmin-omni-'))
os.environ['JAVIS_STATE_DIR']=str(state)
os.environ['JAVIS_ALLOWED_HOSTS']='testserver'
import chatbot_store as bots
import chatbot_runtime as runtime
import conversations as inbox
import inbox_state
from fastapi import FastAPI
from fastapi.testclient import TestClient
import routes.conversations as routes

app=FastAPI()
sent=[]
async def send(channel, account, chat, text, chat_type='private'):
    sent.append((channel, account['id'], chat, text))
    return True,''
routes.channels.gui=send
async def answer(c,msgs,draft=False,instruction=''):
    return {'ok':True,'text':'Nháp: '+instruction,'meta':runtime.manual_meta(c,msgs[-1])}
routes.register(app,routes.ConversationsDeps(bot_status=lambda _: {'running':True},manual_answer=answer,
                                           manual_done=runtime.manual_done,manual_meta=runtime.manual_meta))
cl=TestClient(app)
b,err=bots.create_bot({'name':'MinMin shop','agent_slug':'shop','brain':'shop','channel':'telegram'})
assert b,err
def event(account,chat,text='Khách hỏi',bot=b):
    r=inbox.ghi_su_kien({'channel':'telegram','account_id':account,'bot_id':bot,'external_chat_id':chat,
                        'chat_type':'private','sender_type':'customer','sender_id':chat,'sender_name':'Khách',
                        'text':text,'external_message_id':str(len(inbox.danh_sach())+1)+text})
    return r.get('conversation_id') or r.get('id')
event('page-a','111');event('page-b','111')
rows=inbox.danh_sach();assert len(rows)==2
a=next(x for x in rows if x['channel_account_id']=='telegram:page-a')['id']
c=inbox.chi_tiet(a)
assert inbox_state.state(c,bots.get_bot(b),True)['who']=='ai'
# Per-chat block overrides permissive private-chat defaults; another account/chat remains untouched.
r=cl.post(f'/conversations/{a}/ai',data={'on':'0'});assert r.status_code==200,r.text
assert not bots.chat_allowed(bots.get_bot(b),'private','111','page-a')
assert runtime._ly_do_im(bots.get_bot(b),{'chat_type':'private','chat_id':'111','account_id':'page-a'})=='chat_tat'
assert bots.chat_allowed(bots.get_bot(b),'private','222')
assert bots.chat_allowed(bots.get_bot(b),'private','111','page-b')
assert cl.post(f'/conversations/{a}/ai',data={'on':'1'}).json()['conversation']['ai_allowed']
# MinMin's custom customer-group restrictions survive; explicit per-chat allow does not enable the whole group.
base={'channel':'zalo_personal','rieng_pham_vi':'chon','nhom_khach':[{'id':'care','ten':'Care','bat':False,'thanh_vien':['111','222']} ]}
assert not bots.chat_allowed(base,'private','111')
p=bots.allow_patch(base,'private','111',True)
assert bots.chat_allowed(dict(base,**p),'private','111')
assert not bots.chat_allowed(dict(base,**p),'private','222')
# Draft survives store close/reopen and mode changes, and never counts as an AI message before delivery.
assert cl.post(f'/conversations/{a}/mode',data={'mode':'draft'}).status_code==200
assert cl.post(f'/conversations/{a}/ai-reply',data={'mode':'draft','instruction':'Báo giá 20 thùng'}).status_code==200
d=inbox.draft_of(inbox.chi_tiet(a));assert d['text']=='Nháp: Báo giá 20 thùng' and not sent
inbox.close();assert inbox.draft_of(inbox.chi_tiet(a))['text']==d['text']
assert not any(m['sender_type']=='ai' for m in inbox.tin_nhan(a))
cl.post(f'/conversations/{a}/mode',data={'mode':'human'})
assert inbox.draft_of(inbox.chi_tiet(a)) and inbox_state.state(inbox.chi_tiet(a),bots.get_bot(b),True)['who']=='you'
# Send the owner's edited text once. Duplicate click or lost-response retry cannot deliver again.
r=cl.post(f'/conversations/{a}/draft',data={'action':'send','text':'Giá đã duyệt','draft_ts':d['ts']})
assert r.status_code==200,r.text
assert sent==[('telegram','page-a','111','Giá đã duyệt')]
assert cl.post(f'/conversations/{a}/draft',data={'action':'send','text':'Giá đã duyệt'}).status_code==409
assert len(sent)==1 and not inbox.draft_of(inbox.chi_tiet(a))
# A new customer message invalidates an old draft; a newer draft cannot be sent using an older browser tab.
inbox.save_draft(a,'Câu cũ',inbox.last_customer_message_id(a));old=inbox.draft_of(inbox.chi_tiet(a))
event('page-a','111','Câu khách mới')
assert cl.post(f'/conversations/{a}/draft',data={'action':'send','text':'Câu cũ','draft_ts':old['ts']}).status_code==409
inbox.save_draft(a,'Câu mới',inbox.last_customer_message_id(a));new=inbox.draft_of(inbox.chi_tiet(a))
assert cl.post(f'/conversations/{a}/draft',data={'action':'send','text':'Câu cũ','draft_ts':old['ts']}).status_code==409
# An ambiguous send is durable, retains the draft for review and blocks repeats even after restart.
async def uncertain(*args,**kw): return False,'network outcome unknown'
routes.channels.gui=uncertain
assert cl.post(f'/conversations/{a}/draft',data={'action':'send','text':'Câu mới','draft_ts':new['ts']}).status_code==400
inbox.close();assert inbox.draft_of(inbox.chi_tiet(a))['delivery']=='uncertain'
assert cl.post(f'/conversations/{a}/draft',data={'action':'send','text':'Câu mới'}).status_code==409
assert cl.post(f'/conversations/{a}/draft',data={'action':'discard'}).status_code==200
# Persisted claim serializes two simultaneous callers before network I/O.
inbox.save_draft(a,'Một lần',inbox.last_customer_message_id(a))
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(2) as ex:results=list(ex.map(lambda _:inbox.claim_draft(a)[0],range(2)))
assert sorted(results)==[False,True]
# A channel-filtered list must not include another account; who counts use the same state computation.
r=cl.get('/conversations',params={'account_ids':'telegram:page-a'});assert r.status_code==200,r.text
assert all(x['channel_account_id']=='telegram:page-a' for x in r.json()['items'])
assert 'who_counts' in r.json() and all('who' in x for x in r.json()['items'])
# The real live callback drafts with read-only tools and rechecks a takeover while the model is running.
event('page-a','333','Xin báo giá')
live=next(x for x in inbox.danh_sach() if x['external_chat_id']=='333')['id']
inbox.dat_che_do(live,'draft')
seen=[]
async def engine(text,meta,progress,channel='',bot=None,nhap=False,ghi_kho=True):
    seen.append((bot['muc_quyen'],nhap,ghi_kho))
    return {'text':'Câu tư vấn','files':[]}
runtime.wire(answer=engine,brain_root=lambda _:str(state),read_agent=lambda *a:'')
runtime.chatbot_grounding.thu_thap=lambda *a,**k:{'co':False,'khoi':'','nguon':[]}
out=asyncio.run(runtime._make_answer_fn(b)('Xin báo giá',{'chat_id':'333','account_id':'page-a','chat_type':'private'}))
assert out.get('draft') and not out.get('text') and inbox.draft_of(inbox.chi_tiet(live))['text']=='Câu tư vấn'
assert seen[-1][0]=='suggest'
assert not any(m['sender_type']=='ai' for m in inbox.tin_nhan(live))
# Manual drafting uses the isolated engine session without durable chat writes.
r=asyncio.run(runtime.manual_answer(inbox.chi_tiet(live),inbox.tin_nhan(live),True,'Báo giá sỉ'))
assert r['ok'] and seen[-1]==('suggest',True,False)
inbox.dat_che_do(live,'ai')
async def takeover(text,meta,progress,channel='',bot=None,**kw):
    inbox.dat_che_do(live,'human')
    return {'text':'Không được gửi câu này','files':[]}
runtime.wire(answer=takeover,brain_root=lambda _:str(state),read_agent=lambda *a:'')
out=asyncio.run(runtime._make_answer_fn(b)('Câu tiếp theo',{'chat_id':'333','account_id':'page-a','chat_type':'private'}))
assert not out.get('text') and not any(m['sender_type']=='ai' for m in inbox.tin_nhan(live))
# Brand regression is the actual message sent to Telegram, not a renamed protocol key.
src=(ROOT/'server/telegram_bot.py').read_text(encoding='utf-8')
assert '"🤔 MinMin đang xử lý…"' in src and '"🤔 Javis đang xử lý…"' not in src
print('PASS: MinMin brand, custom scopes, account isolation, persisted drafts, handoff, stale drafts and exactly-once draft claims')
