"""Đội Social - Fanpage qua Graph API (26.10.194): kho, spin, lịch, tạo bài hàng loạt, đăng từng loại qua
Graph giả, hẹn giờ Facebook, thử lại / lỗi quyền, bình luận + quy tắc, Dừng mọi tự động, che token,
URL công khai HMAC, kênh nguồn, HTTP. KHÔNG mạng.
python tests/run.py doi_social_fanpage"""
import asyncio, json, os, random, re, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
os.environ["JAVIS_DOI_SOCIAL_VONG"] = "0"
from _paths import ROOT  # noqa: E402,F401

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


def chay(coro):
    return asyncio.run(coro)


import doi_social as ds  # noqa: E402
import doi_social_v2 as v2  # noqa: E402
import doi_social_fanpage as fp  # noqa: E402
import doi_social_fanpage_graph as fpg  # noqa: E402

GOC = Path(tempfile.mkdtemp())
ds.mo(GOC / "kho")
fpg.dat_ket_noi(lambda: [], None)
fpg._ngu = lambda s: asyncio.sleep(0)
for k in fpg.CONG:
    fpg._MOC[k] = 10 ** 12          # tắt các việc theo cổng thời gian; test gọi trực tiếp
TZ = fp._tz()
USER_TOK = "EAAUSERtokenAbcdefghijklmnop1234567890XYZ9"
P1, P2 = "1110001", "2220002"
PAGE_TOK = {P1: "EAAPAGEoneQwertyuiopasdfghjkl0001", P2: "EAAPAGEtwoQwertyuiopasdfghjkl0002"}


class GraphGia:
    def __init__(self):
        self.goi = []
        self.loi = []          # [(chuỗi con của đường, lỗi, số lần)]
        self.n = 0
        self.bl = {}            # page -> danh sách bình luận trả về khi quét

    def dat_loi(self, chuoi, loi, lan=1):
        self.loi.append([chuoi, loi, lan])

    async def __call__(self, method, url, params=None, data=None, files=None, headers=None, content=None):
        self.goi.append({"method": method, "url": url, "params": dict(params or {}), "data": dict(data or {}),
                         "files": files, "headers": headers, "content": content})
        return self.tra(method, url, dict(params or {}), dict(data or {}))

    def tim(self, method, chuoi):
        return [g for g in self.goi if g["method"] == method and chuoi in g["url"]]

    def tra(self, method, url, params, data):
        self.n += 1
        n = self.n
        path = url.split("/v26.0/", 1)[1] if "/v26.0/" in url else url
        for x in self.loi:
            if x[0] in url and x[2] > 0:
                x[2] -= 1
                return {"error": x[1]}
        tok = params.get("access_token") or data.get("access_token") or ""
        if path == "me/accounts":
            return {"data": [
                {"id": P1, "name": "Hằng Yên Store", "category": "Quần áo", "tasks": ["CREATE_CONTENT", "MODERATE"],
                 "access_token": PAGE_TOK[P1], "picture": {"data": {"url": "https://x/p1.jpg"}}, "followers_count": 1200,
                 "instagram_business_account": {"id": "1789", "username": "hangyen"}},
                {"id": P2, "name": "Đồ Bộ Miệt Vườn", "category": "Quần áo", "tasks": ["MODERATE"],
                 "access_token": PAGE_TOK[P2], "fan_count": 300}]}
        if path == "me":
            return {"id": "u1", "name": "Chủ shop"}
        if path == "debug_token":
            return {"data": {"is_valid": True, "type": "USER", "expires_at": int(time.time()) + 3 * 86400}}
        if method == "GET" and re.fullmatch(r"\d+", path) and params.get("fields") == "access_token":
            return {"access_token": PAGE_TOK.get(path, "EAAPAGEotherQwertyuiop")}
        if method == "GET" and path.endswith("/feed"):
            pg = path.split("/")[0]
            return {"data": [{"id": f"{pg}_900", "comments": {"data": self.bl.get(pg, [])}}]}
        if method == "GET" and "/insights" in path:
            if "impressions" in str(params.get("metric")):
                return {"error": {"message": "(#100) The value must be a valid insights metric", "code": 100}}
            if path.startswith(P1 + "/"):
                return {"data": [{"name": "page_total_media_view_unique", "values": [{"value": 50}, {"value": 70}]},
                                 {"name": "page_post_engagements", "values": [{"value": 9}]},
                                 {"name": "page_media_view", "values": [{"value": 4}]}]}
            return {"data": [{"name": "post_total_media_view_unique", "values": [{"value": 33}]},
                             {"name": "post_clicks", "values": [{"value": 2}]}]}
        if method == "GET" and params.get("fields") == "followers_count,fan_count":
            return {"followers_count": 1250}
        if method == "GET" and "reactions.summary" in str(params.get("fields")):
            return {"reactions": {"summary": {"total_count": 5}}, "comments": {"summary": {"total_count": 2}},
                    "shares": {"count": 1}}
        if method == "GET" and params.get("fields") == "status_code":
            return {"status_code": "FINISHED"}
        if method == "GET":
            return {"id": path.split("/")[0], "name": "x"}
        if "rupload.facebook.com" in url:
            return {"success": True}
        if path.endswith("/feed"):
            return {"id": f"{path.split('/')[0]}_{n}"}
        if path.endswith("/photos"):
            if data.get("published") == "false" and "scheduled_publish_time" not in data:
                return {"id": f"ph{n}"}
            return {"id": f"ph{n}", "post_id": f"{path.split('/')[0]}_{n}"}
        if path.endswith("/videos"):
            return {"id": f"vd{n}"}
        if path.endswith("/video_reels") or path.endswith("/video_stories"):
            if data.get("upload_phase") == "start":
                return {"video_id": f"rv{n}", "upload_url": f"https://rupload.facebook.com/video-upload/v26.0/rv{n}"}
            return {"success": True}
        if path.endswith("/photo_stories"):
            return {"success": True, "post_id": f"st{n}"}
        if path.endswith("/comments"):
            return {"id": f"cmt{n}"}
        if path.endswith("/media_publish"):
            return {"id": f"igm{n}"}
        if path.endswith("/media"):
            return {"id": f"igc{n}"}
        return {"success": True}


G = GraphGia()
fpg.dat_http(G)


def tep_media(ten, du_lieu=b"x" * 100):
    p = GOC / ("tam-" + str(random.random()))
    p.write_bytes(du_lieu)
    return fp.luu_media(ten, p)["tep"]


# ================================================================== cảnh báo khi trống
cb = fp.kiem_loi()
check("chưa có token -> cảnh báo chặn 'chua_token'", any(x["ma"] == "chua_token" and x["muc"] == "chan" for x in cb))
check("cảnh báo có cách sửa + tới chỗ sửa", all(x["cach_sua"] and x["toi"].startswith("#/") for x in cb))

# ================================================================== spin
r = random.Random(1)
kq = {fp.spin("{a|{c|d}}", r) for _ in range(300)}
check("spin lồng nhau chỉ ra a/c/d và ra đủ", kq == {"a", "c", "d"}, kq)
check("spin ngoặc chữ thật {{ }}", fp.spin("{{giữ}} {x|x}", r) == "{giữ} x")
check("spin biến ten_trang/ten_tep/ngay", fp.spin("{ten_trang} - {ten_tep} - {ngay}", r,
                                                   {"ten_trang": "HALIMI", "ten_tep": "tap-12", "ngay": "21/10/2026"})
      == "HALIMI - tap-12 - 21/10/2026")
check("spin biến thiếu giá trị thì giữ nguyên", fp.spin("xem {ten_tep}", r) == "xem {ten_tep}")
check("spin nhóm không đóng giữ nguyên", fp.spin("{a|b", r) == "{a|b")
check("spin cố định theo rnd", fp.spin("{1|2|3|4|5}", random.Random(7)) == fp.spin("{1|2|3|4|5}", random.Random(7)))

# ================================================================== STT, kho, link
check("số từ tên tệp", [fp.so_tu_ten_tep(x) for x in ("12.mp4", "phim_12.jpg", "tap-012.mp4", "abc.mp4",
                                                       "tap-7__qwerty.mp4")] == [12, 12, 12, None, 7])
kho_nd = fp.tao_kho("Caption phim", "noi_dung", "stt", [f"Tập {i} {{hay|đỉnh}}" for i in range(1, 21)])
check("chọn STT theo tên tệp", fp.chon_tu_kho(kho_nd["id"], "tap-012.mp4").startswith("Tập 12 "))
check("STT ngoài phạm vi thì lần lượt", fp.chon_tu_kho(kho_nd["id"], "tap-099.mp4").startswith("Tập 1 ")
      and fp.chon_tu_kho(kho_nd["id"], "abc.mp4").startswith("Tập 2 "))
ct = {}
a = [fp.chon_tu_kho(kho_nd["id"], "", None, ct) for _ in range(3)]
check("con trỏ tạm không ghi DB", fp.lay_kho(kho_nd["id"])["con_tro"] == 2 and a[0].startswith("Tập 3 "))
kho_ll = fp.tao_kho("Lần lượt", "noi_dung", "lan_luot", ["A", "B"])
check("lần lượt quay vòng", [fp.chon_tu_kho(kho_ll["id"]) for _ in range(3)] == ["A", "B", "A"])
check("nhập kho tách dòng '---'", fp.nhap_kho(kho_ll["id"], "Dòng 1\ndòng 2\n---\nBài 2")["so"] == 2
      and fp.lay_kho(kho_ll["id"])["muc"][2] == "Dòng 1\ndòng 2")
check("nhập kho mỗi dòng một mục", fp.tach_muc("a\n\nb\n c ") == ["a", "b", "c"])
check("dựng link từ tên tệp", fp.dung_link("https://phim.sbs/article/{ten_tep}", "Phim Hay Tập 12__abcdef.mp4")
      == "https://phim.sbs/article/phim-hay-tap-12")
check("mẫu link sai bị từ chối", raises(lambda: fp.dung_link("ftp://x/{ten_tep}", "a.mp4"), "http"))
kho_link = fp.tao_kho("Link phim", "link", "ngau_nhien", [], {"noi_dung": [kho_nd["id"]]},
                      "https://phim.sbs/article/{ten_tep}")
check("kho link gắn kho nội dung", fp.link_cho(kho_nd["id"], "noi_dung", "tap-3.mp4") == "https://phim.sbs/article/tap-3")
check("kho link nhận đúng loại kho", raises(lambda: fp.tao_kho("x", "link", gan={"noi_dung": [kho_link["id"]]}), "không phải"))
check("kho link chỉ nhận link", raises(lambda: fp.tao_kho("x", "link", muc=["không phải link"]), "http"))

# ================================================================== lịch
d0 = datetime(2026, 10, 21, 8, 0, tzinfo=TZ)


def lt(h, m=0, ngay=0):
    return (d0.replace(hour=h, minute=m) + timedelta(days=ngay)).timestamp()


L = {"che_do": "gio", "gio": ["09:00", "12:00", "18:00"], "lech_phut": 0, "tu": "08:00", "den": "22:00"}
check("giờ: lần lượt khung trong ngày rồi sang ngày sau",
      fp.tinh_lich(L, 4, d0.timestamp()) == [lt(9), lt(12), lt(18), lt(9, 0, 1)])
check("giờ: bỏ khung đã qua", fp.tinh_lich(L, 1, lt(10)) == [lt(12)])
check("giờ: bỏ khung đã có bài (< 20 phút)", fp.tinh_lich(L, 2, lt(10), [lt(12, 5)]) == [lt(18), lt(9, 0, 1)])
x = fp.tinh_lich({**L, "lech_phut": 30}, 30, d0.timestamp(), (), 0, random.Random(3))
check("giờ: lệch ngẫu nhiên trong ±30 phút",
      all(min(abs(t - lt(h, 0, k)) for k in range(12) for h in (9, 12, 18)) <= 1800 for t in x) and len(set(x)) == 30)
check("giờ: trải theo chỉ số Trang", fp.tinh_lich({**L, "trai_phut": 10}, 1, d0.timestamp(), (), 2) == [lt(9, 20)])
check("giờ: kẹp trong khung tu-den", fp.tinh_lich({**L, "gio": ["23:30"]}, 1, d0.timestamp()) == [lt(22)])
C = {"che_do": "chu_ky", "moi_gio": 4, "tu": "08:00", "den": "22:00", "lech_phut": 0}
check("chu kỳ: từ mốc tròn kế tiếp, trong khung, sang ngày sau từ 'tu'",
      fp.tinh_lich(C, 5, lt(7, 10)) == [lt(8), lt(12), lt(16), lt(20), lt(8, 0, 1)],
      [datetime.fromtimestamp(t, TZ).isoformat() for t in fp.tinh_lich(C, 5, lt(7, 10))])
check("lịch tắt -> không tự xếp", fp.tinh_lich({"che_do": "tat"}, 3, d0.timestamp()) == [])
check("lịch sai giờ bị từ chối", raises(lambda: fp.tinh_lich({"gio": ["25:00"]}, 1, 0), "HH:MM"))
check("cách hẹn fb chỉ khi trong khoảng và loại cho phép",
      fp.cach_hen_cho("chu", "fb", 1000 + 3600, 1000) == "fb" and fp.cach_hen_cho("reel", "fb", 1000 + 3600, 1000) == "tool"
      and fp.cach_hen_cho("chu", "fb", 1000 + 300, 1000) == "tool" and fp.cach_hen_cho("anh", "tool", 99999, 1000) == "tool")

# ================================================================== token + đồng bộ Trang
t1 = fp.them_token("Token chủ", USER_TOK)
check("thêm token: trả che, không trả token thật", t1["che"] == "EAAUSE…XYZ9" and "token" not in t1)
check("thêm token trùng bị từ chối", raises(lambda: fp.them_token("lại", USER_TOK), "đã có"))
check("token rác bị từ chối", raises(lambda: fp.them_token("x", "có khoảng trắng"), "không hợp lệ"))
kq = chay(fpg.dong_bo_trang())
check("đồng bộ Trang qua /me/accounts", kq["so"] == 2 and kq["moi"] == 2 and not kq["loi"], kq)
g = G.tim("GET", "me/accounts")[-1]
check("gọi đúng trường của /me/accounts", "instagram_business_account{id,username}" in g["params"]["fields"]
      and g["params"]["access_token"] == USER_TOK)
tr1 = fp.lay_trang(P1)
check("Trang ghi đủ ảnh/IG/quyền/người theo dõi", tr1["anh"] == "https://x/p1.jpg" and tr1["ig_id"] == "1789"
      and tr1["nguoi_theo_doi"] == 1200 and tr1["so_token"] == 1 and tr1["co_quyen_dang"])
check("token tốt sau đồng bộ", fp.lay_token(t1["id"])["trang_thai"] == "tot" and fp.lay_token(t1["id"])["so_trang"] == 2)
check("page token chỉ trong bộ nhớ", (P1, t1["id"]) in fpg._CACHE and PAGE_TOK[P1] not in
      (GOC / "kho" / "doi-social.db").read_bytes().decode("latin-1"))
cb = fp.kiem_loi()
check("Trang thiếu CREATE_CONTENT -> cảnh báo mất quyền đăng",
      any(x["ma"] == "mat_quyen_dang" and x["doi_tuong"] == P2 for x in cb))
fp.sua_trang(P2, cau_hinh={"duyet_truoc": True})
tk = chay(fpg.kiem_token(t1["id"]))
check("kiểm token đọc hạn từ debug_token", tk["het_han"] and tk["trang_thai"] == "tot")
check("token sắp hết hạn (< 7 ngày) -> cảnh báo nặng", any(x["ma"] == "token_sap_het" for x in fp.kiem_loi()))

# kết nối OAuth hiện như 'kn:<cid>'
fpg.dat_ket_noi(lambda: [{"id": "c1", "label": "FB Shop"}], lambda cid: asyncio.sleep(0, "EAAKNtokenZxcvbnmasdfgh1234"))
fpg.nguon_token()
kn = [x for x in fp.ds_token() if x["loai"] == "ket_noi"]
check("kết nối OAuth hiện như kn:<cid>", len(kn) == 1 and kn[0]["id"] == "kn:c1" and kn[0]["che"] == "")
check("không xoá kết nối OAuth ở tab Token", raises(lambda: fp.xoa_token("kn:c1"), "trang Kết nối"))
fpg.dat_ket_noi(lambda: [], None)
fpg.nguon_token()
check("kết nối bị gỡ thì hàng kn biến mất", not [x for x in fp.ds_token() if x["loai"] == "ket_noi"])

# ================================================================== cấu hình kế thừa
nh = fp.tao_nhom("Phim", "", {"lich": {"che_do": "gio", "gio": ["10:00"], "lech_phut": 0}, "duyet_truoc": False,
                              "kho_noi_dung": kho_nd["id"]})
fp.sua_trang(P1, nhom_id=nh["id"], cau_hinh={"lich": {"lech_phut": 5}})
t = fp.lay_trang(P1)
hl = t["cau_hinh_hieu_luc"]
check("hiệu lực: Trang <- nhóm <- mặc định", hl["lich"]["gio"] == ["10:00"] and hl["lich"]["lech_phut"] == 5
      and hl["duyet_truoc"] is False and hl["lich"]["tu"] == "08:00" and hl["kho_noi_dung"] == kho_nd["id"])
check("nguồn cấu hình lịch = trang", t["nguon_cau_hinh"] == "trang" and t["nhom_ten"] == "Phim")
fp.sua_trang(P1, cau_hinh={"lich": None, "duyet_truoc": None})
t = fp.lay_trang(P1)
check("null ở Trang = theo nhóm", t["nguon_cau_hinh"] == "nhom" and t["cau_hinh_hieu_luc"]["lich"]["lech_phut"] == 0
      and "lich" not in t["cau_hinh"])
check("Trang không nhóm = mặc định", fp.lay_trang(P2)["nguon_cau_hinh"] == "mac_dinh")
check("cấu hình gắn kho sai loại bị từ chối", raises(lambda: fp.sua_trang(P1, cau_hinh={"kho_binh_luan": kho_nd["id"]}),
                                                      "không phải kho"))
fp.sua_nhom(nh["id"], cau_hinh={"duyet_truoc": True, "kho_noi_dung": None})
check("sửa nhóm: null gỡ khoá", "kho_noi_dung" not in fp.lay_nhom(nh["id"])["cau_hinh"])
check("xem trước lịch theo Trang", len(fp.xem_truoc_lich(None, P1, 3)) == 3)

# ================================================================== tạo bài hàng loạt
anh = [tep_media(f"anh-{i}.jpg") for i in range(1, 5)]
NOW = time.time()
kq = fp.tao_bai(trang_ids=[P1, P2], loai="anh", noi_dung=["Váy {đẹp|xinh} tại {ten_trang}"], media=anh,
                chia="mot_trang", hen="tu_dong", rnd=random.Random(2), now=NOW)
check("mot_trang: 4 ảnh chia xoay 2 Trang", kq["so"] == 4 and sorted(b["trang_id"] for b in kq["muc"]) == [P1, P1, P2, P2])
check("mặc định chờ duyệt", all(b["trang_thai"] == "cho_duyet" for b in kq["muc"]))
check("spin + biến Trang trong caption", all(b["noi_dung"].endswith(b["trang_ten"]) for b in kq["muc"]))
check("giờ tự xếp theo lịch hiệu lực, cách nhau", all(b["hen_luc"] and b["hen_luc"] > NOW for b in kq["muc"])
      and len({b["hen_luc"] for b in kq["muc"] if b["trang_id"] == P1}) == 2)
kq2 = fp.tao_bai(trang_ids=[P1, P2], loai="anh", noi_dung=["Váy {đẹp|xinh} tại {ten_trang}"], media=anh,
                 chia="mot_trang", rnd=random.Random(2), now=NOW)
check("chống trùng: tạo lại y hệt -> bỏ hết", kq2["so"] == 0 and kq2["bo_trung"] == 4)
xt = fp.tao_bai(trang_ids=[P1, P2], loai="anh", noi_dung=["Bài khác"], media=anh, chia="tat_ca", chay_thu=True, now=NOW)
dem_truoc = fp.ds_bai()["tong"]
check("chạy thử tat_ca: 8 bài xem trước, không ghi", xt["so"] == 8 and len(xt["xem_truoc"]) == 8 and xt["muc"] == []
      and fp.ds_bai()["tong"] == dem_truoc)
kq3 = fp.tao_bai(nhom_id=nh["id"], loai="chu", kho_id=kho_nd["id"], so_bai=2, now=NOW)
check("bài chữ từ kho (STT không số -> lần lượt) + link từ kho link",
      kq3["so"] == 2 and all("https://phim.sbs/article/" in b["noi_dung"] or b["noi_dung"].startswith("Tập") for b in kq3["muc"]))
check("album nhận list lồng", fp.tao_bai(trang_ids=[P1], loai="album", media=[anh[:2], anh[2:]], noi_dung=["A1", "A2"],
                                          chay_thu=True)["so"] == 2)
check("sai loại tệp bị từ chối", raises(lambda: fp.tao_bai(trang_ids=[P1], loai="video", media=[anh[0]]), "video"))
check("tệp không có bị từ chối", raises(lambda: fp.tao_bai(trang_ids=[P1], loai="anh", media=["khong-co.jpg"]), "không thấy"))
check("lệch số nội dung/media bị từ chối", raises(lambda: fp.tao_bai(trang_ids=[P1], loai="anh", media=anh[:3],
                                                                      noi_dung=["a", "b"]), "phải bằng"))
fp.sua_nhom(nh["id"], cau_hinh={"duyet_truoc": False})
kq4 = fp.tao_bai(trang_ids=[P1], loai="chu", noi_dung=["Tắt duyệt trước"], now=NOW)
check("duyet_truoc tắt -> vào thẳng cho_dang", kq4["muc"][0]["trang_thai"] == "cho_dang")
fp.sua_nhom(nh["id"], cau_hinh={"duyet_truoc": True})
fp.hanh_dong_bai([b["id"] for b in kq["muc"]] + [b["id"] for b in kq3["muc"]] + [kq4["muc"][0]["id"]], "bo")

# ================================================================== đăng từng loại qua nhịp
fp.dat_cai_dat({"luong": 20})
vid = tep_media("clip-1.mp4")
vid2 = tep_media("clip-2.mp4")
tao = {}
for loai, media in (("chu", None), ("anh", [anh[0]]), ("album", [anh[:3]]), ("video", [vid]), ("reel", [vid2]),
                    ("story", [anh[3]])):
    kqx = fp.tao_bai(trang_ids=[P1], loai=loai, noi_dung=[f"Bài {loai}"], media=media, hen="ngay",
                     binh_luan="Link mua: {https://a.vn|https://a.vn}" if loai == "chu" else None,
                     story=(loai == "anh"), now=NOW)
    tao[loai] = kqx["muc"][0]["id"]
fp.hanh_dong_bai(list(tao.values()), "duyet")
check("duyệt -> cho_dang", all(fp.lay_bai(i)["trang_thai"] == "cho_dang" for i in tao.values()))
G.goi.clear()
r = chay(fpg.nhip(None, now=NOW + 5))
check("nhịp đăng đủ 6 bài", r["dang"] == 6, r)
bai = {k: fp.lay_bai(i) for k, i in tao.items()}
check("mọi bài da_dang + có post_id + url", all(b["trang_thai"] == "da_dang" and b["post_id"] and b["url"]
                                                 for b in bai.values()), {k: (b["trang_thai"], b["loi"]) for k, b in bai.items()})
f = G.tim("POST", f"{P1}/feed")
check("chữ: POST /feed message, dùng page token", any(g["data"].get("message") == "Bài chu"
                                                       and g["data"]["access_token"] == PAGE_TOK[P1] for g in f))
ph = [g for g in G.tim("POST", f"{P1}/photos") if g["data"].get("message") == "Bài anh"]
check("ảnh: POST /photos multipart source + message", ph and "source" in ph[0]["files"])
alb = [g for g in f if "attached_media[2]" in g["data"]]
check("album: 3 ảnh published=false rồi /feed attached_media",
      alb and json.loads(alb[0]["data"]["attached_media[0]"])["media_fbid"].startswith("ph"))
vv = G.tim("POST", "graph-video.facebook.com/v26.0/" + P1 + "/videos")
check("video: graph-video /videos source + description", vv and vv[0]["data"]["description"] == "Bài video")
rl = G.tim("POST", f"{P1}/video_reels")
ru = G.tim("POST", "rupload.facebook.com")
check("reel: start -> rupload (OAuth header, file_size) -> finish PUBLISHED",
      [g["data"]["upload_phase"] for g in rl] == ["start", "finish"] and rl[1]["data"]["video_state"] == "PUBLISHED"
      and ru and ru[0]["headers"]["Authorization"] == f"OAuth {PAGE_TOK[P1]}" and ru[0]["headers"]["file_size"] == "100")
check("reel post_id = video_id", bai["reel"]["post_id"].startswith("rv") and "/reel/" in bai["reel"]["url"])
check("story ảnh: photos published=false -> photo_stories", bai["story"]["post_id"].startswith("st"))
check("story kèm bài ảnh đã đăng ngay ở bước phụ", bai["anh"]["story_tt"] == "xong"
      and len(G.tim("POST", "/photo_stories")) == 2)
check("bình luận sau đăng chưa gửi trước 60 giây", bai["chu"]["bl_tt"] == "cho" and not G.tim("POST", "/comments"))
chay(fpg.nhip(None, now=NOW + 70))
cm = G.tim("POST", f"{bai['chu']['post_id']}/comments")
check("bình luận sau đăng gửi sau 60 giây", fp.lay_bai(tao["chu"])["bl_tt"] == "xong" and cm
      and cm[0]["data"]["message"] == "Link mua: https://a.vn")
check("đếm bài đăng của token", fp.lay_token(t1["id"])["so_bai_dang"] >= 6)

# ================================================================== IG qua URL công khai
fp.dat_goc_cong_khai("https://minmin.example.com")
b_ig = fp.tao_bai(trang_ids=[P1], loai="anh", noi_dung=["Lên IG"], media=[anh[1]], ig=True, hen="ngay", now=NOW)["muc"][0]
check("bài có IG khi Trang có ig_id", b_ig["ig"] is True)
fp.hanh_dong_bai([b_ig["id"]], "duyet")
G.goi.clear()
chay(fpg.nhip(None, now=NOW + 80))
ig = G.tim("POST", "1789/media")
check("IG: tạo container image_url công khai + caption",
      ig and ig[0]["data"]["image_url"].startswith("https://minmin.example.com/doi-social/fp/cong-khai/")
      and ig[0]["data"]["caption"] == "Lên IG")
check("IG: chờ FINISHED rồi media_publish", G.tim("POST", "1789/media_publish") and fp.lay_bai(b_ig["id"])["ig_tt"] == "xong")
check("IG đếm 24h", fp.ig_24h(P1) == 1 and fp.ds_instagram()[0]["da_dang_24h"] == 1)

# ================================================================== hẹn giờ trên Facebook
fp.sua_trang(P1, cau_hinh={"lich": {"cach": "fb"}})
hen = NOW + 3600
b_fb = fp.tao_bai(trang_ids=[P1], loai="chu", noi_dung=["Hẹn trên FB"], hen=hen, now=NOW)["muc"][0]
check("cách hẹn fb khi trong khoảng", b_fb["cach_hen"] == "fb")
fp.hanh_dong_bai([b_fb["id"]], "duyet")
G.goi.clear()
chay(fpg.nhip(None, now=NOW + 90))
g = [x for x in G.tim("POST", f"{P1}/feed") if x["data"].get("message") == "Hẹn trên FB"]
check("gửi ngay với published=false + scheduled_publish_time", g and g[0]["data"]["published"] == "false"
      and g[0]["data"]["scheduled_publish_time"] == str(int(hen)))
check("trạng thái da_hen_fb, giờ đăng = giờ hẹn", fp.lay_bai(b_fb["id"])["trang_thai"] == "da_hen_fb"
      and fp.lay_bai(b_fb["id"])["dang_luc"] == hen)
chay(fpg.nhip(None, now=hen + 200))
check("qua giờ hẹn -> da_dang", fp.lay_bai(b_fb["id"])["trang_thai"] == "da_dang")
fp.sua_trang(P1, cau_hinh={"lich": {"cach": "tool"}})

# ================================================================== thử lại / lỗi quyền
b_t = fp.tao_bai(trang_ids=[P1], loai="chu", noi_dung=["Lỗi tạm"], hen="ngay", now=NOW)["muc"][0]
fp.hanh_dong_bai([b_t["id"]], "duyet")
G.dat_loi(f"{P1}/feed", {"code": 2, "message": "Service temporarily unavailable"})
chay(fpg.nhip(None, now=NOW + 100))
x = fp.lay_bai(b_t["id"])
check("lỗi tạm (#2) -> chờ thử lại sau 10 phút", x["trang_thai"] == "cho_dang" and x["so_lan_thu"] == 1
      and abs(x["hen_luc"] - (NOW + 100 + 600)) < 1 and "#2" in x["loi"])
G.dat_loi(f"{P1}/feed", {"code": 2, "message": "tạm"}, 3)
for i in range(3):
    chay(fpg.nhip(None, now=NOW + 100 + 601 * (i + 1)))
check("hết 3 lần thử -> loi", fp.lay_bai(b_t["id"])["trang_thai"] == "loi" and fp.lay_bai(b_t["id"])["so_lan_thu"] == 4)
check("thử lại bằng tay -> cho_dang", fp.hanh_dong_bai([b_t["id"]], "thu_lai")["so"] == 1
      and fp.lay_bai(b_t["id"])["trang_thai"] == "cho_dang")
fp.hanh_dong_bai([b_t["id"]], "bo")
v2.lay_bao()
b_q = fp.tao_bai(trang_ids=[P1], loai="chu", noi_dung=["Lỗi quyền"], hen="ngay", now=NOW)["muc"][0]
fp.hanh_dong_bai([b_q["id"]], "duyet")
G.dat_loi(f"{P1}/feed", {"code": 200, "message": "Requires pages_manage_posts permission"})
chay(fpg.nhip(None, now=NOW + 3000))
x = fp.lay_bai(b_q["id"])
check("lỗi quyền (#200) -> loi ngay, không thử lại", x["trang_thai"] == "loi" and x["so_lan_thu"] == 1 and "#200" in x["loi"])
cb = [c for c in fp.kiem_loi(now=NOW + 3000) if c["ma"] == "bai_loi" and c["doi_tuong"] == "200"]
check("cảnh báo bài lỗi gộp theo mã + cách sửa pages_manage_posts", cb and "pages_manage_posts" in cb[0]["cach_sua"])
check("báo chủ khi lỗi quyền", any("lỗi quyền" in t for t, _ in v2.lay_bao()))
check("Trang ghi lỗi", "#200" in fp.lay_trang(P1)["loi"])
check("lịch sử cảnh báo có ghi", any(h["ma"] == "bai_loi" for h in fp.lich_su_canh_bao()))
fp.hanh_dong_bai([b_q["id"]], "xoa")
fp.kiem_loi(now=NOW + 3000)
check("cảnh báo hết thì đóng (het_luc)", any(h["ma"] == "bai_loi" and h["het_luc"] for h in fp.lich_su_canh_bao()))
# token chết (#190) -> đánh dấu token lỗi
b_190 = fp.tao_bai(trang_ids=[P2], loai="chu", noi_dung=["Token chết"], hen="ngay", now=NOW)["muc"][0]
fp.hanh_dong_bai([b_190["id"]], "duyet")
G.dat_loi(f"{P2}/feed", {"code": 190, "message": "Error validating access token"})
chay(fpg.nhip(None, now=NOW + 3100))
check("lỗi #190 -> token đánh dấu lỗi, bài lỗi", fp.lay_token(t1["id"])["trang_thai"] == "loi"
      and fp.lay_bai(b_190["id"])["trang_thai"] == "loi")
check("mọi token lỗi -> cảnh báo chặn", any(c["ma"] == "moi_token_loi" for c in fp.kiem_loi()))
fp.cap_nhat_token(t1["id"], trang_thai="tot", loi="")
fp.hanh_dong_bai([b_190["id"]], "xoa")

# ================================================================== bình luận + quy tắc
fp.sua_nhom(nh["id"], cau_hinh={"tu_tra_loi": True, "tu_an": True})
fp.sua_trang(P2, cau_hinh={"tu_tra_loi": True})
G.bl[P1] = [{"id": "cm11", "from": {"id": "u9", "name": "Lan"}, "message": "Giá bao nhiêu vậy shop?",
             "created_time": "2026-10-21T01:00:00+0000"},
            {"id": "cm12", "from": {"id": P1, "name": "Shop"}, "message": "Cảm ơn"},
            {"id": "cm13", "from": {"id": "u8", "name": "Spam"}, "message": "Vay tiền nhanh lãi thấp"}]
G.bl[P2] = [{"id": "cm21", "from": {"id": "u7", "name": "Hoa"}, "message": "gia sao b oi"}]
q1 = fp.tao_quy_tac({"ten": "Hỏi giá", "tu_khoa": ["giá"], "hanh_dong": "tra_loi",
                     "mau": ["Dạ {anh|chị} inbox giúp em ạ"], "pham_vi": {"trang": [P1]}})
check("quy tắc mặc định tu_gui = false", q1["tu_gui"] is False)
q2 = fp.tao_quy_tac({"ten": "Giá Trang 2", "tu_khoa": ["gia"], "hanh_dong": "tra_loi", "mau": ["Em gửi giá ạ"],
                     "tu_gui": True, "pham_vi": {"trang": [P2]}})
q3 = fp.tao_quy_tac({"ten": "Ẩn spam", "tu_khoa": ["vay tiền"], "hanh_dong": "an", "uu_tien": 5})
check("quy tắc trả lời thiếu câu mẫu bị từ chối", raises(lambda: fp.tao_quy_tac({"ten": "x", "hanh_dong": "tra_loi"}), "mẫu"))
check("khớp từ khoá bỏ dấu + ranh giới từ", fp.khop_tu_khoa(["giá"], "GIA sao") and not fp.khop_tu_khoa(["ib"], "vibe quá")
      and fp.khop_tu_khoa(["ib"], "ib mình nhé") and fp.khop_tu_khoa([], "bất kỳ"))
G.goi.clear()
so = chay(fpg.quet_binh_luan(P1))
check("quét: 3 bình luận mới", so == 3)
g = G.tim("GET", f"{P1}/feed")[0]
check("quét đọc 15 bài mới nhất kèm comments", g["params"]["limit"] == 15 and "comments.limit(50)" in g["params"]["fields"])
b11, b12, b13 = fp.lay_binh_luan("cm11"), fp.lay_binh_luan("cm12"), fp.lay_binh_luan("cm13")
check("tu_gui false -> câu trả lời chờ duyệt, chưa gửi", b11["trang_thai"] == "cho_duyet" and b11["tra_loi"].startswith("Dạ ")
      and b11["quy_tac_id"] == q1["id"] and not G.tim("POST", "cm11/comments"))
check("bình luận của chính Trang bỏ qua", b12["la_cua_trang"] and b12["trang_thai"] == "bo_qua")
check("ẩn spam (chưa tự gửi) -> đề xuất ẩn chờ duyệt", b13["trang_thai"] == "cho_duyet" and b13["de_xuat"] == "an"
      and not b13["an"])
chay(fpg.quet_binh_luan(P2))
check("tu_gui true -> cho_gui", fp.lay_binh_luan("cm21")["trang_thai"] == "cho_gui")
chay(fpg.nhip(None, now=NOW + 3200))
check("nhịp gửi bình luận cho_gui", fp.lay_binh_luan("cm21")["trang_thai"] == "da_tra_loi"
      and G.tim("POST", "cm21/comments")[0]["data"]["message"] == "Em gửi giá ạ")
check("phạm vi quy tắc: Trang 1 không ăn quy tắc của Trang 2", fp.lay_binh_luan("cm11")["quy_tac_id"] == q1["id"])
chay(fpg.gui_binh_luan("cm13"))
h = G.tim("POST", "v26.0/cm13")
check("gửi đề xuất ẩn -> POST is_hidden=true, da_an", h and h[0]["data"]["is_hidden"] == "true"
      and fp.lay_binh_luan("cm13")["an"] and fp.lay_binh_luan("cm13")["trang_thai"] == "da_an")
chay(fpg.an_binh_luan("cm13", False))
check("hiện lại", not fp.lay_binh_luan("cm13")["an"] and G.tim("POST", "v26.0/cm13")[-1]["data"]["is_hidden"] == "false")
# AI soạn
async def ai_gia(bl, t):
    return f"Dạ {t['ten']} gửi anh/chị giá ạ"
fpg.dat_ai(ai_gia)
q4 = fp.tao_quy_tac({"ten": "AI", "tu_khoa": ["size"], "hanh_dong": "tra_loi_ai", "pham_vi": {"trang": [P1]}})
G.bl[P1] = [{"id": "cm14", "from": {"id": "u6", "name": "Mai"}, "message": "Size M còn không"}]
chay(fpg.quet_binh_luan(P1))
check("quy tắc AI -> AI soạn, chờ duyệt", fp.lay_binh_luan("cm14")["tra_loi"] == "Dạ Hằng Yên Store gửi anh/chị giá ạ"
      and fp.lay_binh_luan("cm14")["trang_thai"] == "cho_duyet")

# Dừng mọi tự động
fp.dat_cai_dat({"dung_tu_dong": True})
G.bl[P1] = [{"id": "cm15", "from": {"id": "u5", "name": "An"}, "message": "giá nhiêu"}]
chay(fpg.quet_binh_luan(P1))
check("dung_tu_dong: không áp quy tắc", fp.lay_binh_luan("cm15")["trang_thai"] == "moi")
b_d = fp.tao_bai(trang_ids=[P1], loai="chu", noi_dung=["Bị dừng"], hen="ngay", now=NOW)["muc"][0]
fp.hanh_dong_bai([b_d["id"]], "duyet")
fp.dat_binh_luan("cm11", trang_thai="cho_gui")
G.goi.clear()
chay(fpg.nhip(None, now=NOW + 3300))
check("dung_tu_dong: không đăng, không gửi bình luận", fp.lay_bai(b_d["id"])["trang_thai"] == "cho_dang"
      and not [g for g in G.goi if g["method"] == "POST"])
check("dung_tu_dong: cảnh báo nhắc", any(c["ma"] == "dung_tu_dong" for c in fp.kiem_loi()))
fp.dat_cai_dat({"dung_tu_dong": False})
fp.dat_binh_luan("cm11", trang_thai="cho_duyet")
fp.hanh_dong_bai([b_d["id"]], "bo")

# ================================================================== insights + báo cáo + đổi info
r = chay(fpg.cap_nhat_so_lieu(P1, now=NOW))
check("insights Trang + bài", r["trang"] == 1 and r["bai"] >= 1, r)
check("số liệu bài: tương tác = cảm xúc + bình luận + chia sẻ", fp.lay_bai(tao["chu"])["so_lieu"]["tuong_tac"] == 8
      and fp.lay_bai(tao["chu"])["so_lieu"]["tiep_can"] == 33)
bc = fp.bao_cao(P1, 7, now=NOW)
check("báo cáo: Trang có tiếp cận + người theo dõi mới", bc["trang"][0]["tiep_can"] == 70
      and bc["trang"][0]["nguoi_theo_doi"] == 1250 and bc["chuoi"])
tq = fp.tong_quan(now=NOW)
check("tổng quan đủ khoá", all(k in tq for k in ("trang", "bai", "nguoi_theo_doi", "tiep_can_7", "tuong_tac_7", "xu_huong",
                                                 "top_trang", "hoat_dong", "canh_bao", "ig", "nguon_token", "dung_tu_dong"))
      and tq["bai"]["da_dang"] >= 8 and len(tq["xu_huong"]) == 14 and tq["top_trang"])
kts = fp.tao_kho("Tiểu sử", "tieu_su", "ngau_nhien", ["{ten_trang} - thời trang nữ"])
G.goi.clear()
r = chay(fpg.hanh_dong_trang([P1], "doi_tieu_su", {"kho_id": kts["id"]}))
check("đổi tiểu sử từ kho (spin biến Trang)", r["so"] == 1 and G.tim("POST", "v26.0/" + P1)[0]["data"]["about"]
      == "Hằng Yên Store - thời trang nữ")
r = chay(fpg.hanh_dong_trang([P1], "doi_bia", {"tep": anh[0]}))
cv = G.tim("POST", "v26.0/" + P1)
check("đổi ảnh bìa: photos published=false -> cover", r["so"] == 1 and cv[-1]["data"].get("cover", "").startswith("ph"))
r = chay(fpg.hanh_dong_trang([P1], "doi_anh", {"tep": vid}))
check("đổi ảnh đại diện từ video bị từ chối", r["so"] == 0 and r["loi"])

# ================================================================== kênh nguồn
k = fp.tao_kenh({"link": "https://www.tiktok.com/@phim", "trang_ids": [P1, P2], "chia": "xoay", "toi_da_moi_lan": 2})
check("kênh tự nhận nền tảng", k["nen_tang"] == "tiktok")
fpg.dat_ytdlp(None, None)
co_that = fpg.co_yt_dlp
fpg.co_yt_dlp = lambda: False
chay(fpg.quet_kenh(k["id"], now=NOW))
check("thiếu yt-dlp -> kênh lỗi rõ ràng", fp.lay_kenh(k["id"])["trang_thai"] == "loi"
      and fp.lay_kenh(k["id"])["loi"] == "máy chủ thiếu yt-dlp")
check("cảnh báo thiếu yt-dlp", any(c["ma"] == "thieu_yt_dlp" for c in fp.kiem_loi(0, False)))
fpg.co_yt_dlp = co_that


def liet_ke(link, n):
    return [{"ma": "v1", "tieu_de": "Tập 1 {hay}", "url": "https://x/v1"}, {"ma": "v2", "tieu_de": "Tập 2", "url": "https://x/v2"},
            {"ma": "v3", "tieu_de": "Tập 3", "url": "https://x/v3"}]


def tai(url, thu_muc, ma):
    thu_muc.mkdir(parents=True, exist_ok=True)
    p = thu_muc / f"{ma}.mp4"
    p.write_bytes(b"v" * 50)
    return p


fpg.dat_ytdlp(liet_ke, tai)
r = chay(fpg.quet_kenh(k["id"], now=NOW))
bk = fp.ds_bai(trang_thai="cho_duyet")["muc"]
bk = [b for b in bk if b["nguon"] == "kenh"]
check("kênh: tải tối đa 2 video, mỗi video một Trang (xoay)", r["so"] == 2 and sorted(b["trang_id"] for b in bk) == [P1, P2])
check("kênh: bài chờ duyệt, loại reel, tệp kenh/<id>/", all(b["loai"] == "reel" and b["media"][0].startswith(f"kenh/{k['id']}/")
                                                            for b in bk))
check("kênh: tiêu đề có ngoặc giữ nguyên chữ", any(b["noi_dung"] == "Tập 1 {hay}" for b in bk), [b["noi_dung"] for b in bk])
r = chay(fpg.quet_kenh(k["id"], now=NOW))
check("kênh: lần quét sau chỉ lấy video chưa có", r["video"] == 1 and fp.lay_kenh(k["id"])["so_video"] == 3)
check("kênh tới hạn theo chu kỳ", not fp.kenh_toi_han(NOW + 60) and fp.kenh_toi_han(NOW + 6 * 3600 + 1))

# ================================================================== URL công khai HMAC + chặn thoát
ma = fp.ma_cong_khai(anh[0], now=NOW)
check("mã công khai hợp lệ -> đúng tệp", fp.doc_ma_cong_khai(ma, now=NOW + 10) == fp.duong_media(anh[0]))
check("mã hết hạn sau 2 giờ", fp.doc_ma_cong_khai(ma, now=NOW + 2 * 3600 + 5) is None)
a_, b_ = ma.split(".")
check("mã sửa chữ ký bị từ chối", fp.doc_ma_cong_khai(a_ + "." + ("A" * len(b_)), now=NOW) is None
      and fp.doc_ma_cong_khai("rac", now=NOW) is None)
check("chặn thoát thư mục", all(fp.duong_media(x) is None for x in ("../doi-social.db", "kenh/1/../../x", "/etc/passwd",
                                                                     "media/../../doi-social.db", ".an", "kenh/a/x.mp4")))
check("không tạo mã cho tệp lạ", raises(lambda: fp.ma_cong_khai("../doi-social.db"), "không có tệp"))
src = (Path(ROOT) / "server" / "main.py").read_text(encoding="utf-8")
m = re.search(r'_DOI_SOCIAL_CONG_KHAI = \(r"([^"]+)"', src)
check("main miễn đăng nhập đúng mẫu mã công khai", m and re.fullmatch(m.group(1), "/doi-social/fp/cong-khai/" + ma)
      and not re.fullmatch(m.group(1), "/doi-social/fp/cong-khai/a/b") and "_DOI_SOCIAL_CONG_KHAI_RE.fullmatch(path)" in src)

# ================================================================== CSV
csv_chu = fp.bai_csv(trang=P1)
check("xuất CSV có tiêu đề + dòng", csv_chu.startswith("﻿id,trang,loai") and "Bài chu" in csv_chu)

# ================================================================== HTTP
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.doi_social as rds  # noqa: E402
rds.ly_do_chan = lambda: None
app = FastAPI()
rds.register(app, rds.DoiSocialDeps())
fpg.dat_ai(ai_gia)
cl = TestClient(app)
JS = []


def j(r):
    JS.append(r.text)
    try:
        return r.json()
    except Exception:
        return {}


r = j(cl.get("/doi-social/fp/tong-quan", headers={"host": "minmin.shop.vn"}))
check("GET tong-quan", r["ok"] and "canh_bao" in r and "xu_huong" in r)
check("nhớ gốc công khai từ yêu cầu web", fp.goc_cong_khai() == "http://minmin.shop.vn")
r = j(cl.get("/doi-social/fp/token"))
check("GET token: có che, không có trường token", r["ok"] and r["muc"] and all("token" not in x and "che" in x for x in r["muc"]))
r = j(cl.post("/doi-social/fp/token", json={"nhan": "Token 2", "token": "EAAPASTEDsecondTokenQwertyuiop12345"}))
t2 = r["token"]["id"]
check("POST token (kiểm luôn)", r["ok"] and r["token"]["trang_thai"] == "tot")
check("POST token/{id}/kiem", j(cl.post(f"/doi-social/fp/token/{t2}/kiem"))["ok"])
check("DELETE token", j(cl.delete(f"/doi-social/fp/token/{t2}"))["ok"] and fp.lay_token(t2) is None)
check("DELETE token lạ -> 404", cl.delete("/doi-social/fp/token/99999").status_code == 404)
r = j(cl.post("/doi-social/fp/trang/dong-bo"))
check("POST trang/dong-bo", r["ok"] and r["so"] == 2)
r = j(cl.get("/doi-social/fp/trang", params={"nhom": nh["id"]}))
check("GET trang lọc nhóm + nhóm + chua_nhom", r["ok"] and [x["id"] for x in r["muc"]] == [P1] and r["nhom"][0]["so"] == 1
      and r["chua_nhom"] == 1 and "cau_hinh_hieu_luc" in r["muc"][0] and "dem" in r["muc"][0])
r = j(cl.patch(f"/doi-social/fp/trang/{P2}", json={"bat": False}))
check("PATCH trang", r["ok"] and r["trang"]["bat"] is False)
r = j(cl.post("/doi-social/fp/trang/hanh-dong", json={"ids": [P2], "hanh_dong": "gan_nhom", "nhom_id": nh["id"]}))
check("POST trang/hanh-dong gan_nhom", r["ok"] and r["so"] == 1 and fp.lay_trang(P2)["nhom_id"] == nh["id"])
r = j(cl.post("/doi-social/fp/trang/hanh-dong", json={"ids": [P2], "hanh_dong": "bat"}))
check("POST trang/hanh-dong bat", r["ok"] and fp.lay_trang(P2)["bat"])
check("hanh-dong lạ -> lỗi", j(cl.post("/doi-social/fp/trang/hanh-dong", json={"ids": [P2], "hanh_dong": "x"}))["ok"] is False)
r = j(cl.post("/doi-social/fp/nhom", json={"ten": "Nhóm 2", "cau_hinh": {"lich": {"che_do": "chu_ky", "moi_gio": 3}}}))
n2 = r["nhom"]["id"]
check("POST nhom (có id ở ngoài)", r["ok"] and r["id"] == n2 and r["nhom"]["cau_hinh"]["lich"]["moi_gio"] == 3)
check("GET nhom", any(x["id"] == n2 for x in j(cl.get("/doi-social/fp/nhom"))["muc"]))
check("PATCH nhom", j(cl.patch(f"/doi-social/fp/nhom/{n2}", json={"ten": "Nhóm Hai"}))["nhom"]["ten"] == "Nhóm Hai")
check("nhóm cấu hình sai -> lỗi", j(cl.patch(f"/doi-social/fp/nhom/{n2}", json={"cau_hinh": {"lich": {"tu": "9h"}}}))["ok"] is False)
check("DELETE nhom", j(cl.delete(f"/doi-social/fp/nhom/{n2}"))["ok"])
r = j(cl.post("/doi-social/fp/kho", json={"ten": "BL", "loai": "binh_luan", "muc": ["Cảm ơn {bạn|anh chị}"]}))
kb = r["kho"]["id"]
check("POST kho", r["ok"] and r["kho"]["so"] == 1)
check("GET kho?loai", [x["id"] for x in j(cl.get("/doi-social/fp/kho", params={"loai": "binh_luan"}))["muc"]] == [kb])
check("GET kho/{id} đầy đủ mục", j(cl.get(f"/doi-social/fp/kho/{kb}"))["kho"]["muc"] == ["Cảm ơn {bạn|anh chị}"])
check("PATCH kho", j(cl.patch(f"/doi-social/fp/kho/{kb}", json={"che_do": "lan_luot"}))["kho"]["che_do"] == "lan_luot")
check("POST kho/{id}/nhap", j(cl.post(f"/doi-social/fp/kho/{kb}/nhap", json={"chu": "a\nb"}))["so"] == 2)
check("kho sai loại -> lỗi", j(cl.post("/doi-social/fp/kho", json={"ten": "x", "loai": "la"}))["ok"] is False)
r = j(cl.post("/doi-social/fp/thu-spin", json={"mau": "{a|b} {ten_tep}", "ten_tep": "phim-1__abcdef.mp4"}))
check("POST thu-spin 5 kết quả", r["ok"] and len(r["mau_thu"]) == 5 and all(x.endswith(" phim-1") for x in r["mau_thu"]))
r = j(cl.post("/doi-social/fp/thu-link", json={"mau_link": "https://phim.sbs/article/{ten_tep}", "ten_tep": "Phim Hay.mp4"}))
check("POST thu-link", r["link"] == "https://phim.sbs/article/phim-hay")
r = j(cl.post("/doi-social/fp/lich/xem-truoc", json={"cau_hinh_lich": {"che_do": "chu_ky", "moi_gio": 2}, "so": 4}))
check("POST lich/xem-truoc", r["ok"] and len(r["gio"]) == 4)
check("lich/xem-truoc theo Trang", len(j(cl.post("/doi-social/fp/lich/xem-truoc", json={"trang_id": P1, "so": 2}))["gio"]) == 2)
r = j(cl.post("/doi-social/fp/media", files=[("tep", ("tập 5.jpg", b"\xff\xd8anh", "image/jpeg")),
                                           ("tep", ("clip.mp4", b"vid", "video/mp4"))]))
check("POST media nhiều tệp", r["ok"] and [x["loai"] for x in r["muc"]] == ["anh", "video"]
      and fp.so_tu_ten_tep(r["muc"][0]["tep"]) == 5)
tep_moi = r["muc"][0]["tep"]
check("POST media sai đuôi -> lỗi", j(cl.post("/doi-social/fp/media", files=[("tep", ("x.exe", b"MZ", "application/x"))]))["ok"] is False)
check("GET media/{tep}", cl.get(f"/doi-social/fp/media/{tep_moi}").content == b"\xff\xd8anh")
check("GET media thoát thư mục -> 404", cl.get("/doi-social/fp/media/..%2Fdoi-social.db").status_code == 404)
check("GET media danh sách", any(x["tep"] == tep_moi for x in j(cl.get("/doi-social/fp/media"))["muc"]))
r = j(cl.post("/doi-social/fp/bai/tao", json={"trang_ids": [P1], "loai": "anh", "media": [tep_moi], "noi_dung": ["HTTP {a|a}"],
                                             "binh_luan": kb, "hen": "tu_dong", "chay_thu": True}))
check("xem trước đủ trường", all(k in r["xem_truoc"][0] for k in ("trang_id", "trang_ten", "loai", "noi_dung", "media",
                                                              "trang_thai", "hen_luc", "cach_hen")))
check("POST bai/tao chạy thử", r["ok"] and r["so"] == 1 and r["xem_truoc"][0]["noi_dung"] == "HTTP a"
      and r["xem_truoc"][0]["binh_luan"].startswith("Cảm ơn"))
r = j(cl.post("/doi-social/fp/bai/tao", json={"trang_ids": [P1], "loai": "anh", "media": [tep_moi], "noi_dung": ["HTTP thật"]}))
bh = r["muc"][0]["id"]
check("POST bai/tao ghi", r["ok"] and r["so"] == 1 and r["muc"][0]["trang_thai"] == "cho_duyet")
check("bai/tao lỗi -> ok false", j(cl.post("/doi-social/fp/bai/tao", json={"loai": "chu"}))["ok"] is False)
r = j(cl.get("/doi-social/fp/bai", params={"trang_thai": "cho_duyet", "trang": P1, "sap_xep": "hen"}))
check("GET bai lọc + dem", r["ok"] and any(x["id"] == bh for x in r["muc"]) and r["dem"].get("da_dang") and "trang_ten" in r["muc"][0])
check("GET bai sắp xếp tương tác", j(cl.get("/doi-social/fp/bai", params={"sap_xep": "tuong_tac"}))["muc"][0]["so_lieu"].get("tuong_tac") == 8)
r = j(cl.patch(f"/doi-social/fp/bai/{bh}", json={"noi_dung": "Đã sửa", "hen_luc": time.time() + 7200}))
check("PATCH bai", r["ok"] and r["bai"]["noi_dung"] == "Đã sửa")
check("PATCH bai đã đăng -> lỗi", j(cl.patch(f"/doi-social/fp/bai/{tao['chu']}", json={"noi_dung": "x"}))["ok"] is False)
r = j(cl.post(f"/doi-social/fp/bai/{bh}/kiem-tra"))
check("POST bai/{id}/kiem-tra", r["ok"] and r["dat"] and {x["ten"] for x in r["buoc"]} >= {"Trang", "Token", "Tệp", "Giờ"})
r = j(cl.post("/doi-social/fp/bai/hanh-dong", json={"ids": [bh], "hanh_dong": "xep_lai_lich"}))
check("POST bai/hanh-dong xep_lai_lich", r["ok"] and r["so"] == 1)
r = j(cl.post("/doi-social/fp/bai/hanh-dong", json={"ids": [bh], "hanh_dong": "duyet"}))
check("POST bai/hanh-dong duyet", r["ok"] and r["so"] == 1 and fp.lay_bai(bh)["trang_thai"] == "cho_dang")
check("hành động bài lạ -> lỗi", j(cl.post("/doi-social/fp/bai/hanh-dong", json={"ids": [bh], "hanh_dong": "x"}))["ok"] is False)
r = cl.get("/doi-social/fp/bai/xuat.csv", params={"trang": P1})
JS.append(r.text)
check("GET bai/xuat.csv", r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "Đã sửa" in r.text)
r = j(cl.get("/doi-social/fp/binh-luan", params={"trang": P1, "chi_khach": 1}))
check("GET binh-luan", r["ok"] and r["tong"] >= 3 and all(not x["la_cua_trang"] for x in r["muc"]) and "hom_nay" in r
      and r["quet_luc"])
G.bl[P1] = [{"id": "cm16", "from": {"id": "u4", "name": "Bé"}, "message": "Hello"}]
r = j(cl.post("/doi-social/fp/binh-luan/quet", json={"trang": P1}))
check("POST binh-luan/quet", r["ok"] and r["so_moi"] == 1)
r = j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["cm16"], "hanh_dong": "tra_loi", "chu": "Chào {bạn|bạn}"}))
check("hanh-dong tra_loi gửi ngay", r["ok"] and r["muc"][0]["trang_thai"] == "da_tra_loi"
      and G.tim("POST", "cm16/comments")[-1]["data"]["message"] == "Chào bạn")
r = j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["cm11"], "hanh_dong": "gui"}))
check("hanh-dong gui (đề xuất của quy tắc)", r["ok"] and fp.lay_binh_luan("cm11")["trang_thai"] == "da_tra_loi")
r = j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["cm15"], "hanh_dong": "an"}))
check("hanh-dong an", r["ok"] and fp.lay_binh_luan("cm15")["an"])
check("hanh-dong hien", j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["cm15"], "hanh_dong": "hien"}))["ok"]
      and not fp.lay_binh_luan("cm15")["an"])
r = j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["cm15"], "hanh_dong": "ai_soan"}))
check("hanh-dong ai_soan", r["ok"] and r["muc"][0]["tra_loi"].startswith("Dạ ") and r["muc"][0]["trang_thai"] == "cho_duyet")
check("hanh-dong bo_qua", j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["cm15"], "hanh_dong": "bo_qua"}))["ok"]
      and fp.lay_binh_luan("cm15")["trang_thai"] == "bo_qua")
check("hanh-dong bình luận lạ -> lỗi", j(cl.post("/doi-social/fp/binh-luan/hanh-dong", json={"ids": ["x"], "hanh_dong": "gui"}))["ok"] is False)
r = j(cl.post("/doi-social/fp/quy-tac", json={"ten": "HTTP", "tu_khoa": "ship, giao hàng", "mau": "Dạ có ạ"}))
qh = r["quy_tac"]["id"]
check("POST quy-tac (từ khoá dạng chuỗi)", r["ok"] and r["quy_tac"]["tu_khoa"] == ["ship", "giao hàng"]
      and r["quy_tac"]["tu_gui"] is False)
check("GET quy-tac", any(x["id"] == qh for x in j(cl.get("/doi-social/fp/quy-tac"))["muc"]))
check("PATCH quy-tac", j(cl.patch(f"/doi-social/fp/quy-tac/{qh}", json={"tu_gui": True}))["quy_tac"]["tu_gui"] is True)
check("DELETE quy-tac", j(cl.delete(f"/doi-social/fp/quy-tac/{qh}"))["ok"])
check("POST tu-dong dừng", j(cl.post("/doi-social/fp/tu-dong", json={"dung": True}))["dung_tu_dong"] is True and fp.dung_tu_dong())
check("POST tu-dong chạy lại", j(cl.post("/doi-social/fp/tu-dong", json={"dung": False}))["dung_tu_dong"] is False)
r = j(cl.get("/doi-social/fp/bao-cao", params={"trang": P1, "ngay": 7}))
check("GET bao-cao", r["ok"] and r["trang"] and "chuoi" in r and "bai" in r)
check("POST bao-cao/cap-nhat", j(cl.post("/doi-social/fp/bao-cao/cap-nhat", json={}))["ok"])
r = j(cl.get("/doi-social/fp/canh-bao"))
check("GET canh-bao", r["ok"] and set(r["dem"]) == {"chan", "nang", "nhac"} and r["kiem_luc"])
check("POST canh-bao/kiem", j(cl.post("/doi-social/fp/canh-bao/kiem"))["ok"])
check("GET canh-bao/lich-su", j(cl.get("/doi-social/fp/canh-bao/lich-su"))["muc"])
r = cl.get("/doi-social/fp/canh-bao/xuat")
JS.append(r.text)
check("GET canh-bao/xuat text", r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
      and "== Token" in r.text)
r = j(cl.post("/doi-social/fp/kenh", json={"link": "https://www.youtube.com/@kenh", "nhom_id": nh["id"], "loai_bai": "video"}))
kh = r["kenh"]["id"]
check("POST kenh (+ nhom_ten, trang_ten mảng, co_yt_dlp)", r["ok"] and r["kenh"]["nen_tang"] == "youtube"
      and r["kenh"]["co_yt_dlp"] is True and r["kenh"]["nhom_ten"] == "Phim" and isinstance(r["kenh"]["trang_ten"], list))
check("GET kenh", any(x["id"] == kh for x in j(cl.get("/doi-social/fp/kenh"))["muc"]))
check("PATCH kenh", j(cl.patch(f"/doi-social/fp/kenh/{kh}", json={"chu_ky_gio": 12}))["kenh"]["chu_ky_gio"] == 12)
check("kênh link sai -> lỗi", j(cl.post("/doi-social/fp/kenh", json={"link": "http://x", "trang_ids": [P1]}))["ok"] is False)
r = j(cl.post(f"/doi-social/fp/kenh/{kh}/quet"))
check("POST kenh/{id}/quet (so_moi)", r["ok"] and r["kenh"]["trang_thai"] == "tot" and "so_moi" in r)
check("DELETE kenh", j(cl.delete(f"/doi-social/fp/kenh/{kh}"))["ok"])
r = j(cl.get("/doi-social/fp/instagram"))
check("GET instagram", r["ok"] and r["muc"][0]["ig_id"] == "1789" and r["muc"][0]["toi_da"] == 50)
r = j(cl.post("/doi-social/fp/cai-dat", json={"luong": 5, "goc_cong_khai": "https://minmin.example.com"}))
check("POST cai-dat", r["ok"] and r["cai_dat"]["luong"] == 5 and r["goc_cong_khai"] == "https://minmin.example.com")
check("cai-dat sai -> lỗi", j(cl.post("/doi-social/fp/cai-dat", json={"luong": 999}))["ok"] is False)
r = j(cl.get("/doi-social/fp/cai-dat"))
check("GET cai-dat (khoá ở cấp ngoài + cai_dat)", r["ok"] and r["cai_dat"]["ig_toi_da_24h"] == 50 and r["luong"] == 5
      and "dung_tu_dong" in r and "co_yt_dlp" in r)
check("GET bai moi_trang=1 luôn có dem.cho_duyet", "cho_duyet" in j(cl.get("/doi-social/fp/bai",
      params={"trang_thai": "loi", "moi_trang": 1}))["dem"])
r = cl.get("/doi-social/fp/cong-khai/" + fp.ma_cong_khai(tep_moi))
check("GET cong-khai hợp lệ (không cookie)", r.status_code == 200 and r.content == b"\xff\xd8anh")
check("GET cong-khai sai mã -> 404", cl.get("/doi-social/fp/cong-khai/" + "x" * 30 + ".yyyy").status_code == 404)
for i in range(4):
    r = j(cl.delete(f"/doi-social/fp/kho/{kb}")) if i == 0 else None
check("DELETE kho", fp.lay_kho(kb) is None)
check("xoá bài", j(cl.post("/doi-social/fp/bai/hanh-dong", json={"ids": [bh], "hanh_dong": "xoa"}))["so"] == 1)
rds.ly_do_chan = lambda: "khoá"
check("app chưa mở khoá -> 403", cl.get("/doi-social/fp/tong-quan").status_code == 403
      and cl.get("/doi-social/fp/cong-khai/" + fp.ma_cong_khai(anh[0])).status_code == 404)
rds.ly_do_chan = lambda: None

# ================================================================== không lộ token
lo = [USER_TOK, PAGE_TOK[P1], PAGE_TOK[P2], "EAAPASTEDsecondTokenQwertyuiop12345", "EAAKNtokenZxcvbnmasdfgh1234"]
for u in ("/doi-social/fp/trang", "/doi-social/fp/bai", "/doi-social/fp/nhom", "/doi-social/fp/canh-bao/lich-su",
          "/doi-social/fp/binh-luan", "/doi-social/fp/kenh", "/doi-social/fp/token"):
    JS.append(cl.get(u).text)
JS.append(fp.xuat_chan_doan())
JS.append(json.dumps(fp.ds_nhat_ky(500), ensure_ascii=False))
tat_ca = "\n".join(JS)
check("không chuỗi token thật nào trong mọi JSON/xuất", not [t for t in lo if t in tat_ca], [t[:8] for t in lo if t in tat_ca])
check("lọc token trong chữ lỗi", fp._loc_token("lỗi EAAABBBCCCDDDEEEFFF123 x") == "lỗi EAAABB…F123 x")

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
