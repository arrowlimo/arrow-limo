@echo off
REM =================================================================
REM Automatic Receipt Widget Cleanup Script
REM Run this to automatically improve the receipt management system
REM while you sleep - no interaction needed!
REM =================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  AUTOMATIC RECEIPT WIDGET CLEANUP
echo ============================================================
echo.
echo Starting automatic improvements...
echo All output will be logged to: L:\limo\logs\receipt_cleanup_auto.log
echo.
echo.

REM Create logs directory if needed
if not exist "L:\limo\logs" mkdir "L:\limo\logs"

REM Run the Python automation script
python -X utf8 "L:\limo\scripts\auto_receipt_widget_cleanup.py"

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo  SUCCESS! Check the log file for details.
    echo ============================================================
    echo.
    timeout /t 10
) else (
    echo.
    echo ============================================================
    echo  ERROR! Check the log file for details.
    echo ============================================================
    echo.
    timeout /t 10
)
