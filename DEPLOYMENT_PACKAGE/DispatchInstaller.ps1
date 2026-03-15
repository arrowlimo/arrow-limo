# Arrow Limousine Dispatch Workstation Installer
# Self-contained installation for dispatch computers
# Run this script as Administrator

param(
    [string]$ServerName = "DISPATCHMAIN"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Arrow Limousine Dispatch Installer" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This installer must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[1/6] Mapping Z: drive to network file storage..." -ForegroundColor Yellow

# Remove existing Z: mapping if present
try {
    net use Z: /delete /yes 2>$null
} catch {}

# Map Z: drive to shared limo_files folder
$networkPath = "\\$ServerName\limo_files"
$sharedUser = "DISPATCHMAIN\ArrowDispatch"
$sharedPassword = "Dispatch2026!"

Write-Host "      Connecting to: $networkPath" -ForegroundColor Gray

try {
    # Try with shared credentials
    net use Z: $networkPath /user:$sharedUser $sharedPassword /persistent:yes
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      [OK] Z: drive mapped successfully!" -ForegroundColor Green
        $zDriveMapped = $true
    } else {
        throw "Failed to map drive"
    }
} catch {
    Write-Host "      [WARNING] Could not map Z: drive" -ForegroundColor Yellow
    Write-Host "      The app will use network path instead: $networkPath" -ForegroundColor Gray
    $zDriveMapped = $false
}

# Create limo_files folder structure if it doesn't exist
Write-Host ""
Write-Host "[2/6] Creating file storage structure..." -ForegroundColor Yellow

$folders = @(
    "Z:\limo_files\employees",
    "Z:\limo_files\vehicles", 
    "Z:\limo_files\business_documents",
    "Z:\limo_files\banking_records",
    "Z:\limo_files\reports",
    "Z:\limo_files\backups"
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "      Created: $folder" -ForegroundColor Gray
    }
}
Write-Host "      [OK] Folder structure ready!" -ForegroundColor Green

# Install application
Write-Host ""
Write-Host "[3/6] Installing Arrow Limousine application..." -ForegroundColor Yellow

$installPath = "C:\ArrowLimo"
if (-not (Test-Path $installPath)) {
    New-Item -ItemType Directory -Path $installPath -Force | Out-Null
}

# Copy application files from deployment package
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appSource = Join-Path $scriptDir "app"

if (Test-Path $appSource) {
    Write-Host "      Installing application files..." -ForegroundColor Gray
    Copy-Item -Path "$appSource\*" -Destination $installPath -Recurse -Force
    Write-Host "      [OK] Application installed to $installPath" -ForegroundColor Green
} else {
    Write-Host "      [WARNING] App files not found in package" -ForegroundColor Yellow
    Write-Host "      You'll need to access the app from \\$ServerName\limo" -ForegroundColor Gray
}

# Configure database connection
Write-Host ""
Write-Host "[4/6] Configuring database connection..." -ForegroundColor Yellow

# Use network path if Z: didn't map
$fileStoragePath = if ($zDriveMapped) { "Z:/limo_files" } else { "\\$ServerName/limo_files" }

$envContent = @"
# Arrow Limousine Database Configuration
# Neon PostgreSQL Connection

DB_HOST=ep-curly-dream-a9nuyxfx-pooler.us-east-2.aws.neon.tech
DB_NAME=almsdata
DB_USER=almsdata_owner
DB_PASSWORD=npg_VZmw3XCcNMHO
DB_PORT=5432
DB_SSLMODE=require

# File Storage (Network Path)
FILE_STORAGE_ROOT=$fileStoragePath

# Application Settings
ENVIRONMENT=production
"@

$envPath = Join-Path $installPath ".env"
$envContent | Out-File -FilePath $envPath -Encoding UTF8
Write-Host "      [OK] Database and file storage configured!" -ForegroundColor Green
Write-Host "      File storage: $fileStoragePath" -ForegroundColor Gray

# Test database connection
Write-Host ""
Write-Host "[5/6] Testing database connection..." -ForegroundColor Yellow

$testScript = @"
import os
import psycopg2
from pathlib import Path

env_file = Path(r"$installPath") / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

try:
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        port=os.environ.get('DB_PORT', '5432'),
        sslmode=os.environ.get('DB_SSLMODE', 'require')
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM charters')
    count = cur.fetchone()[0]
    print(f"Connected! Found {count} charters in database.")
    conn.close()
    exit(0)
except Exception as e:
    print(f"Connection failed: {e}")
    exit(1)
"@

$testScriptPath = Join-Path $installPath "test_connection.py"
$testScript | Out-File -FilePath $testScriptPath -Encoding UTF8

# Try to run the test with Python if available
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    try {
        $result = & python $testScriptPath 2>&1
        Write-Host "      $result" -ForegroundColor Gray
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      [OK] Database connection successful!" -ForegroundColor Green
        } else {
            Write-Host "      [WARNING] Database connection test failed" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "      [WARNING] Could not test database connection" -ForegroundColor Yellow
    }
} else {
    Write-Host "      [SKIPPED] Python not found, skipping connection test" -ForegroundColor Yellow
}

# Create desktop shortcut
Write-Host ""
Write-Host "[6/6] Creating desktop shortcuts..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")

# Shortcut to application launcher
$launcherBat = Join-Path $installPath "START_DISPATCH.bat"
if (Test-Path $launcherBat) {
    $shortcut = $WshShell.CreateShortcut("$desktopPath\Arrow Limousine Dispatch.lnk")
    $shortcut.TargetPath = $launcherBat
    $shortcut.WorkingDirectory = $installPath
    $shortcut.Description = "Arrow Limousine Management System"
    $shortcut.Save()
    Write-Host "      [OK] Desktop shortcut created!" -ForegroundColor Green
} else {
    # Fallback: shortcut to folder
    $shortcut = $WshShell.CreateShortcut("$desktopPath\Arrow Limousine.lnk")
    $shortcut.TargetPath = $installPath
    $shortcut.Description = "Arrow Limousine Management System"
    $shortcut.Save()
    Write-Host "      [OK] Folder shortcut created!" -ForegroundColor Green
}

# Enable insecure guest authentication for network access
Write-Host ""
Write-Host "[EXTRA] Enabling network file access..." -ForegroundColor Yellow

try {
    if (-not (Test-Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation")) {
        New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation" -Force | Out-Null
    }
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation" -Name "AllowInsecureGuestAuth" -Value 1 -Type DWord
    Write-Host "      [OK] Network access configured!" -ForegroundColor Green
} catch {
    Write-Host "      [WARNING] Could not set registry key" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host ""
Write-Host "Installation Summary:" -ForegroundColor White
if ($zDriveMapped) {
    Write-Host "  - Z: drive mapped to $networkPath" -ForegroundColor Gray
} else {
    Write-Host "  - Z: drive NOT mapped (using network path)" -ForegroundColor Yellow
    Write-Host "  - Network path: $networkPath" -ForegroundColor Gray
}
Write-Host "  - Configuration saved to $installPath" -ForegroundColor Gray
Write-Host "  - Database configured for Neon PostgreSQL" -ForegroundColor Gray
Write-Host "  - File storage: $fileStoragePath" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Access frontend/backend from network:" -ForegroundColor White
Write-Host "     \\$ServerName\limo\modern_backend" -ForegroundColor Cyan
Write-Host "     \\$ServerName\limo\frontend" -ForegroundColor Cyan
Write-Host "  2. Or use the desktop shortcut to launch" -ForegroundColor White
if (-not $zDriveMapped) {
    Write-Host ""
    Write-Host "  NOTE: Z: drive mapping failed, but app will work" -ForegroundColor Yellow
    Write-Host "  Files are accessible via network path" -ForegroundColor Gray
}
Write-Host "  1. Verify Z: drive is accessible (open File Explorer)" -ForegroundColor White
Write-Host "  2. Open File Explorer and navigate to \\$ServerName\limo" -ForegroundColor White
Write-Host "  3. Run the application from the network share" -ForegroundColor White
Write-Host "  4. Or copy the application files to C:\ArrowLimo manually" -ForegroundColor White
Write-Host ""
Write-Host "If you have any issues, contact IT support." -ForegroundColor Gray
Write-Host ""

pause
