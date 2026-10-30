# Đội Social - Fanpage qua Graph API (26.10.194)

Hợp đồng chung cho máy chủ và giao diện. Học theo hành vi quan sát được ở LoHa Page (bản demo
lohapage.com/demo, 21/10/2026), dựng lại từ đầu, KHÔNG chép mã hay chữ của họ.

## 0. Vì sao tách lớp này

Phần Đội Social cũ lái trình duyệt GPM ở máy nhà (nick cá nhân). Fanpage thì khác: đăng bằng
**Graph API với token của Trang**, chạy ngay trên VPS, không cần máy nhà, nick có chết thì Trang vẫn
đăng được. Nguồn token:

1. Kết nối OAuth "Facebook Trang (tự tạo app)" (connector `facebook-pages`, đã có ở trang Kết nối).
   Không lưu token, mỗi lần lấy qua `oauth_mcp.auth_headers(cid)` rồi `/me/accounts`.
2. Token dán tay ở tab **Token** (user token hoặc page token). Lưu trong SQLite của Đội Social
   (kho cục bộ của chủ, không gửi đi đâu). Trả ra API luôn che: `EAAB…xyz9` (6 đầu + 4 cuối).

Mọi thao tác trên một Trang dùng page token của chính Trang đó. Một Trang có nhiều nguồn token thì
xoay vòng ("pool"): token lỗi thì thử token kế tiếp và đánh dấu token kia lỗi.

## 1. Luật an toàn (bắt buộc)

- Bài tạo hàng loạt / từ kênh nguồn / từ AI mặc định vào **`cho_duyet`**. Chỉ khi chủ tắt
  `duyet_truoc` trong cấu hình nhóm/Trang thì bài mới vào thẳng `cho_dang`.
- Quy tắc tự trả lời bình luận mặc định `tu_gui = false`: tạo câu trả lời ở trạng thái
  `cho_duyet`, chủ bấm gửi. Chủ bật `tu_gui` cho từng quy tắc thì mới tự gửi.
- Nút **Dừng mọi tự động** (cài đặt `dung_tu_dong`) chặn ngay: tự trả lời, tự ẩn, đăng theo lịch,
  bình luận sau đăng, quét kênh. Bài đã hẹn sẵn trên Facebook (`da_hen_fb`) không rút được bằng
  nút này (ghi rõ trên giao diện).
- Không bao giờ trả token thật ra API/giao diện/log.
- Test không gọi mạng: lớp gọi Graph nhận `http` (hàm async giả) tiêm vào.

## 2. Tệp

- `server/doi_social_fanpage.py` - kho (SQLite chung `ds._db()`), thuần đồng bộ, không mạng:
  bảng, CRUD, spin, lịch, chọn nội dung từ kho, quy tắc bình luận, cảnh báo, số liệu tổng quan.
- `server/doi_social_fanpage_graph.py` - gọi Graph (async, httpx), nguồn token, đăng bài các loại,
  bình luận, ẩn, insights, IG, đổi info, kênh nguồn (yt-dlp), và `nhip()` cho vòng nền.
- `server/routes/doi_social.py` - thêm endpoint `/doi-social/fp/...` (cookie như các endpoint web
  khác) và gọi `fpg.nhip()` trong vòng nền.
- `apps/doi-social/web/views/fp-*.js` + mục "Fanpage (API)" trên thanh bên.
- Tests: `tests/python/test_doi_social_fanpage.py`, cập nhật `tests/js/test_doi_social_web.mjs`
  và `route_table.json` nếu repo có kiểm bảng route.

Thư mục tệp: `ds._goc / "fanpage"` (`media/`, `kenh/<id>/`).

## 3. Bảng (CREATE IF NOT EXISTS trong `tao_bang`, gọi từ `doi_social_v2.tao_bang`)

```
fp_token(id INTEGER PK, nhan TEXT, loai TEXT  -- 'ket_noi' | 'nguoi_dung' | 'trang'
         ket_noi_id TEXT DEFAULT '', token TEXT DEFAULT '', trang_thai TEXT DEFAULT 'chua_kiem',
         -- 'tot' | 'loi' | 'het_han' | 'chua_kiem'
         het_han REAL, kiem_luc REAL, loi TEXT DEFAULT '', so_trang INTEGER DEFAULT 0,
         so_bai_dang INTEGER DEFAULT 0, tao_luc REAL)
fp_trang(id TEXT PK, ten TEXT, anh TEXT, danh_muc TEXT, link TEXT, ig_id TEXT DEFAULT '',
         ig_ten TEXT DEFAULT '', nhom_id INTEGER, cau_hinh TEXT DEFAULT '{}', nguon TEXT DEFAULT '[]',
         -- [token_id...] có quyền với Trang
         quyen TEXT DEFAULT '[]', nguoi_theo_doi INTEGER DEFAULT 0, bat INTEGER DEFAULT 1,
         cap_nhat REAL, loi TEXT DEFAULT '')
fp_nhom(id INTEGER PK, ten TEXT, mo_ta TEXT DEFAULT '', cau_hinh TEXT DEFAULT '{}', tao_luc REAL)
fp_kho(id INTEGER PK, ten TEXT, loai TEXT  -- 'noi_dung' | 'binh_luan' | 'link' | 'tieu_su'
       che_do TEXT DEFAULT 'ngau_nhien'  -- 'ngau_nhien' | 'stt' | 'lan_luot'
       muc TEXT DEFAULT '[]', gan TEXT DEFAULT '{}', -- kho link: {"noi_dung":[id], "binh_luan":[id]}
       mau_link TEXT DEFAULT '', con_tro INTEGER DEFAULT 0, tao_luc REAL)
fp_bai(id INTEGER PK, trang_id TEXT, nhom_id INTEGER, loai TEXT,
       -- 'chu' | 'anh' | 'album' | 'video' | 'reel' | 'story'
       noi_dung TEXT DEFAULT '', media TEXT DEFAULT '[]', link TEXT DEFAULT '',
       binh_luan TEXT DEFAULT '', story INTEGER DEFAULT 0, ig INTEGER DEFAULT 0,
       hen_luc REAL, cach_hen TEXT DEFAULT 'tool',  -- 'tool' | 'fb'
       trang_thai TEXT,  -- 'cho_duyet','cho_dang','da_hen_fb','dang_dang','da_dang','loi','bo'
       post_id TEXT DEFAULT '', url TEXT DEFAULT '', loi TEXT DEFAULT '', so_lan_thu INTEGER DEFAULT 0,
       bl_tt TEXT DEFAULT '',   -- '' | 'cho' | 'xong' | 'loi'
       story_tt TEXT DEFAULT '', ig_tt TEXT DEFAULT '', ig_media_id TEXT DEFAULT '',
       nguon TEXT DEFAULT 'tay',  -- 'tay' | 'kho' | 'kenh' | 'ai' | 'thu_muc'
       khoa_trung TEXT DEFAULT '', so_lieu TEXT DEFAULT '{}', tao_luc REAL, dang_luc REAL)
fp_binh_luan(id TEXT PK, trang_id TEXT, post_id TEXT, cha_id TEXT DEFAULT '', tu_id TEXT, tu_ten TEXT,
       noi_dung TEXT, luc REAL, la_cua_trang INTEGER DEFAULT 0, an INTEGER DEFAULT 0,
       trang_thai TEXT DEFAULT 'moi', -- 'moi','cho_duyet','cho_gui','dang_gui','da_tra_loi','da_an','bo_qua','loi'
       tra_loi TEXT DEFAULT '', quy_tac_id INTEGER, loi TEXT DEFAULT '', cap_nhat REAL)
fp_quy_tac(id INTEGER PK, ten TEXT, pham_vi TEXT DEFAULT '{}', -- {"nhom":[id], "trang":[id]} rỗng = mọi Trang
       tu_khoa TEXT DEFAULT '[]', -- rỗng = mọi bình luận của khách
       hanh_dong TEXT DEFAULT 'tra_loi', -- 'tra_loi' | 'tra_loi_ai' | 'an' | 'an_va_tra_loi'
       mau TEXT DEFAULT '[]',  -- câu trả lời, có spin, chọn ngẫu nhiên
       tu_gui INTEGER DEFAULT 0, bat INTEGER DEFAULT 1, uu_tien INTEGER DEFAULT 0, tao_luc REAL)
fp_kenh(id INTEGER PK, nen_tang TEXT, link TEXT, ten TEXT DEFAULT '', trang_ids TEXT DEFAULT '[]',
       nhom_id INTEGER, chia TEXT DEFAULT 'xoay', -- 'xoay' (mỗi video 1 Trang) | 'tat_ca'
       loai_bai TEXT DEFAULT 'reel', theo_doi INTEGER DEFAULT 1, chu_ky_gio INTEGER DEFAULT 6,
       toi_da_moi_lan INTEGER DEFAULT 5, lan_quet REAL, so_video INTEGER DEFAULT 0,
       trang_thai TEXT DEFAULT 'cho', loi TEXT DEFAULT '', tao_luc REAL)
fp_kenh_video(kenh_id INTEGER, ma TEXT, tieu_de TEXT, tep TEXT DEFAULT '', luc REAL,
       trang_thai TEXT DEFAULT 'da_tai', PRIMARY KEY(kenh_id, ma))
fp_so_lieu(trang_id TEXT, ngay TEXT, nguoi_theo_doi INTEGER, tiep_can INTEGER, tuong_tac INTEGER,
       luot_xem INTEGER, PRIMARY KEY(trang_id, ngay))
fp_canh_bao(id INTEGER PK, luc REAL, muc TEXT, ma TEXT, doi_tuong TEXT, tieu_de TEXT,
       chi_tiet TEXT, cach_sua TEXT, toi TEXT, het_luc REAL)
fp_nhat_ky(id INTEGER PK, luc REAL, loai TEXT, trang_id TEXT, bai_id INTEGER, ket_qua TEXT, chi_tiet TEXT)
```
Cài đặt chung trong `cai_dat` khoá `fp_cai_dat`:
`{"dung_tu_dong": false, "xoa_tep_sau_ngay": 7, "bao_moi_bai": false, "cho_dang_trung": false,
  "luong": 3, "ig_toi_da_24h": 50}`.

## 4. Cấu hình nhóm / Trang (`cau_hinh`, Trang kế thừa nhóm, nhóm kế thừa mặc định)

```
{"lich": {"che_do": "gio" | "chu_ky" | "tat", "gio": ["09:00","12:00","18:00"], "moi_gio": 4,
          "tu": "08:00", "den": "22:00", "lech_phut": 30, "trai_phut": 0, "cach": "tool" | "fb"},
 "kho_noi_dung": null, "kho_binh_luan": null, "kho_tieu_su": null,
 "binh_luan_sau_dang": false, "story": false, "ig_dong_bo": false,
 "tu_an": false, "tu_tra_loi": false, "chia_video": "mot_trang" | "tat_ca",
 "duyet_truoc": true}
```
`hieu_luc(trang)` = gộp sâu mặc định ← nhóm ← Trang (khoá có giá trị `null` ở Trang = theo nhóm).
Trang trả về kèm `cau_hinh_hieu_luc` và `nguon_cau_hinh` ('trang'|'nhom'|'mac_dinh') của mục lịch.

## 5. Thuật toán

- **Spin**: `{a|b|{c|d}}` lồng nhau, chọn ngẫu nhiên (hàm nhận `rnd` để test cố định).
  `{{` `}}` là ngoặc chữ thật. Biến: `{ten_trang}`, `{ngay}`, `{ten_tep}`.
- **Chọn từ kho**: `ngau_nhien` (random), `lan_luot` (con_tro tăng), `stt` (số lấy từ tên tệp media,
  vd `12.mp4`, `phim_12.jpg`, `tap-012.mp4` → 12 → phần tử thứ 12, đếm từ 1; không có số thì lần lượt).
- **Kho link**: kho link gắn với kho nội dung → nối `\n` + link vào cuối caption; gắn với kho
  bình luận → nối vào bình luận. `mau_link` dạng `https://phim.sbs/article/{ten_tep}` dựng link từ
  tên tệp (bỏ dấu, chữ thường, khoảng trắng thành `-`, bỏ đuôi). Có endpoint thử.
- **Lịch** `tinh_lich(cau_hinh_lich, so, bat_dau, da_co: [ts], chi_so_trang, rnd)`:
  - `gio`: lần lượt các ngày từ `bat_dau`, mỗi khung giờ + lệch ngẫu nhiên ±`lech_phut` +
    `chi_so_trang * trai_phut`; bỏ khung đã qua (< bat_dau + 2 phút) và khung đã có bài của Trang đó
    (cách < 20 phút).
  - `chu_ky`: mỗi `moi_gio` giờ trong khung `tu`-`den`, bắt đầu từ mốc tròn kế tiếp.
  - Luôn kẹp trong `tu`-`den` (nếu tu < den). `tat` → không tự xếp (hen_luc = None, đăng tay).
  - Giờ theo múi `localefmt.tz()` (như phần còn lại của Đội Social).
- **Cách hẹn**: `fb` và hen_luc trong (now+11 phút, now+29 ngày) → gửi Facebook kèm
  `published=false&scheduled_publish_time`, trạng thái `da_hen_fb`. Còn lại `tool` (vòng nền đăng
  khi tới giờ). Story, Reels và album luôn `tool`.
- **Chống trùng**: `khoa_trung` = sha1(trang_id + loai + noi_dung chuẩn hoá + tên tệp media). Có
  bài cùng khoá chưa `bo` thì không tạo nữa, trừ khi `cho_dang_trung`.

## 6. Graph (`doi_social_fanpage_graph.py`)

GRAPH = `https://graph.facebook.com/v26.0`, video `https://graph-video.facebook.com/v26.0`.
`http` tiêm được: `async http(method, url, params=None, data=None, files=None) -> dict`.

- Nguồn token: `nguon_token()` = các kết nối `facebook-pages` (qua mcp_store/oauth_mcp, import lười)
  + `fp_token` dán tay. `dong_bo_trang()` gọi `/me/accounts?fields=id,name,category,link,tasks,
  access_token,picture{url},followers_count,fan_count,instagram_business_account{id,username}`
  cho từng user token, `/me?fields=id,name,...` cho page token; ghi `fp_trang` (giữ nhom_id,
  cau_hinh, bat). Page token giữ TRONG BỘ NHỚ (dict, TTL 50 phút) không ghi đĩa (trừ token dán tay
  vốn đã lưu). `kiem_token(id)` gọi `/debug_token` nếu có app token, không thì `/me` và đọc
  `expires_at` từ debug khi được; cập nhật trang_thai/het_han/loi.
- `token_trang(trang_id)` → [(token_id, page_token)] theo thứ tự tốt trước.
- Đăng:
  - `chu`: POST `/{page}/feed` {message, link?}
  - `anh`: POST `/{page}/photos` multipart `source` + `message`
  - `album`: mỗi ảnh POST `/{page}/photos` `published=false` → `/{page}/feed`
    `attached_media[i]={"media_fbid": id}`
  - `video`: POST graph-video `/{page}/videos` multipart `source` + `description`
  - `reel`: `/{page}/video_reels` upload_phase=start → POST `https://rupload.facebook.com/video-upload/v26.0/{video_id}`
    (headers `Authorization: OAuth <token>`, `offset: 0`, `file_size`) → upload_phase=finish
    `video_state=PUBLISHED` `description`. Có thể dùng lại `up_bai.dang_reel` nếu hợp.
  - `story`: ảnh → POST `/{page}/photos` published=false rồi `/{page}/photo_stories` {photo_id};
    video → `/{page}/video_stories` start/upload/finish.
  - Bình luận sau đăng: POST `/{post_id}/comments` {message}. Story kèm: đăng thêm một story từ
    media đầu tiên khi `story=1`.
  - IG (`ig=1`, Trang có ig_id): `/{ig_id}/media` (image_url | video_url + media_type REELS |
    STORIES, caption) → chờ `status_code=FINISHED` → `/{ig_id}/media_publish`. Cần URL công khai:
    `GET /doi-social/fp/cong-khai/{ma}` (không cookie) phục vụ tệp media theo mã HMAC có hạn 2 giờ;
    gốc URL công khai lấy từ yêu cầu web gần nhất (cài đặt `fp_goc_cong_khai`). Đếm 24h theo
    `ig_toi_da_24h`.
- Bình luận: `quet_binh_luan(trang_id)` đọc 15 bài mới nhất
  `/{page}/feed?fields=id,created_time,comments.limit(50).order(reverse_chronological){id,from,message,created_time,parent{id},is_hidden}`;
  ghi `fp_binh_luan` (la_cua_trang khi from.id == trang_id). `tra_loi(cid, chu)` POST
  `/{cid}/comments`; `an(cid, True|False)` POST `/{cid}` {is_hidden}.
- Insights (cố gắng hết sức, metric nào lỗi thì bỏ qua): Trang `followers_count,fan_count` +
  `/{page}/insights?metric=page_total_media_view_unique,page_post_engagements,page_media_view&period=day&date_preset=yesterday (26.10.311: Meta bỏ page_impressions*, ghi vào dòng hôm qua)`;
  bài `reactions.summary(true),comments.summary(true),shares` +
  `/{post}/insights?metric=post_total_media_view_unique,post_clicks` → `fp_bai.so_lieu`, `fp_so_lieu` theo ngày.
- Đổi info: tiểu sử POST `/{page}` {about}; ảnh đại diện POST `/{page}/picture` multipart `source`;
  ảnh bìa: POST `/{page}/photos` published=false → POST `/{page}` {cover: photo_id}.
- Kênh nguồn: `yt_dlp` (đã có trong image, xem `up_bai.tai_video`). Liệt kê kênh `extract_flat`,
  lấy video mới chưa có trong `fp_kenh_video`, tải tối đa `toi_da_moi_lan` vào `fanpage/kenh/<id>/`,
  tạo bài (`nguon='kenh'`, loai theo kênh, caption = tiêu đề video spin qua kho nội dung của nhóm
  nếu có) cho Trang theo `chia`, xếp lịch theo cấu hình hiệu lực.
- `nhip(deps)` (vòng nền 30s, có khoá chống chạy chồng): nếu không `dung_tu_dong`:
  đăng bài `cho_dang` tới giờ (tối đa `luong` bài/nhịp), bình luận sau đăng (đợi 60s sau khi đăng),
  gửi bình luận `cho_gui`; mỗi 10 phút: quét bình luận các Trang có `tu_an`/`tu_tra_loi` + áp quy
  tắc, tự kiểm lỗi; mỗi giờ: kênh tới hạn; mỗi 6 giờ: insights; mỗi ngày: dọn tệp đã đăng quá
  `xoa_tep_sau_ngay`. Lỗi tạm (mạng, 5xx, code 1/2/4/17/32/613) thử lại tối đa 3 lần cách 10 phút;
  lỗi quyền (#200, #10, 190) → `loi` ngay + cảnh báo.

## 7. Cảnh báo lỗi (`kiem_loi()` → danh sách; lưu lịch sử khi xuất hiện / hết)

Mỗi mục: `{muc: 'chan'|'nang'|'nhac', ma, doi_tuong, tieu_de, chi_tiet, cach_sua, toi}`
(`toi` là đường dẫn hash trong app, vd `#/fp-trang?tab=token`). Ít nhất:
- chan: chưa có nguồn token nào; mọi token lỗi; Trang mất quyền đăng (tasks không có CREATE_CONTENT).
- nang: token hết hạn trong 7 ngày; bài lỗi 24h qua (gộp theo mã lỗi, #200 → cách sửa "nối lại
  kết nối và tick quyền pages_manage_posts"); Trang có lịch mà hết bài chờ và kho nội dung rỗng;
  kênh nguồn lỗi; máy chủ thiếu yt-dlp khi có kênh; IG chạm hạn 24h.
- nhac: Trang chưa thuộc nhóm và chưa có lịch; kho trống đang được gắn; hàng chờ của Trang hết
  trong 24h tới; đang bật Dừng mọi tự động.

## 8. API (mọi endpoint web trả `{"ok": true, ...}` hoặc `{"ok": false, "error"}`)

```
GET  /doi-social/fp/tong-quan -> {trang:{tong,co_lich,loi}, bai:{tong,da_dang,cho_duyet,cho_dang,da_hen_fb,loi},
        nguoi_theo_doi, tiep_can_7, tuong_tac_7, xu_huong:[{ngay, da_dang, tiep_can}],
        top_trang:[{id,ten,anh,da_dang,tuong_tac}], hoat_dong:[nhat_ky 20 dòng], canh_bao:{chan,nang,nhac},
        ig:{tai_khoan, da_dang_24h}, nguon_token, dung_tu_dong}
GET  /doi-social/fp/token -> {muc:[{id,nhan,loai,che,trang_thai,het_han,kiem_luc,loi,so_trang,so_bai_dang}]}
        (kết nối OAuth hiện như loai 'ket_noi', id dạng 'kn:<cid>')
POST /doi-social/fp/token {nhan, token} ; POST /doi-social/fp/token/{id}/kiem ; DELETE /doi-social/fp/token/{id}
POST /doi-social/fp/trang/dong-bo -> {so, moi, loi:[...]}
GET  /doi-social/fp/trang?nhom=&q=&sap_xep=ten|da_dang -> {muc:[{id,ten,anh,link,danh_muc,ig_id,ig_ten,nhom_id,nhom_ten,
        cau_hinh, cau_hinh_hieu_luc, nguon_cau_hinh, so_token, quyen, nguoi_theo_doi, bat,
        dem:{da_dang, cho, loi}, bai_ke:ts|null}], nhom:[{id,ten,so}], chua_nhom}
PATCH /doi-social/fp/trang/{id} {nhom_id?, cau_hinh?, bat?}
POST /doi-social/fp/trang/hanh-dong {ids, hanh_dong, ...}
        hanh_dong: 'gan_nhom' {nhom_id|null} | 'gan_cau_hinh' {cau_hinh} | 'doi_tieu_su' {kho_id | chu}
                   | 'doi_anh' {tep} | 'doi_bia' {tep} | 'bat' | 'tat'  -> {ok, so, loi:[{id,loi}]}
GET/POST /doi-social/fp/nhom ; PATCH/DELETE /doi-social/fp/nhom/{id}   (nhom: {id,ten,mo_ta,cau_hinh,so_trang,trang:[...]})
GET  /doi-social/fp/kho?loai= -> {muc:[{id,ten,loai,che_do,so,muc?,gan,mau_link}]}  (muc đầy đủ khi GET /kho/{id})
POST /doi-social/fp/kho ; GET/PATCH/DELETE /doi-social/fp/kho/{id} ; POST /doi-social/fp/kho/{id}/nhap {chu} (mỗi dòng 1 mục; nội dung
        nhiều dòng phân cách bằng dòng '---')
POST /doi-social/fp/thu-spin {mau, ten_tep?} -> {mau_thu:[5 kết quả]} ; POST /doi-social/fp/thu-link {mau_link, ten_tep} -> {link}
POST /doi-social/fp/lich/xem-truoc {cau_hinh_lich | trang_id, so} -> {gio:[ts]}
POST /doi-social/fp/media (multipart, nhiều tệp `tep`) -> {muc:[{tep, ten, loai:'anh'|'video', dai}]}
GET  /doi-social/fp/media/{tep}  (xem lại, cookie)
GET  /doi-social/fp/bai?trang_thai=&trang=&nhom=&loai=&tu=&den=&q=&sap_xep=moi|hen|tuong_tac&trang_so=1&moi_trang=50
        -> {muc:[{id,trang_id,trang_ten,trang_anh,loai,noi_dung,media,link,binh_luan,story,ig,hen_luc,cach_hen,trang_thai,
        post_id,url,loi,bl_tt,story_tt,ig_tt,nguon,so_lieu,tao_luc,dang_luc}], tong, dem:{trang_thai: so}}
POST /doi-social/fp/bai/tao {trang_ids | nhom_id, loai, noi_dung: [chuỗi] | kho_id, media: [[tep...]] | [tep],
        chia: 'mot_trang'|'tat_ca', binh_luan?: chuỗi | kho_binh_luan_id, story?, ig?, hen: 'tu_dong'|'ngay'|ts,
        chay_thu?: bool} -> {so, muc:[bai], bo_trung, xem_truoc (khi chay_thu: không ghi)}
        Ghép: mỗi "đơn vị" = 1 media (hoặc 1 nhóm ảnh với album) hoặc 1 dòng nội dung; mot_trang: chia
        xoay vòng các đơn vị cho các Trang; tat_ca: mỗi Trang nhận đủ.
PATCH /doi-social/fp/bai/{id} {noi_dung?, hen_luc?, binh_luan?, link?}
POST /doi-social/fp/bai/hanh-dong {ids, hanh_dong: 'duyet'|'bo'|'dang_ngay'|'thu_lai'|'xoa'|'xep_lai_lich'} -> {so}
POST /doi-social/fp/bai/{id}/kiem-tra -> {ok, buoc:[{ten, ok, chi_tiet}]}  (không đăng: kiểm token, quyền, tệp, giờ)
GET  /doi-social/fp/bai/xuat.csv?...  (cùng bộ lọc)
GET  /doi-social/fp/binh-luan?trang=&trang_thai=&chi_khach=1&q=&tu=&trang_so= -> {muc:[{...binh_luan, trang_ten}], tong,
        hom_nay:{da_tra_loi, cho_gui, cho_duyet, loi}, quet_luc}
POST /doi-social/fp/binh-luan/quet {trang?} -> {so_moi}
POST /doi-social/fp/binh-luan/hanh-dong {ids, hanh_dong: 'tra_loi' {chu} | 'gui' | 'an' | 'hien' | 'bo_qua' | 'ai_soan'}
GET/POST /doi-social/fp/quy-tac ; PATCH/DELETE /doi-social/fp/quy-tac/{id}
POST /doi-social/fp/tu-dong {dung: bool}
GET  /doi-social/fp/bao-cao?trang=&ngay=7 -> {trang:[{id,ten,anh,nguoi_theo_doi,tang_24h,tiep_can,tuong_tac,luot_xem}],
        bai:[{id,trang_ten,noi_dung,url,dang_luc,so_lieu}], chuoi:[{ngay,nguoi_theo_doi,tiep_can,tuong_tac}]}
POST /doi-social/fp/bao-cao/cap-nhat
GET  /doi-social/fp/canh-bao -> {muc:[...], dem:{chan,nang,nhac}, kiem_luc} ; POST /doi-social/fp/canh-bao/kiem
GET  /doi-social/fp/canh-bao/lich-su ; GET /doi-social/fp/canh-bao/xuat (text/plain chẩn đoán, KHÔNG token)
GET/POST /doi-social/fp/kenh ; PATCH/DELETE /doi-social/fp/kenh/{id} ; POST /doi-social/fp/kenh/{id}/quet
        kenh: {id,nen_tang,link,ten,trang_ids,trang_ten,nhom_id,chia,loai_bai,theo_doi,chu_ky_gio,toi_da_moi_lan,
               lan_quet,so_video,trang_thai,loi, co_yt_dlp}
GET  /doi-social/fp/instagram -> {muc:[{trang_id,trang_ten,ig_id,ig_ten,da_dang_24h,toi_da}]}
GET/POST /doi-social/fp/cai-dat
GET  /doi-social/fp/cong-khai/{ma}   (KHÔNG cookie, mã HMAC có hạn)
```

## 9. Giao diện (thanh bên, nhóm "Fanpage (API)")

- `#/fp-tong-quan` Tổng quan Fanpage: thẻ số + sparkline, hoạt động gần đây, top Trang, cảnh báo.
- `#/fp-trang` Trang & Nhóm: tab Trang (lọc nhóm, chọn nhiều + kéo chọn, Hành động), tab Nhóm
  (thẻ nhóm, sửa cấu hình lịch/kho/công tắc, xem trước giờ đăng), tab Token.
- `#/fp-bai` Bài đăng: bộ lọc, bảng, chọn nhiều duyệt/bỏ/đăng ngay/xuất CSV; nút "Tạo bài hàng loạt"
  (chọn Trang/nhóm, loại, tải tệp, nội dung hoặc kho, chia, bình luận, story, IG, hẹn) có Xem trước.
- `#/fp-kho` Kho nội dung: kho Nội dung / Bình luận / Link / Tiểu sử, cú pháp spin, thử spin, thử link.
- `#/fp-binh-luan` Bình luận: hộp gộp, quét ngay, trả lời/ẩn/gửi, AI soạn, quy tắc tự động,
  Dừng mọi tự động.
- `#/fp-kenh` Kênh nguồn.
- `#/fp-bao-cao` Báo cáo + `#/fp-canh-bao` Cảnh báo lỗi (Cách sửa, Tới chỗ sửa, lịch sử, xuất chẩn đoán).
- Tổng quan Đội Social hiện thêm thẻ nhỏ Fanpage và số cảnh báo chặn đứng.
