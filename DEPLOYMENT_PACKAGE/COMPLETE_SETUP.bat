@echo off
echo ============================================
echo   Arrow Limousine - Complete Setup
echo   ALL-IN-ONE INSTALLER
echo ============================================
echo.
echo This will install everything needed:
echo   1. Python 3.11
echo   2. Required packages (psycopg2, PyQt5)
echo   3. Arrow Limousine application
echo   4. Network drive mapping (Z:)
echo   5. Desktop shortcuts
echo.
echo This computer: %COMPUTERNAME%
echo Will connect to: DISPATCHMAIN
echo.
pause

echo.
echo ============================================
echo STEP 1: Installing Python
echo ============================================
echo.

REM Check if Python already installed
python --version >nul 2>&1
if not errorlevel 1 (
    echo Python is already installed!
    python --version
    goto :skip_python
)

echo Downloading Python 3.11...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe' -OutFile '%TEMP%\python-installer.exe'}"

if errorlevel 1 (
    echo [WARNING] Download failed! You may need to install Python manually.
    echo Continuing anyway...
    goto :skip_python
)

echo Installing Python (this takes 2-3 minutes)...
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

REM Refresh environment
set PATH=%PATH%;C:\Program Files\Python311;C:\Program Files\Python311\Scripts

:skip_python

echo.
echo ============================================
echo STEP 2: Installing Python Packages
echo ============================================
echo.

python -m pip install --upgrade pip --quiet
python -m pip install psycopg2-binary PyQt5 --quiet

if errorlevel 1 (
    echo [WARNING] Package installation had errors
    echo The app may not work properly
    pause
)

echo [OK] Packages installed!

echo.
echo ============================================
echo STEP 3: Installing Arrow Limousine App
echo ============================================
echo.

REM Run the main installer
PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& {Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0DispatchInstaller.ps1""' -Verb RunAs -Wait}"

echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Next Steps:
echo   1. Look for "Arrow Limousine Dispatch" on your desktop
echo   2. Double-click to launch the application
echo   3. Verify Z: drive is accessible in File Explorer
echo.
echo If you have any issues:
echo   - Make sure DISPATCHMAIN computer is on
echo   - Check network connection
echo   - Contact IT support
echo.
pause
