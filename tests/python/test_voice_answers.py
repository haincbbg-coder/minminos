from _paths import ROOT, SERVER
import unittest
from unittest.mock import patch
import voice_answers as v

class CacheTests(unittest.TestCase):
    def setUp(self): v._CACHE.clear()
    def test_scoped_and_fresh(self):
        q="Kết quả kinh doanh ngày 2 tháng 10"
        v.put("a","one",q,"Doanh thu 100 triệu.")
        self.assertIn("100 triệu",v.get("a","one",q,"fast"))
        self.assertIsNone(v.get("b","one",q,"fast"))
        self.assertIsNone(v.get("a","two",q,"fast"))
        self.assertIsNone(v.get("a","one",q,"thorough"))
        with patch.object(v.time,"monotonic",return_value=v.time.monotonic()+901):
            self.assertIsNone(v.get("a","one",q,"fast"))
    def test_refresh_and_actions_never_reuse(self):
        for q in ["Gửi báo cáo doanh thu", "Doanh thu mới nhất", "Kiểm tra lại kết quả kinh doanh"]:
            v.put("a","s",q,"123")
            self.assertIsNone(v.get("a","s",q,"fast"))

if __name__ == "__main__": unittest.main()
