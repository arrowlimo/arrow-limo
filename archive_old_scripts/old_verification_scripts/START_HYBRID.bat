@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM ARROW LIMOUSINE - HYBRID SMART LAUNCHER (Windows Batch)
REM Auto-detects network and launches with correct database
REM ═══════════════════════════════════════════════════════════════════════════

cd /d L:\limo
L:\limo\.venv\Scripts\python.exe smart_launcher.py

if errorlevel 1 (
    echo.
    echo ═══════════════════════════════════════════════════════════════════════════
    echo  ERROR: Smart Launcher Failed
    echo ═══════════════════════════════════════════════════════════════════════════
    echo.
    pause
)
