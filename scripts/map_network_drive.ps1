#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Map L: drive to the master computer's shared limo folder

.DESCRIPTION
    Run this on the OTHER 2 computers (not the master)
    Connects to the master computer's \\HOSTNAME\limo share
#>

Write-Host "="*80 -ForegroundColor Cyan
Write-Host "CLIENT COMPUTER - Map L: Drive to Network Share" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

# Prompt for master computer name
Write-Host "`nEnter the MASTER computer's name (hostname):" -ForegroundColor Yellow
Write-Host "  (The computer where L:\limo is physically located)" -ForegroundColor Gray
$masterComputer = Read-Host "Master computer name"

if ([string]::IsNullOrWhiteSpace($masterComputer)) {
    Write-Host "❌ Computer name required" -ForegroundColor Red
    exit 1
}

$sharePath = "\\$masterComputer\limo"

Write-Host "`n[STEP 1] Testing connection to master computer..." -ForegroundColor Green
try {
    $pingResult = Test-Connection -ComputerName $masterComputer -Count 1 -Quiet
    if ($pingResult) {
        Write-Host "  ✅ Master computer is reachable" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Cannot ping master computer" -ForegroundColor Yellow
        Write-Host "  Continuing anyway (may still work)..." -ForegroundColor Gray
    }
} catch {
    Write-Host "  ⚠️  Ping test failed: $_" -ForegroundColor Yellow
}

Write-Host "`n[STEP 2] Checking if L: is already mapped..." -ForegroundColor Green
$existingDrive = Get-PSDrive -Name L -ErrorAction SilentlyContinue

if ($existingDrive) {
    Write-Host "  L: drive is already mapped to: $($existingDrive.DisplayRoot)" -ForegroundColor Yellow
    $response = Read-Host "`n  Remove and remap? (y/n)"
    if ($response -eq 'y') {
        try {
            net use L: /delete /yes 2>$null
            Write-Host "  Removed existing L: mapping" -ForegroundColor Yellow
        } catch {
            Write-Host "  Could not remove: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  Keeping existing mapping" -ForegroundColor Green
        exit 0
    }
}

Write-Host "`n[STEP 3] Mapping L: to $sharePath..." -ForegroundColor Green
try {
    # Use net use for persistent mapping
    $result = net use L: $sharePath /persistent:yes 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ L: drive mapped successfully" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Mapping may have failed" -ForegroundColor Yellow
        Write-Host "  Output: $result" -ForegroundColor Gray
        
        # Try with credentials prompt
        Write-Host "`n  Credentials may be required..." -ForegroundColor Yellow
        $result = net use L: $sharePath /persistent:yes /user 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ L: drive mapped with credentials" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Failed to map drive" -ForegroundColor Red
            Write-Host "  Error: $result" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "  ❌ Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n[STEP 4] Verifying access to shared files..." -ForegroundColor Green
$testFolders = @("desktop_app", "scripts", "receipts", "documents")

foreach ($folder in $testFolders) {
    $path = "L:\limo\$folder"
    if (Test-Path $path) {
        Write-Host "  ✅ $folder accessible" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $folder not found" -ForegroundColor Yellow
    }
}

Write-Host "`n"
Write-Host "="*80 -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

Write-Host "`nL: drive is now mapped to: $sharePath" -ForegroundColor Green
Write-Host "`nYou can now:" -ForegroundColor Yellow
Write-Host "  ✅ Run the desktop app from L:\limo\desktop_app\main.py" -ForegroundColor White
Write-Host "  ✅ Access all shared PDF/document files" -ForegroundColor White
Write-Host "  ✅ Connect to Neon database (master)" -ForegroundColor White
Write-Host "  ✅ Use Local database as offline cache (read-only)" -ForegroundColor White

Write-Host "`nTo test, run:" -ForegroundColor Yellow
Write-Host "  cd L:\limo" -ForegroundColor White
Write-Host "  python desktop_app\main.py" -ForegroundColor White

Write-Host "`n"
