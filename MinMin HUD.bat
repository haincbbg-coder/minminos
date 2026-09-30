@echo off
chcp 65001 >nul
title MinMin HUD
REM Mo MinMin HUD toan man hinh tren man phu (Arzopa). Bam dup la chay.
REM   "MinMin HUD.bat" install     tu mo moi khi dang nhap Windows
REM   "MinMin HUD.bat" uninstall   bo tu mo
REM   "MinMin HUD.bat" screens     xem danh sach man hinh
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\minmin-hud.ps1" %1
if not "%1"=="" pause
