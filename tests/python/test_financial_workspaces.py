from _paths import ROOT
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='minmin-workspaces-test-')
from fastapi import FastAPI
from fastapi.testclient import TestClient
import giay_phep
import routes.ket_noi_ngoai as knn
import financial_pos as pos
import financial_workspaces as store

p=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./apps/financial-planning/web/engine.js').blank()))"],cwd=ROOT))
# A real legacy database must migrate its snapshots exactly once.
folder=Path(giay_phep.STATE_DIR)/'financial-planning';folder.mkdir(parents=True)
with sqlite3.connect(folder/'plans.sqlite3') as c:
    c.execute('CREATE TABLE versions(revision INTEGER PRIMARY KEY,saved_at TEXT,plan TEXT)')
    c.execute('INSERT INTO versions VALUES (1,?,?)',('2026-10-01',json.dumps(p)))
app=FastAPI();knn.register(app,ROOT/'dashboard')
with TestClient(app) as tc:
    assert tc.get('/api/financial-planning/workspaces').status_code==403
    assert tc.get('/api/financial-planning/pos/sources').status_code==403
    giay_phep.tao_cap_khoa();knn.ghi_dong_y('chung')
    assert tc.get('/api/financial-planning').json()['revision']==1
    assert len(tc.get('/api/financial-planning/history').json()['versions'])==1
    for asset in ['simulator.js','workspaces.js','planning-extra.css']:
        assert tc.get('/apps/financial-planning/'+asset).status_code==200
    w=tc.post('/api/financial-planning/workspaces',json={'name':'PA2','company':'Cty B','store':'Shop B','mode':'pos','connectionId':'source-b','shopId':'shop-b','copyFrom':'default'}).json()['workspace']
    key=w['id'];q='?workspace='+key
    assert tc.get('/api/financial-planning'+q).json()['revision']==1
    p['openingCash']=123
    assert tc.put('/api/financial-planning'+q,json={'plan':p,'revision':1,'workspaceRevision':0}).json()['revision']==2
    assert tc.get('/api/financial-planning').json()['plan']['openingCash']==0
    assert tc.get('/api/financial-planning'+q).json()['plan']['openingCash']==123
    assert tc.get('/api/financial-planning?workspace=not-real').status_code==404
    assert tc.get('/api/financial-planning/history/2?workspace=default').status_code==404
    assert tc.put('/api/financial-planning/workspaces/'+key,json={**w,'store':'Shop C'}).status_code==200
    assert tc.put('/api/financial-planning'+q,json={'plan':p,'revision':2,'workspaceRevision':0}).status_code==409
    assert tc.put('/api/financial-planning/workspaces/'+key,json=w).status_code==409
    calls=[]
    async def fixture_preview(connection,shop,page):
        calls.append((connection,shop,page));return {'products':[],'shop':{'id':shop,'name':'Fixture'}}
    original=pos.preview;pos.preview=fixture_preview
    try:
        res=tc.post('/api/financial-planning/pos/preview'+q,json={'page':2,'connectionId':'source-attack','shopId':'shop-attack'})
        assert res.status_code==200
        assert calls==[('source-b','shop-b',2)] # request cannot replace the saved source
        assert tc.post('/api/financial-planning/pos/preview',json={}).status_code==400
    finally:pos.preview=original
    # Copy never changes the original or its locks.
    p['months'][0]['locked']=True
    assert tc.put('/api/financial-planning'+q,json={'plan':p,'revision':2,'workspaceRevision':1}).status_code==200
    copied=tc.post('/api/financial-planning/workspaces',json={'name':'copy','copyFrom':key}).json()['workspace']['id']
    assert not tc.get('/api/financial-planning?workspace='+copied).json()['plan']['months'][0]['locked']
    assert tc.get('/api/financial-planning'+q).json()['plan']['months'][0]['locked']
rows=[{'id':'p1','name':'Áo','variations':[{'id':'v1','custom_id':'S-ĐỎ','retail_price':500000,'remain_quantity':20},{'id':'v2','custom_id':'M-ĐỎ','retail_price':500000,'cost_price':300000}]}]
products,skipped=pos.normalize_products(rows,'c1','s1')
assert len(products)==2 and products[0]['cost'] is None and products[1]['stock'] is None
assert products[0]['id']!=pos.normalize_products(rows,'c2','s1')[0][0]['id']
assert products[0]['id']!=pos.normalize_products(rows,'c1','s2')[0][0]['id']
assert len(pos.normalize_products(rows+rows,'c1','s1')[0])==2
try:pos.args_for({'properties':{'action':{'enum':['create']}}},'s1');raise AssertionError('must reject write action')
except ValueError:pass
print('OK workspaces: legacy migration, separate companies/revisions/history, cloned locks, source binding, stale configuration, POS variant identities and missing values')

import asyncio
from unittest.mock import patch
seen=[]
specs=[{'name':'pos_shop','fn':'p__pos_shop','schema':{'properties':{'action':{'enum':['list','create']}}}}]
routes={'p__pos_shop':{'tool':'pos_shop','conn':{'id':'c1','connector_id':'pancake-pos','perm':'full'}}}
def guarded(entry,fn,mode):
    seen.append((entry['conn']['perm'],mode))
    async def call(args):
        assert args=={'action':'list'}
        return {'shops':[]}
    return call
with patch('mcp_hub._guard',guarded):
    assert asyncio.run(pos.read_tool(specs,routes,'pos_shop'))=={'shops':[]}
assert seen==[('readonly','suggest')]
assert routes['p__pos_shop']['conn']['perm']=='full'
print('OK POS bridge uses the existing hub read-only ceiling even for a full-permission connection')

# Live POS exposes only the action enum initially; list is TAGS, not products.
live_specs=[
 {'name':'pos_describe','fn':'p__describe','schema':{}},
 {'name':'pos_product','fn':'p__products','schema':{'properties':{'action':{'enum':['list','list_products_variations'],'description':'- list: Product tags'}}}}
]
live_routes={s['fn']:{'tool':s['name'],'conn':{'id':'c1','connector_id':'pancake-pos','perm':'full'}} for s in live_specs}
live_calls=[]
def live_guard(entry,fn,mode):
    assert entry['conn']['perm']=='readonly' and mode=='suggest'
    async def call(args):
        live_calls.append((entry['tool'],args))
        if entry['tool']=='pos_describe':
            assert args=={'tool':'pos_product','action':'list_products_variations'}
            return {'inputSchema':{'type':'object','properties':{'shop_id':{'type':'integer'},'page':{'type':'integer'},'page_size':{'type':'integer','maximum':100}},'required':['shop_id']}}
        assert args=={'action':'list_products_variations','shop_id':123,'page':2,'page_size':50}
        return {'data':[]}
    return call
with patch('mcp_hub._guard',live_guard):
    assert asyncio.run(pos.read_tool(live_specs,live_routes,'pos_product','123',2))=={'data':[]}
assert len(live_calls)==2
flat=[{'id':'v1','product_id':'p1','product':{'name':'Áo'},'custom_id':'S-ĐỎ','retail_price':500000}]
assert pos.normalize_products(flat,'c1','s1')[0][0]['id']==products[0]['id']
assert pos.rows({'data':{'variations':flat}},'products')==flat
assert pos.rows('Shop information\n```json\n{"shops":[{"id":123,"name":"Shop"}]}\n```','shops')==[{'id':123,'name':'Shop'}]
assert pos.described_schema('Action input\n```json\n{"inputSchema":{"properties":{"shop_id":{"type":"integer"}}}}\n```')['properties']['shop_id']['type']=='integer'
print('OK live POS contract expansion, product action rather than tags, pagination and flat variation identity')
