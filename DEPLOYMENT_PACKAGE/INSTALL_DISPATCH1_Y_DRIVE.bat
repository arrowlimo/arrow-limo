@echo off
echo ============================================
echo   Arrow Limousine Dispatch1 Installer
echo   Installing to Y: Drive
echo ============================================
echo.
echo This will install to Y:\ArrowLimo and configure
echo auto-update from the main development computer.
echo.
echo Press any key to continue or close this window to cancel...
pause >nul

echo.
echo Requesting administrator privileges...
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0DispatchInstaller_Dispatch1.ps1""' -Verb RunAs}"

echo.
echo Installation started in administrator window.
echo.
pause
