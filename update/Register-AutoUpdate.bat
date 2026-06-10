@echo off
rem ============================================================
rem  Register-AutoUpdate.bat
rem  Run ONCE on each remote PC to set up the auto-update watcher.
rem  Must be run as Administrator.
rem ============================================================
setlocal

set "INSTALL_ROOT=Y:\limo"
set "SCRIPT=%INSTALL_ROOT%\update\Watch-DropboxDeploy.ps1"
set "TASK_NAME=Arrow Limo Auto-Update Watcher"

echo.
echo ============================================================
echo  Arrow Limousine - Register Auto-Update Watcher
echo ============================================================
echo.
echo This will create a Windows Scheduled Task that:
echo   - Starts automatically when Windows starts
echo   - Monitors Dropbox for new app deploys
echo   - Installs updates automatically 15 minutes after download
echo.
echo Task name : %TASK_NAME%
echo Script    : %SCRIPT%
echo.

if not exist "%SCRIPT%" (
    echo [ERROR] Script not found: %SCRIPT%
    echo         Run install.bat first.
    pause
    exit /b 1
)

rem Delete existing task if present
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

rem Create the task: run at startup, as current user, no window
schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%SCRIPT%\"" ^
  /SC ONSTART ^
  /DELAY 0002:00 ^
  /RU "%USERDOMAIN%\%USERNAME%" ^
  /RL HIGHEST ^
  /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Scheduled task created.
    echo.
    echo Starting watcher now (also runs automatically on next reboot)...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT%"
    echo [OK] Watcher running in background.
) else (
    echo.
    echo [ERROR] Failed to create scheduled task. Make sure you ran as Administrator.
)

echo.
pause
