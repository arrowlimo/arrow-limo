param(
    [string]$InstallRoot = "C:\Program Files\ArrowLimoOffsite",
    [string]$PayloadRoot = (Join-Path $PSScriptRoot "payload")
)

$ErrorActionPreference = "Stop"

function Copy-Tree([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $null = robocopy $Source $Destination /E /R:1 /W:1 /NFL /NDL /NJH /NJS
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed for $Source"
    }
}

function Remove-Tree([string]$PathValue) {
    if (-not (Test-Path $PathValue)) {
        return
    }

    attrib -r -h -s "$PathValue\*" /S /D 2>$null | Out-Null
    Remove-Item -Path $PathValue -Recurse -Force
}

if (-not (Test-Path $InstallRoot)) {
    throw "Install root not found: $InstallRoot"
}

if (-not (Test-Path $PayloadRoot)) {
    throw "Payload root not found: $PayloadRoot"
}

$backupRoot = Join-Path $InstallRoot "_updates_backup"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $timestamp
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

foreach ($name in @("desktop_app", "modern_backend", "frontend", "prerequisites", "launcher.py", "START_ARROW_LIMO_OFFSITE.bat", "Bootstrap-Prereqs.ps1", "Configure-OffsiteInstall.ps1")) {
    $installedPath = Join-Path $InstallRoot $name
    if (Test-Path $installedPath) {
        if ((Get-Item $installedPath).PSIsContainer) {
            Copy-Tree $installedPath (Join-Path $backupDir $name)
        } else {
            Copy-Item $installedPath (Join-Path $backupDir $name) -Force
        }
    }
}

foreach ($name in @("desktop_app", "modern_backend", "frontend", "prerequisites")) {
    $source = Join-Path $PayloadRoot $name
    if (Test-Path $source) {
        Copy-Tree $source (Join-Path $InstallRoot $name)
    }
}

foreach ($name in @("launcher.py", "START_ARROW_LIMO_OFFSITE.bat", "Bootstrap-Prereqs.ps1", "Configure-OffsiteInstall.ps1")) {
    $source = Join-Path $PayloadRoot $name
    if (Test-Path $source) {
        Copy-Item $source (Join-Path $InstallRoot $name) -Force
    }
}

$runtimeSource = Join-Path $PayloadRoot ".venv"
if (Test-Path $runtimeSource) {
    $runtimeDest = Join-Path $InstallRoot ".venv"
    if (Test-Path $runtimeDest) {
        Write-Host "Replacing existing bundled runtime (.venv) to prevent version drift..." -ForegroundColor Yellow
        Remove-Tree $runtimeDest
    }
    Copy-Tree $runtimeSource $runtimeDest
}

$bootstrapScript = Join-Path $InstallRoot "Bootstrap-Prereqs.ps1"
if (Test-Path $bootstrapScript) {
    & powershell.exe -ExecutionPolicy Bypass -NoProfile -File $bootstrapScript -InstallRoot $InstallRoot -AutoRepairPython
}

$configureScript = Join-Path $InstallRoot "Configure-OffsiteInstall.ps1"
if (Test-Path $configureScript) {
    & powershell.exe -ExecutionPolicy Bypass -NoProfile -File $configureScript -InstallRoot $InstallRoot
}

Write-Host "Update applied successfully to $InstallRoot" -ForegroundColor Green