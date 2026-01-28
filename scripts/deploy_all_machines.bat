@echo off
REM Arrow Limo Multi-Machine Deployment Setup
REM This script helps set up deployment on remote machines
REM Usage: deploy_all_machines.bat

setlocal enabledelayedexpansion

REM Configuration
set NETWORK_SHARE=\\Dispatchmain\ArrowLimoApp
set SETUP_SCRIPT=setup_machine_deployment.ps1

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║  Arrow Limo Multi-Machine Deployment Setup                 ║
echo ║  Target: 6 machines connecting to Neon database            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check network share accessibility
echo Checking network share access...
if exist "%NETWORK_SHARE%" (
    echo ✓ Network share accessible: %NETWORK_SHARE%
) else (
    echo ✗ ERROR: Cannot access %NETWORK_SHARE%
    echo.
    echo Please verify:
    echo   1. Dispatchmain machine is powered on
    echo   2. Network connection is available
    echo   3. Windows Firewall allows File Sharing
    echo.
    pause
    exit /b 1
)

REM Generate deployment commands for each machine
echo.
echo ═══════════════════════════════════════════════════════════════
echo  DEPLOYMENT COMMANDS FOR EACH MACHINE
echo ═══════════════════════════════════════════════════════════════
echo.

for /l %%i in (1,1,6) do (
    echo Machine %%i:
    echo   PowerShell -NoProfile -ExecutionPolicy Bypass -Command ^
    echo   ".\%SETUP_SCRIPT% -MachineNumber %%i -NetworkShare '%NETWORK_SHARE%'"
    echo.
)

echo ═══════════════════════════════════════════════════════════════
echo.
echo Instructions:
echo   1. On each remote machine, open PowerShell as Administrator
echo   2. Download %SETUP_SCRIPT% from L:\limo\scripts\
echo   3. Copy the command above for that machine and paste into PowerShell
echo   4. Wait for completion (should see "✓ Neon connection verified")
echo   5. Log out and back in - app will start automatically
echo.
echo Network Share: %NETWORK_SHARE%
echo.

pause
