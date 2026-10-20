"""Đội Social bản đầy đủ (26.10.187): đợt chạy, hạn mức, song song, sự kiện, kho bài, nháp,
lịch hẹn, kế hoạch, quyền máy, đường tĩnh, CSV. KHÔNG mạng, AI được giả lập.
python tests/run.py doi_social_v2"""
import asyncio, base64, json, os, sys, tempfile, time, types
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


import doi_social as ds  # noqa: E402
import doi_social_v2 as v2  # noqa: E402

goc = Path(tempfile.mkdtemp())
ds.mo(goc / "kho")
ds.mo(goc / "kho")      # migration chạy lại không lỗi
check("migration idempotent: cột mới có mặt", {"kich_ban", "song_song"} <= {
    r[1] for r in ds._db().execute("PRAGMA table_info(may)")} and {"dot_id", "chay_thu", "ket_qua"} <= {
    r[1] for r in ds._db().execute("PRAGMA table_info(viec)")})
check("KY_NANG nhận mọi mẫu + kỹ năng nội bộ",
      "fb_nuoi_nick" in ds.KY_NANG and "dang_ban_nhap" in ds.KY_NANG and "fb_gui_tin" in ds.KY_NANG
      and "fb_dang_bai" in ds.KY_NANG)

# ---- hai máy, nick
A = ds.ghep(ds.tao_ma_ghep(), "PC A")
B = ds.ghep(ds.tao_ma_ghep(), "PC B")
ds.nhip(A["may_id"], [{"id": f"n{i}", "ten": f"Nick {i}", "trinh_duyet": "chrome"} for i in range(1, 5)],
        kich_ban=["fb_binh_luan_nhom_sp", "fb_dang_tuong_kho", "fb_nuoi_nick", "fb_tra_loi_binh_luan"], song_song=2)
ds.nhip(B["may_id"], [{"id": "b1", "ten": "Nick B", "trinh_duyet": "chrome"}], kich_ban=["fb_nuoi_nick"])
MA, MB = A["may_id"], B["may_id"]
v2.dat_gioi_han_v2({"chung": {"nghi_phut": [0, 0]}})
check("giới hạn v2 ghép sâu, giữ phần mặc định",
      v2.gioi_han_v2()["chung"]["nghi_phut"] == [0, 0] and v2.gioi_han_v2()["nen_tang"]["facebook"]["thich"] == [8, 30])
check("giới hạn v2 sai bị từ chối", raises(lambda: v2.dat_gioi_han_v2({"chung": {"nghi_phut": [9, 2]}}), "lớn hơn"))

sp = v2.tao_kien_thuc({"ten": "Váy lụa", "gia": "459k", "mo_ta": "Váy lụa mát"})
check("kiến thức tạo được", sp["id"] > 0 and v2.lay_kien_thuc(sp["id"])["tai_lieu"] == [])

# ---- đợt chạy
check("mẫu lạ bị từ chối", raises(lambda: v2.tao_dot(kich_ban="xoa_het", nick=["n1"], tham_so={}), "không có mẫu"))
check("thiếu tham số bắt buộc", raises(lambda: v2.tao_dot(kich_ban="fb_binh_luan_nhom_sp", nick=["n1"], tham_so={}), "thiếu"))
check("nick không có bị từ chối",
      raises(lambda: v2.tao_dot(kich_ban="fb_nuoi_nick", nick=["khong-co"], tham_so={}), "không thấy nick"))
dot = v2.tao_dot(kich_ban="fb_binh_luan_nhom_sp", nick=["n1", "n2", "n3"], tham_so={"san_pham": str(sp["id"])},
                 song_song=2)
vs = dot["viec"]
check("đợt tạo đủ 3 việc cho_chay đúng mẫu",
      len(vs) == 3 and all(v["ky_nang"] == "fb_binh_luan_nhom_sp" and v["trang_thai"] == "cho_chay" for v in vs))
t0 = vs[0]["tham_so"]
check("tham số việc đúng hợp đồng (kich_ban, tham_so, chay_thu, dot_id, nen_tang)",
      t0["kich_ban"] == "fb_binh_luan_nhom_sp" and t0["dot_id"] == dot["id"] and t0["chay_thu"] is True
      and t0["nen_tang"] == "facebook" and t0["tham_so"]["che_do"] == "chay_thu" and dot["chay_thu"] == 1)

g1 = ds.nhan_viec(MA)
g2 = ds.nhan_viec(MA)
g3 = ds.nhan_viec(MA)
check("song song: máy nhận 2 việc, việc thứ 3 chờ", g1 and g2 and g3 is None and g1["nick_id"] != g2["nick_id"])
check("việc giao kèm hạn mức + nghỉ giây", "binh_luan_nhom" in g1["tham_so"]["han_muc"]
      and g1["tham_so"]["nghi_giay"] == [6, 25])
check("đợt chuyển dang_chay", v2.lay_dot(dot["id"], False)["trang_thai"] == "dang_chay")
dot_nhap = v2.tao_dot(kich_ban="fb_nuoi_nick", nick=[g1["nick_id"]], tham_so={}, song_song=3)
check("một nick không chạy 2 việc cùng lúc (song song 3 vẫn không giao)", ds.nhan_viec(MA) is None)
dot_tt = v2.tao_dot(kich_ban="fb_tham_gia_nhom_sp", nick=["n4"], tham_so={"san_pham": str(sp["id"])}, song_song=3)
check("mẫu máy chưa hỗ trợ không bị giao", ds.nhan_viec(MA) is None)
check("máy B không nhận việc của máy A", ds.nhan_viec(MB) is None)

# ---- huỷ đợt
v2.huy_dot(dot["id"])
d = v2.lay_dot(dot["id"])
con = [v for v in d["viec"] if v["id"] not in (g1["id"], g2["id"])][0]
check("huỷ: việc chờ thành bỏ, việc đang chạy nhận cờ dừng",
      con["trang_thai"] == "bo" and v2.can_dung(g1["id"]) and d["trang_thai"] == "huy")
check("huỷ lần hai báo lỗi", raises(lambda: v2.huy_dot(dot["id"]), "kết thúc"))
ds.ghi_ket_qua(g1["id"], MA, True, "ok", dem={"thanh_cong": 2, "bo_qua": 1, "loi": 0})
ds.ghi_ket_qua(g2["id"], MA, False, "lỗi")
check("kết quả lưu dem", ds.lay_viec(g1["id"])["ket_qua"] == {"thanh_cong": 2, "bo_qua": 1, "loi": 0})
check("đợt huỷ vẫn là huy khi việc cuối xong", v2.lay_dot(dot["id"], False)["trang_thai"] == "huy")

# ---- hạn mức
v2.dat_nick_meta(["n2"], tao_tu="2015-01", nhan=["facebook"])
check("tao_tu sai dạng bị từ chối", raises(lambda: v2.dat_nick_meta(["n2"], tao_tu="2015"), "YYYY-MM"))
check("nick lâu năm dùng số thứ 2", v2.han_muc("n2", "facebook", ["thich"])["thich"] == 30)
check("nick mới (không tuổi) dùng số thứ 1", v2.han_muc("n3", "facebook", ["thich"])["thich"] == 8)
with ds._db() as c:
    c.execute("INSERT INTO viec(ky_nang, may_id, nick_id, nick_ten, tham_so, trang_thai, tao_luc, bat_dau, xong_luc) "
              "VALUES('fb_nuoi_nick',?,?,?,'{}','xong',?,?,?)", (MA, "n3", "Nick 3", time.time() - 22 * 86400,
                                                              time.time() - 22 * 86400, time.time() - 22 * 86400))
check("nick mới tăng 25%/tuần: 3 tuần -> 8*1.25^3 = 15", v2.han_muc("n3", "facebook", ["thich"])["thich"] == 15)
check("hành động không có trần = 999", v2.han_muc("n3", "facebook", ["quet"])["quet"] == 999)

# hết hạn mức -> bỏ qua ngay ở máy chủ
with ds._db() as c:
    for _ in range(15):
        c.execute("INSERT INTO su_kien(luc, nick_id, nen_tang, hanh_dong, ket_qua) VALUES(?,?,?,?,?)",
                  (time.time(), "n3", "facebook", "thich", "thanh_cong"))
gn = ds.nhan_viec(MA)
check("hết việc trước thì nick được giao việc kế", gn and gn["dot_id"] == dot_nhap["id"])
d_het = v2.tao_dot(kich_ban="fb_nuoi_nick", nick=["n3"], tham_so={}, song_song=2)
check("việc hết hạn mức không được giao", ds.nhan_viec(MA) is None)
vh = v2.lay_dot(d_het["id"])["viec"][0]
check("việc hết hạn mức kết thúc bỏ qua, đợt hoàn tất",
      vh["trang_thai"] == "bo" and "đủ giới hạn" in vh["thong_diep"] and vh["ket_qua"]["bo_qua"] == 1
      and v2.lay_dot(d_het["id"], False)["trang_thai"] == "hoan_tat")
check("bỏ qua ghi sự kiện bo_qua", any(s["ket_qua"] == "bo_qua" for s in v2.lay_dot(d_het["id"])["su_kien"]))
check("đợt xong xếp thông báo cho chủ", any(t == "Đợt chạy xong" for t, _ in v2.lay_bao()))

# ---- sự kiện + cảnh báo (việc nuôi nick của n1 đang chạy)
sk = v2.ghi_su_kien(gn["id"], MA, {"hanh_dong": "thich", "ket_qua": "thanh_cong", "chi_tiet": "Thích 1 bài"})
check("sự kiện trả con_lai mới", sk["con_lai"]["thich"] == 7 and sk["dung"] is False)
check("ket_qua sai bị từ chối", raises(lambda: v2.ghi_su_kien(gn["id"], MA, {"ket_qua": "xyz"}), "ket_qua"))
check("máy khác không ghi sự kiện được", raises(lambda: v2.ghi_su_kien(gn["id"], MB, {"ket_qua": "loi"}), "không thuộc"))
v2.ghi_su_kien(gn["id"], MA, {"hanh_dong": "", "ket_qua": "loi", "chi_tiet": "Bị đăng xuất", "ma": "dang_xuat"})
n1 = [n for n in v2.ds_nick() if n["id"] == "n1"][0]
tq = v2.tong_quan()
check("mã dang_xuat ghi cảnh báo nick + vào Cần bạn xử lý",
      n1["canh_bao"] == {"facebook": "dang_xuat"}
      and any(x["loai"] == "nick" and x["den"] == "#/tai-khoan" for x in tq["can_xu_ly"]))
check("báo chủ nick bị đăng xuất", any("Nick 1" in b for _, b in v2.lay_bao()))
v2.ghi_su_kien(gn["id"], MA, {"hanh_dong": "thich", "ket_qua": "thanh_cong"})
check("sự kiện thành công sau đó xoá cảnh báo",
      [n for n in v2.ds_nick() if n["id"] == "n1"][0]["canh_bao"] == {})
v2.ghi_buoc(gn["id"], "Đang lướt bảng tin")
check("đang chạy có dòng nhật ký gần nhất", any(x["id"] == gn["id"] and x["buoc_cuoi"] == "Đang lướt bảng tin"
                                              for x in v2.dang_chay()))
hn = v2.hom_nay_theo_nick()
check("hôm nay theo nick có chi tiết", any(x["nick_id"] == "n1" and x["thanh_cong"] == 2 and "Thích" in x["chi_tiet"]
                                         for x in hn))
ds.ghi_ket_qua(gn["id"], MA, True, "xong")

# ---- kho bài: 3 ngữ nghĩa
tam = goc / "a.jpg"
tam.write_bytes(b"\xff\xd8x")
check("kho chặn đuôi lạ", raises(lambda: v2.them_kho(nen_tang="facebook", noi_dung="x", tep=[("a.exe", str(tam))]), "chỉ nhận"))
ids = v2.them_kho(nen_tang="facebook", noi_dung="Bài một\n===\nBài hai\n===\nBài ba")
check("=== tách 3 bài", len(ids) == 3 and v2.kho_tong("facebook")["chung"]["con"] == 3)
idt = v2.them_kho(nen_tang="tiktok", tep=[("v.mp4", str(tam))])
b = v2.lay_bai_kho(idt[0])
check("tệp kho lưu tên an toàn, đường tệp chặn '..'",
      b["tep"][0]["luu"] == "00.mp4" and v2.duong_tep_kho(idt[0], "00.mp4") and v2.duong_tep_kho(idt[0], "../x") is None)
dk = v2.tao_dot(kich_ban="fb_dang_tuong_kho", nick=["n4"], tham_so={"kho": "chung", "so_bai": 3})
gk = ds.nhan_viec(MA)
check("việc kho được giao", gk and gk["dot_id"] == dk["id"])
k1 = v2.lay_kho_cho_viec(gk["id"], MA)
check("lấy kho giữ bài, gọi lại trả đúng bài đang giữ",
      k1["trang_thai"] == "dang_giu" and v2.lay_kho_cho_viec(gk["id"], MA)["id"] == k1["id"])
check("máy khác không đọc được bài kho của việc này", raises(lambda: v2.lay_kho_cho_viec(gk["id"], MB), "không thuộc"))
check("ok -> da_dang", v2.ket_qua_kho(k1["id"], MA, True, True, "https://fb.com/p/1")["trang_thai"] == "da_dang")
k2 = v2.lay_kho_cho_viec(gk["id"], MA)
check("lỗi TRƯỚC khi bấm đăng -> về hàng chờ",
      v2.ket_qua_kho(k2["id"], MA, False, False, loi="mạng")["trang_thai"] == "cho")
k3 = v2.lay_kho_cho_viec(gk["id"], MA)
check("lỗi SAU khi bấm đăng -> loi, không tự đăng lại",
      k3["id"] == k2["id"] and v2.ket_qua_kho(k3["id"], MA, False, True, loi="treo")["trang_thai"] == "loi")
check("bài lỗi trả lại được", v2.tra_lai_kho(k3["id"])["trang_thai"] == "cho")
k4 = v2.lay_kho_cho_viec(gk["id"], MA)
ds.ghi_ket_qua(gk["id"], MA, True, "xong")
check("việc kết thúc khi còn giữ bài -> bài thành lỗi (an toàn)", v2.lay_bai_kho(k4["id"])["trang_thai"] == "loi")

# ---- bản nháp
dr = v2.tao_dot(kich_ban="fb_tra_loi_binh_luan", nick=["n2"], tham_so={"che_do": "duyet_truoc"})
gr = ds.nhan_viec(MA)
check("việc AI duyệt trước được giao", gr and gr["dot_id"] == dr["id"] and gr["chay_thu"] == 0)
nh = v2.tao_ban_nhap_tu_may(gr["id"], MA, {"loai": "binh_luan", "noi_dang": "fb_nhom", "noi_dung": "Váy đẹp lắm",
                                           "link_goc": "https://facebook.com/groups/1/posts/2", "ly_do": "đúng nhu cầu"})
check("nháp từ máy: chờ duyệt, gán nick, hết hạn 18 giờ",
      nh["trang_thai"] == "cho_duyet" and nh["nick_id"] == "n2" and abs(nh["het_han"] - nh["tao_luc"] - 18 * 3600) < 2)
check("nháp loại sai bị từ chối", raises(lambda: v2.tao_ban_nhap_tu_may(gr["id"], MA, {"loai": "x", "noi_dang": "fb_nhom",
                                                                                     "noi_dung": "a"}), "loại"))
ds.ghi_ket_qua(gr["id"], MA, True, "xong")
nd = v2.duyet_ban_nhap(nh["id"], True)
vd = ds.lay_viec(nd["viec_id"])
check("duyệt nháp -> việc dang_ban_nhap cho đúng nick, cho_chay",
      vd["ky_nang"] == "dang_ban_nhap" and vd["nick_id"] == "n2" and vd["trang_thai"] == "cho_chay"
      and vd["tham_so"]["tham_so"]["ban_nhap_id"] == nh["id"] and nd["trang_thai"] == "da_duyet")
check("duyệt lại lần hai bị từ chối", raises(lambda: v2.duyet_ban_nhap(nh["id"], True), "trạng thái"))
gd = ds.nhan_viec(MA)
check("máy có mẫu fb_ nhận việc dang_ban_nhap", gd and gd["id"] == vd["id"])
check("kết quả nháp -> da_dang", v2.ket_qua_ban_nhap(nh["id"], MA, True, "https://fb.com/c/1")["trang_thai"] == "da_dang")
ds.ghi_ket_qua(gd["id"], MA, True, "xong")
n_het = v2.tao_ban_nhap(loai="binh_luan", noi_dang="fb_nhom", noi_dung="cũ")
n_bai = v2.tao_ban_nhap(loai="bai_dang", noi_dang="fb_tuong", noi_dung="bài")
check("bài đăng hết hạn 72 giờ", abs(n_bai["het_han"] - n_bai["tao_luc"] - 72 * 3600) < 2)
v2.vong_nen(time.time() + 19 * 3600)
check("nháp quá hạn -> het_han, chưa quá hạn giữ nguyên",
      v2.lay_ban_nhap(n_het["id"])["trang_thai"] == "het_han" and v2.lay_ban_nhap(n_bai["id"])["trang_thai"] == "cho_duyet")
dsn = v2.ds_ban_nhap("cho_duyet")
check("danh sách nháp có đếm theo trạng thái", dsn["dem"]["het_han"] == 1 and dsn["dem"]["da_dang"] == 1)
check("nháp không nick duyệt xong nằm chờ mẫu AI lấy", v2.duyet_ban_nhap(n_bai["id"], True)["viec_id"] is None)

# ---- lịch hẹn
check("cron sai bị từ chối", raises(lambda: v2.tao_lich(kich_ban="fb_nuoi_nick", nick=["b1"], tham_so={}, cron="abc"), "cron"))
l = v2.tao_lich(kich_ban="fb_nuoi_nick", nick=["b1"], tham_so={"phut": 5}, cron="15 8 * * *", ten="Nuôi sáng")
check("lịch có mô tả cho người đọc và lần kế trong tương lai", "8:15" in l["mo_ta_lich"] and l["lan_ke"] > time.time())
with ds._db() as c:
    c.execute("UPDATE lich_hen SET lan_ke=? WHERE id=?", (time.time() - 5, l["id"]))
moi = v2.vong_nen()
l2 = v2.lay_lich(l["id"])
check("lịch đến giờ tạo đợt nguon=lich và tính lần kế",
      len(moi) == 1 and moi[0]["nguon"] == "lich" and moi[0]["lich_id"] == l["id"] and l2["so_lan"] == 1
      and l2["lan_ke"] > time.time() and l2["lan_truoc"])
check("không chạy lại khi chưa tới giờ", v2.vong_nen() == [])
v2.sua_lich(l["id"], bat=False)
with ds._db() as c:
    c.execute("UPDATE lich_hen SET lan_ke=? WHERE id=?", (time.time() - 5, l["id"]))
check("lịch tắt không chạy", v2.vong_nen() == [])

# ---- kế hoạch
kh = v2.tao_ke_hoach(mo_ta="Nuôi nick B", buoc=[{"kich_ban": "fb_nuoi_nick", "nick": ["b1"], "tham_so": {"phut": 4}},
                                               {"kich_ban": "khong_co", "nick": ["b1"], "tham_so": {}}])
check("kế hoạch bỏ bước sai, ghi chú lại", len(kh["buoc"]) == 1 and "Đã bỏ 1" in kh["mo_ta"]
      and kh["trang_thai"] == "cho_duyet")
check("kế hoạch toàn bước sai bị từ chối", raises(lambda: v2.tao_ke_hoach(mo_ta="x", buoc=[{"kich_ban": "zz"}]), "hợp lệ"))
check("kế hoạch chưa duyệt không tạo đợt", kh["dot_ids"] == [])
kd = v2.duyet_ke_hoach(kh["id"], True)
dk2 = v2.lay_dot(kd["dot_ids"][0])
check("duyệt kế hoạch -> đợt nguon=tro_ly", kd["trang_thai"] == "dang_chay" and dk2["nguon"] == "tro_ly"
      and dk2["viec"][0]["tham_so"]["tham_so"]["phut"] == 4)
check("kế hoạch không duyệt hai lần", raises(lambda: v2.duyet_ke_hoach(kh["id"], True), "trạng thái"))

# ---- nhóm FB, hội thoại, trí nhớ
ids_n = v2.them_nhom(sp["id"], ["https://www.facebook.com/groups/abc/?ref=x", "https://www.facebook.com/groups/abc"])
check("nhóm FB chuẩn hoá link, không trùng", len(ids_n) == 1)
check("link nhóm sai bị từ chối", raises(lambda: v2.them_nhom(sp["id"], ["http://x.com"]), "https"))
v2.ghi_da_lam("n1", "fb_bl:https://fb.com/p/9")
check("trí nhớ chống lặp theo nick và cả đội",
      v2.da_lam("n1", "fb_bl:https://fb.com/p/9") and not v2.da_lam("n2", "fb_bl:https://fb.com/p/9")
      and v2.da_lam("n2", "fb_bl:https://fb.com/p/9", ca_doi=True))

# ---- CSV
csv = v2.su_kien_csv()
check("CSV có BOM và tiêu đề tiếng Việt", csv.startswith("﻿") and "Thời gian" in csv and "Thành công" in csv)

# ---- HTTP
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import giay_phep  # noqa: E402
import routes.ket_noi_ngoai as knn  # noqa: E402
import routes.doi_social as rds  # noqa: E402

giay_phep.da_mo = lambda app_id: app_id == "doi_social"
knn.da_dong_y = lambda phan: True

gia = types.ModuleType("doi_social_ai")
goi = []


async def _xu_ly_may(muc, du_lieu, anh, *, goi_ai, kien_thuc):
    goi.append((muc, list(anh), [Path(a).exists() for a in anh], (kien_thuc or {}).get("ten")))
    if muc == "tra_loi_binh_luan":
        return {"noi_dung": "Bạn inbox shop nhé", "can_hoi_chu": True, "cau_hoi": "Váy có size XXL không?"}
    if muc == "tra_loi_tin_nhan":
        return {"noi_dung": "Dạ", "can_tra_loi_tay": False, "sdt": "0912345678"}
    if muc == "cham_bai":
        raise ValueError("AI trả rác")
    return {"ok": 1}


async def _tro_ly(tin, lich_su, boi_canh, *, goi_ai):
    return {"tra_loi": "Được", "ke_hoach": {"mo_ta": "Nuôi", "buoc": [{"kich_ban": "fb_nuoi_nick", "nick": ["b1"],
                                                                         "tham_so": {}}]}}


async def _viet_bai(kt, noi_dang, so_ban, yeu_cau, *, goi_ai):
    return [f"Bài {i} về {kt['ten']}" for i in range(so_ban)]


gia.xu_ly_may, gia.tro_ly, gia.viet_bai = _xu_ly_may, _tro_ly, _viet_bai
sys.modules["doi_social_ai"] = gia


async def _goi_ai(prompt, anh):
    return "{}"

bao_sk, bao_kh = [], []


async def _bao_sk(t, b):
    bao_sk.append(t)


async def _bao_kh(k):
    bao_kh.append(k["id"])

app = FastAPI()
rds.register(app, rds.DoiSocialDeps(goi_ai=_goi_ai, bao_su_kien=_bao_sk, bao_ke_hoach=_bao_kh,
                                    thong_tin_ai=lambda: {"engine": "claude", "san_sang": True}))
HA, HB = {"x-minmin-may": A["token"]}, {"x-minmin-may": B["token"]}
with TestClient(app) as tc:
    r = tc.post("/doi-social/may/nhip", headers=HA, json={"kich_ban": ["fb_nuoi_nick", "fb_binh_luan_nhom_sp",
                                                                      "fb_dang_tuong_kho", "fb_tra_loi_binh_luan",
                                                                      "fb_tra_loi_tin_nhan"], "song_song": 2})
    check("nhịp trả phiên bản Worker", r.status_code == 200 and r.json()["phien_ban_worker"])
    z = tc.get("/doi-social/may/ban-cap-nhat", headers=HA)
    check("bản cập nhật Worker: zip, không worker.json", z.status_code == 200 and b"minmin_worker.py" in z.content
          and b"worker.json" not in z.content)
    check("bản cập nhật cần token", tc.get("/doi-social/may/ban-cap-nhat").status_code == 401)
    dw = tc.post("/doi-social/dot-chay", json={"kich_ban": "fb_tra_loi_binh_luan", "nick": ["n1"],
                                              "tham_so": {"san_pham": str(sp["id"]), "che_do": "chay_thu"}}).json()
    check("tạo đợt qua HTTP", dw["ok"] and len(dw["dot"]["viec"]) == 1)
    vw = tc.get("/doi-social/may/viec?cho=0", headers=HA).json()["viec"]
    check("worker nhận việc đợt qua long-poll", vw and vw["dot_id"] == dw["dot"]["id"])
    vid = vw["id"]
    check("máy khác không hỏi dừng được việc này (403)", tc.get(f"/doi-social/may/dung/{vid}", headers=HB).status_code == 403)
    check("máy khác không gửi sự kiện được (403)",
          tc.post(f"/doi-social/may/su-kien/{vid}", headers=HB, json={"ket_qua": "loi"}).status_code == 403)
    check("máy khác không gọi AI cho việc này (403)",
          tc.post("/doi-social/may/ai", headers=HB, json={"viec_id": vid, "muc_dich": "cham_bai"}).status_code == 403)
    check("dừng = false khi đợt còn chạy", tc.get(f"/doi-social/may/dung/{vid}", headers=HA).json()["dung"] is False)
    r = tc.post(f"/doi-social/may/su-kien/{vid}", headers=HA, json={"hanh_dong": "tra_loi_binh_luan", "ket_qua": "thanh_cong"})
    check("sự kiện qua HTTP trả con_lai", r.status_code == 200 and "tra_loi_binh_luan" in r.json()["con_lai"])
    png = base64.b64encode(b"\xff\xd8anh").decode()
    r = tc.post("/doi-social/may/ai", headers=HA, json={
        "viec_id": vid, "muc_dich": "tra_loi_binh_luan", "anh": [png],
        "du_lieu": {"bai_cua_nick": True, "bai": {"chu": "x"}, "binh_luan": {"tac_gia": "Lan", "chu": "size?"}}})
    check("AI cho máy: ảnh tạm có lúc gọi, xoá sau, kèm kiến thức sản phẩm",
          r.status_code == 200 and goi[-1][2] == [True] and not any(Path(p).exists() for p in goi[-1][1])
          and goi[-1][3] == "Váy lụa", r.text)
    hd = v2.lay_kien_thuc(sp["id"])["hoi_dap"]
    check("can_hoi_chu -> Hỏi đáp chờ bạn", any(h["trang_thai"] == "cho_ban" and "XXL" in h["hoi"] for h in hd))
    check("AI ValueError -> 400 có câu lỗi",
          tc.post("/doi-social/may/ai", headers=HA, json={"viec_id": vid, "muc_dich": "cham_bai"}).json()["error"] == "AI trả rác")
    check("muc_dich lạ -> 400", tc.post("/doi-social/may/ai", headers=HA, json={"viec_id": vid, "muc_dich": "hack"}).status_code == 400)
    r = tc.post("/doi-social/may/hoi-thoai", headers=HA, json={"viec_id": vid, "khach_ten": "Lan", "khach_link": "https://m.me/lan",
                                                               "tin": [{"tu": "khach", "noi_dung": "còn hàng ko"}]})
    ht = r.json()
    check("hội thoại mới: bot được trả lời", ht["ok"] and ht["bot_duoc_tra_loi"] is True)
    tc.post("/doi-social/may/ai", headers=HA, json={"viec_id": vid, "muc_dich": "tra_loi_tin_nhan",
                                                     "du_lieu": {"hoi_thoai": {"khach_link": "https://m.me/lan", "tin": []}}})
    check("SĐT -> khách tiềm năng", tc.get("/doi-social/hoi-thoai?tab=tiem_nang").json()["dem"]["tiem_nang"] == 1)
    r = tc.post(f"/doi-social/hoi-thoai/{ht['id']}/tra-loi", json={"noi_dung": "Dạ còn ạ"}).json()
    check("chủ trả lời tay -> việc fb_gui_tin cho_chay, bot nhường",
          r["ok"] and r["viec"]["ky_nang"] == "fb_gui_tin" and r["viec"]["trang_thai"] == "cho_chay"
          and r["hoi_thoai"]["nhuong_den"] > time.time() + 11 * 3600)
    r = tc.post("/doi-social/may/hoi-thoai", headers=HA, json={"viec_id": vid, "khach_link": "https://m.me/lan",
                                                               "tin": [{"tu": "khach", "noi_dung": "ok"}]}).json()
    check("đang nhường thì bot không được trả lời", r["bot_duoc_tra_loi"] is False)
    r = tc.post(f"/doi-social/may/ket-qua/{vid}", headers=HA, json={"ok": True, "thong_diep": "xong",
                                                                   "dem": {"thanh_cong": 1}})
    check("kết quả việc đợt qua HTTP", r.status_code == 200 and ds.lay_viec(vid)["trang_thai"] == "xong")

    # multipart kho
    r = tc.post("/doi-social/kho", data={"nen_tang": "instagram", "nick": "", "noi_dung": "Ảnh mới"},
                files=[("tep", ("a.jpg", b"\xff\xd8" + b"x" * 100, "image/jpeg"))])
    check("tải bài lên kho (multipart)", r.status_code == 200 and r.json()["so"] == 1, r.text)
    bid = r.json()["ids"][0]
    check("xem trước tệp kho", tc.get(f"/doi-social/kho/tep/{bid}/00.jpg").content.startswith(b"\xff\xd8"))
    r = tc.post("/doi-social/kho", data={"nen_tang": "instagram"}, files=[("tep", ("x.exe", b"MZ", "application/x"))])
    check("kho chặn đuôi lạ qua HTTP", r.status_code == 400 and "chỉ nhận" in r.json()["error"])
    check("kho tóm tắt", tc.get("/doi-social/kho?nen_tang=instagram").json()["chung"]["con"] == 1)
    r = tc.post(f"/doi-social/kien-thuc/{sp['id']}/tai-lieu", files=[("tep", ("gia.txt", "Giá 459k".encode(), "text/plain"))])
    check("tài liệu .txt tải lên được", r.status_code == 200 and "Giá 459k" in
          v2.lay_kien_thuc(sp["id"])["tai_lieu"][0]["noi_dung"], r.text)
    r = tc.post(f"/doi-social/kien-thuc/{sp['id']}/tai-lieu", files=[("tep", ("x.exe", b"MZ", "application/x"))])
    check("tài liệu đuôi lạ bị chặn", r.status_code == 400)

    # tổng quan, danh mục, AI
    tq = tc.get("/doi-social/tong-quan").json()
    check("tổng quan: số 7 ngày, biểu đồ 14 ngày, ai từ deps",
          tq["ok"] and len(tq["bieu_do"]) == 14 and tq["ai"]["engine"] == "claude" and tq["so7"]["luot"] >= 1)
    check("tổng quan: cần xử lý có đường dẫn trang",
          all(x["den"].startswith("#/") for x in tq["can_xu_ly"]) and any(x["den"] == "#/kien-thuc" for x in tq["can_xu_ly"]))
    kbj = tc.get("/doi-social/kich-ban").json()
    ssm = {m["id"]: m["san_sang"] for m in kbj["mau"]}
    check("danh mục kèm san_sang theo máy", len(kbj["mau"]) == 41 and ssm["fb_nuoi_nick"] and not ssm["tt_nuoi_nick"])
    r = tc.post("/doi-social/viet-bai", json={"san_pham_id": sp["id"], "noi_dang": "fb_tuong", "so_ban": 2}).json()
    check("viết bài AI -> 2 nháp bài đăng", r["ok"] and len(r["muc"]) == 2 and r["muc"][0]["loai"] == "bai_dang")
    r = tc.post("/doi-social/tro-ly", json={"tin": "nuôi nick B giúp"}).json()
    check("trợ lý trả lời + lưu kế hoạch chờ duyệt (web không gửi Telegram)",
          r["ok"] and r["ke_hoach"]["trang_thai"] == "cho_duyet" and bao_kh == [] and r["phien"])
    ls = tc.get(f"/doi-social/tro-ly/lich-su?phien={r['phien']}").json()["muc"]
    check("lịch sử trợ lý có 2 lượt", [x["vai"] for x in ls] == ["nguoi", "ai"])
    kq = asyncio.run(rds.tro_ly_tra_loi("lên kế hoạch", nguon="telegram", chat_id="123"))
    check("trợ lý từ Telegram gửi kế hoạch kèm nút", bao_kh == [kq["ke_hoach"]["id"]])
    r = tc.post(f"/doi-social/ke-hoach/{r['ke_hoach']['id']}/duyet").json()
    check("duyệt kế hoạch qua HTTP", r["ok"] and r["ke_hoach"]["trang_thai"] == "dang_chay" and r["ke_hoach"]["dot_ids"])
    r = tc.post("/doi-social/dot-chay", json={"kich_ban": "fb_nuoi_nick", "nick": ["b1"], "tham_so": {},
                                              "che_do": "hen", "cron": "0 */2 * * *"}).json()
    check("chế độ hẹn tạo lịch", r["ok"] and r["lich"]["cron"] == "0 */2 * * *")
    check("lịch hẹn chạy ngay", tc.post(f"/doi-social/lich-hen/{r['lich']['id']}/chay").json()["dot"]["nguon"] == "lich")
    c = tc.get("/doi-social/su-kien.csv")
    check("CSV qua HTTP có BOM", c.status_code == 200 and c.content.startswith(b"\xef\xbb\xbf"))
    check("dòng thời gian phân trang", tc.get("/doi-social/su-kien?moi_trang=2").json()["tong"] >= 2)
    check("gioi-han-v2 GET", tc.get("/doi-social/gioi-han-v2").json()["mac_dinh"]["chung"]["viec_ngay_moi"] == 20)

    # đường tĩnh
    check("tĩnh: app.js phục vụ được", tc.get("/apps/doi-social/app.js").status_code == 200)
    check("tĩnh: chặn '..'", all(tc.get(u).status_code == 404 for u in (
        "/apps/doi-social/a..js", "/apps/doi-social/..%2Fworker%2Fminmin_worker.py",
        "/apps/doi-social/x/..%2F..%2Fserver.js", "/apps/doi-social/../worker/x.js",
        "/apps/doi-social/minmin_worker.py", "/apps/doi-social/.hidden.js")))
    giay_phep.da_mo = lambda app_id: False
    check("chưa mở khoá thì trang quản lý 403", tc.get("/doi-social/tong-quan").status_code == 403)
    giay_phep.da_mo = lambda app_id: app_id == "doi_social"
    time.sleep(0.2)
check("thông báo kho (đợt chạy xong) được gửi qua bao_su_kien", "Đợt chạy xong" in bao_sk, bao_sk)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
