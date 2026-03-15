# Quick Manual DISPATCH1 Installer (No Unicode issues)
# Run as Administrator

param(
    [string]$DispatchMainIP = "192.168.1.106",
    [string]$PostgresPassword = ""
)

if (-not $PostgresPassword) {
    $PostgresPassword = Read-Host "Enter PostgreSQL password from DISPATCHMAIN" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($PostgresPassword)
    $PostgresPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

Write-Host "STEP 1: Creating Y: drive..." -ForegroundColor Cyan
$vhdPath = "C:\ArrowLimo_Y_Drive.vhdx"
if (-not (Test-Path "Y:\")) {
    New-VHD -Path $vhdPath -SizeBytes 10GB -Dynamic | Out-Null
    $vhd = Mount-VHD -Path $vhdPath -Passthru
    $disk = Initialize-Disk -Number $vhd.Number -PartitionStyle GPT -PassThru
    $partition = New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter Y
    Format-Volume -DriveLetter Y -FileSystem NTFS -NewFileSystemLabel "ArrowLimo" -Confirm:$false | Out-Null
    Get-Disk -Number $vhd.Number | Set-Disk -IsOffline $false
    Write-Host "  Y: drive created!" -ForegroundColor Green
} else {
    Write-Host "  Y: drive already exists" -ForegroundColor Yellow
}

Write-Host "STEP 2: Mapping network drives..." -ForegroundColor Cyan
net use L: /delete 2>$null
net use Z: /delete 2>$null
net use L: \\DISPATCHMAIN\limo /persistent:yes
net use Z: \\DISPATCHMAIN\limo_files /persistent:yes
Write-Host "  L: and Z: drives mapped!" -ForegroundColor Green

Write-Host "STEP 3: Installing application..." -ForegroundColor Cyan
if (-not (Test-Path "Y:\ArrowLimo")) { New-Item -ItemType Directory -Path "Y:\ArrowLimo" -Force | Out-Null }
robocopy L:\limo\desktop_app Y:\ArrowLimo\desktop_app /E /NFL /NDL /NJH /NJS /nc /ns
Copy-Item L:\limo\requirements.txt Y:\ArrowLimo\ -Force 2>$null
Write-Host "  Application files copied!" -ForegroundColor Green

Write-Host "STEP 4: Creating configuration..." -ForegroundColor Cyan
$envContent = @"
DB_HOST=$DispatchMainIP
DB_NAME=almsdata
DB_USER=postgres
DB_PASSWORD=$PostgresPassword
DB_PORT=5432
WORKSTATION_ID=DISPATCH1
RECEIPT_WIDGET_WRITE_ENABLED=true
SHARED_FILES_PATH=Z:\\limo_files
"@
$envContent | Out-File "Y:\ArrowLimo\.env" -Encoding UTF8 -Force
Write-Host "  Configuration created!" -ForegroundColor Green

Write-Host "STEP 5: Installing Python packages..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
python -m pip install -r Y:\ArrowLimo\requirements.txt --quiet
Write-Host "  Python packages installed!" -ForegroundColor Green

Write-Host "STEP 6: Creating launcher..." -ForegroundColor Cyan
$launcherContent = @'
@echo off
cd /d Y:\ArrowLimo\desktop_app
python launcher.py
if errorlevel 1 pause
'@
$launcherContent | Out-File "Y:\ArrowLimo\START.bat" -Encoding ASCII -Force
Write-Host "  Launcher created!" -ForegroundColor Green

Write-Host "STEP 7: Creating desktop shortcut..." -ForegroundColor Cyan
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Arrow Limo DISPATCH1.lnk")
$Shortcut.TargetPath = "Y:\ArrowLimo\START.bat"
$Shortcut.WorkingDirectory = "Y:\ArrowLimo\desktop_app"
$Shortcut.Save()
Write-Host "  Desktop shortcut created!" -ForegroundColor Green

Write-Host ""
Write-Host "COMPLETE! Launch from desktop shortcut." -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to test database connection..."
pause

Write-Host "Testing database connection..." -ForegroundColor Cyan
$testPython = @"
import psycopg2
conn = psycopg2.connect(host='$DispatchMainIP', database='almsdata', user='postgres', password='$PostgresPassword', port=5432)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM information_schema.tables')
print('SUCCESS - Connected!')
conn.close()
"@
$testPython | Out-File "$env:TEMP\test.py" -Encoding UTF8 -Force
python "$env:TEMP\test.py"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Database connection successful!" -ForegroundColor Green
} else {
    Write-Host "Database connection failed - check PostgreSQL network config on DISPATCHMAIN" -ForegroundColor Yellow
}
