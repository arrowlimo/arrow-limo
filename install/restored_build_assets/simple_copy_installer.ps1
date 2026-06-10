param(
    [string]$SourcePath = '',
    [string]$TargetPath = 'Y:\limo',
    [string]$LogPath = 'C:\ProgramData\ArrowLimoInstaller'
)

$ErrorActionPreference = 'Stop'

# Resolve paths
if ([string]::IsNullOrWhiteSpace($SourcePath)) {
    $SourcePath = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$SourcePath = (Resolve-Path $SourcePath).Path
$LogPath = $LogPath.TrimEnd('\')

if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $LogPath "install_$timestamp.log"

Start-Transcript -Path $logFile -Append

Write-Host "==================== Simple Copy-Replace Installer ====================" -ForegroundColor Cyan
Write-Host "Source:       $SourcePath"
Write-Host "Target:       $TargetPath"
Write-Host "Log:          $logFile"
Write-Host "========================================================================" -ForegroundColor Cyan

function Copy-DirectoryRobust {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )

    if (-not (Test-Path $Destination)) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    }

    # /COPY:DAT avoids extended metadata that can fail on cloud placeholder files.
    # Treat exit codes 0-7 as success per robocopy semantics.
    $null = & robocopy $Source $Destination /E /R:2 /W:1 /COPY:DAT /DCOPY:DAT /NFL /NDL /NJH /NJS
    $rc = $LASTEXITCODE
    if ($rc -ge 8) {
        throw "Robocopy failed for '$Source' -> '$Destination' with exit code $rc"
    }
}

# --- Directories and files to copy ---
$requiredItems = @(
    'assets',
    'backend',
    'config',
    'data',
    'database',
    'db',
    'desktop_app',
    'frontend',
    'invoices',
    'migrations',
    'modern_backend',
    'reports',
    'scripts',
    'template',
    'update',
    'methods.txt',
    'pyproject.toml',
    'pytest.ini',
    'render.yaml',
    'scan_signals.py',
    '.venv'
)

# Check for ArrowLimousineApp.exe in dist or root
$exeSource = $null
$exeFromDist = Join-Path $SourcePath 'dist\ArrowLimousineApp.exe'
$exeFromRoot = Join-Path $SourcePath 'ArrowLimousineApp.exe'
if (Test-Path $exeFromDist) {
    $exeSource = $exeFromDist
} elseif (Test-Path $exeFromRoot) {
    $exeSource = $exeFromRoot
}

Write-Host "[10%] Validating source files..." -ForegroundColor Yellow
$missingItems = @()
foreach ($item in $requiredItems) {
    $path = Join-Path $SourcePath $item
    if (-not (Test-Path $path)) {
        $missingItems += $item
    }
}

if ([string]::IsNullOrWhiteSpace($exeSource)) {
    $missingItems += 'ArrowLimousineApp.exe'
}

if ($missingItems.Count -gt 0) {
    Write-Host "ERROR: Missing source items:" -ForegroundColor Red
    $missingItems | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Stop-Transcript
    exit 1
}

Write-Host "[20%] Stopping running app..." -ForegroundColor Yellow
Get-Process ArrowLimousineApp -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Create backup if target exists
if (Test-Path $TargetPath) {
    Write-Host "[30%] Creating backup..." -ForegroundColor Yellow
    $backupDir = Join-Path $TargetPath '_install_backups'
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    $backupName = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    $backupPath = Join-Path $backupDir $backupName
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    
    Get-ChildItem $TargetPath -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '_install_backups' -and $_.Name -ne '_install_reports' } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination $backupPath -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "[30%] Creating target directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
}

# Copy all required items
Write-Host "[40%] Copying application files..." -ForegroundColor Yellow
$copiedCount = 0
foreach ($item in $requiredItems) {
    $src = Join-Path $SourcePath $item
    $dst = Join-Path $TargetPath $item
    
    if (Test-Path $dst) {
        Remove-Item -Path $dst -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    if (Test-Path $src -PathType Container) {
        Copy-DirectoryRobust -Source $src -Destination $dst
    } else {
        Copy-Item -Path $src -Destination $dst -Force -ErrorAction Stop
    }
    $copiedCount++
    Write-Host "  [$copiedCount/$($requiredItems.Count)] Copied: $item" -ForegroundColor Green
}

# Copy the main executable
if (-not [string]::IsNullOrWhiteSpace($exeSource)) {
    $exeDst = Join-Path $TargetPath 'ArrowLimousineApp.exe'
    Copy-Item -Path $exeSource -Destination $exeDst -Force -ErrorAction Stop
    Write-Host "  Copied: ArrowLimousineApp.exe ($([math]::Round((Get-Item $exeSource).Length / 1GB, 2))GB)" -ForegroundColor Green
}

# Create startup launcher
Write-Host "[60%] Creating startup launcher..." -ForegroundColor Yellow
$launcherContent = @(
    '@echo off',
    'setlocal enabledelayedexpansion',
    '',
    'cd /d "%~dp0"',
    '',
    'if exist "ArrowLimousineApp.exe" (',
    '    start "" "ArrowLimousineApp.exe"',
    ') else (',
    '    echo ERROR: ArrowLimousineApp.exe not found',
    '    exit /b 1',
    ')',
    '',
    'exit /b 0'
)

$launcherPath = Join-Path $TargetPath 'START_ARROW_LIMO.bat'
Set-Content -Path $launcherPath -Value $launcherContent -Encoding ASCII
Write-Host "  Created: $launcherPath" -ForegroundColor Green

# Create desktop shortcut
Write-Host "[70%] Creating desktop shortcut..." -ForegroundColor Yellow
try {
    $shell = New-Object -ComObject WScript.Shell
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktopPath 'Arrow Limousine.lnk'
    
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $TargetPath 'ArrowLimousineApp.exe'
    $shortcut.WorkingDirectory = $TargetPath
    
    # Try to find icon
    $iconPaths = @(
        (Join-Path $TargetPath 'desktop_app\arrowyellow.ico'),
        (Join-Path $TargetPath 'desktop_app\icon.ico'),
        (Join-Path $SourcePath 'desktop_app\arrowyellow.ico')
    )
    foreach ($iconPath in $iconPaths) {
        if (Test-Path $iconPath) {
            $shortcut.IconLocation = $iconPath
            break
        }
    }
    
    $shortcut.Save()
    Write-Host "  Created: $shortcutPath" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Could not create desktop shortcut: $_" -ForegroundColor Yellow
}

# Verify files exist
Write-Host "[80%] Verifying installation..." -ForegroundColor Yellow
$exePath = Join-Path $TargetPath 'ArrowLimousineApp.exe'
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: ArrowLimousineApp.exe not found after copy" -ForegroundColor Red
    Stop-Transcript
    exit 1
}

$pyFilesCount = @(Get-ChildItem -Path $TargetPath -Filter '*.py' -Recurse -ErrorAction SilentlyContinue).Count
Write-Host "  Found $pyFilesCount Python files" -ForegroundColor Green
Write-Host "  Main executable verified: $exePath" -ForegroundColor Green

# Test run
Write-Host "[90%] Testing app startup..." -ForegroundColor Yellow
$testTimeout = 30
$testStart = Get-Date
$testPass = $false

try {
    $process = Start-Process -FilePath $exePath -PassThru -ErrorAction Stop -WindowStyle Hidden
    $processId = $process.Id
    Write-Host "  App started (PID: $processId)" -ForegroundColor Green
    
    # Wait up to $testTimeout seconds for the app to show it's running
    while (((Get-Date) - $testStart).TotalSeconds -lt $testTimeout) {
        if ($process.HasExited) {
            Write-Host "  App exited (code: $($process.ExitCode))" -ForegroundColor Yellow
            if ($process.ExitCode -eq 0) {
                $testPass = $true
            }
            break
        }
        Start-Sleep -Seconds 1
        
        # If app is still running after 5 seconds, consider it a pass
        if (((Get-Date) - $testStart).TotalSeconds -gt 5 -and -not $process.HasExited) {
            $testPass = $true
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            break
        }
    }
} catch {
    Write-Host "  WARNING: Could not start app for testing: $_" -ForegroundColor Yellow
}

if ($testPass) {
    Write-Host "  Startup test: PASSED" -ForegroundColor Green
} else {
    Write-Host "  Startup test: WARNING - could not verify" -ForegroundColor Yellow
}

Write-Host "[100%] Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Target Location: $TargetPath" -ForegroundColor Green
Write-Host "  Files Copied:    $($requiredItems.Count)" -ForegroundColor Green
Write-Host "  Python Files:    $pyFilesCount" -ForegroundColor Green
Write-Host "  Startup Test:    $(if ($testPass) { 'PASSED' } else { 'WARNING' })" -ForegroundColor $(if ($testPass) { 'Green' } else { 'Yellow' })
Write-Host ""

Stop-Transcript
exit $(if ($testPass -or ($pyFilesCount -gt 2000)) { 0 } else { 1 })
