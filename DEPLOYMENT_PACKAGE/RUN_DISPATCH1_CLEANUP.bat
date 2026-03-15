@echo off
REM DISPATCH1 NETWORK DRIVE CLEANUP & DESKTOP APP REBUILD
REM Run this as Administrator on dispatch1

setlocal enabledelayedexpansion

echo.
echo ========================================
echo DISPATCH1 CLEANUP & REBUILD
echo ========================================
echo.

REM Check if running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must run as Administrator
    echo.
    echo Right-click this file and select "Run as Administrator"
    pause
    exit /b 1
)

REM Check if L: drive is accessible
if not exist "L:\limo" (
    echo ERROR: L: drive not mapped to \\DISPATCHMAIN\limo
    echo.
    echo Please run this first:
    echo   net use L: \\DISPATCHMAIN\limo /persistent:yes
    echo.
    pause
    exit /b 1
)

echo [STEP 1] Planning cleanup...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'L:\limo\DEPLOYMENT_PACKAGE\DISPATCH1_CLEANUP_AND_REBUILD.ps1'"
echo.
pause

echo [STEP 2] Executing network drive cleanup...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'L:\limo\DEPLOYMENT_PACKAGE\DISPATCH1_EXECUTE_CLEANUP.ps1'"
echo.
pause

echo [STEP 3] Rebuilding desktop app structure...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'L:\limo\DEPLOYMENT_PACKAGE\DISPATCH1_REBUILD_STRUCTURE.ps1'"
echo.
pause

echo.
echo ========================================
echo CLEANUP COMPLETE
echo ========================================
echo.
echo Next steps:
echo   1. Close File Explorer and reopen it
echo   2. Run the test from instructions:
echo      python L:\limo\desktop_app\main.py
echo   3. Verify the desktop app launches
echo   4. If needed, create a desktop shortcut
echo.
echo Full instructions: L:\limo\DEPLOYMENT_PACKAGE\DISPATCH1_CLEANUP_INSTRUCTIONS.md
echo.
pause
