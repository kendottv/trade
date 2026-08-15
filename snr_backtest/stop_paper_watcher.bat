@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "paper" mkdir paper
echo %date% %time% stop watcher >> "paper\scheduled.log"
powershell -NoProfile -WindowStyle Hidden -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'paper_watcher.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
taskkill /F /FI "WINDOWTITLE eq TW Paper Account*" >nul 2>&1
echo %date% %time% stop done >> "paper\scheduled.log"
