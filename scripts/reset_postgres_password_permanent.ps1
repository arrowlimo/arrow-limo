# PostgreSQL Password Reset - PowerShell Version
# Run as Administrator to permanently set postgres password
# This temporarily uses 'trust' auth to reset, then restores 'scram-sha-256'

param(
    [string]$NewPassword = '***REMOVED***'
)

Write-Host "PostgreSQL Password Reset (PowerShell)" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

$PG_VERSION = "18"
$PG_PATH = "C:\Program Files\PostgreSQL\$PG_VERSION"
$PG_DATA = "$PG_PATH\data"
$PG_HBA = "$PG_DATA\pg_hba.conf"
$PG_HBA_BACKUP = "$PG_HBA.backup"
$PG_CTL = "$PG_PATH\bin\pg_ctl.exe"
$PSQL = "$PG_PATH\bin\psql.exe"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')
if (-not $isAdmin) {
    Write-Host "WARNING This script needs to run as Administrator" -ForegroundColor Yellow
    Write-Host "Run PowerShell as Administrator and try again" -ForegroundColor Yellow
    exit 1
}

# Step 1: Check PostgreSQL is running
Write-Host "Step 1: Checking PostgreSQL service..." -ForegroundColor Yellow
$service = Get-Service -Name "postgresql-x64-$PG_VERSION" -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Host "  ERROR PostgreSQL service not found" -ForegroundColor Red
    exit 1
}

if ($service.Status -ne 'Running') {
    Write-Host "  WARNING PostgreSQL is not running, starting..." -ForegroundColor Yellow
    Start-Service -Name "postgresql-x64-$PG_VERSION"
    Start-Sleep -Seconds 3
}

Write-Host "  OK PostgreSQL is running" -ForegroundColor Green

# Step 2: Backup pg_hba.conf
Write-Host "`nStep 2: Backing up pg_hba.conf..." -ForegroundColor Yellow
if (-not (Test-Path $PG_HBA)) {
    Write-Host "  ERROR pg_hba.conf not found at $PG_HBA" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PG_HBA_BACKUP)) {
    Copy-Item $PG_HBA $PG_HBA_BACKUP -Force
    Write-Host "  OK Backup created" -ForegroundColor Green
}
else {
    Write-Host "  OK Backup already exists" -ForegroundColor Green
}

# Step 3: Modify pg_hba.conf to use 'trust' auth
Write-Host "`nStep 3: Modifying pg_hba.conf to use 'trust' auth..." -ForegroundColor Yellow
try {
    $content = Get-Content $PG_HBA
    $modified = @()
    foreach ($line in $content) {
        if ($line -match 'scram-sha-256' -and -not $line.StartsWith('#')) {
            $modified += $line -replace 'scram-sha-256$', 'trust'
        } else {
            $modified += $line
        }
    }
    
    Set-Content -Path $PG_HBA -Value $modified -Force
    Write-Host "  OK pg_hba.conf modified" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR Failed to modify pg_hba.conf: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Reload PostgreSQL config
Write-Host "`nStep 4: Reloading PostgreSQL configuration..." -ForegroundColor Yellow
try {
    & $PG_CTL reload -D $PG_DATA 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    Write-Host "  OK Configuration reloaded" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR Failed to reload: $_" -ForegroundColor Red
    Copy-Item $PG_HBA_BACKUP $PG_HBA -Force
    exit 1
}

# Step 5: Reset password
Write-Host "`nStep 5: Resetting postgres user password to '$NewPassword'..." -ForegroundColor Yellow
try {
    $resetSql = "ALTER USER postgres WITH PASSWORD '$NewPassword';"
    & $PSQL -h localhost -U postgres -d postgres -c $resetSql 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK Password reset successfully" -ForegroundColor Green
    }
    else {
        Write-Host "  ERROR Password reset failed" -ForegroundColor Red
        Copy-Item $PG_HBA_BACKUP $PG_HBA -Force
        & $PG_CTL reload -D $PG_DATA 2>&1 | Out-Null
        exit 1
    }
}
catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    Copy-Item $PG_HBA_BACKUP $PG_HBA -Force
    & $PG_CTL reload -D $PG_DATA 2>&1 | Out-Null
    exit 1
}

# Step 6: Restore pg_hba.conf to use 'scram-sha-256'
Write-Host "`nStep 6: Restoring original pg_hba.conf (scram-sha-256)..." -ForegroundColor Yellow
try {
    Copy-Item $PG_HBA_BACKUP $PG_HBA -Force
    Write-Host "  OK Original config restored" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR Failed to restore: $_" -ForegroundColor Red
    exit 1
}

# Step 7: Reload with secure config
Write-Host "`nStep 7: Reloading with secure configuration..." -ForegroundColor Yellow
try {
    & $PG_CTL reload -D $PG_DATA 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    Write-Host "  OK PostgreSQL reloaded with scram-sha-256" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR Failed to reload: $_" -ForegroundColor Red
    exit 1
}

# Step 8: Test connection with new password
Write-Host "`nStep 8: Testing connection with new password..." -ForegroundColor Yellow
try {
    $env:PGPASSWORD = $NewPassword
    $testOutput = & $PSQL -h localhost -U postgres -d postgres -c "SELECT version();" 2>&1
    $env:PGPASSWORD = $null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK Connection successful!" -ForegroundColor Green
        $version = $testOutput[0] -replace 'PostgreSQL', 'PG'
        Write-Host "  $version" -ForegroundColor Green
    }
    else {
        Write-Host "  ERROR Connection failed" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n" + "="*50 -ForegroundColor Cyan
Write-Host "SUCCESS!" -ForegroundColor Green
Write-Host "PostgreSQL password permanently set to: '$NewPassword'" -ForegroundColor Cyan
Write-Host "="*50 -ForegroundColor Cyan
Write-Host ""

Write-Host "NEXT STEPS: Add this to your environment variables for apps:" -ForegroundColor Yellow
Write-Host "  DB_PASSWORD=$NewPassword" -ForegroundColor White
Write-Host ""
