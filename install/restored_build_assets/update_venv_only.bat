@echo off
setlocal enabledelayedexpansion

REM --- Arrow Limousine Venv-Only Update ---
REM --- Mirrors only .venv from Dropbox to Y:\limo\.venv ---

set "SOURCE_VENV=%USERPROFILE%\Dropbox\limo_deploy\.venv"
if not exist "!SOURCE_VENV!" set "SOURCE_VENV=%USERPROFILE%\Dropbox\install\limo\.venv"
set "TARGET_ROOT=Y:\limo"
set "TARGET_VENV=!TARGET_ROOT!\.venv"

echo.
echo ========== Arrow Limousine - Venv Only Update ==========
echo Source: !SOURCE_VENV!
echo Target: !TARGET_VENV!
echo.

REM --- Safety checks ---
if /I not "!TARGET_ROOT!"=="Y:\limo" (
    echo [ERROR] Unsafe target root. Expected Y:\limo, got !TARGET_ROOT!
    exit /b 1
)

if not exist "!SOURCE_VENV!\Scripts\python.exe" (
    echo [ERROR] Source .venv is missing or invalid: !SOURCE_VENV!
    exit /b 1
)

if not exist "!TARGET_ROOT!" mkdir "!TARGET_ROOT!"

REM --- Mirror only .venv ---
robocopy "!SOURCE_VENV!" "!TARGET_VENV!" /MIR /R:1 /W:1 /XD "__pycache__"
set "RC=!ERRORLEVEL!"
if !RC! GEQ 8 (
    echo [ERROR] .venv copy failed with robocopy exit code !RC!
    exit /b !RC!
)

REM --- Quick validation for pypdf ---
if exist "!TARGET_VENV!\Lib\site-packages\pypdf" (
    echo [SUCCESS] .venv updated and pypdf detected.
) else (
    echo [WARNING] .venv updated, but pypdf folder not found under site-packages.
)

echo.
echo Completed venv-only update.
echo.
exit /b 0
