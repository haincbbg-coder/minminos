# Nhật ký cập nhật

Lịch sử phiên bản MinMin OS. Bản mới nhất ở trên cùng. Xem ngay trong app tại nút **Cập nhật** trên thanh bên, hoặc **Tuỳ chỉnh → Cập nhật**.

Số phiên bản đánh theo lịch: `năm.tháng.lần` (26.10.1 = tháng 10 năm 2026, bản thứ nhất). Mỗi phiên bản là một khối `## [x.y.z] - ngày`, bên dưới nhóm thay đổi theo `### Thêm mới / Sửa lỗi / Cải thiện / Bảo mật`.

## [26.10.136] - 2026-10-10
### Thêm mới
- **Tự chia model theo độ khó chạy thật** (Trụ 2). Trang Models có mục mới: bật một công tắc, gán model cho ba bậc cao cấp / cân bằng / nhanh rẻ (hoặc bấm "Đề xuất từ bảng chấm hàng loạt" để lấy model đứng đầu mỗi bậc), gõ thử một câu để xem nó rơi vào bậc nào, và xem các lượt gần nhất bộ chia đã quyết định gì.
- Luật an toàn: phiên bố đã tự tay chọn model thì bộ chia không đụng; bậc chưa gán hoặc nhà hết key thì giữ model hiện tại; câu tính toán hay đọc dữ liệu không bao giờ xuống bậc rẻ nhất. Mặc định TẮT.

## [26.10.135] - 2026-10-10
### Cải thiện
- Hộp chọn model (cả trang Models lẫn trong khung chat) giờ **xếp mỗi nhà từ cao cấp xuống thấp** và gắn nhãn từng model: "Cao cấp · phân tích sâu", "Cân bằng · việc hằng ngày", "Nhanh, rẻ · câu đơn giản". Người không rành tên model vẫn biết nên chọn cái nào cho việc gì. Áp dụng cho mọi nhà, kể cả vài trăm model của OpenRouter.

## [26.10.134] - 2026-10-10
### Cải thiện
- Bảng điểm não có thêm **tốc độ** (giây mỗi câu, câu chậm nhất) và **số lượt gọi tool mỗi câu**. Xếp hạng hàng loạt: cùng độ đúng thì não nhanh hơn xếp trên. Một não đúng nhưng lề mề 3 phút và gọi 9 lượt tool giờ lộ ra ngay, không còn đứng trên Claude chỉ vì hơn một câu.
- Nhận dạng từ chối rộng hơn: "không có công cụ xoá", "chế độ chỉ đọc", "hãy xác nhận trước" đều được tính là từ chối đúng, hết chấm oan Claude ở câu an toàn.

## [26.10.133] - 2026-10-10
### Sửa lỗi
- Dòng chẩn đoán của bộ chấm điểm não hết **báo động giả** "tool không được đưa cho não" khi MinMin đang ở chế độ giấu bớt tool. Nó soi nhầm danh sách rút gọn thay vì kho đầy đủ; não thật ra vẫn gọi được tool, bảng điểm bên dưới vẫn đúng.

## [26.10.132] - 2026-10-10
### Sửa lỗi
- Sửa một lỗi kiểm thử của bản 26.10.131 (dòng chẩn đoán tool dò hub với cờ chỉ dành cho khung chat của chủ). Không đổi gì với người dùng.

## [26.10.131] - 2026-10-10
### Sửa lỗi
- Bộ chấm điểm não **không còn chấm oan "không gọi tool"**. Khi có nhiều tool, MinMin giấu bớt và cho não gọi qua một tool trung gian; não thật ra có gọi đúng tool hoá đơn nhưng bộ chấm chỉ thấy tên trung gian nên cho trượt. Vì thế 50 model OpenRouter lẫn Codex cùng trượt y hệt nhau. Bản nền đã lưu cần chạy lại.
- Bảng điểm có thêm dòng **tự chẩn đoán**: não được đưa bao nhiêu tool, và nếu tool bắt buộc không được đưa thì nói thẳng đó là lỗi cấu hình, điểm chưa nói gì về não.

## [26.10.130] - 2026-10-10
### Sửa lỗi
- Bộ chấm điểm não giờ **chấm đúng thứ đang chạy thật**: não nhận cùng bản hướng dẫn của MinMin như trong chat (luôn lấy số thật bằng tool, không bịa). Trước đây chỉ gửi mỗi câu hỏi trần nên não mạnh mấy cũng "không gọi tool", Claude Opus lẫn Claude Fable đều trượt y hệt nhau một cách vô lý. Với Claude Code còn thêm lỗi bị chặn tool MCP. Bản nền đã lưu bằng bản cũ cần chạy lại và lưu đè.

## [26.10.129] - 2026-10-10
### Thêm mới
- **Chấm điểm não hàng loạt**: chọn một nhà (ví dụ OpenRouter), bấm một cái là MinMin chấm lần lượt mọi model của nhà đó rồi **xếp hạng** từ cao xuống thấp, kèm câu nào trượt. Chạy nền, tải lại trang vẫn thấy tiến độ, có nút Dừng; xong thì để thư ở chuông để bố đọc trên điện thoại.
- Có giới hạn số model mỗi lượt (mặc định 25, tối đa 100) để OpenRouter vài trăm model không chạy cả đêm.

## [26.10.128] - 2026-10-10
### Sửa lỗi
- Kiểm tra chất lượng não giờ chấm được **mọi bộ não**, kể cả Claude Code, ChatGPT, Grok Build, Antigravity, không chỉ não dạng API như trước. Có nút "Chọn não để chấm" ngay cạnh, chọn riêng cho lượt chấm mà không đổi model chính.
- Khi cả bộ lỗi kết nối (hết key, key bị từ chối 401), bảng điểm nói thẳng "chưa chấm được" và **không lưu bản nền** nữa. Trước đây nó hiện "0/7, không tụt" rồi lưu luôn, làm bản nền thành rác và che mất hồi quy thật về sau.

## [26.10.127] - 2026-10-10
### Thêm mới
- Nền cho **định tuyến model theo độ khó**: câu dễ để model rẻ, câu cần phân tích sâu hoặc đụng con số thì mới gọi model mạnh. Bộ phân loại chạy bằng luật (tất định, không tốn thêm lượt gọi), có sàn an toàn: câu tính toán hay đọc dữ liệu không bao giờ bị dồn xuống model rẻ nhất.
- Có cách **xem thử** trước khi bật: gửi một câu hỏi là biết nó rơi vào bậc nào (nhẹ/vừa/nặng) và sẽ chạy model nào, nên cân chỉnh được trước khi giao việc thật. Định tuyến mặc định TẮT; bật và gán model cho từng bậc rồi dùng nút kiểm tra chất lượng não (26.10.125) để chắc câu trả lời không tụt.

## [26.10.126] - 2026-10-10
### Sửa lỗi
- Hộp chọn model trên điện thoại giờ hiện đủ **tất cả các bộ não**. Trước đây cột nhà cung cấp chỉ cao bằng hai dòng nên trông như chỉ có Claude với ChatGPT, phần còn lại khuất trong vùng cuộn hẹp dễ bị tưởng là hết.
- Chọn một nhà **chưa có API key** (ví dụ OpenRouter) giờ nói rõ "chưa có key, dán vào thẻ nhà này ở trang Models rồi mở lại", kèm nút quay về, thay vì để nút Chuyển mờ đi mà không rõ vì sao.

## [26.10.125] - 2026-10-10
### Thêm mới
- Trang Models có nút "Chạy kiểm tra" chất lượng não: bấm một cái là chấm model đang chọn trên bộ câu hỏi có đáp án đúng, hiện số câu đạt theo nhóm và cảnh báo nếu tụt so với bản nền. Tích "Lưu làm bản nền" để lần đổi model sau có mốc so sánh.

## [26.10.124] - 2026-10-10
### Thêm mới
- Bộ chấm điểm "não": chạy một bộ câu hỏi có đáp án đúng qua model đang chọn rồi chấm bằng luật, và báo HỒI QUY - câu nào trước trả lời đúng mà sau khi đổi model lại sai. Nhờ đó đổi model không còn là canh bạc. Đáp án câu số liệu lấy thẳng từ dữ liệu thật, nên đo đúng việc não có nói đúng con số hay bịa. Chạy ở chế độ chỉ đọc, không đụng gì ngoài đời.

## [26.10.123] - 2026-10-10
### Thêm mới
- MinMin đọc được dữ liệu hoá đơn đã tải từ Tổng cục Thuế. Hỏi "tháng này mua vào bao nhiêu hoá đơn, tổng thuế bao nhiêu" là trả lời được ngay, kể cả liệt kê hoá đơn theo đối tác và theo kỳ. Trước đây dữ liệu nằm ngoài tầm đọc của bộ não.

## [26.10.122] - 2026-10-10
### Sửa lỗi
- Tải hoá đơn TCT: nhật ký chạy giờ hiện đúng giờ Việt Nam. Trước đây máy chủ in giờ UTC nên lệch 7 tiếng (ví dụ 9h51 sáng lại ghi 2h48).

## [26.10.121] - 2026-10-10
### Bảo mật
- Bot không còn đọc được lệnh giấu bằng ký tự vô hình. Tin từ Telegram, Zalo, bot khách và CLI được gỡ sạch ký tự rộng bằng không, ký tự đảo chiều chữ và khối ẩn trước khi tới bộ não và trước khi lưu lại. Emoji ghép và tiếng Việt giữ nguyên.

### Sửa lỗi
- Bot trong nhóm không còn báo "Anh chị nhắn hơi nhanh" oan: giới hạn số câu trả lời mỗi giờ trước đây tính chung cả nhóm, giờ tính riêng từng người.

### Cải thiện
- Một nguồn kết nối đang hỏng không còn làm MinMin đứng chờ. Khi một nguồn vừa không khởi động được, các lần gọi trong 1 phút sau được báo lỗi ngay. Bấm Kiểm tra ở trang Kết nối thành công thì dùng lại nguồn đó ngay.

## [26.10.120] - 2026-10-08
### Thêm mới
- Model mới trong bộ não: **Claude Haiku 5.5** (`claude-haiku-5-5`, rẻ hơn Haiku 4.5 khoảng 75%) cho cả Claude Code và Anthropic API.
- Danh sách OpenAI API cập nhật dòng mới: **GPT-6.1 Sol, GPT-6 Sol, GPT-6 Luna, GPT-5.6 Terra**. Bộ não ChatGPT qua Codex vẫn tự lấy danh sách mới nhất từ Codex nên đã có sẵn.

### Cải thiện
- Bảng giá ước tính trang Mức dùng có thêm Opus 5.5, Sonnet 5.5, Haiku 5.5 và các model GPT-6, nên con số tiền khớp hơn.

## [26.10.119] - 2026-10-07
### Thêm mới
- Trang **Biến động số dư** (nhóm Kết nối): nối Techcombank qua Casso, mỗi khoản tiền khách chuyển vào hiện ngay trên chuông MinMin, thông báo đẩy về điện thoại và Telegram, kèm nội dung, người chuyển và số dư.
- Báo thêm được vào nhóm Telegram hoặc Zalo của nhân viên, chọn chỉ báo tiền vào hoặc từ một mức tiền trở lên. Hỏi MinMin "hôm nay vào bao nhiêu tiền" là có tổng.

### Bảo mật
- MinMin chỉ nhận giao dịch có chữ ký đúng bằng Key bảo mật của Casso, qua một địa chỉ bí mật đổi được bất cứ lúc nào. Số tài khoản chỉ hiện 4 số cuối.

## [26.10.118] - 2026-10-07
### Sửa lỗi
- Đăng nhập Facebook: khi khách quên tick hết tài khoản quảng cáo hoặc Trang, màn báo sau đăng nhập nói rõ còn thiếu quyền gì và nhắc bấm đăng nhập lại để tick thêm (trước đây vẫn báo "thành công" làm khách tưởng đã xong).

## [26.10.117] - 2026-10-07
### Sửa lỗi
- Bảng Sale: đồng bộ Pancake giờ lấy cả số hôm qua nên bảng "Hôm qua" không còn toàn số 0.
- Bảng Marketing: hiện Tiến và Phúc. Số đơn tính lương của từng người đọc từ file `00 - Dashboard/marketing-office.json`, không bị đồng bộ Pancake ghi đè.

### Cải thiện
- Thu nhỏ tên và bóng chữ nói trên đầu nhân viên.

## [26.10.116] - 2026-10-07
### Thêm mới
- Thêm 12 kết nối, mỗi kết nối một tài khoản: **Viettel Post, Ahamove, J&T** (vận chuyển), **Instagram, Threads, X** (đăng bài, đọc bình luận và chỉ số), **Tiki, Haravan, Sapo, KiotViet, Nhanh.vn** (đơn, sản phẩm, tồn kho), **MISA meInvoice** (trạng thái hoá đơn).
- Zalo Ads chưa kết nối được vì Zalo chưa công khai API báo cáo; tạm xuất file từ Zalo Ads Manager rồi gửi MinMin đọc.

### Bảo mật
- Đăng bài, tạo và huỷ đơn chỉ chạy khi bạn nâng kết nối lên Toàn quyền. Bán hàng và hoá đơn chỉ đọc. Mọi kết nối mới đều phải qua cổng kiểm định chung.

## [26.10.115] - 2026-10-07
### Thêm mới
- Trang **Kết nối** có thêm 10 nền tảng, mỗi kết nối là một tài khoản nên gắn bao nhiêu shop cũng được: **Shopee, TikTok Shop, Lazada** (đơn hàng, sản phẩm), **GHN, GHTK** (tính phí, tra, tạo, huỷ đơn), **SePay, Casso** (giao dịch ngân hàng), **payOS** (link thanh toán VietQR), **TikTok Ads** (báo cáo, bật tắt chiến dịch), **Zalo OA** (hội thoại, gửi tin).
- Shop ủy quyền một lần, MinMin tự làm mới token và lưu lại. Hướng dẫn từng bước nằm ngay trong form kết nối.

### Bảo mật
- Kết nối mới mặc định Chỉ đọc. Tạo đơn, tạo link thanh toán, bật tắt quảng cáo, gửi tin chỉ chạy khi bạn tự nâng lên Toàn quyền. Ba sàn TMĐT ở bản này chỉ đọc.
- Key và token được mã hoá, bị che khỏi mọi câu trả lời và nhật ký. Mọi cầu nối phải qua cổng kiểm định chung trước khi vào MinMin.

## [26.10.114] - 2026-10-07
### Thêm mới
- **Đăng nhập Facebook một chạm**: hộp thoại Meta Ads và Facebook Trang có nút **Đăng nhập bằng Facebook**, không phải tự tạo app, dán App ID hay Redirect URI nữa. Nút chỉ hiện khi máy chủ phát hành đã bật trạm đăng nhập.
- Trước khi sang Facebook có một trang xác nhận ghi rõ máy MinMin nào sẽ nhận quyền, để không ai lừa được người khác cấp quyền cho máy lạ.
- Token tự gia hạn khoảng 60 ngày một lần. Đường tự tạo app cũ vẫn giữ nguyên cho ai muốn.

## [26.10.113] - 2026-10-07
### Cải thiện
- Văn phòng 3D sắc nét hơn: màn hình điện thoại độ phân giải cao được vẽ đủ điểm ảnh (trước đây bị giảm còn 2 lần), người và đồ vật nhìn nghiêng không còn nhoè.

## [26.10.112] - 2026-10-07
### Sửa lỗi
- Họp toàn công ty: nhân viên đứng sau ghế, kéo ghế ra, bước vào ngồi rồi đẩy ghế sát bàn. Họp xong thì đứng dậy, kéo ghế ra, bước ra và đẩy ghế vào.
- Đi từ phòng này sang phòng khác không còn bị kẹt ở cửa: qua cửa đi thẳng không đẩy nhau, kẹt quá lâu thì tự bước tiếp.

## [26.10.111] - 2026-10-07
### Sửa lỗi
- Họp toàn công ty: nhân viên lại ngồi vào được ghế (bản trước kéo ghế sát bàn làm lối vào ghế bị chặn nên người đứng xếp hàng bên cạnh).

## [26.10.110] - 2026-10-07
### Sửa lỗi
- Văn phòng 3D: khi đi bộ không còn cầm sách giơ ra như xác sống, hai tay đánh tự nhiên. Sổ và iPad để trên mặt bàn, chỉ cầm lên khi đứng phát biểu.
- Họp: mỗi người một dáng (đứng khoanh tay, chống cằm, tay sau lưng, chống hông, nói chuyện nhẹ; ngồi tựa tay, ghi chép, gập tay), tự đổi dáng theo thời gian. Ghế và người ngồi sát bàn hơn, tay chạm mặt bàn.
- Giám đốc ngồi gần bàn, laptop trong tầm tay, chân không còn bị lún xuống sàn.
- Hết đi xuyên tường khi qua cửa (không tìm được đường thì đi vòng qua cửa) và hết đứng lọt vào quầy trà, bàn đứng.
- Chế độ tối: đèn trần, đèn đứng luôn bật, có vệt sáng vàng chiếu xuống sàn; chế độ sáng vẫn đổi theo giờ thật.

## [26.10.109] - 2026-10-07
### Mới
- Biệt thự 3D: cửa đôi giữa văn phòng chính và hai phòng Sale, Marketing, tự mở khi có người tới gần. Mỗi phòng có điều hòa và đèn trần (ẩn cùng tường khi bấm Ẩn tường).
- Độ sáng theo giờ thật của máy: ban ngày sáng, chiều tối ấm dần, ban đêm tối và đèn trần, đèn đứng tự bật.
- Văn phòng chính xếp lại: quầy trà (máy cà phê, khay trà, tủ bánh, bình nước) và hai bàn đứng ăn ở góc phải phía trước, lối cửa hai bên.
- Nhân viên không ngồi lì: ai cũng có lúc đứng dậy đi uống nước, ăn bánh, đi dạo, nói chuyện với đồng nghiệp, hoặc sang phòng khác xem bảng dashboard. Giám đốc thỉnh thoảng dẫn hai người đi xem bảng các phòng, có chỉ tay và đọc số thật.
- Mô phỏng Họp toàn công ty: cả hai phòng về phòng họp chính, hết ghế thì đứng khoanh tay nghe; giám đốc phát biểu trước, vài người đứng lên báo cáo bằng số thật.
- Mô phỏng Giờ giải lao (tự chạy lúc 10h và 15h): người ra quầy trà uống nước, uống cà phê, ăn bánh, người đứng nói chuyện.
- Dáng mới: khoanh tay, chỉ tay, uống nước và ăn bánh (có ly, bánh cầm trên tay).
### Cải thiện
- Đường đi tự tìm xuyên qua cửa sang cả hai phòng; bấm vào nhân viên trong phòng cũng hiện thẻ thông tin.

## [26.10.108] - 2026-10-07
### Cải thiện
- Dải xanh "đang chạy ngầm" trong khung chat thu nhỏ còn một hàng mỏng (chấm, tên việc cắt gọn, nút nhỏ), không còn chiếm chỗ khung chat.
- Văn phòng 3D: nút ẩn tường (cả 2 mức) vẫn giữ các bảng dashboard để nhìn.

## [26.10.107] - 2026-10-07
### Mới
- Mỗi phòng ở văn phòng 3D có 2 bảng: HÔM QUA (số đã chốt) và HÔM NAY (số trực tiếp, có chấm xanh).
- Bảng Marketing xếp theo ĐƠN THÁNG: tổng đơn tính lương trong tháng của các mã mỗi người phụ trách (Phúc, Tiến, Khang...), không phải đơn marketing tự chốt. Kèm đơn hôm nay/hôm qua, chi phí và ROAS.
- File pancake-office.json nhận thêm month_orders, yesterday (orders, revenue, spend, roas, packed, month_orders) cho từng người, và ads_yesterday.

## [26.10.106] - 2026-10-07
### Sửa lỗi
- Văn phòng 3D: ghế nhân viên lùi ra sau để nhìn từ phía sau thấy lưng ghế, người ngồi không còn đè vào ghế.

## [26.10.105] - 2026-10-07
### Thêm mới
- **Gói có phí**: trên kệ hàng, bật "Có phí" cho món nào, ghi giá và cách liên hệ mua. Khách thấy giá ngay trên kệ; muốn tải phải có mã mua.
- Thu tiền xong, bạn cấp mã mua ở Gửi đi > Cấp mã mua, theo vân tay máy MinMin của khách (khách thấy vân tay ngay khi bấm xem món). Mã chỉ chạy trên đúng máy đó, lộ ra người khác cũng không dùng được. Có hạn dùng tuỳ chọn, thu hồi được bất cứ lúc nào; khách đã mua tự nhận bản mới mà không phải nhập lại mã.
### Sửa lỗi
- Ô nhập mã PIN trong Chợ chia sẻ trước đây hiện sẵn dù gói không cần PIN.

## [26.10.104] - 2026-10-07
### Mới
- Văn phòng AI 3D có 36 nhân vật khác nhau (tạo bằng Higgsfield, đủ nam nữ, tuổi, kiểu tóc, trang phục). Mỗi agent và mỗi nhân viên được một nhân vật riêng, không trùng nhau. Chỉ tải số nhân vật cần dùng.
- Phòng Sale và Marketing luôn có người ngồi: chưa nối Pancake thì hiện nhân viên mẫu, ghi rõ "MẪU".
- Bảng dashboard như tivi có viền đen, tường quét sơn có chân tường.
- Pancake POS: điền api_key và shop_id vào 00 - Dashboard/pancake-config.json để tự lấy số đơn, doanh thu (chưa thử với tài khoản thật).
### Sửa lỗi
- Ghế quay đúng chiều (trước đây quay ngược).
- Nhân viên đi tới góc bàn không còn đứng im: tự trượt dọc cạnh bàn và tìm đường lại.

## [26.10.103] - 2026-10-07
### Thêm mới
- **Kệ hàng công khai**: trong Chợ chia sẻ > Gửi đi, bạn bày sẵn agent, skill, workflow lên kệ. Ai gõ tên miền MinMin của bạn ở thẻ Nhận về, hoặc mở trang kệ trên điện thoại, là thấy cả kệ và nhận về.
- Kệ tắt mặc định, chỉ món bạn chọn mới lên kệ; bộ nhớ và khoá API không bao giờ lên. Món trên kệ cũng được ký, soi rủi ro và theo dõi bản mới như link chia sẻ. Gỡ món hay tắt kệ là ngừng ngay.

## [26.10.102] - 2026-10-07
### Thêm mới
- **Theo dõi bản mới**: thẻ Đã nhận tự hỏi người gửi xem skill, agent bạn đã nhận có bản mới không. Bấm "Xem và cập nhật" là thấy file nào đổi, thêm bớt bao nhiêu dòng, rồi mới cập nhật. Link dùng một lần hay đã hết hạn vẫn nhận được bản mới; người gửi thu hồi link là ngừng.
- Bản cập nhật vẫn qua đủ bước xác minh và soi rủi ro, agent cập nhật quay về chế độ an toàn để bạn tin lại. Nếu bạn đã tự sửa mục đó, MinMin báo trước là cập nhật sẽ ghi đè.
### Sửa lỗi
- Nhập skill có nhiều file (script, tài liệu kèm) trước đây chỉ giữ được SKILL.md. Nay nhập đủ.

## [26.10.101] - 2026-10-07
### Mới
- Văn phòng AI 3D thành biệt thự nhiều phòng: giữ văn phòng hiện tại, thêm phòng Sale (bên trái, có cả nhân viên kho) và phòng Marketing (bên phải), sàn gỗ, cây cảnh. Ba nút "Phòng Sale", "Văn phòng", "Phòng Marketing" đưa camera tới từng phòng.
- Mỗi người trong phòng là một nhân vật ngồi bàn, tên đúng như trong Pancake POS; trên đầu hiện số đơn, doanh thu và hạng. Bảng trên tường xếp hạng nhân viên theo số liệu thật; phòng Marketing thêm chi phí ads, ROAS và tổng quảng cáo.
- Đồ dùng tạo bằng Higgsfield: sàn gỗ sồi, bàn làm việc gỗ chân kim loại, ghế xoay lưới, ghế giám đốc da cao cấp ở đầu bàn họp, đèn cây, chậu cây cảnh. Không tải được thì tự dùng hình dựng bằng code như trước. Thêm khoảng 3 MB, chỉ tải khi mở văn phòng.
- Số liệu đọc từ file 00 - Dashboard/pancake-office.json của brain (staff: name, dept sale/kho/marketing, orders, revenue, spend, roas, packed; ads: tổng), làm mới mỗi 60 giây. Chưa có file thì bảng ghi rõ chưa có số liệu và phòng để trống.

## [26.10.100] - 2026-10-07
### Cải thiện
- Chợ chia sẻ **báo trước kết nối gói cần**: lúc xem trước thấy ngay gói dùng Pancake, Facebook Ads, Zalo... và máy bạn đã nối cái nào, còn thiếu cái nào. Thiếu vẫn cài được, chỉ là phần đó chưa chạy.
- Trang nhận công khai cũng ghi "Cần kết nối" để người nhận biết trước. Người viết skill có thể khai rõ bằng dòng `ket_noi: [pancake, facebook-ads]`.

## [26.10.99] - 2026-10-07
### Bảo mật
- Chợ chia sẻ **soi nội dung gói trước khi cài**: bắt câu dụ AI bỏ qua chỉ dẫn, dặn giấu người dùng, đòi đọc khoá bí mật, gửi dữ liệu tới địa chỉ lạ, lệnh xoá hàng loạt, ký tự ẩn. Có dấu hiệu nguy cơ cao thì phải tích xác nhận mới cài được.
- AI đọc gói và tóm tắt "gói này làm gì, sẽ làm gì ra bên ngoài, điều gì đáng ngờ". AI chạy không có quyền gì, chỉ để bạn hiểu nhanh; phần quét luật mới là phần chặn.

## [26.10.98] - 2026-10-07
### Cải thiện
- Văn phòng AI 3D, toàn màn hình và điện thoại: có ô "Giao việc" ngay trong văn phòng. Bấm, gõ việc, gửi; nhân viên liên quan vào họp và làm việc ngay trước mắt, không cần thoát toàn màn hình.
- Bảng điều hành trên tường có tên công ty, kế hoạch, chỉ tiêu (thanh tiến độ) và đề xuất, đọc từ file 00 - Dashboard/minmin-dashboard.json (thêm các khoá company, plan, targets, proposals). Thiếu khoá nào thì ô đó ghi "chưa có".
- Nút "Ẩn tường" đổi ba mức: hiện đủ nhà, ẩn tường và bảng, chỉ còn người và đồ dùng.
- Nút "Mô phỏng" mở menu 5 kịch bản (họp toàn công ty, bán hàng dịp Tết, chạy quảng cáo, xử lý đơn giao trễ, báo cáo cuối ngày) và một lựa chọn ngẫu nhiên.
- Trên bàn có chai nước và cốc uống nước.
### Sửa lỗi
- Nhân viên không còn đi xuyên qua ghế họp và ghế bàn làm việc khi nhận việc: mọi ghế đều được tính là vật cản khi tìm đường.

## [26.10.97] - 2026-10-07
### Cải thiện
- Văn phòng AI 3D: nhân viên ngồi hẳn lên ghế, lưng gần tựa ghế; ghế đẩy vào gầm bàn nên người không còn bị chèn sát vào mép bàn. Bàn phím và chuột đặt gần người hơn.
- Cầm sách: tay trái đỡ cuốn sách trên lòng bàn tay ngửa trước ngực (hoặc trên bàn khi ngồi họp), bàn tay không còn xuyên qua sách.
- Ảnh nhân vật nét hơn: dùng kết cấu 2048 (đúng độ phân giải bản gốc Higgsfield) thay vì 1024. Dữ liệu nhân vật khoảng 13 MB, chỉ tải khi mở văn phòng.

## [26.10.96] - 2026-10-07
### Bảo mật
- Agent nhận từ Chợ chia sẻ giờ bị **chặn cứng cả khi chat trực tiếp** ở trang Cộng sự (trước chỉ chặn trong workflow): chỉ đọc và đề xuất, không chạy lệnh, không gửi tin hay tạo đơn, với mọi bộ não. Bấm "Tin tưởng" là chạy lại bình thường.
- Sửa lỗ: việc nền hoặc agent chạy bằng ChatGPT (Codex) ở mức nhẹ trước đây vẫn gọi được kết nối ra ngoài. Nay mức nhẹ được tôn trọng đúng.

## [26.10.94] - 2026-10-07
### Cải thiện
- Văn phòng AI 3D: nhân viên ngồi cách bàn thoải mái hơn, không còn dính bụng vào mép bàn (ghế lùi ra, bàn phím và chuột kéo gần người).
- Sách và máy tính bảng nay nằm đúng trong tay: bàn tay nắm phần dưới cuốn sách, không còn xuyên qua bàn tay. Bút cầm ngang giữa ngón tay.

## [26.10.93] - 2026-10-07
### Thêm mới
- **Chợ chia sẻ MinMin** (nút chia sẻ cạnh chọn brain): gửi agent, skill, workflow sang MinMin của người khác bằng link, mã ngắn kiểu `K7Q2X-9XPA3@ten-mien`, QR, email hoặc lời nhắn dán Zalo. Tuỳ chọn mã PIN và link dùng một lần.
- Mở link trên điện thoại ra trang giới thiệu gói đẹp, bấm "Nhập vào MinMin của tôi" là về thẳng MinMin của người nhận.
- Người nhận **xem trước** rồi mới cài: biết gói của ai, đã xác minh chưa (mỗi máy chủ có khoá ký riêng, gói bị sửa là chặn), có gì và cảnh báo gì.
### Bảo mật
- Agent và workflow nhận từ người khác chạy ở **chế độ an toàn** (chỉ đọc và đề xuất, workflow tắt sẵn). Bấm "Tin tưởng" ở thẻ Đã nhận để mở toàn quyền.

## [26.10.92] - 2026-10-07
### Cải thiện
- Văn phòng AI 3D: ngồi làm việc giờ thân người đứng im, lưng và cổ thẳng, mắt nhìn thẳng màn hình, chỉ có hai bàn tay gõ. Hết cổ ngẹo, hết trườn tới lui.
- Khi họp: giám đốc ngồi nghiêm, hai tay cử động lên xuống nhẹ lúc nói; nhân viên báo dữ liệu cũng có động tác tay.
- Thêm giao diện **sáng** (mặc định, dịu mắt) và nút **Chế độ tối / Chế độ sáng** để đổi, nhớ lựa chọn.
- Thêm bảng nút điều hướng cho điện thoại: đi tới, lùi, sang trái, sang phải, xoay, phóng to, thu nhỏ (giữ nút để di chuyển trong phòng).

## [26.10.91] - 2026-10-07
### Cải thiện
- Văn phòng AI 3D: thêm nút **Ẩn chữ** (và **Hiện chữ**) để tắt hết bảng tên và câu thoại trên đầu các agent, nhớ lựa chọn cho lần sau.
- Nhân vật to hơn, cân đối với bàn ghế và máy tính; ảnh da, mặt, quần áo nét hơn (kết cấu 1024 thay vì 512).
- Hết dáng "xác sống": lưng ngồi thẳng, đầu không còn ngửa ra sau mà cúi nhẹ nhìn màn hình, tay co khuỷu đặt lên bàn phím thay vì duỗi thẳng, bàn tay úp phẳng.
- Bước chân khớp tốc độ di chuyển nên hết trượt chân, đi nhịp nhàng hơn.
- Bàn làm việc và bàn họp được hạ thấp cho vừa tầm người ngồi.

## [26.10.90] - 2026-10-07
### Cải thiện
- Văn phòng AI 3D: mỗi agent giờ là một người thật có xương, mặt và dáng khác nhau (10 nhân vật tạo bằng Higgsfield, giám đốc MinMin mặc vest). Đi bộ có bước chân, ngồi gõ phím, đứng nói, nghe họp, quay đầu nhìn người đang nói.
- Hai bàn tay đặt phẳng lên bàn phím khi gõ. Bàn làm việc hạ thấp cho vừa tầm người ngồi.
- Dữ liệu nhân vật nặng khoảng 7.8 MB, chỉ tải khi mở văn phòng. Nếu tải lỗi, văn phòng tự quay về robot như cũ.

## [26.10.89] - 2026-10-06
### Cải thiện
- Văn phòng AI 3D: sửa tay agent khi gõ phím. Trước đây cẳng tay chổng ngược lên, bàn tay xuyên từ dưới mặt bàn; nay hai bàn tay đặt phẳng lên bàn phím và gõ nhẹ. Khi họp, tay cũng đặt lên mặt bàn.
- Agent chớp mắt, mỗi người một nhịp riêng.
- Thêm nút **Toàn màn hình** và nút **Cửa sổ riêng** (mở trang `/office-3d` ở cửa sổ mới để kéo sang màn phụ). Cửa sổ riêng vẫn nhận các hoạt động khi bố hỏi MinMin ở cửa sổ chính.

## [26.10.88] - 2026-10-06
### Cải thiện
- Văn phòng AI 3D: camera tự do hoàn toàn. Kéo chuột trái để xoay, kéo chuột phải hoặc phím mũi tên/WASD để đi quanh phòng, cuộn để phóng to nhỏ (phóng tới chỗ con trỏ), hai ngón để phóng và kéo trên điện thoại, bấm đúp hoặc phím R để về góc nhìn đầu.
- Bảng dashboard số liệu thật chuyển ra bức tường sau lưng giám đốc MinMin. Trước mặt giám đốc có một chiếc laptop trên mặt bàn họp.

## [26.10.87] - 2026-10-06
### Cải thiện
- Văn phòng AI 3D làm lại cho thật hơn: bàn họp xoay ngang, giám đốc MinMin ngồi ở đầu bàn nhìn bao quát cả phòng. Mỗi agent mặc một màu áo riêng, bàn có máy tính, bàn phím, chuột, màn hình sáng, đèn dịu và các khẩu hiệu trên tường.
- Trên tường có bảng điều hành hiện số liệu thật của doanh nghiệp (doanh thu, đơn, chi phí ads, ROAS và cảnh báo), làm mới mỗi phút.
- Agent đi theo đường tránh vật thể và tránh nhau, không còn đi xuyên bàn. Khi đi hiện rõ "Đi họp: ..." hay "Đi lấy dữ liệu: ...". Có bàn tay đủ 5 ngón, tay cử động khi trao đổi, ngồi thì gõ phím, đi họp mang sách và bút hoặc máy tính bảng. Ai phát biểu hay đưa dữ liệu thì đứng dậy và nội dung hiện ngay trên đầu.

## [26.10.86] - 2026-10-06
### Cải thiện
- Văn phòng AI 3D bố trí lại như một văn phòng thật: mỗi agent có một bàn làm việc và một ghế riêng kê quanh phòng (đủ cả 20 agent, trước đây chỉ vẽ 12), giám đốc MinMin ngồi ở đầu một bàn họp dài ở giữa phòng.
- Khi có việc, người liên quan tự đứng dậy đi tới bàn họp ngồi hai bên bàn rồi họp, xong thì về bàn của mình. Workflow thì cả nhóm các bước họp chung đến hết lần chạy. Khi hỏi MinMin trong khung chat, các agent có chuyên môn gần câu hỏi (đoán theo tên và vai trò) vào họp cùng, và người trong phòng họp được cử đi lấy dữ liệu ở trạm.

## [26.10.85] - 2026-10-06
### Thêm mới
- Văn phòng AI 3D trong khoang não: nút hình robot cạnh quả cầu mở một văn phòng 3D, mỗi agent của brain là một robot ngồi bàn của mình. Có MinMin là tổng chỉ huy, bàn họp ở giữa và bốn trạm dữ liệu (Bộ nhớ Brain, Dữ liệu ngoài, Mạng và web, Máy chạy lệnh).
- Robot chạy theo việc thật: workflow tới bước nào thì agent đó đi tới bàn người làm bước trước để lấy kết quả, người kiểm chứng đi tới bàn người vừa làm, agent gọi công cụ thì ra trạm dữ liệu tương ứng, làm xong có từ 2 agent trở lên thì cả nhóm vào bàn họp chốt. Công cụ MinMin gọi trong khung chat cũng hiện ở đây.
- Nút Mô phỏng chạy một tình huống mẫu để xem khi chưa có việc thật. Kéo để xoay, cuộn hoặc chụm để phóng, chạm robot để xem nó đang làm gì.

## [26.10.84] - 2026-10-06
### Cải thiện
- Hình Người hạt giờ là khối 3D thật: có độ dày, có cả mặt sau (lưng, gáy) nên kéo chuột hay dùng cử chỉ tay xoay 360 độ đều thấy một người hoàn chỉnh, không còn là tấm ảnh phẳng. Lúc nghỉ hình lắc nhẹ để thấy khối.
- Số chấm tăng lên 560 nghìn (400 nghìn mặt trước, 160 nghìn mặt sau). Các mức chất lượng Sắc nét, Cân bằng, Nhẹ vẫn giữ nguyên cách hoạt động.

## [26.10.83] - 2026-10-06
### Sửa lỗi
- Hình Người hạt không còn xoay 3D thành lát mỏng nhìn nghiêng. Kéo chuột, cử chỉ tay hay nhìn theo con trỏ chỉ làm hình nghiêng rất nhẹ, mặt luôn hướng thẳng.

## [26.10.82] - 2026-10-06
### Cải thiện
- Hình Người hạt sắc nét hơn nhiều: 400 nghìn chấm (trước 150 nghìn), độ phân giải khung vẽ cao hơn.
- Nút Chất lượng ở thanh công cụ Hub: Sắc nét / Cân bằng / Nhẹ, nhớ lựa chọn trên từng máy. Máy yếu thì tự hạ một bậc khi giật, trừ khi khách đã tự chọn. Thay cho kiểu tự tải lại trang ở bản cũ.

## [26.10.81] - 2026-10-06
### Thêm mới
- Hub có hình mới "Người hạt" làm mặc định: tượng nam lực lưỡng dựng từ 150 nghìn chấm lấy từ ảnh mẫu, có mặt, mắt xanh sáng, ngực, bụng. Mở lên là thân hiện từ bụng lên đầu.
- Khi MinMin nói, miệng và hàm chuyển động theo đúng nhịp giọng (khép khi im, mở theo âm lượng), mắt sáng lên khi nghe và nói.
- Hub mặc định tông sáng kem như ảnh mẫu, vẫn bấm Sáng / Tối được. Các hình cũ (tượng hạt, robot giáp, người, quả cầu) vẫn chọn lại được.

## [26.10.80] - 2026-10-06
### Cải thiện
- Gỡ hẳn tính năng thành viên được mời (nút Thành viên, trang riêng, 2FA thành viên, bản riêng, cổng chuyển). Các tệp tài khoản thành viên cũ (users.json, phiên) tự xoá khi MinMin khởi động.
- Hub robot: ruột tối xanh, viền sáng trắng-xanh rõ hơn, mặt hướng sáng ánh cam, nên đường nét thân nổi hẳn lên.

## [26.10.79] - 2026-10-06
### Thêm mới
- Học viên vào bằng tài khoản được cấp ở trang chủ MinMin giờ thấy đồ thị não ngay (cùng bộ vẽ với MinMin) trong phạm vi brain được cấp, chạm vào chấm để mở ghi chú. Có tab Tệp để duyệt và sửa nếu được quyền. Bản riêng vẫn cho giao diện MinMin đầy đủ.
- Giọng nghe thử có ghi chú từng giọng: nam hay nữ, miền, cao hay trầm, tính cách; chọn được giọng vùng (Bắc, Nam, Trung) cho ChatGPT Live.
- Hub robot mở màn kiểu Apex: thân hiện từ bụng lên đầu với mép sáng quét lên, camera lùi xa rồi đẩy vào.
### Sửa lỗi
- Nút thêm người dùng không còn bị mờ trống, đã có biểu tượng và tên.
- ChatGPT Live báo rõ lý do (hết hạn mức gói, mất kết nối...) bằng tiếng Việt thay vì lỗi chung.
### Cải thiện
- Hub robot đổi sang thân lực lưỡng: cổ dày, cơ thang, vai tròn, ngực nở, bụng sáu múi, đổ bóng theo khối cơ, mặt có sống mũi, gò má, cằm.

## [26.10.78] - 2026-10-06
### Thêm mới
- Bản riêng cho học viên: mỗi học viên có một MinMin tách biệt hoàn toàn (brain, bộ nhớ, đăng nhập AI, kết nối POS, Ads, Higgsfield đều riêng) nhưng vào CHUNG tên miền. Đăng nhập bằng email, mật khẩu và 2FA như thành viên; sau đó cổng chuyển thẳng họ sang bản của họ, cả chat trực tiếp.
- Trong cửa sổ Thành viên có nút Bản riêng: tự tạo container nếu MinMin được gắn quyền Docker, nếu chưa thì hiện lệnh để chạy tay trên VPS rồi nhập địa chỉ vào.
- Container học viên không mở cổng ra ngoài, không đặc quyền, bỏ hết capability, giới hạn RAM và CPU, volume riêng, không gắn socket Docker hay thư mục máy chủ.
- Bản riêng sập thì học viên nhận lỗi 502, không bao giờ rơi về bản của chủ. Cookie của bản riêng không rò ra trình duyệt, học viên không đổi được mật khẩu nội bộ.

## [26.10.77] - 2026-10-06
### Thêm mới
- Mời thành viên vào brain bằng email và mật khẩu riêng (nút người dùng cạnh các nút brain): chủ cấp từng brain ở mức Chỉ xem hoặc Được sửa, khoá, đổi mật khẩu, đặt lại 2FA hoặc xoá thành viên bất cứ lúc nào.
- Thành viên BẮT BUỘC bật xác thực 2 lớp ở lần đăng nhập đầu (quét mã, có mã khôi phục dùng một lần). Chưa bật xong thì chưa xem được gì.
- Thành viên có trang riêng để duyệt cây thư mục, tìm kiếm, xem ảnh/PDF và sửa tệp văn bản trong brain được cấp. Họ không vào được cài đặt, kết nối, khoá API hay brain khác của chủ.
- Mọi lần thành viên sửa tệp đều ghi vào nhật ký member_audit.jsonl.
- Chưa có chat AI cho thành viên (sẽ làm sau, mỗi người dùng tài khoản AI riêng của họ).

## [26.10.76] - 2026-10-06
### Sửa lỗi
- Màn Hub robot luôn mở ở tông tối Apex (đường đồng mức xanh, lõi cam), không còn rơi về giao diện cũ khi trang chính đang ở tông sáng. Nút Sáng / Tối của Hub nhớ riêng, không ảnh hưởng tông của trang chính.
- Lệnh gửi ảnh thử của bot Zalo lấy chat ID từ cài đặt khi bot chưa nạp danh sách.

## [26.10.75] - 2026-10-06
### Thêm mới
- Bot Zalo chính thức lưu lại id tin nhắn Zalo trả về mỗi lần gửi, và có lệnh gửi ảnh thử để kiểm tra bot gửi ảnh được hay không.

## [26.10.74] - 2026-10-06
### Thêm mới
- Nhập lịch sử chat từ nền tảng khác (menu project, mục "Nhập lịch sử chat từ nền tảng khác"): phiên Claude Code trên máy chủ MinMin (đặt tên như bên Claude, phiên MinMin cùng mạch chưa có tên cũng được đặt tên), tệp xuất dữ liệu của ChatGPT và claude.ai. Mỗi nền tảng vào project riêng, nhập lại nhiều lần không bị trùng.
- Gemini chưa nhập được vì Google không cho xuất hội thoại web thành tệp có cấu trúc.

## [26.10.73] - 2026-10-06
### Thêm mới
- Chia sẻ brain bằng link: chọn agent, skill, workflow (hoặc tất cả) rồi tạo link có hạn 7, 30 hoặc 90 ngày. Người nhận dán link vào MinMin của họ để nhập. Bấm "Thu hồi" là link chết ngay.
- Bộ nhớ, wiki, ghi chú và khoá API không bao giờ nằm trong gói chia sẻ.
- Nhập gói từ link của người khác vào brain đang chọn (chỉ nhận link https tới máy chủ công khai).

## [26.10.72] - 2026-10-06
### Sửa lỗi
- Cột phải của cuộc trò chuyện không còn trống khi trong chat có file, ảnh, video: các file Javis nhắc bằng đường dẫn ngắn như attachments/video.mp4 giờ được nhận ra.
### Thêm mới
- Mỗi file, ảnh, video, link ở cột phải có nút "Xem tin gốc": bấm là chat cuộn tới đúng tin nhắn nhắc nó, nháy sáng, kể cả tin rất cũ. Video có ảnh xem trước.
- Mic gõ chữ tự sửa tên riêng nghe nhầm ("Da Vít" thành "Javis", "Hà Li Mi" thành "Halimi") theo từ vựng cá nhân và tên MinMin tự rút từ bộ nhớ, wiki, tên trợ lý.
### Cải thiện
- Màn Hub robot dùng làn nhanh của giọng nói: trả lời ngay, việc nặng chạy nền ở bộ não chính.

## [26.10.71] - 2026-10-06
### Thêm mới
- Tích chọn nhiều hội thoại rồi chuyển sang project khác, có nút Bỏ chọn.
- Đổi tên hiển thị của bất kỳ brain nào (bút cạnh ô chọn brain); nút + tạo brain luôn hiện, cả ở chế độ gọn.
- Chép hoặc chuyển agent, skill, workflow từ brain này sang brain khác (brain mới vốn trống, không tự nối với brain cũ).
- Hội thoại mới tự xếp vào project theo nền tảng AI (Claude, ChatGPT, Gemini, Grok); mục "Gom theo nền tảng AI" trong menu project xếp nốt các hội thoại cũ.
### Sửa lỗi
- Cài như app (PWA) không còn hiện tên cũ, giờ là MinMin OS.

## [26.10.70] - 2026-10-06
### Cải thiện
- Màn Hub hình người kiểu Apex ở tông tối: đường đồng mức xanh điện, lõi cam phát sáng trong đầu thở nhịp nhàng, nhiều bụi sáng bay quanh đầu, nền xanh than với hai dãy núi năng lượng có tia chớp cam chạy dọc đỉnh. Tông sáng giữ bố cục cũ nhưng đổi sang mực xanh. Bấm "Sáng / Tối" để xem.
### Sửa lỗi
- Danh sách hội thoại: hàng nhãn dài (kênh, engine, số tin) không còn đẩy nhóm nút ghim, đổi tên, xóa ra ngoài khung nên nút xóa không bị che nữa.

## [26.10.69] - 2026-10-06
### Thêm mới
- Cửa chính gọn: màn chính chỉ còn khung chat, quả cầu tri thức và ô gõ. Thanh bên và bảng tổng quan được giấu, bấm nút Menu để kéo ra; nút "Hiện đầy đủ" trong Menu đưa bố cục cũ về, lựa chọn nhớ theo từng máy.
- Mục "Hay dùng" đầu Menu: vài trang bạn hay mở nhất.
- MinMin ghi lại cách bạn dùng (trang nào được mở, có gửi chat), tuyệt đối không lưu nội dung chat. Mới chỉ để đưa trang hay dùng lên đầu, chưa đổi hành vi nào của trợ lý.
### Sửa lỗi
- Gửi file hoặc video qua Zalo không còn treo tới hết giờ: lệnh gửi file cũ không bật kết nối nhận tin nên chờ mãi báo tải lên xong. Ảnh vẫn đi đường cũ.

## [26.10.68] - 2026-10-06
### Thêm mới
- Thử bot: nút trên thẻ bot, hỏi thử một câu để xem bot sẽ trả lời gì trước khi phục vụ khách. Chỉ đọc, không gửi cho ai, không ghi vào Hộp thư, không tính thống kê.
- Mức quyền Đọc tài liệu: bot tự liệt kê, tìm và mở thêm tài liệu của chính nó, không ghi được gì và không thấy thư mục khách gửi lên hay ghi chú riêng.
### Cải thiện
- Bot tự nhìn ảnh khách gửi bằng chính model đang chạy nó (OpenAI, Gemini, Claude API, OpenRouter, Groq, Ollama, gói ChatGPT), không cần ChatGPT tả hộ. Model không nhận ảnh thì tự lùi về chữ và nói thật là không xem được.
- Kết nối MCP của Google (Workspace, Tasks, Keep, Search Console, NotebookLM) chạy bản mới nhất; kết nối đã tạo từ trước tự lên lệnh mới, lệnh bạn tự sửa tay vẫn giữ nguyên.
- Google Ads chạy bản chính thức của Google trên PyPI, không cần cài Git, bỏ ô Google Cloud Project ID.
### Bảo mật
- Google Workspace: công cụ chạy hàm Apps Script cần Toàn quyền, công cụ nhập tệp tính là ghi.
### Sửa lỗi
- Khoá mã hoá bị lệch (dựng lại máy, mất file khoá) không còn xoá sạch key API và token khi lưu cài đặt; trả đúng khoá về là kết nối quay lại.
- Duyệt thư mục lớn có giới hạn thời gian, không còn đứng hình khi đếm tài liệu.

## [26.10.67] - 2026-10-05
### Cải thiện
- Hộp thư hiện ảnh trong tin nhắn Zalo, bấm xem lớn; ảnh không tải được có thông báo và đường dẫn mở bản gốc.

## [26.10.66] - 2026-10-05
### Cải thiện
- Trang Kỹ năng có công tắc bật/tắt riêng, khung chi tiết, lọc và sắp xếp; chọn nhiều kỹ năng để xuất ZIP, nhập gói nhiều kỹ năng đầy đủ. Đổi trạng thái giữ nguyên trang đang xem và lưu lỗi báo rõ lý do.
- Giao diện chính, màn hình phụ và các ứng dụng dùng chung chế độ Sáng, Tối hoặc Tự động theo giờ từng thiết bị. Máy chưa chọn dùng lịch 06:00–18:00; lựa chọn đã lưu được giữ nguyên.
### Sửa lỗi
- Đổi mật khẩu admin qua biến môi trường rồi khởi động lại có tác dụng, giữ 2FA và đăng xuất phiên cũ; môi trường không đổi thì giữ mật khẩu đã đổi trong dashboard. Thêm nút xem mật khẩu; sửa tìm thư mục Codex trên Windows, chọn CLI mới nhất và báo rõ lỗi khởi động Claude.
- ChatGPT Live trả lời tiến độ từ việc đang chạy và nhận việc mới song song. Bot Zalo xem được ảnh có chú thích qua ChatGPT đã kết nối; nếu không xem được thì nói rõ, không đoán nội dung ảnh.

## [26.10.65] - 2026-10-04
### Thêm mới
- **Xưởng video đăng được TikTok**: ở tab Khoá và kết nối nhập Client key, Client secret của ứng dụng TikTok rồi bấm Kết nối tài khoản. Video được gắn nhãn nội dung do AI tạo.
- Ứng dụng TikTok chưa qua kiểm duyệt (audit) của TikTok thì bài chỉ lên ở chế độ riêng tư (SELF_ONLY), đây là luật của TikTok. Sau khi audit xong, đổi "Chế độ hiển thị" thành PUBLIC_TO_EVERYONE để đăng công khai.
- Mất mạng ở mảnh video cuối hoặc TikTok chưa xác nhận kịp được ghi là "chưa rõ" và không tự đăng lại, tránh đăng đúp.

## [26.10.64] - 2026-10-04
### Thêm mới
- MinMin Viral Studio trong Kết nối ngoài, cấp giấy phép riêng theo máy và thời hạn. Giao diện đồng bộ MinMin.
- Lưu kênh theo nhóm, nhập JSON hoặc đọc lần chạy Apify Task thành công mới nhất; lọc bài, lưu ý tưởng, xuất CSV. Hỗ trợ chuẩn hóa nguồn Facebook, TikTok, Douyin, Xiaohongshu, YouTube, Instagram và Threads.
- Xưởng nội dung AI dùng API đã kết nối; bản nháp, duyệt và hẹn giờ bài chữ Facebook Page. Nền tảng khác xuất nội dung; chưa tự đăng video.
- Khóa API mã hóa, không trả lại trình duyệt. Kết quả đăng không rõ ràng được giữ để kiểm tra, không tự gửi lại.

## [26.10.63] - 2026-10-04
### Thêm mới
- **Xưởng video** (app mới trong Kết nối ngoài, cần mã kích hoạt): nhập ý tưởng bằng chữ, kèm ảnh hoặc video mẫu, MinMin tự viết kịch bản, chia cảnh, tạo ảnh, tạo video, giọng đọc, ghép phụ đề rồi đăng. Có **Làm hàng loạt**: dán nhiều ý tưởng, mỗi ý một video, giãn giờ đăng đều nhau.
- Nhà cung cấp bản này: ảnh bằng Gemini (Nano Banana) hoặc OpenAI, video qua fal.ai (Veo, Kling, Seedance...), giọng ElevenLabs. Đăng YouTube, YouTube Shorts và Facebook Reels. TikTok, Instagram, X, Threads, Zalo hiện rõ là chưa hỗ trợ.
- An toàn tiền và tài khoản: chọn Chờ duyệt hoặc Tự đăng khi xong, có hạn mức cảnh video và bài đăng mỗi ngày. Lỗi mạng đúng lúc đăng bài được ghi là "chưa rõ" và không bao giờ tự đăng lại để tránh đăng đúp. Khoá API mã hoá trên máy, giao diện chỉ hiện 4 ký tự cuối.

## [26.10.62] - 2026-10-04
### Thêm mới
- **Bot gửi ảnh, video, tài liệu cho khách**: ở form Sửa bot có mục **File bot được gửi cho khách**, tải lên bảng giá, catalogue, ảnh sản phẩm, video hướng dẫn (tối đa 25MB mỗi file). Khi khách cần và có file khớp, bot trả lời rồi gửi kèm file. Chạy trên Zalo cá nhân (mới), Telegram và Zalo Bot.
- Bot CHỈ gửi được file trong thư viện này. Máy tự kiểm tên, đuôi, kích thước và đường dẫn, nên khách (kể cả người lạ) không thể bắt bot gửi file khác trong brain.
### Sửa lỗi
- Zalo cá nhân: ảnh/file bot vừa gửi không còn bị tính là chủ tự tay nhắn (làm bot tự câm trong cuộc chat đó).

## [26.10.61] - 2026-10-04
### Sửa lỗi
- **Hộp thư bị đơ cứng khi mở một cuộc chat của bot**: thanh bot (lý do bot im, nút Gợi ý, Trả lời giúp, chọn Nhóm khách) vẽ lại vô tận khi cuộc chat chưa có nhật ký phán xử, làm trình duyệt treo ngay lúc bấm vào hội thoại hoặc gõ tin. Nay chỉ vẽ lại khi dữ liệu thật sự đổi. Lỗi có từ bản 26.10.50.

## [26.10.60] - 2026-10-04
### Thêm mới
- **Nhóm khách cho bot**: tạo nhiều nhóm, mỗi nhóm có người riêng (chọn từ danh bạ Zalo), phạm vi trả lời riêng (được nói gì, cấm nói gì, từ khoá cấm, ngoài phạm vi thì từ chối hay im), nguồn trả lời riêng và có thể dùng Agent riêng. Ví dụ nhóm Khách mua hàng chỉ hỏi size, tồn kho, giao hàng; nhóm Nội bộ được hỏi chuyện của MinMin. Có thể bật/tắt từng nhóm.
- **Nhóm Người lạ**: người chưa thuộc nhóm nào (ví dụ người lạ kết bạn hỏi tuyển dụng) có chính sách riêng: bot im, hoặc trả lời trong phạm vi hẹp như chỉ nói về tuyển dụng.
- Ở Hộp thư, mỗi cuộc chat có ô chọn **Nhóm khách** để xếp người đó vào nhóm ngay tại chỗ.

## [26.10.59] - 2026-10-04
### Thêm mới
- **Chọn người và nhóm từ danh bạ Zalo, không phải chép id**: ở form bot, bấm **Chọn từ danh bạ Zalo**, gõ tên để tìm (không cần dấu) rồi tích. Dùng cho cả "ai được nhắn riêng" và "nhóm được phép".
- **Phạm vi trả lời của bot**: khai bot ĐƯỢC trả lời về gì, KHÔNG ĐƯỢC trả lời về gì, và câu ngoài phạm vi thì từ chối lịch sự hay im lặng. Thêm **từ khoá cấm**: tin có từ đó là bot im hẳn, máy chặn cứng chứ không nhờ bot tự hiểu.
### Sửa lỗi
- Ô tick Agent phụ nằm lệch xuống dòng riêng, nay nằm cùng dòng với tên.

## [26.10.58] - 2026-10-03
### Thêm mới
- **Một bot gắn nhiều Agent**: ngoài Agent chính (giọng của bot), chọn thêm tối đa 5 Agent phụ ở form bot. Bot biết thêm các vai phụ để trả lời đúng chuyên môn khi khách hỏi đúng chủ đề.
- **Lọc người được nhắn riêng**: bot Zalo cá nhân mặc định CHỈ trả lời người chủ đã cho phép (danh bạ của chủ có bạn bè, người nhà, nên không còn trả lời tất cả). Bấm **Cho bot trả lời** ngay ở Hộp thư, hoặc dán id vào form bot, hoặc chọn "Trả lời mọi người nhắn riêng". Bot Telegram và Zalo Bot giữ nguyên như cũ.

## [26.10.57] - 2026-10-03
### Sửa lỗi
- Nút **Trả lời giúp** và **Gợi ý câu trả lời** ở Hộp thư báo "Lỗi 400" trống trơn khi không soạn được. Nay báo đúng lý do bằng tiếng Việt: cuộc chat chưa gắn bot, chưa có tin khách, bộ não AI lỗi, bot đã chọn im (viết [IM_LANG]) hoặc gửi qua kênh bị lỗi.

## [26.10.56] - 2026-10-03
### Cải thiện
- Chọn đúng từng chứng từ cần tải, xem hóa đơn nguồn và in gộp hồ sơ đã chọn.
- Tải mẫu Excel và nhập danh sách người lao động theo cột.

## [26.10.55] - 2026-10-03
### Thêm mới
- Chế độ Tự phán đoán nhận ra **khách bức xúc / khiếu nại** trong nhóm (giao sai, hoàn tiền, hàng lỗi, lừa đảo, thất vọng...): bot **im**, không trả lời máy móc trước mặt cả nhóm, và **báo chủ qua chuông thông báo của MinMin** (kèm tên nhóm, người nhắn, câu gốc). Một nhóm báo tối đa một lần mỗi nửa giờ để khách giận nhắn liên tục không làm chuông kêu dồn. Telegram có khai người trực thì nhắn thêm cho người đó.
- Tin bị đánh dấu khiếu nại hiện lý do trong nhật ký bộ phán xử; chủ bấm Trả lời giúp hoặc trả lời tay ở Hộp thư.
### Sửa lỗi
- Báo "cần người thật" của bot trước đây chỉ gửi được qua Telegram nên bot Zalo gọi người là rơi vào im lặng. Phần khiếu nại mới đi qua hòm thư MinMin nên chạy cho mọi kênh.

## [26.10.54] - 2026-10-03
### Thêm mới
- Plugin **Công cụ nhóm Zalo** (có sẵn, bật mặc định): bot và MinMin tạo được **ghi chú** (có ghim), **nhắc việc** (lặp ngày/tuần/tháng) và **bình chọn** trong nhóm Zalo, và **tìm thành viên theo tên** (không dấu cũng được) để lấy ID thật mà tag; trùng tên thì hỏi lại, không đoán. Giờ nhắc hiểu theo giờ Việt Nam và tự đổi sang múi giờ máy chủ.
- Ba tool tạo ghi chú, nhắc việc, bình chọn là hành động thật trước mặt cả nhóm nên chỉ chạy ở mức Toàn quyền; tìm thành viên chỉ đọc.
- Chưa kiểm tra với tài khoản Zalo thật: lệnh đúng theo zalo-agent-cli 1.6.2 nhưng cần thử một lần trong nhóm của bố.

## [26.10.53] - 2026-10-03
### Thêm mới
- Bot trên **Zalo cá nhân đứng được trong NHÓM**. Trước đây bot bỏ qua mọi tin nhóm và ảnh nên chế độ phán xử không có chỗ chạy. Nay: nhóm phải do chủ bật (form bot có ô khai nhóm cho kênh Zalo), nhóm chưa bật thì bot IM hẳn, chỉ lên hàng chờ ở trang Chatbot để chủ bấm Cho phép (không nhân danh chủ chen vào nhóm lạ xin được bật).
- Nhận ra bị gọi tên trong nhóm: theo tag @ đúng vị trí và cả chữ @Tên gõ tay, so với tên bot và tên tài khoản. Khách bấm Trả lời vào câu của bot cũng tính là gọi bot.
- Trả lời trong nhóm **tag người vừa hỏi**; mọi "@Tên" khác trong câu được đổi thành tag thật nếu khớp ĐÚNG MỘT thành viên đã nói trong nhóm, mơ hồ thì không đoán. Tag thật đi bằng lệnh `msg send --mention` của chính zalo-agent-cli (cùng bản đã ghim, cùng thư mục đăng nhập); hỏng thì tự rơi về chữ thường qua MCP, câu vẫn tới nhóm.
- Ảnh/file **có caption** trong nhóm tính như một tin ("@Bot giá cái này?" kèm ảnh thì bot trả lời); ảnh không lời thì bỏ qua.
### Sửa lỗi
- Tin gửi vào nhóm Zalo qua MCP đi như tin riêng vì tham số loại tin sai tên (bản zalo-agent-cli ghim là `threadType`, MinMin gửi `type` nên bị bỏ). Nay gửi cả hai.
- Chưa kiểm tra với tài khoản Zalo thật: phần tag thật bằng CLI cần thử một lần trong nhóm của bố.

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
