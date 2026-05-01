@echo off
REM ===========================================================================
REM Arrow Limousine Desktop App - Direct Launcher
REM Launch from local development environment
REM ===========================================================================

setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"
set "VENV_ACTIVATE=%ROOT_DIR%.venv\Scripts\activate.bat"
set "MAIN_PY=%ROOT_DIR%desktop_app\main.py"

if not exist "%VENV_ACTIVATE%" (
    echo.
    echo ERROR: Python virtual environment not found
    echo Expected at: %VENV_ACTIVATE%
    echo.
    pause
    exit /b 1
)

if not exist "%MAIN_PY%" (
    echo.
    echo ERROR: Application entry point not found
    echo Expected at: %MAIN_PY%
    echo.
    pause
    exit /b 1
)

title Arrow Limousine Management System
call "%VENV_ACTIVATE%"
cd /d "%ROOT_DIR%"
python "%MAIN_PY%"

if errorlevel 1 (
    echo.
    echo Application error occurred. Exit code: %errorlevel%
    echo.
    pause
)

endlocal
exit /b 0
