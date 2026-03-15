# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DISPATCH1 COMPLETE SETUP SCRIPT
# Automated setup for DISPATCH1 workstation from VS Code
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 
# This script handles EVERYTHING on DISPATCH1:
# âœ“ Creates Y: drive (virtual disk for application)
# âœ“ Maps network drives (L: and Z:)
# âœ“ Installs application to Y:\ArrowLimo
# âœ“ Configures .env with DISPATCHMAIN database connection
# âœ“ Removes old installations (C:\ArrowLimo if exists)
# âœ“ Creates desktop shortcuts
# âœ“ Sets up auto-update from L: drive
# âœ“ Tests database connectivity
#
# Run this script AS ADMINISTRATOR from VS Code on DISPATCH1
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

#Requires -RunAsAdministrator

param(
    [string]$DispatchMainIP = "",
    [string]$PostgresPassword = "",
    [switch]$SkipCleanup,
    [switch]$ForceReinstall
)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CONFIGURATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

$Script:Config = @{
    DispatchMainIP = $DispatchMainIP
    PostgresPassword = $PostgresPassword
    YDrivePath = "Y:\ArrowLimo"
    YDriveSize = 10GB  # 10GB virtual disk for application
    LDrivePath = "\\DISPATCHMAIN\limo"
    ZDrivePath = "\\DISPATCHMAIN\limo_files"
    OldInstallPath = "C:\ArrowLimo"
    DesktopShortcutName = "Arrow Limo DISPATCH1.lnk"
    DBName = "almsdata"
    DBUser = "postgres"
    DBPort = 5432
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# HELPER FUNCTIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "âœ“ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "â†’ $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "âœ— $Message" -ForegroundColor Red
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-UserInput {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [switch]$Secure
    )
    
    if ($Default) {
        $promptText = "$Prompt [$Default]"
    } else {
        $promptText = $Prompt
    }
    
    if ($Secure) {
        $secureInput = Read-Host -Prompt $promptText -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureInput)
        $input = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    } else {
        $input = Read-Host -Prompt $promptText
    }
    
    if ([string]::IsNullOrWhiteSpace($input) -and $Default) {
        return $Default
    }
    return $input
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 1: PRE-FLIGHT CHECKS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Test-Prerequisites {
    Write-Section "STEP 1: Pre-Flight Checks"
    
    # Check administrator
    if (-not (Test-Administrator)) {
        Write-Error-Custom "This script must be run as Administrator"
        Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
        exit 1
    }
    Write-Success "Running as Administrator"
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python installed: $pythonVersion"
    } catch {
        Write-Error-Custom "Python not found. Please install Python 3.10 or higher"
        Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
    
    # Check if DISPATCHMAIN is accessible
    Write-Info "Testing connection to DISPATCHMAIN..."
    if (Test-Connection -ComputerName "DISPATCHMAIN" -Count 2 -Quiet) {
        Write-Success "DISPATCHMAIN is accessible on network"
    } else {
        Write-Error-Custom "Cannot reach DISPATCHMAIN on network"
        Write-Host "Make sure DISPATCHMAIN is turned on and both computers are on same network" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Success "Pre-flight checks passed"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 2: GATHER CONFIGURATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Get-Configuration {
    Write-Section "STEP 2: Configuration"
    
    # Get DISPATCHMAIN IP
    if ([string]::IsNullOrWhiteSpace($Script:Config.DispatchMainIP)) {
        Write-Host "Enter the IP address of DISPATCHMAIN" -ForegroundColor Cyan
        Write-Host "Run this on DISPATCHMAIN to find it: .\GET_DISPATCHMAIN_IP.ps1" -ForegroundColor Gray
        Write-Host ""
        $Script:Config.DispatchMainIP = Get-UserInput -Prompt "DISPATCHMAIN IP Address"
    }
    
    # Validate IP format
    if ($Script:Config.DispatchMainIP -notmatch '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$') {
        Write-Error-Custom "Invalid IP address format"
        exit 1
    }
    Write-Success "Database server: $($Script:Config.DispatchMainIP)"
    
    # Get PostgreSQL password
    if ([string]::IsNullOrWhiteSpace($Script:Config.PostgresPassword)) {
        Write-Host ""
        Write-Host "Enter the PostgreSQL password from DISPATCHMAIN" -ForegroundColor Cyan
        Write-Host "(This is the 'postgres' user password set during PostgreSQL installation)" -ForegroundColor Gray
        Write-Host ""
        $Script:Config.PostgresPassword = Get-UserInput -Prompt "PostgreSQL Password" -Secure
    }
    
    Write-Host ""
    Write-Success "Configuration collected"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 3: CREATE Y: DRIVE (VIRTUAL DISK)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Initialize-YDrive {
    Write-Section "STEP 3: Create Y: Drive"
    
    # Check if Y: already exists
    if (Test-Path "Y:\") {
        Write-Info "Y: drive already exists"
        
        if ($ForceReinstall) {
            Write-Info "Force reinstall requested - will use existing Y: drive"
        } else {
            $response = Read-Host "Y: drive exists. Use it? (y/n)"
            if ($response -ne 'y') {
                Write-Error-Custom "Setup cancelled by user"
                exit 1
            }
        }
        Write-Success "Using existing Y: drive"
        return
    }
    
    Write-Info "Creating virtual disk for Y: drive..."
    
    # Create VHD file in user's home directory
    $vhdPath = "$env:USERPROFILE\ArrowLimoY.vhdx"
    
    try {
        # Create virtual disk
        $vhd = New-VHD -Path $vhdPath -SizeBytes $Script:Config.YDriveSize -Dynamic
        Write-Success "Virtual disk created: $vhdPath"
        
        # Mount it
        $mounted = Mount-VHD -Path $vhdPath -Passthru
        Write-Success "Virtual disk mounted"
        
        # Initialize and format
        $disk = Get-Disk | Where-Object { $_.Location -eq $vhdPath }
        Initialize-Disk -Number $disk.Number -PartitionStyle MBR
        $partition = New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter Y
        Format-Volume -DriveLetter Y -FileSystem NTFS -NewFileSystemLabel "ArrowLimo" -Confirm:$false
        Write-Success "Y: drive created and formatted"
        
    } catch {
        Write-Error-Custom "Failed to create Y: drive: $_"
        Write-Host "Alternative: Use Disk Management to create Y: drive manually" -ForegroundColor Yellow
        exit 1
    }
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 4: MAP NETWORK DRIVES
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Map-NetworkDrives {
    Write-Section "STEP 4: Map Network Drives"
    
    # Map L: drive (code source)
    Write-Info "Mapping L: drive to $($Script:Config.LDrivePath)..."
    try {
        if (Test-Path "L:\") {
            net use L: /delete /y 2>$null
        }
        net use L: $Script:Config.LDrivePath /persistent:yes
        Write-Success "L: drive mapped (code source for auto-update)"
    } catch {
        Write-Error-Custom "Failed to map L: drive: $_"
        Write-Host "Make sure the share \\DISPATCHMAIN\limo exists" -ForegroundColor Yellow
        exit 1
    }
    
    # Map Z: drive (shared files)
    Write-Info "Mapping Z: drive to $($Script:Config.ZDrivePath)..."
    try {
        if (Test-Path "Z:\") {
            net use Z: /delete /y 2>$null
        }
        net use Z: $Script:Config.ZDrivePath /persistent:yes
        Write-Success "Z: drive mapped (shared documents/exports)"
    } catch {
        Write-Error-Custom "Failed to map Z: drive: $_"
        Write-Host "Make sure the share \\DISPATCHMAIN\limo_files exists" -ForegroundColor Yellow
        exit 1
    }
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 5: INSTALL APPLICATION TO Y: DRIVE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Install-Application {
    Write-Section "STEP 5: Install Application"
    
    # Create application directory
    Write-Info "Creating application directory on Y: drive..."
    if (-not (Test-Path $Script:Config.YDrivePath)) {
        New-Item -ItemType Directory -Path $Script:Config.YDrivePath -Force | Out-Null
        Write-Success "Created $($Script:Config.YDrivePath)"
    }
    
    # Copy application files from L: drive
    Write-Info "Copying application files from L:\limo\desktop_app..."
    $sourcePath = "L:\limo\desktop_app"
    $destPath = "$($Script:Config.YDrivePath)\desktop_app"
    
    if (-not (Test-Path $sourcePath)) {
        Write-Error-Custom "Source path not found: $sourcePath"
        Write-Host "Make sure L: drive is mapped and DISPATCHMAIN has the application" -ForegroundColor Yellow
        exit 1
    }
    
    # Copy desktop_app folder
    Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
    Write-Success "Application files copied"
    
    # Copy Python dependencies (requirements.txt)
    if (Test-Path "L:\limo\requirements.txt") {
        Copy-Item -Path "L:\limo\requirements.txt" -Destination "$($Script:Config.YDrivePath)\requirements.txt" -Force
        Write-Success "Requirements file copied"
    }
    
    # Install Python packages
    Write-Info "Installing Python dependencies..."
    $reqFile = "$($Script:Config.YDrivePath)\requirements.txt"
    if (Test-Path $reqFile) {
        python -m pip install --upgrade pip --quiet
        python -m pip install -r $reqFile --quiet
        Write-Success "Python packages installed"
    } else {
        # Install minimum required packages
        python -m pip install psycopg2-binary PyQt6 python-dotenv --quiet
        Write-Success "Core packages installed"
    }
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 6: CREATE .ENV CONFIGURATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function New-EnvFile {
    Write-Section "STEP 6: Create Configuration File"
    
    $envPath = "$($Script:Config.YDrivePath)\.env"
    
    $envContent = @"
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DISPATCH1 CONFIGURATION - Network PostgreSQL
# Auto-generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# DATABASE CONNECTION (Network PostgreSQL on DISPATCHMAIN)
DB_HOST=$($Script:Config.DispatchMainIP)
DB_NAME=$($Script:Config.DBName)
DB_USER=$($Script:Config.DBUser)
DB_PASSWORD=$($Script:Config.PostgresPassword)
DB_PORT=$($Script:Config.DBPort)

# WORKSTATION IDENTIFICATION
WORKSTATION_ID=DISPATCH1

# RECEIPT WIDGET CONFIGURATION
RECEIPT_WIDGET_WRITE_ENABLED=true

# FILE PATHS
SHARED_FILES_PATH=Z:\\limo_files

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# NETWORK POSTGRESQL ARCHITECTURE
# 
# This workstation connects to PostgreSQL database on DISPATCHMAIN
# Both DISPATCHMAIN and DISPATCH1 share same database in real-time
# 
# Database Server: $($Script:Config.DispatchMainIP):$($Script:Config.DBPort)
# Local Network: 10-50x faster than cloud database
# Offline Capable: No internet required
# Multi-User: PostgreSQL handles concurrent access automatically
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
"@
    
    $envContent | Out-File -FilePath $envPath -Encoding UTF8 -Force
    Write-Success "Configuration file created: $envPath"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 6B: CREATE HYBRID AUTO-DETECTION FILES
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function New-HybridConfiguration {
    Write-Section "STEP 6B: Create Hybrid Auto-Detection Configuration"
    
    Write-Info "Setting up hybrid local/cloud database auto-detection..."
    
    # Create .env.local (local network config)
    if (Test-Path "L:\limo\DEPLOYMENT_PACKAGE\.env.local.dispatch1") {
        $envLocalPath = "$($Script:Config.YDrivePath)\.env.local"
        Copy-Item -Path "L:\limo\DEPLOYMENT_PACKAGE\.env.local.dispatch1" -Destination $envLocalPath -Force
        
        # Update with actual IP
        (Get-Content $envLocalPath) -replace '192\.168\.1\.100', $Script:Config.DispatchMainIP | Out-File -FilePath $envLocalPath -Encoding UTF8 -Force
        Write-Success "Local network configuration created (.env.local)"
    }
    
    # Create .env.cloud (cloud config)
    if (Test-Path "L:\limo\DEPLOYMENT_PACKAGE\.env.cloud.dispatch1") {
        $envCloudPath = "$($Script:Config.YDrivePath)\.env.cloud"
        Copy-Item -Path "L:\limo\DEPLOYMENT_PACKAGE\.env.cloud.dispatch1" -Destination $envCloudPath -Force
        Write-Success "Cloud database configuration created (.env.cloud)"
    }
    
    # Copy smart launcher
    if (Test-Path "L:\limo\smart_launcher.py") {
        Copy-Item -Path "L:\limo\smart_launcher.py" -Destination "$($Script:Config.YDrivePath)\smart_launcher.py" -Force
        
        # Update DISPATCHMAIN_IP in smart launcher
        $smartLauncherPath = "$($Script:Config.YDrivePath)\smart_launcher.py"
        (Get-Content $smartLauncherPath) -replace 'DISPATCHMAIN_IP = "192\.168\.1\.100"', "DISPATCHMAIN_IP = `"$($Script:Config.DispatchMainIP)`"" | Out-File -FilePath $smartLauncherPath -Encoding UTF8 -Force
        Write-Success "Smart launcher installed (auto-detects network location)"
    }
    
    # Copy START_HYBRID.bat
    if (Test-Path "L:\limo\START_HYBRID.bat") {
        $hybridBatPath = "$($Script:Config.YDrivePath)\START_HYBRID.bat"
        $hybridBatContent = @"
@echo off
REM Arrow Limousine Hybrid Smart Launcher for DISPATCH1
cd /d Y:\ArrowLimo
python smart_launcher.py
if errorlevel 1 pause
"@
        $hybridBatContent | Out-File -FilePath $hybridBatPath -Encoding ASCII -Force
        Write-Success "Hybrid launcher created (START_HYBRID.bat)"
    }
    
    Write-Host ""
    Write-Host "  âœ“ Hybrid setup complete!" -ForegroundColor Green
    Write-Host "  â†’ IN OFFICE: Uses local PostgreSQL (fast)" -ForegroundColor Cyan
    Write-Host "  â†’ OFF-SITE: Uses Neon cloud (accessible anywhere)" -ForegroundColor Cyan
    Write-Host "  â†’ Auto-detects location on each launch" -ForegroundColor Cyan
    Write-Host ""
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 7: CREATE AUTO-UPDATE SCRIPT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function New-AutoUpdateScript {
    Write-Section "STEP 7: Create Auto-Update Script"
    
    $updateScriptPath = "$($Script:Config.YDrivePath)\auto_update.ps1"
    
    $updateScript = @'
# Auto-Update Script for DISPATCH1
# Syncs application files from L:\limo\desktop_app to Y:\ArrowLimo\desktop_app

$SourcePath = "L:\limo\desktop_app"
$DestPath = "Y:\ArrowLimo\desktop_app"

Write-Host "Checking for updates from DISPATCHMAIN..." -ForegroundColor Cyan

if (-not (Test-Path $SourcePath)) {
    Write-Host "Source not accessible. Make sure DISPATCHMAIN is on and L: drive is mapped." -ForegroundColor Yellow
    exit 1
}

# Compare modification times
$sourceModified = (Get-Item $SourcePath).LastWriteTime
$destModified = (Get-Item $DestPath).LastWriteTime

if ($sourceModified -gt $destModified) {
    Write-Host "Updates found! Syncing..." -ForegroundColor Green
    Copy-Item -Path "$SourcePath\*" -Destination $DestPath -Recurse -Force
    Write-Host "Update complete!" -ForegroundColor Green
} else {
    Write-Host "Application is up to date." -ForegroundColor Green
}
'@
    
    $updateScript | Out-File -FilePath $updateScriptPath -Encoding UTF8 -Force
    Write-Success "Auto-update script created: $updateScriptPath"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 8: CREATE LAUNCHER SCRIPT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function New-LauncherScript {
    Write-Section "STEP 8: Create Launcher"
    
    $launcherPath = "$($Script:Config.YDrivePath)\START_DISPATCH1.bat"
    
    $launcherContent = @"
@echo off
REM Arrow Limousine DISPATCH1 Launcher
REM Auto-updates from L: drive on each launch

echo â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
echo  ARROW LIMOUSINE DISPATCH1
echo â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
echo.

REM Check for updates
if exist "Y:\ArrowLimo\auto_update.ps1" (
    echo Checking for updates...
    powershell -ExecutionPolicy Bypass -File "Y:\ArrowLimo\auto_update.ps1"
    echo.
)

REM Launch application
echo Starting application...
cd /d Y:\ArrowLimo\desktop_app
python launcher.py

if errorlevel 1 (
    echo.
    echo â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    echo  ERROR: Application failed to start
    echo â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    echo.
    echo Check Y:\ArrowLimo\app_errors.log for details
    pause
)
"@
    
    $launcherContent | Out-File -FilePath $launcherPath -Encoding ASCII -Force
    Write-Success "Launcher created: $launcherPath"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 9: CREATE DESKTOP SHORTCUT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function New-DesktopShortcut {
    Write-Section "STEP 9: Create Desktop Shortcut"
    
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath $Script:Config.DesktopShortcutName
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = "$($Script:Config.YDrivePath)\START_DISPATCH1.bat"
    $Shortcut.WorkingDirectory = "$($Script:Config.YDrivePath)\desktop_app"
    $Shortcut.Description = "Arrow Limousine Dispatch System (DISPATCH1)"
    $Shortcut.IconLocation = "shell32.dll,165"  # Car icon
    $Shortcut.Save()
    
    Write-Success "Desktop shortcut created: $shortcutPath"
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 10: TEST DATABASE CONNECTION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Test-DatabaseConnection {
    Write-Section "STEP 10: Test Database Connection"
    
    Write-Info "Testing connection to PostgreSQL on DISPATCHMAIN..."
    
    # Test port connectivity
    Write-Info "Testing port $($Script:Config.DBPort)..."
    $portTest = Test-NetConnection -ComputerName $Script:Config.DispatchMainIP -Port $Script:Config.DBPort -WarningAction SilentlyContinue
    
    if ($portTest.TcpTestSucceeded) {
        Write-Success "Port $($Script:Config.DBPort) is accessible"
    } else {
        Write-Error-Custom "Port $($Script:Config.DBPort) is blocked or PostgreSQL not listening"
        Write-Host "Run SETUP_POSTGRESQL_NETWORK_ACCESS.ps1 on DISPATCHMAIN" -ForegroundColor Yellow
        return $false
    }
    
    # Test database connection with Python
    Write-Info "Testing database login..."
    
    # Create Python test script (using string building to avoid quote issues)
    $testScriptPath = "$env:TEMP\test_db_connection.py"
    
    @"
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host="$($Script:Config.DispatchMainIP)",
        database="$($Script:Config.DBName)",
        user="$($Script:Config.DBUser)",
        password="$($Script:Config.PostgresPassword)",
        port=$($Script:Config.DBPort)
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    table_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    print("SUCCESS|" + str(table_count))
except Exception as e:
    print("ERROR|" + str(e))
    sys.exit(1)
"@ | Out-File -FilePath $testScriptPath -Encoding UTF8 -Force
    
    try {
        $result = python $testScriptPath 2>&1
        Remove-Item $testScriptPath -Force
        
        if ($result -match '^SUCCESS\|(\d+)') {
            $tableCount = $Matches[1]
            Write-Success "Database connection successful!"
            Write-Success "Connected to database with $tableCount tables"
            return $true
        } else {
            Write-Error-Custom "Database connection failed: $result"
            Write-Host "Check credentials and network configuration" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Error-Custom "Failed to test database: $_"
        return $false
    }
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 11: CLEANUP OLD INSTALLATIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Remove-OldInstallation {
    Write-Section "STEP 11: Cleanup Old Installations"
    
    if ($SkipCleanup) {
        Write-Info "Skipping cleanup (SkipCleanup flag set)"
        return
    }
    
    # Check for old installation on C: drive
    if (Test-Path $Script:Config.OldInstallPath) {
        Write-Info "Found old installation: $($Script:Config.OldInstallPath)"
        
        $response = Read-Host "Remove old installation? (y/n)"
        if ($response -eq 'y') {
            try {
                Remove-Item -Path $Script:Config.OldInstallPath -Recurse -Force
                Write-Success "Old installation removed"
            } catch {
                Write-Error-Custom "Failed to remove old installation: $_"
                Write-Host "You may need to manually delete $($Script:Config.OldInstallPath)" -ForegroundColor Yellow
            }
        } else {
            Write-Info "Keeping old installation"
        }
    } else {
        Write-Info "No old installation found on C: drive"
    }
    
    # Remove old desktop shortcuts
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $oldShortcuts = @(
        "Arrow Limousine Dispatch.lnk",
        "Arrow Limo.lnk",
        "DISPATCH1.lnk"
    )
    
    foreach ($shortcut in $oldShortcuts) {
        $oldShortcutPath = Join-Path $desktopPath $shortcut
        if (Test-Path $oldShortcutPath) {
            Remove-Item -Path $oldShortcutPath -Force
            Write-Success "Removed old shortcut: $shortcut"
        }
    }
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STEP 12: FINAL VERIFICATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Test-Installation {
    Write-Section "STEP 12: Final Verification"
    
    $allGood = $true
    
    # Check Y: drive
    if (Test-Path "Y:\") {
        Write-Success "Y: drive exists"
    } else {
        Write-Error-Custom "Y: drive not found"
        $allGood = $false
    }
    
    # Check L: drive
    if (Test-Path "L:\") {
        Write-Success "L: drive mapped"
    } else {
        Write-Error-Custom "L: drive not mapped"
        $allGood = $false
    }
    
    # Check Z: drive
    if (Test-Path "Z:\") {
        Write-Success "Z: drive mapped"
    } else {
        Write-Error-Custom "Z: drive not mapped"
        $allGood = $false
    }
    
    # Check application files
    if (Test-Path "$($Script:Config.YDrivePath)\desktop_app\launcher.py") {
        Write-Success "Application files installed"
    } else {
        Write-Error-Custom "Application files not found"
        $allGood = $false
    }
    
    # Check .env
    if (Test-Path "$($Script:Config.YDrivePath)\.env") {
        Write-Success "Configuration file exists"
    } else {
        Write-Error-Custom "Configuration file not found"
        $allGood = $false
    }
    
    # Check desktop shortcut
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath $Script:Config.DesktopShortcutName
    if (Test-Path $shortcutPath) {
        Write-Success "Desktop shortcut created"
    } else {
        Write-Error-Custom "Desktop shortcut not found"
        $allGood = $false
    }
    
    return $allGood
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MAIN EXECUTION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function Main {
    Clear-Host
    
    Write-Host ""
    Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
    Write-Host "  DISPATCH1 COMPLETE SETUP" -ForegroundColor Cyan
    Write-Host "  Arrow Limousine Management System - Network PostgreSQL Edition" -ForegroundColor Cyan
    Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "This script will:" -ForegroundColor Yellow
    Write-Host "  â€¢ Create Y: drive for application (10GB virtual disk)" -ForegroundColor White
    Write-Host "  â€¢ Map L: and Z: network drives" -ForegroundColor White
    Write-Host "  â€¢ Install application to Y:\ArrowLimo" -ForegroundColor White
    Write-Host "  â€¢ Configure database connection to DISPATCHMAIN" -ForegroundColor White
    Write-Host "  â€¢ Setup hybrid auto-detection (local/cloud database)" -ForegroundColor White
    Write-Host "  â€¢ Remove old installations (if any)" -ForegroundColor White
    Write-Host "  â€¢ Create desktop shortcut" -ForegroundColor White
    Write-Host "  â€¢ Test database connectivity" -ForegroundColor White
    Write-Host ""
    Write-Host "Estimated time: 10-15 minutes" -ForegroundColor Green
    Write-Host ""
    
    $response = Read-Host "Continue with setup? (y/n)"
    if ($response -ne 'y') {
        Write-Host "Setup cancelled by user" -ForegroundColor Yellow
        exit 0
    }
    
    try {
        # Execute setup steps
        Test-Prerequisites
        Get-Configuration
        Initialize-YDrive
        Map-NetworkDrives
        Install-Application
        New-EnvFile
        New-HybridConfiguration
        New-AutoUpdateScript
        New-LauncherScript
        New-DesktopShortcut
        
        $dbConnected = Test-DatabaseConnection
        
        Remove-OldInstallation
        
        $installOk = Test-Installation
        
        # Final summary
        Write-Section "SETUP COMPLETE"
        
        if ($installOk -and $dbConnected) {
            Write-Host "âœ“ DISPATCH1 is fully configured and ready to use!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Installation Details:" -ForegroundColor Cyan
            Write-Host "  â€¢ Application: $($Script:Config.YDrivePath)" -ForegroundColor White
            Write-Host "  â€¢ Database: $($Script:Config.DispatchMainIP):$($Script:Config.DBPort)" -ForegroundColor White
            Write-Host "  â€¢ Workstation: DISPATCH1" -ForegroundColor White
            Write-Host ""
            Write-Host "To launch the application:" -ForegroundColor Cyan
            Write-Host "  â€¢ Double-click 'Arrow Limo DISPATCH1' on desktop" -ForegroundColor White
            Write-Host "  â€¢ Or run: $($Script:Config.YDrivePath)\START_DISPATCH1.bat" -ForegroundColor White
            Write-Host ""
            Write-Host "Auto-Update:" -ForegroundColor Cyan
            Write-Host "  â€¢ Application syncs from L:\limo on each launch" -ForegroundColor White
            Write-Host "  â€¢ Edit code on DISPATCHMAIN â†’ restart here â†’ changes applied" -ForegroundColor White
            Write-Host ""
            Write-Host "Network Drives:" -ForegroundColor Cyan
            Write-Host "  â€¢ L: â†’ \\DISPATCHMAIN\limo (code source)" -ForegroundColor White
            Write-Host "  â€¢ Z: â†’ \\DISPATCHMAIN\limo_files (shared files)" -ForegroundColor White
            Write-Host ""
            
        } elseif ($installOk -and -not $dbConnected) {
            Write-Host "âš  Installation complete but database connection failed" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Cyan
            Write-Host "  1. Verify DISPATCHMAIN PostgreSQL is configured for network access" -ForegroundColor White
            Write-Host "  2. Run SETUP_POSTGRESQL_NETWORK_ACCESS.ps1 on DISPATCHMAIN" -ForegroundColor White
            Write-Host "  3. Run TEST_DATABASE_CONNECTION.ps1 to verify" -ForegroundColor White
            Write-Host ""
            
        } else {
            Write-Host "âœ— Setup completed with errors" -ForegroundColor Red
            Write-Host "Review the messages above and retry" -ForegroundColor Yellow
            Write-Host ""
        }
        
        Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
        Write-Host ""
        
    } catch {
        Write-Host ""
        Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Red
        Write-Host " SETUP FAILED" -ForegroundColor Red
        Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Red
        Write-Host ""
        Write-Host "Error: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Stack Trace:" -ForegroundColor Yellow
        Write-Host $_.ScriptStackTrace -ForegroundColor Gray
        Write-Host ""
        exit 1
    }
}

# Run main function
Main

