# =========================================================
# CREATE DESKTOP SHORTCUT FOR DISPATCH1
# Run this script to create a desktop shortcut
# =========================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  DISPATCH1 Desktop Shortcut Creator" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# Get desktop path
$DesktopPath = [Environment]::GetFolderPath("Desktop")
Write-Host "[1/3] Desktop location: $DesktopPath" -ForegroundColor Green

# Define shortcut details
$ShortcutPath = Join-Path $DesktopPath "Arrow Limo Dispatch.lnk"
$TargetPath = "Y:\ArrowLimo\app\START_DISPATCH.bat"
$IconPath = "Y:\ArrowLimo\app\desktop_app\main.py"  # Uses Python icon by default

# Verify target exists
Write-Host ""
Write-Host "[2/3] Checking installation..." -ForegroundColor Yellow

if (-not (Test-Path "Y:\ArrowLimo\app\START_DISPATCH.bat")) {
    Write-Host ""
    Write-Host "ERROR: Application not installed at Y:\ArrowLimo\app" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the installer first:" -ForegroundColor Yellow
    Write-Host "  L:\limo\DEPLOYMENT_PACKAGE\INSTALL_DISPATCH1_Y_DRIVE.bat" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "      [OK] Application found" -ForegroundColor Green

# Create shortcut
Write-Host ""
Write-Host "[3/3] Creating desktop shortcut..." -ForegroundColor Yellow

try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = "Y:\ArrowLimo\app"
    $Shortcut.Description = "Arrow Limousine Dispatch - DISPATCH1 Workstation"
    $Shortcut.WindowStyle = 1  # Normal window
    
    # Set icon if Python is installed (uses Python's icon)
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($PythonPath) {
        $Shortcut.IconLocation = "$PythonPath,0"
    }
    
    $Shortcut.Save()
    
    Write-Host "      [OK] Shortcut created successfully" -ForegroundColor Green
    Write-Host ""
    Write-Host "=======================================================" -ForegroundColor Cyan
    Write-Host "  SUCCESS!" -ForegroundColor Green
    Write-Host "=======================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Desktop shortcut created:" -ForegroundColor White
    Write-Host "  $ShortcutPath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Double-click the shortcut to launch the application" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create shortcut" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "You can manually create a shortcut:" -ForegroundColor Yellow
    Write-Host "  1. Right-click Desktop > New > Shortcut" -ForegroundColor White
    Write-Host "  2. Location: Y:\ArrowLimo\app\START_DISPATCH.bat" -ForegroundColor White
    Write-Host "  3. Name: Arrow Limo Dispatch" -ForegroundColor White
    Write-Host ""
}

Read-Host "Press Enter to exit"
