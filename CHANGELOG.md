# MinMin OS

## [26.10.331] - 2026-10-31
### Cải thiện
- **Đội Social, Facebook**: khi không thấy nút Thích hoặc Chia sẻ, Worker ghi vào nhật ký các nút đang thấy trên bài để biết Facebook đổi giao diện chỗ nào.
- **Trả lời tin nhắn**: báo rõ vì sao bỏ qua một hội thoại (không đọc được tin do Messenger khoá tin mã hoá, hoặc tin cuối là của nick) thay vì bỏ qua im lặng.

## [26.10.330] - 2026-10-31
### Sửa lỗi
- Đọc đúng phản hồi POS có nhiều khối JSON và lấy schema riêng, không ghép nhầm với ví dụ gọi lệnh.

## [26.10.328] - 2026-10-31
### Sửa lỗi
- Đọc đúng danh mục sản phẩm và biến thể từ hợp đồng công cụ Pancake POS đang hoạt động; tách khỏi danh sách nhãn sản phẩm.

## [26.10.326] - 2026-10-31
### Thêm mới
- **Thứ tự dùng mô hình** trên trang Bộ não AI: thẻ MAIN rồi Dự phòng 1, 2, kéo hoặc bấm Đảo để đổi. Hết lượt trước khi kịp trả lời thì MinMin tự hỏi lại bằng thẻ kế; hết giữa chừng có nút **Chạy lại ngay**. Đã gọi công cụ thì không bao giờ tự chạy lại.
- **Nhiều API key cho một nhà**: danh sách đánh số, dùng lần lượt, key hết lượt ghi giờ mở lại.
### Cải thiện
- **Nhanh hơn**: Claude Code được giữ sẵn giữa các tin của một cuộc chat. Mở lại trang chỉ tải khoảng 96 KB thay vì 294 KB, font nằm sẵn trong app, máy chủ đang khởi động lại thì trang tự chờ rồi vào lại.
- Sơ đồ, hình và ảnh phóng to, kéo được bằng con lăn hoặc hai ngón tay.

## [26.10.325] - 2026-10-31
### Thêm mới
- **Fanpage qua Pancake vào hộp thư Chatbot**: mỗi Page là một tài khoản. Nhân viên trả lời trên Pancake thì A.I. tự nhường. Mặc định A.I. chỉ soạn nháp chờ bố duyệt, muốn tự trả lời phải bật riêng từng Page.
- **Kênh Zalo OA** trong Chatbot, MinMin tự làm mới token. Bot Zalo cá nhân nhắn được chữ đậm, chữ màu, đọc được file PDF, Word, Excel khách gửi. Gặp câu khó ở chat riêng thì bot im và báo bố.
- **Thống kê "A.I. giúp bố được gì"**, tách theo từng nick/Page. Trên điện thoại, mở chat là toàn màn hình và Enter là xuống dòng.
- **Tua lại hội thoại** từ một câu hỏi cũ, **thanh mục tiêu** `/goal`, Telegram ghim model theo từng cuộc trò chuyện.
### Cải thiện
- **Chuông chỉ kêu tin khẩn**: thông báo có nhóm và mức, tin khác vào ngăn Đã lọc. Trang Công việc chỉ hỏi bố khi thật sự cần, có Đã kiểm / Chưa kiểm. Việc hết lượt không còn bị ghi là Xong.
- **MinMin tự học từ trò chuyện**, có giới hạn mỗi ngày, hoàn tác được và có nút Tạm dừng mọi cải tiến.
### Bảo mật
- Vá Node.js tháng 10/2026.

## [26.10.323] - 2026-10-31
### Sửa lỗi
- **Đội Social, Facebook**: khung chat Messenger còn nổi từ lần nhắn tin trước làm Worker không thấy nút Thích, Chia sẻ trên bài và đọc nhầm tên nhóm thành "Đoạn chat". Worker giờ tự đóng khung chat khi mở trang và chỉ lấy tên trong vùng chính.
- **Messenger đòi mã PIN**: Worker không dừng nữa, tự đóng hộp PIN (không nhập mã, không bấm "Không khôi phục") rồi trả lời tin nhắn tiếp.
- **Tham gia nhóm theo sản phẩm**: khi không có nhóm nào để xin vào, báo rõ lý do (kho hết nhóm, tìm từ khoá thấy bao nhiêu, AI chọn bao nhiêu) thay vì chỉ "xem 0 nhóm".

## [26.10.321] - 2026-10-31
### Thêm mới
- Mô phỏng kế hoạch bằng thanh kéo, xem biểu đồ và số liệu liên thông khi các giả định thay đổi.
- Quản lý nhiều phương án theo cửa hàng/công ty, chọn nhập tay hoặc lấy dữ liệu POS có xem trước trước khi áp dụng.

## [26.10.320] - 2026-10-31
### Cải thiện
- **Tinh gọn đợt 4**: danh sách Agent thành dòng gọn có icon, tên, vai trò, model; xem được 2 đến 3 agent mỗi hàng.
- Bấm **Chi tiết** để mở ngăn bên phải xem skill, nhóm và sửa, xuất, xoá. Trên điện thoại ngăn trượt lên từ dưới.

## [26.10.319] - 2026-10-31
### Sửa lỗi
- **Chiến dịch AI kèm ảnh/video từ kho:** trước đây tệp bị chuyển khỏi kho sang nháp đầu tiên, nên đích thứ hai trở đi và các lượt sau hỏng ("Media không còn trong kho"). Giờ chỉ chép, kho giữ nguyên.
- **Bảng CSV của các mẫu quét** chạy được bằng Chrome MinMin trên VPS (trước báo "Permission denied").
- **Báo cáo Fanpage:** tiếp cận và tương tác không còn luôn bằng 0. Meta đã bỏ chỉ số cũ; MinMin dùng chỉ số mới, lấy số của ngày hôm qua và ghi đúng ngày. Facebook không trả số thì ghi rõ lỗi vào nhật ký.
- **Nháp video TikTok/YouTube đã duyệt** tính vào hạn mức đăng video mỗi ngày.
- **Duyệt nhiều bài cùng lúc cho một nick** không còn đăng dồn liền nhau: các bài cách nhau theo thời gian nghỉ của Giới hạn nick.
- **Trần vào nhóm mỗi giờ** (Giới hạn nick) giờ có hiệu lực; mẫu "Bình luận nhóm theo sản phẩm" cũng tính lượt vào nhóm.
- Worker GPM không còn đóng ngang cửa sổ profile bạn đang tự mở: chỉ dọn trình duyệt do Worker mở lần trước. Mở profile lỗi giữa chừng thì đóng lại, lượt sau khỏi kẹt.
- Chrome MinMin trên VPS đóng được profile của việc bị treo quá giờ.
- Câu báo nick bị đăng xuất / checkpoint đúng cho cả Chrome MinMin, không chỉ GPM. Chữ ở Duyệt nội dung, Tài khoản cập nhật theo.
- Lỗi chiến dịch AI ghi rõ nguyên nhân thay vì "Tác vụ chưa hoàn tất".

## [26.10.317] - 2026-10-31
### Thêm mới
- **Kế Hoạch tài chính** tại Kết Nối Ngoài: kế hoạch bán/nhập hàng, P&L, hòa vốn, công nợ và dòng tiền 12 tháng liên thông.
- So sánh kịch bản, đối soát lợi nhuận với tiền, nhập thực tế, khóa kỳ, lưu 30 phiên bản và xuất bản sao/báo cáo.
- Bản xem trước: chưa đồng bộ dữ liệu sàn/Bảng tính kinh doanh; nhận xét theo quy tắc, chưa có AI offline. Giá trị nhập chưa gồm VAT, thuế là giả định do người dùng đặt.

## [26.10.306] - 2026-10-30
### Cải thiện
- **Webhook bền hơn**: mỗi sự kiện Pancake, chuyển khoản gửi tới đều được lưu lại trước khi xử lý, máy khởi động lại cũng không mất, gửi trùng thì tự bỏ.
- Trang Webhook có thêm phần **Sự kiện** và **Tình trạng**: bố xem từng sự kiện đi tới đâu, lỗi gì, bấm chạy lại được.
- Lỗi tạm thời (kể cả bị chặn vì gửi quá nhanh) tự thử lại; khoá bí mật và mã nhân viên không bao giờ hiện ra màn hình.

## [26.10.305] - 2026-10-30
### Cải thiện
- **Tinh gọn đợt 3**: Chợ MinMin và danh sách dịch vụ sẵn có đổi từ thẻ to sang từng dòng gọn.
- Sổ hành động, và phần giải thích của Việc 1 lần thu gọn, bấm mới mở.

## [26.10.304] - 2026-10-30
### Sửa lỗi
- Tìm kiếm/lọc đích đăng và giữ lựa chọn, phong cách khi chuyển bộ lọc trong chiến dịch AI.
- Giữ nội dung form chưa lưu khi trang Máy ở nhà tự làm mới.

## [26.10.303] - 2026-10-30
### Thêm mới
- Quản lý profile theo nhóm, proxy, vị trí lưu và tạo hàng loạt.
- Chiến dịch nội dung đa nền tảng từ prompt, có ảnh và lịch đăng.
- Rà soát trạng thái tác vụ, không lặp bài để lấp số lượng AI viết thiếu.

## [26.10.302] - 2026-10-29
### Thêm mới
- Chọn chạy Chrome ngay trên VPS hoặc trên máy tính cá nhân đã ghép. Máy cá nhân dùng Chrome riêng, không cần GPM Login.
- Quản lý profile máy tính ngay từ VPS: tạo, đổi tên, mở/đóng, mở kho extension. Người dùng đăng nhập và duyệt cài extension trực tiếp trên máy tính.
- Có lựa chọn dùng phiên Chrome đã đăng nhập sẵn qua cơ chế cho phép kết nối của Chrome 144+. Cốc Cốc chỉ dùng khi bản đang cài hỗ trợ; không chép cookie và không tự đóng trình duyệt cá nhân.

## [26.10.301] - 2026-10-29
### Thêm mới
- **Chrome MinMin**: tạo profile riêng, đăng nhập và giữ phiên Facebook, YouTube, TikTok ngay trên máy chạy MinMin; có màn hình điều khiển trong web cho VPS.
- Máy local mở cửa sổ Chrome, VPS chạy trình duyệt trên máy chủ. Worker tích hợp nhận tác vụ Đội Social trực tiếp, không cần GPM Login.
- Profile Chrome hỗ trợ chạy ẩn và chặn điều khiển tay khi tác vụ đang chạy.

26.10.300 là phiên bản khởi đầu của MinMin OS.
