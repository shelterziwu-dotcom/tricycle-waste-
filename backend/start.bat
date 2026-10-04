@echo off
REM TriCycle Waste backend - double-click to start (Windows).
REM WAMP only provides the MySQL database; this window runs the Python API.
cd /d "%~dp0"
title TriCycle Waste API

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Install Python 3.11 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Creating Python environment, first run only...
  %PY% -m venv .venv
)
call ".venv\Scripts\activate.bat"

echo Installing / checking packages...
python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Package installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example - edit it if your MySQL password is not empty.
)

echo.
echo  ================================================================
echo   TriCycle Waste API is starting. Make sure WAMP is running (green).
echo   Open in your browser:  http://localhost:8000/docs
echo   Keep this window open. Press Ctrl+C to stop.
echo  ================================================================
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
