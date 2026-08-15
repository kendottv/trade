@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 找不到 .venv
  pause
  exit /b 1
)
echo 更新紙上帳戶...
".venv\Scripts\python.exe" paper_daily.py --live --download
echo.
echo 完成。倉位在 paper\account.json
pause
