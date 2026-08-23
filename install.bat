@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "DISPATCHER=%SCRIPT_DIR%update_dispatcher.ps1"
set "ARROW_LIMO_NO_PAUSE=1"
set "SOURCE_ROOT=%SCRIPT_DIR%"

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
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '%DISPATCHER%' -SourcePath '%SOURCE_ROOT%' -TargetRoot 'Y:\limo' -NoElevation -ShowUi:$false -RunSmokeTest:$false -LaunchApp:$true -FullClean:$false -ForceInstall -RecentInstallGuardMinutes 0"

set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo Install failed with exit code %EXITCODE%.
    echo Check report at Y:\limo\_install_reports\latest_install_report.txt if available.
    exit /b %EXITCODE%
)

echo winner winner chicken dinner
echo.
echo Install completed.
echo Installed folder: Y:\limo
echo Shortcut target: Y:\limo\START_ARROW_LIMO.bat

exit /b 0
