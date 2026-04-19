param(
    [string]$ServerName = "DISPATCHMAIN",
    [string]$InstallDrive = "Y:",
    [string]$SharedDrive = "Z:",
    [string]$ShareUsername,
    [string]$SharePassword
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
}

function Invoke-NetUse {
    param([string[]]$Args)
    & net use @Args
    return $LASTEXITCODE
}

function Add-CredentialTarget {
    param(
        [string]$Target,
        [string]$Username,
        [string]$Password
    )

    if (-not $Target -or -not $Username -or -not $Password) {
        return
    }

    cmdkey /add:$Target /user:$Username /pass:$Password | Out-Null
}

function Clear-MappingAndCreds {
    param(
        [string]$Drive,
        [string[]]$Targets
    )

    try { Invoke-NetUse -Args @($Drive, "/delete", "/yes") | Out-Null } catch {}

    foreach ($target in $Targets) {
        if ($target) {
            try { cmdkey /delete:$target | Out-Null } catch {}
        }
    }
}

function Resolve-ServerTarget {
    param([string]$Name)

    try {
        $ping = Test-Connection -ComputerName $Name -Count 1 -ErrorAction Stop
        if ($ping -and $ping[0].Address) {
            return $ping[0].Address.IPAddressToString
        }
    } catch {}

    return $Name
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DISPATCH1 One-Click Repair + Install" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Please run as Administrator." -ForegroundColor Red
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $scriptDir "DispatchInstaller_Dispatch1.ps1"
if (-not (Test-Path $installer)) {
    Write-Host "[ERROR] Installer not found: $installer" -ForegroundColor Red
    exit 1
}

$serverTarget = Resolve-ServerTarget -Name $ServerName
Write-Host "Using server target: $serverTarget" -ForegroundColor Gray

if (-not $ShareUsername) {
    $defaultUser = "$ServerName\ArrowDispatch"
    $inputUser = Read-Host "Share username [$defaultUser]"
    if (-not $inputUser) {
        $ShareUsername = $defaultUser
    } else {
        $ShareUsername = $inputUser
    }
}

if (-not $SharePassword) {
    $pwSecure = Read-Host "Share password for $ShareUsername" -AsSecureString
    $pwBstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwSecure)
    $SharePassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($pwBstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pwBstr)
}

Write-Step "[1/4] Clearing stale drive mappings and cached credentials"
Clear-MappingAndCreds -Drive "L:" -Targets @($ServerName, $serverTarget)
Clear-MappingAndCreds -Drive $SharedDrive -Targets @($ServerName, $serverTarget)

Write-Step "[2/4] Seeding Windows credential targets"
Add-CredentialTarget -Target $ServerName -Username $ShareUsername -Password $SharePassword
Add-CredentialTarget -Target $serverTarget -Username $ShareUsername -Password $SharePassword

Write-Step "[3/4] Pre-mapping network shares"
$lRc = Invoke-NetUse -Args @("L:", "\\$serverTarget\limo", "/user:$ShareUsername", $SharePassword, "/persistent:yes")
if ($lRc -eq 0) {
    Write-Host "      [OK] L: mapped to \\$serverTarget\limo" -ForegroundColor Green
} else {
    Write-Host "      [ERROR] Could not map L: preflight." -ForegroundColor Red
}

$zRc = Invoke-NetUse -Args @($SharedDrive, "\\$serverTarget\limo_files", "/user:$ShareUsername", $SharePassword, "/persistent:yes")
if ($zRc -eq 0) {
    Write-Host "      [OK] $SharedDrive mapped to \\$serverTarget\limo_files" -ForegroundColor Green
} else {
    Write-Host "      [ERROR] Could not map $SharedDrive preflight." -ForegroundColor Red
}

if ($lRc -ne 0 -or $zRc -ne 0) {
    Write-Host "" 
    Write-Host "Mapping failed. Check credentials and share availability before installer run." -ForegroundColor Red
    Write-Host "Try: net use L: \\$serverTarget\limo /user:$ShareUsername <password> /persistent:yes" -ForegroundColor Yellow
    Write-Host "Try: net use $SharedDrive \\$serverTarget\limo_files /user:$ShareUsername <password> /persistent:yes" -ForegroundColor Yellow
    exit 2
}

Write-Step "[4/4] Running Dispatch1 installer"
& powershell -NoProfile -ExecutionPolicy Bypass -File $installer -ServerName $serverTarget -InstallDrive $InstallDrive -SharedDrive $SharedDrive
$installExit = $LASTEXITCODE
if ($installExit -ne 0) {
    Write-Host "[ERROR] Installer exited with code $installExit" -ForegroundColor Red
    exit $installExit
}

Write-Step "[Final] Link status"
$finalL = Test-Path "L:\"
$finalZ = Test-Path "$SharedDrive\\"
Write-Host "      L: available = $finalL" -ForegroundColor Gray
Write-Host "      $SharedDrive available = $finalZ" -ForegroundColor Gray
Write-Host "      App launcher: Y:\ArrowLimo\START_DISPATCH1.bat" -ForegroundColor Gray
Write-Host ""
net use
Write-Host ""
Write-Host "Done. Use desktop shortcut 'Arrow Limo Dispatch' or run Y:\ArrowLimo\START_DISPATCH1.bat" -ForegroundColor Green
