@echo off
setlocal
set "HERE=%~dp0"
cd /d "%HERE%"
if not exist "paper" mkdir paper
echo %date% %time% START cwd=%CD% here=%HERE% >> "paper\scheduled.log"
if not exist "%HERE%.venv\Scripts\python.exe" (
  echo %date% %time% ERROR no venv >> "paper\scheduled.log"
  exit /b 1
)
call "%HERE%_kill_paper_jobs.bat"
echo %date% %time% start watcher >> "paper\scheduled.log"
start "TW Paper Account" /min "%HERE%.venv\Scripts\python.exe" "%HERE%paper_watcher.py"
echo %date% %time% watcher launched exit=0 >> "paper\scheduled.log"
exit /b 0

