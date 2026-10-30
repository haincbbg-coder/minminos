# MinMin OS

## [26.10.309] - 2026-10-30
### Thêm mới
- **Thứ tự dùng** trên trang Bộ não AI: chỉ hiện các nhà bố đã kết nối, thẻ trên cùng là MAIN, sau đó Dự phòng 1, 2. Kéo thẻ (điện thoại thì giữ nút sáu chấm) hoặc bấm **Đảo** để đổi. Mỗi thẻ có chip model và Effort riêng; chat, việc nền và Telegram dùng chung thứ tự này.
- **Hết lượt thì tự sang thẻ kế.** Mô hình đang chạy báo hết lượt trước khi viết chữ nào thì MinMin hỏi lại ngay bằng thẻ kế, kèm một dòng "Đang dùng ... vì ... hết lượt". Hết giữa chừng thì giữ đoạn đã viết và có nút **Chạy lại ngay**; đã gọi công cụ thì không bao giờ tự chạy lại.
- **Nhiều API key cho một nhà**, hiện thành danh sách đánh số: thêm, đổi tên, lên xuống, tắt, đổi key, gỡ. Key đang dùng được tô màu, key hết lượt ghi giờ mở lại. Gói thuê bao vẫn chỉ một tài khoản như cũ.
- **Mô hình việc nền** nằm ngay dưới, có Effort riêng; trên điện thoại bảng chọn trượt từ đáy lên, có nút đóng.

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
