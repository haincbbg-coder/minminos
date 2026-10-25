# 33 - Gợi ý mã hàng cho nhân viên bán hàng

***Tiếng Việt** · [English](en/33-product-code-suggest.md)*

Từ 26.10.220, khi khách nhắn tới Pancake, một tiện ích trên Cốc Cốc/Chrome hiện ngay **mã hàng khách đang hỏi**, kèm độ chắc, lý do và tồn kho. Nhân viên chỉ việc đối chiếu rồi bấm "Đúng mã này".

Tra theo thứ tự từ chắc nhất:

| Nguồn | Ví dụ |
|---|---|
| **Mã trong tin nhắn** | "giá mã V33 nhiêu shop" |
| **ID quảng cáo** | khách bấm từ quảng cáo, tin nhắn mang `ad_ids` của Pancake |
| **Tên chiến dịch** | "CÔNG TY TNHH MTV HALIMI - TÊN PAGE - P720" thì mã là P720 |
| **ID bài viết** | khách bình luận dưới bài |

Ba nguồn trên tra ngay trên máy nhân viên bằng bảng nạp sẵn nên chỉ mất vài mili giây, không tốn token AI.

**Ảnh khách gửi** (từ 26.10.223): tiện ích tự gửi ảnh mới nhất lên MinMin. MinMin rút gọn bằng màu (không tốn token), rồi nhờ ChatGPT trên gói đã đăng nhập nhìn ảnh khách cạnh một bảng ảnh mẫu của khoảng 36 mã giống nhất và chọn tối đa 5 mã. Mất vài giây, chỉ một lần gọi cho mỗi ảnh, ảnh đã so rồi thì không tốn gì. Có trần số lần so mỗi ngày (mặc định 500, đổi bằng biến `JAVIS_GOI_Y_ANH_TRAN_NGAY`). Bấm vào ảnh nhỏ để so ảnh khác. Bấm "Đúng mã này" thì MinMin nhớ ảnh khách đó là mã nào, lần sau rút gọn chính xác hơn. Cần đã đăng nhập ChatGPT ở trang Model.

## Cài tiện ích

1. Nhờ MinMin "tạo mã ghép gợi ý mã hàng" (công cụ `javis_goi_y_ma_ma_ghep`), được mã 6 số sống 15 phút.
2. Trên Cốc Cốc mở `chrome://extensions`, bật Chế độ nhà phát triển, bấm "Tải tiện ích đã giải nén" và chọn thư mục `apps/goi-y-ma`.
3. Bấm biểu tượng tiện ích, nhập địa chỉ MinMin và mã 6 số, bấm Ghép máy.

## Nạp dữ liệu

Bộ não tự lấy mã, tồn và ảnh từ POS, quảng cáo từ Meta, bài viết từ Pancake bằng các kết nối đã nối, rồi gọi `javis_goi_y_ma_nap` theo lô. Dùng `javis_goi_y_ma_tra` để thử tra một tin nhắn, một ID quảng cáo hoặc một ID bài viết.

Có thể nạp cả trăm mã một lần từ một file `.json` trong bộ não: `javis_goi_y_ma_nap` với `tep: "attachments/ten-file.json"`. Danh sách mã dạng gọn `"P664:508"` (mã:tồn) cũng được.

Sau khi nạp mã, nhờ MinMin chạy `javis_goi_y_ma_hoc_anh` một lần để học ảnh mẫu (tải từ POS, chạy lại an toàn, chỉ học mã chưa có).

Mỗi lần nhân viên bấm "Đúng mã này", MinMin nhớ ID quảng cáo hoặc bài viết đó là mã nào cho lần sau.
