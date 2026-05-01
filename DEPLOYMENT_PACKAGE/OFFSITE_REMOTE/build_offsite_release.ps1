param(
    [switch]$Clean,
    [switch]$CompileInstaller,
    [string]$ReleaseName = "ArrowLimoOffsite"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$buildRoot = Join-Path $PSScriptRoot "build"
$stageRoot = Join-Path $buildRoot "staging"
$outputRoot = Join-Path $buildRoot "output"
$stageDir = Join-Path $stageRoot $ReleaseName
$runtimeDir = Join-Path $PSScriptRoot "runtime"
$venvDir = Join-Path $repoRoot ".venv"
$neonEnv = Join-Path $repoRoot ".env.neon"
$prereqDir = Join-Path $PSScriptRoot "prerequisites"
$vcRedistOut = Join-Path $prereqDir "vc_redist.x64.exe"
$vcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

function Write-Step([string]$Message) {
    Write-Host "" 
    Write-Host $Message -ForegroundColor Cyan
}

function Assert-Path([string]$PathValue, [string]$Label) {
    if (-not (Test-Path $PathValue)) {
        throw "$Label not found: $PathValue"
    }
}

function Read-DotEnvFile([string]$PathValue) {
    $map = @{}
    foreach ($line in Get-Content $PathValue) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $map[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $map
}

function Copy-Tree([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $null = robocopy $Source $Destination /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /XD __pycache__ .pytest_cache node_modules .git build dist
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed for $Source"
    }
}

function Ensure-VCRedistInstaller([string]$DestinationPath, [string]$Url) {
    if (Test-Path $DestinationPath) {
        return
    }

    New-Item -ItemType Directory -Path (Split-Path $DestinationPath -Parent) -Force | Out-Null
    Write-Step "[pre] Downloading Visual C++ redistributable"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $DestinationPath -UseBasicParsing
    } catch {
        throw "Failed to download Visual C++ redistributable from $Url. $_"
    }
}

Assert-Path $venvDir ".venv"
Assert-Path $neonEnv ".env.neon"
Assert-Path (Join-Path $repoRoot "desktop_app\main.py") "desktop_app"
Assert-Path $runtimeDir "runtime helper directory"

Ensure-VCRedistInstaller -DestinationPath $vcRedistOut -Url $vcRedistUrl

if ($Clean -and (Test-Path $buildRoot)) {
    Remove-Item -Recurse -Force $buildRoot
}

New-Item -ItemType Directory -Path $stageDir -Force | Out-Null
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$version = Get-Date -Format "yyyy.MM.dd.HHmm"
$gitHash = "nogit"
try {
    $gitHash = (git -C $repoRoot rev-parse --short HEAD).Trim()
} catch {
}

$appRoot = Join-Path $stageDir ""
$desktopAppDest = Join-Path $stageDir "desktop_app"
$modernBackendDest = Join-Path $stageDir "modern_backend"
$frontendDest = Join-Path $stageDir "frontend"
$venvDest = Join-Path $stageDir ".venv"

Write-Step "[1/6] Staging application folders"
Copy-Tree (Join-Path $repoRoot "desktop_app") $desktopAppDest
Copy-Tree (Join-Path $repoRoot "modern_backend") $modernBackendDest

if (Test-Path (Join-Path $repoRoot "frontend\dist")) {
    Copy-Tree (Join-Path $repoRoot "frontend\dist") (Join-Path $frontendDest "dist")
}

if (Test-Path (Join-Path $repoRoot "photo")) {
    Copy-Tree (Join-Path $repoRoot "photo") (Join-Path $stageDir "photo")
}

Write-Step "[2/6] Staging bundled Python runtime"
Copy-Tree $venvDir $venvDest

Write-Step "[3/6] Writing runtime helper files"
Copy-Item (Join-Path $runtimeDir "launcher.py") (Join-Path $stageDir "launcher.py") -Force
Copy-Item (Join-Path $runtimeDir "START_ARROW_LIMO_OFFSITE.bat") (Join-Path $stageDir "START_ARROW_LIMO_OFFSITE.bat") -Force
Copy-Item (Join-Path $runtimeDir "Bootstrap-Prereqs.ps1") (Join-Path $stageDir "Bootstrap-Prereqs.ps1") -Force
Copy-Item (Join-Path $runtimeDir "Configure-OffsiteInstall.ps1") (Join-Path $stageDir "Configure-OffsiteInstall.ps1") -Force
Copy-Item (Join-Path $runtimeDir "Apply-OffsiteUpdate.ps1") (Join-Path $stageDir "Apply-OffsiteUpdate.ps1") -Force

Copy-Tree $prereqDir (Join-Path $stageDir "prerequisites")

$neon = Read-DotEnvFile $neonEnv
$template = @"
# Auto-generated offsite deployment template
ALMS_DEFAULT_DB_TARGET=neon
ALMS_ENABLE_CLOUD_LOGIN=1
ALMS_ENABLE_WEB_LOGIN=1

DB_TARGET=neon
DB_HOST=$($neon["DB_HOST"])
DB_NAME=$($neon["DB_NAME"])
DB_USER=$($neon["DB_USER"])
DB_PASSWORD=$($neon["DB_PASSWORD"])
DB_PORT=$($neon["DB_PORT"])
DB_SSLMODE=$($neon["DB_SSLMODE"])
DB_CHANNEL_BINDING=$($neon["DB_CHANNEL_BINDING"])

NEON_DB_HOST=$($neon["DB_HOST"])
NEON_DB_NAME=$($neon["DB_NAME"])
NEON_DB_USER=$($neon["DB_USER"])
NEON_DB_PASSWORD=$($neon["DB_PASSWORD"])
NEON_DB_PORT=$($neon["DB_PORT"])
NEON_DB_SSLMODE=$($neon["DB_SSLMODE"])
NEON_DB_CHANNEL_BINDING=$($neon["DB_CHANNEL_BINDING"])

LOCAL_DB_HOST=localhost
LOCAL_DB_PORT=5432
LOCAL_DB_NAME=almsdata
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=
LOCAL_DB_SSLMODE=

WORKSTATION_ID=__WORKSTATION_ID__
DATA_ROOT=__DATA_ROOT__
FILE_STORAGE_ROOT=__REMOTE_FILES_ROOT__
RECEIPTS_ROOT=__RECEIPTS_ROOT__
PHOTOS_ROOT=__PHOTOS_ROOT__
REPORTS_ROOT=__REPORTS_ROOT__
LOGS_ROOT=__LOGS_ROOT__
ALMS_UPDATE_ROOT=__UPDATE_ROOT__
ALMS_WEB_URL=https://arrow-limo.onrender.com

SESSION_TIMEOUT_MINUTES=30
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
AUTO_LOGIN=0
"@
Set-Content -Path (Join-Path $stageDir ".env.template") -Value $template -Encoding UTF8

$versionJson = @{
    release_name = $ReleaseName
    version = $version
    git_hash = $gitHash
    built_at = (Get-Date).ToString("s")
    db_target = "neon"
} | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $stageDir "version.json") -Value $versionJson -Encoding UTF8

Write-Step "[4/6] Writing Inno Setup build include"
$isccInclude = @"
#define AppVersion "$version"
#define StageDir "$stageDir"
#define OutputDir "$outputRoot"
#define OutputBaseFilename "ArrowLimoOffsite-Installer-$version"
"@
Set-Content -Path (Join-Path $PSScriptRoot "BuildVersion.iss.inc") -Value $isccInclude -Encoding ASCII

Write-Step "[5/6] Creating portable fallback zip"
$portableZip = Join-Path $outputRoot "ArrowLimoOffsite-Portable-$version.zip"
if (Test-Path $portableZip) {
    Remove-Item $portableZip -Force
}
Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $portableZip -CompressionLevel Optimal

if ($CompileInstaller) {
    Write-Step "[6/6] Compiling Inno Setup installer"
    $isccCandidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        Write-Host "Inno Setup 6 not found. Downloading and installing silently..." -ForegroundColor Yellow
        $isSetupUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_3_3/innosetup-6.3.3.exe"
        $isSetupExe = Join-Path $env:TEMP "innosetup-6.3.3.exe"
        if (-not (Test-Path $isSetupExe)) {
            try {
                Invoke-WebRequest -Uri $isSetupUrl -OutFile $isSetupExe -UseBasicParsing
            } catch {
                throw "Failed to download Inno Setup 6 from $isSetupUrl. $_"
            }
        }
        $installProc = Start-Process -FilePath $isSetupExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-" -Wait -PassThru
        if ($installProc.ExitCode -ne 0) {
            throw "Inno Setup 6 installation failed with exit code $($installProc.ExitCode)"
        }
        $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $iscc) {
            throw "Inno Setup 6 installed but ISCC.exe still not found at expected locations."
        }
        Write-Host "Inno Setup 6 installed successfully." -ForegroundColor Green
    }

    & $iscc (Join-Path $PSScriptRoot "ArrowLimoOffsite.iss") | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed"
    }

    $compiledExe = Get-ChildItem -Path $outputRoot -Filter "ArrowLimoOffsite-Installer-*.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($compiledExe) {
        Write-Host "Installer compiled: $($compiledExe.FullName)" -ForegroundColor Green
    }
} else {
    Write-Step "[6/6] Skipping installer compilation (use -CompileInstaller to build the .exe)"
}

Write-Host "" 
Write-Host "Offsite release staged successfully." -ForegroundColor Green
Write-Host "Stage: $stageDir" -ForegroundColor Gray
Write-Host "Output: $outputRoot" -ForegroundColor Gray