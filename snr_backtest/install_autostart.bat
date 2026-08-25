@echo off
setlocal
cd /d "%~dp0"
set "HERE=%~dp0"
set "HERE=%HERE:~0,-1%"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "DST=%STARTUP%\TW_Paper_Account.bat"
if exist "%DST%" del /F /Q "%DST%"
schtasks /Create /F /TN "TW_Paper_Start" /TR "cmd.exe /c \"%HERE%\start_paper_watcher.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:30 /RL LIMITED
schtasks /Create /F /TN "TW_Paper_Stop" /TR "cmd.exe /c \"%HERE%\stop_paper_watcher.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 22:00 /RL LIMITED
schtasks /Create /F /TN "TW_Paper_Account" /TR "cmd.exe /c \"%HERE%\_run_paper_daily_silent.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:00 /RL LIMITED
schtasks /Create /F /TN "TW_News_0830" /TR "cmd.exe /c \"%HERE%\run_news_0830.bat\"" /SC DAILY /ST 08:30 /RL LIMITED
schtasks /Create /F /TN "TW_News_2130" /TR "cmd.exe /c \"%HERE%\run_news_2130.bat\"" /SC DAILY /ST 21:30 /RL LIMITED
schtasks /Create /F /TN "TW_Git_Daily" /TR "cmd.exe /c \"%HERE%\git_daily.bat\"" /SC DAILY /ST 21:55 /RL LIMITED
echo Removed startup shortcut.
echo Daily 08:30 news: TW_News_0830
echo Daily 21:30 news: TW_News_2130
echo Daily 21:55 git: TW_Git_Daily
echo Weekday 08:30 watcher: TW_Paper_Start
echo Weekday 16:00 live: TW_Paper_Account
echo Weekday 22:00 stop: TW_Paper_Stop
echo.
echo Starting watcher once...
call "%HERE%\start_paper_watcher.bat"
echo Done.
pause
