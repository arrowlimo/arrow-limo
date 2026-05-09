param(
    [switch]$IncludeRuntime,
    [switch]$ExcludeRuntime,
    [string]$ReleaseName = "ArrowLimoOffsite"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$buildRoot = Join-Path $PSScriptRoot "build"
$updatesRoot = Join-Path $buildRoot "updates"
$runtimeDir = Join-Path $PSScriptRoot "runtime"
$version = Get-Date -Format "yyyy.MM.dd.HHmm"
$payloadRoot = Join-Path $updatesRoot "$ReleaseName-$version"
$payloadDir = Join-Path $payloadRoot "payload"
$includeRuntimeEffective = $IncludeRuntime -or (-not $ExcludeRuntime)

function Copy-Tree([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $null = robocopy $Source $Destination /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /XD __pycache__ .pytest_cache node_modules .git build dist
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed for $Source"
    }
}

New-Item -ItemType Directory -Path $payloadDir -Force | Out-Null

Copy-Tree (Join-Path $repoRoot "desktop_app") (Join-Path $payloadDir "desktop_app")
Copy-Tree (Join-Path $repoRoot "modern_backend") (Join-Path $payloadDir "modern_backend")

if (Test-Path (Join-Path $repoRoot "frontend\dist")) {
    Copy-Tree (Join-Path $repoRoot "frontend\dist") (Join-Path $payloadDir "frontend\dist")
}

Copy-Item (Join-Path $runtimeDir "launcher.py") (Join-Path $payloadDir "launcher.py") -Force
Copy-Item (Join-Path $runtimeDir "START_ARROW_LIMO_OFFSITE.bat") (Join-Path $payloadDir "START_ARROW_LIMO_OFFSITE.bat") -Force
Copy-Item (Join-Path $runtimeDir "Bootstrap-Prereqs.ps1") (Join-Path $payloadDir "Bootstrap-Prereqs.ps1") -Force
Copy-Item (Join-Path $runtimeDir "Configure-OffsiteInstall.ps1") (Join-Path $payloadDir "Configure-OffsiteInstall.ps1") -Force
Copy-Item (Join-Path $runtimeDir "Install-OffsiteFromZip.ps1") (Join-Path $payloadDir "Install-OffsiteFromZip.ps1") -Force
Copy-Item (Join-Path $runtimeDir "Install-OffsiteSelfHeal.ps1") (Join-Path $payloadDir "Install-OffsiteSelfHeal.ps1") -Force
Copy-Item (Join-Path $runtimeDir "support-apps.json") (Join-Path $payloadDir "support-apps.json") -Force

if ($includeRuntimeEffective) {
    Copy-Tree (Join-Path $repoRoot ".venv") (Join-Path $payloadDir ".venv")
}

Copy-Item (Join-Path $runtimeDir "Apply-OffsiteUpdate.ps1") (Join-Path $payloadRoot "Apply-OffsiteUpdate.ps1") -Force

$prereqDir = Join-Path $PSScriptRoot "prerequisites"
if (Test-Path $prereqDir) {
    Copy-Tree $prereqDir (Join-Path $payloadDir "prerequisites")
}

$manifest = @{
    release_name = $ReleaseName
    version = $version
    include_runtime = [bool]$includeRuntimeEffective
    built_at = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $payloadRoot "update-manifest.json") -Value $manifest -Encoding UTF8

$zipPath = Join-Path $updatesRoot "$ReleaseName-Update-$version.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $payloadRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Update package created: $zipPath" -ForegroundColor Green