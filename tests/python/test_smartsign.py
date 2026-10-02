"""Exercise SmartSign's session, CAPTCHA retries and invoice identity checks offline."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "tai-hoa-don"))
from thd.providers import ProviderError, smartsign as S

XML = '<HDon><DLHDon><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TMH</KHHDon><SHDon>16</SHDon></TTChung><NDHDon><NBan><MST>0318389331</MST></NBan></NDHDon></DLHDon></HDon>'
FORM = '<input type="hidden" name="__VIEWSTATE" value="state"><img id="ContentPlaceHolder1_Image1" src="Pages/CImage.aspx">'
READY = '<input type="hidden" name="__VIEWSTATE" value="ready">' + ''.join(
    f'<input type="submit" name="{S.PREFIX}ButtonDownLoad{kind}" value="{kind}">'
    for kind in ('XML', 'PDF'))


def response(text='', content=None, status=200):
    return SimpleNamespace(text=text, content=content if content is not None else text.encode(), status_code=status)


class SmartSignTests(unittest.TestCase):
    def run_download(self, posts):
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.side_effect = [response(FORM)] + [response(content=b'image')] * 3
        session.post.side_effect = posts
        solver = MagicMock()
        solver.image.return_value = 'answer'
        with patch.object(S.C, 'make_session', return_value=session):
            data = S.fetch_pdf(XML, {'_ma_tra_cuu': 'lookup'}, lambda _: None, solver)
        return data, session, solver

    def test_download_keeps_session_and_validates_supplier_xml(self):
        data, session, solver = self.run_download([
            response(READY), response(XML), response(content=b'%PDF-original')])
        self.assertEqual(data, b'%PDF-original')
        lookup = session.post.call_args_list[0].kwargs['data']
        self.assertEqual(lookup['__VIEWSTATE'], 'state')
        self.assertEqual(lookup['Action'], 'SHOW_INVOICE')
        self.assertEqual(lookup[S.PREFIX + 'txtCapcha'], 'answer')
        self.assertEqual(session.post.call_args_list[2].kwargs['data']['__VIEWSTATE'], 'ready')
        solver.image.assert_called_once_with(b'image')

    def test_wrong_invoice_is_rejected(self):
        with self.assertRaisesRegex(ProviderError, 'không khớp'):
            self.run_download([response(READY), response(XML.replace('<SHDon>16', '<SHDon>17'))])

    def test_html_instead_of_pdf_is_rejected(self):
        with self.assertRaisesRegex(ProviderError, 'chưa trả về PDF'):
            self.run_download([response(READY), response(XML), response('<html>Error</html>')])

    def test_captcha_retry_uses_new_page_state(self):
        data, session, solver = self.run_download([
            response('Captcha không đúng' + FORM.replace('value="state"', 'value="retry"')),
            response(READY), response(XML), response(content=b'%PDF-original')])
        self.assertEqual(solver.image.call_count, 2)
        self.assertEqual(session.post.call_args_list[1].kwargs['data']['__VIEWSTATE'], 'retry')

    def test_captcha_retries_are_bounded(self):
        with self.assertRaisesRegex(ProviderError, 'sau 3 lần'):
            self.run_download([response('Captcha không đúng' + FORM)] * 3)


if __name__ == '__main__':
    unittest.main()
