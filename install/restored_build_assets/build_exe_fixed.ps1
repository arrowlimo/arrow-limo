param(
    [Switch]$Clean = $false,
    [Switch]$NoClean = $false,
    [Switch]$SkipSmokeTest = $false,
    [Switch]$SkipPackaging = $false,
    [string]$DropboxInstallDir,
    [string]$DropboxUpdateDir
)

if (-not $DropboxInstallDir) { $DropboxInstallDir = Join-Path $env:USERPROFILE 'Dropbox\install' }
if (-not $DropboxUpdateDir) { $DropboxUpdateDir = Join-Path $env:USERPROFILE 'Dropbox\updates' }

$ErrorActionPreference = 'Stop'
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptPath '..\..')).Path
$SpecPath = Join-Path $ScriptPath 'build_desktop_app.spec'
$SmokeTestPath = Join-Path $ScriptPath 'smoke_test_desktop_exe.ps1'
$PackagePath = Join-Path $ScriptPath 'package_remote_exes.ps1'

Set-Location $RepoRoot

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Arrow Limousine Desktop App - PyInstaller Build Script       ║" -ForegroundColor Cyan
Write-Host "║  Building standalone Windows executable                        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow
$venv = ".\.venv\Scripts\pip.exe"
if (-not (Test-Path $venv)) {
    Write-Host "❌ Virtual environment not found at .\.venv" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Virtual environment found" -ForegroundColor Green

Write-Host "[2/7] Installing PyInstaller..." -ForegroundColor Yellow
& .\.venv\Scripts\pip.exe install -q pyinstaller 2>&1 | Out-Null

if ($Clean) {
    Write-Host "[3/7] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue }
    if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" -ErrorAction SilentlyContinue }
    if (Test-Path ".\.spec") { Remove-Item -Force ".\.spec" -ErrorAction SilentlyContinue }
}

Write-Host "[4/7] Checking configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".\.env")) {
    if (Test-Path ".\.env.example") { Copy-Item ".\.env.example" ".\.env" }
}

Write-Host "[5/7] Building executable with PyInstaller..." -ForegroundColor Yellow
& .\.venv\Scripts\pyinstaller.exe $SpecPath --noconfirm --log-level=INFO

if ($LASTEXITCODE -eq 0) {
    $builtExe = Join-Path $RepoRoot 'dist\ArrowLimousineApp.exe'

    if (-not $SkipSmokeTest) {
        Write-Host "[6/7] Running smoke test..." -ForegroundColor Yellow
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SmokeTestPath -ExePath $builtExe
    }

    if (-not $SkipPackaging) {
        Write-Host "[7/7] Building remote installer/updater EXEs..." -ForegroundColor Yellow
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PackagePath 
            -AppExePath $builtExe 
            -DropboxInstallDir $DropboxInstallDir 
            -DropboxUpdateDir $DropboxUpdateDir
    }
    Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
