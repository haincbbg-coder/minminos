"""Tải Hoá Đơn TCT + Quét hoá đơn Gmail trên trình duyệt (26.10.6).

Chạy với cổng thuế GIẢ (tests/python/_mock_gdt.py, captcha luôn ABC12, mật khẩu 123456) nên
không cần mạng hay tài khoản thật. Gmail thay bằng bộ quét giả.

    python tests/python/test_hoa_don.py
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import datetime as dt
import io
import os
import re
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-hd-")
os.environ["JAVIS_STATE_DIR"] = _STATE
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import _mock_gdt  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), _mock_gdt.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["MINMIN_TCT_BASE"] = f"http://127.0.0.1:{srv.server_address[1]}/api"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import giay_phep  # noqa: E402
import routes.ket_noi_ngoai as knn  # noqa: E402
import routes.hoa_don as hd  # noqa: E402

giay_phep.STATE_DIR = Path(_STATE)
_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


def doi_viec(c, vid, han=120):
    het = time.time() + han
    while time.time() < het:
        v = c.get(A + f"/viec/{vid}").json()
        if v.get("trang_thai") != "dang_chay":
            return v
        time.sleep(0.3)
    return {"trang_thai": "qua_gio"}


APP = Path(ROOT) / "apps" / "tai-hoa-don"
# ---- mã nguồn
lib = list((APP / "thd").rglob("*.py"))
check("thư viện hoá đơn không mang phần bản quyền / khoá riêng cũ",
      not (APP / "thd" / "licensing.py").exists() and not list(APP.rglob("*.pem"))
      and not any("taokey" in p.name for p in lib))
check("thư viện chỉ import tương đối giữa các module của nó",
      not [p.name for p in lib if re.search(r"^\s*(from|import) (gdt_client|analysis|providers|invoice_xml|captcha_local)\b",
                                             p.read_text(encoding="utf-8"), re.M)])
em = [str(p.relative_to(APP)) for p in list(APP.rglob("*.py")) + list((APP / "web").glob("*"))
      if "—" in p.read_text(encoding="utf-8")]
check("không có ký tự em dash trong app", not em, em)
html = (APP / "web" / "index.html").read_text(encoding="utf-8")
check("index.html chỉ nạp file có trong danh sách phục vụ",
      set(re.findall(r'(?:src|href)="([a-z.\-]+\.(?:js|css))"', html)) <= hd.WEB_FILES)
check("link bên thứ ba chỉ nhận http(s)",
      hd.link_an_toan("javascript:alert(1)") == "" and hd.link_an_toan("https://x.vn/a?b=1") == "https://x.vn/a?b=1"
      and hd.link_an_toan('https://x.vn/"><script>') == "")
check("chuẩn hoá MST", hd.chuan_mst(" 0312739734 ") == "0312739734" and hd.chuan_mst("0100111948-061") == "0100111948-061")
try:
    hd.chuan_mst("../../etc")
    check("MST lạ bị từ chối", False)
except ValueError:
    check("MST lạ bị từ chối", True)
check("đường ngoài gốc dữ liệu không đọc được", hd.tuyet_doi("../../etc/passwd") is None)

app = FastAPI()
hd.register(app)
A = hd.GOC + "/api"
MST = "0312739734"

with TestClient(app) as c:
    # ---- cửa
    check("chưa mở khoá: trang 403", c.get(hd.GOC + "/").status_code == 403)
    check("chưa mở khoá: API tải hoá đơn 403", c.get(A + "/doanh-nghiep").status_code == 403)
    check("chưa mở khoá: API Gmail 403", c.get(A + "/gmail/cau-hinh").status_code == 403)
    giay_phep.tao_cap_khoa()
    check("có mã nhưng chưa đồng ý điều khoản: vẫn chặn", c.get(A + "/doanh-nghiep").status_code == 403)
    knn.ghi_dong_y("chung")
    st = c.get(A + "/trang-thai").json()
    check("đủ điều kiện: cả hai app mở", st["tai_hoa_don"] and st["gmail"], st)
    check("trang mở", c.get(hd.GOC + "/").status_code == 200 and c.get(hd.GOC + "/app.js").status_code == 200)
    check("file lạ không phục vụ", c.get(hd.GOC + "/thd").status_code == 404)

    # ---- doanh nghiệp + mật khẩu mã hoá
    r = c.post(A + "/doanh-nghiep", json={"mst": MST, "ten": "Đại Phú", "mat_khau": "123456"}).json()
    check("thêm doanh nghiệp", r.get("ok") and r["mst"] == MST, r)
    raw = (Path(_STATE) / "tai-hoa-don" / "cau-hinh.json").read_text(encoding="utf-8")
    check("mật khẩu cổng thuế không lưu dạng chữ thường", "123456" not in raw and '"mk"' in raw)
    check("khoá mã hoá quyền 600", oct((Path(_STATE) / "tai-hoa-don" / ".khoa").stat().st_mode & 0o777) == "0o600")
    ds = c.get(A + "/doanh-nghiep").json()["ds"]
    check("danh sách có MST, chưa đăng nhập, có mật khẩu", ds and ds[0]["co_mk"] and not ds[0]["dang_nhap"], ds)

    r = c.post(A + "/tra-cuu", json={"mst": MST, "tu": "2026-01-01", "den": "2026-03-31"})
    check("chưa đăng nhập thì không cho tra cứu", r.status_code == 400 and "đăng nhập" in r.json()["error"])

    # ---- captcha + đăng nhập
    cap = c.get(A + f"/captcha?mst={MST}").json()
    check("lấy captcha trả SVG + key", cap.get("ok") and "<svg" in cap["svg"] and cap["key"], cap)
    r = c.post(A + "/dang-nhap", json={"mst": MST, "captcha": "SAI", "ckey": cap["key"]})
    check("captcha sai: báo lỗi", r.status_code == 400)
    r = c.post(A + "/dang-nhap", json={"mst": MST, "captcha": "ABC12", "ckey": cap["key"]}).json()
    check("đăng nhập bằng mật khẩu đã lưu", r.get("ok") and r["het_han"] > time.time(), r)
    ph = (Path(_STATE) / "tai-hoa-don" / "phien" / f"{MST}.json").read_text(encoding="utf-8")
    check("token phiên lưu đã mã hoá", _mock_gdt.FAKE_JWT not in ph)
    hd._CLIENT.clear()
    check("phiên nạp lại được sau khi khởi động lại", c.get(A + "/doanh-nghiep").json()["ds"][0]["dang_nhap"])

    # ---- tra cứu
    r = c.post(A + "/tra-cuu", json={"mst": MST, "tu": "2026-01-01", "den": "2026-03-31", "loai": "ca_hai"}).json()
    check("tra cứu chạy nền", r.get("ok") and r.get("viec"), r)
    v = doi_viec(c, r["viec"])
    check("tra cứu xong", v["trang_thai"] == "xong", v.get("loi") or v.get("nhat_ky", [])[-3:])
    mua = [x for x in _mock_gdt.DATA["purchase"] if x["ttxly"] in (5, 6, 8)]
    d = c.get(A + f"/hoa-don?mst={MST}&loai=purchase&tu=2026-01-01&den=2026-03-31").json()
    check("đủ số hoá đơn mua vào", d["tong"]["so_hd"] == len(mua), (d["tong"], len(mua)))
    check("tổng tiền khớp", abs(d["tong"]["tong"] - sum(x["tgtttbso"] for x in mua)) < 1)
    db = c.get(A + f"/hoa-don?mst={MST}&loai=sold").json()
    check("có hoá đơn bán ra", db["tong"]["so_hd"] == len(_mock_gdt.DATA["sold"]))
    d2 = c.get(A + f"/hoa-don?mst={MST}&loai=purchase&tu=2026-01-01&den=2026-01-31").json()
    check("lọc theo ngày", 0 < d2["tong"]["so_hd"] < d["tong"]["so_hd"])

    # ---- tải XML (3 hoá đơn chọn)
    keys = [x["key"] for x in d["ds"][:3]]
    r = c.post(A + "/tai", json={"mst": MST, "loai": "purchase", "keys": keys}).json()
    v = doi_viec(c, r["viec"])
    check("tải XML xong", v["trang_thai"] == "xong" and v["ket_qua"].get("ok") == 3, v.get("ket_qua") or v.get("loi"))
    d = c.get(A + f"/hoa-don?mst={MST}&loai=purchase&tu=2026-01-01&den=2026-03-31").json()
    co = [x for x in d["ds"] if x["co_xml"]]
    check("3 hoá đơn đã có XML", len(co) == 3 and d["tong"]["co_xml"] == 3)
    k = co[0]["key"]
    x = c.get(A + f"/tep/{MST}/purchase/{k}/xml")
    check("tải file XML về", x.status_code == 200 and b"<HDon>" in x.content
          and "attachment" in x.headers.get("content-disposition", ""))
    h = c.get(A + f"/xem/{MST}/purchase/{k}")
    check("xem hoá đơn: HTML + CSP chặn script", h.status_code == 200
          and "default-src 'none'" in h.headers.get("content-security-policy", ""))
    check("file nằm trong STATE/tai-hoa-don/du-lieu/<MST>/MuaVao",
          list((Path(_STATE) / "tai-hoa-don" / "du-lieu" / MST / "MuaVao").rglob("*.xml")))
    check("không có file lạ qua đường tep", c.get(A + f"/tep/{MST}/purchase/{k}/passwd").status_code == 404)

    # ---- xuất
    for kieu, dau in (("excel", b"PK"), ("bang_ke", b"PK"), ("chi_tiet", b"PK"), ("zip", b"PK")):
        r = c.post(A + "/xuat", json={"mst": MST, "tu": "2026-01-01", "den": "2026-03-31", "kieu": kieu})
        check(f"xuất {kieu}", r.status_code == 200 and r.content[:2] == dau, r.text[:200] if r.status_code != 200 else "")
    z = zipfile.ZipFile(io.BytesIO(c.post(A + "/xuat", json={"mst": MST, "tu": "2026-01-01", "den": "2026-03-31", "kieu": "zip"}).content))
    check("ZIP chứa đúng các XML đã tải", sum(1 for n in z.namelist() if n.endswith(".xml")) == 3, z.namelist())
    r = c.post(A + "/xuat", json={"mst": MST, "tu": "2020-01-01", "den": "2020-01-31", "kieu": "excel"})
    check("xuất khoảng ngày trống: báo lỗi dễ hiểu", r.status_code == 400 and "Tra cứu" in r.json()["error"])
    r = c.get(A + f"/canh-bao?mst={MST}&tu=2026-01-01&den=2026-03-31").json()
    check("cảnh báo chạy được", r.get("ok") and isinstance(r["ds"], list))

    # ---- dừng việc
    r = c.post(A + "/tai", json={"mst": MST, "loai": "sold", "tu": "2026-01-01", "den": "2026-03-31"}).json()
    c.post(A + f"/viec/{r['viec']}/dung")
    v = doi_viec(c, r["viec"])
    check("bấm Dừng thì việc dừng", v["trang_thai"] in ("huy", "xong"), v["trang_thai"])

    # ---- Gmail (bộ quét giả)
    check("Gmail chưa cấu hình", c.get(A + "/gmail/cau-hinh").json()["email"] == "")
    check("Gmail sai địa chỉ bị từ chối", c.post(A + "/gmail/cau-hinh", json={"email": "abc"}).status_code == 400)
    c.post(A + "/gmail/cau-hinh", json={"email": "shop@gmail.com", "mat_khau": "abcd efgh ijkl mnop"})
    raw = (Path(_STATE) / "tai-hoa-don" / "cau-hinh.json").read_text(encoding="utf-8")
    check("mật khẩu ứng dụng Gmail mã hoá", "abcdefghijklmnop" not in raw and "abcd efgh" not in raw)
    xml_mau = _mock_gdt.make_zip(_mock_gdt.DATA["purchase"][0])
    xml_bytes = zipfile.ZipFile(io.BytesIO(xml_mau)).read(
        [n for n in zipfile.ZipFile(io.BytesIO(xml_mau)).namelist() if n.endswith(".xml")][0])

    class BoQuetGia:
        def __init__(self, email, pw, log=None, solver=None):
            assert email == "shop@gmail.com" and pw == "abcdefghijklmnop", (email, pw)
            self.log = log or (lambda s: None)
            self.last_uid = 0

        def connect(self):
            pass

        def close(self):
            pass

        def scan(self, a, b, want_download=True, progress=None, since_uid=None, cancel_check=None, **kw):
            self.last_uid = 99
            progress and progress(1, 2)
            return [{"subject": "Hoá đơn điện tử", "from": "hd@misa.vn", "date": "x", "provider": "misa",
                     "xml": xml_bytes, "pdf": b"%PDF-1.4 x", "status": "Đính kèm: XML, PDF", "needs_manual": False},
                    {"subject": "HĐ BKAV", "from": "a@bkav.com", "date": "y", "provider": "bkav", "xml": None,
                     "pdf": None, "status": "cần tải tay", "needs_manual": True, "_so_hd": "123",
                     "lookup_url": "javascript:alert(1)", "_mtc": "ABCD"}]

    gs = hd.thd("gmail_scan")
    goc_cls = gs.GmailScanner
    gs.GmailScanner = BoQuetGia
    try:
        r = c.post(A + "/gmail/quet", json={"tu": "2026-01-01", "den": "2026-03-31"}).json()
        v = doi_viec(c, r["viec"])
        check("quét Gmail xong", v["trang_thai"] == "xong" and v["ket_qua"].get("moi") == 2, v.get("ket_qua") or v.get("loi"))
    finally:
        gs.GmailScanner = goc_cls
    kq = c.get(A + "/gmail/ket-qua").json()["ds"]
    co_xml = [r for r in kq if r["co_xml"]]
    check("kết quả Gmail: có hoá đơn kèm XML + PDF, đọc được người bán", co_xml and co_xml[0]["co_pdf"]
          and co_xml[0]["ban_ten"], kq)
    check("link javascript: từ email bị bỏ", all(not r["link"].startswith("javascript") for r in kq))
    check("lưu mốc quét để lần sau chỉ quét email mới", c.get(A + "/gmail/cau-hinh").json()["co_moc"])
    check("xem hoá đơn Gmail", c.get(A + f"/gmail/xem/{co_xml[0]['id']}").status_code == 200)
    check("tải PDF Gmail", c.get(A + f"/gmail/tep/{co_xml[0]['id']}/pdf").content.startswith(b"%PDF"))
    check("Excel Gmail", c.post(A + "/gmail/xuat").content[:2] == b"PK")
    check("ZIP Gmail", c.post(A + "/gmail/zip").content[:2] == b"PK")

srv.shutdown()
print()
if _fails:
    print(f"FAILED {len(_fails)}: {_fails}")
    sys.exit(1)
print("ALL OK")
