# MinMin Mắt Nhà - camera EZVIZ ở nhà

Mắt Nhà cho MinMin "nhìn" camera ở nhà và ghi lại: ai ra vào (người nhà đã học mặt hay người
lạ), xe và biển số, con vật, đồ vật, và lời nói chép lại. Hỏi MinMin "hôm nay ai đến nhà",
"xe biển 29-B1... về lúc nào", "có người lạ không" là nó tra được.

## Chạy ở đâu

```
Camera EZVIZ --RTSP--> Frigate (máy Windows ở nhà, GPU NVIDIA)
                          |  MQTT (mosquitto, trong máy)
                          v
                    minmin-cau (cầu nối) --HTTPS--> MinMin trên VPS (/mat-nha)
```

VPS không vào được mạng nhà, nên máy ở nhà tự đẩy sự kiện lên. Mọi việc nặng (nhận người, xe,
mặt, biển số, chép lời) chạy trên máy ở nhà bằng [Frigate](https://frigate.video) 0.17.

| Ở lại máy ở nhà (`C:\MinMinMatNha`) | Gửi lên MinMin (VPS) |
|---|---|
| Video ghi hình, luồng trực tiếp | Một dòng tóm tắt mỗi sự kiện: camera, giờ, loại, tên người nhà hoặc "người lạ", biển số, điểm tin cậy |
| Thư viện khuôn mặt đã học | Ảnh chụp nhỏ (khoảng 360px) của sự kiện |
| Mã xác minh camera, mật khẩu Frigate | Lời nói đã chép thành chữ (không gửi tiếng) |
| Mã ghép nối (trong `.env`) | Nhịp "còn sống" mỗi 2 phút |

MinMin giữ sự kiện và ảnh **30 ngày** rồi tự xoá (tối đa 500MB ảnh). Frigate giữ video sự kiện
7 ngày, ảnh chụp 30 ngày trên máy ở nhà.

## Cần gì

- Camera EZVIZ **cắm điện** có RTSP (C6N, dòng H...). Camera dùng pin **không có RTSP**.
- Máy Windows 10/11 bật suốt, tốt nhất có card NVIDIA (driver mới). Không có GPU vẫn chạy
  được nhưng chậm hơn, nhận mặt bản nhẹ, không chép lời nói tiếng Việt.
- Ổ cứng trống khoảng 50GB cho ảnh Frigate + video.

## Cài đặt

1. **Bật RTSP** cho từng camera trong app EZVIZ (điện thoại cùng Wi-Fi với camera):
   Cài đặt → Xem trực tiếp qua mạng LAN (LAN Live View) → chọn camera → bánh răng →
   Cài đặt dịch vụ cục bộ (Local Service Settings) → bật RTSP.
2. Ghi **mã xác minh 6 chữ** in trên tem dưới đáy mỗi camera.
3. Mở MinMin → trang **Mắt Nhà** (`/mat-nha`) → **Tạo mã ghép nối** → Chép. Mã chỉ hiện một lần.
4. Trên máy ở nhà, bấm **Tải CaiMatNha.bat** ở trang Mắt Nhà rồi bấm đúp tệp đó (Windows hỏi
   thì chọn Thông tin thêm → Vẫn chạy, rồi đồng ý quyền quản trị). Bộ cài sẽ:
   - cài WSL2 và Docker Desktop nếu thiếu. Nếu nó báo **cần khởi động lại**: khởi động lại, mở
     Docker Desktop một lần (Accept điều khoản), chờ "Engine running", rồi bấm đúp lại tệp .bat;
   - tải Frigate (vài GB, lần đầu lâu), dựng model nhận diện YOLOv9 cho GPU (5-15 phút);
   - quét mạng nhà tìm thiết bị mở cổng 554, hỏi **tên** (vd `cong`, `san`, `phong_khach`) và
     **mã xác minh** từng camera, thử mở luồng;
   - hỏi mã ghép nối, thử gửi một nhịp lên MinMin, rồi chạy `docker compose up -d`.
5. Mở trang Mắt Nhà: góc phải báo "Máy ở nhà: đang nối" là xong.

Địa chỉ camera dùng: `rtsp://admin:<MÃ>@<IP>:554/Streaming/Channels/101` (luồng chính, để ghi
và nghe) và `/102` (luồng phụ, để nhận diện). Một số đời camera dùng `/ch1/main`.

## Học mặt người nhà và biển số quen

- **Khuôn mặt**: mở Frigate trên máy ở nhà (`http://localhost:5000`) → **Face Library** →
  **Add Face** → mỗi người 1-5 ảnh rõ mặt. Sau vài ngày vào tab **Train** gán thêm ảnh Frigate
  bắt được để nhận chính xác hơn. Tên đặt ở đây là tên MinMin sẽ nói.
  **Chỉ học mặt người đã đồng ý.**
- **Biển số quen**: sửa `C:\MinMinMatNha\config\config.yml`, mục `lpr` → `known_plates`:

  ```yaml
  known_plates:
    Xe cua bo:
      - "29B112345"
  ```

  rồi `docker compose restart frigate` trong `C:\MinMinMatNha`.
- Dòng `format` trong mục `lpr` là mẫu biển số Việt Nam (vd `30A-123.45`, `51LD-123.45`,
  `29-B1 123.45` hai dòng). Biển nào không khớp mẫu thì Frigate **bỏ luôn**. Xem vài ngày, nếu
  thấy sót nhiều thì đổi thành `format: null`.

## Khắc phục sự cố

- **Không thấy camera khi quét / không mở được luồng**: chưa bật RTSP trong app EZVIZ (phải
  làm từng camera, điện thoại cùng Wi-Fi), sai mã xác minh (6 chữ in hoa trên tem), hoặc là
  camera dùng pin (không có RTSP). Có thể nhập IP tay khi bộ cài hỏi.
- **App EZVIZ không có mục Local Service Settings**: cập nhật app và firmware camera. Một số đời
  cũ chỉ bật RTSP được qua phần mềm EZVIZ Studio trên máy tính.
- **Docker báo lỗi WSL / "Engine stopped"**: mở PowerShell (Admin) gõ `wsl --update`, khởi động
  lại máy. Kiểm tra BIOS đã bật ảo hoá (Intel VT-x / AMD-V).
- **Không thấy GPU**: cài driver NVIDIA mới nhất, `nvidia-smi` phải chạy được trong PowerShell.
  Docker Desktop → Settings → Resources → WSL integration bật. Chạy lại bộ cài.
- **Frigate không chạy**: `docker logs frigate` (trong PowerShell). Lỗi cấu hình thì sửa
  `config\config.yml` (bản cũ lưu ở `config.yml.cu`).
- **Trang Mắt Nhà báo "mất nối"**: máy ở nhà tắt hoặc mất mạng. Sự kiện nằm chờ trong
  `C:\MinMinMatNha\cau-data\hang-doi.jsonl` và tự gửi khi có mạng lại. `docker logs
  minmin-mat-nha-minmin-cau-1` để xem cầu nối báo gì; "SAI MA GHEP NOI" thì tạo mã mới và sửa
  `MAT_NHA_TOKEN` trong `C:\MinMinMatNha\.env`, rồi `docker compose up -d`.
- **Muốn Docker tự chạy khi mở máy**: Docker Desktop → Settings → General → Start when you
  sign in.

## Pháp lý và riêng tư

Luật Bảo vệ dữ liệu cá nhân (Luật số 91/2025/QH15, hiệu lực 01/01/2026) xếp dữ liệu sinh trắc
học như **mẫu khuôn mặt** vào dữ liệu cá nhân nhạy cảm. Mắt Nhà vì vậy mặc định:

- giữ mọi video và mẫu khuôn mặt **trên máy ở nhà**, không đưa lên VPS;
- chỉ gửi lên MinMin tóm tắt sự kiện và ảnh chụp nhỏ, tự xoá sau 30 ngày;
- chỉ nên học mặt người **đã đồng ý**; người lạ chỉ được ghi là "người lạ", không học mặt;
- nên dán thông báo "khu vực có camera" ở cổng, và không quay sang nhà hàng xóm hay lối đi chung.

Đây là ghi chú kỹ thuật, không phải tư vấn pháp lý.

## Chưa kiểm trên máy thật

- Khoá cấu hình Frigate đối chiếu với docs.frigate.video (bản 0.17) nhưng chưa chạy trên camera
  EZVIZ thật; lần đầu nên xem `docker logs frigate`.
- Độ chính xác đọc biển số Việt Nam và mẫu `format` cần thử trên video thật.
- Chép lời tiếng Việt dùng Whisper (`language: vi`) trên GPU; độ chính xác với micro camera
  chưa đo. Chủ đề MQTT chép lời có thể cần bật chép lời trực tiếp trong Frigate.
