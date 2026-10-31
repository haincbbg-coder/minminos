@echo off
chcp 65001 >nul
title Khoi dong MinMin OS
cd /d "%~dp0"

echo Bat MinMin OS chay NEN - khong con cua so den (port 7777)...
REM Viec tat instance cu + chay server AN giao het cho start-minmin.vbs (cua so an hoan toan).
REM Log ghi vao server\minmin.log (mo file do neu can xem loi). Tat server: stop-minmin.bat.
wscript //nologo start-minmin.vbs

echo.
echo Da bat. Cho ~10 giay roi mo http://localhost:7777 va bam Ctrl+Shift+R.
echo (Tat server: chay stop-minmin.bat. Xem loi: mo file server\minmin.log)
timeout /t 4 >nul
