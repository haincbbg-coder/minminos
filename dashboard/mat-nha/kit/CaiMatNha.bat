@echo off
setlocal
rem ==============================================================
rem  MinMin Mat Nha - bo cai camera o nha cho may Windows.
rem  Bam dup file nay. Windows hoi thi chon "Thong tin them" roi "Van chay".
rem  File nay chi tai va chay CaiMatNha.ps1 (PowerShell) tu MinMin.
rem ==============================================================
set "MINMIN_URL=__MINMIN_URL__"
if /i "%MINMIN_URL:~0,4%"=="http" goto co_url
echo Nhap dia chi MinMin cua bo, vi du https://minmin.example.com
set /p "MINMIN_URL=Dia chi MinMin: "
:co_url
if "%MINMIN_URL:~-1%"=="/" set "MINMIN_URL=%MINMIN_URL:~0,-1%"

set "THU_MUC=%TEMP%\MinMinMatNha"
if not exist "%THU_MUC%" mkdir "%THU_MUC%"
set "PS1=%THU_MUC%\CaiMatNha.ps1"

echo Dang tai bo cai tu %MINMIN_URL% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%MINMIN_URL%/static/mat-nha/kit/CaiMatNha.ps1' -OutFile '%PS1%'"
if errorlevel 1 (
  if exist "%~dp0CaiMatNha.ps1" (
    echo Khong tai duoc, dung ban CaiMatNha.ps1 nam canh file nay.
    set "PS1=%~dp0CaiMatNha.ps1"
  ) else (
    echo Khong tai duoc bo cai. Kiem tra mang va dia chi MinMin roi chay lai.
    pause
    exit /b 1
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -MinMinUrl "%MINMIN_URL%"
endlocal
