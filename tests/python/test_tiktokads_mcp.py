"""Cầu nối TikTok Ads (server/tiktokads_mcp.py). Không mạng.

    python tests/run.py tiktokads_mcp

Phủ: header Access-Token, tham số danh sách/đối tượng mã hoá JSON trên GET, tự chọn tài khoản
quảng cáo khi chỉ có một (báo lỗi khi nhiều hoặc không có), khoảng ngày báo cáo mặc định và bị
cắt 30 ngày, đổi auth_code lấy token rồi LƯU và không đổi lại lần hai, kiểm tra chặt bật/tắt
chiến dịch và đổi ngân sách TRƯỚC khi chạm mạng, lỗi không lộ bí mật, tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
import os
import tempfile
from datetime import date

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-tiktokads-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import tiktokads_mcp as t  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
da_luu = []
mcp_store.update_connection = lambda cid, patch: da_luu.append((cid, patch)) or True

SECRET = "bi-mat-app-tiktok-987654"
TOKEN = "tok-dai-han-ABCDEF123456"


def spec(**them):
    sec = {"app_id": "7000111", "secret": SECRET, "access_token": TOKEN}
    sec.update(them)
    return {"key": "conn-tta-1", "secrets": sec}


def chay(c):
    return asyncio.run(c)


def ok(data):
    return {"code": 0, "message": "OK", "request_id": "r1", "data": data}


def mot_adv(gia):
    gia.tra("/oauth2/advertiser/get/", ok({"list": [{"advertiser_id": "111222", "advertiser_name": "HALIMI"}]}))


# ---- 1. thiếu ô ----
check("thiếu secret -> báo rõ", "secret" in chay(t.call("tiktokads_tai_khoan", {}, {"secrets": {"app_id": "1"}})))
check("không token không code -> lỗi",
      chay(t.call("tiktokads_tai_khoan", {}, {"secrets": {"app_id": "1", "secret": SECRET}})).startswith("ERROR"))

# ---- 2. header + liệt kê tài khoản + JSON hoá danh sách ----
gia = GiaHttp().lap()
gia.tra("/oauth2/advertiser/get/", ok({"list": [{"advertiser_id": "111222", "advertiser_name": "HALIMI"},
                                                {"advertiser_id": "333444", "advertiser_name": "MeiMei"}]}))
gia.tra("/advertiser/info/", ok({"list": [{"advertiser_id": "111222", "currency": "VND", "balance": 5}]}))
ra = chay(t.call("tiktokads_tai_khoan", {}, spec()))
check("liệt kê tài khoản trả tên + tiền tệ", "HALIMI" in ra and "VND" in ra, ra)
g0 = gia.goi[0]
check("host + path đúng", g0["url"] == "https://business-api.tiktok.com/open_api/v1.3/oauth2/advertiser/get/")
check("header Access-Token", g0["headers"].get("Access-Token") == TOKEN, g0["headers"])
check("advertiser/get gửi app_id + secret", g0["params"] == {"app_id": "7000111", "secret": SECRET})
check("trả về không lộ secret", SECRET not in ra and TOKEN not in ra)
g1 = gia.goi[1]["params"]
check("advertiser_ids gửi dạng chuỗi JSON", g1["advertiser_ids"] == '["111222","333444"]', g1)
check("fields gửi dạng chuỗi JSON", isinstance(g1["fields"], str) and json.loads(g1["fields"])[0] == "advertiser_id")
gia.go()

# ---- 3. chọn tài khoản: một thì tự chọn, nhiều/không thì báo ----
gia = GiaHttp().lap()
mot_adv(gia)
gia.tra("/campaign/get/", ok({"list": [{"campaign_id": "9001", "campaign_name": "Đầm hè"}], "page_info": {}}))
ra = chay(t.call("tiktokads_chien_dich", {"filtering": {"campaign_ids": ["9001"]}}, spec()))
check("một tài khoản -> tự chọn", "Đầm hè" in ra, ra)
cg = [g for g in gia.goi if "/campaign/get/" in g["url"]][0]["params"]
check("chiến dịch dùng advertiser tự chọn", cg["advertiser_id"] == "111222")
check("filtering gửi dạng chuỗi JSON", cg["filtering"] == '{"campaign_ids":["9001"]}', cg)
check("page_size mặc định 100", cg["page_size"] == 100)
chay(t.call("tiktokads_chien_dich", {"advertiser_id": "555", "page_size": 99999}, spec()))
cg = gia.goi[-1]["params"]
check("page_size bị chặn 1000", cg["page_size"] == 1000)
check("advertiser_id truyền vào được dùng", cg["advertiser_id"] == "555")
check("advertiser_id không phải số -> lỗi",
      chay(t.call("tiktokads_chien_dich", {"advertiser_id": "12;x"}, spec())).startswith("ERROR"))
check("filtering sai dạng -> lỗi", chay(t.call("tiktokads_chien_dich", {"filtering": "[1"}, spec())).startswith("ERROR"))
gia.go()

gia = GiaHttp().lap()
gia.tra("/oauth2/advertiser/get/", ok({"list": [{"advertiser_id": "111222"}, {"advertiser_id": "333444"}]}))
ra = chay(t.call("tiktokads_chien_dich", {}, spec()))
check("nhiều tài khoản -> lỗi kèm danh sách mã", ra.startswith("ERROR") and "111222" in ra and "333444" in ra, ra)
check("nhiều tài khoản -> không gọi campaign/get", not any("/campaign/get/" in g["url"] for g in gia.goi))
gia.tra("/campaign/get/", ok({"list": []}))
chay(t.call("tiktokads_chien_dich", {}, spec(advertiser_id="333444")))
check("tài khoản mặc định của kết nối được dùng", gia.goi[-1]["params"]["advertiser_id"] == "333444")
gia.go()

gia = GiaHttp().lap()
gia.tra("/oauth2/advertiser/get/", ok({"list": []}))
check("không có tài khoản -> lỗi", chay(t.call("tiktokads_chien_dich", {}, spec())).startswith("ERROR"))
gia.go()

# ---- 4. nhóm quảng cáo: campaign_ids vào filtering ----
gia = GiaHttp().lap()
gia.tra("/adgroup/get/", ok({"list": []}))
chay(t.call("tiktokads_nhom_quang_cao", {"advertiser_id": "111222", "campaign_ids": "1,2"}, spec()))
p = gia.goi[-1]["params"]
check("nhóm QC: filtering campaign_ids JSON", json.loads(p["filtering"]) == {"campaign_ids": ["1", "2"]}, p)
check("nhóm QC: campaign_ids lạ -> lỗi",
      chay(t.call("tiktokads_nhom_quang_cao", {"advertiser_id": "1", "campaign_ids": "a b"}, spec())).startswith("ERROR"))
gia.go()

# ---- 5. báo cáo: ngày mặc định, cắt 30 ngày, JSON hoá ----
tu, den = t.khoang_ngay({}, hom_nay=date(2026, 10, 7))
check("mặc định 7 ngày gần nhất", (tu, den) == ("2026-10-01", "2026-10-07"), (tu, den))
tu, den = t.khoang_ngay({"start_date": "2026-01-01", "end_date": "2026-06-30"})
check("khoảng dài bị cắt còn 30 ngày", (tu, den) == ("2026-06-01", "2026-06-30"), (tu, den))
tu, den = t.khoang_ngay({"start_date": "2026-03-10", "end_date": "2026-03-01"})
check("ngày đảo ngược được sửa", (tu, den) == ("2026-03-01", "2026-03-10"))

gia = GiaHttp().lap()
gia.tra("/report/integrated/get/", ok({"list": [{"metrics": {"spend": "100000"}}]}))
chay(t.call("tiktokads_bao_cao", {"advertiser_id": "111222", "theo_ngay": True,
                                  "start_date": "2026-01-01", "end_date": "2026-03-01"}, spec()))
p = gia.goi[-1]["params"]
check("báo cáo: report_type BASIC, cấp chiến dịch", p["report_type"] == "BASIC" and p["data_level"] == "AUCTION_CAMPAIGN")
check("báo cáo: dimensions JSON + theo ngày", p["dimensions"] == '["campaign_id","stat_time_day"]', p["dimensions"])
check("báo cáo: metrics mặc định JSON", json.loads(p["metrics"]) == t.CHI_SO_MAC_DINH)
check("báo cáo: khoảng ngày bị cắt 30 ngày", (p["start_date"], p["end_date"]) == ("2026-01-31", "2026-03-01"), p)
chay(t.call("tiktokads_bao_cao", {"advertiser_id": "1", "data_level": "AUCTION_AD",
                                  "metrics": ["spend", "clicks"]}, spec()))
p = gia.goi[-1]["params"]
check("báo cáo: cấp quảng cáo dùng ad_id", p["dimensions"] == '["ad_id"]' and p["metrics"] == '["spend","clicks"]')
n = len(gia.goi)
check("báo cáo: data_level lạ -> lỗi", chay(t.call("tiktokads_bao_cao", {"advertiser_id": "1", "data_level": "X"},
                                                    spec())).startswith("ERROR"))
check("báo cáo: tên chỉ số lạ -> lỗi", chay(t.call("tiktokads_bao_cao", {"advertiser_id": "1",
                                                                         "metrics": ["spend; drop"]},
                                                    spec())).startswith("ERROR"))
check("báo cáo sai không chạm mạng", len(gia.goi) == n)
gia.go()

# ---- 6. đổi auth_code lấy token, lưu, không đổi lần hai ----
da_luu.clear()
gia = GiaHttp().lap()
gia.tra("/oauth2/access_token/", ok({"access_token": "TOK-MOI-777777", "advertiser_ids": ["111222"]}))
gia.tra("/campaign/get/", ok({"list": [{"campaign_name": "C1"}]}))
sp = spec(access_token="", auth_code="CODE-TT-123")
ra = chay(t.call("tiktokads_chien_dich", {}, sp))
check("đổi code xong gọi được", "C1" in ra, ra)
tk = [g for g in gia.goi if "/oauth2/access_token/" in g["url"]]
check("đổi code gửi app_id, secret, auth_code",
      tk and tk[0]["method"] == "POST" and tk[0]["json"] == {"app_id": "7000111", "secret": SECRET,
                                                             "auth_code": "CODE-TT-123"})
check("đổi code xong tự chọn advertiser từ advertiser_ids (không gọi advertiser/get)",
      not any("/oauth2/advertiser/get/" in g["url"] for g in gia.goi))
check("gọi API bằng token mới", gia.goi[-1]["headers"]["Access-Token"] == "TOK-MOI-777777")
luu = {}
for _c, patch in da_luu:
    luu.update(patch["fields"])
check("token mới được LƯU", luu.get("access_token") == "TOK-MOI-777777")
check("đánh dấu code đã dùng", luu.get("auth_code_da_dung") == "CODE-TT-123")
check("lưu đúng kết nối", da_luu and all(c == "conn-tta-1" for c, _ in da_luu))
chay(t.call("tiktokads_chien_dich", {}, sp))
check("code đã dùng không đổi lần hai", len([g for g in gia.goi if "/oauth2/access_token/" in g["url"]]) == 1)
gia.go()

gia = GiaHttp().lap()
gia.tra("/oauth2/access_token/", {"code": 40001, "message": "auth_code invalid CODE-HONG-999", "data": {}})
ra = chay(t.call("tiktokads_tai_khoan", {}, spec(access_token="", auth_code="CODE-HONG-999")))
check("code hỏng -> lỗi không lộ code", ra.startswith("ERROR") and "CODE-HONG-999" not in ra, ra)
gia.go()

# ---- 7. bật/tắt chiến dịch: kiểm tra trước khi chạm mạng ----
gia = GiaHttp().lap()
gia.tra("/campaign/status/update/", ok({"campaign_ids": ["1"]}))
sai = [
    ("thao tác DELETE", {"advertiser_id": "1", "campaign_ids": "1", "operation_status": "DELETE"}),
    ("thao tác lạ", {"advertiser_id": "1", "campaign_ids": "1", "operation_status": "PAUSE"}),
    ("thiếu thao tác", {"advertiser_id": "1", "campaign_ids": "1"}),
    ("quá 20 mã", {"advertiser_id": "1", "campaign_ids": ",".join(str(i) for i in range(21)), "operation_status": "ENABLE"}),
    ("mã không phải số", {"advertiser_id": "1", "campaign_ids": "12,abc", "operation_status": "DISABLE"}),
    ("thiếu mã", {"advertiser_id": "1", "campaign_ids": "", "operation_status": "DISABLE"}),
]
for ten, args in sai:
    check("bật/tắt từ chối: " + ten, chay(t.call("tiktokads_bat_tat_chien_dich", args, spec())).startswith("ERROR"))
check("bật/tắt sai không chạm mạng", gia.goi == [])
ra = chay(t.call("tiktokads_bat_tat_chien_dich", {"advertiser_id": "111222", "campaign_ids": ["1", "2"],
                                                  "operation_status": "disable"}, spec()))
g = gia.goi[-1]
check("bật/tắt hợp lệ là POST đúng body",
      g["method"] == "POST" and g["json"] == {"advertiser_id": "111222", "campaign_ids": ["1", "2"],
                                               "operation_status": "DISABLE"}, g["json"])
check("bật/tắt có header token", g["headers"]["Access-Token"] == TOKEN)
gia.go()

# ---- 8. đổi ngân sách ----
gia = GiaHttp().lap()
gia.tra("/campaign/update/", ok({"campaign_id": "9001"}))
for ten, b in [("0", 0), ("âm", -5), ("chữ", "nhieu"), ("quá lớn", 2_000_000_000), ("NaN", "nan"), ("bool", True)]:
    check("ngân sách từ chối: " + ten, chay(t.call("tiktokads_doi_ngan_sach_chien_dich",
                                                  {"advertiser_id": "1", "campaign_id": "9001", "budget": b},
                                                  spec())).startswith("ERROR"))
check("ngân sách: campaign_id lạ -> lỗi", chay(t.call("tiktokads_doi_ngan_sach_chien_dich",
                                                     {"advertiser_id": "1", "campaign_id": "x", "budget": 1},
                                                     spec())).startswith("ERROR"))
check("ngân sách sai không chạm mạng", gia.goi == [])
chay(t.call("tiktokads_doi_ngan_sach_chien_dich", {"advertiser_id": "111222", "campaign_id": "9001",
                                                   "budget": "500000"}, spec()))
g = gia.goi[-1]
check("ngân sách hợp lệ gửi đúng body", g["method"] == "POST" and g["url"].endswith("/campaign/update/")
      and g["json"] == {"advertiser_id": "111222", "campaign_id": "9001", "budget": 500000.0}, g["json"])
gia.go()

# ---- 9. lỗi không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("/campaign/get/", {"code": 40105, "message": "Access token " + TOKEN + " is invalid", "request_id": "x"})
ra = chay(t.call("tiktokads_chien_dich", {"advertiser_id": "1"}, spec()))
check("code != 0 -> ERROR", ra.startswith("ERROR") and "40105" in ra, ra)
check("lỗi API không lộ token", TOKEN not in ra, ra)
gia.nem_loi("/campaign/get/", ConnectionError("hỏng " + SECRET + " " + TOKEN))
ra = chay(t.call("tiktokads_chien_dich", {"advertiser_id": "1"}, spec()))
check("lỗi mạng không lộ secret/token", ra.startswith("ERROR") and SECRET not in ra and TOKEN not in ra, ra)
gia.tra("/campaign/get/", "<html>lỗi</html>", code=500)
check("HTTP 500 -> ERROR", chay(t.call("tiktokads_chien_dich", {"advertiser_id": "1"}, spec())).startswith("ERROR"))
gia.go()

# ---- 10. danh sách tool + tool lạ + không gạch dài ----
ten_tool = {x["name"] for x in chay(t.list_tools({}))}
check("đủ 6 tool", ten_tool == {"tiktokads_tai_khoan", "tiktokads_chien_dich", "tiktokads_nhom_quang_cao",
                                 "tiktokads_bao_cao", "tiktokads_bat_tat_chien_dich",
                                 "tiktokads_doi_ngan_sach_chien_dich"}, ten_tool)
check("tool lạ -> lỗi", chay(t.call("tiktokads_xoa_chien_dich", {}, spec())).startswith("ERROR"))
nguon = (SERVER / "tiktokads_mcp.py").read_text(encoding="utf-8")
check("không có gạch dài", "\u2014" not in nguon and "\u2013" not in nguon)
check.ket_thuc()
