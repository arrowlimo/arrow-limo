@echo off
REM ===========================================================================
REM Arrow Limousine Desktop App - Direct Launcher
REM Launch from local development environment
REM ===========================================================================

setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"
set "APP_EXE=%ROOT_DIR%ArrowLimousineApp.exe"
set "VENV_ACTIVATE=%ROOT_DIR%.venv\Scripts\activate.bat"
set "MAIN_PY=%ROOT_DIR%desktop_app\main.py"

if exist "%APP_EXE%" (
    title Arrow Limousine Management System
    cd /d "%ROOT_DIR%"
    start "" "%APP_EXE%"
    endlocal
    exit /b 0
)

if not exist "%MAIN_PY%" set "MAIN_PY=%ROOT_DIR%desktop app\main.py"

if not exist "%VENV_ACTIVATE%" set "VENV_ACTIVATE=%ROOT_DIR%venv\Scripts\activate.bat"

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
    echo Hint: If this is a remote install, use the packaged EXE payload so ArrowLimousineApp.exe exists at Y:\limo.
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
