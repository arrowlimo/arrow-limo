param(
    [string]$SourcePath = $PSScriptRoot,
    [string]$TargetRoot = "Y:\limo",
    [string]$IconPath = "E:\new shit\arrowyellow.ico",
    [bool]$LaunchApp = $false,
    [bool]$FullClean = $true,
    [bool]$RunSmokeTest = $true,
    [int]$SmokeTestSeconds = 8,
    [int]$RecentInstallGuardMinutes = 15,
    [switch]$ForceInstall,
    [bool]$SkipBackup = $false,
    [switch]$NoElevation,
    [bool]$ShowUi = $true
)

$ErrorActionPreference = 'Stop'

function Expand-PayloadArchiveToTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    $extractRoot = Join-Path $env:TEMP ("arrow_payload_" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

    try {
        Expand-Archive -Path $ArchivePath -DestinationPath $extractRoot -Force

        Get-ChildItem -Path $extractRoot -Force | ForEach-Object {
            $destination = Join-Path $DestinationRoot $_.Name
            if ($_.PSIsContainer) {
                Copy-Item -Path $_.FullName -Destination $destination -Recurse -Force
            }
            else {
                Copy-Item -Path $_.FullName -Destination $destination -Force
            }
        }
    }
    finally {
        if (Test-Path $extractRoot) {
            Remove-Item -Path $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-TargetRoot {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $Path
    }

    if (Test-Path $Path) {
        return $Path
    }

    # Elevated sessions can lose mapped-drive visibility; fall back to UNC for Y:.
    if ($Path -match '^[Yy]:\\') {
        $suffix = $Path.Substring(3)
        $uncRoot = '\\DISPATCHMAIN\limo_files'
        if (Test-Path $uncRoot) {
            return Join-Path $uncRoot $suffix
        }
    }

    return $Path
}

function Normalize-PathForCompare {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ''
    }

    $normalized = $Path.Trim().Replace('/', '\').TrimEnd('\\')
    return $normalized.ToLowerInvariant()
}

function Assert-AllowedInstallRoot {
    param([string]$Path)

    $normalizedTarget = Normalize-PathForCompare -Path $Path
    $allowedRoots = @(
        'y:\limo',
        '\\dispatchmain\limo_files\limo'
    )

    if ($allowedRoots -notcontains $normalizedTarget) {
        throw "Install root must be Y:\limo (or equivalent \\DISPATCHMAIN\limo_files\limo). Received: $Path"
    }
}

$TargetRoot = Resolve-TargetRoot -Path $TargetRoot
Assert-AllowedInstallRoot -Path $TargetRoot

$script:UiEnabled = $false
$script:InstallForm = $null
$script:ProgressBar = $null
$script:StatusLabel = $null
$script:InstallerMutex = $null
$script:OwnsInstallerMutex = $false

function Initialize-InstallUi {
    if (-not $ShowUi) {
        return
    }

    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing

        $script:InstallForm = New-Object System.Windows.Forms.Form
        $script:InstallForm.Text = 'Arrow Limousine Installer'
        $script:InstallForm.StartPosition = 'CenterScreen'
        $script:InstallForm.Size = New-Object System.Drawing.Size(520, 170)
        $script:InstallForm.TopMost = $true
        $script:InstallForm.FormBorderStyle = 'FixedDialog'
        $script:InstallForm.MaximizeBox = $false
        $script:InstallForm.MinimizeBox = $false

        $script:StatusLabel = New-Object System.Windows.Forms.Label
        $script:StatusLabel.AutoSize = $false
        $script:StatusLabel.Location = New-Object System.Drawing.Point(20, 20)
        $script:StatusLabel.Size = New-Object System.Drawing.Size(470, 40)
        $script:StatusLabel.Text = 'Starting installer...'

        $script:ProgressBar = New-Object System.Windows.Forms.ProgressBar
        $script:ProgressBar.Location = New-Object System.Drawing.Point(20, 75)
        $script:ProgressBar.Size = New-Object System.Drawing.Size(470, 24)
        $script:ProgressBar.Minimum = 0
        $script:ProgressBar.Maximum = 100
        $script:ProgressBar.Value = 0

        $script:InstallForm.Controls.Add($script:StatusLabel)
        $script:InstallForm.Controls.Add($script:ProgressBar)
        $script:InstallForm.Show()
        [System.Windows.Forms.Application]::DoEvents()
        $script:UiEnabled = $true
    }
    catch {
        $script:UiEnabled = $false
    }
}

function Update-InstallUi {
    param(
        [int]$Percent,
        [string]$Status
    )

    Write-Progress -Activity 'Arrow Limousine Installer' -Status $Status -PercentComplete $Percent
    Write-Host "[$Percent%] $Status"

    if ($script:UiEnabled -and $script:InstallForm -and -not $script:InstallForm.IsDisposed) {
        $safePercent = [Math]::Max(0, [Math]::Min(100, $Percent))
        $script:StatusLabel.Text = $Status
        $script:ProgressBar.Value = $safePercent
        [System.Windows.Forms.Application]::DoEvents()
    }
}

function Close-InstallUi {
    if ($script:UiEnabled -and $script:InstallForm -and -not $script:InstallForm.IsDisposed) {
        $script:InstallForm.Close()
    }
}

function Show-InstallMessage {
    param(
        [string]$Message,
        [bool]$IsError = $false
    )

    if (-not $ShowUi) {
        return
    }

    try {
        Add-Type -AssemblyName System.Windows.Forms
        $icon = if ($IsError) { [System.Windows.Forms.MessageBoxIcon]::Error } else { [System.Windows.Forms.MessageBoxIcon]::Information }
        [System.Windows.Forms.MessageBox]::Show(
            $Message,
            'Arrow Limousine Installer',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            $icon
        ) | Out-Null
    }
    catch {
    }
}

function Initialize-InstallerMutex {
    try {
        $createdNew = $false
        $script:InstallerMutex = New-Object System.Threading.Mutex($true, 'Global\ArrowLimoInstallerSingleInstance', [ref]$createdNew)
        $script:OwnsInstallerMutex = [bool]$createdNew
        if (-not $script:OwnsInstallerMutex) {
            throw 'Another Arrow Limousine installer instance is already running.'
        }
    }
    catch {
        throw "Unable to acquire installer lock: $($_.Exception.Message)"
    }
}

function Release-InstallerMutex {
    if ($script:InstallerMutex) {
        try {
            if ($script:OwnsInstallerMutex) {
                $script:InstallerMutex.ReleaseMutex()
            }
            $script:InstallerMutex.Dispose()
        }
        catch {
        }
        $script:InstallerMutex = $null
        $script:OwnsInstallerMutex = $false
    }
}

$localLogRoot = Join-Path $env:ProgramData 'ArrowLimoInstaller'
if (-not (Test-Path $localLogRoot)) {
    New-Item -ItemType Directory -Path $localLogRoot -Force | Out-Null
}
$script:LocalLogPath = Join-Path $localLogRoot ("install_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Start-Transcript -Path $script:LocalLogPath -Force | Out-Null
Write-Host "Local installer log: $script:LocalLogPath"

trap {
    Update-InstallUi -Percent 100 -Status 'Install failed.'
    Write-Host "INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Local installer log: $script:LocalLogPath"
    Close-InstallUi
    Show-InstallMessage -IsError $true -Message "Install failed.`r`n$($_.Exception.Message)`r`n`r`nLog: $script:LocalLogPath"
    Release-InstallerMutex
    try {
        Stop-Transcript | Out-Null
    }
    catch {
    }
    exit 1
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-ReportLine {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    Add-Content -Path $script:ReportPath -Value $line
}

if ((-not $NoElevation) -and (-not (Test-Administrator))) {
    $argsList = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$PSCommandPath`"",
        '-SourcePath', "`"$SourcePath`"",
        '-TargetRoot', "`"$TargetRoot`"",
        '-IconPath', "`"$IconPath`"",
        '-LaunchApp', $(if ($LaunchApp) { '1' } else { '0' }),
        '-FullClean', $(if ($FullClean) { '1' } else { '0' }),
        '-RunSmokeTest', $(if ($RunSmokeTest) { '1' } else { '0' }),
        '-RecentInstallGuardMinutes', "$RecentInstallGuardMinutes",
        '-ForceInstall', $(if ($ForceInstall) { '1' } else { '0' }),
        '-SkipBackup', $(if ($SkipBackup) { '1' } else { '0' }),
        '-ShowUi', $(if ($ShowUi) { '1' } else { '0' }),
        '-SmokeTestSeconds', "$SmokeTestSeconds"
    )
    $pwsh = "$env:ProgramFiles\PowerShell\7\pwsh.exe"
    if (-not (Test-Path $pwsh)) { $pwsh = 'powershell.exe' }
    Start-Process $pwsh -Verb RunAs -ArgumentList $argsList
    exit 0
}

    Initialize-InstallUi
    Initialize-InstallerMutex
    Update-InstallUi -Percent 5 -Status 'Validating install environment...'

$targetParent = Split-Path -Path $TargetRoot -Parent
if ($targetParent -and -not (Test-Path $targetParent)) {
    throw "Install root parent not found: $targetParent. If this is a mapped drive (for example Y:), run INSTALL_ARROW_LIMO.bat as the signed-in user so the mapped drive is visible."
}

if (-not (Test-Path $SourcePath)) {
    throw "Source path not found: $SourcePath"
}

if (-not (Test-Path $TargetRoot)) {
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}

Update-InstallUi -Percent 15 -Status 'Preparing install report...'

$reportDir = Join-Path $TargetRoot '_install_reports'
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}
$script:ReportPath = Join-Path $reportDir 'latest_install_report.txt'

if ((-not $ForceInstall) -and ($RecentInstallGuardMinutes -gt 0) -and (Test-Path $script:ReportPath)) {
    $lastReportWrite = (Get-Item $script:ReportPath).LastWriteTime
    $guardThreshold = (Get-Date).AddMinutes(-$RecentInstallGuardMinutes)
    if ($lastReportWrite -gt $guardThreshold) {
        $recentLines = Get-Content -Path $script:ReportPath -Tail 40 -ErrorAction SilentlyContinue
        $hasPass = $false
        if ($recentLines) {
            $hasPass = [bool]($recentLines | Select-String -SimpleMatch 'RESULT=PASS' -Quiet)
        }

        if ($hasPass) {
            Update-InstallUi -Percent 100 -Status 'Recent successful install detected. Skipping duplicate run.'
            Write-Host "Recent successful install already completed at $lastReportWrite. Skipping duplicate run."
            Write-Host "Use -ForceInstall to reinstall immediately."
            Close-InstallUi
            Release-InstallerMutex
            Stop-Transcript | Out-Null
            exit 0
        }
    }
}

Set-Content -Path $script:ReportPath -Value "Arrow Limousine full install report" -Encoding ASCII
Write-ReportLine "SourcePath=$SourcePath"
Write-ReportLine "TargetRoot=$TargetRoot"

$sourceExe = Join-Path $SourcePath 'ArrowLimousineApp.exe'
if (-not (Test-Path $sourceExe)) {
    throw "Installer source executable not found: $sourceExe"
}

$shortcutScript = Join-Path $SourcePath 'create_desktop_shortcut.ps1'
if (-not (Test-Path $shortcutScript)) {
    throw "Shortcut script not found: $shortcutScript"
}

$packageIconPath = Join-Path $SourcePath 'arrowyellow.ico'
$resolvedIconPath = $IconPath
if (Test-Path $packageIconPath) {
    $resolvedIconPath = $packageIconPath
}
Write-ReportLine "ResolvedIconPath=$resolvedIconPath"

Get-Process -Name 'ArrowLimousineApp' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 250

Update-InstallUi -Percent 30 -Status 'Stopping running app and preparing backup...'

if (-not $SkipBackup -and (Test-Path (Join-Path $TargetRoot 'ArrowLimousineApp.exe'))) {
    $backupRoot = Join-Path $TargetRoot '_install_backups'
    if (-not (Test-Path $backupRoot)) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    }
    $backupDir = Join-Path $backupRoot (Get-Date -Format 'yyyyMMdd_HHmmss')
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Get-ChildItem -Path $TargetRoot -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne '_install_reports' } |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $backupDir $_.Name) -Force }
    Write-ReportLine "BackupCreated=$backupDir"
}

if ($FullClean) {
    Get-ChildItem -Path $TargetRoot -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notin @('_install_reports', '_install_backups') } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-ReportLine "FullClean=completed (top-level files and directories removed)"
}

Update-InstallUi -Percent 50 -Status 'Copying application files...'

$payloadItems = Get-ChildItem -Path $SourcePath -Force -ErrorAction Stop |
    Where-Object { $_.Name -notin @('_install_reports', '_install_backups') }

foreach ($item in $payloadItems) {
    $destination = Join-Path $TargetRoot $item.Name
    if ($item.PSIsContainer) {
        Copy-Item -Path $item.FullName -Destination $destination -Recurse -Force
    }
    else {
        Copy-Item -Path $item.FullName -Destination $destination -Force
    }
}

$fullPayloadArchive = Join-Path $SourcePath 'ArrowLimoFullPayload.zip'
if (Test-Path $fullPayloadArchive) {
    Update-InstallUi -Percent 60 -Status 'Expanding full payload archive...'
    Expand-PayloadArchiveToTarget -ArchivePath $fullPayloadArchive -DestinationRoot $TargetRoot
    Write-ReportLine "ExpandedFullPayload=$fullPayloadArchive"
}

$targetExe = Join-Path $TargetRoot 'ArrowLimousineApp.exe'
Write-ReportLine "CopiedPayloadItems=$($payloadItems.Count)"
Write-ReportLine "CopiedExe=$targetExe"

$startupBat = Join-Path $TargetRoot 'START_ARROW_LIMO.bat'
$startupBatContent = @(
    '@echo off',
    'setlocal',
    'set "ROOT_DIR=%~dp0"',
    'cd /d "%ROOT_DIR%"',
    'start "" "%ROOT_DIR%ArrowLimousineApp.exe"',
    'endlocal',
    'exit /b 0'
)
Set-Content -Path $startupBat -Value $startupBatContent -Encoding ASCII
Write-ReportLine "CreatedStartupLauncher=$startupBat"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $shortcutScript `
    -AppPath $startupBat `
    -ShortcutName 'Arrow Limousine' `
    -IconPath $resolvedIconPath
Write-ReportLine "ShortcutScript=completed"

Update-InstallUi -Percent 70 -Status 'Creating desktop shortcut...'

if ($RunSmokeTest) {
    Update-InstallUi -Percent 80 -Status 'Running smoke test...'
    $smokeProcess = Start-Process -FilePath $targetExe -PassThru
    $ok = $false
    try {
        $deadline = (Get-Date).AddSeconds($SmokeTestSeconds)
        while ((Get-Date) -lt $deadline) {
            $smokeProcess.Refresh()
            if ($smokeProcess.HasExited) {
                throw "Smoke test failed: process exited early with code $($smokeProcess.ExitCode)"
            }
            Start-Sleep -Milliseconds 400
        }
        $ok = $true
    }
    finally {
        if ($smokeProcess -and -not $smokeProcess.HasExited) {
            Stop-Process -Id $smokeProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }

    if (-not $ok) {
        throw "Smoke test failed."
    }
    Write-ReportLine "SmokeTest=passed"
}

Update-InstallUi -Percent 90 -Status 'Verifying installed files and shortcut...'

$desktopPrimary = Join-Path $env:USERPROFILE 'OneDrive\\Desktop\\Arrow Limousine.lnk'
$desktopFallback = Join-Path $env:USERPROFILE 'Desktop\\Arrow Limousine.lnk'
$shortcutPath = if (Test-Path $desktopPrimary) { $desktopPrimary } elseif (Test-Path $desktopFallback) { $desktopFallback } else { $null }
if (-not $shortcutPath) {
    throw "Shortcut verification failed: Arrow Limousine.lnk not found on desktop"
}

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($shortcutPath)
if ($lnk.TargetPath -ne $startupBat) {
    throw "Shortcut target mismatch: expected $startupBat got $($lnk.TargetPath)"
}
Write-ReportLine "ShortcutVerified=$shortcutPath"
Write-ReportLine "ShortcutIcon=$($lnk.IconLocation)"

if (-not (Test-Path $targetExe)) {
    throw "Install verification failed: target EXE missing"
}
if (-not (Test-Path $startupBat)) {
    throw "Install verification failed: startup launcher missing"
}
Write-ReportLine "InstallVerification=passed"

if ($LaunchApp) {
    Update-InstallUi -Percent 95 -Status 'Launching app...'
    Start-Process $startupBat
    Write-ReportLine "LaunchApp=started"
}

Write-ReportLine "RESULT=PASS"
Update-InstallUi -Percent 100 -Status 'Install completed successfully.'
Write-Host "Full install completed successfully."
Write-Host "Report: $script:ReportPath"
Write-Host "Local installer log: $script:LocalLogPath"
Close-InstallUi
Show-InstallMessage -Message "Install complete.`r`nTarget: $TargetRoot`r`nReport: $script:ReportPath"
Release-InstallerMutex
Stop-Transcript | Out-Null

