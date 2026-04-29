@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python runtime not found at %PYTHON_EXE%
    echo Reinstall Arrow Limo Offsite or restore the bundled runtime.
    pause
    exit /b 1
)

if not exist "%~dp0launcher.py" (
    echo launcher.py not found in %~dp0
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0launcher.py"
exit /b %ERRORLEVEL%