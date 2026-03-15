#!/usr/bin/env python3
"""
Arrow Limousine Management System - Dispatch Workstation
Simple launcher for dispatch computers
NETWORK DEPLOYMENT: Works from UNC paths (\\\\Dispatch1\\Y\\ArrowLimo)
"""
import os
import sys
from pathlib import Path

# Determine script location (works on network shares and local drives)
# __file__ gives us the launcher.py location
script_dir = Path(__file__).parent.resolve()

# Load environment variables from .env in same directory as launcher
env_file = script_dir / ".env"
if env_file.exists():
    print(f"Loading config from: {env_file}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
else:
    print(f"WARNING: No .env file found at {env_file}")
    print("  Using default/existing environment variables")

print("=" * 60)
print("  ARROW LIMOUSINE MANAGEMENT SYSTEM")
print("  Dispatch Workstation")
print(f"  Location: {script_dir}")
print("=" * 60)
print()

# Check database connection
print("[1/3] Checking database connection...")
try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', '5432'),
        sslmode=os.environ.get('DB_SSLMODE', 'require')
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM charters')
    count = cur.fetchone()[0]
    print(f"      [OK] Connected! Database has {count} charters")
    conn.close()
except ImportError:
    print("      [ERROR] psycopg2 not installed")
    print("      Run: pip install psycopg2-binary")
    sys.exit(1)
except Exception as e:
    print(f"      [ERROR] Database connection failed: {e}")
    sys.exit(1)

# Check Z: drive
print()
print("[2/3] Checking file storage...")
file_storage = os.environ.get('FILE_STORAGE_ROOT', 'Z:/limo_files')
z_drive = Path("Z:/limo_files")
network_path = Path(file_storage.replace('/', '\\'))

if z_drive.exists():
    print(f"      [OK] Z: drive accessible")
elif network_path.exists():
    print(f"      [OK] Network storage accessible: {file_storage}")
else:
    print(f"      [WARNING] File storage not accessible")
    print(f"      Expected: {file_storage}")
    print(f"      App will work, but file uploads may fail")

# Launch main application
print()
print("[3/3] Starting application...")
print()

# Check if main.py exists in desktop_app subdirectory
desktop_app = script_dir / "desktop_app"
main_py = desktop_app / "main.py"

if main_py.exists():
    print(f"Launching from: {main_py}")
    print()
    # Change to desktop_app directory so relative imports work
    os.chdir(str(desktop_app))
    # Execute main.py in current Python process
    exec(open(str(main_py)).read())
else:
    print("=" * 60)
    print("ERROR: Desktop application not found!")
    print("=" * 60)
    print()
    print(f"Expected location: {main_py}")
    print(f"Current directory: {script_dir}")
    print()
    print("DEPLOYMENT CHECKLIST:")
    print("1. Ensure desktop_app folder exists")
    print("2. Verify main.py is in desktop_app/")
    print("3. Check network path permissions")
    print()
    input("Press Enter to exit...")
