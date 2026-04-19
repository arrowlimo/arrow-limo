# Arrow Limousine Dispatch1 Workstation Installer
# Installs the packaged app layout to Y: drive with auto-update from dev machine
# Run this script as Administrator on DISPATCH1 computer

param(
    [string]$ServerName = "DISPATCHMAIN",
    [string]$InstallDrive = "Y:",
    [string]$SharedDrive = "Z:"
)

$ErrorActionPreference = "Stop"

$script:ShareCredentialUser = $null
$script:ShareCredentialPassword = $null

function Invoke-NetUse {
    param(
        [string[]]$Arguments
    )

    & net use @Arguments | Out-Null
    return $LASTEXITCODE
}

function Get-ShareCredentials {
    param(
        [string]$ServerName
    )

    if ($script:ShareCredentialUser -and $script:ShareCredentialPassword) {
        return $true
    }

    Write-Host "      Share requires credentials." -ForegroundColor Yellow
    Write-Host "      Leave username blank to skip credentialed mapping and use UNC fallback only." -ForegroundColor Gray

    $usernameInput = Read-Host "      Enter share username [$ServerName\ArrowDispatch]"
    if (-not $usernameInput) {
        $usernameInput = "$ServerName\ArrowDispatch"
    }

    if (-not $usernameInput) {
        return $false
    }

    $passwordSecure = Read-Host "      Enter share password for $usernameInput" -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($passwordSecure)
    $passwordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    if (-not $passwordPlain) {
        return $false
    }

    $script:ShareCredentialUser = $usernameInput
    $script:ShareCredentialPassword = $passwordPlain
    return $true
}

function Map-NetworkDrive {
    param(
        [string]$DriveLetter,
        [string]$RemotePath,
        [string]$SuccessMessage,
        [string]$FailureMessage,
        [string]$ServerName
    )

    try {
        Invoke-NetUse -Arguments @($DriveLetter, "/delete", "/yes") | Out-Null
    } catch {}

    Write-Host "      Connecting to: $RemotePath" -ForegroundColor Gray

    $exitCode = Invoke-NetUse -Arguments @($DriveLetter, $RemotePath, "/persistent:yes")
    if ($exitCode -eq 0) {
        Write-Host "      [OK] $SuccessMessage" -ForegroundColor Green
        return $true
    }

    if (Get-ShareCredentials -ServerName $ServerName) {
        $exitCode = Invoke-NetUse -Arguments @(
            $DriveLetter,
            $RemotePath,
            "/user:$script:ShareCredentialUser",
            $script:ShareCredentialPassword,
            "/persistent:yes"
        )
        if ($exitCode -eq 0) {
            Write-Host "      [OK] $SuccessMessage" -ForegroundColor Green
            return $true
        }
    }

    Write-Host "      [WARNING] $FailureMessage" -ForegroundColor Yellow
    return $false
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Arrow Limousine Dispatch1 Installer" -ForegroundColor Cyan
Write-Host "  Installing to $InstallDrive drive" -ForegroundColor Cyan
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

# Check if Y: drive exists
Write-Host "[1/8] Checking Y: drive..." -ForegroundColor Yellow
if (-not (Test-Path "$InstallDrive\")) {
    Write-Host "      [ERROR] Y: drive does not exist!" -ForegroundColor Red
    Write-Host "      Please create Y: volume first in Disk Management" -ForegroundColor Yellow
    pause
    exit 1
}
Write-Host "      [OK] Y: drive found!" -ForegroundColor Green

# Map Z: drive to network file storage
Write-Host ""
Write-Host "[2/8] Mapping $SharedDrive drive to network file storage..." -ForegroundColor Yellow

# Remove existing Z: mapping if present
# Map Z: drive to shared limo_files folder
$networkPath = "\\$ServerName\limo_files"
$zDriveMapped = Map-NetworkDrive `
    -DriveLetter $SharedDrive `
    -RemotePath $networkPath `
    -SuccessMessage "$SharedDrive drive mapped successfully!" `
    -FailureMessage "Could not map $SharedDrive drive" `
    -ServerName $ServerName

if (-not $zDriveMapped) {
    Write-Host "      The app will use network path instead: $networkPath" -ForegroundColor Gray
}

# Map L: drive to development source (for auto-updates)
Write-Host ""
Write-Host "[3/8] Mapping L: drive to development source..." -ForegroundColor Yellow

$devPath = "\\$ServerName\limo"
$lDriveMapped = Map-NetworkDrive `
    -DriveLetter "L:" `
    -RemotePath $devPath `
    -SuccessMessage "L: drive mapped for auto-updates!" `
    -FailureMessage "Could not map L: drive" `
    -ServerName $ServerName

if (-not $lDriveMapped) {
    Write-Host "      Auto-update will be disabled" -ForegroundColor Gray
}

# Create installation directory
Write-Host ""
Write-Host "[4/8] Creating installation directory..." -ForegroundColor Yellow

$installPath = "$InstallDrive\ArrowLimo"
$appInstallPath = Join-Path $installPath "app"
if (-not (Test-Path $installPath)) {
    New-Item -ItemType Directory -Path $installPath -Force | Out-Null
    Write-Host "      Created: $installPath" -ForegroundColor Gray
}
if (-not (Test-Path $appInstallPath)) {
    New-Item -ItemType Directory -Path $appInstallPath -Force | Out-Null
    Write-Host "      Created: $appInstallPath" -ForegroundColor Gray
}

# Copy app files from DEPLOYMENT_PACKAGE
Write-Host ""
Write-Host "[5/8] Installing application files..." -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appSource = Join-Path $scriptDir "app"

if (Test-Path $appSource) {
    Write-Host "      Copying packaged application layout..." -ForegroundColor Gray
    $desktopAppDest = Join-Path $appInstallPath "desktop_app"
    if (-not (Test-Path $desktopAppDest)) {
        New-Item -ItemType Directory -Path $desktopAppDest -Force | Out-Null
    }
    
    # Copy the packaged app so DISPATCH1 launches the same entrypoint as the full desktop app.
    Write-Host "      Copying Python application files..." -ForegroundColor Gray
    Copy-Item -Path "$appSource\*" -Destination $appInstallPath -Recurse -Force
    
    Write-Host "      [OK] Application installed to $appInstallPath" -ForegroundColor Green
} else {
    Write-Host "      [ERROR] App files not found in deployment package!" -ForegroundColor Red
    Write-Host "      Expected: $appSource" -ForegroundColor Yellow
    pause
    exit 1
}

# Configure .env file
Write-Host ""
Write-Host "[6/8] Configuring database and file storage..." -ForegroundColor Yellow

# Prompt for DISPATCHMAIN IP address
Write-Host ""
Write-Host "      DATABASE CONFIGURATION" -ForegroundColor Cyan
Write-Host "      =====================" -ForegroundColor Cyan
Write-Host ""
Write-Host "      DISPATCH1 will connect to PostgreSQL on DISPATCHMAIN" -ForegroundColor White
Write-Host "      Both dispatchers will share the same database." -ForegroundColor Gray
Write-Host ""

$dbHost = Read-Host "      Enter DISPATCHMAIN IP address (e.g., 192.168.1.100)"
if (-not $dbHost) {
    $dbHost = "localhost"
    Write-Host "      [WARNING] No IP entered, using localhost (won't work from DISPATCH1!)" -ForegroundColor Yellow
}

$dbPassword = Read-Host "      Enter PostgreSQL 'postgres' user password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPassword)
$dbPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

Write-Host ""
Write-Host "      Testing database connection..." -ForegroundColor Yellow

# Test connection using Python
$testScript = @"
import psycopg2
import sys
try:
    conn = psycopg2.connect(
        host='$dbHost',
        port=5432,
        dbname='almsdata',
        user='postgres',
        password='$dbPasswordPlain',
        connect_timeout=5
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM charters')
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f'SUCCESS:{count}')
    sys.exit(0)
except Exception as e:
    print(f'ERROR:{str(e)}')
    sys.exit(1)
"@

$tempScript = "$env:TEMP\test_db.py"
$testScript | Out-File -FilePath $tempScript -Encoding UTF8

try {
    $pythonPath = "C:\Python312\python.exe"
    if (-not (Test-Path $pythonPath)) {
        $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
    
    if ($pythonPath) {
        $result = & $pythonPath $tempScript 2>&1
        Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
        
        if ($result -match '^SUCCESS:(\d+)') {
            $charterCount = $matches[1]
            Write-Host "      [OK] Database connection successful!" -ForegroundColor Green
            Write-Host "      Connected to: $dbHost" -ForegroundColor Gray
            Write-Host "      Database: almsdata ($charterCount charters)" -ForegroundColor Gray
        } else {
            $error = ($result -split ':',2)[1]
            Write-Host "      [WARNING] Database connection failed: $error" -ForegroundColor Yellow
            Write-Host "      Installation will continue, but verify database access later" -ForegroundColor Yellow
        }
    } else {
        Write-Host "      [WARNING] Python not found - cannot test connection" -ForegroundColor Yellow
        Write-Host "      Installation will continue" -ForegroundColor Yellow
    }
} catch {
    Write-Host "      [WARNING] Could not test database: $_" -ForegroundColor Yellow
    Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
}

Write-Host ""
$fileStoragePath = if ($zDriveMapped) { "$SharedDrive/limo_files" } else { "\\$ServerName\limo_files" }

$envContent = @"
# Arrow Limousine Database Configuration - DISPATCH1
# Network PostgreSQL (Shared with DISPATCHMAIN)
# Both dispatchers connect to same database for real-time sync

DB_HOST=$dbHost
DB_NAME=almsdata
DB_USER=postgres
DB_PASSWORD=$dbPasswordPlain
DB_PORT=5432
DB_SSLMODE=prefer

# Workstation Identification
WORKSTATION_ID=DISPATCH1

# File Storage (Network Share)
FILE_STORAGE_ROOT=$fileStoragePath

# Application Settings
ENVIRONMENT=production

# Receipt Widget Configuration
RECEIPT_WIDGET_WRITE_ENABLED=1
RECEIPT_WIDGET_SKIP_RECENT=false

# Session Configuration
SESSION_TIMEOUT_MINUTES=30
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
"@

$envPath = Join-Path $appInstallPath ".env"
$envContent | Out-File -FilePath $envPath -Encoding UTF8
Write-Host "      [OK] Configuration saved to .env" -ForegroundColor Green
Write-Host "      Database: $dbHost (Network PostgreSQL)" -ForegroundColor Gray
Write-Host "      File storage: $fileStoragePath" -ForegroundColor Gray
Write-Host "      Workstation: DISPATCH1" -ForegroundColor Gray

# Create auto-update script
Write-Host ""
Write-Host "[7/8] Creating auto-update script..." -ForegroundColor Yellow

$autoUpdateScript = @"
# Auto-Update Script for DISPATCH1
# Syncs latest desktop_app code from L:\limo\desktop_app to Y:\ArrowLimo\app\desktop_app
# Run this before starting the app to get latest updates

`$SourcePath = "L:\limo\desktop_app"
`$DestPath = "$appInstallPath\desktop_app"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Arrow Limo Auto-Update (DISPATCH1)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "`$SourcePath")) {
    Write-Host "[ERROR] Cannot access L:\limo\desktop_app" -ForegroundColor Red
    Write-Host "Make sure DISPATCHMAIN computer is on and L: drive is mapped" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Starting app with current version..." -ForegroundColor Gray
    timeout /t 3
    exit 0
}

Write-Host "Checking for updates from development source..." -ForegroundColor Yellow
Write-Host "Source: `$SourcePath" -ForegroundColor Gray
Write-Host "Destination: `$DestPath" -ForegroundColor Gray
Write-Host ""

try {
    # Compare file timestamps
    `$sourceFiles = Get-ChildItem -Path "`$SourcePath\*.py" -Recurse -File
    `$updateCount = 0
    
    foreach (`$file in `$sourceFiles) {
        `$relativePath = `$file.FullName.Substring(`$SourcePath.Length + 1)
        `$destFile = Join-Path `$DestPath `$relativePath
        
        if (-not (Test-Path `$destFile)) {
            # New file
            `$destDir = Split-Path `$destFile -Parent
            if (-not (Test-Path `$destDir)) {
                New-Item -ItemType Directory -Path `$destDir -Force | Out-Null
            }
            Copy-Item `$file.FullName `$destFile -Force
            Write-Host "[NEW] `$relativePath" -ForegroundColor Green
            `$updateCount++
        } else {
            # Check if source is newer
            `$sourceTime = (Get-Item `$file.FullName).LastWriteTime
            `$destTime = (Get-Item `$destFile).LastWriteTime
            
            if (`$sourceTime -gt `$destTime) {
                Copy-Item `$file.FullName `$destFile -Force
                Write-Host "[UPDATED] `$relativePath" -ForegroundColor Yellow
                `$updateCount++
            }
        }
    }
    
    if (`$updateCount -eq 0) {
        Write-Host "[OK] Application is up to date!" -ForegroundColor Green
    } else {
        Write-Host "" 
        Write-Host "[OK] Updated `$updateCount file(s)" -ForegroundColor Green
    }
    
} catch {
    Write-Host "[ERROR] Update failed: `$_" -ForegroundColor Red
    Write-Host "Starting app with current version..." -ForegroundColor Gray
}

Write-Host ""
timeout /t 2
"@

$updateScriptPath = Join-Path $installPath "AUTO_UPDATE.ps1"
$autoUpdateScript | Out-File -FilePath $updateScriptPath -Encoding UTF8
Write-Host "      [OK] Auto-update script created!" -ForegroundColor Green

# Create launcher that updates then starts the app
$launcherScript = @"
@echo off
title Arrow Limousine - DISPATCH1
cls

echo ============================================
echo   Arrow Limousine Management System
echo   DISPATCH1 Workstation
echo ============================================
echo.

REM Auto-update from dev source
echo Checking for updates...
PowerShell -NoProfile -ExecutionPolicy Bypass -File "$installPath\AUTO_UPDATE.ps1"

echo.
echo Starting application...
echo.

REM Start the packaged application entrypoint
start "Arrow Limousine Dispatch" /wait "$appInstallPath\START_DISPATCH.bat"

pause
"@

$launcherPath = Join-Path $installPath "START_DISPATCH1.bat"
$launcherScript | Out-File -FilePath $launcherPath -Encoding ASCII
Write-Host "      [OK] Compatibility launcher created: START_DISPATCH1.bat" -ForegroundColor Green

# Create desktop shortcuts
Write-Host ""
Write-Host "[8/8] Creating desktop shortcuts..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")

# Shortcut to launcher
$shortcut = $WshShell.CreateShortcut("$desktopPath\Arrow Limo Dispatch.lnk")
$shortcut.TargetPath = $launcherPath
$shortcut.WorkingDirectory = $installPath
$shortcut.Description = "Arrow Limousine Management System - DISPATCH1"
$shortcut.IconLocation = "shell32.dll,165"
$shortcut.Save()

Write-Host "      [OK] Desktop shortcut created!" -ForegroundColor Green

# Final summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installation Details:" -ForegroundColor Cyan
Write-Host "  - Install Location: $installPath" -ForegroundColor Gray
Write-Host "  - App Entry Point: $appInstallPath\START_DISPATCH.bat" -ForegroundColor Gray
Write-Host "  - Shared Files: $SharedDrive\limo_files" -ForegroundColor Gray
if ($lDriveMapped) {
    Write-Host "  - Auto-Update: Enabled (from L:\limo)" -ForegroundColor Gray
} else {
    Write-Host "  - Auto-Update: Disabled (L: not mapped)" -ForegroundColor Yellow
}
Write-Host "  - Workstation ID: DISPATCH1" -ForegroundColor Gray
Write-Host "  - Database Host: $dbHost" -ForegroundColor Gray
Write-Host ""
Write-Host "To Start:" -ForegroundColor Cyan
Write-Host "  Double-click 'Arrow Limo Dispatch' on desktop" -ForegroundColor White
Write-Host "  OR run: $appInstallPath\START_DISPATCH.bat" -ForegroundColor Gray
Write-Host "  Legacy wrapper remains at: $launcherPath" -ForegroundColor Gray
Write-Host ""
Write-Host "The app will auto-update from the development" -ForegroundColor Yellow
Write-Host "computer each time it launches." -ForegroundColor Yellow
Write-Host ""
pause
