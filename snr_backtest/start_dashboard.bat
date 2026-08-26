@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "paper" mkdir paper
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: missing .venv\Scripts\python.exe
  pause
  exit /b 1
)
"%PY%" -c "import socket;s=socket.socket();r=s.connect_ex(('127.0.0.1',8501));s.close();raise SystemExit(0 if r==0 else 1)"
if errorlevel 1 goto START
echo Already running: http://127.0.0.1:8501
start "" "http://127.0.0.1:8501"
echo Not starting a second server.
pause
exit /b 0
:START
echo Starting dashboard: http://127.0.0.1:8501
echo Keep this window open. Closing it stops the dashboard.
echo.
start "" "http://127.0.0.1:8501"
"%PY%" -m uvicorn webapp:app --host 127.0.0.1 --port 8501
echo Exit code %ERRORLEVEL%
if errorlevel 1 echo FAILED. Keep this screenshot.
pause
