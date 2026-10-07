# 30 - Kết nối đa tài khoản: sàn TMĐT, vận chuyển, thanh toán, TikTok Ads, Zalo OA

*Tiếng Việt · [English](en/30-multi-account-connectors.md)*

Từ bản 26.10.115, trang **Kết nối** có thêm 10 nền tảng, bản 26.10.116 thêm 12 nền tảng nữa. Điểm chung: **mỗi kết nối là một tài
khoản**. Có ba shop Shopee thì thêm ba kết nối Shopee, có hai tài khoản GHN thì thêm hai kết nối
GHN. MinMin tự đặt tên riêng cho từng kết nối nên hỏi "đơn hôm nay của shop MeiMei" là đúng shop.

Không cần cài thêm gì: MinMin tự gọi API của từng nền tảng bằng Python, chạy được cả trên máy
nhà lẫn VPS.

## Danh sách

| Nhóm | Nền tảng | Mỗi kết nối là | Làm được gì |
|---|---|---|---|
| Bán hàng | Shopee | 1 shop | Đơn hàng, chi tiết đơn, tiền thực nhận, sản phẩm |
| Bán hàng | TikTok Shop | 1 shop | Đơn hàng, chi tiết đơn, sản phẩm |
| Bán hàng | Lazada | 1 shop | Đơn hàng, sản phẩm trong đơn, sản phẩm |
| Vận chuyển | GHN | 1 tài khoản (nhiều cửa hàng) | Tính phí, tra đơn, tạo đơn, huỷ đơn |
| Vận chuyển | GHTK | 1 tài khoản | Tính phí, tra đơn, tạo đơn, huỷ đơn |
| Thanh toán | SePay | 1 tài khoản (nhiều ngân hàng) | Giao dịch, tổng tiền vào ra trong ngày |
| Thanh toán | Casso | 1 doanh nghiệp | Giao dịch, tổng hợp tiền vào ra |
| Thanh toán | payOS | 1 kênh thanh toán | Tạo link thanh toán VietQR, xem, huỷ link |
| Quảng cáo | TikTok Ads | 1 lần ủy quyền (nhiều tài khoản quảng cáo) | Chiến dịch, báo cáo, bật tắt, đổi ngân sách |
| Nhắn tin | Zalo OA | 1 Official Account | Hội thoại, người quan tâm, gửi tin chăm sóc khách |
| Bán hàng | Tiki | 1 shop | Đơn hàng, sản phẩm, tồn kho (từ 26.10.116) |
| Bán hàng | Haravan, Sapo | 1 cửa hàng | Đơn hàng, sản phẩm, khách hàng, tồn kho |
| Bán hàng | KiotViet, Nhanh.vn | 1 tài khoản | Chi nhánh/kho, sản phẩm, tồn kho, đơn, hoá đơn bán, khách |
| Vận chuyển | Viettel Post, Ahamove | 1 tài khoản | Tính phí, tra đơn, tạo đơn, huỷ đơn |
| Vận chuyển | J&T Express | 1 tài khoản đối tác | Tra hành trình, huỷ đơn (J&T chưa công khai API tạo đơn) |
| Mạng xã hội | Instagram | 1 tài khoản chuyên nghiệp | Đăng ảnh, carousel, Reels; đọc bài, bình luận, chỉ số |
| Mạng xã hội | Threads | 1 hồ sơ | Đăng chữ, ảnh, video, carousel; trả lời; chỉ số |
| Mạng xã hội | X (Twitter) | 1 tài khoản | Đăng bài, trả lời, xoá bài; đọc bài gần đây (X tính phí mỗi bài) |
| Hoá đơn & thuế | MISA meInvoice | 1 mã số thuế | Mẫu hoá đơn, trạng thái hoá đơn, link xem |

## An toàn

- Mọi kết nối mới mặc định **Chỉ đọc**. Muốn MinMin tạo đơn vận chuyển, tạo link thanh toán, bật
  tắt quảng cáo hay gửi tin Zalo thì phải tự nâng kết nối đó lên **Toàn quyền**.
- Các sàn TMĐT, phần mềm bán hàng và MISA meInvoice **chỉ đọc**, kể cả khi nâng quyền: MinMin không sửa giá, sửa tồn, xử lý đơn hay phát hành hoá đơn.
- **Zalo Ads chưa có**: Zalo không công khai API báo cáo quảng cáo. Tạm thời xuất file báo cáo từ Zalo Ads Manager rồi gửi MinMin đọc.
- Key, mật khẩu ứng dụng và token được **mã hoá** khi lưu, và bị che khỏi mọi câu trả lời, nhật
  ký và tin Telegram, kể cả khi nền tảng trả lỗi có nhắc lại token.
- Shopee, Lazada, TikTok Shop, Zalo OA dùng token có hạn. MinMin tự làm mới và lưu token mới, mỗi
  kết nối chỉ làm mới một lần dù nhiều việc chạy cùng lúc, để không làm hỏng refresh token loại
  dùng một lần.
- payOS kiểm chữ ký phản hồi: phản hồi bị sửa trên đường đi thì MinMin báo lỗi chứ không đưa link.

## Ủy quyền shop (Shopee, Lazada, TikTok Shop, Zalo OA)

1. Tạo app trên trang nhà phát triển của nền tảng (hướng dẫn chi tiết nằm ngay trong form kết nối).
2. Dán khoá app vào kết nối rồi lưu.
3. Hỏi MinMin "tạo link ủy quyền Shopee" (hoặc Lazada, Zalo OA), mở link, đăng nhập và đồng ý.
4. Chép `code` trên địa chỉ trả về vào ô **Mã ủy quyền** rồi lưu. MinMin đổi code lấy token ngay.

Shop thứ hai: thêm kết nối mới, dùng lại khoá app, chỉ khác code (và Shop ID với Shopee).

## Kiểm định trước khi đưa vào MinMin

Mỗi nền tảng có bộ test riêng kiểm đúng cách ký và gọi API (`tests/python/test_<ten>_mcp.py`),
cộng một cổng kiểm định chung `tests/python/test_ket_noi_noi_bo.py` mà mọi cầu nối phải qua:
đủ phân loại quyền cho từng tool, tool nguy hiểm bị chặn ở mức thấp, thiếu khoá thì không gọi
mạng, không lộ bí mật trong bất kỳ lỗi nào, hai tài khoản không lẫn token. Test chạy không cần
mạng, nên lần đầu dùng với tài khoản thật vẫn nên bấm **Test** trên trang Kết nối.
