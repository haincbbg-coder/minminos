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
    check("xuất khoảng ngày trống: báo lỗi dễ hiểu", r.status_code == 400 and "tra cứu" in r.json()["error"].lower())
    r = c.get(A + f"/canh-bao?mst={MST}&tu=2026-01-01&den=2026-03-31").json()
    check("cảnh báo chạy được", r.get("ok") and isinstance(r["ds"], list))

    # ---- cài đặt tải: tên file, thư mục, giữ zip, số luồng (như app PC)
    cdat = c.get(A + "/cai-dat").json()
    check("cài đặt mặc định: tên theo ngày lập + đối tác + ký hiệu + số", cdat["cai_dat"]["ten_file"]["tokens"]
          == ["ngay_lap", "ten_doitac", "ky_hieu", "so_hd"] and cdat["vi_du_ten_file"].startswith("2026-09-15_"), cdat)
    cdat = c.post(A + "/cai-dat", json={"ten_file": {"tokens": ["so_hd", "mst", "khong-co"], "keep_viet": True},
                                        "xep_thu_muc": "ncc", "giu_zip": True, "luong": 99}).json()
    check("đổi mẫu tên file: bỏ thành phần lạ, xem trước đúng",
          cdat["cai_dat"]["ten_file"]["tokens"] == ["so_hd", "mst"] and cdat["vi_du_ten_file"] == "0000123_0312345678", cdat["vi_du_ten_file"])
    check("số luồng bị chặn trong 1-8", cdat["cai_dat"]["luong"] == 8)
    check("xếp theo nhà cung cấp, giữ dấu", "THỜI TRANG" in cdat["vi_du_thu_muc"], cdat["vi_du_thu_muc"])

    # tải 2 hoá đơn mới với cài đặt mới + PDF Trống đồng + giữ ZIP
    import shutil as _sh
    chrome = next((p for p in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",) if Path(p).is_file()),
                  _sh.which("chromium") or _sh.which("google-chrome") or "")
    hd.trinh_duyet_in_pdf = lambda: chrome
    moi2 = [x["key"] for x in d["ds"] if not x["co_xml"]][:2]
    r = c.post(A + "/tai", json={"mst": MST, "loai": "purchase", "keys": moi2, "kieu": ["pdf"]}).json()
    v = doi_viec(c, r["viec"], 180)
    check("tải kèm PDF Trống đồng chạy xong", v["trang_thai"] == "xong" and v["ket_qua"].get("ok") == 2, v.get("ket_qua") or v.get("loi"))
    kho = hd.doc_kho(MST, "purchase")
    a2 = [kho[k] for k in moi2]
    check("tên file theo mẫu mới (số HĐ_MST)", all(Path(x["_xml_path"]).stem == f"{int(x['shdon']):07d}_{x['nbmst']}" for x in a2),
          [x.get("_xml_path") for x in a2])
    check("thư mục theo tên nhà cung cấp", all(Path(x["_xml_path"]).parent.name == x["nbten"][:60].strip() for x in a2),
          [x.get("_xml_path") for x in a2])
    check("giữ ZIP gốc khi bật", all(hd.tuyet_doi(x.get("_zip_path")) for x in a2))
    if chrome:
        check("có PDF Trống đồng thật", all((hd.tuyet_doi(x.get("_pdf_path")) or Path("/x")).read_bytes()[:4] == b"%PDF"
                                            for x in a2 if hd.tuyet_doi(x.get("_pdf_path"))) and
              all(hd.tuyet_doi(x.get("_pdf_path")) for x in a2), [x.get("_pdf_loi") for x in a2])
        r = c.post(A + "/xuat", json={"mst": MST, "kieu": "pdf_gop", "che_do": "conthue", "loai": "purchase", "keys": moi2})
        check("gộp PDF để in", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200])
    else:
        print("skip PDF Trống đồng thật (máy test không có Chromium)")
        check("không có trình duyệt: ghi lý do, vẫn tải XML", all(x.get("_pdf_loi") and x.get("_xml_path") for x in a2))
    c.post(A + "/cai-dat", json={"ten_file": {"tokens": ["ngay_lap", "ten_doitac", "ky_hieu", "so_hd"], "keep_viet": False},
                                 "xep_thu_muc": "thang_lap", "giu_zip": False, "luong": 3})
    z = zipfile.ZipFile(io.BytesIO(c.post(A + "/xuat", json={"mst": MST, "kieu": "zip", "loai_tep": ["xml", "zip"],
                                                              "loai": "purchase", "keys": moi2}).content))
    check("ZIP theo loại file + chỉ dòng đã chọn, giữ cây thư mục MuaVao/...",
          len([n for n in z.namelist() if n.endswith(".xml")]) == 2 and len([n for n in z.namelist() if n.endswith(".zip")]) == 2
          and all(n.startswith("MuaVao/") for n in z.namelist()), z.namelist())
    z = zipfile.ZipFile(io.BytesIO(c.post(A + "/xuat", json={"mst": MST, "kieu": "html_zip", "tu": "2026-01-01", "den": "2026-03-31"}).content))
    check("HTML Trống đồng (.zip)", z.namelist() and all(n.endswith(".html") for n in z.namelist()), z.namelist())
    r = c.post(A + "/xuat", json={"mst": MST, "kieu": "excel", "tu": "2026-01-01", "den": "2026-03-31"})
    check("tên file Excel theo mẫu", "MuaBan_20260101_20260331_" + MST in __import__("urllib.parse").parse.unquote(
        r.headers.get("content-disposition", "")), r.headers.get("content-disposition"))

    # ---- dừng việc
    r = c.post(A + "/tai", json={"mst": MST, "loai": "sold", "tu": "2026-01-01", "den": "2026-03-31"}).json()
    c.post(A + f"/viec/{r['viec']}/dung")
    v = doi_viec(c, r["viec"])
    check("bấm Dừng thì việc dừng", v["trang_thai"] in ("huy", "xong"), v["trang_thai"])

    # ---- Gmail (bộ quét giả)
    check("Gmail chưa cấu hình", c.get(A + "/gmail/cau-hinh").json()["ds"] == [])
    r = c.post(A + "/gmail/cau-hinh", json={"email": "shop@gmail.com", "mat_khau": "MatKhauGmail@123"})
    check("dán mật khẩu Gmail thường: từ chối + chỉ sang Đăng nhập bằng Google",
          r.status_code == 400 and "Đăng nhập bằng Google" in r.json()["error"])
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
    hd0 = _mock_gdt.DATA["purchase"][0]
    k0 = f"{hd0['nbmst']}_{hd0['khmshdon']}{hd0['khhdon']}_{hd0['shdon']}"
    inv0 = hd.doc_kho(MST, "purchase").get(k0) or {}
    check("hoá đơn Gmail được ghép vào đúng hoá đơn trong Tải Hoá Đơn TCT (có bản gốc từ Gmail)",
          inv0.get("_goc_nguon") == "Gmail" and hd.tuyet_doi(inv0.get("_goc_path")) and hd.tuyet_doi(inv0.get("_xml_path")), inv0.keys())
    check("bảng Tải Hoá Đơn hiện Gốc (Gmail)", any(x["key"] == k0 and x["co_goc"] and x["goc_nguon"] == "Gmail"
                                                for x in c.get(A + f"/hoa-don?mst={MST}&loai=purchase").json()["ds"]))
    check("kết quả quét báo số đã ghép", (v["ket_qua"].get("ghep", 0) + v["ket_qua"].get("them_vao_kho", 0)) == 1, v["ket_qua"])
    check("email chỉ có link, không có file: không ghép bừa", not any(r.get("lien_ket") for r in kq if not r["co_xml"] and not r["co_pdf"]))
    co_xml = [r for r in kq if r["co_xml"]]
    check("kết quả Gmail: có hoá đơn kèm XML + PDF, đọc được người bán", co_xml and co_xml[0]["co_pdf"]
          and co_xml[0]["ban_ten"], kq)
    check("link javascript: từ email bị bỏ", all(not r["link"].startswith("javascript") for r in kq))
    check("lưu mốc quét để lần sau chỉ quét email mới", c.get(A + "/gmail/cau-hinh").json()["ds"][0]["co_moc"])
    check("kết quả ghi hộp thư nguồn", all(r.get("hop_thu") == "shop@gmail.com" for r in kq))
    check("lỗi IMAP 'Application-specific password required' được giải thích dễ hiểu",
          "Đăng nhập bằng Google" in hd._loi_gmail_de_hieu(Exception("b'[ALERT] Application-specific password required'")))

    # ---- cấu hình cũ (1 Gmail) vẫn đọc được
    ch = hd.doc_cau_hinh(); ch["gmail"] = {"email": "cu@gmail.com", "mk": hd.ma_hoa("abcdabcdabcdabcd")}; hd.ghi_cau_hinh(ch)
    check("cấu hình Gmail cũ hiện thành một tài khoản", any(x["email"] == "cu@gmail.com" for x in c.get(A + "/gmail/cau-hinh").json()["ds"]))
    c.delete(A + "/gmail/tai-khoan/cu@gmail.com")
    check("gỡ tài khoản", not any(x["email"] == "cu@gmail.com" for x in c.get(A + "/gmail/cau-hinh").json()["ds"]))

    # ---- Đăng nhập bằng Google (OAuth) với Google giả
    r = c.get(A + "/gmail/google/bat-dau", follow_redirects=False)
    check("chưa cài OAuth Client: báo cần cài", r.status_code == 403 and "OAuth Client" in r.text)
    check("Client ID sai dạng bị từ chối", c.post(A + "/gmail/google/client", json={"client_id": "abc", "client_secret": "x"}).status_code == 400)
    c.post(A + "/gmail/google/client", json={"client_id": "123-abc.apps.googleusercontent.com", "client_secret": "GOCSPX-bimat"})
    check("client secret không lưu chữ thường", "GOCSPX-bimat" not in (Path(_STATE) / "tai-hoa-don" / "cau-hinh.json").read_text(encoding="utf-8"))
    g = c.get(A + "/gmail/cau-hinh", headers={"x-forwarded-proto": "https", "x-forwarded-host": "minmin.vd.vn"}).json()["google"]
    check("đường về đúng tên miền bố thấy (sau Caddy)", g["duong_ve"] == "https://minmin.vd.vn" + A + "/gmail/google/ve", g)
    r = c.get(A + "/gmail/google/bat-dau", follow_redirects=False, headers={"x-forwarded-proto": "https", "x-forwarded-host": "minmin.vd.vn"})
    from urllib.parse import urlparse, parse_qs
    qg = parse_qs(urlparse(r.headers.get("location", "")).query)
    check("chuyển sang trang Google, chỉ xin quyền ĐỌC thư, có state",
          r.status_code == 302 and "accounts.google.com" in r.headers["location"]
          and qg["scope"][0] == hd.GMAIL_SCOPE + " email" and qg["access_type"][0] == "offline" and qg.get("state"))
    st = qg["state"][0]
    check("state lạ bị từ chối", c.get(A + "/gmail/google/ve?state=gia&code=x").status_code == 403)

    import requests as _rq

    class _R:
        def __init__(self, d, code=200):
            self._d, self.status_code, self.content = d, code, b"x"

        def json(self):
            return self._d

        def raise_for_status(self):
            pass

    goi = {}

    def _post(url, data=None, timeout=None, **k):
        goi.setdefault("post", []).append((url, dict(data or {})))
        if data.get("grant_type") == "authorization_code":
            return _R({"access_token": "at1", "refresh_token": "rt-bi-mat", "scope": hd.GMAIL_SCOPE + " openid"})
        return _R({"access_token": "at2"})

    def _get(url, headers=None, timeout=None, **k):
        return _R({"emailAddress": "Halimi.Ketoan@gmail.com"})

    p0, g0 = _rq.post, _rq.get
    _rq.post, _rq.get = _post, _get
    try:
        r = c.get(A + f"/gmail/google/ve?state={st}&code=ma1", follow_redirects=False)
    finally:
        _rq.post, _rq.get = p0, g0
    check("Google trả về: lưu tài khoản rồi quay lại tab Gmail",
          r.status_code == 302 and "tab=gmail" in r.headers.get("location", ""), r.text[:200])
    ex = [x for x in c.get(A + "/gmail/cau-hinh").json()["ds"] if x["email"] == "halimi.ketoan@gmail.com"]
    check("tài khoản Google hiện trong danh sách", ex and ex[0]["kieu"] == "google", ex)
    check("đổi mã lấy token đúng redirect_uri đã gửi",
          goi["post"][0][1]["redirect_uri"] == "https://minmin.vd.vn" + A + "/gmail/google/ve")
    check("refresh token lưu đã mã hoá", "rt-bi-mat" not in (Path(_STATE) / "tai-hoa-don" / "cau-hinh.json").read_text(encoding="utf-8"))
    check("state chỉ dùng một lần", c.get(A + f"/gmail/google/ve?state={st}&code=ma1").status_code == 403)

    # Bộ quét Gmail API: tìm thư theo ngày, đọc thư thô, mốc = thời điểm thư mới nhất
    import base64 as _b64
    tho = (b"From: hd@misa.vn\r\nSubject: Hoa don dien tu\r\nDate: x\r\nMIME-Version: 1.0\r\n"
           b"Content-Type: multipart/mixed; boundary=B\r\n\r\n--B\r\nContent-Type: text/plain\r\n\r\nHoa don\r\n"
           b"--B\r\nContent-Type: application/xml\r\nContent-Disposition: attachment; filename=hd.xml\r\n"
           b"Content-Transfer-Encoding: base64\r\n\r\n" + _b64.b64encode(xml_bytes) + b"\r\n--B--\r\n")
    hoi = []

    class _S:
        headers = {}

        def get(self, url, params=None, timeout=None):
            hoi.append((url, params))
            if url.endswith("/messages"):
                return _R({"messages": [{"id": "m2"}, {"id": "m1"}]})
            return _R({"raw": _b64.urlsafe_b64encode(tho).decode().rstrip("="), "internalDate": "1767225600000"})

        def close(self):
            pass

    p0 = _rq.post
    _rq.post = _post
    try:
        bq = hd.tao_bo_quet_google("halimi.ketoan@gmail.com", "rt", lambda s: None)
        bq._s = _S()
        bq.connect()
        recs = bq.scan(dt.date(2026, 1, 1), dt.date(2026, 1, 31))
    finally:
        _rq.post = p0
    check("Gmail API: tìm theo khoảng ngày", hoi[0][1]["q"] == "after:2026/01/01 before:2026/02/01", hoi[0])
    check("Gmail API: đọc thư mới nhất trước như bản IMAP", [h[0].rsplit("/", 1)[1] for h in hoi[1:]] == ["m2", "m1"])
    check("Gmail API: nhận ra hoá đơn có XML đính kèm", recs and recs[0].get("xml"), recs)
    check("Gmail API: mốc là thời điểm thư mới nhất", bq.last_uid == 1767225600)
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
