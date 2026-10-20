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

## Vòng công cụ (26.10.179)

Nút tròn ở góc dưới mở sáu múi: Thêm file, Khay file, Sửa ảnh, Ghép ảnh, Gộp PDF,
Tải file. Chọn file trong khay rồi mở vòng để xử lý. Thả file vào vòng cũng thêm được.
Mỗi múi có phản hồi màu/nổi/lún. Tiếng tách được tạo cục bộ, chỉ khi bấm; công tắc âm
thanh ghi nhớ trên trình duyệt. Không tải âm thanh bên ngoài. Mũi tên chuyển múi,
Enter/Space kích hoạt, Escape hoặc nút giữa thu lại. Tôn trọng giảm chuyển động.


## Vòng con (26.10.180)

Chọn file mở vòng tối đa sáu file mỗi trang; chọn nhiều file qua các trang rồi bấm
Dùng file đã chọn. Mỗi file hiện ảnh thu nhỏ và tên đầy đủ khi trỏ/đặt focus. Sửa ảnh
mở vòng Cắt tỷ lệ, Xoay, Định dạng, Chiều rộng, Chú thích, Lưu bản sao. Tỷ lệ,
định dạng và kích thước mở tiếp vòng con; tâm vòng quay lại cấp trước. Bản xem trước
nằm cạnh vòng trên máy tính và phía trên trên điện thoại. Không tạo khay hay dialog
chỉnh ảnh hình chữ nhật. Tải / xem mở vòng tải, xem, sắp thứ tự và bỏ bản sao.
PDF mở trong trình xem PDF của trình duyệt; hộp chọn file vẫn dùng hộp hệ điều hành.

### Linh thú trong nút công cụ (26.10.181)

Trên dashboard, linh thú đang chạy được đặt trong nút vòng công cụ; giữ nguyên màu, hình dáng và trạng thái. Nhánh Linh thú mở các lối tắt cũ bằng vòng con. Tắt linh thú trả lại biểu tượng công cụ; trang không nạp linh thú vẫn dùng nút công cụ bình thường.

### Chọn, xử lý và tải kết quả (26.10.182)

Mở Sửa ảnh, Ghép ảnh hoặc Gộp PDF luôn qua bước chọn file và nút thực hiện có tên
tương ứng. Sửa ảnh cho chọn tỷ lệ cắt giữa, xoay, định dạng và chiều rộng rồi Lưu kết quả.
Kết quả ảnh có bản xem trước; ảnh và PDF đều có nút Tải kết quả ngay bên dưới vòng.

Bấm lại một file để bỏ chọn, hoặc Bỏ chọn tất cả để xoá lựa chọn qua mọi trang.
Đóng vòng bằng ×, Escape, nút giữa hoặc Đóng cũng xoá lựa chọn và bản xem trước.
Các file vẫn ở khay để dùng lại; muốn bỏ bản sao lưu trong khay, mở Tải / xem,
chọn file rồi Bỏ khỏi khay. File gốc trên máy không thay đổi.

### Chuyển mục đích (26.10.183)

Đổi công cụ rồi chọn công cụ mới luôn xoá lựa chọn cũ. Gộp PDF mặc định chỉ liệt kê
PDF; muốn chèn ảnh vào PDF thì bật Hiện thêm ảnh để đưa vào PDF. Mỗi công cụ có nút
Thêm PDF/Thêm ảnh/Thêm file ngay trong màn chọn. Thêm từ máy hoặc kéo thả giữ nguyên
công cụ, chọn các file vừa thêm và mở trang chứa file mới.

Nút Bỏ file đã chọn khỏi khay yêu cầu xác nhận số bản sao trước khi bỏ; file gốc
trên máy không bị xoá. Bỏ chọn tất cả chỉ bỏ dấu chọn, còn Đổi công cụ không xoá dữ liệu.
