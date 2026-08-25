@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: missing .venv
  pause
  exit /b 1
)
echo Updating paper account...
".venv\Scripts\python.exe" paper_daily.py --live --download
echo.
echo Done. See paper\account.json
pause
