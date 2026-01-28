# Arrow Limousine PostgreSQL Auto-Login Profile
# This file automatically loads when PowerShell starts

# Set PostgreSQL environment variables for auto-login
$env:PGPASSWORD = "***REMOVED***"
$env:PGUSER = "postgres"
$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGDATABASE = "almsdata"

# Display confirmation
Write-Host "✅ PostgreSQL auto-login configured" -ForegroundColor Green
Write-Host "   Database: $($env:PGDATABASE) | User: $($env:PGUSER) | Host: $($env:PGHOST)" -ForegroundColor Cyan

# Quick test connection function
function Test-DBConnection {
    try {
        $result = psql -c "SELECT 'Connected!' as status;" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Database connection OK" -ForegroundColor Green
        } else {
            Write-Host "❌ Database connection failed" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ Error: $_" -ForegroundColor Red
    }
}

# Alias for quick database access
Set-Alias -Name limo-db -Value Test-DBConnection
