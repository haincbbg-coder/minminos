"""doi_social_kich_ban.py - danh mục mẫu tự động (kịch bản) của Đội Social (26.10.187).

Một NGUỒN SỰ THẬT DUY NHẤT cho cả ba phía:
  - máy chủ: kiểm tham số khi tạo đợt chạy, đếm giới hạn theo `hanh_dong`;
  - trang web: vẽ thẻ mẫu, form tham số riêng của từng mẫu (GET /doi-social/kich-ban);
  - Worker: `id` mẫu chính là `ky_nang` của việc gửi xuống máy nhà.

Mẫu "sẵn sàng" hay "đang phát triển" KHÔNG ghi cứng ở đây: Worker báo trong nhịp danh sách mẫu nó
làm được (`kich_ban`), máy chủ ghép lại. Mẫu chưa máy nào làm được thì trang hiện nhãn trung thực
"Máy ở nhà chưa hỗ trợ" thay vì giả vờ chạy.

Kiểu tham số (`kieu`):
  so          số nguyên, có min/max
  chu         một dòng chữ
  doan        nhiều dòng chữ
  ds_link     nhiều link, mỗi dòng một link (https://)
  chon        chọn một trong `lua_chon` [(gia_tri, nhan)]
  bat         bật/tắt
  san_pham    chọn một mục trong Kiến thức cho Agent (`loai` = san_pham | chu_de | ca_hai)
  kho         nguồn kho nội dung: "chung" (dùng chung) | "theo_nick" (thư mục riêng từng nick)

Chế độ nội dung AI (`che_do`, có ở mọi mẫu AI tự viết chữ):
  chay_thu     chỉ đọc + viết nháp vào Duyệt nội dung, KHÔNG đăng gì (mặc định)
  duyet_truoc  AI viết nháp, chủ bấm Duyệt thì máy mới đăng
  dang_luon    AI viết xong đăng ngay (chủ tự chọn, chịu trách nhiệm)

Thuần dữ liệu, không import gì của MinMin.
"""
from __future__ import annotations

NEN_TANG = [
    ("facebook", "Facebook"), ("tiktok", "TikTok"), ("youtube", "YouTube"), ("threads", "Threads"),
    ("instagram", "Instagram"), ("x", "X"), ("reddit", "Reddit"),
]
NHOM = [("dang_bai", "Đăng bài"), ("tuong_tac", "Tương tác"), ("ket_ban", "Kết bạn & nhắn tin")]

# Hành động được đếm vào giới hạn ngày của nick (khoá dùng chung máy chủ <-> Worker).
HANH_DONG = {
    "dang_tuong": "Đăng tường", "dang_nhom": "Đăng bài nhóm", "dang_trang": "Đăng lên Trang",
    "dang_video": "Đăng video", "vao_nhom": "Vào nhóm", "binh_luan_nhom": "Bình luận trong nhóm",
    "tra_loi_binh_luan": "Trả lời bình luận", "binh_luan": "Bình luận seeding",
    "thich": "Thích / thả tim", "chia_se": "Chia sẻ / đăng lại", "luu": "Lưu",
    "theo_doi": "Theo dõi", "nhan_tin": "Nhắn tin", "tra_loi_tin_nhan": "Trả lời tin nhắn",
    "binh_luan_live": "Bình luận LIVE", "quan_ly_bai": "Ghim / xoá bài", "quet": "Quét dữ liệu",
}

CHE_DO = {"key": "che_do", "nhan": "Chế độ", "kieu": "chon", "mac_dinh": "chay_thu",
          "lua_chon": [["chay_thu", "Chạy thử (chỉ viết nháp, không đăng)"],
                       ["duyet_truoc", "Duyệt trước (nháp vào Duyệt nội dung)"],
                       ["dang_luon", "Đăng luôn"]]}


def _sp(bat_buoc=True, loai="san_pham"):
    return {"key": "san_pham", "nhan": "Sản phẩm / chủ đề (Kiến thức cho Agent)", "kieu": "san_pham",
            "loai": loai, "bat_buoc": bat_buoc}


def _so(key, nhan, mac, lo=1, hi=50, goi_y=""):
    return {"key": key, "nhan": nhan, "kieu": "so", "mac_dinh": mac, "min": lo, "max": hi, "goi_y": goi_y}


def _links(key="links", nhan="Danh sách link (mỗi dòng một link)", bat_buoc=True):
    return {"key": key, "nhan": nhan, "kieu": "ds_link", "bat_buoc": bat_buoc}


def _doan(key, nhan, goi_y="", bat_buoc=False):
    return {"key": key, "nhan": nhan, "kieu": "doan", "goi_y": goi_y, "bat_buoc": bat_buoc}


def _bat(key, nhan, mac=True):
    return {"key": key, "nhan": nhan, "kieu": "bat", "mac_dinh": mac}


KHO = {"key": "kho", "nhan": "Lấy bài từ kho", "kieu": "kho", "mac_dinh": "chung",
       "lua_chon": [["chung", "Kho dùng chung (mỗi bài một nick)"], ["theo_nick", "Kho riêng của từng nick"]]}
PHUT_NUOI = _so("phut", "Lướt bao nhiêu phút", 10, 3, 60)


def _m(id, nen_tang, nhom, ten, mo_ta, chi_tiet, hanh_dong, tham_so, tinh_nang, ai=False):
    return {"id": id, "nen_tang": nen_tang, "nhom": nhom, "ten": ten, "mo_ta": mo_ta,
            "chi_tiet": chi_tiet, "hanh_dong": hanh_dong, "tham_so": tham_so,
            "tinh_nang": tinh_nang, "ai": ai}


MAU = [
    # ------------------------------------------------------------------ FACEBOOK (13)
    _m("fb_dang_nhom_ai", "facebook", "dang_bai", "Đăng bài AI vào nhóm theo sản phẩm",
       "Đăng các bài AI đã viết và bạn đã duyệt vào đúng nhóm của sản phẩm.",
       "Lấy bài 'Bài đăng · Nhóm FB' đã duyệt của sản phẩm trong Duyệt nội dung. Mỗi nick đăng vào nhóm "
       "mà nó đã tham gia trong Kho group FB. Mỗi nhóm nhận tối đa số bài đặt trong 7 ngày. Nhóm cần duyệt "
       "bài thì ghi 'chờ quản trị viên duyệt', không đăng lại.",
       ["dang_nhom"], [_sp(), _so("so_bai", "Số bài mỗi nick", 1, 1, 5), _so("moi_nhom_7_ngay", "Mỗi nhóm tối đa bài / 7 ngày", 1, 1, 7)],
       "Đăng bài"),
    _m("fb_dang_tuong_kho", "facebook", "dang_bai", "Đăng status lên tường từ kho",
       "Đăng bài trong Kho nội dung (chữ + ảnh/video) lên tường cá nhân của nick.",
       "Mỗi lượt lấy bài kế tiếp trong kho. Đăng xong chuyển bài sang 'Đã đăng'. Lỗi trước khi bấm Đăng thì "
       "trả bài về hàng chờ; lỗi sau khi đã bấm Đăng thì để ở 'Lỗi', không tự đăng lại. Kho hết bài thì báo "
       "'Hết bài' (vàng), không tính là lỗi.",
       ["dang_tuong"], [KHO, _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("fb_dang_nhom_link", "facebook", "dang_bai", "Đăng bài vào nhóm theo link",
       "Dán link các nhóm, nick đăng cùng một nội dung (hoặc lấy từ kho) vào từng nhóm.",
       "Nick chưa vào nhóm thì bỏ qua nhóm đó (ghi 'chưa tham gia'). Giữa hai nhóm nghỉ ngẫu nhiên theo giới "
       "hạn nick. Nhóm duyệt bài thì ghi 'chờ duyệt'.",
       ["dang_nhom"], [_links("links", "Link nhóm (mỗi dòng một nhóm)"),
                       {"key": "nguon", "nhan": "Nội dung", "kieu": "chon", "mac_dinh": "nhap",
                        "lua_chon": [["nhap", "Nhập ở dưới"], ["kho", "Lấy từ kho dùng chung"]]},
                       _doan("noi_dung", "Nội dung bài (khi chọn Nhập ở dưới)"),
                       _so("so_nhom", "Tối đa số nhóm mỗi nick", 3, 1, 20)], "Đăng bài"),
    _m("fb_dang_tuong_ai", "facebook", "dang_bai", "Đăng bài AI đã duyệt lên tường",
       "Đăng các bài AI viết cho tường cá nhân mà bạn đã duyệt.",
       "Lấy bài 'Bài đăng · Tường' đã duyệt (của nick đó hoặc chưa gán nick). Đọc lại tường thấy bài mới tính "
       "là thành công.",
       ["dang_tuong"], [_sp(False), _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("fb_tuong_tac_link", "facebook", "tuong_tac", "Tương tác bài theo link",
       "Mở từng link bài viết: thả cảm xúc, bình luận, chia sẻ như người thật.",
       "Bình luận lấy ngẫu nhiên từ danh sách bạn nhập (mỗi dòng một câu) hoặc để AI viết theo bài. Mỗi nick "
       "chỉ tương tác một lần trên một bài. Chỉ tính thành công khi đọc lại thấy cảm xúc/bình luận đã hiện.",
       ["thich", "binh_luan", "chia_se"],
       [_links("links", "Link bài viết"),
        {"key": "cam_xuc", "nhan": "Cảm xúc", "kieu": "chon", "mac_dinh": "thich",
         "lua_chon": [["khong", "Không thả"], ["thich", "Thích"], ["yeu_thich", "Yêu thích"], ["thuong_thuong", "Thương thương"],
                      ["haha", "Haha"], ["wow", "Wow"], ["ngau_nhien", "Ngẫu nhiên"]]},
        _bat("binh_luan", "Bình luận", False), _doan("cau_binh_luan", "Câu bình luận (mỗi dòng một câu; để trống = AI viết)"),
        _bat("chia_se", "Chia sẻ lên tường", False)], "Bình luận tương tác"),
    _m("fb_nuoi_nick", "facebook", "tuong_tac", "Nuôi nick (lướt bảng tin)",
       "Lướt bảng tin, xem video, thỉnh thoảng thả thích để nick trông như người dùng thật.",
       "Không bình luận, không kết bạn, không chia sẻ. Lượt thích có trần theo tuổi nick, tăng dần mỗi tuần "
       "(giới hạn nick). Chỉ đếm một lượt thích khi nút đã chuyển sang trạng thái đã thích.",
       ["thich"], [PHUT_NUOI], "Nuôi nick"),
    _m("fb_binh_luan_nhom_sp", "facebook", "tuong_tac", "Bình luận nhóm theo sản phẩm",
       "Quét bài mới trong nhóm của sản phẩm, AI chọn bài có người đang cần rồi viết bình luận.",
       "Mỗi nhóm có một nick phụ trách (Kho group FB). AI đọc chữ và ảnh của bài, chấm mức đúng nhu cầu, bỏ bài "
       "đối thủ và bài đã có nick khác trong đội bình luận. Link (nếu có) để ở trả lời con, không để ở bình luận "
       "đầu. Chạy thử = chỉ tạo nháp kèm 'Vì sao AI chọn'.",
       ["binh_luan_nhom"], [_sp(), _so("so_bai_quet", "Quét bao nhiêu bài mỗi nhóm", 15, 5, 50),
                            _so("toi_da", "Tối đa bình luận mỗi nick", 3, 1, 20), CHE_DO], "Bình luận group", ai=True),
    _m("fb_binh_luan_nhom_link", "facebook", "tuong_tac", "Bình luận nhóm theo link",
       "Dán link nhóm, AI quét bài mới và bình luận vào bài đúng nhu cầu sản phẩm.",
       "Giống mẫu theo sản phẩm nhưng nhóm do bạn dán. Nick chưa vào nhóm thì bấm Tham gia và ghi lại trạng thái.",
       ["binh_luan_nhom", "vao_nhom"], [_links("links", "Link nhóm"), _sp(), _so("toi_da", "Tối đa bình luận mỗi nick", 3, 1, 20),
                                        _bat("tu_tham_gia", "Tự tham gia nếu chưa vào", True), CHE_DO], "Bình luận group", ai=True),
    _m("fb_tra_loi_binh_luan", "facebook", "tuong_tac", "Tự trả lời bình luận",
       "Đọc thông báo, trả lời bình luận trên bài của nick và chỗ nick được nhắc tên.",
       "Bài của nick: trả lời mọi bình luận chưa có trả lời. Bài người khác: chỉ trả lời khi được nhắc. Câu hỏi "
       "chưa có trong Kiến thức thì mời nhắn tin và ghi vào Hỏi đáp chờ bạn trả lời. Không nói giá công khai nếu "
       "hồ sơ sản phẩm dặn vậy.",
       ["tra_loi_binh_luan"], [_sp(False, "ca_hai"), _so("so_thong_bao", "Đọc bao nhiêu thông báo", 20, 5, 60), CHE_DO],
       "Trả lời comment", ai=True),
    _m("fb_tra_loi_tin_nhan", "facebook", "tuong_tac", "Tự trả lời tin nhắn Messenger",
       "Đọc hộp thư, trả lời khách theo đúng giá và thông tin sản phẩm.",
       "Khách chờ lâu nhất được trả lời trước. Câu khó, khiếu nại, đặt hàng hoặc số điện thoại sai thì gửi câu "
       "giữ khách và báo bạn 'cần trả lời tay'. Có số điện thoại thì đưa vào Khách tiềm năng. Bạn tự trả lời thì "
       "bot nhường hội thoại đó 12 giờ. Bỏ qua nhóm chat, không đụng mã PIN tin nhắn mã hoá.",
       ["tra_loi_tin_nhan"], [_sp(False, "ca_hai"), _so("so_hoi_thoai", "Tối đa hội thoại mỗi lượt", 10, 1, 40), CHE_DO],
       "Nhắn tin Messenger", ai=True),
    _m("fb_tuong_tac_bai_app", "facebook", "tuong_tac", "Tương tác bài đội đã đăng trong nhóm",
       "Các nick khác vào thích và bình luận tự nhiên dưới bài đội vừa đăng trong nhóm.",
       "Tối đa 3 nick mỗi bài, rải trong 2-6 giờ sau khi đăng, không dùng nick đã đăng bài. Mỗi nick một kiểu "
       "câu, không chèn link, không review lố.",
       ["thich", "binh_luan"], [_so("so_bai", "Số bài mỗi nick", 3, 1, 10), CHE_DO], "Bình luận tương tác", ai=True),
    _m("fb_nhan_tin_ds", "facebook", "ket_ban", "Nhắn tin theo danh sách",
       "Gửi tin nhắn tới danh sách người nhận (UID, username hoặc link trang cá nhân).",
       "Nhớ ai đã được nhắn để không nhắn lại, chia đều người nhận cho các nick. Một người nhận lỗi 3 lần thì bỏ.",
       ["nhan_tin"], [_doan("nguoi_nhan", "Người nhận (mỗi dòng một UID / username / link)", bat_buoc=True),
                      _doan("noi_dung", "Nội dung (mỗi dòng một mẫu, chọn ngẫu nhiên)", bat_buoc=True),
                      _so("moi_nick", "Tối đa người mỗi nick", 10, 1, 50)], "Nhắn tin Messenger"),
    _m("fb_tham_gia_nhom_sp", "facebook", "ket_ban", "Tham gia nhóm theo sản phẩm",
       "Tìm và xin vào nhóm hợp sản phẩm; AI trả lời câu hỏi duyệt thành viên.",
       "Mỗi nhóm: 1 nick chính + tối đa 3 nick tương tác. Câu hỏi đòi số điện thoại/email thì bỏ nhóm. Chờ "
       "duyệt thì xem lại sau 12 giờ, quá 7 ngày đổi nick khác. Trần vào nhóm theo tuổi nick.",
       ["vao_nhom"], [_sp(), _so("so_nhom", "Số nhóm mỗi nick", 2, 1, 6), _bat("tu_tim", "Tự tìm nhóm theo từ khoá sản phẩm", True)],
       "Tham gia group", ai=True),

    # ------------------------------------------------------------------ TIKTOK (5)
    _m("tt_dang_video_kho", "tiktok", "dang_bai", "Đăng video TikTok từ kho",
       "Tải video trong kho lên TikTok Studio kèm mô tả, đặt công khai.",
       "Xử lý hộp kiểm tra nội dung. Chỉ báo thành công khi trang rời khỏi màn tải lên. Gặp captcha thì dừng nick.",
       ["dang_video"], [KHO, _so("so_bai", "Số video mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("tt_tuong_tac_video", "tiktok", "tuong_tac", "Tương tác video TikTok theo link",
       "Thả tim, bình luận, lưu video theo danh sách link.",
       "Captcha, đăng xuất hoặc 'quá nhanh' thì dừng ngay. Không thành công lượt nào thì báo thất bại.",
       ["thich", "binh_luan", "luu"], [_links("links", "Link video"), _bat("thich", "Thả tim"),
                                        _doan("cau_binh_luan", "Câu bình luận (mỗi dòng một câu; trống = không bình luận)"),
                                        _bat("luu", "Lưu video", False)], "Bình luận tương tác"),
    _m("tt_binh_luan_live", "tiktok", "tuong_tac", "Bình luận phiên LIVE",
       "Nhiều nick vào LIVE và bình luận xen kẽ từ danh sách câu bạn soạn.",
       "Câu được trộn riêng cho từng nick, giãn cách ngẫu nhiên, tối đa 150 ký tự mỗi câu.",
       ["binh_luan_live"], [_links("links", "Link phiên LIVE"), _doan("cau_binh_luan", "Câu bình luận (mỗi dòng một câu)", bat_buoc=True),
                            _so("so_cau", "Số câu mỗi nick", 5, 1, 50), _so("gian_cach", "Giãn cách (giây)", 40, 10, 600)],
       "Bình luận tương tác"),
    _m("tt_nuoi_nick", "tiktok", "tuong_tac", "Nuôi nick TikTok",
       "Lướt Dành cho bạn, xem mỗi video 5-20 giây, thỉnh thoảng thả tim.", "Trần thả tim tăng dần theo tuần.",
       ["thich"], [PHUT_NUOI], "Nuôi nick"),
    _m("tt_tra_loi_binh_luan", "tiktok", "tuong_tac", "Tự trả lời bình luận TikTok",
       "Trả lời bình luận dưới video mới của nick theo sản phẩm nhận ra từ mô tả.", "",
       ["tra_loi_binh_luan"], [_sp(False, "ca_hai"), _so("so_video", "Số video gần nhất", 3, 1, 10), CHE_DO],
       "Trả lời comment", ai=True),

    # ------------------------------------------------------------------ YOUTUBE (1)
    _m("yt_dang_video_kho", "youtube", "dang_bai", "Đăng video YouTube từ kho",
       "Tải video lên YouTube Studio với tiêu đề, mô tả, chế độ công khai.",
       "Tiêu đề tối đa 100 ký tự. Bị đẩy sang trang đăng nhập Google thì báo lỗi đăng xuất.",
       ["dang_video"], [KHO, {"key": "che_do_hien", "nhan": "Hiển thị", "kieu": "chon", "mac_dinh": "cong_khai",
                              "lua_chon": [["cong_khai", "Công khai"], ["khong_cong_khai", "Không công khai"], ["rieng_tu", "Riêng tư"]]}],
       "Đăng bài"),

    # ------------------------------------------------------------------ THREADS (7)
    _m("th_dang_kho", "threads", "dang_bai", "Đăng Threads từ kho",
       "Đăng bài trong kho lên Threads; dòng '---' tách thành chuỗi bài.",
       "Mỗi phần tối đa 500 ký tự, tối đa 20 ảnh.", ["dang_tuong"], [KHO, _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("th_dang_ai", "threads", "dang_bai", "Đăng bài AI đã duyệt lên Threads", "Đăng các bài Threads AI viết đã được duyệt.", "",
       ["dang_tuong"], [_sp(False), _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("th_tuong_tac", "threads", "tuong_tac", "Tương tác Threads theo link", "Thích, trả lời, đăng lại bài theo link.", "",
       ["thich", "binh_luan", "chia_se"], [_links("links", "Link bài"), _bat("thich", "Thích"),
                                           _doan("cau_binh_luan", "Câu trả lời (mỗi dòng một câu)"), _bat("dang_lai", "Đăng lại", False)],
       "Bình luận tương tác"),
    _m("th_nuoi_nick", "threads", "tuong_tac", "Nuôi nick Threads", "Lướt mục Dành cho bạn và thỉnh thoảng thích.", "",
       ["thich"], [PHUT_NUOI], "Nuôi nick"),
    _m("th_tra_loi_binh_luan", "threads", "tuong_tac", "Tự trả lời bình luận Threads", "Trả lời trả lời mới dưới bài của nick.", "",
       ["tra_loi_binh_luan"], [_sp(False, "ca_hai"), CHE_DO], "Trả lời comment", ai=True),
    _m("th_tuong_tac_bai_app", "threads", "tuong_tac", "Tương tác bài đội đã đăng trên Threads",
       "Nick khác thích và trả lời tự nhiên dưới bài đội vừa đăng.", "", ["thich", "binh_luan"],
       [_so("so_bai", "Số bài mỗi nick", 3, 1, 10), CHE_DO], "Bình luận tương tác", ai=True),
    _m("th_quet_csv", "threads", "tuong_tac", "Quét Threads ra bảng", "Quét hồ sơ, trả lời hoặc kết quả tìm kiếm thành bảng CSV.", "",
       ["quet"], [{"key": "kieu_quet", "nhan": "Quét gì", "kieu": "chon", "mac_dinh": "tim_kiem",
                   "lua_chon": [["tim_kiem", "Kết quả tìm kiếm"], ["ho_so", "Bài của hồ sơ"], ["tra_loi", "Trả lời của bài"]]},
                  {"key": "dau_vao", "nhan": "Từ khoá hoặc link", "kieu": "chu", "bat_buoc": True},
                  _so("so_dong", "Tối đa số dòng", 50, 10, 500)], "Quét dữ liệu"),

    # ------------------------------------------------------------------ INSTAGRAM (6)
    _m("ig_dang_kho", "instagram", "dang_bai", "Đăng Instagram từ kho", "Đăng ảnh, nhiều ảnh hoặc Reel trong kho kèm chú thích.",
       "Chú thích tối đa 2200 ký tự, không nhận ảnh webp. Xác nhận thấy bài mới trên trang cá nhân.",
       ["dang_tuong"], [KHO, _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("ig_dang_ai", "instagram", "dang_bai", "Đăng bài AI đã duyệt lên Instagram", "Đăng bài AI viết đã duyệt (cần có ảnh).", "",
       ["dang_tuong"], [_sp(False), _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("ig_nuoi_nick", "instagram", "tuong_tac", "Nuôi nick Instagram", "Xem tin, lướt bảng tin và Reels, thỉnh thoảng thích.", "",
       ["thich"], [PHUT_NUOI], "Nuôi nick"),
    _m("ig_tuong_tac_link", "instagram", "tuong_tac", "Tương tác Instagram theo link", "Thích, bình luận, lưu bài theo link.", "",
       ["thich", "binh_luan", "luu"], [_links("links", "Link bài"), _bat("thich", "Thích"),
                                        _doan("cau_binh_luan", "Câu bình luận (mỗi dòng một câu)"), _bat("luu", "Lưu", False)],
       "Bình luận tương tác"),
    _m("ig_tra_loi_binh_luan", "instagram", "tuong_tac", "Tự trả lời bình luận Instagram",
       "Trả lời bình luận dưới bài của nick; hỏi giá thì mời nhắn tin.", "", ["tra_loi_binh_luan"],
       [_sp(False, "ca_hai"), CHE_DO], "Trả lời comment", ai=True),
    _m("ig_dang_nhap_threads", "instagram", "ket_ban", "Đăng nhập Threads bằng Instagram",
       "Mở Threads và đăng nhập bằng tài khoản Instagram đang có trong profile.", "", [], [], "Lịch chạy"),

    # ------------------------------------------------------------------ X (5)
    _m("x_dang_kho", "x", "dang_bai", "Đăng X từ kho", "Đăng bài trong kho lên X, tự chia chuỗi khi dài.",
       "Tối đa 4 ảnh hoặc 1 video; quá 280 ký tự thì tách chuỗi; hai bài cách nhau ít nhất 10 phút.",
       ["dang_tuong"], [KHO, _so("so_bai", "Số bài mỗi nick", 1, 1, 3)], "Đăng bài"),
    _m("x_quan_ly_bai", "x", "dang_bai", "Ghim / bỏ ghim / xoá bài X", "Quản lý bài của chính nick theo link.", "Xoá cần xác nhận trong hộp thoại X.",
       ["quan_ly_bai"], [_links("links", "Link bài của nick"), {"key": "hanh_dong", "nhan": "Làm gì", "kieu": "chon", "mac_dinh": "ghim",
                                                                 "lua_chon": [["ghim", "Ghim"], ["bo_ghim", "Bỏ ghim"], ["xoa", "Xoá"]]}],
       "Đăng bài"),
    _m("x_tra_loi_tu_khoa", "x", "tuong_tac", "Trả lời X theo từ khoá (AI)", "Tìm bài theo từ khoá, AI viết trả lời phù hợp.",
       "Bỏ tài khoản tích xanh/xám, quảng cáo, crypto, 18+, chính trị.", ["binh_luan"],
       [{"key": "tu_khoa", "nhan": "Từ khoá", "kieu": "chu", "bat_buoc": True}, _sp(False, "ca_hai"),
        _so("so_tra_loi", "Số trả lời mỗi nick", 3, 1, 20), CHE_DO], "Bình luận tương tác", ai=True),
    _m("x_tuong_tac_link", "x", "tuong_tac", "Tương tác X theo link", "Thích và đăng lại bài theo link.", "",
       ["thich", "chia_se"], [_links("links", "Link bài"), _bat("thich", "Thích"), _bat("dang_lai", "Đăng lại", False)],
       "Bình luận tương tác"),
    _m("x_nuoi_nick", "x", "tuong_tac", "Nuôi nick X", "Lướt mục Dành cho bạn và thỉnh thoảng thích.", "", ["thich"], [PHUT_NUOI], "Nuôi nick"),

    # ------------------------------------------------------------------ REDDIT (4)
    _m("rd_dang_sub", "reddit", "dang_bai", "Đăng bài vào subreddit", "Đăng bài chữ/link vào sub đã chọn, kèm flair nếu sub yêu cầu.",
       "Tiêu đề tối đa 300 ký tự, một bài một sub, nick nên nuôi ít nhất 3 ngày.", ["dang_tuong"],
       [{"key": "sub", "nhan": "Subreddit (vd r/vietnam)", "kieu": "chu", "bat_buoc": True},
        {"key": "tieu_de", "nhan": "Tiêu đề", "kieu": "chu", "bat_buoc": True}, _doan("noi_dung", "Nội dung"),
        {"key": "flair", "nhan": "Flair (nếu sub bắt buộc)", "kieu": "chu"}], "Đăng bài"),
    _m("rd_nuoi_nick", "reddit", "tuong_tac", "Nuôi nick Reddit", "Lướt trang chủ và các sub, thỉnh thoảng upvote.", "", ["thich"], [PHUT_NUOI], "Nuôi nick"),
    _m("rd_binh_luan_ai", "reddit", "tuong_tac", "Bình luận Reddit bằng AI", "AI đọc bài mới trong sub và viết bình luận hữu ích.",
       "Giữ tỷ lệ 9 bình luận giúp ích : 1 nhắc sản phẩm.", ["binh_luan"],
       [{"key": "sub", "nhan": "Các subreddit (cách nhau dấu phẩy)", "kieu": "chu", "bat_buoc": True}, _sp(False, "ca_hai"),
        _so("toi_da", "Tối đa bình luận mỗi nick", 3, 1, 10), CHE_DO], "Bình luận tương tác", ai=True),
    _m("rd_tham_gia_sub", "reddit", "ket_ban", "Tham gia subreddit", "Bấm Join các sub trong danh sách.", "", ["vao_nhom"],
       [{"key": "sub", "nhan": "Các subreddit (cách nhau dấu phẩy)", "kieu": "chu", "bat_buoc": True}], "Tham gia group"),
]

THEO_ID = {m["id"]: m for m in MAU}

# Giới hạn mặc định (nick mới / nick lâu năm) theo hành động, mỗi ngày mỗi nick.
GIOI_HAN_MAC_DINH = {
    "chung": {"viec_ngay_moi": 20, "viec_ngay_lau": 60, "nghi_phut": [8, 25], "lau_nam_sau_ngay": 90,
              "nghi_giay": [6, 25], "tang_tuan_pt": 25},
    "nen_tang": {
        "facebook": {"dang_tuong": [2, 5], "dang_nhom": [2, 6], "dang_trang": [3, 10], "vao_nhom": [3, 6],
                     "binh_luan_nhom": [5, 15], "tra_loi_binh_luan": [10, 30], "binh_luan": [5, 15],
                     "thich": [8, 30], "chia_se": [2, 5], "nhan_tin": [10, 30], "tra_loi_tin_nhan": [20, 60],
                     "vao_nhom_moi_gio": 5},
        "tiktok": {"dang_video": [1, 3], "thich": [15, 60], "binh_luan": [5, 15], "luu": [5, 20],
                   "binh_luan_live": [10, 40], "tra_loi_binh_luan": [10, 30]},
        "youtube": {"dang_video": [1, 3]},
        "threads": {"dang_tuong": [2, 6], "thich": [10, 40], "binh_luan": [5, 15], "chia_se": [2, 6],
                    "tra_loi_binh_luan": [10, 30], "quet": [3, 10]},
        "instagram": {"dang_tuong": [1, 3], "thich": [10, 40], "binh_luan": [5, 15], "luu": [5, 20],
                      "theo_doi": [5, 20], "tra_loi_binh_luan": [10, 30]},
        "x": {"dang_tuong": [3, 10], "thich": [10, 40], "binh_luan": [3, 12], "chia_se": [3, 10], "quan_ly_bai": [10, 30]},
        "reddit": {"dang_tuong": [1, 2], "thich": [10, 30], "binh_luan": [2, 8], "vao_nhom": [3, 8]},
    },
}


def danh_muc() -> dict:
    return {"nen_tang": NEN_TANG, "nhom": NHOM, "hanh_dong": HANH_DONG, "mau": MAU}


def kiem_tham_so(mau_id: str, ts: dict) -> dict:
    """Chuẩn hoá + kiểm tham số theo khai báo. Trả dict sạch; raise ValueError câu tiếng Việt."""
    m = THEO_ID.get(mau_id)
    if not m:
        raise ValueError(f"không có mẫu '{mau_id}'")
    ts = dict(ts or {})
    ra = {}
    for f in m["tham_so"]:
        k, kieu = f["key"], f["kieu"]
        v = ts.get(k, f.get("mac_dinh"))
        if kieu == "so":
            try:
                v = int(v if v not in (None, "") else f.get("mac_dinh", 0))
            except Exception:
                raise ValueError(f"'{f['nhan']}' phải là số")
            v = max(f.get("min", 0), min(f.get("max", 10 ** 6), v))
        elif kieu == "bat":
            v = bool(v) and str(v).lower() not in ("0", "false", "off", "no")
        elif kieu in ("chon", "kho"):
            hop = [x[0] for x in f.get("lua_chon") or []]
            v = str(v or f.get("mac_dinh") or "")
            if hop and v not in hop:
                raise ValueError(f"'{f['nhan']}' không hợp lệ")
        elif kieu == "ds_link":
            if isinstance(v, str):
                v = [x.strip() for x in v.replace(",", "\n").splitlines() if x.strip()]
            v = [str(x).strip() for x in (v or []) if str(x).strip()]
            sai = [x for x in v if not x.startswith("https://")]
            if sai:
                raise ValueError(f"link phải bắt đầu bằng https:// ({sai[0][:60]})")
            v = v[:500]
        elif kieu == "san_pham":
            v = str(v or "").strip()
        else:
            v = str(v or "").strip()[:20000]
        if f.get("bat_buoc") and v in ("", [], None):
            raise ValueError(f"thiếu '{f['nhan']}'")
        ra[k] = v
    return ra
