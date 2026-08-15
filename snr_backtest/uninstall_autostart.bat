@echo off
chcp 65001 >nul
set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TW_Paper_Account.bat"
if exist "%DST%" del /F /Q "%DST%"
schtasks /Delete /F /TN "TW_Paper_Account" >nul 2>&1
schtasks /Delete /F /TN "TW_Paper_Start" >nul 2>&1
schtasks /Delete /F /TN "TW_Paper_Stop" >nul 2>&1
echo 已取消開機啟動與平日 08:30 / 16:00 / 22:00 排程。
pause
