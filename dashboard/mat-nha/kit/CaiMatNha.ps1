#Requires -Version 5.1
<#
  MinMin Mắt Nhà - bộ cài cho máy Windows ở nhà (có GPU NVIDIA càng tốt).

  Làm gì:
    1. Kiểm tra / cài WSL2 và Docker Desktop, xem có GPU NVIDIA không.
    2. Tạo C:\MinMinMatNha, tải mẫu cấu hình từ MinMin.
    3. Quét mạng nhà tìm camera mở cổng RTSP 554, hỏi tên và mã xác minh từng cái, thử luồng.
    4. Viết config\config.yml cho Frigate và docker-compose.yml, dựng model nhận diện cho GPU.
    5. Hỏi mã ghép nối MinMin, thử gửi một nhịp, rồi chạy docker compose up -d.

  Riêng tư: mã camera, video, khuôn mặt đã học CHỈ nằm trên máy này. Lên MinMin chỉ có dòng
  tóm tắt sự kiện + ảnh chụp nhỏ (do minmin-cau gửi).

  Chạy qua CaiMatNha.bat (bấm đúp). Chạy tay:
    powershell -ExecutionPolicy Bypass -File CaiMatNha.ps1 -MinMinUrl https://minmin.example.com
#>
param([string]$MinMinUrl = "")

# "Continue", KHÔNG "Stop": PowerShell 5.1 biến chữ lệnh ngoài (docker, wsl) in ra stderr thành
# lỗi, và với "Stop" thì lỗi đó làm dừng cả bộ cài. Lỗi thật được kiểm bằng $LASTEXITCODE.
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$Goc = "C:\MinMinMatNha"
$AnhFrigateGpu = "ghcr.io/blakeblackshear/frigate:stable-tensorrt"
$AnhFrigateCpu = "ghcr.io/blakeblackshear/frigate:stable"
$TenModel = "yolov9-s-320.onnx"
$Utf8KhongBom = New-Object System.Text.UTF8Encoding($false)

function Noi($chu) { Write-Host $chu }
function Tot($chu) { Write-Host ("  [OK] " + $chu) -ForegroundColor Green }
function Canh($chu) { Write-Host ("  [!] " + $chu) -ForegroundColor Yellow }
function Loi($chu) { Write-Host ("  [X] " + $chu) -ForegroundColor Red }
function Buoc($chu) { Write-Host ""; Write-Host ("== " + $chu + " ==") -ForegroundColor Cyan }
function Hoi($cau, $macDinh = "") {
    if ($macDinh) { $t = Read-Host ("$cau [$macDinh]") } else { $t = Read-Host $cau }
    if ([string]::IsNullOrWhiteSpace($t)) { return $macDinh }
    return $t.Trim()
}
function Dung($chu) {
    Loi $chu
    Read-Host "Bấm Enter để đóng"
    exit 1
}
function GhiFile($duong, $noiDung) {
    [System.IO.File]::WriteAllText($duong, $noiDung, $Utf8KhongBom)
}

# ------------------------------------------------------------------ 0. Quyền quản trị
$laAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $laAdmin) {
    Noi "Cần quyền quản trị để cài WSL/Docker. Windows sẽ hỏi, bố bấm Có (Yes)."
    $thamSo = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($MinMinUrl) { $thamSo += " -MinMinUrl `"$MinMinUrl`"" }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $thamSo
    exit 0
}

Write-Host ""
Write-Host "  MinMin Mắt Nhà - cài camera ở nhà" -ForegroundColor Magenta
Write-Host "  Video và khuôn mặt ở yên trên máy này. MinMin chỉ nhận tóm tắt sự kiện." -ForegroundColor DarkGray

if (-not $MinMinUrl) { $MinMinUrl = Hoi "Địa chỉ MinMin (vd https://minmin.example.com)" }
$MinMinUrl = $MinMinUrl.TrimEnd("/")
if ($MinMinUrl -notmatch '^https?://') { Dung "Địa chỉ MinMin phải bắt đầu bằng https://" }

# ------------------------------------------------------------------ 1. WSL2, Docker, GPU
Buoc "1. Kiểm tra WSL2, Docker Desktop, GPU"
$canKhoiDongLai = $false
& docker info *> $null
if ($LASTEXITCODE -eq 0) {
    Tot "Docker Desktop đang chạy (WSL2 sẵn sàng)"
} elseif (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    & wsl.exe --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Canh "Chưa có WSL2. Đang cài (cần mạng, vài phút)..."
        & wsl.exe --install --no-distribution
        $canKhoiDongLai = $true
    } else { Tot "WSL2 đã có" }
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Canh "Chưa có Docker Desktop. Đang cài bằng winget (tải khoảng 500MB)..."
        & winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
        $canKhoiDongLai = $true
    } else {
        Dung "Máy chưa có Docker Desktop và cũng không có winget. Tải Docker Desktop ở https://www.docker.com/products/docker-desktop/ , cài xong khởi động lại máy rồi bấm đúp CaiMatNha.bat lần nữa."
    }
} else {
    Canh "Docker chưa chạy. Đang mở Docker Desktop, chờ tối đa 3 phút..."
    $exe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $exe) { Start-Process $exe }
    $den = (Get-Date).AddMinutes(3)
    do { Start-Sleep 5; & docker info *> $null } while ($LASTEXITCODE -ne 0 -and (Get-Date) -lt $den)
    if ($LASTEXITCODE -ne 0) {
        Dung "Docker vẫn chưa chạy. Mở Docker Desktop, chờ 'Engine running', rồi bấm đúp CaiMatNha.bat lại. Nếu Docker báo lỗi WSL: mở PowerShell (Admin) gõ 'wsl --update' rồi khởi động lại máy."
    }
}

if ($canKhoiDongLai) {
    Write-Host ""
    Canh "CẦN KHỞI ĐỘNG LẠI MÁY để WSL2/Docker chạy được. Sau khi khởi động lại:"
    Noi   "   1) Mở Docker Desktop một lần (biểu tượng cá voi), bấm Accept điều khoản, bỏ qua đăng nhập."
    Noi   "   2) Chờ góc dưới Docker Desktop báo 'Engine running' (màu xanh)."
    Noi   "   3) Bấm đúp CaiMatNha.bat lần nữa, bộ cài chạy tiếp từ đây."
    Read-Host "Bấm Enter để đóng"
    exit 0
}
Tot "Docker đang chạy"

$coGpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $tenGpu = (& nvidia-smi -L 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -eq 0 -and $tenGpu) { $coGpu = $true; Tot "GPU NVIDIA: $tenGpu" }
}
if (-not $coGpu) {
    Canh "Không thấy GPU NVIDIA (nvidia-smi). Vẫn cài được nhưng chạy bằng CPU: chậm hơn, tắt chép lời nói, nhận mặt bản nhẹ."
    Canh "Máy CÓ card NVIDIA mà báo vậy: cài driver mới nhất ở nvidia.com rồi chạy lại bộ cài."
}
$anhFrigate = if ($coGpu) { $AnhFrigateGpu } else { $AnhFrigateCpu }

# ------------------------------------------------------------------ 2. Thư mục + mẫu
Buoc "2. Tạo $Goc và tải mẫu cấu hình"
foreach ($d in @("", "config", "config\model_cache", "storage", "cau-data", "minmin-cau", "kit-mau", "kit-mau\minmin-cau")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Goc $d) | Out-Null
}
$kit = "$MinMinUrl/static/mat-nha/kit"
foreach ($f in @("docker-compose.yml", "config.yml", "minmin-cau/Dockerfile", "minmin-cau/cau.py")) {
    $dich = Join-Path $Goc ("kit-mau\" + $f.Replace("/", "\"))
    try {
        Invoke-WebRequest -UseBasicParsing -ErrorAction Stop -Uri "$kit/$f" -OutFile $dich
    } catch {
        Dung "Không tải được $kit/$f ($($_.Exception.Message)). Kiểm tra địa chỉ MinMin và mạng."
    }
}
Copy-Item -Force (Join-Path $Goc "kit-mau\minmin-cau\*") (Join-Path $Goc "minmin-cau")
Tot "Đã tải mẫu vào $Goc\kit-mau"

Noi "Tải Frigate ($anhFrigate). Lần đầu khá nặng (vài GB), bố chờ nhé..."
& docker pull $anhFrigate
if ($LASTEXITCODE -ne 0) { Dung "Không tải được ảnh Frigate. Kiểm tra mạng rồi chạy lại." }

# ------------------------------------------------------------------ 3. Tìm camera
$fileCfg = Join-Path $Goc "config\config.yml"
$viet = $true
if (Test-Path $fileCfg) {
    $tl = Hoi "Đã có cấu hình camera cũ. Quét và nhập lại camera? (c = có / k = giữ nguyên)" "k"
    if ($tl -notmatch '^[cCyY]') { $viet = $false }
}

function ThuRtsp($url) {
    # Dùng ffprobe có sẵn trong ảnh Frigate. Trả "ok|video,audio", "sai" hoặc "khongkiemduoc".
    # CHƯA KIỂM TRÊN MÁY THẬT: đường dẫn ffprobe trong ảnh Frigate có thể đổi theo phiên bản.
    $sh = 'for p in $(command -v ffprobe) /usr/lib/ffmpeg/*/bin/ffprobe /usr/lib/btbn-ffmpeg/bin/ffprobe; do if [ -x $p ]; then exec $p -v error -rtsp_transport tcp -timeout 8000000 -i $0 -show_entries stream=codec_type -of csv=p=0; fi; done; echo NOFFPROBE; exit 3'
    $ra = & docker run --rm --entrypoint /bin/bash $anhFrigate -c $sh $url 2>&1
    $chu = ($ra | Out-String)
    if ($chu -match 'NOFFPROBE') { return "khongkiemduoc" }
    if ($LASTEXITCODE -eq 0 -and $chu -match 'video') {
        $co = @("video"); if ($chu -match 'audio') { $co += "audio" }
        return "ok|" + ($co -join ",")
    }
    return "sai"
}

$cams = @()
if ($viet) {
    Buoc "3. Tìm camera trong mạng nhà (cổng RTSP 554)"
    Noi "Nhắc: trong app EZVIZ phải BẬT RTSP cho từng camera trước:"
    Noi "  Cài đặt > Xem trực tiếp qua mạng LAN (LAN Live View) > chọn camera > bánh răng >"
    Noi "  Cài đặt dịch vụ cục bộ (Local Service Settings) > bật RTSP. Điện thoại phải cùng Wi-Fi."
    $ipMay = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
        Select-Object -First 1 | ForEach-Object { $_.IPv4Address.IPAddress } | Select-Object -First 1
    $thay = @()
    if ($ipMay) {
        $tien = ($ipMay -split '\.')[0..2] -join '.'
        Noi "Máy này: $ipMay. Đang quét $tien.1-254 (khoảng 3 giây)..."
        $viec = @{}
        foreach ($i in 1..254) {
            $ip = "$tien.$i"
            if ($ip -eq $ipMay) { continue }
            $c = New-Object System.Net.Sockets.TcpClient
            $viec[$ip] = @{ c = $c; t = $c.ConnectAsync($ip, 554) }
        }
        Start-Sleep -Milliseconds 2500
        foreach ($ip in $viec.Keys) {
            $v = $viec[$ip]
            if ($v.t.IsCompleted -and -not $v.t.IsFaulted -and $v.c.Connected) { $thay += $ip }
            try { $v.c.Close() } catch {}
        }
        $thay = @($thay | Sort-Object { [int](($_ -split '\.')[3]) })
    } else {
        Canh "Không xác định được mạng của máy này."
    }
    if ($thay.Count -gt 0) { Tot ("Thấy " + $thay.Count + " thiết bị mở RTSP: " + ($thay -join ", ")) }
    else { Canh "Không thấy thiết bị nào mở cổng 554. Kiểm tra đã bật RTSP trong app EZVIZ chưa. Có thể nhập IP tay." }

    $them = Hoi "Nhập thêm IP camera khác (cách nhau dấu phẩy, bỏ trống nếu không)" ""
    if ($them) { $thay = @($thay) + @($them -split '[,; ]+' | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' }) }

    $daDung = @{}
    foreach ($ip in $thay) {
        Write-Host ""
        Noi "Camera ở $ip"
        $chinh = $null
        $ten = Hoi "  Đặt tên (không dấu, vd cong, san, phong_khach). Bỏ trống = bỏ qua camera này" ""
        if (-not $ten) { continue }
        $ten = ($ten.ToLower() -replace '[^a-z0-9_]+', '_').Trim('_')
        if (-not $ten -or $daDung.ContainsKey($ten)) { $ten = "cam_" + ($ip -split '\.')[3] }
        while ($true) {
            $ma = Hoi "  Mã xác minh 6 chữ in trên tem dưới đáy camera (Verification Code)" ""
            $ma = $ma.Trim().ToUpper()
            if ($ma -notmatch '^[A-Z]{6}$') { Canh "  Mã EZVIZ là 6 chữ cái in hoa, vd ABCDEF. Nhập lại."; continue }
            $chinh = "rtsp://admin:$ma@${ip}:554/Streaming/Channels/101"
            $phu = "rtsp://admin:$ma@${ip}:554/Streaming/Channels/102"
            Noi "  Đang thử luồng (tối đa 10 giây)..."
            $kq = ThuRtsp $chinh
            if ($kq -like "ok*") { Tot ("  Xem được luồng chính (" + $kq.Substring(3) + ")"); break }
            if ($kq -eq "khongkiemduoc") { Canh "  Không kiểm được (thiếu ffprobe), vẫn thêm camera. Xem lại trong giao diện Frigate."; break }
            $lai = Hoi "  Không mở được luồng. Sai mã, chưa bật RTSP, hoặc camera dùng pin (không có RTSP). Nhập lại mã? (c/k)" "c"
            if ($lai -notmatch '^[cCyY]') { $chinh = $null; break }
        }
        if (-not $chinh) { continue }
        $daDung[$ten] = $true
        $cams += [pscustomobject]@{ ten = $ten; chinh = $chinh; phu = $phu }
    }
    if ($cams.Count -eq 0) { Dung "Chưa có camera nào. Bật RTSP trong app EZVIZ rồi chạy lại bộ cài." }
}

# ------------------------------------------------------------------ 4. Model + config.yml + compose
Buoc "4. Viết cấu hình Frigate"
$dungGpu = $coGpu
$fileModel = Join-Path $Goc "config\model_cache\$TenModel"
if ($dungGpu -and -not (Test-Path $fileModel)) {
    Noi "Dựng model nhận diện YOLOv9 cho GPU (một lần, 5-15 phút, cần mạng)..."
    $df = @'
FROM python:3.11 AS build
RUN apt-get update && apt-get install --no-install-recommends -y cmake libgl1
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /bin/
WORKDIR /yolov9
ADD https://github.com/WongKinYiu/yolov9.git .
RUN uv pip install --system -r requirements.txt
RUN uv pip install --system onnx==1.18.0 onnxruntime onnx-simplifier==0.4.*
ARG MODEL_SIZE
ARG IMG_SIZE
ADD https://github.com/WongKinYiu/yolov9/releases/download/v0.1/yolov9-${MODEL_SIZE}-converted.pt yolov9-${MODEL_SIZE}.pt
RUN python3 export.py --weights ./yolov9-${MODEL_SIZE}.pt --imgsz ${IMG_SIZE} --simplify --include onnx
FROM scratch
ARG MODEL_SIZE
ARG IMG_SIZE
COPY --from=build /yolov9/yolov9-${MODEL_SIZE}.onnx /yolov9-${MODEL_SIZE}-${IMG_SIZE}.onnx
'@
    $thuMucModel = Join-Path $Goc "config\model_cache"
    Push-Location $thuMucModel
    try { $df | & docker build . --build-arg MODEL_SIZE=s --build-arg IMG_SIZE=320 --output . -f- } finally { Pop-Location }
    if (-not (Test-Path $fileModel)) {
        Canh "Dựng model không thành. Tạm dùng bộ nhận diện CPU có sẵn (chậm hơn). Chạy lại bộ cài sau để thử lại."
        $dungGpu = $false
    } else { Tot "Đã có model $TenModel" }
}

$mau = [System.IO.File]::ReadAllText((Join-Path $Goc "kit-mau\config.yml"))
if (-not $dungGpu) {
    $khoiCpu = "# >>> DETECTORS`r`n# Không có GPU/model ONNX: dùng bộ nhận diện CPU có sẵn trong Frigate.`r`ndetectors:`r`n  cpu1:`r`n    type: cpu`r`n# <<< DETECTORS"
    $mau = [regex]::Replace($mau, '(?s)# >>> DETECTORS.*?# <<< DETECTORS', { param($m) $khoiCpu })
}
if (-not $coGpu) {
    $mau = $mau -replace 'hwaccel_args: preset-nvidia', 'hwaccel_args: auto'
    $mau = [regex]::Replace($mau, '(?s)(face_recognition:.*?model_size: )large', '${1}small')
    $mau = [regex]::Replace($mau, '(?s)(lpr:.*?device: )GPU', '${1}CPU')
    $mau = [regex]::Replace($mau, '(?s)(audio_transcription:\s*enabled: )true', '${1}false')
}
if ($viet) {
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("# >>> CAMERAS")
    [void]$sb.AppendLine("go2rtc:")
    [void]$sb.AppendLine("  streams:")
    foreach ($c in $cams) {
        [void]$sb.AppendLine("    $($c.ten):")
        [void]$sb.AppendLine("      - $($c.chinh)")
        [void]$sb.AppendLine("    $($c.ten)_sub:")
        [void]$sb.AppendLine("      - $($c.phu)")
    }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("cameras:")
    foreach ($c in $cams) {
        [void]$sb.AppendLine("  $($c.ten):")
        [void]$sb.AppendLine("    enabled: true")
        [void]$sb.AppendLine("    ffmpeg:")
        [void]$sb.AppendLine("      inputs:")
        [void]$sb.AppendLine("        - path: rtsp://127.0.0.1:8554/$($c.ten)")
        [void]$sb.AppendLine("          input_args: preset-rtsp-restream")
        [void]$sb.AppendLine("          roles:")
        [void]$sb.AppendLine("            - record")
        [void]$sb.AppendLine("            - audio")
        [void]$sb.AppendLine("        - path: rtsp://127.0.0.1:8554/$($c.ten)_sub")
        [void]$sb.AppendLine("          input_args: preset-rtsp-restream")
        [void]$sb.AppendLine("          roles:")
        [void]$sb.AppendLine("            - detect")
    }
    [void]$sb.Append("# <<< CAMERAS")
    $khoiCam = $sb.ToString()
    $mau = [regex]::Replace($mau, '(?s)# >>> CAMERAS.*?# <<< CAMERAS', { param($m) $khoiCam })
    if (Test-Path $fileCfg) { Copy-Item -Force $fileCfg ($fileCfg + ".cu") }
    GhiFile $fileCfg $mau
    Tot "Đã viết $fileCfg (bản cũ nếu có: config.yml.cu)"
    $tenCams = ($cams | ForEach-Object { $_.ten }) -join ","
} else {
    $tenCams = ""
    $cu = [System.IO.File]::ReadAllText($fileCfg)
    $mc = [regex]::Match($cu, '(?ms)^cameras:\s*$(.*)')
    if ($mc.Success) {
        $tenCams = ([regex]::Matches($mc.Groups[1].Value, '(?m)^  ([a-z0-9_]+):') | ForEach-Object { $_.Groups[1].Value }) -join ","
    }
    Tot "Giữ nguyên cấu hình camera cũ ($tenCams)"
}

$compose = [System.IO.File]::ReadAllText((Join-Path $Goc "kit-mau\docker-compose.yml"))
if ($coGpu) {
    $khoiGpu = "deploy:`r`n      resources:`r`n        reservations:`r`n          devices:`r`n            - driver: nvidia`r`n              count: 1`r`n              capabilities: [gpu]"
    $compose = $compose.Replace("#__GPU__", $khoiGpu)
} else {
    $compose = $compose.Replace("#__GPU__", "# (không có GPU NVIDIA)")
    $compose = $compose.Replace($AnhFrigateGpu, $AnhFrigateCpu)
}
GhiFile (Join-Path $Goc "docker-compose.yml") $compose
Tot "Đã viết $Goc\docker-compose.yml"

# ------------------------------------------------------------------ 5. Ghép nối MinMin
Buoc "5. Ghép nối với MinMin"
Noi "Mở $MinMinUrl/mat-nha, bấm 'Tạo mã ghép nối', bấm Chép, rồi dán vào đây (chuột phải = dán)."
$fileEnv = Join-Path $Goc ".env"
$maCu = ""
if (Test-Path $fileEnv) {
    $m = Select-String -Path $fileEnv -Pattern '^MAT_NHA_TOKEN=(.+)$' | Select-Object -First 1
    if ($m) { $maCu = $m.Matches[0].Groups[1].Value.Trim() }
}
while ($true) {
    if ($maCu) { $ma = Hoi "Mã ghép nối (Enter = giữ mã cũ ...$($maCu.Substring([Math]::Max(0, $maCu.Length - 4))))" "" ; if (-not $ma) { $ma = $maCu } }
    else { $ma = Hoi "Mã ghép nối" "" }
    if (-not $ma) { continue }
    $than = '{"loai":"nhip","phien_ban":"cai","cameras":[' + (($tenCams -split ',' | Where-Object { $_ } | ForEach-Object { '"' + $_ + '"' }) -join ',') + ']}'
    try {
        $r = Invoke-WebRequest -UseBasicParsing -ErrorAction Stop -Method Post -Uri "$MinMinUrl/mat-nha/su-kien" `
            -Headers @{ "x-mat-nha-token" = $ma } -ContentType "application/json" -Body $than
        if ($r.StatusCode -eq 200) { Tot "MinMin đã nhận mã"; break }
    } catch {
        $st = 0; try { $st = [int]$_.Exception.Response.StatusCode } catch {}
        if ($st -eq 401) { Canh "MinMin báo SAI MÃ. Tạo mã mới trên trang Mắt Nhà rồi dán lại."; $maCu = ""; continue }
        $tl = Hoi "Không gửi được tới MinMin ($($_.Exception.Message)). Thử lại? (c = thử lại / k = lưu mã và chạy tiếp)" "c"
        if ($tl -notmatch '^[cCyY]') { break }
    }
}
GhiFile $fileEnv ("MINMIN_URL=$MinMinUrl`nMAT_NHA_TOKEN=$ma`nCAMERAS=$tenCams`nGUI_ANH=1`nANH_CAO=360`n")
Tot "Đã lưu $fileEnv (mã chỉ nằm trên máy này)"

# ------------------------------------------------------------------ 6. Chạy
Buoc "6. Khởi động Frigate + MQTT + cầu nối"
Push-Location $Goc
try { & docker compose up -d --build } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { Dung "docker compose up lỗi. Xem thông báo ở trên, sửa rồi chạy lại: cd $Goc ; docker compose up -d" }

Write-Host ""
Write-Host "  XONG. Mắt Nhà đang chạy." -ForegroundColor Green
Noi "  Giao diện Frigate trên máy này:   http://localhost:5000"
Noi "  Từ điện thoại trong nhà:           https://<IP máy này>:8971  (mật khẩu admin: docker logs frigate)"
Noi "  Sự kiện trên MinMin:               $MinMinUrl/mat-nha"
Noi ""
Noi "  Việc tiếp theo:"
Noi "   1) Frigate > Face Library (Thư viện khuôn mặt) > Add Face: mỗi người nhà ĐÃ ĐỒNG Ý 1-5 ảnh rõ mặt."
Noi "   2) Biển số quen: sửa config\config.yml mục lpr > known_plates, rồi: docker compose restart frigate"
Noi "   3) Xem vài ngày, biển số hay bị bỏ sót thì đổi dòng lpr format thành 'format: null'."
Noi "   4) Để Docker Desktop tự chạy khi mở máy: Docker Desktop > Settings > General > Start when you sign in."
Read-Host "Bấm Enter để đóng"
