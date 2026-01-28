# Reset PostgreSQL password - RUN AS ADMINISTRATOR
# This temporarily enables trust auth, resets password, then re-enables security

Write-Host "Resetting PostgreSQL password..." -ForegroundColor Yellow
Write-Host ""

# Stop PostgreSQL
Write-Host "1. Stopping PostgreSQL service..."
Stop-Service postgresql-x64-17 -Force
Start-Sleep -Seconds 2

# Backup pg_hba.conf
Write-Host "2. Backing up pg_hba.conf..."
Copy-Item "C:\Program Files\PostgreSQL\17\data\pg_hba.conf" "C:\Program Files\PostgreSQL\17\data\pg_hba.conf.backup"

# Enable trust authentication temporarily (both IPv4 and IPv6)
Write-Host "3. Enabling trust authentication..."
(Get-Content "C:\Program Files\PostgreSQL\17\data\pg_hba.conf") `
    -replace 'host\s+all\s+all\s+127\.0\.0\.1/32\s+scram-sha-256', 'host    all             all             127.0.0.1/32            trust' `
    -replace 'host\s+all\s+all\s+::1/128\s+scram-sha-256', 'host    all             all             ::1/128                 trust' `
    | Set-Content "C:\Program Files\PostgreSQL\17\data\pg_hba.conf"

# Start PostgreSQL
Write-Host "4. Starting PostgreSQL service..."
Start-Service postgresql-x64-17
Start-Sleep -Seconds 5

# Reset password
Write-Host "5. Resetting postgres password to '***REMOVED***'..."
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD '***REMOVED***';"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Password reset successful!" -ForegroundColor Green
} else {
    Write-Host "   Password reset failed!" -ForegroundColor Red
    exit 1
}

# Restore secure authentication
Write-Host "6. Restoring secure authentication..."
Stop-Service postgresql-x64-17 -Force
Start-Sleep -Seconds 2

Copy-Item "C:\Program Files\PostgreSQL\17\data\pg_hba.conf.backup" "C:\Program Files\PostgreSQL\17\data\pg_hba.conf" -Force

Start-Service postgresql-x64-17
Start-Sleep -Seconds 5

# Test new password
Write-Host "7. Testing new password..."
$env:PGPASSWORD = '***REMOVED***'
$testResult = & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres -c "SELECT version();" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS! PostgreSQL password is now '***REMOVED***'" -ForegroundColor Green
    Write-Host ""
    
    # Create almsdata database
    Write-Host "8. Creating almsdata database..."
    & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres -c "CREATE DATABASE almsdata;" 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   almsdata database created!" -ForegroundColor Green
    } else {
        Write-Host "   almsdata database already exists or error occurred" -ForegroundColor Yellow
    }
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "FAILED! Could not connect with new password" -ForegroundColor Red
    Write-Host ""
    exit 1
}
