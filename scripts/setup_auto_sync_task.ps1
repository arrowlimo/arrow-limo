# Create Windows Scheduled Task for Neon Sync
# Run as Administrator
# This sets up automatic daily full sync from local → Neon at 7 AM

$TaskName = "Arrow Limo - Neon Database Sync"
$PythonPath = "L:\limo\.venv\Scripts\python.exe"
$ScriptPath = "L:\limo\scripts\auto_sync_to_neon.py"
$LogPath = "L:\limo\logs\neon_sync.log"

# Create logs directory if needed
New-Item -Path "L:\limo\logs" -ItemType Directory -Force | Out-Null

Write-Host "Setting up automated Neon sync task..." -ForegroundColor Cyan
Write-Host ""

# Create the scheduled task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument $ScriptPath `
    -WorkingDirectory "L:\limo"

# Create daily trigger (runs at 7 AM every day)
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM

# Create settings (run even if user is not logged in, highest privileges)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Create the principal (run with SYSTEM account)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# Register the task
try {
    # Remove existing task if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Create new task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Automatically syncs local almsdata to Neon cloud database daily at 7 AM with full table reload" | Out-Null
    
    Write-Host "✓ Scheduled task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Yellow
    Write-Host "  Name: $TaskName"
    Write-Host "  Schedule: Daily at 7:00 AM (full sync for day match)"
    Write-Host "  Script: $ScriptPath"
    Write-Host "  Log: $LogPath"
    Write-Host ""
    Write-Host "To test immediately:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host ""
    Write-Host "To view task:" -ForegroundColor Yellow
    Write-Host "  Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host ""
    Write-Host "To disable task:" -ForegroundColor Yellow
    Write-Host "  Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host "✗ Failed to create task: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure you're running as Administrator" -ForegroundColor Yellow
    exit 1
}
