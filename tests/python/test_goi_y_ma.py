"""Test lõi tra mã hàng (không mạng)."""
from _paths import ROOT, SERVER  # noqa: F401
import sys
import tempfile

import goi_y_ma as g

ok = loi = 0


def kt(ten, dieu_kien):
    global ok, loi
    if dieu_kien:
        ok += 1
    else:
        loi += 1
        print("FAIL:", ten)


g.mo(tempfile.mkdtemp())
g.nap_sku([{"ma": "v33", "ten": "Set V33", "ton": 80, "anh": ["http://a/1.jpg"]},
           {"ma": "P720", "ten": "Váy P720", "ton": 120}])
kt("chuẩn mã", g.chuan_ma("v 33") == "V33" and g.chuan_ma("p-720") == "P720")
kt("tên chiến dịch", g.ma_tu_ten_chien_dich("CÔNG TY TNHH MTV HALIMI - TÊN PAGE - P720") == "P720")
kt("tên chiến dịch không mã", g.ma_tu_ten_chien_dich("Chiến dịch tháng 10") == "")
r = g.phan_giai(text="giá mã V33 nhiêu shop")
kt("mã trong chữ", r["ung_vien"] and r["ung_vien"][0]["ma"] == "V33" and r["ung_vien"][0]["ton"] == 80)
kt("không bắt nhầm số lạ", g.phan_giai(text="ship 500k nhé")["ung_vien"] == [])
g.nap_quang_cao([{"ad_id": "A1", "ten_chien_dich": "CÔNG TY TNHH MTV HALIMI - PAGE X - P720", "tai_khoan": "Vinh 2"},
                 {"ad_id": "A2", "ma": "v33"}, {"ad_id": "A3"}])
r = g.phan_giai(text="set này giá bao nhiêu", ad_id="A1")
kt("tra theo quảng cáo", r["ung_vien"][0]["ma"] == "P720")
r = g.phan_giai(text="giá V33", ad_id="A2")
kt("hai nguồn cùng mã chắc hơn", r["ung_vien"][0]["do_chac"] > 1.0 - 0.06 and len(r["ung_vien"][0]["bang_chung"]) == 2)
g.nap_bai_viet([{"post_id": "P9", "ma": "p720", "page_id": "pg"}])
kt("tra theo bài viết", g.phan_giai(post_id="P9")["ung_vien"][0]["ma"] == "P720")
kt("lạ thì rỗng", g.phan_giai(ad_id="zzz", post_id="yyy")["ung_vien"] == [])
g.xac_nhan("V33", "quang_cao", "A9")
kt("học từ xác nhận", g.phan_giai(ad_id="A9")["ung_vien"][0]["ma"] == "V33")
ma = g.tao_ma_ghep()
m = g.ghep(ma, "Máy A")
kt("ghép máy", g.may_theo_token(m["token"])["id"] == m["may_id"])
try:
    g.ghep(ma)
    kt("mã dùng một lần", False)
except ValueError:
    kt("mã dùng một lần", True)
kt("token sai", g.may_theo_token("mmg_sai") is None)
b = g.xuat_bang()
kt("xuất bảng", b["ad"]["A1"] == "P720" and b["sku"]["V33"][1] == 80)
# --- HTTP: cổng đăng nhập miễn đúng tiền tố, token máy bắt buộc
import os
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-gym-"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import routes.goi_y_ma as rt

app = FastAPI()
rt.register(app)
cl = TestClient(app)
h = {"x-minmin-may": m["token"]}
kt("không token = 401", cl.get("/goi-y-ma/may/bang").status_code == 401)
kt("có token lấy bảng", cl.get("/goi-y-ma/may/bang", headers=h).json()["ad"]["A1"] == "P720")
r = cl.post("/goi-y-ma/may/tra", headers=h, json={"text": "giá V33", "ad_id": "A1"}).json()
kt("tra qua HTTP", {u["ma"] for u in r["ung_vien"]} == {"V33", "P720"})
kt("ghép sai mã = 400", cl.post("/goi-y-ma/may/ghep", json={"ma": "000000"}).status_code == 400)
r2 = cl.post("/goi-y-ma/api/ma-ghep").json()
kt("tạo mã ghép", len(r2["ma"]) == 6)
kt("xác nhận thiếu mã = 400", cl.post("/goi-y-ma/may/xac-nhan", headers=h, json={}).status_code == 400)
kt("xác nhận ok", cl.post("/goi-y-ma/may/xac-nhan", headers=h, json={"ma": "P720", "nguon": "bai_viet", "khoa": "Z1"}).json()["ok"])

print(f"goi_y_ma: {ok} đạt, {loi} lỗi")
sys.exit(1 if loi else 0)
