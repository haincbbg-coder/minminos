@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MinMin - Cau noi Concat
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || if exist "%USERPROFILE%\Documents\MinMinWorker\.venv\Scripts\python.exe" set PY="%USERPROFILE%\Documents\MinMinWorker\.venv\Scripts\python.exe"
:lap
%PY% concat_cau.py chay
echo Cau noi dung. Tu chay lai sau 10 giay (dong cua so nay de tat han)...
timeout /t 10 >nul
goto lap
