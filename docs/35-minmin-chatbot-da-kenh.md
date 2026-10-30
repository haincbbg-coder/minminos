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
| Pancake (từ 26.10.315) | Có, mỗi Fanpage một tài khoản | Đồng bộ tăng dần qua Pancake; mặc định A.I. chỉ soạn nháp, tự trả lời bật riêng từng Page |
| Sapo, Nhanh.vn | Chưa có adapter hội thoại trong MinMin | Kết nối dữ liệu bán hàng không tự trở thành đường nhận/gửi chat |

Gắn bot và bật tự trả lời là cấu hình của chủ tài khoản. Bản nâng cấp giữ token, phạm vi nhóm khách, Agent và tài liệu đang có.
Chưa tự nối tài khoản mới, bật bot mới hay gửi tin thử tới khách.

## Phát triển tiếp cho Sapo và Nhanh.vn

Nền Chatbot dùng chung kho hội thoại, trạng thái người trực, bản nháp và sổ kênh. Adapter mới cần đi qua cùng các lớp này.
Pancake đã làm xong ở 26.10.315, xem mục dưới.
Với Sapo/Nhanh.vn, cần quyền và tài liệu API nhận/gửi hội thoại của tài khoản sử dụng trước khi triển khai adapter; API sản phẩm/đơn hàng không chứng minh quyền gửi chat.

Nguồn đối chiếu: Javis OS 0.371.0 đến 0.380.0, đặc tả Chatbot v5 và các kiểm thử của upstream (MIT), giữ nền quy tắc riêng của MinMin.
Tài liệu công khai: [Nhanh.vn Open API](https://apidocs.nhanh.vn/), [Webhook Nhanh.vn](https://apidocs.nhanh.vn/v3/webhooks/webhooks),
[Hội thoại Sapo Chat OmniAI](https://help.sapo.vn/quan-ly-hoi-thoai-tren-chat-omniai).

## Fanpage qua Pancake (26.10.315)

Bố đã quyết: khách Fanpage vào hộp thư MinMin **đi qua Pancake**, không nối Messenger thẳng. Nhân viên sale vẫn
trả lời trong Pancake như thường, khách không bao giờ nhận hai câu từ hai hệ thống.

### Bố bật thế nào

1. Trang **Kết nối**: kết nối **Thống kê Pancake** đã có sẵn các Page (mỗi dòng `page_id | page_access_token | tên`).
   Không cần nhập token lần nữa. Muốn gửi tin từ MinMin thì kết nối phải ở mức **Toàn quyền**.
2. Trang **Chatbot**, tab **Kênh**: mục **Pancake** hiện từng Page. Chọn một Page, bật công tắc **Ghi hội thoại**.
   Từ lúc bật, tin mới của Page đó vào tab Hội thoại (khoảng 30 giây một lượt). Lịch sử cũ không bị kéo về.
3. Muốn A.I. soạn sẵn câu trả lời: ở ô **A.I. trực ở Page này** chọn một bot rồi Lưu. Mỗi tin khách mới, A.I. soạn
   nháp; bố hoặc người trực bấm **Gửi** ở Hộp thư, nháp đi qua đúng API gửi của Pancake, và chỉ gửi một lần.
4. Chỉ khi thật sự muốn, bấm **Bật A.I. tự trả lời** ở thẻ Page. MinMin hỏi lại với cảnh báo: nhân viên đang trả lời
   trong Pancake có thể trả lời cùng lúc. Tắt lại thì các cuộc chat đang tự trả lời của Page đó về "A.I. soạn, tôi duyệt".

### Luật chạy

- Mặc định mọi cuộc chat Pancake là **A.I. soạn, tôi duyệt** (có bot) hoặc **Chỉ ghi lại** (không bot). Nút
  "A.I. tự trả lời" của một cuộc chat bị khoá khi Page chưa bật; server cũng từ chối.
- Nhân viên nhắn trong Pancake thì cuộc chat thành **Bạn đang xử lý**, nháp đang chờ bị bỏ, A.I. nhường như khi
  bố tự gõ. Tin tự động (Botcake, POS) không tính là người trực.
- Câu MinMin gửi quay về qua Pancake được nhận ra (theo mã tin và nội dung), không hiện hai lần, không bị tính là nhân viên.
- Facebook chỉ cho Page nhắn trong 24 giờ kể từ tin cuối của khách. Quá 24 giờ thì MinMin không gửi và nói rõ lý do.
- Tab Thống kê đếm Pancake như mọi kênh; tin nhân viên tính là tin người trực.
- Có sẵn điểm nối webhook `pancake_inbox.bao_co_su_kien(page_id)`: hòm webhook bền gọi hàm này thì Page được đọc ngay.

### API Pancake dùng

Chỉ các đường đã có trong mã MinMin (`pancake_hoi_thoai.py`), cùng token page, host `pages.fm/api/public_api`:
`GET v2 /pages/{id}/conversations` (`type=INBOX`, `order_by=updated_at`, `since`, `until`),
`GET v1 /pages/{id}/conversations/{cid}/messages`, `GET v1 /pages/{id}/tags`, `GET v1 /pages/{id}/users`,
`POST v1 /pages/{id}/conversations/{cid}/messages` (`action=reply_inbox`).

### Còn thiếu, cần thử với tài khoản thật

- Tên trường của hội thoại và tin nhắn (khách, số điện thoại, thẻ, nhân viên phụ trách, người gửi phía Page) đọc
  khoan dung vì tài liệu công khai không mô tả; cần đối chiếu một Page thật.
- Giờ dạng ISO không kèm múi giờ đang coi là UTC.
- Pancake không công bố cờ "khung 24 giờ"; MinMin tự tính theo tin khách trong kho và đổi lỗi gửi của Facebook thành câu dễ hiểu.
- Bình luận (COMMENT) chưa vào Hộp thư; ảnh, file chỉ ghi mô tả và link. Pancake chưa công bố webhook tin nhắn
  có chữ ký, nên webhook chỉ dùng để đánh thức vòng đọc.
