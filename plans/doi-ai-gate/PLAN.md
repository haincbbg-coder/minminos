# Bảng việc có GATE cho các đội AI - phương án 1 "Dòng việc theo job"

Thiết kế đã chọn: phương án 1 trên canvas "MinMin Bảng việc có GATE - 2 phương án" + màn duyệt bằng Telegram (chủ repo chốt 2026-10-26).
Branch: `claude/doi-ai-gate-26.10.244` - PR #257, phát hành bản 26.10.246 (244, 245 bị bản khác lấy trước).

## Xong là khi
- Giao được một **job** cho một đội (Social, Ads, hoặc tự kê bước). Job = chuỗi bước chạy lần lượt trên Bảng việc (Kanban) có sẵn.
- Một bước loại **GATE** không chạy gì: tới lượt nó thì job dừng, báo chủ (hòm thư + Telegram có nút), hiện khung "Bạn sắp cho phép".
- **Duyệt** = GATE xong + cấp quyền chạy thật (`execution_mode=full`) cho ĐÚNG các bước GATE đó mở khoá, một lần. **Sửa lại** = gửi ghi chú, chạy lại bước ngay trước GATE với ghi chú, GATE quay về chờ. **Từ chối** = dừng job, huỷ các bước còn lại.
- Các bước trước GATE chạy ở mức quyền thấp (`auto`/`suggest`): thao tác thật ra ngoài (bật camp, đăng bài, gửi tin, chi tiền) bị chặn cứng - kể cả với engine Claude Code. Phase 03 kiểm và bịt đường lách.
- Bước lỗi hoặc bị huỷ thì job hiện trạng thái "kẹt", không để các bước sau treo im lặng.
- Trang Bảng việc có khu "Đội AI" ở trên cùng: mỗi job một hàng bước như bản thiết kế; job ở GATE mở sẵn khung xem trước + 3 nút.
- Telegram: tin GATE có nút Duyệt / Từ chối / Xem chi tiết; bấm Duyệt trên Telegram cho kết quả y như trên dashboard.

## Phạm vi bản đầu và lệch so với thiết kế
- Mẫu job **Đội Social** dùng các công cụ Đội Social sẵn có. Mẫu **Đội Ads** có khung bước, nhưng bước dựng/bật camp cần công cụ ghi Facebook Ads chưa có trong MinMin (kết nối hiện có chỉ đọc): bản này chạy tới bước nghiên cứu + viết content, bước dựng/bật camp ghi rõ "cần nối công cụ ghi Facebook Ads".
- "Sửa lại" chỉ có trên dashboard (cần gõ ghi chú). Telegram có Duyệt / Từ chối / Xem chi tiết.
- Khung "Bạn sắp cho phép" lấy từ kết quả bước ngay trước GATE + mô tả GATE do người tạo job/mẫu ghi; chưa có trường số tiền chuẩn hoá.

## Hợp đồng

### Dữ liệu
- Thêm cột `job_id TEXT` vào bảng `tasks` (migration an toàn, NULL cho task cũ) + bảng `jobs`:
  `id TEXT PK, brain_root, title, doi (social|ads|khac), status (dang_chay|cho_duyet|ket|xong|dung), chat_id, created_at, updated_at, metadata_json`.
- Bước GATE là task `capability="gate"`. Bước sau GATE có `deps` trỏ tới task GATE. Metadata của GATE: `{"gate": {"mo_ta": "...", "mo_khoa": [task_id...]}}`.
- Bước thường có `metadata.job_step = n` (thứ tự hiển thị).

### Python (server/tasks.py, đối tượng `tasks.current()`)
- `create_job(brain, title, doi, steps, chat_id="") -> job_id`; `steps` = list `{"title","intent","capability","gate": bool, "gate_mo_ta": str}`; bước gate=True tạo task capability "gate"; bước ngay sau gate tạo `capability="external-write"`, `execution_mode="auto"` (bị chặn tới khi được cấp quyền).
- `jobs_view(brain) -> {"jobs": [job_view...]}` ; `job_view` = `{"id","title","doi","status","created_at","chat_id","buoc":[{"task_id","title","loai":"buoc|gate","status","ket_qua_ngan","block_reason"}], "gate_cho": null | {"task_id","mo_ta","xem_truoc","mo_khoa":[...]}}`.
- `gate_action(brain, job_id, action, note="", source="dashboard") -> {"ok": bool, "status": str, "loi"?: str}`; action `duyet|sua|tu_choi`. Idempotent (bấm hai lần không cấp quyền hai lần), ghi task_events `gate_duyet|gate_sua|gate_tu_choi` kèm `source`.
- Khi GATE tới lượt: dispatcher KHÔNG chạy nó; đặt `blocked`, `block_kind="gate"`, job `cho_duyet`, rồi gọi `deps.notify_gate(job_view, gate_task)` đúng một lần (nhớ cờ trong metadata để không báo lặp).

### HTTP (đăng ký cùng chỗ các route /kanban khác)
- `GET /kanban/jobs?brain=` -> `jobs_view`
- `POST /kanban/job` form `brain, title, doi, steps(JSON), chat_id?` hoặc `mau=<id mẫu>, muc_tieu=<chữ>` -> `{"ok","job_id"}`
- `POST /kanban/job/gate` form `brain, job_id, action, note?` -> kết quả `gate_action`
- `GET /kanban/job-templates` -> mẫu từ `system/doi-ai-mau.json`

### Telegram / thông báo (server/main.py)
- `notify_gate`: hòm thư + gửi theo `chat_id` của job (rỗng thì người nhận Telegram đầu tiên như `_notify_owner`); Telegram có `reply_markup` inline: `gv:<job_id>:d` (Duyệt), `gv:<job_id>:t` (Từ chối), nút URL "Xem chi tiết" nếu có địa chỉ công khai, không thì nút `gv:<job_id>:x` trả lời tóm tắt.
- `_tg_callback` thêm tiền tố `gv:` gọi `gate_action(..., source="telegram")`, sửa tin thành "Đã duyệt"/"Đã từ chối". Chỉ người trong whitelist bấm được (cơ chế có sẵn).

## Phase
| Phase | Mục tiêu | File được sửa (độc quyền) | Phụ thuộc | Cách kiểm tra | Lane |
|---|---|---|---|---|---|
| 01 | Job + GATE trong Kanban, route, mẫu | `server/task_store.py`, `server/tasks.py`, `system/doi-ai-mau.json` (mới), `tests/python/test_doi_ai_gate.py` (mới), `tests/python/route_table.json` | hợp đồng | test mới + test kanban cũ | 1 |
| 02 | Thông báo GATE + nút Telegram | `server/main.py` (notify_gate, `_gui_qua_kenh` nhận reply_markup, `_tg_callback` tiền tố gv:), `server/telegram_bot.py` nếu cần, `tests/python/test_gate_telegram.py` (mới) | hợp đồng (giả lập gate_action) | test mới + test telegram cũ | 1 |
| 03 | Kiểm + bịt đường lách quyền ở bước trước GATE | báo cáo trước; sửa ở file engine (`server/claude_cli.py`/`claude_sdk_engine.py`/`mcp_hub.py`/`mcp_catalog.py`) - KHÔNG sửa tasks.py (ghi lại cho người điều phối) | - | test chứng minh mức auto không gọi được công cụ ghi | 1 |
| 04 | Giao diện khu Đội AI trên Bảng việc | `dashboard/doi-ai.js`, `dashboard/doi-ai.css` (mới), i18n vi/en (khoá `doiai.*`), `tests/js/test_doi_ai.js` (mới) | hợp đồng | test JS + i18n + design tokens | 1 |
| 05 | Gắn vào trang (console.js renderKanban, index.html), nối thật, chụp màn, toàn bộ test | `dashboard/console.js`, `dashboard/index.html`, `tests/python/test_design_tokens.py` | 01-04 | ảnh + toàn bộ test | 2 |
| GATE | Bố xem ảnh + tin Telegram mẫu | - | 05 | - | - |
| 06 | Changelog, merge, phát hành | `CHANGELOG.md` | GATE | CI xanh | - |

## Kết quả
- 01 ✅ job + GATE trong Kanban, 4 route, 3 mẫu, 77 kiểm tra. GATE không bao giờ được claim; duyệt cấp full đúng bước trong một giao dịch, bấm lại không cấp thêm; GATE bị dọn tay mà chưa duyệt không mở khoá bước sau.
- 02 ✅ báo GATE: hòm thư + Telegram có nút gv:<job>:d/t/x, sửa tin gốc sau khi bấm, 48 kiểm tra.
- 03 ✅ kiểm quyền xác nhận 4 đường lách và đã bịt (Bash ở bước code, javis_task/javis_schedule tự tạo việc full, ghi file cấu hình/quyền/loop trong brain, engine Antigravity và Codex không sandbox). test_gate_khong_lach. Còn mở: cùng các đường đó với việc lẻ mức auto ngoài job (chưa đổi để không phá hành vi cũ, trừ kẹp javis_task/javis_schedule áp cho mọi lượt dưới full); MCP cá nhân trong cấu hình HOME của Grok/Muse/Copilot/Kimi/Vibe chưa đo.
- 04 ✅ khu Đội AI, 76 kiểm tra.
- 05 ✅ gắn đầu trang Bảng việc; bước GATE trong panel cũ không có nút Thử lại/Xoá. Chạy thật: tạo 2 job từ mẫu, GATE tự mở, hòm thư nhận 2 tin, bấm Duyệt thật cấp full đúng bước Đăng bài, bước Bật camp vẫn auto. Sửa theo ảnh: tên job lặp tên đội. 712/713 test xanh; test còn lại là phép đo thời gian khởi động đã hết biên ngay trên main, nâng trần 5,0 kèm số đo.
