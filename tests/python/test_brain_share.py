"""Chia sẻ brain bằng link (26.10.73). Canh các ranh giới an toàn.

    python tests/run.py brain_share
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import io
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-bshare-")
BR = tempfile.mkdtemp(prefix="javis-bshare-brain-")
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import brain_share  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


main._ensure_brain_scaffold(Path(BR))
b = Path(BR)
(b / "agents").mkdir(exist_ok=True)
(b / "agents" / "viet-mail.md").write_text("---\nname: Viết mail\ngroup: Content\n---\nViết email.", encoding="utf-8")
(b / "agents" / "rieng-tu.md").write_text("---\nname: Riêng tư\n---\nbí mật", encoding="utf-8")
(b / "memory" / "facts").mkdir(parents=True, exist_ok=True)
(b / "memory" / "MEMORY.md").write_text("MẬT KHẨU WIFI 12345", encoding="utf-8")
(b / "settings-bi-mat.json").write_text('{"api_key":"sk-abc"}', encoding="utf-8")
sk = b / "skills" / "bao-gia"; sk.mkdir(parents=True)
(sk / "SKILL.md").write_text("---\nname: bao-gia\ndescription: Báo giá\ngroup: Sales\n---\nthân", encoding="utf-8")

c = TestClient(main.app, base_url="http://localhost")
r = c.post("/brains/share", data={"brain": BR, "items": json.dumps({"agent": ["viet-mail"], "skill": ["bao-gia"]}), "days": "3"}).json()
tok = r.get("token")
check("tạo link được và trả token dài", r.get("ok") and tok and len(tok) >= 30, r)
z = c.get(f"/bs/{tok}/goi.zip")
check("tải gói bằng token", z.status_code == 200 and z.content[:2] == b"PK", z.status_code)
names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
check("gói có agent và skill đã chọn", "agents/viet-mail.md" in names and "skills/bao-gia/SKILL.md" in names, names)
check("agent KHÔNG chọn thì không vào gói", "agents/rieng-tu.md" not in names)
blob = b"".join(zipfile.ZipFile(io.BytesIO(z.content)).read(n) for n in names)
check("bộ nhớ và khoá bí mật KHÔNG bao giờ vào gói", b"12345" not in blob and b"sk-abc" not in blob)
check("lượt tải được đếm", brain_share.doc(tok)["tai"] == 1)

# tất cả
r2 = c.post("/brains/share", data={"brain": BR, "tat_ca": "1"}).json()
n2 = zipfile.ZipFile(io.BytesIO(c.get(f"/bs/{r2['token']}/goi.zip").content)).namelist()
check("chia sẻ tất cả có cả hai agent", "agents/rieng-tu.md" in n2 and "agents/viet-mail.md" in n2, n2)
check("nhưng vẫn không có memory", not any(x.startswith("memory") for x in n2))

# danh sách, thu hồi, hết hạn, token lạ
ds = c.get("/brains/shares", params={"brain": BR}).json()["shares"]
check("danh sách thấy 2 link", len(ds) == 2, ds)
check("thu hồi xong là 404", c.post("/brains/shares/revoke", data={"token": tok}).json()["ok"]
      and c.get(f"/bs/{tok}/goi.zip").status_code == 404)
d = json.loads(brain_share.STORE.read_text(encoding="utf-8")); d[r2["token"]]["het_han"] = time.time() - 5
brain_share.STORE.write_text(json.dumps(d), encoding="utf-8")
check("hết hạn là 404", c.get(f"/bs/{r2['token']}/goi.zip").status_code == 404)
check("token bịa là 404", c.get("/bs/khongcothat123456789012345/goi.zip").status_code == 404)
check("không chọn gì thì từ chối", c.post("/brains/share", data={"brain": BR, "items": "{}"}).status_code == 400)
check("slug độc hại bị từ chối", c.post("/brains/share", data={"brain": BR, "items": json.dumps({"agent": ["../x"]})}).status_code == 400)

# nhập từ link: chỉ https + đúng đường + địa chỉ công khai
for bad in ("http://example.com/bs/aaaaaaaaaaaaaaaaaaaaaaaa/goi.zip", "https://example.com/etc/passwd",
            "https://127.0.0.1/bs/aaaaaaaaaaaaaaaaaaaaaaaa/goi.zip",
            "https://localhost/bs/aaaaaaaaaaaaaaaaaaaaaaaa/goi.zip",
            "https://user:pw@example.com/bs/aaaaaaaaaaaaaaaaaaaaaaaa/goi.zip",
            "https://10.0.0.5/bs/aaaaaaaaaaaaaaaaaaaaaaaa/goi.zip"):
    rr = c.post("/brains/import-link", data={"url": bad, "to_brain": BR})
    check("từ chối link xấu: " + bad[:48], rr.status_code == 400, rr.text[:80])

# "/bs/" công khai phải CÓ gạch chéo cuối: "/bs" sẽ mở /bsomething
check('tiền tố công khai là "/bs/" có gạch chéo cuối', "/bs/" in main._AUTH_PUBLIC_PREFIX and "/bs" not in main._AUTH_PUBLIC_PREFIX)
check("/brains/share KHÔNG nằm trong đường công khai",
      not any("/brains/share".startswith(p) for p in main._AUTH_PUBLIC_PREFIX))
if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
