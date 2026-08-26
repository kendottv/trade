@echo off
setlocal
cd /d "%~dp0"
if not exist "paper" mkdir paper
echo %date% %time% git before stop >> "paper\scheduled.log"
call "%~dp0git_daily.bat"
echo %date% %time% git_daily exit=%ERRORLEVEL% >> "paper\scheduled.log"
echo %date% %time% stop watcher >> "paper\scheduled.log"
call "%~dp0_kill_paper_jobs.bat"
echo %date% %time% stop done >> "paper\scheduled.log"
