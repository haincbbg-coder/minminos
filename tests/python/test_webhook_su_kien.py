"""Nền tảng sự kiện webhook (26.10.273): lưu bền qua khởi động lại, chống trùng, lọc, chuyển tiếp
không cần AI, thử lại kể cả 429, chạy lại bằng cấu hình hiện tại, chữ ký Stripe/GitHub/Shopify/
Systeme.io/HMAC, che dữ liệu khách và mã nhân viên (dạng đơn POSCake thật), khoá không lộ.

    python tests/run.py webhook_su_kien
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import base64
import hashlib
import hmac
import json
import os
import tempfile
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-whsk-")
import webhook_chay as ch  # noqa: E402
import webhook_ky as ky  # noqa: E402
import webhook_su_kien as sk  # noqa: E402
import webhooks as wh  # noqa: E402

fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        fails.append(n)


# ---------------------------------------------------------------- lưu bền + trùng
r = sk.nhan("wh_a", b'{"id": 1}', "application/json", {}, "h:1", 24)
check("lưu được", not r["trung"] and sk.lay(r["id"])["trang_thai"] == sk.CHO)
check("cùng khoá là trùng", sk.nhan("wh_a", b'{"id": 1}', "", {}, "h:1", 24)["trung"])
check("webhook khác không trùng", not sk.nhan("wh_b", b'{"id": 1}', "", {}, "h:1", 24)["trung"])
check("hết cửa sổ thì nhận lại",
      not sk.nhan("wh_a", b"x", "", {}, "h:1", 24, now=time.time() + 25 * 3600)["trung"])
check("khoá ưu tiên mã nhà gửi", sk.khoa_giao({"x-request-id": "r"}, b"x", "github:9") == "p:github:9")
check("khoá theo header quen", sk.khoa_giao({"x-request-id": "r"}, b"x") == "h:r")
check("không header thì băm thân", sk.khoa_giao({}, b"x").startswith("b:"))
viec = sk.nhan_viec(gioi_han=10)
check("nhận việc chuyển sang đang chạy", viec and all(sk.lay(v["id"])["trang_thai"] == sk.DANG_CHAY for v in viec))
# giả lập tắt máy: đóng kết nối, mở lại
sk.dong_db()
n = sk.phuc_hoi_sau_khoi_dong()
check("sự kiện kẹt lúc tắt máy thành bị chặn, không tự gửi lại",
      n == len(viec) and all(sk.lay(v["id"])["trang_thai"] == sk.BI_CHAN for v in viec))
check("dòng thời gian ghi lý do", any(t["buoc"] == "chan" for t in sk.dong_thoi_gian(viec[0]["id"])))
check("chạy lại mọi sự kiện bị chặn", sk.chay_lai_bi_chan("wh_a") >= 1
      and sk.lay(viec[0]["id"])["trang_thai"] in (sk.CHO, sk.BI_CHAN))
if os.name != "nt":
    check("file kho chỉ chủ đọc được", (os.stat(sk.file_db()).st_mode & 0o077) == 0)
else:
    print("POSIX mode check is not applicable to Windows ACLs")

# ---------------------------------------------------------------- bộ lọc
doc = {"event_type": "create", "status": 0, "items": [{"variation_info": {"name": "Đầm lụa xanh"}}]}
L = sk.chuan_loc([{"duong": "event_type", "phep": "bang", "gia_tri": "create"},
                  {"duong": "items[*].variation_info.name", "phep": "chua", "gia_tri": "đầm"}])
check("lọc khớp đơn POSCake", sk.xet_loc(L, doc)[0])
check("sai trạng thái thì bỏ qua", not sk.xet_loc(sk.chuan_loc([{"duong": "status", "gia_tri": 1}]), doc)[0])
ok, ly = sk.xet_loc(sk.chuan_loc([{"duong": "items[*].name", "phep": "chua", "gia_tri": "x"}]), doc)
check("thiếu trường thì bỏ qua và nói rõ", not ok and "thiếu trường" in ly, ly)
check("phép trong", sk.xet_loc(sk.chuan_loc([{"duong": "status", "phep": "trong", "gia_tri": "0,1"}]), doc)[0])
try:
    sk.chuan_loc([{"duong": "a", "phep": "eval"}])
    check("phép lạ bị từ chối", False)
except ValueError:
    check("phép lạ bị từ chối", True)

# ---------------------------------------------------------------- chữ ký
K = "whsec_khoa_bi_mat_123"
than = b'{"id":"evt_1","type":"charge.succeeded"}'
ts = str(int(time.time()))
sig = hmac.new(K.encode(), ts.encode() + b"." + than, hashlib.sha256).hexdigest()
check("Stripe đúng", ky.kiem({"kieu": "stripe"}, K, {"stripe-signature": f"t={ts},v1=sai,v1={sig}"}, than)[0])
check("Stripe quá cũ bị chặn", not ky.kiem({"kieu": "stripe"}, K, {"stripe-signature": f"t={ts},v1={sig}"},
                                           than, now=time.time() + 400)[0])
check("Stripe sửa thân bị chặn", not ky.kiem({"kieu": "stripe"}, K, {"stripe-signature": f"t={ts},v1={sig}"},
                                             than + b" ")[0])
gh = "sha256=" + hmac.new(K.encode(), than, hashlib.sha256).hexdigest()
check("GitHub đúng", ky.kiem({"kieu": "github"}, K, {"x-hub-signature-256": gh}, than)[0])
check("GitHub sai khoá", not ky.kiem({"kieu": "github"}, "khac_khoa_123", {"x-hub-signature-256": gh}, than)[0])
sh = base64.b64encode(hmac.new(K.encode(), than, hashlib.sha256).digest()).decode()
check("Shopify đúng", ky.kiem({"kieu": "shopify"}, K, {"x-shopify-hmac-sha256": sh}, than)[0])
sy = hmac.new(K.encode(), than, hashlib.sha256).hexdigest()
check("Systeme.io đúng trên thân gốc", ky.kiem({"kieu": "systeme_io"}, K, {"x-webhook-signature": sy}, than)[0])
cfg = ky.chuan_cau_hinh({"kieu": "hmac_sha256", "header": "X-Sig", "ma_hoa": "hex", "tien_to": "sha256="})
check("HMAC tuỳ chỉnh đúng", ky.kiem(cfg, K, {"x-sig": "sha256=" + sy.upper()}, than)[0])
check("thiếu khoá thì từ chối (fail closed)", not ky.kiem({"kieu": "github"}, "", {"x-hub-signature-256": gh}, than)[0])
check("none luôn qua", ky.kiem({"kieu": "none"}, "", {}, than)[0])
for bad in ({"kieu": "poscake"}, {"kieu": "md5"}, {"kieu": "hmac_sha256", "header": "content-type"}):
    try:
        ky.chuan_cau_hinh(bad)
        check(f"cấu hình sai bị từ chối {bad}", False)
    except ky.LoiCauHinh:
        check(f"cấu hình sai bị từ chối {bad['kieu']}", True)
check("mã lần giao GitHub", ky.ma_lan_giao("github", {"x-github-delivery": "d1"}, {}) == "github:d1")
check("header lưu không có chữ ký", "x-hub-signature-256" not in ky.header_luu({"x-hub-signature-256": gh, "user-agent": "u"}))
check("lý do lỗi không chứa khoá", K not in json.dumps(ky.kiem({"kieu": "github"}, K, {}, than)))

# ---------------------------------------------------------------- che (dạng đơn POSCake thật)
poscake = {
    "event_type": "create", "id": 739, "system_id": 739, "shop_id": 123, "status": 0, "status_name": "new",
    "cod": 297000, "total_quantity": 1, "updated_at": "2026-10-22T03:10:25",
    "bill_full_name": "Nguyễn Thị Lan", "bill_phone_number": "0912345678", "bill_email": "lan@gmail.com",
    "payment_link": "https://pos.pages.fm/pay?token=abc",
    "creator": {"id": "staff-uuid-1111", "name": "NV Hoa", "fb_id": "1000123"},
    "assigning_seller_id": "staff-uuid-2222", "editor_id": "staff-uuid-3333",
    "status_history": [{"status": 0, "editor": {"id": "staff-uuid-4444", "name": "NV B"}, "editor_id": "staff-uuid-4444"}],
    "shipping_address": {"full_address": "12 Lê Lợi, Q1", "phone_number": "0988777666", "full_name": "Lan"},
    "items": [{"quantity": 1, "variation_info": {"name": "Đầm lụa xanh", "retail_price": 297000, "display_id": "D01"}}],
    "note": "Gọi 0912345678 trước khi giao",
}
m = sk.che(poscake)
txt = json.dumps(m, ensure_ascii=False)
check("giữ mã đơn, trạng thái, tiền, thời gian", m["id"] == 739 and m["status"] == 0 and m["cod"] == 297000
      and m["updated_at"] == "2026-10-22T03:10:25" and m["event_type"] == "create")
check("giữ tên sản phẩm và giá", m["items"][0]["variation_info"]["name"] == "Đầm lụa xanh"
      and m["items"][0]["variation_info"]["retail_price"] == 297000)
for lo in ("Nguyễn Thị Lan", "0912345678", "lan@gmail.com", "12 Lê Lợi", "0988777666", "pages.fm", "token=abc"):
    check(f"che {lo}", lo not in txt)
for nv in ("staff-uuid-1111", "staff-uuid-2222", "staff-uuid-3333", "staff-uuid-4444", "NV Hoa", "1000123"):
    check(f"che mã/tên nhân viên {nv}", nv not in txt)
check("khoá bí mật thành ••••", sk.che({"api_token": "abc"})["api_token"] == "••••")
check("thân văn bản che số điện thoại", "0912345678" not in sk.xem_che(b"goi 0912345678 nhe", "text/plain"))

# ---------------------------------------------------------------- bộ chạy: lọc, chuyển tiếp, thử lại, 429
HOOK = {"id": "wh_r", "ten": "Đơn Pancake", "viec": "Báo chủ", "muc_quyen": "suggest", "brain": "brain",
        "loc": sk.chuan_loc([{"duong": "event_type", "gia_tri": "create"}]),
        "hanh_dong": [{"id": "ai", "loai": "ai"}, {"id": "sheet", "loai": "chuyen_tiep", "lap_an_toan": True, "url": "https://script.google.com/macros/s/AKfy_rieng/exec"}]}
GUI, AI, BAO = [], [], []
TRA = {"ma": [200], "h": {}}


async def gui(url, than, hd):
    GUI.append((url, than, dict(hd)))
    return TRA["ma"].pop(0) if len(TRA["ma"]) > 1 else TRA["ma"][0], TRA["h"]


async def chay_ai(brain, prompt, muc):
    AI.append(prompt)
    return "xong", ""


async def bao(ten, text):
    BAO.append(text)


async def kiem_ok(url):
    return ""

NOW = [time.time()]
bc = ch.BoChay(ch.ChayDeps(lay_hook=lambda i: HOOK if i == "wh_r" else None, chay_ai=chay_ai, bao_chu=bao,
                           gui_http=gui, kiem_dia_chi=kiem_ok, clock=lambda: NOW[0]))


def ev(than):
    sid = sk.nhan("wh_r", json.dumps(than).encode(), "application/json", {}, "", 24, now=NOW[0])["id"]
    return sid


async def chay_het():
    for _ in range(10):
        if not await bc.mot_nhip():
            break

s1 = ev({"event_type": "update", "id": 1})
asyncio.run(chay_het())
check("không khớp lọc thì bỏ qua, không gọi AI", sk.lay(s1)["trang_thai"] == sk.BO_QUA and not AI and not GUI)
s2 = ev({"event_type": "create", "id": 2})
asyncio.run(chay_het())
check("khớp lọc thì chạy AI và chuyển tiếp", sk.lay(s2)["trang_thai"] == sk.XONG and len(AI) == 1 and len(GUI) == 1)
check("chuyển tiếp gửi nguyên thân và mã lần giao cố định",
      GUI[0][1] == json.dumps({"event_type": "create", "id": 2}).encode()
      and GUI[0][2]["X-MinMin-Delivery"] == f"{s2}.sheet")
check("báo chủ kết quả AI", BAO and "xong" in BAO[-1])

TRA["ma"], TRA["h"] = [429], {"Retry-After": "900"}
s3 = ev({"event_type": "create", "id": 3})
asyncio.run(chay_het())
e3 = sk.lay(s3)
check("429 thì hẹn thử lại, theo Retry-After", e3["trang_thai"] == sk.THU_LAI and e3["chay_luc"] >= NOW[0] + 899, e3)
check("AI đã xong không chạy lại khi thử lại", e3["giao"]["ai"]["tt"] == "xong")
n_ai = len(AI)
TRA["ma"], TRA["h"] = [200], {}
NOW[0] += 1000
asyncio.run(chay_het())
check("lần thử sau xong, AI không chạy hai lần", sk.lay(s3)["trang_thai"] == sk.XONG and len(AI) == n_ai)
check("lần gửi lại giữ cùng mã lần giao", GUI[-1][2]["X-MinMin-Delivery"] == GUI[-2][2]["X-MinMin-Delivery"])

TRA["ma"] = [500]
s4 = ev({"event_type": "create", "id": 4})
for _ in range(ch.LAN_THU_TOI_DA + 1):
    asyncio.run(chay_het())
    NOW[0] += 8000
e4 = sk.lay(s4)
check("hết lượt thử thì bị chặn, giữ thân", e4["trang_thai"] == sk.BI_CHAN and b'"id": 4' in e4["than"], e4["ly_do"])
check("bị chặn thì báo chủ", any("bị chặn" in b for b in BAO))
TRA["ma"] = [404]
s5 = ev({"event_type": "create", "id": 5})
asyncio.run(chay_het())
check("4xx là lỗi hẳn, chặn ngay", sk.lay(s5)["trang_thai"] == sk.BI_CHAN)

# chạy lại với cấu hình HIỆN TẠI: bỏ hành động chuyển tiếp hỏng
HOOK["hanh_dong"] = [{"id": "ai", "loai": "ai"}]
check("chạy lại đưa về hàng chờ", sk.chay_lai(s5))
asyncio.run(chay_het())
check("chạy lại dùng cấu hình mới và xong", sk.lay(s5)["trang_thai"] == sk.XONG)


async def kiem_noi_bo(url):
    return await ch.kiem_dia_chi_cong_khai("https://localhost/x")

check("địa chỉ nội bộ bị chặn (SSRF)", asyncio.run(kiem_noi_bo("")) != "")
for bad in ([{"loai": "chuyen_tiep", "url": "http://a.com"}], [{"loai": "chuyen_tiep", "url": "https://a.com:8080/"}],
            [{"loai": "shell"}]):
    try:
        ch.chuan_hanh_dong(bad)
        check(f"hành động sai bị từ chối {bad}", False)
    except ValueError:
        check("hành động sai bị từ chối", True)
check("giao diện chỉ thấy tên máy của nơi chuyển tiếp", ch.an_url("https://script.google.com/macros/s/AKfy_rieng/exec")
      == "https://script.google.com/…")

# AI lỗi tạm (hết lượt) thì thử lại, lỗi hẳn thì chặn


async def ai_429(brain, prompt, muc):
    return "", "HTTP 429 rate limit"

bc.deps.chay_ai = ai_429
s6 = ev({"event_type": "create", "id": 6})
asyncio.run(chay_het())
check("AI bị 429 thì thử lại", sk.lay(s6)["trang_thai"] == sk.THU_LAI)

# ---------------------------------------------------------------- khoá ký mã hoá, không lộ qua API
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.webhooks as rw  # noqa: E402


async def ai_ok(b, p, m):
    return "ok", ""

app = FastAPI()
rw.register(app, rw.WebhooksDeps(chay_ai=ai_ok, tu_chay=False))
c = TestClient(app)
t = c.post("/webhooks", json={"ten": "GitHub", "viec": "Báo", "muc_quyen": "suggest"}).json()
wid = t["webhook"]["id"]
r = c.post("/webhooks/cap-nhat", json={"id": wid, "xac_thuc": {"kieu": "github"}, "khoa": K}).json()
check("lưu kiểu GitHub", r["ok"], r)
check("khoá không nằm trần trong kho", K not in open(wh.file_kho(), encoding="utf-8").read())
check("API không trả khoá", K not in json.dumps(c.get("/webhooks").json()) and
      c.get("/webhooks").json()["webhooks"][-1]["xac_thuc"]["co_khoa"] is True)
check("từ chối kiểu poscake", not c.post("/webhooks/cap-nhat", json={"id": wid, "xac_thuc": {"kieu": "poscake"}}).json()["ok"])
body = b'{"action":"opened"}'
sai = c.post("/hook/" + t["token"], content=body, headers={"content-type": "application/json",
                                                            "x-hub-signature-256": "sha256=00"})
check("chữ ký sai thì 401 và KHÔNG lưu", sai.status_code == 401 and not sk.danh_sach(wid))
dung_sig = "sha256=" + hmac.new(K.encode(), body, hashlib.sha256).hexdigest()
h = {"content-type": "application/json", "x-hub-signature-256": dung_sig, "x-github-delivery": "dlv-1"}
d1 = c.post("/hook/" + t["token"], content=body, headers=h).json()
check("chữ ký đúng thì lưu", d1.get("su_kien"))
d2 = c.post("/hook/" + t["token"], content=body + b" ", headers={**h, "x-hub-signature-256":
            "sha256=" + hmac.new(K.encode(), body + b" ", hashlib.sha256).hexdigest()}).json()
check("GitHub gửi lại cùng mã lần giao là trùng", d2.get("trung") is True)
ct = c.get("/webhooks/su-kien/chi-tiet", params={"sk": d1["su_kien"]}).json()["su_kien"]
check("chi tiết không lộ chữ ký hay khoá", dung_sig not in json.dumps(ct) and K not in json.dumps(ct)
      and "khoa_giao" not in ct)
check("chi tiết có dòng thời gian", ct["dong_thoi_gian"][0]["buoc"] == "nhan")
xt = c.post("/webhooks/xem-truoc", json={"id": wid, "than": '{"a": 1}'}).json()
check("xem trước không lưu gì", xt["ok"] and xt["se_chay"] and len(sk.danh_sach(wid)) == 1)
tt = c.get("/webhooks/tinh-trang").json()
check("tình trạng có hàng đợi và đếm 24 giờ", "hang_doi" in tt and wid in tt["hook"])
check("xoá webhook xoá luôn sự kiện", c.post("/webhooks/xoa", json={"id": wid}).json()["ok"] and not sk.danh_sach(wid))

print("PASS" if not fails else f"FAILED: {fails}")
raise SystemExit(1 if fails else 0)

