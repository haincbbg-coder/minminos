# Đội Social bản đầy đủ (26.10.187) - hợp đồng kiến trúc

Tài liệu này là HỢP ĐỒNG giữa 4 phần làm song song: máy chủ, trang web, Worker lõi + Facebook,
Worker các nền tảng khác. Đổi hợp đồng thì sửa file này trước.

Mục tiêu: trang `/apps/doi-social/` là một ứng dụng web đầy đủ cùng bố cục và tính năng với bản
demo LOHA Agents (xem `docs/doi-social/QUAN-SAT.md`),
KHÁC ở chỗ: tài khoản là profile GPM Login đã đăng nhập sẵn trên máy ở nhà, nên KHÔNG có tạo tài
khoản, proxy, tiện ích, gói giá. AI là chính bộ não MinMin (không cần khoá API riêng).

Không chép mã, chữ, logo của LOHA. Viết lại bằng lời MinMin.

## 0. Nguồn sự thật dùng chung

`server/doi_social_kich_ban.py` - 41 mẫu (id, nền tảng, nhóm, tham số, hành động bị đếm), danh sách
`HANH_DONG`, `GIOI_HAN_MAC_DINH`, `kiem_tham_so()`. **Id mẫu = `ky_nang` của việc gửi xuống Worker.**
Không ai sửa id mẫu. Thêm tham số thì sửa file này (chỉ phần máy chủ).

## 1. Mô hình dữ liệu (SQLite `STATE_DIR/doi-social/doi-social.db`, mở bởi `doi_social.mo`)

Bảng cũ giữ nguyên: `ma_ghep`, `may`, `nick`, `viec`, `cai_dat`. Bổ sung (migration `ALTER TABLE ... ADD COLUMN`
bọc try, idempotent):

- `may`: + `kich_ban TEXT DEFAULT '[]'` (danh sách id mẫu Worker làm được, gửi trong nhịp), + `song_song INTEGER DEFAULT 1`.
- `viec`: + `dot_id INTEGER`, + `chay_thu INTEGER DEFAULT 0`, + `ket_qua TEXT DEFAULT '{}'` (số đếm thành công/bỏ qua/lỗi do Worker báo).
- `nick_meta(nick_id PK, nhan TEXT '[]' (nền tảng: facebook, tiktok...), tao_tu TEXT 'YYYY-MM', ghi_chu, canh_bao TEXT '{}' ({nen_tang: "dang_xuat"|"checkpoint"|"captcha"|"qua_nhanh"}), lan_chay REAL)`.
- `dot_chay(id, ten, kich_ban, nick TEXT json ids, tham_so json, song_song, chay_an, chay_thu, trang_thai: cho|dang_chay|hoan_tat|huy, tao_luc, xong_luc, lich_id, nguon: web|lich|tro_ly|telegram)`.
- `lich_hen(id, ten, kich_ban, nick json, tham_so json, song_song, cron, bat, lan_ke REAL, lan_truoc REAL, so_lan, so_loi, tao_luc)`.
- `su_kien(id, luc REAL, viec_id, dot_id, nick_id, nick_ten, nen_tang, kich_ban, tinh_nang, hanh_dong, ket_qua: thanh_cong|bo_qua|loi|thong_tin, chi_tiet, link, nhom, san_pham, ma)` + index (luc), (nick_id, luc).
- `kho_bai(id, nen_tang, nick_id ''=chung, tieu_de, noi_dung, tep json [{ten, luu, co}], trang_thai: cho|dang_giu|da_dang|loi, giu_boi_viec, luc_tao, luc_dang, link, loi)`. Tệp ở `STATE_DIR/doi-social/kho/<id>/`.
- `ban_nhap(id, loai: binh_luan|bai_dang|tra_loi, noi_dang: fb_nhom|fb_tuong|fb_trang|threads|instagram|reddit|x|tiktok, nick_id, nick_ten, nhom, link_goc, bai_goc, ly_do, noi_dung, san_pham_id, trang_thai: cho_duyet|da_duyet|da_dang|da_bo|loi|het_han, tao_luc, het_han REAL, viec_tao TEXT, ket_qua, tep json)`.
- `kien_thuc(id, loai: san_pham|chu_de, ten, mo_ta, gia, link, tu_khoa, giong_van, dan_rieng, trang_thai: dang_dung|cho_duyet, tao_luc)`; `tai_lieu(id, kt_id, ten, noi_dung)`; `hoi_dap(id, kt_id, hoi, dap, trang_thai: da_tra_loi|cho_ban, nguon, luc)`.
- `nhom_fb(id, san_pham_id, link UNIQUE per sp, ten, trang_thai: cho_duyet|da_duyet|den, nick_chinh, nick_tuong_tac json, tinh_trang_vao json {nick_id: da_vao|cho_duyet|bi_tu_choi}, lan_quet REAL, quet_lai_gio INT 24, ghi_chu)`.
- `hoi_thoai(id, nick_id, nick_ten, khach_ten, khach_link UNIQUE per nick, san_pham_id, trang_thai: bot_dang_lo|can_tra_loi_tay|da_xu_ly|spam, tiem_nang INT, sdt, nhuong_den REAL, cap_nhat REAL)`; `tin_nhan(id, ht_id, tu: khach|bot|chu, noi_dung, luc)`.
- `ke_hoach(id, mo_ta, buoc json [{kich_ban, nick:[ids], tham_so, ghi_chu}], trang_thai: cho_duyet|dang_chay|hoan_tat|tu_choi, nguon, chat_id, tao_luc, dot_ids json)`; `tro_ly(id, phien, vai: nguoi|ai, noi_dung, ke_hoach_id, luc)`.
- Giới hạn v2: `cai_dat` khoá `gioi_han_v2` (JSON cùng dạng `GIOI_HAN_MAC_DINH`, ghép sâu với mặc định).

Mã nguồn: phần lớn ở module mới `server/doi_social_v2.py` (cùng kết nối `doi_social._db()`), để
`doi_social.py` cũ không phình. AI ở `server/doi_social_ai.py` (dựng prompt + bóc JSON, không gọi mạng; hàm gọi AI được tiêm vào).

## 2. Vòng đời

- **Đợt chạy** (bulk run): `tao_dot(...)` kiểm mẫu + tham số + nick → tạo 1 `viec` cho mỗi nick
  (`ky_nang` = id mẫu, `trang_thai='cho_chay'`, vì chủ đã bấm Bắt đầu trên web hoặc duyệt kế hoạch;
  `tham_so` = {kich_ban, tham_so, chay_thu, dot_id, han_muc, nghi_giay, nen_tang}). Đợt xong khi mọi việc xong/lỗi.
  Huỷ đợt = việc `cho_chay` → `bo`, việc đang chạy nhận cờ dừng (Worker hỏi `/may/dung/{vid}`).
- `nhan_viec` mới: mỗi máy chạy tối đa `may.song_song` việc cùng lúc (ghi đè được bằng `song_song` của đợt,
  trần 3); khoảng nghỉ giữa 2 việc của cùng nick = ngẫu nhiên trong `chung.nghi_phut` [a,b] (cũ: số phút cố định;
  việc `fb_dang_bai` cũ vẫn theo `gioi_han()` cũ). Một nick không chạy 2 việc cùng lúc. Không giao việc của mẫu mà
  máy không báo có trong `kich_ban` (trừ `fb_dang_bai`).
- **Hạn mức** (`han_muc`): lúc giao việc, máy chủ tính cho nick đó, mỗi hành động trong `mau.hanh_dong`:
  `con_lai = tran(hanh_dong, tuoi_nick, tuan) - da_lam_hom_nay` (đếm `su_kien` thanh_cong hôm nay theo nick+hanh_dong).
  Trần: nick lâu năm (tuổi ≥ `lau_nam_sau_ngay`, tuổi tính từ `tao_tu`, không có thì coi là mới) dùng số thứ 2,
  nick mới dùng số thứ 1 nhân (1 + tang_tuan_pt/100)^(số tuần từ lần chạy đầu) nhưng không quá số thứ 2.
  Đồng thời tổng việc/ngày (`viec_ngay_moi|lau`). `con_lai` = 0 cho mọi hành động → việc kết thúc `bo_qua` ngay ở máy chủ
  với thông điệp "đã đủ giới hạn hôm nay".
- **Sự kiện**: Worker báo từng thao tác qua `/may/su-kien/{vid}`. Máy chủ ghi `su_kien`, trả lại `con_lai` mới.
  `ma` ∈ {dang_xuat, checkpoint, captcha, qua_nhanh} → ghi `nick_meta.canh_bao[nen_tang]`, đưa vào "Cần bạn xử lý".
  Một sự kiện thành công sau đó của cùng nền tảng xoá cảnh báo.
- **Kho bài**: `/may/kho/lay` giữ (dang_giu) 1 bài cho việc; `/may/kho/{id}/ket-qua` {ok, da_bam_dang, link, loi}:
  ok → da_dang; lỗi và da_bam_dang=false → trả về `cho`; lỗi và da_bam_dang=true → `loi` (không tự đăng lại).
  Kho rỗng → Worker báo sự kiện `bo_qua` chi_tiet "Hết bài" `ma='het_bai'` (trang hiện vàng).
- **Bản nháp**: Worker ở `chay_thu`/`duyet_truoc` gửi nháp qua `/may/ban-nhap` (hết hạn mặc định 18 giờ với bình
  luận, 72 giờ với bài đăng). Chủ Duyệt → máy chủ tạo việc `dang_ban_nhap` (ky_nang nội bộ, xem 4.3) cho đúng nick,
  `cho_chay`. Ở `chay_thu` nháp vẫn vào hàng duyệt nhưng gắn cờ `chay_thu` (duyệt thì vẫn đăng được - chủ quyết).
  Mẫu đăng bài AI (`fb_dang_nhom_ai`, `fb_dang_tuong_ai`, `th_dang_ai`, `ig_dang_ai`) lấy nháp `da_duyet` qua `/may/ban-nhap/lay`.
- **Lịch hẹn**: vòng nền 30 giây (`asyncio` task trong `register`) tìm lịch `bat` có `lan_ke <= now` → tạo đợt
  (nguon=lich), tính `lan_ke` mới bằng `cron_util.cron_next(cron, now, localefmt.tz())`. Cùng vòng: nháp quá hạn → het_han;
  lịch quét lại nhóm (chỉ đánh dấu, việc quét do mẫu chạy). Mô tả lịch cho người đọc: `cron_util.describe_cron`.
- **Kế hoạch AI**: Trợ lý trả kế hoạch (các bước = đợt chạy). Chủ Duyệt (web hoặc nút Telegram `dsk:<id>:1|0`) →
  tạo đợt cho từng bước (nguon=tro_ly). Kế hoạch KHÔNG tự chạy khi chưa duyệt.

## 3. API máy chủ

Tất cả trả JSON `{ok: true, ...}` hoặc `{ok: false, error}` (HTTP 4xx). Trang quản lý cần đăng nhập + `ly_do_chan()`.
Thời gian là epoch giây (float). Phân trang: `?trang=1&moi_trang=50` → `{tong, trang, muc: [...]}`.

### 3.1 Cho trang web
| Phương thức | Đường | Ghi chú |
|---|---|---|
| GET | `/doi-social/tong-quan?ngay=14` | `{nick_tong, nen_tang_dung:[...], ai:{engine, mo_hinh, nhin_anh, san_sang}, may:[{id,ten,online,phien_ban}], so7:{luot, thanh_cong, dang_chay, loi, ty_le}, bieu_do:[{ngay:'YYYY-MM-DD', thanh_cong, loi}], hom_nay, can_xu_ly:[{loai, tieu_de, chi_tiet, nut, den:'#/...'}]}` |
| GET | `/doi-social/kich-ban` | `danh_muc()` + mỗi mẫu thêm `san_sang: bool` (có máy online/đã ghép báo hỗ trợ) |
| GET | `/doi-social/nick` | `[{id, ten, may_id, may_ten, nhom (thư mục GPM), trinh_duyet, co_proxy, nhan, tao_tu, tuoi_ngay, muc ('moi'|'lau'), canh_bao, lan_chay, online}]` |
| POST | `/doi-social/nick/meta` | `{ids:[...], nhan?:[...], tao_tu?:'YYYY-MM', ghi_chu?}` áp cho nhiều nick |
| GET/POST | `/doi-social/gioi-han-v2` | GET → `{gia_tri, mac_dinh, hanh_dong}`; POST body cùng dạng `gia_tri` (ghép sâu) |
| GET | `/doi-social/dot-chay?trang_thai=&tu=` | danh sách đợt + `tien_trinh:{tong, xong, loi, dang}` |
| POST | `/doi-social/dot-chay` | `{ten?, kich_ban, nick:[ids], tham_so:{}, song_song:1..3, chay_an:bool, che_do:'ngay'|'hen', cron?}` → `{dot}` hoặc `{lich}` |
| GET | `/doi-social/dot-chay/{id}` | đợt + `viec:[...]` + `su_kien` gần nhất |
| POST | `/doi-social/dot-chay/{id}/huy` | |
| GET | `/doi-social/lich-hen` | `[{..., mo_ta_lich, lan_ke, lan_truoc}]` |
| POST | `/doi-social/lich-hen/{id}` | `{bat?, ten?, cron?, nick?, tham_so?}` |
| DELETE | `/doi-social/lich-hen/{id}` | |
| POST | `/doi-social/lich-hen/{id}/chay` | chạy ngay một lần |
| GET | `/doi-social/lich-su?trang_thai=&kich_ban=&trang=` | việc (kèm tên đợt, mẫu) |
| GET | `/doi-social/dang-chay` | việc `dang_chay` + bước nhật ký gần nhất |
| GET | `/doi-social/hom-nay-theo-nick` | `[{nick_id, nick_ten, thanh_cong, bo_qua, loi, chi_tiet:'Bình luận 2 · Thích 5'}]` |
| GET | `/doi-social/su-kien?tu=&den=&nick=&tinh_nang=&ket_qua=&trang=` | dòng thời gian |
| GET | `/doi-social/su-kien.csv?...` | cùng bộ lọc, UTF-8 có BOM |
| GET | `/doi-social/kho?nen_tang=` | `{chung:{con, da_dang, loi}, theo_nick:[{nick_id, nick_ten, con, da_dang, loi}]}` |
| GET | `/doi-social/kho/muc?nen_tang=&nick=&trang_thai=&trang=` | |
| POST | `/doi-social/kho` | multipart: `nen_tang, nick ('' = chung), tieu_de, noi_dung, tep[]` (nhiều bài: `noi_dung` có dòng `===` tách bài) |
| DELETE | `/doi-social/kho/{id}` · POST `/doi-social/kho/{id}/tra-lai` | |
| GET | `/doi-social/kho/tep/{id}/{luu}` | xem trước ảnh/video |
| POST | `/doi-social/viet-bai` | `{san_pham_id, noi_dang, nick_id?, nhom?, so_ban:1..5, yeu_cau?}` → AI viết, tạo nháp `bai_dang` |
| GET | `/doi-social/ban-nhap?trang_thai=cho_duyet&noi_dang=&san_pham=&trang=` | + `dem:{cho_duyet, da_duyet, da_dang, da_bo, loi, het_han}`, `dem_noi_dang:{...}` |
| POST | `/doi-social/ban-nhap/{id}/duyet` · `/bo` · `/viet-lai {yeu_cau?}` | |
| PUT | `/doi-social/ban-nhap/{id}` | `{noi_dung}` sửa tay |
| POST | `/doi-social/ban-nhap/duyet-nhieu` | `{ids, dong_y}` |
| GET/POST | `/doi-social/kien-thuc` | GET → `[{..., so_tai_lieu, so_hoi_dap, so_nhom, cho_ban}]`; POST tạo |
| GET/PUT/DELETE | `/doi-social/kien-thuc/{id}` | GET kèm `tai_lieu, hoi_dap, nhom` |
| POST | `/doi-social/kien-thuc/{id}/tai-lieu` | `{ten, noi_dung}` hoặc multipart tệp .txt/.md (PDF/DOCX: trích chữ nếu có thư viện, không thì báo) |
| DELETE | `/doi-social/tai-lieu/{id}` | |
| POST | `/doi-social/kien-thuc/{id}/hoi-dap` | `{hoi, dap}`; PUT `/doi-social/hoi-dap/{id}` `{dap}` → da_tra_loi; DELETE |
| GET | `/doi-social/nhom-fb?san_pham=` | |
| POST | `/doi-social/nhom-fb` | `{san_pham_id, links:[...] hoặc link, ten?}` |
| PUT/DELETE | `/doi-social/nhom-fb/{id}` | `{trang_thai?, nick_chinh?, nick_tuong_tac?, quet_lai_gio?}` |
| GET | `/doi-social/hoi-thoai?tab=can_tay|tat_ca|tiem_nang` | + `dem` |
| GET | `/doi-social/hoi-thoai/{id}` | kèm `tin` |
| POST | `/doi-social/hoi-thoai/{id}` | `{hanh_dong: cho_ai_tiep|spam|da_xu_ly}` |
| POST | `/doi-social/hoi-thoai/{id}/tra-loi` | `{noi_dung}` → việc `fb_gui_tin` (ky_nang nội bộ) cho nick, `cho_chay` (chủ tự gõ nên không cần duyệt); ghi tin `chu`, nhường bot 12 giờ |
| POST | `/doi-social/tro-ly` | `{tin, phien?}` → `{phien, tra_loi, ke_hoach?}` |
| GET | `/doi-social/tro-ly/lich-su?phien=` · GET `/doi-social/tro-ly/phien` | |
| GET | `/doi-social/ke-hoach` · POST `/doi-social/ke-hoach/{id}/duyet` · `/tu-choi` | |

Trang tĩnh: `GET /apps/doi-social/{ten}` phục vụ MỌI tệp trong `apps/doi-social/web/` có tên khớp
`^[a-z0-9][a-z0-9._-]*\.(html|js|css|svg|png|webp|json)$` (kể cả thư mục con 1 cấp `{thu_muc}/{ten}`), không cho `..`.

### 3.2 Cho Worker (miễn đăng nhập, header `x-minmin-may`)
Cũ giữ nguyên: `ghep`, `nhip`, `viec` (long-poll), `tep/{vid}/{luu}`, `ket-qua/{vid}`.

- `POST /may/nhip` thêm trường `kich_ban: [ids]`, `song_song: int`. Phản hồi thêm `phien_ban_worker` (đọc `PHIEN_BAN` từ
  `apps/doi-social/worker/minmin_worker.py` của máy chủ) để Worker tự cập nhật.
- `GET /may/ban-cap-nhat` → zip mã Worker (giống `/doi-social/tai-worker.zip`, nhưng xác thực bằng token máy, KHÔNG gồm worker.json).
- `GET /may/viec` trả `viec` có `tham_so` mới (mục 2). Việc `ket-qua` thêm `dem:{thanh_cong, bo_qua, loi}`; việc
  không có thao tác thành công nào thì Worker gửi `ok=false`.
- `POST /may/su-kien/{vid}` `{hanh_dong, ket_qua, chi_tiet, link?, nhom?, san_pham?, ma?}` → `{con_lai:{hanh_dong:n}, dung:bool}`.
- `POST /may/buoc/{vid}` `{dong}` một dòng nhật ký trực tiếp (cho mục "Đang chạy"; giữ 30 dòng cuối trong bộ nhớ).
- `GET /may/dung/{vid}` → `{dung:bool}` (đợt bị huỷ).
- `POST /may/ai` `{viec_id, muc_dich, du_lieu, anh?:[base64 jpeg ≤4]}` → `{ok, ket_qua}`. `muc_dich`:
  - `cham_bai` du_lieu `{bai:{chu, tac_gia, link, binh_luan:[...]}, san_pham_id}` → `{diem:0-100, chon:bool, ly_do, la_doi_thu:bool}`
  - `viet_binh_luan` `{bai, san_pham_id, kieu?:'tu_nhien'|'tu_van', ngon_ngu?}` → `{noi_dung, tra_loi_con?:str (chứa link nếu có)}`
  - `tra_loi_binh_luan` `{bai_cua_nick:bool, bai, binh_luan:{tac_gia, chu}, san_pham_id?}` → `{noi_dung, can_hoi_chu:bool, cau_hoi?}`
    (can_hoi_chu → máy chủ tự ghi `hoi_dap` cho_ban)
  - `tra_loi_tin_nhan` `{hoi_thoai:{khach_ten, khach_link, tin:[{tu, noi_dung}]}, san_pham_id?}` → `{noi_dung, can_tra_loi_tay:bool, ly_do?, sdt?}`
  - `tra_loi_cau_hoi_nhom` `{nhom, cau_hoi:[...], san_pham_id}` → `{tra_loi:[...], bo_nhom:bool}`
  - `viet_bai` `{san_pham_id, noi_dang, yeu_cau?}` → `{noi_dung}`
  - `chon_nhom` `{ket_qua_tim:[{ten, link, thanh_vien, mo_ta}], san_pham_id}` → `{chon:[link...]}`
- `POST /may/ban-nhap` `{viec_id, loai, noi_dang, nhom?, link_goc?, bai_goc?, ly_do?, noi_dung, san_pham_id?, het_han_gio?}` → `{id}`.
- `GET /may/ban-nhap/lay?viec_id=&noi_dang=&san_pham=` → `{ban_nhap|null}` (nháp da_duyet, chưa gán hoặc gán đúng nick; giữ cho việc).
  `POST /may/ban-nhap/{id}/ket-qua` `{ok, link?, loi?}` → da_dang | loi.
- `GET /may/kho/lay?viec_id=` → `{bai|null}` (nền tảng + kho chung/theo_nick theo tham số việc), `GET /may/kho/tep/{id}/{luu}`,
  `POST /may/kho/{id}/ket-qua` `{ok, da_bam_dang, link?, loi?}`.
- `GET /may/nhom-fb?viec_id=` → nhóm của sản phẩm trong tham số việc, kèm vai của nick (chinh|tuong_tac|chua_gan) và `tinh_trang_vao`.
  `POST /may/nhom-fb` `{viec_id, link, ten?, tinh_trang?:'da_vao'|'cho_duyet'|'bi_tu_choi', lan_quet?:true, them_moi?:bool}`.
- `GET /may/da-tuong-tac?nick_id=&khoa=` / `POST /may/da-tuong-tac` `{khoa}` - trí nhớ chống lặp (bài đã bình luận, người đã
  nhắn...). `khoa` là chuỗi tự do, vd `fb_bl:<link bài>`, `fb_nt:<uid>`. Bảng `da_lam(nick_id, khoa, luc)`, có cả truy vấn
  "có nick nào trong đội đã làm khoá này chưa" (`?ca_doi=1`).
- `POST /may/hoi-thoai` `{viec_id, khach_ten, khach_link, tin:[{tu, noi_dung, luc?}], san_pham_id?, trang_thai?, sdt?}` →
  `{id, bot_duoc_tra_loi:bool}` (false khi chủ đang nhường/đã đánh dấu cần trả lời tay/spam).
- `GET /may/bai-doi-da-dang?viec_id=` → bài đội đã đăng trong nhóm/Threads 2-48 giờ qua (từ su_kien thành công `dang_nhom`/
  `dang_tuong` có link), trừ bài của chính nick, mỗi bài chưa quá 3 nick tương tác.

## 4. Worker (máy ở nhà)

### 4.1 Lõi (`minmin_worker.py`, `ngu_canh.py`)
- Đăng ký mẫu: mỗi tệp `ky_nang_<nen_tang>.py` khai báo `KICH_BAN = {"<id mẫu>": ham}`. Lõi nạp mọi
  `ky_nang_*.py` (bỏ tệp lỗi import, ghi log), gửi danh sách id trong nhịp. `ky_nang_fb.dang_bai` cũ vẫn phục vụ `fb_dang_bai`.
- Chạy song song tối đa `song_song` việc (mỗi việc một luồng, mỗi luồng `sync_playwright()` riêng). Một nick một việc.
- Tự cập nhật: nhịp trả `phien_ban_worker` lớn hơn `PHIEN_BAN` → tải `/may/ban-cap-nhat`, giải nén đè các tệp mã (giữ
  worker.json, worker.log), thoát mã 3 để `chay.bat` khởi động lại. Chỉ cập nhật khi không có việc đang chạy.
- `ham(nc: NguCanh) -> str` trả thông điệp tổng kết; raise `LoiKyNang(thong_diep, ma=None)` khi hỏng.

### 4.2 `NguCanh` (giao diện mà mọi tệp kỹ năng dùng - KHÔNG đổi chữ ký)
```python
class LoiKyNang(RuntimeError):  # ngu_canh.LoiKyNang; ky_nang_fb.LoiKyNang = cùng lớp
    def __init__(self, thong_diep: str, ma: str | None = None)   # ma: dang_xuat|checkpoint|captcha|qua_nhanh|het_bai|...

class NguCanh:
    page            # playwright Page (đã mở trong profile)
    ctx             # BrowserContext
    viec: dict      # nguyên việc
    ts: dict        # viec["tham_so"]["tham_so"]  (tham số mẫu đã kiểm)
    nen_tang: str
    chay_thu: bool
    che_do: str     # 'chay_thu'|'duyet_truoc'|'dang_luon' (mẫu không AI: 'dang_luon' trừ khi chay_thu)
    tay: Nguoi      # nguoi.Nguoi(page): nghi(a,b), bam(loc), go(text), luot(lan), di_toi(loc)
    def nhat_ky(self, s: str) -> None
    def su_kien(self, hanh_dong: str, ket_qua: str, chi_tiet: str = "", link: str = "", nhom: str = "",
                san_pham: str = "", ma: str = "") -> dict     # trả {con_lai, dung}; cập nhật bộ đếm
    def con_lai(self, hanh_dong: str) -> int                  # theo hạn mức đã biết
    def nen_dung(self) -> bool                                # đợt bị huỷ / hết hạn mức tổng
    def nghi_thao_tac(self) -> None                           # ngủ ngẫu nhiên trong nghi_giay
    def ai(self, muc_dich: str, du_lieu: dict, anh: list[bytes] = ()) -> dict   # raise LoiKyNang nếu AI lỗi
    def ban_nhap(self, **kw) -> int                           # POST /may/ban-nhap
    def lay_ban_nhap(self, noi_dang: str) -> dict | None
    def xong_ban_nhap(self, id: int, ok: bool, link: str = "", loi: str = "") -> None
    def lay_kho(self) -> dict | None     # bài kho; tệp đã tải sẵn: bai["tep_cuc_bo"] = [đường dẫn]
    def xong_kho(self, id: int, ok: bool, da_bam_dang: bool, link: str = "", loi: str = "") -> None
    def nhom_fb(self) -> list
    def bao_nhom(self, link: str, **kw) -> None
    def da_lam(self, khoa: str, ca_doi: bool = False) -> bool
    def ghi_da_lam(self, khoa: str) -> None
    def hoi_thoai(self, **kw) -> dict
    def bai_doi_da_dang(self) -> list
    def chup(self) -> bytes                                   # ảnh màn hình hiện tại
    def mo(self, url: str) -> None                            # goto chịu chuyển hướng (ky_nang_fb.mo_trang)
    def kiem_dang_nhap(self) -> None                          # raise LoiKyNang(..., ma='dang_xuat'|'checkpoint'|'captcha') theo nền tảng
```
Quy tắc cho mọi kỹ năng:
- Chọn phần tử theo vai trò + nhãn trợ năng (tiếng Việt và tiếng Anh), không theo class CSS.
- Chỉ báo `thanh_cong` khi ĐỌC LẠI trang thấy trạng thái đã đổi (nút đã thích, bình luận hiện, bài mới hiện).
- `chay_thu`: không bấm bất kỳ nút công khai nào (Đăng, Gửi, Bình luận, Thích, Tham gia, Chia sẻ). Được mở trang, đọc,
  cuộn, gọi AI, tạo nháp, báo sự kiện `thong_tin` "Chạy thử: sẽ ...".
- Trước mỗi thao tác bị đếm: `if nc.con_lai(hd) <= 0: break`. Sau mỗi thao tác: `nc.nghi_thao_tac()`.
- Gặp đăng xuất/checkpoint/captcha/"bạn đang làm quá nhanh" → raise `LoiKyNang(..., ma=...)` ngay.
- Gõ chữ luôn qua `nc.tay.go()` (từng chữ). Không dán.

### 4.3 Kỹ năng nội bộ (không có trong danh mục, máy chủ tạo)
- `dang_ban_nhap`: tham số `{ban_nhap_id, loai, noi_dang, link_goc, nhom, noi_dung, tep}` - đăng nháp đã duyệt
  (bình luận dưới `link_goc`, hoặc bài vào `nhom`/tường). Lõi FB làm `fb_*`, các nền tảng khác tự khai trong `KICH_BAN` của
  họ với khoá `dang_ban_nhap:<nen_tang>` (lõi chọn theo `noi_dang`).
- `fb_gui_tin`: `{khach_link, noi_dung, hoi_thoai_id}` gửi một tin Messenger chủ tự gõ.

## 5. Trang web (`apps/doi-social/web/`)
SPA thuần JS (không build), hash route, nền sáng, thẻ trắng bo 16px, nhấn gradient tím `#7c3aed → #6366f1`, chữ
Inter/system. Thanh bên trái cố định (thu gọn thành ngăn kéo trên điện thoại):
- **Tổng quan** `#/tong-quan`
- Nhóm **AI AGENTS**: Automation `#/automation` (tab Chọn mẫu · Lịch hẹn · nút + Chạy hàng loạt → `#/chay-hang-loat?mau=`),
  Nhật ký hoạt động `#/nhat-ky` (tab Hoạt động · Đợt chạy hàng loạt · Lịch sử chạy), Kho nội dung `#/kho` (Kho bài · Viết bài AI),
  Kho group FB `#/nhom-fb`, Duyệt nội dung `#/duyet`, Tin nhắn `#/tin-nhan` (huy hiệu số cần trả lời tay), Trợ lý AI `#/tro-ly`,
  Kiến thức cho Agent `#/kien-thuc`
- Nhóm **QUẢN LÝ**: Tài khoản `#/tai-khoan` (profile GPM, chỉ đọc + gắn nhãn nền tảng/tuổi), Giới hạn nick `#/gioi-han`
  (tab Chung · Theo nền tảng · Tuổi nick), Máy ở nhà `#/may` (ghép máy, tải Worker, trạng thái, mẫu máy hỗ trợ)
- Chân thanh bên: tên MinMin, phiên bản, nút sáng/tối (lưu localStorage, bọc try), link "Về MinMin" (/).
Mọi chữ tiếng Việt. Không em dash. Mẫu máy chưa hỗ trợ: thẻ mờ + nhãn "Máy ở nhà chưa hỗ trợ", nút Chạy vẫn cho tạo
đợt nhưng cảnh báo.

## 6. Telegram / chat MinMin
Plugin `system/plugins/doi-social` thêm tool: `social_tong_quan` (readonly), `social_ke_hoach` (full: tạo kế hoạch từ yêu cầu
tự do, gửi Telegram kèm nút Duyệt/Từ chối - KHÔNG tự chạy), `social_chay_mau` (full: tạo đợt chạy một mẫu cho các nick, AI
mặc định `chay_thu`). Vậy "đăng một bài thu hút lên fanpage đời sống" từ Telegram → kế hoạch → bố bấm Duyệt → chạy.

## 7. Giao diện giữa các module máy chủ (cố định)

`server/doi_social_ai.py` (thuần, async, không gọi mạng; `goi_ai` được tiêm):
```python
GoiAI = Callable[[str, list], Awaitable[str]]     # (prompt, đường dẫn ảnh) -> chữ AI trả
async def xu_ly_may(muc_dich: str, du_lieu: dict, anh: list, *, goi_ai: GoiAI, kien_thuc: dict | None) -> dict
async def viet_bai(kien_thuc: dict, noi_dang: str, so_ban: int, yeu_cau: str, *, goi_ai: GoiAI) -> list   # list[str]
async def viet_lai(ban_nhap: dict, kien_thuc: dict | None, yeu_cau: str, *, goi_ai: GoiAI) -> str
async def tro_ly(tin: str, lich_su: list, boi_canh: dict, *, goi_ai: GoiAI) -> dict   # {tra_loi, ke_hoach: {mo_ta, buoc:[{kich_ban, nick:[ids], tham_so, ghi_chu}]} | None}
def boc_json(s: str) -> dict | None
```
`kien_thuc` = `{id, loai, ten, mo_ta, gia, link, tu_khoa, giong_van, dan_rieng, tai_lieu:[{ten, noi_dung}], hoi_dap:[{hoi, dap}]}`.
`boi_canh` = `{mau:[{id, ten, nen_tang, mo_ta, tham_so:[key...], san_sang}], nick:[{id, ten, nhan}], kien_thuc:[{id, ten, loai}], tong_quan:{...}}`.
Kế hoạch trả về được máy chủ kiểm lại bằng `kiem_tham_so` + nick có thật trước khi lưu; bước sai bị bỏ kèm ghi chú.

`server/doi_social_v2.py` (kho, đồng bộ) phải có tối thiểu (plugin và main dùng):
```python
def tao_dot(*, kich_ban, nick, tham_so, ten="", song_song=1, chay_an=False, nguon="web", lich_id=None) -> dict
def tao_ke_hoach(*, mo_ta, buoc, nguon="web", chat_id="") -> dict
def duyet_ke_hoach(kid, dong_y: bool) -> dict          # đồng ý -> tạo đợt cho từng bước, trả kế hoạch kèm dot_ids
def lay_ke_hoach(kid) -> dict | None
def tong_quan(ngay: int = 14) -> dict
def ds_kien_thuc() -> list ; def lay_kien_thuc(kid, day_du=True) -> dict | None
def boi_canh_tro_ly() -> dict
```
`routes.doi_social.DoiSocialDeps` thêm: `goi_ai: GoiAI | None`, `thong_tin_ai: Callable[[], dict] | None` (→ `{engine, mo_hinh, nhin_anh, san_sang}`),
`bao_ke_hoach: Callable[[dict], Awaitable] | None` (gửi kế hoạch lên Telegram kèm nút `dsk:<id>:1|0`),
`bao_su_kien: Callable[[str, str], Awaitable] | None` (tiêu đề, nội dung → hòm thư + Telegram; dùng cho "đợt chạy xong", "nick bị đăng xuất", "N nháp chờ duyệt").
Hàm dùng chung trong `routes.doi_social`: `tao_dot_va_chay(**kw)` (tạo đợt + đánh thức máy), `duyet_ke_hoach_va_chay(kid, dong_y)`,
`async tro_ly_tra_loi(tin, phien, nguon='web', chat_id='') -> dict` (gọi AI, lưu lịch sử, lưu kế hoạch, báo Telegram nếu nguon=telegram).

## Chrome MinMin (26.10.301)

Ngoài Worker GPM, máy chạy MinMin có Worker Chromium tích hợp. Trang `#/chrome` tải Chromium,
tạo profile, bật/tắt Worker, mở cửa sổ trên desktop hoặc điều khiển qua ảnh màn hình trên VPS.
Dữ liệu nằm trong `STATE_DIR/social-chrome`; mỗi profile một thư mục riêng, không dùng profile
Chrome mặc định của người dùng. Cookie được giữ qua đóng trình duyệt và cập nhật MinMin.
Không tự nhập cookie/profile GPM; người dùng đăng nhập lại trong profile mới.

`server/social_browser.py` quản lý context, giới hạn 3 profile mở đồng thời, tự khởi động lại
Worker đã bật. Worker dùng `may_chrome.py` để lấy CDP qua API loopback. Các endpoint `/chrome/*`
được cổng đăng nhập/CSRF của main bảo vệ và kiểm mở khoá app. Endpoint `/may/chrome/*` cần token
máy tích hợp, IP loopback và tác vụ đang chạy thuộc đúng profile. Token lưu mã hoá, không trả
về UI. CDP chỉ nghe loopback, không đưa cổng điều khiển ra Internet.

Trong tác vụ, UI chỉ xem màn hình; không gõ/đóng profile đang chạy. Chạy ẩn có tác dụng với
Chrome tích hợp (desktop chuyển sang headless; VPS luôn headless). Worker GPM cũ vẫn độc lập.
Không có giả dấu vân tay hay đảm bảo vượt chặn tự động; người dùng tự đăng nhập, xử lý xác minh.

Kiểm chứng: `test_social_browser.py` chạy Chromium thật trên CI cả headless lẫn desktop qua
Xvfb, kiểm cookie bền, cách ly profile, nhập liệu/ảnh màn hình, khoá tác vụ, quyền máy/profile,
Worker CDP và đóng profile. Các trang/nội dung thử đều giả lập, không đăng lên tài khoản thật.
