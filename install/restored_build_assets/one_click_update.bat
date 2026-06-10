@echo off
setlocal enabledelayedexpansion

REM --- Arrow Limousine One-Click App Update ---
REM --- Copies full app folder (including .venv) from Dropbox to Y:\limo ---

REM --- Set source and target ---
set "DROPBOX_APP_PATH=%USERPROFILE%\Dropbox\limo_deploy"
if not exist "!DROPBOX_APP_PATH!" set "DROPBOX_APP_PATH=%USERPROFILE%\Dropbox\install\limo"
set "TARGET_PATH=Y:\limo"

REM --- Hard safety guard: never allow drive-root or non-limo target ---
if /I "!TARGET_PATH!"=="Y:\" (
	echo [ERROR] Unsafe target path Y:\ detected. Update aborted.
	exit /b 1
)
if /I not "!TARGET_PATH!"=="Y:\limo" (
	echo [ERROR] Target path must be Y:\limo. Current: !TARGET_PATH!
	exit /b 1
)

echo.
echo ========== Arrow Limousine - One-Click App Update ==========
echo Source: !DROPBOX_APP_PATH!
echo Target: !TARGET_PATH!
echo.

REM --- Validate source before changing target ---
if not exist "!DROPBOX_APP_PATH!" (
	echo [ERROR] Source folder does not exist: !DROPBOX_APP_PATH!
	exit /b 1
)

if not exist "!DROPBOX_APP_PATH!\desktop_app" (
	echo [ERROR] Source missing desktop_app folder. Update aborted.
	exit /b 1
)

if not exist "!DROPBOX_APP_PATH!\ArrowLimousineApp.exe" (
	echo [ERROR] Source missing ArrowLimousineApp.exe. Update aborted.
	exit /b 1
)

if not exist "!DROPBOX_APP_PATH!\.venv\Scripts\python.exe" (
	echo [ERROR] Source missing .venv or python runtime. Update aborted.
	exit /b 1
)

REM --- Try to pin payload locally to reduce cloud-placeholder copy failures ---
attrib +P "!DROPBOX_APP_PATH!\*" /S /D >nul 2>&1

REM --- Stop running app if needed ---
powershell -Command "Get-Process ArrowLimousineApp -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"

REM --- Backup current install ---
if not exist "!TARGET_PATH!" mkdir "!TARGET_PATH!"
set "BACKUP_DIR=!TARGET_PATH!\_install_backups"
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"
set "BACKUP_NAME=backup_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP_NAME=!BACKUP_NAME: =0!"
set "BACKUP_PATH=!BACKUP_DIR!\!BACKUP_NAME!"
mkdir "!BACKUP_PATH!"
robocopy "!TARGET_PATH!" "!BACKUP_PATH!" /E /XD "_install_backups" /R:1 /W:1 /COPY:DAT /DCOPY:DAT >nul

REM --- Remove old app files (except backups) ---
for /D %%d in ("!TARGET_PATH!\*") do if /I not "%%~nd"=="_install_backups" rmdir /S /Q "%%d"
for %%f in ("!TARGET_PATH!\*") do del /F /Q "%%f" >nul 2>&1

REM --- Copy new app files from Dropbox ---
robocopy "!DROPBOX_APP_PATH!" "!TARGET_PATH!" /E /R:1 /W:1 /XD "_install_backups" /COPY:DAT /DCOPY:DAT
set "RC=!ERRORLEVEL!"
if !RC! GEQ 8 (
	echo [ERROR] Copy failed with robocopy exit code !RC!.
	exit /b !RC!
)

echo.
echo [SUCCESS] App update complete. Launch with START_ARROW_LIMO.bat
echo.
exit /b 0