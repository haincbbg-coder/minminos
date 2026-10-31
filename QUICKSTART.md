# Bắt đầu với MinMin OS

[Tiếng Việt](QUICKSTART.md) · [English](QUICKSTART.en.md)

## PC Windows

1. Cài Python 3.12 và Node.js LTS.
2. Tải ZIP từ [repo MinMin](https://github.com/haincbbg-coder/minminos), giải nén.
3. Mở CMD trong thư mục có `install.ps1` và chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

4. Mở `http://localhost:7777`.
5. Lần sau chạy `start-minmin.bat`; dừng bằng `stop-minmin.bat`.

## Hostinger

**Docker Manager → Compose → URL**:

```text
https://raw.githubusercontent.com/haincbbg-coder/minminos/main/docker-compose.minmin.hostinger.yml
```

Đặt `DOMAIN_NAME`, `MINMIN_ADMIN_USER`, `MINMIN_ADMIN_PASSWORD` riêng trước khi Deploy. Trỏ DNS về VPS để dùng HTTPS. Chi tiết: [Hướng dẫn VPS](DEPLOY.md).

## VPS dùng Docker

Với VPS đã có Git, Docker và Docker Compose:

```bash
git clone https://github.com/haincbbg-coder/minminos.git /opt/minminos
cd /opt/minminos
cp .env.minmin.example .env
nano .env
```

Thay mật khẩu mẫu rồi chạy:

```bash
docker compose -f docker-compose.minmin.yml up -d --pull always
```

Mở `http://<IP-VPS>:7777`. Đặt tên miền và HTTPS trước khi kết nối tài khoản dịch vụ.

## Sau khi cài

Chọn AI ở **Models**, thêm tài khoản cửa hàng ở **Kết nối**, rồi chọn **Skills** và **Agents**. Mỗi khách dùng tài khoản riêng. Xem [hướng dẫn sử dụng](docs/README.md).

## Cập nhật và xử lý lỗi

Docker: dùng đúng file Compose của bản đang chạy. Với bản mới ở trên, chạy lại lệnh `up -d --pull always`. Sao lưu trước khi cập nhật; không dùng `down -v`.

PC: chạy `stop-minmin.bat` rồi `start-minmin.bat` để khởi động lại; xem lỗi trong `server/minmin.log`. Với ZIP, giữ bản cũ và sao lưu dữ liệu trước khi chuyển bản mới. Nhấn Ctrl + F5 sau khi cập nhật.
