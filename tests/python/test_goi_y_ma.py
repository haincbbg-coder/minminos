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
r = g.phan_giai(ad_id="zz9", ad_text="Set đẹp lắm. Mã: V33 - mua 2 miễn ship")
kt("mã trong nội dung quảng cáo", r["ung_vien"] and r["ung_vien"][0]["ma"] == "V33" and r["ung_vien"][0]["bang_chung"][0]["nguon"] == "noi_dung")
kt("nội dung quảng cáo không mã thì rỗng", g.phan_giai(ad_text="Sét bộ thun in chữ phối bèo")["ung_vien"] == [])
r = g.phan_giai(ma_ro=["s26", "V33"])
kt("mã ghi rõ trong tin: có cả mã chưa nằm trong bảng", [u["ma"] for u in r["ung_vien"]] == ["S26", "V33"] and r["ung_vien"][0]["ton"] in (None, 0))
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

# --- tra.js (tiện ích) phải ra cùng kết quả với phan_giai
import shutil
import subprocess
import json as _j
if shutil.which("node"):
    js = ("require(%r);const b=%s;const r=mmTra(b,{text:'giá V33',ad_ids:['A1'],post_id:'pg_P9',ad_text:'mã V33',ma_ro:['S26']});"
          "console.log(JSON.stringify(r.map(x=>[x.ma,x.ton,x.bang_chung.length])))") % (
        str(ROOT / "apps" / "goi-y-ma" / "tra.js"), _j.dumps(g.xuat_bang()))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        kq_js = _j.loads(out.stdout.strip() or "[]")
    except ValueError:
        kq_js = []
    py = g.phan_giai(text="giá V33", ad_id="A1", post_id="P9", ad_text="mã V33", ma_ro=["S26"])["ung_vien"]
    kt("tra.js khớp Python", sorted(x[0] for x in kq_js) == sorted(u["ma"] for u in py) and len(kq_js) == 3)

# --- content.js: đọc đúng dữ liệu Pancake thật (ad_click, sticker/nút like không phải ảnh)
if shutil.which("node"):
    js = r"""
const listeners = {};
global.window = global; global.self = global;
global.addEventListener = (t, f) => { listeners[t] = f; };
global.document = { createElement: () => ({ set innerHTML(v) { this.textContent = String(v).replace(/<[^>]*>/g, ""); }, style: {} }), addEventListener() {}, body: null };
global.chrome = { runtime: { sendMessage: (m, r) => r({ ok: false }) } };
require(%r);
require(%r);
const T = window.__mmGyTest;
const ds = [
  { from: { id: "P" }, attachments: [{ type: "ad_click", ad_id: "120257403105160399", post_attachments: [{ description: "Sét bộ thun. Mã: V33 nhé", url: "https://content.pancake.vn/x/ad.jpg" }] }] },
  { from: { id: "K1" }, message: "Xin giá set", attachments: [] },
  { from: { id: "P" }, message: "MÃ : T145", attachments: [] },
  { from: { id: "K1" }, message: "BÁO GIÁ MÃ #S26", attachments: [] },
  { from: { id: "P" }, message: "Chị nhận mã giảm giá ạ, mã vận đơn ABC123", attachments: [] },
  { from: { id: "K1" }, attachments: [{ type: "sticker", id: "369239263222822", url: "https://statics.pancake.vn/cache.pancake.vn/stickers/369239263222822" }] },
  { from: { id: "K1" }, attachments: [{ type: "photo", url: "https://content.pancake.vn/x/anh.jpg", image_data: { width: 1080, height: 1920 } }] },
];
T.docMessages("https://pancake.vn/api/v1/pages/P/conversations/P_K1/messages?x=1", { messages: ds });
const h = T.hienTai();
console.log(JSON.stringify({ anh: h.anh, ad: h.ad_ids, txt: h.ad_text, adanh: h.ad_anh, ro: h.ma_ro })); process.exit(0);
""" % (str(ROOT / "apps" / "goi-y-ma" / "tra.js"), str(ROOT / "apps" / "goi-y-ma" / "content.js"))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        h = _j.loads(out.stdout.strip().splitlines()[-1])
    except Exception:
        h = {}
    kt("content.js bỏ sticker/nút like", h.get("anh") == ["https://content.pancake.vn/x/anh.jpg"])
    kt("content.js lấy mã ghi rõ trong tin (kể cả tin của shop), không bắt nhầm 'mã giảm giá'", sorted(h.get("ro", [])) == ["S26", "T145"])
    kt("content.js đọc ad_click", h.get("ad") == ["120257403105160399"] and "V33" in h.get("txt", "") and h.get("adanh", "").endswith("ad.jpg"))

# --- nạp dạng gọn và nạp từ file qua plugin
import asyncio
import importlib.util
from pathlib import Path
g.nap_sku([{"ma": "K1", "ten": "Áo K1", "ton": 5, "anh": ["http://a/k1.jpg"]}])
g.nap_sku(["K1:77", "Q9:61"])
bb = g.xuat_bang()
kt("dạng gọn ghi tồn", bb["sku"]["K1"][1] == 77 and bb["sku"]["Q9"][1] == 61)
kt("dạng gọn giữ tên cũ", bb["sku"]["K1"][0] == "Áo K1")

spec = importlib.util.spec_from_file_location("gym_plugin", str(ROOT / "system" / "plugins" / "goi-y-ma" / "plugin.py"))
pl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pl)


class _Ctx:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, handler=None, **kw):
        self.tools[name] = handler


class _C:
    vault_root = tempfile.mkdtemp()


ctx = _Ctx()
pl.register(ctx)
kt("plugin có 4 tool", set(ctx.tools) == {"javis_goi_y_ma_nap", "javis_goi_y_ma_tra", "javis_goi_y_ma_ma_ghep"} or len(ctx.tools) == 4)
(Path(_C.vault_root) / "attachments").mkdir()
(Path(_C.vault_root) / "attachments" / "d.json").write_text(_j.dumps({"sku": ["Z7:99"], "bai_viet": [{"post_id": "PP1", "ma": "Z7"}]}), encoding="utf-8")
out = asyncio.run(ctx.tools["javis_goi_y_ma_nap"]({"tep": "attachments/d.json"}, _C()))
kt("nạp từ file", '"sku": 1' in out and g.phan_giai(post_id="PP1")["ung_vien"][0]["ma"] == "Z7")
kt("chặn đường ra ngoài brain", asyncio.run(ctx.tools["javis_goi_y_ma_nap"]({"tep": "../../etc/passwd.json"}, _C())).startswith("ERROR"))
kt("chặn file không phải json", asyncio.run(ctx.tools["javis_goi_y_ma_nap"]({"tep": "attachments/d.txt"}, _C())).startswith("ERROR"))
kt("không dữ liệu = lỗi", asyncio.run(ctx.tools["javis_goi_y_ma_nap"]({}, _C())).startswith("ERROR"))

print(f"goi_y_ma: {ok} đạt, {loi} lỗi")
sys.exit(1 if loi else 0)
