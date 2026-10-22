@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo .venv was not found. Create it in this folder first:
    echo     python -m venv .venv
    echo.
    pause
    exit /b 1
)

echo Installing Python packages into .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

if exist "ThirdParty\instantclient_23_26\oci.dll" (
    echo Oracle Instant Client is already installed.
    goto done
)

echo Downloading Oracle Instant Client
if not exist "ThirdParty" mkdir "ThirdParty"
curl.exe -L --fail --retry 2 -o "ThirdParty\instantclient-basiclite.zip" "https://download.oracle.com/otn_software/nt/instantclient/2326400/instantclient-basiclite-windows.x64-23.26.4.0.0.zip"
if errorlevel 1 goto fail
tar -xf "ThirdParty\instantclient-basiclite.zip" -C "ThirdParty"
del "ThirdParty\instantclient-basiclite.zip"
if not exist "ThirdParty\instantclient_23_26\oci.dll" goto fail

:done
echo.
echo Ready. Restart Reflex with start_reflex.bat.
echo.
pause
exit /b 0

:fail
echo.
echo Setup failed.
echo.
pause
exit /b 1
