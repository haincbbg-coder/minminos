"""Đội Social: kho (ghép máy, nick, việc, duyệt, giới hạn), HTTP cho worker, bộ gõ giống người.
python tests/run.py doi_social"""
import base64, json, os, random, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
from _paths import ROOT  # noqa: E402

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


def raises(fn, chua=""):
    try:
        fn()
    except ValueError as e:
        return chua in str(e)
    return False


import doi_social as ds  # noqa: E402

goc = Path(tempfile.mkdtemp())
ds.mo(goc / "kho")
cho_phep = goc / "brain"
(cho_phep / "inbox").mkdir(parents=True)
anh = cho_phep / "inbox" / "a.jpg"
anh.write_bytes(b"\xff\xd8anh")
ngoai = goc / "bi-mat.jpg"
ngoai.write_bytes(b"x")
ds.dat_goc_tep([cho_phep])

# ---- ghép máy
ma = ds.tao_ma_ghep()
check("mã ghép 6 số", len(ma) == 6 and ma.isdigit())
check("mã sai bị từ chối", raises(lambda: ds.ghep("000000" if ma != "000000" else "111111"), "sai"))
kq = ds.ghep(ma, "PC nhà")
check("ghép trả token mmw_ và id máy", kq["token"].startswith("mmw_") and kq["may_id"].startswith("m"))
check("mã chỉ dùng một lần", raises(lambda: ds.ghep(ma), "sai"))
check("token đúng tìm ra máy, token sai thì không",
      ds.may_theo_token(kq["token"])["id"] == kq["may_id"] and ds.may_theo_token("mmw_xxx") is None
      and ds.may_theo_token("") is None)
raw_db = (goc / "kho" / "doi-social.db").read_bytes()
check("token không lưu dạng rõ trên đĩa", kq["token"].encode() not in raw_db)
may = kq["may_id"]

ds.nhip(may, [{"id": "p1", "ten": "Minh Anh - J'oli Store", "trinh_duyet": "chrome", "co_proxy": False},
              {"id": "p2", "ten": "Muse 001", "trinh_duyet": "firefox"},
              {"id": "p3", "ten": "Minh Anh 2", "trinh_duyet": "chrome", "co_proxy": True}], driver_ok=True)
m = ds.ds_may()[0]
check("nhịp cập nhật nick và trạng thái máy", m["so_nick"] == 3 and m["online"] and m["driver_ok"] == 1
      and "token_bam" not in m)
check("tìm nick không dấu, khớp đúng tên trước",
      [n["id"] for n in ds.tim_nick("minh anh - j'oli store")] == ["p1"]
      and {n["id"] for n in ds.tim_nick("minh anh")} == {"p1", "p3"})

# ---- tạo việc
check("trùng nhiều nick thì báo để hỏi lại",
      raises(lambda: ds.tao_viec(ky_nang="fb_dang_bai", nick="minh anh", noi_dung="x"), "nhiều nick"))
check("nick Firefox bị từ chối", raises(lambda: ds.tao_viec(ky_nang="fb_dang_bai", nick="Muse 001", noi_dung="x"), "Firefox"))
check("kỹ năng lạ bị từ chối", raises(lambda: ds.tao_viec(ky_nang="xoa_het", nick="Minh Anh 2", noi_dung="x"), "kỹ năng"))
check("bài rỗng bị từ chối", raises(lambda: ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2"), "chữ hoặc"))
check("nơi đăng phải là link facebook https",
      raises(lambda: ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2", noi_dung="x", noi_dang="http://evil.com"), "facebook"))
check("tệp ngoài thư mục cho phép bị từ chối",
      raises(lambda: ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2", noi_dung="x", tep=[str(ngoai)]), "ngoài"))
check("việc hỏng tệp không để lại rác", ds.ds_viec() == [])
v = ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2", noi_dung="Váy mới về 🌸\nInbox nhé", tep=[str(anh)],
                chat_id="123")
check("việc mới chờ duyệt, tệp đã chép vào kho",
      v["trang_thai"] == "cho_duyet" and v["tham_so"]["tep"][0]["luu"] == "00.jpg"
      and ds.duong_tep(v["id"], "00.jpg").read_bytes() == anh.read_bytes())
check("đường tệp lạ không thoát kho", ds.duong_tep(v["id"], "../doi-social.db") is None)
check("máy không nhận việc chưa duyệt", ds.nhan_viec(may) is None)
check("tóm tắt có nick, tệp và nội dung", "Minh Anh 2" in ds.tom_tat(v) and "a.jpg" in ds.tom_tat(v)
      and "Váy mới về" in ds.tom_tat(v))

v = ds.duyet(v["id"], True)
check("duyệt chuyển sang chờ máy", v["trang_thai"] == "cho_chay")
check("không duyệt lại lần hai", raises(lambda: ds.duyet(v["id"], True), "trạng thái"))
nv = ds.nhan_viec(may)
check("máy nhận đúng việc, chuyển đang chạy", nv and nv["id"] == v["id"] and nv["trang_thai"] == "dang_chay")
check("mỗi máy một việc một lúc", ds.nhan_viec(may) is None)
check("máy khác không ghi kết quả được", raises(lambda: ds.ghi_ket_qua(v["id"], "mkhac", True), "không thuộc"))
xong = ds.ghi_ket_qua(v["id"], may, True, "Đã đăng", ["a", "b"], b"\x89PNGanh")
check("ghi kết quả + ảnh, dọn tệp đính kèm",
      xong["trang_thai"] == "xong" and xong["co_anh"] == 1 and ds.duong_anh(v["id"]).read_bytes() == b"\x89PNGanh"
      and not (goc / "kho" / "tep" / str(v["id"])).exists() and xong["buoc"] == ["a", "b"])

# ---- khoảng nghỉ và giới hạn ngày
v2 = ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2", noi_dung="bài 2", can_duyet=False)
check("không cần duyệt thì vào thẳng hàng chờ", v2["trang_thai"] == "cho_chay")
check("chưa hết khoảng nghỉ thì máy chưa nhận", ds.nhan_viec(may) is None)
ds.dat_gioi_han(nghi_phut=0)
check("hết khoảng nghỉ thì nhận", (ds.nhan_viec(may) or {}).get("id") == v2["id"])
ds.ghi_ket_qua(v2["id"], may, False, "nút Đăng bị khoá")
ds.dat_gioi_han(bai_moi_ngay=2)
ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2", noi_dung="bài 3")
check("đủ số bài trong ngày thì chặn (bài lỗi không tính)",
      raises(lambda: ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh 2", noi_dung="bài 4"), "đủ 2 bài"))
check("giới hạn bị kẹp trong khoảng hợp lệ", ds.dat_gioi_han(bai_moi_ngay=999)["bai_moi_ngay"] == 50)
ds.dat_gioi_han(bai_moi_ngay=5)

# ---- việc treo quá giờ
v4 = ds.tao_viec(ky_nang="fb_dang_bai", nick="Minh Anh - J'oli Store", noi_dung="treo", can_duyet=False)
ds.nhan_viec(may)
with ds._db() as c:
    c.execute("UPDATE viec SET bat_dau=? WHERE id=?", (time.time() - ds.HET_GIO_CHAY - 5, v4["id"]))
ds.nhip(may)
check("đang chạy quá giờ thì thành lỗi", ds.lay_viec(v4["id"])["trang_thai"] == "loi")

# ---- HTTP cho worker
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import giay_phep  # noqa: E402
import routes.ket_noi_ngoai as knn  # noqa: E402
import routes.doi_social as rds  # noqa: E402

giay_phep.da_mo = lambda app_id: app_id == "doi_social"
knn.da_dong_y = lambda phan: True
bao = []


def cho_bao(muc, giay=3.0):
    """Báo chủ chạy ở nền: chờ tối đa vài giây cho nó tới."""
    han = time.time() + giay
    while time.time() < han and muc not in bao:
        time.sleep(0.05)
    return muc in bao


async def _bao(viec, su_kien):
    bao.append((viec["id"], su_kien))

app = FastAPI()
rds.register(app, rds.DoiSocialDeps(bao=_bao))
with TestClient(app) as tc:
    r = tc.post("/doi-social/may/ghep", json={"ma": "12345"})
    check("ghép qua HTTP: mã sai trả 400", r.status_code == 400)
    ma2 = tc.post("/doi-social/ma-ghep").json()["ma"]
    r = tc.post("/doi-social/may/ghep", json={"ma": ma2, "ten": "PC2"})
    tok = r.json().get("token", "")
    check("ghép qua HTTP trả token", r.status_code == 200 and tok.startswith("mmw_"))
    H = {"x-minmin-may": tok}
    check("không token thì 401", tc.get("/doi-social/may/viec?cho=0").status_code == 401)
    check("token bậy thì 401", tc.get("/doi-social/may/viec?cho=0", headers={"x-minmin-may": "mmw_bay"}).status_code == 401)
    r = tc.post("/doi-social/may/nhip", headers=H,
                json={"nick": [{"id": "q1", "ten": "Tô Mi Yến - Cludy Studio", "trinh_duyet": "chrome"}], "driver_ok": True})
    check("nhịp qua HTTP trả giới hạn", r.status_code == 200 and r.json()["gioi_han"]["bai_moi_ngay"] == 5)
    check("chưa có việc: long-poll trả null", tc.get("/doi-social/may/viec?cho=0", headers=H).json()["viec"] is None)
    r = tc.post("/doi-social/viec", json={"nick": "to mi yen", "noi_dung": "Chào cả nhà"})
    vid = r.json()["viec"]["id"]
    check("trang web tạo việc chờ duyệt và báo chủ", r.status_code == 200 and cho_bao((vid, "cho_duyet")), bao)
    check("duyệt qua HTTP", tc.post(f"/doi-social/viec/{vid}/duyet", json={"dong_y": True}).json()["viec"]["trang_thai"] == "cho_chay")
    j = tc.get("/doi-social/may/viec?cho=0", headers=H).json()["viec"]
    check("worker nhận việc vừa duyệt", j and j["id"] == vid and j["nick_id"] == "q1")
    png = base64.b64encode(b"\x89PNGxx").decode()
    r = tc.post(f"/doi-social/may/ket-qua/{vid}", headers=H, json={"ok": True, "thong_diep": "Đã đăng", "buoc": ["x"], "anh": png})
    check("gửi kết quả qua HTTP và báo chủ", r.status_code == 200 and cho_bao((vid, "xong")), bao)
    check("ảnh kết quả xem được", tc.get(f"/doi-social/anh/{vid}.png").content == b"\x89PNGxx")
    st = tc.get("/doi-social/trang-thai").json()
    check("trạng thái có máy, nick, việc", len(st["may"]) == 2 and any(n["id"] == "q1" for n in st["nick"]))
    z = tc.get("/doi-social/tai-worker.zip")
    check("tải gói Worker (có file chạy, không có worker.json)",
          z.status_code == 200 and b"minmin_worker.py" in z.content and b"worker.json" not in z.content)
    giay_phep.da_mo = lambda app_id: False
    check("app chưa mở khoá thì worker bị chặn 403",
          tc.get("/doi-social/may/viec?cho=0", headers=H).status_code == 403)

# ---- cổng đăng nhập của main.py miễn đúng tiền tố, đúng phương thức
src = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
check("main.py miễn đăng nhập chỉ GET/POST của tiền tố worker",
      '_DOI_SOCIAL_MAY = ("/doi-social/may/", ("GET", "POST"))' in src
      and "path.startswith(_DOI_SOCIAL_MAY[0]) and request.method in _DOI_SOCIAL_MAY[1]" in src)

# ---- bộ gõ giống người (worker)
sys.path.insert(0, str(ROOT / "apps" / "doi-social" / "worker"))
import nguoi  # noqa: E402

mau = ["Váy lụa mới về 🌸 giá 459k!\nInbox shop nhé, link: https://halimi.vn/vay-lua-01 #halimi @MinhAnh",
       "Đẹp quá trời luôn. Ai mua thì nhắn em nha, ship toàn quốc.",
       "ABC xyz Test QUICK brown fox jumps over the lazy dog " * 4]
dung_het = True
co_nham = False
nham_trong_link = False
for s in mau:
    for seed in range(40):
        kh = nguoi.ke_hoach_go(s, random.Random(seed), ty_le_nham=0.08)
        if nguoi.ap_ke_hoach(kh) != s:
            dung_het = False
        if any(b[1] == "Backspace" for b in kh):
            co_nham = True
        # mỗi chữ trong link/@/# phải được gõ ngay lần đầu, không có Backspace nào xoá chữ đó
        cam = nguoi._vung_cam(s)
        pos = 0
        for i, b in enumerate(kh):
            if b[0] == "go" and i + 1 < len(kh) and kh[i + 1][1] == "Backspace" and pos < len(s) and cam[pos]:
                nham_trong_link = True
            if b[0] == "go" and not (i + 1 < len(kh) and kh[i + 1][1] == "Backspace"):
                pos += 1
            elif b == ("phim", "Enter", b[2]):
                pos += 1
check("kế hoạch gõ luôn ra đúng nguyên văn (có dấu, emoji, xuống dòng)", dung_het)
check("có gõ nhầm rồi xoá lại", co_nham)
check("không gõ nhầm trong link, @tên, #thẻ", not nham_trong_link)
kh = nguoi.ke_hoach_go("Xin chào. Mình là MinMin", random.Random(1), ty_le_nham=0)
tre = [b[2] for b in kh if b[0] == "go"]
check("nhịp gõ không đều và chậm hơn sau dấu chấm",
      len(set(tre)) > 10 and tre[9] > min(tre[:8]) and all(35 <= t <= 2000 for t in tre))
check("không có bước dán cả đoạn", all(len(b[1]) <= 1 or b[0] != "go" for b in kh))
pts = nguoi.duong_cong(10, 10, 400, 300, random.Random(3))
check("đường chuột cong kết thúc đúng đích, không đi thẳng",
      pts[-1] == (400, 300) and len(pts) >= 12
      and max(abs((p[1] - 10) - (p[0] - 10) * 290 / 390) for p in pts) > 3)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
