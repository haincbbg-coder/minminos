"""Regression coverage for envelope XML and email-only lookup identities."""
from _paths import ROOT, SERVER
import datetime as dt
from email.message import EmailMessage
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import routes.hoa_don as hd


def invoice(number):
    return f'''<TDiep xmlns="urn:invoice"><TTChung><MST>9999999999</MST></TTChung>
    <DLieu><HDon><DLHDon><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TAA</KHHDon>
    <SHDon>{number}</SHDon><NLap>2026-06-15</NLap></TTChung><NDHDon>
    <NBan><MST>1111111111</MST><Ten>Supplier</Ten></NBan>
    <NMua><MST>2222222222</MST></NMua><TToan><TgTTTBSo>100</TgTTTBSo></TToan>
    </NDHDon></DLHDon><MCCQT>AUTH-CODE</MCCQT></HDon></DLieu></TDiep>'''.encode()


class EnvelopeRecovery(unittest.TestCase):
    def test_invoice_header_is_inside_signed_payload(self):
        mod = hd.thd('invoice_xml')
        result = mod.parse_invoice(invoice('00000030'))
        self.assertEqual(result['shdon'], '00000030')
        self.assertEqual(result['khhdon'], 'C26TAA')
        self.assertEqual(result['ngay'], '2026-06-15')
        self.assertEqual(result['ban_mst'], '1111111111')
        self.assertEqual(result['mccqt'], 'AUTH-CODE')
        with self.assertRaises(ValueError):
            mod.parse_invoice(b'<TDiep><DLHDon/><DLHDon/></TDiep>')

    def test_mail_subject_provides_identity_without_attachment(self):
        mod = hd.thd('gmail_scan')
        msg = EmailMessage()
        msg['From'] = 'thongbao@ihoadon.vn'
        msg['Subject'] = 'Vv phát hành HDĐT số 1875 C26TTH, MST 1111111111 (03-08-2026)'
        msg.set_content('Mã tra cứu: TESTCODE123\nhttps://tracuu.ihoadon.vn/?shd=1875&mtc=TESTCODE123')
        scanner = mod.GmailScanner('test@example.com', '')
        with patch.object(scanner, '_search_uids', return_value=['1']), patch.object(scanner, '_fetch_raw', return_value=msg.as_bytes()):
            rows = scanner.scan(dt.date(2026,1,1), dt.date(2026,12,31), want_download=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['_seller_mst'], '1111111111')
        self.assertEqual(rows[0]['_khhdon'], 'C26TTH')
        self.assertEqual(rows[0]['_so_hd'], '1875')
        self.assertEqual(rows[0]['_mtc'], 'TESTCODE123')

    def test_rescan_preserves_distinct_enveloped_invoices_and_matches_metadata(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(hd, 'goc_du_lieu', return_value=Path(folder)):
            hd.ghi_cau_hinh({'doanh_nghiep': {'2222222222': {'ten':'Buyer'}}})
            hd.ghi_kho('2222222222', 'purchase', {
                str(n): {'nbmst':'1111111111','khhdon':'C26TAA','khmshdon':'1','shdon':n}
                for n in (30,31,32)})
            records = [{'xml':invoice(str(n)), 'pdf':b'%PDF-fixture', 'subject':'Invoice', 'from':'sender'} for n in (30,31)]
            records.append({'_seller_mst':'1111111111','_khhdon':'C26TAA','_so_hd':'32','code':'LOOKUP32','lookup_url':'https://tracuu.ihoadon.vn/','subject':'Invoice 32'})
            records += [{'subject':f'Unknown {n}','_source_id':str(n)} for n in (1,2)]
            scanner = Mock(last_uid=0)
            scanner.scan.return_value = records
            with patch.object(hd,'ds_gmail',return_value={'mail@example.com':{'kieu':'google','refresh':'fake'}}), patch.object(hd,'giai_ma',return_value='fake'), patch.object(hd,'tao_bo_quet_google',return_value=scanner):
                for _ in range(2):
                    hd.quet_gmail(Mock(),dt.date(2026,1,1),dt.date(2026,12,31),False)
            self.assertEqual(len(hd._doc_json(hd._gmail_kho_path(),{})),5)
            rows = hd.doc_kho('2222222222','purchase')
            self.assertTrue(rows['30']['_goc_path'])
            self.assertTrue(rows['31']['_goc_path'])
            self.assertEqual(rows['32']['_ma_tra_cuu'],'LOOKUP32')
            self.assertEqual(len(rows),3)


if __name__ == '__main__':
    unittest.main()
