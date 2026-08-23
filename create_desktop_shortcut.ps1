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

function New-DesktopShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetDesktopPath
    )

    if (-not (Test-Path $TargetDesktopPath)) {
        New-Item -ItemType Directory -Path $TargetDesktopPath -Force | Out-Null
    }

    $shortcutPath = Join-Path $TargetDesktopPath "$ShortcutName.lnk"
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
}

$targetDesktops = @()
if (-not [string]::IsNullOrWhiteSpace($DesktopPath)) {
    $targetDesktops += $DesktopPath
} else {
    $oneDriveDesktop = Join-Path $env:USERPROFILE 'OneDrive\\Desktop'
    if (Test-Path $oneDriveDesktop) {
        $targetDesktops += $oneDriveDesktop
    } else {
        $targetDesktops += [Environment]::GetFolderPath('Desktop')
    }

    # Also create in Public Desktop so the icon is visible after elevated/server installs.
    $publicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
    if (-not [string]::IsNullOrWhiteSpace($publicDesktop)) {
        $targetDesktops += $publicDesktop
    }
}

$targetDesktops = $targetDesktops | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
$createdCount = 0
$publicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
foreach ($target in $targetDesktops) {
    try {
        New-DesktopShortcut -TargetDesktopPath $target
        $createdCount++
    }
    catch {
        $isPublicDesktop = $false
        if (-not [string]::IsNullOrWhiteSpace($publicDesktop)) {
            $isPublicDesktop = $target.TrimEnd('\\') -ieq $publicDesktop.TrimEnd('\\')
        }

        if ($isPublicDesktop -and $createdCount -gt 0) {
            Write-Host "INFO: Skipping public desktop shortcut in '$target' (non-fatal): $($_.Exception.Message)" -ForegroundColor Yellow
        } else {
            Write-Warning "Could not create shortcut in '$target': $($_.Exception.Message)"
        }
    }
}

if ($createdCount -eq 0) {
    throw "No desktop shortcuts were created. Check permissions for desktop locations."
}
