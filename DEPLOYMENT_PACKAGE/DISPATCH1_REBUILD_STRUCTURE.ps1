# REBUILD DISPATCH1 DESKTOP APP STRUCTURE
# Creates proper folder organization and symlinks for dispatch1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "REBUILDING DISPATCH1 DESKTOP APP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$basePath = "L:"

# Verify we have access to all required source folders
Write-Host "STEP 1: Verifying source folders..." -ForegroundColor Yellow

$sourceFolders = @{
    "desktop_app" = "$basePath\desktop_app"
    "backend" = "$basePath\backend"
    "frontend" = "$basePath\frontend"
    "scripts" = "$basePath\scripts"
    "config" = "$basePath\config"
    "DEPLOYMENT_PACKAGE" = "$basePath\DEPLOYMENT_PACKAGE"
}

$allGood = $true
foreach($name in $sourceFolders.Keys) {
    $path = $sourceFolders[$name]
    if (Test-Path $path) {
        $itemCount = @(Get-ChildItem $path -ErrorAction SilentlyContinue).Count
        Write-Host "  [OK] $name ($itemCount items)" -ForegroundColor Green
    } else {
        Write-Host "  [X] MISSING: $name" -ForegroundColor Red
        $allGood = $false
    }
}

if (-not $allGood) {
    Write-Host ""
    Write-Host "ERROR: Not all required folders are accessible!" -ForegroundColor Red
    Write-Host "Make sure L: drive is mapped to \\DISPATCHMAIN\limo" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "STEP 2: Creating dispatcher local config..." -ForegroundColor Yellow

# Create local dispatcher config directory
$dispatcherConfigPath = "$basePath\DEPLOYMENT_PACKAGE\app\config"
if (-not (Test-Path $dispatcherConfigPath)) {
    New-Item -ItemType Directory -Path $dispatcherConfigPath -Force | Out-Null
    Write-Host "  [OK] Created $dispatcherConfigPath" -ForegroundColor Green
} else {
    Write-Host "  [i] Config directory already exists" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "STEP 3: Verifying DEPLOYMENT_PACKAGE structure..." -ForegroundColor Yellow

$deployPackagePath = "$basePath\DEPLOYMENT_PACKAGE"
$appPath = "$deployPackagePath\app"

if (-not (Test-Path $appPath)) {
    New-Item -ItemType Directory -Path $appPath -Force | Out-Null
    Write-Host "  [OK] Created app folder" -ForegroundColor Green
}

# Check for launcher
if (Test-Path "$appPath\launcher.py") {
    Write-Host "  [OK] launcher.py exists" -ForegroundColor Green
} else {
    Write-Host "  [!] launcher.py missing (create from backend launcher)" -ForegroundColor Yellow
}

# Ensure desktop_app is linked or copied
if (Test-Path "$appPath\desktop_app") {
    Write-Host "  [OK] desktop_app folder linked/present" -ForegroundColor Green
} else {
    Write-Host "  [!] desktop_app not linked in DEPLOYMENT_PACKAGE\app" -ForegroundColor Yellow
    Write-Host "    Consider creating symlink: mklink /D '$appPath\desktop_app' '$basePath\desktop_app'" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "STEP 4: Desktop App Structure" -ForegroundColor Yellow
Write-Host @"
L:\ (network mapped drive to \\DISPATCHMAIN\limo)
│
├── desktop_app/              ← MAIN APP SOURCE
│   ├── main.py              ← Entry point
│   ├── requirements.txt
│   ├── dashboards/
│   ├── widgets/
│   └── ... (130+ files)
│
├── backend/                  ← API SERVER
│   ├── main.py
│   └── ... (database, routes)
│
├── frontend/                 ← WEB INTERFACE
│   ├── package.json
│   └── src/
│
├── DEPLOYMENT_PACKAGE/       ← DISPATCHER LAUNCHER
│   ├── app/
│   │   ├── launcher.py       ← Starts desktop_app
│   │   ├── desktop_app/      ← Symlink to ../../../desktop_app
│   │   └── START_DISPATCH.bat
│   ├── DispatchInstaller.ps1
│   └── ... (setup scripts)
│
├── scripts/                  ← UTILITIES
│   ├── database_sync.py
│   ├── auto_updater.py
│   └── ...
│
├── config/                   ← CONFIGURATION
│   ├── .env.dispatch1
│   ├── database.conf
│   └── ...
│
└── data/                     ← LOCAL DATA (if needed)
    ├── cache/
    └── logs/
"@ -ForegroundColor Green

Write-Host ""
Write-Host "STEP 5: Endpoints for Desktop App" -ForegroundColor Yellow
Write-Host ""
Write-Host "  SHORT CUT: L:\DEPLOYMENT_PACKAGE\app\START_DISPATCH.bat" -ForegroundColor Green
Write-Host "  PYTHON:    python L:\DEPLOYMENT_PACKAGE\app\launcher.py" -ForegroundColor Green
Write-Host "  DIRECT:    python L:\desktop_app\main.py" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "REBUILD COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test launching from DEPLOYMENT_PACKAGE/app/launcher.py"
Write-Host "  2. Verify database connections work"
Write-Host "  3. Create START_DISPATCH.bat shortcut on desktop"
Write-Host "  4. Remove any old .bat files or shortcuts"
