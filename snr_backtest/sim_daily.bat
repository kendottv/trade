@echo off
rem NN 模擬送單排程：%1 = open 或 close。只准 simulation。
cd /d C:\Users\AUSER\Desktop\trade\snr_backtest
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe sim_trader.py --auto %1 --retry >> paper_nn\sim_trader.log 2>&1
