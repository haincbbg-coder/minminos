# Nhật ký cập nhật

Lịch sử phiên bản MinMin OS. Bản mới nhất ở trên cùng. Xem ngay trong app tại nút **Cập nhật** trên thanh bên, hoặc **Tuỳ chỉnh → Cập nhật**.

Số phiên bản đánh theo lịch: `năm.tháng.lần` (26.10.1 = tháng 10 năm 2026, bản thứ nhất). Mỗi phiên bản là một khối `## [26.10.14] - 2026-10-01
### Cải thiện
- Hoá đơn: cấu hình API giải captcha, hỗ trợ mã tra cứu, chọn chứng từ Gmail để tải/xuất/in gộp; lọc kỳ, nhà cung cấp và sắp xếp số tiền.

## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [26.10.13] - 2026-10-01
### Sửa lỗi
- Giữ ảnh nền Trống đồng từ ZIP cổng thuế và ngắt dòng chữ ký dài khi in PDF.

## [26.10.12] - 2026-10-01
### Sửa lỗi
- Sửa nhận diện Chromium mới để tải được PDF Trống đồng; chỉ nhận file PDF mới tạo hợp lệ.
- PDF gốc thử thêm link trong XML khi cách tải của hãng thất bại, đọc PDF trong ZIP/base64 và ghép từ Gmail đã quét.
- Quét Gmail đọc cả ZIP đính kèm, ghép XML/PDF theo tên khi thư có nhiều hoá đơn và bổ sung file thiếu khi quét lại.
- Kết quả tải báo rõ hoá đơn còn thiếu file; ZIP xuất ra kèm danh sách đối soát từng file.

## [26.10.11] - 2026-10-01
### Thêm mới
- **Tải Hoá Đơn TCT đầy đủ như bản PC**: tách rõ tải XML thuế, PDF Trống đồng (bản thể hiện cổng thuế), PDF gốc của nhà cung cấp; giữ ZIP gốc cổng thuế; tải nhiều luồng song song.
- **Cài đặt tải**: tự ghép mẫu tên file hoá đơn và tên file Excel (có xem trước), chọn xếp thư mục theo tháng lập, theo nhà cung cấp hoặc theo ngày tải.
- **Xuất ra máy**: ZIP chọn loại file (giữ nguyên cây thư mục), HTML Trống đồng (.zip), gộp PDF để in hàng loạt. Mọi nút xuất áp dụng cho các dòng đã tích, hoặc cả khoảng ngày nếu không tích dòng nào.
- **Gmail ghép vào Tải Hoá Đơn TCT**: hoá đơn quét được trong Gmail tự gắn bản gốc PDF và XML vào đúng hoá đơn đã tra từ cổng thuế. Hoá đơn chưa có trong kho thì được thêm vào mục mua vào. Có nút Ghép lại khi vừa tra thêm kỳ mới.

## [26.10.10] - 2026-10-01
### Cải thiện
- Ẩn Điều khiển máy tính khỏi Kết nối ngoài và danh sách chọn ứng dụng khi tạo mã kích hoạt.

## [26.10.8] - 2026-10-01
### Thêm mới
- **Quét hoá đơn Gmail: Đăng nhập bằng Google.** Tài khoản bật xác minh 2 bước kiểu g.co/sc, mã PIN, khoá bảo mật giờ quét được: bấm nút, đăng nhập ngay trên trang Google, MinMin chỉ nhận quyền đọc thư. Cài Google OAuth Client một lần, trang có hướng dẫn từng bước.
- **Nhiều tài khoản Gmail**: thêm bao nhiêu hộp thư tuỳ ý (Google hoặc mật khẩu ứng dụng), chọn hộp thư khi quét, bảng kết quả ghi rõ hộp thư nguồn.
### Sửa lỗi
- Dán nhầm mật khẩu Gmail thường giờ bị chặn ngay lúc lưu, kèm lời chỉ dẫn, thay vì quét xong mới báo lỗi tiếng Anh khó hiểu.

## [26.10.7] - 2026-10-01
### Thêm mới
- **Tải Hoá Đơn TCT chạy trên trình duyệt** (Kết nối ngoài, cần mã kích hoạt): lưu nhiều doanh nghiệp, đăng nhập cổng hoadondientu.gdt.gov.vn bằng captcha ngay trên trang, tra cứu mua vào / bán ra (cả hoá đơn máy tính tiền), tải XML và PDF gốc của hãng, xem hoá đơn, xuất Excel, bảng kê thuế GTGT, chi tiết mặt hàng, ZIP, và xem cảnh báo.
- **Quét hoá đơn Gmail**: nhập Gmail + mật khẩu ứng dụng, quét hộp thư lấy hoá đơn đính kèm (XML, PDF) và mã tra cứu, lần sau chỉ quét email mới. Xuất Excel và ZIP.
### Bảo mật
- Mật khẩu cổng thuế, phiên đăng nhập và mật khẩu ứng dụng Gmail được mã hoá trên máy chủ.

## [26.10.6] - 2026-10-01
### Thêm mới
- Lead Engine: thêm hồ sơ doanh nghiệp, kho lead có dẫn chứng hội thoại và bản nháp quảng cáo/chăm sóc theo từng brain.
- Có bảng theo dõi đơn giao thành công và chi phí đã nhập, chống cộng lặp khi đồng bộ lại. Bản đầu chưa tự gửi tin hoặc chạy quảng cáo.

## [26.10.5] - 2026-10-01
### Cải thiện
- **Mã kích hoạt của TrungKienHa có hiệu lực trên mọi bản MinMin**: gắn khoá công khai của nhà phát hành, nên mã cấp cho khách được máy khách nhận và mở đúng app.

## [26.10.4] - 2026-10-01
### Thêm mới
- **Zalo Forwarder chạy ngay trên trình duyệt**: trong Kết nối ngoài, thẻ Zalo Forwarder có nút **Mở** (cần mã kích hoạt). Đủ các tính năng của bản máy tính: đăng nhập Zalo bằng mã QR, nhiều tài khoản cùng lúc, tuyến chuyển tiếp có biên tập giá / thương hiệu / link, AI soạn tin, đăng nhóm hàng loạt kèm ảnh, nhắn bạn bè, nhật ký trực tiếp.
- **Mỗi tài khoản Zalo một môi trường riêng**: trình duyệt riêng cố định cho từng tài khoản, và ô **proxy riêng** khi đăng nhập để các tài khoản không chung địa chỉ mạng.
- Đang chuyển tiếp mà MinMin cập nhật hay khởi động lại thì **tự chạy lại**, không phải vào bấm.

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
