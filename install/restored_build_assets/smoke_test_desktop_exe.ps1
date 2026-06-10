param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [int]$StartupTimeoutSeconds = 20
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $ExePath)) {
    throw "Smoke test failed: executable not found at $ExePath"
}

Write-Host "Running smoke test for: $ExePath" -ForegroundColor Yellow
$process = Start-Process -FilePath $ExePath -PassThru

try {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $process.Refresh()
        if ($process.HasExited) {
            throw "Smoke test failed: process exited early with code $($process.ExitCode)."
        }

        # Consider startup successful once the process is alive long enough to indicate no immediate crash.
        if ($process.StartTime -and (((Get-Date) - $process.StartTime).TotalSeconds -ge 5)) {
            break
        }
    }

    $process.Refresh()
    if ($process.HasExited) {
        throw "Smoke test failed: process exited before startup timeout."
    }

    Write-Host "Smoke test passed: executable launched successfully." -ForegroundColor Green
}
finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}
