@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Chrome MinMin tren may tinh
.venv\Scripts\python minmin_worker.py chrome
pause
