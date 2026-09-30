"""Mắt Nhà - canh rào (0.64.98): vượt rào, vào khu cấm, tiến sát, lảng vảng.

    python tests/python/test_mat_nha_canh_rao.py      (KHÔNG mạng)

Canh ba lớp:
1. Cầu nối `minmin-cau` suy đúng mức từ thứ tự vùng (`rao_...` rồi `trong_...`), gửi cảnh báo
   SỚM đúng một lần lúc người đang vượt rào, và bản lúc kết thúc không nhắn chủ lần hai.
2. Server lưu `canh_bao` + `vung` đã làm sạch, lọc `chi_canh_bao`, gộp bản sớm với bản đầy đủ,
   và chỉ nhắn chủ cho vượt rào / vào khu cấm, mỗi camera tối đa một tin mỗi 2 phút.
3. Route POST /mat-nha/su-kien gọi `bao_chu` đúng lúc, không chặn trả lời cho cầu nối.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import base64
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-canhrao-")
os.environ["JAVIS_STATE_DIR"] = _STATE
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import mat_nha  # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


KIT = Path(ROOT) / "dashboard" / "mat-nha" / "kit"
spec = importlib.util.spec_from_file_location("cau_canh_rao", KIT / "minmin-cau" / "cau.py")
cau = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cau)
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64

# ============ 1. Suy mức từ vùng ============
m = cau.muc_canh_bao
check("rao_ rồi trong_ = vượt rào", m(["rao_sau", "trong_san"]) == "vuot_rao")
check("thẳng vào trong_ = vào khu cấm", m(["trong_san"]) == "vao_khu")
check("trong_ trước rồi mới rao_ (đi từ trong ra) = vào khu, không phải vượt rào",
      m(["trong_san", "rao_sau"]) == "vao_khu")
check("chỉ rao_, đang diễn ra: chưa kết luận", m(["rao_sau"]) is None)
check("chỉ rao_, xong, 10 giây = tiến sát", m(["rao_sau"], 100, 110, xong=True) == "tien_sat")
check("chỉ rao_, xong, 45 giây = lảng vảng", m(["rao_sau"], 100, 145, xong=True) == "lang_vang")
check("vùng không theo quy ước: không cảnh báo", m(["san_truoc", "duong"], 1, 99, xong=True) is None)
check("không vùng nào: không cảnh báo", m([], xong=True) is None)

# ============ 2. Cầu nối: cảnh báo sớm một lần, bản cuối không nhắn lại ============
c = cau.Cau(thu_muc=tempfile.mkdtemp(prefix="cau-"), gui_ham=lambda b: 0, lay_anh_ham=lambda eid: JPEG,
            minmin_url="http://x", token="t")


def su_kien(loai, zones, eid="e1", label="person", **them):
    after = {"id": eid, "camera": "san_sau", "label": label, "start_time": time.time() - 5,
             "end_time": time.time() if loai == "end" else None, "entered_zones": zones,
             "has_snapshot": True, "top_score": 0.9}
    after.update(them)
    return c.xu_ly("frigate/events", json.dumps({"type": loai, "after": after}))

check("mới vào dải rào: chưa gửi gì", su_kien("update", ["rao_sau"]) is None)
som = su_kien("update", ["rao_sau", "trong_san"])
check("vừa vào trong: gửi cảnh báo SỚM vượt rào kèm ảnh",
      som and som["id"] == "cb-e1" and som["canh_bao"] == "vuot_rao" and som.get("anh_b64")
      and som["la_nguoi_la"] is True and som["vung"] == ["rao_sau", "trong_san"])
check("cập nhật tiếp theo không gửi lại", su_kien("update", ["rao_sau", "trong_san"]) is None)
cuoi = su_kien("end", ["rao_sau", "trong_san"])
check("bản lúc kết thúc vẫn gửi để lưu, mang cờ da_bao",
      cuoi and cuoi["id"] == "e1" and cuoi["canh_bao"] == "vuot_rao" and cuoi.get("da_bao") is True)
ts = su_kien("end", ["rao_cong"], eid="e2", start_time=time.time() - 60)
check("chỉ ở dải rào 60 giây rồi đi: lảng vảng, không cờ da_bao",
      ts and ts["canh_bao"] == "lang_vang" and not ts.get("da_bao"))
check("xe vào khu trong không tính canh rào (chỉ người)",
      su_kien("update", ["rao_sau", "trong_san"], eid="e3", label="car") is None)
check("cau.py vẫn chỉ ASCII", all(b < 128 for b in (KIT / "minmin-cau" / "cau.py").read_bytes()))

# ============ 3. Server: lưu, lọc, gộp, nhắn chủ ============
b64 = base64.b64encode(JPEG).decode()
now = time.time()
r1 = mat_nha.luu_su_kien({"id": "cb-e1", "camera": "san_sau", "loai": "nguoi", "la_nguoi_la": True,
                          "bat_dau": now, "canh_bao": "vuot_rao", "vung": ["rao_sau", "trong_san", "RAO BẬY!!"],
                          "anh_b64": b64})
check("vượt rào mới: kết quả mang câu nhắn chủ", "VƯỢT RÀO" in (r1.get("bao_chu") or "") and "san_sau" in r1["bao_chu"])
r2 = mat_nha.luu_su_kien({"id": "e1", "camera": "san_sau", "loai": "nguoi", "la_nguoi_la": True,
                          "bat_dau": now, "ket_thuc": now + 20, "canh_bao": "vuot_rao",
                          "vung": ["rao_sau", "trong_san"], "da_bao": True})
check("bản cuối có da_bao: không nhắn lần hai", "bao_chu" not in r2)
r3 = mat_nha.luu_su_kien({"id": "e9", "camera": "san_sau", "loai": "nguoi", "bat_dau": now + 5,
                          "canh_bao": "vao_khu", "vung": ["trong_san"]})
check("cùng camera trong 2 phút: không nhắn thêm", "bao_chu" not in r3)
r4 = mat_nha.luu_su_kien({"id": "e10", "camera": "cong", "loai": "nguoi", "bat_dau": now + 6,
                          "canh_bao": "vao_khu", "vung": ["trong_kho"]})
check("camera khác: nhắn", "vào khu cấm" in (r4.get("bao_chu") or ""))
r5 = mat_nha.luu_su_kien({"id": "e11", "camera": "cong2", "loai": "nguoi", "bat_dau": now + 7,
                          "canh_bao": "lang_vang", "vung": ["rao_cong"]})
check("lảng vảng: lưu nhưng không nhắn chủ", r5["ok"] and "bao_chu" not in r5)
r6 = mat_nha.luu_su_kien({"id": "e12", "camera": "cong3", "loai": "nguoi", "bat_dau": now + 8,
                          "canh_bao": "hack", "vung": "khong-phai-list"})
check("mức lạ và vùng sai kiểu bị bỏ, không nhắn", "bao_chu" not in r6)

ds = mat_nha.tim(chi_canh_bao=True, limit=50)
ids = [e["id"] for e in ds]
check("lọc chi_canh_bao chỉ trả sự kiện có cảnh báo", set(ids) == {"e1", "e9", "e10", "e11"}, ids)
check("bản sớm cb-e1 được gộp vào bản đầy đủ e1", "cb-e1" not in ids)
e1 = [e for e in ds if e["id"] == "e1"][0]
check("vùng được làm sạch (bỏ tên sai quy cách)", e1["vung"] == ["rao_sau", "trong_san"], e1.get("vung"))
e12 = mat_nha.tim(limit=50)
e12 = [e for e in e12 if e["id"] == "e12"][0]
check("sự kiện có mức lạ lưu như thường, không có canh_bao", "canh_bao" not in e12 and "vung" not in e12)
tt = mat_nha.tom_tat(ds)
check("tóm tắt cho MinMin nói rõ cảnh báo canh rào", "Cảnh báo canh rào" in tt and "VƯỢT RÀO" in tt, tt[:200])

# ============ 4. Route: gọi bao_chu, không chặn cầu nối ============
from fastapi import FastAPI                 # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402
import routes.mat_nha as rmn                # noqa: E402

nhan = []


async def _bao(text):
    nhan.append(text)

app = FastAPI()
rmn.register(app, rmn.MatNhaDeps(dashboard_dir=Path(ROOT) / "dashboard", bao_chu=_bao))
ma = mat_nha.tao_ma()
with TestClient(app) as tc:
    r = tc.post("/mat-nha/su-kien", headers={"x-mat-nha-token": ma},
                content=json.dumps({"id": "e20", "camera": "vuon", "loai": "nguoi", "bat_dau": time.time(),
                                    "canh_bao": "vuot_rao", "vung": ["rao_vuon", "trong_vuon"]}))
    check("route nhận sự kiện vượt rào (200) và không trả câu nhắn ra ngoài",
          r.status_code == 200 and "bao_chu" not in r.json(), r.text)
    for _ in range(20):
        if nhan:
            break
        time.sleep(0.05)
    check("route đã nhắn chủ đúng một lần", len(nhan) == 1 and "vuon" in nhan[0], nhan)
    r = tc.get("/mat-nha/su-kien?chi_canh_bao=true")
    check("GET lọc chi_canh_bao qua HTTP", r.status_code == 200 and all(e.get("canh_bao") for e in r.json()["su_kien"]))

for f in ("server/mat_nha.py", "server/routes/mat_nha.py", "dashboard/mat-nha/mat-nha.js",
          "dashboard/mat-nha/index.html", "docs/mat-nha.md"):
    check(f"không có em dash trong {f}", "—" not in (Path(ROOT) / f).read_text(encoding="utf-8"))

if _fails:
    print(f"\nFAIL - test_mat_nha_canh_rao: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_mat_nha_canh_rao: tất cả pass")
