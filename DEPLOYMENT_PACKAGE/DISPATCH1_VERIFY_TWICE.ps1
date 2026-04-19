param(
    [string]$ServerIp = "192.168.1.176",
    [string]$RunLabel = "pass1"
)

$ErrorActionPreference = "Continue"

$outDir = "L:\limo\DEPLOYMENT_PACKAGE\ERRORS ON DISPATCH1"
if (-not (Test-Path $outDir)) {
    New-Item -Path $outDir -ItemType Directory -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $outDir ("VERIFY_{0}_{1}.txt" -f $RunLabel, $timestamp)

function Add-Line {
    param([string]$Text)
    $Text | Out-File -FilePath $outFile -Append -Encoding UTF8
}

Add-Line "DISPATCH1 Verification Report"
Add-Line "Run Label: $RunLabel"
Add-Line "Timestamp: $(Get-Date -Format o)"
Add-Line "Server IP: $ServerIp"
Add-Line ""

Add-Line "=== MACHINE CONTEXT ==="
Add-Line ("Hostname: {0}" -f $env:COMPUTERNAME)
Add-Line ("User: {0}" -f ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name))
$admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Add-Line ("IsAdmin: {0}" -f $admin)
Add-Line ""

Add-Line "=== NETWORK REACHABILITY ==="
try {
    $ping = Test-Connection -ComputerName $ServerIp -Count 1 -ErrorAction Stop
    Add-Line ("Ping {0}: OK ({1})" -f $ServerIp, $ping[0].Address)
} catch {
    Add-Line ("Ping {0}: FAILED ({1})" -f $ServerIp, $_.Exception.Message)
}
Add-Line ""

Add-Line "=== SHARE PATH TESTS ==="
$paths = @("\\$ServerIp\limo", "\\$ServerIp\limo_files", "\\DISPATCHMAIN\limo", "\\DISPATCHMAIN\limo_files")
foreach ($p in $paths) {
    Add-Line ("{0} => {1}" -f $p, (Test-Path $p))
}
Add-Line ""

Add-Line "=== DRIVE MAPS (net use) ==="
cmd /c "net use" | Out-File -FilePath $outFile -Append -Encoding UTF8
Add-Line ""

Add-Line "=== CACHED CREDENTIALS (cmdkey /list) ==="
cmd /c "cmdkey /list" | Out-File -FilePath $outFile -Append -Encoding UTF8
Add-Line ""

Add-Line "=== INSTALLER/LAUNCHER FILES ==="
$mustHave = @(
    "Y:\ArrowLimo\START_DISPATCH1.bat",
    "Y:\ArrowLimo\app\START_DISPATCH.bat",
    "Y:\ArrowLimo\app\launcher.py",
    "Y:\ArrowLimo\app\desktop_app\main.py"
)
foreach ($f in $mustHave) {
    Add-Line ("{0} => {1}" -f $f, (Test-Path $f))
}
Add-Line ""

Add-Line "=== LAST ERROR LOG SNIPPET ==="
$errFile = "L:\limo\DEPLOYMENT_PACKAGE\ERRORS ON DISPATCH1\ERROR.txt"
if (Test-Path $errFile) {
    Add-Line ("Using: {0}" -f $errFile)
    Get-Content $errFile -Tail 80 | Out-File -FilePath $outFile -Append -Encoding UTF8
} else {
    Add-Line "ERROR.txt not found"
}
Add-Line ""

Add-Line "=== QUICK RESULT ==="
$hasL = Test-Path "L:\"
$hasZ = Test-Path "Z:\"
$hasLauncher = Test-Path "Y:\ArrowLimo\app\START_DISPATCH.bat"
if ($hasL -and $hasZ -and $hasLauncher) {
    Add-Line "STATUS: PASS (links and launcher present)"
} else {
    Add-Line "STATUS: FAIL (missing links and/or launcher)"
}

Write-Host "Verification report written:" -ForegroundColor Green
Write-Host $outFile -ForegroundColor Green
