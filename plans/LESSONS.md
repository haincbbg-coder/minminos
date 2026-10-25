# Bài học khi chia phase

- 2026-10-25 design system: nhiều test JS ghim số CSS dạng chữ (`font-size: 16px`). Đổi sang token thì đọc CSS qua `tests/js/_doc_css.js` thay vì sửa từng regex.
- Số `?v=` của style.css/console.css phải là số nguyên tăng dần (test_sysbar_layout, test_mobile_layout so số), đừng đổi sang dạng phiên bản.
- Bump VERSION thì bump luôn PHIEN_BAN ở apps/concat, apps/doi-social, apps/goi-y-ma (test bắt khớp).
- Chụp màn trước/sau: chạy server với JAVIS_STATE_DIR tạm, POST /settings general setup_done=true để bỏ màn chào, tick điều khoản rồi điều hướng bằng Alpine.store('nav').go(id).
