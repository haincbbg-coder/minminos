# Zalo giống người thật + Thống kê chatbot

Học theo Javis 0.399 (thống kê chatbot) và 0.413-0.414 (Zalo đang-soạn-tin + chữ màu).
Adapt vào MinMin, KHÔNG bê nguyên.

## Tiêu chí xong

Tính năng A - Zalo giống người thật:
- Khách chat riêng với bot Zalo cá nhân thấy "đang soạn tin..." khi bot đang viết.
- Bot gửi được chữ đậm/chữ màu (`{red:Giảm 50%}`, `**...**`), khách thấy đúng định dạng, không thấy dấu `**`.
- Kết nối Zalo đang chạy (nhận + gửi tin) KHÔNG gián đoạn sau khi nâng gói.

Tính năng B - Thống kê chatbot:
- Trang hiện: % câu AI lo, số tin AI trả thay, ước tính giờ rảnh, tin trả lúc 21h-7h, số khách phục vụ + khách mới, tốc độ trả lời đầu (AI vs tay), giờ khách nhắn nhiều.
- Chọn kỳ (Hôm nay / 7 / 30 / 90 ngày / Tháng trước / tự chọn) và so kỳ liền trước.
- Số lấy từ dữ liệu inbox thật (inbox_state, conversations), không bịa.
- Trang bám design-system MinMin (chỉ token --mm-*).

Branch: feature/zalo-nguoi-that-thong-ke-chatbot

## Hiện trạng đã khảo sát
- MinMin gửi tin Zalo qua MCP của gói `javis-zalo`/`zalo-agent-cli`, bản đang dùng **1.6.2**.
- Tính năng typing + chữ màu cần bản javis-zalo mới hơn (Javis dùng ~1.9.0). => RỦI RO phụ thuộc.
- Tin inbox lưu ở `server/inbox_state.py` + `_zalo_inbox_dir` / `_tg_inbox_dir`; reply AI/tay xử ở `chatbot_runtime.py`, `conversations.py`. => Đủ dữ liệu tính thống kê, không cần đường ống mới.

## Phân phase (2 lane)

| Phase | Mục tiêu | File sửa (độc quyền) | Phụ thuộc | Cách kiểm tra | Lane |
|---|---|---|---|---|---|
| 01 | API tổng hợp thống kê chatbot (đọc inbox thật, trả JSON theo kỳ + so kỳ trước) | server/chatbot_stats.py (mới) + đăng ký route cuối main.py | - | curl /api/chatbot/stats?period=7d trả JSON đúng; test_route_table --update | 1 |
| 02 | Trang Thống kê chatbot (UI, bám design-system) | dashboard/chatbot-stats.js (mới) + chatbot-stats.css (mới) + nối tab | 01 | Playwright mở trang thấy số + đổi kỳ; chụp màn | 2 |
| 03 | SPIKE Zalo (sandbox, KHÔNG đụng live): cài javis-zalo bản mới, xác nhận có tool typing + gửi styled, nhận tin không vỡ | (chỉ test, không sửa code sản phẩm) | - | log sandbox: gọi được tool typing; gửi `{red:}` ra đúng; nhận tin cũ vẫn chuẩn hoá đúng | 1 |
| 04 | Nối typing + parse rich text vào đường gửi bot Zalo | server/zalo_personal_channel.py + ch? (xác định sau P03) | 03 | test gửi 1 tin có định dạng tới account test; thấy typing | 2 |
| GATE | Bố test tay | - | 01-04 | danh sách test tay bên dưới | - |
| cuối | PR + changelog + bump VERSION/PHIEN_BAN; nâng gói Zalo trên VPS (SAU khi bố duyệt) | VERSION, CHANGELOG.md, apps/* | GATE | CI xanh | - |

## Rủi ro & chỗ cần bố quyết
- **Nâng `javis-zalo` đụng kết nối Zalo đang bán hàng.** Làm trong sandbox trước (P03). Chỉ nâng trên VPS SAU GATE, bố cho phép.
- Bản javis-zalo mới có thể đổi cách chuẩn hoá tin (conversations.py nhắc 1.6.2 cũ khác) => P03 phải kiểm nhận tin không vỡ. Nếu P03 báo không tương thích an toàn => dừng tính năng A, vẫn giao tính năng B.
- Thống kê "giờ rảnh" là ƯỚC TÍNH theo số phút/tin bố tự đặt, không quy ra tiền (giống Javis). Ghi rõ trên trang.

## Kết quả Phase 01 - API thống kê (ĐÃ NGHIỆM THU ✅)
- server/chatbot_stats.py đọc thẳng kho `conversations.py` (bảng messages/conversations/channel_accounts/customers, schema khớp 100%). Route GET /api/chatbot/stats đăng ký cuối main.py, 400 khi sai kỳ.
- Tự chạy test dữ liệu giả có kết quả biết trước: ai/owner count, %, giờ rảnh, tin đêm, khách phục vụ, trung vị tốc độ trả lời, histogram giờ, kỳ + kỳ trước + delta ĐỀU ĐÚNG.
- test_route_table.py: xanh (898 mục). 
- Lưu ý đã ghi vào `_notes`: new_customers đếm theo lúc khách lần đầu vào kho (không theo giờ tin).

## Kết quả Phase 03 - SPIKE Zalo (đã nghiệm thu)
- `javis-zalo` KHÔNG có trên npm (bản fork riêng, private của cùng tác giả). Gói công khai là `zalo-agent-cli`, bản mới nhất = **1.6.2** (đúng bản MinMin ghim). Không có gì để nâng.
- **Chữ đậm/màu: GO, rủi ro thấp, KHÔNG nâng gói.** CLI 1.6.2 đã hỗ trợ `msg send <thread> <text> --md` (`**đậm**`, `{red:}`, `{green:}`, `{yellow:}`). MinMin đã có mẫu shell qua CLI: `server/channels/zalo_personal.py` (`lenh_cli`, `gui_co_tag` dùng `msg send --mention`). Chỉ thêm 1 nhánh gọi `--md`.
- **Typing "đang soạn tin": NO-GO bây giờ.** Không có tool MCP/lệnh CLI ở 1.6.2 (kể cả 1.7.0 chưa publish). Chỉ nằm ở lõi zca-js (`sendTypingEvent`) hoặc bản fork riêng. Hoãn tới khi có/kiểm chứng fork javis-zalo. => Cần bố quyết.
- **Rủi ro nâng gói (đã loại khỏi vòng này):** 1.7.0 đổi thứ tự chuẩn hoá tin + backfill → có thể làm bot trả lời tin cũ. Không nâng.

### Phase 04 (sửa lại theo spike)
- CHỈ làm chữ màu/đậm qua CLI `--md` trong server/channels/zalo_personal.py. An toàn, không đụng nhận tin, KHÔNG cần nâng gói trên VPS.
- Bỏ "đang soạn tin" khỏi vòng này (hoãn, chờ bố quyết chuyện xin bản fork javis-zalo).

## Thiết kế UI (tính năng B)
Trang Thống kê chatbot bám design-system MinMin (phương án "Nổi mềm tinh gọn", chỉ --mm-*), mô phỏng bố cục trang Thống kê/Mức dùng hiện có: khối lợi ích đầu trang + các ô số + 1-2 biểu đồ. Con làm mockup cho bố xem ở đầu Phase 02 nếu bố muốn chọn bố cục trước.
