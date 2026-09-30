# MinMin HUD - mo HUD toan man hinh tren man phu (vd Arzopa), man chinh (Samsung) de nguyen.
#
#   minmin-hud.ps1              mo HUD
#   minmin-hud.ps1 install      tu mo HUD moi khi dang nhap Windows
#   minmin-hud.ps1 uninstall    bo tu mo
#   minmin-hud.ps1 screens      liet ke man hinh (de biet so thu tu)
#
# Tuy chinh qua bien moi truong (khong bat buoc):
#   MINMIN_HUD_URL     dia chi MinMin (mac dinh https://minmin.elaria.cloud)
#   MINMIN_HUD_SCREEN  so thu tu man hinh, bat dau tu 1 (mac dinh: man KHONG phai man chinh)
#   MINMIN_HUD_FORM    portrait | orb
param([string]$Action = "open")
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$Base = if ($env:MINMIN_HUD_URL) { $env:MINMIN_HUD_URL.TrimEnd("/") } else { "https://minmin.elaria.cloud" }
$Form = if ($env:MINMIN_HUD_FORM) { $env:MINMIN_HUD_FORM } else { "portrait" }
$Url = "$Base/hud?autostart=1&form=$Form"
$HudProfile = Join-Path $env:LOCALAPPDATA "MinMinHUD\profile"
$Startup = [Environment]::GetFolderPath("Startup")
$Shortcut = Join-Path $Startup "MinMin HUD.lnk"

$screens = [System.Windows.Forms.Screen]::AllScreens

if ($Action -eq "screens") {
    $i = 1
    foreach ($s in $screens) {
        $b = $s.Bounds
        $tag = if ($s.Primary) { " (man chinh)" } else { "" }
        Write-Host ("{0}. {1}x{2} tai ({3},{4}){5}" -f $i, $b.Width, $b.Height, $b.X, $b.Y, $tag)
        $i++
    }
    exit 0
}

if ($Action -eq "install") {
    $sh = (New-Object -ComObject WScript.Shell).CreateShortcut($Shortcut)
    $sh.TargetPath = "powershell.exe"
    $sh.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $sh.WorkingDirectory = Split-Path $PSCommandPath
    $sh.Save()
    Write-Host "Da bat: MinMin HUD tu mo tren man phu moi khi dang nhap Windows."
    exit 0
}
if ($Action -eq "uninstall") {
    if (Test-Path $Shortcut) { Remove-Item $Shortcut }
    Write-Host "Da bo tu mo MinMin HUD."
    exit 0
}

# --- chon man hinh ---
$target = $null
if ($env:MINMIN_HUD_SCREEN) {
    $idx = [int]$env:MINMIN_HUD_SCREEN - 1
    if ($idx -ge 0 -and $idx -lt $screens.Length) { $target = $screens[$idx] }
}
if (-not $target) { $target = $screens | Where-Object { -not $_.Primary } | Select-Object -First 1 }
if (-not $target) {
    Write-Host "Chi thay 1 man hinh. Cam man Arzopa roi chay lai; tam thoi mo HUD tren man chinh."
    $target = [System.Windows.Forms.Screen]::PrimaryScreen
}
$b = $target.Bounds

# --- chon trinh duyet: Chrome neu co, khong thi Edge (luon co tren Windows) ---
$browsers = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$exe = $browsers | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $exe) { Write-Host "Khong tim thay Chrome hay Edge."; exit 1 }

New-Item -ItemType Directory -Force -Path $HudProfile | Out-Null
# Ho so rieng: HUD khong dung chung tab voi trinh duyet bo dang lam viec. Lan dau bo dang nhap
# MinMin va cho phep micro mot lan trong cua so nay; lan sau tu nho.
$browserArgs = @(
    "--app=$Url",
    "--user-data-dir=$HudProfile",
    "--window-position=$($b.X),$($b.Y)",
    "--window-size=$($b.Width),$($b.Height)",
    "--start-fullscreen",
    "--autoplay-policy=no-user-gesture-required",
    "--disable-features=Translate",
    "--no-first-run",
    "--no-default-browser-check"
)
Start-Process -FilePath $exe -ArgumentList $browserArgs
Write-Host ("Da mo MinMin HUD tren man {0}x{1}. Thoat toan man hinh: F11. Dong: Alt+F4." -f $b.Width, $b.Height)
