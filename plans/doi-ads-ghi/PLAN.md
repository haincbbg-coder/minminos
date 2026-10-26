# Đội Ads ghi Facebook Ads: dựng camp TẮT trước GATE, bật sau GATE

Chủ repo chốt 2026-10-26: đi qua **MCP Meta Ads chính chủ** (`https://mcp.facebook.com/ads`, chủ đã thử tạo được campaign PAUSED thật);
trần ngân sách **700.000đ/camp/ngày**; tài khoản được phép ban đầu chỉ **"CÔNG TY HALIMI - ĐẠT 3" = act_1372588536646337**.
Quy tắc lên camp của chủ: camp tạo ra luôn TẮT/NHÁP, không tự bật khi chưa có xác nhận; tên camp "CÔNG TY TNHH MTV HALIMI - TÊN PAGE - <mã SP>";
mặc định 300.000đ/ngày, nữ 23-54, Việt Nam, giờ bắt đầu 23:59.
Branch: `claude/doi-ads-ghi-26.10.248` - PR #259.

## Xong là khi
- Bước "Dựng camp" của job Đội Ads tạo campaign + nhóm quảng cáo + quảng cáo ở dạng NHÁP/TẮT bằng công cụ hẹp `meta_ads_dung_camp`, lưu mã vào job, khung GATE hiện tài khoản, tên camp, ngân sách/ngày.
- Bước "Bật camp" (sau GATE, toàn quyền) dùng `meta_ads_bat_camp`: chỉ bật ĐÚNG các mã đã lưu trong job, kiểm lại luật, đọc lại trạng thái thật.
- Lớp chặn ở hub cho MỌI lệnh Meta Ads thô (kể cả ngoài job): tài khoản ngoài danh sách bị chặn; ngân sách vượt trần bị chặn; dưới full không được kích hoạt / sửa / đặt ACTIVE / publish_as_active; `ads_update_entity` là nguy hiểm.
- Ô "Giới hạn Đội Ads" để chủ sửa danh sách tài khoản và trần.
- Không có kết nối Meta MCP thì công cụ báo rõ "cần nối MCP Meta Ads chính chủ" (không giả vờ đã làm).

## Sự thật về MCP Meta (đọc từ schema thật, không đoán)
- Tên tool: `ads_create_campaign`, `ads_create_ad_set`, `ads_create_ad`, `ads_create_creative`, `ads_activate_entity`, `ads_update_entity`, `ads_get_ad_entities`, `ads_get_ad_accounts`, `ads_get_ad_account_pages`...
- `ad_account_id`: số, KHÔNG có tiền tố `act_`.
- Mọi lệnh cần `client_conversation_id`: 20 ký tự [A-Za-z0-9], tạo ở lệnh đầu, dùng lại giá trị Meta trả về ở các lệnh sau trong cùng lượt.
- `ads_create_campaign`: bắt buộc `ad_account_id, campaign_name, objective (OUTCOME_SALES|OUTCOME_TRAFFIC|OUTCOME_ENGAGEMENT|...), buying_type (AUCTION)`; ngân sách CBO `campaign_daily_budget` (số nguyên, đơn vị nhỏ nhất của tiền tài khoản; VND = đồng); `campaign_start_time` ISO 8601; `special_ad_categories` mặc định "[]". Luôn tạo PAUSED; khi bật chế độ nháp thì trả status=DRAFT kèm campaign_id.
- `ads_create_ad_set`: bắt buộc `ad_account_id, campaign_id, ad_set_name, billing_event (IMPRESSIONS), optimization_goal, targeting (JSON chuỗi: {"geo_locations":{"countries":["VN"]},"age_min":23,"age_max":54,"genders":[2]})`; dưới CBO KHÔNG truyền daily_budget. `promoted_object` JSON chuỗi (ví dụ {"page_id":"..."} hoặc pixel).
- `ads_create_ad`: bắt buộc `ad_account_id, ad_set_id, ad_name`, `creative` JSON chuỗi: một trong `{"object_story_id":"<page>_<post>"}` (bài có sẵn) hoặc `{"object_story_spec":{"page_id":..,"link_data":{"link":..,"message":..,"image_hash"|...}}}`. Luôn PAUSED/DRAFT.
- `ads_activate_entity`: `ad_account_id, entity_id, entity_type (campaign|ad_set|ad)`; với nháp: `object_ids` = danh sách mã campaign + ad set + ad, `publish_as_active=true` để bật target. Đây là lệnh tiêu tiền.
- `ads_get_ad_entities`: đọc lại `effective_status` (`object_ids`, `level`, `fields`, `object_state` live|draft).

## Hợp đồng

### Settings và luật (Lane 1 sở hữu `server/meta_ads_luat.py`)
- `settings["quyen"]["meta_ads"] = {"tai_khoan": ["1372588536646337"], "tran_ngay_vnd": 700000}` (mặc định như trên khi chưa có; tài khoản lưu dạng số không `act_`).
- `meta_ads_luat.doc_luat(settings=None) -> {"tai_khoan": [str], "tran_ngay_vnd": int}`
- `meta_ads_luat.chuan_tk(x) -> str` (bỏ `act_`, khoảng trắng)
- `meta_ads_luat.la_tool_meta_ads(tool_name) -> bool` (tên kết thúc bằng một tool Meta Ads ở trên, có hoặc không tiền tố connector)
- `meta_ads_luat.kiem_lenh(tool_name, args, mode, settings=None) -> str` : "" = cho qua, khác rỗng = câu lý do chặn tiếng Việt. Luật: tài khoản (`ad_account_id`) ngoài danh sách -> chặn (MỌI mức); mọi trường ngân sách ngày (`campaign_daily_budget`, `daily_budget`, `daily_spend_cap`, `fields.daily_budget`) > trần -> chặn (MỌI mức); trường ngân sách trọn đời -> chặn nếu > trần x 30 (ghi chú rõ); dưới `full`: `ads_activate_entity`, `ads_update_entity`, `ads_boost_*`, `*delete*`, mọi `status`/`fields.status` = ACTIVE, `publish_as_active` = true -> chặn.
- Route: `GET /meta-ads/luat` -> `doc_luat()` ; `POST /meta-ads/luat` form `data` (JSON {tai_khoan, tran_ngay_vnd}) -> lưu, kiểm hợp lệ (trần 50.000-50.000.000đ, tài khoản là số). POST đi qua lớp CSRF chung.

### Plugin (Lane 2 sở hữu `system/plugins/meta-ads-camp/`)
- `meta_ads_dung_camp` (min_mode `safe`): tham số `{page_id, page_ten, ma_sp, ngan_sach_ngay_vnd?(mặc định 300000), objective?(mặc định OUTCOME_SALES), creative (object_story_id hoặc link_data), tai_khoan?(mặc định tài khoản đầu danh sách), gio_bat_dau?}`. Tự đặt tên camp theo mẫu; ép trạng thái PAUSED/nháp; kiểm `meta_ads_luat.kiem_lenh`; gọi tuần tự create campaign -> ad set -> ad qua kết nối MCP Meta; trả JSON `{"ok", "tai_khoan", "campaign_id", "adset_ids", "ad_ids", "ten", "ngan_sach_ngay_vnd", "trang_thai": "NHAP|TAT", "loi"?}` và gọi `tasks.current().job_ads_luu(task_id, ads)` khi đang chạy trong một bước job.
- `meta_ads_bat_camp` (min_mode `full`): KHÔNG nhận mã từ AI; đọc `tasks.current().job_ads_doc(task_id)`; kiểm lại luật; gọi `ads_activate_entity` với `object_ids` = đúng các mã đã lưu, `publish_as_active=true`; đọc lại `effective_status`; trả kết quả trung thực (PUBLISHING không phải "đã chạy").

### Kanban (Lane 3 sở hữu `server/tasks.py`, `system/doi-ai-mau.json`)
- `job_ads_luu(task_id, ads) -> bool` lưu vào `jobs.metadata.ads` của job chứa task đó; `job_ads_doc(task_id) -> dict|None`.
- Cách plugin biết `task_id` đang chạy: lane 2 tìm (gợi ý: `once_ledger` gắn job `kanban:<tid>` cho lượt chạy - tìm contextvar/accessor hiện có; nếu không có thì lane 3 cung cấp `tasks.current_task_id()` dựa trên cơ chế gắn mã việc `_gan_ma_viec`). Hai lane thống nhất qua hàm `tasks.ma_viec_dang_chay() -> str` do lane 3 viết.
- `jobs_view(...).gate_cho.ads` = `jobs.metadata.ads` khi có.
- Mẫu `ads-len-camp`: bước dựng camp gọi `meta_ads_dung_camp` (capability `files` hoặc `auto` để chạy ở mức auto); bước bật camp chỉ được gọi `meta_ads_bat_camp`.
- Bước job ở mức `full` cũng `mcp_strict` (chỉ MCP do MinMin đưa vào), để lệnh bật camp luôn đi qua lớp kiểm của hub.

### Giao diện (Lane 4 sở hữu `dashboard/doi-ai.js`, `dashboard/doi-ai.css`, i18n)
- Khung GATE: có `gate_cho.ads` thì hiện thẻ "Camp sẽ bật": tài khoản, tên camp, ngân sách/ngày, số nhóm quảng cáo/quảng cáo, trạng thái hiện tại.
- Ô gập "Giới hạn Đội Ads" trong khu Đội AI: danh sách tài khoản (mỗi dòng một mã), trần/ngày; GET/POST `/meta-ads/luat`.

## Phase
| Phase | Mục tiêu | File | Lane |
|---|---|---|---|
| 01 | Luật + lớp chặn hub + route luật | `server/meta_ads_luat.py` (mới), `server/mcp_hub.py`, `server/mcp_catalog.py`, `server/main.py` (chỉ đăng ký route ở cuối + mặc định), `tests/python/test_meta_ads_luat.py` (mới), `tests/python/route_table.json` | 1 |
| 02 | Plugin dựng/bật camp | `system/plugins/meta-ads-camp/*` (mới), `tests/python/test_meta_ads_camp.py` (mới) | 1 |
| 03 | Kanban: lưu mã camp vào job, mẫu, strict ở full | `server/tasks.py`, `system/doi-ai-mau.json`, `tests/python/test_doi_ai_ads.py` (mới) | 1 |
| 04 | Giao diện GATE + Giới hạn Đội Ads | `dashboard/doi-ai.js`, `dashboard/doi-ai.css`, `dashboard/i18n/vi.json`, `dashboard/i18n/en.json`, `tests/js/test_doi_ai.js` | 1 |
| 05 | Nối lại, chạy thật với MCP Meta giả, toàn bộ test | - | 2 |
| GATE | Bố duyệt | - | - |

## Kết quả
- 01 ✅ `server/meta_ads_luat.py` + chặn ở `mcp_hub._guard` (nhận MCP Meta theo địa chỉ `mcp.facebook.com/ads`), route GET/POST `/meta-ads/luat`. Lệnh bật/sửa thô trong bước job chỉ được nhắm đúng mã đã lưu, kể cả ở full.
- 02 ✅ plugin `meta-ads-camp`: `meta_ads_dung_camp` (safe) và `meta_ads_bat_camp` (full). Bật bản nháp bằng object_ids + publish_as_active, rồi bật từng nhóm/quảng cáo còn TẮT, đọc lại effective_status; chỉ báo ok khi đủ ACTIVE.
- 03 ✅ `job_ads_luu` (chỉ bước đứng trước GATE chưa duyệt) / `job_ads_doc`, `gate_cho.ads`, mẫu `ads-len-camp` dùng hai công cụ. Bước job ở full: strict MCP + `ENABLE_CLAUDEAI_MCP_SERVERS=false` (engine nhận `env_them`).
- 04 ✅ thẻ "Camp sẽ bật" trong khung GATE + ô gập "Giới hạn Đội Ads".
- 05 ✅ test_doi_ads_ghi (73 kiểm tra, MCP Meta giả), test_doi_ai thêm 13. Chạy thật trên máy chủ cục bộ: GATE hiện thẻ camp, lưu giới hạn qua giao diện, Duyệt mở đúng bước Bật camp. Chưa thử được với Meta thật (không đụng tài khoản của chủ từ đây).
- Soát độc lập (agent riêng, không xem lập luận của người viết) tìm 3 lỗ nặng + 8 lỗ vừa/nhẹ, đã sửa hết:
  mã việc chưa tới hub ở Codex/Grok/Muse... (nay gắn header X-Javis-Job cho mọi engine phụ); bật camp NHÁP không kèm object_ids đăng lậu con chưa duyệt (nay bắt buộc liệt kê, và trong bước job chỉ còn lệnh bật được phép); connector Facebook Ads native ngoài job (nay chặn ở MỌI phiên Claude); tool ghi lạ lọt qua (nay tên không có từ đọc coi là ghi, chỉ tạo nháp mới được dưới full); ngân sách trọn đời / lịch ngân sách / sao chép từ đối tượng có sẵn / ngân sách nhóm riêng (nay cấm); đọc lại ngân sách trước khi bật hỏng (nay đọc daily/lifetime cả chiến dịch lẫn nhóm, đọc lỗi thì không bật); lưu mã từ bước không đứng ngay trước GATE; lấy nhầm `id` lồng (nay chỉ khoá đã khai, phải là số); soát quá trần nút thì cho qua (nay chặn); `ok` khi mới một cấp ACTIVE (nay phải đủ).
  Còn mở: MCP Facebook do người dùng tự cài trong cấu hình RIÊNG của Codex/Grok/Muse (không phải ~/.claude.json) chưa bị chặn; lệnh bật thô ở chat toàn quyền của chủ (ngoài job) không đọc lại tài khoản sở hữu của entity_id.
- Lệch so với hợp đồng: không có tham số `objective` (loại camp tự chọn theo luật landing/bài viết của chủ); `tasks.ma_viec_dang_chay()` không cần vì `once_ledger.current_job()` đã mang mã việc cả đường in-process lẫn HTTP.
