<#
Registers a Windows Scheduled Task to run the personal claimables scanner monthly
for the last full calendar month. Runs at 6:00 AM on the 1st of each month.

Usage (PowerShell as Administrator):
  ./register_monthly_personal_claimables_task.ps1

It will create a task named 'Limo-PersonalClaimables-LastMonth'.
#>

param(
  [string]$TaskName = 'Limo-PersonalClaimables-LastMonth',
  [string]$Workspace = 'l:\limo'
)

# Resolve python executable
$python = $env:PYTHON || 'python'

# Script to run
$scriptPath = Join-Path $Workspace 'scripts\scan_personal_claimables.py'

if (-not (Test-Path $scriptPath)) {
  Write-Error "Script not found: $scriptPath"
  exit 1
}

# Action: run last-month
$arguments = '"' + $scriptPath + '" --last-month'

$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $Workspace

# Trigger: monthly on the 1st at 06:00
$trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At 06:00AM

# Principal: run with highest privileges (adjust UserId as needed or run under current user)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

# Settings: allow run on demand, restart if missed
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# If task exists, remove it first
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "It will run: $python $arguments"