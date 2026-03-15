@echo off
REM =========================================================
REM Arrow Limousine Dispatch - Desktop Startup Script
REM For DISPATCH1 Computer
REM =========================================================
REM 
REM This file should be placed on the Desktop or in:
REM Y:\ArrowLimo\app\
REM 
REM Create desktop shortcut to this file for easy access
REM =========================================================

TITLE Arrow Limousine Dispatch - DISPATCH1
COLOR 0A

echo.
echo ========================================================
echo   ARROW LIMOUSINE MANAGEMENT SYSTEM
echo   DISPATCH1 Workstation
echo ========================================================
echo.

REM ========================================================
REM STEP 1: Verify Y: Drive Installation Exists
REM ========================================================
echo [1/4] Checking local installation...

if not exist "Y:\ArrowLimo\app" (
    COLOR 0C
    echo.
    echo ERROR: Local installation not found!
    echo.
    echo Expected location: Y:\ArrowLimo\app
    echo.
    echo Please run the installer first:
    echo   L:\limo\DEPLOYMENT_PACKAGE\INSTALL_DISPATCH1_Y_DRIVE.bat
    echo.
    pause
    exit /b 1
)

echo       [OK] Installation found at Y:\ArrowLimo\app
echo.

REM ========================================================
REM STEP 2: Verify Network Access to DISPATCHMAIN
REM ========================================================
echo [2/4] Checking network connection to DISPATCHMAIN...

REM Test if L: drive is accessible
if exist "L:\limo\" (
    echo       [OK] L: drive connected to DISPATCHMAIN
) else (
    COLOR 0E
    echo       [WARNING] L: drive not connected
    echo.
    echo       Attempting to connect...
    
    REM Try to map L: drive
    net use L: \\DISPATCHMAIN\limo /persistent:yes >nul 2>&1
    
    if exist "L:\limo\" (
        echo       [OK] L: drive connected successfully
    ) else (
        COLOR 0C
        echo       [ERROR] Cannot connect to DISPATCHMAIN
        echo.
        echo       Please check:
        echo       - Is DISPATCHMAIN computer turned on?
        echo       - Are you on the same network?
        echo       - Can you ping DISPATCHMAIN? (run: ping DISPATCHMAIN)
        echo.
        echo       To manually map L: drive:
        echo       net use L: \\DISPATCHMAIN\limo /persistent:yes
        echo.
        pause
        exit /b 1
    )
)

echo.

REM ========================================================
REM STEP 3: Check for Updates from DISPATCHMAIN
REM ========================================================
echo [3/4] Checking for application updates...

if exist "L:\limo\DEPLOYMENT_PACKAGE\app\desktop_app\main.py" (
    REM Compare file timestamps - if L: drive version is newer, auto-update
    for %%A in ("Y:\ArrowLimo\app\desktop_app\main.py") do set Y_DATE=%%~tA
    for %%A in ("L:\limo\DEPLOYMENT_PACKAGE\app\desktop_app\main.py") do set L_DATE=%%~tA
    
    if not "%Y_DATE%"=="%L_DATE%" (
        echo       [UPDATE] New code detected on DISPATCHMAIN
        echo       Updating local copy...
        
        REM Copy updated files from L: to Y:
        xcopy /E /I /Y /Q "L:\limo\DEPLOYMENT_PACKAGE\app\desktop_app\*.py" "Y:\ArrowLimo\app\desktop_app\" >nul 2>&1
        
        if errorlevel 1 (
            COLOR 0E
            echo       [WARNING] Auto-update failed, continuing with existing code
        ) else (
            COLOR 0A
            echo       [OK] Application updated successfully
        )
    ) else (
        echo       [OK] Application is up to date
    )
) else (
    COLOR 0E
    echo       [WARNING] Cannot check for updates (L: drive not accessible)
    echo       Continuing with local copy...
)

echo.

REM ========================================================
REM STEP 4: Launch Application
REM ========================================================
echo [4/4] Starting Arrow Limousine application...
echo.

REM Change to the application directory (critical for imports to work)
cd /d "Y:\ArrowLimo\app"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    COLOR 0C
    echo.
    echo ========================================================
    echo ERROR: Python is not installed!
    echo ========================================================
    echo.
    echo Please install Python 3.10 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

COLOR 0B
echo ========================================================
echo   LAUNCHING APPLICATION...
echo ========================================================
echo.
echo Current directory: %CD%
echo.
echo Application will open in a new window.
echo This console will remain open for error messages.
echo.
echo ========================================================
echo.

REM Launch the Python launcher
python launcher.py

REM If the application exits, show this message
echo.
echo ========================================================
echo   APPLICATION CLOSED
echo ========================================================
echo.

if errorlevel 1 (
    COLOR 0C
    echo Application exited with an error. 
    echo Check the error messages above.
    echo.
    echo For help, see: Y:\ArrowLimo\READ_ME_FIRST.md
    echo.
) else (
    COLOR 0A
    echo Application exited normally.
    echo.
)

pause
