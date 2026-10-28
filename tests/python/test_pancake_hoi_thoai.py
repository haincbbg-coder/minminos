"""Pancake conversation API and mandatory approval. No live customer or network calls."""
from _paths import ROOT, SERVER
import asyncio
import json
import os
import tempfile
from pathlib import Path

os.environ['JAVIS_STATE_DIR']=tempfile.mkdtemp(prefix='pc-tests-')
import pancake_hoi_thoai as pc
import pancake_chat_mcp as stats
import mcp_hub as hub
import hanh_dong as hd


async def main():
    calls=[]
    async def request(page,method,version,path,params=None,body=None,file=None):
        calls.append((page['id'],method,version,path,params,body))
        return {'success':True,'data':[{'message':'hello'}]}
    pc.request=request
    spec={'secrets':{'pages':'123456789 | token-secret-first | Shop A\n987654321 | token-secret-second | Shop B'}}
    assert (await pc.call('pancake_messages_get',{'conversation_id':'c'},spec)).startswith('ERROR:')
    assert not calls, 'Never guess which of several pages a customer belongs to'
    out=await stats.call('pancake_messages_get',{'page':'123456789','conversation_id':'123_456','current_count':30},spec)
    assert 'hello' in out and calls[-1][:4]==('123456789','GET','v1','/conversations/123_456/messages')
    assert calls[-1][4]['current_count']==30
    for bad in ['../other','x/y','a?token=leak','https://evil']:
        before=len(calls)
        assert (await pc.call('pancake_messages_get',{'page':'123456789','conversation_id':bad},spec)).startswith('ERROR:')
        assert len(calls)==before
    method,ver,path,q,body=pc.plan('pancake_send_message',{'conversation_id':'1','message':'Tư vấn đầy đủ','reply_to_comment_id':'2'})
    assert body=={'action':'reply_comment','message_id':'2','message':'Tư vấn đầy đủ'}
    assert pc.plan('pancake_conversation_assign',{'conversation_id':'1','assignee_ids':[]})[-1]=={'assignee_ids':[]}
    assert pc.plan('pancake_conversation_tag',{'conversation_id':'1','tag_id':'9','action':'remove'})[-1]['action']=='remove'
    for name in pc.WRITE:
        assert hub.mcp_catalog.classify(hub.mcp_catalog.get('pancake-thong-ke'),name,{})=='danger'
    async def fail(*a,**kw): raise RuntimeError('token-secret-first')
    pc.request=fail
    out=await pc.call('pancake_tags_list',{'page':'123456789'},spec)
    assert 'token-secret-first' not in out
    # Non-image files cannot be posted through image upload.
    f=Path(tempfile.mkdtemp())/'secret.txt';f.write_text('not an image')
    try: pc.image(str(f));raise AssertionError('accepted text as image')
    except ValueError: pass
    sent=[]; approvals=[]; state={'enabled':True,'perm':'full'}
    conn={'id':'pc-test','connector_id':'pancake-thong-ke','label':'Pancake','perm':'full','enabled':True}
    ent={'conn':conn,'tool':'pancake_send_message','spec':{}}
    hub._rate_ok=lambda *a:True
    hub._nen_bat=lambda:False
    hub._chinh_sach_loai_viec=lambda:{}
    hub._audit_append=lambda r:None
    hub.mcp_store.list_connections=lambda:[{**conn,**state}]
    async def network(routes,name,args):sent.append(args);return '{"success":true}'
    hub.mcp_client.call_route=network
    async def deny(yc,timeout): approvals.append(yc);return 'tu_choi'
    hd.cho_quyet=deny
    args={'page':'123456789','conversation_id':'123_456','message':'Nội dung '+('rất dài '*80)}
    out=await hub._guard(ent,'pancake_send_message','full')(args)
    assert out.startswith('ERROR:') and not sent and approvals
    assert args['message'] in approvals[-1]['chi_tiet'], 'Full approved text must be visible'
    # A mutable caller cannot change the message after the review has begun.
    original=dict(args)
    async def approve(yc,timeout):args['message']='changed after review';return 'dong_y'
    hd.cho_quyet=approve
    out=await hub._guard(ent,'pancake_send_message','full')(args)
    assert len(sent)==1 and sent[-1]['message']==original['message']
    async def revoke(yc,timeout):state['enabled']=False;return 'dong_y'
    hd.cho_quyet=revoke
    out=await hub._guard(ent,'pancake_send_message','full')(args)
    assert out.startswith('ERROR:') and len(sent)==1
    for mode in ['suggest','auto']:
        out=await hub._guard(ent,'pancake_send_message',mode)(args)
        assert out.startswith('ERROR:') and len(sent)==1
    print('PASS: page isolation, pagination, API contract, secret redaction, image validation, approval, frozen arguments and revoked permissions')


if __name__=='__main__':asyncio.run(main())
