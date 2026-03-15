@echo off
REM =========================================================
REM DISPATCH1 INSTALLATION SCRIPT (Enhanced)
REM Installs Arrow Limousine to Y:\ArrowLimo
REM =========================================================
REM 
REM IMPORTANT: Run this from L: drive, not UNC path!
REM Correct:   L:\limo\DEPLOYMENT_PACKAGE\INSTALL_DISPATCH1.bat
REM Wrong:     \\DISPATCHMAIN\limo\DEPLOYMENT_PACKAGE\...
REM
REM =========================================================

TITLE DISPATCH1 Installation - Arrow Limousine

REM Check if running from UNC path (causes issues)
echo %~dp0 | find "\\" >nul
if %errorlevel% equ 0 (
    COLOR 0C
    echo.
    echo ========================================================
    echo ERROR: Running from UNC path!
    echo ========================================================
    echo.
    echo You are running this batch file from a network path
    echo like \\DISPATCHMAIN\limo\...
    echo.
    echo This causes issues because Windows cannot set the
    echo current directory to a UNC path.
    echo.
    echo SOLUTION:
    echo ========================================================
    echo.
    echo 1. Map the L: drive first:
    echo    net use L: \\DISPATCHMAIN\limo /persistent:yes
    echo.
    echo 2. Then run this script from L: drive:
    echo    L:\limo\DEPLOYMENT_PACKAGE\INSTALL_DISPATCH1.bat
    echo.
    echo ========================================================
    echo.
    pause
    exit /b 1
)

COLOR 0B
echo.
echo ========================================================
echo   DISPATCH1 INSTALLATION
echo   Arrow Limousine Management System
echo ========================================================
echo.
echo This will install the Arrow Limousine application to:
echo   Y:\ArrowLimo
echo.
echo Installation includes:
echo   - Application files
echo   - Database configuration
echo   - Desktop shortcut
echo   - Auto-update system
echo.
echo ========================================================
echo.
pause

REM Check if running as Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    COLOR 0E
    echo.
    echo ========================================================
    echo WARNING: Not running as Administrator
    echo ========================================================
    echo.
    echo Some installation features may not work properly.
    echo.
    echo Right-click this file and select "Run as administrator"
    echo for full installation.
    echo.
    echo Press any key to continue anyway...
    pause >nul
)

COLOR 0A
echo.
echo ========================================================
echo STEP 1: Verify Source Files
echo ========================================================
echo.

REM Verify we can access the deployment package
if not exist "%~dp0app\desktop_app\main.py" (
    COLOR 0C
    echo ERROR: Source files not found!
    echo.
    echo Expected location: %~dp0app\desktop_app\main.py
    echo Current directory: %~dp0
    echo.
    echo Please ensure you are running this from:
    echo   L:\limo\DEPLOYMENT_PACKAGE\
    echo.
    pause
    exit /b 1
)

echo [OK] Source files found
echo Location: %~dp0app
echo.

echo ========================================================
echo STEP 2: Create Installation Directory
echo ========================================================
echo.

REM Create Y:\ArrowLimo directory structure
mkdir "Y:\ArrowLimo" 2>nul
mkdir "Y:\ArrowLimo\app" 2>nul
mkdir "Y:\ArrowLimo\logs" 2>nul

if not exist "Y:\ArrowLimo\app" (
    COLOR 0C
    echo ERROR: Cannot create Y:\ArrowLimo\app
    echo.
    echo Make sure you have permission to create folders on Y: drive.
    echo.
    echo If Y: drive doesn't exist, create it first in Disk Management
    echo or use a local folder like C:\ArrowLimo
    echo.
    pause
    exit /b 1
)

echo [OK] Installation directory created
echo Location: Y:\ArrowLimo
echo.

echo ========================================================
echo STEP 3: Copy Application Files
echo ========================================================
echo.

echo Copying files from L: drive to Y: drive...
echo This may take a minute...
echo.

REM Copy all application files
xcopy /E /I /Y /Q "%~dp0app\*" "Y:\ArrowLimo\app\"

if errorlevel 1 (
    COLOR 0C
    echo.
    echo ERROR: File copy failed!
    echo.
    echo Check that:
    echo   - Source exists: %~dp0app\
    echo   - Destination writable: Y:\ArrowLimo\app\
    echo.
    pause
    exit /b 1
)

echo [OK] Application files copied
echo.

echo ========================================================
echo STEP 4: Configure Database Connection
echo ========================================================
echo.

REM Get DISPATCHMAIN IP address
set DISPATCHMAIN_IP=
for /f "tokens=2 delims=:" %%a in ('ping -n 1 DISPATCHMAIN ^| find "Pinging"') do (
    for /f "tokens=1" %%b in ("%%a") do set DISPATCHMAIN_IP=%%b
)

REM Remove leading/trailing spaces
set DISPATCHMAIN_IP=%DISPATCHMAIN_IP: =%

if "%DISPATCHMAIN_IP%"=="" (
    COLOR 0E
    echo WARNING: Could not auto-detect DISPATCHMAIN IP
    echo.
    set /p DISPATCHMAIN_IP="Enter DISPATCHMAIN IP address (e.g., 192.168.1.100): "
)

echo DISPATCHMAIN IP Address: %DISPATCHMAIN_IP%
echo.

REM Prompt for database password
set /p DB_PASSWORD="Enter PostgreSQL password for DISPATCHMAIN: "

REM Create .env file for DISPATCH1
echo Creating database configuration...
(
echo # Database Configuration for DISPATCH1
echo # Auto-generated on %date% at %time%
echo.
echo DB_HOST=%DISPATCHMAIN_IP%
echo DB_NAME=almsdata
echo DB_USER=postgres
echo DB_PASSWORD=%DB_PASSWORD%
echo DB_PORT=5432
echo DB_SSLMODE=disable
echo.
echo WORKSTATION_ID=DISPATCH1
echo.
echo # File storage
echo FILE_STORAGE_ROOT=Z:/limo_files
) > "Y:\ArrowLimo\app\.env"

echo [OK] Database configuration created
echo File: Y:\ArrowLimo\app\.env
echo.

echo ========================================================
echo STEP 5: Test Database Connection
echo ========================================================
echo.

echo Testing connection to DISPATCHMAIN database...
python -c "import psycopg2; conn = psycopg2.connect(host='%DISPATCHMAIN_IP%', database='almsdata', user='postgres', password='%DB_PASSWORD%', port=5432); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM charters'); print(f'Connected! Database has {cur.fetchone()[0]} charters'); conn.close()" 2>nul

if errorlevel 1 (
    COLOR 0E
    echo.
    echo WARNING: Database connection test failed
    echo.
    echo The application files are installed, but database
    echo connection could not be verified.
    echo.
    echo Please check:
    echo   - DISPATCHMAIN is running PostgreSQL
    echo   - Password is correct
    echo   - Firewall allows port 5432
    echo.
    echo You can manually test later using:
    echo   L:\limo\DEPLOYMENT_PACKAGE\TEST_DATABASE_CONNECTION.ps1
    echo.
    pause
) else (
    echo [OK] Database connection successful
    echo.
)

echo ========================================================
echo STEP 6: Create Desktop Shortcut
echo ========================================================
echo.

REM Use PowerShell to create shortcut
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Arrow Limo Dispatch.lnk'); $Shortcut.TargetPath = 'Y:\ArrowLimo\app\START_DISPATCH.bat'; $Shortcut.WorkingDirectory = 'Y:\ArrowLimo\app'; $Shortcut.Description = 'Arrow Limousine Dispatch - DISPATCH1'; $Shortcut.Save()" 2>nul

if errorlevel 1 (
    COLOR 0E
    echo WARNING: Could not create desktop shortcut automatically
    echo.
    echo Please manually create a shortcut:
    echo   1. Right-click Desktop ^> New ^> Shortcut
    echo   2. Location: Y:\ArrowLimo\app\START_DISPATCH.bat
    echo   3. Name: Arrow Limo Dispatch
    echo.
) else (
    echo [OK] Desktop shortcut created
    echo.
)

echo ========================================================
echo STEP 7: Copy Documentation Files
echo ========================================================
echo.

copy /Y "%~dp0DISPATCH1_READ_ME_FIRST.md" "Y:\ArrowLimo\READ_ME_FIRST.md" >nul 2>&1
copy /Y "%~dp0DISPATCH1_QUICK_REFERENCE_CARD.txt" "Y:\ArrowLimo\QUICK_REFERENCE.txt" >nul 2>&1

echo [OK] Documentation copied to Y:\ArrowLimo\
echo.

COLOR 0A
echo ========================================================
echo   INSTALLATION COMPLETE!
echo ========================================================
echo.
echo Arrow Limousine has been installed to:
echo   Y:\ArrowLimo\app
echo.
echo To start the application:
echo   - Double-click the "Arrow Limo Dispatch" shortcut on your desktop
echo   OR
echo   - Navigate to Y:\ArrowLimo\app and run START_DISPATCH.bat
echo.
echo For help and troubleshooting:
echo   - See: Y:\ArrowLimo\READ_ME_FIRST.md
echo   - See: Y:\ArrowLimo\QUICK_REFERENCE.txt
echo   - See: L:\limo\DEPLOYMENT_PACKAGE\*.md
echo.
echo ========================================================
echo.
echo Press any key to launch the application now...
pause >nul

REM Launch the application
start "Arrow Limousine Dispatch" "Y:\ArrowLimo\app\START_DISPATCH.bat"

echo.
echo Application starting...
echo.
timeout /t 3 >nul
