@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p URL=Dia chi MinMin (vd https://minmin.elaria.cloud): 
set /p MA=Ma ghep 6 so: 
.venv\Scripts\python minmin_worker.py ghep %URL% %MA%
pause
