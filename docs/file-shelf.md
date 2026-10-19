# Khay làm việc

Khay giữ bản sao file trên trình duyệt đang sử dụng (IndexedDB), tách theo tên tài khoản
MinMin và origin. Không đồng bộ giữa thiết bị. Có thể mở khay ở Hộp thư, Hóa đơn / Bộ chứng
từ, hub phụ, Viral Studio và Xưởng video. Dữ liệu vẫn còn sau tải lại hoặc chuyển trang.
Không dùng khay như nơi sao lưu lâu dài: xóa dữ liệu trình duyệt sẽ xóa cả khay.

## Bản đầu

- Hộp thư: mỗi ảnh Zalo có nút **Thêm vào khay**. Ảnh được lấy qua máy chủ MinMin để chỉnh
  sửa được khi CDN không cho phép CORS. Chỉ CDN Zalo HTTPS; kiểm tra mọi redirect, tối đa
  20 MB, xác minh ảnh, xóa file tạm. Không gửi nội dung tới AI hoặc dịch vụ chuyển đổi.
- Hóa đơn / Bộ chứng từ: **Thêm PDF vào khay** lấy bản PDF đã có; không tự tìm bản gốc còn
  thiếu. Có thể thêm các file chứng từ đã xuất từ máy bằng kéo thả / chọn file.
- Khay: chọn nhiều file, thay thứ tự bằng nút lên/xuống, bỏ từng bản sao, tải từng file.
- Ảnh PNG/JPG/WebP: xem trước, xoay, cắt giữa theo tỷ lệ, đổi kích thước, chú thích dưới ảnh,
  xuất bản sao PNG/JPG/WebP. Ghép 2–9 ảnh thành một ảnh PNG dạng lưới.
- Gộp PDF và ảnh đã chọn thành PDF theo thứ tự khay (ảnh thành trang A4, giữ tỷ lệ).
  PDF có mật khẩu không được bỏ qua; báo lỗi theo tên file. Xem trước và tải PDF để in.

Giới hạn: 40 file, 20 MB/file, 100 MB/khay; gộp tối đa 200 trang. Các ảnh đầu vào để xử lý
tối đa 24 megapixel, ảnh chỉnh xuất tối đa 16 megapixel. File không hỗ trợ chỉnh vẫn có thể
lưu/tải. Không có chuyển đổi Word, xử lý video/audio, tự đăng bài, menu toàn hệ điều hành
hay tự đính kèm file vào bản nháp ở bản đầu này.

## Phụ thuộc và hoàn tác

`pdf-lib` 1.17.1 (MIT) được đóng gói trong `dashboard/vendor`, nạp lười khi gộp PDF; không
phụ thuộc CDN lúc sử dụng. Giấy phép nằm cạnh file. Các phép chỉnh ảnh dùng Canvas.

Thay đổi không ghi đè file gốc hoặc thay đổi schema máy chủ. Có thể revert commit phát hành
bằng một PR và phát hành phiên bản kế tiếp. Dữ liệu khay cũ vẫn ở trình duyệt; khi bật lại
tính năng có thể đọc lại. Không xóa IndexedDB khi rollback.
