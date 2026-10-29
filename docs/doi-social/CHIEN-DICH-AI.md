# Chiến dịch AI và profile — 26.10.303

Vào **Đội Social → Chiến dịch AI · một prompt**. Chọn tài khoản/Trang và giọng văn,
nhập ý tưởng cùng giờ hoặc tần suất, chọn nguồn ảnh rồi bấm **Tạo chiến dịch từ prompt**.
Không cần tạo hồ sơ sản phẩm để viết từ ý tưởng. Có thể tiếp tục dùng Viết bài AI trong Kho nội dung.

## Nội dung và lịch

- AI lập kế hoạch một lần, theo giờ/ngày trong tuần hoặc khoảng cách từ 30 phút đến 30 ngày.
  Không có lịch trong prompt thì tạo một lượt ngay. Múi giờ mặc định Asia/Ho_Chi_Minh.
- Mỗi đích có giọng văn và nội dung riêng. Bài viết trùng bị từ chối, không nhân bản để lấp số lượng.
- Mặc định tạo nháp chờ duyệt. Bật **Cho phép tự duyệt và đăng theo lịch** để dùng hàng đợi đăng
  hiện có. API Fanpage dùng kết nối Trang; nick trình duyệt cần Worker online và phiên đăng nhập.
- “Đã tạo nháp / vào hàng đợi” không xác nhận bài đã công khai. Xem trạng thái từng bài trong
  Bài đăng hoặc Duyệt nội dung. Tạm dừng chiến dịch ngăn lượt tạo mới; bài đã duyệt cần dừng ở hàng đợi.
- Giới hạn mặc định 5 lượt nội dung và 5 lượt tạo ảnh/ngày; chỉnh từ 1 đến 24. Lượt nội dung được
  tính theo ngày hẹn, lượt gọi tạo ảnh tính theo ngày gọi. Khởi động lại giữ mã tác vụ/nháp đã tạo.
- Chưa rõ kết quả một lệnh tạo ảnh thì báo cần kiểm tra; không tự gọi tạo ảnh lại. Ba lượt lỗi liên
  tiếp đưa chiến dịch sang Cần kiểm tra. Sửa kết nối trước khi tiếp tục lịch. Lượt lỗi không tự chạy lại.

## Ảnh và video

Chọn chữ, media tải lên/kho, một thư mục ảnh trên máy cài MinMin, hoặc MCP tạo ảnh.
Thư mục ảnh không phải đường dẫn PC Worker. Đọc một ảnh mỗi lượt, không quét thư mục con.
Ảnh nhập từ MCP/thư mục cần JPEG/PNG/WebP, tối đa 15MB và 40 megapixel. YouTube cần một
video có sẵn; không nhận ảnh thay video. Instagram/TikTok cần ảnh hoặc video.

MCP lấy từ **Kết nối** của chính MinMin. Thêm Higgsfield/MCP mới tại đó rồi tải danh sách công cụ.
Công cụ tạo ảnh cần kết nối Toàn quyền và vẫn qua cổng quyền/audit hiện có. Điền tham số JSON
theo schema (model, kích thước… tuỳ nhà cung cấp). Biến hỗ trợ: `{{prompt}}`, `{{image_prompt}}`,
`{{job_id}}`. Nhà cung cấp trả mã tác vụ cần công cụ kiểm tra trạng thái và mẫu JSON tương ứng.
Không dùng thông tin đăng nhập của dịch vụ ChatGPT để cấu hình MinMin.

## Profile VPS và máy tính

Trong Chrome MinMin chọn vị trí chạy. Mỗi vị trí có bảng tên, nhóm, proxy, nơi lưu, trạng thái,
tìm kiếm/lọc nhóm và lựa chọn nhiều profile. Tạo tối đa 100 profile; cùng lúc mở tối đa theo hạn
mức hiện có (mặc định 3), không mở cả trăm trình duyệt chỉ vì đã tạo cả trăm profile.

Tạo lô bằng mẫu `Shop {n}`, số bắt đầu/số chữ số, hoặc mỗi dòng một tên. Proxy chấp nhận
HTTP/HTTPS/SOCKS5, URL hoặc `IP:PORT:USER:PASS`; một dòng dùng chung hoặc đúng N dòng
cho N profile. Chọn nhiều profile để gom nhóm, đổi/bỏ proxy. Đóng profile trước khi sửa cấu hình.
Mật khẩu được che trong danh sách, mã hoá trên VPS/hàng đợi Worker; bridge loopback giữ mật
khẩu khỏi dòng lệnh Chrome. Proxy hỏng trả lỗi, không chuyển sang mạng trực tiếp.

Đường dẫn lưu là đường dẫn tuyệt đối trên **máy chạy Chrome đã chọn**. Đổi mặc định chỉ áp
dụng cho profile mới; profile cũ giữ đường dẫn cũ. Thư mục có Local State/Cookies không được
nhận làm nơi tạo profile mới. Phiên Chrome/Cốc Cốc có sẵn vẫn dùng cơ chế cho phép kết nối
của trình duyệt; không sao chép cookie và không áp proxy của MinMin lên phiên cá nhân đó.

## Tác vụ từng tạm dừng

Nút **Máy ở nhà → Kiểm tra Sheet (không đăng)** và công cụ `up_bai_kiem_tra` trả bằng chứng:
Page nào bật, số dòng, Page ID, có link media hay không, lý do bỏ qua, thứ tự UP NGAY (mới nhất trước).
Không sửa Sheet/không đăng. Pipeline native bỏ Page tắt hoặc chưa có cấu hình thay vì mặc định bật.
Không tự bật lại vòng đã bị hậu kiểm tạm dừng; cần đối chiếu dữ liệu và xác minh kết quả đăng thật.

## Kiểm chứng

Test dùng SQLite thật, HTTP routes thật, proxy socket HTTP/SOCKS5 nội bộ, Worker ghép thử,
Chromium trên Windows và Linux. AI/MCP/phía mạng xã hội được thay bằng fixture; không đăng
bài thật và không gọi tạo ảnh tính phí trong CI. Kết nối tài khoản thật và máy Worker thật vẫn
cần kiểm chứng tại nơi vận hành trước khi giao chiến dịch tự đăng.
