# ═══════════════════════════════════════════════════════════════════════════
# AUTOMATIC POSTGRESQL TIMEOUT FIX (Run as Administrator)
# ═══════════════════════════════════════════════════════════════════════════
# This script configures PostgreSQL to never timeout your sessions
# Run this in PowerShell as Administrator
# ═══════════════════════════════════════════════════════════════════════════

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PostgreSQL Timeout Configuration Fix" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Find PostgreSQL installation
$pgPath = $null
$possiblePaths = @(
    "C:\Program Files\PostgreSQL\16",
    "C:\Program Files\PostgreSQL\15",
    "C:\Program Files\PostgreSQL\14",
    "C:\Program Files\PostgreSQL\13",
    "C:\Program Files (x86)\PostgreSQL\16",
    "C:\Program Files (x86)\PostgreSQL\15",
    "C:\Program Files (x86)\PostgreSQL\14",
    "C:\Program Files (x86)\PostgreSQL\13"
)

foreach ($path in $possiblePaths) {
    if (Test-Path "$path\data\postgresql.conf") {
        $pgPath = $path
        break
    }
}

if (-not $pgPath) {
    Write-Host "❌ ERROR: Could not find PostgreSQL installation" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the SQL fix instead:" -ForegroundColor Yellow
    Write-Host "  File: l:\limo\RUN_THIS_NOW_FIX_TIMEOUT.sql" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "✓ Found PostgreSQL at: $pgPath" -ForegroundColor Green
$confFile = "$pgPath\data\postgresql.conf"
Write-Host "✓ Config file: $confFile" -ForegroundColor Green
Write-Host ""

# Backup the config file
$backupFile = "$pgPath\data\postgresql.conf.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Write-Host "Creating backup..." -ForegroundColor Yellow
Copy-Item $confFile $backupFile
Write-Host "✓ Backup created: $backupFile" -ForegroundColor Green
Write-Host ""

# Read current config
$config = Get-Content $confFile

# Check if settings already exist
$hasIdleTimeout = $config | Where-Object { $_ -match "^idle_in_transaction_session_timeout" }
$hasStatementTimeout = $config | Where-Object { $_ -match "^statement_timeout" }

Write-Host "Updating PostgreSQL configuration..." -ForegroundColor Yellow

# Add or update settings
if ($hasIdleTimeout) {
    Write-Host "  - Updating idle_in_transaction_session_timeout..." -ForegroundColor Cyan
    $config = $config -replace "^idle_in_transaction_session_timeout.*", "idle_in_transaction_session_timeout = 7200000  # 2 hours"
} else {
    Write-Host "  - Adding idle_in_transaction_session_timeout..." -ForegroundColor Cyan
    $config += ""
    $config += "# Desktop application timeout fix - added $(Get-Date -Format 'yyyy-MM-dd')"
    $config += "idle_in_transaction_session_timeout = 7200000  # 2 hours in milliseconds"
}

if ($hasStatementTimeout) {
    Write-Host "  - Updating statement_timeout..." -ForegroundColor Cyan
    $config = $config -replace "^statement_timeout.*", "statement_timeout = 900000  # 15 minutes"
} else {
    Write-Host "  - Adding statement_timeout..." -ForegroundColor Cyan
    if (-not $hasIdleTimeout) {
        $config += ""
        $config += "# Desktop application timeout fix - added $(Get-Date -Format 'yyyy-MM-dd')"
    }
    $config += "statement_timeout = 900000  # 15 minutes in milliseconds"
}

# Write updated config
Write-Host ""
Write-Host "Writing updated configuration..." -ForegroundColor Yellow
$config | Set-Content $confFile -Encoding UTF8
Write-Host "✓ Configuration updated" -ForegroundColor Green
Write-Host ""

# Find and restart PostgreSQL service
Write-Host "Finding PostgreSQL service..." -ForegroundColor Yellow
$pgService = Get-Service | Where-Object { $_.Name -like "postgresql*" -and $_.Status -eq "Running" } | Select-Object -First 1

if ($pgService) {
    Write-Host "✓ Found service: $($pgService.Name)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Restarting PostgreSQL service..." -ForegroundColor Yellow
    Write-Host "  (This will cause a brief disconnection - database will be back online in 10 seconds)" -ForegroundColor Cyan
    
    try {
        Restart-Service $pgService.Name -Force
        Start-Sleep -Seconds 3
        
        # Wait for service to be running
        $timeout = 30
        $elapsed = 0
        while ($elapsed -lt $timeout) {
            $status = (Get-Service $pgService.Name).Status
            if ($status -eq "Running") {
                Write-Host "✓ PostgreSQL service restarted successfully!" -ForegroundColor Green
                break
            }
            Start-Sleep -Seconds 1
            $elapsed++
        }
        
        if ($elapsed -ge $timeout) {
            Write-Host "⚠️  WARNING: Service took longer than expected to restart" -ForegroundColor Yellow
            Write-Host "  Check Services (services.msc) to verify PostgreSQL is running" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ ERROR: Failed to restart service" -ForegroundColor Red
        Write-Host "  Error: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please restart the service manually:" -ForegroundColor Yellow
        Write-Host "  1. Open Services (Win+R, type 'services.msc')" -ForegroundColor Yellow
        Write-Host "  2. Find '$($pgService.Name)'" -ForegroundColor Yellow
        Write-Host "  3. Right-click → Restart" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  WARNING: Could not find running PostgreSQL service" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please restart PostgreSQL manually:" -ForegroundColor Yellow
    Write-Host "  1. Open Services (Win+R, type 'services.msc')" -ForegroundColor Yellow
    Write-Host "  2. Find a service starting with 'postgresql'" -ForegroundColor Yellow
    Write-Host "  3. Right-click → Restart" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ CONFIGURATION COMPLETE!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Run the SQL index fix: l:\limo\RUN_THIS_NOW_FIX_TIMEOUT.sql" -ForegroundColor White
Write-Host "  2. Restart your desktop application" -ForegroundColor White
Write-Host "  3. Test: Open a receipt and leave it for 5+ minutes" -ForegroundColor White
Write-Host "  4. Should NOT timeout anymore! ✨" -ForegroundColor White
Write-Host ""
Write-Host "BACKUP LOCATION:" -ForegroundColor Cyan
Write-Host "  $backupFile" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
