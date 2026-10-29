@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Ghep Chrome tren may tinh voi MinMin VPS ===
.venv\Scripts\python minmin_worker.py ghep-chrome
pause
