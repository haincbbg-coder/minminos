from _paths import ROOT, SERVER
import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
import routes.hoa_don as hd
from routes.invoice_recovery import unpack, hints, pdf_qr

A = '/apps/tai-hoa-don/api/tim-ban-goc'
XML = '''<HDon><DLHDon><TTChung><KHMSHDon>2</KHMSHDon><KHHDon>C26MYY</KHHDon><SHDon>168</SHDon><NLap>2026-10-02</NLap><MSTTCGP>0106026495-001</MSTTCGP></TTChung><NDHDon><NBan><MST>001203013937</MST><Ten>PHƯƠNG HUY</Ten></NBan><NMua><MST>2401063265</MST><Ten>HALIMI</Ten></NMua><TToan><TgTTTBSo>30000000</TgTTTBSo></TToan></NDHDon><TTKhac><TTin><TTruong>Mã tra cứu</TTruong><DLieu>B0E189FA72670372</DLieu></TTin></TTKhac></DLHDon></HDon>'''.encode()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for p in (patch.object(hd,'goc_du_lieu',return_value=self.root),patch.object(hd,'ly_do_chan',return_value=None)):
            p.start(); self.addCleanup(p.stop)
        hd.ghi_cau_hinh({'doanh_nghiep':{'2401063265':{}}})
        app=FastAPI();hd.register(app);self.c=TestClient(app);self.addCleanup(self.c.close)
        self.jobs=[]
        def immediate(kind, title, callback):
            v=hd.Viec(kind,title); v.ket_qua=callback(v);self.jobs.append(v);return v
        p=patch.object(hd,'chay_viec',side_effect=immediate);p.start();self.addCleanup(p.stop)

    def intake(self,data=XML,name='invoice.xml'):
        r=self.c.post(A+'/nhap',json={'name':name,'data':base64.b64encode(data).decode()})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()['rows'][0]

    def test_xml_import_identifies_branch_and_lookup_without_marking_original(self):
        row=self.intake()
        self.assertEqual(row['code'],'B0E189FA72670372')
        self.assertEqual(row['provider'],'M-Invoice (CN TP.HCM)')
        self.assertIn('tracuuhoadon.minvoice.com.vn',row['url'])
        inv=hd.doc_kho(row['mst'],'purchase')[row['key']]
        self.assertNotIn('_goc_path',inv)
        self.assertTrue(hd.tuyet_doi(inv['_xml_path']))
        self.assertEqual(len(self.c.get(A).json()['rows']),1)
        self.intake();self.assertEqual(len(self.c.get(A).json()['rows']),1)

    def test_wrong_buyer_and_invalid_xml_stay_unbound(self):
        row=self.intake(XML.replace(b'2401063265',b'9999999999'))
        self.assertNotIn('key',row)
        self.assertEqual(row['status'],'need-source')
        row=self.intake(b'<!DOCTYPE x [<!ENTITY a "foo">]><HDon/>','bad.xml')
        self.assertNotIn('key',row)

    def test_pdf_evidence_never_becomes_original(self):
        w=PdfWriter();w.add_blank_page(width=100,height=100);buf=io.BytesIO();w.write(buf)
        row=self.intake(buf.getvalue(),'trong-dong.pdf')
        self.assertEqual(row['status'],'need-source')
        self.assertNotIn('download',row)

    def test_zip_paths_are_not_extracted_and_nested_archives_are_rejected(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('../../invoice.xml',XML)
        self.assertEqual(unpack('a.zip',b.getvalue())[0][0],'invoice.xml')
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('nested.zip',b'PK')
        with self.assertRaises(ValueError):unpack('a.zip',b.getvalue())

    def test_gmail_recovery_does_not_require_tax_login_and_verifies_pdf(self):
        row=self.intake();self.root.joinpath('mail.pdf').write_bytes(b'%PDF-fixture')
        hd._ghi_json(hd._gmail_kho_path(),{'mail':{'xml':hd.doc_kho(row['mst'],'purchase')[row['key']]['_xml_path'],'pdf':'mail.pdf'}})
        reader=type('Reader',(),{'pages':[type('Page',(),{'extract_text':lambda self:'verified invoice'})()]})
        with patch('pypdf.PdfReader',return_value=reader),patch.object(hd.thd('invoice_identity'),'matches',return_value=True),patch.object(hd,'_can_dang_nhap',side_effect=AssertionError('No tax login')):
            r=self.c.post(A+'/chay',json={'ids':[row['id']]})
        self.assertEqual(r.status_code,200,r.text)
        result=self.c.get(A).json()['rows'][0]
        self.assertEqual(result['status'],'done');self.assertEqual(result['source'],'Gmail')
        self.assertTrue(hd.tuyet_doi(hd.doc_kho(row['mst'],'purchase')[row['key']]['_goc_path']))

    def test_mismatched_provider_pdf_is_not_saved(self):
        row=self.intake()
        reader=type('Reader',(),{'pages':[type('Page',(),{'extract_text':lambda self:'wrong buyer'})()]})
        with patch('pypdf.PdfReader',return_value=reader),patch.object(hd.thd('providers'),'fetch_original_pdf',return_value=('Test',b'%PDF-wrong')):
            r=self.c.post(A+'/chay',json={'ids':[row['id']]})
        self.assertEqual(r.status_code,200,r.text)
        self.assertNotIn('_goc_path',hd.doc_kho(row['mst'],'purchase')[row['key']])
        self.assertEqual(self.c.get(A).json()['rows'][0]['status'],'need-source')

    def test_empty_scope_and_private_url_rejected(self):
        self.assertEqual(self.c.post(A+'/chay',json={'ids':[]}).status_code,400)
        row=self.intake()
        r=self.c.post(A+'/nguon',json={'id':row['id'],'url':'https://127.0.0.1/admin'})
        self.assertEqual(r.status_code,400)

    def test_tracking_pixel_is_not_lookup_and_code_keeps_case(self):
        self.assertEqual(hints('Mã tra cứu: AbCd1234')[0],'AbCd1234')
        text='<img src="https://email.kiemtrahoadon.vn/o/beacon"><a href="https://tracuuhoadon.minvoice.com.vn/">Tra cứu</a>'
        self.assertEqual(hd.thd('gmail_scan')._find_lookup_link(text),'https://tracuuhoadon.minvoice.com.vn/')

    def test_embedded_qr_retains_lookup_link_and_code(self):
        import zxingcpp
        from PIL import Image
        from types import SimpleNamespace
        url='https://tracuu.example.com/invoice?code=AbCd1234'
        qr=zxingcpp.create_barcode(url,zxingcpp.BarcodeFormat.QRCode)
        image=Image.fromarray(qr.to_image(scale=4))
        values=pdf_qr(SimpleNamespace(images=[SimpleNamespace(image=image)]))
        self.assertEqual(values,[url])
        self.assertEqual(hints(values[0]),('AbCd1234',url))


if __name__=='__main__':unittest.main()
