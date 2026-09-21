@echo off
setlocal
cd /d "%~dp0"
title Corporate Filings Downloader - starting...

where python >nul 2>nul
if errorlevel 1 goto NOPYTHON

python -c "import sys" >nul 2>nul
if errorlevel 1 goto NOPYTHON

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup - this only happens once, please wait...
    python -m venv .venv
    if errorlevel 1 goto NOPYTHON
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "gui.py"
) else (
    ".venv\Scripts\python.exe" "gui.py"
)
goto END

:NOPYTHON
echo.
echo  =========================================================
echo   Python is not installed on this computer (or was only
echo   partially set up).
echo.
echo   1. Go to https://www.python.org/downloads/
echo   2. Download and run the installer.
echo   3. On the FIRST screen, tick "Add python.exe to PATH"
echo      before clicking Install.
echo   4. Once it finishes, double-click this file again.
echo  =========================================================
echo.
pause

:END
endlocal
