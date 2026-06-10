param(
    [string]$AppExePath = '',
    [string]$InstallScriptPath = '',
    [string]$UpdateScriptPath = '',
    [string]$ShortcutScriptPath = '',
    [string]$IconFilePath = '',
    [string]$OutputDir = '',
    [string]$DropboxInstallDir = '',
    [string]$DropboxUpdateDir = ''
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..\..')).Path

if ([string]::IsNullOrWhiteSpace($InstallScriptPath)) { $InstallScriptPath = Join-Path $scriptRoot 'install_dispatcher.ps1' }
if ([string]::IsNullOrWhiteSpace($UpdateScriptPath)) { $UpdateScriptPath = Join-Path $repoRoot 'update\update_dispatcher.ps1' }
if ([string]::IsNullOrWhiteSpace($ShortcutScriptPath)) { $ShortcutScriptPath = Join-Path $scriptRoot 'create_desktop_shortcut.ps1' }
if ([string]::IsNullOrWhiteSpace($IconFilePath)) {
    $preferredIconPaths = @(
        'E:\new shit\arrowyellow.ico',
        (Join-Path $repoRoot 'desktop_app\arrowyellow.ico'),
        (Join-Path $repoRoot 'desktop_app\icon.ico')
    )
    foreach ($candidate in $preferredIconPaths) {
        if (Test-Path $candidate) {
            $IconFilePath = $candidate
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) { $OutputDir = Join-Path $repoRoot 'dist' }
if ([string]::IsNullOrWhiteSpace($AppExePath)) { $AppExePath = Join-Path $repoRoot 'dist\ArrowLimousineApp.exe' }
if ([string]::IsNullOrWhiteSpace($DropboxInstallDir)) { $DropboxInstallDir = Join-Path $env:USERPROFILE 'Dropbox\install' }
if ([string]::IsNullOrWhiteSpace($DropboxUpdateDir)) { $DropboxUpdateDir = Join-Path $env:USERPROFILE 'Dropbox\updates' }

function New-FullPayloadArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $true)]
        [string]$RepoRootPath
    )

    $payloadEntries = @(
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
        '.venv',
        'methods.txt',
        'pyproject.toml',
        'pytest.ini',
        'render.yaml',
        'scan_signals.py',
        'START_ARROW_LIMO.bat'
    )

    $sources = @()
    foreach ($entry in $payloadEntries) {
        $candidate = Join-Path $RepoRootPath $entry
        if (Test-Path $candidate) {
            $sources += $candidate
        }
    }

    if ($sources.Count -eq 0) {
        throw "No payload sources found to build full payload archive."
    }

    if (Test-Path $ArchivePath) {
        Remove-Item -Path $ArchivePath -Force -ErrorAction SilentlyContinue
    }

    Compress-Archive -Path $sources -DestinationPath $ArchivePath -CompressionLevel Optimal -Force
}

function Resolve-LimoPublishDir {
    param([string]$Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path).Trim()
    if ([string]::IsNullOrWhiteSpace($expanded)) {
        return $expanded
    }

    if ((Split-Path -Leaf $expanded).ToLowerInvariant() -ne 'limo') {
        return Join-Path $expanded 'limo'
    }

    return $expanded
}

$DropboxInstallDir = Resolve-LimoPublishDir -Path $DropboxInstallDir
$DropboxUpdateDir = Resolve-LimoPublishDir -Path $DropboxUpdateDir

function New-IExpressSed {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SedPath,
        [Parameter(Mandatory = $true)]
        [string]$TargetExe,
        [Parameter(Mandatory = $true)]
        [string]$FriendlyName,
        [Parameter(Mandatory = $true)]
        [string]$LaunchCommand,
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string[]]$Files
    )

    $lines = @(
        '[Version]',
        'Class=IEXPRESS',
        'SEDVersion=3',
        '[Options]',
        'PackagePurpose=InstallApp',
        'ShowInstallProgramWindow=1',
        'HideExtractAnimation=0',
        'UseLongFileName=1',
        'InsideCompressed=0',
        'CAB_FixedSize=0',
        'CAB_ResvCodeSigning=0',
        'RebootMode=I',
        'InstallPrompt=%InstallPrompt%',
        'DisplayLicense=%DisplayLicense%',
        'FinishMessage=%FinishMessage%',
        'TargetName=%TargetName%',
        'FriendlyName=%FriendlyName%',
        'AppLaunched=%AppLaunched%',
        'PostInstallCmd=%PostInstallCmd%',
        'AdminQuietInstCmd=%AdminQuietInstCmd%',
        'UserQuietInstCmd=%UserQuietInstCmd%',
        'SourceFiles=SourceFiles',
        '[Strings]',
        'InstallPrompt=',
        'DisplayLicense=',
        'FinishMessage=',
        "TargetName=$TargetExe",
        "FriendlyName=$FriendlyName",
        "AppLaunched=$LaunchCommand",
        'PostInstallCmd=<None>',
        'AdminQuietInstCmd=<None>',
        'UserQuietInstCmd=<None>'
    )

    for ($i = 0; $i -lt $Files.Count; $i++) {
        $safeName = $Files[$i].Trim()
        $lines += "FILE$i=$safeName"
    }

    $lines += '[SourceFiles]'
    $lines += "SourceFiles0=$SourceDir\"
    $lines += '[SourceFiles0]'

    for ($i = 0; $i -lt $Files.Count; $i++) {
        $lines += "%FILE$i%="
    }

    Set-Content -Path $SedPath -Value $lines -Encoding ASCII
}

$requiredPaths = @($AppExePath, $InstallScriptPath, $UpdateScriptPath, $ShortcutScriptPath, $IconFilePath)
foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        throw "Required file not found: $path"
    }
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$stagingRoot = Join-Path $OutputDir '_iexpress_staging'
$installStage = Join-Path $stagingRoot 'install'
$updateStage = Join-Path $stagingRoot 'update'

if (Test-Path $stagingRoot) {
    Remove-Item -Path $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $installStage -Force | Out-Null
New-Item -ItemType Directory -Path $updateStage -Force | Out-Null

Copy-Item $AppExePath (Join-Path $installStage 'ArrowLimousineApp.exe') -Force
Copy-Item $InstallScriptPath (Join-Path $installStage 'install_dispatcher.ps1') -Force
Copy-Item $UpdateScriptPath (Join-Path $installStage 'update_dispatcher.ps1') -Force
Copy-Item $ShortcutScriptPath (Join-Path $installStage 'create_desktop_shortcut.ps1') -Force
Copy-Item $IconFilePath (Join-Path $installStage 'arrowyellow.ico') -Force

$installPayloadArchive = Join-Path $installStage 'ArrowLimoFullPayload.zip'
New-FullPayloadArchive -ArchivePath $installPayloadArchive -RepoRootPath $repoRoot

Copy-Item $AppExePath (Join-Path $updateStage 'ArrowLimousineApp.exe') -Force
Copy-Item $UpdateScriptPath (Join-Path $updateStage 'update_dispatcher.ps1') -Force
Copy-Item $ShortcutScriptPath (Join-Path $updateStage 'create_desktop_shortcut.ps1') -Force
Copy-Item $IconFilePath (Join-Path $updateStage 'arrowyellow.ico') -Force

$updatePayloadArchive = Join-Path $updateStage 'ArrowLimoFullPayload.zip'
New-FullPayloadArchive -ArchivePath $updatePayloadArchive -RepoRootPath $repoRoot

$ps7Bootstrap = @(
    '@echo off',
    'setlocal',
    '',
    'rem --- Ensure PowerShell 7 is installed ---',
    'set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"',
    'if exist "%PWSH%" goto :HAVE_PS7',
    '',
    'echo PowerShell 7 not found. Installing via winget...',
    'winget install --id Microsoft.PowerShell --silent --accept-source-agreements --accept-package-agreements >nul 2>&1',
    'if exist "%PWSH%" goto :HAVE_PS7',
    '',
    'echo Winget install failed. Trying MSI download...',
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^',
    '  "Invoke-WebRequest -Uri ''https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/PowerShell-7.4.6-win-x64.msi'' -OutFile ''%TEMP%\ps7.msi''"',
    'msiexec /i "%TEMP%\ps7.msi" /quiet /norestart',
    'del /f /q "%TEMP%\ps7.msi" >nul 2>&1',
    '',
    ':HAVE_PS7'
)

$installLauncher = $ps7Bootstrap + @(
    'rem --- Strip trailing backslash from %%~dp0 to avoid quote-escaping bug ---',
    'set "SRCDIR=%~dp0"',
    'if "%SRCDIR:~-1%"=="\" set "SRCDIR=%SRCDIR:~0,-1%"',
    'rem --- Run update_dispatcher directly and force full reinstall every launch ---',
    '"%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%SRCDIR%\update_dispatcher.ps1" -SourcePath "%SRCDIR%" -NoElevation -ForceInstall -RecentInstallGuardMinutes 0',
    'exit /b %ERRORLEVEL%'
)
Set-Content -Path (Join-Path $installStage 'run_install.bat') -Value $installLauncher -Encoding ASCII

$installerExe = Join-Path $OutputDir 'ArrowLimousine_RemoteInstaller.exe'
$installSed = Join-Path $OutputDir 'ArrowLimousine_RemoteInstaller.sed'

foreach ($artifact in @($installerExe, $installSed)) {
    if (Test-Path $artifact) {
        Remove-Item -Path $artifact -Force -ErrorAction SilentlyContinue
    }
}

New-IExpressSed `
    -SedPath $installSed `
    -TargetExe $installerExe `
    -FriendlyName 'Arrow Limousine Remote Installer' `
    -LaunchCommand 'cmd.exe /c run_install.bat' `
    -SourceDir $installStage `
    -Files @('ArrowLimousineApp.exe', 'install_dispatcher.ps1', 'update_dispatcher.ps1', 'create_desktop_shortcut.ps1', 'arrowyellow.ico', 'ArrowLimoFullPayload.zip', 'run_install.bat')

# Prefer the 32-bit IExpress binary so generated SFX stubs run on both 32-bit and 64-bit Windows.
$iexpressCandidates = @(
    (Join-Path $env:WINDIR 'SysWOW64\iexpress.exe'),
    (Join-Path $env:WINDIR 'System32\iexpress.exe')
)
$iexpress = $iexpressCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($iexpress)) {
    throw "IExpress not found in SysWOW64 or System32"
}
Write-Host "Using IExpress binary: $iexpress" -ForegroundColor Cyan

# Use standard unattended mode. The /M switch can leave only CAB artifacts
# without producing the final self-extracting EXE in some environments.
& $iexpress /N /Q $installSed

# Large runtime payloads (including .venv) can take much longer than 5 minutes
# for IExpress to finish writing the final stub.
$maxWaitSeconds = 1800
for ($i = 0; $i -lt $maxWaitSeconds -and -not (Test-Path $installerExe); $i++) {
    if (($i -gt 0) -and ($i % 60 -eq 0)) {
        Write-Host "Waiting for IExpress output... ${i}s" -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 1
}
if (-not (Test-Path $installerExe)) {
    throw "Failed to build ArrowLimousine_RemoteInstaller.exe"
}

if (-not (Test-Path $DropboxInstallDir)) {
    New-Item -ItemType Directory -Path $DropboxInstallDir -Force | Out-Null
}

Copy-Item $installerExe (Join-Path $DropboxInstallDir 'ArrowLimousine_RemoteInstaller.exe') -Force

Write-Host 'Remote EXE packaging complete.' -ForegroundColor Green
Write-Host "Installer EXE: $installerExe" -ForegroundColor Green
Write-Host "Dropbox install publish: $DropboxInstallDir" -ForegroundColor Green

if ($LASTEXITCODE -ne 0) {
    $LASTEXITCODE = 0
}
