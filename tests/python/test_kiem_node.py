"""Vá Node.js tháng 10/2026 (26.10.310): ảnh Docker ghim bản đã vá, bộ cài lấy bản vá, MinMin tự soi Node.js.

    python tests/run.py kiem_node      (không cần mạng)

Ghim ở đây:
  1. Xếp loại phiên bản: dòng còn hỗ trợ đã vá / thiếu vá / hết hỗ trợ / dòng mới hơn mọi dòng đã biết.
  2. Tin trong chuông: máy đã vá hoặc không có Node.js thì im; thiếu vá thì nói rõ cách sửa theo kiểu cài.
  3. Dockerfile, install.sh, install.ps1 và server/kiem_node.py khớp cùng một đợt vá.
  4. Trang /notifications: tin phát chung bị thay bằng tin theo Node.js THẬT của máy.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import re
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-node-"))
os.environ["JAVIS_ALLOWED_HOSTS"] = "testserver"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import kiem_node as kn  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


# ---- 1. Xếp loại ----
check("đọc v22.12.0", kn.doc_phien_ban("v22.12.0\n") == (22, 12, 0))
check("rác thì None", kn.doc_phien_ban("command not found") is None)
check("22 đã vá", kn.xep_loai((22, 23, 4)) == "on" and kn.xep_loai((22, 24, 0)) == "on")
check("22 thiếu vá", kn.xep_loai((22, 23, 3)) == "thieu_va" and kn.xep_loai((22, 12, 0)) == "thieu_va")
check("24 thiếu vá", kn.xep_loai((24, 22, 0)) == "thieu_va")
check("26 đã vá", kn.xep_loai((26, 12, 1)) == "on")
check("20 hết hỗ trợ", kn.xep_loai((20, 19, 0)) == "het_ho_tro")
check("dòng lẻ 23 hết hỗ trợ", kn.xep_loai((23, 11, 0)) == "het_ho_tro")
check("dòng mới hơn mọi dòng đã biết thì coi là ổn", kn.xep_loai((28, 0, 0)) == "on")
check("không có Node.js thì không nhắc", kn.xep_loai(None) == "on" and kn.tin_canh_bao(None, "native") is None)

# ---- 2. Tin trong chuông ----
check("đã vá thì không có tin", kn.tin_canh_bao((22, 23, 4), "native") is None)
t = kn.tin_canh_bao((22, 12, 0), "windows")
check("thiếu vá: tin bảo mật ưu tiên cao", t and t["kind"] == "security" and t["priority"] == "high", t)
check("tin nói đúng phiên bản máy", "v22.12.0" in t["summary"] and t["id"].endswith(":v22.12.0"))
check("Windows: chỉ cách winget", "winget upgrade OpenJS.NodeJS.LTS" in t["body"])
check("Docker: chỉ cách cập nhật MinMin", "Cập nhật MinMin" in kn.tin_canh_bao((22, 1, 0), "docker")["body"])
check("hết hỗ trợ: nói không có bản vá", "hết hỗ trợ" in kn.tin_canh_bao((20, 1, 0), "native")["summary"])
check("có link thông báo của Node.js", t["cta"]["url"] == kn.DOT_VA_URL)
check("không có em dash, không lộ tên Javis",
      all("—" not in str(v) and "Javis" not in str(v) for v in t.values()))

# ---- 3. Ba chỗ ghim khớp nhau ----
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
m = re.search(r"FROM node:(\d+\.\d+\.\d+)-bookworm-slim AS node_source", DOCKER)
check("Dockerfile ghim ĐÚNG một bản Node (không thẻ trôi node:22)", bool(m), "FROM node:...")
check("bản ghim trong Dockerfile = BAN_DOCKER", m and m.group(1) == kn.BAN_DOCKER, m and m.group(1))
check("bản ghim trong Dockerfile đã vá", m and kn.xep_loai(kn.doc_phien_ban(m.group(1))) == "on")
SH = (ROOT / "install.sh").read_text(encoding="utf-8")
for dong, ban in kn.BAN_VA.items():
    check(f"install.sh: sàn dòng {dong} = {'.'.join(map(str, ban))}",
          f"{dong}) echo {'.'.join(map(str, ban))};;" in SH)
check("install.sh cài lại 22 chưa vá chứ không chỉ khi thiếu Node", "outdated" in SH and "need_node()" in SH
      and "-lt 20 ]" not in SH)
PS = (ROOT / "install.ps1").read_text(encoding="utf-8")
for dong, ban in kn.BAN_VA.items():
    check(f"install.ps1: sàn dòng {dong}", f'{dong} = [version]"{".".join(map(str, ban))}"' in PS)
check("install.ps1 nâng Node 22 chưa vá bằng winget", "winget upgrade -e --id OpenJS.NodeJS.LTS" in PS)
check("install.ps1 vẫn là ASCII (PowerShell 5 đọc file không BOM)", all(ord(c) < 128 for c in PS))

# ---- 4. /notifications thay tin phát chung bằng tin theo máy ----
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

cl = TestClient(main.app)


async def _ann():
    return ([{"id": kn.DOT_VA_ID, "kind": "security", "title": "x", "published_at": "2026-10-28"}], None)


async def _cl():
    return {"releases": [], "current": "26.10.310", "latest": "26.10.310"}

_goc = (main._load_community_announcements, main.changelog_index, kn.phien_ban_node)
try:
    main._load_community_announcements, main.changelog_index = _ann, _cl
    kn.phien_ban_node = lambda: (22, 12, 0)
    main._NOTIFICATION_CACHE.clear()
    r = cl.get("/notifications")
    check("/notifications trả 200", r.status_code == 200, r.text[:200])
    d = r.json()
    ids = [i["id"] for i in d.get("items") or []]
    check("máy thiếu vá: có đúng một tin theo máy, tin phát chung bị bỏ",
          ids.count(kn.DOT_VA_ID) == 0 and sum(1 for i in ids if i.startswith(kn.DOT_VA_ID + ":")) == 1, ids)
    kn.phien_ban_node = lambda: (22, 23, 4)
    main._NOTIFICATION_CACHE.clear()
    r = cl.get("/notifications")
    d = r.json() if r.status_code == 200 else {"items": [{"id": kn.DOT_VA_ID + ":loi"}]}
    check("máy đã vá: không có tin Node nào", not any(str(i["id"]).startswith(kn.DOT_VA_ID)
                                                     for i in d.get("items") or []), d.get("items"))
finally:
    main._load_community_announcements, main.changelog_index, kn.phien_ban_node = _goc
    main._NOTIFICATION_CACHE.clear()

check("ANNOUNCEMENTS.json mang tin phát chung cho bản cũ",
      kn.DOT_VA_ID in (ROOT / "ANNOUNCEMENTS.json").read_text(encoding="utf-8"))
check("server soi Node.js lúc khởi động", "kiem_node.tu_soi_khi_khoi_dong" in (SERVER / "main.py").read_text(encoding="utf-8"))

print()
if _fails:
    raise SystemExit(f"FAIL {len(_fails)}: " + "; ".join(_fails[:4]))
print("All green.")
