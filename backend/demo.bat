@echo off
REM Plays a complete pickup story and prints each step. Run start.bat once first (it installs packages).
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Please run start.bat once first to install everything.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python demo.py
pause
