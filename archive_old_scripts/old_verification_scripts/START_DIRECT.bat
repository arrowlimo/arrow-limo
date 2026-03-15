@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM ARROW LIMOUSINE - DIRECT LAUNCHER
REM Launches the desktop application directly
REM ═══════════════════════════════════════════════════════════════════════════

cd /d L:\limo\desktop_app
L:\limo\.venv\Scripts\python.exe main.py

if errorlevel 1 (
    echo.
    echo ═══════════════════════════════════════════════════════════════════════════
    echo  ERROR: Application Failed to Launch
    echo ═══════════════════════════════════════════════════════════════════════════
    echo.
    echo Possible issues:
    echo  1. Database password incorrect - run: L:\limo\diagnose_connection.py
    echo  2. PostgreSQL not running - run: Start-Service postgresql-x64-17
    echo.
    pause
)
