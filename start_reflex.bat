@echo off
cd /d "%~dp0"
echo Starting Reflex. The browser opens at http://localhost:3000/ when the server is ready.
echo If port 3000 is busy, Reflex uses the next free port and opens that address.
".venv\Scripts\reflex.exe" run --env prod --single-port
echo.
pause
