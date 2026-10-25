# -*- coding: utf-8 -*-
"""Trang Tổng quan (26.10.239): GET /tong-quan gom số liệu trong tiến trình. Không mạng.

    python tests/run.py tong_quan

Phủ: brain trống (mọi khối chưa nối, không số bịa), đọc pancake-office.json, tiền vào từ biến động
số dư, một nguồn ném lỗi chỉ hỏng khối đó và câu lỗi không lộ token, Kanban review + blocked,
sắp xếp bad trước warn và trần 12 mục, Thống kê Pancake theo page, hợp đồng khoá cấp 1 của PLAN.md.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-tongquan-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ.setdefault("BRAINS_DIR", tempfile.mkdtemp(prefix="javis-tongquan-brains-"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI                 # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402
import bien_dong                            # noqa: E402
import routes.hud as hud                    # noqa: E402
import tasks                                # noqa: E402
import tong_quan as tq                      # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


BRAIN = Path(tempfile.mkdtemp(prefix="minmin-tongquan-brain-"))
TOKEN = "EAAGtokenGiaBiMatKhongDuocLo1234567890"
deps = tq.TongQuanDeps(brain_root=lambda b: str(BRAIN))
app = FastAPI()
tq.register(app, deps)
client = TestClient(app)


def lay():
    r = client.get("/tong-quan", params={"brain": "brain"})
    check("HTTP 200", r.status_code == 200, r.status_code)
    return r.json()


KHOA_CAP1 = {"luc", "cai_dat", "can_xu_ly", "tien_vao", "chi_phi_ai", "so_chinh", "theo_page"}
KHOA_SO_CHINH = {"doanh_thu", "don_chot", "chot_hoi_thoai", "chi_ads"}

# ---- (1) + (7) brain trống, không nối gì ----
j = lay()
check("hợp đồng: đủ khoá cấp 1", set(j) == KHOA_CAP1, sorted(j))
check("hợp đồng: đủ khoá so_chinh", set(j["so_chinh"]) == KHOA_SO_CHINH, sorted(j["so_chinh"]))
check("luc là ISO có múi giờ", "T" in j["luc"] and ("+" in j["luc"][10:] or j["luc"].endswith("Z")), j["luc"])
cd = j["cai_dat"]
check("cài đặt có 6 bước đúng id", [b["id"] for b in cd["buoc"]] == ["pos", "ads", "zalo", "telegram", "biendong", "nao"], cd)
check("cài đặt: trang để đi nối", [b["trang"] for b in cd["buoc"]] == ["mcp", "mcp", "mcp", "channels", "biendong", "models"], cd)
check("cài đặt chưa xong hết", cd["tong"] == 6 and cd["xong"] < cd["tong"], cd)
check("tiền vào: chưa nối", j["tien_vao"] == {"trang_thai": "chua_noi"}, j["tien_vao"])
for k in KHOA_SO_CHINH:
    check(f"so_chinh.{k}: chưa nối, không có số", j["so_chinh"][k] == {"trang_thai": "chua_noi"}, j["so_chinh"][k])
check("theo_page: chưa nối", j["theo_page"] == {"trang_thai": "chua_noi"}, j["theo_page"])
check("cần xử lý: rỗng, ok", j["can_xu_ly"]["trang_thai"] == "ok" and j["can_xu_ly"]["muc"] == [], j["can_xu_ly"])
check("chi phí AI: ok, 0 lượt thật (kho trống)", j["chi_phi_ai"].get("trang_thai") == "ok"
      and j["chi_phi_ai"]["luot"] == 0 and j["chi_phi_ai"]["usd_that"] == 0, j["chi_phi_ai"])
check("không ghi file cài đặt biến động", not bien_dong.file_cai_dat().exists())

# ---- (2) pancake-office.json giả ----
dash = BRAIN / "00 - Dashboard"
dash.mkdir(parents=True, exist_ok=True)
(dash / "pancake-office.json").write_text(json.dumps({"updated": "2026-10-25 10:00", "staff": [
    {"name": "Lan", "dept": "sale", "orders": 10, "revenue": 5000000, "yesterday": {"orders": 7, "revenue": 3500000}},
    {"name": "Huệ", "dept": "sale", "orders": 3, "revenue": 1200000, "yesterday": {"orders": 4, "revenue": 2000000}},
    {"name": "Kho A", "dept": "kho", "orders": 0, "revenue": 0, "packed": 9},
], "ads": {"spend": 960000, "roas": 3.2}}), encoding="utf-8")
j = lay()
dt, dc = j["so_chinh"]["doanh_thu"], j["so_chinh"]["don_chot"]
check("doanh thu hôm nay = tổng staff", dt == {"trang_thai": "ok", "hom_nay": 6200000, "hom_qua": 5500000}, dt)
check("đơn chốt hôm nay/hôm qua", dc == {"trang_thai": "ok", "hom_nay": 13, "hom_qua": 11}, dc)
check("chi ads từ ads.spend", j["so_chinh"]["chi_ads"] == {"trang_thai": "ok", "hom_nay": 960000}, j["so_chinh"]["chi_ads"])
check("số tiền VND là số nguyên", isinstance(dt["hom_nay"], int))

# File không có ads -> chi_ads chưa nối; không có hôm qua -> hom_qua null (không bịa 0)
(dash / "pancake-office.json").write_text(json.dumps({"staff": [{"name": "Lan", "orders": 2, "revenue": 100}]}), encoding="utf-8")
j = lay()
check("không có ads -> chi_ads chưa nối", j["so_chinh"]["chi_ads"] == {"trang_thai": "chua_noi"}, j["so_chinh"]["chi_ads"])
check("không có số hôm qua -> null", j["so_chinh"]["doanh_thu"]["hom_qua"] is None, j["so_chinh"]["doanh_thu"])

# Có cấu hình POS, file cũ hơn TTL, đồng bộ lỗi nhại cả khoá -> vẫn trả số cũ, ghi chú đã giấu khoá
(dash / "pancake-config.json").write_text(json.dumps({"api_key": TOKEN, "shop_id": 1}), encoding="utf-8")
cu = time.time() - hud.PANCAKE_TTL - 60
os.utime(dash / "pancake-office.json", (cu, cu))
_goc_dong_bo = hud.dong_bo_pancake
goi_dong_bo = []
hud.dong_bo_pancake = lambda root: (goi_dong_bo.append(root), f"Pancake: HTTPError: 401 api_key={TOKEN}")[1]
j = lay()
hud.dong_bo_pancake = _goc_dong_bo
check("file cũ hơn TTL -> gọi đồng bộ đúng một lần", len(goi_dong_bo) == 1, goi_dong_bo)
check("đồng bộ lỗi vẫn trả số lần trước", j["so_chinh"]["don_chot"]["hom_nay"] == 2, j["so_chinh"]["don_chot"])
check("ghi chú đồng bộ không lộ khoá", TOKEN not in json.dumps(j, ensure_ascii=False), j["so_chinh"]["doanh_thu"])
check("bước cài đặt POS xong khi có pancake-config", j["cai_dat"]["buoc"][0]["xong"] is True, j["cai_dat"]["buoc"][0])
(dash / "pancake-config.json").unlink()

# ---- (3) biến động số dư: giao dịch hôm nay ----
bien_dong._ghi_json(bien_dong.file_cai_dat(), {**bien_dong.MAC_DINH, "token": "x" * 30, "khoa": "khoa-ma-hoa"})
bay_gio = time.time()
hom_qua = bien_dong.dau_hom_nay() - 3600
bien_dong._ghi_json(bien_dong.file_kho(), {"version": 1, "da_thay": [], "giao_dich": [
    {"id": "1", "so_tien": 2350000, "mo_ta": "CK don hang HL123 " + "x" * 80, "luc": bay_gio - 10},
    {"id": "2", "so_tien": 500000, "mo_ta": "Khach B", "luc": bay_gio - 20},
    {"id": "3", "so_tien": -300000, "mo_ta": "Tien ra", "luc": bay_gio - 30},
    {"id": "4", "so_tien": 100000, "mo_ta": "Thu nghiem", "luc": bay_gio - 40, "thu_nghiem": True},
    {"id": "5", "so_tien": 900000, "mo_ta": "Khach C", "luc": bay_gio - 50},
    {"id": "6", "so_tien": 700000, "mo_ta": "Khach D", "luc": bay_gio - 60},
    {"id": "7", "so_tien": 9999999, "mo_ta": "Hom qua", "luc": hom_qua},
]})
j = lay()
tv = j["tien_vao"]
check("tiền vào: ok", tv.get("trang_thai") == "ok", tv)
check("tiền vào: tổng = 4 giao dịch vào hôm nay (bỏ tiền ra, thử nghiệm, hôm qua)",
      tv.get("tong") == 2350000 + 500000 + 900000 + 700000 and tv.get("so_gd") == 4, tv)
check("tiền vào: 3 giao dịch mới nhất", [g["so_tien"] for g in tv.get("gan_nhat", [])] == [2350000, 500000, 900000], tv)
check("tiền vào: mô tả cắt 60 ký tự", len(tv["gan_nhat"][0]["mo_ta"]) == 60, tv["gan_nhat"][0])
check("tiền vào: luc là epoch nguyên", isinstance(tv["gan_nhat"][0]["luc"], int), tv["gan_nhat"][0])
check("bước biến động xong", j["cai_dat"]["buoc"][4]["xong"] is True, j["cai_dat"]["buoc"][4])

# ---- (4) một nguồn ném lỗi: chỉ khối đó hỏng, không lộ token ----
_goc_ai = tq.khoi_chi_phi_ai
_goc_kn = tq.nguon_ket_noi


def ai_hong(deps, brain):
    raise RuntimeError(f"401 Unauthorized for https://api.x.ai/v1?key={TOKEN}")


def kn_hong(deps, brain):
    raise ValueError(f"Bearer {TOKEN} bị từ chối")


tq.khoi_chi_phi_ai = lambda d, b: {"trang_thai": "loi", "loi": tq.giau_loi(RuntimeError(f"token {TOKEN}"))}
j = lay()
check("khối lỗi tự xử: chi_phi_ai loi", j["chi_phi_ai"]["trang_thai"] == "loi", j["chi_phi_ai"])
tq.khoi_chi_phi_ai = ai_hong
tq.nguon_ket_noi = kn_hong
r = client.get("/tong-quan")
j = r.json()
tq.khoi_chi_phi_ai = _goc_ai
tq.nguon_ket_noi = _goc_kn
check("nguồn ném lỗi vẫn 200", r.status_code == 200, r.status_code)
check("chi_phi_ai -> loi kèm câu ngắn", j["chi_phi_ai"]["trang_thai"] == "loi" and j["chi_phi_ai"]["loi"], j["chi_phi_ai"])
check("khối khác vẫn ok", j["tien_vao"]["trang_thai"] == "ok" and j["so_chinh"]["don_chot"]["trang_thai"] == "ok", j)
check("loi_nguon ghi nguồn Kết nối", any(x.startswith("Kết nối:") for x in j["can_xu_ly"]["loi_nguon"]), j["can_xu_ly"])
check("can_xu_ly vẫn ok khi một nguồn lỗi", j["can_xu_ly"]["trang_thai"] == "ok", j["can_xu_ly"])
check("không đâu lộ token", TOKEN not in r.text, r.text[:300])
check("giau_loi che chuỗi dài giống token", "***" in tq.giau_loi("lỗi abcdefghijklmnopqrstuvwxyz0123"))

# ---- (5) Kanban: 1 review + 1 blocked (needs_input) + 1 blocked capability ----


class _BangGia:
    def __init__(self, attention):
        self.attention = attention

    def board_view(self, brain):
        return {"operations": {"attention": self.attention}}


_goc_current = tasks.current
tasks.current = lambda: _BangGia([
    {"id": "t-blk", "title": "Soạn email khách", "status": "blocked", "block_kind": "needs_input",
     "block_reason": "cũ", "metadata": {"qa": [{"q": "Gửi cho ai trước?"}]}},
    {"id": "t-cap", "title": "Đăng bài", "status": "blocked", "block_kind": "capability", "block_reason": "x"},
    {"id": "t-rev", "title": "Báo cáo tuần", "status": "review"},
])
j = lay()
muc = {m["id"]: m for m in j["can_xu_ly"]["muc"]}
check("kanban: 3 mục", {"kanban:t-rev", "kanban:t-blk", "kanban:t-cap"} <= set(muc), list(muc))
rev = muc.get("kanban:t-rev", {})
check("review: warn + nút Duyệt có task_id", rev.get("muc_do") == "warn" and rev["nut"][0] ==
      {"nhan": "Duyệt", "loai": "duyet_kanban", "task_id": "t-rev"}, rev)
check("review: nút Mở trang kanban", rev["nut"][1] == {"nhan": "Mở", "loai": "trang", "trang": "kanban", "task_id": "t-rev"}, rev)
blk = muc.get("kanban:t-blk", {})
check("blocked needs_input: hỏi câu cuối", blk.get("mo_ta") == "Đang hỏi bạn: Gửi cho ai trước?", blk)
check("blocked: chỉ có nút Mở", [n["nhan"] for n in blk.get("nut", [])] == ["Mở"], blk)
check("blocked capability: câu cấp quyền", muc.get("kanban:t-cap", {}).get("mo_ta") == "Chờ cấp quyền thao tác ra ngoài", muc.get("kanban:t-cap"))
check("mục có nguon kanban", all(m["nguon"] == "kanban" for m in muc.values()), muc)
tasks.current = lambda: None
j = lay()
check("tasks chưa khởi tạo: bỏ qua êm", j["can_xu_ly"]["muc"] == [] and j["can_xu_ly"]["loi_nguon"] == [], j["can_xu_ly"])

# ---- (6) sắp xếp bad trước warn trước info, tối đa 12 ----
_goc_lp = tq.nguon_loop
tasks.current = lambda: _BangGia([{"id": f"w{i}", "title": f"Việc {i}", "status": "review"} for i in range(10)])
tq.nguon_loop = lambda d, b: (
    [tq._muc(f"loop:i{i}", "loop", "info", "info", "", []) for i in range(2)]
    + [tq._muc(f"loop:b{i}", "loop", "bad", "bad", "", []) for i in range(4)])
j = lay()
tq.nguon_loop = _goc_lp
tasks.current = _goc_current
ds = j["can_xu_ly"]["muc"]
check("tối đa 12 mục", len(ds) == 12, len(ds))
check("bad đứng đầu", [m["muc_do"] for m in ds[:4]] == ["bad"] * 4, [m["muc_do"] for m in ds])
check("rồi tới warn, info bị cắt", all(m["muc_do"] == "warn" for m in ds[4:]), [m["muc_do"] for m in ds])

# ---- Thống kê Pancake theo page (giả lập kết nối + API) ----
import mcp_store              # noqa: E402
import pancake_chat_mcp as pk  # noqa: E402
_goc_resolved, _goc_tq = mcp_store.resolved, pk.tong_quan
mcp_store.resolved = lambda enabled_only=True: [
    {"id": "c1", "connector_id": "pancake-thong-ke", "secrets": {"pages": f"598364820025920 | {TOKEN} | HALIMI"}}]


async def tq_gia(pages, a):
    return {"tong_tat_ca_page": {"ty_le_chot": 31.0, "khach_nhan_tin": 200, "so_dien_thoai_moi": 118, "don_chot": 62},
            "tung_page": [{"page": "HALIMI", "khach_nhan_tin": 124, "so_dien_thoai_moi": 76, "don_chot": 41, "ty_le_chot": 33.0}]}


pk.tong_quan = tq_gia
j = lay()
check("chot_hoi_thoai từ tổng mọi page", j["so_chinh"]["chot_hoi_thoai"] ==
      {"trang_thai": "ok", "ty_le": 31.0, "khach": 200, "sdt": 118}, j["so_chinh"]["chot_hoi_thoai"])
check("theo_page dòng HALIMI", j["theo_page"] == {"trang_thai": "ok", "dong": [
    {"page": "HALIMI", "khach": 124, "sdt": 76, "don": 41, "ty_le": 33.0}]}, j["theo_page"])


async def tq_loi(pages, a):
    return {"loi": [f"HALIMI: ERROR: 403 page_access_token={TOKEN}"], "tung_page": []}


pk.tong_quan = tq_loi
r = client.get("/tong-quan")
j = r.json()
check("pancake lỗi hết page -> loi", j["theo_page"]["trang_thai"] == "loi" and j["so_chinh"]["chot_hoi_thoai"]["trang_thai"] == "loi", j["theo_page"])
check("câu lỗi pancake không lộ token", TOKEN not in r.text, j["theo_page"])


async def tq_nem(pages, a):
    raise ConnectionError(f"boom {TOKEN}")


pk.tong_quan = tq_nem
r = client.get("/tong-quan")
check("pancake ném lỗi -> loi, không lộ token", r.json()["theo_page"]["trang_thai"] == "loi" and TOKEN not in r.text, r.text[:200])
mcp_store.resolved, pk.tong_quan = _goc_resolved, _goc_tq

# ---- gom() gọi thẳng (không qua HTTP) cũng chịu một khối ném lỗi ở tầng ráp ----
_goc_cd = tq.khoi_cai_dat


def cd_hong(d, b):
    raise OSError(f"đĩa hỏng {TOKEN}")


tq.khoi_cai_dat = cd_hong
kq = asyncio.run(tq.gom("brain", deps))
tq.khoi_cai_dat = _goc_cd
check("khối cài đặt ném lỗi: vẫn đủ khoá, tong=6", set(kq) == KHOA_CAP1 and kq["cai_dat"]["tong"] == 6
      and TOKEN not in json.dumps(kq, ensure_ascii=False), kq["cai_dat"])

# Không có em dash trong module
check("module không có em dash", "\u2014" not in Path(tq.__file__).read_text(encoding="utf-8"))

print()
if _fails:
    print(f"{len(_fails)} FAIL: {_fails}")
    raise SystemExit(1)
print("Tất cả xanh.")
