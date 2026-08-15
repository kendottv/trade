@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 找不到 .venv
  exit /b 1
)
if not exist "paper" mkdir paper
echo %date% %time% start: news 08:30 vs last 21:30 >> "paper\scheduled.log"
".venv\Scripts\python.exe" news_risk.py --slot 0830 >> "paper\scheduled.log" 2>&1
if errorlevel 1 echo %date% %time% news_risk 0830 failed, still starting watcher >> "paper\scheduled.log"
".venv\Scripts\python.exe" -c "from datetime import datetime; from zoneinfo import ZoneInfo; open(r'paper\last_news_0830.txt','w',encoding='utf-8').write(datetime.now(ZoneInfo('Asia/Taipei')).strftime('%%Y-%%m-%%d %%H:%%M:%%S'))"
start "TW Paper Account" /min ".venv\Scripts\python.exe" paper_watcher.py
echo %date% %time% watcher launched >> "paper\scheduled.log"
