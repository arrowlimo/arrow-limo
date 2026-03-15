# DISPATCH1 CLEANUP SCRIPT
# Run this on dispatch1 AS ADMINISTRATOR to remove duplicate network drives

# Stop the dispatcher service if running
Write-Host "Stopping Arrow Dispatcher service..." -ForegroundColor Yellow
Stop-Service -Name "ArrowDispatcher" -ErrorAction SilentlyContinue -Force
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "========== REMOVING DUPLICATE NETWORK DRIVES ==========" -ForegroundColor Red

# List drives to remove
$drivesToRemove = @('Y:', 'Z:', 'M:', 'N:', 'O:', 'P:', 'Q:')

foreach($drive in $drivesToRemove) {
    if (Test-Path "$drive\") {
        Write-Host "Removing $drive..." -ForegroundColor Yellow
        net use "$drive" /delete /y 2>$null
        if ($?) {
            Write-Host "  [OK] $drive removed" -ForegroundColor Green
        } else {
            Write-Host "  [X] $drive not mapped or error" -ForegroundColor Cyan
        }
    }
}

Write-Host ""
Write-Host "========== VERIFY MAIN L: DRIVE MAPPING ==========" -ForegroundColor Green

# Check if L: is mapped, if not map it
if (Test-Path "L:\desktop_app") {
    Write-Host "[OK] L: drive is already mapped to a limo location" -ForegroundColor Green
    Get-PSDrive L | Format-List Name, Root
} else {
    Write-Host "[!] L: drive not mapped or limo folder not accessible" -ForegroundColor Yellow
    Write-Host "Run this command on dispatch1 to map the L: drive:" -ForegroundColor Cyan
    Write-Host '  net use L: \\DISPATCHMAIN\limo /persistent:yes' -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========== CURRENT NETWORK DRIVES AFTER CLEANUP ==========" -ForegroundColor Green
Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Root -like '\\*'} | Format-Table Name, Root -AutoSize

Write-Host ""
Write-Host "========== VERIFYING DESKTOP APP STRUCTURE ==========" -ForegroundColor Green

$requiredFolders = @(
    "L:\desktop_app",
    "L:\backend",
    "L:\frontend",
    "L:\scripts",
    "L:\DEPLOYMENT_PACKAGE",
    "L:\config",
    "L:\data"
)

foreach($folder in $requiredFolders) {
    if (Test-Path $folder) {
        $itemCount = (Get-ChildItem $folder).Count
        Write-Host "[OK] $folder ($itemCount items)" -ForegroundColor Green
    } else {
        Write-Host "[X] MISSING: $folder" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========== CLEANUP COMPLETE ==========" -ForegroundColor Green
Write-Host "Dispatcher service will auto-restart" -ForegroundColor Yellow
Write-Host "Launch dispatch app from: L:\DEPLOYMENT_PACKAGE\app\launcher.py" -ForegroundColor Cyan
