@echo off
set "ROOT_LAUNCHER=%~dp0..\..\DISPATCHMAINSTART.bat"
if exist "%ROOT_LAUNCHER%" (
    call "%ROOT_LAUNCHER%"
    exit /b %errorlevel%
)

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

REM Resolve the active project root and desktop app path
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%..\.."
set "APP_DIR=%ROOT_DIR%\desktop_app"
set "VENV_ACTIVATE=%ROOT_DIR%\.venv\Scripts\activate.bat"

if not exist "%APP_DIR%\main.py" (
    REM Fallback for legacy layout where desktop_app may be next to this launcher
    set "APP_DIR=%SCRIPT_DIR%desktop_app"
    set "VENV_ACTIVATE=%SCRIPT_DIR%.venv\Scripts\activate.bat"
)

REM Check if virtual environment exists
if exist "%VENV_ACTIVATE%" (
    echo [✓] Activating virtual environment...
    call "%VENV_ACTIVATE%"
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
if not exist "%APP_DIR%\main.py" (
    echo [✗] ERROR: Could not find desktop app main.py
    echo     Checked: "%APP_DIR%\main.py"
    echo.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"
python main.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo [✗] Application exited with error
    pause
)
