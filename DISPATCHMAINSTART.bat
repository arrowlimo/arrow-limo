@echo off
REM ===========================================================================
REM Arrow Limousine Desktop App - Development Launcher
REM Quick start script for running the PyQt6 desktop application in development
REM ===========================================================================

echo.
echo ===========================================================================
echo   ARROW LIMOUSINE MANAGEMENT SYSTEM - Desktop Application
echo ===========================================================================
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    echo [✓] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo [✓] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [!] No virtual environment found - using system Python
)

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [✗] ERROR: Python is not installed or not in PATH!
    echo     Please install Python 3.10+ from python.org
    echo.
    pause
    exit /b 1
)

echo [✓] Python found
echo [✓] Starting desktop application...
echo.

set RECEIPT_WIDGET_WRITE_ENABLED=1

REM Run the desktop app
cd desktop_app
python main.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo [✗] Application exited with error
    pause
)
