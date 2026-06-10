<#
.SYNOPSIS
    Self-healing prerequisite bootstrap for the Arrow Limousine desktop app.
    Run on the target machine after robocopy install completes.

.DESCRIPTION
    Ensures all runtime dependencies are present and functional:
      - pywin32 COM components registered (required for Outlook/printing)
      - Visual C++ 2015-2022 x64 Redistributable installed
      - Print Spooler service running
      - Outlook detected (non-blocking warning if absent)
      - pip packages verified / repaired from requirements.txt
      - All critical application files present

.PARAMETER InstallRoot
    Root folder where the app is installed (default: Y:\limo)
#>

param(
    [string]$InstallRoot = 'Y:\limo'
)

$ErrorActionPreference = 'Stop'

$hadWarnings = $false

function Write-Pass([string]$msg)    { Write-Host "  [OK] $msg"      -ForegroundColor Green }
function Write-Warn([string]$msg)    { Write-Host "  [WARN] $msg"    -ForegroundColor Yellow; $script:hadWarnings = $true }
function Write-Action([string]$msg)  { Write-Host "  [FIX] $msg"     -ForegroundColor Cyan }
function Write-Step([string]$msg)    { Write-Host "`n--- $msg ---"    -ForegroundColor Magenta }

# -----------------------------------------------------------------------
# 1. Verify critical application files are present
# -----------------------------------------------------------------------
Write-Step "Verifying required application files"

$requiredPaths = @(
    '.venv\Scripts\python.exe',
    'ArrowLimousineApp.exe',
    'desktop_app\main.py',
    'desktop_app\app_logger.py',
    'modern_backend\requirements.txt',
    '.env'
)

$missingFiles = @()
foreach ($rel in $requiredPaths) {
    $full = Join-Path $InstallRoot $rel
    if (Test-Path $full) {
        Write-Pass "$rel"
    } else {
        Write-Warn "MISSING: $rel"
        $missingFiles += $rel
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Warn "$($missingFiles.Count) required file(s) missing -- install may be incomplete."
}

# -----------------------------------------------------------------------
# 1b. File integrity manifest check
# -----------------------------------------------------------------------
$manifestFile = Join-Path $InstallRoot 'file_manifest.sha256'
if (Test-Path $manifestFile) {
    Write-Step "Verifying file integrity (manifest)"
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $manifestLines = [System.IO.File]::ReadAllLines($manifestFile)
    $manifestOk = 0
    $manifestFail = 0

    foreach ($line in $manifestLines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '  ', 2
        if ($parts.Count -lt 2) { continue }
        $expectedHash = $parts[0].Trim()
        $relPath      = $parts[1].Trim()
        $fullPath     = Join-Path $InstallRoot $relPath

        if (-not (Test-Path $fullPath -PathType Leaf)) {
            Write-Host "  [MISSING] $relPath" -ForegroundColor Red
            $manifestFail++
            $script:hadWarnings = $true
            continue
        }
        try {
            $stream = [System.IO.File]::OpenRead($fullPath)
            $hashBytes = $sha256.ComputeHash($stream)
            $stream.Dispose()
            $actualHash = [BitConverter]::ToString($hashBytes) -replace '-', ''
            if ($actualHash -ne $expectedHash) {
                Write-Host "  [CORRUPT] $relPath" -ForegroundColor Red
                $manifestFail++
                $script:hadWarnings = $true
            } else {
                $manifestOk++
            }
        } catch {
            Write-Host "  [ERROR] $relPath : $($_.Exception.Message)" -ForegroundColor Red
            $manifestFail++
            $script:hadWarnings = $true
        }
    }
    $sha256.Dispose()

    if ($manifestFail -eq 0) {
        Write-Pass "All $manifestOk files passed integrity check"
    } else {
        Write-Warn "$manifestFail file(s) failed integrity check -- re-run install.bat to repair"
    }
} else {
    Write-Host "  [SKIP] file_manifest.sha256 not found -- skipping integrity check" -ForegroundColor DarkGray
}

$pythonExe = Join-Path $InstallRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host "`n[FATAL] Python runtime not found at $pythonExe. Cannot continue bootstrap." -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------------------
# 2. pywin32 COM registration  (Outlook / win32com.client)
# -----------------------------------------------------------------------
Write-Step "Registering pywin32 COM components (Outlook/printing)"

$pywin32Script = Join-Path $InstallRoot '.venv\Scripts\pywin32_postinstall.py'
if (Test-Path $pywin32Script) {
    Write-Action "Running pywin32_postinstall.py -install ..."
    $pywin32Output = & "$pythonExe" "$pywin32Script" -install 2>&1
    $pywin32OutStr = ($pywin32Output | Out-String)
    if ($LASTEXITCODE -ne 0) {
        if ($pywin32OutStr -match 'No Python at') {
            Write-Warn "pywin32 COM registration skipped -- base Python install path not found on this machine (bundled .venv is sufficient for app functionality)"
        } else {
            $pywin32Output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
            Write-Warn "pywin32_postinstall returned exit code $LASTEXITCODE (may need Admin for system COM registration)"
        }
    } else {
        Write-Pass "pywin32 COM components registered"
    }
} else {
    Write-Warn "pywin32_postinstall.py not found -- Outlook COM may not be registered"
}

# -----------------------------------------------------------------------
# 3. Visual C++ 2015-2022 x64 Redistributable
# -----------------------------------------------------------------------
Write-Step "Checking Visual C++ Redistributable (required by Python packages)"

function Test-VCRedist {
    $dll1 = Join-Path $env:WINDIR 'System32\vcruntime140.dll'
    $dll2 = Join-Path $env:WINDIR 'System32\vcruntime140_1.dll'
    return (Test-Path $dll1) -and (Test-Path $dll2)
}

if (Test-VCRedist) {
    Write-Pass "Visual C++ runtime present (vcruntime140.dll + vcruntime140_1.dll)"
} else {
    Write-Action "Visual C++ runtime missing -- attempting install via winget..."
    $wingetAvailable = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)

    if ($wingetAvailable) {
        $wingetResult = & winget install Microsoft.VCRedist.2015+.x64 `
            --silent --accept-package-agreements --accept-source-agreements 2>&1
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
            # 0 = installed, -1978335189 = already installed (winget code 0x80073D0B)
            Write-Pass "Visual C++ Redistributable installed/confirmed via winget"
        } else {
            Write-Warn "winget install returned $LASTEXITCODE -- manual install may be needed"
            Write-Warn "Download: https://aka.ms/vs/17/release/vc_redist.x64.exe"
        }
    } else {
        Write-Warn "winget not available on this machine"
        Write-Warn "Manually install Visual C++ Redistributable from:"
        Write-Warn "  https://aka.ms/vs/17/release/vc_redist.x64.exe"
    }
}

# -----------------------------------------------------------------------
# 4. Print Spooler service
# -----------------------------------------------------------------------
Write-Step "Checking Print Spooler service"

$spooler = Get-Service -Name 'Spooler' -ErrorAction SilentlyContinue
if ($null -eq $spooler) {
    Write-Warn "Print Spooler service not found on this system"
} elseif ($spooler.Status -eq 'Running') {
    Write-Pass "Print Spooler is running"
} else {
    Write-Action "Print Spooler is $($spooler.Status) -- attempting to start..."
    try {
        Set-Service -Name 'Spooler' -StartupType Automatic -ErrorAction SilentlyContinue
        Start-Service -Name 'Spooler'
        Write-Pass "Print Spooler started successfully"
    } catch {
        Write-Warn "Could not start Print Spooler: $($_.Exception.Message)"
    }
}

# -----------------------------------------------------------------------
# 5. Outlook detection  (non-blocking - app emails use win32com.client)
# -----------------------------------------------------------------------
Write-Step "Checking Outlook installation"

$outlookPaths = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE'
)
$outlookFound = $outlookPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($outlookFound) {
    $outlookExePath = (Get-ItemProperty $outlookFound).'(default)' -replace '"', ''
    Write-Pass "Outlook detected: $outlookExePath"
} else {
    # Also check common program files paths
    $outlookExeCandidates = @(
        "${env:ProgramFiles}\Microsoft Office\root\Office16\OUTLOOK.EXE",
        "${env:ProgramFiles}\Microsoft Office\Office16\OUTLOOK.EXE",
        "${env:ProgramFiles(x86)}\Microsoft Office\root\Office16\OUTLOOK.EXE"
    )
    $outlookExe = $outlookExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($outlookExe) {
        Write-Pass "Outlook found at: $outlookExe"
    } else {
        Write-Warn "Outlook not detected -- email automation features will not work"
        Write-Warn "Install Microsoft Outlook or Microsoft 365 to enable email features"
    }
}

# -----------------------------------------------------------------------
# 6. pip package verification + auto-repair
# -----------------------------------------------------------------------
Write-Step "Verifying Python package dependencies"

$requirementsPath = Join-Path $InstallRoot 'modern_backend\requirements.txt'
$stampPath = Join-Path $InstallRoot '.venv\limo_pkg_stamp.txt'

function Get-RequirementsHash {
    if (-not (Test-Path $requirementsPath)) { return $null }
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $stream = [System.IO.File]::OpenRead($requirementsPath)
        try {
            $bytes = $sha.ComputeHash($stream)
            return ([BitConverter]::ToString($bytes) -replace '-', '')
        } finally {
            $stream.Dispose()
            $sha.Dispose()
        }
    } catch {
        return $null
    }
}

$currentHash = Get-RequirementsHash
$storedHash  = if (Test-Path $stampPath) { (Get-Content $stampPath -Raw).Trim() } else { '' }

$pipCheckFailed = $false
$ErrorActionPreference = 'Continue'
$checkOutput = & "$pythonExe" -m pip check 2>&1 | Out-String
$pipCheckExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($pipCheckExit -ne 0) {
    $pipCheckFailed = $true
    Write-Warn "pip check found broken/missing dependencies:`n$checkOutput"
}

if ($pipCheckFailed -or ($currentHash -and ($currentHash -ne $storedHash))) {
    if ($currentHash -ne $storedHash) {
        Write-Action "Requirements hash changed -- repairing packages..."
    } else {
        Write-Action "Broken dependencies detected -- repairing from requirements.txt..."
    }

    & "$pythonExe" -m pip install --disable-pip-version-check --quiet -r $requirementsPath 2>&1 |
        ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

    if ($LASTEXITCODE -eq 0) {
        # Re-register pywin32 in case it was re-installed
        if (Test-Path $pywin32Script) {
            & "$pythonExe" "$pywin32Script" -install 2>&1 | Out-Null
        }
        Set-Content -Path $stampPath -Value $currentHash -Encoding UTF8
        Write-Pass "Package repair completed and stamp updated"
    } else {
        Write-Warn "pip repair returned non-zero exit - some packages may be missing"
    }
} else {
    # Write stamp if first time
    if (-not (Test-Path $stampPath) -and $currentHash) {
        Set-Content -Path $stampPath -Value $currentHash -Encoding UTF8
    }
    Write-Pass "All packages verified (requirements hash matches)"
}

# -----------------------------------------------------------------------
# 7. Final import smoke test
# -----------------------------------------------------------------------
Write-Step "Running runtime import smoke test"

$smokeScript = @'
import importlib, sys
modules = {
    "win32com.client": "Outlook/COM (pywin32)",
    "pythoncom":       "COM bridge (pywin32)",
    "win32print":      "Printer API (pywin32)",
    "reportlab":       "PDF rendering",
    "PyQt6":           "Desktop UI (PyQt6)",
    "requests":        "HTTP client",
    "pandas":          "Data analysis",
    "psycopg2":        "PostgreSQL driver",
    "fastapi":         "Web API backend",
    "pypdf":           "PDF parser",
    "openpyxl":        "Excel export",
    "dotenv":          "Environment config"
}
failed = []
for mod, label in modules.items():
    try:
        importlib.import_module(mod)
        print(f"  OK  {label} ({mod})")
    except Exception as e:
        print(f"  FAIL {label} ({mod}): {e}")
        failed.append(mod)
if failed:
    print(f"\nFAILED_IMPORTS: {failed}")
    sys.exit(1)
print("\nALL_IMPORTS_OK")
'@

$tempSmoke = Join-Path $env:TEMP 'limo_smoke_test.py'
Set-Content -Path $tempSmoke -Value $smokeScript -Encoding UTF8

$ErrorActionPreference = 'Continue'
$smokeOut = & "$pythonExe" "$tempSmoke" 2>$null
$smokeExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$smokeOut | ForEach-Object {
    if ($_ -match 'FAIL') {
        Write-Host "  $_" -ForegroundColor Yellow
        $script:hadWarnings = $true
    } elseif ($_ -match 'OK|ALL_IMPORTS') {
        Write-Host "  $_" -ForegroundColor Green
    } else {
        Write-Host "  $_"
    }
}
if ($smokeExit -ne 0) {
    Write-Warn "Smoke test exited with code $smokeExit - some imports may be broken"
}
Remove-Item -Path $tempSmoke -Force -ErrorAction SilentlyContinue

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
Write-Host ""
if ($hadWarnings) {
    Write-Host "=============================================" -ForegroundColor Yellow
    Write-Host " Bootstrap completed WITH WARNINGS." -ForegroundColor Yellow
    Write-Host " See [WARN] lines above for items that need" -ForegroundColor Yellow
    Write-Host " manual attention (e.g. Outlook, VC++, COM)." -ForegroundColor Yellow
    Write-Host "=============================================" -ForegroundColor Yellow
} else {
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host " Bootstrap complete -- all prerequisites OK." -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
}
