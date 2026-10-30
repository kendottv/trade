@echo off
setlocal
cd /d "%~dp0"
if not exist "paper" mkdir paper
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" nn_paper.py --daily >> "paper\scheduled.log" 2>&1
