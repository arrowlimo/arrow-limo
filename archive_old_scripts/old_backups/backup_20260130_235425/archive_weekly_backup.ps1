param(
    [string]$BackupDir = "L:\limo\backups",
    [string]$ArchiveDir = "L:\limo\backups\weekly_archives",
    [int]$ArchiveRetentionWeeks = 52  # Keep 1 year of weekly archives
)

$ErrorActionPreference = 'Stop'

# Ensure archive directory exists
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $BackupDir ("weekly_archive_" + $ts + ".log")

Write-Output ("[INFO] Starting weekly archive at " + (Get-Date)) | Tee-Object -FilePath $logFile -Append | Out-Null

# Get the most recent backup from the current week (Sunday to Saturday)
$today = Get-Date
$dayOfWeek = [int]$today.DayOfWeek  # 0=Sunday, 6=Saturday
$weekStart = $today.AddDays(-$dayOfWeek).Date  # Start of this week (Sunday)
$weekEnd = $weekStart.AddDays(7)  # Start of next week

$latestBackup = Get-ChildItem -Path $BackupDir -Filter 'almsdata_*.dump' -File | 
    Where-Object { $_.LastWriteTime -ge $weekStart -and $_.LastWriteTime -lt $weekEnd } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latestBackup) {
    Write-Output ("[WARN] No backup found for current week") | Tee-Object -FilePath $logFile -Append | Out-Null
    exit 0
}

# Check if we already have an archive for this week
$archiveWeek = Get-Date $weekStart -Format 'yyyy-MM-dd'
$existingArchive = Get-ChildItem -Path $ArchiveDir -Filter "almsdata_${archiveWeek}_*.dump" -File | Select-Object -First 1

if ($existingArchive) {
    Write-Output ("[INFO] Archive already exists for week $archiveWeek : " + $existingArchive.Name) | Tee-Object -FilePath $logFile -Append | Out-Null
    exit 0
}

# Create archive copy with week identifier
$archiveName = "almsdata_${archiveWeek}_weekly.dump"
$archivePath = Join-Path $ArchiveDir $archiveName

try {
    Copy-Item -Path $latestBackup.FullName -Destination $archivePath -Force
    Write-Output ("[INFO] Archived backup: $archivePath (source: " + $latestBackup.Name + ")") | Tee-Object -FilePath $logFile -Append | Out-Null
    
    # Create zip of the archive
    $zipPath = $archivePath -replace '\.dump$', '.zip'
    Compress-Archive -Path $archivePath -DestinationPath $zipPath -Force
    Write-Output ("[INFO] Created compressed archive: $zipPath") | Tee-Object -FilePath $logFile -Append | Out-Null
    
    # Optionally remove the uncompressed .dump from archive to save space
    Remove-Item -Path $archivePath -Force
    Write-Output ("[INFO] Removed uncompressed archive, kept zip only") | Tee-Object -FilePath $logFile -Append | Out-Null
    
} catch {
    Write-Output ("[ERROR] Failed to create archive: $_") | Tee-Object -FilePath $logFile -Append | Out-Null
    exit 1
}

# Retention cleanup - remove archives older than retention period
$cutoffDate = (Get-Date).AddDays(-($ArchiveRetentionWeeks * 7))
$oldArchives = Get-ChildItem -Path $ArchiveDir -Filter 'almsdata_*_weekly.*' -File | 
    Where-Object { $_.LastWriteTime -lt $cutoffDate }

foreach ($old in $oldArchives) {
    Write-Output ("[INFO] Removing old archive: " + $old.FullName) | Tee-Object -FilePath $logFile -Append | Out-Null
    Remove-Item -Force $old.FullName
}

Write-Output ("[INFO] Weekly archive complete") | Tee-Object -FilePath $logFile -Append | Out-Null
