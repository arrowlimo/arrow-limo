@echo off
echo ============================================
echo   Arrow Limousine Dispatch Installer
echo ============================================
echo.
echo This will install the dispatch software and
echo connect to the central database.
echo.
echo Press any key to continue or close this window to cancel...
pause >nul

echo.
echo Requesting administrator privileges...
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0DispatchInstaller.ps1""' -Verb RunAs}"

echo.
echo Installation started in administrator window.
echo.
pause
