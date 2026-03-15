# Import Beverage Tables to Neon
# Usage: .\upload_to_neon.ps1 -Password "your_neon_password"

param(
    [Parameter(Mandatory=$true)]
    [string]$Password
)

Write-Host "=" * 80
Write-Host "UPLOADING BEVERAGE TABLES TO NEON CLOUD DATABASE"
Write-Host "=" * 80
Write-Host ""

$NEON_HOST = "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"
$NEON_DB = "neondb"  
$NEON_USER = "neondb_owner"
$IMPORT_DIR = "L:\limo\neon_exports"

# Set password environment variable
$env:PGPASSWORD = $Password

Write-Host "Target: $NEON_HOST"
Write-Host "Database: $NEON_DB"
Write-Host "User: $NEON_USER"
Write-Host ""

# Get SQL files
$sqlFiles = Get-ChildItem -Path $IMPORT_DIR -Filter *.sql | Sort-Object Name

if ($sqlFiles.Count -eq 0) {
    Write-Host "❌ No SQL files found in $IMPORT_DIR"
    exit 1
}

Write-Host "Found $($sqlFiles.Count) tables to import"
Write-Host ""

$successCount = 0
$errorCount = 0

foreach ($file in $sqlFiles) {
    $tableName = $file.BaseName
    Write-Host "Importing $tableName..." -NoNewline
    
    $output = psql -h $NEON_HOST -U $NEON_USER -d $NEON_DB -f $file.FullName --set sslmode=require 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host " ❌" -ForegroundColor Red
        Write-Host "  Error: $output" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host ""
Write-Host "=" * 80
Write-Host "UPLOAD COMPLETE"
Write-Host "=" * 80
Write-Host "Successful: $successCount" -ForegroundColor Green
Write-Host "Errors: $errorCount" -ForegroundColor Red
Write-Host ""

if ($successCount -gt 0) {
    Write-Host "Verifying tables exist in Neon..."
    psql -h $NEON_HOST -U $NEON_USER -d $NEON_DB --set sslmode=require -c "\dt beverage*" 2>&1
}

# Clean up password
$env:PGPASSWORD = $null
