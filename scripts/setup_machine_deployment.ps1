# Multi-Machine Deployment Setup Script for Arrow Limo Desktop App
# This script configures Task Scheduler auto-start and Neon connection on a target machine
# Usage: .\setup_machine_deployment.ps1 -MachineNumber 1 -NetworkShare "\\SERVER\arrow-limo-app"

param(
    [Parameter(Mandatory=$true)]
    [int]$MachineNumber,
    
    [Parameter(Mandatory=$true)]
    [string]$NetworkShare,
    
    [string]$LocalAppPath = "C:\ArrowLimoApp"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Arrow Limo Desktop App - Machine Setup" -ForegroundColor Cyan
Write-Host "Machine #$MachineNumber" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Verify network share is accessible
Write-Host "`nStep 1: Verifying network share access..." -ForegroundColor Yellow
if (-not (Test-Path -Path $NetworkShare)) {
    Write-Host "ERROR: Cannot access network share: $NetworkShare" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Network share accessible: $NetworkShare" -ForegroundColor Green

# Step 2: Create local app directory
Write-Host "`nStep 2: Creating local app directory..." -ForegroundColor Yellow
if (-not (Test-Path -Path $LocalAppPath)) {
    New-Item -ItemType Directory -Path $LocalAppPath -Force | Out-Null
    Write-Host "✓ Created: $LocalAppPath" -ForegroundColor Green
} else {
    Write-Host "✓ Already exists: $LocalAppPath" -ForegroundColor Green
}

# Step 3: Copy app files from network share
Write-Host "`nStep 3: Copying app files from network share..." -ForegroundColor Yellow
$itemsToCopy = @(
    "main.py",
    "desktop_app",
    "requirements.txt",
    ".env.neon"
)

foreach ($item in $itemsToCopy) {
    $source = Join-Path -Path $NetworkShare -ChildPath $item
    $dest = Join-Path -Path $LocalAppPath -ChildPath $item
    
    if (Test-Path -Path $source) {
        if ((Get-Item $source).PSIsContainer) {
            Copy-Item -Path $source -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  ✓ Copied folder: $item" -ForegroundColor Green
        } else {
            Copy-Item -Path $source -Destination $dest -Force
            Write-Host "  ✓ Copied file: $item" -ForegroundColor Green
        }
    } else {
        Write-Host "  ⚠ Not found in share: $item" -ForegroundColor Yellow
    }
}

# Step 4: Copy .env.neon to .env
Write-Host "`nStep 4: Setting up environment file..." -ForegroundColor Yellow
$envSource = Join-Path -Path $LocalAppPath -ChildPath ".env.neon"
$envDest = Join-Path -Path $LocalAppPath -ChildPath ".env"
if (Test-Path -Path $envSource) {
    Copy-Item -Path $envSource -Destination $envDest -Force
    Write-Host "✓ Created .env from .env.neon" -ForegroundColor Green
} else {
    Write-Host "⚠ .env.neon not found—you'll need to create .env manually" -ForegroundColor Yellow
}

# Step 5: Install Python dependencies
Write-Host "`nStep 5: Installing Python dependencies..." -ForegroundColor Yellow
$reqFile = Join-Path -Path $LocalAppPath -ChildPath "requirements.txt"
if (Test-Path -Path $reqFile) {
    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonExe) {
        & python -m pip install -r $reqFile --quiet 2>&1 | Out-Null
        Write-Host "✓ Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "⚠ Python not found in PATH—install manually or add Python to PATH" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠ requirements.txt not found" -ForegroundColor Yellow
}

# Step 6: Create Task Scheduler job for auto-start
Write-Host "`nStep 6: Creating Task Scheduler auto-start job..." -ForegroundColor Yellow

$taskName = "ArrowLimoApp-Machine$MachineNumber"
$taskPath = "\ArrowLimo\"
$pythonPath = Get-Command python -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }

if (-not $pythonPath) {
    $pythonPath = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe"
    if (-not (Test-Path $pythonPath)) {
        Write-Host "⚠ Python not found—please install Python 3.12+ or set pythonPath manually" -ForegroundColor Yellow
    }
}

# Remove existing task if present
$existingTask = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -InputObject $existingTask -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  ✓ Removed existing task" -ForegroundColor Green
}

# Create new task
$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "-X utf8 main.py" `
    -WorkingDirectory $LocalAppPath

$trigger = New-ScheduledTaskTrigger -AtLogOn

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$task = New-ScheduledTask `
    -Action $action `
    -Principal $principal `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Arrow Limo Desktop App - Auto-start on login for Machine $MachineNumber"

Register-ScheduledTask `
    -TaskName $taskName `
    -TaskPath $taskPath `
    -InputObject $task `
    -Force | Out-Null

Write-Host "✓ Task Scheduler job created: $taskPath$taskName" -ForegroundColor Green

# Step 7: Create desktop shortcut
Write-Host "`nStep 7: Creating desktop shortcut..." -ForegroundColor Yellow
$desktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
$shortcutPath = Join-Path -Path $desktopPath -ChildPath "Arrow Limo App.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonPath
$shortcut.Arguments = "-X utf8 main.py"
$shortcut.WorkingDirectory = $LocalAppPath
$shortcut.Description = "Arrow Limo Desktop Application - Machine $MachineNumber"
$shortcut.Save()

Write-Host "✓ Desktop shortcut created" -ForegroundColor Green

# Step 8: Verify connection to Neon
Write-Host "`nStep 8: Testing Neon connection..." -ForegroundColor Yellow
$pythonTest = @"
import sys
sys.path.insert(0, r'$LocalAppPath')
try:
    import psycopg2
    from dotenv import load_dotenv
    import os
    
    load_dotenv(r'$($envDest)')
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    
    cur = conn.cursor()
    cur.execute('SELECT version()')
    version = cur.fetchone()[0]
    print(f'✓ Neon connection successful: {version}')
    
    # Check key tables
    cur.execute('SELECT COUNT(*) FROM public.charters')
    charter_count = cur.fetchone()[0]
    print(f'✓ Charters table: {charter_count} rows')
    
    cur.close()
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'✗ Connection failed: {e}')
    sys.exit(1)
"@

& python -c $pythonTest 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Neon connection verified" -ForegroundColor Green
} else {
    Write-Host "✗ Neon connection failed—check .env credentials" -ForegroundColor Red
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Setup Complete for Machine #$MachineNumber" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nConfiguration Summary:" -ForegroundColor Yellow
Write-Host "  Local App Path: $LocalAppPath"
Write-Host "  Task Name: $taskPath$taskName"
Write-Host "  Auto-start: Enabled (on login)"
Write-Host "  Database: Neon (ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech)"
Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "  1. Log out and log back in (or run 'Start-ScheduledTask -TaskPath $taskPath -TaskName $taskName')"
Write-Host "  2. App will start automatically on next login"
Write-Host "  3. Check logs in: $LocalAppPath\logs\" -ForegroundColor White
Write-Host "`n"
