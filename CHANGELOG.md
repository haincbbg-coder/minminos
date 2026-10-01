# Nhật ký cập nhật

Lịch sử phiên bản MinMin OS. Bản mới nhất ở trên cùng. Xem ngay trong app tại nút **Cập nhật** trên thanh bên, hoặc **Tuỳ chỉnh → Cập nhật**.

Số phiên bản đánh theo lịch: `năm.tháng.lần` (26.10.1 = tháng 10 năm 2026, bản thứ nhất). Mỗi phiên bản là một khối `## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [26.10.3] - 2026-10-01
### Thêm mới
- **Mục Kết nối ngoài** trong nhóm Kết nối & khách: nơi chứa các app riêng của TrungKienHa (Zalo Forwarder, Tải Hoá Đơn TCT, Quét hoá đơn Gmail, Điều khiển máy tính). Mỗi app mở khoá bằng **mã kích hoạt**, khoá theo máy và thời hạn. Các app đang được chuyển dần lên trình duyệt, thẻ hiện "Sắp ra mắt".
- **Máy nhà phát hành** (giữ khoá riêng) tự mở mọi app và có khung **tạo mã kích hoạt** cho khách ngay trong trang.
- **Điều khoản sử dụng**: lần đầu mở MinMin phải đọc và bấm đồng ý. Tự động hoá Zalo và Điều khiển máy tính có điều khoản riêng, hỏi thêm khi mở app.

## [26.10.2] - 2026-10-01
### Cải thiện
- **DeepSeek và Kimi K3 gọi công cụ ổn định hơn** qua OpenRouter và OpenAI Compatible: MinMin giữ lại phần "suy nghĩ" của model giữa các vòng gọi công cụ (đọc POS, Ads, Zalo, file...), đúng như hai hãng yêu cầu. Trước đây phần này bị bỏ nên việc nhiều bước có thể lỗi hoặc trả lời kém.
- Gợi ý model OpenRouter mặc định thêm DeepSeek V4.1 Flash và Kimi K3.

## [26.10.1] - 2026-10-01
### Thêm mới
- **Nút Cập nhật ngay trên thanh bên**, dưới nhóm Thiết lập. Bấm vào là MinMin hỏi "Có bản mới, cập nhật ngay?" với hai nút Đồng ý / Không. Có bản mới thì nút đổi màu có chấm đỏ, và một thẻ báo hiện lên ở góc màn hình.
- **Mắt Nhà thành ứng dụng trong Chợ MinMin** (mục Ứng dụng MinMin): cài thì hiện ở nhóm Kết nối & khách, gỡ thì ẩn khỏi thanh bên.
### Cải thiện
- **Đánh số phiên bản mới theo lịch**, bắt đầu từ 26.10.1. Nhật ký các bản cũ đã dọn.
- Thanh bên gọn hơn: ẩn Kho tài liệu và nhóm Xưởng code (các trang vẫn còn, không mất dữ liệu).
