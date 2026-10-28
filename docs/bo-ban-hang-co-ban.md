# Bộ bán hàng cơ bản: 4 agent và 12 skill

Từ phiên bản 26.10.278, bộ mẫu đi kèm mã nguồn và Docker image. Khách tải ZIP bản mới, giải nén, cài và chạy bình thường. Không cần tải hoặc nhập gói thứ hai.

## Bắt đầu

Mở **Đội ngũ AI**, tìm nhóm **Bán hàng cơ bản**:

| Agent | Skill |
|---|---|
| Trợ lý kinh doanh POS | Báo cáo kinh doanh POS; Phân tích trạng thái đơn; Tổng hợp nhiều cửa hàng |
| Trợ lý quản lý Pancake | Báo cáo hội thoại Pancake; So sánh hiệu quả page; Hiệu suất nhân viên Pancake |
| Trợ lý hóa đơn | Tổng hợp hóa đơn mua bán; Tra cứu hóa đơn; Kiểm tra dữ liệu hóa đơn |
| Trợ lý báo cáo Google Sheets | Thiết lập báo cáo Google Sheets; Cập nhật báo cáo Google Sheets; Đối chiếu báo cáo Google Sheets |

Đăng nhập bộ não AI, nối tài khoản doanh nghiệp tại **Kết nối**. Chọn trợ lý và nhờ hướng dẫn thiết lập. Chưa nối thì bộ mẫu vẫn xuất hiện nhưng chưa lấy được dữ liệu thật.

Hồ sơ riêng nằm trong brain, tại `commercial/ho-so-doanh-nghiep.md`; ánh xạ Sheet tại `commercial/cau-hinh-bao-cao.md`. Không nhập bí mật vào các file này. Thông tin đăng nhập lưu qua màn hình Kết nối.

Ví dụ: "Đọc file Google Sheets này, đề xuất ánh xạ cột với số POS và Pancake để tôi duyệt. Sau đó điền báo cáo hôm qua, giữ công thức và không tạo dòng trùng."

## Máy đã cài

Cập nhật mã nguồn/bản phát hành rồi khởi động lại server. Bộ mẫu được đồng bộ vào các brain trong thư mục brain của bản cài, và brain ngoài khi được sử dụng. Không chép nguyên dữ liệu máy khác. Có thêm các skill hệ thống khác là bình thường; bộ thương mại gồm riêng 12 skill kể trên.

Nội dung khách sửa hoặc file cùng tên đã có được giữ nguyên. Mẫu đã xóa không tự cài lại; skill đã tắt vẫn tắt. Bản mẫu chưa sửa nhận nâng cấp từ app. Xem `commercial/BAT-DAU.md` trong brain để bắt đầu.

Bộ mẫu không cấp API key, không thay quyền kết nối và không mở khóa ứng dụng trả phí. Hóa đơn yêu cầu dữ liệu đã tải hoặc nguồn tương ứng; đây là hỗ trợ chuẩn bị dữ liệu, không tự kê khai, quyết toán hoặc kết luận nghĩa vụ thuế.
