@echo off
setlocal
set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TW_Paper_Account.bat"
if exist "%DST%" del /F /Q "%DST%"
schtasks /Delete /F /TN "TW_Paper_Account" >nul 2>&1
schtasks /Delete /F /TN "TW_Paper_Start" >nul 2>&1
schtasks /Delete /F /TN "TW_Paper_Stop" >nul 2>&1
schtasks /Delete /F /TN "TW_News_0830" >nul 2>&1
schtasks /Delete /F /TN "TW_News_2130" >nul 2>&1
schtasks /Delete /F /TN "TW_Git_Daily" >nul 2>&1
echo Removed scheduled tasks.
pause
