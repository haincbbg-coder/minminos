# Design system MinMin - phương án A "Nổi mềm tinh gọn"

Thiết kế đã chọn: phương án A trên canvas "MinMin Design System - 2 phương án" (chủ repo chốt 2026-10-25).
Branch: `claude/design-system-26.10.233` - PR #249, phát hành bản 26.10.238.

## Xong là khi
- Có MỘT bộ token chung cho cỡ chữ, bo góc, khoảng cách, nằm ở `dashboard/surface-tokens.css`.
- Thang chữ còn 7 cỡ (12, 13, 14, 16, 20, 24, 32) + 1 cỡ huy hiệu (10). Bo góc còn 5 mức (8, 12, 16, 22, tròn).
- `style.css`, `console.css`, `noi-mem.css` và các file CSS phụ dùng token thay cho số gõ cứng trong vùng đã chuẩn hoá.
- Có quy chuẩn bằng chữ (`docs/design-system.md`) để mọi phiên sau làm trang mới đều bám theo.
- Có test chặn số lạ quay lại.
- Ảnh chụp trước/sau 7 trang chính ở cả tông sáng và tối không vỡ bố cục.

## Khảo sát (Bước 0)
- 3 lớp token chồng nhau: `--mm-*` (surface-tokens.css), `--nm-*` (noi-mem.css), bộ cũ `--bg/--accent/--text*` (style.css).
  Lớp màu đã nối `--nm-*` -> `--mm-*` nên giữ nguyên trong PR này; việc gộp lớp màu cũ là PR sau.
- Cỡ chữ px: 28 giá trị khác nhau. Bo góc px: 21 giá trị khác nhau.

## Bảng quy đổi
| Đang có | Thành |
|---|---|
| font 10, 10.5 | `--mm-fs-badge` (10) |
| font 11, 11.5, 12 | `--mm-fs-12` |
| font 12.5, 13 | `--mm-fs-13` |
| font 13.5, 14, 14.5 | `--mm-fs-14` |
| font 15, 16, 16.5, 17 | `--mm-fs-16` |
| font 18 ... 22 | `--mm-fs-20` |
| font 23, 24, 26 | `--mm-fs-24` |
| font < 10 và >= 30 | giữ nguyên (nhãn đồ thị, số trang trí) |
| bo 5, 6, 7, 8 | `--mm-r-chip` (8) |
| bo 9, 10, 11, 12 | `--mm-r-btn` (12) |
| bo 13, 14, 16 | `--mm-r-field` (16) |
| bo 18, 20, 21, 22, 24 | `--mm-r-card` (22) |
| bo 99, 999 | `--mm-r-pill` |
| bo 2, 3, 4 | giữ nguyên (thanh mảnh, thanh cuộn) |

## Phase
| Phase | Mục tiêu | File được sửa (độc quyền) | Phụ thuộc | Cách kiểm tra | Lane |
|---|---|---|---|---|---|
| 01 | Token cỡ chữ, bo góc, khoảng cách | `dashboard/surface-tokens.css` | - | grep token, chạy test cũ | 1 |
| 02 | Quy chuẩn bằng chữ | `docs/design-system.md`, `docs/quy-uoc-dev.md` | - | đọc lại, đủ mục | 1 |
| 03 | Test chặn số lạ | `tests/python/test_design_tokens.py` | 01 | chạy test | 1 |
| 04 | Quy đổi CSS sang token | `dashboard/*.css` trừ surface-tokens, `tests/python/test_theme_tokens.py` (chỉ chỗ ghim số 18px) | 01 | toàn bộ test python + js, chụp màn | 2 |
| 05 | So ảnh trước/sau, sửa chỗ vỡ | như 04 | 04 | ảnh 7 trang x 2 tông | 2 |
| GATE | Bố xem ảnh trước/sau + canvas | - | 05 | - | - |
| 06 | Changelog, bump `?v=`, PR sẵn sàng, merge | `CHANGELOG.md`, `dashboard/index.html` | GATE | CI xanh | - |

Rủi ro: cỡ chữ 11 -> 12 làm vài chỗ chật dòng; huy hiệu đếm số dùng 10px. Phase 05 bắt các chỗ này bằng ảnh.

## Kết quả
- 01 ✅ token khai trong surface-tokens.css.
- 02 ✅ docs/design-system.md (10 mục, 46 token nhắc tới đều có thật, không em dash). Hở: chip trạng thái tông sáng đạt tương phản 4.1-4.4 (dưới 4.5), chữ trắng trên đầu nhạt dải nút chính 3.83. Cần chỉnh token màu, để PR sau.
- 03 ✅ tests/python/test_design_tokens.py, 17 check, tự thử trên CSS mẫu bắt đúng ca sai. Hở: chưa soi shorthand `font:` (còn ~10 chỗ cỡ lẻ), chưa soi CSS tiêm từ JS.
- 04 ✅ 1.295 chỗ quy đổi (788 cỡ chữ, 507 bo góc) trong 10 file CSS. Lan ra ngoài kế hoạch (có lý do): console.js 1 dòng (khung chat tab Trò chuyện phải cùng bo với cockpit), 6 test JS + test_theme_tokens đọc CSS qua `tests/js/_doc_css.js` (đổi token về px để test kiểm giá trị), số `?v=` của CSS, PHIEN_BAN ở 3 app con (test bắt khớp VERSION).
- 05 ✅ chụp 7 trang x 2 tông trước/sau: khác 0.3-5.4% điểm ảnh, không trang nào vỡ bố cục. Toàn bộ test JS 183/183 xanh.
