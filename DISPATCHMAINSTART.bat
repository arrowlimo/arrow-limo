@echo off
REM ===========================================================================
REM Arrow Limousine Desktop App - Primary Root Launcher
REM Canonical launcher for local development/operations
REM ===========================================================================

TITLE Arrow Limousine Desktop Launcher

echo.
echo ===========================================================================
echo   ARROW LIMOUSINE MANAGEMENT SYSTEM - Desktop Application
echo ===========================================================================
echo.

set "ROOT_DIR=%~dp0"
set "PRIMARY_LAUNCHER=%ROOT_DIR%DEPLOYMENT_PACKAGE\app\START_DISPATCH.bat"
set "FALLBACK_APP_DIR=%ROOT_DIR%desktop_app"
set "VENV_ACTIVATE=%ROOT_DIR%.venv\Scripts\activate.bat"

if exist "%PRIMARY_LAUNCHER%" (
    echo [✓] Using primary launcher:
    echo     %PRIMARY_LAUNCHER%
    echo.
    call "%PRIMARY_LAUNCHER%"
    exit /b %errorlevel%
)

echo [!] Primary launcher not found, using fallback startup...

if exist "%VENV_ACTIVATE%" (
    echo [✓] Activating virtual environment...
    call "%VENV_ACTIVATE%"
) else (
    echo [!] No virtual environment found - using system Python
)

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

if not exist "%FALLBACK_APP_DIR%\main.py" (
    echo [✗] ERROR: Could not find desktop app entrypoint:
    echo     %FALLBACK_APP_DIR%\main.py
    echo.
    pause
    exit /b 1
)

set RECEIPT_WIDGET_WRITE_ENABLED=1
cd /d "%FALLBACK_APP_DIR%"
python main.py

if errorlevel 1 (
    echo.
    echo [✗] Application exited with error
    pause
)
