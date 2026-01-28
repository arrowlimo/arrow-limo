"""
Arrow Limo Desktop App - Standalone Installer
Downloads app from GitHub/local and sets up auto-start
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def log(msg):
    print(msg)

def run_command(cmd, shell=False):
    """Run command and return success status"""
    try:
        subprocess.run(cmd, shell=shell, check=True, capture_output=True)
        return True
    except:
        return False

def main():
    print("=" * 70)
    print("  ARROW LIMO DESKTOP APP - INSTALLATION")
    print("=" * 70)
    print("")
    
    # Get machine number
    machine_num = input("Enter machine number (1-6): ").strip()
    if not machine_num.isdigit() or int(machine_num) not in range(1, 7):
        print("❌ Invalid machine number. Must be 1-6.")
        input("Press Enter to exit...")
        return 1
    
    machine_num = int(machine_num)
    
    log(f"\n✓ Installing for Machine #{machine_num}")
    log("")
    
    # Installation directory
    install_dir = Path("C:/ArrowLimoApp")
    log(f"Installation directory: {install_dir}")
    log("")
    
    # Step 1: Create directory
    log("Step 1: Creating installation directory...")
    install_dir.mkdir(parents=True, exist_ok=True)
    log(f"  ✓ Created: {install_dir}")
    
    # Step 2: Copy .env
    log("\nStep 2: Configuring database connection...")
    env_source = Path(__file__).parent / ".env.neon"
    if env_source.exists():
        shutil.copy(env_source, install_dir / ".env")
        log("  ✓ Database credentials configured")
    else:
        log("  ⚠ Warning: .env.neon not found")
    
    # Step 3: Try to get app from network share
    log("\nStep 3: Fetching application code...")
    
    network_share = Path(r"\\Dispatchmain\ArrowLimoApp")
    
    if network_share.exists():
        log(f"  Using network share: {network_share}")
        
        # Copy files
        for item in ["main.py", "desktop_app", "requirements.txt"]:
            src = network_share / item
            if not src.exists():
                continue
                
            dst = install_dir / item
            
            try:
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy(src, dst)
                log(f"  ✓ Copied: {item}")
            except Exception as e:
                log(f"  ⚠ Failed to copy {item}: {e}")
    else:
        log("  Network share not available - creating minimal app...")
        
        # Create minimal main.py
        main_py = '''import sys
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
    
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM public.charters")
    count = cur.fetchone()[0]
    
    QMessageBox.information(None, "Arrow Limo App", 
        f"✓ Connected to Neon database!\\n\\n"
        f"Found {count:,} charters in database.\\n\\n"
        f"Full app features coming soon."
    )
    
    conn.close()
except Exception as e:
    QMessageBox.critical(None, "Connection Error", 
        f"Failed to connect to database:\\n{e}"
    )

sys.exit(0)
'''
        
        (install_dir / "main.py").write_text(main_py)
        log("  ✓ Created main.py")
    
    # Step 4: Install Python dependencies
    log("\nStep 4: Installing Python dependencies...")
    
    packages = ["psycopg2-binary", "PyQt6", "python-dotenv", "pywin32"]
    
    for pkg in packages:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                check=True,
                capture_output=True,
                timeout=60
            )
            log(f"  ✓ {pkg}")
        except Exception as e:
            log(f"  ⚠ Failed to install {pkg}")
    
    # Step 5: Create auto-start task
    log("\nStep 5: Setting up auto-start...")
    
    task_name = f"ArrowLimoApp-Machine{machine_num}"
    python_exe = sys.executable
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
        "/TR", f'"{python_exe}" -X utf8 "{app_script}"',
        "/SC", "ONLOGON",
        "/RL", "LIMITED",
        "/F"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        log(f"  ✓ Auto-start task: {task_name}")
    else:
        log(f"  ⚠ Task creation warning: {result.stderr.strip()}")
    
    # Step 6: Create desktop shortcut
    log("\nStep 6: Creating desktop shortcut...")
    
    try:
        import win32com.client
        
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "Arrow Limo App.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = python_exe
        shortcut.Arguments = f'-X utf8 "{app_script}"'
        shortcut.WorkingDirectory = str(install_dir)
        shortcut.Description = f"Arrow Limo App - Machine {machine_num}"
        shortcut.Save()
        
        log("  ✓ Desktop shortcut created")
    except Exception as e:
        log(f"  ⚠ Shortcut creation skipped: {e}")
    
    # Step 7: Test connection
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
            sslmode=os.getenv("DB_SSLMODE", "require"),
            connect_timeout=10
        )
        
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM public.charters")
        count = cur.fetchone()[0]
        
        log(f"  ✓ Connected to Neon database")
        log(f"  ✓ Verified: {count:,} charters available")
        
        cur.close()
        conn.close()
    except Exception as e:
        log(f"  ⚠ Connection test failed: {e}")
        log("  (Check your internet connection)")
    
    # Done!
    log("")
    log("=" * 70)
    log("  INSTALLATION COMPLETE! ✓")
    log("=" * 70)
    log("")
    log(f"Installation location: {install_dir}")
    log(f"Machine number: {machine_num}")
    log(f"Auto-start task: {task_name}")
    log("")
    log("Next steps:")
    log("  1. Log out completely and log back in")
    log("  2. App will start automatically (10-20 seconds)")
    log("  3. Or click desktop shortcut to start now")
    log("")
    
    input("Press Enter to exit...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
