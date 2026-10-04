@echo off
REM Live demo: pretend users and collectors use the system so the dashboard map moves.
REM Start the API with start.bat first and keep it running, then double-click this file.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Please run start.bat once first to install everything.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
for /f "tokens=1,* delims==" %%a in ('findstr /b "ADMIN_PASSWORD=" .env') do set ADMIN_PASSWORD=%%b
start "" http://localhost:8000/dashboard
python simulate.py
pause
