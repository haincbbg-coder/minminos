"""Đội Social 26.10.192: nút Tạm dừng / Tiếp tục / Huỷ trên từng việc, và quét Trang / tài khoản để chọn
nơi đăng cho từng nick. KHÔNG mạng.
python tests/run.py doi_social_dieu_khien"""
import os, tempfile
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

ds.mo(Path(tempfile.mkdtemp()) / "kho")
A = ds.ghep(ds.tao_ma_ghep(), "PC A")
MA = A["may_id"]
ds.nhip(MA, [{"id": f"n{i}", "ten": f"Nick {i}", "trinh_duyet": "chrome"} for i in range(1, 4)],
        kich_ban=["fb_nuoi_nick", "fb_dang_tuong_kho", "quet_tai_khoan"], song_song=3)
v2.dat_gioi_han_v2({"chung": {"nghi_phut": [0, 0]}})

# ---- điều khiển từng việc
dot = v2.tao_dot(kich_ban="fb_nuoi_nick", nick=["n1", "n2", "n3"], tham_so={"phut": 3}, song_song=3)
v1, vv2, v3 = [v["id"] for v in dot["viec"]]
x = v2.dieu_khien_viec(v1, "tam_dung")
check("tạm dừng việc chưa chạy -> tam_dung", x["trang_thai"] == "tam_dung")
g = [ds.nhan_viec(MA), ds.nhan_viec(MA), ds.nhan_viec(MA)]
check("việc tạm dừng không được giao", v1 not in [y["id"] for y in g if y])
check("đợt chưa xong khi còn việc tạm dừng", v2.lay_dot(dot["id"], False)["tien_trinh"]["tam"] == 1)
x = v2.dieu_khien_viec(v1, "tiep_tuc")
check("tiếp tục -> về hàng chờ", x["trang_thai"] == "cho_chay")
check("việc đã tiếp tục được giao", ds.nhan_viec(MA)["id"] == v1)

check("đang chạy: lệnh rỗng", v2.lenh_viec(vv2) == {"dung": False, "tam_dung": False})
v2.dieu_khien_viec(vv2, "tam_dung")
check("tạm dừng việc đang chạy -> máy được báo tam_dung", v2.lenh_viec(vv2) == {"dung": False, "tam_dung": True}
      and ds.lay_viec(vv2)["trang_thai"] == "dang_chay")
v2.dieu_khien_viec(vv2, "tiep_tuc")
check("tiếp tục việc đang chạy -> hết tạm dừng", v2.lenh_viec(vv2)["tam_dung"] is False)
v2.dieu_khien_viec(vv2, "huy")
check("huỷ việc đang chạy -> máy được báo dừng", v2.lenh_viec(vv2)["dung"] is True)
r = ds.ghi_ket_qua(vv2, MA, True, "lướt 1 phút", [])
check("kết quả của việc đã huỷ ghi là bo + câu đã huỷ", r["trang_thai"] == "bo" and "đã huỷ" in r["thong_diep"])
check("huỷ việc đã kết thúc bị từ chối", raises(lambda: v2.dieu_khien_viec(vv2, "huy"), "kết thúc"))
check("hành động lạ bị từ chối", raises(lambda: v2.dieu_khien_viec(v1, "xoa"), "hành động"))
ds.ghi_ket_qua(v1, MA, True, "ok", [])
ds.ghi_ket_qua(v3, MA, True, "ok", [])
check("đợt hoàn tất khi mọi việc kết thúc", v2.lay_dot(dot["id"], False)["trang_thai"] == "hoan_tat")

dot2 = v2.tao_dot(kich_ban="fb_nuoi_nick", nick=["n1", "n2"], tham_so={"phut": 3})
v2.dieu_khien_dot(dot2["id"], "tam_dung")
check("tạm dừng cả đợt", all(v["trang_thai"] == "tam_dung" for v in v2.lay_dot(dot2["id"])["viec"]))
v2.huy_dot(dot2["id"])
check("huỷ đợt bỏ cả việc đang tạm dừng", all(v["trang_thai"] == "bo" for v in v2.lay_dot(dot2["id"])["viec"]))

# ---- quét Trang / tài khoản
q = v2.tao_quet_tai_khoan(["n1"], ["facebook", "instagram"])
check("tạo việc quét", len(q) == 1 and q[0]["ky_nang"] == "quet_tai_khoan" and q[0]["chay_thu"] == 1)
check("không tạo trùng việc quét khi còn chờ", v2.tao_quet_tai_khoan(["n1"]) == [])
gq = ds.nhan_viec(MA)
check("máy báo hỗ trợ quét thì được giao", gq and gq["id"] == q[0]["id"])
kq = v2.ghi_dich_den(gq["id"], MA, ["facebook", "instagram"], [
    {"nen_tang": "facebook", "loai": "trang", "ten": "Hằng Yên Store", "link": "https://www.facebook.com/profile.php?id=1"},
    {"nen_tang": "facebook", "loai": "trang", "ten": "Đồ Bộ Miệt Vườn", "link": "https://www.facebook.com/100088"},
    {"nen_tang": "instagram", "loai": "tai_khoan", "ten": "@halimi", "link": "https://www.instagram.com/halimi/"},
    {"nen_tang": "tiktok", "loai": "tai_khoan", "ten": "@x", "link": "https://www.tiktok.com/@x"},     # chưa quét -> bỏ
    {"nen_tang": "facebook", "ten": "rác", "link": "javascript:alert(1)"}])
check("ghi nơi đăng: chỉ nền tảng đã quét, bỏ link bẩn", kq["so"] == 3)
check("nhãn nền tảng tự gắn theo kết quả quét", set(kq["nhan"]) == {"facebook", "instagram"})
nk = [n for n in v2.ds_nick() if n["id"] == "n1"][0]
check("danh sách nick kèm nơi đăng + đang quét", len(nk["dich_den"]) == 3 and nk["nhan"] == kq["nhan"]
      and nk["dang_quet"] is True and nk["quet_luc"] is None)
ds.ghi_ket_qua(gq["id"], MA, True, "ok", [])
nk = [n for n in v2.ds_nick() if n["id"] == "n1"][0]
check("quét xong có thời điểm quét", nk["dang_quet"] is False and nk["quet_luc"])
q2 = v2.tao_quet_tai_khoan(["n1"], ["facebook"])
g2 = ds.nhan_viec(MA)
v2.ghi_dich_den(g2["id"], MA, ["facebook"], [{"nen_tang": "facebook", "loai": "trang", "ten": "Hằng Yên Store",
                                              "link": "https://www.facebook.com/profile.php?id=1"}])
d = v2.ds_dich_den("n1")
check("quét lại thay danh sách nền tảng đó (Trang mất quyền biến mất), giữ nền tảng khác",
      sorted(x["ten"] for x in d) == ["@halimi", "Hằng Yên Store"])

# ---- chọn nơi đăng theo từng nick khi tạo đợt
dot3 = v2.tao_dot(kich_ban="fb_dang_tuong_kho", nick=["n1", "n2"],
                  tham_so={"dang_len": {"n1": "https://www.facebook.com/profile.php?id=1"}, "kho": "chung"})
ts = {v["nick_id"]: v["tham_so"]["tham_so"]["dang_len"] for v in dot3["viec"]}
check("mỗi việc nhận đúng nơi đăng của nick mình ('' = tường)",
      ts == {"n1": "https://www.facebook.com/profile.php?id=1", "n2": ""})
check("nơi đăng không phải https bị từ chối",
      raises(lambda: v2.tao_dot(kich_ban="fb_dang_tuong_kho", nick=["n1"], tham_so={"dang_len": {"n1": "ftp://x"}}), "https"))

# ---- HTTP
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.doi_social as rds  # noqa: E402
rds.ly_do_chan = lambda: None
app = FastAPI()
rds.register(app, rds.DoiSocialDeps())
cl = TestClient(app)
v_tt = dot3["viec"][1]["id"]
r = cl.post(f"/doi-social/viec/{v_tt}/dieu-khien", json={"hanh_dong": "tam_dung"}).json()
check("POST viec/{id}/dieu-khien", r["ok"] and r["viec"]["trang_thai"] == "tam_dung")
check("dieu-khien sai -> lỗi", cl.post(f"/doi-social/viec/{v_tt}/dieu-khien", json={"hanh_dong": "x"}).json()["ok"] is False)
r = cl.post(f"/doi-social/dot-chay/{dot3['id']}/dieu-khien", json={"hanh_dong": "tiep_tuc"}).json()
check("POST dot-chay/{id}/dieu-khien", r["ok"] and ds.lay_viec(v_tt)["trang_thai"] == "cho_chay")
r = cl.get("/doi-social/dich-den", params={"nick": "n1"}).json()
check("GET dich-den", r["ok"] and len(r["muc"]) == 2)
r = cl.post("/doi-social/quet-tai-khoan", json={"nick": ["n2", "n3"]}).json()
check("POST quet-tai-khoan tạo việc cho từng nick", r["ok"] and r["so"] == 2)
tok = A["token"]
vq = r["muc"][0]["id"]
ds._db().execute("UPDATE viec SET trang_thai='dang_chay', bat_dau=? WHERE id=?", (ds._bay_gio(), vq))
h = {"x-minmin-may": tok}
r = cl.get(f"/doi-social/may/dung/{vq}", headers=h).json()
check("máy hỏi lệnh: có dung + tam_dung", r["ok"] and r["dung"] is False and r["tam_dung"] is False)
r = cl.post("/doi-social/may/dich-den", headers=h, json={"viec_id": vq, "nen_tang": ["tiktok"], "muc": [
    {"nen_tang": "tiktok", "loai": "tai_khoan", "ten": "@shop", "link": "https://www.tiktok.com/@shop"}]}).json()
check("máy gửi kết quả quét", r["ok"] and r["so"] == 1)
check("máy lạ không gửi được", cl.post("/doi-social/may/dich-den", headers={"x-minmin-may": "sai"},
                                         json={"viec_id": vq}).status_code in (401, 403))

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
