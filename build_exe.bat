@echo off
REM Arrow Limousine Desktop App - Build Batch File
REM This file makes it easy to build the exe on Windows without needing PowerShell

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ════════════════════════════════════════════════════════════════
echo   Arrow Limousine Desktop App - Building Windows Executable
echo ════════════════════════════════════════════════════════════════
echo.

REM Check if venv exists
if not exist ".\.venv\Scripts\python.exe" (
    echo ✗ Virtual environment not found!
    echo.
    echo Run these commands first:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking PyInstaller...
.\.venv\Scripts\pip install -q pyinstaller >nul 2>&1
if errorlevel 1 (
    echo ✗ Failed to install PyInstaller
    pause
    exit /b 1
)
echo ✓ PyInstaller ready

echo [2/4] Checking .env file...
if not exist ".\.env" (
    echo ! Creating .env from .env.example
    if exist ".\.env.example" (
        copy ".\.env.example" ".\.env" >nul
        echo ✓ .env created - EDIT WITH YOUR DATABASE CREDENTIALS
    ) else (
        echo ✗ .env.example not found
        pause
        exit /b 1
    )
) else (
    echo ✓ .env found
)

echo [3/4] Cleaning old builds...
if exist ".\build" rmdir /s /q ".\build" >nul 2>&1
if exist ".\dist" rmdir /s /q ".\dist" >nul 2>&1
echo ✓ Clean build directory

echo [4/4] Building executable...
echo     Please wait - this may take 2-5 minutes...
echo.

.\.venv\Scripts\pyinstaller.exe build_desktop_app.spec --noconfirm --log-level=INFO

if errorlevel 1 (
    echo.
    echo ✗ Build failed! Check errors above.
    pause
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════════════════════
echo   ✓ BUILD SUCCESSFUL!
echo.
echo   Location: .\dist\ArrowLimousineApp.exe
echo.
echo   Next steps:
echo   1. Copy .\dist\ArrowLimousineApp.exe to dispatcher
echo   2. Include .env.example file
echo   3. Include DISPATCHER_SETUP.md for instructions
echo   4. Dispatcher edits .env with their credentials
echo   5. Dispatcher runs ArrowLimousineApp.exe
echo ════════════════════════════════════════════════════════════════
echo.

REM Create deployment folder
if not exist ".\dist\ArrowLimousine_Deployment" mkdir ".\dist\ArrowLimousine_Deployment"
copy ".\dist\ArrowLimousineApp.exe" ".\dist\ArrowLimousine_Deployment\" >nul
copy ".\.env.example" ".\dist\ArrowLimousine_Deployment\" >nul
copy ".\DISPATCHER_SETUP.md" ".\dist\ArrowLimousine_Deployment\" >nul

echo ✓ Deployment package created at: .\dist\ArrowLimousine_Deployment
echo.
echo Ready to distribute!
echo.
pause
