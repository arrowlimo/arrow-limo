@echo off
REM Arrow Limousine Desktop App Launcher
REM Double-click this file to start the application

cd /d L:\limo
python -X utf8 desktop_app/main.py

REM If there's an error, pause so user can see it
if errorlevel 1 (
    echo.
    echo ============================================================
    echo Error starting the application. Press any key to close.
    echo ============================================================
    pause
)
