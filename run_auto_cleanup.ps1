# =================================================================
# Automatic Receipt Widget Cleanup Script (PowerShell)
# Run this to automatically improve the receipt management system
# =================================================================

Write-Host "`n" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AUTOMATIC RECEIPT WIDGET CLEANUP INITIATING" -ForegroundColor Cyan
Write-Host "  Running in background - logs will be saved" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "`n"

$LogDir = "L:\limo\logs"
$LogFile = "$LogDir\receipt_cleanup_auto.log"
$ScriptPath = "L:\limo\scripts\auto_receipt_widget_cleanup.py"

# Create logs directory if it doesn't exist
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Add timestamp to console output
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[$timestamp] Starting automatic cleanup..." -ForegroundColor Yellow
Write-Host "Log file: $LogFile" -ForegroundColor Gray
Write-Host "`n"

# Run the Python automation script
try {
    & python -X utf8 $ScriptPath
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  ✅ AUTOMATION COMPLETE!" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "Check the log for detailed results:" -ForegroundColor Green
        Write-Host "  $LogFile" -ForegroundColor Green
        Write-Host "`n"
    } else {
        Write-Host "`n" -ForegroundColor Red
        Write-Host "============================================================" -ForegroundColor Red
        Write-Host "  ⚠️  AUTOMATION COMPLETED WITH WARNINGS" -ForegroundColor Red
        Write-Host "============================================================" -ForegroundColor Red
        Write-Host "Check the log for details:" -ForegroundColor Red
        Write-Host "  $LogFile" -ForegroundColor Red
        Write-Host "`n"
    }
}
catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    exit 1
}
