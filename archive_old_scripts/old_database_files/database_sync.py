# ═══════════════════════════════════════════════════════════════════════════
# DATABASE SYNC SCRIPT - Sync Between Local PostgreSQL and Neon Cloud
# Use this to keep local and cloud databases in sync
# ═══════════════════════════════════════════════════════════════════════════

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values

# ANSI color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

BASE_DIR = Path(__file__).parent
ENV_LOCAL = BASE_DIR / ".env.local"
ENV_CLOUD = BASE_DIR / ".env.cloud"

def print_header():
    """Display sync header"""
    print()
    print("═" * 79)
    print(f"{CYAN}{BOLD}  ARROW LIMOUSINE - DATABASE SYNC UTILITY{RESET}")
    print(f"{CYAN}  Sync between Local PostgreSQL and Neon Cloud{RESET}")
    print("═" * 79)
    print()

def load_config(env_file):
    """Load database configuration from .env file"""
    if not env_file.exists():
        print(f"{RED}✗ ERROR: {env_file} not found{RESET}")
        return None
    
    config = dotenv_values(env_file)
    return {
        'host': config.get('DB_HOST'),
        'port': config.get('DB_PORT', '5432'),
        'database': config.get('DB_NAME'),
        'user': config.get('DB_USER'),
        'password': config.get('DB_PASSWORD')
    }

def create_backup(config, label):
    """Create backup of database"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    backup_file = backup_dir / f"backup_{label}_{timestamp}.sql"
    
    print(f"{YELLOW}→{RESET} Creating backup: {backup_file.name}")
    
    # Set PGPASSWORD environment variable
    env = os.environ.copy()
    env['PGPASSWORD'] = config['password']
    
    # pg_dump command
    cmd = [
        'pg_dump',
        '-h', config['host'],
        '-p', config['port'],
        '-U', config['user'],
        '-d', config['database'],
        '-F', 'c',  # Custom format (compressed)
        '-f', str(backup_file)
    ]
    
    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        print(f"{GREEN}✓{RESET} Backup created: {backup_file}")
        return backup_file
    except subprocess.CalledProcessError as e:
        print(f"{RED}✗{RESET} Backup failed: {e.stderr}")
        return None
    except FileNotFoundError:
        print(f"{RED}✗{RESET} pg_dump not found. Install PostgreSQL client tools.")
        return None

def restore_backup(config, backup_file, label):
    """Restore backup to database"""
    print(f"{YELLOW}→{RESET} Restoring to {label} database...")
    
    # Set PGPASSWORD environment variable
    env = os.environ.copy()
    env['PGPASSWORD'] = config['password']
    
    # pg_restore command
    cmd = [
        'pg_restore',
        '-h', config['host'],
        '-p', config['port'],
        '-U', config['user'],
        '-d', config['database'],
        '--clean',  # Drop existing objects first
        '--if-exists',  # Don't error if objects don't exist
        '-j', '4',  # Use 4 parallel jobs
        str(backup_file)
    ]
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        # pg_restore may have warnings, don't fail on non-zero exit for warnings
        if result.returncode != 0 and "error" in result.stderr.lower():
            print(f"{RED}✗{RESET} Restore had errors: {result.stderr}")
            return False
        print(f"{GREEN}✓{RESET} Restore completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{RED}✗{RESET} Restore failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"{RED}✗{RESET} pg_restore not found. Install PostgreSQL client tools.")
        return False

def sync_local_to_cloud():
    """Sync local PostgreSQL to Neon cloud"""
    print()
    print("═" * 79)
    print(f"{CYAN}  SYNC: Local PostgreSQL → Neon Cloud{RESET}")
    print("═" * 79)
    print()
    print(f"{YELLOW}⚠{RESET}  This will OVERWRITE the cloud database with local data!")
    print()
    
    response = input("Continue? (type 'yes' to confirm): ")
    if response.lower() != 'yes':
        print("Cancelled by user")
        return False
    
    # Load configurations
    local_config = load_config(ENV_LOCAL)
    cloud_config = load_config(ENV_CLOUD)
    
    if not local_config or not cloud_config:
        return False
    
    # Create backup of local database
    backup_file = create_backup(local_config, "local")
    if not backup_file:
        return False
    
    # Create backup of cloud database (safety)
    print()
    create_backup(cloud_config, "cloud_before_sync")
    
    # Restore local backup to cloud
    print()
    success = restore_backup(cloud_config, backup_file, "cloud")
    
    if success:
        print()
        print(f"{GREEN}✓ Sync complete: Local → Cloud{RESET}")
        print(f"  Cloud database now matches local database")
        return True
    else:
        print()
        print(f"{RED}✗ Sync failed{RESET}")
        return False

def sync_cloud_to_local():
    """Sync Neon cloud to local PostgreSQL"""
    print()
    print("═" * 79)
    print(f"{CYAN}  SYNC: Neon Cloud → Local PostgreSQL{RESET}")
    print("═" * 79)
    print()
    print(f"{YELLOW}⚠{RESET}  This will OVERWRITE the local database with cloud data!")
    print()
    
    response = input("Continue? (type 'yes' to confirm): ")
    if response.lower() != 'yes':
        print("Cancelled by user")
        return False
    
    # Load configurations
    local_config = load_config(ENV_LOCAL)
    cloud_config = load_config(ENV_CLOUD)
    
    if not local_config or not cloud_config:
        return False
    
    # Create backup of cloud database
    backup_file = create_backup(cloud_config, "cloud")
    if not backup_file:
        return False
    
    # Create backup of local database (safety)
    print()
    create_backup(local_config, "local_before_sync")
    
    # Restore cloud backup to local
    print()
    success = restore_backup(local_config, backup_file, "local")
    
    if success:
        print()
        print(f"{GREEN}✓ Sync complete: Cloud → Local{RESET}")
        print(f"  Local database now matches cloud database")
        return True
    else:
        print()
        print(f"{RED}✗ Sync failed{RESET}")
        return False

def backup_both():
    """Create backups of both databases"""
    print()
    print("═" * 79)
    print(f"{CYAN}  BACKUP: Both Databases{RESET}")
    print("═" * 79)
    print()
    
    # Load configurations
    local_config = load_config(ENV_LOCAL)
    cloud_config = load_config(ENV_CLOUD)
    
    if not local_config or not cloud_config:
        return False
    
    # Backup local
    local_backup = create_backup(local_config, "local")
    print()
    
    # Backup cloud
    cloud_backup = create_backup(cloud_config, "cloud")
    print()
    
    if local_backup and cloud_backup:
        print(f"{GREEN}✓ Both databases backed up successfully{RESET}")
        return True
    else:
        print(f"{RED}✗ Some backups failed{RESET}")
        return False

def show_menu():
    """Display sync menu"""
    print()
    print("What would you like to do?")
    print()
    print(f"  {CYAN}1{RESET}. Sync Local → Cloud (upload office data to cloud)")
    print(f"  {CYAN}2{RESET}. Sync Cloud → Local (download cloud data to office)")
    print(f"  {CYAN}3{RESET}. Backup Both Databases (safety backup)")
    print(f"  {CYAN}4{RESET}. Exit")
    print()

def main():
    """Main sync utility"""
    print_header()
    
    # Check for PostgreSQL tools
    try:
        subprocess.run(['pg_dump', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{RED}✗ ERROR: PostgreSQL client tools not found{RESET}")
        print()
        print("Please install PostgreSQL client tools:")
        print("  • Windows: Install PostgreSQL from postgresql.org")
        print("  • The installer includes pg_dump and pg_restore")
        print()
        input("Press Enter to exit...")
        sys.exit(1)
    
    while True:
        show_menu()
        
        choice = input("Enter choice (1-4): ").strip()
        
        if choice == '1':
            sync_local_to_cloud()
        elif choice == '2':
            sync_cloud_to_local()
        elif choice == '3':
            backup_both()
        elif choice == '4':
            print()
            print("Goodbye!")
            break
        else:
            print(f"{YELLOW}Invalid choice. Please enter 1-4.{RESET}")
        
        if choice in ['1', '2', '3']:
            print()
            input("Press Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Cancelled by user{RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}✗ Unexpected error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
