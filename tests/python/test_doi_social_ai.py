"""Đội Social - phần AI (doi_social_ai): bóc JSON chịu lỗi, cắt độ dài, giá trị an toàn, không bịa
giá, link chỉ ở trả lời con, kế hoạch trợ lý chỉ dùng mẫu/nick có thật. goi_ai là đồ giả.
python tests/python/test_doi_social_ai.py"""
import asyncio, json, os, sys, tempfile
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
from _paths import ROOT  # noqa: E402,F401

import doi_social_ai as ai  # noqa: E402

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


def gia(tra, ghi=None):
    """goi_ai giả: trả cố định `tra` (chuỗi hoặc dict -> JSON), ghi lại prompt + ảnh."""
    async def goi(prompt, anh):
        if ghi is not None:
            ghi.append((prompt, list(anh)))
        return tra if isinstance(tra, str) else json.dumps(tra, ensure_ascii=False)
    return goi


def chay(coro):
    return asyncio.run(coro)


KT = {"id": 1, "loai": "san_pham", "ten": "Váy lụa HALIMI", "mo_ta": "Váy lụa thiết kế, form suông",
      "gia": "450000", "link": "https://halimi.vn/vay-lua", "tu_khoa": "váy đi tiệc", "giong_van": "", "dan_rieng": "",
      "tai_lieu": [{"ten": "Bảng size", "noi_dung": "S M L, combo 2 váy 850k"}], "hoi_dap": [{"hoi": "Có ship COD?", "dap": "Có ạ"}]}
KT_KHONG_GIA = dict(KT, gia="", tai_lieu=[], hoi_dap=[])

# ---------------------------------------------------------------- bóc JSON
check("bóc JSON trong code fence", ai.boc_json('Đây ạ:\n```json\n{"a": 1}\n```') == {"a": 1})
check("bóc JSON có chữ thừa trước/sau", ai.boc_json('Kết quả là {"a": 2} nhé bố') == {"a": 2})
check("bóc JSON dấu phẩy thừa", ai.boc_json('{"a": [1, 2,],}') == {"a": [1, 2]})
check("bóc JSON có dấu } trong chuỗi", ai.boc_json('x {"t": "a } b", "n": 1} y') == {"t": "a } b", "n": 1})
check("rác -> None", ai.boc_json("không có json") is None and ai.boc_json("") is None and ai.boc_json(None) is None)
check("mảng trần không phải dict -> None", ai.boc_json("[1,2]") is None)

# ---------------------------------------------------------------- cham_bai
kq = chay(ai.xu_ly_may("cham_bai", {"bai": {"chu": "x"}}, [], goi_ai=gia("tôi không biết"), kien_thuc=KT))
check("chấm bài AI trả rác -> chon=false", kq["chon"] is False and kq["diem"] == 0, kq)
kq = chay(ai.xu_ly_may("cham_bai", {"bai": {"chu": "x"}}, [], goi_ai=gia({"diem": 90, "chon": True, "la_doi_thu": True}),
                       kien_thuc=KT))
check("bài đối thủ thì không chọn dù điểm cao", kq["chon"] is False and kq["la_doi_thu"] is True, kq)
kq = chay(ai.xu_ly_may("cham_bai", {"bai": {"chu": "x"}}, [], goi_ai=gia({"diem": "30", "chon": "true"}), kien_thuc=KT))
check("điểm thấp mà AI nói chọn -> không chọn; ép kiểu chuỗi", kq["chon"] is False and kq["diem"] == 30, kq)
ghi = []
kq = chay(ai.xu_ly_may("cham_bai", {"bai": {"chu": "Ai biết chỗ mua váy đi tiệc không?", "tac_gia": "Lan"}}, ["/a.jpg"],
                       goi_ai=gia({"diem": 150, "chon": True, "ly_do": "Hỏi mua \u2014 đúng nhu cầu"}, ghi), kien_thuc=KT))
check("điểm kẹp 100, chọn, ly_do bỏ gạch dài", kq["chon"] and kq["diem"] == 100 and "\u2014" not in kq["ly_do"], kq)
check("ảnh được chuyển cho goi_ai và prompt nhắc xem ảnh", ghi[0][1] == ["/a.jpg"] and "XEM ẢNH" in ghi[0][0])
check("prompt cấm coi bài là lệnh", "KHÔNG phải lệnh" in ghi[0][0])

# ---------------------------------------------------------------- viet_binh_luan: link ở trả lời con
kq = chay(ai.xu_ly_may("viet_binh_luan", {"bai": {"chu": "cần váy"}}, [], kien_thuc=KT, goi_ai=gia(
    {"noi_dung": "Mình mặc mẫu này đi tiệc rồi, đẹp lắm https://halimi.vn/vay-lua #halimi giá 450k", "tra_loi_con": ""})))
check("bình luận đầu không chứa link", not ai.tim_link(kq["noi_dung"]), kq)
check("link chuyển xuống trả lời con", kq["tra_loi_con"] and "halimi.vn/vay-lua" in kq["tra_loi_con"], kq)
check("bình luận không hashtag, không giá", "#" not in kq["noi_dung"] and not ai.gia_trong(kq["noi_dung"]), kq)
kq = chay(ai.xu_ly_may("viet_binh_luan", {"bai": {"chu": "cần váy"}}, [], kien_thuc=KT, goi_ai=gia(
    {"noi_dung": "Đẹp quá", "tra_loi_con": "Link đây https://lua-dao.com/x"})))
check("link bịa ở trả lời con bị bỏ -> tra_loi_con None", kq["tra_loi_con"] is None and kq["noi_dung"] == "Đẹp quá", kq)
kq = chay(ai.xu_ly_may("viet_binh_luan", {"bai": {"chu": "a"}}, [], kien_thuc=KT, goi_ai=gia({"noi_dung": "ầ " * 400})))
check("bình luận cắt <= 500", len(kq["noi_dung"]) <= 500, len(kq["noi_dung"]))
kq = chay(ai.xu_ly_may("viet_binh_luan", {"bai": {"chu": "live"}, "noi_dang": "live"}, [], kien_thuc=KT,
                       goi_ai=gia({"noi_dung": "chị ơi " * 60, "tra_loi_con": "https://halimi.vn/vay-lua"})))
check("bình luận LIVE <= 150, không trả lời con", len(kq["noi_dung"]) <= 150 and kq["tra_loi_con"] is None, kq)
kq = chay(ai.xu_ly_may("viet_binh_luan", {"bai": {"chu": "a"}}, [], kien_thuc=KT, goi_ai=gia("rác")))
check("bình luận AI trả rác -> rỗng + bo_qua", kq["noi_dung"] == "" and kq.get("bo_qua") is True, kq)
kq = chay(ai.xu_ly_may("viet_binh_luan", {"bai": {"chu": "a"}}, [], kien_thuc=KT,
                       goi_ai=gia({"noi_dung": "Hay quá 😍😍😍🔥🔥"})))
check("emoji không tràn lan (<= 1)", sum(1 for c in kq["noi_dung"] if ord(c) > 0x1F000) <= 1, kq)

# ---------------------------------------------------------------- tra_loi_binh_luan
kq = chay(ai.xu_ly_may("tra_loi_binh_luan", {"bai_cua_nick": True, "bai": {"chu": "váy"},
                                             "binh_luan": {"tac_gia": "Hoa", "chu": "giá bao nhiêu shop?"}},
                       [], kien_thuc=KT, goi_ai=gia({"noi_dung": "Dạ váy này 450k ạ.", "can_hoi_chu": False})))
check("hỏi giá công khai -> không nói giá, mời inbox", not ai.gia_trong(kq["noi_dung"]) and "nhắn tin" in kq["noi_dung"], kq)
kq = chay(ai.xu_ly_may("tra_loi_binh_luan", {"bai": {}, "binh_luan": {"chu": "vải có co giãn không?"}}, [], kien_thuc=KT,
                       goi_ai=gia({"noi_dung": "Bạn nhắn mình nhé", "can_hoi_chu": True, "cau_hoi": ""})))
check("câu chưa có thông tin -> can_hoi_chu + cau_hoi lấy từ bình luận",
      kq["can_hoi_chu"] and "co giãn" in (kq["cau_hoi"] or ""), kq)

# ---------------------------------------------------------------- tra_loi_tin_nhan: không bịa giá
ht = {"hoi_thoai": {"khach_ten": "Mai", "tin": [{"tu": "khach", "noi_dung": "váy này giá sao em?"}]}}
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", ht, [], kien_thuc=KT, goi_ai=gia({"noi_dung": "Dạ váy 450.000đ ạ", "can_tra_loi_tay": False})))
check("giá đúng hồ sơ thì giữ", "450.000" in kq["noi_dung"] and kq["can_tra_loi_tay"] is False, kq)
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", ht, [], kien_thuc=KT, goi_ai=gia({"noi_dung": "Dạ váy 399k thôi ạ"})))
check("giá bịa (không có trong hồ sơ) -> câu giữ khách + cần trả lời tay",
      kq["can_tra_loi_tay"] and not ai.gia_trong(kq["noi_dung"]), kq)
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", ht, [], kien_thuc=KT, goi_ai=gia({"noi_dung": "Combo 2 váy 850k ạ"})))
check("giá có trong tài liệu thì được nói", "850k" in kq["noi_dung"] and not kq["can_tra_loi_tay"], kq)
ghi = []
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", ht, [], kien_thuc=KT_KHONG_GIA, goi_ai=gia({"noi_dung": "Dạ 300k ạ"}, ghi)))
check("không có giá trong hồ sơ: prompt cấm giá", "CẤM nói bất kỳ con số giá" in ghi[0][0])
check("không có giá mà AI vẫn nói giá -> chặn", kq["can_tra_loi_tay"] and not ai.gia_trong(kq["noi_dung"]), kq)
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", {"hoi_thoai": {"tin": [{"tu": "khach", "noi_dung": "sđt em 0912 345 678"}]}},
                       [], kien_thuc=KT, goi_ai=gia({"noi_dung": "Dạ shop gọi lại ngay ạ"})))
check("số điện thoại khách đọc bằng mã", kq["sdt"] == "0912345678", kq)
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", {"hoi_thoai": {"tin": [{"tu": "khach", "noi_dung": "số em 0123 456 78"}]}},
                       [], kien_thuc=KT, goi_ai=gia({"noi_dung": "Dạ vâng"})))
check("số điện thoại sai -> cần trả lời tay", kq["can_tra_loi_tay"] and not kq["sdt"], kq)
kq = chay(ai.xu_ly_may("tra_loi_tin_nhan", ht, [], kien_thuc=KT, goi_ai=gia("lỗi rồi")))
check("tin nhắn AI trả rác -> giữ khách + tay", kq["can_tra_loi_tay"] and kq["noi_dung"] == ai.CAU_GIU_KHACH, kq)

# ---------------------------------------------------------------- câu hỏi nhóm, chọn nhóm
kq = chay(ai.xu_ly_may("tra_loi_cau_hoi_nhom", {"nhom": "Hội váy", "cau_hoi": ["Bạn ở đâu?", "Cho xin số điện thoại"]},
                       [], kien_thuc=KT, goi_ai=gia({"tra_loi": ["Hà Nội", "0912"], "bo_nhom": False})))
check("nhóm xin SĐT -> bỏ nhóm (mã chặn, không trông AI)", kq["bo_nhom"] is True, kq)
kq = chay(ai.xu_ly_may("tra_loi_cau_hoi_nhom", {"nhom": "Hội váy", "cau_hoi": ["Bạn ở đâu?", "Đồng ý nội quy?"]},
                       [], kien_thuc=KT, goi_ai=gia({"tra_loi": ["Mình ở Hà Nội"], "bo_nhom": "false"})))
check("đủ số câu trả lời theo số câu hỏi", len(kq["tra_loi"]) == 2 and kq["bo_nhom"] is False, kq)
kq = chay(ai.xu_ly_may("chon_nhom", {"ket_qua_tim": [{"ten": "A", "link": "https://facebook.com/groups/a"},
                                                    {"ten": "B", "link": "https://facebook.com/groups/b"}]},
                       [], kien_thuc=KT, goi_ai=gia({"chon": ["https://facebook.com/groups/a/", "https://facebook.com/groups/la"]})))
check("chọn nhóm chỉ giữ link có trong kết quả tìm", kq["chon"] == ["https://facebook.com/groups/a"], kq)

try:
    chay(ai.xu_ly_may("lam_bay", {}, [], goi_ai=gia("{}"), kien_thuc=None))
    check("mục đích lạ -> ValueError", False)
except ValueError:
    check("mục đích lạ -> ValueError", True)


async def hong(prompt, anh):
    raise RuntimeError("AI sập")
try:
    chay(ai.xu_ly_may("cham_bai", {"bai": {}}, [], goi_ai=hong, kien_thuc=KT))
    check("lỗi gọi AI được để nổi lên", False)
except RuntimeError:
    check("lỗi gọi AI được để nổi lên", True)

# ---------------------------------------------------------------- viết bài / viết lại
ds = chay(ai.viet_bai(KT, "fb_trang", 3, "", goi_ai=gia({"ban": ["Bài một \u2014 hay", "Bài một \u2014 hay", "x" * 5000]})))
check("viết bài: bỏ trùng, bỏ gạch dài, cắt <= 3000", len(ds) == 2 and "\u2014" not in ds[0] and len(ds[1]) <= 3000, ds)
ds = chay(ai.viet_bai(KT, "threads", 1, "", goi_ai=gia({"ban": ["a " * 600]})))
check("Threads cắt <= 500", len(ds[0]) <= 500)
ds = chay(ai.viet_bai(KT_KHONG_GIA, "fb_tuong", 1, "", goi_ai=gia({"ban": ["Váy mới về. Giá chỉ 299k thôi. Ghé nhé."]})))
check("bài không có giá trong hồ sơ -> gỡ câu có giá", not ai.gia_trong(ds[0]) and "Váy mới về" in ds[0], ds)
ds = chay(ai.viet_bai(KT, "fb_nhom", 1, "", goi_ai=gia({"ban": ["Chia sẻ váy đẹp https://halimi.vn/vay-lua #vay"]})))
check("bài trong nhóm không link, không hashtag", not ai.tim_link(ds[0]) and "#" not in ds[0], ds)
ds = chay(ai.viet_bai(KT, "fb_tuong", 1, "", goi_ai=gia("Hôm nay mình mặc chiếc váy lụa mới, nhẹ tênh mà lên dáng xinh lắm mọi người ơi.")))
check("AI quên JSON nhưng trả bài chữ thuần -> vẫn dùng", len(ds) == 1)
try:
    chay(ai.viet_bai(KT, "fb_tuong", 2, "", goi_ai=gia("{}")))
    check("viết bài rác -> ValueError", False)
except ValueError:
    check("viết bài rác -> ValueError", True)
s = chay(ai.viet_lai({"loai": "binh_luan", "noi_dang": "fb_nhom", "noi_dung": "cũ"}, KT, "ngắn hơn",
                     goi_ai=gia({"noi_dung": "Mới nè https://halimi.vn/vay-lua #a 450k"})))
check("viết lại bình luận: không link/hashtag/giá", not ai.tim_link(s) and "#" not in s and not ai.gia_trong(s), s)
try:
    chay(ai.viet_lai({"loai": "bai_dang", "noi_dung": "cũ"}, KT, "", goi_ai=gia("rác")))
    check("viết lại rác -> ValueError (giữ nháp cũ)", False)
except ValueError:
    check("viết lại rác -> ValueError (giữ nháp cũ)", True)

# ---------------------------------------------------------------- trợ lý
BC = {"mau": [{"id": "fb_dang_nhom_link", "ten": "Đăng bài vào nhóm theo link", "nen_tang": "facebook", "mo_ta": "",
               "tham_so": ["links", "nguon", "noi_dung", "so_nhom"], "san_sang": True},
              {"id": "fb_binh_luan_nhom_sp", "ten": "Bình luận nhóm", "nen_tang": "facebook", "mo_ta": "",
               "tham_so": ["san_pham", "so_bai_quet", "toi_da", "che_do"], "san_sang": True}],
      "nick": [{"id": 7, "ten": "Mai Anh", "nhan": ["facebook"]}, {"id": 8, "ten": "Lan", "nhan": ["facebook"]}],
      "kien_thuc": [{"id": 1, "ten": "Váy lụa", "loai": "san_pham"}],
      "tong_quan": {"hom_nay": 12, "so7": {"luot": 80, "loi": 2}}}
ghi = []
kq = chay(ai.tro_ly("hôm nay nick chạy thế nào", [], BC, goi_ai=gia({"tra_loi": "Hôm nay 12 lượt \u2014 ổn", "ke_hoach": None}, ghi)))
check("trợ lý thống kê: không kế hoạch, bỏ gạch dài", kq["ke_hoach"] is None and "\u2014" not in kq["tra_loi"], kq)
check("prompt trợ lý có tổng quan thật + cấm bịa", '"hom_nay": 12' in ghi[0][0] and "KHÔNG bịa" in ghi[0][0])
kh_ai = {"mo_ta": "Đăng bài Trang", "buoc": [
    {"kich_ban": "fb_dang_nhom_link", "nick": [7, "Lan", 99], "tham_so": {"links": ["https://facebook.com/doisong"],
                                                                         "nguon": "nhap", "noi_dung": "Bài hay", "la": 1}},
    {"kich_ban": "mau_bia", "nick": [7], "tham_so": {}},
    {"kich_ban": "fb_binh_luan_nhom_sp", "nick": [8], "tham_so": {"san_pham": "1", "che_do": "dang_luon"}},
    {"kich_ban": "fb_binh_luan_nhom_sp", "nick": [42], "tham_so": {"san_pham": "1"}}]}
kq = chay(ai.tro_ly("đăng bài thu hút lên fanpage đời sống", [], BC, goi_ai=gia({"tra_loi": "Đã lên kế hoạch", "ke_hoach": kh_ai})))
kh = kq["ke_hoach"]
check("kế hoạch: bỏ mẫu lạ và bước không có nick hợp lệ", kh and len(kh["buoc"]) == 2, kh)
check("kế hoạch: nick theo tên được đổi ra id, nick lạ bị bỏ", kh["buoc"][0]["nick"] == [7, 8], kh)
check("kế hoạch: khoá tham số lạ bị bỏ, nội dung giữ", "la" not in kh["buoc"][0]["tham_so"]
      and kh["buoc"][0]["tham_so"]["noi_dung"] == "Bài hay", kh)
check("kế hoạch: dang_luon khi chủ không dặn -> duyet_truoc", kh["buoc"][1]["tham_so"]["che_do"] == "duyet_truoc", kh)
check("trả lời nêu phần bị bỏ", "không hợp lệ" in kq["tra_loi"], kq["tra_loi"])
kq = chay(ai.tro_ly("bình luận nhóm váy", [], BC, goi_ai=gia({"tra_loi": "ok", "ke_hoach": {"buoc": [
    {"kich_ban": "fb_binh_luan_nhom_sp", "nick": [7], "tham_so": {"san_pham": "1"}}]}})))
check("mẫu AI không ghi chế độ -> chay_thu", kq["ke_hoach"]["buoc"][0]["tham_so"]["che_do"] == "chay_thu", kq)
kq = chay(ai.tro_ly("x", [], BC, goi_ai=gia({"tra_loi": "", "ke_hoach": {"buoc": [{"kich_ban": "mau_bia", "nick": [1]}]}})))
check("kế hoạch toàn bước sai -> None", kq["ke_hoach"] is None and kq["tra_loi"], kq)
kq = chay(ai.tro_ly("x", [{"vai": "nguoi", "noi_dung": "chào"}], BC, goi_ai=gia("Chào bố, con nghe đây.")))
check("trợ lý AI trả chữ thuần -> dùng làm câu trả lời", kq["tra_loi"].startswith("Chào") and kq["ke_hoach"] is None, kq)

# ---------------------------------------------------------------- plugin doi-social 1.2.0 (kho + routes giả)
import importlib.util, types  # noqa: E402

goi_dot, goi_tro_ly = [], []
f_rds = types.ModuleType("routes.doi_social")
f_rds.ly_do_chan = lambda: None


async def _tro_ly_tra_loi(tin, phien, nguon="web", chat_id=""):
    goi_tro_ly.append((tin, phien, nguon, chat_id))
    return {"phien": phien, "tra_loi": "Mình đã lên kế hoạch.",
            "ke_hoach": {"id": 41, "buoc": [{"kich_ban": "fb_nuoi_nick", "nick": [7]}]}}


def _tao_dot_va_chay(**kw):
    goi_dot.append(kw)
    return {"id": 5, "ten": kw.get("ten") or ""}


f_rds.tro_ly_tra_loi = _tro_ly_tra_loi
f_rds.tao_dot_va_chay = _tao_dot_va_chay
f_ds = types.ModuleType("doi_social")
NICK = [{"id": 7, "ten": "Mai Anh", "may_id": 1}, {"id": 8, "ten": "Mai Anh 2", "may_id": 1}]
f_ds.ds_nick = lambda: NICK
f_ds.tim_nick = lambda t: [n for n in NICK if t.lower() in n["ten"].lower()]
f_ds.ds_may = lambda: [{"id": 1, "ten": "Nhà", "online": True}]
f_v2 = types.ModuleType("doi_social_v2")
f_v2.tong_quan = lambda ngay=14: {"nick_tong": 2, "nen_tang_dung": ["facebook"], "may": [{"ten": "Nhà", "online": True}],
                                  "ai": {"engine": "Claude Code", "mo_hinh": "opus", "nhin_anh": True, "san_sang": True},
                                  "so7": {"luot": 80, "thanh_cong": 78, "loi": 2, "dang_chay": 0, "ty_le": 97},
                                  "hom_nay": 12, "can_xu_ly": [{"tieu_de": "Nick Lan bị đăng xuất"}]}
import routes as _routes_pkg  # noqa: E402
_cu = {k: sys.modules.get(k) for k in ("routes.doi_social", "doi_social", "doi_social_v2")}
sys.modules.update({"routes.doi_social": f_rds, "doi_social": f_ds, "doi_social_v2": f_v2})
_rds_cu = getattr(_routes_pkg, "doi_social", None)
_routes_pkg.doi_social = f_rds
spec = importlib.util.spec_from_file_location("_pl_doi_social", ROOT / "system" / "plugins" / "doi-social" / "plugin.py")
pl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pl)


class Ctx:
    vault_root = None
    slug = "doi-social"
    tools = []

    def register_tool(self, **kw):
        self.tools.append(kw)


c = Ctx()
pl.register(c)
ten_tool = [t["name"] for t in c.tools]
check("plugin giữ tool cũ + thêm 3 tool mới", all(x in ten_tool for x in (
    "social_nick", "social_tao_bai_fb", "social_viec", "up_bai_chay", "up_bai_trang_thai",
    "social_tong_quan", "social_ke_hoach", "social_chay_mau")), ten_tool)
mm = {t["name"]: t["min_mode"] for t in c.tools}
check("min_mode: tổng quan readonly, kế hoạch/chạy mẫu full",
      mm["social_tong_quan"] == "readonly" and mm["social_ke_hoach"] == "full" and mm["social_chay_mau"] == "full")
s = pl._tong_quan({}, c)
check("social_tong_quan tóm tắt số thật", "80 lượt" in s and "Hôm nay: 12" in s and "đăng xuất" in s, s)
s = chay(pl._ke_hoach({"yeu_cau": "đăng bài lên fanpage đời sống", "chat_id": "123"}, c))
check("social_ke_hoach gửi Telegram, không tự chạy", goi_tro_ly[-1][2] == "telegram" and goi_tro_ly[-1][3] == "123"
      and "#41" in s and "bấm Duyệt" in s and not goi_dot, s)
s = chay(pl._chay_mau({"kich_ban": "fb_binh_luan_nhom_sp", "nick": ["7"], "tham_so": {"san_pham": "1"}}, c))
check("social_chay_mau: mẫu AI mặc định chạy thử", goi_dot and goi_dot[-1]["tham_so"]["che_do"] == "chay_thu"
      and goi_dot[-1]["nick"] == [7] and "#5" in s, s)
VIEC = {9: {"id": 9, "nhan_ky_nang": "Đăng bài", "nick_ten": "Mai", "trang_thai": "loi", "thong_diep": "không đăng được",
            "buoc": ["Mở profile", "Chẩn đoán trang: 1 dấu hiệu lỗi gần nhất", "  HTTP 500: POST https://x/api"]},
        10: {"id": 10, "nhan_ky_nang": "Đăng bài", "nick_ten": "Mai", "trang_thai": "xong", "thong_diep": "ok",
             "buoc": ["Mở profile"]}}
f_ds.lay_viec = lambda i: VIEC.get(i)
s = pl._viec({"id": 9}, c)
check("social_viec theo id, việc lỗi -> kèm nhật ký có chẩn đoán", "HTTP 500" in s and "Chẩn đoán trang" in s, s)
s = pl._viec({"id": 10}, c)
check("social_viec theo id, việc xong -> không dài dòng nhật ký", "Mở profile" not in s, s)
n = len(goi_dot)
s = chay(pl._chay_mau({"kich_ban": "fb_nuoi_nick", "nick": "Mai"}, c))
check("social_chay_mau: tên khớp nhiều nick -> hỏi lại, không chạy", len(goi_dot) == n and "khớp 2 nick" in s, s)
s = chay(pl._chay_mau({"kich_ban": "mau_bia", "nick": ["7"]}, c))
check("social_chay_mau: mẫu lạ bị từ chối", len(goi_dot) == n and "Không có mẫu" in s, s)
for k, v in _cu.items():
    if v is None:
        sys.modules.pop(k, None)
    else:
        sys.modules[k] = v
if _rds_cu is not None:
    _routes_pkg.doi_social = _rds_cu

# ---------------------------------------------------------------- không có em dash trong mã nguồn
for f in ("server/doi_social_ai.py", "system/plugins/doi-social/plugin.py", "system/plugins/doi-social/plugin.yaml",
          "tests/python/test_doi_social_ai.py"):
    src = (ROOT / f).read_text(encoding="utf-8")
    check(f"không có em dash: {f}", chr(0x2014) not in src)

# YouTube: tiêu đề dòng đầu <= 100, mô tả tới 5000 (vượt trần chung 3000)
check("YouTube: trần bài 5000, có gợi ý tiêu đề + mô tả",
      ai.tran_bai("youtube") == 5000 and ai.tran_bai("x") == 280 and "TIÊU ĐỀ" in ai.NOI_DANG_GOI_Y["youtube"]
      and "youtube" in ai.NOI_DANG_TEN)
_yt = ai._lam_sach_bai("# Tiêu đề: " + "Kem dưỡng <ẩm> " * 12 + "\nMô tả đầu.\n" + "Chi tiết. " * 450, "youtube", None)
check("YouTube: làm sạch tiêu đề (bỏ '#', 'Tiêu đề:', '< >', <= 100) và giữ mô tả dài",
      len(_yt.split("\n")[0]) <= 100 and _yt.startswith("Kem dưỡng ẩm") and "<" not in _yt
      and _yt.split("\n")[1] == "" and 3000 < len(_yt) <= 5000, (_yt[:120], len(_yt)))

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
