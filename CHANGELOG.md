# Nhật ký cập nhật

Lịch sử phiên bản MinMin OS. Bản mới nhất ở trên cùng. Xem ngay trong app tại nút **Cập nhật** trên thanh bên, hoặc **Tuỳ chỉnh → Cập nhật**.

Số phiên bản đánh theo lịch: `năm.tháng.lần` (26.10.1 = tháng 10 năm 2026, bản thứ nhất). Mỗi phiên bản là một khối `## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [26.10.52] - 2026-10-03
### Thêm mới
- Tìm bản gốc từ XML, PDF hoặc ZIP; tìm lại hàng loạt trong kho và xem rõ nguồn đã thử.
- Đối chiếu Gmail và thông tin hóa đơn trước khi lưu bản gốc; nhận diện M-Invoice chi nhánh TP.HCM.

## [26.10.51] - 2026-10-03
### Sửa lỗi
- Dòng "Bot im: lý do" trong Hộp thư dùng một icon không có trong bộ icon của MinMin nên hiện trống và làm CI đỏ. Đổi sang icon có sẵn (mặt trăng).

## [26.10.50] - 2026-10-03
### Thêm mới
- Hộp thư, cuộc chat có bot: nút **Gợi ý câu trả lời** (bot soạn nháp vào ô gõ, bố sửa rồi tự gửi, không gửi gì cả) và nút **Trả lời giúp tin này** (bot trả lời tin khách cuối và gửi ngay, kể cả khi bộ phán xử đã chọn im; vẫn là bot nói nên không tự tiếp quản cuộc chat).
- Dòng **Bot im: lý do** hiện ngay trong cuộc chat khi bộ phán xử chọn im, kèm hai nút "Im là đúng" / "Lẽ ra phải nói" để bot học ngưỡng riêng của nhóm đó.
- Thiết kế học theo Javis 0.65, viết lại riêng cho MinMin.

## [26.10.49] - 2026-10-03
### Thêm mới
- Bot trong nhóm có chế độ **Tự phán đoán**: không ai gọi tên thì bot đọc vài tin gần nhất rồi tự quyết nên nói hay im (tin hỏi giá, còn hàng, size thì nói; xã giao, khách nói với nhau, bot vừa nói xong thì im). Chấm bằng luật nên không tốn lượt gọi model cho mỗi tin trong nhóm đông.
- Mọi quyết định, kể cả im, được ghi kèm lý do (xem `GET /chatbots/{id}/phan-xu`). Chủ chấm Đúng/Sai (`POST /chatbots/{id}/phan-xu/phan-hoi`): Sai thì ngưỡng của riêng nhóm đó lệch một nấc, có chặn trên chặn dưới. `POST .../phan-xu/quen` xoá phần đã học.
- Thiết kế học theo cách Javis 0.65 làm, nhưng viết lại riêng cho MinMin.

## [26.10.48] - 2026-10-03
### Sửa lỗi
- Nghe thử giọng ChatGPT Live phát được âm thanh: bổ sung 9 file mẫu giọng (arbor, breeze, cove, ember, juniper, maple, sol, spruce, vale) mà trang Giọng nói gọi tới nhưng trong MinMin bị thiếu nên bấm Nghe thử không ra tiếng. Lấy từ Javis 0.65.17.
### Bảo mật
- Màn đăng nhập che kín hẳn: nền đặc, chưa đăng nhập thì không còn thấy lờ mờ bố cục phía sau. Lấy từ Javis 0.70.2.

## [26.10.47] - 2026-10-03
### Cải thiện
- Đồng bộ chiều sâu, nút, ô nhập và hộp thoại của Hóa đơn/Gmail, Zalo và Bộ chứng từ với MinMin. Màn hình phụ theo cùng tông sáng/tối, cả đồ họa hạt và nhãn.

## [26.10.46] - 2026-10-03
### Sửa lỗi
- Thanh đầu trên điện thoại: nút menu, chuông, chip model và nút thêm dùng bóng nổi nhỏ và sát, không còn quầng mờ tràn lên vùng tai thỏ và đè lên quả cầu; thanh đầu được tách lớp vẽ riêng.

## [26.10.45] - 2026-10-03
### Sửa lỗi
- Quả cầu tri thức trên điện thoại quay lại bình thường: trước đây rời sang trang khác rồi quay về màn chính là quả cầu bị dừng hẳn dù đã chọn tốc độ.

## [26.10.44] - 2026-10-03
### Sửa lỗi
- Hóa đơn, Gmail, chứng từ và Zalo Forwarder theo đúng tông sáng hoặc tối đang chọn trong MinMin với bảng màu y hệt, không còn tự chuyển đen theo cài đặt của máy.

## [26.10.43] - 2026-10-03
### Sửa lỗi
- Nút mũi tên thu gọn dùng bộ biểu tượng của MinMin thay ký tự rời, khắc phục lỗi kiểm tra tự động trên bản trước.
### Cải thiện
- Hóa đơn và Zalo Forwarder dùng cùng bảng màu ngà và cam của MinMin, cả tông sáng lẫn tối.

## [26.10.42] - 2026-10-03
### Sửa lỗi
- Quả cầu tôn trọng tốc độ quay đã chọn, kể cả khi điện thoại bật giảm chuyển động. Nền khớp tông sáng có chiều sâu của Min Min.
- Thanh cuộc gọi và tiến độ có mũi tên thu gọn riêng, vẫn thấy trạng thái và phần trăm; thanh đầu trang điện thoại dùng nền rõ nét.
- ChatGPT Live nhận rõ kết quả đã hoàn tất để đọc, nhận cả lời đọc chỉ gửi transcript cuối, tránh thử đọc lại nhầm.
- Gemini nghe thử giữ âm thanh đến hết khi kết nối đóng. Nếu iPhone chặn phát tự động, bấm Nghe thử lần nữa phát bản đã tạo.

## [26.10.41] - 2026-10-03
### Sửa lỗi
- Khôi phục tông sáng có chiều sâu và kiểu nút cũ; giữ biểu tượng và bố cục hội thoại mới.

## [26.10.40] - 2026-10-03
### Sửa lỗi
- Tải PDF Petrolimex dùng đúng trình duyệt do MinMin quản lý trên VPS.

## [26.10.39] - 2026-10-03
### Cải thiện
- Diện mạo riêng của Min Min: nền trắng lạnh, xanh ngọc, khối phẳng và bộ biểu tượng hình học mới; thay bố cục nổi kem/tím cũ.
- Cột Không gian phiên bên phải gom ảnh/video, tệp và liên kết của từng hội thoại, có tìm kiếm, mở và tải xuống; trên điện thoại mở dạng ngăn bên.
- Bảng Tóm tắt trích các yêu cầu gần đây và kết quả gần nhất để xem nhanh nội dung phiên.
- Thanh tiến độ lớn ngay trên ô nhập, chuyển động mượt theo các bước xử lý thực tế. Phần trăm là ước tính; chỉ báo 100% khi lượt hoàn tất, phân biệt lỗi và dừng.

## [26.10.38] - 2026-10-03
### Cải thiện
- Tải hóa đơn BKAV tự tìm bằng định danh XML khi thiếu mã tra cứu. Petrolimex bằng mã trong XML, đối chiếu đúng hóa đơn trước khi lưu; sửa ngày hiển thị lệch múi giờ.
- Phân trang TCT, Gmail và cảnh báo; thêm số thứ tự, thu gọn cảnh báo, hiển thị rõ số đã chọn và cách xếp file ZIP.
- Nghe thử Gemini phát liền mạch; thêm nhịp nói Live, lựa chọn model và danh sách giọng.

## [26.10.37] - 2026-10-03
### Cải thiện
- Mic nhập chữ chờ nhả cuộc gọi cũ, hiện chữ trực tiếp và giữ cả chữ cuối khi bấm dừng. Không còn báo có bản nháp khi chưa nhận được chữ; lỗi mic hoặc mạng được báo rõ.
- Nút tắt mic và cúp máy tròn, lớn, có hiệu ứng. Cuộc gọi hiện tiến độ lấy dữ liệu/soạn câu trả lời và đổi nút Gửi thành Dừng khi đang xử lý.
- ChatGPT Live đọc kết quả theo từng đoạn, giữ phần cuối thay vì cắt 600 ký tự. Đọc thiếu sẽ thử tiếp phần chưa đọc; nếu vẫn lỗi có nút Đọc tiếp kết quả.
- Thêm Nhanh, Cân bằng, Kỹ: ưu tiên số liệu đã có đúng ngày/phạm vi hoặc yêu cầu đối chiếu lại. Mức Nhanh giữ kết nối lâu hơn khi im và nhắc rõ thời điểm khi dùng lại kết quả.


## [26.10.36] - 2026-10-03
### Sửa lỗi
- Sửa nút Nghe thử Gemini Live bị đứng chờ và không phát âm thanh.

## [26.10.34] - 2026-10-03
### Cải thiện
- Mic ở ô chat chỉ nhập lời nói thành bản nháp, không tự gửi khi ngừng nói. Xem lại rồi bấm Gửi; dừng mic hoặc rời trang vẫn giữ chữ đã nhập.
- Nút điện thoại riêng dùng để gọi Min Min và nhận trả lời trực tiếp; tránh bật nhầm cuộc gọi khi chỉ muốn nhập chữ.
- Chọn Gemini Live hoặc ChatGPT Live ngay trong cài đặt Giọng nói. Gemini có nghe thử giọng bằng lời chào Min Min, không mở mic; cần Gemini API key ở Bộ não AI.

## [26.10.33] - 2026-10-03
### Sửa lỗi
- Bổ sung tải bản gốc CyberBill qua mã tra cứu và CAPTCHA, đối chiếu XML hãng trước khi lưu PDF.

## [26.10.32] - 2026-10-03
### Sửa lỗi
- Thêm tải PDF gốc VIN-HOADON qua CAPTCHA ảnh; EFY dùng dịch vụ reCAPTCHA đã cấu hình. Đối chiếu XML hãng trước khi lưu PDF để tránh ghép nhầm hóa đơn.
- Sửa liên kết EFY để tự điền đúng số hóa đơn và mã tra cứu.

## [26.10.31] - 2026-10-02
### Sửa lỗi
- Kiểm tra và hoàn thiện phát hành luồng tải bản gốc SmartSign.

## [26.10.30] - 2026-10-02
### Sửa lỗi
- Hoàn thiện luồng tải bản gốc từ các nhà phát hành còn thiếu.

## [26.10.29] - 2026-10-02
### Cải thiện
- Ảnh AI vừa sửa hiện ngay trong câu trả lời, kể cả khi ghi đè file cũ; trình sửa file có bộ đếm từ và ký tự.
- Link chia sẻ lấy tên theo tiêu đề file, đổi tên và tìm theo tên được mà không đổi đường link.
- Sửa thanh công cụ bị che và gửi ảnh kéo thả trên iPhone.
- Cập nhật Docker kiểm tra bản đã đóng gói, báo rõ khi chưa thay được bản mới và bỏ trạng thái chờ khi khởi động bản mới thành công. Bộ cập nhật trong file cài đặt dùng Watchtower được bảo trì.

## [26.10.28] - 2026-10-02
### Cải thiện
- Bổ sung trang tra cứu nhà phát hành và mục chứng từ ngân hàng riêng trong hai bảng hóa đơn.

## [26.10.27] - 2026-10-02
### Sửa lỗi
- Tải bản gốc MY SOFTWARE bằng mã CQT có trong XML thuế, kể cả khi không có email hoặc mã tra cứu riêng. Đối chiếu đúng hóa đơn trước khi lưu PDF.
- Giữ mã tra cứu trong email có chứng từ đính kèm; mở thẳng PDF hãng khi đã có mã.

## [26.10.26] - 2026-10-02
### Sửa lỗi
- Nghe thử ChatGPT Live thực sự phát lời chào Min Min: chờ kênh âm thanh mở rồi gửi lệnh đọc; tạo tín hiệu im lặng để duy trì nhịp phát, không mở microphone.

## [26.10.25] - 2026-10-02
### Sửa lỗi
- Dùng mã tra cứu EFY đã tìm được từ Gmail khi mở trang nhà phát hành.
- Quét lại Gmail không tạo thêm dòng chỉ vì trang hãng tạo một file PDF có dữ liệu kỹ thuật khác lần trước.

## [26.10.24] - 2026-10-02
### Sửa lỗi
- Nghe thử ChatGPT Live bằng chính giọng đang chọn với lời chào “Min Min”, bỏ mẫu thu sẵn xưng Javis và số doanh thu minh họa.
- Nhắc giọng gọi phát âm tên thành hai tiếng Min Min, đọc tiếng Việt rõ dấu và số liệu tự nhiên.
### Cải thiện
- Phiên nghe thử chỉ phát âm thanh, không mở mic, không lưu hội thoại và không giao việc; tự đóng sau khi nghe thử.

## [26.10.23] - 2026-10-02
### Sửa lỗi
- Tự nối lại theo dõi tải hóa đơn và quét Gmail khi mất kết nối tạm thời, tránh dừng thanh tiến độ vì lỗi 502.
- Lưu và ghép từng hóa đơn Gmail ngay khi đọc được, giảm giữ file trong bộ nhớ và giữ lại kết quả nếu lượt quét bị gián đoạn.

## [26.10.22] - 2026-10-02
### Thêm mới
- ChatGPT Live qua WebRTC bằng phiên ChatGPT đã kết nối; chọn giọng và nghe thử ngay trong Tuỳ chỉnh → Giọng nói.
- Bấm mic để gọi liên tục, có thanh trạng thái, đồng hồ, tắt mic và cúp máy; tự chọn đường gọi phù hợp.
### Cải thiện
- Nói tiếp để nối lại sau 30 giây im lặng, chuẩn bị kết nối ngay khi nghe câu đầu; giữ màn hình sáng khi gọi.
- Tai Groq nghe lại câu Việt xen tiếng Anh khi đã có API key; cài đặt giọng nói tự lưu, chọn model riêng cho từng bộ não trả lời nhanh.
### Sửa lỗi
- Không đọc lặp hoặc chồng hai câu trả lời; nói chen ở đường Cơ bản không huỷ việc đang chạy.
- Nối lại thất bại không tự đổi giọng giữa cuộc gọi ChatGPT Live. Giữ tùy chọn ElevenLabs và thương hiệu MinMin.


## [26.10.21] - 2026-10-02
### Sửa lỗi
- Không lưu trang báo lỗi của cổng thuế thành ZIP hoặc PDF Trống đồng; nhận diện chứng từ lỗi đã lưu trước đây.

## [26.10.20] - 2026-10-02
### Sửa lỗi
- Đọc đúng số hóa đơn trong XML gửi qua Gmail có lớp thông điệp; khôi phục ghép bản gốc vào kho thuế.

## [26.10.19] - 2026-10-02
### Sửa lỗi
- Phân biệt hóa đơn chưa tải XML, chưa thử bản gốc và đã thử nhưng chưa thành công; hiển thị số lượng từng nhóm.
- Sửa nút mở trang hãng khi không có đường dẫn, thêm tải XML ngay trong hộp tra cứu và đọc mã SmartSign từ XML.
- Kết nối captcha trượt Viettel và luồng reCAPTCHA của HTInvoice với API giải captcha đã cấu hình.

## [26.10.18] - 2026-10-02
### Cải thiện
- Hóa đơn TCT và Gmail: lọc riêng có/chưa có XML, Trống đồng, PDF gốc; hiện số lượng theo từng bộ lọc.
- Gmail: tải bản Trống đồng đã ghép từ kho TCT, đưa vào ZIP cùng XML và PDF gốc, kèm bảng đối soát file.
- Zalo Forwarder: chặn xử lý lặp cùng mã tin, ngăn hàng đợi cũ gửi tiếp sau khi dừng/bật lại, cảnh báo khi hàng đợi đầy.
- Nhật ký Zalo: lọc lỗi/cảnh báo/thành công, tìm tài khoản hoặc nội dung và xuất CSV các dòng đang lọc.

## [26.10.17] - 2026-10-02
### Cải thiện
- Tra cứu đúng tab Mua vào hoặc Bán ra đang chọn; mặc định tra cả hoá đơn điện tử và máy tính tiền.
- Tải Hoá Đơn TCT tự đối chiếu cả bản gốc Gmail không kèm XML, kiểm tra MST hai bên, ký hiệu và số hoá đơn trước khi ghép.
- Thêm lọc hãng phát hành và bản gốc còn thiếu; mặc định chọn XML, Trống đồng và bản gốc khi tải.
- Giữ các hoá đơn đã chọn sau khi tải để xuất ZIP đúng phạm vi; file còn thiếu được liệt kê trong bản đối soát.


## [26.10.16] - 2026-10-02
### Sửa lỗi
- BKAV: tải thêm mẫu hoá đơn dùng nút tải file PDF có sẵn trong trang tra cứu.
- FAST/J&T: nhận đúng link PDF trong email, tránh nhầm link bảng kê vận đơn hoặc chỉ mở trang chủ. Quét lại email cũ để bổ sung link tải.

## [26.10.15] - 2026-10-02
### Sửa lỗi
- BKAV: tải PDF từ hoá đơn mở trực tiếp, không bắt khai báo captcha khi trang không yêu cầu.
- EasyInvoice: sửa địa chỉ tải, khôi phục nút Trang tra cứu cho dữ liệu Gmail cũ.
- Gmail: lọc hãng phát hành và chứng từ cần tải lại rồi tải cả danh sách bằng một nút. Báo kết quả từng hoá đơn và tiếp tục khi một hoá đơn lỗi.

## [26.10.14] - 2026-10-01
### Cải thiện
- Hoá đơn: nhập API key 2Captcha/OmoCaptcha, kiểm tra số dư và bật giải captcha khi tải bản gốc. Xem, sao chép và bổ sung mã tra cứu ngay tại mỗi hoá đơn.
- Gmail: tích chọn chứng từ để tải lại, xuất Excel/ZIP, ghép kho hoặc in gộp PDF. File còn thiếu được báo rõ.
- Cả hai danh sách có kỳ tháng/quý/nửa năm, lọc nhà cung cấp, số hoá đơn, khoảng tiền và sắp xếp tăng/giảm. Tải và xuất dùng đúng danh sách đã chọn hoặc đang lọc.


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
