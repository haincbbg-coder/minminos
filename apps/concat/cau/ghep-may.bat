@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || if exist "%USERPROFILE%\Documents\MinMinWorker\.venv\Scripts\python.exe" set PY="%USERPROFILE%\Documents\MinMinWorker\.venv\Scripts\python.exe"
%PY% --version >nul 2>nul || (echo Chua co Python. Tai Python 3.11+ o https://www.python.org/downloads/ ^(tick "Add to PATH"^) roi chay lai. & pause & exit /b 1)
set /p URL=Dia chi MinMin (vd https://minmin.elaria.cloud): 
set /p MA=Ma ghep 6 so: 
%PY% concat_cau.py ghep %URL% %MA%
pause
