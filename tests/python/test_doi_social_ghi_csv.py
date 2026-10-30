"""26.10.311: Worker Chrome tích hợp trên VPS chạy trong /app chỉ đọc. Bảng CSV của các mẫu quét
phải ghi được vào thư mục dữ liệu/thư mục tạm thay vì báo "Permission denied". KHÔNG mạng.
python tests/run.py doi_social_ghi_csv"""
import os, stat, sys, tempfile
from pathlib import Path
from _paths import ROOT  # noqa: F401

sys.path.insert(0, str(ROOT / "apps" / "doi-social" / "worker"))
import tien_ich_web as w  # noqa: E402

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


goc = Path(tempfile.mkdtemp())
w.THU_MUC = goc            # không ghi bảng thử vào thư mục mã nguồn
p = w.ghi_csv("thu.csv", ["a", "b"], [{"a": "Váy", "b": 1}])
check("ghi được ở chỗ mặc định", p.exists() and "Váy" in p.read_text(encoding="utf-8-sig"))

chi_doc = goc / "worker"
chi_doc.mkdir()
os.chmod(chi_doc, stat.S_IRUSR | stat.S_IXUSR)
cu = w.THU_MUC
w.THU_MUC = chi_doc
du_lieu = goc / "state"
os.environ["JAVIS_STATE_DIR"] = str(du_lieu)
try:
    if os.access(chi_doc, os.W_OK):          # chạy bằng root: quyền chỉ đọc không có tác dụng, giả lập lỗi
        goc_mkdir = Path.mkdir

        def _mkdir(self, *a, **k):
            if str(self).startswith(str(chi_doc)):
                raise PermissionError(13, "Permission denied", str(self))
            return goc_mkdir(self, *a, **k)
        Path.mkdir = _mkdir
    p2 = w.ghi_csv("vps.csv", ["a"], [{"a": "x"}])
    check("thư mục worker chỉ đọc thì ghi sang thư mục dữ liệu", p2.exists() and str(p2).startswith(str(du_lieu)), p2)
finally:
    w.THU_MUC = cu
    if "goc_mkdir" in dir():
        Path.mkdir = goc_mkdir
    os.chmod(chi_doc, stat.S_IRWXU)

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
