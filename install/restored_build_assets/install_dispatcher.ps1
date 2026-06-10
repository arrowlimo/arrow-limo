param(
    [string]$SourcePath = $PSScriptRoot,
    [string]$TargetRoot = "Y:\limo",
    [string]$IconPath = "E:\new shit\arrowyellow.ico",
    [bool]$LaunchApp = $true,
    [bool]$FullClean = $true,
    [bool]$RunSmokeTest = $true,
    [int]$SmokeTestSeconds = 8,
    [bool]$SkipBackup = $false,
    [switch]$NoElevation,
    [bool]$ShowUi = $true
)

$ErrorActionPreference = 'Stop'

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

$TargetRoot = Resolve-TargetRoot -Path $TargetRoot

$updateDispatcher = Join-Path $SourcePath 'update_dispatcher.ps1'
if (-not (Test-Path $updateDispatcher)) {
    throw "update_dispatcher.ps1 not found in package source: $SourcePath"
}

$args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $updateDispatcher,
    '-SourcePath', $SourcePath,
    '-TargetRoot', $TargetRoot,
    '-IconPath', $IconPath,
    '-LaunchApp', $(if ($LaunchApp) { '1' } else { '0' }),
    '-FullClean', $(if ($FullClean) { '1' } else { '0' }),
    '-RunSmokeTest', $(if ($RunSmokeTest) { '1' } else { '0' }),
    '-SmokeTestSeconds', $SmokeTestSeconds,
    '-SkipBackup', $(if ($SkipBackup) { '1' } else { '0' }),
    '-ShowUi', $(if ($ShowUi) { '1' } else { '0' })
)

if ($NoElevation) {
    $args += '-NoElevation'
}

$pwsh = "$env:ProgramFiles\PowerShell\7\pwsh.exe"
if (-not (Test-Path $pwsh)) { $pwsh = 'powershell.exe' }
& $pwsh @args
exit $LASTEXITCODE
