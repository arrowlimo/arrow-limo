@echo off
REM ========================================
REM Update Deployment Package with All Files
REM ========================================

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

REM Copy all Python files from desktop_app to deployment
echo Copying Python modules...
xcopy /Y "l:\limo\desktop_app\*.py" "Y:\DEPLOYMENT_PACKAGE\app\"

REM Copy ai_knowledge_db folder if it exists
if exist "l:\limo\desktop_app\ai_knowledge_db" (
    echo Copying AI knowledge database...
    xcopy /E /I /Y "l:\limo\desktop_app\ai_knowledge_db" "Y:\DEPLOYMENT_PACKAGE\app\ai_knowledge_db\"
)

REM Copy JSON configuration files
echo Copying configuration files...
if exist "l:\limo\desktop_app\*.json" (
    xcopy /Y "l:\limo\desktop_app\*.json" "Y:\DEPLOYMENT_PACKAGE\app\"
)

echo.
echo ================================================
echo   DEPLOYMENT PACKAGE UPDATED
echo ================================================
echo.
echo All files have been copied to:
echo Y:\DEPLOYMENT_PACKAGE\app
echo (Network: \\DISPATCHMAIN\limo_files\DEPLOYMENT_PACKAGE\app)
echo.
echo The receipt form and all other features should now work.
echo.
pause
