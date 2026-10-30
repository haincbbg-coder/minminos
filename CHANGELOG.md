# MinMin OS

## [26.10.307] - 2026-10-30
### Thêm mới
- **Bot Zalo đọc được file PDF, Word, Excel khách gửi.** Trong nhóm, khách gửi file rồi mới gọi bot vẫn được.
- **Chat riêng gặp câu khó** (giảm giá, hoàn tiền, khiếu nại) thì bot im và báo bố ở chuông, ghi rõ khách nhắn gì và vì sao bot không tự trả lời. Bot cũng biết tự tách câu dài thành vài tin ngắn.
- **Bot đọc tag Zalo của cuộc chat**: form bot có ô "Không trả lời các cuộc chat có tag Zalo" (ví dụ Gia đình).
- **Tin bot gửi mà Zalo không nhận** thì Hộp thư ghi "chưa gửi được" và chuông báo bố, không còn hiện như đã gửi.
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
