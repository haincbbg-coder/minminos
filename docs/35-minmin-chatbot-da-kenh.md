# MinMin Chatbot đa kênh (26.10.284)

## Telegram mang tên MinMin

Tin trạng thái của bot chính đổi thành **🤔 MinMin đang xử lý…**. Tên tài khoản Telegram vẫn là tên đã đặt với BotFather.
Chấm “đang nhập” do Telegram hiển thị theo tên tài khoản; dòng trong ảnh là tin nhắn trạng thái do MinMin gửi.
Cập nhật ứng dụng và khởi động lại tiến trình bot để dùng mã mới. Tin trạng thái cũ trong lịch sử giữ nguyên.

## Hộp thư và người trực

Trang **Chatbot** có Hội thoại, Bot, Kênh, Thống kê và mục Vận hành của MinMin.

- Hội thoại gom các tài khoản đã kết nối; chọn nhiều nick, lọc ngày, thẻ, tin cuối, đã ghim và người đang xử lý.
- Trạng thái và số đếm do server tính thống nhất. Cần bạn bao gồm nháp chờ duyệt và khách chờ khi bot tắt.
- Mỗi cuộc chat chọn **A.I. tự trả lời**, **A.I. soạn, tôi duyệt**, **Tôi trả lời**. Tắt A.I. ở một tài khoản/cuộc chat giữ nguyên các tài khoản khác.
- Chế độ soạn chỉ dùng công cụ đọc. Nháp được lưu SQLite, giữ qua tải lại/khởi động lại và khi đổi chế độ.
- Nút **A.I. trả lời** coi chữ trong ô nhập là chỉ dẫn riêng để soạn nháp. Nút **Gửi** gửi nguyên văn chữ đã kiểm tra.
- Người trực tiếp quản trong lúc model đang chạy thì câu trả lời đó dừng gửi. Bản nháp cũ bị chặn khi khách vừa nhắn thêm.
- Một nháp được nhận gửi một lần bằng dấu trạng thái bền trước khi gọi kênh. Nếu kết quả chưa rõ, kiểm tra hội thoại thật rồi bỏ/soạn lại; ứng dụng không tự gửi lần nữa.
- Tab Kênh đổi bot trực tài khoản, giữ nguyên tin cũ và chuyển chúng theo bot mới. Có lựa chọn Không cần bot.
- Thống kê hiển thị tin A.I./người trực, thời gian chờ và so với kỳ trước. Vận hành giữ hồ sơ, người phụ trách, mẫu trả lời, báo cáo và nhật ký hiện có.

## Phạm vi kênh thực tế

| Kết nối | Nhận/gửi trong Chatbot | Vai trò hiện có |
|---|---|---|
| Telegram | Có | Bot chuyên trách và bot chính riêng biệt |
| Zalo Bot | Có | Token bot, nhóm/người được cho phép |
| Zalo cá nhân | Có | Dùng kết nối Zalo và phạm vi nhóm khách của MinMin |
| Pancake | Qua công cụ hội thoại đã có | Đọc hội thoại, soạn/gửi qua công cụ; lệnh ghi vẫn duyệt từng nội dung |
| Sapo, Nhanh.vn | Chưa có adapter hội thoại trong MinMin | Kết nối dữ liệu bán hàng không tự trở thành đường nhận/gửi chat |

Gắn bot và bật tự trả lời là cấu hình của chủ tài khoản. Bản nâng cấp giữ token, phạm vi nhóm khách, Agent và tài liệu đang có.
Chưa tự nối tài khoản mới, bật bot mới hay gửi tin thử tới khách.

## Phát triển tiếp cho Pancake, Sapo và Nhanh.vn

Nền Chatbot dùng chung kho hội thoại, trạng thái người trực, bản nháp và sổ kênh. Adapter mới cần đi qua cùng các lớp này.
Với Pancake, bước tiếp theo là nhận sự kiện hoặc đồng bộ tin tăng dần theo Page, ánh xạ mã tin để chống lặp, rồi nối chính API gửi đang có.
Với Sapo/Nhanh.vn, cần quyền và tài liệu API nhận/gửi hội thoại của tài khoản sử dụng trước khi triển khai adapter; API sản phẩm/đơn hàng không chứng minh quyền gửi chat.

Nguồn đối chiếu: Javis OS 0.371.0 đến 0.380.0, đặc tả Chatbot v5 và các kiểm thử của upstream (MIT), giữ nền quy tắc riêng của MinMin.
Tài liệu công khai: [Nhanh.vn Open API](https://apidocs.nhanh.vn/), [Webhook Nhanh.vn](https://apidocs.nhanh.vn/v3/webhooks/webhooks),
[Hội thoại Sapo Chat OmniAI](https://help.sapo.vn/quan-ly-hoi-thoai-tren-chat-omniai).
