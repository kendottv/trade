@echo off
rem NN sim order schedule: %1 = open or close. Simulation only.
cd /d C:\Users\AUSER\Desktop\trade\snr_backtest
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe sim_trader.py --auto %1 --retry >> paper_nn\sim_trader.log 2>&1
