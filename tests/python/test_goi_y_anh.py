"""Gợi ý mã theo ảnh khách (server/goi_y_anh.py). Không mạng, AI được thay bằng hàm giả.

    python3 tests/python/test_goi_y_anh.py
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import io
import json
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-gya-"))
from PIL import Image, ImageDraw

import goi_y_anh as ga
import goi_y_ma as gm

ok = loi = 0


def kt(ten, dk):
    global ok, loi
    if dk:
        ok += 1
    else:
        loi += 1
        print("FAIL:", ten)


def anh(mau, nen=(255, 255, 255), nhieu=0):
    im = Image.new("RGB", (300, 400), nen)
    d = ImageDraw.Draw(im)
    d.rectangle([60, 50, 240, 360], fill=mau)
    if nhieu:
        d.ellipse([100, 120, 140, 160], fill=(mau[0] // 2, mau[1] // 2, mau[2] // 2))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=88)
    return out.getvalue()


MAU = [(220, 30, 30), (30, 60, 220), (30, 170, 60), (240, 200, 20), (150, 40, 180), (20, 20, 20), (240, 130, 20), (130, 130, 130)]
gm.mo(tempfile.mkdtemp())
ds = []
for i in range(40):
    m = MAU[i % len(MAU)]
    m = (min(255, m[0] + i), max(0, m[1] - i // 2), m[2])
    ds.append({"ma": f"X{i}", "ten": f"Mẫu {i}", "ton": 60 + i, "anh": [f"https://content.test/x{i}.jpg"]})
gm.nap_sku(ds)
kho = {f"https://content.test/x{i}.jpg": anh((min(255, MAU[i % 8][0] + i), max(0, MAU[i % 8][1] - i // 2), MAU[i % 8][2])) for i in range(40)}


async def tai_gia(u):
    return kho.get(u)


r = asyncio.run(ga.hoc_anh_mau(tai=tai_gia))
kt("học đủ 40 mã", r["hoc_xong"] == 40 and r["tong_ma_co_dac_trung"] == 40)
kt("chạy lại không học lại", asyncio.run(ga.hoc_anh_mau(tai=tai_gia))["hoc_xong"] == 0)

# --- đặc trưng và rút gọn
khach_do = anh((225, 35, 35), nen=(200, 220, 255), nhieu=1)
rg = ga.rut_gon(ga.dac_trung(khach_do), 8)
do = {f"X{i}" for i in range(40) if i % 8 == 0}
kt("rút gọn: toàn mã đỏ đứng đầu", len([m for m, _ in rg[:5] if m in do]) >= 4)
kt("bảng ảnh vẽ được", len(ga.ve_bang([m for m, _ in rg])) > 2000)

# --- gọi AI giả
goi = {"n": 0, "anh": 0}


async def ai_gia(urls, cau_hoi, nhan):
    goi["n"] += 1
    goi["anh"] = len(urls)
    return {"ok": True, "text": 'Ảnh 1: giống.\n{"ung_vien":[{"ma":"x8","do_giong":90,"ly_do":"cùng màu đỏ"},{"ma":"BIA","do_giong":99,"ly_do":"mã không có"}],"khong_co":false}'}


r = asyncio.run(ga.tra_anh(khach_do, mo_ta=ai_gia))
kt("trả mã hợp lệ, bỏ mã bịa", r["ok"] and [u["ma"] for u in r["ung_vien"]] == ["X8"])
kt("hai ảnh một lần gọi", goi["n"] == 1 and goi["anh"] == 2)
kt("kèm tồn kho và bằng chứng", r["ung_vien"][0]["ton"] == 68 and r["ung_vien"][0]["bang_chung"][0]["nguon"] == "anh")
r2 = asyncio.run(ga.tra_anh(khach_do, mo_ta=ai_gia))
kt("hỏi lại cùng ảnh = cache, không gọi AI", r2["cache"] and goi["n"] == 1)

# --- học từ xác nhận
kt("xác nhận ảnh khách thì học", ga.hoc_tu_xac_nhan("X8", r["hash"]) and ga.thong_ke()["anh_khach_da_hoc"] == 1)
kt("hash lạ không học", not ga.hoc_tu_xac_nhan("X8", "khongco"))

# --- AI không biết / lỗi / trần ngày
async def ai_khong(urls, c, n):
    return {"ok": True, "text": '{"ung_vien":[],"khong_co":true}'}


async def ai_loi(urls, c, n):
    return {"ok": False, "error": "Chưa kết nối ChatGPT"}


r = asyncio.run(ga.tra_anh(anh((20, 200, 200)), mo_ta=ai_khong))
kt("AI nói không có", r["ok"] and r["khong_co"] and r["ung_vien"] == [])
r = asyncio.run(ga.tra_anh(anh((10, 90, 90)), mo_ta=ai_loi))
kt("AI lỗi báo rõ, không cache", not r["ok"] and "ChatGPT" in r["error"])
ga.TRAN_MOI_NGAY = ga.da_dung_hom_nay()
r = asyncio.run(ga.tra_anh(anh((90, 10, 90)), mo_ta=ai_gia))
kt("chạm trần ngày thì dừng, không gọi AI", not r["ok"] and "hôm nay" in r["error"])
kt("ảnh hỏng báo lỗi", not asyncio.run(ga.tra_anh(b"khong phai anh", mo_ta=ai_gia))["ok"])
kt("đọc trả lời lộn xộn", ga.doc_tra_loi("không phải json", {"A"}) == [] and ga.doc_tra_loi('{"ung_vien":"x"}', {"A"}) == [])

# --- HTTP
from fastapi import FastAPI
from fastapi.testclient import TestClient
import routes.goi_y_ma as rt

ga.TRAN_MOI_NGAY = 500
app = FastAPI()
rt.register(app)
cl = TestClient(app)
may = gm.ghep(gm.tao_ma_ghep(), "t")
h = {"x-minmin-may": may["token"]}
b64 = base64.b64encode(anh((10, 90, 90))).decode()
kt("anh không token = 401", cl.post("/goi-y-ma/may/anh", json={"anh": b64}).status_code == 401)
kt("anh sai loại = 400", cl.post("/goi-y-ma/may/anh", headers=h, json={"anh": b64, "mime": "text/html"}).status_code == 400)
ga_goc = ga.image_vision if hasattr(ga, "image_vision") else None
import image_vision
goc_ai = image_vision.describe_data_urls
image_vision.describe_data_urls = ai_gia
rr = cl.post("/goi-y-ma/may/anh", headers=h, json={"anh": b64, "mime": "image/jpeg"})
image_vision.describe_data_urls = goc_ai
kt("HTTP trả ứng viên theo ảnh", rr.status_code == 200 and rr.json()["ung_vien"][0]["ma"] == "X8")
hs = rr.json()["hash"]
rr = cl.post("/goi-y-ma/may/xac-nhan", headers=h, json={"ma": "X8", "nguon": "anh", "khoa": hs})
kt("HTTP xác nhận ảnh thì học", rr.json().get("da_hoc_anh") is True)

print(f"goi_y_anh: {ok} đạt, {loi} lỗi")
sys.exit(1 if loi else 0)
