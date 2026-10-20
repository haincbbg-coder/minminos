# Quan sát bản demo LOHA Agents (lohaagent.com/demo, v2.0.0) - 2026-10-20

Ghi chép HÀNH VI và BỐ CỤC quan sát được để MinMin tự làm bản của mình. KHÔNG chép mã, logo, tên, chữ
nguyên văn của họ vào sản phẩm: viết lại bằng lời của MinMin.

## Giao diện chung
- Nền sáng, thẻ trắng bo tròn lớn, bóng mềm; màu nhấn gradient tím-xanh (nút chính tím). Chữ nhỏ gọn.
- Thanh bên trái cố định: logo trên cùng; mục "Tổng quan"; các NHÓM thu gọn/mở được:
  CẤU HÌNH, AI AGENTS (Automation, Nhật ký hoạt động, Kho nội dung, Kho group FB, Duyệt nội dung,
  Tin nhắn [huy hiệu số chưa đọc], Trợ lý AI, Kiến thức cho Agent), QUẢN LÝ (Tài khoản, Giới hạn nick,
  Proxy, Tiện ích), THÔNG TIN (Gói hiện tại, Gói & giá). Dưới cùng: email + gói, phiên bản, nút sáng/tối, ngôn ngữ.
- Điều hướng bằng hash route (#/overview, #/templates, #/activity, #/post-library, #/fb-groups,
  #/review-queue, #/messages, #/ai-settings, #/content-profiles, #/profiles, #/nick-limits).

## Tổng quan (#/overview)
- Lời chào theo giờ ("Chào buổi tối"), câu tóm tắt "Agent đang trông N tài khoản trên M nền tảng, viết và làm việc bằng K AI".
- Huy hiệu "Agent đang trực · Telegram".
- 5 nút nhanh có icon: Viết bài AI, Chạy hàng loạt, Thêm tài khoản, Lịch hẹn, Duyệt nội dung.
- Hình minh hoạ lớn: robot ở giữa, các icon nền tảng quanh (Telegram, YouTube, Reddit, Facebook, Instagram, TikTok, X), chữ "<Tên> Agent · Sẵn sàng".
- Thẻ nguồn AI: từng nguồn (Gemini/Groq: "chưa có API key", gói AI web "1/6 AI dùng được", Google Flow "1 nick · tạo ảnh").
- Số lớn: "14 tài khoản trên 6 nền tảng", "2 AI sẵn sàng trên 9 AI hỗ trợ".
- 4 ô số: Lượt chạy · 7 ngày (1.577), Thành công (1.537, 97%), Đang chạy (0), Lỗi (40).
- Biểu đồ cột chồng "Lượt chạy 14 ngày" (thành công xanh / lỗi đỏ), tổng + % thành công, nhãn ngày, "Hôm nay 267".
- "Cần bạn xử lý (3)": danh sách việc kèm nút (Xem / Đổi / Duyệt): việc Agent cần xem (kèm lý do), proxy chết, group chờ duyệt.
- Link "Mở nhật ký hoạt động".

## Automation (#/templates) - 3 tab: Chọn mẫu | Lịch hẹn (số) | nút "+ Chạy hàng loạt"
- Tab nền tảng có số: Facebook 13, TikTok 5, YouTube 1, Threads 7, Instagram 6, X 5, Reddit 4.
- Lọc nhóm (chip): Tất cả, Đăng bài (4), Tương tác (7), Kết bạn & nhắn tin (2).
- Danh sách theo nhóm ("ĐĂNG BÀI (4)", "TƯƠNG TÁC (7)"...), mỗi thẻ: icon nền tảng, tên mẫu, mô tả rút gọn 1 dòng (bấm mở rộng), nút "Chạy hàng loạt".
- Form "Tạo bulk run mới" (trang #/bulk-run/new?template=...):
  Tên (tuỳ chọn, gợi ý "để trống sẽ tự đặt theo workflow"); WORKFLOW (select mọi mẫu);
  PROFILES (x/y đã chọn · z khớp filter) + ô tìm + "Chọn N"/"Bỏ chọn" + lọc theo nhãn nền tảng của mẫu
  + lọc Thư mục; mỗi dòng nick: checkbox, tên, quốc gia, trạng thái ready/warning;
  khối THAM SỐ RIÊNG của mẫu (vd sản phẩm từ Kiến thức, số bài/lượt, mỗi group tối đa N bài/7 ngày...);
  CONCURRENCY; tuỳ chọn (bắt buộc proxy, chạy ẩn, sắp xếp cửa sổ); CHẾ ĐỘ: Chạy ngay | Hẹn lịch (cron);
  nút Huỷ / "Bắt đầu bulk run (N profile)".
- Lịch hẹn: ghi chú "Lịch chỉ chạy khi app đang mở". Bảng: Tên | Workflow | Số profile | Lịch hẹn
  (dạng người đọc: "Hàng ngày lúc 08:15", "Mỗi 2 giờ", hoặc cron thô) | Trạng thái Bật/Tắt | Lần kế
  ("8 giờ nữa") | Lần trước | Số lần / lỗi | Thao tác.

## Nhật ký hoạt động (#/activity) - 3 tab: Hoạt động | Đợt chạy hàng loạt | Lịch sử chạy
- Hoạt động: "Đang chạy" (tự làm mới 5 giây; "Không có nick nào đang chạy"); "Hôm nay theo nick":
  Nick | Thành công | Bỏ qua | Lỗi | Chi tiết ("Bình luận 1 · react 1 · reply 1 · Đăng bài 1");
  "Dòng thời gian" có Làm mới, Xuất CSV, lọc thời gian (Hôm nay/24 giờ/7 ngày/30 ngày/Tuỳ chọn), lọc nick,
  lọc tính năng (Bình luận group, Tìm group, Trả lời comment, Nhắn tin Messenger, Đăng bài, Bình luận
  tương tác, Nuôi nick, Tham gia group, AI agent (MCP), Lịch chạy), lọc kết quả (Thành công/Bỏ qua/Lỗi/Thông tin).
  Bảng: Thời gian | Nick | Việc (2 dòng: hành động + tính năng) | Group (tên group + sản phẩm) | Kết quả | Chi tiết + "Mở bài".
  Ví dụ chi tiết: "Quét 12 bài mới, 3 bài đúng nhu cầu", "Bỏ qua: bài đã có bình luận của nick khác trong team",
  "Nhóm yêu cầu duyệt bài: bài đang chờ quản trị viên", "Nuôi nick: lướt bảng tin 6 phút".
- Đợt chạy hàng loạt: "104 / 104 batch", lọc trạng thái (Đang chạy/Hoàn tất/Đã huỷ/Đang chờ) + thời gian.
  Bảng: Tên (+ "N nick") | Trạng thái | Tiến trình ("4/4 · ✓3 ✗1") | Concurrency | Comments/profile | Tạo lúc.
- Lịch sử chạy: "2690 kết quả", lọc status (Chờ/Đang chạy/Thành công/Thất bại/Đã huỷ), "Hiện cả lượt tự trả lời tin nhắn".
  Bảng: Bulk run | Workflow | Số run | Status | Bắt đầu | Xem.

## Kho nội dung (#/post-library) - tab Kho bài | Viết bài AI
- Kho bài theo thư mục trên máy (Facebook status, TikTok, YouTube, Threads, Instagram, X, Reddit); bảng mỗi
  profile: Còn | Đã đăng | Lỗi | Mở | Thêm bài…; "Tạo cấu trúc mẫu". (MinMin: kho trên máy chủ, tải lên từ điện thoại.)
- Viết bài AI: tạo bài từ hồ sơ sản phẩm, chọn nơi đăng, gửi sang Duyệt nội dung.

## Kho group FB (#/fb-groups)
- Chọn sản phẩm (select): "<Sản phẩm> - 6 group đã duyệt · 5 đã có nick tham gia"; "+ Thêm sản phẩm mới".
  Danh sách group theo sản phẩm: trạng thái (chờ duyệt/đã duyệt/danh sách đen), nick phụ trách, nick tương tác, lần quét.

## Duyệt nội dung (#/review-queue)
- Nút "Viết bài AI". Tab: Chờ duyệt (5) | Đã duyệt (1) | Đã đăng (1) | Đã bỏ | Lỗi | Hết hạn.
- Lọc Nơi đăng (Tất cả/Facebook nhóm-tường/Threads/Instagram/Reddit, có số) và Sản phẩm. "Chọn tất cả".
- Thẻ: loại (Bình luận | Bài đăng · Nhóm FB), nick, group, sản phẩm, "hết hạn sau 18 giờ", "Mở bài gốc",
  "Bài gốc: …", "Vì sao AI chọn: …", nội dung, nút Duyệt / Bỏ / Viết lại (AI). Phân trang "1–5 / 5".

## Tin nhắn (#/messages)
- "Tin nhắn khách", Làm mới. Tab: Cần trả lời tay (1) | Tất cả hội thoại (5) | Khách tiềm năng (1).
- Thẻ hội thoại: tên khách, trạng thái "Chờ trả lời tay", "Nick: … · Sản phẩm: … · 20/10 20:20", trích tin cuối,
  nút: Cho AI trả lời tiếp, Đánh dấu spam, Mở nick, Chép link, Xem tin (mở dòng tin Khách/Bot).

## Trợ lý AI (#/ai-settings)
- Trạng thái "Trợ lý AI đã sẵn sàng · Đang chạy - nguồn AI sẵn sàng", "Mở bảng điều khiển".
- "Kế hoạch AI": thẻ kế hoạch (#41) mô tả 1 câu, "Chờ bạn duyệt · 3 bước", nút Duyệt/Từ chối, danh sách bước
  (mỗi bước trạng thái chuẩn bị/đang chạy/xong); kế hoạch cũ "Hoàn tất · 1 bước".
- Khung chat "Trợ lý AI" có Lịch sử / Hội thoại mới; ví dụ: hỏi "Hôm nay các nick chạy thế nào?" -> trả số liệu;
  người dùng "Có, đăng vào nhóm mẹ bỉm" -> "Mình đã lên kế hoạch #41 - bạn xem và bấm Duyệt để chạy nhé."
- "Cài đặt AI" (MinMin: dùng chính bộ não MinMin, không cần khoá riêng).

## Kiến thức cho Agent (#/content-profiles)
- "Thêm sản phẩm". Hai nhóm: SẢN PHẨM (n) và CHỦ ĐỀ (CHỈ TƯƠNG TÁC) (n).
- Thẻ: tên, trạng thái (AI đang dùng | Chờ duyệt), "2 tài liệu · 3 hỏi đáp · 6 group", "1 câu khách hỏi chờ bạn trả lời".
- Chi tiết: mô tả, giá, tài liệu, tab Hỏi đáp (câu hỏi khách AI chưa trả lời được chờ chủ trả lời), group.

## Tài khoản (#/profiles) (MinMin: lấy từ GPM, không tạo/không proxy)
- Lọc quốc gia, thư mục, nền tảng; "Chọn tất cả". Mỗi dòng: chữ viết tắt, tên, cờ, trạng thái Ready/Warning,
  nhãn nền tảng (Facebook, Instagram, Threads...), cảnh báo "Đăng xuất · Facebook", lần chạy cuối, thư mục/nhóm, nút Khởi chạy.

## Giới hạn nick (#/nick-limits) - tab: Chung cho mọi nền tảng | Theo nền tảng | Tuổi nick
- Chung: Tổng việc/ngày nick mới, nick lâu năm, Nghỉ giữa 2 việc (phút, khoảng a–b), Nick thành "lâu năm" sau N ngày tuổi.
- Theo nền tảng (Facebook/Instagram/Threads/TikTok/X/Reddit):
  ĐĂNG BÀI & HOẠT ĐỘNG/NGÀY: Việc | Nick mới | Nick lâu năm (Đăng tường, Đăng bài nhóm, Vào nhóm, Bình luận trong
  nhóm, Trả lời bình luận, Bình luận seeding); TƯƠNG TÁC & NUÔI NICK/NGÀY: Thao tác | Tuần đầu | Tối đa (Thích...),
  Tăng mỗi tuần (%), Nghỉ giữa 2 thao tác (giây, a–b); LUẬT RIÊNG: Vào nhóm tối đa/giờ, % tổng việc giữ riêng
  cho trả lời bình luận; "Mặc định cho Facebook".
- Tuổi nick: "8/14 nick đang dùng giới hạn lâu năm", chọn nick + "Áp dụng cho nick đã chọn";
  bảng Nick | Tạo từ (tháng) | Tuổi | Mức giới hạn ("Nick mới · còn 50 ngày lên Lâu năm").

## Danh mục 41 mẫu (tóm tắt hành vi - viết lại bằng lời MinMin)
FACEBOOK (13): đăng bài AI đã duyệt vào nhóm theo sản phẩm; đăng status tường theo kho/thư mục; đăng bài vào nhóm theo
link; đăng bài AI đã duyệt lên tường; tương tác bài theo link (thích, cảm xúc, bình luận, chia sẻ; hoặc từ CSV);
nuôi nick (lướt bảng tin N phút, thích có giới hạn tăng dần 8→30/ngày, không bình luận/kết bạn/chia sẻ, chỉ tính
khi đọc lại thấy "Gỡ Thích"); bình luận nhóm theo sản phẩm (mỗi group 1 nick phụ trách, quét bài mới, AI chấm nhu cầu
có đọc ảnh, tránh bài đối thủ nhưng đọc bình luận để trả lời người hỏi mua, link để ở reply, lịch quét lại 12h/24h/3-7
ngày, chạy thử = nháp); bình luận nhóm theo link (dán link group, tự tham gia nếu chưa vào); tự trả lời bình luận (đọc
thông báo, bài của nick: trả lời mọi bình luận chưa trả lời; bài người khác: chỉ khi được nhắc; câu chưa có thông tin
-> mời inbox + ghi Hỏi đáp); tự trả lời tin nhắn (khách chờ lâu nhất trước, đúng giá trong hồ sơ, câu khó/đặt mua/khiếu
nại/SĐT sai -> câu giữ khách + báo Telegram "cần trả lời tay", SĐT -> khách tiềm năng, chủ tự trả lời -> bot nhường
12 giờ, bỏ nhóm chat, không đụng mã PIN, nhịp 20-60 giây); tương tác bài app đã đăng trong group (tối đa 3 nick/bài,
rải 2-6 giờ, không dùng nick đăng bài, mỗi nick một kiểu, không link/icon/review); nhắn tin danh sách người nhận (UID/
username/link, nhớ ai đã nhắn, chia đều, 3 lần lỗi thì bỏ); tham gia group theo sản phẩm (1 nick chính + 3 nick tương tác
mỗi group, AI trả lời câu hỏi duyệt, câu hỏi xin SĐT/email thì bỏ group, xem lại chờ duyệt 12h, quá 7 ngày đổi nick,
giới hạn join nick mới 3/ngày lâu năm 6/ngày tối đa 5/giờ).
TIKTOK (5): đăng video theo kho (đặt công khai, xử lý hộp kiểm tra nội dung, xác minh rời /upload mới báo thành công,
captcha -> dừng); tương tác video (thích, bình luận, lưu; captcha/đăng xuất/quá nhanh -> dừng; 0 thành công -> báo thất
bại); bình luận LIVE (pool bình luận trộn mỗi nick, giãn ngẫu nhiên, xoay URL live, ô chat contenteditable tối đa 150 ký
tự + nút gửi); nuôi nick (For You, xem 5-20 giây/video, tim có giới hạn 15→60); tự trả lời bình luận (video mới của nick,
nhận sản phẩm theo caption).
YOUTUBE (1): đăng video qua YouTube Studio theo kho (tiêu đề ≤100 ký tự, mô tả, công khai; bị đẩy sang accounts.google.com -> lỗi).
THREADS (7): đăng bài theo kho (≤500 ký tự/phần, dòng --- tách chuỗi, ≤20 ảnh); đăng bài AI đã duyệt; tương tác (thích,
trả lời, đăng lại; từ link hoặc CSV); nuôi nick (Dành cho bạn, thích 10→40); tự trả lời bình luận; tương tác bài app đã
đăng; quét Threads ra CSV (hồ sơ/trả lời/tìm kiếm).
INSTAGRAM (6): đăng theo kho (ảnh/nhiều ảnh/Reel, caption ≤2200, không nhận webp, xác nhận bài mới trên trang); đăng bài
AI đã duyệt (cần ảnh); nuôi nick (story, feed, Reels; thích/lưu/theo dõi có giới hạn); tương tác theo link; tự trả lời
bình luận (bình luận công khai không nói giá -> mời inbox); đăng nhập Threads qua Instagram.
X (5): đăng theo kho (≤4 ảnh/1 video, tự chia chuỗi >280, chữ có dấu tính 2, cách nhau ≥10 phút); ghim/bỏ ghim/xoá bài của
nick (xoá cần xác nhận); trả lời theo từ khoá bằng AI (mặc định chạy thử, bỏ bài tích vàng/xám, quảng cáo, crypto,
18+, chính trị); tương tác theo link (thích, đăng lại); nuôi nick.
REDDIT (4): đăng vào sub (tiêu đề ≤300, flair, 1 bài 1 sub, nick nuôi ≥3 ngày); nuôi nick; bình luận AI (luật 9:1, 3 chế
độ chạy thử/duyệt trước/đăng luôn); tham gia sub theo danh sách.
PHỤ: tạo ảnh Google Flow cho bài nháp.

## Nguyên tắc chung rút ra
- Mỗi thao tác chỉ tính thành công khi ĐỌC LẠI trang thấy trạng thái đã đổi.
- Lỗi SAU khi đã bấm Đăng -> không tự đăng lại (đưa vào "lỗi"/_failed); lỗi TRƯỚC khi bấm -> trả về hàng chờ.
- "Hết bài" là trạng thái vàng riêng, khác lỗi đỏ.
- Đăng xuất / checkpoint / captcha / "hành động quá nhanh" -> dừng ngay nick đó, báo lỗi, không thành công giả.
- Giới hạn theo ngày theo nick, tăng dần theo tuần, nghỉ ngẫu nhiên giữa thao tác.
- Hầu hết mẫu có "Chạy thử": chỉ tạo nháp/ghi nhật ký, không đăng.
