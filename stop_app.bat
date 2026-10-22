@echo off
cd /d "%~dp0"
echo Stopping Reflex instances of this project.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_app.ps1"
echo.
pause
