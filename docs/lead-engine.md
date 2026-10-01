# Lead Engine cho MinMin OS

Bản 0.1 là kho lead, công cụ cho agent và dashboard có đăng nhập, dùng được với các model
đang có qua MCP Hub. Không khóa vào Grok/Hermes, HALIMI, hoặc một ngành kinh doanh.

## Bắt đầu

Sau khi triển khai bản app chứa tính năng này, mở **Đồ nghề > Lead Engine > Mở trang**,
hoặc `/ext/lead-engine/` trên chính tên miền MinMin. Chọn brain, lưu hồ sơ doanh nghiệp và
bấm **Thêm agent**. Agent xuất hiện trong **Nhân sự AI > Marketing**. Nếu đã có file agent
cùng slug, nút giữ nguyên file đó. Agent Buyer Conversation Analyzer hiện có không bị sửa.

Giao việc trong chat với agent, ví dụ:

> Đọc hội thoại của nguồn đã kết nối trong 90 ngày gần đây. Nhập lead, tìm nhu cầu có dẫn
> chứng, soạn quảng cáo và tin chăm sóc. Báo rõ phạm vi dữ liệu đã đọc và nguồn còn thiếu.

Agent dùng connector có sẵn để đọc nguồn, gọi `lead_capture`, `lead_analyze`, `lead_draft`,
`lead_outcome`, `lead_spend`. Việc có chạy được hay không phụ thuộc connector thật, quyền
đã cấp và phạm vi dữ liệu mà API cung cấp. Không có connector thì phải báo chưa kết nối.
Không có tiến trình nền nào tự bật khi cài plugin hoặc bấm Thêm agent.

## Phạm vi đã có

- Hồ sơ doanh nghiệp theo brain: tên, offer, khách mục tiêu, tiền tệ.
- Nhập lead/hội thoại qua tool hoặc file JSON; chống trùng theo provider + account + ID gốc.
- Agent phân tích bằng model đã chọn. Plugin kiểm tra trích dẫn có nằm trong tin khách thật
  đã nhập hay không, tính điểm ưu tiên bằng quy tắc công khai, không phải mô hình dự đoán.
- Bản nháp quảng cáo và chăm sóc, khóa chống lặp; chặn tạo tin mới khi khách đã từ chối.
- Đối soát đơn: chỉ trạng thái delivered cộng doanh thu. Hoàn/hủy không cộng. Đọc lại cùng
  đơn không cộng lần hai. `won` của lead không tự tạo doanh thu.
- Chi phí campaign/ngày được lưu dạng snapshot tổng tích lũy, không cộng lại mỗi lần đồng bộ.
- Dashboard lấy số thật từ sổ, tự tải lại mỗi 30 giây khi tab đang mở. Đây là polling, không
  phải stream thời gian thực từ các nền tảng. Có giới hạn 200 lead và 100 bản nháp hiển thị;
  tổng số lead vẫn tính toàn sổ. Chi tiết trả tối đa 500 tin mới nhất.

## Chưa có trong bản này

- Tự tạo/bật/tăng ngân sách campaign; tự gửi email/SMS/Zalo; tự thu thập prospects ngoài nguồn
  đã được doanh nghiệp kết nối. Các hành động này không được giả lập thành kết quả thành công.
- Hàng đợi thực thi có budget reservation, hạn mức tần suất, retry và trạng thái chưa rõ khi
  nhà cung cấp nhận lệnh nhưng mất phản hồi.
- Phân phối/bán lead, đối soát thanh toán, hoàn tiền, quyền nhận và chuyển giao lead.
- Tự quy nguồn đơn cho campaign, CPL/ROAS theo cohort, dashboard lợi nhuận. Không lấy tổng
  doanh thu chia tổng ads rồi coi là ROAS nếu chưa có attribution tương ứng.
- SaaS nhiều doanh nghiệp trong một bản cài: brain chỉ là phạm vi dữ liệu, không phải ranh
  giới đăng nhập. Lõi hiện cho quản trị viên truy cập các brain của bản cài.

## Đường thương mại hóa

1. **Pilot riêng từng doanh nghiệp:** một instance/container, state volume, tài khoản quản
   trị và connector riêng. Dùng cùng mã nguồn với hồ sơ và cấu hình ngành khác nhau.
2. **Kết nối thực thi đầu tiên:** chọn Pancake + Meta, Zalo hoặc form; hoàn thiện adapter đọc
   có cursor/checkpoint, đồng bộ tăng dần, mapping ID và báo dữ liệu lỗi/thiếu.
3. **Thực thi có giới hạn:** cấu hình tài khoản/kênh/người nhận, hạn mức chi tiêu và tần suất,
   trạng thái draft/approved/running/succeeded/failed/unknown, khóa chống chạy trùng. Chỉ
   ghi thành công sau khi xác minh ID kết quả ở nhà cung cấp. Lệnh không rõ kết quả không
   được retry mù. Quy tắc chặn phải ở server, không chỉ trong system prompt.
4. **SaaS:** tenant ID lấy từ phiên đăng nhập đã xác thực; phân quyền mọi API, MCP, worker,
   webhook, secrets, backup và export; kiểm thử truy cập chéo; giới hạn tài nguyên, quota,
   nhật ký và chính sách lưu/xóa dữ liệu. Không dùng ID tenant do model tự truyền làm quyền.
5. **Bán lead:** tách người mua sản phẩm khỏi doanh nghiệp mua lead; lưu điều kiện chia sẻ,
   danh sách từ chối, chất lượng, độc quyền/trùng, bàn giao và đối soát.

## Định dạng nhập lead

```json
{
  "source": "pancake:shop-example",
  "external_id": "contact-example",
  "name": "Khách ví dụ",
  "messages": [
    {
      "id": "message-example",
      "role": "customer",
      "text": "Tôi muốn đặt, cần nhận trước thứ sáu.",
      "at": "2026-09-30T10:00:00+07:00"
    }
  ]
}
```

Mã và nội dung trong mẫu là dữ liệu minh họa. Khi nhập thực tế, giữ ID và timestamp gốc.
Một lần tối đa 500 tin, file tối đa 2 MB. Nhập tiếp các trang với cùng source/external_id.
Một message ID có nội dung khác bị từ chối để tránh làm mất dẫn chứng phân tích đã lưu.
Chưa tự gộp cùng một người giữa Zalo/Pancake/email vì tên trùng không chứng minh cùng người.

`lead_analyze` nhận `lead_id`, `summary`, `signals` gồm `kind`, `message_id`, `quote`.
Điểm: purchase_intent 45, product_fit 25, timing 20, đã có đơn delivered trong sổ 10.
Tín hiệu hội thoại cũ hơn 90 ngày không cộng điểm. HOT >=70, WARM >=40; còn lại COLD.
Điểm chỉ hỗ trợ xếp việc; câu trích dẫn tồn tại không đảm bảo diễn giải của model là đúng.
Sổ không tự xác minh evidence_ref với provider; agent phải đọc và đối chiếu nguồn trước khi ghi.

## Vận hành và dữ liệu

- SQLite dưới `JAVIS_STATE_DIR/plugin-data/lead-engine/<hash-brain>/leads.sqlite3`.
  Sao lưu cả state cùng brain, dùng SQLite backup API hoặc dừng ghi khi sao chép database.
- Khóa scope lấy từ đường dẫn tuyệt đối của brain trong context, không nhận tenant ID từ tool.
  Chuyển đường dẫn brain cần di trú scope tương ứng; không tự tìm lại theo tên.
- Profile/lead/draft/outcome/spend là tool mức safe; report/detail mức readonly.
  Các HTTP route dùng đăng nhập và CSRF của MinMin, không mở endpoint public.
- Không lưu credential trong sổ. Hội thoại là dữ liệu khách hàng; bảo vệ volume và backup như
  các dữ liệu riêng khác của doanh nghiệp. Bản này chưa có tác vụ xóa theo thời hạn.
- Số tiền là integer theo đơn vị nhỏ nhất, VND đồng / USD cent; không đổi tiền tệ sau khi
  sổ đã có số tiền. Mọi tổng là toàn bộ dữ liệu đã nhập, không khẳng định toàn bộ dữ liệu nguồn.

Kiểm thử: `python tests/python/test_lead_engine.py`, cùng các test host/plugin HTTP sẵn có.
