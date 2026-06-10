param(
    [Alias('AppExePath')]
    [string]$AppPath = "L:\limo\install\ArrowLimousineApp.exe",
    [string]$ShortcutName = "Arrow Limousine",
    [string]$IconPath = "E:\new shit\arrowyellow.ico"
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $AppPath)) {
    throw "Application target not found: $AppPath"
}

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "$ShortcutName.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $AppPath
$shortcut.WorkingDirectory = Split-Path $AppPath -Parent
$shortcut.WindowStyle = 1

if (Test-Path $IconPath) {
    $shortcut.IconLocation = $IconPath
} else {
    $shortcut.IconLocation = $AppPath
}

$shortcut.Save()

Write-Host "Created desktop shortcut: $shortcutPath"
Write-Host "Target: $AppPath"
Write-Host "Icon: $(if (Test-Path $IconPath) { $IconPath } else { $AppPath })"