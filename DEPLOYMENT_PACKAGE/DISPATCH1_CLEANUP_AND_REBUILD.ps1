# DISPATCH1 Network Drive Cleanup & Desktop App Rebuild
# Run this on dispatch1 to consolidate network drives and rebuild the app structure

param(
    [string]$MainServerPath = "\\DISPATCHMAIN\limo"  # Central limo repo location
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DISPATCH1 CLEANUP & REBUILD PLAN" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# STEP 1: List current mapped drives
Write-Host "STEP 1: Current Network Mappings" -ForegroundColor Yellow
Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Root -like '\\*'} | Format-Table Name, Root, @{N="Provider";E={$_.Provider.Name}} -AutoSize

Write-Host ""
Write-Host "STEP 2: Proposed Consolidation" -ForegroundColor Yellow
Write-Host "  Single drive: L: -> \\DISPATCHMAIN\limo" -ForegroundColor Green
Write-Host "  Contains: backend/, frontend/, desktop_app/, scripts/, config/, data/" -ForegroundColor Green
Write-Host ""

# STEP 3: Show folder structure to create
Write-Host "STEP 3: Desktop App Extended Structure" -ForegroundColor Yellow
@"
L:\limo\                          (network mapped)
├── desktop_app/                  (source code)
├── backend/                      (FastAPI server)
├── frontend/                     (web interface)
├── scripts/                      (deployment & utility scripts)
├── DEPLOYMENT_PACKAGE/           (installer & setup)
│   ├── app/                      (launcher + symlink to desktop_app)
│   ├── DispatchInstaller.ps1
│   └── START_HERE.txt
├── config/                       (database configs, env files)
├── data/                         (local database files, if needed)
└── requirements.txt              (all dependencies)
"@ | Write-Host -ForegroundColor Green

Write-Host ""
Write-Host "STEP 4: Cleanup Actions Needed" -ForegroundColor Yellow
Write-Host "  ❌ Remove: Y: (alms) - consolidate into main L: drive" -ForegroundColor Red
Write-Host "  ❌ Remove: arrowLimo folder mapping - use L:\limo instead" -ForegroundColor Red
Write-Host "  ❌ Remove: duplicate DEPLOYMENT_PACKAGE mapping" -ForegroundColor Red
Write-Host "  ✅ Keep: L: mapped to \\DISPATCHMAIN\limo (single source)" -ForegroundColor Green
Write-Host ""

Write-Host "STEP 5: Rebuild Desktop App on dispatch1" -ForegroundColor Yellow
Write-Host ""
$steps = @(
    "1. Remove all extra network drive mappings (keep only L: drive)",
    "2. Map L: drive to \\DISPATCHMAIN\limo if not already",
    "3. Verify all required folders exist on central server:",
    "   - L:\limo\desktop_app",
    "   - L:\limo\backend",
    "   - L:\limo\frontend",
    "   - L:\limo\scripts",
    "4. Set up dispatcher service to use L:\limo paths",
    "5. Create .env and config files locally in dispatch1",
    "6. Test desktop app launches from L:\limo\desktop_app\main.py"
)

foreach($step in $steps) {
    Write-Host "   $step"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NEXT: Run the cleanup script below" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
