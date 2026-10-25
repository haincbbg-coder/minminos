# Bảng Hiệu suất Sale trong Văn phòng 3D

Tiêu chí xong:
- Phòng Sale có bảng xếp hạng sale theo điểm hiệu suất 100 điểm (Mở khách 40 + Chốt 45 + Tốc độ 15), số lấy THẲNG từ kết nối Thống kê Pancake ở máy chủ (không chờ AI ghi file).
- Mỗi người có: khách đã trả lời, tin nhắn gửi, SĐT, đơn chốt, tỷ lệ chốt, phản hồi trung bình, điểm và vai nổi bật.
- Có kỳ Hôm nay, Hôm qua, 7 ngày; số hôm nay tự làm mới (đệm 60 giây).
- Nhãn trên đầu nhân viên trong phòng hiện điểm và hạng.
- Chưa có kết nối Thống kê Pancake thì bảng nói rõ cách nối, không bịa số.

Thiết kế đã chọn: A (bố chọn 26/10 00:57). Loại "TEN" khỏi bảng: không ghi cứng tên trong code, dùng `bo_qua`/`chi_tinh` trong `00 - Dashboard/hieu-suat-sale.json` của brain.
- A: bảng thứ 3 "HIỆU SUẤT SALE" trên tường bên của Phòng Sale, giữ nguyên 2 bảng POS; tự xoay Hôm nay -> Hôm qua -> 7 ngày mỗi 15 giây.
- B: thay bảng "HÔM QUA" (POS) bằng bảng điểm hiệu suất gọn + ô tổng cả phòng.

Branch: feature/hieu-suat-sale (số phiên bản đặt chỗ trước khi code)

| Phase | Mục tiêu | File được sửa (độc quyền) | Phụ thuộc | Cách kiểm tra | Lane |
|---|---|---|---|---|---|
| 01 | Hàm chấm điểm thuần (trọng số đọc từ file cấu hình brain, mặc định 20/15/5/35/10/15) | server/diem_sale.py, tests/python/test_diem_sale.py | - | python tests/run.py diem_sale | 1 |
| 02 | Endpoint GET /office/hieu-suat?brain=&ky=nay/qua/7ngay: đọc kết nối pancake-thong-ke, gọi pancake_chat_mcp.nhan_vien, chấm điểm, gộp tên theo khoá bỏ dấu | server/routes/hud.py (chỉ thêm hàm mới), tests/python/test_hieu_suat_route.py | 01 | test giả HTTP + curl server chạy thử | 2 |
| 03 | Vẽ bảng + nhãn điểm trên đầu, xoay kỳ, chỗ đặt theo phương án đã chọn | dashboard/office3d.js | 02 | test JS hiện có + chụp màn 3D bằng Playwright | 2 |
| GATE | Bố mở Văn phòng 3D xem bảng, đối chiếu điểm với câu trả lời MinMin | - | 01-03 | danh sách test tay | - |
| cuối | VERSION, CHANGELOG, PR, merge, phát hành | VERSION, CHANGELOG.md, PHIEN_BAN apps | GATE | CI xanh, ảnh Docker xong | - |

Rủi ro & chỗ cần bố quyết:
- Tên sale trên Pancake chat và POS có thể khác dấu (Khanh Vy / Khánh Vy): gộp theo khoá bỏ dấu như bảng POS đang làm.
- Đơn chốt ở Thống kê Pancake là đơn tạo từ hội thoại, chưa trừ huỷ; doanh thu vẫn ở bảng POS.
- Tài khoản như "TEN" (người hoặc bot?) bố cho biết có loại khỏi bảng không.

## Kết quả nghiệm thu
- 01 ✅ server/diem_sale.py + test_diem_sale.py: 24/24. Thứ tự hạng ngày 25/10 khớp MinMin chấm (Khánh Vy, Hồng Cẩm, Bích Hoàng, Phương Nguyên, Bích Vân); điểm lệch nhẹ vì đã bỏ TEN khỏi đội.
- 02 ✅ GET /office/hieu-suat + test_hieu_suat_route.py: 14/14; route_table thêm đúng 1 mục ở cuối; chạy server thật trả đúng thông báo khi chưa có kết nối.
- 03 ✅ office3d.js: bảng vẽ đúng (sáng, tối, lỗi) - chụp bằng chính hàm veBangHieuSuat; cảnh 3D dựng không lỗi console, nhãn đầu người hiện "64,2 điểm · #1".
  ⚠️ Điểm lệch so với thiết kế: bảng đặt ở TƯỜNG CHUNG với văn phòng (đoạn giữa góc trong và cửa) thay vì tường ngoài, vì từ nút "Phòng Sale" tường ngoài bị nhìn xiên, gần như không đọc được.
  ⚠️ Chưa kiểm được: số thật trên VPS của bố (cần phát hành).
