$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -in @('waitress-serve','python') }
if (-not $procs) {
  Write-Output "No waitress/python processes found."
  exit 0
}
foreach ($p in $procs) {
  try {
    if ($p.Path -and ($p.Path -like "L:\limo\*" -or $p.Path -like "L:\limo\.venv\Scripts\*")) {
      Write-Host "Stopping PID=$($p.Id) Name=$($p.ProcessName) Path=$($p.Path)"
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
  } catch {}
}
