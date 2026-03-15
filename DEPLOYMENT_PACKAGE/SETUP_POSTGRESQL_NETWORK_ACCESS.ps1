# ============================================================================
# PostgreSQL Network Access Setup for Dual Dispatchers
# Run on DISPATCHMAIN as Administrator
# ============================================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Network Access Setup" -ForegroundColor Cyan
Write-Host "Allows DISPATCH1 to connect to DISPATCHMAIN's database" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Find PostgreSQL installation
$pgVersions = @(18, 17, 16, 15, 14, 13)
$pgPath = $null
$pgData = $null

foreach ($ver in $pgVersions) {
    $testPath = "C:\Program Files\PostgreSQL\$ver"
    if (Test-Path $testPath) {
        $pgPath = $testPath
        $pgData = "$testPath\data"
        Write-Host "✓ Found PostgreSQL $ver at: $pgPath" -ForegroundColor Green
        break
    }
}

if (-not $pgPath) {
    Write-Host "✗ PostgreSQL not found in standard locations" -ForegroundColor Red
    Write-Host "  Please locate your PostgreSQL installation manually" -ForegroundColor Yellow
    exit 1
}

# Backup existing config files
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$env:USERPROFILE\Desktop\pg_backup_$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host "`n1. Backing up configuration files..." -ForegroundColor Yellow
Copy-Item "$pgData\postgresql.conf" "$backupDir\postgresql.conf.backup"
Copy-Item "$pgData\pg_hba.conf" "$backupDir\pg_hba.conf.backup"
Write-Host "   Backups saved to: $backupDir" -ForegroundColor Green

# Enable network listening
Write-Host "`n2. Configuring postgresql.conf..." -ForegroundColor Yellow
$pgConfPath = "$pgData\postgresql.conf"
$pgConf = Get-Content $pgConfPath

# Check if already configured
if ($pgConf -match "listen_addresses.*=.*'\*'") {
    Write-Host "   Already configured for network access" -ForegroundColor Green
} else {
    # Add network listening
    $newConf = $pgConf -replace "#listen_addresses = 'localhost'", "listen_addresses = '*'"
    $newConf | Set-Content $pgConfPath
    Write-Host "   ✓ Set listen_addresses = '*'" -ForegroundColor Green
}

# Configure client authentication
Write-Host "`n3. Configuring pg_hba.conf..." -ForegroundColor Yellow
$hbaPath = "$pgData\pg_hba.conf"
$hbaContent = Get-Content $hbaPath

# Add rule for local network access (adjust IP range as needed)
$networkRule = "host    all             all             192.168.0.0/16          scram-sha-256"
if ($hbaContent -notcontains $networkRule) {
    Add-Content $hbaPath "`n# Allow local network access for dual dispatcher setup"
    Add-Content $hbaPath $networkRule
    Write-Host "   ✓ Added network authentication rule" -ForegroundColor Green
} else {
    Write-Host "   Network rule already exists" -ForegroundColor Green
}

# Configure Windows Firewall
Write-Host "`n4. Configuring Windows Firewall..." -ForegroundColor Yellow
$firewallRule = Get-NetFirewallRule -DisplayName "PostgreSQL Database Server" -ErrorAction SilentlyContinue
if ($firewallRule) {
    Write-Host "   Firewall rule already exists" -ForegroundColor Green
} else {
    New-NetFirewallRule -DisplayName "PostgreSQL Database Server" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 5432 `
        -Action Allow `
        -Profile Domain,Private `
        -Description "Allow PostgreSQL connections from local network" | Out-Null
    Write-Host "   ✓ Created firewall rule for port 5432" -ForegroundColor Green
}

# Restart PostgreSQL service
Write-Host "`n5. Restarting PostgreSQL service..." -ForegroundColor Yellow
$pgService = Get-Service -Name "postgresql-*" -ErrorAction SilentlyContinue
if ($pgService) {
    Restart-Service $pgService.Name -Force
    Start-Sleep -Seconds 3
    $status = (Get-Service $pgService.Name).Status
    if ($status -eq "Running") {
        Write-Host "   ✓ PostgreSQL restarted successfully" -ForegroundColor Green
    } else {
        Write-Host "   ✗ PostgreSQL failed to restart - status: $status" -ForegroundColor Red
    }
} else {
    Write-Host "   ⚠ Could not find PostgreSQL service - please restart manually" -ForegroundColor Yellow
}

# Display network info
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Cyan

$ipAddress = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).IPAddress
Write-Host "DISPATCHMAIN IP Address: $ipAddress" -ForegroundColor Yellow
Write-Host "`nOn DISPATCH1, use this .env configuration:" -ForegroundColor White
Write-Host "DB_HOST=$ipAddress" -ForegroundColor Cyan
Write-Host "DB_PORT=5432" -ForegroundColor Cyan  
Write-Host "DB_NAME=almsdata" -ForegroundColor Cyan
Write-Host "DB_USER=postgres" -ForegroundColor Cyan
Write-Host "DB_PASSWORD=your_postgres_password" -ForegroundColor Cyan
Write-Host "DB_SSLMODE=prefer" -ForegroundColor Cyan

Write-Host "`nTest connection from DISPATCH1:" -ForegroundColor Yellow
Write-Host "psql -h $ipAddress -U postgres -d almsdata" -ForegroundColor Cyan

Write-Host "`nConfiguration backups saved to:" -ForegroundColor White
Write-Host "$backupDir`n" -ForegroundColor Cyan
