"""Plugin google-link-doc (26.10.144): đọc link Docs/Sheets/Slides công khai. Không mạng (giả _tai).

    python tests/run.py google_link_doc
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import os
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-glink-"))
_fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        _fails.append(n)


spec = importlib.util.spec_from_file_location("t_glink", str(ROOT / "system/plugins/google-link-doc/plugin.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
l, i, g = m.phan_tich(f"https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing#gid=987")
check("nhận Sheets + gid ở fragment", (l, i, g) == ("spreadsheets", ID, "987"), (l, i, g))
l, i, g = m.phan_tich(f"https://docs.google.com/document/d/{ID}/edit")
check("nhận Docs", l == "document" and g == "")
check("từ chối host lạ", m.phan_tich(f"https://evil.example.com/spreadsheets/d/{ID}")[0] is None)
check("từ chối localhost", m.phan_tich("http://127.0.0.1:8000/document/d/" + ID)[0] is None)
check("từ chối link không phải tài liệu", m.phan_tich("https://docs.google.com/forms/d/" + ID)[0] is None)
check("url xuất Sheets có gid", m.url_xuat("spreadsheets", ID, "987").endswith("export?format=csv&gid=987"))

goi = []


def gia(st, ct, text):
    async def _t(url):
        goi.append(url)
        return st, ct, text
    return _t


async def chay(args):
    return await m._doc(args)


m._tai = gia(200, "text/csv", "﻿link,fanpage\nhttps://fb.com/p/1,Halimi\n")
kq = asyncio.run(chay({"url": f"https://docs.google.com/spreadsheets/d/{ID}/edit#gid=5"}))
check("đọc CSV đúng, bỏ BOM", "link,fanpage" in kq and "﻿" not in kq and kq.startswith("[Google Sheets"), kq)
check("gọi đúng đường export", goi and "export?format=csv&gid=5" in goi[0], goi)

m._tai = gia(200, "text/html; charset=utf-8", "<html>Sign in</html>")
kq = asyncio.run(chay({"url": f"https://docs.google.com/document/d/{ID}/edit"}))
check("tài liệu riêng tư báo cách chia sẻ", kq.startswith("ERROR") and "Bất kỳ ai" in kq, kq)

m._tai = gia(401, "", "")
check("401 báo cách chia sẻ", "Bất kỳ ai" in asyncio.run(chay({"url": f"https://docs.google.com/document/d/{ID}/edit"})))

m._tai = gia(200, "text/plain", "x" * 40000)
kq = asyncio.run(chay({"url": f"https://docs.google.com/document/d/{ID}/edit"}))
check("cắt tài liệu dài", "đã cắt" in kq and len(kq) < 31000)

m._tai = gia(200, "text/plain", "")
check("tài liệu trống", asyncio.run(chay({"url": f"https://docs.google.com/document/d/{ID}/edit"})) == "Tài liệu trống.")
check("thiếu url", asyncio.run(chay({})).startswith("ERROR"))

# plugin nạp được qua plugins_host với readonly
import plugins_host  # noqa: E402
tools, route = plugins_host.plugin_tools("readonly", None)
check("tool có trong chế độ readonly", "google_link_doc" in {t["fn"] for t in tools})

if _fails:
    print("\nFAIL:", _fails)
    raise SystemExit(1)
print("\nOK")
