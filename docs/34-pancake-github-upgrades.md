# Pancake hội thoại, Webhook, Store và GitHub (26.10.279)

## Pancake

Trong Kết nối, kết nối **Thống kê Pancake** nay mang tên **Pancake: Thống kê & hội thoại**.
Danh sách page và token cũ vẫn dùng được. Ba công cụ thống kê cũ giữ nguyên.

- Hỏi “Liệt kê hội thoại inbox của page ...”, rồi đọc tin bằng mã hội thoại và Page ID.
- Khi có nhiều page, MinMin cần chọn đúng Page ID trước khi đọc hoặc thao tác. Không tự đoán page.
- Có thể soạn câu trả lời, gửi chữ/ảnh local, gắn thẻ, đánh dấu đọc, phân công và thêm ghi chú.
- Muốn thao tác, chủ đổi kết nối sang Toàn quyền. Mọi lệnh ghi vẫn chờ nút **Đồng ý** trong chat
  hoặc **Kết nối > Chờ duyệt**. Nội dung đầy đủ hiện ở thẻ duyệt. Từ chối, hết giờ, hoặc thu hồi
  quyền trong lúc chờ thì không thực hiện. Lượt Chỉ đọc/Ghi nháp không ghi lên Pancake.
- Gửi lỗi không tự gửi lại; kiểm tra hội thoại thật trước khi yêu cầu gửi lần nữa.

Gói Pancake hội thoại cài riêng từ Store cũng phải qua cổng duyệt của hub. Dùng kết nối có sẵn
để tránh phải nhập cùng token hai lần. Không tạo lại token Pancake nếu token cũ vẫn dùng được.

## Webhook đơn hàng

Mở **Kết nối > Webhook > Mở trang Webhook**, hoặc `/webhook`.
Đường `/hook/<mã>` cũ vẫn dùng được. Sự kiện được lưu SQLite trước khi trả lời nhà gửi.
Khởi động lại giữ hàng chờ; việc dở dang chưa rõ kết quả sẽ bị chặn để chủ kiểm tra.

Trong Chi tiết có bộ lọc, thời gian chống trùng, hành động AI và chuyển tiếp HTTP.
Với POSCake, có thể dùng bộ lọc `status | bang | 0` cho đơn mới. Bật chống trùng theo
`shop_id + id + status` khi chỉ cần một lần cho mỗi trạng thái đơn. Để tắt nếu cần nhận
mọi lần sửa giá trị của một đơn cùng trạng thái. Nguồn khác vẫn dùng mã lần giao hoặc băm thân.

Mặc định, lỗi mạng hoặc HTTP 500/408 là chưa rõ bên nhận đã xử lý chưa: dừng và báo chủ.
Chỉ bật **Bên nhận tự chống trùng** nếu nơi nhận thực sự dùng `X-MinMin-Delivery` để loại bản lặp.
HTTP 429 được thử lại theo Retry-After. Hành động đã thành công không chạy lại cùng hành động lỗi.
Phần Sự kiện che dữ liệu khách/nhân viên, giữ lịch sử xử lý; phần Tình trạng có hàng đợi và lỗi.

Webhook mới mặc định chỉ đọc/đề xuất. Bản nâng cấp không tự tạo webhook gửi tin, không tự đổi
đường trên POSCake và không tự kết nối dữ liệu tài chính của doanh nghiệp.

## Store theo nguồn

Tab repo gợi ý trong MinMin Store hiện các gói có nguồn GitHub, commit và ngày đồng bộ.
Kho được làm mới độc lập với app. Cài/cập nhật vẫn qua màn hình kiểm tra gói và xác nhận digest;
không âm thầm chạy code mới chỉ vì tác giả sửa repo. Nguồn thiếu/sai được bỏ qua.

## GitHub trong chat

Kết nối GitHub trên tab Đã nối bằng token của mình, hoặc dùng lại token sao lưu sau kiểm tra.
Trong thanh soạn tin, bấm **GitHub** để chọn repo và nhánh gốc; mỗi chat có worktree riêng.
Có thể gắn nhiều repo. Repo được tải ngoài brain để không lẫn vào sao lưu và tìm kiếm.

Sau lượt sửa mã, MinMin kiểm tra cục bộ, quét secret, commit, đẩy nhánh, mở PR nháp và theo dõi CI
đúng commit. Không có CI hoặc CI lỗi không được coi là đạt. Có vòng sửa lỗi giới hạn; thay đổi
làm yếu kiểm tra, phát hiện chưa xử lý hoặc yêu cầu repo chưa đạt đều chặn tự merge.
Mỗi repo có công tắc tự merge; trạng thái và lượt việc tiếp theo xem từ chip GitHub.

Review chéo hiện dùng các nhà cung cấp API đã nối, với danh sách tool rỗng và không tự chuyển
sang nhà khác. Nếu không có nhà thứ hai phù hợp, PR ghi rõ chưa review chéo.
Các model API cũng nhận công cụ file/lệnh giới hạn trong worktree của chat. GitHub token giữ
ở server, được mã hoá trong settings, không đưa vào prompt hay URL remote.

Nguồn tích hợp: blogminhquy/javis-os 0.370.0; Javis Store pancake-chat-mcp 1.1.0;
nền tảng webhook MinMin PR #280. Kiểm thử mạng dùng API giả, không nhắn khách thật.
