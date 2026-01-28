param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 5000
)
$ErrorActionPreference = 'Stop'
$venv = "L:/limo/.venv/Scripts"
$exe = Join-Path $venv "waitress-serve.exe"
if (-not (Test-Path $exe)) {
    Write-Host "Installing waitress into venv..."
    & "$venv/python.exe" -m pip install waitress | Out-Host
}
$env:API_HOST = $BindHost
$env:API_PORT = "$Port"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.Arguments = "--listen=${BindHost}:${Port} api:app"
$psi.WorkingDirectory = "L:/limo"
$psi.CreateNoWindow = $true
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Seconds 1
Write-Output "Started API PID=$($p.Id) on http://${BindHost}:${Port}"
