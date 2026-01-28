# Arrow Limo Desktop App - Create Email Installer Package
# Creates a ZIP file that can be emailed to all 6 machines

param(
    [string]$OutputPath = "L:\limo\dist\ArrowLimoInstaller.zip"
)

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Arrow Limo - Creating Email Installer Package            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Create temp directory for packaging
$tempDir = "L:\limo\installer_package_temp"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Write-Host "📦 Preparing installer package..." -ForegroundColor Green
Write-Host ""

# Copy .env.neon
Write-Host "  Copying configuration..." -ForegroundColor Yellow
Copy-Item "L:\limo\.env.neon" "$tempDir\.env.neon" -Force
Write-Host "  ✓ .env.neon (Neon database credentials)" -ForegroundColor Green

# Create installation script (Python)
Write-Host "  Creating installation script..." -ForegroundColor Yellow

$installPy = @'
"""
Arrow Limo Desktop App - Installer
Auto-downloads and configures the app from GitHub or network location
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import urllib.request
import zipfile
import tempfile

def log(msg):
    print(msg)

def main():
    print("="  * 70)
    print("  Arrow Limo Desktop App - Installation")
    print("=" * 70)
    print("")
    
    # Get machine number
    machine_num = input("Enter machine number (1-6): ").strip()
    if not machine_num.isdigit() or int(machine_num) not in range(1, 7):
        print("❌ Invalid machine number. Must be 1-6.")
        input("Press Enter to exit...")
        return
    
    machine_num = int(machine_num)
    
    log(f"\n✓ Machine #{machine_num}")
    log("")
    
    # Installation directory
    install_dir = Path("C:/ArrowLimoApp")
    log(f"Installing to: {install_dir}")
    log("")
    
    # Create directory
    log("Step 1: Creating installation directory...")
    install_dir.mkdir(parents=True, exist_ok=True)
    log(f"  ✓ Created: {install_dir}")
    
    # Copy .env.neon
    log("\nStep 2: Setting up configuration...")
    env_source = Path(__file__).parent / ".env.neon"
    if env_source.exists():
        shutil.copy(env_source, install_dir / ".env")
        log("  ✓ Database credentials configured")
    else:
        log("  ⚠ Warning: .env.neon not found")
    
    # Download/clone app code
    log("\nStep 3: Downloading application code...")
    
    # Option 1: Download from network share (if available)
    network_share = r"\\Dispatchmain\ArrowLimoApp"
    if Path(network_share).exists():
        log(f"  Using network share: {network_share}")
        
        # Copy files
        for item in ["main.py", "desktop_app", "requirements.txt"]:
            src = Path(network_share) / item
            if src.exists():
                dst = install_dir / item
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy(src, dst)
                log(f"  ✓ Copied: {item}")
    else:
        log("  Network share not available - creating minimal app...")
        
        # Create a minimal main.py that connects to Neon
        main_py_content = '''
import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from dotenv import load_dotenv
import psycopg2

load_dotenv()

app = QApplication(sys.argv)

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )
    
    QMessageBox.information(None, "Arrow Limo App", 
        "✓ Connected to Neon database successfully!\\n\\n"
        "Full app deployment will be available soon."
    )
    
    conn.close()
except Exception as e:
    QMessageBox.critical(None, "Connection Error", 
        f"Failed to connect to Neon database:\\n{e}"
    )

sys.exit(0)
'''
        
        (install_dir / "main.py").write_text(main_py_content)
        log("  ✓ Created main.py (minimal app)")
    
    # Install Python dependencies
    log("\nStep 4: Installing Python dependencies...")
    
    # Check if Python is available
    try:
        python_exe = sys.executable
        
        # Install required packages
        packages = ["psycopg2-binary", "PyQt6", "python-dotenv", "pywin32"]
        
        for pkg in packages:
            try:
                subprocess.run(
                    [python_exe, "-m", "pip", "install", pkg, "--quiet"],
                    check=True,
                    capture_output=True
                )
                log(f"  ✓ {pkg}")
            except Exception as e:
                log(f"  ⚠ Failed to install {pkg}: {e}")
        
    except Exception as e:
        log(f"  ⚠ Python check failed: {e}")
    
    # Create Task Scheduler auto-start
    log("\nStep 5: Setting up auto-start...")
    
    task_name = f"ArrowLimoApp-Machine{machine_num}"
    python_path = sys.executable
    app_script = str(install_dir / "main.py")
    
    # Delete existing task
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True
    )
    
    # Create new task
    result = subprocess.run([
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'"{python_path}" -X utf8 "{app_script}"',
        "/SC", "ONLOGON",
        "/RL", "LIMITED",
        "/F"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        log(f"  ✓ Auto-start configured: {task_name}")
    else:
        log(f"  ⚠ Task creation failed: {result.stderr}")
    
    # Create desktop shortcut
    log("\nStep 6: Creating desktop shortcut...")
    
    try:
        import win32com.client
        
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "Arrow Limo App.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = python_path
        shortcut.Arguments = f'-X utf8 "{app_script}"'
        shortcut.WorkingDirectory = str(install_dir)
        shortcut.Description = f"Arrow Limo Desktop App - Machine {machine_num}"
        shortcut.Save()
        
        log("  ✓ Desktop shortcut created")
    except Exception as e:
        log(f"  ⚠ Shortcut creation failed: {e}")
    
    # Test Neon connection
    log("\nStep 7: Testing database connection...")
    
    try:
        import psycopg2
        from dotenv import load_dotenv
        
        load_dotenv(install_dir / ".env")
        
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            sslmode=os.getenv("DB_SSLMODE", "require")
        )
        
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM public.charters")
        count = cur.fetchone()[0]
        
        log(f"  ✓ Connected to Neon database")
        log(f"  ✓ Found {count:,} charters")
        
        cur.close()
        conn.close()
    except Exception as e:
        log(f"  ⚠ Connection test failed: {e}")
    
    # Done
    log("")
    log("=" * 70)
    log("  Installation Complete! ✓")
    log("=" * 70)
    log("")
    log(f"Location: {install_dir}")
    log(f"Machine: #{machine_num}")
    log("")
    log("Next steps:")
    log("  1. Log out and log back in (app will auto-start)")
    log("  2. Or use desktop shortcut to start now")
    log("")
    
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
'@

Set-Content -Path "$tempDir\install.py" -Value $installPy -Encoding UTF8
Write-Host "  ✓ install.py" -ForegroundColor Green

# Create batch file launcher
Write-Host "  Creating batch launcher..." -ForegroundColor Yellow

$installBat = @'
@echo off
title Arrow Limo Desktop App - Installer

echo.
echo ====================================================================
echo   Arrow Limo Desktop App - Installation
echo ====================================================================
echo.
echo This will install the Arrow Limo Desktop App on your computer.
echo The app connects to a cloud database (Neon) and will auto-start
echo when you log in.
echo.
echo Press any key to begin installation...
pause >nul

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.12 or newer from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Run the installer
python install.py

pause
'@

Set-Content -Path "$tempDir\INSTALL.bat" -Value $installBat -Encoding ASCII
Write-Host "  ✓ INSTALL.bat" -ForegroundColor Green

# Create README
Write-Host "  Creating instructions..." -ForegroundColor Yellow

$readme = @'
═══════════════════════════════════════════════════════════════════════
  ARROW LIMO DESKTOP APP - INSTALLATION PACKAGE
═══════════════════════════════════════════════════════════════════════

QUICK START (3 Easy Steps)
───────────────────────────

1. Right-click INSTALL.bat → Run as Administrator
2. Enter your machine number when prompted (1-6)
3. Wait for "Installation Complete!" message

That's it! The app will auto-start on your next login.

═══════════════════════════════════════════════════════════════════════
REQUIREMENTS
═══════════════════════════════════════════════════════════════════════

• Windows 10/11
• Python 3.12+ (if not installed, get from: https://www.python.org)
• Internet connection (to reach cloud database)

═══════════════════════════════════════════════════════════════════════
WHAT GETS INSTALLED
═══════════════════════════════════════════════════════════════════════

Location: C:\ArrowLimoApp\

• Application files (main.py, etc.)
• Database configuration (.env)
• Python dependencies (psycopg2, PyQt6, etc.)
• Auto-start task (runs on login)
• Desktop shortcut

═══════════════════════════════════════════════════════════════════════
AFTER INSTALLATION
═══════════════════════════════════════════════════════════════════════

The app will start automatically when you log in.

To start manually:
  • Double-click desktop shortcut: "Arrow Limo App"
  • Or run: C:\ArrowLimoApp\main.py

To check auto-start status:
  • Open Task Scheduler
  • Look for: \ArrowLimoApp-Machine{N}

═══════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════

ISSUE: "Python is not installed"
FIX: Download and install Python 3.12+ from https://www.python.org
     Make sure to check "Add Python to PATH" during installation!

ISSUE: "Connection test failed"
FIX: Check your internet connection and firewall settings.
     The app needs to connect to: ep-curly-dream-*.us-west-2.aws.neon.tech

ISSUE: "App doesn't auto-start on login"
FIX: Run Task Scheduler, find \ArrowLimoApp-Machine{N}, and enable it.

═══════════════════════════════════════════════════════════════════════
SUPPORT
═══════════════════════════════════════════════════════════════════════

If you encounter any issues during installation:

1. Check C:\ArrowLimoApp\logs\ for error logs
2. Verify Python is installed: python --version
3. Contact IT support with error details

═══════════════════════════════════════════════════════════════════════
DATABASE CONNECTION
═══════════════════════════════════════════════════════════════════════

The app connects to a cloud database (Neon) automatically.
Credentials are stored in: C:\ArrowLimoApp\.env

Database details:
  • Host: ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech
  • Database: neondb
  • SSL: Required
  • Data: 1,864+ charters, 2,464+ payments, 2,165+ receipts

═══════════════════════════════════════════════════════════════════════

Installation Package Contents:
  • INSTALL.bat      ← Run this to install
  • install.py       ← Installation script
  • .env.neon        ← Database credentials
  • README.txt       ← This file

═══════════════════════════════════════════════════════════════════════
'@

Set-Content -Path "$tempDir\README.txt" -Value $readme -Encoding UTF8
Write-Host "  ✓ README.txt" -ForegroundColor Green

# Create the ZIP file
Write-Host ""
Write-Host "📦 Creating ZIP package..." -ForegroundColor Green

$distDir = "L:\limo\dist"
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
}

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

Compress-Archive -Path "$tempDir\*" -DestinationPath $OutputPath -CompressionLevel Optimal

# Clean up temp directory
Remove-Item $tempDir -Recurse -Force

# Show results
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  EMAIL INSTALLER PACKAGE CREATED ✓                         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$zipFile = Get-Item $OutputPath
$sizeMB = [math]::Round($zipFile.Length / 1MB, 2)

Write-Host "📦 Package Details:" -ForegroundColor Green
Write-Host "  File: $OutputPath" -ForegroundColor White
Write-Host "  Size: $sizeMB MB" -ForegroundColor White
Write-Host ""

Write-Host "✉️  How to Distribute:" -ForegroundColor Yellow
Write-Host "  1. Email this ZIP file to all 6 machines" -ForegroundColor White
Write-Host "  2. Users extract the ZIP" -ForegroundColor White
Write-Host "  3. Users run INSTALL.bat as Administrator" -ForegroundColor White
Write-Host "  4. Users enter their machine number (1-6)" -ForegroundColor White
Write-Host ""

Write-Host "📋 Package Contents:" -ForegroundColor Green
Write-Host "  • INSTALL.bat   (Run this to install)" -ForegroundColor White
Write-Host "  • install.py    (Installation script)" -ForegroundColor White
Write-Host "  • .env.neon     (Neon database credentials)" -ForegroundColor White
Write-Host "  • README.txt    (User instructions)" -ForegroundColor White
Write-Host ""

Write-Host "✅ Ready to email to all 6 machines!" -ForegroundColor Green
Write-Host ""
