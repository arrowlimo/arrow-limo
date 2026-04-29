param(
    [string]$InstallRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator rights are required for prerequisite installation."
    }
}

function Assert-64BitWindows {
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "Arrow Limo Offsite requires a 64-bit Windows system."
    }
}

function Test-VCRedistInstalled {
    $runtimeDll = Join-Path $env:WINDIR "System32\vcruntime140.dll"
    $runtimeDll1 = Join-Path $env:WINDIR "System32\vcruntime140_1.dll"
    return (Test-Path $runtimeDll) -and (Test-Path $runtimeDll1)
}

function Install-VCRedistIfMissing([string]$InstallRootPath) {
    if (Test-VCRedistInstalled) {
        Write-Host "Visual C++ runtime detected." -ForegroundColor Green
        return
    }

    $installerPath = Join-Path $InstallRootPath "prerequisites\vc_redist.x64.exe"
    if (-not (Test-Path $installerPath)) {
        throw "Visual C++ redistributable installer not found at $installerPath"
    }

    Write-Host "Installing Visual C++ redistributable..." -ForegroundColor Yellow
    $process = Start-Process -FilePath $installerPath -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru
    if ($process.ExitCode -ne 0 -and $process.ExitCode -ne 1638 -and $process.ExitCode -ne 3010) {
        throw "Visual C++ redistributable installation failed with exit code $($process.ExitCode)"
    }

    if (-not (Test-VCRedistInstalled)) {
        throw "Visual C++ runtime still not detected after installer run."
    }

    Write-Host "Visual C++ runtime installed successfully." -ForegroundColor Green
}

function Assert-BundledPython([string]$InstallRootPath) {
    $pythonExe = Join-Path $InstallRootPath ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        throw "Bundled Python runtime is missing: $pythonExe"
    }
}

Assert-Admin
Assert-64BitWindows
Assert-BundledPython -InstallRootPath $InstallRoot
Install-VCRedistIfMissing -InstallRootPath $InstallRoot

Write-Host "Prerequisite bootstrap completed." -ForegroundColor Green