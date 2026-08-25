@echo off
setlocal
set "HERE=%~dp0"
cd /d "%HERE%"
if not exist "paper" mkdir paper
echo %date% %time% NEWS 2130 cwd=%CD% >> "paper\scheduled.log"
if not exist "%HERE%.venv\Scripts\python.exe" (
  echo %date% %time% ERROR no venv >> "paper\scheduled.log"
  exit /b 1
)
"%HERE%.venv\Scripts\python.exe" "%HERE%news_risk.py" --slot 2130 >> "paper\scheduled.log" 2>&1
echo %date% %time% NEWS 2130 done err=%ERRORLEVEL% >> "paper\scheduled.log"
exit /b 0
