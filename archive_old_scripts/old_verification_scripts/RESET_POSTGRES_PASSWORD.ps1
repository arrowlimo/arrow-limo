# ============================================================================
# Reset PostgreSQL Password to Match .env File
# ============================================================================
# Run as Administrator
# ============================================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Password Reset" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "This script will reset the PostgreSQL 'postgres' user password" -ForegroundColor Yellow
Write-Host "to match what's in your .env file." -ForegroundColor Yellow
Write-Host ""

# Load .env file to get the password
$envFile = "l:\limo\.env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found at $envFile" -ForegroundColor Red
    pause
    exit 1
}

$dbPassword = ""
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^DB_PASSWORD=(.+)$') {
        $dbPassword = $matches[1]
    }
}

if ([string]::IsNullOrEmpty($dbPassword)) {
    Write-Host "ERROR: DB_PASSWORD not found in .env file" -ForegroundColor Red
    Write-Host "Please edit l:\limo\.env and set DB_PASSWORD=" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "Found password in .env file (length: $($dbPassword.Length))" -ForegroundColor Green
Write-Host ""

# Find PostgreSQL installation
$pgVersions = @("17", "16", "15", "14", "13")
$pgBinPath = $null

foreach ($ver in $pgVersions) {
    $binPath = "C:\Program Files\PostgreSQL\$ver\bin"
    if (Test-Path "$binPath\psql.exe") {
        $pgBinPath = $binPath
        Write-Host "✓ Found PostgreSQL $ver at $binPath" -ForegroundColor Green
        break
    }
}

if (-not $pgBinPath) {
    Write-Host "ERROR: Could not find PostgreSQL installation" -ForegroundColor Red
    pause
    exit 1
}

$psqlExe = Join-Path $pgBinPath "psql.exe"

Write-Host ""
Write-Host "Attempting to reset password..." -ForegroundColor Yellow
Write-Host ""

# Try to connect and change password
# First, try with empty password (sometimes default after install)
$env:PGPASSWORD = ""
$result = & $psqlExe -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD '$dbPassword';" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "! Could not connect with empty password, trying other methods..." -ForegroundColor Yellow
    
    # Try with trust authentication by temporarily modifying pg_hba.conf
    Write-Host ""
    Write-Host "You may need to:" -ForegroundColor Yellow
    Write-Host "1. Open pgAdmin or another PostgreSQL tool" -ForegroundColor White
    Write-Host "2. Connect as postgres user" -ForegroundColor White
    Write-Host "3. Run this SQL command:" -ForegroundColor White
    Write-Host ""
    Write-Host "   ALTER USER postgres WITH PASSWORD '$dbPassword';" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "OR use Windows Integrated Authentication instead (recommended):" -ForegroundColor Yellow
    Write-Host "   Run: l:\limo\SETUP_WINDOWS_INTEGRATED_AUTH.ps1" -ForegroundColor Cyan
} else {
    Write-Host "✓ Password reset successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run the application with:" -ForegroundColor Green
    Write-Host "  l:\limo\START_HYBRID.bat" -ForegroundColor Cyan
}

Write-Host ""
pause
