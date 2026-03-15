# Sync Neon cloud database to local PostgreSQL
$ErrorActionPreference = "Stop"

Write-Host "=== Neon to Local Database Sync ===" -ForegroundColor Cyan

# Credentials
$neonConn = "postgresql://neondb_owner:npg_89MbcFmZwUWo@ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech:5432/neondb?sslmode=require"
$localHost = "localhost"
$localPort = "5432"
$localDb = "almsdata"
$localUser = "postgres"
$localPassword = "ArrowLimousine"

# File paths
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpFile = "L:\limo\neon_dump_$timestamp.sql"
$localBackup = "L:\limo\local_backup_$timestamp.sql"

Write-Host "Step 1: Dumping Neon database..." -ForegroundColor Yellow
$env:PGPASSWORD = "npg_89MbcFmZwUWo"
pg_dump "$neonConn" --file=$dumpFile --no-owner --no-privileges 2>&1 | Out-Null
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

if (Test-Path $dumpFile) {
    $dumpSize = (Get-Item $dumpFile).Length / 1MB
    Write-Host "OK - Dump size: $([math]::Round($dumpSize, 2)) MB" -ForegroundColor Green
} else {
    Write-Host "ERROR - Dump failed" -ForegroundColor Red
    exit 1
}

Write-Host "Step 2: Backing up local database..." -ForegroundColor Yellow
$env:PGPASSWORD = $localPassword
pg_dump -h $localHost -p $localPort -U $localUser -d $localDb --file=$localBackup --no-owner --no-privileges 2>&1 | Out-Null
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
Write-Host "OK - Local backup created" -ForegroundColor Green

Write-Host "Step 3: Recreating local database..." -ForegroundColor Yellow
$env:PGPASSWORD = $localPassword
psql -h $localHost -p $localPort -U $localUser -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$localDb' AND pid <> pg_backend_pid();" 2>&1 | Out-Null
psql -h $localHost -p $localPort -U $localUser -d postgres -c "DROP DATABASE IF EXISTS $localDb;" 2>&1 | Out-Null
psql -h $localHost -p $localPort -U $localUser -d postgres -c "CREATE DATABASE $localDb;" 2>&1 | Out-Null
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
Write-Host "OK - Database recreated" -ForegroundColor Green

Write-Host "Step 4: Restoring Neon dump to local..." -ForegroundColor Yellow
$env:PGPASSWORD = $localPassword
psql -h $localHost -p $localPort -U $localUser -d $localDb --file=$dumpFile 2>&1 | Out-Null
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
Write-Host "OK - Restore complete" -ForegroundColor Green

Write-Host "Step 5: Verifying..." -ForegroundColor Yellow
$env:PGPASSWORD = $localPassword
$tableCount = (psql -h $localHost -p $localPort -U $localUser -d $localDb -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';").Trim()
$receiptCount = (psql -h $localHost -p $localPort -U $localUser -d $localDb -t -c "SELECT COUNT(*) FROM receipts;").Trim()
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

Write-Host "OK - Tables: $tableCount | Receipts: $receiptCount" -ForegroundColor Green
Write-Host ""
Write-Host "=== Sync Complete ===" -ForegroundColor Green
Write-Host "Neon dump: $dumpFile" -ForegroundColor Gray
Write-Host "Local backup: $localBackup" -ForegroundColor Gray
