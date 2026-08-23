@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "paper" mkdir paper
echo %date% %time% dashboard start >> "paper\scheduled.log"
if not exist "%~dp0.venv\Scripts\streamlit.exe" (
  echo 尚未安裝 streamlit。請先在 snr_backtest 執行：
  echo   .venv\Scripts\python -m pip install streamlit
  pause
  exit /b 1
)
echo 瀏覽器會開 http://localhost:8501
"%~dp0.venv\Scripts\streamlit.exe" run "%~dp0dashboard.py" --server.headless false --browser.gatherUsageStats false --server.port 8501 --server.address 127.0.0.1
echo %date% %time% dashboard exit=%ERRORLEVEL% >> "paper\scheduled.log"
