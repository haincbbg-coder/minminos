"""Offline regressions for issuer lookup, CAPTCHA and original-file identity checks."""
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps' / 'tai-hoa-don'))
from thd.providers import ProviderError, vinhoadon as V, efy as E

XML = '<HDon><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TNL</KHHDon><SHDon>60</SHDon></TTChung><NBan><MST>0319388041</MST></NBan></HDon>'
PDF = b'%PDF-original'


def response(obj=None, text='', content=b''):
    r = MagicMock(status_code=200, text=text, content=content)
    r.json.return_value = obj
    r.__enter__.return_value = r
    r.iter_content.return_value = [content]
    return r


def vin_result(xml=XML, pdf=PDF):
    return response({'result': {'status': 1,
        'fileData': {'fileData': base64.b64encode(xml.encode()).decode()},
        'filePdf': {'fileData': base64.b64encode(pdf).decode()}}})


class VinTests(unittest.TestCase):
    def download(self, found, rejection=False):
        s = MagicMock()
        s.__enter__.return_value = s
        cap = response({'result': {'key': 'k', 'image': 'data:image/png;base64,aW1n'}})
        s.post.side_effect = ([cap, response({'result': {'status': 2}})] if rejection else []) + [cap, found]
        solver = MagicMock()
        solver.image.return_value = '1234'
        with patch.object(V.C, 'make_session', return_value=s):
            pdf = V.fetch_pdf(XML, {'_ma_tra_cuu': 'secret'}, lambda _: None, solver)
        return pdf, s, solver

    def test_valid_and_retry(self):
        pdf, s, solver = self.download(vin_result(), True)
        self.assertEqual(pdf, PDF)
        self.assertEqual(solver.image.call_count, 2)
        self.assertTrue(s.verify.endswith('ca.pem'))
        self.assertEqual(s.post.call_args.kwargs['json']['doanhNghiep_MST'], '0319388041')

    def test_wrong_invoice(self):
        with self.assertRaisesRegex(ProviderError, 'không khớp'):
            self.download(vin_result(XML.replace('>60<', '>61<')))

    def test_html_rejected(self):
        with self.assertRaisesRegex(ProviderError, 'chưa có PDF'):
            self.download(vin_result(pdf=b'<html>error</html>'))


class EfyTests(unittest.TestCase):
    def download(self, xml=XML, pdf=PDF, retry=False):
        s = MagicMock()
        s.__enter__.return_value = s
        s.get.return_value = response(text="var site_key_recaptcha = 'public-site-key';")
        found = response({'status': 'success', 'data': {
            'attach_file': [{'code': 'HD01', 'name': 'invoice.xml', 'link': 'https://ihoadon.vn/file.xml'}],
            'pdf_file': {'link': 'https://ihoadon.vn/file.pdf'}}})
        s.post.side_effect = ([response({'status': 'error', 'message': 'Mã xác minh không đúng'})] if retry else []) + [found]
        solver = MagicMock()
        solver.recaptcha_v2.return_value = 'token'
        with patch.object(E.C, 'make_session', return_value=s), patch.object(E, '_download', side_effect=[xml.encode(), pdf]):
            result = E.fetch_pdf(XML, {'_ma_tra_cuu': 'lookup-code'}, lambda _: None, solver)
        return result, s, solver

    def test_efy_calls_recaptcha_and_downloads_supplier_files(self):
        data, s, solver = self.download()
        self.assertEqual(data, PDF)
        solver.recaptcha_v2.assert_called_once_with('public-site-key', E.LOOKUP_PAGE)
        self.assertEqual(s.post.call_args.kwargs['json']['gRecaptchaResponse'], 'token')
        self.assertEqual(s.post.call_args.kwargs['json']['certificate_id'], '60')
        self.assertIn('shd=60&mtc=lookup-code', E.lookup_url('60', 'lookup-code'))

    def test_efy_retry_token(self):
        _, _, solver = self.download(retry=True)
        self.assertEqual(solver.recaptcha_v2.call_count, 2)

    def test_efy_wrong_invoice(self):
        with self.assertRaisesRegex(ProviderError, 'không khớp'):
            self.download(xml=XML.replace('>60<', '>61<'))

    def test_efy_html_rejected(self):
        with self.assertRaisesRegex(ProviderError, 'chưa trả về PDF'):
            self.download(pdf=b'<html>error</html>')

    def test_download_blocks_private_target_before_network(self):
        s = MagicMock()
        with self.assertRaises(ProviderError):
            E._download(s, 'https://127.0.0.1/file.pdf')
        s.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
