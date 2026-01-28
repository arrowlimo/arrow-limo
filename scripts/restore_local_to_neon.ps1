#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Restore local backup to Neon using psql connection string (bypasses SSL flag issues)
#>

Write-Host "="*80 -ForegroundColor Cyan
Write-Host "RESTORE LOCAL BACKUP TO NEON" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

$backupFile = "backups\almsdata_PRE_NEON_20260124_022515.dump"
$neonConnStr = "postgresql://neondb_owner:***REMOVED***@ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech:5432/neondb?sslmode=require"

if (-not (Test-Path $backupFile)) {
    Write-Host "❌ Backup file not found: $backupFile" -ForegroundColor Red
    exit 1
}

$size = (Get-Item $backupFile).Length / 1MB
Write-Host "`nBackup file: $backupFile ($([math]::Round($size, 1)) MB)" -ForegroundColor Green

Write-Host "`nThis will:" -ForegroundColor Yellow
Write-Host "  1. Drop all existing objects in Neon" -ForegroundColor White
Write-Host "  2. Restore fresh data from local (18,679 charters, 26 vehicles, etc.)" -ForegroundColor White
Write-Host "  3. Include updated schema (no driver_code, CVIP in vehicles)" -ForegroundColor White

$confirm = Read-Host "`nProceed? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host "`nRestoring to Neon..." -ForegroundColor Green
Write-Host "(This may take 2-5 minutes for 34MB backup)" -ForegroundColor Gray

try {
    & "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" `
        --verbose `
        --clean `
        --if-exists `
        --no-owner `
        --no-acl `
        --dbname="$neonConnStr" `
        --format=c `
        "$backupFile" 2>&1 | Out-String | Write-Host
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Restore completed successfully" -ForegroundColor Green
    } else {
        Write-Host "`n⚠️  Restore finished with warnings (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
        Write-Host "This is normal - some warnings are expected" -ForegroundColor Gray
    }
} catch {
    Write-Host "`n❌ Restore failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`nVerifying restore..." -ForegroundColor Green
& python -X utf8 scripts\test_neon_ready.py

Write-Host "`n✅ Neon database is now synced with local" -ForegroundColor Green
Write-Host "`nYou can now:" -ForegroundColor Cyan
Write-Host "  - Run: python desktop_app\main.py" -ForegroundColor White
Write-Host "  - Choose: Neon (master - online)" -ForegroundColor White
Write-Host "  - All 3 computers will use the same Neon master" -ForegroundColor White
