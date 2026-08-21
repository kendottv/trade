@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "HERE=%~dp0"
set "HERE=%HERE:~0,-1%"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "DST=%STARTUP%\TW_Paper_Account.bat"

rem 不再開機自啟，改平日 08:30 啟動、22:00 關閉
if exist "%DST%" del /F /Q "%DST%"

schtasks /Create /F /TN "TW_Paper_Start" /TR "cmd.exe /c \"%HERE%\start_paper_watcher.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:30 /RL LIMITED
schtasks /Create /F /TN "TW_Paper_Stop" /TR "cmd.exe /c \"%HERE%\stop_paper_watcher.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 22:00 /RL LIMITED
schtasks /Create /F /TN "TW_Paper_Account" /TR "cmd.exe /c \"%HERE%\_run_paper_daily_silent.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:00 /RL LIMITED
schtasks /Create /F /TN "TW_News_0830" /TR "cmd.exe /c \"%HERE%\run_news_0830.bat\"" /SC DAILY /ST 08:30 /RL LIMITED
schtasks /Create /F /TN "TW_News_2130" /TR "cmd.exe /c \"%HERE%\run_news_2130.bat\"" /SC DAILY /ST 21:30 /RL LIMITED
schtasks /Create /F /TN "TW_Git_Daily" /TR "cmd.exe /c \"%HERE%\git_daily.bat\"" /SC DAILY /ST 21:55 /RL LIMITED

echo 已取消開機啟動。
echo 已設定每天 08:30 新聞：TW_News_0830
echo 已設定每天 21:30 新聞：TW_News_2130
echo 已設定每天 21:55 git add/commit/push：TW_Git_Daily
echo 已設定平日 08:30 啟動 watcher：TW_Paper_Start
echo 已設定平日 16:00 收盤單：TW_Paper_Account
echo 已設定平日 22:00 關閉：TW_Paper_Stop
echo.
echo 現在啟動一次監看（含抓新聞）...
call "%HERE%\start_paper_watcher.bat"
echo 完成。
pause
