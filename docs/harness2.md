# Cải tiến có đối chứng (Trụ 2: tự học có đối chứng)

Thuật toán theo Harness² của Google Research, arXiv 2610.14224, Apache 2.0; lời dặn chuyển ý từ
harness2/core/prompts.py. MinMin không gắn gói gốc (gói đó cần OpenCode, Vertex, Docker) mà viết
lại thuật toán trong `server/harness2.py`, chạy trên mọi bộ não MinMin chặn được từng lời gọi tool
(Claude Code và các bộ não API key).

## Nó làm gì

Cách tự học cũ (dòng `JAVIS_LESSON`) học từ MỘT lượt chạy: trợ lý tự nói "lần sau nên làm X" là X
vào bộ nhớ, không có bằng chứng X giúp được gì. Cải tiến có đối chứng thì:

1. Lấy vài việc thật gần đây của trợ lý làm **đề** (nhật ký chạy, đề bạn gõ thêm, và
   `memory/agents/<slug>/de-thi.json` nếu có).
2. **Chạy thử** trợ lý hiện tại trên các đề đó, ghi lại toàn bộ đường đi (tool đã gọi, kết quả).
3. Hai người sửa độc lập đọc bằng chứng đó: **INV** chỉ sửa cách làm việc (lập kế hoạch, dùng tool,
   kiểm lại), **DOM** chỉ sửa kiến thức nghề (quy tắc shop, cách đọc số POS/Ads). Mỗi thay đổi phải
   chỉ ra khoảnh khắc trong đường đi đã thúc đẩy nó.
4. Chạy thử từng bản sửa trên cùng đề.
5. Một bước **ghép** đọc mọi đường đi và sản phẩm rồi gộp, chọn một, hoặc **giữ nguyên**. Đồng thuận
   chỉ là ủng hộ, không phải bằng chứng; thay đổi gắn với lượt không giao được gì bị coi là không an toàn.
6. Chạy thử bản ghép. Có đáp án thì chấm bằng LUẬT; bản ghép kém hơn bản gốc thì tự giữ nguyên.
7. Bạn xem so sánh trước/sau rồi **Áp dụng** hoặc **Bỏ**. Áp dụng xong vẫn **Hoàn tác** được.

Ba thứ bài báo chứng minh là tạo ra hiệu quả (bỏ thứ nào cũng tụt điểm) được giữ nguyên: chạy thật để
đối chứng, hai người sửa tách phạm vi, bước ghép riêng có quyền giữ nguyên. Thư viện kinh nghiệm theo
nhóm việc cũng giữ: chỉ ghi khi có tương phản thực thi và khi bạn đã áp dụng.

## An toàn: chạy thử KHÔNG làm gì thật

Trợ lý ở mức Toàn quyền vẫn không gửi tin, tạo đơn, đăng bài, chạy ads, giao việc nền... trong lúc chạy
thử. Cơ chế ở `server/che_do_thu.py`:

- Tool MCP loại ghi/nguy hiểm: hub không gọi, chỉ ghi "ý định" (tên tool + tham số đã che bí mật) và trả
  câu "GIẢ LẬP" để trợ lý làm tiếp như thật. Không tạo yêu cầu "hỏi trước", không ghi sổ hành động thật.
- Plugin mức safe/full (`javis_task`, `zalo_send_image`, `fb_page_post`...): không chạy dòng mã nào.
- Ghi file chỉ vào brain TẠM (bản sao chữ của brain trong `STATE_DIR/harness/<lần chạy>/`). Brain tạm
  biến mất giữa chừng thì lượt cải tiến DỪNG, hub không bao giờ tự rơi về brain thật.
- Claude Code chạy thử luôn có allowlist chỉ đọc + hub, cấm Bash/Write/Edit/Web/Task, không nạp
  connector của tài khoản Claude. Bộ não khác (Codex, Grok, Muse, Copilot...) bị từ chối chạy thử vì
  MinMin chưa chặn được từng lời gọi tool của chúng.

Tool ĐỌC vẫn chạy thật (cần số thật để so cách làm). Lưu ý: tool đọc trả phí (ví dụ quét Apify) vẫn tốn
phí như lượt thật.

## Cái gì được sửa, cái gì không

Được sửa: thân `agents/<slug>.md` (kể cả mục `## Cách dùng công cụ`), mục `## Bài học (tự học)` trong
`memory/agents/<slug>/MEMORY.md`, `memory/agents/<slug>/kinh-nghiem.md`, skill bạn đã gán cho trợ lý
(chỉ nối thêm, không viết lại), và tạo skill mới riêng cho trợ lý (mô tả tối đa 150 ký tự, có nhóm).

Không bao giờ sửa: mức quyền, model, nhà cung cấp và mọi khoá frontmatter khác ngoài `skills`; skill hệ
thống; skill bạn khoá bằng `learn_lock: true`; script, plugin, CLAUDE.md. Phần bạn viết tay trong
MEMORY.md (ngoài mục bài học) giữ nguyên từng chữ.

## Cách dùng trên giao diện

1. Trang **Cộng sự**, chọn một trợ lý, cột phải **Cài đặt**, bấm **Cải tiến có đối chứng**.
2. Tick các việc gần đây muốn dùng làm đề (mặc định 3, tối đa 5), gõ thêm đề nếu muốn.
3. Chọn số ứng viên k (1, 2, 3) và chế độ **Song song** hay **Nối tiếp**; chọn bộ não cải tiến.
4. Xem ước lượng: số lượt chạy trợ lý (4k x số đề), số phiên cải tiến (3k) và tiền ước tính. Bấm **Chạy**.
5. Lượt chạy nền; khung hiện tiến độ. Xong thì hòm thư (chuông) có thư báo.
6. Xem so sánh: khác biệt từng file, lý do của bước ghép, bảng "mỗi thay đổi đã làm gì", các hành động
   trợ lý định làm (đã giả lập), điểm luật nếu có, chi phí thật. Bấm **Áp dụng** hoặc **Bỏ**.
7. Đã áp dụng thì có nút **Hoàn tác** (git revert commit `harness:`; máy không có git thì khôi phục bản
   cũ đã lưu). Danh sách các lần cải tiến nằm ngay dưới.

## Chi phí

Với k=1 và 3 đề: 12 lượt chạy trợ lý + 3 phiên cải tiến + 1 phiên rút kinh nghiệm (không có bộ chọn
vì chỉ có một bản cuối). k=2 thêm một phiên chọn mù. Trần cứng: số lần gọi model không vượt mức tính
trước, và tiền không vượt trần (mặc định gấp 2,5 lần ước tính); chạm trần là dừng, trợ lý giữ nguyên.

Chạy bằng gói thuê bao (Claude Pro/Max...) thì đây là tải nền nặng; Anthropic tính gói cho dùng cá nhân
thông thường, nên dùng API key hoặc chọn bộ não API cho phần cải tiến nếu chạy thường xuyên.

## Đề có đáp án (tuỳ chọn)

`memory/agents/<slug>/de-thi.json` cùng định dạng bộ chấm điểm não (`server/danh_gia.py`): mỗi câu có
`id`, `cau_hoi`, `cham` (kiểu `so`, `khop`, `chua`, `regex`, `tu_choi`, `bao_cao`) và đáp án tĩnh hoặc
`su_that` (lấy bằng tool plugin chỉ đọc). Điểm chỉ dùng làm chặn an toàn sau bước ghép; nó KHÔNG BAO GIỜ
vào ngữ cảnh của người sửa hay người ghép (để không học theo bộ chấm).

## Endpoint

`POST /harness/uoc-luong`, `POST /harness/chay` (trả ngay, chạy nền), `GET /harness/trang-thai`,
`GET /harness/ket-qua`, `POST /harness/ap-dung`, `POST /harness/bo` (bỏ đề xuất hoặc dừng lượt đang
chạy), `POST /harness/hoan-tac`, `GET /harness/lich-su`. Dữ liệu từng lần ở `STATE_DIR/harness/<mã>/`
(ngoài brain, ngoài git): cấu hình, trạng thái, trajectory JSONL, ngữ cảnh từng phiên, kết quả.

## Khác Harness² gốc ở đâu

- Lượt chạy thử luôn ở chế độ shadow (bài báo chạy trong container nên không cần).
- Người sửa không ghi file trực tiếp: trả lời bằng khối `<file path="...">toàn văn</file>`, MinMin ghi
  giúp ("model đề xuất, code ghi"). Lý do: Write/Edit native của Claude nhận đường dẫn tuyệt đối nên
  trèo ra khỏi thư mục bằng chứng được; cách này chạy giống nhau trên Claude Code và bộ não API.
- Ngân sách chữ luôn nạp: tối đa 12.000 ký tự và không phình quá 1,5 lần bản gốc, nhưng luôn chừa ít
  nhất 2.000 ký tự để trợ lý có lời dặn ngắn vẫn sửa được.
- Không rút kinh nghiệm khi kết luận giữ nguyên (thư viện chỉ ghi khi bạn áp dụng, nên phiên đó chỉ tốn tiền).
- Chặn an toàn sau bước ghép: điểm luật thấp hơn bản gốc, hoặc bản ghép không giao được ở đề mà bản gốc
  giao được, thì tự giữ nguyên.
