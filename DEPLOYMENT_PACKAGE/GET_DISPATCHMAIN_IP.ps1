# ============================================================================
# Get DISPATCHMAIN IP Address
# Run this on DISPATCHMAIN to get the IP address needed for DISPATCH1 setup
# ============================================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "DISPATCHMAIN Network Information" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Get IPv4 addresses
$adapters = Get-NetIPAddress -AddressFamily IPv4 | 
    Where-Object {$_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.254.*"} |
    Sort-Object -Property InterfaceAlias

if ($adapters.Count -eq 0) {
    Write-Host "No network adapters found!" -ForegroundColor Red
    exit 1
}

Write-Host "Network Adapters:" -ForegroundColor Yellow
Write-Host ""

foreach ($adapter in $adapters) {
    Write-Host "  Interface: $($adapter.InterfaceAlias)" -ForegroundColor White
    Write-Host "  IP Address: $($adapter.IPAddress)" -ForegroundColor Cyan
    Write-Host "  Status: $(if ((Get-NetAdapter -Name $adapter.InterfaceAlias).Status -eq 'Up') {'Connected'} else {'Disconnected'})" -ForegroundColor $(if ((Get-NetAdapter -Name $adapter.InterfaceAlias).Status -eq 'Up') {'Green'} else {'Red'})
    Write-Host ""
}

# Get primary/recommended IP
$primaryIP = ($adapters | Where-Object {
    $adapter = Get-NetAdapter -Name $_.InterfaceAlias
    $adapter.Status -eq 'Up' -and $adapter.MediaType -like "*802.3*"
} | Select-Object -First 1).IPAddress

if (-not $primaryIP) {
    $primaryIP = ($adapters | Where-Object {
        (Get-NetAdapter -Name $_.InterfaceAlias).Status -eq 'Up'
    } | Select-Object -First 1).IPAddress
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RECOMMENDED IP FOR DISPATCH1:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  $primaryIP" -ForegroundColor Green -NoNewline
Write-Host "  (Copy this!)" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "When installing on DISPATCH1, use this IP address for:" -ForegroundColor White
Write-Host "  - Database connection (DB_HOST)" -ForegroundColor Gray
Write-Host "  - Running TEST_DATABASE_CONNECTION.ps1" -ForegroundColor Gray
Write-Host ""

Write-Host "NOTE: Both computers must be on the same network!" -ForegroundColor Yellow
Write-Host ""

# Test if PostgreSQL is listening
Write-Host "Testing PostgreSQL service..." -ForegroundColor Yellow
$pgService = Get-Service -Name "postgresql-*" -ErrorAction SilentlyContinue
if ($pgService) {
    $status = $pgService.Status
    if ($status -eq "Running") {
        Write-Host "  ✓ PostgreSQL service is running" -ForegroundColor Green
    } else {
        Write-Host "  ✗ PostgreSQL service is NOT running (Status: $status)" -ForegroundColor Red
        Write-Host "    Start PostgreSQL before DISPATCH1 can connect" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ PostgreSQL service not found" -ForegroundColor Yellow
    Write-Host "    Verify PostgreSQL is installed" -ForegroundColor Gray
}
Write-Host ""

# Check if network setup has been run
$pgDataDir = $null
$pgVersions = @(18, 17, 16, 15, 14, 13)
foreach ($ver in $pgVersions) {
    $testPath = "C:\Program Files\PostgreSQL\$ver\data"
    if (Test-Path $testPath) {
        $pgDataDir = $testPath
        break
    }
}

if ($pgDataDir) {
    $hbaPath = "$pgDataDir\pg_hba.conf"
    if (Test-Path $hbaPath) {
        $hbaContent = Get-Content $hbaPath -Raw
        if ($hbaContent -match "192\.168\.0\.0/16.*scram-sha-256") {
            Write-Host "  ✓ PostgreSQL configured for network access" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ PostgreSQL NOT configured for network access" -ForegroundColor Yellow
            Write-Host "    Run: SETUP_POSTGRESQL_NETWORK_ACCESS.ps1" -ForegroundColor Cyan
        }
    }
}
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor White
Write-Host ""
Write-Host "1. If not done yet, run:" -ForegroundColor Gray
Write-Host "   SETUP_POSTGRESQL_NETWORK_ACCESS.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. On DISPATCH1, run:" -ForegroundColor Gray
Write-Host "   TEST_DATABASE_CONNECTION.ps1" -ForegroundColor Cyan
Write-Host "   (Enter IP: $primaryIP)" -ForegroundColor Green
Write-Host ""
Write-Host "3. If test passes, run DISPATCH1 installer" -ForegroundColor Gray
Write-Host "============================================================`n" -ForegroundColor Cyan

pause
