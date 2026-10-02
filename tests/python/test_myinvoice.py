"""Verified MY SOFTWARE portal flow; fixtures contain no real customer codes."""
from _paths import ROOT
import datetime as dt
from email.message import EmailMessage
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(ROOT / "apps" / "tai-hoa-don"))
from thd.providers import myinvoice as p, ProviderError, manual_download_info, detect
from thd import gmail_scan as g

CODE = "0123456789ABCDEF"


def xml(number="35", seller="1111111111"):
    return (f'<HDon><DLHDon><TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TPC</KHHDon>'
            f'<SHDon>{number}</SHDon><MSTTCGP>0108971656</MSTTCGP></TTChung>'
            f'<NDHDon><NBan><MST>{seller}</MST></NBan></NDHDon></DLHDon>'
            '<MCCQT>0123456789ABCDEF0123456789ABCDEF</MCCQT></HDon>').encode()


class MyInvoice(unittest.TestCase):
    def test_real_flow_and_identity_normalization(self):
        session = Mock()
        session.get.side_effect = [Mock(status_code=200, content=xml("00000035")),
                                   Mock(status_code=200, content=b"%PDF-test")]
        with patch.object(p.C, "make_session", return_value=session):
            self.assertEqual(p.fetch_pdf(xml().decode(), {"_code": CODE}, Mock()), b"%PDF-test")
        self.assertEqual([call.args[0] for call in session.get.call_args_list],
                         [p.API + CODE + "/xml", p.API + CODE + "/pdf"])
        session.close.assert_called_once()

    def test_wrong_invoice_never_downloads_pdf(self):
        for document in (xml("36"), xml(seller="9999999999")):
            session = Mock()
            session.get.return_value = Mock(status_code=200, content=document)
            with patch.object(p.C, "make_session", return_value=session), self.assertRaises(ProviderError):
                p.fetch_pdf(xml().decode(), {"_code": CODE}, Mock())
            self.assertEqual(session.get.call_count, 1)

    def test_missing_code_does_not_use_tax_code_or_number(self):
        with patch.object(p.C, "make_session") as session, self.assertRaises(ProviderError):
            p.fetch_pdf(xml().decode(), {}, Mock())
        session.assert_not_called()
        self.assertIs(detect(xml()), p)
        info = manual_download_info(xml(), {"_ma_tra_cuu": CODE})
        self.assertEqual(info["code"], CODE)
        self.assertEqual(info["url"], p.API + CODE + "/pdf")
        self.assertNotIn("captcha", info["method"])

    def test_rejects_html_and_redirect(self):
        for response in (Mock(status_code=200, content=b"<html>gateway</html>"),
                         Mock(status_code=302, content=b"")):
            session = Mock()
            session.get.return_value = response
            with patch.object(p.C, "make_session", return_value=session), self.assertRaises(ProviderError):
                p.fetch_documents(CODE, Mock())
            self.assertEqual(session.get.call_count, 1)

    def test_rejects_non_pdf(self):
        session = Mock()
        session.get.side_effect = [Mock(status_code=200, content=xml()),
                                   Mock(status_code=200, content=b"<html>error</html>")]
        with patch.object(p.C, "make_session", return_value=session), self.assertRaises(ProviderError):
            p.fetch_documents(CODE, Mock())

    def test_email_html_label_not_cqt(self):
        info = g.extract_link_info("myinvoice", f'Mã CQT: <b>{"A" * 32}</b> và nhập mã: <strong>{CODE}</strong>')
        self.assertEqual(info["code"], CODE)
        self.assertEqual(p.email_code("Mã CQT: " + "A" * 32), "")

    def test_attachment_email_keeps_lookup_code(self):
        msg = EmailMessage()
        msg["From"] = "no-reply@mysoftware.vn"
        msg["Subject"] = "Hóa đơn số 35"
        msg.set_content(f"https://tracuu.myinvoice.vn và nhập mã: {CODE}")
        msg.add_attachment(xml(), maintype="application", subtype="xml", filename="invoice.xml")
        scanner = g.GmailScanner("test@example.com", "")
        with patch.object(scanner, "_search_uids", return_value=["1"]), patch.object(scanner, "_fetch_raw", return_value=msg.as_bytes()):
            rows = scanner.scan(dt.date(2026,1,1), dt.date(2026,12,31), want_download=False)
        self.assertEqual(rows[0]["code"], CODE)
        self.assertEqual(rows[0]["lookup_url"], p.PORTAL)


if __name__ == "__main__":
    unittest.main()
