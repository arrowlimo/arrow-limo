# Neon Clone Script
# Usage:
#   pwsh -File scripts\neon_clone.ps1 -NeonHost your-project.neon.tech -NeonUser neondb_owner -NeonDb almsdata -DumpPath L:\limo\almsdata.dump
# Notes:
# - Requires PostgreSQL client tools (pg_dump, pg_restore) in PATH
# - Uses SSL-required connections for Neon

param(
    [Parameter(Mandatory=$true)] [string]$NeonHost,
    [Parameter(Mandatory=$true)] [string]$NeonUser,
    [Parameter(Mandatory=$true)] [string]$NeonDb,
    [Parameter(Mandatory=$false)] [string]$DumpPath = "L:\\limo\\almsdata.dump"
)

Write-Host "== Arrow Limo: Neon Clone ==" -ForegroundColor Cyan
Write-Host "Neon Host: $NeonHost" -ForegroundColor Cyan
Write-Host "Neon User: $NeonUser" -ForegroundColor Cyan
Write-Host "Neon DB:   $NeonDb" -ForegroundColor Cyan
Write-Host "Dump Path: $DumpPath" -ForegroundColor Cyan

# Verify pg_dump/pg_restore
$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
$pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
if (-not $pgDump -or -not $pgRestore) {
  Write-Host "ERROR: PostgreSQL client tools not found (pg_dump/pg_restore)." -ForegroundColor Red
  Write-Host "Install PostgreSQL or add its bin directory to PATH (e.g., C:\\Program Files\\PostgreSQL\\16\\bin)." -ForegroundColor Yellow
  exit 1
}

# Dump local database if dump file does not exist
if (-not (Test-Path $DumpPath)) {
  Write-Host "Creating local dump..." -ForegroundColor Yellow
  $dumpCmd = "pg_dump -h localhost -U postgres -d almsdata -F c -f \"$DumpPath\""
  Write-Host $dumpCmd -ForegroundColor DarkGray
  & pg_dump -h localhost -U postgres -d almsdata -F c -f $DumpPath
  if ($LASTEXITCODE -ne 0) { Write-Host "Dump failed." -ForegroundColor Red; exit 1 }
  Write-Host "✓ Dump created: $DumpPath" -ForegroundColor Green
}

# Restore to Neon
Write-Host "Restoring to Neon (SSL required)..." -ForegroundColor Yellow
# Note: pg_restore uses libpq env vars or .pgpass. Prompt for password for clarity.
$NeonPassword = Read-Host -AsSecureString "Enter Neon password for user '$NeonUser'"
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($NeonPassword)
$PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Set env for libpq (optional); many pg clients accept these
$env:PGPASSWORD = $PlainPassword

$restoreCmd = "pg_restore -h $NeonHost -U $NeonUser -d $NeonDb --clean --if-exists \"$DumpPath\""
Write-Host $restoreCmd -ForegroundColor DarkGray
& pg_restore -h $NeonHost -U $NeonUser -d $NeonDb --clean --if-exists $DumpPath
if ($LASTEXITCODE -ne 0) { Write-Host "Restore failed." -ForegroundColor Red; exit 1 }
Write-Host "✓ Restore complete." -ForegroundColor Green

# Clear sensitive vars
$env:PGPASSWORD = $null
Write-Host "All done." -ForegroundColor Green
