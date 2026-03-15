# ============================================================================
# Test PostgreSQL Network Connection from DISPATCH1
# Run on DISPATCH1 to verify database connectivity
# ============================================================================

param(
    [string]$ServerIP = "",
    [string]$Password = ""
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Network Connection Test" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Get server IP if not provided
if (-not $ServerIP) {
    $ServerIP = Read-Host "Enter DISPATCHMAIN IP address (e.g., 192.168.1.100)"
}

# Get password if not provided
if (-not $Password) {
    $securePassword = Read-Host "Enter postgres password" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

# Test 1: Ping server
Write-Host "1. Testing network connectivity to $ServerIP..." -ForegroundColor Yellow
$pingResult = Test-Connection -ComputerName $ServerIP -Count 2 -Quiet
if ($pingResult) {
    Write-Host "   ✓ Network connection successful" -ForegroundColor Green
} else {
    Write-Host "   ✗ Cannot ping server - check network connection" -ForegroundColor Red
    exit 1
}

# Test 2: Test port 5432
Write-Host "`n2. Testing PostgreSQL port 5432..." -ForegroundColor Yellow
$portTest = Test-NetConnection -ComputerName $ServerIP -Port 5432 -WarningAction SilentlyContinue
if ($portTest.TcpTestSucceeded) {
    Write-Host "   ✓ Port 5432 is open" -ForegroundColor Green
} else {
    Write-Host "   ✗ Port 5432 is blocked - check firewall on DISPATCHMAIN" -ForegroundColor Red
    exit 1
}

# Test 3: Try Python psycopg2 connection
Write-Host "`n3. Testing database connection with Python..." -ForegroundColor Yellow

$testScript = @"
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host='$ServerIP',
        port=5432,
        dbname='almsdata',
        user='postgres',
        password='$Password',
        connect_timeout=5
    )
    cur = conn.cursor()
    
    # Test query
    cur.execute('SELECT COUNT(*) FROM charters')
    charter_count = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM clients')
    client_count = cur.fetchone()[0]
    
    cur.execute('SELECT version()')
    pg_version = cur.fetchone()[0]
    
    print(f'SUCCESS|{charter_count}|{client_count}|{pg_version}')
    
    cur.close()
    conn.close()
    sys.exit(0)
    
except Exception as e:
    print(f'ERROR|{str(e)}')
    sys.exit(1)
"@

$tempScript = "$env:TEMP\test_pg_connection.py"
$testScript | Out-File -FilePath $tempScript -Encoding UTF8

# Find Python
$pythonPath = $null
$pythonLocations = @(
    "C:\Python312\python.exe",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)

foreach ($loc in $pythonLocations) {
    if (Test-Path $loc) {
        $pythonPath = $loc
        break
    }
}

if (-not $pythonPath) {
    # Try to find in PATH
    $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $pythonPath) {
    Write-Host "   ✗ Python not found - cannot test database connection" -ForegroundColor Red
    Write-Host "   Please install Python and psycopg2" -ForegroundColor Yellow
    exit 1
}

try {
    $result = & $pythonPath $tempScript
    Remove-Item $tempScript -Force
    
    if ($result -match '^SUCCESS\|(\d+)\|(\d+)\|(.+)$') {
        $charters = $matches[1]
        $clients = $matches[2]
        $version = $matches[3]
        
        Write-Host "   ✓ Database connection successful!" -ForegroundColor Green
        Write-Host "   Database: almsdata" -ForegroundColor Cyan
        Write-Host "   Charters: $charters" -ForegroundColor Cyan
        Write-Host "   Clients: $clients" -ForegroundColor Cyan
        Write-Host "   Version: $version" -ForegroundColor Cyan
    } elseif ($result -match '^ERROR\|(.+)$') {
        $error = $matches[1]
        Write-Host "   ✗ Database connection failed" -ForegroundColor Red
        Write-Host "   Error: $error" -ForegroundColor Yellow
        
        if ($error -match "password authentication failed") {
            Write-Host "`n   → Check postgres password is correct" -ForegroundColor Yellow
        } elseif ($error -match "no pg_hba.conf entry") {
            Write-Host "`n   → DISPATCHMAIN needs to allow your IP in pg_hba.conf" -ForegroundColor Yellow
        } elseif ($error -match "timeout") {
            Write-Host "`n   → Check firewall allows port 5432" -ForegroundColor Yellow
        }
        exit 1
    } else {
        Write-Host "   ✗ Unexpected result: $result" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   ✗ Error running test: $_" -ForegroundColor Red
    Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "ALL TESTS PASSED" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Cyan

Write-Host "You can now update DISPATCH1 .env file:" -ForegroundColor White
Write-Host "DB_HOST=$ServerIP" -ForegroundColor Cyan
Write-Host "DB_NAME=almsdata" -ForegroundColor Cyan
Write-Host "DB_USER=postgres" -ForegroundColor Cyan
Write-Host "DB_PASSWORD=<your_password>" -ForegroundColor Cyan
Write-Host "DB_SSLMODE=prefer`n" -ForegroundColor Cyan
