@echo off
setlocal
cd /d "C:\Users\AUSER\Desktop\trade\snr_backtest"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=C:\Users\AUSER\Desktop\trade\snr_backtest\.venv\Scripts\python.exe"
"%PY%" -c "import socket;s=socket.socket();r=s.connect_ex(('127.0.0.1',8501));s.close();raise SystemExit(0 if r==0 else 1)"
if %ERRORLEVEL%==0 exit /b 0
start "snr-dashboard" /min "%PY%" -m uvicorn webapp:app --host 127.0.0.1 --port 8501
exit /b 0
