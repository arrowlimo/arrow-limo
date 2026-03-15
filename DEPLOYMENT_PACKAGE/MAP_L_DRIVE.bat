@echo off
REM =========================================================
REM MAP L: DRIVE TO DISPATCHMAIN
REM Helper script for DISPATCH1
REM =========================================================

TITLE Map L: Drive to DISPATCHMAIN

COLOR 0B
echo.
echo ========================================================
echo   MAP L: DRIVE TO DISPATCHMAIN
echo ========================================================
echo.
echo This will map the L: drive to \\DISPATCHMAIN\limo
echo.
echo The L: drive provides access to:
echo   - Source code repository
echo   - Deployment packages
echo   - Installation scripts
echo   - Documentation files
echo.
echo ========================================================
echo.

REM Check if L: drive is already mapped
if exist "L:\limo\" (
    COLOR 0A
    echo.
    echo [INFO] L: drive is already mapped to DISPATCHMAIN
    echo.
    net use L: 2>nul | find "\\DISPATCHMAIN\limo"
    echo.
    echo Do you want to disconnect and remap it?
    echo.
    choice /C YN /M "Remap L: drive"
    if errorlevel 2 (
        echo.
        echo Operation cancelled.
        echo.
        pause
        exit /b 0
    )
    
    echo.
    echo Disconnecting current L: drive...
    net use L: /delete /yes >nul 2>&1
)

COLOR 0E
echo.
echo ========================================================
echo   MAPPING L: DRIVE
echo ========================================================
echo.

REM Test if DISPATCHMAIN is reachable
echo Testing connection to DISPATCHMAIN...
ping -n 1 DISPATCHMAIN >nul 2>&1

if errorlevel 1 (
    COLOR 0C
    echo.
    echo ERROR: Cannot reach DISPATCHMAIN
    echo.
    echo Please check:
    echo   1. Is DISPATCHMAIN computer turned on?
    echo   2. Are you on the same network as DISPATCHMAIN?
    echo   3. Is the computer name correct? (DISPATCHMAIN)
    echo.
    echo Try pinging manually:
    echo   ping DISPATCHMAIN
    echo.
    pause
    exit /b 1
)

echo [OK] DISPATCHMAIN is reachable
echo.

REM Map the L: drive
echo Mapping L: drive to \\DISPATCHMAIN\limo...
echo.

net use L: \\DISPATCHMAIN\limo /persistent:yes

if errorlevel 1 (
    COLOR 0C
    echo.
    echo ========================================================
    echo   ERROR: Failed to map L: drive
    echo ========================================================
    echo.
    echo Common causes:
    echo   1. The share "limo" doesn't exist on DISPATCHMAIN
    echo   2. You don't have permission to access the share
    echo   3. Network credentials are required
    echo.
    echo To create the share on DISPATCHMAIN:
    echo   1. Right-click the limo folder
    echo   2. Properties ^> Sharing ^> Advanced Sharing
    echo   3. Check "Share this folder"
    echo   4. Share name: limo
    echo   5. Permissions: Grant access to Everyone or specific users
    echo.
    echo Alternatively, try mapping with credentials:
    echo   net use L: \\DISPATCHMAIN\limo /user:DISPATCHMAIN\username /persistent:yes
    echo.
    pause
    exit /b 1
)

COLOR 0A
echo.
echo ========================================================
echo   SUCCESS!
echo ========================================================
echo.
echo L: drive has been mapped to \\DISPATCHMAIN\limo
echo.
echo Testing access...

if exist "L:\limo\desktop_app\main.py" (
    echo [OK] Can access source code files
    echo.
    echo Available directories:
    dir L:\limo /B
    echo.
    echo ========================================================
    echo.
    echo You can now:
    echo   - Run installation: L:\limo\DEPLOYMENT_PACKAGE\INSTALL_DISPATCH1_ENHANCED.bat
    echo   - Access source code: L:\limo\desktop_app\
    echo   - Read documentation: L:\limo\DEPLOYMENT_PACKAGE\*.md
    echo.
) else (
    COLOR 0E
    echo [WARNING] L: drive is mapped but files are not accessible
    echo.
    echo Check folder structure on DISPATCHMAIN:
    echo   Should have: L:\limo\desktop_app\main.py
    echo.
)

echo ========================================================
echo.
echo L: drive will automatically reconnect on startup.
echo.
pause
