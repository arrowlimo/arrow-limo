# Network Share Setup for Dual Dispatcher System
# Run this on DISPATCHMAIN (your development computer) as Administrator
# This shares the L:\limo folder so DISPATCH1 can auto-update

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Network Share Setup for L:\limo" -ForegroundColor Cyan
Write-Host "  Enables DISPATCH1 Auto-Updates" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Must run as Administrator!" -ForegroundColor Red
    pause
    exit 1
}

# Check if L:\limo exists
if (-not (Test-Path "L:\limo")) {
    Write-Host "[ERROR] L:\limo directory not found!" -ForegroundColor Red
    Write-Host "Make sure your development folder exists at L:\limo" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[1/4] Creating shared dispatch user account..." -ForegroundColor Yellow

$username = "ArrowDispatch"
$password = "Dispatch2026!"
$description = "Shared account for Arrow Limo dispatch workstations"

# Check if user already exists
$userExists = Get-LocalUser -Name $username -ErrorAction SilentlyContinue

if ($userExists) {
    Write-Host "      User '$username' already exists, resetting password..." -ForegroundColor Gray
    $securePassword = ConvertTo-SecureString $password -AsPlainText -Force
    Set-LocalUser -Name $username -Password $securePassword
} else {
    Write-Host "      Creating user '$username'..." -ForegroundColor Gray
    $securePassword = ConvertTo-SecureString $password -AsPlainText -Force
    New-LocalUser -Name $username -Password $securePassword -Description $description -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
}

Write-Host "      [OK] User account ready!" -ForegroundColor Green
Write-Host "      Username: $env:COMPUTERNAME\$username" -ForegroundColor Gray
Write-Host "      Password: $password" -ForegroundColor Gray

# Create share for L:\limo
Write-Host ""
Write-Host "[2/4] Creating network share for L:\limo..." -ForegroundColor Yellow

$shareName = "limo"
$sharePath = "L:\limo"

# Remove existing share if present
$existingShare = Get-SmbShare -Name $shareName -ErrorAction SilentlyContinue
if ($existingShare) {
    Write-Host "      Removing existing share..." -ForegroundColor Gray
    Remove-SmbShare -Name $shareName -Force
}

# Create new share
New-SmbShare -Name $shareName -Path $sharePath -FullAccess "Everyone" -Description "Arrow Limo Development Source for Auto-Updates" | Out-Null
Write-Host "      [OK] Share created: \\$env:COMPUTERNAME\$shareName" -ForegroundColor Green

# Set NTFS permissions
Write-Host ""
Write-Host "[3/4] Configuring folder permissions..." -ForegroundColor Yellow

$acl = Get-Acl $sharePath
$readPermission = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $username,
    "ReadAndExecute",
    "ContainerInherit,ObjectInherit",
    "None",
    "Allow"
)
$acl.AddAccessRule($readPermission)
Set-Acl $sharePath $acl

Write-Host "      [OK] Read access granted to $username" -ForegroundColor Green

# Create share for limo_files (if exists)
Write-Host ""
Write-Host "[4/4] Checking limo_files share..." -ForegroundColor Yellow

if (Test-Path "Z:\limo_files") {
    $limoFilesShare = Get-SmbShare -Name "limo_files" -ErrorAction SilentlyContinue
    if (-not $limoFilesShare) {
        New-SmbShare -Name "limo_files" -Path "Z:\limo_files" -FullAccess "Everyone" -Description "Arrow Limo Shared File Storage" | Out-Null
        Write-Host "      [OK] Created limo_files share" -ForegroundColor Green
    } else {
        Write-Host "      [OK] limo_files share already exists" -ForegroundColor Green
    }
} else {
    Write-Host "      [INFO] Z:\limo_files not found, skipping" -ForegroundColor Gray
}

# Test the share
Write-Host ""
Write-Host "Testing network shares..." -ForegroundColor Yellow
Write-Host "  \\$env:COMPUTERNAME\limo -> $sharePath" -ForegroundColor Gray

if (Test-Path "\\$env:COMPUTERNAME\limo") {
    Write-Host "      [OK] Share accessible!" -ForegroundColor Green
} else {
    Write-Host "      [WARNING] Share may not be accessible" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Network Share Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Share Details:" -ForegroundColor Cyan
Write-Host "  Share Name: \\$env:COMPUTERNAME\limo" -ForegroundColor White
Write-Host "  Local Path: $sharePath" -ForegroundColor Gray
Write-Host "  Access: ReadAndExecute for ArrowDispatch" -ForegroundColor Gray
Write-Host ""
Write-Host "Dispatch1 can now:" -ForegroundColor Cyan
Write-Host "  1. Map L: to \\$env:COMPUTERNAME\limo" -ForegroundColor White
Write-Host "  2. Auto-update from your development files" -ForegroundColor White
Write-Host "  3. Always run latest code when launched" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Copy DEPLOYMENT_PACKAGE to DISPATCH1" -ForegroundColor White
Write-Host "  2. On DISPATCH1, run INSTALL_DISPATCH1_X_DRIVE.bat" -ForegroundColor White
Write-Host "  3. App will auto-update each launch" -ForegroundColor White
Write-Host ""
pause
