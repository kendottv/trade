@echo off
setlocal
cd /d "%~dp0"
if not exist "paper" mkdir paper
echo %date% %time% dashboard start >> "paper\scheduled.log"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo ERROR: missing .venv\Scripts\python.exe
  pause
  exit /b 1
)
netstat -ano | findstr "127.0.0.1:8501" | findstr LISTENING >nul
if %ERRORLEVEL%==0 (
  echo Dashboard already running: http://127.0.0.1:8501
  start "" http://127.0.0.1:8501
  echo.
  echo Not starting a second server.
  pause
  exit /b 0
)
echo Starting dashboard: http://127.0.0.1:8501
echo Keep this window open. Closing it stops the dashboard.
echo.
start "" cmd /c "ping -n 3 127.0.0.1 >nul & start http://127.0.0.1:8501"
"%~dp0.venv\Scripts\python.exe" -m uvicorn webapp:app --host 127.0.0.1 --port 8501
echo.
echo %date% %time% dashboard exit=%ERRORLEVEL% >> "paper\scheduled.log"
echo Exit code %ERRORLEVEL%
if not %ERRORLEVEL%==0 echo FAILED. Screenshot the errors above.
pause