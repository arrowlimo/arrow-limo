param(
    [ValidateSet('Daily', 'Weekly')]
    [string]$Frequency = 'Daily',
    [string]$AtTime = '02:00',
    [switch]$Disable
)

$ErrorActionPreference = 'Stop'

$taskName = 'ArrowLimousine_RebuildAndPackage'
$scriptPath = Join-Path $PSScriptRoot 'build_exe.ps1'

if ($Disable) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Scheduled rebuild task removed: $taskName" -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $scriptPath)) {
    throw "Build script not found: $scriptPath"
}

$timeParts = $AtTime.Split(':')
if ($timeParts.Count -ne 2) {
    throw 'AtTime must be in HH:mm format, for example 02:00'
}

$hour = [int]$timeParts[0]
$minute = [int]$timeParts[1]
$start = (Get-Date).Date.AddHours($hour).AddMinutes($minute)
if ($start -lt (Get-Date)) {
    $start = $start.AddDays(1)
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File \"$scriptPath\" -NoClean"
if ($Frequency -eq 'Daily') {
    $trigger = New-ScheduledTaskTrigger -Daily -At $start
} else {
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $start
}

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Scheduled rebuild task configured: $taskName" -ForegroundColor Green
Write-Host "Frequency: $Frequency at $AtTime" -ForegroundColor Green
