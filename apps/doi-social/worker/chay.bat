@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MinMin Worker
:lap
.venv\Scripts\python minmin_worker.py chay
echo Worker dung. Tu chay lai sau 10 giay (dong cua so nay de tat han)...
timeout /t 10 >nul
goto lap
