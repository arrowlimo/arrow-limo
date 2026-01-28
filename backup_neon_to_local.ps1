# Backup Neon database to local file
# Run this weekly/daily to maintain local backup

param(
    [string]$BackupDir = "L:\limo\neon_backups"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "$BackupDir\neon_backup_$timestamp.dump"

# Ensure backup directory exists
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

# Neon connection details (from your .env)
$env:PGPASSWORD = '***REMOVED***'
$env:PGSSLMODE = 'require'

Write-Host "⏳ Starting backup from Neon to $backupFile..."

& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" `
    -h ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech `
    -U neondb_owner `
    -d neondb `
    -F c `
    -f $backupFile

if ($LASTEXITCODE -eq 0) {
    $sizeMB = [math]::Round((Get-Item $backupFile).Length / 1MB, 2)
    Write-Host "✅ Backup complete: $sizeMB MB"
    Write-Host "📁 Location: $backupFile"
    
    # Clean up old backups (keep last 7 days)
    Get-ChildItem $BackupDir -Filter "neon_backup_*.dump" | 
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | 
        ForEach-Object {
            Write-Host "🗑️ Removing old backup: $($_.Name)"
            Remove-Item $_.FullName
        }
} else {
    Write-Host "❌ Backup failed with exit code $LASTEXITCODE"
    exit 1
}
