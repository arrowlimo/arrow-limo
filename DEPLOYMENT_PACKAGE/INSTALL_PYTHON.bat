@echo off
echo ============================================
echo   Arrow Limousine - Install Python
echo ============================================
echo.
echo This will download and install Python 3.11
echo.
pause

echo Downloading Python installer...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe' -OutFile '%TEMP%\python-installer.exe'"

if errorlevel 1 (
    echo ERROR: Download failed!
    echo Please download Python manually from python.org
    pause
    exit /b 1
)

echo.
echo Installing Python...
echo This may take a few minutes...
echo.

"%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

if errorlevel 1 (
    echo ERROR: Installation failed!
    pause
    exit /b 1
)

echo.
echo [OK] Python installed successfully!
echo.

echo Installing required Python packages...
python -m pip install --upgrade pip
python -m pip install psycopg2-binary PyQt5

echo.
echo [OK] All dependencies installed!
echo.
pause
