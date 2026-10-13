---
name: Báo cáo ngày
description: Báo cáo kinh doanh ngày/tuần từ POS và ads theo công thức gọi cố định, ít bước, số nhất quán giữa các ngày.
description_en: "Daily/weekly business report from POS and ads with a fixed call recipe: few steps, numbers consistent day to day."
group: Operations
---

# BÁO CÁO NGÀY - lấy số theo công thức, không mò lại mỗi sáng

## Khi nào dùng

Kích hoạt khi người dùng muốn số liệu kinh doanh của một kỳ ngắn: "báo cáo hôm nay",
"hôm qua bán được bao nhiêu", "tuần này thế nào", "chạy báo cáo", "doanh thu và chi tiêu ads",
hoặc khi một reminder/loop báo cáo định kỳ chạy. Dùng cho MỌI shop, mọi POS, mọi nền ads đang
kết nối; không gắn với một cửa hàng cụ thể nào.

Không dùng cho câu hỏi phân tích sâu ("vì sao tháng này tụt") - câu đó cần đọc rộng hơn, cứ
làm như bình thường.

## Vì sao có skill này

Một báo cáo 2 shop đo được 10 bước và 634k token (13/10/2026), trong đó 1 bước hỏi cách dùng
tool, 4 bước gọi cùng một tool với tham số khác nhau, mỗi bước nạp lại toàn bộ ngữ cảnh.
Việc lấy số KHÔNG cần sáng tạo, cần NHẤT QUÁN: hôm nay đếm kiểu nào, ngày mai đếm đúng kiểu
đó, hai ngày mới so được với nhau. Nên công thức gọi phải cố định và được ghi nhớ, không để
não tự nghĩ lại mỗi sáng.

## Nguyên tắc 3 bước (tối đa 4)

**Bước 0 - đọc công thức đã lưu, KHÔNG gọi tool mô tả.** Mở `memory/facts/cong-thuc-bao-cao.md`
(nếu có). File này ghi: tên kết nối, shop_id, bảng mã trạng thái đơn, tool và tham số cho
từng con số, tài khoản ads và trường cần lấy. Có file thì bỏ qua mọi `*_describe`,
`javis_search_tools`, `javis_connections`: công thức đã nói đủ.

**Bước 1 - gọi TẤT CẢ trong MỘT lượt, song song.** Mọi lần gọi tool để lấy số (từng shop, từng
trạng thái, từng tài khoản ads) phát ra cùng một lúc trong một tin nhắn, không gọi xong cái
này mới gọi cái kia. Engine chạy song song được; mỗi lần tách bước là nạp lại toàn bộ ngữ
cảnh thêm một lần nữa.

**Bước 2 - viết báo cáo.** Số từ kết quả tool, không tự cộng trừ ngoài những phép cộng ghi rõ
trong công thức (ví dụ tổng 2 shop). Có kỳ trước thì so; không có thì nói không có, đừng bịa.
Kết thúc bằng 1 đến 3 việc cần làm nếu có.

**Bước 3 (chỉ khi cần) - lưu số kỳ đã đóng vào cache.** Kỳ đã đóng (hôm qua, tuần trước) thì
ghi snapshot vào `05 - Data Cache/` theo quy ước cache; kỳ đang chạy thì không.

## Lần đầu chưa có công thức

Chỉ lần này được phép mò, và mò xong phải GHI LẠI để không bao giờ mò lại:

1. `javis_connections` để biết có những kết nối POS/ads nào.
2. Với mỗi POS: gọi `*_describe` (hoặc đọc mô tả tool) MỘT lần để lấy shop_id, bảng mã trạng
   thái, tham số đếm. Với ads: tài khoản, trường (spend, impressions, purchases...).
3. Chốt công thức: với mỗi con số trong báo cáo, ghi đúng một dòng `tool(tham số)`.
4. Ghi `memory/facts/cong-thuc-bao-cao.md` (type: business) và thêm một dòng vào
   `memory/MEMORY.md`. Mẫu:

```
---
type: business
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
# Công thức báo cáo ngày
## Kết nối
- <tên kết nối POS>: shop_id=<...>, bảng trạng thái: <mã>=<nghĩa>, ...
- <tên kết nối ads>: tài khoản act_<...>
## Từng con số
- Đơn mới hôm nay (shop A): <tool>(<tham số>)
- Đơn đã giao (shop A): <tool>(<tham số>)
- Chi tiêu ads hôm nay: <tool>(<tham số>, fields=spend,...)
## Phép cộng được phép
- Tổng đơn = shop A + shop B
```

Lần sau mở file này ra là đi thẳng Bước 1.

## Khi công thức sai

Tool đổi tham số, shop thêm trạng thái mới, kết nối đổi tên: sửa đúng dòng đó trong
`cong-thuc-bao-cao.md` ngay trong lượt phát hiện, ghi `updated`, rồi làm tiếp. Không tạo file
công thức thứ hai.

## Pitfalls

- Gọi `*_describe` khi công thức đã có là tốn một bước vô ích; chỉ gọi khi tham số thật sự bị
  tool từ chối.
- `page_size=1` chỉ để lấy tổng (total) khi tool trả total trong phần meta; nếu tool không trả
  total thì phải ghi rõ trong công thức cách đếm khác, đừng đếm nhầm 1 đơn thành tổng.
- Số nào trong báo cáo cũng phải có mặt trong kết quả tool hoặc là phép cộng đã ghi trong
  công thức. Chân nguồn tự động sẽ cảnh báo số không thấy; đừng để nó phải cảnh báo.
- Không dùng gạch dài trong báo cáo.
