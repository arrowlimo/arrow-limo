# ============================================================================
# Update .env File with PostgreSQL Password
# ============================================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Update .env File Password" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$envFile = "l:\limo\.env"
$envLocal = "l:\limo\.env.local"

Write-Host "This script will update your .env file with the correct PostgreSQL password." -ForegroundColor Yellow
Write-Host ""

# Prompt for password
$password = Read-Host "Enter the PostgreSQL 'postgres' user password" -AsSecureString
$passwordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

if ([string]::IsNullOrEmpty($passwordPlain)) {
    Write-Host "ERROR: Password cannot be empty" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "Updating .env files..." -ForegroundColor Yellow

# Update .env file
if (Test-Path $envFile) {
    $content = Get-Content $envFile
    $newContent = @()
    $updated = $false
    
    foreach ($line in $content) {
        if ($line -match '^DB_PASSWORD=') {
            $newContent += "DB_PASSWORD=$passwordPlain"
            $updated = $true
            Write-Host "✓ Updated $envFile" -ForegroundColor Green
        } else {
            $newContent += $line
        }
    }
    
    if (-not $updated) {
        $newContent += "DB_PASSWORD=$passwordPlain"
        Write-Host "✓ Added DB_PASSWORD to $envFile" -ForegroundColor Green
    }
    
    $newContent | Set-Content -Path $envFile -Encoding UTF8
} else {
    Write-Host "! Warning: $envFile not found" -ForegroundColor Yellow
}

# Update .env.local file
if (Test-Path $envLocal) {
    $content = Get-Content $envLocal
    $newContent = @()
    $updated = $false
    
    foreach ($line in $content) {
        if ($line -match '^DB_PASSWORD=') {
            $newContent += "DB_PASSWORD=$passwordPlain"
            $updated = $true
            Write-Host "✓ Updated $envLocal" -ForegroundColor Green
        } else {
            $newContent += $line
        }
    }
    
    if (-not $updated) {
        $newContent += "DB_PASSWORD=$passwordPlain"
        Write-Host "✓ Added DB_PASSWORD to $envLocal" -ForegroundColor Green
    }
    
    $newContent | Set-Content -Path $envLocal -Encoding UTF8
} else {
    Write-Host "! Warning: $envLocal not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Testing connection..." -ForegroundColor Yellow

# Test the connection
try {
    $env:DB_PASSWORD = $passwordPlain
    python l:\limo\diagnose_connection.py
} catch {
    Write-Host "! Could not run diagnostic" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Update Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run the application with:" -ForegroundColor Green
Write-Host "  l:\limo\START_HYBRID.bat" -ForegroundColor Cyan
Write-Host ""

pause
