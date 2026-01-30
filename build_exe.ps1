#!/usr/bin/env powershell
"""
Build Script for Arrow Limousine Desktop App Executable
Creates a standalone Windows .exe that can be distributed to dispatchers

Usage:
    .\build_exe.ps1                # Build with default settings
    .\build_exe.ps1 -Clean         # Clean build artifacts first
    .\build_exe.ps1 -NoClean       # Keep previous build, just update
"""

param(
    [Switch]$Clean = $false,
    [Switch]$NoClean = $false
)

$ErrorActionPreference = 'Stop'
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptPath

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Arrow Limousine Desktop App - PyInstaller Build Script       ║" -ForegroundColor Cyan
Write-Host "║  Building standalone Windows executable                        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check prerequisites
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow
$venv = ".\.venv\Scripts\pip.exe"
if (-not (Test-Path $venv)) {
    Write-Host "❌ Virtual environment not found at .\.venv" -ForegroundColor Red
    Write-Host "   Run: python -m venv .venv" -ForegroundColor White
    Write-Host "   Then: .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor White
    exit 1
}
Write-Host "✓ Virtual environment found" -ForegroundColor Green

# Step 2: Install PyInstaller if needed
Write-Host "[2/5] Installing PyInstaller..." -ForegroundColor Yellow
& .\.venv\Scripts\pip.exe install -q pyinstaller 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ PyInstaller ready" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to install PyInstaller" -ForegroundColor Red
    exit 1
}

# Step 3: Clean old builds if requested
if ($Clean) {
    Write-Host "[3/5] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue }
    if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" -ErrorAction SilentlyContinue }
    if (Test-Path ".\.spec") { Remove-Item -Force ".\.spec" -ErrorAction SilentlyContinue }
    Write-Host "✓ Clean build directory prepared" -ForegroundColor Green
} else {
    Write-Host "[3/5] Skipping clean (use -Clean flag to clean build)" -ForegroundColor Yellow
}

# Step 4: Check .env file
Write-Host "[4/5] Checking configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".\.env")) {
    Write-Host "⚠ .env file not found. Creating from template..." -ForegroundColor Yellow
    if (Test-Path ".\.env.example") {
        Copy-Item ".\.env.example" ".\.env"
        Write-Host "✓ .env created from .env.example - EDIT THIS FILE WITH YOUR DATABASE CREDENTIALS" -ForegroundColor Green
    } else {
        Write-Host "❌ .env.example template not found" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ .env configuration file found" -ForegroundColor Green
}

# Step 5: Run PyInstaller
Write-Host "[5/5] Building executable with PyInstaller..." -ForegroundColor Yellow
Write-Host "      This may take 2-5 minutes..." -ForegroundColor Gray
Write-Host ""

& .\.venv\Scripts\pyinstaller.exe build_desktop_app.spec --noconfirm --log-level=INFO

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  ✅ BUILD SUCCESSFUL!                                          ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║  Location: .\dist\ArrowLimousineApp.exe                        ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║  Distribution:                                                 ║" -ForegroundColor Green
    Write-Host "║  1. Copy .\dist\ArrowLimousineApp.exe to dispatcher            ║" -ForegroundColor Green
    Write-Host "║  2. Include the .env.example file and instructions             ║" -ForegroundColor Green
    Write-Host "║  3. Dispatcher copies .env.example → .env in same directory   ║" -ForegroundColor Green
    Write-Host "║  4. Dispatcher edits .env with their Neon credentials         ║" -ForegroundColor Green
    Write-Host "║  5. Dispatcher runs ArrowLimousineApp.exe                      ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    
    # Create a deployment folder structure
    Write-Host "Creating deployment package structure..." -ForegroundColor Yellow
    $deployDir = ".\dist\ArrowLimousine_Deployment"
    if (-not (Test-Path $deployDir)) {
        New-Item -ItemType Directory -Path $deployDir -Force | Out-Null
    }
    Copy-Item ".\dist\ArrowLimousineApp.exe" "$deployDir\ArrowLimousineApp.exe" -Force
    Copy-Item ".\.env.example" "$deployDir\.env.example" -Force
    
    Write-Host "✓ Deployment package ready at: $deployDir" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 Zip this folder to distribute to dispatchers:" -ForegroundColor Cyan
    Write-Host "   Get-ChildItem -Path '$deployDir' -Recurse | Compress-Archive -DestinationPath ArrowLimousine_Installer.zip" -ForegroundColor White
    
} else {
    Write-Host ""
    Write-Host "❌ Build failed! Check the error messages above." -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure all dependencies are installed: pip install -r requirements.txt" -ForegroundColor White
    Write-Host "  2. Check .env file is properly configured" -ForegroundColor White
    Write-Host "  3. Verify database connection is working" -ForegroundColor White
    exit 1
}
