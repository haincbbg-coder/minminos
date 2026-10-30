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
| Zalo OA | Có (26.10.314) | Webhook HTTPS, chỉ chat riêng, dùng chung token với kết nối Zalo OA ở trang Kết nối |
| Pancake | Qua công cụ hội thoại đã có | Đọc hội thoại, soạn/gửi qua công cụ; lệnh ghi vẫn duyệt từng nội dung |
| Sapo, Nhanh.vn | Chưa có adapter hội thoại trong MinMin | Kết nối dữ liệu bán hàng không tự trở thành đường nhận/gửi chat |

Gắn bot và bật tự trả lời là cấu hình của chủ tài khoản. Bản nâng cấp giữ token, phạm vi nhóm khách, Agent và tài liệu đang có.
Chưa tự nối tài khoản mới, bật bot mới hay gửi tin thử tới khách.

## Zalo OA (26.10.314)

Bot chuyên trách trả lời được hộp thư **Zalo Official Account**, đi qua API chính thức OA Open API v3: cùng Agent, giờ trực, Hộp thư và tiếp quản như mọi kênh.

**Một OA một kho token.** Refresh token của Zalo chỉ dùng được một lần, nên kênh Chatbot không giữ token riêng: nó dùng chung kết nối **Zalo OA** ở trang Kết nối (tạo tự động nếu chưa có, mặc định Chỉ đọc). Mỗi lần làm mới, cặp token mới được ghi ngay vào kết nối, kho kết nối ghi nguyên tử nên máy tắt giữa chừng cũng không mất. Tài khoản kênh chỉ lưu id kết nối.

Cách nối, làm một lần:

1. Mở MinMin bằng **tên miền HTTPS**. Vào **Chatbot**, tab **Kênh**, **Kết nối kênh mới**, chọn **Zalo OA**. Form hiện **Địa chỉ webhook** và ô **Mã xác thực tên miền Zalo**.
2. Ở [developers.zalo.me](https://developers.zalo.me) tạo app, liên kết OA với app. Chép **App ID** và **Khóa bí mật của ứng dụng**.
3. Mục **Xác thực tên miền**: nhập tên miền MinMin, chọn cách file HTML. Dán tên file `zalo_verifier...html` vào ô của MinMin, bấm **Lưu mã**, rồi quay lại Zalo bấm **Xác thực**.
4. Mục **Webhook**: dán địa chỉ MinMin hiện (`https://<tên miền>/zalo-oa/webhook`), bật các sự kiện `user_send_text`, `user_send_image`, `user_send_file`, `user_send_audio`, `user_send_sticker`, `user_send_location`. Chép **OA Secret Key** ở đây.
5. **API Explorer**: chọn OA Access Token, đúng app và OA, lấy **Refresh token**. Nếu trang Kết nối đã có kết nối Zalo OA cùng App ID thì bỏ qua bước này.
6. Dán vào ô token, cách nhau dấu cách: `App ID  App secret key  OA secret key  Refresh token`. Bấm **Kiểm tra** (MinMin làm mới token một lần, đọc tên OA), rồi **Lưu**.
7. Ở tab Kênh chọn bot trực cho OA vừa thêm.

Khi bot im: thiếu OA secret key thì thẻ báo đỏ (mọi tin sẽ bị từ chối chữ ký). Lỗi -230 là khách lâu không nhắn, Zalo không cho tin tư vấn nữa cho tới khi khách nhắn lại. Lỗi -224 là gói OA chưa cho dùng API. Hộp thư chỉ có tin từ lúc nối, không kéo tin cũ.

## Bot Zalo cá nhân nhắn giống người hơn (26.10.314)

- Chữ **đậm**, nghiêng, gạch ngang, chữ màu `{red:...}`: bot viết Markdown, khách thấy định dạng Zalo chứ không thấy dấu sao. Gửi qua lệnh `msg send --style` của zalo-agent-cli 1.6.2; lệnh hỏng thì tin vẫn đi bằng chữ thường. Trong nhóm bot gửi chữ thường để tag người không lệch.
- "Đang soạn tin": MinMin thử tool `zalo_send_typing` trong lúc bot viết (chỉ chat riêng). zalo-agent-cli 1.6.2, bản mới nhất trên npm, **chưa có tool này**, nên hiện tại khách chưa thấy dòng đó; MinMin tự nghỉ thử một giờ mỗi lần và câu trả lời không phải chờ. Khi gói có tool, chỉ cần cập nhật gói.

## Thống kê và điện thoại (26.10.314)

- Thống kê có khối **A.I. đã trả lời bao nhiêu tin**, tỉ lệ tin do A.I. lo, giờ tiết kiệm ước tính (1 phút mỗi tin), tin A.I. trả lời lúc bạn nghỉ (21h-7h); bốn ô khách được phục vụ và khách mới, tốc độ trả lời đầu A.I. so với người (trung vị), tin trả lời tay, chat đang chờ; biểu đồ tin khách theo giờ; A.I. và tin tay theo từng nick/Page, có ô chọn xem một tài khoản.
- Hội thoại: bốn nút lọc nhanh gom thành **một nút thả xuống** luôn hiện số Cần bạn. Trên điện thoại mở chat là **toàn màn hình**, Enter trong ô trả lời là xuống dòng (nút Gửi mới gửi).
- Tab Kênh: thẻ tài khoản nằm sau nút **Thông tin** (chấm đỏ khi lỗi), không chiếm đầu khung nữa.
- Nhóm giữ **1000 tin** gần nhất (trước là 100).

## Phát triển tiếp cho Pancake, Sapo và Nhanh.vn

Nền Chatbot dùng chung kho hội thoại, trạng thái người trực, bản nháp và sổ kênh. Adapter mới cần đi qua cùng các lớp này.
Với Pancake, bước tiếp theo là nhận sự kiện hoặc đồng bộ tin tăng dần theo Page, ánh xạ mã tin để chống lặp, rồi nối chính API gửi đang có.
Với Sapo/Nhanh.vn, cần quyền và tài liệu API nhận/gửi hội thoại của tài khoản sử dụng trước khi triển khai adapter; API sản phẩm/đơn hàng không chứng minh quyền gửi chat.

Nguồn đối chiếu: Javis OS 0.371.0 đến 0.380.0, đặc tả Chatbot v5 và các kiểm thử của upstream (MIT), giữ nền quy tắc riêng của MinMin.
Tài liệu công khai: [Nhanh.vn Open API](https://apidocs.nhanh.vn/), [Webhook Nhanh.vn](https://apidocs.nhanh.vn/v3/webhooks/webhooks),
[Hội thoại Sapo Chat OmniAI](https://help.sapo.vn/quan-ly-hoi-thoai-tren-chat-omniai).
