# Dựng video từ tư liệu thật

Vào Xưởng video → Ảnh/clip của tôi, chọn ảnh/clip và tạo dự án. Đổi thứ tự,
bỏ/thêm cảnh, nhập lời từng cảnh rồi bấm Lưu và dựng video. Kết quả có xem trước,
tải MP4 và SRT (khi có phụ đề). Bỏ cảnh không xóa file gốc khỏi khay dự án.

Chọn Không lời đọc, Edge TTS, ElevenLabs đã kết nối hoặc file thu âm riêng.
Edge gửi lời cảnh tới Microsoft; ElevenLabs dùng cấu hình và chi phí hiện có.
Edge có thể từ chối kết nối: app báo lỗi và cho chọn nguồn khác, không tự chuyển
sang dịch vụ tính phí. Nhạc nền và lời đọc có âm lượng độc lập.

## Giới hạn

- 1–30 cảnh, mỗi cảnh 1–30 giây, tổng thời lượng đặt tối đa 180 giây.
  Lời đọc sinh theo cảnh có thể kéo dài cảnh; bản cuối không quá 5 phút.
- Clip ngắn được lặp, âm thanh gốc bị tắt. Chọn giữ trọn hình hoặc cắt lấp đầy.
- Edge dùng mốc lời khi dịch vụ trả về. Nếu không có mốc, phụ đề theo cảnh.
  File lời đọc riêng phát từ đầu, cắt theo thời lượng video; không nhận dạng lời
  nói hoặc tự căn từng từ. Chưa có Whisper.
- Render CPU bằng FFmpeg, mỗi tiến trình máy chủ dựng một bản tư liệu cùng lúc.
  Các lượt dựng được lưu riêng tới khi xóa dự án.
- Chưa bổ sung kho stock, quét xu hướng hoặc kết nối đăng mạng xã hội mới.
  Các kết nối xuất bản hiện có giữ nguyên.

## Kiến trúc và nguồn tham khảo

Workflow lấy cảm hứng từ [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo):
tư liệu → lời đọc → phụ đề/nhạc → MP4. Đây là triển khai native dùng FFmpeg của
MinMin, không nhúng worker hay sao chép mã nguồn MoneyPrinterTurbo.

Manifest của từng dự án giới hạn đầu vào; không nhận URL/path tùy ý. FFmpeg và
ffprobe chỉ được đọc giao thức file/pipe. API vẫn qua cổng giấy phép hiện có.
Không chỉnh bản dựng hoặc upload trong lúc tác vụ đang chạy.

Kiểm thử: `python tests/run.py xuong_video -v`. Test dựng thật có ảnh, clip, audio,
nhạc, phụ đề; kiểm tra API giấy phép, file ngoài dự án, tải attachment và khởi
động tác vụ nền. Test timing TTS giả lập nhà cung cấp, vẫn render FFmpeg thật.
