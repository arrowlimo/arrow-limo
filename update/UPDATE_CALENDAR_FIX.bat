@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "DISPATCHER=%SCRIPT_DIR%update_dispatcher.ps1"
set "ARROW_LIMO_NO_PAUSE=1"

if not exist "%DISPATCHER%" (
    echo ERROR: Update dispatcher not found:
    echo %DISPATCHER%
    exit /b 1
)

if not exist "Y:\" (
    echo ERROR: Y: drive is not accessible in this session.
    echo Map Y: first, then run again.
    exit /b 1
)

echo Applying Arrow Limousine calendar fix update...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DISPATCHER%" -SourcePath "%SCRIPT_DIR%" -TargetRoot "Y:\limo" -NoElevation -ShowUi:$false -RunSmokeTest:$true -LaunchApp:$false

set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo Update failed with exit code %EXITCODE%.
    echo Check report at Y:\limo\_install_reports\latest_install_report.txt if available.
    exit /b %EXITCODE%
)

echo.
echo Update completed.
echo Target: Y:\limo
echo Shortcut target: Y:\limo\START_ARROW_LIMO.bat
exit /b 0