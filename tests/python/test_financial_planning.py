from _paths import ROOT
import json
import os
import subprocess
import tempfile
os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='minmin-plan-test-')
from fastapi import FastAPI
from fastapi.testclient import TestClient
import giay_phep
import routes.ket_noi_ngoai as knn

app=FastAPI();knn.register(app,ROOT/'dashboard')
plan=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./apps/financial-planning/web/engine.js').blank()))"],cwd=ROOT))
with TestClient(app) as tc:
    assert any(u['id']=='financial_planning' for u in tc.get('/ket-noi-ngoai').json()['ung_dung'])
    for path in ['/apps/financial-planning/','/apps/financial-planning/engine.js','/api/financial-planning','/api/financial-planning/history']:
        assert tc.get(path).status_code==403
    giay_phep.tao_cap_khoa()
    assert tc.get('/api/financial-planning').status_code==403
    knn.ghi_dong_y('chung')
    for name in ['index.html','style.css','engine.js','app.js']:
        assert tc.get('/apps/financial-planning/'+name).status_code==200
    assert tc.get('/apps/financial-planning/config.py').status_code==404
    assert tc.get('/api/financial-planning').json()['revision']==0
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':0}).json()['revision']==1
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':0}).status_code==409
    assert tc.get('/api/financial-planning/history/1').json()['plan']==plan
    plan['months'][3]['locked']=True
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':1}).status_code==200
    plan['months'][0]['fixed']=100
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':2}).status_code==400
    plan['months'][3]['locked']=False
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':2}).status_code==400
    plan['months'][0]['fixed']=0
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':2}).status_code==200
    plan['collectionLag']=1.2
    assert tc.put('/api/financial-planning',json={'plan':plan,'revision':3}).status_code==400
    assert tc.put('/api/financial-planning',content=b'x'*2_000_001).status_code==413
    assert tc.get('/api/financial-planning').json()['revision']==3
print('OK financial planning registration, license/terms, atomic storage, stale-write rejection, history, locked-period enforcement, validation')
