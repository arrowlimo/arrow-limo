param(
    [string]$InstallRoot = $PSScriptRoot,
    [string]$DataRoot = "C:\ProgramData\ArrowLimoOffsite"
)

$ErrorActionPreference = "Stop"

$templatePath = Join-Path $InstallRoot ".env.template"
$envPath = Join-Path $InstallRoot ".env"
$remoteFiles = Join-Path $DataRoot "RemoteFiles"
$updatesRoot = Join-Path $DataRoot "Updates"
$logsRoot = Join-Path $DataRoot "Logs"
$reportsRoot = Join-Path $InstallRoot "reports"

if (-not (Test-Path $templatePath)) {
    throw ".env.template not found at $templatePath"
}

New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
New-Item -ItemType Directory -Path $remoteFiles -Force | Out-Null
New-Item -ItemType Directory -Path $updatesRoot -Force | Out-Null
New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null

$content = Get-Content $templatePath -Raw
$content = $content.Replace("__WORKSTATION_ID__", $env:COMPUTERNAME)
$content = $content.Replace("__REMOTE_FILES_ROOT__", ($remoteFiles -replace "\\", "/"))
$content = $content.Replace("__UPDATE_ROOT__", ($updatesRoot -replace "\\", "/"))

Set-Content -Path $envPath -Value $content -Encoding UTF8

Write-Host "Configured Arrow Limo Offsite install at $InstallRoot" -ForegroundColor Green