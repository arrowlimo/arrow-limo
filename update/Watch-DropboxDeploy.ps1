<#
.SYNOPSIS
    Auto-update watcher for Arrow Limousine app.
    Monitors the Dropbox limo_deploy folder for new publishes and runs
    install.bat automatically 15 minutes after a new deploy is detected.

.DESCRIPTION
    Watches file_manifest.sha256 in the Dropbox payload folder.
    When its hash changes (meaning a new publish happened), waits
    DELAY_MINUTES then silently runs install.bat with no user interaction.

    Designed to run as a Windows Scheduled Task at startup (as SYSTEM or
    current user). One instance only — exits if already running.

.PARAMETER PayloadRoot
    Path to the Dropbox limo_deploy folder.
    Default: auto-detected from Dropbox info or $env:ARROW_PAYLOAD_ROOT

.PARAMETER DelayMinutes
    Minutes to wait after detecting a new deploy before running install.
    Default: 15

.PARAMETER InstallBat
    Path to install.bat inside PayloadRoot. Default: <PayloadRoot>\install.bat

.PARAMETER LogFile
    Where to write the watcher log. Default: %TEMP%\arrow_limo_autoupdate.log

.EXAMPLE
    # Run manually to test
    powershell -NoProfile -ExecutionPolicy Bypass -File Watch-DropboxDeploy.ps1

    # Run with custom path
    powershell -NoProfile -ExecutionPolicy Bypass `
        -File Watch-DropboxDeploy.ps1 `
        -PayloadRoot "C:\Users\dispatch\Dropbox\limo_deploy"
#>

param(
    [string]$PayloadRoot  = '',
    [int]   $DelayMinutes = 15,
    [string]$InstallBat   = '',
    [string]$LogFile      = "$env:TEMP\arrow_limo_autoupdate.log"
)

# ── Singleton guard ──────────────────────────────────────────────────────────
$lockFile = "$env:TEMP\arrow_limo_watcher.lock"
if (Test-Path $lockFile) {
    $lockedPid = Get-Content $lockFile -ErrorAction SilentlyContinue
    if ($lockedPid -and (Get-Process -Id ([int]$lockedPid) -ErrorAction SilentlyContinue)) {
        Write-Host "Watcher already running (PID $lockedPid). Exiting."
        exit 0
    }
}
[string]$PID | Set-Content $lockFile -Force

# ── Logging ──────────────────────────────────────────────────────────────────
function Log([string]$msg) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line  = "$stamp  $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
}

# ── Resolve Dropbox payload path ─────────────────────────────────────────────
function Find-DropboxPath {
    # Dropbox stores its folder location in a JSON info file
    $infoPaths = @(
        "$env:APPDATA\Dropbox\info.json",
        "$env:LOCALAPPDATA\Dropbox\info.json"
    )
    foreach ($p in $infoPaths) {
        if (Test-Path $p) {
            try {
                $info = Get-Content $p -Raw | ConvertFrom-Json
                $base = $info.personal.path
                if (-not $base) { $base = $info.business.path }
                if ($base) { return $base }
            } catch {}
        }
    }
    # Fallback: common locations
    foreach ($candidate in @(
        "$env:USERPROFILE\Dropbox",
        "C:\Users\Public\Dropbox",
        "D:\Dropbox"
    )) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

if (-not $PayloadRoot) {
    $PayloadRoot = $env:ARROW_PAYLOAD_ROOT
}
if (-not $PayloadRoot) {
    $dbRoot = Find-DropboxPath
    if ($dbRoot) {
        $PayloadRoot = Join-Path $dbRoot 'limo_deploy'
    }
}
if (-not $PayloadRoot -or -not (Test-Path $PayloadRoot)) {
    Log "ERROR: Cannot locate limo_deploy folder. Set ARROW_PAYLOAD_ROOT env var or pass -PayloadRoot."
    Remove-Item $lockFile -ErrorAction SilentlyContinue
    exit 1
}

$ManifestFile = Join-Path $PayloadRoot 'file_manifest.sha256'
if (-not $InstallBat) {
    $InstallBat = Join-Path $PayloadRoot 'install.bat'
}

Log "=== Arrow Limo Auto-Update Watcher started ==="
Log "Payload : $PayloadRoot"
Log "Manifest: $ManifestFile"
Log "Delay   : $DelayMinutes min"
Log "Install : $InstallBat"

# ── Seed the current manifest hash ───────────────────────────────────────────
function Get-ManifestHash {
    if (-not (Test-Path $ManifestFile)) { return '' }
    try {
        return (Get-FileHash $ManifestFile -Algorithm SHA256).Hash
    } catch { return '' }
}

$lastHash    = Get-ManifestHash
$pendingAt   = $null   # DateTime when change was first detected
$pollSeconds = 60      # Check every 60 s

Log "Baseline manifest hash: $($lastHash.Substring(0,[Math]::Min(16,$lastHash.Length)))..."

# ── Main poll loop ────────────────────────────────────────────────────────────
while ($true) {
    Start-Sleep -Seconds $pollSeconds

    $currentHash = Get-ManifestHash

    if ($currentHash -ne $lastHash -and $currentHash -ne '') {
        if (-not $pendingAt) {
            $pendingAt = Get-Date
            Log "NEW DEPLOY detected (hash changed). Will install in $DelayMinutes min at $($pendingAt.AddMinutes($DelayMinutes).ToString('HH:mm:ss'))."
        }
    }

    if ($pendingAt -and ((Get-Date) -ge $pendingAt.AddMinutes($DelayMinutes))) {
        Log "Delay elapsed. Starting silent install..."

        # Kill app if running so robocopy can overwrite files
        Stop-Process -Name 'ArrowLimousineApp' -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3

        # Run install.bat silently
        $env:ARROW_LIMO_NO_PAUSE = '1'
        $proc = Start-Process -FilePath 'cmd.exe' `
            -ArgumentList "/c `"$InstallBat`"" `
            -Wait -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput "$env:TEMP\arrow_limo_install_stdout.log" `
            -RedirectStandardError  "$env:TEMP\arrow_limo_install_stderr.log"

        if ($proc.ExitCode -lt 8) {
            Log "Install completed successfully (exit $($proc.ExitCode))."
        } else {
            Log "Install returned error (exit $($proc.ExitCode)). Check $env:TEMP\arrow_limo_install_stdout.log"
        }

        # Reset state
        $lastHash  = Get-ManifestHash
        $pendingAt = $null
        Log "Watcher reset. Monitoring for next deploy..."
    }
}
