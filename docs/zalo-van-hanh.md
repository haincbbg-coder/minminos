# Vận hành Zalo trong MinMin

Bản 26.10.195 đưa công cụ chăm khách vào **Kết nối & Khách → Hộp thư khách**. Dùng kho
hội thoại và kết nối hiện có, không cần mua gói LohaZalo hoặc tạo một hộp thư thứ hai.

## Sử dụng

1. Kết nối tài khoản Zalo bằng QR ở Nguồn dữ liệu. Trong Hộp thư khách → Tài khoản bot,
   bật ghi hội thoại cho tài khoản cần theo dõi. Chỉ tin đã được adapter ghi vào kho mới
   xuất hiện; không hứa tải toàn bộ lịch sử từ trước khi kết nối.
2. Mở một hội thoại → **Hồ sơ**. Lưu tên người phụ trách, thẻ và ghi chú. Hai cửa sổ cùng
   sửa một hồ sơ: cửa sổ cũ phải mở lại trước khi lưu để tránh ghi đè. Trong nhóm, hồ sơ
   gắn với khách đã được liên kết; không phải một hồ sơ chung cho mọi thành viên.
3. Lọc **Chưa đọc** hoặc nhập tên thẻ ở thanh bộ lọc. Thẻ khớp nguyên tên, áp dụng trước
   phân trang. Số tổng quan cũ vẫn tính theo kênh/tài khoản, không phải theo thẻ.
4. Tab **Vận hành → Mẫu trả lời dùng chung**: tạo mã như `chao`, nội dung có `{tenKhach}`.
   Bấm mẫu cũ để sửa; lưu cùng mã sẽ cập nhật mẫu. Trong hội thoại, chọn **Mẫu trả lời**
   hoặc gõ `/chao` và Enter: mẫu được chèn thành nháp, đọc lại rồi bấm Gửi. Lệnh không
   tồn tại được báo lỗi, không gửi nguyên mã lệnh cho khách.
5. Nếu tài khoản đã gắn Chatbot, dùng **AI gợi ý** hiện có hoặc **Hồ sơ → AI tóm tắt**.
   Tóm tắt chỉ đọc, không gửi tin, không tạo đơn. Nó dùng trích đoạn cuối tối đa 60 tin /
   12.000 ký tự và có thể bỏ sót ngữ cảnh trước đó. Bot chưa gắn thì nút tóm tắt bị khóa.
6. Trong **Vận hành**, chọn kênh, cửa sổ trượt 24 giờ / 7 ngày / 30 ngày và mục tiêu
   phản hồi. Bấm Mở ở khách đang chờ để về đúng hội thoại. Bấm Làm mới để cập nhật số.

## Bản 26.10.306: bot Zalo cá nhân

- **Bot đọc file khách gửi** (PDF, Word .docx, Excel .xlsx, file chữ), tải từ CDN Zalo vào
  `attachments/zalo/<chat>/tep/` của brain bot. Trong nhóm: gửi file rồi gọi bot trong 10 phút vẫn được (chỉ người gửi).
- **Chat riêng ở chế độ Tự phán đoán**: câu khó (giá riêng, khiếu nại, hoàn tiền) bot im và báo chuông,
  một lần mỗi 10 phút mỗi cuộc chat. Bot tự tách câu dài thành tối đa 4 tin ngắn.
- **Tag Zalo của cuộc chat** (Gia đình, Khách...) đọc bằng `label list` của chính gói zalo-agent-cli đã
  ghim, ở nền mỗi 10 phút. Form bot có ô "Không trả lời các cuộc chat có tag Zalo".
- Zalo báo gửi thành công mà không có id tin thì coi là **chưa gửi**: Hộp thư có dòng báo, chuông kêu.

Chưa làm vì zalo-agent-cli 1.6.2 (bản mới nhất trên npm) không có: đọc/thả cảm xúc qua MCP, đọc
ghi chú ghim của nhóm. Javis dùng bản CLI riêng (javis-zalo 1.7, 1.8) cho hai việc này.

## Ý nghĩa báo cáo

- Một đợt chờ bắt đầu ở tin khách đầu tiên sau lần đáp trước và kết thúc ở lần đáp đầu
  của người hoặc AI. Khách nhắn tiếp không làm lại đồng hồ. Tin hệ thống không kết thúc
  đợt chờ. Hội thoại đóng không nằm trong backlog.
- Các mẫu phản hồi tính trong cửa sổ trượt đã chọn, thời gian liên tục (gồm ngoài giờ),
  và gồm phản hồi AI. Một đợt bắt đầu trước cửa sổ không được dùng làm mẫu SLA của kỳ.
- Backlog dùng toàn bộ lịch sử còn lưu, không chỉ kỳ báo cáo. Bảng hiện tối đa 100 dòng;
  tổng số chờ/quá mục tiêu vẫn tính đầy đủ. Hội thoại nhóm bị cắt lịch sử chỉ đo được
  trên phần còn giữ.
- Bảng người gửi dùng tên ghi trên tin nhắn. Dữ liệu cũ thường chỉ ghi “Bạn”, nên không
  tách được hiệu suất từng nhân viên. Nhãn “Người phụ trách” không dùng để giả định ai đã gửi.
- Nhật ký ghi lưu hồ sơ, lưu mẫu, gửi tay, gợi ý, đổi chế độ, tóm tắt từ bản này. Không
  hồi dựng thao tác trước đây và không bao trùm mọi luồng quản trị khác của hệ thống.
  CSV xuất tối đa 500 thao tác gần nhất. API không có sửa/xóa nhật ký; SQLite có trigger
  chặn UPDATE/DELETE thông thường. Người quản trị máy chủ vẫn có quyền sửa file hoặc trigger.

## Đối chiếu khảo sát LohaZalo

Nguồn khảo sát ngày 21/10/2026: [trang giới thiệu và hướng dẫn](https://lohatech.vn/san-pham/lohazalo).
Đã đọc khối tổng quan, toàn bộ hướng dẫn theo mục, so sánh, bảng giá và FAQ. Đây là khảo
sát nội dung công khai, chưa đăng nhập hay kiểm thử nội bộ dịch vụ LohaZalo.

| Mục được khảo sát | Áp dụng trong MinMin | Trạng thái |
| --- | --- | --- |
| Tài khoản và tình trạng kết nối | QR nhiều tài khoản, trạng thái adapter, lỗi đồng bộ ở Tài khoản bot | Có sẵn; không gọi lỗi adapter là bằng chứng tài khoản đã bị khóa |
| Xử lý hội thoại | Hộp thư chung, tìm kiếm, đọc/đáp, tiếp quản, phân trang và ảnh | Có sẵn; thêm đường từ báo cáo về đúng cuộc chat |
| Thẻ phân loại | Thẻ, ghi chú và tên phụ trách ngay trong Hồ sơ; lọc thẻ chính xác | Đã bổ sung giao diện và API |
| Kịch bản dùng lại | Quản lý mẫu, chọn mẫu hoặc /lệnh, thay biến tên trong bản nháp | Đã bổ sung |
| Trợ lý chăm khách | Dùng Chatbot, tài liệu brain và tính năng thử bot hiện có | Có sẵn; cần người dùng cấu hình bot/tri thức thực tế |
| Tổng hợp nội dung | Tóm tắt trích đoạn hội thoại qua engine của Chatbot ở quyền chỉ đọc | Đã bổ sung; chưa phải tự động phân loại khách bằng AI |
| Trợ lý hỏi số liệu | Chat MinMin có công cụ hiện có; thêm báo cáo xác định từ kho hội thoại | Chưa thêm tool chuyên biệt để AI hỏi đáp báo cáo mới |
| Luồng AI và bàn giao | Gợi ý rồi người gửi; bot chạy tự động tùy cấu hình; tiếp quản để dừng AI | Có sẵn từng phần; chưa có ba chế độ mới thống nhất theo mọi tài khoản |
| Nhân sự và phân quyền | Phiên quản trị chung; nhãn người phụ trách để điều phối | Chưa có tài khoản nhân viên và ACL riêng từng Zalo; cần thiết kế xác thực toàn hệ thống |
| Truy vết | Nhật ký thao tác mới, chỉ thêm qua API, xuất CSV | Đã bổ sung; không cam kết bất biến trước chủ máy chủ |
| Tổng quan vận hành | Lượng tin theo nguồn gửi, khách mới, chưa đọc, biểu đồ giờ và backlog | Đã bổ sung, cập nhật khi mở/làm mới; không gọi là realtime push |
| Hiệu quả AI | Đếm tin AI thực sự lưu trong kho | Chưa có tỷ lệ tự xử lý/bàn giao, chi phí từng tính năng và lead lớn đã xác minh |
| SLA | Thời gian đợt chờ, mục tiêu, số đợt đạt, trung bình và lâu nhất theo tên gửi | Đã bổ sung; chưa có lịch giờ làm việc hoặc danh tính nhân viên riêng |
| Báo cáo định kỳ | Nền lịch tự chạy của MinMin có sẵn | Chưa tạo lịch mới hoặc gửi báo cáo ra ngoài thay người dùng |
| Hạn chế tần suất gửi | Tái sử dụng giới hạn bot/kênh hiện có | Không chứng minh được “không bao giờ bị khóa”; chưa có bộ giới hạn chung mới cho mọi đường gửi |
| Gói thương mại | Các gói/ghế dùng, hạn mức AI, hỗ trợ và hạ tầng của bên cung cấp | Không sao chép giá, hạn mức SaaS hoặc SLA hạ tầng sang MinMin tự lưu trữ |

### Các điểm cần kiểm chứng trước khi mở rộng

Trang nguồn mô tả tự động trả lời trong phần hướng dẫn/bảng giá, nhưng FAQ nói AI chỉ
soạn gợi ý. Vì vậy hai hành vi phải được tách rõ trong MinMin, không tự bật trả lời cho
các tài khoản hiện có. Tốc độ quảng cáo khoảng 0,18 giây không phải kết quả đo của MinMin.
Lưu tin đã thu hồi phụ thuộc adapter nhận và lưu được tin trước đó; bản này không có
tính năng khôi phục tin chưa từng đồng bộ. Không thể bảo đảm khách không xuất dữ liệu
qua ảnh chụp màn hình chỉ bằng việc đặt nhãn phụ trách.

Phần cần ưu tiên ở đợt tiếp theo là danh tính nhân viên và ACL kiểm tra ở server cho
mọi API cũ/mới, sau đó mới phân công theo danh tính và đo SLA từng người. AI tự gắn thẻ,
báo cáo tự động, lưu sự kiện thu hồi và giới hạn gửi dùng chung cần thiết kế luồng chạy
thật cùng kiểm thử độc lập; chưa được đánh dấu đã triển khai trong bản này.

## Kiểm thử

`python tests/run.py conversation_ops hoi_thoai_crm security route_table bot_zalo_ca_nhan zalo_gom_tin`

Test mới dùng SQLite tạm và engine giả, không gửi khách hay đăng nhập Zalo thật. Kiểm tra
giao diện dùng dữ liệu tổng hợp cục bộ: lưu thẻ, giữ ghi chú, chèn mẫu thay tên khách và
bảng báo cáo. Cần cấu hình Chatbot/engine thực tế để chạy tóm tắt thật trên máy triển khai.
