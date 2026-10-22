@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git_sync.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if "%~1"=="" pause
exit /b %ERR%
