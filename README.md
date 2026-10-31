# MinMin OS

MinMin OS là trợ lý AI tự chạy trên máy tính hoặc VPS của bạn. Kết nối dữ liệu cửa hàng, sử dụng skill và agent, lưu kiến thức trong bộ não riêng và chọn nhà cung cấp AI phù hợp với công việc.

**[Tiếng Việt](README.md) · [English](README.en.md)**

## Cài đặt

Chọn một trong ba cách dưới đây. Hướng dẫn từng bước: [Bắt đầu nhanh](QUICKSTART.md).

### PC Windows

1. Cài Python 3.12 và Node.js LTS từ website chính thức.
2. Bấm **Code → Download ZIP** tại [repo MinMin](https://github.com/haincbbg-coder/minminos), giải nén vào thư mục cố định.
3. Mở CMD ngay trong thư mục có `install.ps1`, chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

4. Mở [http://localhost:7777](http://localhost:7777).
5. Những lần sau chạy `start-minmin.bat`. Dừng bằng `stop-minmin.bat`.

Bộ cài tạo môi trường Python riêng, cài thư viện, thử cài các bộ não CLI và khởi động ứng dụng. Nếu cài thêm CLI sau đó, khởi động lại MinMin để nhận PATH mới.

### Hostinger Docker Manager

Vào **VPS → Docker Manager → Compose → URL**, dán:

```text
https://raw.githubusercontent.com/haincbbg-coder/minminos/main/docker-compose.minmin.hostinger.yml
```

Trong **Environment**, đặt:

```dotenv
DOMAIN_NAME=minmin.tenmiencuaban.com
MINMIN_ADMIN_USER=admin
MINMIN_ADMIN_PASSWORD=ThayBangMatKhauRieng
```

Trỏ DNS tên miền về VPS, bấm **Deploy**, rồi mở `https://<DOMAIN_NAME>`. Chưa có tên miền có thể vào tạm `http://<IP-VPS>:7777`. Dùng HTTPS trước khi nhập thông tin tài khoản dịch vụ.

Tùy chọn `MINMIN_AUTO_UPDATE=true` bật kiểm tra cập nhật mỗi ngày. Bỏ trống để cập nhật khi bạn chọn trong ứng dụng hoặc Redeploy.

### VPS Linux dùng Docker

VPS cần có Git, Docker và Docker Compose. Cài một bản MinMin mới:

```bash
git clone https://github.com/haincbbg-coder/minminos.git /opt/minminos
cd /opt/minminos
cp .env.minmin.example .env
nano .env
```

Đặt tài khoản quản trị và thay mật khẩu mẫu trong `.env`, sau đó chạy:

```bash
docker compose -f docker-compose.minmin.yml up -d --pull always
docker compose -f docker-compose.minmin.yml ps
```

Mở `http://<IP-VPS>:7777`. Chi tiết về tên miền, HTTPS, nhiều bản cài và cập nhật: [Hướng dẫn VPS](DEPLOY.md).

Nếu máy đã có một bản Docker đang chạy, cập nhật bằng **đúng file Compose của bản đó**. Không chuyển sang file khác khi chưa kiểm tra volume và sao lưu dữ liệu.

### Linux hoặc macOS chạy trực tiếp

Trong thư mục dự án:

```bash
chmod +x install.sh
./install.sh
```

Theo dõi kết quả bộ cài và mở `http://localhost:7777`.

## Thiết lập sau khi cài

1. Vào **Models / Bộ não AI** để đăng nhập nhà cung cấp hoặc nhập API key.
2. Vào **Kết nối** để thêm tài khoản Pancake POS, Google Sheets và các dịch vụ của bạn.
3. Kiểm tra **Skills** và **Agents**, chọn hoặc chỉnh theo công việc cửa hàng.
4. Cấu hình Telegram, lịch chạy và quyền thao tác khi cần.

Mỗi khách dùng tài khoản và dữ liệu riêng. Một số ứng dụng cần giấy phép kích hoạt riêng. Việc cài phần mềm không tự đăng nhập các dịch vụ hoặc bao gồm chi phí sử dụng AI.

## Năng lực của MinMin

- Trò chuyện, giọng nói và lựa chọn nhà cung cấp AI.
- Bộ nhớ, wiki và đồ thị tri thức từ dữ liệu của bạn.
- Skill, agent, workflow và công việc định kỳ.
- Kết nối bán hàng, báo cáo, lịch, email và công cụ bên ngoài.
- Quản lý tệp, phiên hội thoại, mức sử dụng và sao lưu.

Xem [mục lục hướng dẫn](docs/README.md) để tìm từng chức năng.

## Cập nhật

**Docker:** trong thư mục bản cài, chạy lệnh tương ứng với file đang dùng. Với bản mới theo hướng dẫn này:

```bash
docker compose -f docker-compose.minmin.yml up -d --pull always
```

**PC tải ZIP:** sao lưu bộ não, cấu hình và dữ liệu trước khi thay bản cài. Bản ZIP không mặc nhiên cập nhật được bằng Git. Tải bản mới vào thư mục riêng và kiểm tra dữ liệu trước khi bỏ bản cũ.

Sau cập nhật, nhấn **Ctrl + F5** trên giao diện. Không chạy `docker compose down -v` để cập nhật: tùy chọn `-v` xóa volume dữ liệu.

## Khi gặp lỗi

- Không mở được giao diện: kiểm tra server đang chạy và cổng 7777.
- Python hoặc Node.js không được nhận diện: mở CMD mới sau khi cài và kiểm tra PATH.
- Cài thư viện thất bại: tại thư mục MinMin, chạy `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Docker báo không có quyền tải ảnh: kiểm tra quyền của package `ghcr.io/haincbbg-coder/minminos`.
- Với Docker, xem nhật ký bằng `docker compose -f docker-compose.minmin.yml logs --tail=80`.
- Với PC, mở nhật ký `server/minmin.log`.

Không đăng công khai mật khẩu, API key, token hay bộ não của khách khi gửi ảnh hỗ trợ.

## Tài liệu và giấy phép

- [Bắt đầu nhanh](QUICKSTART.md)
- [Triển khai VPS và Hostinger](DEPLOY.md)
- [Hướng dẫn sử dụng](docs/README.md)
- [Giấy phép MIT và thông báo bản quyền](LICENSE)
