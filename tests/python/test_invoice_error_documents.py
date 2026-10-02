"""A tax gateway error page must not become a downloadable invoice."""
from _paths import ROOT, SERVER
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import routes.hoa_don as hd

ERROR = b"<!DOCTYPE html><html><head><title>Error</title></head><body>This page can't be displayed.</body></html>"


class TaxErrorDocuments(unittest.TestCase):
    def test_raw_error_writes_no_invoice_files(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'chứng từ'):
                hd.thd('invoice_xml').save_invoice_files(folder, 'invoice', ERROR, keep_zip=True)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_zipped_gateway_error_is_rejected_but_invoice_html_is_kept(self):
        for data, bad in ((ERROR, True), (b'<html><title>Invoice 30</title><body>Invoice</body></html>', False)):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as z:
                z.writestr('invoice.html', data)
            if bad:
                with self.assertRaises(ValueError):
                    hd.thd('invoice_xml').extract_zip(buf.getvalue())
            else:
                self.assertEqual(hd.thd('invoice_xml').extract_zip(buf.getvalue())['html'], data)

    def test_legacy_error_is_hidden_without_deleting_files_or_original(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(hd, 'goc_du_lieu', return_value=Path(folder)):
            root = Path(folder)
            (root / 'error.html').write_bytes(ERROR)
            (root / 'error.zip').write_bytes(ERROR)
            (root / 'error.pdf').write_bytes(b'%PDF-error-render')
            (root / 'original.pdf').write_bytes(b'%PDF-original')
            hd.ghi_kho('2222222222', 'purchase', {'invoice': {
                '_html_path':'error.html', '_zip_path':'error.zip', '_pdf_path':'error.pdf',
                '_goc_path':'original.pdf'}})
            inv = hd.doc_kho('2222222222','purchase')['invoice']
            self.assertNotIn('_pdf_path',inv)
            self.assertNotIn('_zip_path',inv)
            self.assertEqual(inv['_goc_path'],'original.pdf')
            self.assertTrue((root / 'error.pdf').exists())


if __name__ == '__main__':
    unittest.main()
