"""Supplier downloads: captured WebForms shape, legacy email tokens and batch errors."""
from _paths import ROOT, SERVER
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import routes.hoa_don as hd

bkav=hd.thd("providers.bkav")
easy=hd.thd("providers.easyinvoice")
gmail=hd.thd("gmail_scan")
PDF=b"%PDF-1.4\nfixture"
GUID="00000000-0000-0000-0000-000000000001"

def response(text="",content=b"",status=200):
    return SimpleNamespace(text=text,content=content,status_code=status)

class SupplierBatch(unittest.TestCase):
    def test_bkav_direct_postback_never_calls_captcha(self):
        from unittest.mock import Mock
        session=Mock()
        session.get.side_effect=[response("ViewInvoice('"+GUID+"');"), response('<input type="hidden" name="__VIEWSTATE" value="state"/><a href="javascript:__doPostBack(&#39;UcHtmlPdfToolbar$lbtnDownloadHtmlAsPdf&#39;,&#39;&#39;)">')]
        session.post.return_value=response(content=PDF)
        solver=Mock()
        with patch.object(bkav.C,"make_session",return_value=session):
            self.assertEqual(bkav.fetch_pdf("",{"_code":"TEST123"},lambda s:None,solver),PDF)
        solver.recaptcha_v2.assert_not_called()
        data=session.post.call_args.kwargs["data"]
        self.assertEqual(data["__VIEWSTATE"],"state")
        self.assertEqual(data["__EVENTTARGET"],"UcHtmlPdfToolbar$lbtnDownloadHtmlAsPdf")
        self.assertIn("InvoiceGUID="+GUID,session.post.call_args.args[0])

    def test_bkav_no_invoice_does_not_claim_success(self):
        from unittest.mock import Mock
        session=Mock();session.get.return_value=response('<div>captcha</div>')
        with patch.object(bkav.C,"make_session",return_value=session):
            with self.assertRaises(hd.thd("providers").ProviderError):
                bkav.fetch_pdf("",{"_code":"TEST123"},lambda s:None)
        session.post.assert_not_called()

    def test_easy_rejects_corporate_host_and_uses_central(self):
        with patch.object(easy,"_get_pdf",return_value=PDF) as get:
            self.assertEqual(easy.download_by_token("YWJjfDE=",lambda s:None,hosts=["http://easyinvoice.vn","https://evil.example"]),PDF)
            self.assertEqual(get.call_args.args[1],"https://tracuu.easyinvoice.vn")
        info=gmail.extract_link_info("easyinvoice",'https://tenant.easyinvoice.vn/Invoice/ViewFromEmail?token=YWJjfDE%3D')
        self.assertIn("tenant.easyinvoice.vn/Invoice/ViewFromEmail?token=YWJjfDE%3D",info["lookup_url"])

    def test_legacy_token_recovery_without_mail_rescan(self):
        row={"nha_cung_cap":"easyinvoice","ma_tra_cuu":"YWJjfDE=","link":""}
        info=hd.thong_tin_tra_cuu_gmail(row)
        self.assertEqual(info["token"],"YWJjfDE=")
        self.assertEqual(row["link"],"https://tracuu.easyinvoice.vn/Invoice/ViewFromEmail?token=YWJjfDE%3D")

    def test_batch_continues_after_failure_and_persists_status(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(hd,"goc_du_lieu",return_value=Path(temp)),patch.object(hd,"tao_solver",return_value=None),patch.object(hd,"lien_ket_gmail"),patch.object(gmail,"fetch_from_link",side_effect=[ValueError("expired"),PDF]):
            rows=[{"id":"a","so":"1","nha_cung_cap":"easyinvoice","ma_tra_cuu":"YWJjfDE="},{"id":"b","so":"2","nha_cung_cap":"easyinvoice","ma_tra_cuu":"YWJjfDI="}]
            hd._ghi_json(hd._gmail_kho_path(),{r["id"]:r for r in rows})
            result=hd.tai_gmail_da_chon(hd.Viec("gmail","test"),rows)
            self.assertEqual(result,{"co_pdf":1,"thieu":1})
            stored=hd._doc_json(hd._gmail_kho_path(),{})
            self.assertTrue(stored["a"]["can_tai_tay"])
            self.assertIn("expired",stored["a"]["trang_thai"])
            self.assertFalse(stored["b"]["can_tai_tay"])
            self.assertIn("ViewFromEmail",stored["a"]["link"])

if __name__ == "__main__":unittest.main()
