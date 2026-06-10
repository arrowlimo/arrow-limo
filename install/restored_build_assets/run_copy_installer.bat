@echo off
setlocal enabledelayedexpansion

REM --- Simple Copy-Replace Installer for Arrow Limousine ---
REM --- This batch file calls the PowerShell script ---

REM --- Source directory (where the original files are) ---
REM --- Can be overridden by passing as first argument: run_copy_installer.bat L:\limo ---
if not "!1!"=="" (
    set "SOURCE=%1"
) else (
    set "SOURCE=L:\limo"
)

echo.
echo ========== Arrow Limousine - Simple Copy Installer ==========
echo Source Directory: !SOURCE!
echo Target Directory: Y:\limo
echo.

REM --- Detect PowerShell 7 or 5.1 ---
set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not exist "!PWSH!" (
    set "PWSH=powershell.exe"
)

REM --- Run the installer script ---
"!PWSH!" -NoProfile -ExecutionPolicy Bypass -File "%~dp0simple_copy_installer.ps1" -SourcePath "!SOURCE!" -TargetPath "Y:\limo"

set "EXIT_CODE=!ERRORLEVEL!"
echo.
if !EXIT_CODE! equ 0 (
    echo [SUCCESS] Installation completed successfully.
) else (
    echo [ERROR] Installation failed with exit code !EXIT_CODE!
)
echo.
echo Check log file: C:\ProgramData\ArrowLimoInstaller\
echo.

exit /b !EXIT_CODE!
