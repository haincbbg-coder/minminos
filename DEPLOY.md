# Cài MinMin OS trên VPS

[Tiếng Việt](DEPLOY.md) · [English](DEPLOY.en.md)

Hướng dẫn dành cho bản cài MinMin mới. PC Windows xem [Bắt đầu nhanh](QUICKSTART.md). Máy đang có dữ liệu cần sao lưu và giữ đúng file Compose đang dùng trước khi cập nhật.

## Chuẩn bị

- VPS Linux có Git, Docker Engine và Docker Compose.
- Tên miền trỏ DNS A về IP VPS nếu muốn dùng HTTPS.
- Tài khoản quản trị và mật khẩu riêng, tối thiểu 8 ký tự.
- Ảnh ứng dụng: `ghcr.io/haincbbg-coder/minminos:latest`.

Cài Docker theo [tài liệu chính thức](https://docs.docker.com/engine/install/ubuntu/). Không cần cài Python hoặc Node.js riêng trên VPS khi dùng ảnh Docker.

## Cách 1 dùng Hostinger Docker Manager

Vào **hPanel → VPS → Docker Manager → Compose → URL**, dán:

```text
https://raw.githubusercontent.com/haincbbg-coder/minminos/main/docker-compose.minmin.hostinger.yml
```

Đặt các giá trị Environment trước khi Deploy:

```dotenv
DOMAIN_NAME=minmin.tenmiencuaban.com
MINMIN_ADMIN_USER=admin
MINMIN_ADMIN_PASSWORD=ThayBangMatKhauRieng
```

Bấm Deploy, đợi ứng dụng và HTTPS sẵn sàng rồi mở `https://<DOMAIN_NAME>`. Nếu chưa có tên miền, mở tạm `http://<IP-VPS>:7777`; cấu hình HTTPS trước khi nhập thông tin dịch vụ.

Để dùng tên miền miễn phí đi kèm VPS Hostinger, đặt dạng `minmin.<hostname-vps>.hstgr.cloud` khi DNS của nhà cung cấp hỗ trợ. Hostname nằm trong bảng quản lý VPS.

Cài thêm một bản trên cùng VPS: tạo stack riêng, đặt `MINMIN_NAME`, `MINMIN_HOST_PORT` và `DOMAIN_NAME` khác nhau. Ví dụ bản thứ hai dùng `MINMIN_NAME=minmin-shop2`, `MINMIN_HOST_PORT=7778` và tên miền riêng. Mỗi stack phải có project riêng để dữ liệu volume tách biệt.

## Cách 2 dùng Docker Compose qua SSH

Đăng nhập từ CMD hoặc Terminal trên máy tính:

```bash
ssh root@IP-VPS
```

Tải mã nguồn và tạo cấu hình cho bản cài mới:

```bash
git clone https://github.com/haincbbg-coder/minminos.git /opt/minminos
cd /opt/minminos
cp .env.minmin.example .env
nano .env
```

Thay mật khẩu mẫu trong file:

```dotenv
MINMIN_NAME=minminos
MINMIN_HOST_PORT=7777
MINMIN_ADMIN_USER=admin
MINMIN_ADMIN_PASSWORD=ThayBangMatKhauRieng
```

Lưu file, siết quyền và khởi động:

```bash
chmod 600 .env
docker compose -f docker-compose.minmin.yml up -d --pull always
docker compose -f docker-compose.minmin.yml ps
```

Mở `http://<IP-VPS>:7777`. Nếu hiện `health: starting`, chờ server khởi động rồi kiểm tra lại. Nếu chưa truy cập được, kiểm tra cổng TCP 7777 trong bảng quản lý mạng của VPS và xem nhật ký:

```bash
docker compose -f docker-compose.minmin.yml logs --tail=80
```

## Tên miền và HTTPS

Hostinger dùng cấu hình Traefik trong file chuyên dụng ở Cách 1.

Với VPS khác, có thể đặt Caddy hoặc Nginx làm reverse proxy tới `127.0.0.1:7777`, cấp chứng chỉ HTTPS cho tên miền và đặt `MINMIN_BIND=127.0.0.1` trong `.env`. Chỉ đổi bind sau khi reverse proxy đã được cấu hình để tránh mất đường truy cập.

## Thiết lập trong MinMin

Đăng nhập bằng tài khoản quản trị đã đặt. Vào **Models** để kết nối AI, **Kết nối** để thêm tài khoản cửa hàng, sau đó chọn **Skills** và **Agents**. Tài khoản của mỗi nhà cung cấp thuộc về khách; không sao chép token từ máy khác.

## Cập nhật

Với bản mới theo hướng dẫn này:

```bash
cd /opt/minminos
docker compose -f docker-compose.minmin.yml up -d --pull always
```

Trên Hostinger, dùng nút Cập nhật của ứng dụng nếu dịch vụ cập nhật hoạt động, hoặc Redeploy cùng stack. `MINMIN_AUTO_UPDATE=true` bật kiểm tra mỗi ngày; mặc định tắt để tránh khởi động lại giữa công việc.

Với bản cài đã có từ trước, chạy lệnh cập nhật bằng đúng file Compose, project và volume đang dùng. Không đổi tên project hay thay file triển khai chỉ để đổi tên hiển thị: bạn có thể vô tình tạo một bộ volume trống.

## Sao lưu và bảo mật

Sao lưu cấu hình, dữ liệu ứng dụng, bộ não và thông tin đăng nhập trước khi nâng cấp hoặc chuyển VPS. Bảo vệ cả khóa mã hóa đi kèm dữ liệu; không đăng chúng lên repo công khai.

Không dùng `docker compose down -v` để cập nhật: tùy chọn `-v` xóa volume. Không công khai file `.env`, nhật ký có token hoặc ảnh chứa mật khẩu.

## Khi tải ảnh Docker bị từ chối

Repo GitHub và package Docker có quyền truy cập riêng. Nếu báo `unauthorized` hoặc `denied`, chủ package cần kiểm tra **GitHub → Packages → minminos → Package settings**. Nếu package riêng tư, tài khoản tải cần có quyền truy cập phù hợp; không nhúng token vào URL tài liệu.

## Tài liệu tiếp theo

- [Bắt đầu nhanh](QUICKSTART.md)
- [Thiết lập lần đầu](docs/01-bat-dau-thiet-lap.md)
- [Kết nối dữ liệu](docs/09-mcp-va-so-lieu.md)
- [Sao lưu](docs/18-sao-luu-github.md)
- [Giấy phép](LICENSE)
