"""Kết nối ngoài (26.10.3): mã kích hoạt ký số, khoá theo máy / thời hạn, điều khoản sử dụng.

    python tests/python/test_ket_noi_ngoai.py      (KHÔNG mạng)
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-knn-")
os.environ["JAVIS_STATE_DIR"] = _STATE
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import giay_phep  # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


def loi(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    return ""


check("thư mục giấy phép nằm trong STATE tạm", _STATE in str(giay_phep._thu_muc()))
m1 = giay_phep.ma_may()
check("mã máy ổn định giữa các lần gọi", m1 == giay_phep.ma_may() and m1.startswith("MM-"))

# ---- máy KHÁCH: chưa có khoá riêng, chưa có khoá công khai -> mọi app khoá
check("chưa phải nhà phát hành", not giay_phep.la_nha_phat_hanh())
check("mọi app khoá khi chưa có mã", not any(v["mo"] for v in giay_phep.quyen().values()))
check("không tạo được mã khi thiếu khoá riêng", "khoá riêng" in loi(lambda: giay_phep.tao_ma("A", ["*"])))

# ---- máy NHÀ PHÁT HÀNH: sinh khoá ở một STATE khác, tạo mã, rồi đưa khoá công khai cho khách
khach_state = giay_phep.STATE_DIR
ph_state = tempfile.mkdtemp(prefix="javis-knn-ph-")
giay_phep.STATE_DIR = Path(ph_state)
pub = giay_phep.tao_cap_khoa()
check("tạo khoá: in khoá công khai 32 byte", len(__import__("base64").b64decode(pub)) == 32)
check("tạo khoá lần hai không ghi đè khoá cũ", giay_phep.tao_cap_khoa() == pub)
check("máy có khoá riêng là nhà phát hành, mọi app tự mở",
      giay_phep.la_nha_phat_hanh() and all(v["mo"] for v in giay_phep.quyen().values()))
han = (date.today() + timedelta(days=30)).isoformat()
ma_dung = giay_phep.tao_ma("Shop A", ["tai_hoa_don"], m1, han, "gói 10 MST")
ma_moi_may = giay_phep.tao_ma("Shop B", ["*"], "*", None)
ma_may_khac = giay_phep.tao_ma("Shop C", ["zalo_forwarder"], "MM-KHAC000000000", None)
ma_het = giay_phep.tao_ma("Shop D", ["dieu_khien_may"], "*", (date.today() - timedelta(days=1)).isoformat())
check("mã bắt đầu MM1. và có 3 phần", ma_dung.startswith("MM1.") and ma_dung.count(".") == 2)
check("app lạ bị loại, không còn app nào thì lỗi", "chưa chọn" in loi(lambda: giay_phep.tao_ma("X", ["app_la"])))
check("ngày hết hạn sai định dạng bị từ chối", loi(lambda: giay_phep.tao_ma("X", ["*"], "*", "01/10/2026")) != "")

# ---- về máy khách, tin đúng khoá công khai của nhà phát hành
giay_phep.STATE_DIR = khach_state
giay_phep.KHOA_CONG_KHAI = (pub,)
check("khách kích hoạt mã đúng máy, đúng hạn", giay_phep.kich_hoat(ma_dung)["kh"] == "Shop A")
q = giay_phep.quyen()
check("chỉ đúng app trong mã được mở, kèm hạn", q["tai_hoa_don"]["mo"] and q["tai_hoa_don"]["het_han"] == han
      and not q["zalo_forwarder"]["mo"])
check("mã cho máy khác bị từ chối", "không phải máy này" in loi(lambda: giay_phep.kich_hoat(ma_may_khac)))
check("mã hết hạn bị từ chối", "hết hạn" in loi(lambda: giay_phep.kich_hoat(ma_het)))
gia = ma_dung[:-4] + ("AAAA" if not ma_dung.endswith("AAAA") else "BBBB")
check("sửa một ký tự chữ ký là hỏng", "chữ ký" in loi(lambda: giay_phep.kich_hoat(gia)) or "cắt" in loi(lambda: giay_phep.kich_hoat(gia)))
import base64 as _b
p, s = ma_dung[4:].split(".")
pl = json.loads(_b.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
pl["ung_dung"] = ["*"]
gia2 = "MM1." + _b.urlsafe_b64encode(json.dumps(pl).encode()).decode().rstrip("=") + "." + s
check("sửa nội dung (đổi app thành *) là chữ ký hỏng", "chữ ký" in loi(lambda: giay_phep.kich_hoat(gia2)))
check("rác không đúng định dạng", "định dạng" in loi(lambda: giay_phep.kich_hoat("abc")))
giay_phep.kich_hoat(ma_moi_may)
q = giay_phep.quyen()
check("mã * vĩnh viễn mở mọi app và thắng mã có hạn", all(v["mo"] for v in q.values()) and q["tai_hoa_don"]["het_han"] is None)
check("kích hoạt lại không lưu trùng", len(giay_phep._doc_kho()) == 2 and giay_phep.kich_hoat(ma_moi_may) and len(giay_phep._doc_kho()) == 2)
check("gỡ mã", giay_phep.go_ma(ma_moi_may) and not giay_phep.quyen()["zalo_forwarder"]["mo"])
check("hết hạn tính theo ngày", not giay_phep.quyen(hom_nay=date.today() + timedelta(days=31))["tai_hoa_don"]["mo"]
      and giay_phep.quyen(hom_nay=date.today() + timedelta(days=31))["tai_hoa_don"]["het_han_roi"])
check("mã máy khách không đổi sau khi đổi qua lại", giay_phep.ma_may() == m1)

# ---- Route + điều khoản
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.ket_noi_ngoai as rk  # noqa: E402

app = FastAPI()
rk.register(app, Path(ROOT) / "dashboard")
with TestClient(app) as tc:
    d = tc.get("/ket-noi-ngoai").json()
    check("GET trả mã máy, danh sách app và điều khoản chưa đồng ý",
          d["ma_may"] == m1 and {u["id"] for u in d["ung_dung"]} == {
              "zalo_forwarder", "tai_hoa_don", "quet_hoa_don_gmail",
              "bo_chung_tu_ke_toan", "xuong_video", "dieu_khien_may", "viral_studio",
              "doi_social", "concat", "business_finance",
          } and d["dieu_khoan"]["chung"] is False)
    r = tc.post("/ket-noi-ngoai/kich-hoat", data={"ma": ma_moi_may})
    check("chưa đồng ý điều khoản thì không kích hoạt được (403)", r.status_code == 403)
    r = tc.post("/dieu-khoan/dong-y", data={"phan": "chung"})
    check("đồng ý điều khoản chung", r.status_code == 200 and r.json()["dieu_khoan"]["chung"] is True)
    ghi = json.loads((giay_phep._thu_muc() / "dong-y-dieu-khoan.json").read_text(encoding="utf-8"))["chung"]
    check("lưu bằng chứng đồng ý: phiên bản, thời điểm, mã máy",
          ghi["phien_ban"] == rk.DIEU_KHOAN_PHIEN_BAN and ghi["luc"] > 0 and ghi["ma_may"] == m1)
    check("phần lạ bị từ chối", tc.post("/dieu-khoan/dong-y", data={"phan": "hack"}).status_code == 400)
    r = tc.post("/ket-noi-ngoai/kich-hoat", data={"ma": ma_moi_may})
    check("đồng ý rồi thì kích hoạt được", r.status_code == 200 and r.json()["khach"] == "Shop B")
    check("máy khách không tạo được mã (403)",
          tc.post("/ket-noi-ngoai/tao-ma", json={"khach": "x", "ung_dung": ["*"]}).status_code == 403)
    md = tc.get("/dieu-khoan.md")
    check("văn bản điều khoản có đủ phụ lục Zalo và Điều khiển máy",
          md.status_code == 200 and "Phụ lục A" in md.text and "Phụ lục B" in md.text)
    rk.DIEU_KHOAN_PHIEN_BAN = "2099-01-01"
    check("đổi phiên bản điều khoản thì phải đồng ý lại", tc.get("/ket-noi-ngoai").json()["dieu_khoan"]["chung"] is False)

for f in ("server/giay_phep.py", "server/routes/ket_noi_ngoai.py", "dashboard/ket-noi-ngoai.js",
          "dashboard/legal/dieu-khoan-su-dung.md"):
    check(f"không có em dash trong {f}", "—" not in (Path(ROOT) / f).read_text(encoding="utf-8"))
check("khoá riêng KHÔNG nằm trong repo", not list(Path(ROOT).rglob("khoa-rieng.pem")))

if _fails:
    print(f"\nFAIL - test_ket_noi_ngoai: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_ket_noi_ngoai: tất cả pass")

