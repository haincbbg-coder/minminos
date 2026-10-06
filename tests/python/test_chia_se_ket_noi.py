"""26.10.100: màn xem trước báo KẾT NỐI gói chia sẻ cần, so với máy nhận đang có.

    python tests/run.py chia_se_ket_noi
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-ketnoi-")
BR = tempfile.mkdtemp(prefix="javis-ketnoi-brain-")
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import ket_noi_can  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


def goi(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


G = goi({
    "workflows/len-camp.md": "---\nname: Lên camp sáng\nket_noi: [Facebook Ads, POS Pancake]\nsteps:\n  - agent: chot\n    task: x\n---\nx",
    "agents/chot.md": "---\nname: Chốt đơn\n---\nĐọc tin khách trên Zalo rồi tạo đơn trên Pancake.",
    "skills/anh/SKILL.md": "---\nname: anh\ndescription: ảnh\n---\nTạo ảnh bằng Higgsfield.",
    "memory/MEMORY.md": "Shopee",   # ngoài agents/skills/workflows: không tính
})
can = ket_noi_can.phat_hien(G)
ids = {k["id"]: k for k in can}
check("đọc được khai báo ket_noi trong frontmatter", ids.get("facebook-ads", {}).get("khai_bao") and ids.get("pancake", {}).get("khai_bao"), can)
check("phát hiện Zalo từ chữ (không khai)", "zalo" in ids and not ids["zalo"]["khai_bao"])
check("phát hiện Higgsfield trong skill", "higgsfield" in ids and ids["higgsfield"]["o"] == ["skill anh"], ids.get("higgsfield"))
check("ghi mục nào nhắc tới", "agent chot" in ids["pancake"]["o"])
check("file ngoài gói chính không tính", "shopee" not in ids)
check("khai báo xếp trước", can[0]["khai_bao"])
check("gói không nhắc gì thì rỗng", ket_noi_can.phat_hien(goi({"agents/a.md": "---\nname: A\n---\nViết thơ."})) == [])
check("zip hỏng không ném lỗi", ket_noi_can.phat_hien(b"x") == [])

dc = {k["id"]: k["trang_thai"] for k in ket_noi_can.doi_chieu(can, [
    {"ten": "poscake POSCake Shop HALIMI poscake-1", "bat": True},
    {"ten": "zalo Zalo Agent MCP Zalo cá nhân zalo", "bat": False},
])}
check("đã nối Pancake: da_co", dc["pancake"] == "da_co", dc)
check("Zalo có nhưng tắt: dang_tat", dc["zalo"] == "dang_tat", dc)
check("chưa nối Facebook Ads: chua_co", dc["facebook-ads"] == "chua_co", dc)

# luồng thật
main._ensure_brain_scaffold(Path(BR))
main._ket_noi_hien_co = lambda: [{"ten": "poscake POSCake", "bat": True}]
c = TestClient(main.app, base_url="http://localhost")
x = c.post("/brains/import/xem", data={"to_brain": BR}, files={"goi": ("g.zip", G, "application/zip")}).json()
kn = {k["id"]: k["trang_thai"] for k in x.get("ket_noi", [])}
check("xem trước trả ket_noi đã đối chiếu", kn.get("pancake") == "da_co" and kn.get("facebook-ads") == "chua_co", x.get("ket_noi"))
check("thiếu kết nối KHÔNG chặn cài", c.post("/brains/import/cai", data={"sha256": x["sha256"], "to_brain": BR}).json().get("ok"))

# trang nhận của người gửi cũng nói gói cần gì
ag = Path(BR) / "agents"
r = c.post("/brains/share", data={"brain": BR, "items": json.dumps({"agent": ["chot"]})}).json()
info = c.get(r["trang"], headers={"accept": "application/json"}).json()
check("trang nhận (JSON) có ket_noi", any(k["ten"] == "Zalo" for k in info.get("ket_noi", [])), info.get("ket_noi"))
h = c.get(r["trang"], headers={"accept": "text/html"}).text
check("trang nhận (HTML) ghi Cần kết nối", "Zalo" in h and ("Cần kết nối" in h or "Needs:" in h))
r2 = c.post("/brains/share", data={"brain": BR, "items": json.dumps({"agent": ["chot"]}), "pin": "1234"}).json()
check("có PIN thì trang công khai không lộ kết nối", c.get(r2["trang"], headers={"accept": "application/json"}).json().get("ket_noi") == [])

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
