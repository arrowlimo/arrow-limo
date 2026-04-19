@echo off
REM ========================================
REM Update Deployment Package with All Files
REM ========================================

setlocal enabledelayedexpansion

echo.
echo ================================================
echo   UPDATING DEPLOYMENT PACKAGE
echo ================================================
echo.
echo This will copy all required files from desktop_app
echo to the deployment package at Y:\DEPLOYMENT_PACKAGE\app
echo (Network path: \\DISPATCHMAIN\limo_files\DEPLOYMENT_PACKAGE\app)
echo.
pause

cd /d "%~dp0"

set "SOURCE_DIR=%~dp0desktop_app"
set "TARGET_PRIMARY=%~dp0DEPLOYMENT_PACKAGE\app\desktop_app"
set "TARGET_LEGACY=Y:\DEPLOYMENT_PACKAGE\app"

if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source folder not found: %SOURCE_DIR%
    pause
    exit /b 1
)

if not exist "%TARGET_PRIMARY%" (
    mkdir "%TARGET_PRIMARY%" >nul 2>&1
)

REM Copy all Python files from desktop_app to deployment
echo Copying Python modules to primary deployment path...
xcopy /Y "%SOURCE_DIR%\*.py" "%TARGET_PRIMARY%\"

REM Copy ai_knowledge_db folder if it exists
if exist "%SOURCE_DIR%\ai_knowledge_db" (
    echo Copying AI knowledge database...
    xcopy /E /I /Y "%SOURCE_DIR%\ai_knowledge_db" "%TARGET_PRIMARY%\ai_knowledge_db\"
)

REM Copy JSON configuration files
echo Copying configuration files...
if exist "%SOURCE_DIR%\*.json" (
    xcopy /Y "%SOURCE_DIR%\*.json" "%TARGET_PRIMARY%\"
)

REM Optional legacy mirror for older installers still using Y:\DEPLOYMENT_PACKAGE\app
if exist "%TARGET_LEGACY%" (
    echo Mirroring to legacy deployment path...
    xcopy /Y "%SOURCE_DIR%\*.py" "%TARGET_LEGACY%\"

    if exist "%SOURCE_DIR%\ai_knowledge_db" (
        xcopy /E /I /Y "%SOURCE_DIR%\ai_knowledge_db" "%TARGET_LEGACY%\ai_knowledge_db\"
    )

    if exist "%SOURCE_DIR%\*.json" (
        xcopy /Y "%SOURCE_DIR%\*.json" "%TARGET_LEGACY%\"
    )
)

echo.
echo ================================================
echo   DEPLOYMENT PACKAGE UPDATED
echo ================================================
echo.
echo All files have been copied to:
echo %TARGET_PRIMARY%
if exist "%TARGET_LEGACY%" echo Also mirrored to: %TARGET_LEGACY%
echo.
echo The receipt form and all other features should now work.
echo.
pause

endlocal
