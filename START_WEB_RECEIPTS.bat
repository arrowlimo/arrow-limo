@echo off
REM ========================================
REM Launch Web App Receipt Entry System
REM ========================================

echo.
echo ================================================
echo   ARROW LIMOUSINE - WEB RECEIPT ENTRY
echo ================================================
echo.

cd /d "%~dp0"

REM Check if backend is already running
powershell -Command "$process = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue; if ($process) { Write-Host '  Backend already running on port 8001' -ForegroundColor Green; exit 0 } else { exit 1 }"
if %ERRORLEVEL% EQU 0 (
    echo   Backend server: ALREADY RUNNING
) else (
    echo   Starting backend server...
    start "FastAPI Backend" cmd /k "cd /d l:\limo\modern_backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"
    timeout /t 3 /nobreak >nul
)

REM Check if frontend is already running
powershell -Command "$process = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue; if ($process) { Write-Host '  Frontend already running on port 8080' -ForegroundColor Green; exit 0 } else { exit 1 }"
if %ERRORLEVEL% EQU 0 (
    echo   Frontend server: ALREADY RUNNING
) else (
    echo   Starting frontend dev server...
    start "Vue.js Frontend" cmd /k "cd /d l:\limo\frontend && npm run serve"
    timeout /t 5 /nobreak >nul
)

echo.
echo ================================================
echo   SERVERS STARTED
echo ================================================
echo.
echo   Backend API:  http://127.0.0.1:8001
echo   API Docs:     http://127.0.0.1:8001/docs
echo.
echo   Opening receipt entry page in browser...
echo.

REM Wait a bit more for servers to be ready
timeout /t 2 /nobreak >nul

REM Open the receipt entry page
start http://localhost:8080/receipt-entry.html

echo.
echo   Receipt Entry: http://localhost:8080/receipt-entry.html
echo.
echo ================================================
echo   Press any key to exit this launcher...
echo   (Servers will continue running in background)
echo ================================================
pause >nul
