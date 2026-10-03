# MinMin Viral Studio

Ứng dụng trong **Kết nối ngoài**, đường dẫn `/apps/viral-studio/`, mã giấy phép `viral_studio`.
Giao diện dùng font, nền, bóng nổi và chế độ sáng/tối chung của MinMin.

## Phạm vi phát hành

- Danh sách kênh bền vững, chia nhóm theo chiến dịch/ngành/đối thủ, tạm dừng theo dõi.
- Bảng bài nổi bật từ nguồn đã nhập hoặc đã kết nối: lọc nền tảng, nhóm, từ khóa,
  lượt xem; lưu ý tưởng; phân trang; xuất CSV chống công thức.
- Chuẩn hóa URL và số liệu Facebook, TikTok, Douyin, Xiaohongshu, YouTube, Instagram,
  Threads. Thiếu số liệu hiển thị “—”; chỉ tính điểm khi có ngày và đủ ba loại tương tác.
- Xưởng nội dung: AI viết góc nhìn mới theo thương hiệu, lưu bản nháp có liên kết nguồn.
- Facebook Page: duyệt bài chữ, đăng ngay hoặc hẹn giờ khi MinMin đang chạy. Nền tảng
  khác xuất CSV; chưa đăng ảnh/video trực tiếp. Không tự đăng nội dung AI chưa duyệt.

## Kết nối nguồn thật

Tạo Apify Task dùng Actor phù hợp nền tảng và kênh/từ khóa, chạy thành công và đặt lịch
trong Apify. Lưu Task ID trong kênh và token tại Kết nối. MinMin chỉ đọc tối đa 500 bài
từ dataset của lần chạy thành công gần nhất; không tự chạy Actor có phí. Mỗi Task cần
được người dùng cấu hình đúng nguồn của kênh. Dataset cũ không làm mới ngày quan sát.
Cho phép khớp trường JSON riêng khi Actor trả tên trường khác. Có thể nhập JSON thủ công.
Đây không phải nguồn thống kê toàn bộ mạng xã hội. Độ phủ và độ mới phụ thuộc Task,
lịch chạy, quyền truy cập và dữ liệu nhà cung cấp trả về.

AI dùng key riêng hoặc key nhà cung cấp đã lưu trong MinMin; phải chọn đúng model.
Facebook cần Page ID, phiên bản Graph API còn được hỗ trợ và Page access token có
quyền đăng. Kết nối ứng dụng Meta và các quyền cần được chủ Trang cấp ngoài ứng dụng.
Không có token nên không thể xác minh bài đăng thật trong kiểm thử tự động.

## Thu phí

Dùng hệ thống mã ký số Ed25519 hiện có: nhà phát hành tạo mã riêng cho `viral_studio`,
gắn máy khách và ngày hết hạn. Hiện dùng “liên hệ kích hoạt”; không tích hợp cổng thanh
toán hay tự trừ tiền. Phí Apify và AI của khách tính riêng. Bản MinMin triển khai riêng
cho từng khách; chưa phải SaaS nhiều tổ chức trong một kho dữ liệu chung.

## Lưu trữ và vận hành

SQLite tại `<STATE_DIR>/viral-studio/studio.sqlite`; backup cùng STATE. Các token lưu
mã hóa qua `secrets_store`; API trạng thái chỉ trả cờ đã cấu hình. API có cổng giấy phép,
điều khoản chung và bảo vệ đăng nhập/CSRF của MinMin. Giới hạn 200 kênh, 10.000 bài,
2.000 bản nháp. Phần AI/chuyển đổi gửi nội dung tham khảo đến nhà cung cấp đã chọn.
Không có cơ chế tự thử lại bài đăng có kết quả không rõ: trạng thái “Cần kiểm tra” yêu
cầu xem Trang để tránh đăng trùng. Khởi động lại giữa lúc gửi cũng giữ trạng thái này.

## Tham khảo sản phẩm và API

Nghiên cứu giao diện [Kingcontent](https://kingcontent.pro/tinh-nang): quản lý kênh,
bài nổi bật, nội dung đã lưu, AI nội dung và lịch đăng được chọn cho bản này. Các phần
video AI, chỉnh video, thư viện mẫu, quảng cáo và đăng chéo video chưa có trong bản này.
Không sao chép mã nguồn hoặc tài sản của Kingcontent.

- [Apify API](https://docs.apify.com/api/v2)
- [Lần chạy Task gần nhất](https://docs.apify.com/api/v2/actor-task-runs-last-get)
- [TikTok Content Posting](https://developers.tiktok.com/doc/content-posting-api-get-started)

Kiểm thử: `python tests/python/test_viral_studio.py`, `test_ket_noi_ngoai.py`,
`test_route_table.py`, `node --check apps/viral-studio/web/app.js`. Mock mọi gửi bài/API
bên ngoài; kiểm tra nhập, bộ lọc, lưu nhóm và bản nháp qua giao diện localhost riêng.
