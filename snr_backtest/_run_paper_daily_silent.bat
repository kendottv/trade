@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" paper_daily.py --live --download >> "paper\scheduled.log" 2>&1
