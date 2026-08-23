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
echo Starting dashboard: http://127.0.0.1:8501
echo Keep this window open. Closing it stops the dashboard.
echo.
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0dashboard.py" --server.headless false --browser.gatherUsageStats false --server.port 8501 --server.address 127.0.0.1
echo.
echo %date% %time% dashboard exit=%ERRORLEVEL% >> "paper\scheduled.log"
echo Exit code %ERRORLEVEL%
if not %ERRORLEVEL%==0 echo FAILED. Screenshot the errors above.
pause