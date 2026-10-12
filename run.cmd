@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 cold_chain_watch.py
) else (
  where python >nul 2>nul
  if errorlevel 1 goto no_python
  python cold_chain_watch.py
)
if errorlevel 1 goto failed
start "" "%~dp0dashboard.html"
exit /b 0

:no_python
echo Python 3 was not found. Install Python 3.10 or newer, then run this file again.
pause
exit /b 1

:failed
echo The project did not finish successfully. Read the error above.
pause
exit /b 1
