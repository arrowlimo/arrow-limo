param(
    [string]$InstallRoot = $PSScriptRoot,
    [switch]$AutoRepairPython,
    [switch]$ForceRepairVCRedist
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

function Get-BundledPythonExe([string]$InstallRootPath) {
    return (Join-Path $InstallRootPath ".venv\Scripts\python.exe")
}

function Get-PythonVersion([string]$PythonExe) {
    $version = & $PythonExe -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"
    if ($LASTEXITCODE -ne 0 -or -not $version) {
        throw "Unable to detect bundled Python version."
    }
    return $version.Trim()
}

function Get-RequirementsHash([string]$InstallRootPath) {
    $requirementsPath = Join-Path $InstallRootPath "modern_backend\requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        return $null
    }
    return (Get-FileHash -Path $requirementsPath -Algorithm SHA256).Hash
}

function ConvertFrom-JsonLenient([string]$JsonText) {
    try {
        return $JsonText | ConvertFrom-Json
    } catch {
        # Allow common human-edited JSON issue: trailing commas before } or ]
        $sanitized = [System.Text.RegularExpressions.Regex]::Replace(
            $JsonText,
            ',\s*(?=[}\]])',
            '',
            [System.Text.RegularExpressions.RegexOptions]::Multiline
        )

        return $sanitized | ConvertFrom-Json
    }
}

function Read-JsonFileLenient([string]$PathValue, [switch]$WriteBackIfSanitized) {
    $raw = Get-Content $PathValue -Raw
    try {
        return $raw | ConvertFrom-Json
    } catch {
        $sanitized = [System.Text.RegularExpressions.Regex]::Replace(
            $raw,
            ',\s*(?=[}\]])',
            '',
            [System.Text.RegularExpressions.RegexOptions]::Multiline
        )

        $obj = ConvertFrom-JsonLenient -JsonText $sanitized
        if ($WriteBackIfSanitized) {
            Set-Content -Path $PathValue -Value ($obj | ConvertTo-Json -Depth 8) -Encoding UTF8
        }
        return $obj
    }
}

function Test-PythonRepairRequired([string]$InstallRootPath, [string]$PythonExe) {
    $requirementsHash = Get-RequirementsHash -InstallRootPath $InstallRootPath
    if (-not $requirementsHash) {
        return $false
    }

    $stampPath = Join-Path $InstallRootPath ".venv\offsite_runtime_stamp.json"
    if (-not (Test-Path $stampPath)) {
        return $true
    }

    try {
        $stamp = Read-JsonFileLenient -PathValue $stampPath -WriteBackIfSanitized
    } catch {
        return $true
    }

    if ($stamp.requirements_hash -ne $requirementsHash) {
        return $true
    }

    $currentPython = Get-PythonVersion -PythonExe $PythonExe
    if ($stamp.python_version -ne $currentPython) {
        return $true
    }

    return $false
}

function Write-PythonRepairStamp([string]$InstallRootPath, [string]$PythonExe) {
    $requirementsHash = Get-RequirementsHash -InstallRootPath $InstallRootPath
    if (-not $requirementsHash) {
        return
    }

    $stampPath = Join-Path $InstallRootPath ".venv\offsite_runtime_stamp.json"
    $stamp = @{
        requirements_hash = $requirementsHash
        python_version = Get-PythonVersion -PythonExe $PythonExe
        stamped_at = (Get-Date).ToString("s")
    } | ConvertTo-Json -Depth 3
    Set-Content -Path $stampPath -Value $stamp -Encoding UTF8
}

function Repair-PythonEnvironment([string]$InstallRootPath) {
    $pythonExe = Get-BundledPythonExe -InstallRootPath $InstallRootPath
    $requirementsPath = Join-Path $InstallRootPath "modern_backend\requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        Write-Host "No requirements.txt found for backend; skipping pip repair." -ForegroundColor Yellow
        return
    }

    Write-Host "Repairing Python packages from bundled requirements..." -ForegroundColor Yellow

    & $pythonExe -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update pip/setuptools/wheel in bundled runtime."
    }

    & $pythonExe -m pip install --disable-pip-version-check --upgrade-strategy eager -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to repair Python dependencies from $requirementsPath"
    }

    Write-PythonRepairStamp -InstallRootPath $InstallRootPath -PythonExe $pythonExe
    Write-Host "Python dependency repair completed." -ForegroundColor Green
}

Assert-Admin
Assert-64BitWindows
Assert-BundledPython -InstallRootPath $InstallRoot

if ($ForceRepairVCRedist) {
    $installerPath = Join-Path $InstallRoot "prerequisites\vc_redist.x64.exe"
    if (-not (Test-Path $installerPath)) {
        throw "Visual C++ redistributable installer not found at $installerPath"
    }
    Write-Host "Running Visual C++ redistributable repair..." -ForegroundColor Yellow
    $repairProcess = Start-Process -FilePath $installerPath -ArgumentList "/repair", "/quiet", "/norestart" -Wait -PassThru
    if ($repairProcess.ExitCode -ne 0 -and $repairProcess.ExitCode -ne 1638 -and $repairProcess.ExitCode -ne 3010) {
        throw "Visual C++ redistributable repair failed with exit code $($repairProcess.ExitCode)"
    }
}

Install-VCRedistIfMissing -InstallRootPath $InstallRoot

if ($AutoRepairPython) {
    Repair-PythonEnvironment -InstallRootPath $InstallRoot
} else {
    $pythonExe = Get-BundledPythonExe -InstallRootPath $InstallRoot
    if (Test-PythonRepairRequired -InstallRootPath $InstallRoot -PythonExe $pythonExe) {
        Repair-PythonEnvironment -InstallRootPath $InstallRoot
    } else {
        Write-Host "Python dependency versions match installed requirements." -ForegroundColor Green
    }
}

Write-Host "Prerequisite bootstrap completed." -ForegroundColor Green