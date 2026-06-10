param(
    [Parameter(Mandatory = $true)]
    [Alias('AppExePath')]
    [string]$AppPath,
    [string]$ShortcutName = "Arrow Limousine",
    [string]$IconPath = "",
    [string]$DesktopPath = ""
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $AppPath)) {
    throw "Application target not found: $AppPath"
}

if ([string]::IsNullOrWhiteSpace($DesktopPath)) {
    $oneDriveDesktop = Join-Path $env:USERPROFILE 'OneDrive\\Desktop'
    if (Test-Path $oneDriveDesktop) {
        $DesktopPath = $oneDriveDesktop
    } else {
        $DesktopPath = [Environment]::GetFolderPath('Desktop')
    }
}

if (-not (Test-Path $DesktopPath)) {
    New-Item -ItemType Directory -Path $DesktopPath -Force | Out-Null
}

$shortcutPath = Join-Path $DesktopPath "$ShortcutName.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $AppPath
$shortcut.WorkingDirectory = Split-Path $AppPath -Parent
$shortcut.WindowStyle = 1

if (-not [string]::IsNullOrWhiteSpace($IconPath) -and (Test-Path $IconPath)) {
    $shortcut.IconLocation = $IconPath
} else {
    $shortcut.IconLocation = $AppPath
}

$shortcut.Save()

Write-Host "Created desktop shortcut: $shortcutPath"
Write-Host "Target: $AppPath"
Write-Host "Icon: $($shortcut.IconLocation)"
