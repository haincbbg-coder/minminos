"""Đội Social 26.10.200: Viết bài AI chọn rõ nơi đăng (Fanpage qua API, hoặc nick + đúng Trang của nick)
và giờ đăng (ngay khi duyệt / theo lịch nhóm Trang / chọn giờ, các bài cách nhau). KHÔNG mạng.
python tests/run.py doi_social_viet_bai"""
import asyncio, json, os, tempfile, time
from pathlib import Path
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
os.environ["JAVIS_DOI_SOCIAL_VONG"] = "0"
from _paths import ROOT  # noqa: E402,F401

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


import doi_social as ds  # noqa: E402
import doi_social_v2 as v2  # noqa: E402
import doi_social_fanpage as fp  # noqa: E402

ds.mo(Path(tempfile.mkdtemp()) / "kho")
A = ds.ghep(ds.tao_ma_ghep(), "PC A")
MA = A["may_id"]
ds.nhip(MA, [{"id": "n1", "ten": "Hán Ngọc Nhi", "trinh_duyet": "chrome"}, {"id": "n2", "ten": "Nick 2", "trinh_duyet": "chrome"}],
        kich_ban=["dang_ban_nhap", "quet_tai_khoan"], song_song=3)
v2.dat_gioi_han_v2({"chung": {"nghi_phut": [0, 0]}})
for i, ten in ((111111, "Trang Một"), (222222, "Trang Hai"), (333333, "Trang Ba"), (444444, "Trang Bốn"), (555555, "Trang Năm")):
    fp.ghi_trang({"id": str(i), "name": ten, "tasks": ["CREATE_CONTENT"]})
q = v2.tao_quet_tai_khoan(["n1"], ["facebook"])
g = ds.nhan_viec(MA)
v2.ghi_dich_den(g["id"], MA, ["facebook"], [
    {"nen_tang": "facebook", "loai": "trang", "ten": "HALIMI Store", "link": "https://www.facebook.com/halimi.store"},
    {"nen_tang": "facebook", "loai": "trang", "ten": "MeiMei Design", "link": "https://www.facebook.com/meimei"}])
ds.ghi_ket_qua(g["id"], MA, True, "ok", [])
k = v2.tao_kien_thuc({"loai": "san_pham", "ten": "Váy lụa HALIMI", "mo_ta": "Váy lụa tơ tằm dáng suông"})

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.doi_social as rds  # noqa: E402
rds.ly_do_chan = lambda: None
goi = {"n": 0, "p": []}


async def ai(prompt, anh):
    goi["n"] += 1
    goi["p"].append(prompt)
    import re
    so = int(re.search(r"Viết (\d+) bản", prompt).group(1))
    return json.dumps({"ban": [f"Bài số {goi['n']}-{i} về váy lụa tơ tằm mát, dáng suông dễ mặc đi làm." for i in range(so)]},
                      ensure_ascii=False)

app = FastAPI()
rds.register(app, rds.DoiSocialDeps(goi_ai=ai))
cl = TestClient(app)
now = time.time()

# ---- Fanpage qua API: xem trước không gọi AI
r = cl.post("/doi-social/viet-bai", json={"che_do": "api", "trang_ids": ["111111", "222222"], "so_ban": 2,
                                          "lich": "gio", "bat_dau": now + 3600, "cach_phut": 30, "xem_truoc": True}).json()
check("xem trước API: 2 Trang x 2 bài = 4 dòng kế hoạch", r["ok"] and len(r["ke_hoach"]) == 4, r)
check("xem trước không gọi AI", goi["n"] == 0)
gio = [x["hen_luc"] for x in r["ke_hoach"]]
check("chọn giờ: bài k lúc bat_dau + k*30 phút", all(abs(gio[i] - (now + 3600 + i * 1800)) < 2 for i in range(4)), gio)
check("mỗi Trang nhận đủ 2 bài", sorted(x["dich_ten"] for x in r["ke_hoach"]) == ["Trang Hai", "Trang Hai", "Trang Một", "Trang Một"])
check("quá 20 bài bị chặn", cl.post("/doi-social/viet-bai", json={"che_do": "api", "trang_ids": ["111111", "222222", "333333", "444444", "555555"],
                                                                    "so_ban": 5, "xem_truoc": True}).json()["ok"] is False)
check("API không chọn Trang bị chặn", cl.post("/doi-social/viet-bai", json={"che_do": "api", "trang_ids": [], "xem_truoc": True}).json()["ok"] is False)

# ---- Fanpage qua API: viết thật
r = cl.post("/doi-social/viet-bai", json={"che_do": "api", "san_pham_id": k["id"], "trang_ids": ["111111", "222222", "333333"],
                                          "so_ban": 2, "lich": "gio", "bat_dau": now + 7200, "cach_phut": 60}).json()
check("viết thật API: 6 bài", r["ok"] and r["so"] == 6, r)
check("6 bài cần 2 lượt AI (5 + 1)", goi["n"] == 2, goi["n"])
check("lượt sau được dặn viết khác các bài trước", "Viết KHÁC hẳn" in goi["p"][1])
bai = fp.ds_bai(trang_thai="cho_duyet")["muc"]
check("mọi bài API vào chờ duyệt, nguồn AI", len(bai) == 6 and all(b["nguon"] == "ai" for b in bai))
check("không có hai bài trùng chữ", len({b["noi_dung"] for b in bai}) == 6)
nh = fp.tao_nhom("Nhóm tắt duyệt", cau_hinh={"duyet_truoc": False})
fp.sua_trang("333333", nhom_id=nh["id"])
r = cl.post("/doi-social/viet-bai", json={"che_do": "api", "san_pham_id": k["id"], "trang_ids": ["333333"], "so_ban": 1,
                                          "lich": "duyet"}).json()
check("bài AI vẫn chờ duyệt dù nhóm tắt Duyệt trước", r["ok"] and r["muc"][0]["trang_thai"] == "cho_duyet", r)
check("lịch 'ngay khi duyệt' = hen_luc bây giờ", r["muc"][0]["hen_luc"] and r["muc"][0]["hen_luc"] <= time.time() + 5)
r = cl.post("/doi-social/viet-bai", json={"che_do": "api", "trang_ids": ["111111"], "so_ban": 1, "lich": "nhom",
                                          "xem_truoc": True}).json()
check("lịch theo nhóm Trang cho ra giờ trong tương lai", r["ok"] and r["ke_hoach"][0]["hen_luc"] > now, r)

# ---- nick ở máy nhà: Trang Facebook của nick
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "fb_trang", "so_ban": 2, "xem_truoc": True}).json()
check("Trang FB qua nick: thiếu nick bị chặn", r["ok"] is False and "nick" in r["error"])
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "fb_trang", "nick_id": "n1", "so_ban": 2, "xem_truoc": True}).json()
check("Trang FB qua nick: thiếu Trang bị chặn", r["ok"] is False and "Trang" in r["error"])
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "fb_trang", "nick_id": "n1", "so_ban": 2,
                                          "dich": "https://www.facebook.com/meimei", "lich": "gio", "bat_dau": now + 600,
                                          "cach_phut": 120, "xem_truoc": True}).json()
check("kế hoạch nick: tên Trang lấy từ danh sách đã quét", r["ok"] and r["ke_hoach"][0]["dich_ten"] == "MeiMei Design", r)
check("kế hoạch nick: hai giờ cách 2 tiếng", abs(r["ke_hoach"][1]["hen_luc"] - r["ke_hoach"][0]["hen_luc"] - 7200) < 1)
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "san_pham_id": k["id"], "noi_dang": "fb_trang", "nick_id": "n1",
                                          "so_ban": 2, "dich": "https://www.facebook.com/meimei", "lich": "gio",
                                          "bat_dau": now + 600, "cach_phut": 120}).json()
check("viết thật qua nick: 2 nháp", r["ok"] and r["so"] == 2, r)
n0 = r["muc"][0]
check("nháp mang link Trang + tên Trang + giờ đăng", n0["nhom"] == "https://www.facebook.com/meimei"
      and n0["muc_tieu"]["dich_ten"] == "MeiMei Design" and abs(n0["hen_luc"] - (now + 600)) < 2)
check("nháp hẹn xa không hết hạn trước giờ đăng", r["muc"][1]["het_han"] > r["muc"][1]["hen_luc"])
d = v2.duyet_ban_nhap(n0["id"], True)
vc = ds.lay_viec(d["viec_id"])
check("duyệt -> việc của đúng nick, chờ tới giờ", vc["nick_id"] == "n1" and vc["trang_thai"] == "cho_chay")
check("việc chưa tới giờ thì máy chưa nhận", ds.nhan_viec(MA) is None)
ds._db().execute("UPDATE viec SET chay_sau=? WHERE id=?", (time.time() - 1, vc["id"]))
gv = ds.nhan_viec(MA)
check("tới giờ thì máy nhận việc đăng nháp", gv and gv["id"] == vc["id"]
      and gv["tham_so"]["tham_so"]["nhom"] == "https://www.facebook.com/meimei")
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "fb_tuong", "so_ban": 1, "lich": "nhom", "xem_truoc": True}).json()
check("lịch nhóm Trang không dùng cho nick", r["ok"] is False)
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "instagram", "so_ban": 1, "xem_truoc": True}).json()
check("Instagram qua nick cần chọn nick", r["ok"] is False)
r = cl.post("/doi-social/viet-bai", json={"san_pham_id": k["id"], "noi_dang": "fb_nhom", "so_ban": 1}).json()
check("kiểu gọi cũ (chỉ noi_dang) vẫn chạy như trước", r["ok"] and r["che_do"] == "nick" and r["muc"][0]["hen_luc"] is None, r)
check("giờ đã qua bị chặn", cl.post("/doi-social/viet-bai", json={"che_do": "api", "trang_ids": ["111111"], "lich": "gio",
                                                                   "bat_dau": now - 3600, "xem_truoc": True}).json()["ok"] is False)

# nháp không gán nick, hẹn giờ: mẫu "Đăng bài AI đã duyệt" chưa lấy trước giờ
nb = v2.tao_ban_nhap(loai="bai_dang", noi_dang="fb_tuong", noi_dung="Bài hẹn giờ không gán nick", hen_luc=time.time() + 3600)
v2.duyet_ban_nhap(nb["id"], True)
ds._db().execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc) VALUES('fb_dang_tuong_ai',?,?,?,?,'dang_chay',?)",
                 (MA, "n2", "Nick 2", "{}", time.time()))
dot = {"viec": [{"id": ds._db().execute("SELECT MAX(id) FROM viec").fetchone()[0]}]}
if dot:
    vid = dot["viec"][0]["id"]
    check("nháp hẹn giờ chưa tới thì mẫu đăng AI chưa lấy", v2.lay_ban_nhap_cho_viec(vid, MA, "fb_tuong") is None)

# ---- 26.10.229: video cho TikTok / YouTube qua nick
_tam = Path(tempfile.mkdtemp())
(_tam / "vay.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 2000)
(_tam / "anh.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 500)
VD = fp.luu_media("vay.mp4", _tam / "vay.mp4")["tep"]
AN = fp.luu_media("anh.jpg", _tam / "anh.jpg")["tep"]
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "tiktok", "nick_id": "n1", "so_ban": 1,
                                          "xem_truoc": True}).json()
check("TikTok qua nick thiếu video bị chặn", r["ok"] is False and "video" in r["error"])
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "tiktok", "nick_id": "n1", "so_ban": 1,
                                          "media": [VD, AN], "xem_truoc": True}).json()
check("không trộn video với ảnh", r["ok"] is False)
r = cl.post("/doi-social/viet-bai", json={"che_do": "api", "trang_ids": ["111111"], "so_ban": 1, "media": [VD],
                                          "xem_truoc": True}).json()
check("Fanpage API không nhận video ở Viết bài AI", r["ok"] is False)
r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "san_pham_id": k["id"], "noi_dang": "tiktok",
                                          "nick_id": "n1", "so_ban": 1, "media": [VD]}).json()
check("TikTok qua nick kèm video: nháp có tệp video", r["ok"] and r["muc"][0]["tep"]
      and r["muc"][0]["tep"][0]["ten"].endswith(".mp4") and r["ke_hoach"][0]["loai"] == "video", r)
if "youtube" in v2.NOI_DANG:
    r = cl.post("/doi-social/viet-bai", json={"che_do": "nick", "noi_dang": "youtube", "nick_id": "n1", "so_ban": 1,
                                              "media": [AN], "xem_truoc": True}).json()
    check("YouTube cần video (ảnh không đủ)", r["ok"] is False and "video" in r["error"])

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
