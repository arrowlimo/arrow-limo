param(
    [string]$InstallRoot = $PSScriptRoot,
    [string]$DataRoot = "C:\ProgramData\ArrowLimoOffsite\Data"
)

$ErrorActionPreference = "Stop"

$templatePath = Join-Path $InstallRoot ".env.template"
$envPath = Join-Path $InstallRoot ".env"

if (-not (Test-Path $templatePath)) {
    throw ".env.template not found at $templatePath"
}

# Create all data subfolders
$subFolders = @("Reports", "Receipts", "Photos", "Logs", "Updates", "RemoteFiles")
foreach ($sub in $subFolders) {
    $subPath = Join-Path $DataRoot $sub
    New-Item -ItemType Directory -Path $subPath -Force | Out-Null
    Write-Host "Created: $subPath" -ForegroundColor Gray
}

$reportsRoot  = Join-Path $DataRoot "Reports"
$receiptsRoot = Join-Path $DataRoot "Receipts"
$photosRoot   = Join-Path $DataRoot "Photos"
$logsRoot     = Join-Path $DataRoot "Logs"
$updatesRoot  = Join-Path $DataRoot "Updates"
$remoteFiles  = Join-Path $DataRoot "RemoteFiles"

# Also create a reports subfolder inside the install dir for scripts that use it
New-Item -ItemType Directory -Path (Join-Path $InstallRoot "reports") -Force | Out-Null

# Write a DATA_ROOT.txt so the user knows where their data is
$readmePath = Join-Path $DataRoot "DATA_ROOT.txt"
Set-Content -Path $readmePath -Value @"
Arrow Limo Offsite - Data Storage
==================================
Install folder : $InstallRoot
Data root      : $DataRoot

Subfolders:
  Reports   -> $reportsRoot
  Receipts  -> $receiptsRoot
  Photos    -> $photosRoot
  Logs      -> $logsRoot
  Updates   -> $updatesRoot
"@ -Encoding UTF8

$content = Get-Content $templatePath -Raw
$content = $content.Replace("__WORKSTATION_ID__",   $env:COMPUTERNAME)
$content = $content.Replace("__REMOTE_FILES_ROOT__", ($remoteFiles  -replace "\\", "/"))
$content = $content.Replace("__UPDATE_ROOT__",       ($updatesRoot   -replace "\\", "/"))
$content = $content.Replace("__DATA_ROOT__",         ($DataRoot      -replace "\\", "/"))
$content = $content.Replace("__REPORTS_ROOT__",      ($reportsRoot   -replace "\\", "/"))
$content = $content.Replace("__RECEIPTS_ROOT__",     ($receiptsRoot  -replace "\\", "/"))
$content = $content.Replace("__PHOTOS_ROOT__",       ($photosRoot    -replace "\\", "/"))
$content = $content.Replace("__LOGS_ROOT__",         ($logsRoot      -replace "\\", "/"))

Set-Content -Path $envPath -Value $content -Encoding UTF8

Write-Host "Configured Arrow Limo Offsite:" -ForegroundColor Green
Write-Host "  Install : $InstallRoot" -ForegroundColor Cyan
Write-Host "  Data    : $DataRoot" -ForegroundColor Cyan
Write-Host "  Reports : $reportsRoot" -ForegroundColor Cyan