"""26.10.103: kệ hàng công khai /bs/ke.

    python tests/run.py chia_se_ke_hang
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-ke-")
GUI = tempfile.mkdtemp(prefix="javis-ke-gui-")
NHAN = tempfile.mkdtemp(prefix="javis-ke-nhan-")
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import goi_chia_se  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


for b in (GUI, NHAN):
    main._ensure_brain_scaffold(Path(b))
g = Path(GUI)
(g / "agents").mkdir(exist_ok=True)
(g / "agents" / "viet-bai.md").write_text("---\nname: Viết bài <b>FB</b>\nrole: Viết bài Facebook\nskills: [giong-van]\n---\nViết.", encoding="utf-8")
(g / "agents" / "bi-mat.md").write_text("---\nname: Bí mật\n---\nkhông lên kệ", encoding="utf-8")
(g / "skills" / "giong-van").mkdir(parents=True)
(g / "skills" / "giong-van" / "SKILL.md").write_text("---\nname: giong-van\ndescription: Giọng văn shop\n---\nDùng Zalo để hỏi khách.", encoding="utf-8")
(g / "memory").mkdir(exist_ok=True)
(g / "memory" / "MEMORY.md").write_text("MẬT KHẨU 13579", encoding="utf-8")

c = TestClient(main.app, base_url="http://localhost")
HOST = "minmin.ke.vn"


async def _gia_host(h):
    return "" if h == HOST else "chặn"


async def _gia_tai(url, headers=None, tran=0):
    r = c.get(url[len(f"https://{HOST}"):], headers=dict(headers or {}, accept="application/json"))
    return r.status_code, r.content, ""


main._host_cong_khai, main._tai_https = _gia_host, _gia_tai

# ---------- kệ tắt mặc định ----------
check("kệ tắt mặc định: /bs/ke là 404", c.get("/bs/ke").status_code == 404)
r = c.post("/ke-hang/them", data={"brain": GUI, "items": json.dumps({"agent": ["viet-bai"], "skill": ["javis-builder", "khong-co"]})}).json()
check("đưa món lên kệ (bỏ qua skill hệ thống và món không tồn tại)", r["them"] == 1 and len(r["loi"]) == 2, r)
check("còn tắt thì món vẫn không lộ", c.get("/bs/ke").status_code == 404)
ds = c.get("/ke-hang").json()
mid = ds["mon"][0]["id"]
check("chủ máy thấy món trên kệ", ds["mon"][0]["ten"].startswith("Viết bài") and ds["bat"] is False)
check("món tắt kệ: tải gói là 404", c.get(f"/bs/ke/{mid}/goi.zip").status_code == 404)
again = c.post("/ke-hang/them", data={"brain": GUI, "items": json.dumps({"agent": ["viet-bai"]})}).json()
check("đưa lại món đã có không tạo món trùng", len(c.get("/ke-hang").json()["mon"]) == 1)

c.post("/ke-hang/cai-dat", data={"bat": "1", "ten_ke": "Bộ công cụ shop", "gioi_thieu": "Đồ dùng cho shop thời trang"})
j = c.get("/bs/ke", headers={"accept": "application/json"}).json()
check("mở kệ: thấy tên kệ + món", j["ten_ke"] == "Bộ công cụ shop" and len(j["mon"]) == 1, j)
check("trang kệ không lộ đường dẫn brain", GUI not in json.dumps(j) and "brain" not in j["mon"][0])
check("trang kệ báo kết nối cần", any(k["ten"] == "Zalo" for k in j["mon"][0]["ket_noi"]), j["mon"][0])
check("món không đưa lên kệ thì không có", "Bí mật" not in json.dumps(j, ensure_ascii=False))
h = c.get("/bs/ke", headers={"accept": "text/html"})
check("trang kệ HTML có CSP nonce", "script-src 'nonce-" in h.headers.get("content-security-policy", ""))
check("tên món được escape", "<b>FB</b>" not in h.text and "&lt;b&gt;FB" in h.text)
check("trang kệ có QR", "<svg" in h.text and c.get("/bs/ke/qr.svg").status_code == 200)

goi = c.get(f"/bs/ke/{mid}/goi.zip")
names = zipfile.ZipFile(io.BytesIO(goi.content)).namelist()
check("tải món kèm phụ thuộc (skill của agent)", "agents/viet-bai.md" in names and "skills/giong-van/SKILL.md" in names, names)
check("gói món có chữ ký hợp lệ", goi_chia_se.doc_chu_ky(goi.content)["trang_thai"] == "hop_le")
check("kênh theo dõi của món là id món", goi_chia_se.doc_theo_doi(goi.content) == mid)
blob = b"".join(zipfile.ZipFile(io.BytesIO(goi.content)).read(n) for n in names)
check("bộ nhớ không bao giờ lên kệ", b"13579" not in blob)

# ---------- máy khác duyệt kệ + nhận ----------
dk = c.post("/brains/import/ke", data={"host": f"https://{HOST}/bs/ke"}).json()
check("duyệt kệ theo tên miền", dk.get("ok") and dk["mon"][0]["link"] == f"https://{HOST}/bs/ke/{mid}", dk)
check("duyệt kệ tên miền xấu bị từ chối", c.post("/brains/import/ke", data={"host": "localhost"}).status_code == 400)
x = c.post("/brains/import/xem", data={"to_brain": NHAN, "nguon": dk["mon"][0]["link"]}).json()
check("xem trước món trên kệ qua link", x.get("ok") and x["xac_minh"]["xac_minh"] == "da_xac_minh", x.get("xac_minh"))
ci = c.post("/brains/import/cai", data={"sha256": x["sha256"], "to_brain": NHAN}).json()
check("nhận món trên kệ", ci.get("ok") and "agent:viet-bai" in ci["imported"], ci)
am, _ = main._read_md(Path(NHAN) / "agents" / "viet-bai.md")
check("món trên kệ cũng về ở chế độ an toàn", am.get("muc_quyen") == "suggest")
kt = {i["slug"]: i["trang_thai"] for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("món trên kệ theo dõi được bản mới", kt.get("viet-bai") == "moi_nhat", kt)
(g / "agents" / "viet-bai.md").write_text("---\nname: Viết bài FB\nskills: [giong-van]\n---\nViết hay hơn.", encoding="utf-8")
kt = {i["slug"]: i["trang_thai"] for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("người bày sửa món: máy nhận thấy bản mới", kt.get("viet-bai") == "co_ban_moi", kt)

# ---------- gỡ / tắt ----------
c.post("/ke-hang/cai-dat", data={"bat": "0"})
check("tắt kệ: món và kênh theo dõi chết ngay", c.get(f"/bs/ke/{mid}/goi.zip").status_code == 404 and c.get(f"/bs/td/{mid}").status_code == 404)
c.post("/ke-hang/cai-dat", data={"bat": "1"})
check("bật lại: sống lại", c.get(f"/bs/td/{mid}").status_code == 200)
check("gỡ món", c.post("/ke-hang/bo", data={"id": mid}).json()["ok"])
check("gỡ rồi: 404", c.get(f"/bs/ke/{mid}/goi.zip").status_code == 404)
check("id bịa: 404", c.get("/bs/ke/khongcothat123456789012345/goi.zip").status_code == 404)
check("quản lý kệ KHÔNG công khai", not any("/ke-hang".startswith(p) for p in main._AUTH_PUBLIC_PREFIX))

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
