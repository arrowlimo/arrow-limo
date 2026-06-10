@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "DISPATCHER=%SCRIPT_DIR%update_dispatcher.ps1"
set "ARROW_LIMO_NO_PAUSE=1"

REM Pre-flight: check for nested limo folder
if exist "Y:\limo\limo" (
    echo ERROR: Found Y:\limo\limo -- this should not exist. Please remove or rename it so only Y:\limo exists.
    exit /b 1
)

if not exist "%DISPATCHER%" (
    echo ERROR: Installer script not found:
    echo %DISPATCHER%
    exit /b 1
)

if not exist "Y:\" (
    echo ERROR: Y: drive is not accessible in this session.
    echo Map Y: first, then run again.
    exit /b 1
)

echo Starting Arrow Limousine install/update (delta mode)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DISPATCHER%" -SourcePath "%SCRIPT_DIR%" -TargetRoot "Y:\limo" -NoElevation -ShowUi:$false -RunSmokeTest:$true -LaunchApp:$false -FullClean:$false

set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo Install failed with exit code %EXITCODE%.
    echo Check report at Y:\limo\_install_reports\latest_install_report.txt if available.
    echo If no report exists, check for errors above or path issues (Y: not mapped, or Y:\limo\limo exists).
    exit /b %EXITCODE%
)

echo.
echo Install completed.
echo Installed folder: Y:\limo
echo Shortcut target: Y:\limo\START_ARROW_LIMO.bat

rem Sync folders that live in the Dropbox root (not inside update\) but are
rem required by the app. Running via update\ subfolder misses these.
for %%F in (template assets) do (
    if exist "%SCRIPT_DIR%..\%%F" (
        robocopy "%SCRIPT_DIR%..\%%F" "Y:\limo\%%F" /E /R:1 /W:1 /NJH /NJS /NP >nul 2>&1
        echo   Synced: %%F
    )
)

exit /b 0
