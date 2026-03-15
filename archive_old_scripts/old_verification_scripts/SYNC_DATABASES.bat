@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM DATABASE SYNC UTILITY - Easy Launcher
REM Sync between local PostgreSQL and Neon cloud
REM ═══════════════════════════════════════════════════════════════════════════

cd /d L:\limo
python database_sync.py

if errorlevel 1 (
    echo.
    echo ═══════════════════════════════════════════════════════════════════════════
    echo  ERROR: Database Sync Failed
    echo ═══════════════════════════════════════════════════════════════════════════
    echo.
    pause
)
