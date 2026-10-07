"""26.10.102: theo dõi bản mới của gói đã nhận từ máy khác.

    python tests/run.py chia_se_theo_doi

Hai máy chủ giả lập trong một tiến trình như test_cho_chia_se: mọi lượt máy nhận gọi
https://<HOST>/... được chuyển vào chính TestClient.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-td-")
GUI = tempfile.mkdtemp(prefix="javis-td-gui-")
NHAN = tempfile.mkdtemp(prefix="javis-td-nhan-")
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
(g / "agents" / "chot.md").write_text("---\nname: Chốt đơn\nskills: [bao-gia]\n---\nChốt đơn lịch sự.", encoding="utf-8")
sk = g / "skills" / "bao-gia"
(sk / "scripts").mkdir(parents=True)
(sk / "SKILL.md").write_text("---\nname: bao-gia\ndescription: Báo giá\n---\nBảng giá cũ.", encoding="utf-8")
(sk / "scripts" / "cu.py").write_text("print('cu')", encoding="utf-8")

c = TestClient(main.app, base_url="http://localhost")
HOST = "minmin.ban.vn"


async def _gia_host(h):
    return "" if h == HOST else "chặn"


async def _gia_tai(url, headers=None, tran=0):
    r = c.get(url[len(f"https://{HOST}"):], headers=headers or {})
    return r.status_code, r.content, ""


main._host_cong_khai, main._tai_https = _gia_host, _gia_tai

# ---------- nhận lần đầu bằng link dùng một lần ----------
r = c.post("/brains/share", data={"brain": GUI, "items": json.dumps({"agent": ["chot"]}), "toi_da": "1"}).json()
goi = c.get(f"/bs/{r['token']}/goi.zip").content
td = goi_chia_se.doc_theo_doi(goi)
check("gói tải về mang kênh theo dõi", len(td) >= 30)
check("kênh theo dõi được chữ ký phủ", goi_chia_se.doc_chu_ky(goi)["trang_thai"] == "hop_le")
check("link dùng một lần đã hết lượt", c.get(f"/bs/{r['token']}/goi.zip").status_code == 404)
x = c.post("/brains/import/xem", data={"to_brain": NHAN}, files={"goi": ("g.zip", goi, "application/zip")}).json()
check("lần đầu: chưa có gì để cập nhật", x.get("cap_nhat") == {}, x.get("cap_nhat"))
# file tải tay không có host: ghi host như khi đến từ link để giả lập đúng luồng
d, tt = goi_chia_se.lay_cho(x["sha256"])
goi_chia_se.cat_cho(d, dict(tt, host=HOST))
ci = c.post("/brains/import/cai", data={"sha256": x["sha256"], "to_brain": NHAN}).json()
check("cài lần đầu được agent + skill", ci.get("ok") and len(ci["imported"]) == 2, ci)
so = goi_chia_se.doc_so(main._brain_root(NHAN))
check("sổ ghi kênh theo dõi + dấu bản", so["skill:bao-gia"].get("td") == td and so["skill:bao-gia"].get("phien_ban"), so)
check("sổ ghi dấu file sau khi cài", so["agent:chot"].get("hash_cai"))
check("skill nhiều file nhập về ĐỦ file (lỗi cũ: chỉ còn SKILL.md)",
      (Path(NHAN) / "skills" / "bao-gia" / "scripts" / "cu.py").is_file())
check("file theo dõi không lọt vào brain", not list(Path(NHAN).rglob("minmin-theo-doi.json")))

kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("chưa đổi gì: đang là bản mới nhất", kt["bao-gia"]["trang_thai"] == "moi_nhat" and kt["chot"]["trang_thai"] == "moi_nhat", kt)
check("chưa sửa tại chỗ", not kt["chot"]["sua_tai_cho"])
check("kênh theo dõi chỉ trả dấu, không trả nội dung", "Bảng giá" not in c.get(f"/bs/td/{td}").text)

# ---------- người gửi ra bản mới ----------
(sk / "SKILL.md").write_text("---\nname: bao-gia\ndescription: Báo giá\n---\nBảng giá MỚI tháng 10.\nThêm dòng.", encoding="utf-8")
(sk / "scripts" / "cu.py").unlink()
(sk / "scripts" / "moi.py").write_text("print('moi')", encoding="utf-8")
kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("skill đổi: có bản mới (dù link đã hết lượt)", kt["bao-gia"]["trang_thai"] == "co_ban_moi", kt)
check("agent không đổi: vẫn mới nhất", kt["chot"]["trang_thai"] == "moi_nhat")

xu = c.post("/brains/import/xem", data={"to_brain": NHAN, "td": td, "host_td": HOST}).json()
cn = xu.get("cap_nhat", {})
check("xem bản mới qua kênh theo dõi", xu.get("ok") and xu["xac_minh"]["xac_minh"] == "da_xac_minh", xu.get("xac_minh"))
check("bản mới: đánh dấu skill có bản mới", cn.get("skill:bao-gia", {}).get("co_ban_moi") and not cn.get("agent:chot", {}).get("co_ban_moi"), cn)
files = {k["file"]: k["trang_thai"] for k in cn["skill:bao-gia"]["khac"]}
check("khác biệt liệt kê đúng file sửa/mới/xoá", files == {"bao-gia/SKILL.md": "sua", "bao-gia/scripts/moi.py": "moi", "bao-gia/scripts/cu.py": "xoa"}, files)
check("agent: không báo khác chỉ vì dòng máy nhận tự ghi", cn["agent:chot"]["khac"] == [], cn["agent:chot"])

cu2 = c.post("/brains/import/cai", data={"sha256": xu["sha256"], "to_brain": NHAN, "overwrite": "1",
                                         "chon": json.dumps(["skill:bao-gia"])}).json()
skn = Path(NHAN) / "skills" / "bao-gia"
check("cập nhật xong skill là bản mới", cu2.get("ok") and "MỚI tháng 10" in (skn / "SKILL.md").read_text(encoding="utf-8"), cu2)
check("file bản mới bỏ đi thì bị xoá theo", not (skn / "scripts" / "cu.py").exists() and (skn / "scripts" / "moi.py").exists())
kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("sau cập nhật: mới nhất", kt["bao-gia"]["trang_thai"] == "moi_nhat", kt)

# ---------- tin tưởng không bị coi là tự sửa; tự sửa thì báo ----------
c.post("/brains/imported/trust", data={"brain": NHAN, "type": "agent", "slug": "chot"})
kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("bấm Tin tưởng không bị báo là tự sửa", not kt["chot"]["sua_tai_cho"], kt["chot"])
p = Path(NHAN) / "agents" / "chot.md"
p.write_text(p.read_text(encoding="utf-8") + "\nGhi chú riêng của tôi.", encoding="utf-8")
kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("tự sửa agent thì báo sửa tại chỗ", kt["chot"]["sua_tai_cho"])
(g / "agents" / "chot.md").write_text("---\nname: Chốt đơn\nskills: [bao-gia]\n---\nChốt đơn lịch sự, bản 2.", encoding="utf-8")
xu2 = c.post("/brains/import/xem", data={"to_brain": NHAN, "td": td, "host_td": HOST}).json()
check("xem bản mới cảnh báo sẽ ghi đè phần tự sửa", xu2["cap_nhat"]["agent:chot"]["sua_tai_cho"])
c.post("/brains/import/cai", data={"sha256": xu2["sha256"], "to_brain": NHAN, "overwrite": "1", "chon": json.dumps(["agent:chot"])})
am, _ = main._read_md(p)
check("cập nhật agent: quay về chế độ an toàn, phải tin lại", am.get("muc_quyen") == "suggest", am)

# ---------- nguồn khác không trộn ----------
check("gói từ máy khác không bị coi là bản mới của mục này",
      main._thong_tin_cap_nhat(goi, NHAN, "may-khac.vn") == {})

# ---------- thu hồi ----------
c.post("/brains/shares/revoke", data={"token": r["token"]})
kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("thu hồi link: báo không còn nhận bản mới", kt["bao-gia"]["trang_thai"] == "het", kt)
check("thu hồi link: kênh theo dõi chết hẳn", c.get(f"/bs/td/{td}/goi.zip").status_code == 404)
check("token theo dõi bịa là 404", c.get("/bs/td/khongcothat123456789012345").status_code == 404)
check("td sai dạng bị từ chối khi xem", c.post("/brains/import/xem", data={"to_brain": NHAN, "td": "../x", "host_td": HOST}).status_code == 400)

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
