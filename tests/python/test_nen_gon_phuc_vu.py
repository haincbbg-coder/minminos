"""Dashboard nhẹ hơn khi mở (26.10.313): JS/CSS gửi bản nén gọn, vân tay khớp bản gửi, font tự lưu.

Phần "bản nén có cùng token với bản gốc" do tests/js/test_nen_gon.js lo (cần acorn). File này lo
đường phục vụ: máy chủ gửi đúng bản gọn, freshness.js băm đúng thứ nó nhận, tắt được bằng env.
"""
from _paths import ROOT, SERVER  # noqa: F401
import json
import os
import re
import sys
import tempfile
import zlib

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="minmin-nengon-")
sys.path.insert(0, str(SERVER))
import main  # noqa: E402
import nen_gon  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_fails = []


def check(name, cond, extra=""):
    print(("  ok  " if cond else "  FAIL ") + name + (f"  [{extra}]" if not cond and extra else ""))
    if not cond:
        _fails.append(name)


c = TestClient(main.app, base_url="http://127.0.0.1:8080")
DASH = ROOT / "dashboard"

r = c.get("/static/app.js?v=1", headers={"accept-encoding": "identity"})
goc = (DASH / "app.js").read_text(encoding="utf-8")
check("app.js trả về 200", r.status_code == 200, r.status_code)
check("app.js gửi bản nén gọn", r.text == nen_gon.nen_js(goc))
check("bản gọn nhẹ hơn bản gốc ít nhất 20%", len(r.content) < len(goc.encode()) * 0.8,
      f"{len(r.content)} / {len(goc.encode())}")
check("giữ nguyên số dòng (báo lỗi trình duyệt vẫn đúng dòng)", r.text.count("\n") == goc.count("\n"))
check("có ETag, cache 1 năm khi có ?v=", bool(r.headers.get("etag"))
      and "immutable" in (r.headers.get("cache-control") or ""))
r304 = c.get("/static/app.js?v=1", headers={"if-none-match": r.headers.get("etag", "")})
check("hỏi lại với ETag thì 304", r304.status_code == 304, r304.status_code)

css = c.get("/static/style.css?v=1")
check("CSS cũng gửi bản gọn", css.status_code == 200 and "/*" not in css.text
      and len(css.content) < (DASH / "style.css").stat().st_size)

ven = c.get("/static/vendor/lucide-icons.js?v=1")
check("thư viện vendor gửi nguyên văn", ven.content == (DASH / "vendor" / "lucide-icons.js").read_bytes())

# Vân tay nhúng trong trang phải là crc của CHÍNH bản gửi đi (freshness.js băm bản nó tải về)
trang = c.get("/").text
moc = json.loads(re.search(r'<script id="javis-fresh" type="application/json">(.*?)</script>', trang, re.S).group(1))
crc_app = moc["assets"].get("app.js")
check("vân tay app.js = crc32 của bản gọn",
      crc_app == format(zlib.crc32(r.content) & 0xFFFFFFFF, "08x"), crc_app)
check("URL trong trang mang đúng vân tay đó", f"/static/app.js?v={crc_app}" in trang)

# Đường trèo ra ngoài dashboard không được phục vụ qua lớp nén
tr = c.get("/static/../server/main.py")
check("không trèo ra ngoài dashboard", tr.status_code in (400, 404), tr.status_code)

# Tắt hẳn bằng env
os.environ["MINMIN_MINIFY"] = "0"
raw = c.get("/static/app.js?v=2", headers={"accept-encoding": "identity"})
check("MINMIN_MINIFY=0 gửi nguyên bản gốc", raw.content == (DASH / "app.js").read_bytes())
os.environ.pop("MINMIN_MINIFY", None)

# Font tự lưu
html = (DASH / "index.html").read_text(encoding="utf-8")
check("không còn gọi Google Fonts lúc mở trang", "fonts.googleapis.com" not in html)
check("nạp fonts.css tự lưu", "/static/fonts/fonts.css" in html)
fcss = (DASH / "fonts" / "fonts.css").read_text(encoding="utf-8")
thieu = [u for u in re.findall(r"url\(([^)]+)\)", fcss) if not (DASH / "fonts" / u).is_file()]
check("mọi file font trong fonts.css đều có thật", not thieu, thieu)
check("có giấy phép OFL kèm font", (DASH / "fonts" / "OFL.txt").is_file())
w = c.get("/static/fonts/be-vietnam-pro-400-vietnamese.woff2")
check("font được cache 30 ngày", w.status_code == 200 and "max-age=2592000" in (w.headers.get("cache-control") or ""))

for f in ("server/nen_gon.py", "dashboard/mang-ben.js", "dashboard/fonts/fonts.css"):
    check(f"{f} không có em dash", "—" not in (ROOT / f).read_text(encoding="utf-8"))

if _fails:
    print(f"\nFAIL - test_nen_gon_phuc_vu: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_nen_gon_phuc_vu")
