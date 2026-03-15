"""
Auto-save session work to prevent data loss from VS Code chat crashes.

This script should be run CONTINUOUSLY in a background terminal during data entry sessions.
It monitors the verification markdown file and creates timestamped backups every time changes are detected.

Usage:
    # Run in a separate PowerShell terminal (keeps running)
    python scripts/auto_save_session_work.py

    # Specify custom watch file
    python scripts/auto_save_session_work.py --watch-file reports/custom_file.md

Features:
    - Monitors file for changes every 30 seconds
    - Creates timestamped backups in reports/auto_backups/
    - Keeps last 50 backups (auto-rotates old ones)
    - Runs continuously until Ctrl-C
    - Safe to run multiple times (won't conflict)
"""
import os
import sys
import time
import shutil
import hashlib
from datetime import datetime
from pathlib import Path

DEFAULT_WATCH_FILE = r'l:\limo\reports\2012_cibc_complete_running_balance_verification.md'
BACKUP_DIR = r'l:\limo\reports\auto_backups'
CHECK_INTERVAL = 30  # seconds
MAX_BACKUPS = 50  # Keep last 50 backups


def get_file_hash(filepath):
    """Calculate SHA256 hash of file contents."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        print(f"Error reading file: {e}")
        return None


def create_backup(filepath, backup_dir):
    """Create timestamped backup of file."""
    if not os.path.exists(filepath):
        return None
    
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = Path(filepath).stem
    extension = Path(filepath).suffix
    backup_name = f"{filename}_backup_{timestamp}{extension}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    try:
        shutil.copy2(filepath, backup_path)
        file_size = os.path.getsize(backup_path)
        print(f"[OK] Backup created: {backup_name} ({file_size:,} bytes)")
        return backup_path
    except Exception as e:
        print(f"[FAIL] Backup failed: {e}")
        return None


def rotate_old_backups(backup_dir, max_backups):
    """Remove oldest backups if exceeding max count."""
    if not os.path.exists(backup_dir):
        return
    
    backups = []
    for f in os.listdir(backup_dir):
        if f.endswith('.md'):
            filepath = os.path.join(backup_dir, f)
            backups.append((filepath, os.path.getmtime(filepath)))
    
    backups.sort(key=lambda x: x[1])  # Sort by modification time
    
    # Delete oldest backups
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        try:
            os.remove(oldest[0])
            print(f"🗑️  Rotated old backup: {Path(oldest[0]).name}")
        except Exception as e:
            print(f"[WARN]  Failed to remove {oldest[0]}: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Auto-save session work to prevent data loss')
    parser.add_argument('--watch-file', default=DEFAULT_WATCH_FILE, 
                       help='File to monitor for changes')
    parser.add_argument('--backup-dir', default=BACKUP_DIR,
                       help='Directory to store backups')
    parser.add_argument('--interval', type=int, default=CHECK_INTERVAL,
                       help='Check interval in seconds')
    args = parser.parse_args()
    
    watch_file = args.watch_file
    backup_dir = args.backup_dir
    check_interval = args.interval
    
    print("🛡️  AUTO-SAVE SESSION PROTECTION")
    print("=" * 70)
    print(f"Watching file: {watch_file}")
    print(f"Backup location: {backup_dir}")
    print(f"Check interval: {check_interval} seconds")
    print(f"Max backups: {MAX_BACKUPS}")
    print("=" * 70)
    print("\n[WARN]  LEAVE THIS RUNNING during your work session!")
    print("   Press Ctrl-C to stop when done.\n")
    
    if not os.path.exists(watch_file):
        print(f"[FAIL] Watch file not found: {watch_file}")
        print("   Creating empty file...")
        Path(watch_file).parent.mkdir(parents=True, exist_ok=True)
        Path(watch_file).touch()
    
    last_hash = None
    backup_count = 0
    
    try:
        while True:
            current_hash = get_file_hash(watch_file)
            
            if current_hash and current_hash != last_hash:
                # File changed - create backup
                backup_path = create_backup(watch_file, backup_dir)
                if backup_path:
                    backup_count += 1
                    last_hash = current_hash
                    rotate_old_backups(backup_dir, MAX_BACKUPS)
                    print(f"   Total backups this session: {backup_count}")
            
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Auto-save stopped by user")
        print(f"[OK] Created {backup_count} backup(s) this session")
        print(f"📁 Backups saved in: {backup_dir}")


if __name__ == '__main__':
    main()
