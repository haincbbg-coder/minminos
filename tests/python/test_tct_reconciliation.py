"""No network: PDF identity, cross-company ambiguity and selected TCT downloads."""
from _paths import ROOT, SERVER  # noqa
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import routes.hoa_don as hd

identity = hd.thd('invoice_identity')
BUYER = '1234567890'
SELLER = '0987654321'
TEXT = identity.normalized('''HÓA ĐƠN
Mẫu số - Ký hiệu (Serial No.): 1C26TYY
Số (Invoice No.): 0000123
Đơn vị bán (Seller): Công ty A
MST (Tax Code): 0987654321
Người mua (Buyer): Công ty B
MST (Tax Code): 1234567890
''')


class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = patch.object(hd, 'goc_du_lieu', return_value=self.root)
        p.start(); self.addCleanup(p.stop)
        hd.ghi_cau_hinh({'doanh_nghiep': {BUYER: {}}})
        (self.root/'original.pdf').write_bytes(b'%PDF-1.7\nfixture')
        self.inv = {'nbmst': SELLER, 'khmshdon': 1, 'khhdon': 'C26TYY', 'shdon': 123,
                    '_loai': 'purchase', 'tdlap': '2026-09-01'}
        self.ban = {'pdf': 'original.pdf', 'so': 'wrong-email-number', 'ma_tra_cuu': 'TESTCODE',
                    'nha_cung_cap': 'bkav', 'link': 'https://tchd.ehoadon.vn/TCHD?MTC=TESTCODE'}

    def test_pdf_requires_complete_identity(self):
        self.assertTrue(identity.matches(TEXT, self.inv, BUYER))
        for change in ({'nbmst': '9999999999'}, {'khhdon': 'C25TYY'}, {'shdon': 12}):
            self.assertFalse(identity.matches(TEXT, dict(self.inv, **change), BUYER))
        self.assertFalse(identity.matches(TEXT, self.inv, '9999999999'))
        self.assertFalse(identity.matches(TEXT.replace('0000123', '00001234'), self.inv, BUYER))
        self.assertFalse(identity.matches(TEXT + '\n', dict(self.inv, khhdon='C26TAA'), BUYER))

    def test_fast_spaced_ids_and_value_before_label(self):
        text = identity.normalized('1C26TYY\n123\nKý hiệu\n(Serial No.)\n:\nSố (Invoice No.):\nĐơn vị bán:\nMST: 0 9 8 7 6 5 4 3 2 1\nNgười mua:\nMST: 1 2 3 4 5 6 7 8 9 0\n')
        self.assertTrue(identity.matches(text, self.inv, BUYER))
        self.assertEqual(identity.numbers(text), {'123'})

    def test_bkav_header_serialized_after_footer(self):
        lines = TEXT.splitlines()
        text = '\n'.join(lines[3:] + lines[:3])
        self.assertEqual(identity.numbers(text), {'123'})
        self.assertTrue(identity.matches(text, self.inv, BUYER))
        self.assertFalse(identity.matches(text + '\nso (invoice no.): 456', self.inv, BUYER))

    def test_unique_pdf_only_match_ignores_email_guess(self):
        with patch.object(identity, 'read_pdf', return_value=TEXT):
            self.assertEqual(hd.tim_hd_gmail(None, self.ban, {BUYER: {'one': self.inv}}), (BUYER, 'one'))
            self.assertIsNone(hd.tim_hd_gmail(None, self.ban, {BUYER: {'one': self.inv, 'two': self.inv}}))
            self.assertIsNone(hd.tim_hd_gmail(None, self.ban, {'9999999999': {'one': self.inv}}))

    def test_xml_identity_does_not_fall_back_to_other_pdf(self):
        det = {'shdon': 999, 'ban_mst': SELLER, 'mua_mst': BUYER, 'khhdon': 'C26TYY', 'khmshdon': 1}
        with patch.object(identity, 'read_pdf', return_value=TEXT) as read:
            self.assertIsNone(hd.tim_hd_gmail(det, self.ban, {BUYER: {'one': self.inv}}))
            read.assert_not_called()

    def test_gmail_link_and_code_persist_after_unique_pdf_match(self):
        hd.ghi_kho(BUYER, 'purchase', {'one': self.inv})
        with patch.object(identity, 'read_pdf', return_value=TEXT):
            self.assertEqual(hd.lien_ket_gmail(self.ban), 'ghep')
        result = hd.doc_kho(BUYER, 'purchase')['one']
        self.assertTrue(hd.tuyet_doi(result['_goc_path']).exists())
        self.assertEqual(result['_bkav_mtc'], 'TESTCODE')
        self.assertEqual(result['_goc_nguon'], 'Gmail')
        self.assertEqual(hd.tom_tat(result)['can_tai_tay'], False)

    def test_tct_batch_reconciles_only_selected_invoices(self):
        other = dict(self.inv, shdon=124)
        hd.ghi_kho(BUYER, 'purchase', {'one': self.inv, 'two': other})
        hd._ghi_json(hd._gmail_kho_path(), {'mail': self.ban})
        v = SimpleNamespace(huy=threading.Event(), log=lambda s: None, i=0, n=0)
        client = SimpleNamespace(clone=lambda: SimpleNamespace())
        with patch.object(identity, 'read_pdf', return_value=TEXT), patch.object(hd, '_can_dang_nhap', return_value=client), patch.object(hd, 'tai_mot', return_value={'thieu': [], 'goc': False, 'pdf': False}) as download:
            hd.tai_ds(v, BUYER, 'purchase', ['one'], ['goc'])
        self.assertEqual(download.call_count, 1)
        rows = hd.doc_kho(BUYER, 'purchase')
        self.assertIn('_goc_path', rows['one'])
        self.assertNotIn('_goc_path', rows['two'])

    def test_unreadable_pdf_never_uses_weak_email_metadata(self):
        with patch.object(identity, 'read_pdf', return_value=''):
            self.assertIsNone(hd.tim_hd_gmail(None, dict(self.ban, so=123, ban_mst=SELLER), {BUYER: {'one': self.inv}}))


if __name__ == '__main__':
    unittest.main()
