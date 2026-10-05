# Đối chiếu Javis 0.66–0.77.1 cho MinMin 26.10.66

Cơ sở: MinMin main 5727c681 (26.10.65), các commit Javis tương ứng tới a8fe467b (0.77.1). Không nâng toàn bộ lên 0.81.

## Đã tích hợp

- 0.77.1: thay đổi env admin áp dụng lúc boot, lưu dấu vân tay có salt, giữ 2FA và hủy phiên khi reset. Env không đổi không ghi đè mật khẩu dashboard. Lần nâng cấp đầu chưa có dấu env: nếu env khác mật khẩu hiện tại thì áp dụng env; cần biết giá trị env đang dùng trước khi khởi động lại.
- 0.76: trang kỹ năng, chọn nhiều/xuất ZIP, nhập nhiều thư mục, chuẩn hóa nhóm, báo lỗi lưu và giữ phân trang.
- 0.74/0.75.1: lịch sáng/tối theo thiết bị; nền, font và màu MinMin giữ nguyên. Cache theme được đổi đồng thời cho hub và app ngoài.
- 0.71.1/0.74.2: chọn Codex mới nhất, truyền thư mục home rõ ràng và lỗi có hướng xử lý.
- 0.72.1: dấu vết khởi động MCP và lỗi Claude có bằng chứng. Trace chỉ trong RAM.
- 0.71.2: Live theo dõi việc song song, hỏi tiến độ và tự báo lúc yên lặng. Giữ bộ nhớ câu trả lời, nghe thử, đọc đầy đủ theo đoạn, dừng/đọc tiếp của MinMin.
- 0.73/0.74.1: công cụ mô tả ảnh trong brain và ảnh Zalo có chú thích đi tới bot. Ảnh tải từ CDN hợp lệ, kiểm tra chuyển hướng, giới hạn kích thước và đường dẫn. Không có ChatGPT hoặc tải lỗi thì trả lời trung thực chưa xem được ảnh.
- Hàm chọn bản dịch dùng chung hỗ trợ các lỗi mới, giữ ngôn ngữ mặc định của MinMin.

## Không chuyển nguyên khối

- 0.77 bộ phán xử tự điều chỉnh: MinMin có cơ chế luật và thư viện tệp được chủ duyệt khác upstream. Chưa triển khai tự đổi luật từ phản hồi; cần thiết kế, kiểm thử hoàn tác và quyền riêng trước khi bật.
- Slack/WhatsApp 0.71 là kênh mới, cần cấu hình ứng dụng/tài khoản thực tế. Không thêm kênh chưa được cấu hình vào lần sửa độ ổn định này.
- Không chuyển công cụ Zalo sẵn có sang Store; không tuyên bố hỗ trợ luồng Trả lời giúp chưa có trong MinMin. Giữ rào tiếp quản, nhóm và chỉ gửi tệp thuộc thư viện chủ duyệt.
- Màn đăng nhập nền đặc đã có. Không sao chép README, ảnh giới thiệu và bản dịch thương hiệu Javis vào MinMin.
- Đây không phải bản hoàn thiện Viral Studio tự quét. Chức năng đó vẫn cần bổ sung nguồn quét, lịch chạy, trạng thái và dữ liệu thật.

## Xác minh

Kiểm thử chuyên biệt cho mật khẩu/env/2FA, Codex home và CLI, lỗi Claude, nhập kỹ năng, lịch theme, ảnh Zalo, Live song song/tiến độ và hàng đọc. Bộ JS toàn ứng dụng và CI Linux toàn bộ phải xanh trước merge; build GHCR phải thành công trước cập nhật máy chạy.
