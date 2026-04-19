Set-Location "L:\limo"

$ErrorActionPreference = "Stop"

Write-Host "[1/5] Verifying Python venv..."
if (!(Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: .venv python not found at L:\limo\.venv\Scripts\python.exe"
    exit 1
}

Write-Host "[2/5] Running GL CSV vs ALMS audit script..."
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "archive\tmp_zip_analysis\gl_csv_vs_alms_manual_run_$ts.log"
& ".\.venv\Scripts\python.exe" "archive\tmp_zip_analysis\gl_csv_vs_alms_audit.py" *>&1 | Tee-Object -FilePath $log
Write-Host "Log: $log"

Write-Host "[3/5] Checking expected output files..."
$files = @(
  "archive\tmp_zip_analysis\gl_csv_vs_alms_audit_summary.txt",
  "archive\tmp_zip_analysis\gl_csv_vs_alms_row_results.csv",
  "archive\tmp_zip_analysis\gl_csv_vs_alms_missing_only.csv",
  "archive\tmp_zip_analysis\gl_csv_vs_alms_mismatch_only.csv",
  "archive\tmp_zip_analysis\gl_csv_vs_alms_key_stats.csv"
)
foreach ($f in $files) {
  Write-Host "$f => $(Test-Path $f)"
}

Write-Host "[4/5] Key totals from summary..."
if (Test-Path "archive\tmp_zip_analysis\gl_csv_vs_alms_audit_summary.txt") {
  Select-String -Path "archive\tmp_zip_analysis\gl_csv_vs_alms_audit_summary.txt" -Pattern "Per-file class totals|Combined class totals|PRESENT_STRONG|PRESENT_WEAK|MISSING_IN_ALMS|MISMATCH_IN_ALMS" | ForEach-Object { $_.Line }
} else {
  Write-Host "Summary file missing. Check log output."
}

Write-Host "[5/5] Done."
