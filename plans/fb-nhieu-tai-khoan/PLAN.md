# Facebook nhiều tài khoản: soi quyền, quét Trang, bật/tắt camp có duyệt

Thiết kế đã chọn: **phương án A "Bảng gộp theo Trang"** trên canvas "MinMin Facebook nhiều tài khoản"
(chủ repo chốt 2026-10-26), cộng màn Soi quyền, thẻ duyệt bật/tắt camp trong chat và trên Telegram.
Branch: `claude/fb-nhieu-tai-khoan-26.10.252` - PR #264.

## Vì sao
Chủ nối nhiều tài khoản Facebook (app tự tạo, Graph API). Trang chủ cầm quyền cá nhân (quản trị,
biên tập) không hiện. Mã đọc `me/accounts` / `me/adaccounts` và không lọc gì: thứ thiếu là thứ
Facebook không giao cho token. Chủ cần (1) thấy rõ tài khoản nào cầm gì, cái gì chưa giao và vì sao,
(2) đăng bài và bật/tắt camp trên đúng tài khoản. Kết nối Meta Ads (Graph) hiện CHỈ ĐỌC.

## Xong là khi
- Trang Kết nối, tab Đã nối, có khối "Facebook - Trang và tài khoản quảng cáo" (chỉ hiện khi có kết
  nối `facebook-pages` hoặc `meta-ads-graph`): hàng thẻ tài khoản Facebook, tab Trang / Tài khoản
  quảng cáo / Cần xử lý, bảng gộp mỗi Trang một dòng, mỗi tài khoản một cột (vai trò + nguồn),
  cột "MinMin đăng bằng".
- Màn Soi quyền cho một tài khoản: 4 ô tóm tắt, dải quyền token, danh sách chưa giao kèm lý do +
  cách sửa, ô "Hỏi Facebook về một Trang" trả lời bằng lời thường, có nguyên văn Facebook gập lại.
- Danh sách Trang lật trang (không dừng ở 200); đưa ID Trang không có trong danh sách thì thử lấy
  thẳng theo ID trên từng tài khoản.
- Công cụ `meta_ads_tim` (đọc) tìm chiến dịch/nhóm/quảng cáo theo tên trên mọi tài khoản;
  `meta_ads_de_xuat_trang_thai` (safe) KHÔNG đổi gì, chỉ tạo đề xuất chờ duyệt và trả thẻ.
  Chỉ người bấm Duyệt (dashboard hoặc Telegram) mới làm MinMin đổi trạng thái thật, đọc lại kết quả,
  ghi sổ hành động. Có Từ chối, Sửa lại, Hoàn tác (30 phút). Tôn trọng chính sách "Tiền & quảng cáo"
  = chặn của Quyền theo loại việc.

## Không làm (bản này)
- Không đổi phạm vi quyền mà gói kết nối xin (gói nằm ở kho ngoài). Thiếu quyền thì Soi quyền nói rõ.
- Không nâng quyền app với Meta (việc của chủ, chỉ có hướng dẫn).
- Không đụng đường MCP Meta chính chủ và luật Đội Ads của PR #259.
- Trang cá nhân CHƯA tick lúc đăng nhập không lộ qua API: chỉ phát hiện được khi tài khoản khác/BM
  thấy nó, hoặc chủ hỏi bằng ID/link. Màn Soi quyền nói đúng như vậy.

## Hợp đồng

### Python: `server/meta_tai_san.py` (lane 1)
Nguồn: mọi kết nối đã đăng nhập có `connector_id` thuộc `facebook-pages`, `meta-ads-graph`. Gom theo
`fb_id` (GET `me?fields=id,name`). Chèn được để test: `dat_ket_noi(fn)`, `dat_token(fn)`, `dat_http(fn)`.
- `async tai_san() -> dict` (đệm 120 giây, `lam_moi=True` bỏ đệm):
```
{"ok": true, "kiem_luc": "<iso>", "loi": [str],
 "tai_khoan": [{"fb_id","ten","ten_fb","mac_dinh":bool,
   "ket_noi":[{"id","connector_id","label"}],
   "token":{"trang_thai":"tot|sap_het|het_han|loi","con_ngay":int|null,"loi":""},
   "so_trang":int,"so_tkqc":int,"can_xu_ly":int,"thieu_quyen":[{"ma","ten"}]}],
 "trang": [{"id","ten","nguon":{"<fb_id>":{"vai_tro":"quan_tri|bien_tap|kiem_duyet|quang_cao|phan_tich|khac",
            "qua":"ca_nhan|bm","bm_ten":"","giao":bool}},
            "dang_bang":"<fb_id>|", "van_de":"|chua_giao"}],
 "tkqc": [{"id":"<số>","ten","nguon":{"<fb_id>":{"qua":"ca_nhan|bm","bm_ten":"","giao":bool}},
           "dung":"<fb_id>|", "van_de":"|chua_giao|thieu_quyen_ghi"}]}
```
- `async soi_quyen(fb_id) -> dict`:
```
{"ok", "tai_khoan":{...như trên...}, "ung_dung":"<tên app>",
 "quyen":[{"ma","ten","co":bool,"de_lam":"<cần để làm gì>"}],
 "trang_giao":int, "tkqc_giao":int,
 "chua_giao":[{"loai":"trang|tkqc","id","ten","vai_tro","qua","bm_ten","ly_do_ma","ly_do","cach_sua","nut":"dang_nhap_lai|cap_quyen|huong_dan"}]}
```
- `async hoi_trang(fb_id, q) -> dict` (q = tên, ID hoặc link facebook.com):
```
{"ok", "id", "ten", "ket_qua":"giao|giao_khong_dang|chua_giao_bm|khong_thay_quyen|khong_tim_thay|thieu_quyen|loi_token|can_id",
 "ly_do", "cach_sua", "nguyen_van"}
```
- Không bao giờ trả access token ra ngoài.

### Python: `server/meta_ads_duyet.py` (lane 1)
Kho đề xuất (JSON trong STATE_DIR), hết hạn 30 phút. Chèn được: `dat_http`, `dat_token`, `dat_gui_telegram`.
- `async tao(muc:[{"id","trang_thai":"bat|tat"}], chat="", ly_do="") -> dict`: đọc từng đối tượng bằng
  token đọc được nó, lưu `{id, tao_luc, het_han, trang_thai:"cho", muc:[{id,cap,ten,tk_id,tk_ten,fb_id,fb_ten,conn_id,
  tu,sang,chi_hom_nay,ngan_sach_ngay}], chat, ly_do}`; chat là chat_id Telegram thì gửi tin có nút.
- `xem(id) -> dict|None` (bản gọn, không token).
- `async quyet(id, hanh_dong:"duyet|tu_choi|sua|hoan_tac", ai="", nguon="dashboard") -> dict`: duyệt chạy đúng
  một lần (bấm lại không chạy lại); đọc lại trạng thái thật; ghi `hanh_dong` sổ; hoàn tác chỉ cho mục đã đổi
  thành công, trong 30 phút từ lúc đổi.
- Chặn khi chính sách loại việc `tien` = `chan`.

### HTTP (đăng ký ở ĐUÔI main.py)
- `GET /meta/tai-san?lam_moi=0|1` -> `tai_san()`
- `GET /meta/soi-quyen?fb_id=` -> `soi_quyen()`
- `POST /meta/hoi-trang` form `fb_id, q` -> `hoi_trang()`
- `GET /meta-ads/duyet/{id}` -> `xem()` (404 khi không có)
- `POST /meta-ads/duyet/{id}` form `hanh_dong` -> `quyet()`
- Telegram callback `fa:<id>:d|t` -> `quyet(...nguon="telegram")`.

### Plugin
- `meta-pages-graph`: `_pages` lật trang; `_resolve_page` thử lấy thẳng theo ID (GET `<id>?fields=id,name,access_token,tasks`).
- `meta-ads-graph`: thêm `meta_ads_tim` (readonly), `meta_ads_de_xuat_trang_thai` (safe) gọi `meta_ads_duyet.tao`.
  Kết quả web trả dòng `<!-- JAVIS_CARD: {"type":"duyet_ads","id":"<id>"} -->` để model chép nguyên vào câu trả lời.

### Giao diện (lane 2)
- `dashboard/fb-tai-san.js` + `dashboard/fb-tai-san.css` (mới): `window.FbTaiSan.mount(el)` vẽ khối phương án A,
  mở màn Soi quyền (hộp phủ), ô Hỏi Facebook. Chỉ token `--mm-*`.
- `dashboard/chat-card.js`: nhận `type:"duyet_ads"` (id `[a-z0-9]{8,32}`) -> khung chờ `data-duyet-ads`.
  `dashboard/duyet-ads.js`: nạp `GET /meta-ads/duyet/{id}`, vẽ thẻ theo thiết kế, nút gọi `POST`. Nội dung thẻ
  lấy từ máy chủ, không từ chữ model.
- `console.js` renderConnect: chèn `<div id="fbTaiSan">` đầu tab Đã nối khi có kết nối Facebook; `index.html` nạp file.
- i18n vi/en khoá `fbts.*`, `dads.*`.

## Phase
| Phase | Mục tiêu | File (độc quyền) | Phụ thuộc | Kiểm | Lane |
|---|---|---|---|---|---|
| 01 | Soi quyền + tài sản gộp + hỏi Trang | `server/meta_tai_san.py`, `tests/python/test_meta_tai_san.py` | hợp đồng | test mới | 1 |
| 02 | Quét Trang lật trang + lấy theo ID | `system/plugins/meta-pages-graph/plugin.py`, `tests/python/test_meta_pages.py` | - | test cũ + mới | 1 |
| 03 | Đề xuất + duyệt bật/tắt camp | `server/meta_ads_duyet.py`, `system/plugins/meta-ads-graph/*`, `tests/python/test_meta_ads_duyet.py` | hợp đồng | test mới | 1 |
| 03b | Route + Telegram | `server/main.py` (đuôi + nhánh `fa:`), `tests/python/route_table.json` | 01, 03 | test route | 1 |
| 04 | Giao diện A + Soi quyền + thẻ duyệt | `dashboard/fb-tai-san.*`, `dashboard/duyet-ads.js`, `dashboard/chat-card.js`, i18n, `tests/js/test_fb_tai_san.js` | hợp đồng | test JS + token | 2 |
| 05 | Gắn trang, chạy thật với Facebook giả, chụp màn, toàn bộ test | `dashboard/console.js`, `dashboard/index.html` | 01-04 | ảnh + test | 1 |
| GATE | Bố xem ảnh | - | 05 | - | - |
| 06 | Changelog, merge, phát hành | `CHANGELOG.md` | GATE | CI xanh | - |

## Kết quả
