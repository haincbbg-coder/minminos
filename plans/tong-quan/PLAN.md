# Trang Tổng quan - phương án 1 "Bàn làm việc"

Thiết kế đã chọn: phương án 1 trên canvas "MinMin Tổng quan - 2 phương án" (chủ repo chốt 2026-10-25), dựng bằng design system A (`docs/design-system.md`).
Chủ repo chốt thêm: Tổng quan là trang mặc định khi mở MinMin, đứng đầu thanh bên.
Branch: `claude/tong-quan-26.10.239` - PR #252, phát hành bản 26.10.242 (239, 240, 241 bị bản khác lấy trước).

## Xong là khi
- Thanh bên có mục "Tổng quan" đứng đầu nhóm Trung tâm; mở MinMin là vào trang này.
- Trang hiện: lời chào + số việc cần bố; thanh "Hoàn tất cài đặt" (ẩn khi đủ); khối "Cần bố xử lý"; Tiền vào hôm nay; Chi phí AI hôm nay; 4 số chính; bảng theo page.
- Mọi con số lấy từ nguồn thật. Nguồn chưa nối thì ô đó nói rõ "chưa nối" kèm nút đi nối, không bao giờ hiện số bịa hay số 0 giả.
- Một nguồn lỗi không làm hỏng cả trang.
- Test mới cho máy chủ và giao diện; toàn bộ test cũ xanh.

## Lệch so với bản thiết kế (bố duyệt ở GATE)
- Bỏ nút Hôm nay / 7 ngày / 30 ngày ở bản này: số POS chỉ có hôm nay và hôm qua, chi phí AI không có kỳ trượt. Bản này hiện "Hôm nay, so với hôm qua".
- Chi phí AI: bỏ dòng "% câu chạy model rẻ" vì MinMin chưa lưu số đó (bộ định tuyến chỉ nhớ 30 lượt trong RAM). Thay bằng tiền thật (API key) và giá trị quy đổi phần chạy bằng gói.
- Chi ads: lấy từ số đồng bộ sẵn trong brain nếu có; chưa có thì ô ghi "chưa có số". Gom chi tiêu 50+ tài khoản quảng cáo trực tiếp từ Facebook là PR sau (cần chạy nền và đệm, không làm chậm trang).
- Nút Duyệt ngay trên trang chỉ có cho việc Kanban đang chờ duyệt (dùng đúng endpoint nút Duyệt của Bảng việc). Mục khác có nút "Mở" đưa tới đúng chỗ xử lý. Thao tác thật ra ngoài (cấp quyền, hỏi trước, đăng bài) vẫn duyệt ở trang gốc.
- Ai đang làm dở ở Trò chuyện hoặc Studio rồi tải lại trang thì vẫn quay về đúng chỗ đó (giữ tính năng cũ); còn lại mở là vào Tổng quan.

## Hợp đồng dữ liệu `GET /tong-quan?brain=<brain>`
Mỗi khối có `trang_thai`: `"ok"` | `"chua_noi"` | `"loi"` (kèm `loi`: câu ngắn đã giấu bí mật).
```json
{
  "luc": "2026-10-25T23:06:00+07:00",
  "cai_dat": {"buoc": [{"id": "pos|ads|zalo|telegram|biendong|nao", "ten": "Pancake POS", "xong": true, "trang": "mcp"}], "xong": 4, "tong": 6},
  "can_xu_ly": {"trang_thai": "ok", "muc": [
     {"id": "kanban:t1", "nguon": "kanban|doi_social|ket_noi|nhac_hen|loop|workflow",
      "muc_do": "bad|warn|info", "tieu_de": "...", "mo_ta": "...",
      "nut": [{"nhan": "Duyệt", "loai": "duyet_kanban", "task_id": "t1"},
              {"nhan": "Mở", "loai": "trang", "trang": "kanban", "task_id": "t1"},
              {"nhan": "Mở", "loai": "link", "url": "/apps/doi-social/#/duyet"}]}],
     "loi_nguon": ["..."]},
  "tien_vao": {"trang_thai": "ok|chua_noi", "tong": 18420000, "so_gd": 11, "gan_nhat": [{"mo_ta": "...", "so_tien": 2350000, "luc": 1761400000}]},
  "chi_phi_ai": {"trang_thai": "ok", "usd_that": 0.42, "usd_quy_doi": 3.1, "luot": 57},
  "so_chinh": {
     "doanh_thu": {"trang_thai": "ok|chua_noi|loi", "hom_nay": 45280000, "hom_qua": 40400000},
     "don_chot": {"trang_thai": "ok", "hom_nay": 62, "hom_qua": 54},
     "chot_hoi_thoai": {"trang_thai": "ok", "ty_le": 31.0, "khach": 200, "sdt": 118},
     "chi_ads": {"trang_thai": "ok|chua_noi", "hom_nay": 9640000}},
  "theo_page": {"trang_thai": "ok|chua_noi|loi", "dong": [{"page": "HALIMI", "khach": 124, "sdt": 76, "don": 41, "ty_le": 33.0}]}
}
```
Số tiền: VND là số nguyên, USD là số thực. `ty_le` là phần trăm, có thể `null`.

## Phase
| Phase | Mục tiêu | File được sửa (độc quyền) | Phụ thuộc | Cách kiểm tra | Lane |
|---|---|---|---|---|---|
| 01 | Máy chủ: gom số liệu + route | `server/tong_quan.py` (mới), `server/main.py` (chỉ thêm đăng ký route ở cuối), `tests/python/route_table.json`, `tests/python/test_tong_quan.py` (mới) | - | test mới, route_table, import main | 1 |
| 02 | Giao diện trang | `dashboard/tong-quan.js`, `dashboard/tong-quan.css` (mới), `dashboard/i18n/vi.json`, `dashboard/i18n/en.json`, `tests/js/test_tong_quan.js` (mới) | hợp đồng ở trên | test JS mới + test_i18n + test_design_tokens | 1 |
| 03 | Gắn trang + trang mặc định | `dashboard/console.js`, `dashboard/ui-actions.js`, `server/ui_targets.py`, `server/voice_brain.py`, `dashboard/index.html`, `tests/js/test_linh_vat.js`, `tests/js/test_khoi_phuc_trang_dang_lam.js`, `tests/python/test_settings_consolidation.py`, `tests/python/test_design_tokens.py` (thêm tong-quan.css vào danh sách) | - | test_ui_actions, các test đã sửa | 1 |
| 04 | Chạy thật, dữ liệu mẫu, chụp màn sáng/tối + điện thoại, toàn bộ test | - | 01-03 | ảnh + 700 test | 2 |
| GATE | Bố xem ảnh + danh sách lệch | - | 04 | - | - |
| 05 | Changelog, PR, merge, xác nhận phát hành | `CHANGELOG.md` | GATE | CI xanh, ảnh GHCR | - |

## Kết quả
- 01 ✅ server/tong_quan.py + GET /tong-quan, 67 kiểm tra. Thêm khoá tuỳ chọn `ghi_chu` khi số đọc được nhưng có cảnh báo. Hở: chưa đệm ở tầng trang (Thống kê Pancake chậm thì trang chờ tối đa 15 giây); test chưa phủ Đội Social đã mở khoá.
- 02 ✅ tong-quan.js/css, 48 khoá i18n vi/en, 58 kiểm tra.
- 03 ✅ gắn trang, trang mở đầu, bí danh lệnh nói; 4 test cũ cập nhật.
- 04 ✅ chạy thật với dữ liệu mẫu: trang mở đầu là tongquan; bấm Duyệt thật chuyển việc sang xong. Sửa theo ảnh: tiêu đề trùng, đệm hai lần, linh vật che nút, bước Bộ não lệch với khối Cần xử lý, chữ "bố" trong câu máy chủ. Toàn bộ 709/709 test xanh, CI xanh.
