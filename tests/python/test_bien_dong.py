# -*- coding: utf-8 -*-
"""Biến động số dư (26.10.119): Casso Webhook V2 đẩy giao dịch ngân hàng vào MinMin. Chạy tay:

    python tests/run.py bien_dong

Phần đầu là test AN TOÀN, vì POST /bien-dong/casso/<mã> là đường mới được miễn cổng đăng nhập
(Casso không có cookie):
  1. Chỉ đúng POST + đúng một đoạn mã 20-80 ký tự được miễn. GET cùng đường, đường có thêm
     đoạn, dấu "/" cuối, mã ngắn và mọi đường /bien-dong khác vẫn 401 khi chưa đăng nhập.
  2. Sai mã -> 404 và tính vào giới hạn sai theo IP; chưa có khoá / sai chữ ký -> 401.
Sau đó: chữ ký mẫu chính thức của Casso, lưu, chống báo trùng, lọc tiền ra / ngưỡng, giao dịch
thử, trần thân, cài đặt không lộ khoá, nơi nhận thêm, đổi mã, câu báo, plugin bien-dong.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-biendong-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ.setdefault("BRAINS_DIR", tempfile.mkdtemp(prefix="javis-biendong-brains-"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI                 # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402
import main                                 # noqa: E402
import bien_dong                            # noqa: E402
import routes.bien_dong as rbd              # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


KEY = "mgExMrjj4i7a1p8Cs6LmFbpCd8lbw4sSX4LZXPag7TKazeIogtR90tvWYTkwQbvs"
MAU = {"error": 0, "data": {
    "id": 0, "reference": "MA_GIAO_DICH_THU_NGHIEM", "description": "giao dich thu nghiem",
    "amount": 599000, "runningBalance": 25000000, "transactionDateTime": "2024-10-03 15:06:37",
    "accountNumber": "88888888", "bankName": "VPBank", "bankAbbreviation": "VPB",
    "virtualAccountNumber": "", "virtualAccountName": "", "counterAccountName": "NGUYEN VAN A",
    "counterAccountNumber": "8888888888", "counterAccountBankId": "970415",
    "counterAccountBankName": "VietinBank"}}
MAU_HEADER = ("t=1727948258788,v1=ed0a4bd2e826d5cb69988cdb141e6c1a080e21f3b57eb72cd78192220042b9e7"
              "dde0868fc667faea8e224900fa7904e7c88dfa098032fb2d6b6996856e8b7ff3")


def ky(body, key=KEY, t=None, ascii_=True):
    t = int(time.time() * 1000) if t is None else t
    than = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii_)
    return f"t={t},v1=" + hmac.new(key.encode(), f"{t}.{than}".encode("utf-8"), hashlib.sha512).hexdigest()


def gd(gid, so_tien, mo_ta="CK mua ao HALIMI", tk="19036688886688"):
    return {"error": 0, "data": {
        "id": gid, "reference": f"FT{gid}", "description": mo_ta, "amount": so_tien,
        "runningBalance": 25000000,
        "transactionDateTime": datetime.now(bien_dong._tz()).strftime("%Y-%m-%d %H:%M:%S"),
        "accountNumber": tk, "bankName": "Techcombank", "bankAbbreviation": "TCB",
        "counterAccountName": "TRAN THI B", "counterAccountNumber": "0123456789",
        "counterAccountBankName": "Vietcombank"}}


def raw_post(c, url, body, sig=None, ascii_=True):
    data = json.dumps(body, ensure_ascii=ascii_).encode("utf-8")
    h = {"content-type": "application/json"}
    if sig is not None:
        h["x-casso-signature"] = sig
    return c.post(url, content=data, headers=h)


# ============ 1. Cổng đăng nhập BẬT: chỉ POST /bien-dong/casso/<mã> lọt qua ============
cl = TestClient(main.app, base_url="http://localhost")
_gate_goc = main.cfgmod.gate_active
main.cfgmod.gate_active = lambda: True
MA_GIA = "A" * 32
r = cl.post(f"/bien-dong/casso/{MA_GIA}", json={"error": 0, "data": {}})
check("bật cổng, POST /bien-dong/casso/<mã đúng dạng> lọt hàng rào, endpoint trả 404 (mã sai)",
      r.status_code == 404 and not r.json().get("auth_required"), (r.status_code, r.text))
for m, d in (("GET", f"/bien-dong/casso/{MA_GIA}"), ("PUT", f"/bien-dong/casso/{MA_GIA}"),
             ("POST", f"/bien-dong/casso/{MA_GIA}/x"), ("POST", f"/bien-dong/casso/{MA_GIA}/"),
             ("POST", "/bien-dong/casso/ngan"), ("POST", "/bien-dong/casso/" + "A" * 81),
             ("POST", "/bien-dong/casso/"), ("POST", f"/bien-dong/casso/{'A' * 30}.x"),
             ("GET", "/bien-dong"), ("GET", "/bien-dong/giao-dich"), ("GET", "/bien-dong/cai-dat"),
             ("POST", "/bien-dong/cai-dat"), ("POST", "/bien-dong/doi-token"), ("POST", "/bien-dong/thu"),
             ("POST", f"/bien-dong/xcasso/{MA_GIA}"), ("POST", f"/x/bien-dong/casso/{MA_GIA}")):
    rr = cl.request(m, d)
    check(f"bật cổng, {m} {d[:60]} vẫn cần đăng nhập (401 của hàng rào)",
          rr.status_code == 401 and rr.json().get("auth_required") is True, (rr.status_code, rr.text[:80]))
check("hằng miễn đăng nhập của main khớp module route", main._BIEN_DONG_CONG_KHAI == rbd.LOI_VAO_CONG_KHAI
      and main._BIEN_DONG_CONG_KHAI[1] == "POST")
check("không đưa /bien-dong vào danh sách công khai",
      not any(p.startswith("/bien") for p in main._AUTH_PUBLIC_PREFIX + main._AUTH_PUBLIC_EXACT))
main.cfgmod.gate_active = lambda: False
rbd._SAI.clear()

# ============ 2. Nối deps giả để đếm tin báo ============
BAO, GUI = [], []


async def _bao(text):
    BAO.append(text)


async def _gui(dich, text):
    GUI.append((dich, text))
    return True, ""

ZALO_OK = []
app = FastAPI()
rbd.register(app, rbd.BienDongDeps(dashboard_dir=Path(ROOT) / "dashboard", bao_chu=_bao, gui_kenh=_gui,
                                   ds_telegram=lambda: ["111", "-100222"], ds_zalo=lambda: list(ZALO_OK)))


def cho(n_bao, giay=2.0):
    het = time.time() + giay
    while time.time() < het and len(BAO) < n_bao:
        time.sleep(0.02)
    time.sleep(0.05)


with TestClient(app) as tc:
    cd = tc.get("/bien-dong/cai-dat").json()
    URL = cd["duong_dan"]
    check("cài đặt: có đường webhook /bien-dong/casso/<mã>, chưa có khoá, không có trường khoá",
          URL.startswith("/bien-dong/casso/") and len(URL) > 40 and cd["da_co_khoa"] is False
          and "khoa" not in cd, cd)
    check("cài đặt mặc định: chỉ tiền vào, ngưỡng 0", cd["chi_tien_vao"] is True and cd["nguong_toi_thieu"] == 0)
    check("mã sinh ra khớp mẫu hàng rào", main._BIEN_DONG_CONG_KHAI_RE.fullmatch(URL) is not None)

    b = gd(101, 599000)
    r = raw_post(tc, URL, b, ky(b))
    check("chưa có khoá -> 401 kể cả chữ ký đúng", r.status_code == 401, r.text)

    r = tc.post("/bien-dong/cai-dat", json={"khoa": KEY})
    check("lưu khoá: da_co_khoa, không trả khoá", r.status_code == 200 and r.json()["da_co_khoa"] is True
          and KEY not in r.text, r.text)
    tep = (Path(_STATE) / "bien_dong_cai_dat.json").read_text(encoding="utf-8")
    check("khoá lưu đã mã hoá (không có nguyên văn trong file)", KEY not in tep and '"khoa": "' in tep)
    check("GET cài đặt không lộ khoá", KEY not in tc.get("/bien-dong/cai-dat").text)
    check("GET /settings của MinMin không lộ khoá", KEY not in cl.get("/settings").text)
    check("lay_khoa giải mã được", bien_dong.lay_khoa() == KEY)
    r = tc.post("/bien-dong/cai-dat", json={"khoa": "", "chi_tien_vao": True})
    check("khoá rỗng trong patch -> giữ khoá cũ", r.json()["da_co_khoa"] is True and bien_dong.lay_khoa() == KEY)

    # ---- chữ ký
    check("chữ ký mẫu chính thức của Casso đúng", bien_dong.xac_thuc_chu_ky(MAU_HEADER, MAU, KEY))
    check("mẫu chính thức: sai khoá -> sai", not bien_dong.xac_thuc_chu_ky(MAU_HEADER, MAU, KEY + "x"))
    sua = json.loads(json.dumps(MAU)); sua["data"]["amount"] = 599001
    check("mẫu chính thức: sửa số tiền -> sai", not bien_dong.xac_thuc_chu_ky(MAU_HEADER, sua, KEY))
    viet = gd(7, 120000, mo_ta="Chuyển khoản mua váy HALIMI đơn 123")
    check("nội dung tiếng Việt, ký kiểu JSON.stringify (không thoát) -> đúng",
          bien_dong.xac_thuc_chu_ky(ky(viet, ascii_=False), viet, KEY))
    check("nội dung tiếng Việt, ký kiểu json.dumps mặc định -> đúng",
          bien_dong.xac_thuc_chu_ky(ky(viet, ascii_=True), viet, KEY))
    for h in ("", "v1=abc", "t=abc,v1=" + "0" * 128, "t=1,v1=zz", "rac", "t=1727948258788"):
        check(f"header hỏng {h[:20]!r} -> sai", not bien_dong.xac_thuc_chu_ky(h, MAU, KEY))
    r = raw_post(tc, URL, b)
    check("thiếu chữ ký -> 401", r.status_code == 401)
    r = raw_post(tc, URL, b, "t=1,v1=xyz")
    check("chữ ký hỏng -> 401", r.status_code == 401)
    r = raw_post(tc, URL, b, ky(b, key="khoa-khac"))
    check("ký bằng khoá khác -> 401", r.status_code == 401)
    r = raw_post(tc, URL, b, ky(b, t=int((time.time() - 5 * 86400) * 1000)))
    check("chữ ký quá cũ (5 ngày) -> 401", r.status_code == 401)
    r = raw_post(tc, URL, MAU, MAU_HEADER)
    check("mẫu Casso 2024 gửi lại qua HTTP -> 401 vì quá hạn", r.status_code == 401)
    check("chưa báo gì khi chữ ký sai", BAO == [])

    # ---- giao dịch thật
    r = raw_post(tc, URL, b, ky(b))
    check("giao dịch hợp lệ -> 200 {success: true}", r.status_code == 200 and r.json() == {"success": True}, r.text)
    cho(1)
    check("báo đúng 1 lần", len(BAO) == 1, BAO)
    check("câu báo: số tiền, nội dung, người chuyển, số dư",
          "+599.000đ" in BAO[0] and "CK mua ao HALIMI" in BAO[0] and "TRAN THI B" in BAO[0]
          and "25.000.000đ" in BAO[0], BAO[0])
    check("câu báo che số tài khoản còn 4 số cuối",
          "6688" in BAO[0] and "19036688886688" not in BAO[0] and "0123456789" not in BAO[0], BAO[0])
    check("câu báo không có em dash / en dash", "\u2014" not in BAO[0] and "\u2013" not in BAO[0])
    r = raw_post(tc, URL, b, ky(b))
    cho(2, 0.3)
    check("Casso gửi lại cùng id -> 200, không báo lại", r.status_code == 200 and r.json() == {"success": True}
          and len(BAO) == 1, (r.text, len(BAO)))
    ds = tc.get("/bien-dong/giao-dich").json()["giao_dich"]
    check("trùng id không lưu hai lần", [g["id"] for g in ds].count("101") == 1, ds)
    kho = (Path(_STATE) / "bien_dong.json").read_text(encoding="utf-8")
    check("kho không giữ số tài khoản đầy đủ", "19036688886688" not in kho and "0123456789" not in kho)

    ra = gd(102, -50000)
    r = raw_post(tc, URL, ra, ky(ra))
    cho(2, 0.3)
    check("tiền ra: lưu nhưng không báo (chỉ tiền vào)", r.status_code == 200 and len(BAO) == 1)
    tc.post("/bien-dong/cai-dat", json={"nguong_toi_thieu": 100000})
    nho = gd(103, 50000)
    raw_post(tc, URL, nho, ky(nho))
    cho(2, 0.3)
    check("dưới ngưỡng: không báo", len(BAO) == 1)
    lon = gd(104, 200000)
    raw_post(tc, URL, lon, ky(lon))
    cho(2)
    check("trên ngưỡng: báo", len(BAO) == 2 and "+200.000đ" in BAO[-1], BAO[-1:])

    # ---- giao dịch thử (id 0): luôn báo, gắn nhãn, không tính vào tổng
    thu = gd(0, 1000)
    raw_post(tc, URL, thu, ky(thu))
    cho(3)
    check("id 0: báo kèm '(thử nghiệm)' (kể cả dưới ngưỡng)", len(BAO) == 3 and "(thử nghiệm)" in BAO[-1], BAO[-1:])
    raw_post(tc, URL, thu, ky(thu))
    cho(4)
    check("bấm Gọi thử lần hai vẫn báo", len(BAO) == 4)

    # ---- trần thân, JSON hỏng
    to = gd(105, 1000, mo_ta="x" * 70000)
    r = raw_post(tc, URL, to, ky(to))
    check("thân quá 64KB -> 413", r.status_code == 413, r.status_code)
    r = tc.post(URL, content=b"{hong", headers={"content-type": "application/json", "x-casso-signature": ky({})})
    check("JSON hỏng -> 400", r.status_code == 400, r.status_code)
    r = raw_post(tc, URL, {"error": 0, "data": "x"}, ky({"error": 0, "data": "x"}))
    check("data không phải object -> 400", r.status_code == 400, r.status_code)

    # ---- danh sách và tổng
    j = tc.get("/bien-dong/giao-dich").json()
    hn = j["hom_nay"]
    check("tổng hôm nay: vào 599.000 + 50.000 + 200.000 (không tính giao dịch thử)",
          hn["tong_vao"] == 849000 and hn["so_gd_vao"] == 3 and hn["tong_ra"] == 50000, hn)
    co_thu = [g for g in j["giao_dich"] if g.get("thu_nghiem")]
    check("giao dịch thử được lưu, gắn cờ thu_nghiem", len(co_thu) == 2, co_thu)
    check("lọc chỉ tiền vào", all(g["so_tien"] > 0 for g in tc.get("/bien-dong/giao-dich?chi_vao=true").json()["giao_dich"]))
    check("tìm theo người chuyển", len(tc.get("/bien-dong/giao-dich?tim=tran%20thi").json()["giao_dich"]) >= 4)
    check("mốc ngày sai -> 400", tc.get("/bien-dong/giao-dich?tu_ngay=hom-qua").status_code == 400)

    # ---- nơi nhận thêm
    for sai in (["555"], ["zalo:ab cd"], ["<script>"], ["zalo:"], "111,999", ["telegram:111"]):
        r = tc.post("/bien-dong/cai-dat", json={"noi_nhan_them": sai})
        check(f"nơi nhận sai {sai!r} -> 400", r.status_code == 400 and r.json().get("error"), r.text)
    check("bị từ chối thì không ghi gì", tc.get("/bien-dong/cai-dat").json()["noi_nhan_them"] == [])
    r = tc.post("/bien-dong/cai-dat", json={"noi_nhan_them": ["-100222", "zalo:999", "-100222"]})
    check("nơi nhận hợp lệ (nhóm Telegram trong whitelist + zalo) -> lưu, bỏ trùng",
          r.status_code == 200 and r.json()["noi_nhan_them"] == ["-100222", "zalo:999"], r.text)
    ZALO_OK.append("777")
    r = tc.post("/bien-dong/cai-dat", json={"noi_nhan_them": ["zalo:999"]})
    check("bot Zalo có whitelist: id Zalo ngoài whitelist -> 400", r.status_code == 400, r.text)
    ZALO_OK.clear()
    tc.post("/bien-dong/cai-dat", json={"nguong_toi_thieu": 0})
    t2 = gd(106, 300000)
    raw_post(tc, URL, t2, ky(t2))
    cho(5)
    time.sleep(0.1)
    check("báo chủ + gửi từng nơi nhận thêm", len(BAO) == 5 and sorted(d for d, _ in GUI) == ["-100222", "zalo:999"]
          and all("+300.000đ" in t for _, t in GUI), (len(BAO), GUI))
    check("nguong âm / chữ -> 400", tc.post("/bien-dong/cai-dat", json={"nguong_toi_thieu": -1}).status_code == 400
          and tc.post("/bien-dong/cai-dat", json={"nguong_toi_thieu": "abc"}).status_code == 400)

    # ---- Gửi thử: cùng đường báo, không lưu
    so_truoc = len(tc.get("/bien-dong/giao-dich").json()["giao_dich"])
    GUI.clear()
    r = tc.post("/bien-dong/thu")
    check("Gửi thử: báo chủ (thử nghiệm) + nơi nhận thêm, không lưu",
          r.status_code == 200 and "(thử nghiệm)" in BAO[-1] and len(GUI) == 2
          and len(tc.get("/bien-dong/giao-dich").json()["giao_dich"]) == so_truoc, (r.text, GUI))

    # ---- đổi mã: đường cũ chết
    r = tc.post("/bien-dong/doi-token")
    URL2 = r.json()["duong_dan"]
    check("đổi mã -> đường mới khác", URL2 != URL and URL2.startswith("/bien-dong/casso/"))
    t3 = gd(107, 10000)
    check("đường cũ -> 404", raw_post(tc, URL, t3, ky(t3)).status_code == 404)
    check("đường mới -> 200", raw_post(tc, URL2, t3, ky(t3)).status_code == 200)
    rbd._SAI.clear()

    # ---- chống dò mã
    for _ in range(20):
        raw_post(tc, "/bien-dong/casso/" + "B" * 32, t3, ky(t3))
    check("sai mã 20 lần -> 429 (kể cả mã đúng, trong 10 phút)",
          raw_post(tc, URL2, t3, ky(t3)).status_code == 429)
    rbd._SAI.clear()

    check("trang /bien-dong trả HTML", tc.get("/bien-dong").status_code == 200
          and "Biến động số dư" in tc.get("/bien-dong").text)

# ============ 3. Câu báo và định dạng số ============
check("tien(): chấm ngăn nghìn", bien_dong.tien(1234567) == "1.234.567đ" and bien_dong.tien(0) == "0đ"
      and bien_dong.tien(-5000) == "5.000đ")
check("cuoi4", bien_dong.cuoi4("1903 6688 8866 88") == "6688" and bien_dong.cuoi4("") == "")
g = bien_dong.chuan_hoa(gd(9, -75000)["data"])
cau = bien_dong.cau_bao(g)
check("tiền ra: '-75.000đ ra khỏi', 'Người nhận'", cau.startswith("💸 -75.000đ ra khỏi") and "Người nhận" in cau, cau)
bien_dong.luu_cai_dat({"nhan_tk": {"19036688886688": "TK shop HALIMI"}})
cau = bien_dong.cau_bao(bien_dong.chuan_hoa(gd(10, 5000)["data"]))
check("nhãn tài khoản thay tên ngân hàng", "TK shop HALIMI (Techcombank 6688)" in cau, cau)

# ============ 4. Plugin bien-dong ============
import plugins_host  # noqa: E402

plugins_host.invalidate()
desc = {d["slug"]: d for d in plugins_host.describe(None)}
check("plugin bien-dong có mặt, bật sẵn, chỉ đọc",
      "bien-dong" in desc and desc["bien-dong"]["enabled"] and desc["bien-dong"]["loaded"]
      and desc["bien-dong"]["min_mode"] == "readonly", desc.get("bien-dong"))
tools, route = plugins_host.plugin_tools("suggest", None)
check("tool bien_dong_doc chạy được ở chế độ suggest", "bien_dong_doc" in {t["fn"] for t in tools})
out = json.loads(asyncio.run(route["bien_dong_doc"]["call"]({})))
check("hôm nay: tổng vào 599.000 + 50.000 + 200.000 + 300.000 + 10.000, không tính giao dịch thử",
      out["tong"]["tong_vao"] == 1159000 and out["tong"]["so_gd_vao"] == 5 and out["tong"]["tong_ra"] == 50000
      and not any(x["thu_nghiem"] for x in out["giao_dich"]), out["tong"])
out = json.loads(asyncio.run(route["bien_dong_doc"]["call"]({"chi_tien_vao": True, "limit": 2})))
check("limit chỉ cắt danh sách, tổng vẫn tính đủ", len(out["giao_dich"]) == 2 and out["tong"]["tong_vao"] == 1159000
      and out["tong"]["tong_ra"] == 0, out["tong"])
out = json.loads(asyncio.run(route["bien_dong_doc"]["call"]({"tim": "khong-co-ai"})))
check("tìm không thấy -> tổng 0", out["tong"]["so_gd"] == 0)
out = asyncio.run(route["bien_dong_doc"]["call"]({"tu_ngay": "sai"}))
check("mốc sai -> ERROR, không nổ", out.startswith("ERROR"), out)
check("không lộ số tài khoản đầy đủ qua tool",
      "19036688886688" not in asyncio.run(route["bien_dong_doc"]["call"]({})))

# ============ 4b. Gửi nhóm nhân viên: kiểm lại whitelist ngay lúc gửi ============
# `_gui_qua_kenh` gặp id lạ thì rơi về người khác (Telegram -> chủ, Zalo -> mọi id), nên id bị
# gỡ khỏi danh sách cho phép SAU khi lưu cài đặt phải bị bỏ chứ không được gửi lệch.
_da_gui = []


async def _gui_gia(dich, text, **kw):
    _da_gui.append(dich)
    return True, ""

_goc_gui, _goc_doc = main._gui_qua_kenh, main.cfgmod.read_settings
main._gui_qua_kenh = _gui_gia
main.cfgmod.read_settings = lambda: {"telegram": {"chat_id": "111,-100222"}, "zalo_bot": {"chat_id": "z1"}}
try:
    kq_ok = asyncio.run(main._bien_dong_gui_kenh("-100222", "x"))
    kq_tg = asyncio.run(main._bien_dong_gui_kenh("-100999", "x"))
    kq_z = asyncio.run(main._bien_dong_gui_kenh("zalo:z9", "x"))
    kq_z_ok = asyncio.run(main._bien_dong_gui_kenh("zalo:z1", "x"))
finally:
    main._gui_qua_kenh, main.cfgmod.read_settings = _goc_gui, _goc_doc
check("gửi được tới nhóm Telegram còn trong whitelist", kq_ok[0] and "-100222" in _da_gui)
check("id Telegram đã bị gỡ khỏi whitelist -> bỏ, không rơi về chủ", not kq_tg[0] and "-100999" not in _da_gui)
check("id Zalo không còn trong danh sách -> bỏ, không gửi mọi id", not kq_z[0] and "zalo:z9" not in _da_gui)
check("id Zalo còn trong danh sách -> gửi", kq_z_ok[0] and "zalo:z1" in _da_gui)

# ============ 5. Không có em dash / en dash trong file mới ============
for p in ("server/bien_dong.py", "server/routes/bien_dong.py", "dashboard/bien-dong/index.html",
          "dashboard/bien-dong/bien-dong.js", "dashboard/bien-dong/bien-dong.css",
          "system/plugins/bien-dong/plugin.py", "system/plugins/bien-dong/plugin.yaml"):
    s = (Path(ROOT) / p).read_text(encoding="utf-8")
    check(f"{p}: không em dash / en dash", "\u2014" not in s and "\u2013" not in s)

main.cfgmod.gate_active = _gate_goc
print()
if _fails:
    print(f"ĐỎ {len(_fails)} phép thử:")
    for f in _fails:
        print("  - " + f)
    sys.exit(1)
print("Tất cả phép thử Biến động số dư đều xanh.")
