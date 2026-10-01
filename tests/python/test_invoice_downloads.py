"""Regression: PDF fallback, provider payloads, email ZIP pairing and incomplete downloads."""
from _paths import ROOT, SERVER  # noqa
import base64
import io
import json
import tempfile
import unittest
import zipfile
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import routes.hoa_don as hd

providers = hd.thd("providers")
link = providers.xmllink
exporter = hd.thd("exporter")
gmail = hd.thd("gmail_scan")
PDF = b"%PDF-1.7\nfixture\n%%EOF"
XML = b"<HDon><DLHDon><TTChung><SHDon>1</SHDon></TTChung></DLHDon></HDon>"


def archive(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, content in files:
            z.writestr(name, content)
    return b.getvalue()


class Downloads(unittest.TestCase):
    def test_provider_failure_uses_embedded_link_without_mutating_xml(self):
        raw = b'<HDon><PdfUrl>https://example.com/invoice.pdf</PdfUrl></HDon>'
        provider = SimpleNamespace(NAME="Vendor", fetch_pdf=lambda *a, **k: (_ for _ in ()).throw(providers.ProviderError("offline")))
        with patch.object(providers, "detect", return_value=provider), patch.object(link, "fetch_pdf", return_value=PDF) as fallback:
            self.assertEqual(providers.fetch_original_pdf(raw), (link.NAME, PDF))
            self.assertEqual(fallback.call_args.args[0].encode(), raw)
            fallback.reset_mock()
            with patch.object(providers, "PROVIDERS", [provider]), self.assertRaises(providers.ProviderError):
                providers.fetch_original_pdf(raw, force="Vendor")
            fallback.assert_not_called()

    def test_payloads_and_ambiguity(self):
        self.assertEqual(link._pdf_payload(PDF), PDF)
        self.assertEqual(link._pdf_payload(archive([("a.pdf", PDF), ("a.xml", XML)])), PDF)
        self.assertEqual(link._pdf_payload(json.dumps({"data": {"fileContent": base64.b64encode(PDF).decode()}}).encode()), PDF)
        self.assertIsNone(link._pdf_payload(archive([("a.pdf", PDF), ("b.pdf", PDF)])))
        self.assertIsNone(link._pdf_payload(b'<html>captcha</html>'))
        self.assertIsNone(link._pdf_payload(b'{"pdf":"not base64"}'))

    def test_xml_fields_order_namespace_and_cdata(self):
        from minmin_thd.providers import _common as common
        raw = '<i:HDon xmlns:i="urn:invoice"><i:TTin><i:DLieu><![CDATA[https://example.com/a?x=1&y=2]]></i:DLieu><i:TTruong>PdfUrl</i:TTruong></i:TTin></i:HDon>'
        self.assertEqual(common.ttkhac(raw, "PdfUrl"), "https://example.com/a?x=1&y=2")

    def test_private_and_redirect_destinations_blocked(self):
        for url in ("http://example.com/a.pdf", "https://u:p@example.com/a.pdf"):
            with self.assertRaises(providers.ProviderError):
                link._public_url(url)
        with patch.object(link.socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("127.0.0.1", 443))]):
            with self.assertRaises(providers.ProviderError):
                link._public_url("https://example.com/a.pdf")
        from unittest.mock import MagicMock
        response = MagicMock(status_code=302, headers={"Location": "https://127.0.0.1/private"})
        response.__enter__.return_value = response
        session = MagicMock()
        session.get.return_value = response
        with patch.object(link, "_public_url", side_effect=[None, providers.ProviderError("private")]):
            self.assertIsNone(link._try_download(session, "https://example.com/a.pdf", lambda s: None))
        self.assertEqual(session.get.call_count, 1)
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def test_pdf_generation_rejects_stale_and_invalid_output(self):
        with tempfile.TemporaryDirectory() as temp:
            html = Path(temp) / "hoá đơn #1.html"
            html.write_text("<h1>Invoice</h1>", encoding="utf-8")
            out = Path(temp) / "invoice.pdf"
            out.write_bytes(PDF)
            with patch.object(exporter.subprocess, "run"):
                with self.assertRaises(RuntimeError):
                    exporter.html_to_pdf(str(html), str(out), "browser")
            self.assertEqual(out.read_bytes(), PDF)
            def run(cmd, **kwargs):
                self.assertEqual(cmd[-1], html.resolve().as_uri())
                path = next(x.split("=", 1)[1] for x in cmd if x.startswith("--print-to-pdf="))
                Path(path).write_bytes(PDF + b"new")
            with patch.object(exporter.subprocess, "run", side_effect=run):
                exporter.html_to_pdf(str(html), str(out), "browser")
            self.assertEqual(out.read_bytes(), PDF + b"new")

    def test_gmail_zip_pairs_by_name_not_order(self):
        msg = EmailMessage()
        msg.set_content("Hoa don")
        msg.add_attachment(archive([("one.xml", XML), ("two.pdf", PDF + b"two"),
                                    ("two.xml", XML), ("one.pdf", PDF)]),
                           maintype="application", subtype="zip", filename="invoices.zip")
        pairs = gmail._invoice_attachments(gmail._attachments(msg))
        self.assertEqual([p[1] for p in pairs], [PDF, PDF + b"two"])
        self.assertEqual(gmail._invoice_attachments([("one.xml", XML), ("two.xml", XML), ("other.pdf", PDF)]),
                         [(XML, None), (XML, None)])
        self.assertEqual(gmail._invoice_attachments([("one.xml", XML), ("one.xml", XML), ("one.pdf", PDF)]),
                         [(XML, None), (XML, None)])

    def test_retry_cached_xml_recovers_detail_and_counts_missing(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(hd, "goc_du_lieu", return_value=Path(temp)):
            xml = Path(temp) / "invoice.xml"
            xml.write_bytes(XML)
            inv = {"_xml_path": "invoice.xml", "shdon": 1}
            client = SimpleNamespace(download_xml_zip=lambda *a: self.fail("cached XML must not redownload"))
            config = dict(hd.cai_dat_tai(), giu_zip=False)
            r = hd.tai_mot(client, "1234567890", inv, ["pdf"], lambda s: None, config, "")
            self.assertEqual(r["thieu"], ["pdf"])
            self.assertIn("_detail", inv)
            self.assertTrue(inv["_pdf_loi"])


if __name__ == "__main__":
    unittest.main()
