@echo off
set "PROJ=C:\Users\parkd\new project\Transport-gap-audit"
set "PY_EXE=C:\Users\parkd\AppData\Local\Programs\Python\Python312\python.exe"
cd /d "%PROJ%" || exit /b 1
echo ==== %DATE% %TIME% ==== >> "%PROJ%\scratch\_task_log.txt"
"%PY_EXE%" -m src.collectors.arrival_snapshot >> "%PROJ%\scratch\_task_log.txt" 2>&1
exit /b %ERRORLEVEL%
