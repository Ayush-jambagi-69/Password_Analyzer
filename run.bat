@echo off
setlocal
cd /d "%~dp0"
title PasswordLab launcher
set "PORT=5000"
set "URL=http://127.0.0.1:%PORT%"

echo ==== PasswordLab ====

rem --- 1. Is the server already running? Then just open the browser (no duplicate instance).
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing '%URL%/api/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo PasswordLab is already running at %URL%. Opening the browser.
    start "" "%URL%"
    exit /b 0
)

rem --- 2. Find Python 3
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY goto :nopython

rem --- 3. Create the virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto :venvfail
)

rem --- 4. Activate it and install dependencies
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :venvfail
echo Installing dependencies from backend\requirements.txt ...
python -m pip install --disable-pip-version-check -q -r backend\requirements.txt
if errorlevel 1 goto :pipfail

rem --- 5. Start the server in its own window so errors stay visible
echo Starting server ...
start "PasswordLab server (close this window to stop)" cmd /k ""%~dp0.venv\Scripts\python.exe" "%~dp0backend\app.py" %PORT%"

rem --- 6. Wait until the server answers, then open the browser
powershell -NoProfile -Command "for ($i=0; $i -lt 40; $i++) { try { Invoke-WebRequest -UseBasicParsing '%URL%/api/health' -TimeoutSec 1 | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 goto :startfail
echo Server is ready. Opening %URL%
start "" "%URL%"
exit /b 0

:nopython
echo.
echo [ERROR] Python 3 was not found.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer,
echo then run this file again.
pause
exit /b 1

:venvfail
echo.
echo [ERROR] Could not create or activate the virtual environment .venv
echo Delete the .venv folder and run this file again.
pause
exit /b 1

:pipfail
echo.
echo [ERROR] Installing dependencies failed. Check your internet connection and try again.
pause
exit /b 1

:startfail
echo.
echo [ERROR] The server did not start. Read the message in the "PasswordLab server" window.
echo If port %PORT% is used by another program, close it or run: python backend\app.py 5001
pause
exit /b 1
