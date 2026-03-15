@echo off
REM =========================================================
REM Arrow Limousine Dispatch Launcher
REM Simple startup from Y:\ArrowLimo\app folder
REM =========================================================

TITLE Arrow Limousine Dispatch
echo.
echo ========================================================
echo   ARROW LIMOUSINE MANAGEMENT SYSTEM
echo ========================================================
echo.
echo Starting Arrow Limousine Dispatch...
echo.

REM Critical: Change to this directory first
REM This ensures relative paths work correctly
cd /d "%~dp0"

echo Current directory: %CD%
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    COLOR 0C
    echo ========================================================
    echo ERROR: Python is not installed!
    echo ========================================================
    echo.
    echo Please install Python 3.10 or higher from python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

REM Verify launcher.py exists
if not exist "launcher.py" (
    COLOR 0C
    echo ========================================================
    echo ERROR: launcher.py not found!
    echo ========================================================
    echo.
    echo Current directory: %CD%
    echo Expected file: %CD%\launcher.py
    echo.
    echo Please reinstall or copy files from:
    echo L:\limo\DEPLOYMENT_PACKAGE\app
    echo.
    pause
    exit /b 1
)

REM Run the launcher
echo Launching application...
echo.
python launcher.py

REM Show exit status
echo.
if errorlevel 1 (
    COLOR 0C
    echo ========================================================
    echo Application exited with errors
    echo ========================================================
    echo.
    echo Check the error messages above
    echo.
) else (
    echo ========================================================
    echo Application closed normally
    echo ========================================================
    echo.
)

pause
