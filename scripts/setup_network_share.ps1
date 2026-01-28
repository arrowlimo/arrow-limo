#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Setup L:\limo as a network share for 3-computer dispatch/office setup

.DESCRIPTION
    Run this on the MASTER computer (the one with L:\limo and all PDFs/documents)
    Creates SMB share so other 2 computers can map L: drive and access files
#>

Write-Host "="*80 -ForegroundColor Cyan
Write-Host "MASTER COMPUTER - Network Share Setup" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

# Get hostname for other computers to use
$hostname = $env:COMPUTERNAME
Write-Host "`n[STEP 1] Computer name: $hostname" -ForegroundColor Green
Write-Host "  Other computers will use: \\$hostname\limo" -ForegroundColor Yellow

# Check if share already exists
Write-Host "`n[STEP 2] Checking existing shares..." -ForegroundColor Green
$existingShare = Get-SmbShare -Name "limo" -ErrorAction SilentlyContinue

if ($existingShare) {
    Write-Host "  Share 'limo' already exists:" -ForegroundColor Yellow
    Write-Host "    Path: $($existingShare.Path)" -ForegroundColor White
    Write-Host "    Description: $($existingShare.Description)" -ForegroundColor White
    
    $response = Read-Host "`n  Remove and recreate? (y/n)"
    if ($response -eq 'y') {
        Remove-SmbShare -Name "limo" -Force
        Write-Host "  Removed existing share" -ForegroundColor Yellow
    } else {
        Write-Host "  Keeping existing share" -ForegroundColor Green
        Write-Host "`n[DONE] Share is ready" -ForegroundColor Green
        Write-Host "`nOn OTHER computers, run:" -ForegroundColor Cyan
        Write-Host "  net use L: \\$hostname\limo /persistent:yes" -ForegroundColor White
        exit 0
    }
}

# Create new share
Write-Host "`n[STEP 3] Creating SMB share..." -ForegroundColor Green
try {
    New-SmbShare `
        -Name "limo" `
        -Path "L:\limo" `
        -Description "Arrow Limousine Management System - Shared files and PDFs" `
        -FullAccess "Everyone" `
        -ErrorAction Stop
    
    Write-Host "  ✅ Share created successfully" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Error creating share: $_" -ForegroundColor Red
    Write-Host "`n  You may need to run this as Administrator" -ForegroundColor Yellow
    exit 1
}

# Verify critical folders are accessible
Write-Host "`n[STEP 4] Verifying critical folders..." -ForegroundColor Green
$criticalFolders = @(
    "receipts",
    "documents",
    "pdf",
    "vehicle_documents",
    "employee_documents",
    "business_documents"
)

foreach ($folder in $criticalFolders) {
    $path = "L:\limo\$folder"
    if (Test-Path $path) {
        $count = (Get-ChildItem $path -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Host "  ✅ $folder ($count files)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $folder (not found)" -ForegroundColor Yellow
    }
}

# Show network access info
Write-Host "`n[STEP 5] Network access verification..." -ForegroundColor Green
$share = Get-SmbShare -Name "limo"
Write-Host "  Share Name: $($share.Name)" -ForegroundColor White
Write-Host "  Local Path: $($share.Path)" -ForegroundColor White
Write-Host "  Network Path: \\$hostname\limo" -ForegroundColor White

# Test network accessibility
Write-Host "`n[STEP 6] Testing network access..." -ForegroundColor Green
try {
    $testPath = "\\$hostname\limo"
    if (Test-Path $testPath) {
        Write-Host "  ✅ Network path accessible" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Network path not accessible (may need firewall/network config)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠️  Could not test network path: $_" -ForegroundColor Yellow
}

# Instructions for other computers
Write-Host "`n"
Write-Host "="*80 -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

Write-Host "`nOn the OTHER 2 computers, run this command:" -ForegroundColor Yellow
Write-Host "  net use L: \\$hostname\limo /persistent:yes" -ForegroundColor White

Write-Host "`nIf prompted for credentials, use:" -ForegroundColor Yellow
Write-Host "  Username: $env:USERDOMAIN\$env:USERNAME (or just .\$env:USERNAME)" -ForegroundColor White
Write-Host "  Password: [this computer's login password]" -ForegroundColor White

Write-Host "`nAll 3 computers will then:" -ForegroundColor Green
Write-Host "  ✅ Access same L:\limo codebase" -ForegroundColor White
Write-Host "  ✅ Access same PDF/document files" -ForegroundColor White
Write-Host "  ✅ Connect to Neon database (or local if offline)" -ForegroundColor White

Write-Host "`nFirewall notes:" -ForegroundColor Yellow
Write-Host "  - File and Printer Sharing must be enabled on this computer" -ForegroundColor White
Write-Host "  - Network Discovery should be ON" -ForegroundColor White
Write-Host "  - Set network to 'Private' not 'Public'" -ForegroundColor White

Write-Host "`n"
