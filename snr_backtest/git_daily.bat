@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "HERE=%~dp0"
set "REPO=%HERE%.."
cd /d "%REPO%"
if not exist "%HERE%paper" mkdir "%HERE%paper"
echo %date% %time% git_daily start cwd=%CD% >> "%HERE%paper\scheduled.log"
if not exist ".git" (
  echo %date% %time% git_daily ERROR no .git in %CD% >> "%HERE%paper\scheduled.log"
  exit /b 1
)
set "PATH=C:\Program Files\Git\cmd;%PATH%"
set "GIT_TERMINAL_PROMPT=0"
set "MSG="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "MSG=%%i"
if not defined MSG (
  echo %date% %time% git_daily ERROR no date >> "%HERE%paper\scheduled.log"
  exit /b 1
)

git add .
if errorlevel 1 (
  echo %date% %time% git_daily ERROR git add >> "%HERE%paper\scheduled.log"
  exit /b 1
)

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "%MSG%"
  if errorlevel 1 (
    echo %date% %time% git_daily ERROR git commit >> "%HERE%paper\scheduled.log"
    exit /b 1
  )
  echo %date% %time% git_daily committed %MSG% >> "%HERE%paper\scheduled.log"
) else (
  echo %date% %time% git_daily nothing to commit >> "%HERE%paper\scheduled.log"
)

git push
if errorlevel 1 (
  echo %date% %time% git_daily ERROR git push >> "%HERE%paper\scheduled.log"
  exit /b 1
)
echo %date% %time% git_daily push ok >> "%HERE%paper\scheduled.log"
exit /b 0
