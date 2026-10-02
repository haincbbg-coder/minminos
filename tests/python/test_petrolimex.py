"""Public portal contract, Fkey selection and fail-closed invoice reconciliation."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'apps'/'tai-hoa-don'))
from thd.providers import petrolimex as P, ProviderError, manual_download_info
from thd import exporter
from thd.providers import bkav

XML='<HDon><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>K26AAA</KHHDon><SHDon>12</SHDon><MSTTCGP>0100684378</MSTTCGP></TTChung><NBan><MST>1234567890</MST><Ten>PETROLIMEX TEST</Ten></NBan><TTKhac><TTin><TTruong>MaTimKiem</TTruong><DLieu>not-the-lookup</DLieu></TTin><TTin><TTruong>Fkey</TTruong><DLieu>CODE*</DLieu></TTin></TTKhac></HDon>'
FORM='<input name="__RequestVerificationToken" value="state">'
READY='<a href="/SearchInvoicebycode/DownloadXml/?checkCode=abc++xyz">Tải</a>'

def res(text):
    return SimpleNamespace(status_code=200,text=text,content=text.encode(),json=lambda:{'str':text})

class PetrolimexTests(unittest.TestCase):
    def test_mapping_does_not_capture_other_vnpt_sellers(self):
        self.assertTrue(P.detect(XML,{}))
        self.assertFalse(P.detect(XML.replace('PETROLIMEX TEST','OTHER'),{}))
        info=manual_download_info(XML.encode())
        self.assertEqual(info['code'],'CODE*')
        self.assertTrue(info['url'].startswith(P.PORTAL))

    def run_lookup(self,xml=XML):
        session=MagicMock(); session.__enter__.return_value=session
        session.get.side_effect=[res(FORM),res('image'),res(xml)]
        session.post.side_effect=[res(READY),res('<html><head></head><body>Invoice</body></html>')]
        solver=MagicMock();solver.image.return_value='1234'
        def render(src,dst,browser):
            html=Path(src).read_text()
            self.assertIn("default-src 'none'",html)
            Path(dst).write_bytes(b'%PDF-fixture')
        with patch.object(P.C,'make_session',return_value=session),patch.object(exporter,'find_browser',return_value='browser'),patch.object(exporter,'html_to_pdf',side_effect=render):
            pdf=P.fetch_pdf(XML,{},lambda _:None,solver)
        return pdf,session

    def test_lookup_uses_fkey_and_preserves_portal_post_encoding(self):
        pdf,session=self.run_lookup()
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual(session.post.call_args_list[0].kwargs['data']['strFkey'],'CODE*')
        self.assertEqual(session.post.call_args_list[1].kwargs['data'],'checkCode=abc++xyz')

    def test_wrong_invoice_rejected_before_render(self):
        with self.assertRaisesRegex(ProviderError,'không khớp'):
            self.run_lookup(XML.replace('<SHDon>12','<SHDon>13'))

class BkavUuidTests(unittest.TestCase):
    def test_uuid_recovery_verifies_issuer_xml_before_pdf(self):
        xml=XML.replace('<HDon>','<HDon><DLHDon Id="f465cb70-251b-4754-a5fc-e979f2089b70"/>').replace('PETROLIMEX TEST','BKAV TEST')
        for source,ok in [(xml,True),(xml.replace('<SHDon>12','<SHDon>13'),False)]:
            session=MagicMock();session.__enter__.return_value=session
            session.get.return_value=res(FORM+'LinkDownXML')
            session.post.return_value=res(source)
            with patch.object(bkav.C,'make_session',return_value=session),patch.object(bkav,'_direct_invoice',return_value=b'%PDF-fixture') as download:
                if ok:
                    inv={}
                    self.assertEqual(bkav.fetch_pdf(xml,inv,lambda _:None),b'%PDF-fixture')
                    self.assertIn('InvoiceGUID=',inv['_manual_url'])
                else:
                    with self.assertRaises(ProviderError):bkav.fetch_pdf(xml,{},lambda _:None)
                    download.assert_not_called()

if __name__=='__main__':
    unittest.main()
