"""Issuer portals must remain available with or without an extracted lookup code."""
from _paths import ROOT
import sys
import unittest
sys.path.insert(0, str(ROOT / "apps" / "tai-hoa-don"))
from thd.providers import manual_download_info, issuer_name


def xml(issuer):
    return (f'<HDon><DLHDon><TTChung><MSTTCGP>{issuer}</MSTTCGP><SHDon>7</SHDon>'
            '</TTChung><NDHDon><NBan><MST>1111111111</MST></NBan></NDHDon>'
            '</DLHDon></HDon>').encode()


class LookupPortals(unittest.TestCase):
    def test_verified_portals_keep_code(self):
        for issuer, host in [('0401486901', 'https://tracuu.vin-hoadon.com/'),
                             ('0402024593', 'https://tracuu.vin-hoadon.com/'),
                             ('0105232093', 'https://tracuuhoadon1.xcyber.vn/')]:
            with self.subTest(issuer=issuer):
                info = manual_download_info(xml(issuer), {'_ma_tra_cuu':'EXAMPLE123'})
                self.assertTrue(info['url'].startswith(host))
                self.assertEqual(info['code'], 'EXAMPLE123')
                self.assertFalse(issuer_name({'_detail':{'msttcgp':issuer}}).startswith('NPH '))

    def test_missing_code_still_has_portal(self):
        info = manual_download_info(xml('0105232093'))
        self.assertTrue(info['url'].startswith('https://tracuuhoadon1.xcyber.vn/'))
        self.assertFalse(info['code'])

    def test_unknown_issuer_does_not_invent_link(self):
        info = manual_download_info(xml('9999999999'), {'_ma_tra_cuu':'EXAMPLE123'})
        self.assertFalse((info or {}).get('url'))


if __name__ == '__main__':
    unittest.main()
