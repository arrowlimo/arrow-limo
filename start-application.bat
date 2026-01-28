@echo off
REM Quick start script for Arrow Limousine Management System
REM This script starts both backend (FastAPI) and frontend (Vue)

echo.
echo ========================================
echo Arrow Limousine Management System
echo Quick Start
echo ========================================
echo.

REM Check if Node is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js not found. Please install from https://nodejs.org/
    exit /b 1
)

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Please install from https://python.org/
    exit /b 1
)

REM Check if psql is available for DB verification
where psql >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Testing database connection...
    psql -U postgres -d almsdata -c "SELECT 1" >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo WARNING: Could not connect to almsdata database
        echo Make sure PostgreSQL is running
    ) else (
        echo ✓ Database connection OK
    )
) else (
    echo WARNING: psql not found in PATH. Skipping database check.
)

echo.
echo Installing dependencies...
echo.

REM Install Python backend dependencies
echo Installing Python dependencies for FastAPI backend...
pip install -e modern_backend[dev] >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install Python dependencies
    exit /b 1
)
echo ✓ Backend dependencies installed

REM Install Node frontend dependencies
echo Installing Node dependencies for Vue frontend...
cd frontend
call npm install >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install Node dependencies
    cd ..
    exit /b 1
)
echo ✓ Frontend dependencies installed
cd ..

echo.
echo ========================================
echo Starting Application
echo ========================================
echo.
echo Backend (FastAPI) will start on: http://127.0.0.1:8000
echo  - Swagger UI: http://127.0.0.1:8000/docs
echo  - API: http://127.0.0.1:8000/api/*
echo.
echo Frontend (Vue) will start on: http://localhost:8080
echo.
echo Press Ctrl+C to stop servers
echo.
pause

REM Start backend in new window
start "Arrow Limousine - Backend (FastAPI)" cmd /k "cd /d %cd% && uvicorn modern_backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

REM Wait a moment for backend to start
timeout /t 2 /nobreak

REM Start frontend in new window
start "Arrow Limousine - Frontend (Vue)" cmd /k "cd /d %cd%\frontend && npm run serve"

echo.
echo ========================================
echo ✓ Application started in new windows
echo ========================================
echo.
echo Waiting for services to start...
timeout /t 5 /nobreak

echo.
echo Opening frontend in browser...
start http://localhost:8080

echo.
echo To stop the application:
echo - Close the two command windows that opened
echo - Or press Ctrl+C in each window
echo.
