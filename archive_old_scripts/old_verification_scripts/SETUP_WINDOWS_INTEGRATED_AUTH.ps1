# ============================================================================
# Setup Windows Integrated Authentication (SSPI) for PostgreSQL
# ============================================================================
# This script configures PostgreSQL to use your Windows login credentials
# instead of requiring a separate database password.
#
# Benefits:
# - No more password prompts
# - Seamless single sign-on
# - Improved security (uses Windows authentication)
#
# Run as Administrator
# ============================================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Windows Integrated Auth Setup" -ForegroundColor Cyan  
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

# Find PostgreSQL installation
Write-Host "Finding PostgreSQL installation..." -ForegroundColor Yellow

$pgVersions = @("17", "16", "15", "14", "13")
$pgDataPath = $null
$pgServiceName = $null

foreach ($ver in $pgVersions) {
    $serviceName = "postgresql-x64-$ver"
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    
    if ($service) {
        Write-Host "✓ Found PostgreSQL $ver service: $serviceName" -ForegroundColor Green
        $pgServiceName = $serviceName
        
        # Try to find data directory from registry
        $regPath = "HKLM:\SOFTWARE\PostgreSQL\Installations\postgresql-x64-$ver"
        if (Test-Path $regPath) {
            $dataDir = (Get-ItemProperty -Path $regPath -Name "Data Directory" -ErrorAction SilentlyContinue)."Data Directory"
            if ($dataDir -and (Test-Path $dataDir)) {
                $pgDataPath = $dataDir
                Write-Host "✓ Found data directory: $pgDataPath" -ForegroundColor Green
                break
            }
        }
        
        # Try common locations
        $commonPaths = @(
            "C:\Program Files\PostgreSQL\$ver\data",
            "C:\PostgreSQL\$ver\data",
            "D:\PostgreSQL\$ver\data"
        )
        
        foreach ($path in $commonPaths) {
            if (Test-Path "$path\pg_hba.conf") {
                $pgDataPath = $path
                Write-Host "✓ Found data directory: $pgDataPath" -ForegroundColor Green
                break
            }
        }
        
        if ($pgDataPath) { break }
    }
}

if (-not $pgDataPath) {
    Write-Host "ERROR: Could not find PostgreSQL data directory" -ForegroundColor Red
    Write-Host "Please enter the path to your PostgreSQL data directory:" -ForegroundColor Yellow
    Write-Host "(It should contain pg_hba.conf file)" -ForegroundColor Gray
    $pgDataPath = Read-Host "Data directory path"
    
    if (-not (Test-Path "$pgDataPath\pg_hba.conf")) {
        Write-Host "ERROR: pg_hba.conf not found in $pgDataPath" -ForegroundColor Red
        pause
        exit 1
    }
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Service: $pgServiceName" -ForegroundColor White
Write-Host "  Data Dir: $pgDataPath" -ForegroundColor White
Write-Host ""

# Backup pg_hba.conf
$pgHbaPath = Join-Path $pgDataPath "pg_hba.conf"
$backupPath = "$pgHbaPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

Write-Host "Creating backup of pg_hba.conf..." -ForegroundColor Yellow
Copy-Item -Path $pgHbaPath -Destination $backupPath -Force
Write-Host "✓ Backup created: $backupPath" -ForegroundColor Green
Write-Host ""

# Read current pg_hba.conf
$hbaContent = Get-Content $pgHbaPath

# Modify authentication method for IPv4 and IPv6 localhost
$newContent = @()
$modified = $false

foreach ($line in $hbaContent) {
    # Replace md5/password/scram-sha-256 with sspi for localhost connections
    if ($line -match '^\s*host\s+all\s+all\s+127\.0\.0\.1/32\s+(md5|password|scram-sha-256|trust)\s*$') {
        $newContent += "host    all             all             127.0.0.1/32            sspi"
        Write-Host "✓ Updated IPv4 localhost authentication to SSPI" -ForegroundColor Green
        $modified = $true
    }
    elseif ($line -match '^\s*host\s+all\s+all\s+::1/128\s+(md5|password|scram-sha-256|trust)\s*$') {
        $newContent += "host    all             all             ::1/128                 sspi"
        Write-Host "✓ Updated IPv6 localhost authentication to SSPI" -ForegroundColor Green
        $modified = $true
    }
    else {
        $newContent += $line
    }
}

# If no localhost entries found, add them
if (-not $modified) {
    Write-Host "! No localhost entries found, adding new SSPI rules..." -ForegroundColor Yellow
    # Find the position to insert (after comments, before any host entries)
    $insertIndex = 0
    for ($i = 0; $i -lt $newContent.Count; $i++) {
        if ($newContent[$i] -match '^\s*#\s*TYPE\s+DATABASE\s+USER\s+ADDRESS\s+METHOD') {
            $insertIndex = $i + 1
            break
        }
    }
    
    $sspiRules = @(
        "",
        "# Windows Integrated Authentication (SSPI) for localhost",
        "host    all             all             127.0.0.1/32            sspi",
        "host    all             all             ::1/128                 sspi"
    )
    
    $newContent = $newContent[0..$insertIndex] + $sspiRules + $newContent[($insertIndex+1)..($newContent.Count-1)]
    $modified = $true
}

if ($modified) {
    # Write new configuration
    Write-Host ""
    Write-Host "Writing new pg_hba.conf..." -ForegroundColor Yellow
    $newContent | Set-Content -Path $pgHbaPath -Encoding UTF8
    Write-Host "✓ pg_hba.conf updated successfully" -ForegroundColor Green
    
    # Restart PostgreSQL service
    Write-Host ""
    Write-Host "Restarting PostgreSQL service..." -ForegroundColor Yellow
    Restart-Service -Name $pgServiceName -Force
    
    # Wait for service to start
    Start-Sleep -Seconds 3
    $service = Get-Service -Name $pgServiceName
    
    if ($service.Status -eq "Running") {
        Write-Host "✓ PostgreSQL service restarted successfully" -ForegroundColor Green
    } else {
        Write-Host "! Warning: PostgreSQL service status is $($service.Status)" -ForegroundColor Yellow
    }
} else {
    Write-Host "! No changes needed - SSPI already configured" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Configuration Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update your .env file to remove the DB_PASSWORD" -ForegroundColor White
Write-Host "2. The app will now use your Windows login credentials" -ForegroundColor White
Write-Host ""
Write-Host "To test the connection, run:" -ForegroundColor Yellow
Write-Host "  psql -U $env:USERNAME -d almsdata" -ForegroundColor Gray
Write-Host ""
Write-Host "If you need to revert, restore from:" -ForegroundColor Yellow  
Write-Host "  $backupPath" -ForegroundColor Gray
Write-Host ""

pause
