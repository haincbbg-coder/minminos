"""Native Business Finance must keep license/terms gates for every asset."""
from _paths import ROOT
import os
import tempfile
from pathlib import Path
os.environ['JAVIS_STATE_DIR'] = tempfile.mkdtemp(prefix='minmin-finance-test-')
import giay_phep
from fastapi import FastAPI
from fastapi.testclient import TestClient
import routes.ket_noi_ngoai as knn
app=FastAPI();knn.register(app,ROOT/'dashboard')
with TestClient(app) as tc:
    assert any(u['id']=='business_finance' and u['duong_dan']=='/apps/business-finance/#calculator' for u in tc.get('/ket-noi-ngoai').json()['ung_dung'])
    for path in ['/apps/business-finance/','/apps/business-finance/profit.js','/apps/business-finance/numbers.js']:
        assert tc.get(path).status_code==403
    # Isolated temporary publisher credentials, never stored in source.
    giay_phep.tao_cap_khoa()
    assert tc.get('/apps/business-finance/').status_code==403
    knn.ghi_dong_y('chung')
    for filename in ['index.html','profit.js','business-engine.js','calculator.js','business.js','numbers.js','readability.css','theme-bridge.css','audit-ui.js','fee-data.js','fee-catalog.js','fee-presets.js','fee-presets.css']:
        response=tc.get('/apps/business-finance/'+filename)
        assert response.status_code==200, filename
        assert response.headers.get('cache-control')=='no-cache'
    assert 'data-mm-app="business-finance"' in tc.get('/apps/business-finance/').text
    for filename in ['VERSION','config.py','../giay_phep.py','missing.js','khoa-rieng.pem']:
        assert tc.get('/apps/business-finance/'+filename).status_code in (404,307)
    assert tc.get('/apps/business-finance',follow_redirects=False).status_code==307
print('OK: Business Finance registration, license/terms, asset allowlist and native theme')
