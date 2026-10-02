"""Missing-source states and issuer challenge/PDF contracts, without paid calls."""
from _paths import ROOT, SERVER
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
import routes.hoa_don as hd


class RecoveryTests(unittest.TestCase):
    def test_missing_original_is_not_always_a_failed_download(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(hd, 'goc_du_lieu', return_value=Path(folder)):
            Path(folder, 'a.xml').write_text('<HDon/>')
            Path(folder, 'a.pdf').write_bytes(b'%PDF-fixture')
            self.assertEqual(hd.tom_tat({})['goc_trang_thai'], 'no-xml')
            self.assertEqual(hd.tom_tat({'_xml_path':'a.xml'})['goc_trang_thai'], 'pending')
            self.assertEqual(hd.tom_tat({'_xml_path':'a.xml','_goc_loi':'captcha'})['goc_trang_thai'], 'failed')
            self.assertEqual(hd.tom_tat({'_goc_path':'a.pdf','_goc_loi':'old'})['goc_trang_thai'], 'done')
            info=hd.ma_tra_cuu_hd({})
            self.assertFalse(info['has_xml']); self.assertEqual(info['url'], '')
            self.assertIn('chưa tải XML', info['note'])
            info=hd.ma_tra_cuu_hd({'_gmail_lookup':{'link':'https://example.com/lookup','ma_tra_cuu':'TEST123'}})
            self.assertEqual(info['code'], 'TEST123'); self.assertEqual(info['url'], 'https://example.com/lookup')

    def test_smartsign_code_is_read_from_xml_not_invoice_number(self):
        xml=b'<HDon><MSTTCGP>0309612872</MSTTCGP><SHDon>999</SHDon><TTKhac><TTin><TTruong>Matracuu</TTruong><DLieu>DEMO123</DLieu></TTin></TTKhac></HDon>'
        info=hd.thd('providers').manual_download_info(xml)
        self.assertEqual(info['code'], 'DEMO123')
        self.assertTrue(info['url'].startswith('https://tracuuhd.smartsign.com.vn'))

    def test_slider_coordinates_and_bounds(self):
        mod=hd.thd('captcha_solver')
        for provider,solution in [('2captcha',{'coordinates':[{'x':125,'y':50}]}),('omocaptcha',{'end':{'x':125,'y':50}})]:
            with patch.object(mod, '_solve', return_value=solution) as solve:
                solver=mod.Solver(provider=provider,api_key='fake')
                self.assertEqual(solver.slider(b'bg',b'piece','vinvoice.viettel.vn',300,150,50),100)
                self.assertEqual(solve.call_args.args[2]['type'], 'CoordinatesTask' if provider=='2captcha' else 'SliderAllWebTask')
            with patch.object(mod, '_solve', return_value={'end':{'x':999}}):
                with self.assertRaises(mod.CaptchaError):
                    mod.Solver(provider='omocaptcha',api_key='fake').slider(b'bg',b'p','example.com',300,150,50)

    def test_unknown_issuer_retains_explicit_lookup_code_without_inventing_url(self):
        mod=hd.thd('providers')
        for field in ('MaTraCuu','MTCuu','QuanLy_SoBaoMat','MaTimKiem'):
            xml=f'<HDon><SHDon>999</SHDon><TTKhac><TTin><TTruong>{field}</TTruong><DLieu>LOOKUP</DLieu></TTin></TTKhac></HDon>'.encode()
            info=mod.manual_download_info(xml)
            self.assertEqual(info['code'],'LOOKUP'); self.assertEqual(info['url'],'')
        self.assertIsNone(mod.manual_download_info(b'<HDon><SHDon>999</SHDon></HDon>'))

    def test_viettel_verified_token_is_used_for_pdf_and_rejection_stops(self):
        mod=hd.thd('providers.viettel')
        def image(size):
            out=io.BytesIO(); Image.new('RGB',size).save(out,format='PNG')
            return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
        challenge={'backgroundUrl':image((300,150)), 'puzzleUrl':image((50,50)), 'token':'challenge'}
        session=Mock(); session.get.return_value.json.return_value=challenge
        verify=Mock(); verify.json.return_value={'success':True,'token':'verified'}
        pdf=Mock(status_code=200,content=b'%PDF-fixture')
        session.post.side_effect=[verify,pdf]
        solver=Mock(); solver.slider.return_value=100
        with patch.object(mod.C,'make_session',return_value=session), patch.object(mod,'_secret',return_value='DEMO'), patch.object(mod.C,'seller_mst',return_value='1234567890'):
            self.assertEqual(mod.fetch_pdf('<HDon/>',{},lambda s:None,solver), b'%PDF-fixture')
            self.assertEqual(session.post.call_args.kwargs['json']['recaptcha'],'verified')
            session.post.reset_mock(); verify.json.return_value={'success':False}
            session.post.side_effect=[verify]
            with self.assertRaises(hd.thd('providers').ProviderError): mod.fetch_pdf('<HDon/>',{},lambda s:None,solver)
            self.assertEqual(session.post.call_count,1)

    def test_htinvoice_uses_lookup_token_and_real_embedded_pdf(self):
        mod=hd.thd('providers.htinvoice')
        page=Mock(text="'sitekey': 'site-key'")
        view=Mock(content=b'<html>',text="const pdfBase64 = '"+base64.b64encode(b'%PDF-fixture').decode()+"';")
        session=Mock(); session.get.side_effect=[page,view]; session.post.return_value.json.return_value='invoice-token'
        solver=Mock(); solver.recaptcha_v2.return_value='captcha-token'
        with patch.object(mod.C,'make_session',return_value=session):
            result=mod.fetch_pdf('<HDon/>',{'_ma_tra_cuu':'DEMO'},lambda s:None,solver)
            self.assertEqual(result,b'%PDF-fixture')
            self.assertEqual(session.post.call_args.kwargs['json'],{'MaTraCuu':'DEMO','recaptchaResponse':'captcha-token'})
            self.assertEqual(session.get.call_args.kwargs['params'],{'token':'invoice-token'})


if __name__ == '__main__': unittest.main()
