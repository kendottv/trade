@echo off
setlocal
cd /d "%~dp0"
if not exist "paper" mkdir paper
echo %date% %time% kill paper_watcher paper_alert >> "paper\scheduled.log"
powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'paper_watcher\.py' -or $_.CommandLine -match 'paper_alert\.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
taskkill /F /FI "WINDOWTITLE eq TW Paper Account*" >nul 2>&1
echo %date% %time% kill done >> "paper\scheduled.log"
exit /b 0
