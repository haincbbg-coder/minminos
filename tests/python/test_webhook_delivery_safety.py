"""Ambiguous delivery must not resend a customer's action without an idempotent receiver."""
from _paths import ROOT, SERVER
import asyncio, json, os, tempfile
os.environ['JAVIS_STATE_DIR']=tempfile.mkdtemp(prefix='wh-safe-')
import webhook_su_kien as sk
import webhook_chay as ch


async def main():
    a={'id':'receiver','loai':'chuyen_tiep','url':'https://example.com/receive'}
    assert ch.chuan_hanh_dong([a])[0]['lap_an_toan'] is False
    async def good_url(url): return ''
    async def timeout(*args): raise TimeoutError('unknown remote outcome')
    worker=ch.BoChay(ch.ChayDeps(lay_hook=lambda _:None,gui_http=timeout,kiem_dia_chi=good_url))
    event={'id':'e1','than':b'{}','ctype':'application/json'}
    try: await worker._chuyen_tiep(a,event);raise AssertionError('must block')
    except ch.LoiHan: pass
    try: await worker._chuyen_tiep({**a,'lap_an_toan':True},event);raise AssertionError('must retry')
    except ch.LoiTam: pass
    async def overload(*args): return 429,{'Retry-After':'90'}
    worker.deps.gui_http=overload
    try: await worker._chuyen_tiep(a,event);raise AssertionError('429 must retry')
    except ch.LoiTam as e: assert e.cho>=90
    async def server_error(*args): return 500,{}
    worker.deps.gui_http=server_error
    try: await worker._chuyen_tiep(a,event);raise AssertionError('500 is ambiguous')
    except ch.LoiHan: pass
    d={'shop_id':42,'id':123,'status':0,'updated_at':'one'}
    body=lambda x:json.dumps(x).encode()
    key=sk.khoa_giao({},body(d),trung_theo_don=True)
    assert key==sk.khoa_giao({},body({**d,'updated_at':'two'}),trung_theo_don=True)
    assert key!=sk.khoa_giao({},body({**d,'status':1}),trung_theo_don=True)
    assert key!=sk.khoa_giao({},body({**d,'shop_id':43}),trung_theo_don=True)
    assert sk.khoa_giao({},body({'x':1}),trung_theo_don=True)!=sk.khoa_giao({},body({'x':2}),trung_theo_don=True)
    assert sk.khoa_giao({},body(d))!=sk.khoa_giao({},body({**d,'updated_at':'two'}))
    print('PASS: ambiguous transport/500 blocked, explicit idempotent retry, Retry-After, order/shop/status keys and opt-in behavior')


if __name__=='__main__':asyncio.run(main())
