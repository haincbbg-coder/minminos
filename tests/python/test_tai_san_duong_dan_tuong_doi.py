"""Cột phải: file nhắc bằng đường dẫn TƯƠNG ĐỐI (attachments/x.mp4) phải lên danh sách, kèm mã tin gốc.

    python tests/run.py tai_san_duong_dan_tuong_doi
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-taisan2-"))
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from sessions import get_store  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


BRAIN = tempfile.mkdtemp(prefix="javis-brain-tuongdoi-")
b = Path(BRAIN)
(b / "attachments").mkdir()
(b / "attachments" / "video-h264.mp4").write_bytes(b"0" * 64)
(b / "attachments" / "thu-gui-excel.xlsx").write_bytes(b"0" * 64)
st = get_store()
SID = "tuong-doi"
st.get_or_create(SID, brain=BRAIN, engine="cli", model="x")
m1 = st.append_message(SID, "user", "chào")
m2 = st.append_message(SID, "assistant",
                       "| 1 | `attachments/video-h264.mp4` (772 KB) |\n"
                       "Excel: attachments/thu-gui-excel.xlsx xong. Giả định: `attachments/khong-co.mp4` và ../etc/passwd.png")
m3 = st.append_message(SID, "assistant", "Nhắc lại `attachments/video-h264.mp4`")
c = TestClient(main.app, base_url="http://127.0.0.1")
d = c.get(f"/sessions/{SID}/assets").json()
fs = {f["name"]: f for f in d["files"]}
check("video nhắc trong backtick, tương đối, có thật thì lên", "video-h264.mp4" in fs, list(fs))
check("excel nhắc trần, tương đối, có thật thì lên", "thu-gui-excel.xlsx" in fs)
check("file không có thật thì bỏ", "khong-co.mp4" not in fs)
check("đi ra ngoài brain bị bỏ", "passwd.png" not in fs)
check("mã tin gốc (mid) là lần nhắc ĐẦU, không phải lần nhắc lại",
      fs.get("video-h264.mp4", {}).get("mid") == m2 and m3 != m2, fs.get("video-h264.mp4"))
if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
