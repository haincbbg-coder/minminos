@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Cai dat MinMin Worker ===
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Chua co Python. Tai Python 3.11+ o https://www.python.org/downloads/ ^(tick "Add to PATH"^) roi chay lai. & pause & exit /b 1)
if not exist .venv %PY% -m venv .venv
call .venv\Scripts\python -m pip install --upgrade pip >nul
call .venv\Scripts\python -m pip install -r requirements.txt || (echo Cai thu vien loi. & pause & exit /b 1)
echo.
echo Xong. Tiep theo: chay ghep-may.bat va nhap ma 6 so tu trang Doi Social.
pause
