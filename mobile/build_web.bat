@echo off
REM Rebuilds the browser version of the app and copies it into the backend (served at /app).
cd /d "%~dp0"
call flutter build web --release --base-href /app/ || exit /b 1
if exist ..\backend\webapp rmdir /s /q ..\backend\webapp
robocopy build\web ..\backend\webapp /E /XD canvaskit >nul
echo Done. Restart start.bat and open http://localhost:8000/app
