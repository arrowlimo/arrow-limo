# ═══════════════════════════════════════════════════════════════════════════
# HYBRID SMART LAUNCHER - Auto-Detects Network Location
# Automatically uses local PostgreSQL when in office, cloud when remote
# ═══════════════════════════════════════════════════════════════════════════

import os
import sys
import socket
import subprocess
import shutil
from pathlib import Path

# Configuration
DISPATCHMAIN_IP = "192.168.1.106"  # DISPATCHMAIN IP address
DISPATCHMAIN_HOSTNAME = "DISPATCHMAIN"
POSTGRES_PORT = 5432
TIMEOUT_SECONDS = 2

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
ENV_LOCAL = BASE_DIR / ".env.local"
ENV_CLOUD = BASE_DIR / ".env.cloud"

def print_header():
    """Display startup header"""
    print("═" * 79)
    print("  ARROW LIMOUSINE DISPATCH - HYBRID SMART LAUNCHER")
    print("  Auto-detecting network location...")
    print("═" * 79)
    print()

def test_local_network():
    """Test if we can reach DISPATCHMAIN on local network"""
    print("→ Testing local network connectivity...")
    
    # Try hostname first
    try:
        socket.gethostbyname(DISPATCHMAIN_HOSTNAME)
        print(f"  ✓ Resolved {DISPATCHMAIN_HOSTNAME}")
    except socket.gaierror:
        print(f"  ✗ Cannot resolve {DISPATCHMAIN_HOSTNAME}")
    
    # Try direct IP connection to PostgreSQL port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT_SECONDS)
        result = sock.connect_ex((DISPATCHMAIN_IP, POSTGRES_PORT))
        sock.close()
        
        if result == 0:
            print(f"  ✓ DISPATCHMAIN PostgreSQL reachable at {DISPATCHMAIN_IP}:{POSTGRES_PORT}")
            return True
        else:
            print(f"  ✗ Cannot reach {DISPATCHMAIN_IP}:{POSTGRES_PORT}")
            return False
    except Exception as e:
        print(f"  ✗ Network test failed: {e}")
        return False

def test_cloud_connectivity():
    """Test if we can reach Neon cloud database"""
    print("→ Testing cloud database connectivity...")
    
    try:
        # Read cloud config to get hostname
        if not ENV_CLOUD.exists():
            print("  ✗ Cloud configuration file not found")
            return False
        
        with open(ENV_CLOUD, 'r') as f:
            for line in f:
                if line.startswith('DB_HOST='):
                    cloud_host = line.split('=')[1].strip()
                    
                    # Try to resolve DNS
                    try:
                        socket.gethostbyname(cloud_host)
                        print(f"  ✓ Cloud database {cloud_host} is reachable")
                        return True
                    except socket.gaierror:
                        print(f"  ✗ Cannot resolve {cloud_host}")
                        return False
        
        return False
    except Exception as e:
        print(f"  ✗ Cloud test failed: {e}")
        return False

def switch_to_local():
    """Switch to local network PostgreSQL"""
    print()
    print("═" * 79)
    print("  📍 LOCATION: IN OFFICE")
    print("  🗄️  DATABASE: Local Network PostgreSQL (FAST)")
    print("═" * 79)
    print()
    
    if not ENV_LOCAL.exists():
        print("⚠️  ERROR: .env.local file not found!")
        print(f"   Expected: {ENV_LOCAL}")
        return False
    
    try:
        shutil.copy2(ENV_LOCAL, ENV_FILE)
        print("✓ Switched to LOCAL network database configuration")
        print(f"  Database: localhost (DISPATCHMAIN)")
        print(f"  Speed: 10-50x faster than cloud")
        print()
        return True
    except Exception as e:
        print(f"✗ Failed to switch configuration: {e}")
        return False

def switch_to_cloud():
    """Switch to cloud database (Neon)"""
    print()
    print("═" * 79)
    print("  📍 LOCATION: OFF-SITE / REMOTE")
    print("  ☁️  DATABASE: Neon Cloud PostgreSQL")
    print("═" * 79)
    print()
    
    if not ENV_CLOUD.exists():
        print("⚠️  ERROR: .env.cloud file not found!")
        print(f"   Expected: {ENV_CLOUD}")
        return False
    
    try:
        shutil.copy2(ENV_CLOUD, ENV_FILE)
        print("✓ Switched to CLOUD database configuration")
        print(f"  Database: Neon cloud (internet connection)")
        print(f"  Note: Slower than local, but accessible anywhere")
        print()
        return True
    except Exception as e:
        print(f"✗ Failed to switch configuration: {e}")
        return False

def launch_application():
    """Launch the main application"""
    print("→ Launching Arrow Limousine application...")
    print()
    
    launcher_path = BASE_DIR / "desktop_app" / "main.py"
    
    if not launcher_path.exists():
        print(f"✗ ERROR: Main application not found at {launcher_path}")
        return False
    
    try:
        # Launch the actual application
        os.chdir(BASE_DIR / "desktop_app")
        subprocess.run([sys.executable, "main.py"])
        return True
    except Exception as e:
        print(f"✗ Failed to launch application: {e}")
        return False

def main():
    """Main smart launcher logic"""
    print_header()
    
    # Test local network first (preferred)
    local_available = test_local_network()
    
    if local_available:
        # In office - use local database
        if switch_to_local():
            launch_application()
        else:
            print("✗ Failed to configure local database")
            sys.exit(1)
    else:
        # Off-site - check cloud availability
        print()
        print("ℹ️  Local network not available - checking cloud database...")
        print()
        
        cloud_available = test_cloud_connectivity()
        
        if cloud_available:
            # Use cloud database
            if switch_to_cloud():
                launch_application()
            else:
                print("✗ Failed to configure cloud database")
                sys.exit(1)
        else:
            # Neither available
            print()
            print("═" * 79)
            print("  ✗ ERROR: No Database Connection Available")
            print("═" * 79)
            print()
            print("Cannot reach local network or cloud database.")
            print()
            print("Troubleshooting:")
            print(f"  • Make sure you're on office network (WiFi/ethernet)")
            print(f"  • OR have internet connection for cloud database")
            print(f"  • Check DISPATCHMAIN is powered on")
            print(f"  • Verify network cables/WiFi connection")
            print()
            input("Press Enter to exit...")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nℹ️  Application cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
