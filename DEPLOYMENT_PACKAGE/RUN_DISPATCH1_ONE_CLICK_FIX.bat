@echo off
setlocal

echo ============================================================
echo   DISPATCH1 One-Click Repair + Install
echo ============================================================
echo.
echo This will:
echo   1) Clear stale L:/Z: mappings and cached share credentials
echo   2) Remap shares (prompts once if needed)
echo   3) Run DispatchInstaller_Dispatch1.ps1
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process PowerShell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%~dp0RUN_DISPATCH1_ONE_CLICK_FIX.ps1'"

if errorlevel 1 (
  echo.
  echo Failed to start elevated repair script.
  pause
  exit /b 1
)

echo.
echo Elevated installer launched. Approve UAC if prompted.
exit /b 0
