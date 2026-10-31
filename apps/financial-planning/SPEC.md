# Kế Hoạch tài chính — phân tích HCWPlan và đặc tả MinMin

Ngày khảo sát: 31/10/2026. Đây là bản triển khai độc lập trong MinMin, không phải mã nguồn hoặc bản giải mã HCWPlan.

## Bằng chứng đã thu thập

| Mã | Nguồn công khai | Điều quan sát được | Giới hạn |
|---|---|---|---|
| E01 | https://hcw.com.vn/lp/hcwplan-desktop | Landing page có 8 nhóm: chiến lược/KPI nhân sự; P&L/KPI tài chính; bán/cung ứng; dự án; vận hành; dòng tiền/vốn; kịch bản/nhiều năm; báo cáo. | Nội dung do nhà cung cấp công bố; không chứng minh runtime. |
| E02 | Cùng URL, phần Cơ chế liên kết dữ liệu | Bán → P&L; cung ứng → dòng tiền/vốn; dòng kết chuyển được đánh dấu, khóa sửa; kết chuyển có xem trước và hoàn tác. | Chưa kiểm chứng hành vi chạy thực tế. |
| E03 | https://hcw.com.vn/lp/hcwplan-desktop/assets/img/mod-forecast-1.png | Ảnh 1600×1000: sidebar chia nhóm; bộ lọc năm/nhãn; danh sách kế hoạch có tên, ngày tạo, nguồn, dự kiến hiệu lực, phê duyệt/hiệu lực, ghi chú, thao tác; badge ngân sách gốc và trạng thái đã duyệt T1–T12. Dòng hướng dẫn nêu không sửa/xóa trực tiếp kế hoạch đã duyệt. | Ảnh tĩnh; không xác nhận cách lưu DB. |
| E04 | https://hcw.com.vn/lp/hcwplan-desktop/assets/img/mod-cash-2.png | Bảng dòng tiền kinh doanh/đầu tư/tài chính; waterfall đối soát lãi–tiền; donut cơ cấu thu/chi; cảnh báo thiếu tiền theo tháng; so sánh liên kỳ. | Giá trị minh họa không phải bộ dữ liệu để truy ra đầy đủ thuật toán. |
| E05 | E01, phần Bán & Cung ứng | Công bố lượng nhập theo bán, tồn, hàng đang về, tồn an toàn, lô/MOQ; lịch giao và công nợ NCC; thống kê sai số dự báo. | Không công bố thuật toán chọn mô hình hay tham số thống kê cụ thể. |
| E06 | E01, phần bảo mật/FAQ | Nhà cung cấp mô tả SQLCipher, backup .hcwbak có mật khẩu, AI chạy offline, Windows/macOS; link cài và mã kích hoạt gửi sau thanh toán. | Chưa có bộ cài, giấy phép, DB hay mã nguồn. Không biết framework UI, runtime desktop, schema DB hoặc mô hình AI cụ thể. |

SHA-256 của các bản khảo sát tải về:

- HTML E01: `90644d52505910b2611d542c361788d5802b8f8f8d4ee0afeee204e0989c21d4`
- PNG E03: `9a73329b7667b5eeff3dc7d31b4f5f14f4027329f49bf8c44c42e413d2a610b3`
- PNG E04: `26dbb498951a6e21fadcc69893a97c2169621950f13a35a73641bf66a4ddb499`

Không tìm thấy URL `.exe`, `.dmg` hoặc `.zip` công khai trong landing page. Chưa tải/cài/chạy hoặc giải mã phần mềm. Không gửi form đặt mua hay thanh toán. Muốn soi công thức nội bộ cần bộ cài hợp lệ, quyền sử dụng, bộ dữ liệu thử và môi trường chạy Windows/macOS.

## Bóc tách cách xây dựng sản phẩm

Quan sát E01–E06 cho thấy thiết kế nghiệp vụ xoay quanh một nguồn dữ liệu, nguồn gốc dòng số liệu, snapshot kế hoạch và cổng phê duyệt; không chỉ quanh biểu đồ. Công thức dự báo tạo số dự kiến, P&L đo hiệu quả dồn tích, lịch thu/chi quy đổi sang tiền, công nợ/tồn kho giải thích chênh lệch. Đây là suy luận thiết kế từ tài liệu và ảnh, không phải kết luận về kiến trúc mã nguồn HCW.

UI HCW có mật độ dữ liệu cao, sidebar phân nhóm công việc, bảng 12 tháng và màu tín hiệu. MinMin giữ luồng điều hành này nhưng dùng thiết kế riêng, chữ tối thiểu 14–16px cho bảng/đầu vào, bố cục đáp ứng điện thoại và theme chung. Không sao chép ảnh, thương hiệu hay CSS HCW vào giao diện MinMin.

## Phạm vi triển khai thực tế

| Nhóm | HCW công bố | MinMin trong thay đổi này |
|---|---|---|
| Bán/cung ứng | Nhiều thuật toán, mùa vụ, hàng đang về, nhiều NCC, tồn an toàn thống kê | Nhập sản lượng 12 tháng theo SKU; gợi ý trung bình 3 kỳ; tồn đầu/tồn an toàn cố định; làm tròn lô/MOQ; lịch cần đặt theo lead time. Chưa có hàng đang về riêng hoặc chọn nhiều NCC. |
| P&L | Phiên bản ngân sách, chiều phòng/chi nhánh, phê duyệt riêng | Doanh thu/giá vốn từ SKU, biến phí, định phí, khấu hao, lãi vay, thuế giả định; lưu phiên bản; trạng thái nháp/trình/duyệt chung, chưa phân quyền người duyệt. |
| Dòng tiền/vốn | Nhiều nguồn, aging, DSO/DPO/DIO/CCC | Thu/trả theo độ trễ tháng; công nợ đầu kỳ; tồn kho, vốn lưu động, CAPEX, gốc vay, tài trợ; cảnh báo âm quỹ. Chưa có sổ công nợ từng hóa đơn hoặc aging. |
| Hòa vốn | Nhiều chiều, biên an toàn | Hòa vốn theo cơ cấu bán tháng; không chia khi số dư đảm phí ≤ 0; biên an toàn trong engine. |
| Kịch bản | Giả định, kế hoạch nhiều năm cuốn chiếu | So sánh thay đổi giá/sản lượng/giá vốn, áp dụng vào bản nháp; mô phỏng 3 năm độc lập. Chưa cuốn chiếu công nợ giữa các năm. |
| Thực tế | Nhập thực tế, đóng sổ | Doanh thu và lợi nhuận thực tế từng tháng, giữ ô trống là chưa nhập; khóa kỳ trên cả server/UI; mở khóa tường minh. |
| Báo cáo | Kéo thả, Excel, PDF/HTML, AI offline | Bảng báo cáo và công thức; in/lưu PDF qua trình duyệt, CSV mở bằng Excel; nhận xét xác định từ quy tắc. Chưa có LLM, report builder kéo thả hoặc XLSX. |
| BSC/KPI nhân sự, dự án/EVM, vận hành phòng ban | E01 có các nhóm này | Chưa triển khai trong module tài chính này; không có thẻ giao diện giả. |

## Công thức MinMin (thiết kế độc lập)

Đơn vị tiền VND, chưa VAT. Không hard-code chính sách thuế hiện hành. Thuế suất mặc định 0, do người dùng nhập giả định. Mô hình quản trị chưa xử lý VAT, bù lỗ, nghĩa vụ kê khai hoặc chênh lệch thuế.

1. Doanh thu = tổng sản lượng × giá bán; giá vốn = tổng sản lượng × giá vốn chuẩn. Giá vốn tồn kho dùng cùng giá chuẩn, chưa có FIFO/lô.
2. Nhu cầu nhận = max(0, bán + tồn an toàn − tồn đầu). Nếu dương, lượng nhận = ceil(max(nhu cầu, MOQ)/lô) × lô. Mua tự đáp ứng bán trong tháng; lead time chỉ lùi lịch cần đặt. Tháng cần đặt trước T1 được cảnh báo rõ.
3. Tồn cuối = tồn đầu + nhận − bán. Giá trị mua đi lịch phải trả, không đi thẳng vào giá vốn kỳ mua. Giá trị tồn = lượng tồn × giá vốn chuẩn.
4. Biến phí = doanh thu × tỷ lệ. Lợi nhuận trước thuế = doanh thu − giá vốn − biến phí − định phí − khấu hao − lãi vay. Thuế giả định = max(0, LNTT tháng) × tỷ lệ; lợi nhuận sau thuế = LNTT − thuế.
5. Thu khách = doanh thu dịch theo độ trễ tháng + phải thu đầu kỳ (thu T1). Trả NCC = mua dịch theo độ trễ tháng + phải trả đầu kỳ (trả T1). Khoản chưa đến hạn cuối năm vẫn ở công nợ; không làm mất số dư.
6. Tiền cuối = tiền đầu + thu khách − trả NCC − biến phí − định phí − lãi vay − thuế giả định − CAPEX − gốc vay + tài trợ ròng. Khấu hao không đi tiền; gốc vay/CAPEX không bị trừ thêm vào P&L.
7. Vốn lưu động ròng = phải thu + tồn kho − phải trả. Cầu nối tiền: Δ tiền = LN sau thuế + khấu hao − Δ vốn lưu động − CAPEX − trả gốc + tài trợ ròng (giá chuẩn không đổi).
8. Tỷ lệ số dư đảm phí = (doanh thu − giá vốn − biến phí)/doanh thu. Hòa vốn = (định phí + khấu hao + lãi vay)/tỷ lệ đảm phí, chỉ khi tỷ lệ dương. Mẫu số 0 trả null, hiển thị “—”.
9. Thiếu tiền = max(0, −min(tiền cuối 12 tháng)); không thay thế mô hình tiền trong ngày.
10. Thực tế − kế hoạch là chênh lệch tuyệt đối. Trống ≠ 0. Dự báo gợi ý là trung bình tối đa 3 kỳ gần nhất; không khẳng định nhận diện mùa vụ.

## Kiến trúc và tích hợp MinMin

- Thẻ riêng `financial_planning`, nhãn chính xác **Kế Hoạch tài chính** tại Kết Nối Ngoài; đường dẫn `/apps/financial-planning/`.
- `engine.js`: hàm thuần, kiểm tra đầu vào, tính lại toàn bộ số liệu từ nguồn duy nhất; không lưu dòng kết chuyển để tránh ghi nhận trùng.
- `app.js`: 8 màn hình, bảng nhập và báo cáo; escape nội dung người dùng, không dùng CDN.
- `server/financial_planning.py`: SQLite trong `STATE_DIR/financial-planning/plans.sqlite3`; ghi giao dịch nguyên tử, revision lease chống hai cửa sổ lưu đè; giữ 30 snapshot. Không lưu DB vào source.
- Scope dùng chung trong một cài đặt MinMin; chưa tách theo brain/đơn vị. Dữ liệu chưa mã hóa riêng ở module. Mọi route đi auth chung MinMin và cổng giấy phép/điều khoản của app. Static asset theo allowlist.
- Khóa kỳ chặn sửa đầu vào dùng chung hoặc tháng trước làm thay đổi tồn/công nợ của tháng đã khóa. Server kiểm tra độc lập UI. Lưu mở khóa riêng trước khi sửa số liệu.
- Lưu một kế hoạch hiện hành, snapshot cho lịch sử/khôi phục qua JSON; chưa có danh mục nhiều kế hoạch hiện hành song song. Chưa đồng bộ module Bảng tính kinh doanh/sàn/ERP để tránh tự cộng trùng nguồn.

## Kiểm chứng

`node tests/js/test_financial_planning.js`: giá vốn và tiền mua khác nhau; MOQ/tồn; công nợ đầu năm chỉ một lần; công nợ cuối năm bảo toàn; cầu nối lợi nhuận–tiền; độ trễ 0/1; mẫu số 0; thực tế trống; kịch bản không sửa nguồn; đầu vào sai.

`python tests/python/test_financial_planning.py`: đăng ký thẻ; license/terms cả API và assets; allowlist; lưu/đọc snapshot; stale write 409; khóa kỳ và mở khóa riêng; payload/input bounds.

Kiểm thử hồi quy Bảng tính kinh doanh/Kết Nối Ngoài và bảng route được chạy cùng thay đổi. Kiểm tra trình duyệt thực sẽ được ghi trong PR nếu môi trường có trình duyệt; không coi cú pháp hoặc kiểm thử DOM là bằng chứng kiểm tra hình ảnh.

Kết quả thực thi trong phiên 31/10/2026: 10/10 tệp kiểm thử liên quan đã qua (financial_planning Python/JS, business_finance Python/JS, ket_noi_ngoai, route_table, theme_tokens, shared_app_theme, i18n, i18n_ngoai_trinh_duyet). Bảng route thêm đúng 7 endpoint, thứ tự/tên/đường dẫn cũ giữ nguyên. Kiểm tra DOM bằng jsdom ngoài repo đã qua 8 màn hình, thêm SKU/dự báo, tổng liên thông, lưu, khóa/mở khóa, sửa khi đang lưu và escape tên báo cáo. Chưa kiểm tra ảnh giao diện MinMin bằng Chromium: môi trường không có executable và bản tải trình duyệt thất bại; không có ảnh screenshot runtime để đính kèm.

## Mở rộng 26.10.318

- Phòng mô phỏng có 5 thanh kéo (giá bán, sản lượng, giá vốn, định phí, số tháng thu tiền), dữ liệu minh họa tách biệt, so sánh gốc/mô phỏng, biểu đồ đường có trục và đơn vị, nội suy trạng thái bằng requestAnimationFrame, chạy một vòng 12 tháng và tạm dừng. Tôn trọng prefers-reduced-motion; không tự lặp hoặc tự lưu giả định. Nút lưu tạo phương án mới, không sửa nguồn.
- Nhiều phương án theo công ty/cửa hàng, mỗi phương án có cấu hình nguồn, revision và 30 snapshot riêng. Database cũ được chuyển sang phương án default đúng một lần. Đây là phân tách dữ liệu trong cùng tài khoản/cài đặt MinMin, chưa phải phân quyền nhiều người dùng theo pháp nhân.
- Chọn Nhập tay hoặc POS. Dùng kết nối Pancake POS đã lưu trong MinMin; không nhận hoặc hiện API key trong module. Chỉ dò/call kết nối được chọn, qua guard readonly; từ chối thao tác không được phân loại đọc. Shop phải nằm trong danh sách của kết nối đã chọn. Giá trị source/shop trong request preview không được thay cấu hình đã lưu.
- Xem trước một trang danh mục POS, chọn SKU/biến thể, bổ sung trường còn thiếu, xác nhận cơ sở VAT của giá bán, rồi áp dụng vào bản nháp. ID nối dựa trên kết nối + shop + product + variation; cùng SKU ở hai shop không trộn. Không tự coi giá vốn thiếu là 0. Tồn kho hiện tại chỉ làm tồn đầu kỳ khi người dùng tích chọn rõ; lưu thời điểm và tồn quan sát riêng.
- Chưa tự suy đoán doanh thu thuần/lợi nhuận từ báo cáo POS chưa được xác minh. Có nhập JSON báo cáo tháng có đối chiếu năm/công ty/cửa hàng, giữ kỳ khóa và xem trước. Chưa có lịch tự chạy nền, chưa ghi ngược POS, chưa triển khai adapter POS khác Pancake. Tài liệu tham khảo chính thức: https://docs.pancake.biz/pos/st-f13/st-p1?lang=vi và https://docs.pancake.biz/pos/st-f3/st-p1/st-s1.
- Kiểm thử số học bổ sung xác nhận kết quả thanh kéo bằng kết quả khi áp dụng giả định vào kế hoạch mới, không đổi nguồn và cầu nối lợi nhuận-tiền khớp. Kiểm thử server bao gồm migration, tách công ty/revision/history, sao chép kỳ khóa, config revision, nguồn POS bị giả mạo, ID biến thể, giá vốn thiếu. Kiểm tra DOM thực hiện kéo/thay input, 3 chart, sao chép, cấu hình nguồn/shop, bổ sung giá vốn thiếu, không tự đổi tồn đầu, nhập lại không trùng SKU, lưu đúng phương án.
