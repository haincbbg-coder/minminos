"""CyberBill downloads must verify issuer XML before requesting the original PDF."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps' / 'tai-hoa-don'))
from thd.providers import ProviderError, cyberbill as C, detect

XML = '<HDon><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TTC</KHHDon><SHDon>121</SHDon><MSTTCGP>0105232093</MSTTCGP></TTChung><NBan><MST>3702825688</MST></NBan></HDon>'
PDF = b'%PDF-original'


def result(obj):
    r = Mock(status_code=200)
    r.json.return_value = {'result': obj}
    return r


def file_response(data):
    r = Mock(status_code=200)
    r.iter_content.return_value = [data]
    return r


class CyberBillTests(unittest.TestCase):
    def download(self, xml=XML, pdf=PDF, retry=False):
        s = MagicMock()
        s.__enter__.return_value = s
        cap = result({'key': 'challenge', 'image': 'data:image/png;base64,aW1n'})
        found = result({'status': 1, 'key': 'download-key', 'fileData': {'fileToken': 'xml-token', 'fileName': 'original.xml'}})
        s.post.side_effect = ([cap, result({'status': 2})] if retry else []) + [cap, found, result({'fileToken': 'pdf-token', 'fileName': 'a&b.pdf'})]
        s.get.side_effect = [file_response(xml.encode()), file_response(pdf)]
        solver = Mock()
        solver.image.return_value = '1234'
        with patch.object(C.C, 'make_session', return_value=s):
            data = C.fetch_pdf(XML, {'_ma_tra_cuu': 'code'}, lambda _: None, solver)
        return data, s, solver

    def test_detect(self):
        self.assertIs(detect(XML.encode()), C)

    def test_original_and_captcha_retry(self):
        data, session, solver = self.download(retry=True)
        self.assertEqual(data, PDF)
        self.assertEqual(solver.image.call_count, 2)
        self.assertEqual(session.post.call_args.args[0], C.API + 'DownloadPdf')
        self.assertEqual(session.post.call_args.kwargs['json']['key'], 'download-key')
        self.assertIn('a%26b.pdf', session.get.call_args.args[0])
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_wrong_invoice_stops_pdf_download(self):
        with self.assertRaisesRegex(ProviderError, 'không khớp'):
            self.download(xml=XML.replace('>121<', '>122<'))

    def test_html_not_saved_as_pdf(self):
        with self.assertRaisesRegex(ProviderError, 'chưa có PDF'):
            self.download(pdf=b'<html>error</html>')

    def test_response_closed_on_size_limit(self):
        response = file_response(b'12345')
        session = Mock()
        session.get.return_value = response
        with patch.object(C, 'MAX_FILE', 4), self.assertRaisesRegex(ProviderError, 'giới hạn'):
            C._file(session, {'fileToken': 'token'})
        response.close.assert_called_once()

    def test_no_download_without_token(self):
        session = Mock()
        with self.assertRaises(ProviderError):
            C._file(session, {'fileName': 'x'})
        session.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
