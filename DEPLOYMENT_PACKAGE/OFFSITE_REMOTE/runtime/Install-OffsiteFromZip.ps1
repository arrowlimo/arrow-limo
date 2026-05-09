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

function Resolve-ZipFromInput([string]$InputPath, [string]$WorkingRoot) {
    if ($InputPath -match '\.zip$') {
        return (Resolve-Path $InputPath).Path
    }

    if ($InputPath -notmatch '^(.*\.zip)\.part(\d{3})$') {
        throw "ZipPath must point to a .zip file or the first split part (*.zip.part001)."
    }

    $baseZip = $matches[1]
    $firstPartNumber = $matches[2]
    if ($firstPartNumber -ne '001') {
        throw "Use the first split part (*.zip.part001) when installing from split files."
    }

    $parts = Get-ChildItem -Path (Split-Path $InputPath -Parent) -Filter ([System.IO.Path]::GetFileName($baseZip) + '.part*') |
        Sort-Object Name

    if (-not $parts -or $parts.Count -eq 0) {
        throw "No split zip parts found for $baseZip"
    }

    $joinedZip = Join-Path $WorkingRoot ([System.IO.Path]::GetFileName($baseZip))
    $outStream = [System.IO.File]::Create($joinedZip)
    try {
        foreach ($part in $parts) {
            $inStream = [System.IO.File]::OpenRead($part.FullName)
            try {
                $inStream.CopyTo($outStream)
            } finally {
                $inStream.Dispose()
            }
        }
    } finally {
        $outStream.Dispose()
    }

    return $joinedZip
}

function Remove-Tree([string]$PathValue) {
    if (-not (Test-Path $PathValue)) {
        return
    }

    attrib -r -h -s "$PathValue\*" /S /D 2>$null | Out-Null
    Remove-Item -Path $PathValue -Recurse -Force
}

$zipInputPath = (Resolve-Path $ZipPath).Path
Assert-PathExists -PathValue $zipInputPath -Label "Zip package"

$extractRoot = Join-Path $env:TEMP ("ArrowLimoOffsiteZipInstall_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

$useFullReplace = $FullReplace -or (-not $PreserveInstallRoot)

try {
    Write-Progress -Activity "Installing Arrow Limo Offsite" -Status "Resolving package" -PercentComplete 8
    $zipFullPath = Resolve-ZipFromInput -InputPath $zipInputPath -WorkingRoot $extractRoot
    Write-Host "Extracting update zip..." -ForegroundColor Cyan
    Write-Progress -Activity "Installing Arrow Limo Offsite" -Status "Extracting package" -PercentComplete 22
    Expand-Archive -Path $zipFullPath -DestinationPath $extractRoot -Force

    $payloadRoot = Join-Path $extractRoot "payload"
    Assert-PathExists -PathValue $payloadRoot -Label "Extracted payload folder"

    $applyScript = Join-Path $PSScriptRoot "Apply-OffsiteUpdate.ps1"
    Assert-PathExists -PathValue $applyScript -Label "Apply-OffsiteUpdate.ps1"

    $applyArgs = @(
        "-ExecutionPolicy", "Bypass",
        "-NoProfile",
        "-File", $applyScript,
        "-InstallRoot", $InstallRoot,
        "-PayloadRoot", $payloadRoot
    )
    if ($useFullReplace) {
        $applyArgs += "-FullReplace"
    }

    Write-Host "Applying package to $InstallRoot..." -ForegroundColor Cyan
    Write-Progress -Activity "Installing Arrow Limo Offsite" -Status "Applying files" -PercentComplete 52
    & powershell.exe @applyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Apply-OffsiteUpdate.ps1 failed with exit code $LASTEXITCODE"
    }

    $configureScript = Join-Path $InstallRoot "Configure-OffsiteInstall.ps1"
    if (Test-Path $configureScript) {
        Write-Host "Refreshing install configuration..." -ForegroundColor Cyan
        Write-Progress -Activity "Installing Arrow Limo Offsite" -Status "Refreshing configuration" -PercentComplete 84
        & powershell.exe -ExecutionPolicy Bypass -NoProfile -File $configureScript -InstallRoot $InstallRoot -DataRoot $DataRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Configure-OffsiteInstall.ps1 failed with exit code $LASTEXITCODE"
        }
    }

    Write-Host "Zip install completed successfully." -ForegroundColor Green
    Write-Progress -Activity "Installing Arrow Limo Offsite" -Status "Completed" -PercentComplete 100
} finally {
    Write-Progress -Activity "Installing Arrow Limo Offsite" -Completed
    Remove-Tree $extractRoot
}
