#!/usr/bin/env pwsh
# Quick start script for Arrow Limousine Management System (PowerShell)
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File start-application.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Arrow Limousine Management System" -ForegroundColor Cyan
Write-Host "Quick Start (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if Python is installed
$pythonCheck = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCheck) {
    Write-Host "ERROR: Python not found. Please install from https://python.org/" -ForegroundColor Red
    exit 1
}

# Check if Node is installed
$nodeCheck = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCheck) {
    Write-Host "ERROR: Node.js not found. Please install from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Verify database connection
$psqlCheck = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCheck) {
    Write-Host "Testing database connection..." -ForegroundColor Yellow
    $dbTest = & psql -U postgres -d almsdata -c "SELECT 1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Database connection OK" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Could not connect to almsdata database" -ForegroundColor Yellow
        Write-Host "Make sure PostgreSQL is running on localhost:5432" -ForegroundColor Yellow
    }
}

Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
Write-Host ""

# Install Python dependencies
Write-Host "Installing Python dependencies for FastAPI backend..." -ForegroundColor Yellow
& python -m pip install -e "modern_backend[dev]" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install Python dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Backend dependencies installed" -ForegroundColor Green

# Install Node dependencies
Write-Host "Installing Node dependencies for Vue frontend..." -ForegroundColor Yellow
Push-Location frontend
& npm install --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install Node dependencies" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "✓ Frontend dependencies installed" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Starting Application" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Backend (FastAPI) will start on: " -NoNewline
Write-Host "http://127.0.0.1:8000" -ForegroundColor Blue
Write-Host "  - Swagger UI: " -NoNewline
Write-Host "http://127.0.0.1:8000/docs" -ForegroundColor Blue
Write-Host "  - API: " -NoNewline
Write-Host "http://127.0.0.1:8000/api/*" -ForegroundColor Blue
Write-Host ""
Write-Host "Frontend (Vue) will start on: " -NoNewline
Write-Host "http://localhost:8080" -ForegroundColor Blue
Write-Host ""
Write-Host "Press Ctrl+C in each window to stop servers" -ForegroundColor Yellow
Write-Host ""

Read-Host "Press Enter to continue"

Write-Host "`nStarting backend..." -ForegroundColor Yellow
$backendProcess = Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; uvicorn modern_backend.app.main:app --host 127.0.0.1 --port 8000 --reload" -PassThru
$backendWindow = $backendProcess.MainWindowHandle
[System.Windows.Forms.SendKeys]::SendWait("^+T")

Start-Sleep -Seconds 2

Write-Host "Starting frontend..." -ForegroundColor Yellow
$frontendProcess = Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run serve" -PassThru

Start-Sleep -Seconds 5

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✓ Application started in new PowerShell windows" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Opening frontend in default browser..." -ForegroundColor Cyan
Start-Process "http://localhost:8080"

Write-Host "`nTo stop the application:" -ForegroundColor Yellow
Write-Host "  - Close the PowerShell windows" -ForegroundColor Yellow
Write-Host "  - Or press Ctrl+C in each window" -ForegroundColor Yellow
Write-Host ""

# Keep main script running
Wait-Process -InputObject $backendProcess, $frontendProcess -Any
