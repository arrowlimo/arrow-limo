param(
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [string]$InstallRoot = "C:\Program Files\ArrowLimoOffsite",
    [string]$DataRoot = "C:\ProgramData\ArrowLimoOffsite\Data",
    [switch]$FullReplace,
    [switch]$PreserveInstallRoot
)

$ErrorActionPreference = "Stop"

function Assert-PathExists([string]$PathValue, [string]$Label) {
    if (-not (Test-Path $PathValue)) {
        throw "$Label not found: $PathValue"
    }
}

function Get-ShortcutTarget([string]$ShortcutPath) {
    if (-not (Test-Path $ShortcutPath)) {
        return $null
    }

    try {
        $shell = New-Object -ComObject WScript.Shell
        return $shell.CreateShortcut($ShortcutPath)
    } catch {
        return $null
    }
}

function Test-DesktopShortcut([string]$InstallRootPath) {
    $commonDesktop = [Environment]::GetFolderPath("CommonDesktopDirectory")
    $desktopShortcutPath = Join-Path $commonDesktop "Arrow Limo Offsite.lnk"
    $launcherBat = Join-Path $InstallRootPath "START_ARROW_LIMO_OFFSITE.bat"
    $expectedTarget = Join-Path $env:WINDIR "System32\cmd.exe"
    $expectedArguments = "/c `"$launcherBat`""

    $shortcut = Get-ShortcutTarget -ShortcutPath $desktopShortcutPath
    if (-not $shortcut) {
        throw "Desktop shortcut not found or unreadable: $desktopShortcutPath"
    }

    if ($shortcut.TargetPath -ne $expectedTarget) {
        throw "Desktop shortcut target mismatch. Expected $expectedTarget, got $($shortcut.TargetPath)"
    }

    if ($shortcut.Arguments -ne $expectedArguments) {
        throw "Desktop shortcut arguments mismatch. Expected '$expectedArguments', got '$($shortcut.Arguments)'"
    }

    if ($shortcut.WorkingDirectory -ne $InstallRootPath) {
        throw "Desktop shortcut working directory mismatch. Expected '$InstallRootPath', got '$($shortcut.WorkingDirectory)'"
    }

    if (-not (Test-Path $launcherBat)) {
        throw "Launcher batch missing after install: $launcherBat"
    }

    Write-Host "Desktop shortcut validation passed: $desktopShortcutPath" -ForegroundColor Green
}

$runtimeRoot = $PSScriptRoot
$zipInstallerScript = Join-Path $runtimeRoot "Install-OffsiteFromZip.ps1"
$bootstrapScript = Join-Path $runtimeRoot "Bootstrap-Prereqs.ps1"
$configureScript = Join-Path $runtimeRoot "Configure-OffsiteInstall.ps1"

Assert-PathExists -PathValue $zipInstallerScript -Label "Install-OffsiteFromZip.ps1"
Assert-PathExists -PathValue $bootstrapScript -Label "Bootstrap-Prereqs.ps1"
Assert-PathExists -PathValue $configureScript -Label "Configure-OffsiteInstall.ps1"

Write-Host "[1/4] Applying package from zip..." -ForegroundColor Cyan
$useFullReplace = $FullReplace -or (-not $PreserveInstallRoot)
Write-Progress -Activity "Install + self-heal" -Status "Applying package" -PercentComplete 15
$zipArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $zipInstallerScript,
    "-ZipPath", $ZipPath,
    "-InstallRoot", $InstallRoot,
    "-DataRoot", $DataRoot
)
if ($useFullReplace) {
    $zipArgs += "-FullReplace"
}

& powershell.exe @zipArgs
if ($LASTEXITCODE -ne 0) {
    throw "Install-OffsiteFromZip.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "[2/4] Running prerequisite self-heal..." -ForegroundColor Cyan
Write-Progress -Activity "Install + self-heal" -Status "Repairing prerequisites" -PercentComplete 45
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -InstallRoot $InstallRoot -AutoRepairPython
if ($LASTEXITCODE -ne 0) {
    throw "Bootstrap-Prereqs.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "[3/4] Refreshing install configuration and shortcuts..." -ForegroundColor Cyan
Write-Progress -Activity "Install + self-heal" -Status "Refreshing configuration" -PercentComplete 72
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $configureScript -InstallRoot $InstallRoot -DataRoot $DataRoot
if ($LASTEXITCODE -ne 0) {
    throw "Configure-OffsiteInstall.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "[4/4] Verifying desktop shortcut wiring..." -ForegroundColor Cyan
Write-Progress -Activity "Install + self-heal" -Status "Verifying shortcuts" -PercentComplete 90
Test-DesktopShortcut -InstallRootPath $InstallRoot

Write-Host "Offsite install + self-heal completed successfully." -ForegroundColor Green
Write-Progress -Activity "Install + self-heal" -Status "Completed" -PercentComplete 100
Write-Progress -Activity "Install + self-heal" -Completed
