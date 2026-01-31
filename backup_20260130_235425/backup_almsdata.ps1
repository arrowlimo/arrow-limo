param(
    [string]$HostName = "localhost",
    [int]$Port = 5432,
    [string]$Database = "almsdata",
    [string]$User = "postgres",
    [string]$PgDumpPath = $null,
    [string]$OutDir = "L:\limo\backups",
    [int]$RetentionDays = 14,
    [string]$RootBackupPath = $null,  # e.g., "\\server\share\backups" or "C:\RootBackups"
    [switch]$ZipBackup = $false
)

$ErrorActionPreference = 'Stop'

# Resolve pg_dump
if (-not $PgDumpPath) {
    $pg = (Get-Command pg_dump -ErrorAction SilentlyContinue).Source
    if (-not $pg) {
        $pg = Get-ChildItem -Path 'C:\Program Files\PostgreSQL','C:\Program Files (x86)\PostgreSQL' -Filter pg_dump.exe -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $pg) { throw "pg_dump not found. Set PATH or pass -PgDumpPath." }
    $PgDumpPath = $pg
}

# Ensure output directory
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$outFile = Join-Path $OutDir ("almsdata_" + $ts + ".dump")
$logFile = Join-Path $OutDir ("almsdata_backup_" + $ts + ".log")

Write-Output ("[INFO] Starting backup at " + (Get-Date)) | Tee-Object -FilePath $logFile -Append | Out-Null

# Run pg_dump; pick up password from PGPASSWORD env if set
$env:PGPASSWORD = $env:PGPASSWORD # no-op, ensures variable exists if already set
& "$PgDumpPath" --host=$HostName --port=$Port --username=$User --format=custom --file=$outFile $Database 2>&1 |
    Tee-Object -FilePath $logFile -Append

if ($LASTEXITCODE -ne 0) {
    Write-Output ("[ERROR] Backup failed with exit code $LASTEXITCODE") | Tee-Object -FilePath $logFile -Append | Out-Null
    exit $LASTEXITCODE
}

# Retention cleanup
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $OutDir -Filter 'almsdata_*.dump' -File | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
    Write-Output ("[INFO] Removing old backup: " + $_.FullName) | Tee-Object -FilePath $logFile -Append | Out-Null
    Remove-Item -Force $_.FullName
}

Write-Output ("[INFO] Backup complete: $outFile") | Tee-Object -FilePath $logFile -Append | Out-Null

# Copy to Root backup location if specified
if ($RootBackupPath) {
    try {
        New-Item -ItemType Directory -Force -Path $RootBackupPath | Out-Null
        $rootFile = Join-Path $RootBackupPath (Split-Path $outFile -Leaf)
        
        if ($ZipBackup) {
            $zipFile = $outFile -replace '\.dump$', '.zip'
            Write-Output ("[INFO] Creating zip: $zipFile") | Tee-Object -FilePath $logFile -Append | Out-Null
            Compress-Archive -Path $outFile -DestinationPath $zipFile -Force
            $rootZip = Join-Path $RootBackupPath (Split-Path $zipFile -Leaf)
            Copy-Item -Path $zipFile -Destination $rootZip -Force
            Write-Output ("[INFO] Copied zip to Root: $rootZip") | Tee-Object -FilePath $logFile -Append | Out-Null
        } else {
            Copy-Item -Path $outFile -Destination $rootFile -Force
            Write-Output ("[INFO] Copied to Root: $rootFile") | Tee-Object -FilePath $logFile -Append | Out-Null
        }
        
        # Retention cleanup on Root location
        Get-ChildItem -Path $RootBackupPath -Filter 'almsdata_*.*' -File | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
            Write-Output ("[INFO] Removing old Root backup: " + $_.FullName) | Tee-Object -FilePath $logFile -Append | Out-Null
            Remove-Item -Force $_.FullName
        }
    } catch {
        Write-Output ("[ERROR] Failed to copy to Root: $_") | Tee-Object -FilePath $logFile -Append | Out-Null
    }
}

