#!/usr/bin/env python3
"""
Safe Script Wrapper - Automatically create backups before major operations

This wrapper ensures:
1. Full database backup BEFORE any major change script runs
2. Timestamped record of what script was run and when
3. Point-in-time recovery if something goes wrong

Usage Examples:
    python safe_script_wrapper.py import_payments.py --dry-run
    python safe_script_wrapper.py apply_migrations.py
    python safe_script_wrapper.py bulk_update_vendor_names.py --write

The wrapper will:
1. Create a backup before the script runs
2. Run the script
3. Log the result with the backup timestamp
4. Allow quick rollback with: backup_and_rollback.py --restore <timestamp>
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import json

SCRIPTS_DIR = Path(r"l:\limo\scripts")
BACKUP_WRAPPER_LOG = Path(r"l:\limo\backup_wrapper_log.json")

def load_operation_log():
    """Load previous operations log."""
    if BACKUP_WRAPPER_LOG.exists():
        with open(BACKUP_WRAPPER_LOG, 'r') as f:
            return json.load(f)
    return {"operations": []}

def save_operation_log(log):
    """Save operations log."""
    with open(BACKUP_WRAPPER_LOG, 'w') as f:
        json.dump(log, f, indent=2)

def create_backup():
    """Create backup before script execution."""
    print("\n" + "="*80)
    print("🔒 CREATING SAFETY BACKUP BEFORE SCRIPT EXECUTION")
    print("="*80)
    
    backup_script = SCRIPTS_DIR / "backup_and_rollback.py"
    result = subprocess.run(
        [sys.executable, str(backup_script), "--backup"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(result.stdout)
        # Extract timestamp from output
        for line in result.stdout.split('\n'):
            if "Timestamp:" in line:
                timestamp = line.split("Timestamp:")[-1].strip()
                return timestamp
    else:
        print(f"❌ Backup failed: {result.stderr}")
        return None

def run_safe_script(script_name, script_args):
    """
    Run script safely with backup.
    
    Args:
        script_name: Name of the script to run
        script_args: Arguments to pass to the script
    
    Returns:
        (success, backup_timestamp)
    """
    script_path = SCRIPTS_DIR / script_name
    
    if not script_path.exists():
        print(f"❌ Script not found: {script_path}")
        return False, None
    
    # Step 1: Create backup
    backup_timestamp = create_backup()
    if not backup_timestamp:
        print("❌ Cannot proceed without backup. Aborting.")
        return False, None
    
    # Step 2: Run script
    print("\n" + "="*80)
    print(f"🚀 RUNNING SCRIPT: {script_name}")
    print("="*80)
    print(f"Backup timestamp: {backup_timestamp}")
    print(f"Script: {script_path}")
    if script_args:
        print(f"Arguments: {' '.join(script_args)}")
    
    start_time = datetime.now()
    result = subprocess.run(
        [sys.executable, str(script_path)] + script_args,
        capture_output=True,
        text=True
    )
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    success = result.returncode == 0
    
    # Step 3: Log operation
    print("\n" + "="*80)
    print("📋 LOGGING OPERATION")
    print("="*80)
    
    log = load_operation_log()
    operation = {
        "timestamp": datetime.now().isoformat(),
        "script": script_name,
        "arguments": script_args,
        "backup_timestamp": backup_timestamp,
        "success": success,
        "exit_code": result.returncode,
        "duration_seconds": duration,
        "rollback_command": f"python backup_and_rollback.py --restore {backup_timestamp}"
    }
    log["operations"].append(operation)
    save_operation_log(log)
    
    print(f"✅ Operation logged")
    print(f"Script:           {script_name}")
    print(f"Status:           {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Duration:         {duration:.1f}s")
    print(f"Backup:           {backup_timestamp}")
    
    if not success:
        print(f"\n⚠️  Script failed! To rollback:")
        print(f"   python backup_and_rollback.py --restore {backup_timestamp}")
    
    return success, backup_timestamp

def main():
    if len(sys.argv) < 2:
        print("""
Safe Script Wrapper - Automatic Backup Before Major Operations

Usage:
    python safe_script_wrapper.py <script_name> [args...]

Examples:
    python safe_script_wrapper.py import_payments.py --dry-run
    python safe_script_wrapper.py apply_migrations.py
    python safe_script_wrapper.py bulk_update_vendor_names.py --write

The wrapper will automatically:
1. Create a full database backup BEFORE running the script
2. Run the script with provided arguments
3. Log the operation with backup timestamp
4. Provide rollback command if needed

If script fails, rollback with:
    python backup_and_rollback.py --restore <timestamp>
        """)
        return
    
    script_name = sys.argv[1]
    script_args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    success, backup_timestamp = run_safe_script(script_name, script_args)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
