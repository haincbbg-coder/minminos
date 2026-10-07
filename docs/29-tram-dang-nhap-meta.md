# Trạm đăng nhập Meta

***Tiếng Việt** · [English](en/29-meta-login-relay.md)*

Trạm đăng nhập Meta cho phép người dùng MinMin bấm **Đăng nhập bằng Facebook** là xong, không phải tự tạo Facebook App, dán App ID, App Secret hay khai Redirect URI. Trang này dành cho **người vận hành trạm** (nhà phát hành MinMin). Người dùng thường không cần đọc: họ chỉ thấy thêm một nút trong hộp thoại kết nối Meta Ads và Facebook Trang.

## Cách nó chạy

1. Người dùng bấm **Đăng nhập bằng Facebook** trên trang Kết nối của MinMin.
2. Máy MinMin của họ gửi yêu cầu có ký số tới trạm. Trạm trả về một trang xác nhận.
3. Trang xác nhận ghi rõ địa chỉ máy MinMin sẽ nhận token và các quyền sẽ cấp. Người dùng bấm **Tiếp tục với Facebook**.
4. Facebook hỏi quyền, rồi trả mã về trạm. Trạm là nơi duy nhất giữ App Secret nên đổi mã lấy token dài hạn ở đây.
5. Trạm mã hoá token cho riêng máy đó, chuyển trình duyệt về máy MinMin. Máy nhận bản mã hoá, giải mã, lưu vào kết nối như mọi kết nối khác.
6. Khoảng 60 ngày sau, máy tự nhờ trạm gia hạn token.

Trạm không lưu token. Bản đã mã hoá nằm trong bộ nhớ tạm tối đa 5 phút rồi bị xoá. Nhưng token có đi qua bộ nhớ của trạm trong lúc đổi mã, và trang Chính sách nói rõ điều này. Người nào không muốn vẫn dùng đường tự tạo app như cũ.

## Dựng trạm (làm một lần)

### 1. Tạo Facebook App

1. Vào [developers.facebook.com/apps](https://developers.facebook.com/apps), bấm **Create App**, chọn loại **Business**, gắn vào Business Manager của công ty.
2. Thêm **Đăng nhập bằng Facebook** (hoặc **Facebook Login for Business**, xem mục 5) và **Marketing API**.
3. Ở phần cài đặt Đăng nhập bằng Facebook, ô **Valid OAuth Redirect URIs** điền đúng một dòng: `https://minmin.elaria.cloud/mt/ve` (thay bằng tên miền của bạn).
4. Vào **Cài đặt ứng dụng > Thông tin cơ bản**, điền:
   - **Miền ứng dụng**: `minmin.elaria.cloud`
   - **URL chính sách quyền riêng tư**: `https://minmin.elaria.cloud/mt/chinh-sach`
   - **URL điều khoản dịch vụ**: `https://minmin.elaria.cloud/mt/dieu-khoan`
   - **URL hướng dẫn xoá dữ liệu**: `https://minmin.elaria.cloud/mt/xoa-du-lieu`
   - Biểu tượng ứng dụng, danh mục, email liên hệ.
5. Vào **Cài đặt ứng dụng > Nâng cao**, để **Yêu cầu App Secret** (Require App Secret) ở **TẮT**. Lý do: máy của từng người dùng gọi Graph API trực tiếp bằng token, không có App Secret để tính `appsecret_proof`. Bật lên là mọi máy người dùng gọi API đều bị từ chối.

### 2. Bật trạm trên VPS

Thêm vào file `.env` cạnh `docker-compose.yml`:

```
JAVIS_META_TRAM_APP_ID=<App ID>
JAVIS_META_TRAM_APP_SECRET=<App Secret>
JAVIS_META_TRAM_GOC=https://minmin.elaria.cloud
JAVIS_META_TRAM_LIEN_HE=<email hỗ trợ>
```

Rồi chạy `docker compose up -d` để container nhận biến mới. Kiểm tra: mở `https://minmin.elaria.cloud/mt/thong-tin`, phải thấy `"bat": true`. Ba trang Chính sách, Điều khoản, Xoá dữ liệu phải mở được không cần đăng nhập.

### 3. Thử ở chế độ phát triển

Khi app chưa được duyệt, chỉ những tài khoản có vai trò trong app (Admin, Developer, Tester) mới đăng nhập được. Cách dùng thử:

1. Thêm tài khoản Facebook của mình (và vài người dùng tin cậy) làm **Tester** ở mục **Vai trò ứng dụng**.
2. Trên một máy MinMin bất kỳ, mở **Kết nối > Meta Ads**, bấm **Đăng nhập bằng Facebook**.
3. Hỏi MinMin số liệu quảng cáo để chắc chắn token chạy được.

Giai đoạn này cũng là lúc tích lượt gọi API: Meta đòi ít nhất 1.500 lượt gọi Marketing API trong 30 ngày, tỉ lệ lỗi dưới 10%, trước khi cho lên mức Standard Access.

### 4. Gửi Meta duyệt

1. **Xác minh doanh nghiệp** ở Business Manager (giấy phép kinh doanh, tên miền, số điện thoại).
2. Ở **Xét duyệt ứng dụng**, xin Quyền truy cập nâng cao cho: `ads_read`, `ads_management`, `business_management`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_manage_engagement`, `read_insights`. Chỉ xin quyền thật sự dùng: xin thừa là lý do bị từ chối thường gặp.
3. Mỗi quyền cần một đoạn mô tả cách dùng và một video quay màn hình: bấm Đăng nhập trên MinMin, qua trang xác nhận, chọn tài khoản, rồi MinMin đọc báo cáo quảng cáo hoặc đăng bài lên Trang.
4. Duyệt xong thì chuyển app sang **Live**, xin thêm **Ads Management Standard Access**.

### 5. Facebook Login for Business (nếu Meta yêu cầu)

Nếu app doanh nghiệp không còn dùng được Đăng nhập bằng Facebook bản thường, tạo một **cấu hình** trong Facebook Login for Business (chọn loại token người dùng, chọn các quyền ở trên), rồi điền mã cấu hình vào `.env`:

```
JAVIS_META_TRAM_CONFIG_ID=<mã cấu hình>
```

Trạm sẽ gửi `config_id` thay cho danh sách quyền.

## Các biến

| Biến | Máy nào | Ý nghĩa |
|---|---|---|
| `JAVIS_META_TRAM_APP_ID` | trạm | App ID của Facebook App |
| `JAVIS_META_TRAM_APP_SECRET` | trạm | App Secret. Có cả hai biến này thì máy là trạm |
| `JAVIS_META_TRAM_GOC` | trạm | Địa chỉ công khai của trạm, phải khớp Redirect URI đã khai với Meta |
| `JAVIS_META_TRAM_LIEN_HE` | trạm | Email hỗ trợ, hiện trên ba trang bắt buộc |
| `JAVIS_META_TRAM_SCOPES` | trạm | Giới hạn các quyền trạm cho xin, ngăn bằng dấu phẩy. Mặc định 8 quyền ở trên |
| `JAVIS_META_TRAM_CONFIG_ID` | trạm | Mã cấu hình Facebook Login for Business |
| `JAVIS_META_TRAM_CHU` | trạm | Tên đơn vị vận hành, hiện trên trang Chính sách. Mặc định `MinMin OS` |
| `JAVIS_META_TRAM` | máy người dùng | Địa chỉ trạm. Mặc định `https://minmin.elaria.cloud`. Đặt `off` để tắt đường này |

## Bảo mật

- Mọi yêu cầu từ máy MinMin tới trạm đều ký bằng khoá danh tính của máy. Chỉ đúng máy mở phiên mới nhận được token của phiên đó.
- Token được mã hoá riêng cho máy nhận bằng khoá tạm sinh mỗi lần đăng nhập. Lộ đường dẫn qua lịch sử trình duyệt cũng không đọc được token.
- Trình duyệt phải đi qua trang xác nhận và mang cookie do trang đó đặt. Kẻ xấu gửi thẳng link Facebook cho người khác thì trạm từ chối, nên token của nạn nhân không thể chảy về máy kẻ xấu.
- Trạm chỉ chuyển hướng về `/connect/oauth/callback` của một địa chỉ https công khai hoặc `http://localhost`.
- Mọi đường `/mt/` có giới hạn tần suất theo địa chỉ IP.

## Giới hạn phải biết

- **Hạn mức gọi API tính chung cho cả app.** Mọi người dùng chia nhau một hạn mức. Đông người dùng thì phải lên Standard Access và theo dõi lỗi giới hạn.
- **Trạm sập là không ai đăng nhập mới hay gia hạn được.** Token đang có vẫn chạy tới khi hết hạn khoảng 60 ngày.
- **Meta có thể khoá app** nếu một người dùng lạm dụng (spam bài, lạm dụng quảng cáo). Điều khoản của trạm cấm việc này và trạm có thể chặn máy vi phạm, nhưng rủi ro chung một app là có thật.

## Liên quan

- [Kết nối & số liệu kinh doanh](09-mcp-va-so-lieu.md): đường tự tạo app vẫn còn nguyên.
- [Cấu hình .env](16-cau-hinh-env.md): các biến `JAVIS_META_TRAM_*` đặt trong `.env` cạnh `docker-compose.yml`.
